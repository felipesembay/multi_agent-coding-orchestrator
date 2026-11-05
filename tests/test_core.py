import json
import pytest
from orchestrator.core import extract_json, decide, more

def test_extract_json():
    assert extract_json('```json\n{"tasks": []}\n```') == {'tasks':[]}
    assert extract_json('{"approved":true}')['approved'] is True

def test_review_loop(monkeypatch):
    monkeypatch.setenv('MAX_ATTEMPTS','3')
    assert decide({'review':{'approved':False},'attempts':1})=='retry'
    assert decide({'review':{'approved':False},'attempts':3})=='blocked'
    assert decide({'review':{'approved':True},'attempts':3})=='next'

def test_more():
    assert more({'task_index':0,'plan':{'tasks':[{}]}})=='continue'
    assert more({'task_index':1,'plan':{'tasks':[{}]}})=='finish'
