import logging
from cardinal_glue.cap_api.capauth import CAPAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject


logger = logging.getLogger(__name__)


class CAPClient():
    """
    A class represening a client for interfacing with the Stanford CAP API.
    """
    def __init__(self, auth=None):
        """
        The constructor for the CAPClient class.

        Parameters
        ----------
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
        ----------
        uid : string
            The UID to query.
        community : string
            The CAP Client community level.
        """
        valid_communities=['public','stanford','hidden','stanford_full','stanford_full_hidden']
        if community:
            if community not in valid_communities:
                logger.error("Please enter a valid value for community.")
                raise ValueError(f"Invalid community: {community}. Must be one of {valid_communities}")
            url = f'https://cap.stanford.edu/cap-api/api/profiles/v1?uids={uid}&community={community}'
        else:
            url = f'https://cap.stanford.edu/cap-api/api/profiles/v1?uids={uid}'
        response = self._auth.make_request('get', url).json()
        if 'values' in response:
            return response['values'][0]
        return None

    def get_org_from_code(self, org_code):
        """
        Resolve an organization code to its human-readable alias.

        Parameters
        ----------
        org_code : string
            The organization code to resolve (e.g., 'AABB').

        Returns
        -------
        string or None
            The organization alias if found, otherwise None.
        """
        url = f'https://cap.stanford.edu/cap-api/api/cap/v1/orgs/{org_code}'
        response = self._auth.make_request('get', url).json()
        if 'alias' in response:
            return response['alias']
        return None