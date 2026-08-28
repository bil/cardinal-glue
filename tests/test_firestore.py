"""
FirestoreGenerator: database_id discovery and the three authentication branches.

The google clients are monkeypatched -- these tests assert which branch runs and what it is
handed, never that a real Firestore connection works.
"""
import json

import pytest

from cardinal_glue.auth.core import InvalidAuthInfo
from cardinal_glue import firestore as fs_mod
from cardinal_glue.firestore import FirestoreGenerator

SERVICE_ACCOUNT = {
    'type': 'service_account',
    'project_id': 'dor-wtni-dbpportal',
    'private_key_id': 'x',
    'client_email': 'sa@example.iam.gserviceaccount.com',
}


@pytest.fixture
def stub_google(monkeypatch):
    """Replace both client paths and firebase_admin with recorders."""
    calls = {'v1': [], 'firebase_client': [], 'initialize_app': 0, 'certificate': []}

    class FakeV1Client:
        def __init__(self, database=None, credentials=None):
            calls['v1'].append({'database': database, 'credentials': credentials})

    class FakeCredentials:
        @staticmethod
        def Certificate(cred_dict):
            calls['certificate'].append(cred_dict)
            return 'CERT-OBJECT'

    class FakeFirebaseAdmin:
        _apps = {}
        credentials = FakeCredentials

        @staticmethod
        def initialize_app(creds):
            calls['initialize_app'] += 1
            return 'APP'

        @staticmethod
        def get_app():
            return 'EXISTING-APP'

    def fake_firebase_client(app, database_id=None):
        calls['firebase_client'].append({'app': app, 'database_id': database_id})
        return 'FIREBASE-DB'

    monkeypatch.setattr(fs_mod.firestore_v1, 'Client', FakeV1Client)
    monkeypatch.setattr(fs_mod, 'firebase_admin', FakeFirebaseAdmin)
    monkeypatch.setattr(fs_mod.firestore, 'client', fake_firebase_client)
    return calls


# ------------------------------------------------------------------- database_id
def test_database_id_from_argument(isolated_auth_dir, stub_google):
    gen = FirestoreGenerator(database_id='dbp-workshops', auto_auth=False)
    assert gen.database_id == 'dbp-workshops'


def test_database_id_read_from_firestore_json(isolated_auth_dir, stub_google):
    (isolated_auth_dir / 'firestore.json').write_text(json.dumps({'DATABASE_ID': 'from-file'}))
    (isolated_auth_dir / 'firebase.json').write_text(json.dumps(SERVICE_ACCOUNT))
    assert FirestoreGenerator().database_id == 'from-file'


def test_argument_beats_the_file(isolated_auth_dir, stub_google):
    (isolated_auth_dir / 'firestore.json').write_text(json.dumps({'DATABASE_ID': 'from-file'}))
    (isolated_auth_dir / 'firebase.json').write_text(json.dumps(SERVICE_ACCOUNT))
    assert FirestoreGenerator(database_id='explicit').database_id == 'explicit'


def test_no_id_and_no_file_raises(isolated_auth_dir, stub_google):
    with pytest.raises(InvalidAuthInfo, match='database_id'):
        FirestoreGenerator()


def test_file_without_the_key_raises(isolated_auth_dir, stub_google):
    (isolated_auth_dir / 'firestore.json').write_text(json.dumps({'other': 'value'}))
    with pytest.raises(InvalidAuthInfo, match='DATABASE_ID'):
        FirestoreGenerator()


def test_auto_auth_false_skips_authentication(isolated_auth_dir, stub_google):
    gen = FirestoreGenerator(database_id='d', auto_auth=False)
    assert not hasattr(gen, 'database')
    assert stub_google['v1'] == [] and stub_google['firebase_client'] == []


# ------------------------------------------------------------------ auth branches
def test_cloud_run_uses_ambient_credentials(isolated_auth_dir, stub_google, monkeypatch):
    """
    On Cloud Run (K_REVISION set) the runtime service account is used directly -- no key file.
    This is the branch flaskboot actually runs in production.
    """
    monkeypatch.setenv('K_REVISION', 'portal-00042-abc')
    FirestoreGenerator(database_id='dbp-workshops')
    assert stub_google['v1'] == [{'database': 'dbp-workshops', 'credentials': None}]
    assert stub_google['initialize_app'] == 0, 'must not touch firebase_admin on Cloud Run'


def test_local_uses_the_firebase_service_account_file(isolated_auth_dir, stub_google):
    (isolated_auth_dir / 'firebase.json').write_text(json.dumps(SERVICE_ACCOUNT))
    gen = FirestoreGenerator(database_id='dbp-workshops-dev')
    assert stub_google['certificate'] == [SERVICE_ACCOUNT]
    assert stub_google['initialize_app'] == 1
    assert stub_google['firebase_client'] == [{'app': 'APP', 'database_id': 'dbp-workshops-dev'}]
    assert gen.database == 'FIREBASE-DB'


def test_local_without_a_key_file_raises(isolated_auth_dir, stub_google):
    with pytest.raises(InvalidAuthInfo, match='valid json file'):
        FirestoreGenerator(database_id='d')


def test_existing_firebase_app_is_reused(isolated_auth_dir, stub_google, monkeypatch):
    """Re-initializing firebase_admin raises, so an already-initialized app must be reused."""
    (isolated_auth_dir / 'firebase.json').write_text(json.dumps(SERVICE_ACCOUNT))
    monkeypatch.setattr(fs_mod.firebase_admin, '_apps', {'[DEFAULT]': 'APP'})
    FirestoreGenerator(database_id='d')
    assert stub_google['initialize_app'] == 0
    assert stub_google['firebase_client'][0]['app'] == 'EXISTING-APP'


# ------------------------------------------------------- constructor side effect
def test_google_cloud_project_is_exported_to_the_environment(isolated_auth_dir, stub_google,
                                                             monkeypatch):
    """
    Documents a side effect rather than endorsing it: passing google_cloud_project mutates
    os.environ for the whole process. It is how the Colab branch and downstream google libraries
    pick the project up, but it means constructing this object changes global state.
    """
    import os
    monkeypatch.setenv('K_REVISION', 'x')
    FirestoreGenerator(database_id='d', google_cloud_project='some-project')
    assert os.environ['GOOGLE_CLOUD_PROJECT'] == 'some-project'
