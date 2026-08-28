"""WorkgroupAuth: credential discovery precedence, server selection, cert plumbing."""
import pytest

from cardinal_glue.auth.core import InvalidAuthInfo
from cardinal_glue.workgroup_api.workgroupauth import WorkgroupAuth

PROD = 'https://workgroupsvc.stanford.edu/workgroups/2.0'
UAT = 'https://workgroupsvc-uat.stanford.edu/workgroups/2.0'


def write_pair(directory, cert='CERTDATA', key='KEYDATA'):
    (directory / 'stanford_workgroup.cert').write_text(cert)
    (directory / 'stanford_workgroup.key').write_text(key)


# ------------------------------------------------------------------ server selection
def test_defaults_to_production():
    assert WorkgroupAuth(auto_auth=False)._base_url == PROD


def test_use_uat_true_selects_uat():
    assert WorkgroupAuth(auto_auth=False, use_uat=True)._base_url == UAT


def test_env_var_selects_uat(monkeypatch):
    monkeypatch.setenv('WORKGROUP_UAT', 'true')
    assert WorkgroupAuth(auto_auth=False)._base_url == UAT


def test_env_var_is_case_insensitive(monkeypatch):
    monkeypatch.setenv('WORKGROUP_UAT', 'TRUE')
    assert WorkgroupAuth(auto_auth=False)._base_url == UAT


def test_explicit_false_beats_the_env_var(monkeypatch):
    """An explicit argument must win, or a stray shell export silently redirects writes."""
    monkeypatch.setenv('WORKGROUP_UAT', 'true')
    assert WorkgroupAuth(auto_auth=False, use_uat=False)._base_url == PROD


def test_any_other_env_value_means_production(monkeypatch):
    monkeypatch.setenv('WORKGROUP_UAT', 'yes')
    assert WorkgroupAuth(auto_auth=False)._base_url == PROD


# ------------------------------------------------------- credential discovery order
def test_explicit_creds_take_precedence(isolated_auth_dir, monkeypatch, tmp_path):
    """The `creds` argument is level 1 of the chain and must beat the env vars."""
    cert, key = tmp_path / 'c.pem', tmp_path / 'k.pem'
    cert.write_text('c')
    key.write_text('k')
    monkeypatch.setenv('WORKGROUP_CERT_PATH', '/should/be/ignored')
    monkeypatch.setenv('WORKGROUP_KEY_PATH', '/should/be/ignored')

    auth = WorkgroupAuth(creds=(str(cert), str(key)), auto_auth=False)
    monkeypatch.setattr(auth, 'make_request', lambda *a, **k: _ok())
    auth.authenticate()

    assert auth._auth_method == 'file'
    assert auth._credentials == (str(cert), str(key)), 'env vars must not override explicit creds'


def test_creds_must_be_a_tuple_of_strings():
    with pytest.raises(InvalidAuthInfo):
        WorkgroupAuth(creds=['a', 'b'], auto_auth=False)
    with pytest.raises(InvalidAuthInfo):
        WorkgroupAuth(creds=(1, 2), auto_auth=False)


def test_path_env_vars_used_when_no_creds_passed(isolated_auth_dir, monkeypatch):
    write_pair(isolated_auth_dir)
    cert = isolated_auth_dir / 'stanford_workgroup.cert'
    key = isolated_auth_dir / 'stanford_workgroup.key'
    monkeypatch.setenv('WORKGROUP_CERT_PATH', str(cert))
    monkeypatch.setenv('WORKGROUP_KEY_PATH', str(key))

    auth = WorkgroupAuth(auto_auth=False)
    monkeypatch.setattr(auth, 'make_request', lambda *a, **k: _ok())
    auth.authenticate()
    assert auth._auth_method == 'file'
    assert auth._credentials == (str(cert), str(key))


def test_content_env_vars_select_memory_mode(monkeypatch, isolated_auth_dir):
    monkeypatch.setenv('WORKGROUP_CERT', 'CERT-CONTENT')
    monkeypatch.setenv('WORKGROUP_KEY', 'KEY-CONTENT')
    auth = WorkgroupAuth(auto_auth=False)
    monkeypatch.setattr(auth, 'make_request', lambda *a, **k: _ok())
    auth.authenticate()
    assert auth._auth_method == 'memory'


def test_falls_back_to_the_default_file_pair(isolated_auth_dir, monkeypatch):
    write_pair(isolated_auth_dir)
    auth = WorkgroupAuth(auto_auth=False)
    monkeypatch.setattr(auth, 'make_request', lambda *a, **k: _ok())
    auth.authenticate()
    assert auth._auth_method == 'file'
    assert auth._credentials[0].endswith('stanford_workgroup.cert')


def test_missing_files_raise_rather_than_calling_the_api(isolated_auth_dir):
    """
    Nothing on disk, nothing in the env. This must fail before any request -- and the autouse
    no_network fixture would catch it if it didn't.
    """
    with pytest.raises(InvalidAuthInfo, match='cert and key file paths'):
        WorkgroupAuth(auto_auth=False).authenticate()


def test_partial_env_config_is_ignored(isolated_auth_dir, monkeypatch):
    """Only the cert, no key: must not be treated as usable env config."""
    monkeypatch.setenv('WORKGROUP_CERT', 'CERT-ONLY')
    with pytest.raises(InvalidAuthInfo):
        WorkgroupAuth(auto_auth=False).authenticate()


# ---------------------------------------------------------------- request plumbing
def test_file_mode_passes_the_cert_pair_to_requests(isolated_auth_dir, monkeypatch):
    write_pair(isolated_auth_dir)
    auth = WorkgroupAuth(auto_auth=False)
    auth._auth_method = 'file'
    auth._credentials = ('cert-path', 'key-path')

    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return _ok()

    monkeypatch.setattr('cardinal_glue.workgroup_api.workgroupauth.requests.request', fake_request)
    auth.make_request('get', 'https://example.test/x')
    assert captured['cert'] == ('cert-path', 'key-path')


def test_memory_mode_writes_temp_files_and_passes_their_paths(monkeypatch, isolated_auth_dir):
    """
    Memory mode exists for containers, where the cert arrives as an env string. The temp files
    must exist at request time (they are deleted on close).
    """
    monkeypatch.setenv('WORKGROUP_CERT', 'CERT-CONTENT')
    monkeypatch.setenv('WORKGROUP_KEY', 'KEY-CONTENT')
    auth = WorkgroupAuth(auto_auth=False)
    auth._auth_method = 'memory'

    seen = {}

    def fake_request(method, url, **kwargs):
        cert_path, key_path = kwargs['cert']
        seen['cert_body'] = open(cert_path).read()
        seen['key_body'] = open(key_path).read()
        return _ok()

    monkeypatch.setattr('cardinal_glue.workgroup_api.workgroupauth.requests.request', fake_request)
    auth.make_request('get', 'https://example.test/x')
    assert seen == {'cert_body': 'CERT-CONTENT', 'key_body': 'KEY-CONTENT'}


def _ok():
    from conftest import FakeResponse
    return FakeResponse(200, {})
