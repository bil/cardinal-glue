import logging
from cardinal_glue.canvas_api.canvasauth import CanvasAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject

logger = logging.getLogger(__name__)

class CanvasClient():
    """
    A class representing a client for interfacing with the Canvas LMS API.
    """
    def __init__(self, auth=None):
        """
        The constructor for the CanvasClient class.

        Parameters
        ----------
        auth : CanvasAuth, optional
            The CanvasAuth object needed to query the Canvas API.
        """
        self._auth = auth

    def _get_auth(self):
        """
        Lazily initialize and authenticate the CanvasAuth object.
        """
        if not self._auth:
            try:
                # auto_auth=True by default in CanvasAuth.__init__
                self._auth = CanvasAuth()
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject("Unable to initialize Canvas authentication.")
        return self._auth

    def get_courses(self, **params):
        """
        Fetch all courses the authenticated user has access to, handling pagination automatically.

        Parameters
        ----------
        **params : dict
            Additional query parameters (e.g., enrollment_type=['teacher']).

        Returns
        -------
        list
            A list of course objects.
        """
        url = "/api/v1/courses"
        courses = []
        
        if 'per_page' not in params:
            params['per_page'] = 100

        auth = self._get_auth()
        response = auth.make_request('get', url, params=params)
        response.raise_for_status()
        courses.extend(response.json())

        while 'next' in response.links:
            next_url = response.links['next']['url']
            response = auth.make_request('get', next_url)
            response.raise_for_status()
            courses.extend(response.json())

        return courses

    def get_user(self, user_id):
        """
        Fetch a single user's information from Canvas.

        Parameters
        ----------
        user_id : string or int
            The Canvas user ID or a string identifier (e.g., 'sis_user_id:SUNET').

        Returns
        -------
        dict
            The user object from Canvas.
        """
        url = f"/api/v1/users/{user_id}"
        auth = self._get_auth()
        response = auth.make_request('get', url)
        response.raise_for_status()
        return response.json()

    def get_users_in_course(self, course_id, **params):
        """
        Fetch all users in a specific course from Canvas, handling pagination automatically.

        Parameters
        ----------
        course_id : string or int
            The Canvas course ID.
        **params : dict
            Additional query parameters (e.g., enrollment_type=['teacher']).

        Returns
        -------
        list
            A list of user objects.
        """
        url = f"/api/v1/courses/{course_id}/users"
        users = []
        
        # Ensure we ask for per_page=100 for efficiency if not specified
        if 'per_page' not in params:
            params['per_page'] = 100

        auth = self._get_auth()
        response = auth.make_request('get', url, params=params)
        response.raise_for_status()
        users.extend(response.json())

        # Handle Pagination via Link header
        while 'next' in response.links:
            next_url = response.links['next']['url']
            response = auth.make_request('get', next_url)
            response.raise_for_status()
            users.extend(response.json())

        return users
