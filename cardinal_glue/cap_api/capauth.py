import os
import json
import requests
from cardinal_glue.auth.core import Auth, InvalidAuthInfo


class CAPAuth(Auth):
    """
    A class representing authentication with the Stanford CAP API.
    Extends the Auth class.

    Attributes
    __________
    __CAP_AUTH_JSON_NAME : string
        The name of the file containing authentication information for the Stanford CAP API.
    """
    __CAP_AUTH_JSON_NAME = 'cap_client.json'

    def __init__(self, auto_auth=True):
        """
        The constructor for the CAPAuth class.

        Parameters
        __________
        auto_auth : bool
            User choice as whether to automatically attempt authentication with the Stanford CAP API while instantiating the object.
        """
        super().__init__()
        if auto_auth:
            self.authenticate()

    def authenticate(self, file_path=None):
        """
        Attempt to authenticate with the Stanford CAP API.
        """
        if not file_path:
            file_path = os.path.join(self._AUTH_PATH, self.__CAP_AUTH_JSON_NAME)
        if os.path.exists(file_path):
            f = open(file_path)
            user_info = json.load(f)
            self._client_id, self._client_secret = user_info['client_id'], user_info['client_secret']
        else:
            raise InvalidAuthInfo('Unable to generate credentials. Please ensure that there is valid json file containing CAP API authentication information.')
        url = 'https://authz.stanford.edu/oauth/token'
        data = {'grant_type' : 'client_credentials'}
        auth = (self._client_id, self._client_secret)
        response = requests.post(url, data=data, auth=auth).json()
        self.access_token = response['access_token']