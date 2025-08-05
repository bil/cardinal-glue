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
        self._auth_method = None
        if auto_auth:
            self.authenticate()

    def authenticate(self):
        """
        Determines the method to use to authenticate with the Stanford CAP API.
        Prioritizes environment variables, falls back to local files.
        """
        if "CAP_CLIENT" in os.environ:
            self._auth_method = 'memory'

        else:
            file_path = os.path.join(self._AUTH_PATH, self.__CAP_AUTH_JSON_NAME)
            if os.path.exists(file_path):
                self._auth_method = 'file'
                with open(file_path) as f:
                    cap_creds = json.load(f)
            else:
                raise InvalidAuthInfo('Unable to generate credentials. Please ensure that there is valid json file containing CAP API authentication information.')
            self._client_id, self._client_secret = cap_creds['client_id'], cap_creds['client_secret']
        
    def make_request(self, method, url, **kwargs):
        """
        Fetches a fresh access token and then makes an authenticated request to the CAP API.

        This method abstracts the authentication details, handling both file-based
        credentials for local development and in-memory, string-based credentials
        from environment variables for containerized deployments.

        Parameters
        __________
        method : str
            The HTTP method for the request (e.g., 'get', 'post').
        url : str
            The target CAP API URL for the final request.
        **kwargs : dict
            Additional keyword arguments to pass to the `requests` library, such as 'params' or 'json'.

        Returns
        _______
        response : requests.Response
            The Response object from the final, authenticated API call.

        Raises
        ------
        InvalidAuthInfo
            If the authentication method has not been determined.
        requests.exceptions.HTTPError
            If fetching the access token fails.
        """ 
        if self._auth_method == 'memory':
            cap_creds = json.loads(os.environ.get("CAP_CLIENT"))
            token_auth = (cap_creds['client_id'], cap_creds['client_secret'])
        elif self._auth_method == 'file':
            token_auth = (self._client_id, self._client_secret)
        token_url = 'https://authz.stanford.edu/oauth/token'
        token_data = {'grant_type' : 'client_credentials'}
        token_response = requests.post(token_url, data=token_data, auth=token_auth)
        token_response.raise_for_status()
        access_token = token_response.json()['access_token']

        headers = {'Authorization': f'Bearer {access_token}'}
        if 'headers' in kwargs:
            headers.update(kwargs.get('headers', {}))
        
        kwargs['headers'] = headers
        return requests.request(method, url, **kwargs)