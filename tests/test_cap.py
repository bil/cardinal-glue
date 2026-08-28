"""CAPClient and CAPAuth. Never exercised before, so expect findings."""
import json
import time

import pytest

from cardinal_glue.auth.core import InvalidAuthInfo
from cardinal_glue.cap_api.cap import CAPClient
from cardinal_glue.cap_api.capauth import CAPAuth

from conftest import FakeResponse


@pytest.fixture
def client(auth):
    return CAPClient(auth=auth)


# ------------------------------------------------------------------ get_profile_from_uid
def test_profile_lookup_builds_the_uid_url(client, auth):
    auth.queue(FakeResponse(200, {'values': [{'uid': 'alovelace', 'displayName': 'A H'}]}))
    profile = client.get_profile_from_uid('alovelace')
    assert profile['displayName'] == 'A H'
    assert 'uids=alovelace' in auth.urls[0]
    assert 'community=' not in auth.urls[0]


def test_profile_lookup_passes_a_valid_community(client, auth):
    auth.queue(FakeResponse(200, {'values': [{'uid': 'x'}]}))
    client.get_profile_from_uid('x', community='stanford')
    assert 'community=stanford' in auth.urls[0]


def test_invalid_community_rejected_before_any_request(client, auth):
    with pytest.raises(ValueError, match='Invalid community'):
        client.get_profile_from_uid('x', community='wide-open')
    assert auth.calls == [], 'must not reach the API with an invalid argument'


def test_profile_absent_key_returns_none(client, auth):
    auth.queue(FakeResponse(200, {'totalCount': 0}))
    assert client.get_profile_from_uid('nobody') is None


@pytest.mark.xfail(
    reason="BUG: get_profile_from_uid does response['values'][0] guarded only by "
           "`if 'values' in response`, so an empty list raises IndexError instead of "
           "returning None. CAP returns {'values': []} for an unknown uid.",
    raises=IndexError,
    strict=True,
)
def test_profile_empty_values_should_return_none(client, auth):
    auth.queue(FakeResponse(200, {'values': []}))
    assert client.get_profile_from_uid('nobody') is None


# ------------------------------------------------------------------------ get_org_from_code
def test_org_lookup_returns_alias(client, auth):
    auth.queue(FakeResponse(200, {'alias': 'Department of Genetics'}))
    assert client.get_org_from_code('AABB') == 'Department of Genetics'
    assert auth.urls[0].endswith('/orgs/AABB')


def test_org_lookup_missing_alias_returns_none(client, auth):
    auth.queue(FakeResponse(200, {'code': 'AABB'}))
    assert client.get_org_from_code('AABB') is None


# --------------------------------------------------------------------------- photos
def test_extract_photo_url_for_default_rendition(client):
    profile = {'profilePhotos': {'350x350': {'url': 'https://cap.test/a.jpg'}}}
    assert client._extract_profile_photo_url(profile) == 'https://cap.test/a.jpg'


def test_extract_photo_url_for_other_rendition(client):
    profile = {'profilePhotos': {'square': {'url': 'https://cap.test/sq.jpg'}}}
    assert client._extract_profile_photo_url(profile, rendition='square') == 'https://cap.test/sq.jpg'


@pytest.mark.parametrize('profile', [None, {}, {'profilePhotos': {}},
                                     {'profilePhotos': {'350x350': {}}}])
def test_extract_photo_url_handles_every_missing_shape(client, profile):
    assert client._extract_profile_photo_url(profile) is None


def test_get_profile_photo_fetches_the_url(client, auth):
    profile = {'profilePhotos': {'350x350': {'url': 'https://cap.test/a.jpg'}}}
    auth.queue(FakeResponse(200, None, content=b'JPEGBYTES'))
    result = client.get_profile_photo(profile=profile)
    assert result.content == b'JPEGBYTES'
    assert auth.urls[0] == 'https://cap.test/a.jpg'


def test_get_profile_photo_looks_up_the_profile_when_given_a_uid(client, auth):
    auth.queue(
        FakeResponse(200, {'values': [{'profilePhotos': {'350x350': {'url': 'https://cap.test/b.jpg'}}}]}),
        FakeResponse(200, None, content=b'B'),
    )
    assert client.get_profile_photo(uid='alovelace').content == b'B'


def test_get_profile_photo_without_photo_returns_none(client, auth):
    assert client.get_profile_photo(profile={'profilePhotos': {}}) is None


def test_get_profile_photo_with_neither_uid_nor_profile_returns_none(client, auth):
    assert client.get_profile_photo() is None
    assert auth.calls == []


# ----------------------------------------------------------------------- CAPAuth
def test_capauth_prefers_the_env_var(isolated_auth_dir, monkeypatch):
    monkeypatch.setenv('CAP_CLIENT', json.dumps({'client_id': 'i', 'client_secret': 's'}))
    (isolated_auth_dir / 'cap_client.json').write_text('{"client_id": "file", "client_secret": "f"}')
    a = CAPAuth()
    assert a._auth_method == 'memory'


def test_capauth_falls_back_to_the_file(isolated_auth_dir):
    (isolated_auth_dir / 'cap_client.json').write_text(
        json.dumps({'client_id': 'i', 'client_secret': 's'}))
    a = CAPAuth()
    assert a._auth_method == 'file'
    assert a._client_id == 'i'


def test_capauth_missing_config_raises(isolated_auth_dir):
    with pytest.raises(InvalidAuthInfo):
        CAPAuth()


def test_capauth_incomplete_file_raises(isolated_auth_dir):
    (isolated_auth_dir / 'cap_client.json').write_text('{"client_id": "only"}')
    with pytest.raises(InvalidAuthInfo, match="client_id.*client_secret"):
        CAPAuth()


def test_capauth_fetches_and_caches_the_token(isolated_auth_dir, monkeypatch):
    (isolated_auth_dir / 'cap_client.json').write_text(
        json.dumps({'client_id': 'i', 'client_secret': 's'}))
    a = CAPAuth()

    token_posts = []

    def fake_post(url, data=None, auth=None, **kw):
        token_posts.append((url, auth))
        return FakeResponse(200, {'access_token': 'TOK', 'expires_in': 3600})

    api_calls = []

    def fake_request(method, url, **kwargs):
        api_calls.append(kwargs.get('headers'))
        return FakeResponse(200, {})

    monkeypatch.setattr('cardinal_glue.cap_api.capauth.requests.post', fake_post)
    monkeypatch.setattr('cardinal_glue.cap_api.capauth.requests.request', fake_request)

    a.make_request('get', 'https://cap.test/x')
    a.make_request('get', 'https://cap.test/y')

    assert len(token_posts) == 1, 'the token should be fetched once and reused'
    assert token_posts[0][1] == ('i', 's'), 'client credentials go in the auth tuple'
    assert api_calls[0]['Authorization'] == 'Bearer TOK'


def test_capauth_refetches_an_expired_token(isolated_auth_dir, monkeypatch):
    (isolated_auth_dir / 'cap_client.json').write_text(
        json.dumps({'client_id': 'i', 'client_secret': 's'}))
    a = CAPAuth()
    a._access_token = 'OLD'
    a._token_expires_at = time.time() - 1      # already expired

    posts = []

    def fake_post(url, data=None, auth=None, **kw):
        posts.append(url)
        return FakeResponse(200, {'access_token': 'NEW', 'expires_in': 3600})

    monkeypatch.setattr('cardinal_glue.cap_api.capauth.requests.post', fake_post)
    monkeypatch.setattr('cardinal_glue.cap_api.capauth.requests.request',
                        lambda *a_, **k: FakeResponse(200, {}))
    a.make_request('get', 'https://cap.test/x')
    assert len(posts) == 1
    assert a._access_token == 'NEW'


def test_capauth_token_response_without_a_token_raises(isolated_auth_dir, monkeypatch):
    (isolated_auth_dir / 'cap_client.json').write_text(
        json.dumps({'client_id': 'i', 'client_secret': 's'}))
    a = CAPAuth()
    monkeypatch.setattr('cardinal_glue.cap_api.capauth.requests.post',
                        lambda *a_, **k: FakeResponse(200, {'not_a_token': 1}))
    with pytest.raises(InvalidAuthInfo, match='access_token'):
        a.make_request('get', 'https://cap.test/x')


def test_capauth_empty_env_var_raises(isolated_auth_dir, monkeypatch):
    monkeypatch.setenv('CAP_CLIENT', '')
    with pytest.raises(InvalidAuthInfo):
        CAPAuth().make_request('get', 'https://cap.test/x')
