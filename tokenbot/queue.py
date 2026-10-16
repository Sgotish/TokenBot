"""Durable serial client-side batch queue, NOT a provider discounted Batch API.
Each item contains a complete context. Unknown delivery outcomes require review.
"""
import hashlib
import math
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import sqlite3
import time
from .usage import normalize

SCHEMA='''CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, model TEXT NOT NULL, body TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
 available_at REAL NOT NULL DEFAULT 0, http_status INTEGER, usage TEXT, result TEXT,
 updated_at REAL NOT NULL, created_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);'''

class Queue:
    def __init__(self,path):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(p,os.O_WRONLY|os.O_CREAT,0o600);os.close(fd)
        p.chmod(0o600)
        self.db=sqlite3.connect(p,timeout=10,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.executescript(SCHEMA)

    def enqueue(self,items):
        # Validate all items before making changes, and import atomically.
        prepared=[];seen=set()
        for item in items:
            ident=item['custom_id'];body=item['body']
            if not isinstance(ident,str) or not ident or len(ident)>128 or ident in seen:
                raise ValueError('custom_id must be unique, nonempty, <=128 characters')
            seen.add(ident)
            if item.get('url','/v1/responses')!='/v1/responses' or item.get('method','POST')!='POST':
                raise ValueError('Local batch supports POST /v1/responses only')
            if not isinstance(body,dict) or not isinstance(body.get('model'),str) or not body['model'] or 'input' not in body:
                raise ValueError('Each item needs model and complete input')
            if body.get('stream') or body.get('background') or body.get('previous_response_id') or body.get('conversation'):
                raise ValueError('Batch requires self-contained non-streaming requests, no remote conversation IDs')
            raw=json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False)
            prepared.append((ident,hashlib.sha256(raw.encode()).hexdigest(),body['model'],raw))
        self.db.execute('BEGIN IMMEDIATE')
        added=0
        try:
            for ident,digest,model,raw in prepared:
                old=self.db.execute('SELECT fingerprint FROM jobs WHERE id=?',(ident,)).fetchone()
                if old:
                    if old[0]!=digest: raise ValueError('Existing custom_id has different content')
                    continue
                now=time.time()
                self.db.execute('INSERT INTO jobs(id,fingerprint,model,body,updated_at,created_at) VALUES(?,?,?,?,?,?)',(ident,digest,model,raw,now,now));added+=1
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
        return added

    def bind_target(self,client):
        # Prevent accidentally resuming jobs on a different endpoint or customer key.
        target=hashlib.sha256((client.base+'\0'+client.key).encode()).hexdigest()
        self.db.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)',('target',target))
        if self.db.execute('SELECT value FROM metadata WHERE key=?',('target',)).fetchone()[0]!=target:
            raise ValueError('Queue is bound to a different endpoint/key; use a separate database')

    def claim(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute("SELECT * FROM jobs WHERE status='queued' AND available_at<=? ORDER BY created_at,id LIMIT 1",(time.time(),)).fetchone()
            if row:
                self.db.execute("UPDATE jobs SET status='running',attempts=attempts+1,updated_at=? WHERE id=?",(time.time(),row['id']))
            self.db.execute('COMMIT');return row
        except BaseException:
            self.db.execute('ROLLBACK');raise

    def run_one(self,client):
        self.bind_target(client)
        row=self.claim()
        if row is None: return False
        status,headers,raw=client.request('POST','/responses',json.loads(row['body']))
        state='failed';usage=None;result=None;available=0
        if status==429 and row['attempts']<3:
            retry=next((v for k,v in headers.items() if k.lower()=='retry-after'),'30')
            try: delay=max(5,float(retry))
            except ValueError:
                try: delay=max(5, parsedate_to_datetime(retry).timestamp()-time.time())
                except (ValueError,TypeError,OverflowError): delay=30
            if not math.isfinite(delay): delay=30
            available=time.time()+delay;state='queued'
        elif status==0 or status>=500:
            state='uncertain'
        elif 200<=status<300:
            try:
                data=json.loads(raw)
                if not isinstance(data,dict): raise ValueError('Object expected')
                if data.get('error') is not None or data.get('status')=='failed':
                    state='failed'
                elif data.get('status')=='completed':
                    state='succeeded';result=json.dumps(data,ensure_ascii=False)
                    try: usage=normalize(data)
                    except (KeyError,ValueError,TypeError): usage=None
                else:
                    state='uncertain'
            except (ValueError,TypeError): state='uncertain'
        self.db.execute('UPDATE jobs SET status=?,http_status=?,usage=?,result=?,available_at=?,updated_at=? WHERE id=?',
                        (state,status,json.dumps(usage) if usage is not None else None,result,available,time.time(),row['id']))
        return True

    def metrics(self):
        # Does not export prompt, output, key, customer identity, or upstream error text.
        return [dict(id=r['id'],model=r['model'],status=r['status'],attempts=r['attempts'],http_status=r['http_status'],usage=json.loads(r['usage']) if r['usage'] else None)
                for r in self.db.execute('SELECT id,model,status,attempts,http_status,usage FROM jobs ORDER BY created_at,id')]

    def recover(self,seconds):
        if seconds<300: raise ValueError('Only jobs older than 300 seconds can be marked uncertain')
        return self.db.execute("UPDATE jobs SET status='uncertain',updated_at=? WHERE status='running' AND updated_at<?",(time.time(),time.time()-seconds)).rowcount
