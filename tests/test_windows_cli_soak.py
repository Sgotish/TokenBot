import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('soak', Path(__file__).parents[1]/'scripts/windows_cli_soak.py')
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)

def test_completion_and_exact_answer_required():
    answer = {'type':'item.completed','item':{'type':'agent_message','text':'42'}}
    done = {'type':'turn.completed','usage':{'output_tokens':5}}
    assert soak.assess([answer,done], '42', 0)['pass']
    assert not soak.assess([answer], '42', 0)['pass']
    assert not soak.assess([answer,done], '43', 0)['pass']
    assert not soak.assess([answer,done], '42', 1)['pass']
    assert not soak.assess([answer,done,{'type':'error'}], '42', 0)['pass']
    assert not soak.assess([answer,done,done], '42', 0)['pass']
