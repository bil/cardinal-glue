import unittest
from cardinal_glue.cap_api.custom_parsing import transform_cap_profile

class TestCustomParsing(unittest.TestCase):
    def test_affiliation_transformations(self):
        # A minimal mock profile that triggers the organization assignment
        def make_mock_profile(org_code):
            return {
                'titles': [
                    {
                        'affiliation': 'capStaff',
                        'title': 'Staff',
                        'organization': {
                            'orgCode': org_code
                        }
                    }
                ]
            }

        # Mock CAPClient to just return the org_code as the organization name
        class MockCapClient:
            def get_org_from_code(self, org_code):
                return org_code

        mock_client = MockCapClient()
        
        test_cases = [
            ('school-of-medicine', 'SoM'),
            ('graduate-school-of-business', 'GSB'),
            ('land-buildings-and-real-estate', 'LBRE'),
            ('vice-provost-and-dean-of-research', 'VPDoR'),
            ('school-of-humanities-and-sciences', 'H&S'),
            ('school-of-engineering', 'SoE'),
            ('department-of-athletics-physical-education-and-recreation', 'DAPER'),
            ('graduate-school-of-education', 'GSE'),
            ('slac-national-accelerator-laboratory', 'SLAC'),
            ('vice-provost-for-student-affairs', 'VPSA'),
            ('some-other-school', 'some-other-school') # Test that it leaves others alone
        ]
        
        for input_org, expected_affiliation in test_cases:
            profile = make_mock_profile(input_org)
            result = transform_cap_profile('testuid', profile, cap_client=mock_client)
            self.assertEqual(
                result.get('affiliation_mapped'), 
                expected_affiliation, 
                f"Failed for input: {input_org}"
            )

    def test_nkgv_organization_transformation(self):
        # Test existing logic that 'NKGV' becomes 'vice-provost-and-dean-of-research'
        # which should then become 'VPDoR'
        def make_mock_profile(org_code):
            return {
                'titles': [
                    {
                        'affiliation': 'capStaff',
                        'title': 'Staff',
                        'organization': {
                            'orgCode': org_code
                        }
                    }
                ]
            }

        class MockCapClient:
            def get_org_from_code(self, org_code):
                return org_code

        mock_client = MockCapClient()
        profile = make_mock_profile('NKGV')
        result = transform_cap_profile('testuid', profile, cap_client=mock_client)
        self.assertEqual(result.get('affiliation_mapped'), 'VPDoR')

    def test_titles_array_primary_resolution(self):
        # Verify that if titles[0] exists, we resolve the primary title and organization from it
        class MockCapClient:
            def get_org_from_code(self, org_code):
                return org_code

        mock_client = MockCapClient()
        profile = {
            'titles': [
                {
                    'affiliation': 'capPhdStudent',
                    'title': 'Ph.D. Student',
                    'organization': {'orgCode': 'school-of-engineering'}
                },
                {
                    'affiliation': 'capStaff',
                    'title': 'Software Developer',
                    'organization': {'orgCode': 'school-of-medicine'}
                }
            ],
            'affiliations': {
                'capPhdStudent': True,
                'capStaff': True
            }
        }
        
        result = transform_cap_profile('testuid', profile, cap_client=mock_client)
        self.assertEqual(result.get('title'), 'phdstudent')
        self.assertEqual(result.get('affiliation_mapped'), 'SoE') # 'resolved-school-of-engineering' -> 'school-of-engineering' -> 'SoE'

    def test_staff_plus_faculty_override(self):
        # Verify that if both staff and faculty exist in affiliations, we override to staff
        profile = {
            'titles': [
                {
                    'affiliation': 'capFaculty',
                    'title': 'Acting Assistant Professor',
                    'organization': {'orgCode': 'school-of-medicine'}
                }
            ],
            'affiliations': {
                'capStaff': True,
                'capFaculty': True
            }
        }
        result = transform_cap_profile('testuid', profile)
        self.assertEqual(result.get('title'), 'staff')

    def test_registry_overrides(self):
        # Undergrad override
        profile_undergrad = {
            'titles': [{'affiliation': 'capRegistry', 'title': 'Undergraduate'}]
        }
        result = transform_cap_profile('testuid', profile_undergrad)
        self.assertEqual(result.get('title'), 'undergraduate')

        # Fellow override
        profile_fellow = {
            'titles': [{'affiliation': 'capRegistry', 'title': 'Affiliate'}],
            'affiliations': {'capRegistry': True, 'capFellow': True}
        }
        result = transform_cap_profile('testuid', profile_fellow)
        self.assertEqual(result.get('title'), 'fellow')

        # Default to staff
        profile_default = {
            'titles': [{'affiliation': 'capRegistry', 'title': 'Affiliate'}]
        }
        result = transform_cap_profile('testuid', profile_default)
        self.assertEqual(result.get('title'), 'staff')

    def test_instructor_and_research_scientist_overrides(self):
        # Instructor -> postdoc
        profile_instructor = {
            'titles': [{'affiliation': 'capFaculty', 'title': 'Instructor'}]
        }
        result = transform_cap_profile('testuid', profile_instructor)
        self.assertEqual(result.get('title'), 'postdoc')

        # Research Scientist -> staff
        profile_scientist = {
            'titles': [{'affiliation': 'capFaculty', 'title': 'Research Scientist'}]
        }
        result = transform_cap_profile('testuid', profile_scientist)
        self.assertEqual(result.get('title'), 'staff')

    def test_blrs_override(self):
        # Basic Life Research Scientist (regardless of faculty/staff base title) -> postdoc
        profile_faculty_blrs = {
            'titles': [{'affiliation': 'capFaculty', 'title': 'Basic Life Res. Scientist'}]
        }
        result = transform_cap_profile('testuid', profile_faculty_blrs)
        self.assertEqual(result.get('title'), 'postdoc')

        profile_staff_blrs = {
            'titles': [{'affiliation': 'capStaff', 'title': 'Basic Life Research Scientist'}]
        }
        result = transform_cap_profile('testuid', profile_staff_blrs)
        self.assertEqual(result.get('title'), 'postdoc')

    def test_staff_faculty_title_override(self):
        # User is both staff and faculty, with faculty at index 0 and staff at index 1
        profile = {
            'affiliations': {'capStaff': True, 'capFaculty': True},
            'titles': [
                {
                    'affiliation': 'capFaculty',
                    'title': 'Professor',
                    'organization': {'orgCode': 'ABCD'}
                },
                {
                    'affiliation': 'capStaff',
                    'title': 'Manager',
                    'organization': {'orgCode': 'XYZ'}
                }
            ]
        }
        
        class MockCapClient:
            def get_org_from_code(self, org_code):
                return f"Resolved-{org_code}"

        mock_client = MockCapClient()
        result = transform_cap_profile('testuid', profile, cap_client=mock_client)
        
        # Verify that it bypassed the faculty ABCD org and correctly used XYZ org (from capStaff)
        self.assertEqual(result.get('title'), 'staff')
        self.assertEqual(result.get('affiliation'), 'Resolved-XYZ')

if __name__ == '__main__':
    unittest.main()
