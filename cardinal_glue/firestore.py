import os
import json
from google.cloud import firestore
import firebase_admin

class FirestoreGenerator():
    """
    A class providing easy creation of a Firestore client through multiple authentication workflows.

    Attributes
    __________
    __FIREBASE_JSON_NAME: string
        The name of the JSON file containing the Firebase service account credentials
    """

    __FIREBASE_JSON_NAME = 'firebase.json'

    def __init__(self, database_id, google_cloud_project=None, auto_auth=True):

        if google_cloud_project:
            os.environ['GOOGLE_CLOUD_PROJECT'] = google_cloud_project
        self.database_id = database_id
        if auto_auth:
            self.authenticate()

    def authenticate(self)
        if os.getenv('K_REVISION') or os.getenv('COLAB_RELEASE_TAG'):
            self.database = firestore.Client(database=self.database_id)
        else:
            file_path = os.path.join(self._AUTH_PATH, self.__FIREBASE_JSON_NAME)
            if os.path.exists(file_path):
                f = open(file_path)
                firebase_cred_dict = json.load(f)
            else:
                raise InvalidAuthInfo('Unable to generate credentials from file. Please ensure that there is valid json file containing Firebase authentication information.')
            creds = firebase_admin.credentials.Certificate(firebase_cred_dict)
            firebase_app = firebase_admin.initialize_app(creds)    
            self.database = firestore.client(firebase_app, database_id=database_id)