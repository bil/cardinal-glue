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


def create_gcs_buckets(workshop_num, workshop_date, uid_list, project_id=None, storage_client=None):
    """
    Creates GCS buckets for a workshop and grants write access to specified Stanford users.
    
    Parameters
    ----------
    workshop_num : str
        The workshop number (e.g., '220').
    workshop_date : str
        The date of the workshop session (e.g., '20260610').
    uid_list : list of str
        The list of Stanford UIDs (SUNet IDs) for whom to create buckets.
    project_id : str, optional
        The Google Cloud project ID (e.g., 'dor-wutsaineuro-dbp').
    storage_client : google.cloud.storage.Client, optional
        An existing storage Client instance.
    """
    import os
    import logging
    from google.cloud import storage
    from cardinal_glue.auth.googleauth import GoogleAuth

    logger = logging.getLogger(__name__)

    # Ensure project_id is available
    if not project_id:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")

    if not storage_client:
        if not project_id:
            raise ValueError("A valid 'project_id' or 'storage_client' must be specified.")
        
        # Build GCS client with appropriate credentials
        if os.environ.get('K_REVISION'):
            # Running inside GCP (Cloud Run) - use default credentials
            storage_client = storage.Client(project=project_id)
        else:
            # Local/Colab environment - use GoogleAuth credentials
            gauth = GoogleAuth()
            storage_client = storage.Client(project=project_id, credentials=gauth.credentials)

    # Sanitize inputs
    sanitized_date = str(workshop_date).replace('-', '')
    sanitized_num = str(workshop_num)

    results = {}
    for uid in uid_list:
        if not uid:
            continue
        user = f"{uid}@stanford.edu"
        member = f"user:{uid}@stanford.edu"
        role = 'roles/storage.legacyObjectOwner'
        bucket_name = f'dbp_{sanitized_num}_{sanitized_date}_{uid}'
        
        try:
            bucket_ref = storage_client.bucket(bucket_name)
            if not bucket_ref.exists():
                bucket = storage_client.create_bucket(bucket_name, location='us-west1')
                bucket.acl.user(user).grant_write()
                bucket.acl.save()
                bucket.iam_configuration.public_access_prevention = "enforced"
                bucket.add_lifecycle_delete_rule(age=30)
                bucket.patch()
                policy = bucket.get_iam_policy(requested_policy_version=3)
                policy.bindings.append({"role": role, "members": {member}})
                bucket.set_iam_policy(policy)
                logger.info(f"Bucket '{bucket_name}' created successfully for {uid}")
                results[uid] = "created"
            else:
                logger.info(f"Bucket '{bucket_name}' already exists for {uid}")
                results[uid] = "exists"
        except Exception as e:
            logger.error(f"Failed to create bucket '{bucket_name}' for {uid}: {e}", exc_info=True)
            results[uid] = f"error: {str(e)}"
            
    return results


    
    
