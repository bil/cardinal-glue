import re

def transform_cap_profile(uid, raw_profile, cap_client=None):
    """
    Transforms a raw CAP API profile dict into a standardized user profile format.
    
    This function handles custom parsing and edge cases:
    1. Extracts affiliations from the raw API response
    2. Resolves organization codes to human-readable names
    3. Applies domain-specific business rules for title/affiliation mapping
    4. Extracts principal investigator / advisor (pi) if present
    
    Args:
        uid (str): The user's SUNet ID
        raw_profile (dict): The raw dict returned from CAP API.
        cap_client (CAPClient, optional): An instance of CAPClient for resolving organization codes.
    
    Returns:
        dict with keys: 'uid', 'title', 'affiliation', 'affiliation_mapped', 'display_name', 'pi'
    """
    title, affiliation, display_name, pi = None, None, None, None
    
    if not raw_profile:
        return {'uid': uid, 'title': title, 'affiliation': affiliation, 'display_name': display_name, 'pi': None}
    
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
        has_real_staff_title = False
        # Override the primary extraction by finding the specific staff title entry
        for t in titles:
            aff = str(t.get('affiliation', '')).lower()
            if aff in ('capstaff', 'staff'):
                # Exclude simple institute memberships (jobCode 1234, or title of "Member")
                job_code = t.get('jobCode')
                t_title = t.get('title', '')
                if job_code != '1234' and (not isinstance(t_title, str) or t_title.lower() != 'member'):
                    has_real_staff_title = True
                    primary_title_str = str(t_title if t_title is not None else 'NULL')
                    org_dict = t.get('organization')
                    org_code = org_dict.get('orgCode') if isinstance(org_dict, dict) else None
                    if org_code and org_code != 'NULL':
                        if cap_client:
                            organization = cap_client.get_org_from_code(org_code)
                        if not organization:
                            organization = org_code
                    break
        if has_real_staff_title:
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
    if title != 'staff' and primary_title_str and re.compile(r"Basic Life Res.* Scientist", re.IGNORECASE).match(primary_title_str): 
        title = 'postdoc'

    if organization == 'NKGV': 
        organization = 'vice-provost-and-dean-of-research'
    affiliation = (organization.split('/')[0] if isinstance(organization, str) else None)
    
    # Generate the mapped affiliation for the new affiliation_mapped field
    affiliation_mapped = None
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
        affiliation_mapped = affiliation_mapping.get(affiliation, affiliation)
    
    # --- Extract advisor/PI if present ---
    stanford_advisors = raw_profile.get('stanfordAdvisors')
    if isinstance(stanford_advisors, list) and len(stanford_advisors) > 0:
        first_advisor = stanford_advisors[0]
        if isinstance(first_advisor, dict):
            pi = first_advisor.get('fullName')

    return {'uid': uid, 'title': title, 'affiliation': affiliation, 'affiliation_mapped': affiliation_mapped, 'display_name': display_name, 'pi': pi}
