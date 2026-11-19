from datetime import datetime,timezone
import json

import pytest
from pydantic import ValidationError

from orchestrator.accounting.pricing import CatalogInput, PricingError, create_catalog, quote, list_catalogs
from orchestrator.accounting.usage import record_usage
from orchestrator.providers.base import AgentCall,InvocationRequest,InvocationResult,UsageReport,invoke_measured
from orchestrator.project_store import connection


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch,tmp_path):
    monkeypatch.setenv('ORCH_DB',str(tmp_path/'events.db'))


def catalog(at='2026-01-01T00:00:00Z',**values):
    return {'entries':[{'adapter':'openrouter','model':'vendor/model','effective_from':at,
                        'input_price':1.0,'output_price':2.0,**values}]}


def test_versions_import_origin_units_and_timezone_boundaries():
    first=create_catalog(catalog())
    second=create_catalog({**catalog('2026-02-01T03:00:00+03:00',input_price=5.0),'source':'import'})
    assert first['source']=='manual' and second['source']=='import'
    assert first['entries'][0]['unit']=='per_1m_tokens'
    assert quote('openrouter','vendor/model',at='2025-12-31T23:59:59Z') is None
    assert quote('openrouter','vendor/model',at='2026-01-01T00:00:00Z')['input_price']==1
    assert quote('openrouter','vendor/model',at='2026-02-01T00:00:00Z')['input_price']==5
    assert list_catalogs()[0]==first and len(list_catalogs())==2


def test_expired_version_does_not_resurrect_old_open_ended_price():
    create_catalog(catalog())
    create_catalog(catalog('2026-02-01T00:00:00Z',effective_to='2026-03-01T00:00:00Z'))
    assert quote('openrouter','vendor/model',at='2026-03-01T00:00:00Z') is None


@pytest.mark.parametrize('values',[{'input_price':-1.0},{'output_price':float('inf')},
    {'input_price':True},{'effective_from':'2026-01-01'}, {'currency':'usd'},
    {'effective_to':'2025-01-01T00:00:00Z'},{'unit':'per_token'},{'api_key':'sentinel-secret'}])
def test_bad_price_data_is_rejected(values):
    with pytest.raises(ValidationError): CatalogInput.model_validate(catalog(**values))


def test_conflicting_import_is_atomic_and_prior_version_unchanged():
    original=create_catalog(catalog())
    batch={'source':'import','entries':[
        catalog('2026-02-01T00:00:00Z')['entries'][0],catalog()['entries'][0]]}
    with pytest.raises(PricingError):create_catalog(batch)
    assert list_catalogs()==[original]


def test_historical_estimate_is_pinned_and_new_prices_never_reprice_calls():
    first=create_catalog(catalog())
    call=AgentCall(call_id='call-one',provider='openrouter',role='planner',model='vendor/model',
        duration_ms=10,started_at='2026-01-15T00:00:00Z',
        usage=UsageReport(input_tokens=1_000_000,output_tokens=1_000_000,source='provider_reported'))
    record_usage(run_id='run-price',call=call,billing_mode='api_metered')
    with connection() as conn:
        before=dict(conn.execute("SELECT * FROM usage_records WHERE id='call-one'").fetchone())
    assert before['estimated_cost_usd']==3.0
    assert before['reported_cost_usd'] is None
    assert before['price_entry_id']==first['entries'][0]['id']
    create_catalog(catalog('2026-02-01T00:00:00Z',input_price=100.0))
    record_usage(run_id='run-price',call=call,billing_mode='api_metered')
    with connection() as conn:
        after=dict(conn.execute("SELECT * FROM usage_records WHERE id='call-one'").fetchone())
    assert after==before


@pytest.mark.parametrize('mode',['subscription_quota','api_metered'])
def test_estimate_remains_separate_from_reported_cost_and_billing(mode):
    create_catalog(catalog())
    call=AgentCall(call_id='reported',provider='openrouter',role='reviewer',model='vendor/model',
        duration_ms=1,started_at='2026-01-15T00:00:00Z',
        usage=UsageReport(input_tokens=1_000_000,output_tokens=1_000_000,
                          reported_cost_usd=2.5,source='provider_reported'))
    record_usage(run_id='run-price',call=call,billing_mode=mode)
    with connection() as conn:
        row=conn.execute("SELECT * FROM usage_records WHERE id='reported'").fetchone()
        assert row['estimated_cost_usd']==3.0 and row['reported_cost_usd']==2.5
        assert row['billing_mode']==mode


def test_no_price_no_usage_or_ambiguous_components_stay_unavailable():
    create_catalog(catalog())
    for name,adapter,usage in [('unknown','missing',UsageReport(input_tokens=1,output_tokens=2,source='cli_reported')),
        ('empty','openrouter',UsageReport()),
        ('cache','openrouter',UsageReport(input_tokens=10,output_tokens=2,cache_read_tokens=3,source='provider_reported'))]:
        record_usage(run_id='run-price',call=AgentCall(call_id=name,provider=adapter,role='planner',
            model='vendor/model',duration_ms=1,started_at='2026-01-15T00:00:00Z',usage=usage),billing_mode='api_metered')
    with connection() as conn:
        rows=conn.execute('SELECT estimated_cost_usd,price_entry_id FROM usage_records').fetchall()
        assert all(row['estimated_cost_usd'] is None for row in rows)


def test_price_selection_uses_actual_start_not_completion_time(monkeypatch):
    create_catalog(catalog())
    class Clock(datetime):
        current=datetime(2026,1,15,tzinfo=timezone.utc)
        @classmethod
        def now(cls,tz=None):return cls.current
    monkeypatch.setattr('orchestrator.providers.base.datetime',Clock)
    def generate():
        create_catalog(catalog('2026-02-01T00:00:00Z',input_price=100.0))
        Clock.current=datetime(2026,2,15,tzinfo=timezone.utc)
        return InvocationResult(text='done',usage=UsageReport(input_tokens=1_000_000,output_tokens=1_000_000,source='provider_reported'))
    invoke_measured('openrouter',InvocationRequest(role='planner',prompt='x',cwd='/tmp',model='vendor/model',permission='read_only'),
        generate,lambda call:record_usage(run_id='run-price',call=call,billing_mode='api_metered'))
    with connection() as conn:
        row=conn.execute('SELECT estimated_cost_usd,started_at FROM usage_records').fetchone()
        assert row['estimated_cost_usd']==3.0 and row['started_at'].startswith('2026-01-15')


def test_absent_historical_estimate_is_not_backfilled_on_duplicate_call():
    call=AgentCall(call_id='no-price-yet',provider='openrouter',role='planner',model='vendor/model',duration_ms=1,
        started_at='2026-01-15T00:00:00Z',usage=UsageReport(input_tokens=10,output_tokens=10,source='provider_reported'))
    record_usage(run_id='run-price',call=call,billing_mode='api_metered')
    create_catalog(catalog())
    record_usage(run_id='run-price',call=call,billing_mode='api_metered')
    with connection() as conn:
        assert conn.execute('SELECT estimated_cost_usd FROM usage_records').fetchone()[0] is None


@pytest.mark.parametrize('currency',['USD','EUR'])
def test_zero_price_is_explicit_and_currency_is_never_converted(currency):
    create_catalog(catalog(input_price=0.0,output_price=0.0,currency=currency))
    call=AgentCall(call_id='zero',provider='openrouter',role='planner',model='vendor/model',duration_ms=1,
        started_at='2026-01-15T00:00:00Z',usage=UsageReport(input_tokens=10,output_tokens=10,source='provider_reported'))
    record_usage(run_id='run-price',call=call,billing_mode='api_metered')
    with connection() as conn:
        result=conn.execute('SELECT estimated_cost_usd FROM usage_records').fetchone()[0]
        assert result==(0.0 if currency=='USD' else None)


def test_positive_price_that_underflows_storage_never_becomes_zero_cost():
    create_catalog(catalog(input_price=5e-324,output_price=0.0))
    call=AgentCall(call_id='tiny',provider='openrouter',role='planner',model='vendor/model',duration_ms=1,
        started_at='2026-01-15T00:00:00Z',usage=UsageReport(input_tokens=1,output_tokens=0,source='provider_reported'))
    record_usage(run_id='run-price',call=call,billing_mode='api_metered')
    with connection() as conn:
        row=conn.execute('SELECT estimated_cost_usd,price_entry_id FROM usage_records').fetchone()
        assert row['estimated_cost_usd'] is None and row['price_entry_id'] is None


def test_pricing_api_is_authenticated_append_only_and_sanitizes_rejections(workflow_client):
    client,_=workflow_client
    response=client.post('/pricing',json=catalog())
    assert response.status_code==201,response.text
    assert client.get('/pricing').json()[0]['id']==response.json()['id']
    selected=client.get('/pricing/quote',params={'adapter':'openrouter','model':'vendor/model','at':'2026-01-01T00:00:00Z'})
    assert selected.status_code==200 and selected.json()['available'] is True
    assert client.put('/pricing',json=catalog()).status_code==405
    bad=client.post('/pricing',json={**catalog(),'api_key':'sentinel-secret'})
    assert bad.status_code==422 and 'sentinel-secret' not in bad.text
    client.headers.pop('X-Orchestrator-CSRF')
    assert client.get('/pricing').status_code==403


# Reuse the existing authenticated fixture without any real provider calls.
from .test_workflow_api import workflow_client
