import sys
from cardinal_glue.workgroup_api.workgroup import Workgroup, get_workgroup_list
from cardinal_glue.qualtrics_api import xm


def transfer_between_lists(transfer_uid_list, src_objects, dest_objects):
    """
    Wrapper to transfer UIDs between different lists and services.
    Currently requires that valid service objects be passed as parameters.
    Future implementation will allow specifying other parameters.

    Parameters
    __________
    transfer_uid_list : list
        The list of UIDs to transfer:
    src_object : Workgroup or xm.Mailinglist
        A Workgroup object or xm.Mailinglist object to transfer UIDs from. 
    dest_object : Workgroup or xm.Mailinglist
        A Workgroup object or xm.Mailinglist object to transfer UIDs to. 
    """
    if not isinstance(src_objects, list):
        src_objects = list(src_objects)
    if not isinstance(dest_objects, list):
        dest_objects = list(dest_objects)
    for dest in dest_objects:
        copy_to_service(src=transfer_uid_list,dest_object=dest)
    for src in src_objects:
        remove_from_service(uid_remove_list=transfer_uid_list, target_object=src)

def sync_service(src, sync_object=None, sync_service=None, sync_list_name=None, sync_workgroup_stem=None, sync_xm_directory=None):
    """
    Wrapper to synchronize the contents of a service with a source.

    Parameters
    ----------
    src : Workgroup, xm.Mailinglist, or list
        A Workgroup object, xm.Mailinglist object, or list containing UIDs.
    sync_object : Workgroup or xm.Mailinglist
        A Workgroup object or xm.Mailinglist object to synchronize with 'src'.
        Can be used in place of 'sync_service' and 'sync_list_name'.
    sync_service : string
        The name of the external service to synchronize ("qualtrics" or "workgroup").
        Not required when 'sync_object' is specified. Must be used with 'sync_list_name'.
    sync_list_name:  string
        The name of the destination service UID list to synchronize.
        Not required when 'sync_object' is specified. Must be used with 'sync_service'.
    sync_workgroup_stem : string
        The Stanford workgroup stem.
        Not required when 'sync_object' is specified. Must be used when 'sync_service' is "workgroup".
    sync_xm_directory : xm.Directory
        The xm.Directory containing the mailing list to add UIDs to.
        Optional. Will be instantiated from auth files if it is not specified.
        Useful when you don't need to reference updates made to the directory.
    """
    if not sync_object and (not sync_service or not sync_list_name):
        raise ValueError("Please provide values for either 'sync_object' or both 'sync_service' and 'sync_list_name'.")
    src_uid_list = _prepare_src(src=src)

    if not sync_object:
        _validate_service(service=sync_service, list_name=sync_list_name)
        if sync_service == 'qualtrics':
            sync_object = _validate_qualtrics(xm_directory=sync_xm_directory, list_name=sync_list_name)
        if sync_service == 'workgroup':
            sync_object = _validate_workgroup(workgroup_stem=sync_workgroup_stem, list_name=sync_list_name)

    if isinstance(sync_object, xm.MailingList):
        if 'extRef' in sync_object.contacts.columns:
            dest_uid_list = list(sync_object.contacts['extRef'])
            uid_remove_list = list(set(dest_uid_list) - set(src_uid_list))
            _remove_from_qualtrics(uid_remove_list=uid_remove_list, target_mailinglist=sync_object)
        _copy_to_qualtrics(uid_add_list=src_uid_list, dest_mailinglist=sync_object)
    elif isinstance(sync_object, Workgroup):
        dest_uid_list = sync_object.member_UIDs
        uid_remove_list = list(set(dest_uid_list) - set(src_uid_list))
        _remove_from_workgroup(uid_remove_list=uid_remove_list, target_workgroup=target_workgroup)
        _copy_to_workgroup(src_uid_list=src_uid_list, dest_workgroup=sync_object)
    else:
        raise ValueError('Please provide a valid destination object.')

def copy_to_service(src, dest_object=None, dest_service=None, dest_list_name=None, dest_workgroup_stem=None, dest_xm_directory=None):
    """
    Copy a list of UIDs from a source to a destination service.

    Parameters
    ----------
    src : Workgroup, xm.Mailinglist, or list
        A Workgroup object, xm.Mailinglist object, or list containing UIDs.
    dest_object : Workgroup or xm.Mailinglist
        A Workgroup object or xm.Mailinglist object to synchronize with 'src'.
        Can be used in place of 'dest_service' and 'dest_list_name'.
    dest_service : string
        The name of the external service to synchronize ("qualtrics" or "workgroup").
        Not required when 'dest_object' is specified. Must be used with 'dest_list_name'.
    dest_list_name:  string
        The name of the destination service UID list to synchronize.
        Not required when 'dest_object' is specified. Must be used with 'dest_service'.
    dest_workgroup_stem : string
        The Stanford workgroup stem.
        Not required when 'dest_object' is specified. Must be used when 'dest_service' is "workgroup".
    dest_xm_directory : xm.Directory
        The xm.Directory containing the mailing list to add UIDs to.
        Optional. Will be instantiated from auth files if it is not specified.
        Useful when you don't need to reference updates made to the directory.
    """
    if not dest_object and (not dest_service or not dest_list_name):
        raise ValueError("Please provide values for either 'dest_object' or both 'dest_service' and 'dest_list_name'.")
    src_uid_list = _prepare_src(src=src)

    if dest_object:
        if isinstance(dest_object, xm.MailingList):
            _copy_to_qualtrics(uid_add_list=src_uid_list, dest_xm_mailinglist=dest_object)     
        elif isinstance(dest_object, Workgroup):
            _copy_to_workgroup(uid_add_list=src_uid_list, dest_workgroup=dest_object)
        else:
            raise ValueError('Please provide a valid destination object.')
        return
    
    if dest_service:
        _validate_service(service=dest_service, list_name=dest_list_name)
        if dest_service == 'qualtrics':
            _copy_to_qualtrics(uid_add_list=src_uid_list, dest_list_name=dest_list_name, dest_xm_directory=dest_xm_directory)
        if dest_service == 'workgroup':
            _copy_to_workgroup(uid_add_list=src_uid_list, dest_list_name=dest_list_name, dest_workgroup_stem=dest_workgroup_stem)

def remove_from_service(uid_remove_list, target_object=None, target_service=None, target_list_name=None, target_workgroup_stem=None, target_xm_directory=None):
    """
    Remove a list of UIDs from a target service.

    Parameters
    ----------
    uid_remove_list : list
        A list containing UIDs to remove.
    target_object : Workgroup or xm.Mailinglist
        A Workgroup object or xm.Mailinglist object to remove UIDs from.
        Can be used in place of 'target_service' and 'target_list_name'.
    target_service : string
        The name of the external service to remove UIDs from ("qualtrics" or "workgroup").
        Not required when 'target_object' is specified. Must be used with 'target_list_name'.
    target_list_name : string
        The name of the destination service list to remove UIDs from.
        Not required when 'target_object' is specified. Must be used with 'target_service'.
    target_workgroup_stem : string
        The Stanford workgroup stem.
        Not required when 'target_object' is specified. Must be used when 'target_service' is "workgroup".
    target_xm_directory : xm.Directory
        The xm.Directory containing the mailing list to sync.
        Optional. Will be instantiated from auth files if it is not specified.
        Useful when you don't need to reference updates made to the directory.
    """
    if not target_object and (not target_service or not target_list_name):
        raise ValueError("Please provide values for either 'target_object' or both 'target_service' and 'target_list_name'.")

    if target_object:
        if isinstance(target_object, xm.MailingList):
            _remove_from_qualtrics(uid_remove_list=uid_remove_list, target_xm_mailinglist=target_object)     
        elif isinstance(target_object, Workgroup):
            _remove_from_workgroup(uid_remove_list=uid_remove_list, target_workgroup=target_object)
        else:
            raise ValueError('Please provide a valid destination object.')
        return

    if target_service:
        _validate_service(service=target_service, list_name=target_list_name)
        if target_service == 'qualtrics':
            _remove_from_qualtrics(uid_remove_list=uid_remove_list, target_list_name=target_list_name, target_xm_directory=target_xm_directory)
        if target_service == 'workgroup':
            _remove_from_workgroup(uid_remove_list=uid_remove_list, target_list_name=target_list_name, target_workgroup_stem=target_workgroup_stem)

def _copy_to_qualtrics(uid_add_list, dest_list_name=None, dest_xm_directory=None, dest_xm_mailinglist=None):
    """
    Copy a list of UID values to a Qualtrics mailing list.

    Parameters
    ----------
    uid_add_list : list
        A list containing UIDs.
    dest_list_name:  string
        The name of the Qualtrics mailing list.
    dest_xm_directory : xm.Directory
        The xm.Directory containing the mailing list to add UIDs to.
        Optional. Will be instantiated from auth files if it is not specified.
    dest_xm_mailinglist : xm.MailingList
        The MailingList to remove UIDs from.
        Optional, will be instantiated from 'dest_list_name', 'dest_xm_directory', and auth files if not specified.
    """
    dest_mailinglist = _validate_qualtrics(xm_directory=dest_xm_directory, list_name=dest_list_name, xm_mailinglist=dest_xm_mailinglist)
    if 'extRef' in dest_mailinglist.contacts.columns:
        dest_uid_list = list(dest_mailinglist.contacts['extRef'])
        uid_add_list = list(set(uid_add_list) - set(dest_uid_list))
    for uid in uid_add_list:
        dest_mailinglist.create_contact(**{'extRef':uid})
    remove_qualtrics_duplicates(list_name=dest_list_name, xm_directory=dest_xm_directory, xm_mailinglist=dest_xm_mailinglist)

def _remove_from_qualtrics(uid_remove_list, target_list_name=None, target_xm_directory=None, target_xm_mailinglist=None):
    """
    Remove a list of UIDs from a Qualtrics mailing list.

    Parameters
    ----------
    uid_remove_list : list
        A list containing UIDs to remove.
    target_list_name : string
        The name of the Qualtrics mailing list.
        Not required when 'workgroup' is specified.
    target_xm_directory : xm.Directory
        The xm.Directory containing the mailing list to remove UIDs from.
        Optional. Will be instantiated from auth files if it is not specified.
    target_xm_mailinglist : xm.MailingList
        The MailingList to remove UIDs from.
        Optional, will be instantiated from 'target_list_name', 'target_xm_directory', and auth files if not specified.
    """
    target_xm_mailinglist = _validate_qualtrics(xm_directory=target_xm_directory, list_name=target_list_name, xm_mailinglist=target_xm_mailinglist)
    if 'extRef' in target_xm_mailinglist.contacts.columns:
        dest_uid_list = list(target_xm_mailinglist.contacts['extRef'])
        uid_remove_list = list(set(uid_remove_list) & set(dest_uid_list))
        contactID_remove_list = target_xm_mailinglist.get_contactID_from_extref(uid_remove_list)
        target_xm_mailinglist.delete_contacts(contactID_remove_list)

def _copy_to_workgroup(uid_add_list, dest_list_name=None, dest_workgroup_stem=None, dest_workgroup=None):
    """
    Add a list of UIDs to a Stanford workgroup.

    Parameters
    ----------
    uid_add_list : list
        A list containing UID values.
    dest_list_name : string
        The name of the Stanford workgroup.
        Not required when 'dest_workgroup' is specified.
    dest_workgroup_stem : string
        The Stanford workgroup stem.
        Not required when 'dest_workgroup' is specified.
    dest_workgroup : Workgroup
        The Workgroup to remove UIDs from.
        Optional, will be instantiated from 'dest_list_name', 'dest_workgroup_stem', and auth files if not specified.
    """
    dest_workgroup = _validate_workgroup(workgroup_stem=dest_workgroup_stem, list_name=dest_list_name, workgroup=dest_workgroup)
    dest_workgroup.add_members(uid_add_list)

def _remove_from_workgroup(uid_remove_list, target_list_name=None, target_workgroup_stem=None, target_workgroup=None):
    """
    Remove a list of UIDs from a Stanford workgroup.

    Parameters
    ----------
    uid_remove_list : list
        A list containing UIDs to remove.
    target_list_name : string
        The name of the Stanford workgroup.
        Not required when 'target_workgroup' is specified.
    target_workgroup_stem : string
        The Stanford workgroup stem.
        Not required when 'target_workgroup' is specified.
    target_workgroup : Workgroup
        The Workgroup oject to be acted on.
        Optional, will be instantiated from 'target_list_name', 'target_workgroup_stem', and auth files if not specified.
    """
    target_workgroup = _validate_workgroup(workgroup_stem=target_workgroup_stem, list_name=target_list_name, workgroup=target_workgroup)
    target_workgroup.remove_members(uid_remove_list)   

def _prepare_src(src):
    """
    Retrieve list of UIDs from 'src' if 'src' is not a list.

    Parameters
    ----------
    src : Workgroup, xm.Mailinglist, or list
        A Workgroup object, xm.Mailinglist object, or list containing UID values.

    Returns
    -------
    uid_list : list
        A list containing UID values.
    """
    uid_list = src
    if isinstance(src, xm.MailingList):
        uid_list = list(src.contacts['extRef'])
    elif isinstance(src, Workgroup):
        uid_list = src.member_UIDs
    if not isinstance(uid_list, list):
        raise ValueError('Please provide a valid source object or list.')
    return uid_list

def _validate_service(service, list_name):
    """
    Check for valid service names.

    Parameters
    ----------
    service : string
        The name of the external service to synchronize ("qualtrics" or "workgroup").
    """
    if type(service) is list:
        raise ValueError('Please pass a single service name as a string.')
    valid_services = ['qualtrics','workgroup']
    for valid in valid_services:
        if valid.lower() not in valid_services:
            raise ValueError('Please provide a valid service name.')

def _validate_qualtrics(xm_directory=None, list_name=None, xm_mailinglist=None):
    """
    Check for a valid Qualtrics directory that contains the specified mailing list.

    Parameters
    ----------
    xm_directory : xm.Directory
        The xm.Directory object to validate.
        Not required when 'xm_mailinglist' is specified.
    list_name:  string
        The name of the Qualtrics mailing list to validate.
        Not required when 'xm_mailinglist' is specified.
    xm_mailinglist : xm.MailingList
        The xm.MailingList object to validate.
        Not required when 'xm_directory' and 'list_name' are specified.

    Returns
    -------
    xm_mailinglist : xm.MailingList
        A valid xm.MailingList object.
    """
    if xm_mailinglist:
        if isinstance(xm_mailinglist, xm.MailingList):
            return xm_mailinglist
        else:
            raise TypeError("Please provide a valid xm.MailingList object.")
    if xm_directory and not isinstance(xm_directory, xm.Directory):
        raise TypeError("Please provide a valid xm.Directory object.")
    if not xm_directory:
        xm_directory = xm.Directory()
    valid_list_names = list(xm_directory.mailinglist_frame['name'])
    if list_name not in valid_list_names:
        raise ValueError('Please provide a valid Qualtrics mailing list name.')
    return xm_directory.get_list_from_name(list_name)

def _validate_workgroup(workgroup_stem=None, list_name=None, workgroup=None):
    """
    Check for a valid Stanford workgroup stem that contains the specified workgroup.

    Parameters
    ----------
    workgroup_stem : string
        The Stanford workgroup stem.
        Not requried when 'workgroup' is specified.
    list_name : string
        The name of the Stanford workgroup to validate.
        Not required when 'workgroup' is specified.
    workgroup : Workgroup
        The Workgroup object to validate.
        Not required when 'workgroup_stem' and 'list_name' are specified.

    Returns
    _______
    workgroup : Workgroup
        A valid Workgroup object.
    """
    if (not list_name or not workgroup_stem) and not workgroup:
        raise ValueError("Please specify a value for either 'workgroup' or both 'list_name' and 'workgroup_stem'.")
    if workgroup and not isinstance(workgroup, Workgroup):
        raise TypeError("Please specify 'workgroup' as a valid Workgroup object.")  
    if not workgroup:
        list_name = workgroup.name
        valid_list_names = get_workgroup_list(workgroup_stem)
        if list_name not in valid_list_names:
            raise ValueError('Please provide a valid workgroup name.')
        workgroup = Workgroup(workgroup_stem, list_name)
    return workgroup

def remove_qualtrics_duplicates(xm_directory=None, list_name=None, xm_mailinglist=None):
    """
    Remove duplicate UIDs from a Qualtrics mailing list.

    Parameters
    ----------
    xm_directory : xm.Directory
        The xm.Directory containing the mailing list to remove duplicate UIDs from.
        Not required when 'xm_mailinglist' is specified.
        Will be instantiated from auth files if only 'list_name' is not specified.
    list_name:  string
        The name of the Qualtrics mailing list to remove duplicate UIDs from.
        Not required when 'xm_mailinglist' is specified.
    xm_mailinglist : xm.MailingList
        The xm.MailingList object to remove duplicate UIDs from.
        Not required when 'xm_directory' and 'list_name' are specified.
    """
    mailinglist = _validate_qualtrics(xm_directory=xm_directory, list_name=list_name, xm_mailinglist=xm_mailinglist)
    contact_df = mailinglist.contacts
    if 'contactId' in contact_df.columns:
        duplicate_rows = contact_df.duplicated(subset='extRef')
        contactID_list = contact_df[duplicate_rows]['contactId']
        mailinglist.delete_contacts(contactID_list)

