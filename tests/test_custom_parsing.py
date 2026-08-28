"""
transform_cap_profile: the pure function flaskboot leans on hardest.

Every business rule here is a decision someone made about real Stanford title data, so each gets
its own test -- a regression in this function silently mislabels people in the portal's
demographics rather than raising.
"""
import pytest

from cardinal_glue.cap_api.custom_parsing import transform_cap_profile


class StubCAP:
    """Stands in for CAPClient.get_org_from_code."""

    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.looked_up = []

    def get_org_from_code(self, org_code):
        self.looked_up.append(org_code)
        return self.mapping.get(org_code)


def profile(**overrides):
    base = {
        'displayName': 'Ada Lovelace',
        'affiliations': {'capStaff': True, 'capFaculty': False},
        'titles': [{'title': 'Research Manager', 'affiliation': 'capStaff',
                    'organization': {'orgCode': 'ABCD'}}],
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------------ empty input
@pytest.mark.parametrize('empty', [None, {}])
def test_empty_profile_returns_nulls(empty):
    result = transform_cap_profile('someuid', empty)
    assert result['uid'] == 'someuid'
    assert result['title'] is None
    assert result['affiliation'] is None
    assert result['display_name'] is None
    assert result['pi'] is None


@pytest.mark.xfail(
    reason="BUG: the `if not raw_profile` early return omits 'affiliation_mapped', while the "
           "normal return includes it. Callers that index the key -- rather than .get() it -- "
           "raise KeyError for any user whose CAP profile is missing or empty.",
    raises=KeyError,
    strict=True,
)
def test_empty_profile_should_still_have_affiliation_mapped():
    assert transform_cap_profile('someuid', None)['affiliation_mapped'] is None


# ---------------------------------------------------------------------- basic extraction
def test_display_name_passthrough():
    assert transform_cap_profile('u', profile())['display_name'] == 'Ada Lovelace'


def test_title_comes_from_the_first_title_affiliation_with_cap_stripped():
    result = transform_cap_profile('u', profile(
        affiliations={'capStaff': True},
        titles=[{'title': 'X', 'affiliation': 'capStaff'}]))
    assert result['title'] == 'staff'


def test_pi_from_first_stanford_advisor():
    result = transform_cap_profile('u', profile(stanfordAdvisors=[{'fullName': 'Grace Hopper'}]))
    assert result['pi'] == 'Grace Hopper'


@pytest.mark.parametrize('advisors', [[], None, ['not-a-dict'], [{}]])
def test_pi_absent_shapes(advisors):
    assert transform_cap_profile('u', profile(stanfordAdvisors=advisors))['pi'] is None


def test_missing_titles_leaves_title_none():
    assert transform_cap_profile('u', profile(titles=[]))['title'] is None


# --------------------------------------------------------------- organization resolution
def test_org_code_resolved_through_the_cap_client():
    cap = StubCAP({'ABCD': 'school-of-medicine'})
    result = transform_cap_profile('u', profile(), cap_client=cap)
    assert cap.looked_up == ['ABCD']
    assert result['affiliation'] == 'school-of-medicine'


def test_org_code_used_verbatim_without_a_client():
    assert transform_cap_profile('u', profile())['affiliation'] == 'ABCD'


def test_org_code_used_verbatim_when_lookup_fails():
    assert transform_cap_profile('u', profile(), cap_client=StubCAP({}))['affiliation'] == 'ABCD'


def test_null_org_code_is_ignored():
    result = transform_cap_profile('u', profile(
        titles=[{'title': 'X', 'affiliation': 'capStaff', 'organization': {'orgCode': 'NULL'}}]))
    assert result['affiliation'] is None


def test_affiliation_takes_only_the_first_path_segment():
    cap = StubCAP({'ABCD': 'school-of-medicine/department-of-genetics'})
    result = transform_cap_profile('u', profile(), cap_client=cap)
    assert result['affiliation'] == 'school-of-medicine'


def test_nkgv_is_rewritten_to_the_readable_name():
    """A hardcoded special case that would be invisible without a test."""
    result = transform_cap_profile('u', profile(
        titles=[{'title': 'X', 'affiliation': 'capStaff', 'organization': {'orgCode': 'NKGV'}}]))
    assert result['affiliation'] == 'vice-provost-and-dean-of-research'
    assert result['affiliation_mapped'] == 'VPDoR'


@pytest.mark.parametrize('org,expected', [
    ('school-of-medicine', 'SoM'),
    ('graduate-school-of-business', 'GSB'),
    ('school-of-engineering', 'SoE'),
    ('slac-national-accelerator-laboratory', 'SLAC'),
])
def test_known_affiliations_are_abbreviated(org, expected):
    cap = StubCAP({'ABCD': org})
    assert transform_cap_profile('u', profile(), cap_client=cap)['affiliation_mapped'] == expected


def test_unknown_affiliation_passes_through_unmapped():
    cap = StubCAP({'ABCD': 'some-new-school'})
    result = transform_cap_profile('u', profile(), cap_client=cap)
    assert result['affiliation_mapped'] == 'some-new-school'


# ------------------------------------------------------------------- registry rules
def test_registry_undergraduate():
    result = transform_cap_profile('u', profile(
        affiliations={'capRegistry': True},
        titles=[{'title': 'Undergraduate', 'affiliation': 'capRegistry'}]))
    assert result['title'] == 'undergraduate'


def test_registry_fellow_affiliation_wins_over_the_staff_default():
    result = transform_cap_profile('u', profile(
        affiliations={'capRegistry': True, 'capFellow': True},
        titles=[{'title': 'Something', 'affiliation': 'capRegistry'}]))
    assert result['title'] == 'fellow'


def test_registry_otherwise_becomes_staff():
    result = transform_cap_profile('u', profile(
        affiliations={'capRegistry': True},
        titles=[{'title': 'Something', 'affiliation': 'capRegistry'}]))
    assert result['title'] == 'staff'


# -------------------------------------------------------------------- faculty rules
def test_faculty_instructor_becomes_postdoc():
    result = transform_cap_profile('u', profile(
        affiliations={'capFaculty': True},
        titles=[{'title': 'Instructor', 'affiliation': 'capFaculty'}]))
    assert result['title'] == 'postdoc'


def test_faculty_research_scientist_becomes_staff():
    result = transform_cap_profile('u', profile(
        affiliations={'capFaculty': True},
        titles=[{'title': 'Senior Research Scientist', 'affiliation': 'capFaculty'}]))
    assert result['title'] == 'staff'


def test_plain_faculty_stays_faculty():
    result = transform_cap_profile('u', profile(
        affiliations={'capFaculty': True},
        titles=[{'title': 'Professor', 'affiliation': 'capFaculty'}]))
    assert result['title'] == 'faculty'


# --------------------------------------------------- staff+faculty dual-role override
def test_dual_role_with_a_real_staff_title_resolves_to_staff():
    result = transform_cap_profile('u', profile(
        affiliations={'capStaff': True, 'capFaculty': True},
        titles=[
            {'title': 'Professor', 'affiliation': 'capFaculty'},
            {'title': 'Director of Operations', 'affiliation': 'capStaff',
             'jobCode': '5678', 'organization': {'orgCode': 'ABCD'}},
        ]))
    assert result['title'] == 'staff'
    assert result['affiliation'] == 'ABCD', 'org should come from the staff title entry'


def test_dual_role_ignores_institute_membership_jobcode_1234():
    """jobCode 1234 is a bare institute membership, not a real staff job."""
    result = transform_cap_profile('u', profile(
        affiliations={'capStaff': True, 'capFaculty': True},
        titles=[
            {'title': 'Professor', 'affiliation': 'capFaculty'},
            {'title': 'Affiliate', 'affiliation': 'capStaff', 'jobCode': '1234'},
        ]))
    assert result['title'] == 'faculty', 'must not be downgraded to staff'


def test_dual_role_ignores_a_title_of_member():
    result = transform_cap_profile('u', profile(
        affiliations={'capStaff': True, 'capFaculty': True},
        titles=[
            {'title': 'Professor', 'affiliation': 'capFaculty'},
            {'title': 'Member', 'affiliation': 'capStaff', 'jobCode': '9999'},
        ]))
    assert result['title'] == 'faculty'


# ------------------------------------------------------------ Basic Life Res Scientist
@pytest.mark.parametrize('title_str', [
    'Basic Life Research Scientist',
    'Basic Life Res Scientist',
    'basic life research scientist',
])
def test_basic_life_research_scientist_becomes_postdoc(title_str):
    result = transform_cap_profile('u', profile(
        affiliations={'capFaculty': True},
        titles=[{'title': title_str, 'affiliation': 'capFaculty'}]))
    assert result['title'] == 'postdoc'


def test_basic_life_rule_does_not_override_a_dual_role_staff_decision():
    result = transform_cap_profile('u', profile(
        affiliations={'capStaff': True, 'capFaculty': True},
        titles=[
            {'title': 'Basic Life Research Scientist', 'affiliation': 'capFaculty'},
            {'title': 'Basic Life Research Scientist', 'affiliation': 'capStaff',
             'jobCode': '5678'},
        ]))
    assert result['title'] == 'staff'


# --------------------------------------------------------------------- robustness
@pytest.mark.parametrize('titles', [
    'not-a-list',
    [None],
    ['a string'],
    [{'affiliation': None}],
])
def test_malformed_titles_do_not_raise(titles):
    """CAP data is inconsistent; this function must degrade rather than explode."""
    result = transform_cap_profile('u', profile(titles=titles))
    assert result['uid'] == 'u'


def test_return_keys_are_stable():
    result = transform_cap_profile('u', profile())
    assert set(result) == {'uid', 'title', 'affiliation', 'affiliation_mapped',
                           'display_name', 'pi'}
