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



class WorkgroupManager():
    """
    A class allowing users to manage Stanford workgroups.
    """

    def __init__(self, stem, auth=None):
        """
        The constructor for the WorkgroupManager class.

        Parameters
        __________
        stem : string
            The stem of the workgroups you want to manage.
        auth : WorkgroupAuth
            The WorkgroupAuth object needed to query the Stanford Workgroup API.
        """
        self._auth = auth
        self.stem = stem
        if not self._auth:
            try:
                self._auth = WorkgroupAuth()
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()
        # self.workgroup_list = self.populate_workgroup_list(stem)

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
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/search/{self.stem}*'
        response = self._auth.make_request('get', url)
        workgroup_list = []
        for item in response.json()['results']:
            temp = item['name']
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
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{workgroup_name}'
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
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{workgroup_name}/links'
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
        """
        name = name.lower()
        workgroup_name = f'{self.stem}:{name}'
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{workgroup_name}/links'
        data = {'link': 'GOOGLE'}
        
        try:
            response = self._auth.make_request('delete', url=url, params=data)
            if response.status_code == 200:
                logger.info(f'Successfully unlinked Google Group from {workgroup_name}.')
            elif response.status_code == 404:
                logger.info(f'Google Link not found for {workgroup_name} (skipping).')
            else:
                logger.warning(f'Failed to unlink Google Group for {workgroup_name}. Status: {response.status_code}')
        except Exception as e:
            logger.error(f"Exception during Google Group unlink: {e}")

    def delete_workgroup(self, name, remove_google_link=False):
        name = name.lower()
        if remove_google_link:
            self._remove_google_link(name)

        workgroup_name = f'{self.stem}:{name}'
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{workgroup_name}'
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


class Workgroup():
    """
    A class representing a Stanford workgroup.
    """
    def __init__(self, stem, workgroup, auth=None, privgroup=False):
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
                self._auth = WorkgroupAuth()
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()

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
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}'
        response = self._auth.make_request('get', url)
        if response.status_code == 200:
            self._member_details = response.json().get('members', [])
            self._admins = response.json().get('administrators', [])
            self._members = [i['id'] for i in self._member_details]
            self._description = response.json().get('description')
            self._filter = response.json().get('filter')
            self._visibility = response.json().get('visibility')
            self._reusable = response.json().get('reusable')
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
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}/privgroup'
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
        if member_type not in ['USER', 'WORKGROUP']:
            raise ValueError("member_type must be either 'USER' or 'WORKGROUP'")

        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}/members/'
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
        if member_type not in ['USER', 'WORKGROUP']:
            raise ValueError("member_type must be either 'USER' or 'WORKGROUP'")

        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}/members/'
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