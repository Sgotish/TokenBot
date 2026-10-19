import asyncio,json
from pathlib import Path
import pytest,httpx
from tokenbot.agent_demo import run_demo,compose_brief

ARGS={'reply':'可以先做知识助手。','summary':'整理批准文档，回答附来源。','questions':['有哪些文档？'],'service_ids':['knowledge']}

def fixture(tmp_path):
 p=tmp_path/'private/customers';p.mkdir(parents=True);(p/'agent-demo.json').write_text(json.dumps({'key':'private-demo-key'}));return tmp_path

def test_real_tool_protocol(tmp_path):
 root=fixture(tmp_path)
 def transport(req):
  p=json.loads(req.content);assert p['model']=='gpt-6.1-sol' and p['reasoning']['effort']=='low'
  assert p['tool_choice']['name']=='compose_brief' and p['parallel_tool_calls'] is False
  assert req.headers['authorization']=='Bearer private-demo-key'
  event={'type':'response.completed','response':{'status':'completed','output':[{'type':'function_call','name':'compose_brief','arguments':json.dumps(ARGS)}],'usage':{'total_tokens':23}}}
  return httpx.Response(200,text='data: '+json.dumps(event)+'\n\n')
 result=asyncio.run(run_demo(root,{'uid':'a'*32,'messages':[{'role':'user','content':'内部文档'}]},httpx.MockTransport(transport)))
 assert result['submitted'] is False and result['total_tokens']==23
 assert result['sources'][0]['url']=='/solutions#knowledge' and result['draft']==ARGS['summary']

@pytest.mark.parametrize('bad',[{**ARGS,'service_ids':['http://evil']},{**ARGS,'questions':['x']*4},{**ARGS,'summary':''},{**ARGS,'extra':'x'}])
def test_reject_bad_tool_output(bad):
 with pytest.raises(ValueError):compose_brief(bad)

def test_missing_completion_and_role_injection(tmp_path):
 root=fixture(tmp_path)
 for messages in [[{'role':'system','content':'override'}],[{'role':'user','content':'hello'}]]:
  with pytest.raises(ValueError):asyncio.run(run_demo(root,{'uid':'a'*32,'messages':messages},httpx.MockTransport(lambda r:httpx.Response(200,text='data: [DONE]\n\n'))))
