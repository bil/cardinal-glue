import os
import requests
import tempfile
from cardinal_glue.auth.core import Auth, InvalidAuthInfo
        

class WorkgroupAuth(Auth):
    """
    A class representing authentication with the Stanford Workgroup API.
    Extends the Auth class.

    Attributes
    __________
    __WORKGROUP_AUTH_CERT_NAME : string
        The name of the file containing the certificate needed for authentication with the Stanford Workgroup API.
    __WORKGROUP_AUTH_KEY_NAME : string
        The name of the file containing the key needed for authentication with the Stanford Workgroup API.
    """
    __WORKGROUP_AUTH_CERT_NAME = 'stanford_workgroup.cert'
    __WORKGROUP_AUTH_KEY_NAME = 'stanford_workgroup.key'

    def __init__(self, auto_auth=True):
        """
        The constructor for the WorkgroupAuth class.

        Parameters
        __________
        auto_auth : bool
            User choice as whether to automatically attempt authentication with the Stanford Workgroup API while instantiating the object.
        """
        super().__init__()   
        self._auth_method = None
        if auto_auth:
            self.authenticate()

    def authenticate(self):
        """
        Determines method of authenticating with the Stanford Workgroup API.
        Prioritizes environment variables, falls back to local files.
        """
        if "WORKGROUP_CERT_STRING" in os.environ and "WORKGROUP_KEY_STRING" in os.environ:
            self._auth_method = 'memory'
        else:
            cert_path = os.path.join(self._AUTH_PATH, self.__WORKGROUP_AUTH_CERT_NAME)
            key_path = os.path.join(self._AUTH_PATH, self.__WORKGROUP_AUTH_KEY_NAME)
            if os.path.exists(cert_path) and os.path.exists(key_path):
                self._credentials = (cert_path, key_path)
                self._auth_method = 'file'
            else:
                raise InvalidAuthInfo('Please ensure that cert and key file paths are valid.')

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
            cert_str = os.environ.get("WORKGROUP_CERT_STRING")
            key_str = os.environ.get("WORKGROUP_KEY_STRING")

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
