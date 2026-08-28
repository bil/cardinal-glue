"""Status-code to exception mapping on the read paths, and the soft-delete case."""
import pytest

from cardinal_glue.workgroup_api.workgroup import (
    Workgroup,
    WorkgroupAPIError,
    WorkgroupError,
    WorkgroupInactive,
    WorkgroupNotFound,
    WorkgroupPermissionDenied,
    raise_for_workgroup_status,
)

from conftest import FakeResponse


# ------------------------------------------------------------------ exception hierarchy
def test_inactive_is_a_notfound():
    """
    Deliberate subclassing. Existing callers -- including
    flaskboot's delete_course_term_workgroup -- catch WorkgroupNotFound, and a deleted workgroup
    should satisfy them without a code change.
    """
    assert issubclass(WorkgroupInactive, WorkgroupNotFound)
    assert issubclass(WorkgroupNotFound, WorkgroupError)


# ------------------------------------------------------------------ the helper directly
@pytest.mark.parametrize('status,body,expected', [
    (404, {}, WorkgroupNotFound),
    (401, {}, WorkgroupPermissionDenied),
    (403, {}, WorkgroupPermissionDenied),
    (500, {}, WorkgroupAPIError),
    (400, {'notification': 'something else entirely'}, WorkgroupAPIError),
    (400, {'notification': 'Workgroup is inactive.'}, WorkgroupInactive),
])
def test_status_mapping(status, body, expected):
    with pytest.raises(expected):
        raise_for_workgroup_status(FakeResponse(status, body), 'thing')


def test_200_does_not_raise():
    raise_for_workgroup_status(FakeResponse(200, {}), 'thing')


def test_inactive_detected_case_insensitively():
    with pytest.raises(WorkgroupInactive):
        raise_for_workgroup_status(FakeResponse(400, {'notification': 'WORKGROUP IS INACTIVE'}), 'x')


def test_inactive_detected_from_message_field():
    """The API isn't consistent about which key carries the explanation."""
    with pytest.raises(WorkgroupInactive):
        raise_for_workgroup_status(FakeResponse(400, {'message': 'Workgroup is inactive.'}), 'x')


def test_unparseable_body_falls_back_to_a_generic_error():
    """A 400 with no JSON must still raise, not blow up inside the error handler."""
    with pytest.raises(WorkgroupAPIError):
        raise_for_workgroup_status(FakeResponse(400, None, text='<html>gateway</html>'), 'x')


def test_error_message_names_the_subject():
    with pytest.raises(WorkgroupNotFound, match='dbp:missing'):
        raise_for_workgroup_status(FakeResponse(404, {}), "Workgroup 'dbp:missing'")


# ---------------------------------------------------------------- through the read paths
def test_populate_workgroup_raises_inactive_for_deleted_group(auth):
    """
    Regression guard: a deleted workgroup answers 400 'Workgroup is inactive', not 404. Before
    the fix this surfaced as a bare WorkgroupAPIError and every `except WorkgroupNotFound` missed
    it -- which is exactly what crashed a verification script after a real rename.
    """
    auth.route('get', '/dbp:gone', 400, {'notification': 'Workgroup is inactive.', 'code': 400})
    with pytest.raises(WorkgroupInactive):
        Workgroup('dbp', 'gone', auth=auth).populate_workgroup()


def test_deleted_group_is_caught_by_notfound_handlers(auth):
    auth.route('get', '/dbp:gone', 400, {'notification': 'Workgroup is inactive.'})
    try:
        Workgroup('dbp', 'gone', auth=auth).populate_workgroup()
    except WorkgroupNotFound:
        pass  # what an existing caller writes
    else:
        pytest.fail('a deleted workgroup must satisfy except WorkgroupNotFound')


def test_populate_workgroup_404(auth):
    auth.route('get', '/dbp:never', 404, {})
    with pytest.raises(WorkgroupNotFound):
        Workgroup('dbp', 'never', auth=auth).populate_workgroup()


def test_populate_privgroup_maps_errors_too(auth):
    auth.route('get', '/dbp:x/privgroup', 401, {})
    with pytest.raises(WorkgroupPermissionDenied):
        Workgroup('dbp', 'x', auth=auth).populate_privgroup()


def test_failed_populate_leaves_the_object_unpopulated(auth):
    """No half-populated state after a failure -- otherwise a retry would serve garbage."""
    auth.route('get', '/dbp:gone', 400, {'notification': 'Workgroup is inactive.'})
    wg = Workgroup('dbp', 'gone', auth=auth)
    with pytest.raises(WorkgroupNotFound):
        wg.populate_workgroup()
    assert wg._populated is False
    assert wg._members is None
