import requests
from cardinal_glue.workgroup_api.workgroupauth import WorkgroupAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject

        
def get_workgroup_list(stem):
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
    auth = WorkgroupAuth()
    url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/search/{stem}*'

    response = auth.make_request('get', url)
    workgroup_list = []
    for item in response.json()['results']:
        temp = item['name']
        temp = str.split(temp, ':')[1]
        workgroup_list.append(temp)
    return workgroup_list


class Workgroup():
    """
    A class representing a Stanford workgroup.
    """
    def __init__(self, stem, workgroup, auth=None, verbose=False):
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
        verbose : bool
            Whether to include a larger set of output statements when making API requests.
            Passed to class functions.
        """
        self.members = None
        self.admins = None
        self.privgroup_members = None
        self.privgroup_admins = None
        self.member_UIDs = None
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
        self.get_workgroup(verbose)
        # self.get_privgroup(verbose)

    def get_workgroup(self, verbose=False):
        """
        Return the parameters of a workgroup.

        Parameters
        __________
        verbose : bool
            Whether to include a larger set of output statements when making API requests.
        """
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}'
        response = self._auth.make_request('get', url)
        if response.status_code == 200:
            self.members = response.json()['members']
            self.admins = response.json()['administrators']
            self.member_UIDs = [i['id'] for i in self.members]
            if not self.members and verbose:
                print(f'{self.stem}:{self.name} is empty.')
            self.description = response.json()['description']
            self.filter = response.json()['filter']
            self.visibility = response.json()['visibility']
            self.reusable = response.json()['reusable']
            self.integrations = response.json()['integrations']
        elif response.status_code == 404:
            print(f"Workgroup '{self.name}' not found.")
        elif response.status_code == 401:
            print('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
        else:
            print(f'Error {response.status_code}')
 
    def get_privgroup(self, verbose=False):
        """
        Return the privgroup values of a workgroup.

        Parameters
        __________
        verbose : bool
            Whether to include a larger set of output statements when making API requests.
        """
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}/privgroup'
        response = self._auth.make_request('get', url)
        if response.status_code == 200:
            self.privgroup_members = response.json()['members']
            self.privgroup_admins = response.json()['administrators']
            if not self.privgroup_members and verbose:
                print(f'{self.stem}:{self.name} is empty.')
        elif response.status_code == 404:
            print(f"Workgroup '{self.name}' not found.")
        elif response.status_code == 401:
            print('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
        else:
            print(f'Error {response.status_code}')  

    def add_members(self, uid_list, verbose=False):
        """
        Add members to a workgroup.

        Parameters
        __________
        uid_list : list
            The list of UIDs to add.
        verbose : bool
            Whether to include a larger set of output statements when making API requests.
        """
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}/members/'
        if (type(uid_list) is not list):
            uid_list = [uid_list]
        self.get_workgroup()
        uid_list = list(set(uid_list)-set(self.member_UIDs))
        if not uid_list:
            if verbose:
                print(f'All of the provided SUNet IDs were already in {self.name}')
            return

        for uid in uid_list:
            response = self._auth.make_request('put', f'{url}{uid}', params={'type':'USER'})
            if response.status_code == 200:
                print(f'{uid} was added successfully to Workgroup {self.name}')
            elif response.status_code == 409:
                print(f'{uid} is already in {self.name}')
            elif response.status_code == 401:
                print('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
            else:
                print(f'Error {response.status_code}')
        self.get_workgroup()

    def remove_members(self, uid_list, verbose=False):
        """
        Remove members from a workgroup.

        Parameters
        __________
        uid_list : list
            The list of UIDs to remove.
        verbose : bool
            Whether to include a larger set of output statements when making API requests.
        """
        url = f'https://workgroupsvc.stanford.edu/workgroups/2.0/{self.stem}:{self.name}/members/'
        if (type(uid_list) is not list):
            uid_list = [uid_list]
        self.get_workgroup()
        uid_list = list(set(uid_list) & set(self.member_UIDs))
        if not uid_list:
            if verbose:
                print(f'None of the provided SUNet IDs were in {self.name}')
            return

        for uid in uid_list:
            response = self._auth.make_request('delete', f'{url}{uid}', params={'type':'USER'})
            if response.status_code == 200:
                print(f'{uid} was removed successfully from Workgroup {self.name}')
            elif response.status_code == 404:
                print(f'{uid} is not in {self.name}')
            elif response.status_code == 401:
                print('Permission denied. Make sure that you have added the appropriate certificate as a workgroup administrator.')
            else:
                print(f'Error {response.status_code}')
        self.get_workgroup()