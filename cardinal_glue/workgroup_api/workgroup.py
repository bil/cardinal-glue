import requests
import os
import logging
import time
from cardinal_glue.workgroup_api.workgroupauth import WorkgroupAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject



logger = logging.getLogger(__name__)


class WorkgroupError(Exception):
    """Base class for Workgroup API errors."""
    pass

class WorkgroupNotFound(WorkgroupError):
    """Raised when a workgroup is not found (404)."""
    pass

class WorkgroupInactive(WorkgroupNotFound):
    """
    Raised when a workgroup has been deleted (the API soft-deletes).

    A GET on a deleted workgroup answers 400 with {"notification": "Workgroup is inactive."}
    rather than 404, so without this it surfaces as a generic WorkgroupAPIError. Subclasses
    WorkgroupNotFound deliberately: callers that only care whether the workgroup is usable keep
    working with `except WorkgroupNotFound`, while callers that need to distinguish "never
    existed" from "deleted" can catch this specifically.
    """
    pass

class WorkgroupPermissionDenied(WorkgroupError):
    """Raised when permission is denied (401)."""
    pass

class WorkgroupAPIError(WorkgroupError):
    """Raised when the Workgroup API returns an unexpected error."""
    pass

class WorkgroupAlreadyExists(WorkgroupError):
    """Raised when creating a workgroup that already exists (409)."""
    pass

class LinkageRemovalFailed(WorkgroupError):
    """Raised when a linkage cannot be removed from a workgroup."""
    pass


# The API is asymmetric: a GET reports person members as type 'PERSON', but PUT/DELETE only
# accept 'USER' for the same thing. Feeding a type straight back from a read is the obvious
# thing to do, so accept the read vocabulary everywhere and normalise it here.
MEMBER_TYPE_ALIASES = {'PERSON': 'USER'}
VALID_MEMBER_TYPES = ('USER', 'WORKGROUP', 'CERTIFICATE')

# Substring of the 400 notification returned for a soft-deleted workgroup.
_INACTIVE_NOTIFICATION = 'workgroup is inactive'


def normalize_member_type(member_type, label='member_type'):
    """
    Upper-case a member/admin type and map read-only aliases (PERSON -> USER) onto the value the
    API accepts for writes. Raises ValueError for anything unusable.
    """
    normalized = str(member_type).upper()
    normalized = MEMBER_TYPE_ALIASES.get(normalized, normalized)
    if normalized not in VALID_MEMBER_TYPES:
        raise ValueError(
            f"{label} must be one of {', '.join(VALID_MEMBER_TYPES)} "
            f"(or an alias: {', '.join(MEMBER_TYPE_ALIASES)})"
        )
    return normalized


def qualify_member_name(name, member_type, default_stem):
    """
    Stem-qualify a WORKGROUP member name, leaving every other type untouched.

    Must run BEFORE any membership comparison: the members list holds nested workgroups
    stem-qualified, so comparing a bare name against it never matches.
    """
    if member_type == 'WORKGROUP' and ':' not in name:
        return f'{default_stem}:{name}'
    return name


def _is_inactive_response(response):
    """True if this 400 is the API's 'workgroup is inactive' (soft-deleted) answer."""
    if response.status_code != 400:
        return False
    try:
        body = response.json()
    except Exception:
        return False
    haystack = ' '.join(
        str(body.get(k, '')) for k in ('notification', 'message', 'error')
    ).lower()
    return _INACTIVE_NOTIFICATION in haystack


def raise_for_workgroup_status(response, description):
    """
    Translate a non-200 read response into the right exception.

    Read paths only. Write paths have their own per-status handling (409 already-exists, 404
    ignore_missing, ...) that this would flatten.
    """
    if response.status_code == 200:
        return
    if _is_inactive_response(response):
        logger.error(f"{description} has been deleted (inactive).")
        raise WorkgroupInactive(f"{description} has been deleted (inactive).")
    if response.status_code == 404:
        logger.error(f"{description} not found.")
        raise WorkgroupNotFound(f"{description} not found.")
    if response.status_code in (401, 403):
        logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
        raise WorkgroupPermissionDenied(f"Permission denied accessing {description}.")
    logger.error(f'Error {response.status_code}')
    raise WorkgroupAPIError(f"Workgroup API error for {description}: {response.status_code}")


class WorkgroupManager():
    """
    A class allowing users to manage Stanford workgroups.
    """

    def __init__(self, stem, auth=None, use_uat=None):
        """
        The constructor for the WorkgroupManager class.

        Parameters
        __________
        stem : string
            The stem of the workgroups you want to manage.
        auth : WorkgroupAuth
            The WorkgroupAuth object needed to query the Stanford Workgroup API.
        use_uat : bool
            Whether to use the UAT server. If None, checks the WORKGROUP_UAT environment variable.
        """
        self._auth = auth
        self.stem = stem
        self.workgroup_list = None
        if not self._auth:
            try:
                self._auth = WorkgroupAuth(use_uat=use_uat)
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()
        
        # Use base_url from auth object if it exists (WorkgroupAuth has it)
        if hasattr(self._auth, '_base_url'):
            self._base_url = self._auth._base_url
        else:
            # Fallback logic if a custom auth object is passed that doesn't have _base_url
            if use_uat is True:
                self._base_url = "https://workgroupsvc-uat.stanford.edu/workgroups/2.0"
            elif use_uat is False:
                self._base_url = "https://workgroupsvc.stanford.edu/workgroups/2.0"
            else:
                if os.environ.get('WORKGROUP_UAT', 'false').lower() == 'true':
                    self._base_url = "https://workgroupsvc-uat.stanford.edu/workgroups/2.0"
                else:
                    self._base_url = "https://workgroupsvc.stanford.edu/workgroups/2.0"

    def populate_workgroup_list(self):
        """
        List the workgroups nested under this manager's stem, into self.workgroup_list.

        Returns
        _______
        workgroup_list : list
            A list of bare workgroup names (no stem prefix).

        Raises
        ______
        WorkgroupPermissionDenied, WorkgroupAPIError
            On any non-200 response. This used to return an empty list instead, which is
            indistinguishable from a genuinely empty stem.
        """
        # Search on '{stem}:*' rather than '{stem}*': the API rejects wildcards on search
        # strings shorter than 4 characters, so a 3-character stem (e.g. 'dbp') always 400s
        # without the colon and the whole stem silently looks empty.
        url = f'{self._base_url}/search/{self.stem}:*'
        response = self._auth.make_request('get', url)
        raise_for_workgroup_status(response, f"workgroup search for stem '{self.stem}'")

        workgroup_list = []
        for item in response.json().get('results', []):
            temp = item.get('name')
            if not temp:
                logger.warning("Workgroup search item found but 'name' is missing.")
                continue
            # rpartition, not split(':')[1]: stems themselves contain colons (e.g. 'som:it'),
            # so the workgroup name is everything after the LAST colon.
            _, _, bare_name = temp.rpartition(':')
            workgroup_list.append(bare_name)
        self.workgroup_list = workgroup_list

    def create_workgroup(self, name, description, filter_in='NONE', reusable='FALSE', visibility='PRIVATE', privgroup='TRUE', add_google_link=False):
        name = name.lower()
        workgroup_name = f'{self.stem}:{name}'
        data={
            'description':description,           # workgroup description
            'filter':filter_in,                # NONE = default; all Stanford affiliates allowed
            'reusable':reusable,              # FALSE = default; can be nested under other stems
            'visibility':visibility,         # PRIVATE = membership can only be seen by admins
            'privgroup':privgroup             # TRUE = default; unused?
        }
        url = f'{self._base_url}/{workgroup_name}'
        response = self._auth.make_request('post', url=url, params=data)
        if response.status_code == 201:
            logger.info(f'Workgroup {workgroup_name} created successfully.')
        elif response.status_code == 409:
            logger.info(f'Workgroup {workgroup_name} already exists.')
            raise WorkgroupAlreadyExists(f"Workgroup '{workgroup_name}' already exists.")
        elif response.status_code == 401:
            logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
            raise WorkgroupPermissionDenied("Permission denied creating workgroup.")
        else:
            logger.error(f'Error {response.status_code}')
            raise WorkgroupAPIError(f"Error creating workgroup: {response.status_code}")
        
        if add_google_link:
            self._add_google_link(name)
        
        try:
            ret = response.json()
        except:
            ret = {}
        ret['statusCode'] = response.status_code
        return ret

    def _add_google_link(self, name):
        """
        Private helper to link a Google Group integration.
        """
        name = name.lower()
        workgroup_name = f'{self.stem}:{name}'
        url = f'{self._base_url}/{workgroup_name}/links'
        data = {'link': 'GOOGLE'}

        retries = 5
        wait_time = 2
        for i in range(retries):
            try:
                response = self._auth.make_request('put', url=url, params=data)
                if response.status_code in (200, 201):
                    logger.info(f'Successfully linked Google Group to {workgroup_name}.')
                    return True
                elif response.status_code == 409:
                    logger.info(f'Google Group linkage already exists for {workgroup_name}.')
                    return True
                elif response.status_code == 404:
                    if i < retries - 1:
                        logger.info(f'Workgroup {workgroup_name} not ready for linking, retrying in {wait_time} seconds...')
                        time.sleep(wait_time)
                        wait_time *= 2
                        continue
                    else:
                        logger.warning(f'Failed to link Google Group for {workgroup_name} after {retries} attempts. Status: {response.status_code}')
                        return False
                else:
                    logger.warning(f'Failed to link Google Group for {workgroup_name}. Status: {response.status_code}')
                    return False
            except Exception as e:
                logger.error(f"Exception during Google Group link creation: {e}")
                return False

    def _remove_google_link(self, name):
        """
        Private helper to unlink a Google Group integration.
        
        Returns
        _______
        bool
            True if linkage was successfully removed or did not exist.
            False if removal failed for other reasons.
        """
        name = name.lower()
        workgroup_name = f'{self.stem}:{name}'
        url = f'{self._base_url}/{workgroup_name}/links'
        data = {'link': 'GOOGLE'}
        
        try:
            response = self._auth.make_request('delete', url=url, params=data)
            if response.status_code == 200:
                logger.info(f'Successfully unlinked Google Group from {workgroup_name}.')
                return True
            elif response.status_code == 404:
                logger.info(f'Google Link not found for {workgroup_name} (skipping).')
                return True
            elif response.status_code == 400:
                # API returns 400 with specific message for non-existent linkage
                try:
                    message = response.json().get('message', '')
                    if 'does not have linkage' in message:
                        logger.info(f'Google Link not found for {workgroup_name} (skipping).')
                        return True
                except Exception:
                    pass  # Fall through to warning below
                logger.warning(f'Failed to unlink Google Group for {workgroup_name}. Status: {response.status_code}')
                return False
            else:
                logger.warning(f'Failed to unlink Google Group for {workgroup_name}. Status: {response.status_code}')
                return False
        except Exception as e:
            logger.error(f"Exception during Google Group unlink: {e}")
            return False

    def delete_workgroup(self, name, remove_google_link=False):
        name = name.lower()
        if remove_google_link:
            success = self._remove_google_link(name)
            if not success:
                raise LinkageRemovalFailed(
                    f"Failed to remove Google linkage for workgroup '{self.stem}:{name}'. "
                    "Cannot delete workgroup with active linkage."
                )

        workgroup_name = f'{self.stem}:{name}'
        url = f'{self._base_url}/{workgroup_name}'
        response = self._auth.make_request('delete', url=url)
        if response.status_code == 200:
            logger.info(f'Workgroup {workgroup_name} deleted successfully.')
        elif response.status_code == 404:
            logger.info(f'Workgroup {workgroup_name} not found.')
            raise WorkgroupNotFound(f"Workgroup '{workgroup_name}' not found.")
        elif response.status_code == 401:
            logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
            raise WorkgroupPermissionDenied("Permission denied deleting workgroup.")
        else:
            logger.error(f'Error {response.status_code}')
            raise WorkgroupAPIError(f"Error deleting workgroup: {response.status_code}")

        try:
            ret = response.json()
        except:
            ret = {}
        ret['statusCode'] = response.status_code
        return ret

    def copy_workgroup(self, name, new_stem=None, new_name=None, remove_original=False, overwrite=False):
        """
        Copy a workgroup. Optionally change the stem or name during the copy.
        
        Parameters
        __________
        name : string
            The name of the workgroup to copy.
        new_stem : string, optional
            The stem to place the copied workgroup under. Defaults to the current stem.
        new_name : string, optional
            The new name for the copied workgroup. Defaults to the original name.
        remove_original : bool
            Whether to delete the original workgroup after successfully copying.
        overwrite : bool
            If True, will sync missing members, admins, and integrations to an existing destination workgroup instead of failing.
        """
        name = name.lower()
        new_stem = new_stem if new_stem else self.stem
        new_name = (new_name.lower() if new_name else name)
        
        if new_stem == self.stem and new_name == name:
            raise ValueError("Must specify a different stem or a different name to copy.")
            
        # 1. Fetch original workgroup details
        old_wg = Workgroup(self.stem, name, auth=self._auth)
        try:
            old_wg.populate_workgroup()
        except WorkgroupNotFound:
            logger.error(f"Original workgroup '{self.stem}:{name}' not found.")
            return {'statusCode': 404, 'message': f"Original workgroup '{self.stem}:{name}' not found."}
            
        # 2. Check for Google integration
        has_google = False
        if old_wg._integrations:
            for integration in old_wg._integrations:
                if 'GOOGLE' in integration:
                    has_google = True
                    break
        
        copy_successful = True
        try:
            # 3. Create new workgroup with original settings
            new_mgr = WorkgroupManager(new_stem, auth=self._auth) if new_stem != self.stem else self
            
            description = old_wg.description or ''
            filter_in = old_wg._filter or 'NONE'
            reusable = str(old_wg._reusable).upper() if old_wg._reusable is not None else 'FALSE'
            visibility = old_wg._visibility or 'PRIVATE'
            privgroup = str(old_wg._privgroup).upper() if old_wg._privgroup is not None else 'TRUE'
            
            try:
                # Create without adding google link immediately to avoid order of operations failure
                new_mgr.create_workgroup(
                    name=new_name,
                    description=description,
                    filter_in=filter_in,
                    reusable=reusable,
                    visibility=visibility,
                    privgroup=privgroup,
                    add_google_link=False
                )
            except WorkgroupAlreadyExists:
                if not overwrite:
                    raise
                logger.info(f"Workgroup '{new_stem}:{new_name}' already exists. Overwrite=True, syncing contents.")
                
            # 4. Wait for propagation (Exponential Backoff)
            new_wg = Workgroup(new_stem, new_name, auth=self._auth)
            retries = 5
            wait_time = 2
            for i in range(retries):
                try:
                    new_wg.populate_workgroup()
                    break
                except WorkgroupNotFound:
                    if i == retries - 1:
                        raise
                    logger.info(f"Workgroup '{new_stem}:{new_name}' not yet available, retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    wait_time *= 2

            # 5. Copy admins
            # Group admins by type
            admins_by_type = {}
            for admin in old_wg._admins:
                a_type = admin.get('type')
                a_id = admin.get('id')
                if a_type and a_id:
                    admins_by_type.setdefault(a_type, []).append(a_id)
                    
            for a_type, a_list in admins_by_type.items():
                try:
                    api_type = normalize_member_type(a_type, label='admin_type')
                except ValueError:
                    logger.warning(f"Skipping admins of unsupported type '{a_type}'.")
                    continue
                new_wg.add_admins(a_list, admin_type=api_type, filter_admins=True, ignore_missing=True)

            # 6. Copy members
            # Group members by type
            members_by_type = {}
            for member in old_wg._member_details:
                m_type = member.get('type')
                m_id = member.get('id')
                if m_type and m_id:
                    members_by_type.setdefault(m_type, []).append(m_id)
            
            for m_type, m_list in members_by_type.items():
                # normalize_member_type handles the GET-'PERSON' / PUT-'USER' asymmetry.
                try:
                    api_type = normalize_member_type(m_type)
                except ValueError:
                    logger.warning(f"Skipping members of unsupported type '{m_type}'.")
                    continue
                new_wg.add_members(m_list, member_type=api_type, filter_members=True, ignore_missing=True)
                    
            # 7. Add Google Link if needed
            if has_google:
                already_has_google = False
                if new_wg._integrations:
                    for integration in new_wg._integrations:
                        if 'GOOGLE' in integration:
                            already_has_google = True
                            break
                if not already_has_google:
                    success = new_mgr._add_google_link(new_name)
                    if not success:
                        copy_successful = False
                        logger.error(f"Failed to add Google linkage to {new_stem}:{new_name}. Original workgroup will not be deleted.")
        except Exception as e:
            logger.error(f"Error copying workgroup {self.stem}:{name} to {new_stem}:{new_name}: {e}")
            return {'statusCode': 500, 'message': f'Error during copy: {e}'}

        # 8. Optionally delete original (ONLY if replication was fully successful)
        if remove_original:
            if copy_successful:
                self.delete_workgroup(name, remove_google_link=has_google)
            else:
                logger.warning(f"Copy of {self.stem}:{name} was incomplete or had errors. Skipping deletion of original.")
                return {'statusCode': 207, 'message': f'Workgroup {self.stem}:{name} copied with warnings, original preserved.'}
            
        return {'statusCode': 200, 'message': f'Workgroup {self.stem}:{name} successfully copied to {new_stem}:{new_name}'}


class Workgroup():
    """
    A class representing a Stanford workgroup.
    """
    def __init__(self, stem, workgroup, auth=None, privgroup=False, use_uat=None):
        """
        The constructor for the Workgroup class.

        Parameters
        __________
        stem : string
            The stem of the workgroup you want to query.
        workgroup : string
            The workgroup name of the workgroup you want to query.
        auth : WorkgroupAuth
            The WorkgroupAuth object needed to query the Stanford Workgroup API.
        use_uat : bool
            Whether to use the UAT server. If None, checks the WORKGROUP_UAT environment variable.
        """
        self._members = None
        self._admins = None
        self._privgroup_members = None
        self._privgroup_admins = None
        self._member_details = None
        self._auth = auth
        self.stem = stem
        self.name = workgroup
        self._description = None
        self._filter = None
        self._visibility = None
        self._reusable = None
        self._integrations = None
        
        self._populated = False
        self._privgroup_populated = False
        self._privgroup = privgroup

        if not self._auth:
            try:
                self._auth = WorkgroupAuth(use_uat=use_uat)
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()

        # Use base_url from auth object if it exists (WorkgroupAuth has it)
        if hasattr(self._auth, '_base_url'):
            self._base_url = self._auth._base_url
        else:
            # Fallback logic if a custom auth object is passed that doesn't have _base_url
            if use_uat is True:
                self._base_url = "https://workgroupsvc-uat.stanford.edu/workgroups/2.0"
            elif use_uat is False:
                self._base_url = "https://workgroupsvc.stanford.edu/workgroups/2.0"
            else:
                if os.environ.get('WORKGROUP_UAT', 'false').lower() == 'true':
                    self._base_url = "https://workgroupsvc-uat.stanford.edu/workgroups/2.0"
                else:
                    self._base_url = "https://workgroupsvc.stanford.edu/workgroups/2.0"

    @property
    def members(self):
        if not self._populated: self.populate_workgroup()
        return self._members

    @members.setter
    def members(self, value):
        self._members = value

    @property
    def admins(self):
        if not self._populated: self.populate_workgroup()
        return self._admins

    @admins.setter
    def admins(self, value):
        self._admins = value

    def _members_of_type(self, wanted):
        """Ids of members whose type matches `wanted`, after alias normalisation."""
        if not self._populated: self.populate_workgroup()
        ids = []
        for entry in (self._member_details or []):
            member_id = entry.get('id')
            raw_type = entry.get('type')
            if not member_id or not raw_type:
                continue
            if MEMBER_TYPE_ALIASES.get(str(raw_type).upper(), str(raw_type).upper()) == wanted:
                ids.append(member_id)
        return ids

    @property
    def person_members(self):
        """
        Bare SUNet IDs of the people in this workgroup.

        Prefer this over `.members`, which mixes bare uids (people, certificates) with
        stem-qualified names (nested workgroups) and drops the type, leaving a person and a
        certificate indistinguishable.
        """
        return self._members_of_type('USER')

    @property
    def workgroup_members(self):
        """Stem-qualified names of the workgroups nested in this workgroup."""
        return self._members_of_type('WORKGROUP')

    @property
    def certificate_members(self):
        """Names of the certificate principals in this workgroup."""
        return self._members_of_type('CERTIFICATE')

    @property
    def member_details(self):
        if not self._populated: self.populate_workgroup()
        return self._member_details

    @member_details.setter
    def member_details(self, value):
        self._member_details = value

    @property
    def description(self):
        if not self._populated: self.populate_workgroup()
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    @property
    def privgroup_members(self):
        if not self._privgroup_populated: self.populate_privgroup()
        return self._privgroup_members

    @privgroup_members.setter
    def privgroup_members(self, value):
        self._privgroup_members = value
        
    @property
    def privgroup_admins(self):
        if not self._privgroup_populated: self.populate_privgroup()
        return self._privgroup_admins

    @privgroup_admins.setter
    def privgroup_admins(self, value):
        self._privgroup_admins = value

    def populate_workgroup(self):
        """
        Populate the parameters of a workgroup.
        """
        url = f'{self._base_url}/{self.stem}:{self.name}'
        response = self._auth.make_request('get', url)
        raise_for_workgroup_status(response, f"Workgroup '{self.stem}:{self.name}'")
        if response.status_code == 200:
            self._member_details = response.json().get('members', [])
            self._admins = response.json().get('administrators', [])
            self._members = [i.get('id') for i in self._member_details if i.get('id')]
            self._description = response.json().get('description')
            self._filter = response.json().get('filter')
            self._visibility = response.json().get('visibility')
            self._reusable = response.json().get('reusable')
            self._privgroup = response.json().get('privgroup')
            self._integrations = response.json().get('integrations')
            self._populated = True
            logger.info(f'Workgroup {self.name} populated.')
 
    def populate_privgroup(self):
        """
        Populate the privgroup values of a workgroup.
        """
        url = f'{self._base_url}/{self.stem}:{self.name}/privgroup'
        response = self._auth.make_request('get', url)
        raise_for_workgroup_status(response, f"Privgroup for workgroup '{self.stem}:{self.name}'")
        if response.status_code == 200:
            self._privgroup_members = response.json().get('members', [])
            self._privgroup_admins = response.json().get('administrators', [])
            self._privgroup_populated = True
            logger.info(f'Privgroup information for Workgroup {self.name} populated.')

    def update_properties(self, description=None, reusable=None, visibility=None, privgroup=None, filter_in=None):
        """
        Update the properties of an existing workgroup.

        Parameters
        __________
        description : str, optional
            A string (max 255 characters). Cannot be empty or blank.
        reusable : str, optional
            'TRUE' or 'FALSE'.
        visibility : str, optional
            'PRIVATE' or 'STANFORD'.
        privgroup : str, optional
            'TRUE' or 'FALSE'.
        filter_in : str, optional
            Accepted values: 'ACADEMIC_ADMINISTRATIVE', 'STUDENT', 'FACULTY', 'STAFF', 
            'FACULTY_STAFF', 'FACULTY_STUDENT', 'STAFF_STUDENT', 'FACULTY_STAFF_STUDENT', or 'NONE'.
        """
        data = {}
        if description is not None: data['description'] = description
        if reusable is not None: data['reusable'] = reusable.upper()
        if visibility is not None: data['visibility'] = visibility.upper()
        if privgroup is not None: data['privgroup'] = privgroup.upper()
        if filter_in is not None: data['filter'] = filter_in.upper()

        if not data:
            logger.info("No properties provided to update.")
            return

        url = f'{self._base_url}/{self.stem}:{self.name}'
        response = self._auth.make_request('put', url=url, params=data)

        if response.status_code == 200:
            logger.info(f"Successfully updated properties for Workgroup {self.name}.")
            self.populate_workgroup()
        elif response.status_code == 404:
            logger.error(f"Workgroup '{self.name}' not found.")
            raise WorkgroupNotFound(f"Workgroup '{self.name}' not found.")
        elif response.status_code in [401, 403]:
            logger.error('Permission denied updating workgroup properties.')
            raise WorkgroupPermissionDenied("Permission denied updating workgroup properties.")
        else:
            logger.error(f'Error {response.status_code}')
            raise WorkgroupAPIError(f"Error updating workgroup properties: {response.status_code}")

    def add_members(self, member_list, member_type='USER', member_stem=None, filter_members=False, ignore_missing=False):
        """
        Add members to a workgroup.

        Parameters
        __________
        member_list : list
            The list of members (UIDs or Workgroup names) to add.
        member_type : str
            The type of member to add ('USER' or 'WORKGROUP'). Default is 'USER'.
        member_stem : str
            The stem of the workgroup member to add. 
            Only used if member_type is 'WORKGROUP' and the member name does not contain a colon.
            Defaults to self.stem if not provided.
        filter_members : bool
            Whether to check if members exist before adding. Defaults to False (faster).
        ignore_missing : bool
            Whether to ignore 404 Not Found errors for individual members (useful for migrations). Defaults to False.
        """
        member_type = normalize_member_type(member_type)

        url = f'{self._base_url}/{self.stem}:{self.name}/members/'
        if (type(member_list) is not list):
            member_list = [member_list]

        # Qualify BEFORE filtering. self.members holds nested workgroups stem-qualified, so
        # filtering a bare workgroup name against it never matches -- which used to mean a
        # redundant add (harmless 409) here and a silent no-op in remove_members.
        stem_to_use = member_stem if member_stem else self.stem
        member_list = [qualify_member_name(m, member_type, stem_to_use) for m in member_list]

        # Filter existing members locally to reduce API calls IF requested
        if filter_members:
            member_list = list(set(member_list)-set(self.members))
        
        if not member_list:
            if filter_members:
                logger.info(f'All of the provided members were already in {self.name}')
            return

        for member in member_list:
            response = self._auth.make_request('put', f'{url}{member}', params={'type': member_type})
            if response.status_code == 200:
                logger.info(f'{member} was added successfully to Workgroup {self.name}')
            elif response.status_code == 409:
                logger.info(f'{member} is already in {self.name}')
            elif response.status_code == 404:
                if ignore_missing:
                    logger.warning(f"Member '{member}' not found in Stanford registry. Skipping.")
                else:
                    logger.error(f"Workgroup '{self.name}' or Member '{member}' not found.")
                    raise WorkgroupNotFound(f"Workgroup '{self.name}' or Member '{member}' not found.")
            elif response.status_code == 401:
                logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
                raise WorkgroupPermissionDenied("Permission denied adding member.")
            else:
                logger.error(f'Error {response.status_code}')
                raise WorkgroupAPIError(f"Error adding member {member}: {response.status_code}")
        self.populate_workgroup()

    def add_admins(self, admin_list, admin_type='USER', admin_stem=None, filter_admins=False, ignore_missing=False):
        """
        Add administrators to a workgroup.

        Parameters
        __________
        admin_list : list
            The list of admins (UIDs, Workgroup names, or Certificate names) to add.
        admin_type : str
            The type of admin to add ('USER', 'WORKGROUP', or 'CERTIFICATE'). Default is 'USER'.
        admin_stem : str
            The stem of the workgroup admin to add. 
            Only used if admin_type is 'WORKGROUP' and the name does not contain a colon.
            Defaults to self.stem if not provided.
        filter_admins : bool
            Whether to check if admins exist before adding. Defaults to False.
        ignore_missing : bool
            Whether to ignore 404 Not Found errors for individual admins (useful for migrations). Defaults to False.
        """
        admin_type = normalize_member_type(admin_type, label='admin_type')

        url = f'{self._base_url}/{self.stem}:{self.name}/administrators/'
        if (type(admin_list) is not list):
            admin_list = [admin_list]

        # Qualify BEFORE filtering -- see add_members.
        stem_to_use = admin_stem if admin_stem else self.stem
        admin_list = [qualify_member_name(a, admin_type, stem_to_use) for a in admin_list]

        # Filter existing admins locally to reduce API calls IF requested
        if filter_admins:
            admin_ids = [i.get('id') for i in self.admins if i.get('id')]
            admin_list = list(set(admin_list)-set(admin_ids))
        
        if not admin_list:
            if filter_admins:
                logger.info(f'All of the provided admins were already in {self.name}')
            return

        for admin in admin_list:
            response = self._auth.make_request('put', f'{url}{admin}', params={'type': admin_type})
            if response.status_code == 200:
                logger.info(f'{admin} was added successfully as admin to Workgroup {self.name}')
            elif response.status_code == 409:
                logger.info(f'{admin} is already an admin of {self.name}')
            elif response.status_code == 404:
                if ignore_missing:
                    logger.warning(f"Admin '{admin}' not found in Stanford registry. Skipping.")
                else:
                    logger.error(f"Workgroup '{self.name}' or Admin '{admin}' not found.")
                    raise WorkgroupNotFound(f"Workgroup '{self.name}' or Admin '{admin}' not found.")
            elif response.status_code == 401:
                logger.error('Permission denied adding administrator.')
                raise WorkgroupPermissionDenied("Permission denied adding administrator.")
            else:
                logger.error(f'Error {response.status_code}')
                raise WorkgroupAPIError(f"Error adding administrator {admin}: {response.status_code}")
        self.populate_workgroup()

    def remove_members(self, member_list, member_type='USER', member_stem=None, filter_members=False):
        """
        Remove members from a workgroup.

        Parameters
        __________
        member_list : list
            The list of members (UIDs or Workgroup names) to remove.
        member_type : str
            The type of member to remove ('USER' or 'WORKGROUP'). Default is 'USER'.
        member_stem : str
            The stem of the workgroup member to remove. 
            Only used if member_type is 'WORKGROUP' and the member name does not contain a colon.
            Defaults to self.stem if not provided.
        """
        member_type = normalize_member_type(member_type)

        url = f'{self._base_url}/{self.stem}:{self.name}/members/'
        if (type(member_list) is not list):
            member_list = [member_list]

        # Qualify BEFORE filtering -- see add_members. Getting this order wrong made
        # remove_members(['bare_group'], member_type='WORKGROUP', filter_members=True) filter the
        # name out entirely and report success while removing nothing.
        stem_to_use = member_stem if member_stem else self.stem
        member_list = [qualify_member_name(m, member_type, stem_to_use) for m in member_list]

        # Filter members to remove locally to reduce API calls IF requested
        if filter_members:
            member_list = list(set(member_list) & set(self.members))
             
        if not member_list:
            if filter_members:
                logger.info(f'None of the provided members were in {self.name}')
            return

        status_codes = []
        for member in member_list:
            response = self._auth.make_request('delete', f'{url}{member}', params={'type': member_type})
            if response.status_code == 200:
                logger.info(f'{member} was removed successfully from Workgroup {self.name}')
            elif response.status_code == 404:
                logger.info(f'{member} is not in {self.name}')
                # If the workgroup itself is missing, DELETE on members usually returns 404 too?
                # It's hard to distinguish "Member not found" from "Workgroup not found" purely on a DELETE /members/member call return of 404 without body inspection.
                # Assuming "Member not in workgroup" is the common case (non-fatal).
            elif response.status_code == 401:
                logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
                raise WorkgroupPermissionDenied("Permission denied removing member.")
            else:
                logger.error(f'Error {response.status_code}')
                raise WorkgroupAPIError(f"Error removing member {member}: {response.status_code}")
        self.populate_workgroup()