import os
import shutil


class InvalidAuthInfo(Exception):
    """
    An exception indicating that the user passed improperly formatted authentication infomation.
    Extends the built-in python Exception class.
    """

    pass


class CannotInstantiateServiceObject(Exception):
    """
    An exception indicating that it was not possible to authenticate with the information provided.
    Extends the built-in python Exception class.
    """

    def __init__(self,  message='Unable to authenticate with the service provider. Consult the documentation for help on authentication.'):
        """
        The constructor for the CannotInstantiateServiceObject class.

        Parameters
        __________
        message : string
            The message displayed to the user following the exception.
        """
        self.message = message
        super().__init__(self.message)
    

class Auth():
    """
    A class representing a generalized authentication object.

    Attributes
    __________
    _CONFIG_PATH : string
        The path to the .config folder (or equivalent).
    _AUTH_PATH : string
        The path to the cardinal-glue folder which should contain all authorization files.
    """

    _CONFIG_PATH = None
    if os.name == "nt":
        _CONFIG_PATH = os.getenv("APPDATA")
    if not _CONFIG_PATH:
        _CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".config")
    _AUTH_PATH = os.path.join(_CONFIG_PATH,"cardinal-glue")
    
    def __init__(self, auth_path=_AUTH_PATH):
        """
        The constructor for the Auth class.

        Parameters
        __________
        auth_path : string
            The path to the cardinal-glue folder which should contain all authorization files.
        """
        self.set_auth_directory(auth_path)

    def set_auth_directory(self, new_path):
        """
        Set a new path to search for authorization files.

        Parameters
        __________
        new_path : string
            The name of the new path that will replace the path to the cardinal-glue folder.
        """
        os.makedirs(new_path, exist_ok=True)
        files = os.listdir(self._AUTH_PATH)
        for f in files:
            src_path = os.path.join(self._AUTH_PATH, f)
            dst_path = os.path.join(new_path, f)
            shutil.move(src_path, dst_path)
        self._AUTH_PATH = new_path


