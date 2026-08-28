"""QualtricsAuth. Note: authenticate() is currently broken -- see the xfail below."""
import json

import pytest

from cardinal_glue.auth.core import InvalidAuthInfo
from cardinal_glue.qualtrics_api.qualtricsauth import (
    QualtricsAPIError,
    QualtricsAuth,
    QualtricsError,
)


def test_module_imports_and_exceptions_are_defined():
    assert issubclass(QualtricsAPIError, QualtricsError)


def test_missing_config_file_raises(isolated_auth_dir):
    """This path never reaches the missing `requests` reference, so it works today."""
    with pytest.raises(InvalidAuthInfo, match='Qualtrics authentication information'):
        QualtricsAuth()


def test_missing_data_center_raises(isolated_auth_dir):
    (isolated_auth_dir / 'qualtrics.json').write_text(json.dumps({'api_token': 't'}))
    with pytest.raises(InvalidAuthInfo, match='data_center'):
        QualtricsAuth()


def test_neither_token_nor_client_credentials_raises(isolated_auth_dir):
    (isolated_auth_dir / 'qualtrics.json').write_text(json.dumps({'data_center': 'ca1'}))
    with pytest.raises(InvalidAuthInfo, match='api_token'):
        QualtricsAuth()


def test_client_id_without_secret_raises(isolated_auth_dir):
    (isolated_auth_dir / 'qualtrics.json').write_text(
        json.dumps({'data_center': 'ca1', 'client_id': 'i'}))
    with pytest.raises(InvalidAuthInfo):
        QualtricsAuth()


@pytest.mark.xfail(
    reason="BUG: qualtricsauth.py calls requests.request() three times but never imports "
           "requests (imports are os, re, json, logging, and cardinal_glue.auth.core). Any "
           "successful config therefore dies with NameError, so QualtricsAuth cannot "
           "authenticate at all. Fix: add `import requests`.",
    raises=NameError,
    strict=True,
)
def test_valid_api_token_config_should_authenticate(isolated_auth_dir, monkeypatch):
    (isolated_auth_dir / 'qualtrics.json').write_text(
        json.dumps({'data_center': 'ca1', 'api_token': 'TOKEN'}))
    QualtricsAuth()


@pytest.mark.xfail(
    reason="Same missing `import requests` -- the OAuth branch is equally unreachable.",
    raises=NameError,
    strict=True,
)
def test_valid_oauth_config_should_authenticate(isolated_auth_dir):
    (isolated_auth_dir / 'qualtrics.json').write_text(
        json.dumps({'data_center': 'ca1', 'client_id': 'i', 'client_secret': 's'}))
    QualtricsAuth()
