"""WorkgroupManager: create, delete, google-link handling, and copy."""
import pytest

from cardinal_glue.workgroup_api import workgroup as wg_mod
from cardinal_glue.workgroup_api.workgroup import (
    LinkageRemovalFailed,
    WorkgroupAPIError,
    WorkgroupAlreadyExists,
    WorkgroupManager,
    WorkgroupNotFound,
    WorkgroupPermissionDenied,
)

from conftest import FakeResponse, workgroup_payload


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """_add_google_link retries with exponential backoff; don't actually wait 30s."""
    monkeypatch.setattr(wg_mod.time, 'sleep', lambda *_: None)


@pytest.fixture
def mgr(auth):
    return WorkgroupManager('dbp', auth=auth)


# ------------------------------------------------------------------------- create
def test_create_posts_settings_and_returns_status(mgr, auth):
    auth.route('post', '/dbp:newgroup', 201, {})
    result = mgr.create_workgroup('newgroup', 'a description')
    assert result['statusCode'] == 201
    method, url, params, _ = auth.calls[0]
    assert method == 'post' and url.endswith('/dbp:newgroup')
    assert params == {'description': 'a description', 'filter': 'NONE',
                      'reusable': 'FALSE', 'visibility': 'PRIVATE', 'privgroup': 'TRUE'}


def test_create_lowercases_the_name(mgr, auth):
    auth.route('post', '/dbp:mixedcase', 201, {})
    mgr.create_workgroup('MixedCase', 'd')
    assert auth.urls[0].endswith('/dbp:mixedcase')


def test_create_conflict_raises_already_exists(mgr, auth):
    auth.route('post', '/dbp:dup', 409, {})
    with pytest.raises(WorkgroupAlreadyExists):
        mgr.create_workgroup('dup', 'd')


def test_create_permission_denied(mgr, auth):
    auth.route('post', '/dbp:x', 401, {})
    with pytest.raises(WorkgroupPermissionDenied):
        mgr.create_workgroup('x', 'd')


def test_create_unexpected_status(mgr, auth):
    auth.route('post', '/dbp:x', 500, {})
    with pytest.raises(WorkgroupAPIError):
        mgr.create_workgroup('x', 'd')


def test_create_with_google_link_puts_to_links(mgr, auth):
    auth.route('post', '/dbp:g', 201, {})
    auth.route('put', '/dbp:g/links', 201, {})
    mgr.create_workgroup('g', 'd', add_google_link=True)
    link_calls = [c for c in auth.calls if c[1].endswith('/links')]
    assert link_calls and link_calls[0][2] == {'link': 'GOOGLE'}


def test_google_link_retries_while_the_group_propagates(mgr, auth):
    """A freshly created workgroup 404s on /links until it propagates; that must be retried."""
    auth.route('post', '/dbp:g', 201, {})
    auth.queue(FakeResponse(404, {}), FakeResponse(404, {}), FakeResponse(201, {}))
    mgr.create_workgroup('g', 'd', add_google_link=True)
    assert len([c for c in auth.calls if c[1].endswith('/links')]) == 3


def test_no_google_link_by_default(mgr, auth):
    auth.route('post', '/dbp:g', 201, {})
    mgr.create_workgroup('g', 'd')
    assert not [c for c in auth.calls if c[1].endswith('/links')]


# ------------------------------------------------------------------------- delete
def test_delete_sends_delete(mgr, auth):
    auth.route('delete', '/dbp:old', 200, {})
    assert mgr.delete_workgroup('old')['statusCode'] == 200


def test_delete_missing_raises_notfound(mgr, auth):
    auth.route('delete', '/dbp:ghost', 404, {})
    with pytest.raises(WorkgroupNotFound):
        mgr.delete_workgroup('ghost')


def test_delete_removes_google_link_first(mgr, auth):
    auth.route('delete', '/dbp:old/links', 200, {})
    auth.route('delete', '/dbp:old', 200, {})
    mgr.delete_workgroup('old', remove_google_link=True)
    assert auth.urls[0].endswith('/links'), 'linkage must go before the workgroup'


def test_absent_linkage_does_not_block_deletion(mgr, auth):
    """404, and the API's odd 400 'does not have linkage', both mean "nothing to unlink"."""
    auth.route('delete', '/dbp:old/links', 400, {'message': 'workgroup does not have linkage'})
    auth.route('delete', '/dbp:old', 200, {})
    assert mgr.delete_workgroup('old', remove_google_link=True)['statusCode'] == 200


def test_failed_unlink_aborts_deletion(mgr, auth):
    """
    Refusing to delete is correct: a workgroup with a live Google linkage can't be removed
    cleanly, and deleting it anyway would orphan the group.
    """
    auth.route('delete', '/dbp:old/links', 500, {})
    with pytest.raises(LinkageRemovalFailed):
        mgr.delete_workgroup('old', remove_google_link=True)
    assert not [c for c in auth.calls if c[0] == 'delete' and c[1].endswith('/dbp:old')]


# --------------------------------------------------------------------------- copy
def test_copy_replicates_settings_admins_and_members(mgr, auth):
    source = workgroup_payload(
        members=[{'id': 'alovelace', 'type': 'PERSON'}, {'id': 'dbp:basics', 'type': 'WORKGROUP'}],
        administrators=[{'id': 'bdgrier', 'type': 'PERSON'}],
        description='umbrella group for DBP short courses',
    )
    auth.route('get', '/dbp:short_courses', 200, source)
    auth.route('post', '/dbp:courses', 201, {})
    auth.route('get', '/dbp:courses', 200, workgroup_payload(members=[], administrators=[]))

    result = mgr.copy_workgroup('short_courses', new_name='courses')
    assert result['statusCode'] == 200

    create = [c for c in auth.calls if c[0] == 'post'][0]
    assert create[2]['description'] == 'umbrella group for DBP short courses'
    assert create[2]['visibility'] == 'PRIVATE'
    assert create[2]['reusable'] == 'TRUE'

    # PERSON must be translated to USER for the write side
    member_puts = [c for c in auth.calls if c[0] == 'put' and '/members/' in c[1]]
    assert ('USER', True) == ((member_puts[0][2] or {}).get('type'),
                              member_puts[0][1].endswith('/alovelace'))
    types = {(c[2] or {}).get('type') for c in member_puts}
    assert types == {'USER', 'WORKGROUP'}
    assert any(c[1].endswith('/administrators/bdgrier') for c in auth.calls)


def test_copy_refuses_to_copy_onto_itself(mgr):
    with pytest.raises(ValueError):
        mgr.copy_workgroup('same', new_name='same')


def test_copy_of_missing_source_reports_404_without_creating(mgr, auth):
    auth.route('get', '/dbp:ghost', 404, {})
    result = mgr.copy_workgroup('ghost', new_name='target')
    assert result['statusCode'] == 404
    assert not [c for c in auth.calls if c[0] == 'post']


def test_copy_carries_the_google_link(mgr, auth):
    auth.route('get', '/dbp:src', 200,
               workgroup_payload(integrations=[{'GOOGLE': 'dbp_src'}], members=[], administrators=[]))
    auth.route('post', '/dbp:dst', 201, {})
    auth.route('get', '/dbp:dst', 200, workgroup_payload(members=[], administrators=[]))
    auth.route('put', '/dbp:dst/links', 201, {})
    mgr.copy_workgroup('src', new_name='dst')
    assert any(c[1].endswith('/dbp:dst/links') for c in auth.calls)


def test_copy_with_remove_original_deletes_the_source(mgr, auth):
    auth.route('get', '/dbp:src', 200, workgroup_payload(members=[], administrators=[]))
    auth.route('post', '/dbp:dst', 201, {})
    auth.route('get', '/dbp:dst', 200, workgroup_payload(members=[], administrators=[]))
    auth.route('delete', '/dbp:src', 200, {})
    mgr.copy_workgroup('src', new_name='dst', remove_original=True)
    assert any(c[0] == 'delete' and c[1].endswith('/dbp:src') for c in auth.calls)


def test_copy_preserves_the_original_when_the_google_link_fails(mgr, auth):
    """
    The safety property that matters most in copy_workgroup: an incomplete replication must never
    be followed by deleting the source.
    """
    auth.route('get', '/dbp:src', 200,
               workgroup_payload(integrations=[{'GOOGLE': 'dbp_src'}], members=[], administrators=[]))
    auth.route('post', '/dbp:dst', 201, {})
    auth.route('get', '/dbp:dst', 200, workgroup_payload(members=[], administrators=[]))
    auth.route('put', '/dbp:dst/links', 500, {})     # linkage fails
    result = mgr.copy_workgroup('src', new_name='dst', remove_original=True)
    assert result['statusCode'] == 207
    assert not [c for c in auth.calls if c[0] == 'delete'], 'source must survive a partial copy'


def test_copy_onto_existing_target_requires_overwrite(mgr, auth):
    auth.route('get', '/dbp:src', 200, workgroup_payload(members=[], administrators=[]))
    auth.route('post', '/dbp:dst', 409, {})
    result = mgr.copy_workgroup('src', new_name='dst')
    assert result['statusCode'] == 500, 'the AlreadyExists is caught and reported as an error'


def test_copy_overwrite_syncs_into_the_existing_target(mgr, auth):
    auth.route('get', '/dbp:src', 200,
               workgroup_payload(members=[{'id': 'alovelace', 'type': 'PERSON'}], administrators=[]))
    auth.route('post', '/dbp:dst', 409, {})
    auth.route('get', '/dbp:dst', 200, workgroup_payload(members=[], administrators=[]))
    result = mgr.copy_workgroup('src', new_name='dst', overwrite=True)
    assert result['statusCode'] == 200
    assert any(c[1].endswith('/members/alovelace') for c in auth.calls)
