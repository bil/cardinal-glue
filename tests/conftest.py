"""
Shared fixtures for the cardinal-glue test suite.

Two invariants the whole suite depends on, both enforced by autouse fixtures:

1. **No test reads real credentials.** Every Auth subclass resolves creds from
   `Auth._AUTH_PATH` (~/.config/cardinal-glue) or from environment variables. Without
   isolation a test would pick up the developer's actual certs, so results would depend on
   the machine -- and a bug could send real credentials at a real API.
2. **No test performs real HTTP.** Faking is done at the `auth.make_request` seam, so any call
   reaching `requests` means a test built its object wrong (most often by letting
   `auto_auth=True` authenticate in `__init__`). That should fail loudly, not quietly hit the
   network.
"""
import json
import os
import shutil

import pytest
import requests

import cardinal_glue.auth.core as auth_core
from cardinal_glue.auth.core import Auth

# The real credential directory. Nothing in this suite may read from or write to it.
REAL_AUTH_DIR = os.path.realpath(
    os.path.join(os.path.expanduser('~'), '.config', 'cardinal-glue')
)

# Every environment variable consulted by an auth chain in this package. Scrubbed before each
# test so the developer's shell can't change the outcome.
AUTH_ENV_VARS = (
    'WORKGROUP_CERT',
    'WORKGROUP_CERT_PATH',
    'WORKGROUP_KEY',
    'WORKGROUP_KEY_PATH',
    'WORKGROUP_UAT',
    'CAP_CLIENT',
    'CANVAS_ACCESS_TOKEN',
    'CANVAS_BASE_URL',
    'QUALTRICS_CLIENT',
    'K_REVISION',
    'COLAB_RELEASE_TAG',
    'GOOGLE_CLOUD_PROJECT',
    'GOOGLE_APPLICATION_CREDENTIALS',
)


@pytest.fixture(autouse=True)
def protect_real_credentials(monkeypatch):
    """
    Hard stop on any move touching the real credential directory.

    `Auth.set_auth_directory()` does not just point at a new location -- it `shutil.move`s every
    file out of the old one, and `Auth.__init__` calls it on construction. A single careless test
    can therefore relocate the developer's real certs. (That happened while writing this suite.)
    Patching `_AUTH_PATH` alone is NOT enough, so this guard is independent of it and refuses the
    operation outright rather than trusting the isolation below to hold.
    """
    real_move = shutil.move

    def guarded_move(src, dst, *args, **kwargs):
        for path in (src, dst):
            resolved = os.path.realpath(str(path))
            if resolved == REAL_AUTH_DIR or resolved.startswith(REAL_AUTH_DIR + os.sep):
                raise AssertionError(
                    'test tried to move a file in or out of the REAL credential directory: '
                    f'{src!r} -> {dst!r}. Credential isolation is broken.'
                )
        return real_move(src, dst, *args, **kwargs)

    monkeypatch.setattr(auth_core.shutil, 'move', guarded_move)


@pytest.fixture(autouse=True)
def isolated_auth_dir(tmp_path, monkeypatch, protect_real_credentials):
    """
    Point credential discovery at an empty tmp dir and clear every auth env var.

    Two patches are needed, not one:

    * the `Auth._AUTH_PATH` class attribute, which subclasses read as `self._AUTH_PATH`; and
    * `Auth.__init__.__defaults__`, because the signature is
      `def __init__(self, auth_path=_AUTH_PATH)` and that default is bound **at class-definition
      time** to the real path. Without this second patch every `Auth()` construction re-points
      `_AUTH_PATH` back at the developer's real directory, defeating the first patch entirely.
    """
    for var in AUTH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    auth_dir = tmp_path / 'cardinal-glue'
    auth_dir.mkdir()
    monkeypatch.setattr(Auth, '_AUTH_PATH', str(auth_dir))
    monkeypatch.setattr(Auth.__init__, '__defaults__', (str(auth_dir),))
    return auth_dir


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Turn any real HTTP call into a test failure."""
    def _blocked(*args, **kwargs):
        raise AssertionError(
            f"test attempted a real HTTP request: args={args!r} kwargs={kwargs!r}. "
            "Inject a fake auth (or pass auto_auth=False) instead."
        )

    monkeypatch.setattr(requests, 'request', _blocked)
    monkeypatch.setattr(requests, 'get', _blocked)
    monkeypatch.setattr(requests, 'post', _blocked)
    monkeypatch.setattr(requests.Session, 'request', _blocked)


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, json_body=None, text=None, content=b'', links=None):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text if text is not None else json.dumps(json_body or {})
        self.content = content
        # The Canvas client paginates off response.links; requests exposes {} when absent.
        self.links = links or {}

    def json(self):
        if self._json_body is None:
            raise ValueError('no JSON body')
        return self._json_body

    def raise_for_status(self):
        """The Canvas client relies on this rather than inspecting status_code itself."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f'{self.status_code} error', response=self
            )


class FakeAuth:
    """
    Auth double that records requests and replays queued responses.

    Responses are matched in one of two ways:
      * `queue(...)` -- consumed in FIFO order, for tests that care about call sequence.
      * `route(method, url_suffix, ...)` -- matched by method and URL suffix and reusable, for
        tests where the sequence is incidental.

    Anything unmatched returns `default`, so a test only declares the responses it cares about.
    """

    def __init__(self, base_url='https://api.example.test/2.0', default=None):
        self._base_url = base_url
        self.calls = []           # list of (method, url, params, kwargs)
        self._queue = []
        self._routes = []
        self.default = default if default is not None else FakeResponse(200, {})

    # -- programming the double -------------------------------------------------------
    def queue(self, *responses):
        """Queue responses to be returned in order. Accepts FakeResponse or (status, body)."""
        for r in responses:
            self._queue.append(r if isinstance(r, FakeResponse) else FakeResponse(*r))
        return self

    def route(self, method, url_suffix, status_code=200, json_body=None, **kw):
        self._routes.append((method.lower(), url_suffix, FakeResponse(status_code, json_body, **kw)))
        return self

    # -- the seam under test ---------------------------------------------------------
    def make_request(self, method, url, **kwargs):
        self.calls.append((method.lower(), url, kwargs.get('params'), kwargs))
        for r_method, suffix, response in self._routes:
            if r_method == method.lower() and url.endswith(suffix):
                return response
        if self._queue:
            return self._queue.pop(0)
        return self.default

    # -- assertion helpers -----------------------------------------------------------
    @property
    def urls(self):
        return [c[1] for c in self.calls]

    def calls_of(self, method):
        return [c for c in self.calls if c[0] == method.lower()]

    def types_sent(self, method):
        """The 'type' param of each call of `method` -- USER / WORKGROUP / CERTIFICATE."""
        return [(c[2] or {}).get('type') for c in self.calls_of(method)]


@pytest.fixture
def fake_auth():
    """Factory so a test can make several doubles with different base URLs."""
    return lambda **kw: FakeAuth(**kw)


@pytest.fixture
def auth():
    """The common case: one FakeAuth with the default base URL."""
    return FakeAuth()


# Realistic workgroup GET payload. Mirrors the live API shape confirmed 2026-08-28: people come
# back as type PERSON (not USER), nested groups are stem-qualified, certificates look like
# people in the `id` field.
def workgroup_payload(members=None, administrators=None, **overrides):
    payload = {
        'members': members if members is not None else [
            {'id': 'dbp:basics', 'type': 'WORKGROUP', 'name': 'Basics', 'lastUpdate': '2026-01-01'},
            {'id': 'alovelace', 'type': 'PERSON', 'name': 'A Lovelace', 'lastUpdate': '2026-01-01'},
            {'id': 'dbp-wrkgrp', 'type': 'CERTIFICATE', 'name': 'cert', 'lastUpdate': '2026-01-01'},
        ],
        'administrators': administrators if administrators is not None else [
            {'id': 'bdgrier', 'type': 'PERSON', 'name': 'B Grier'},
        ],
        'description': 'umbrella group',
        'filter': 'NONE',
        'visibility': 'PRIVATE',
        'reusable': 'TRUE',
        'privgroup': 'TRUE',
        'integrations': [],
    }
    payload.update(overrides)
    return payload
