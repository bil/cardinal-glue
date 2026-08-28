"""Tests for cardinal_glue.auth.core.Auth -- credential directory resolution."""
import os

import pytest

from cardinal_glue.auth.core import Auth, CannotInstantiateServiceObject, InvalidAuthInfo


def test_auth_path_defaults_under_config(isolated_auth_dir):
    """The fixture repoints _AUTH_PATH; constructing Auth must respect it, not the real ~/.config."""
    a = Auth()
    assert a._AUTH_PATH == str(isolated_auth_dir)
    assert '.config/cardinal-glue' not in a._AUTH_PATH


def test_set_auth_directory_creates_target(isolated_auth_dir, tmp_path):
    target = tmp_path / 'elsewhere'
    Auth().set_auth_directory(str(target))
    assert target.is_dir()


def test_set_auth_directory_MOVES_existing_credentials(isolated_auth_dir, tmp_path):
    """
    Documents a sharp edge rather than endorsing it: set_auth_directory does not merely point at
    a new location, it shutil.move()s every file out of the old one. Callers expecting setter
    semantics silently relocate their credentials.
    """
    (isolated_auth_dir / 'cap_client.json').write_text('{"client_id": "x"}')
    target = tmp_path / 'moved'

    a = Auth()
    a.set_auth_directory(str(target))

    assert (target / 'cap_client.json').exists(), 'file should have been moved to the new dir'
    assert not (isolated_auth_dir / 'cap_client.json').exists(), 'and removed from the old one'
    assert a._AUTH_PATH == str(target)


def test_set_auth_directory_mutates_the_class_not_just_the_instance(isolated_auth_dir, tmp_path):
    """
    _AUTH_PATH is assigned via `self._AUTH_PATH = new_path`, which shadows on the instance -- so a
    *second*, independently constructed Auth still sees the old path. Worth pinning: anything
    relying on a process-wide credential directory will be surprised.
    """
    target = tmp_path / 'instance_only'
    first = Auth()
    first.set_auth_directory(str(target))

    second = Auth()
    assert first._AUTH_PATH == str(target)
    assert second._AUTH_PATH == str(isolated_auth_dir), 'per-instance, not global'


def test_exception_hierarchy():
    """flaskboot catches these by name, so their identity matters."""
    assert issubclass(InvalidAuthInfo, Exception)
    assert issubclass(CannotInstantiateServiceObject, Exception)
    assert 'Unable to authenticate' in str(CannotInstantiateServiceObject())
