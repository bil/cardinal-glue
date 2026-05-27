import requests
import os
import logging
from cardinal_glue.workgroup_api.workgroupauth import WorkgroupAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject



logger = logging.getLogger(__name__)


class WorkgroupError(Exception):
    """Base class for Workgroup API errors."""
    pass

class WorkgroupNotFound(WorkgroupError):
    """Raised when a workgroup is not found (404)."""
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
        List the workgroups nested under a given stem.

        Parameters
        __________
        stem : string
            The workgroup stem to query.

        Returns
        _______
        workgroup_list : list
            A list of workgroup names.
        """
        url = f'{self._base_url}/search/{self.stem}*'
        response = self._auth.make_request('get', url)
        workgroup_list = []
        for item in response.json().get('results', []):
            temp = item.get('name')
            if not temp:
                logger.warning("Workgroup search item found but 'name' is missing.")
                continue
            temp = str.split(temp, ':')[1]
            workgroup_list.append(temp)
        self.workgroup_list = workgroup_list

    def create_workgroup(self, name, description, filter_in='NONE', reusable='TRUE', visibility='PRIVATE', privgroup='TRUE', add_google_link=False):
        name = name.lower()
        workgroup_name = f'{self.stem}:{name}'
        data={
            'description':description,           # workgroup description
            'filter':filter_in,                # NONE = default; all Stanford affiliates allowed
            'reusable':reusable,              # TRUE = default; can be nested under other stems
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
        
        try:
            response = self._auth.make_request('put', url=url, params=data)
            if response.status_code == 201:
                logger.info(f'Successfully linked Google Group to {workgroup_name}.')
            elif response.status_code == 409:
                logger.info(f'Google Group linkage already exists for {workgroup_name}.')
            else:
                logger.warning(f'Failed to link Google Group for {workgroup_name}. Status: {response.status_code}')
        except Exception as e:
            logger.error(f"Exception during Google Group link creation: {e}")

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

    def copy_workgroup(self, name, new_stem=None, new_name=None, remove_original=False):
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
            raise WorkgroupNotFound(f"Original workgroup '{self.stem}:{name}' not found.")
            
        # 2. Check for Google integration
        has_google = False
        if old_wg._integrations:
            for integration in old_wg._integrations:
                if 'GOOGLE' in integration:
                    has_google = True
                    break
                    
        # 3. Create new workgroup with original settings
        new_mgr = WorkgroupManager(new_stem, auth=self._auth) if new_stem != self.stem else self
        
        description = old_wg.description or ''
        filter_in = old_wg._filter or 'NONE'
        reusable = str(old_wg._reusable).upper() if old_wg._reusable is not None else 'TRUE'
        visibility = old_wg._visibility or 'PRIVATE'
        privgroup = str(old_wg._privgroup).upper() if old_wg._privgroup is not None else 'TRUE'
        
        new_mgr.create_workgroup(
            name=new_name,
            description=description,
            filter_in=filter_in,
            reusable=reusable,
            visibility=visibility,
            privgroup=privgroup,
            add_google_link=has_google
        )
        
        # 4. Copy members and admins
        new_wg = Workgroup(new_stem, new_name, auth=self._auth)
        
        # Group members by type
        members_by_type = {}
        for member in old_wg._member_details:
            m_type = member.get('type')
            m_id = member.get('id')
            if m_type and m_id:
                members_by_type.setdefault(m_type, []).append(m_id)
        
        for m_type, m_list in members_by_type.items():
            # Workgroup API uses 'PERSON' in GET but 'USER' in PUT/POST for type
            api_type = 'USER' if m_type == 'PERSON' else m_type
            if api_type in ['USER', 'WORKGROUP', 'CERTIFICATE']:
                new_wg.add_members(m_list, member_type=api_type)
        
        # Group admins by type
        admins_by_type = {}
        for admin in old_wg._admins:
            a_type = admin.get('type')
            a_id = admin.get('id')
            if a_type and a_id:
                admins_by_type.setdefault(a_type, []).append(a_id)
                
        for a_type, a_list in admins_by_type.items():
            api_type = 'USER' if a_type == 'PERSON' else a_type
            if api_type in ['USER', 'WORKGROUP', 'CERTIFICATE']:
                new_wg.add_admins(a_list, admin_type=api_type)
                
        # 5. Optionally delete original
        if remove_original:
            self.delete_workgroup(name, remove_google_link=has_google)
            
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
        elif response.status_code == 404:
            logger.error(f"Workgroup '{self.name}' not found.")
            raise WorkgroupNotFound(f"Workgroup '{self.name}' not found.")
        elif response.status_code == 401:
            logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
            raise WorkgroupPermissionDenied("Permission denied accessing workgroup.")
        else:
            logger.error(f'Error {response.status_code}')
            raise WorkgroupAPIError(f"Workgroup API error: {response.status_code}")
 
    def populate_privgroup(self):
        """
        Populate the privgroup values of a workgroup.
        """
        url = f'{self._base_url}/{self.stem}:{self.name}/privgroup'
        response = self._auth.make_request('get', url)
        if response.status_code == 200:
            self._privgroup_members = response.json().get('members', [])
            self._privgroup_admins = response.json().get('administrators', [])
            self._privgroup_populated = True
            logger.info(f'Privgroup information for Workgroup {self.name} populated.')
        elif response.status_code == 404:
            logger.error(f"Workgroup '{self.name}' not found.")
            raise WorkgroupNotFound(f"Workgroup '{self.name}' not found.")
        elif response.status_code == 401:
            logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
            raise WorkgroupPermissionDenied("Permission denied accessing workgroup.")
        else:
            logger.error(f'Error {response.status_code}')
            raise WorkgroupAPIError(f"Workgroup API error: {response.status_code}")

    def add_members(self, member_list, member_type='USER', member_stem=None, filter_members=False):
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
        """
        member_type = member_type.upper()
        if member_type not in ['USER', 'WORKGROUP', 'CERTIFICATE']:
            raise ValueError("member_type must be either 'USER', 'WORKGROUP', or 'CERTIFICATE'")

        url = f'{self._base_url}/{self.stem}:{self.name}/members/'
        if (type(member_list) is not list):
            member_list = [member_list]
        
        # Filter existing members locally to reduce API calls IF requested
        if filter_members:
            member_list = list(set(member_list)-set(self.members))
        
        if not member_list:
            if filter_members:
                logger.info(f'All of the provided members were already in {self.name}')
            return

        for member in member_list:
            if member_type == 'WORKGROUP':
                stem_to_use = member_stem if member_stem else self.stem
                member = f"{stem_to_use}:{member}"

            response = self._auth.make_request('put', f'{url}{member}', params={'type': member_type})
            if response.status_code == 200:
                logger.info(f'{member} was added successfully to Workgroup {self.name}')
            elif response.status_code == 409:
                logger.info(f'{member} is already in {self.name}')
            elif response.status_code == 404:
                # 404 on PUT usually implies the workgroup itself is missing (or member lookup failed weirdly)
                # But 'populate' check usually catches workgroup missing.
                # If the TARGET (self.name) is missing:
                logger.error(f"Workgroup '{self.name}' not found.")
                raise WorkgroupNotFound(f"Workgroup '{self.name}' not found.")
            elif response.status_code == 401:
                logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
                raise WorkgroupPermissionDenied("Permission denied adding member.")
            else:
                logger.error(f'Error {response.status_code}')
                raise WorkgroupAPIError(f"Error adding member {member}: {response.status_code}")
        self.populate_workgroup()

    def add_admins(self, admin_list, admin_type='USER', admin_stem=None, filter_admins=False):
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
        """
        admin_type = admin_type.upper()
        if admin_type not in ['USER', 'WORKGROUP', 'CERTIFICATE']:
            raise ValueError("admin_type must be either 'USER', 'WORKGROUP', or 'CERTIFICATE'")

        url = f'{self._base_url}/{self.stem}:{self.name}/administrators/'
        if (type(admin_list) is not list):
            admin_list = [admin_list]
        
        # Filter existing admins locally to reduce API calls IF requested
        if filter_admins:
            admin_ids = [i.get('id') for i in self.admins if i.get('id')]
            admin_list = list(set(admin_list)-set(admin_ids))
        
        if not admin_list:
            if filter_admins:
                logger.info(f'All of the provided admins were already in {self.name}')
            return

        for admin in admin_list:
            if admin_type == 'WORKGROUP':
                stem_to_use = admin_stem if admin_stem else self.stem
                admin = f"{stem_to_use}:{admin}"

            response = self._auth.make_request('put', f'{url}{admin}', params={'type': admin_type})
            if response.status_code == 200:
                logger.info(f'{admin} was added successfully as admin to Workgroup {self.name}')
            elif response.status_code == 409:
                logger.info(f'{admin} is already an admin of {self.name}')
            elif response.status_code == 404:
                logger.error(f"Workgroup '{self.name}' not found.")
                raise WorkgroupNotFound(f"Workgroup '{self.name}' not found.")
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
        member_type = member_type.upper()
        if member_type not in ['USER', 'WORKGROUP', 'CERTIFICATE']:
            raise ValueError("member_type must be either 'USER', 'WORKGROUP', or 'CERTIFICATE'")

        url = f'{self._base_url}/{self.stem}:{self.name}/members/'
        if (type(member_list) is not list):
            member_list = [member_list]

        # Filter members to remove locally to reduce API calls IF requested
        if filter_members:
            member_list = list(set(member_list) & set(self.members))
             
        if not member_list:
            if filter_members:
                logger.info(f'None of the provided members were in {self.name}')
            return

        status_codes = []
        for member in member_list:
            if member_type == 'WORKGROUP':
                stem_to_use = member_stem if member_stem else self.stem
                member = f"{stem_to_use}:{member}"

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