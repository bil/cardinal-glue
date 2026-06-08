import re

def transform_cap_profile(uid, raw_profile, cap_client=None):
    """
    Transforms a raw CAP API profile dict into a standardized user profile format.
    
    This function handles custom parsing and edge cases:
    1. Extracts affiliations from the raw API response
    2. Resolves organization codes to human-readable names
    3. Applies domain-specific business rules for title/affiliation mapping
    
    Args:
        uid (str): The user's SUNet ID
        raw_profile (dict): The raw dict returned from CAP API.
        cap_client (CAPClient, optional): An instance of CAPClient for resolving organization codes.
    
    Returns:
        dict with keys: 'uid', 'title', 'affiliation', 'display_name'
    """
    title, affiliation, display_name = None, None, None
    
    if not raw_profile:
        return {'uid': uid, 'title': title, 'affiliation': affiliation, 'display_name': display_name}
    
    # --- Extract affiliations from raw profile ---
    # Collect all true affiliations as a list, stripping 'cap' prefix
    cap_affiliation_dict = raw_profile.get('affiliations', {})
    affiliations = [
        (k.lower()[3:] if k.startswith('cap') else k.lower())
        for k, v in cap_affiliation_dict.items() if v is True
    ]
    
    # --- Extract position from contacts ---
    position = 'NULL'
    contacts = None
    if 'contacts' in raw_profile and raw_profile['contacts']:
        contacts = raw_profile['contacts'][0]
        position = str(contacts.get('position', 'NULL'))
    
    # --- Resolve organization ---
    organization = None
    if 'advisees' in raw_profile:
        # For advisors, get org from titles
        for title_entry in raw_profile.get('titles', []):
            if title_entry.get('appointmentType') == 'pr':
                org_code = title_entry.get('organization', {}).get('orgCode')
                if org_code and cap_client:
                    organization = cap_client.get_org_from_code(org_code)
                break
    else:
        # For others, get org from organizations list
        for org in raw_profile.get('organizations', []):
            if org.get('type') == 'affiliation':
                org_code = org.get('organization', {}).get('orgCode')
                if org_code and org_code != 'NULL':
                    if cap_client:
                        organization = cap_client.get_org_from_code(org_code)
                    if not organization:
                        organization = org_code
                    break
    
    # --- Extract display name ---
    display_name = raw_profile.get('displayName')

    # --- Determine title from affiliations ---
    if isinstance(affiliations, list) and affiliations:
        title = affiliations[0]
    elif isinstance(affiliations, str):
        title = affiliations
    else:
        title = None
    
    # --- Apply business rules for title mapping ---
    
    # Specific case: registry + fellow = fellow (not staff)
    if isinstance(affiliations, list):
        if 'registry' in affiliations and 'fellow' in affiliations:
            title = 'fellow'
        # Specific case: student affiliations should override staff
        elif 'staff' in affiliations and 'msstudent' in affiliations:
            title = 'msstudent'
        elif 'staff' in affiliations and 'phdstudent' in affiliations:
            title = 'phdstudent'
        elif 'staff' in affiliations and 'mdstudent' in affiliations:
            title = 'mdstudent'
        # Specific case: staff + faculty with University Staff affiliationType = staff
        elif 'staff' in affiliations and 'faculty' in affiliations:
            if isinstance(contacts, dict) and contacts.get('affiliationType') == 'University - Staff':
                title = 'staff'
        # Transform registry to undergraduate or staff based on position
        elif title == 'registry':
            if position.lower() == 'undergraduate':
                title = 'undergraduate'
            else:
                title = 'staff'
    elif isinstance(affiliations, str):
        if title == 'registry':
            if position.lower() == 'undergraduate':
                title = 'undergraduate'
            else:
                title = 'staff'
        
    # Transform faculty with specific contact positions
    if title == 'faculty' and isinstance(contacts, dict):
        contact_position = contacts.get('position', '')
        if contact_position == 'Instructor':
            title = 'postdoc'
        elif 'research scientist' in contact_position.lower():
            title = 'staff'
            
    if position and re.compile(r"Basic Life Res.* Scientist", re.IGNORECASE).match(position): 
        title = 'postdoc'
    if organization == 'NKGV': 
        organization = 'vice-provost-and-dean-of-research'
    affiliation = (str.split(organization, '/')[0] if organization else None)
    
    # Apply hardcoded affiliation transformations
    if affiliation:
        affiliation_mapping = {
            'school-of-medicine': 'SoM',
            'graduate-school-of-business': 'GSB',
            'land-buildings-and-real-estate': 'LBRE',
            'vice-provost-and-dean-of-research': 'VPDoR',
            'school-of-humanities-and-sciences': 'H&S',
            'school-of-engineering': 'SoE',
            'department-of-athletics-physical-education-and-recreation': 'DAPER',
            'graduate-school-of-education': 'GSE',
            'slac-national-accelerator-laboratory': 'SLAC',
            'vice-provost-for-student-affairs': 'VPSA'
        }
        affiliation = affiliation_mapping.get(affiliation, affiliation)
    
    return {'uid': uid, 'title': title, 'affiliation': affiliation, 'display_name': display_name}
