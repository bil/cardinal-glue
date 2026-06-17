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
    
    # --- Resolve organization and primary title ---
    organization = None
    title = None
    titles = raw_profile.get('titles', [])
    primary_title_str = ""

    # Primary title extraction path (using titles[0])
    if titles and isinstance(titles, list) and isinstance(titles[0], dict):
        primary_title_entry = titles[0]
        raw_title_aff = primary_title_entry.get('affiliation')
        primary_title_str = str(primary_title_entry.get('title', 'NULL'))

        if raw_title_aff:
            title = str(raw_title_aff).lower()
            if title.startswith('cap'):
                title = title[3:]

        # Extract organization code from primary title
        org_code = primary_title_entry.get('organization', {}).get('orgCode')
        if org_code and org_code != 'NULL':
            if cap_client:
                organization = cap_client.get_org_from_code(org_code)
            if not organization:
                organization = org_code

    # --- Extract display name ---
    display_name = raw_profile.get('displayName')

    # --- Apply business rules for title mapping ---

    # Specific case: staff + faculty with University Staff/any override = staff
    if isinstance(affiliations, list) and 'staff' in affiliations and 'faculty' in affiliations:
        title = 'staff'

    # Transform registry based on title string or fellow affiliation
    elif title == 'registry':
        if primary_title_str.lower() == 'undergraduate':
            title = 'undergraduate'
        elif isinstance(affiliations, list) and 'fellow' in affiliations:
            title = 'fellow'
        else:
            title = 'staff'

    # Transform faculty with specific title strings
    elif title == 'faculty':
        if primary_title_str == 'Instructor':
            title = 'postdoc'
        elif 'research scientist' in primary_title_str.lower():
            title = 'staff'

    # Transform Basic Life Research Scientist (can be faculty or staff)
    if primary_title_str and re.compile(r"Basic Life Res.* Scientist", re.IGNORECASE).match(primary_title_str): 
        title = 'postdoc'

    if organization == 'NKGV': 
        organization = 'vice-provost-and-dean-of-research'
    affiliation = (organization.split('/')[0] if isinstance(organization, str) else None)
    
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
