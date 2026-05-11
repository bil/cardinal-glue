import os
import json
import requests
import logging
from cardinal_glue.auth.core import Auth, InvalidAuthInfo

logger = logging.getLogger(__name__)

class CanvasAuth(Auth):
    """
    A class representing authentication with the Canvas LMS API.
    Extends the Auth class.

    Attributes
    ----------
    __CANVAS_AUTH_JSON_NAME : string
        The name of the file containing authentication information for the Canvas API.
    """
    __CANVAS_AUTH_JSON_NAME = 'canvas.json'

    def __init__(self, auto_auth=True):
        """
        The constructor for the CanvasAuth class.

        Parameters
        ----------
        auto_auth : bool
            Whether to automatically attempt authentication.
        """
        super().__init__()
        self._auth_method = None
        self._api_token = None
        self._base_url = 'https://canvas.stanford.edu'
        
        if auto_auth:
            self.authenticate()

    def authenticate(self):
        """
        Determines the method to use to authenticate with the Canvas API.
        Prioritizes environment variables, falls back to local files.
        """
        if "CANVAS_ACCESS_TOKEN" in os.environ:
            self._auth_method = 'memory'
            if "CANVAS_BASE_URL" in os.environ:
                self._base_url = os.environ.get("CANVAS_BASE_URL").rstrip('/')
        else:
            file_path = os.path.join(self._AUTH_PATH, self.__CANVAS_AUTH_JSON_NAME)
            if os.path.exists(file_path):
                self._auth_method = 'file'
                with open(file_path) as f:
                    try:
                        config = json.load(f)
                    except json.JSONDecodeError:
                        raise InvalidAuthInfo(f"File {file_path} is not valid JSON.")
                
                self._api_token = config.get('api_token')
                if not self._api_token:
                    raise InvalidAuthInfo("Canvas configuration file must include 'api_token'.")
                
                if 'base_url' in config:
                    self._base_url = config['base_url'].rstrip('/')
            else:
                # We don't raise here to allow lazy instantiation without environment/files present initially
                # But make_request will fail if _auth_method is None
                pass

    def make_request(self, method, url, **kwargs):
        """
        Makes an authenticated request to the Canvas API.

        Parameters
        ----------
        method : str
            The HTTP method for the request (e.g., 'get', 'post').
        url : str
            The target Canvas API URL. If relative, prepends base_url.
        **kwargs : dict
            Additional arguments to pass to requests.request.
        """
        if self._auth_method == 'memory':
            access_token = os.environ.get("CANVAS_ACCESS_TOKEN")
            base_url = os.environ.get("CANVAS_BASE_URL", self._base_url).rstrip('/')
        elif self._auth_method == 'file':
            access_token = self._api_token
            base_url = self._base_url
        else:
            # Try to authenticate JIT if not already done
            self.authenticate()
            if self._auth_method == 'memory':
                access_token = os.environ.get("CANVAS_ACCESS_TOKEN")
                base_url = os.environ.get("CANVAS_BASE_URL", self._base_url).rstrip('/')
            elif self._auth_method == 'file':
                access_token = self._api_token
                base_url = self._base_url
            else:
                raise InvalidAuthInfo("Unable to find Canvas authentication information. Please set CANVAS_ACCESS_TOKEN or provide a canvas.json file.")

        if not url.startswith('http'):
            url = f"{base_url}/{url.lstrip('/')}"

        headers = {'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'}
        if 'headers' in kwargs:
            headers.update(kwargs.get('headers', {}))
        
        kwargs['headers'] = headers
        return requests.request(method, url, **kwargs)
