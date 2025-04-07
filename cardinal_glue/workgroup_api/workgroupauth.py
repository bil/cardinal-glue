import os
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
        if auto_auth:
            self.authenticate()

    def authenticate(self):
        """
        Attempt to authenticate with the Stanford Workgroup API.
        """
        cert_path = os.path.join(self._AUTH_PATH, self.__WORKGROUP_AUTH_CERT_NAME)
        key_path = os.path.join(self._AUTH_PATH, self.__WORKGROUP_AUTH_KEY_NAME)
        if os.path.exists(cert_path) and os.path.exists(key_path):
            self._credentials = (cert_path, key_path)
        else:
            raise InvalidAuthInfo('Please ensure that cert and key file paths are valid.')