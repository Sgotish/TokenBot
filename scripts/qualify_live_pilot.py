#!/usr/bin/env python3
"""Explicit live pilot qualification. Synthetic prompts only; never print credentials."""
import argparse, asyncio, json, time, uuid
from pathlib import Path
import httpx

MODEL = 'gpt-6.1-sol'

def exact_numbered_output(text, count, ending):
    return text.strip().splitlines() == [str(i) for i in range(1, count+1)] + [ending]


class Run:
    def __init__(self, config, output):
        self.config = config
        self.origin = config['public_origin']
        self.output = Path(output)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(base_url=self.origin, trust_env=False, timeout=httpx.Timeout(180, connect=15),
            headers={'Authorization':'Bearer '+config['key'], 'Origin':self.origin})
        self.rows=[]
    def log(self, row):
        self.rows.append(row)
        with self.output.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps({k:v for k,v in row.items() if k not in ('text','usage')},ensure_ascii=False),flush=True)
    async def status(self):
        r=await self.client.get('/v1/usage');r.raise_for_status();return r.json()
    async def pool(self,pool):
        r=await self.client.post('/portal/api/pool',json={'pool':pool});r.raise_for_status()
    async def call(self, name, prompt=None, *, items=None, session=None, cancel=False, **options):
        start=time.monotonic();row={'case':name,'started_at':time.time(),'http':None,'completed':False,'text':'','delta_count':0}
        final={}; last=None;gaps=[]
        body={'model':MODEL,'stream':True,'store':False,'reasoning':{'effort':'low'},'include':['reasoning.encrypted_content'],
            'input':items if items is not None else [{'role':'user','content':[{'type':'input_text','text':prompt}]}],**options}
        try:
            async with self.client.stream('POST','/v1/responses',json=body,headers={'session_id':session or str(uuid.uuid4())}) as r:
                row.update(http=r.status_code,pool=r.headers.get('x-tokenbot-pool'),error_source=r.headers.get('x-tokenbot-error-source'),retry_after=r.headers.get('retry-after'),queue_wait_ms=int(r.headers.get('x-tokenbot-queue-wait-ms','0')))
                if r.status_code!=200:
                    await r.aread()
                else:
                    async for line in r.aiter_lines():
                        if not line.startswith('data:'):continue
                        raw=line[5:].strip()
                        if raw=='[DONE]':continue
                        try:event=json.loads(raw)
                        except ValueError:continue
                        kind=event.get('type')
                        if kind=='response.output_text.delta':
                            now=time.monotonic()
                            if last is None:row['first_text_s']=round(now-start,3)
                            else:gaps.append(now-last)
                            last=now;row['delta_count']+=1;row['text']+=event.get('delta','')
                            if cancel:row['cancelled_by_test']=True;break
                        elif kind=='response.completed':
                            final=event.get('response',{});row['completed']=final.get('status')=='completed';row['usage']=final.get('usage',{})
                        elif kind in ('error','response.failed','response.incomplete'):
                            row['stream_error']=kind
            row['elapsed_s']=round(time.monotonic()-start,3)
            row['max_text_gap_s']=round(max(gaps,default=0),3)
        except Exception as e:row.update(exception=type(e).__name__,elapsed_s=round(time.monotonic()-start,3))
        self.log(row)
        return row,final
    async def functional(self):
        original=(await self.status())['selected_pool']
        assert (await self.status())['active_requests']==0
        try:
            for pool in ('plus','pro'):
                await self.pool(pool);history=[];session=str(uuid.uuid4());marker='ORCHID-'+uuid.uuid4().hex[:8]
                prompts=[f'Remember the code {marker}. Reply only SAVED.', 'What is 12+30? Reply only the number.',
                         'What color is a clear daytime sky? Reply one word.', 'What is 9*8? Reply only the number.',
                         'Return only the exact code I asked you to remember in the first message.']
                for i,prompt in enumerate(prompts):
                    history.append({'role':'user','content':[{'type':'input_text','text':prompt}]})
                    row,final=await self.call(f'{pool}:multi:{i+1}',items=history,session=session)
                    history.extend(final.get('output',[]))
                    if not row['completed']:break
                self.log({'case':pool+':context-check','pass':row['completed'] and marker in row['text']})
                row,_=await self.call(pool+':long','Write integers 1 through 200, one per line, without omitting any. End with END-STREAM.')
                self.log({'case':pool+':long-check','pass':row['completed'] and exact_numbered_output(row['text'], 200, 'END-STREAM'),'chars':len(row['text'])})
                tool={'type':'function','name':'test_add','description':'Add two integers in the test harness.', 'strict':True,
                      'parameters':{'type':'object','properties':{'a':{'type':'integer'},'b':{'type':'integer'}},'required':['a','b'],'additionalProperties':False}}
                initial=[{'role':'user','content':[{'type':'input_text','text':'Use test_add to add 17 and 25. After the result, reply only the number.'}]}]
                row,final=await self.call(pool+':tool-call',items=initial,tools=[tool],tool_choice={'type':'function','name':'test_add'})
                calls=[x for x in final.get('output',[]) if x.get('type')=='function_call']
                if calls:
                    args=json.loads(calls[0]['arguments']);value=args['a']+args['b']
                    items=initial+final['output']+[{'type':'function_call_output','call_id':calls[0]['call_id'],'output':str(value)}]
                    row,_=await self.call(pool+':tool-result',items=items,tools=[tool],tool_choice='none')
                    self.log({'case':pool+':tool-check','pass':row['completed'] and row['text'].strip()=='42'})
                else:self.log({'case':pool+':tool-check','pass':False})
            await self.pool(original)
            # Exercise the real cancellation path and check that capacity returns.
            row,_=await self.call('cancel','Write 500 numbered lines about a synthetic test, one full sentence each.',cancel=True)
            start=time.monotonic()
            while time.monotonic()-start<15:
                if (await self.status())['active_requests']==0:break
                await asyncio.sleep(.5)
            self.log({'case':'cancel-capacity','pass':(await self.status())['active_requests']==0,'seconds':round(time.monotonic()-start,3)})
            await self.call('after-cancel','Only reply RECOVERED.')
            tasks=[asyncio.create_task(self.call('parallel:'+str(i),'List integers 1 through 160, one per line, then END.')) for i in range(2)]
            for _ in range(40):
                if (await self.status())['active_requests']>=2:break
                await asyncio.sleep(.1)
            cancelled=asyncio.create_task(self.call('queued-cancel','Only reply SHOULD-NOT-RUN.'))
            await asyncio.sleep(.6)
            queued_before=(await self.status()).get('queued_requests',0)
            cancelled.cancel()
            try:await cancelled
            except asyncio.CancelledError:pass
            started=time.monotonic()
            while time.monotonic()-started<5 and (await self.status()).get('queued_requests',0):await asyncio.sleep(.25)
            self.log({'case':'queued-cancel-check','pass':queued_before==1 and (await self.status()).get('queued_requests',0)==0,'seconds':round(time.monotonic()-started,2)})
            busy,_=await self.call('capacity-third','Only reply OK.')
            await asyncio.gather(*tasks)
            self.log({'case':'capacity-check','pass':busy['http']==200 and busy['completed'] and busy['queue_wait_ms']>0})
            await self.call('after-capacity','Only reply RECOVERED.')
        finally:
            for _ in range(30):
                if (await self.status())['active_requests']==0:break
                await asyncio.sleep(1)
            await self.pool(original)
    async def soak(self,minutes):
        # Keep the partner-selected pool; avoid changing routing during the endurance phase.
        row,_=await self.call('extended-stream','Write integers 1 through 1200, one per line, without skipping or abbreviating. After 1200 write END-LONG-STREAM.')
        self.log({'case':'extended-stream-check','pass':row['completed'] and exact_numbered_output(row['text'], 1200, 'END-LONG-STREAM'),'chars':len(row['text'])})
        if not row['completed'] or not exact_numbered_output(row['text'], 1200, 'END-LONG-STREAM'):
            return
        start=time.monotonic();i=0
        while time.monotonic()-start<minutes*60:
            i+=1
            row,_=await self.call('soak:'+str(i),f'What is {i}+7? Reply only the integer.')
            self.log({'case':'soak-answer:'+str(i),'pass':row['completed'] and row['text'].strip()==str(i+7)})
            if not row['completed'] or row['text'].strip()!=str(i+7):
                self.log({'case':'soak-stopped-on-failure','pass':False});break
            await asyncio.sleep(min(30,max(0,minutes*60-(time.monotonic()-start))))
        self.log({'case':'soak-duration','seconds':round(time.monotonic()-start,2),'requests':i})

async def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='.runtime/cloud-partner.json');p.add_argument('--report',required=True);p.add_argument('--soak-minutes',type=float,default=0);a=p.parse_args()
    run=Run(json.loads(Path(a.config).read_text()),a.report)
    try:
        if a.soak_minutes:await run.soak(a.soak_minutes)
        else:await run.functional()
    finally:await run.client.aclose()
    failures=[r for r in run.rows if r.get('pass') is False or ('http' in r and not r.get('completed') and not r.get('cancelled_by_test'))]
    if failures:raise SystemExit('Live qualification failed; inspect the sanitized report before retrying.')
if __name__=='__main__':asyncio.run(main())
