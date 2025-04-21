import shutil
import fsspec
import gdrivefs
import gcsfs
from cardinal_glue.auth.googleauth import GoogleAuth


class FileSystem():
    """
    A class representing an abstract file system.
    """
    def __init__(self, end_point, project=None):
        """
        The constructor for the FileSystem class.
        Currently in development to include additional file systems.

        Parameters
        __________
        end_point : string
            The file system to setup.
        """
        valid_end_points = ['gdrive','gcsfs']
        if end_point not in valid_end_points:
            raise ValueError("Please provide a valid endpoint.")
        self.end_point = end_point
        if self.end_point == 'gdrive':
            self._auth = GoogleAuth()
            self._fs = gdrivefs.GoogleDriveFileSystem(token='cache')
        elif self.end_point == 'gcsfs':
            if not project:
                raise ValueError("Please provide a value for 'project' when specifying 'endpoint' as \"gcsfs\".")
            self._auth = GoogleAuth()
            self.project = project
            self._fs = gcsfs.core.GCSFileSystem(project=self.project,token=self._auth.credentials)

    def _validate_google_auth(self, google_auth):
        """
        Not currently implemented
        """

    def read(self, path, mode='text'):
        """
        Read from a file.

        Parameters
        __________
        path : string
            The path to the file to be read from.
        mode : string
            The file opening mode. Must be 'text'/'t' or 'binary'/'b'.
        """
        valid_modes = {
            'text':'t',
            'binary':'b'
        }
        if mode not in valid_modes.values():
            mode = modes[mode]
        fio = self._open(path, f'r{mode}')
        with fio as f:
            return f

    def write(self, path, data, mode='text'):
        """
        Write to a file.

        Parameters
        __________
        path : string
            The path to the file to write data to.
        data
            The data to write to the file.
        mode : string
            The file opening mode. Must be 'text'/'t' or 'binary'/'b'.
        """
        valid_modes = {
            'text':'t',
            'binary':'b'
        }
        if mode not in valid_modes.values():
            mode = modes[mode]
        fio = self._open(path, f'w{mode}')
        with fio as f:
            return f.write(data)

    def _open(self, path, mode):
        """
        Read from a file.

        Parameters
        __________
        path : string
            The path to the file to be read from.
        mode : string
            The file opening mode. Must be 'text'/'t' or 'binary'/'b'.
        """
        return fsspec.core.OpenFile(self._fs, path, f'{mode}')   

    def ls(self, path):
        """
        List directory contents.

        Parameters
        __________
        path : string
            The directory to list the contents of.
        """
        self._fs.ls(path)

    def get(self, src_path, dest_path):
        """
        Copy a file from a remote source to a destination target.

        Parameters
        _________
        src_path : string
            Path to the remote file.
        dest_path : string
            Local path to copy the file to.
        """
        self._fs.get(source_path, dest_path)

    def put(self, src_path, dest_path):
        """
        Copy a file from a local source to a remote destination.

        Parameters
        _________
        src_path : string
            Path to the local file.
        dest_path : string
            Remote path to copy the file to.
        """
        self._fs.put(source_path, dest_path)

    
    
