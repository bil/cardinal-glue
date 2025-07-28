import requests
from cardinal_glue.cap_api.capauth import CAPAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject


class CAPClient():
    """
    A class represening a client for interfacing with the Stanford CAP API.
    """
    def __init__(self, auth=None):
        """
        The constructor for the CAPClient class.

        Parameters
        __________
        auth : CAPAuth
            The CAPAuth object needed to query the Stanford CAP API.
        """
        self._auth = auth
        if not self._auth:
            try:
                self._auth = CAPAuth()
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()

    def get_profile_from_uid(self, uid, community=None):
        """
        Use a UID to query the CAP API for a profile.

        Parameters
        __________
        uid : string
            The UID to query.
        community : string
            The CAP Client community level.
        """
        valid_communities=['public','stanford','hidden','stanford_full','stanford_full_hidden']
        if community:
            if community not in valid_communities:
                print("Please enter a valid value for community.")
                return
            url = f'https://cap.stanford.edu/cap-api/api/profiles/v1?uids={uid}&community={community}'
        else:
            url = f'https://cap.stanford.edu/cap-api/api/profiles/v1?uids={uid}'
        response = self._auth.make_request('get', url).json()
        if 'values' in response:
            return CAPProfile(response['values'][0], cap_client=self)

    def get_org_from_code(self, org_code):
        url=f'https://cap.stanford.edu/cap-api/api/cap/v1/orgs/{org_code}'
        response = self._auth.make_request('get', url).json()
        if 'alias' in response:
            return response['alias']


class CAPProfile():
    """
    A class represening a profile returned from the Stanford CAP API.
    """
    def __init__(self, profile, cap_client=None):
        """
        The constructor for the CAPProfile class.

        Parameters
        __________
        profile : dict
            A dict object returned from a CAPClient.
        cap_client : CAPClient
            A valid CAPClient object.
        """
        self.profile = profile
        if not isinstance(cap_client, CAPClient):
            cap_client = CAPClient()

        cap_affiliation_dict = self.profile['affiliations']
        cap_affiliation = list(cap_affiliation_dict.keys())[list(cap_affiliation_dict.values()).index(True)]
        cap_affiliation = cap_affiliation.lower()[3:]
        affiliation_out = cap_affiliation
        
        position_out = 'NULL'
        if 'contacts' in self.profile:
            cap_contact_dict = self.profile['contacts'][0]
            position_out = str(cap_contact_dict.get('position'))

        if 'advisees' in self.profile.keys():
            for title in self.profile['titles']:
                if title['appointmentType'] == 'pr':
                    org_code = title['organization']['orgCode']
                    organization_out = cap_client.get_org_from_code(org_code)
        else:
            for org in self.profile['organizations']:
                if org['type'] == 'affiliation':
                    org_code = org['organization']['orgCode']
                    if org_code == 'NULL':
                        continue
                    organization_out = cap_client.get_org_from_code(org_code)
                    if not organization_out:
                        organization_out = org_code

        self.affiliation = affiliation_out
        self.position = position_out
        self.organization = organization_out