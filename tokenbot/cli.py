import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
from .client import Client
from .queue import Queue
from .usage import summarize
from .economics import calculate


def save_private(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Refuse overwrite: submissions/receipts must not disappear on a second invocation.
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f: json.dump(data,f,ensure_ascii=False,indent=2)


def write_private_bytes(path, data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data)


def update_receipt(path, data):
    """Keep the last durable receipt if a process stops during a write."""
    p=Path(path)
    fd,tmp=tempfile.mkstemp(prefix='.receipt-',dir=p.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def main():
    p=argparse.ArgumentParser(description='TokenBot pilot operations; secrets come from environment only')
    s=p.add_subparsers(dest='command',required=True)
    for name in ('enqueue','work','metrics','recover','results'):
        q=s.add_parser(name);q.add_argument('--db',required=True)
        if name=='enqueue':q.add_argument('input')
        if name=='work':q.add_argument('--limit',type=int,default=1)
        if name=='recover':q.add_argument('--older-than',type=int,default=900)
        if name=='results':q.add_argument('--out',required=True)
    q=s.add_parser('cost');q.add_argument('metrics');q.add_argument('--pricing',required=True)
    s.add_parser('models')
    q=s.add_parser('economics');q.add_argument('input')
    q=s.add_parser('provider-batch-submit');q.add_argument('input');q.add_argument('--receipt',required=True);q.add_argument('--enabled',action='store_true')
    q=s.add_parser('provider-batch-status');q.add_argument('batch_id')
    q=s.add_parser('provider-batch-results');q.add_argument('file_id');q.add_argument('--out',required=True)
    q=s.add_parser('provider-batch-cancel');q.add_argument('batch_id');q.add_argument('--confirm',action='store_true')
    a=p.parse_args()
    try:
        if a.command=='economics':
            print(json.dumps(calculate(json.loads(Path(a.input).read_text())),ensure_ascii=False,indent=2));return
        if a.command=='models':
            status,_,raw=Client.from_env().request('GET','/models')
            if status!=200:raise ValueError('Model list failed; HTTP '+str(status))
            print(json.dumps({'models':[x['id'] for x in json.loads(raw)['data']]},ensure_ascii=False));return
        if a.command=='cost':
            print(json.dumps(summarize(json.loads(Path(a.metrics).read_text()),json.loads(Path(a.pricing).read_text())),indent=2));return
        if a.command=='provider-batch-results':
            if not re.fullmatch(r'file[-_][A-Za-z0-9_-]+',a.file_id):raise ValueError('Invalid file ID')
            if Path(a.out).exists():raise ValueError('Output already exists')
            status,_,raw=Client.from_env().request('GET','/files/'+a.file_id+'/content')
            if status!=200:raise ValueError('File download failed; HTTP '+str(status))
            write_private_bytes(a.out,raw);print(json.dumps({'saved':a.out}));return
        if a.command in ('provider-batch-status','provider-batch-cancel'):
            if not re.fullmatch(r'batch_[A-Za-z0-9_-]+',a.batch_id): raise ValueError('Invalid batch ID')
            if a.command=='provider-batch-cancel' and not a.confirm:raise ValueError('Cancellation requires --confirm')
            method='POST' if a.command=='provider-batch-cancel' else 'GET'
            path='/batches/'+a.batch_id+('/cancel' if method=='POST' else '')
            status,_,raw=Client.from_env().request(method,path)
            if status!=200:raise ValueError('Batch status failed; HTTP '+str(status))
            data=json.loads(raw)
            print(json.dumps({k:data.get(k) for k in ('id','status','request_counts','output_file_id','error_file_id')},indent=2));return
        if a.command=='provider-batch-submit':
            # Explicit opt-in; do not infer native Batch support from Responses support.
            if not a.enabled: raise ValueError('Confirm provider/model Batch support, then pass --enabled')
            if Path(a.input).stat().st_size>10_000_000:raise ValueError('Pilot batch limit is 10 MB')
            lines=Path(a.input).read_text().splitlines();items=[json.loads(v) for v in lines if v.strip()]
            if not items: raise ValueError('Empty batch')
            for item in items:
                if not isinstance(item,dict):raise ValueError('Batch items must be objects')
                body=item.get('body');ident=item.get('custom_id')
                if (item.get('method')!='POST' or item.get('url')!='/v1/responses'
                    or not isinstance(ident,str) or not ident or len(ident)>128
                    or not isinstance(body,dict) or not isinstance(body.get('model'),str)
                    or not body['model'] or 'input' not in body):
                    raise ValueError('Require custom_id, POST /v1/responses, body.model and complete input')
                if body.get('previous_response_id') or body.get('conversation'):
                    raise ValueError('Batch requires self-contained input, no remote conversation IDs')
            if len({i['body']['model'] for i in items}) != 1: raise ValueError('Native batch requires exactly one model')
            if any(i['body'].get('stream') or i['body'].get('background') for i in items): raise ValueError('Batch cannot stream or run background responses')
            if len({i['custom_id'] for i in items})!=len(items):raise ValueError('Duplicate custom_id')
            save_private(a.receipt,{'state':'submission_started','note':'Do not resubmit without checking provider; no automatic retries.'})
            client=Client.from_env();boundary='TokenBot'+secrets.token_hex(16)
            body=(f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nbatch\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="batch.jsonl"\r\nContent-Type: application/jsonl\r\n\r\n'.encode()+('\n'.join(json.dumps(x) for x in items)+'\n').encode()+f'\r\n--{boundary}--\r\n'.encode())
            status,_,raw=client.request('POST','/files',body,'multipart/form-data; boundary='+boundary)
            receipt={'state':'upload_uncertain','http_status':status}
            if status in (200,201):
                file_id=json.loads(raw)['id'];receipt={'state':'uploaded','file_id':file_id}
                update_receipt(a.receipt,receipt)
                status,_,raw=client.request('POST','/batches',{'input_file_id':file_id,'endpoint':'/v1/responses','completion_window':'24h'})
                receipt.update(state='submission_uncertain',http_status=status)
                if status in (200,201):
                    data=json.loads(raw);receipt.update(state='submitted',batch_id=data['id'],status=data.get('status'))
            update_receipt(a.receipt,receipt)
            print(json.dumps(receipt))
            if receipt['state']!='submitted':sys.exit(1)
            return
        queue=Queue(a.db)
        if a.command=='enqueue': print(json.dumps({'added':queue.enqueue([json.loads(v) for v in Path(a.input).read_text().splitlines() if v.strip()])}))
        elif a.command=='work':
            if not 1<=a.limit<=1000:raise ValueError('limit must be 1..1000')
            client=Client.from_env();count=0
            while count<a.limit and queue.run_one(client):count+=1
            print(json.dumps({'processed':count,'note':'429 jobs wait until retry time; rerun work later. Uncertain jobs never auto-replay.'}))
        elif a.command=='metrics':print(json.dumps(queue.metrics(),ensure_ascii=False,indent=2))
        elif a.command=='recover':print(json.dumps({'marked_uncertain':queue.recover(a.older_than)}))
        elif a.command=='results':
            save_private(a.out,[{'custom_id':r['id'],'status':r['status'],'response':json.loads(r['result']) if r['result'] else None} for r in queue.db.execute('SELECT id,status,result FROM jobs')])
    except (ValueError,KeyError,OSError) as e:
        # Never print raw upstream errors or URL/request objects, which may contain secrets.
        print('Operation failed: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);sys.exit(1)

if __name__=='__main__':main()
