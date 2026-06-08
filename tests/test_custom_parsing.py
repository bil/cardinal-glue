import unittest
from cardinal_glue.cap_api.custom_parsing import transform_cap_profile

class TestCustomParsing(unittest.TestCase):
    def test_affiliation_transformations(self):
        # A minimal mock profile that triggers the organization assignment
        def make_mock_profile(org_code):
            return {
                'organizations': [
                    {
                        'type': 'affiliation',
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
                result.get('affiliation'), 
                expected_affiliation, 
                f"Failed for input: {input_org}"
            )

    def test_nkgv_organization_transformation(self):
        # Test existing logic that 'NKGV' becomes 'vice-provost-and-dean-of-research'
        # which should then become 'VPDoR'
        def make_mock_profile(org_code):
            return {
                'organizations': [
                    {
                        'type': 'affiliation',
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
        self.assertEqual(result.get('affiliation'), 'VPDoR')

if __name__ == '__main__':
    unittest.main()
