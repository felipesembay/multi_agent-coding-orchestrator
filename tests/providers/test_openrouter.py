import json

import httpx
import pytest
from pydantic import ValidationError

from orchestrator.providers.base import GenerationRequest
from orchestrator.providers.errors import InvocationFailure
from orchestrator.providers.models.openrouter import OpenRouterProvider
from orchestrator.secrets.store import CredentialStore, InMemoryKeyringBackend


SENTINEL = 'sk-or-test-never-persist-this'


def provider(handler):
    store = CredentialStore(backend=InMemoryKeyringBackend())
    ref = store.set_credential('openrouter', 'pc-api', SENTINEL)
    return OpenRouterProvider(credential_store=store, transport=httpx.MockTransport(handler)), ref


def request(ref, **values):
    return GenerationRequest(role='planner', prompt='Return JSON tasks', model='vendor/model',
                             credential_ref=ref, **values)


def response():
    return {'model': 'vendor/model', 'choices': [{'finish_reason': 'stop', 'message': {
        'role': 'assistant', 'content': '{"tasks":[{"id":"T1"}]}'}}],
        'usage': {'prompt_tokens': 9, 'completion_tokens': 4, 'cost': 0.001,
                  'prompt_tokens_details': {'cached_tokens': 2},
                  'completion_tokens_details': {'reasoning_tokens': 1}}}


def test_generate_reads_keyring_at_call_time_and_returns_reported_usage():
    seen = []
    def handle(req):
        seen.append(req)
        assert str(req.url) == 'https://openrouter.ai/api/v1/chat/completions'
        assert req.headers['authorization'] == 'Bearer ' + SENTINEL
        body = json.loads(req.content)
        assert 'cwd' not in body and 'credential_ref' not in body
        assert body['model'] == 'vendor/model' and body['stream'] is False
        assert body['provider']['allow_fallbacks'] is False
        return httpx.Response(200, json=response())
    api, ref = provider(handle)
    result = api.generate(request(ref), context=[])
    assert result.structured == {'tasks': [{'id': 'T1'}]}
    assert result.usage.source == 'provider_reported'
    assert result.usage.input_tokens == 9 and result.usage.output_tokens == 4
    assert result.usage.cache_read_tokens == 2 and result.usage.reasoning_tokens == 1
    assert result.usage.reported_cost_usd == 0.001
    assert SENTINEL not in result.model_dump_json() and len(seen) == 1


@pytest.mark.parametrize('status,code,safe', [(401,'auth_failed',False), (402,'quota_exhausted',True),
    (429,'rate_limited',True), (500,'unavailable',False), (503,'unavailable',False),
    (403,'permission_denied',False), (400,'invalid_output',False)])
def test_status_errors_are_sanitized_and_do_not_retry(status, code, safe):
    calls = []
    def handle(req):
        calls.append(req)
        return httpx.Response(status, json={'error': {'message': SENTINEL}})
    api, ref = provider(handle)
    with pytest.raises(InvocationFailure) as caught: api.generate(request(ref), context=[])
    assert caught.value.code == code and caught.value.safe_to_retry is safe
    assert SENTINEL not in str(caught.value) and caught.value.__cause__ is None
    assert len(calls) == 1


@pytest.mark.parametrize('error,code', [(httpx.ReadTimeout('secret'), 'timeout'),
    (httpx.ConnectError('secret'), 'unavailable')])
def test_transport_failures_are_ambiguous_and_never_marked_retry_safe(error, code):
    api, ref = provider(lambda req: (_ for _ in ()).throw(error))
    with pytest.raises(InvocationFailure) as caught: api.generate(request(ref), context=[])
    assert caught.value.code == code and caught.value.safe_to_retry is False
    assert 'secret' not in str(caught.value)


@pytest.mark.parametrize('data', [None, {}, {'choices': []},
    {'choices': [{'message': {'content': SENTINEL}, 'finish_reason': 'length'}]},
    {'choices': [{'message': {'content': '{}', 'tool_calls': [{'id':'tool'}]}, 'finish_reason':'tool_calls'}]},
    {'error': {'code': 429, 'message': SENTINEL}},
    {'choices': [{'message': {'content': '{"approved":1,"findings":[]}'}, 'finish_reason':'stop'}]}])
def test_malformed_truncated_tool_or_semantic_errors_are_rejected(data):
    api, ref = provider(lambda req: httpx.Response(200, content=json.dumps(data)))
    result = api.generate(GenerationRequest(role='reviewer', model='vendor/model', prompt='Review', credential_ref=ref), context=[])
    assert result.error_code == 'invalid_output'
    assert SENTINEL not in result.model_dump_json()


def test_missing_usage_stays_unavailable_and_invalid_json_is_sanitized():
    data = response(); data.pop('usage')
    api, ref = provider(lambda req: httpx.Response(200, json=data))
    assert api.generate(request(ref), context=[]).usage.source == 'unavailable'
    api, ref = provider(lambda req: httpx.Response(200, text=SENTINEL))
    with pytest.raises(InvocationFailure): api.generate(request(ref), context=[])


@pytest.mark.parametrize('extra', [{'cwd':'/private'}, {'env':{'SECRET':'value'}},
    {'role':'implementer'}, {'permission':'workspace_write'}, {'model':None}])
def test_generation_contract_rejects_filesystem_execution_and_implicit_model(extra):
    with pytest.raises(ValidationError):
        GenerationRequest(**{'role':'planner', 'prompt':'x', 'model':'vendor/model',
            'credential_ref':'multi-agent-orchestrator:openrouter:pc-api', **extra})


def test_probe_is_offline_and_model_list_is_explicit():
    calls=[]
    api, _ = provider(lambda req: (calls.append(req), httpx.Response(200, json={'data':[
        {'id':'vendor/model', 'name':'Model', 'context_length':1000}]}))[1])
    assert api.probe().credential_present is None and calls == []
    assert api.list_models()[0].id == 'vendor/model'
    assert calls[0].url.path == '/api/v1/models'


def test_deleted_key_is_not_read_from_environment_or_cached(monkeypatch):
    api, ref = provider(lambda req: pytest.fail('No HTTP without a keyring key'))
    api._credentials.delete_credential(ref)
    monkeypatch.setenv('OPENROUTER_API_KEY', SENTINEL)
    with pytest.raises(InvocationFailure) as caught: api.generate(request(ref), context=[])
    assert caught.value.code == 'auth_failed'


def test_echoed_key_is_redacted_and_invalid_usage_is_never_fabricated():
    data = response(); data['choices'][0]['message']['content'] = json.dumps({'tasks':[{'id':'T1','title':SENTINEL}]})
    data['usage']['prompt_tokens'] = True
    api, ref = provider(lambda req: httpx.Response(200,json=data))
    result = api.generate(request(ref),context=[])
    assert SENTINEL not in result.model_dump_json()
    assert result.usage.source == 'unavailable'
