import os
import requests
import tempfile
import logging
from cardinal_glue.auth.core import Auth, InvalidAuthInfo


logger = logging.getLogger(__name__)


class WorkgroupAuth(Auth):
    """
    A class representing authentication with the Stanford Workgroup API.
    Extends the Auth class.

    Authentication Priority
    _______________________
    1. `creds` parameter passed to constructor (explicit file paths)
    2. `WORKGROUP_CERT_PATH` + `WORKGROUP_KEY_PATH` environment variables (file paths)
    3. `WORKGROUP_CERT` + `WORKGROUP_KEY` environment variables (cert/key content, written to temp files)
    4. Default paths: ~/.config/cardinal-glue/stanford_workgroup.{cert,key}

    Attributes
    __________
    __WORKGROUP_AUTH_CERT_NAME : string
        The name of the file containing the certificate needed for authentication with the Stanford Workgroup API.
    __WORKGROUP_AUTH_KEY_NAME : string
        The name of the file containing the key needed for authentication with the Stanford Workgroup API.
    """
    __WORKGROUP_AUTH_CERT_NAME = 'stanford_workgroup.cert'
    __WORKGROUP_AUTH_KEY_NAME = 'stanford_workgroup.key'

    def __init__(self, creds=None, auto_auth=True):
        """
        The constructor for the WorkgroupAuth class.

        Parameters
        __________
        creds : tuple
            Local paths to credential files.    
        auto_auth : bool
            User choice as whether to automatically attempt authentication with the Stanford Workgroup API while instantiating the object.
        """
        super().__init__()
        if creds:
            if not isinstance(creds, tuple):
                raise InvalidAuthInfo("Please pass 'creds' as a tuple")
            if not isinstance(creds[0], str) or not isinstance(creds[1], str):
                raise InvalidAuthInfo("Please ensure that the items in 'creds' are strings")
        self._credentials = creds
        self._auth_method = None
        self.__valid = False
        if auto_auth:
            self.authenticate()

    def authenticate(self):
        """
        Determines method of authenticating with the Stanford Workgroup API.
        
        Priority order:
        1. creds parameter (explicit paths passed to constructor)
        2. WORKGROUP_CERT_PATH + WORKGROUP_KEY_PATH env vars (file paths)
        3. WORKGROUP_CERT + WORKGROUP_KEY env vars (content, written to temp files)
        4. Default paths (~/.config/cardinal-glue/stanford_workgroup.{cert,key})
        """
        if self._credentials:
            self._auth_method = 'file'
        elif "WORKGROUP_CERT_PATH" in os.environ and "WORKGROUP_KEY_PATH" in os.environ:
            self._auth_method = 'file'
            cert_path = os.environ.get("WORKGROUP_CERT_PATH")
            key_path = os.environ.get("WORKGROUP_KEY_PATH")
            self._credentials = (cert_path, key_path)
        elif "WORKGROUP_CERT" in os.environ and "WORKGROUP_KEY" in os.environ:
            self._auth_method = 'memory'
        else:
            self._auth_method = 'file'
            cert_path = os.path.join(self._AUTH_PATH, self.__WORKGROUP_AUTH_CERT_NAME)
            key_path = os.path.join(self._AUTH_PATH, self.__WORKGROUP_AUTH_KEY_NAME)
            self._credentials = (cert_path, key_path)
        
        # Validate file paths exist for file-based auth
        if self._auth_method == 'file':
            if not (os.path.exists(self._credentials[0]) and os.path.exists(self._credentials[1])):
                raise InvalidAuthInfo('Please ensure that cert and key file paths are valid.')
        url=f'https://workgroupsvc.stanford.edu/workgroups/2.0/search/mockurl'
        response = self.make_request('get', url)
        if response.status_code == 200:
            self.__valid = True
            logger.info('Workgroup credentials validated.')
        else:
            logger.critical('Unable to validate Workgroup credentials')

    def make_request(self, method, url, **kwargs):
        """
        Makes an authenticated request to the Workgroup API.

        This method abstracts the authentication details, handling both file-based
        credentials for local development and in-memory, string-based credentials
        from environment variables for containerized deployments.

        Parameters
        __________
        method : string
            The HTTP method to use for the request (e.g., 'get', 'post', 'put').
        url : string
            The URL to send the request to.
        **kwargs : dict
            Additional keyword arguments to pass to the requests library,
            such as 'params' or 'json'.

        Returns
        _______
        response : requests.Response
            The Response object returned by the requests library.
        
        Raises
        ______
        InvalidAuthInfo
            If the authentication method has not been successfully determined prior
            to calling this method.
        """      
        if self._auth_method == 'file':
            return requests.request(method, url, cert=self._credentials, **kwargs)
        
        elif self._auth_method == 'memory':
            cert_string = os.environ.get("WORKGROUP_CERT")
            key_string = os.environ.get("WORKGROUP_KEY")

            with tempfile.NamedTemporaryFile(mode='w', suffix='.cert', delete=True) as cert_file:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=True) as key_file:
                    cert_file.write(cert_string)
                    key_file.write(key_string)
                    cert_file.flush()
                    key_file.flush()
                    
                    cert_tuple = (cert_file.name, key_file.name)
                    return requests.request(method, url, cert=cert_tuple, **kwargs)
        else:
            raise InvalidAuthInfo("Authentication method not determined. Please call authenticate().")