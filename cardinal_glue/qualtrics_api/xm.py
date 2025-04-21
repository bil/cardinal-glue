import requests
import pandas as pd
import json
import datetime
from cardinal_glue.qualtrics_api.qualtricsauth import QualtricsAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject


class Directory():
    """
    A class representing a Qualtrics XM Directory directory.
    """
    def __init__(self, directoryID=None, auth=None, get_contact_dates=False):
        """
        The constructor for the Directory class.

        Parameters
        __________
        directoryID : string
            The Qualtrics directoryId value for the directory represented by the object.
        auth : QualtricsAuth
            The QualtricsAuth object needed to query the Qualtrics API.
        get_contact_dates : bool
            Whether to query contact creation and modification time stamps.
            Passed through to the MailingList constructor.
            Significantly increases object initialization time.
        """
        self._auth = auth
        self._directoryID = directoryID         
        if not self._auth:
            try:
                self._auth = QualtricsAuth()
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()
            except ValueError:
                raise CannotInstantiateServiceObject()
        if not self._directoryID:
            print('No directory ID provided. Choosing from the first directory available.')
            self._directoryID = self._auth.available_directories[0]
        self.get_mailinglists(get_contact_dates=get_contact_dates)

    def get_mailinglists(self, get_contact_dates=False, next_page_url=None):
        """
        Return a list of the mailing lists in an XM Directory.

        Parameters
        __________
        get_contact_dates : bool
            Whether to query contact creation and modification time stamps.
            Passed through to the MailingList constructor.
            Significantly increases object initialization time.
        next_page_url : string
            A URL pointing to the next page in the results.
            Allows this function to be run recursively to retrieve paginated results.
        
        Returns
        _______
        dict_list : list
            A list of query responses. Only returned by recursive calls to this function.
        """
        if next_page_url:
            url = next_page_url
        else:
            url = f'https://{self._auth._data_center}.qualtrics.com/API/v3/directories/{self._directoryID}/mailinglists?includeCount=true&pageSize=100'
        headers = self._auth._request_headers

        response = requests.get(url, headers=headers)
        dict_list = response.json()['result']['elements']
        additional_url = response.json()['result']['nextPage']
        if additional_url:
            next_response = self.get_mailinglists(next_page_url=additional_url)
            dict_list = dict_list + next_response
        if next_page_url:
            return dict_list
        mailinglists = [MailingList(auth=self._auth,get_contact_dates=get_contact_dates,**i) for i in dict_list]
        df_mailinglists = pd.DataFrame(dict_list)
        self.mailinglists =  mailinglists
        self.mailinglist_frame =  df_mailinglists
  
    def get_ID_from_name(self, name):
        """
        Retrieve a Qualtrics mailingListId value from a MailingList name.

        Parameters
        __________
        name : string
            The name of the MailingList.

        Returns
        _______
        The Qualtrics mailingListId value of the MailingList.
        """
        index = self.mailinglist_frame.index[self.mailinglist_frame['name'] == name]
        if not index.empty:
            index = index[0]
            return self.mailinglist_frame['mailingListId'][index]
        else:
            print(f"No MailingList with the name '{name}' not found.")
  
    def get_mailinglist_from_name(self, name):
        """
        Retrieve a Qualtrics MailingList by its name.

        Parameters
        __________
        name : string
            The name of the MailingList.

        Returns
        _______
        The Qualtrics MailingList.
        """
        index = self.mailinglist_frame.index[self.mailinglist_frame['name'] == name]
        if not index.empty:
            index = index[0]
            return self.mailinglists[index]
        else:
            print(f"No MailingList with the name '{name}' not found.")
    
           
class MailingList():
    """
    A class representing a Qualtrics XM Directory mailing list.
    """
    def __init__(self, auth=None, get_contact_dates=False, **kwargs):
        """
        The constructor for the MailingList class.

        Parameters
        __________
        auth : QualtricsAuth
            The QualtricsAuth object needed to query the Qualtrics API.
        get_contact_dates : bool
            Whether to query contact creation and modification time stamps.
            Significantly increases object initialization time.
        **kwargs : dict
            Additional keyword arguments that are included to accommodate the output generated during the creation of a Directory object.
            See https://api.qualtrics.com/2d23a14718b4c-mailing-list for more details.
        """
        valid_keys = {'contactCount', 'mailingListId', 'name', 'lastModifiedDate', 'creationDate', 'ownerId'}
        self.__dict__.update((key, value) for key, value in kwargs.items() if key in valid_keys)
        if not self.mailingListId:
            raise ValueError("'mailingListId' must be specified.")
        self._auth = auth         
        if not self._auth:
            try:
                self._auth = QualtricsAuth()
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()
        self.get_contacts(get_contact_dates=get_contact_dates)

    def get_contacts(self, get_contact_dates=False, next_page_url=None):
        """
        Return a list of contacts in a specified mailing list.

        Parameters
        __________
        get_contact_dates : bool
            Whether to query contact creation and modification time stamps.
            Significantly increases object initialization time.
        next_page_url : string
            A URL pointing to the next page in the results.
            Allows this function to be run recursively to retrieve paginated results.
        
        Returns
        _______
        dict_list : list
            A list of query responses. Only returned by recursive calls to this function.
        """     
        if next_page_url:
            url = next_page_url
        else:       
            url = f'https://{self._auth._data_center}.qualtrics.com/API/v3/directories/{self._directoryID}/mailinglists/{self.mailingListId}/contacts'
        headers = self._auth._request_headers

        request = requests.get(url, headers=headers)
        dict_list = request.json()['result']['elements']
        additional_url = request.json()['result']['nextPage']
        if additional_url:
            next_request = self.get_contacts(next_page_url=additional_url)
            dict_list = dict_list + next_request
        if next_page_url:
            return dict_list
        else:
            contact_df = pd.DataFrame(dict_list)
            if get_contact_dates and 'contactId' in contact_df.columns:
                with requests.Session() as s: 
                    for i, contactId in enumerate(contact_df['contactId'].to_numpy()):
                        url = f'https://{self._auth._data_center}.qualtrics.com/API/v3/directories/{self._directoryID}/mailinglists/{self.mailingListId}/contacts/{contactId}'
                        request = s.get(url, headers=headers)
                        creationDate = request.json()['result']['creationDate']/1000
                        contact_df.loc[i, 'creationDate'] = datetime.datetime.fromtimestamp(creationDate).strftime('%Y-%m-%d')
                        lastModified = request.json()['result']['lastModified']/1000
                        contact_df.loc[i, 'lastModified'] = datetime.datetime.fromtimestamp(lastModified).strftime('%Y-%m-%d')
            self.contacts = contact_df

    def create_contact(self, **kwargs):
        """
        Create a contact in the Qualtrics mailing list.

        Parameters
        __________
        **kwargs : dict
            Additional keyword arguments that are included to accommodate the creation of more information-dense mailing lists.
            See https://api.qualtrics.com/29ece8921ba05-create-contact-request for more details.
        """
        valid_keys = {'firstName', 'lastName', 'email','phone','extRef','embeddedData','privateEmbeddedData','language','unsubscribed'}
        data = {key: value for key, value in kwargs.items() if key in valid_keys}
        if 'extRef' not in data.keys():
            raise ValueError("'extRef' must be specified.")
        url = f'https://{self._auth._data_center}.qualtrics.com/API/v3/directories/{self._directoryID}/mailinglists/{self.mailingListId}/contacts'
        headers = self._auth._request_headers
        data_json = json.dumps(data)

        response = requests.post(url, headers=headers, data=data_json)
        if response.status_code == 200:
            print(f"Contact for {data['extRef']} was successfully created in {self.name}.")
        else:
            print(f'Error {response.status_code}')

    def delete_contacts(self, contactID_list):
        """
        Delete contacts from the Qualtrics mailing list.

        Parameters
        __________
        contactID_list : list
            The Qualtrics contactId values of the contacts to remove from the Qualtrics mailing list.
        """
        if type(contactID_list) is str:
            contactID_list = [contactID_list]

        for contactID in contactID_list:
            url = f'https://{self._auth._data_center}.qualtrics.com/API/v3/directories/{self._directoryID}/mailinglists/{self.mailingListId}/contacts/{contactID}'
            headers = self._auth._request_headers
            response = requests.delete(url, headers=headers)
            if response.status_code == 200:
                # response returns 200 even if contactID doesn't exist
                print(f"No deletion errors. Confirm manually that {self.get_extref_from_contactID(contactID)[0]} was successfully deleted from {self.name}.")
            else:
                print(f'Error {response.status_code}')
       
    def get_contactID_from_extref(self, extref_list):
        """
        Look up Qualtrics contactId values from external reference values.

        Paramters
        _________
        extref_list : list
            The list of external reference values.

        Returns
        _______
        contactID_list : list
            A list of Qualtrics contactId values.
        """
        if 'extRef' not in self.contacts.columns:
            print(f'MailingList {self.name} has no contacts.')
            return
        contactID_list = []
        if type(extref_list) is str:
            extref_list = [extref_list]
        for extref in extref_list:
            index = self.contacts.index[self.contacts['extRef'] == extref]
            if not index.empty:
                index = index[0]
                contactID_list.append(self.contacts['contactId'][index])
            else:
                print(f"ExtRef '{extref}' was not found in MailingList {self.name}.")
        return contactID_list

    def get_extref_from_contactID(self, contactID_list):
        """
        Look up contact external reference values from Qualtrics contactId values.

        Paramters
        _________
        contactID_list : list
            The list of Qualtrics contactId values.

        Returns
        _______
        extref_list : list
            A list of external reference values.
        """
        if 'extRef' not in self.contacts.columns:
            print(f'MailingList {self.name} has no contacts.')
            return
        extref_list = []
        if type(contactID_list) is str:
            contactID_list = [contactID_list]
        for contactID in contactID_list:
            index = self.contacts.index[self.contacts['contactId'] == contactID]
            if not index.empty:
                index = index[0]
                extref_list.append(self.contacts['extRef'][index])
            else:
                print(f"ContactId '{contactID}' was not found in MailingList {self.name}.")
        return extref_list
    