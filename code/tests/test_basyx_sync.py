"""
test_basyx_sync.py

TDD for the BaSyx server push implemented in aas_manager.sync_to_basyx().

The HTTP transport is exercised by monkeypatching `aas_manager.requests` with a
recording fake — no real BaSyx server needed.  Covers:

  - happy path: shell + 3 submodels POSTed to the Part 2 REST API
  - idempotent upsert: a 409 (already exists) falls back to PUT
  - resilience: a network error is reported, never raised
  - the Base64URL id helper used in REST paths

The unconfigured no-op contract lives in test_aas_sync_seam.py and must stay
green alongside these.
"""

import base64
import json

import pytest
import requests as real_requests

import aas_manager


VALID_TYPE, VALID_ID = 'equipment', 'filling-machine-1'
ENV_URL = 'http://basyx-test:8081'


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code
        self.text = ''


class FakeRequests:
    """Mimics the subset of `requests` sync_to_basyx uses and records calls."""

    RequestException = real_requests.RequestException

    def __init__(self, post_status=201, put_status=204, post_exc=None):
        self.post_status = post_status
        self.put_status = put_status
        self.post_exc = post_exc
        self.posts = []
        self.puts = []

    def post(self, url, json=None, timeout=None):
        if self.post_exc:
            raise self.post_exc
        self.posts.append((url, json))
        return _Resp(self.post_status)

    def put(self, url, json=None, timeout=None):
        self.puts.append((url, json))
        return _Resp(self.put_status)


@pytest.fixture
def configured(monkeypatch):
    """Point aas_manager at a (fake) BaSyx server for the duration of a test."""
    monkeypatch.setattr(aas_manager, 'BASYX_AAS_ENV_URL', ENV_URL)
    return monkeypatch


class TestSyncSuccess:
    def test_synced_pushes_shell_and_three_submodels(self, configured):
        fake = FakeRequests(post_status=201)
        configured.setattr(aas_manager, 'requests', fake)

        result = aas_manager.sync_to_basyx(VALID_TYPE, VALID_ID)

        assert result['status'] == 'synced'
        assert result['submodel_count'] == 3
        assert result['shell_id']
        # 1 shell + 3 submodels, each created with a single POST
        assert len(fake.posts) == 4
        urls = [u for u, _ in fake.posts]
        assert sum('/submodels' in u for u in urls) == 3
        assert sum(u.endswith('/shells') for u in urls) == 1

    def test_bodies_are_aas_json(self, configured):
        fake = FakeRequests(post_status=201)
        configured.setattr(aas_manager, 'requests', fake)
        aas_manager.sync_to_basyx(VALID_TYPE, VALID_ID)
        for _url, body in fake.posts:
            assert isinstance(body, dict)
            assert 'modelType' in body

    def test_shell_pushed_after_submodels(self, configured):
        # Submodels must exist before the shell that references them.
        fake = FakeRequests(post_status=201)
        configured.setattr(aas_manager, 'requests', fake)
        aas_manager.sync_to_basyx(VALID_TYPE, VALID_ID)
        urls = [u for u, _ in fake.posts]
        assert urls[-1].endswith('/shells')


class TestUpsert:
    def test_conflict_falls_back_to_put(self, configured):
        # Server says every object already exists → upsert via PUT.
        fake = FakeRequests(post_status=409, put_status=204)
        configured.setattr(aas_manager, 'requests', fake)

        result = aas_manager.sync_to_basyx(VALID_TYPE, VALID_ID)

        assert result['status'] == 'synced'
        assert len(fake.puts) == 4
        for url, _ in fake.puts:
            assert '/shells/' in url or '/submodels/' in url


class TestErrors:
    def test_network_error_returns_error_status(self, configured):
        fake = FakeRequests(post_exc=real_requests.RequestException('boom'))
        configured.setattr(aas_manager, 'requests', fake)

        result = aas_manager.sync_to_basyx(VALID_TYPE, VALID_ID)

        assert result['status'] == 'error'
        assert 'boom' in result['reason']
        assert result['shell_id']

    def test_bad_status_returns_error_status(self, configured):
        fake = FakeRequests(post_status=500)
        configured.setattr(aas_manager, 'requests', fake)
        result = aas_manager.sync_to_basyx(VALID_TYPE, VALID_ID)
        assert result['status'] == 'error'


class TestB64Url:
    def test_round_trip_padding_free(self):
        ident = 'urn:vertebrate:ispe:boston:equipment:filling-machine-1:aas'
        encoded = aas_manager._b64url(ident)
        assert '=' not in encoded
        pad = '=' * (-len(encoded) % 4)
        assert base64.urlsafe_b64decode(encoded + pad).decode() == ident
