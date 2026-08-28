"""Write paths: add/remove members and admins -- type aliasing, qualification, filtering."""
import pytest

from cardinal_glue.workgroup_api.workgroup import (
    Workgroup,
    WorkgroupAPIError,
    WorkgroupNotFound,
    WorkgroupPermissionDenied,
)

from conftest import FakeResponse, workgroup_payload


@pytest.fixture
def wg(auth):
    """A populated dbp:all whose members are dbp:basics (nested), alovelace, dbp-wrkgrp (cert)."""
    auth.route('get', '/dbp:all', 200, workgroup_payload())
    return Workgroup('dbp', 'all', auth=auth)


def puts(auth):
    return [c for c in auth.calls if c[0] == 'put']


def deletes(auth):
    return [c for c in auth.calls if c[0] == 'delete']


# ----------------------------------------------------------------- type aliasing (C.1)
def test_person_is_accepted_and_sent_as_user(wg, auth):
    """
    A GET returns type PERSON; the write API only accepts USER. Feeding a type straight back
    from a read is the natural thing to do, so it must work.
    """
    wg.add_members(['newperson'], member_type='PERSON')
    assert [(c[2] or {}).get('type') for c in puts(auth)] == ['USER']


def test_member_type_is_case_insensitive(wg, auth):
    wg.add_members(['newperson'], member_type='person')
    assert [(c[2] or {}).get('type') for c in puts(auth)] == ['USER']


def test_unsupported_member_type_rejected(wg):
    with pytest.raises(ValueError, match='member_type'):
        wg.add_members(['x'], member_type='ROBOT')


def test_admin_type_error_names_the_right_parameter(wg):
    with pytest.raises(ValueError, match='admin_type'):
        wg.add_admins(['x'], admin_type='ROBOT')


# ------------------------------------------------- qualify-before-filter (C.3 regression)
def test_remove_bare_workgroup_name_actually_issues_the_delete(wg, auth):
    """
    Regression guard for the worst of today's bugs. Qualification used to happen *after*
    filter_members compared the bare name against `.members` (which holds 'dbp:basics'), so the
    name was filtered out and the call reported success while removing nothing.
    """
    wg.remove_members(['basics'], member_type='WORKGROUP', filter_members=True)
    assert len(deletes(auth)) == 1, 'a silent no-op means this regressed'
    assert deletes(auth)[0][1].endswith('/dbp:basics')


def test_add_bare_workgroup_name_dedupes_against_qualified_member(wg, auth):
    """The same ordering bug, benign direction: a redundant PUT and a wasted 409."""
    wg.add_members(['basics'], member_type='WORKGROUP', filter_members=True)
    assert puts(auth) == []


def test_bare_workgroup_name_is_qualified_with_the_parent_stem(wg, auth):
    wg.add_members(['newgroup'], member_type='WORKGROUP')
    assert puts(auth)[0][1].endswith('/dbp:newgroup')


def test_member_stem_overrides_the_parent_stem(wg, auth):
    wg.add_members(['theirgroup'], member_type='WORKGROUP', member_stem='som:it')
    assert puts(auth)[0][1].endswith('/som:it:theirgroup')


def test_cross_stem_qualified_name_is_left_alone(wg, auth):
    """
    Already-qualified names must not be re-stemmed, or a cross-stem parent silently looks for the
    child in its own stem.
    """
    wg.add_members(['som:it:grp'], member_type='WORKGROUP')
    assert puts(auth)[0][1].endswith('/som:it:grp')


def test_people_are_never_qualified(wg, auth):
    wg.add_members(['alovelace2'], member_type='USER')
    assert puts(auth)[0][1].endswith('/alovelace2')


# ------------------------------------------------------------------------ filtering
def test_filter_members_skips_existing_person(wg, auth):
    wg.add_members(['alovelace'], filter_members=True)
    assert puts(auth) == []


def test_filter_members_off_by_default(wg, auth):
    wg.add_members(['alovelace'])
    assert len(puts(auth)) == 1, 'no filtering unless asked -- a 409 is tolerated'


def test_remove_filter_skips_non_member(wg, auth):
    wg.remove_members(['stranger'], filter_members=True)
    assert deletes(auth) == []


def test_scalar_member_is_accepted_as_well_as_a_list(wg, auth):
    wg.add_members('solo')
    assert puts(auth)[0][1].endswith('/solo')


# --------------------------------------------------------------------- status handling
def test_ignore_missing_skips_unknown_sunetid(wg, auth):
    auth.route('put', '/members/ghost', 404, {})
    wg.add_members(['ghost'], ignore_missing=True)   # must not raise


def test_missing_sunetid_raises_without_ignore_missing(wg, auth):
    auth.route('put', '/members/ghost', 404, {})
    with pytest.raises(WorkgroupNotFound):
        wg.add_members(['ghost'])


def test_409_on_add_is_tolerated(wg, auth):
    auth.route('put', '/members/dup', 409, {})
    wg.add_members(['dup'])   # already a member is not an error


def test_401_on_add_raises_permission_denied(wg, auth):
    auth.route('put', '/members/x', 401, {})
    with pytest.raises(WorkgroupPermissionDenied):
        wg.add_members(['x'])


def test_unexpected_status_on_add_raises(wg, auth):
    auth.route('put', '/members/x', 503, {})
    with pytest.raises(WorkgroupAPIError):
        wg.add_members(['x'])


def test_404_on_remove_is_not_an_error(wg, auth):
    """Removing someone who isn't a member is a no-op by design."""
    auth.route('delete', '/members/stranger', 404, {})
    wg.remove_members(['stranger'])


def test_401_on_remove_raises(wg, auth):
    auth.route('delete', '/members/alovelace', 401, {})
    with pytest.raises(WorkgroupPermissionDenied):
        wg.remove_members(['alovelace'])


def test_empty_list_makes_no_calls(wg, auth):
    before = len(auth.calls)
    wg.add_members([])
    wg.remove_members([])
    assert len(auth.calls) == before


# ----------------------------------------------------------------------- admins
def test_add_admins_sends_to_the_administrators_endpoint(wg, auth):
    wg.add_admins(['bdgrier2'])
    assert puts(auth)[0][1].endswith('/administrators/bdgrier2')


def test_add_admins_qualifies_workgroup_admins(wg, auth):
    wg.add_admins(['owners'], admin_type='WORKGROUP')
    assert puts(auth)[0][1].endswith('/administrators/dbp:owners')


def test_add_admins_accepts_person_and_certificate(wg, auth):
    wg.add_admins(['someone'], admin_type='PERSON')
    wg.add_admins(['dbp-wrkgrp'], admin_type='CERTIFICATE')
    assert [(c[2] or {}).get('type') for c in puts(auth)] == ['USER', 'CERTIFICATE']


def test_filter_admins_skips_existing(wg, auth):
    wg.add_admins(['bdgrier'], filter_admins=True)   # already an administrator in the payload
    assert puts(auth) == []


# ----------------------------------------------------------------- state refresh
def test_write_refreshes_cached_membership(auth):
    """Both add_members and remove_members re-populate, so cached state can't go stale."""
    auth.route('get', '/dbp:all', 200, workgroup_payload(members=[{'id': 'a', 'type': 'PERSON'}]))
    wg = Workgroup('dbp', 'all', auth=auth)
    assert wg.members == ['a']

    # shadow the earlier route so the next GET reflects the added member
    auth._routes.insert(0, ('get', '/dbp:all', FakeResponse(200, workgroup_payload(
        members=[{'id': 'a', 'type': 'PERSON'}, {'id': 'b', 'type': 'PERSON'}]))))
    wg.add_members(['b'])
    assert wg.members == ['a', 'b'], 'membership should reflect the write'
