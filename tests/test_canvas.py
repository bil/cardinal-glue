"""CanvasClient and CanvasAuth: pagination, URL building, token discovery."""
import json

import pytest
import requests

from cardinal_glue.auth.core import CannotInstantiateServiceObject, InvalidAuthInfo
from cardinal_glue.canvas_api.canvas import CanvasClient
from cardinal_glue.canvas_api.canvasauth import CanvasAuth

from conftest import FakeResponse

DEFAULT_BASE = 'https://canvas.stanford.edu'


@pytest.fixture
def client(auth):
    return CanvasClient(auth=auth)


# --------------------------------------------------------------------- get_courses
def test_get_courses_requests_a_full_page(client, auth):
    auth.queue(FakeResponse(200, [{'id': 1}]))
    assert client.get_courses() == [{'id': 1}]
    assert auth.calls[0][2]['per_page'] == 100, 'default per_page avoids needless pagination'


def test_caller_can_override_per_page(client, auth):
    auth.queue(FakeResponse(200, []))
    client.get_courses(per_page=10)
    assert auth.calls[0][2]['per_page'] == 10


def test_extra_params_are_forwarded(client, auth):
    auth.queue(FakeResponse(200, []))
    client.get_courses(enrollment_type=['teacher'])
    assert auth.calls[0][2]['enrollment_type'] == ['teacher']


def test_get_courses_follows_pagination_links(client, auth):
    auth.queue(
        FakeResponse(200, [{'id': 1}], links={'next': {'url': 'https://canvas.test/page2'}}),
        FakeResponse(200, [{'id': 2}], links={'next': {'url': 'https://canvas.test/page3'}}),
        FakeResponse(200, [{'id': 3}]),
    )
    assert client.get_courses() == [{'id': 1}, {'id': 2}, {'id': 3}]
    assert auth.urls[1:] == ['https://canvas.test/page2', 'https://canvas.test/page3']


def test_pagination_stops_when_the_next_link_has_no_url(client, auth):
    """Malformed Link header must terminate the loop, not spin forever."""
    auth.queue(
        FakeResponse(200, [{'id': 1}], links={'next': {}}),
        FakeResponse(200, [{'id': 99}]),
    )
    assert client.get_courses() == [{'id': 1}]


def test_http_error_propagates(client, auth):
    auth.queue(FakeResponse(403, {'errors': 'nope'}))
    with pytest.raises(requests.exceptions.HTTPError):
        client.get_courses()


# ---------------------------------------------------------- single course and user
def test_get_course_builds_the_url(client, auth):
    auth.queue(FakeResponse(200, {'id': 42, 'name': 'DBP'}))
    assert client.get_course(42)['name'] == 'DBP'
    assert auth.urls[0] == '/api/v1/courses/42'


def test_get_user_builds_the_url(client, auth):
    auth.queue(FakeResponse(200, {'id': 7}))
    assert client.get_user(7) == {'id': 7}
    assert auth.urls[0] == '/api/v1/users/7'


def test_get_user_accepts_an_sis_identifier(client, auth):
    """flaskboot looks users up by SUNet ID via the sis_user_id: form."""
    auth.queue(FakeResponse(200, {'id': 7}))
    client.get_user('sis_user_id:alovelace')
    assert auth.urls[0] == '/api/v1/users/sis_user_id:alovelace'


def test_get_users_in_course_paginates(client, auth):
    auth.queue(
        FakeResponse(200, [{'id': 1}], links={'next': {'url': 'https://canvas.test/p2'}}),
        FakeResponse(200, [{'id': 2}]),
    )
    assert client.get_users_in_course(42) == [{'id': 1}, {'id': 2}]
    assert auth.urls[0] == '/api/v1/courses/42/users'


# ------------------------------------------------------------------ lazy auth wiring
def test_client_does_not_authenticate_until_a_call_is_made(isolated_auth_dir):
    """
    Constructing the client must be free of side effects -- no credential reads, no network.
    The autouse no_network fixture makes a violation fail loudly.
    """
    CanvasClient()


def test_missing_credentials_surface_as_cannot_instantiate(isolated_auth_dir, monkeypatch):
    def boom():
        raise InvalidAuthInfo('no creds')

    monkeypatch.setattr('cardinal_glue.canvas_api.canvas.CanvasAuth', lambda: boom())
    with pytest.raises(CannotInstantiateServiceObject):
        CanvasClient().get_courses()


# ----------------------------------------------------------------------- CanvasAuth
def test_token_from_env_selects_memory_mode(isolated_auth_dir, monkeypatch):
    monkeypatch.setenv('CANVAS_ACCESS_TOKEN', 'ENVTOKEN')
    a = CanvasAuth()
    assert a._auth_method == 'memory'
    assert a._base_url == DEFAULT_BASE


def test_base_url_override_from_env(isolated_auth_dir, monkeypatch):
    monkeypatch.setenv('CANVAS_ACCESS_TOKEN', 'T')
    monkeypatch.setenv('CANVAS_BASE_URL', 'https://canvas.example.test/')
    assert CanvasAuth()._base_url == 'https://canvas.example.test', 'trailing slash stripped'


def test_env_token_wins_over_the_file(isolated_auth_dir, monkeypatch):
    (isolated_auth_dir / 'canvas.json').write_text(json.dumps({'api_token': 'FILE'}))
    monkeypatch.setenv('CANVAS_ACCESS_TOKEN', 'ENV')
    assert CanvasAuth()._auth_method == 'memory'


def test_token_from_file(isolated_auth_dir):
    (isolated_auth_dir / 'canvas.json').write_text(
        json.dumps({'api_token': 'FILETOKEN', 'base_url': 'https://c.test/'}))
    a = CanvasAuth()
    assert a._auth_method == 'file'
    assert a._api_token == 'FILETOKEN'
    assert a._base_url == 'https://c.test'


def test_file_without_api_token_raises(isolated_auth_dir):
    (isolated_auth_dir / 'canvas.json').write_text(json.dumps({'base_url': 'https://c.test'}))
    with pytest.raises(InvalidAuthInfo, match='api_token'):
        CanvasAuth()


def test_invalid_json_raises_a_clear_error(isolated_auth_dir):
    (isolated_auth_dir / 'canvas.json').write_text('{not json')
    with pytest.raises(InvalidAuthInfo, match='not valid JSON'):
        CanvasAuth()


def test_absent_config_defers_instead_of_raising(isolated_auth_dir):
    """
    Deliberate: CanvasAuth() with nothing configured does not raise, to allow lazy setup. The
    failure is moved to make_request instead.
    """
    a = CanvasAuth()
    assert a._auth_method is None
    with pytest.raises(InvalidAuthInfo, match='CANVAS_ACCESS_TOKEN'):
        a.make_request('get', '/api/v1/courses')


def test_relative_url_gets_the_base_prepended(isolated_auth_dir, monkeypatch):
    monkeypatch.setenv('CANVAS_ACCESS_TOKEN', 'T')
    a = CanvasAuth()
    seen = {}

    def fake_request(method, url, **kwargs):
        seen.update(url=url, headers=kwargs.get('headers'))
        return FakeResponse(200, {})

    monkeypatch.setattr('cardinal_glue.canvas_api.canvasauth.requests.request', fake_request)
    a.make_request('get', '/api/v1/courses')
    assert seen['url'] == f'{DEFAULT_BASE}/api/v1/courses'
    assert seen['headers']['Authorization'] == 'Bearer T'
    assert seen['headers']['Accept'] == 'application/json'


def test_absolute_url_is_left_alone(isolated_auth_dir, monkeypatch):
    """Pagination hands back absolute URLs; prepending the base would corrupt them."""
    monkeypatch.setenv('CANVAS_ACCESS_TOKEN', 'T')
    a = CanvasAuth()
    seen = {}
    monkeypatch.setattr('cardinal_glue.canvas_api.canvasauth.requests.request',
                        lambda m, url, **kw: (seen.update(url=url), FakeResponse(200, {}))[1])
    a.make_request('get', 'https://canvas.test/api/v1/courses?page=2')
    assert seen['url'] == 'https://canvas.test/api/v1/courses?page=2'


def test_caller_headers_are_merged_not_replaced(isolated_auth_dir, monkeypatch):
    monkeypatch.setenv('CANVAS_ACCESS_TOKEN', 'T')
    a = CanvasAuth()
    seen = {}
    monkeypatch.setattr('cardinal_glue.canvas_api.canvasauth.requests.request',
                        lambda m, url, **kw: (seen.update(kw), FakeResponse(200, {}))[1])
    a.make_request('get', '/x', headers={'X-Custom': '1'})
    assert seen['headers']['X-Custom'] == '1'
    assert seen['headers']['Authorization'] == 'Bearer T'
