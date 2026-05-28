# cardinal_glue

An integrative Python package that provides easy authentication with Google and Qualtrics, as well as Stanford-specific services. This is coupled with straightforward, Pythonic file-management capabilities for Google Drive and Google Cloud Storage. Additional functionality allows for effective UID management within the Stanford computing ecosystem.

---

## API Reference

### Google Authentication

`GoogleAuth` handles authentication with Google services including Drive, GCS, and Firestore.

```python
from cardinal_glue.auth.googleauth import GoogleAuth

gauth = GoogleAuth()
credentials = gauth.credentials  # Use with Google client libraries
```

**Credential Discovery Order:**
1. `GOOGLE_APPLICATION_CREDENTIALS` env var
2. JSON credentials at `~/.config/cardinal-glue/google_application_credentials.json`
3. DB credentials from `gcloud auth login`
4. Google Colab interactive login (if in Colab environment)

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google credentials JSON |
| `CLOUDSDK_CONFIG` | Path to gcloud config directory |
| `USE_AUTH_EPHEM` | Set to `0` to use file-based credentials |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID (for Firestore) |

---

### Stanford Workgroup API

Manage Stanford Workgroups programmatically.

#### Authentication

> **Note:** `Workgroup` and `WorkgroupManager` automatically handle authentication when instantiated. You only need to use `WorkgroupAuth` directly if you want to pass a custom auth object.

```python
from cardinal_glue.workgroup_api.workgroupauth import WorkgroupAuth

auth = WorkgroupAuth()  # Only needed for custom auth configuration
wg = Workgroup(stem="my-stem", workgroup="my-group", auth=auth)
```

**Credential Priority:**
1. `creds` parameter (tuple of cert/key paths)
2. `WORKGROUP_CERT_PATH` + `WORKGROUP_KEY_PATH` env vars (file paths)
3. `WORKGROUP_CERT` + `WORKGROUP_KEY` env vars (cert/key content for containers)
4. Default: `~/.config/cardinal-glue/stanford_workgroup.{cert,key}`

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `WORKGROUP_CERT_PATH` | Path to cert file |
| `WORKGROUP_KEY_PATH` | Path to key file |
| `WORKGROUP_CERT` | Certificate content (for containers) |
| `WORKGROUP_KEY` | Key content (for containers) |
| `WORKGROUP_UAT` | Set to `'true'` to use the UAT server (`workgroupsvc-uat.stanford.edu`) |

#### Workgroup

```python
from cardinal_glue.workgroup_api.workgroup import Workgroup

# Query a workgroup
wg = Workgroup(stem="my-stem", workgroup="my-group")

# Access members and admins
print(wg.members)           # List of member UIDs
print(wg.member_details)    # Detailed member info
print(wg.admins)            # List of administrator info

# Add/remove members and admins (supports types 'USER', 'WORKGROUP', 'CERTIFICATE')
# Note: Set ignore_missing=True during migrations to gracefully skip deleted legacy entities
wg.add_members(["user1", "user2"])
wg.add_admins(["admin1", "dept:admin-group"], admin_type='WORKGROUP')
wg.remove_members(["user3"])

# Programmatically tighten security properties
wg.update_properties(reusable='FALSE', visibility='PRIVATE')
```

#### WorkgroupManager

```python
from cardinal_glue.workgroup_api.workgroup import WorkgroupManager

# Manage workgroups under a stem
mgr = WorkgroupManager(stem="my-stem")

# List workgroups
print(mgr.populate_workgroup_list())

# Create/delete workgroups
mgr.create_workgroup(name="new-group", description="My new workgroup")
mgr.delete_workgroup(name="old-group")

# Copy/Move/Sync workgroups
mgr.copy_workgroup(
    name="source-group", 
    new_stem="new-stem", 
    new_name="migrated-group",
    overwrite=True,       # Sync to destination if it already exists
    remove_original=True  # Move the group instead of just copying
)
```

---

### Qualtrics XM API

Interact with Qualtrics XM Directory mailing lists.

#### Authentication

> **Note:** `Directory` and `MailingList` automatically handle authentication when instantiated. You only need to use `QualtricsAuth` directly if you want to pass a custom auth object.

```python
from cardinal_glue.qualtrics_api.qualtricsauth import QualtricsAuth

auth = QualtricsAuth()  # Only needed for custom auth configuration
directory = Directory(directoryID="POOL_xxx", auth=auth)
```

**Credential File:** `~/.config/cardinal-glue/qualtrics.json`

#### Directory

```python
from cardinal_glue.qualtrics_api.xm import Directory

# Connect to your XM Directory
directory = Directory(directoryID="POOL_xxx")

# List mailing lists
print(directory.mailinglist_frame)

# Get a specific mailing list
mlist = directory.get_mailinglist_from_name("My Survey List")
```

#### MailingList

```python
from cardinal_glue.qualtrics_api.xm import MailingList

# Get contacts
print(mlist.contacts)

# Create a contact
mlist.create_contact(firstName="John", lastName="Doe", email="jdoe@stanford.edu", extRef="jdoe")

# Delete contacts
mlist.delete_contacts(contactID_list=["CID_xxx", "CID_yyy"])
```

#### Survey

```python
from cardinal_glue.qualtrics_api.surveys import Survey

# Connect to a survey
survey = Survey(survey_ID="SV_xxxxxxxxxxxxx")

# Get question definitions
all_questions = survey.get_question()           # All questions
one_question = survey.get_question("QID1")      # Specific question

# Update a question
survey.update_question("QID1", updates={"QuestionText": "New question text"})

# Pull survey responses as DataFrame
survey.pull_survey_responses()
print(survey.responses)  # pd.DataFrame
```

---

### Stanford CAP API

Query Stanford's Community Academic Profiles.

#### Authentication

> **Note:** `CAPClient` automatically handles authentication when instantiated. You only need to use `CAPAuth` directly if you want to pass a custom auth object.

```python
from cardinal_glue.cap_api.capauth import CAPAuth

auth = CAPAuth()  # Only needed for custom auth configuration
client = CAPClient(auth=auth)
```

**Credential File:** `~/.config/cardinal-glue/cap.json`

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `CAP_CLIENT` | JSON string of credentials (alternative to file) |

#### CAPClient

```python
from cardinal_glue.cap_api.cap import CAPClient

# Initialize client
client = CAPClient()

# Get a profile by UID (returns raw dict from API)
profile = client.get_profile_from_uid("jsmith")

# Access profile data directly
print(profile['affiliations'])   # e.g., {'capFaculty': True, 'capStaff': False, ...}
print(profile['displayName'])    # e.g., "John Smith"
print(profile['contacts'])       # List of contact info dicts

# Resolve organization codes to human-readable names
org_name = client.get_org_from_code("AABB")  # e.g., "School of Medicine"
```

### Canvas LMS API

Export user and course data from Canvas.

#### Authentication

> **Note:** `CanvasClient` automatically handles authentication when instantiated. You only need to use `CanvasAuth` directly if you want to pass a custom auth object.

```python
from cardinal_glue.canvas_api.canvasauth import CanvasAuth

auth = CanvasAuth()  # Only needed for custom auth configuration
client = CanvasClient(auth=auth)
```

**Credential File:** `~/.config/cardinal-glue/canvas.json`

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `CANVAS_ACCESS_TOKEN` | Your Canvas static access token |
| `CANVAS_BASE_URL` | Base URL (defaults to `https://canvas.stanford.edu`) |

**JSON Structure (canvas.json):**
```json
{
    "base_url": "https://canvas.stanford.edu",
    "api_token": "YOUR_STATIC_TOKEN"
}
```

#### Getting Credentials

to get credentials for the canvas api, it's just self-service through your profile: log in to canvas and go to `account` > `settings` > `approved integrations` > `+ new access token`.

#### CanvasClient

```python
from cardinal_glue.canvas_api.canvas import CanvasClient

# Initialize client
client = CanvasClient()

# List courses you have access to
courses = client.get_courses()
for course in courses:
    print(f"{course['id']}: {course['name']}")

# Get a single user
user = client.get_user("sis_user_id:jsmith")
print(user['name'])

# Get all users in a course (automatically handles pagination)
users = client.get_users_in_course("12345")
print(f"Found {len(users)} users")
```

---

### Firestore

Create Firestore clients with automatic credential handling.

```python
from cardinal_glue.firestore import FirestoreGenerator

# Initialize with database ID
fs = FirestoreGenerator(database_id="my-database")

# Access the Firestore client
db = fs.database
doc = db.collection("users").document("user1").get()
```

**Authentication Priority:**
1. Cloud Run environment (`K_REVISION` env var → automatic)
2. Google Colab with `GOOGLE_CLOUD_PROJECT` env var
3. Firebase service account JSON at `~/.config/cardinal-glue/firebase.json`

**Credential Files:**
- `~/.config/cardinal-glue/firebase.json` — Firebase service account
- `~/.config/cardinal-glue/firestore.json` — Database ID config

---

### FileSystem

Unified file operations for Google Drive and Google Cloud Storage.

```python
from cardinal_glue.filesystem import FileSystem

# Google Drive
gdrive = FileSystem(end_point="gdrive")
gdrive.ls("/path/to/folder")
gdrive.get("/remote/file.txt", "/local/file.txt")
gdrive.put("/local/file.txt", "/remote/file.txt")

# Google Cloud Storage
gcs = FileSystem(end_point="gcsfs", project="my-gcp-project")
gcs.ls("my-bucket/path/")
```

---

### Core Sync Utilities

High-level functions for syncing UIDs between services.

```python
from cardinal_glue import sync_service, copy_to_service, remove_from_service

# Sync workgroup members to Qualtrics mailing list
sync_service(
    src=workgroup,
    sync_service="qualtrics",
    sync_list_name="Survey Recipients"
)

# Copy UIDs to a workgroup
copy_to_service(
    src=["uid1", "uid2", "uid3"],
    dest_service="workgroup",
    dest_list_name="my-group",
    dest_workgroup_stem="dept:myorg"
)

# Remove UIDs from Qualtrics
remove_from_service(
    uid_remove_list=["uid1", "uid2"],
    target_service="qualtrics",
    target_list_name="Survey Recipients"
)
```

---

## Planned Functionality

- File management through `s3fs` and `sshfs`

---

## Contact

[Bryce Grier](mailto:bdgrier@stanford.edu)