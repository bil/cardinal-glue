import os
import re
import json
import requests
from cardinal_glue.auth.core import Auth, InvalidAuthInfo

        
class QualtricsAuth(Auth):
    """
    A class representing authentication with the Qualtrics API.
    Extends the Auth class.

    Attributes
    __________
    __QUALTRICS_AUTH_JSON_NAME : string
        The name of the file containing authentication information for the Qualtrics API.
    """
    __QUALTRICS_AUTH_JSON_NAME = 'qualtrics.json'

    def __init__(self, auto_auth=True):
        """
        The constructor for the QualtricsAuth class.

        Parameters
        __________
        auto_auth : bool
            User choice as whether to automatically attempt authentication with the Qualtrics API while instantiating the object.
        """
        super().__init__()    
        if auto_auth:
            self.authenticate()

    def authenticate(self):
        """
        Attempt to authenticate with the Qualtrics API.
        """
        file_path = os.path.join(self._AUTH_PATH, self.__QUALTRICS_AUTH_JSON_NAME)
        if os.path.exists(file_path):
            f = open(file_path)
            user_info = json.load(f)      
            if user_info.get('data_center'):
                self._data_center = user_info['data_center']
            else:
                raise InvalidAuthInfo("Please provide a value for 'data_center' in the Qualtrics JSON file.")
            self._api_token = user_info.get('api_token')         
            self._client_id = user_info.get('client_id')
            self._client_secret = user_info.get('client_secret')
            if (not self._client_id or not self._client_secret) and not self._api_token:
                raise InvalidAuthInfo("Please provide a value for 'api_token' or for both 'client_id' and 'client_secret' in the Qualtrics JSON file.")
        else:
            raise InvalidAuthInfo('Please ensure that there is valid JSON file containing Qualtrics authentication information.')
        if self._api_token:
            self._auth_method = 'apitoken'
            validate_url = f'https://{self._data_center}.qualtrics.com/API/v3/whoami'
            self._request_headers = {
                'X-API-TOKEN': self._api_token, 
                'Accept': 'application/json'
                }
            response = requests.request("GET", url=validate_url, headers=self._request_headers)
            if response.status_code != 200:
                raise InvalidAuthInfo("Invalid API token.")
        else:
            self._auth_method = 'oauth'
            bearer_url = f'https://{self._data_center}.qualtrics.com/oauth2/token'
            data = {'grant_type': 'client_credentials','scope': 'manage:all'}
            auth = (self._client_id, self._client_secret)
            response = requests.request("POST",url=bearer_url, data=data, auth=auth)
            if response.status_code != 200:
                raise InvalidAuthInfo("Invalid client values.")
            self._access_token = 'Bearer ' + response.json()['access_token']
            self._request_headers = {
                'Authorization': self._access_token, 
                'Accept': 'application/json'
                }
        directory_url = f'https://{self._data_center}.qualtrics.com/API/v3/directories'
        response = requests.request("GET", url=directory_url, headers=self._request_headers)
        elements = response.json()['result']['elements']
        available_directories = []
        for directory in elements:
            available_directories.append(directory['directoryId'])
        self.available_directories = available_directories

