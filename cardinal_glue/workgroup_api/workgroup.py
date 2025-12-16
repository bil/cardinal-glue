import requests
import os
import logging
from cardinal_glue.workgroup_api.workgroupauth import WorkgroupAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
if os.getenv('CARDINAL_LOGGING'):
    logger.setLevel(os.getenv('CARDINAL_LOGGING').upper())
else:
    logger.setLevel('ERROR') 


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

    def create_workgroup(self, name, description, filter_in='NONE', reusable='TRUE', visibility='PRIVATE', privgroup='TRUE'):
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
        elif response.status_code == 401:
            logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
        else:
            logger.error(f'Error {response.status_code}')
        
        try:
            ret = response.json()
        except:
            ret = {}
        ret['statusCode'] = response.status_code
        return ret

    def delete_workgroup(self, name):
        workgroup_name = f'{self.stem}:{name}'
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{workgroup_name}'
        response = self._auth.make_request('delete', url=url)
        if response.status_code == 200:
            logger.info(f'Workgroup {workgroup_name} deleted successfully.')
        elif response.status_code == 400:
            logger.info(f'Workgroup {workgroup_name} not found.')
        elif response.status_code == 401:
            logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
        else:
            logger.error(f'Error {response.status_code}')

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
        self.members = None
        self.admins = None
        self.privgroup_members = None
        self.privgroup_admins = None
        self.member_details = None
        self._auth = auth
        self.stem = stem
        self.name = workgroup
        self.description = None
        self.filter = None
        self.visibility = None
        self.reusable = None
        self.integrations = None
        if not self._auth:
            try:
                self._auth = WorkgroupAuth()
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()
        if privgroup:
            self.populate_privgroup()
        else:
            self.populate_workgroup()

    def populate_workgroup(self):
        """
        Populate the parameters of a workgroup.
        """
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}'
        response = self._auth.make_request('get', url)
        if response.status_code == 200:
            self.member_details = response.json()['members']
            self.admins = response.json()['administrators']
            self.members = [i['id'] for i in self.member_details]
            self.description = response.json()['description']
            self.filter = response.json()['filter']
            self.visibility = response.json()['visibility']
            self.reusable = response.json()['reusable']
            self.integrations = response.json()['integrations']
            logger.info(f'Workgroup {self.name} populated.')
        elif response.status_code == 404:
            logger.error(f"Workgroup '{self.name}' not found.")
        elif response.status_code == 401:
            logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
        else:
            logger.error(f'Error {response.status_code}')
 
    def populate_privgroup(self):
        """
        Populate the privgroup values of a workgroup.
        """
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}/privgroup'
        response = self._auth.make_request('get', url)
        if response.status_code == 200:
            self.privgroup_members = response.json()['members']
            self.privgroup_admins = response.json()['administrators']
            logger.info(f'Privgroup information for Workgroup {self.name} populated.')
        elif response.status_code == 404:
            logger.error(f"Workgroup '{self.name}' not found.")
        elif response.status_code == 401:
            logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
        else:
            logger.error(f'Error {response.status_code}')

    def add_members(self, member_list, member_type='USER', member_stem=None):
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
        """
        member_type = member_type.upper()
        if member_type not in ['USER', 'WORKGROUP']:
            raise ValueError("member_type must be either 'USER' or 'WORKGROUP'")

        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}/members/'
        if (type(member_list) is not list):
            member_list = [member_list]
        # self.populate_workgroup()
        
        # Filter existing members locally to reduce API calls
        member_list = list(set(member_list)-set(self.members))
        
        if not member_list:
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
            elif response.status_code == 401:
                logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
            else:
                logger.error(f'Error {response.status_code}')
        self.populate_workgroup()

    def remove_members(self, member_list, member_type='USER', member_stem=None):
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
        # self.populate_workgroup()

        # Filter members to remove locally to reduce API calls
        member_list = list(set(member_list) & set(self.members))
             
        if not member_list:
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
            elif response.status_code == 401:
                logger.error('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
            else:
                logger.error(f'Error {response.status_code}')
        self.populate_workgroup()