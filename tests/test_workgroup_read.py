"""Read paths: populate_workgroup, privgroup, member accessors, and the stem search."""
import pytest

from cardinal_glue.workgroup_api.workgroup import (
    Workgroup,
    WorkgroupAPIError,
    WorkgroupManager,
)

from conftest import FakeResponse, workgroup_payload


def make_wg(auth, payload=None, stem='dbp', name='courses'):
    auth.route('get', f'/{stem}:{name}', 200, payload or workgroup_payload())
    return Workgroup(stem, name, auth=auth)


# --------------------------------------------------------------------------- populate
def test_populate_parses_every_field(auth):
    wg = make_wg(auth)
    wg.populate_workgroup()
    assert wg.description == 'umbrella group'
    assert wg._filter == 'NONE'
    assert wg._visibility == 'PRIVATE'
    assert wg._reusable == 'TRUE'
    assert wg._privgroup == 'TRUE'
    assert wg._integrations == []


def test_properties_populate_lazily_once(auth):
    wg = make_wg(auth)
    _ = wg.members
    _ = wg.admins
    _ = wg.description
    assert len(auth.calls_of('get')) == 1, 'should populate once, then serve from cache'


def test_members_is_the_documented_mixed_shape(auth):
    """
    `.members` deliberately keeps its historical shape: bare ids for people and certificates,
    stem-qualified for nested workgroups, type discarded. flaskboot's nesting check depends on
    this exact behaviour, so a change here is a breaking change.
    """
    wg = make_wg(auth)
    assert wg.members == ['dbp:basics', 'alovelace', 'dbp-wrkgrp']


def test_typed_accessors_split_by_type(auth):
    wg = make_wg(auth)
    assert wg.person_members == ['alovelace']
    assert wg.workgroup_members == ['dbp:basics']
    assert wg.certificate_members == ['dbp-wrkgrp']


def test_person_members_accepts_both_read_and_write_vocabulary(auth):
    """The live API says PERSON; USER is the write spelling. Both must count as people."""
    payload = workgroup_payload(members=[
        {'id': 'aaa', 'type': 'PERSON'},
        {'id': 'bbb', 'type': 'USER'},
        {'id': 'dbp:x', 'type': 'WORKGROUP'},
    ])
    wg = make_wg(auth, payload)
    assert wg.person_members == ['aaa', 'bbb']


def test_typed_accessors_skip_entries_missing_id_or_type(auth):
    payload = workgroup_payload(members=[
        {'id': 'aaa', 'type': 'PERSON'},
        {'type': 'PERSON'},          # no id
        {'id': 'ccc'},               # no type
    ])
    wg = make_wg(auth, payload)
    assert wg.person_members == ['aaa']


def test_empty_membership(auth):
    wg = make_wg(auth, workgroup_payload(members=[]))
    assert wg.members == []
    assert wg.person_members == []


# --------------------------------------------------------------------------- privgroup
def test_populate_privgroup_uses_its_own_endpoint(auth):
    auth.route('get', '/dbp:courses/privgroup', 200,
               {'members': [{'id': 'aaa'}], 'administrators': []})
    wg = Workgroup('dbp', 'courses', auth=auth)
    assert wg.privgroup_members == [{'id': 'aaa'}]
    assert auth.urls[-1].endswith('/dbp:courses/privgroup')


# --------------------------------------------------------- populate_workgroup_list (regression)
def test_search_url_uses_colon_wildcard(auth):
    """
    Regression guard: searching '{stem}*' makes the API reject any stem shorter than 4 chars
    ("Search String length must be at least 4 characters before using wildcards"), which made
    the entire 'dbp' stem look empty. The colon supplies the 4th character.
    """
    auth.route('get', '/search/dbp:*', 200, {'results': [{'name': 'dbp:100'}]})
    mgr = WorkgroupManager('dbp', auth=auth)
    mgr.populate_workgroup_list()
    assert auth.urls[0].endswith('/search/dbp:*')
    assert '/search/dbp*' not in auth.urls[0]


def test_search_strips_only_the_last_colon_segment(auth):
    """
    Regression guard: split(':')[1] returned the middle token for stems that contain a colon,
    so 'som:it:some-group' became 'it'.
    """
    auth.route('get', '/search/som:it:*', 200,
               {'results': [{'name': 'som:it:some-group'}, {'name': 'som:it:other'}]})
    mgr = WorkgroupManager('som:it', auth=auth)
    mgr.populate_workgroup_list()
    assert mgr.workgroup_list == ['some-group', 'other']


def test_search_raises_instead_of_returning_empty(auth):
    """
    Regression guard: the old code did .json().get('results', []) with no status check, so every
    error became an empty list -- indistinguishable from a genuinely empty stem.
    """
    auth.route('get', '/search/dbp:*', 400,
               {'notification': 'Search String length must be at least 4 characters'})
    mgr = WorkgroupManager('dbp', auth=auth)
    with pytest.raises(WorkgroupAPIError):
        mgr.populate_workgroup_list()
    assert mgr.workgroup_list is None, 'must not leave a misleading empty list behind'


def test_search_skips_results_without_a_name(auth):
    auth.route('get', '/search/dbp:*', 200,
               {'results': [{'name': 'dbp:100'}, {'description': 'nameless'}]})
    mgr = WorkgroupManager('dbp', auth=auth)
    mgr.populate_workgroup_list()
    assert mgr.workgroup_list == ['100']


def test_search_empty_stem_is_an_empty_list_not_an_error(auth):
    auth.route('get', '/search/dbp:*', 200, {'results': []})
    mgr = WorkgroupManager('dbp', auth=auth)
    mgr.populate_workgroup_list()
    assert mgr.workgroup_list == []
