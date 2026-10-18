"""Explicit user-facing Codex models; never silently map one model to another."""
MODEL_EFFORTS = {
    'gpt-6.1-sol': ('low', 'medium', 'high', 'xhigh', 'max', 'ultra'),
    'gpt-6-astra': ('low', 'medium', 'high', 'xhigh', 'max', 'ultra'),
    'gpt-6-sol': ('low', 'medium', 'high', 'xhigh', 'max', 'ultra'),
    'gpt-6-luna': ('low', 'medium', 'high', 'xhigh', 'max'),
    'gpt-5.6-sol': ('low', 'medium', 'high', 'xhigh', 'max', 'ultra'),
    'gpt-5.6-terra': ('low', 'medium', 'high', 'xhigh', 'max', 'ultra'),
    'gpt-5.6-luna': ('low', 'medium', 'high', 'xhigh', 'max'),
}


def discovery():
    return {'object': 'list', 'data': [
        {'id': model, 'object': 'model', 'owned_by': 'subscription-pilot',
         'supported_reasoning_efforts': [e for e in efforts if e != 'ultra'],
         'client_reasoning_efforts': list(efforts)}
        for model, efforts in MODEL_EFFORTS.items()
    ]}


def validate_selection(data):
    if not isinstance(data, dict) or not isinstance(data.get('model'), str) or data['model'] not in MODEL_EFFORTS:
        return 'Model unavailable; choose a model returned by /v1/models'
    reasoning = data.get('reasoning')
    if reasoning is not None and not isinstance(reasoning, dict):
        return 'Invalid reasoning configuration'
    nested = (reasoning or {}).get('effort')
    flat = data.get('reasoning_effort')
    if nested is not None and flat is not None and nested != flat:
        return 'Conflicting reasoning effort values'
    if 'ultra' in (nested, flat):
        return 'Ultra is a Codex client workflow, not a wire reasoning effort; select Ultra in Codex, which sends xhigh to the model.'
    for effort in (nested, flat):
        if effort is not None and (not isinstance(effort, str) or effort not in MODEL_EFFORTS[data['model']]):
            return 'Unsupported reasoning effort for selected model: ' + ', '.join(MODEL_EFFORTS[data['model']])
    return None
