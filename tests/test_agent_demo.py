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


def test_general_question_without_service_is_a_valid_answer():
    # Screenshot reproduction: the model correctly supplied no matching service.
    args={'reply':'可以从 python.org 下载 macOS 安装包。','summary':'用户问如何安装 Python，并非定制需求。','questions':[],'service_ids':[]}
    result=compose_brief(args)
    assert result['mode']=='answer' and result['reply']==args['reply']
    assert result['draft']=='' and result['sources']==[]
    args['summary']=''
    assert compose_brief(args)['mode']=='answer'


def test_general_answer_completion_protocol(tmp_path):
    root=fixture(tmp_path)
    args={'reply':'安装后在终端运行 python3 --version 检查。','summary':'','questions':[],'service_ids':[]}
    event={'type':'response.completed','response':{'status':'completed','output':[{'type':'function_call','name':'compose_brief','arguments':json.dumps(args)}],'usage':{'total_tokens':20}}}
    result=asyncio.run(run_demo(root,{'uid':'b'*32,'messages':[{'role':'user','content':'python怎么在mac上安装'}]},httpx.MockTransport(lambda r:httpx.Response(200,text='data: '+json.dumps(event)+'\n\n'))))
    assert result['mode']=='answer' and result['submitted'] is False
    assert result['steps']==['已分析问题','已生成回答']
