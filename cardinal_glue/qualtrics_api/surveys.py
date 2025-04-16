import requests
import pandas as pd
import re
import zipfile
import json
import io
import sys
import time
from cardinal_glue.qualtrics_api.qualtricsauth import QualtricsAuth
from cardinal_glue.auth.core import InvalidAuthInfo, CannotInstantiateServiceObject


class Survey():
    """
    A class representing a Qualtrics survey.
    """
    def __init__(self, survey_ID, auth=None):
        """
        The constructor for the Survey class.

        Parameters
        __________
        survey_ID : string
            The Qualtrics surveyId value for the survey represented by the object.
        auth : QualtricsAuth
            The QualtricsAuth object needed to query the Qualtrics API.
        """
        survey_ID_pattern = re.compile(r"SV_[A-Za-z0-9]{15}", re.IGNORECASE)
        if not survey_ID_pattern.match(survey_ID):
            raise ValueError("Please provide a valid survey ID")
        self._survey_ID = survey_ID
        self._auth = auth
        if not self._auth:
            try:
                self._auth = QualtricsAuth()
            except InvalidAuthInfo:
                raise CannotInstantiateServiceObject()
            except ValueError:
                raise CannotInstantiateServiceObject()

    def get_question(self, question_ID=None):
        """
        Retrieve a question definition.
        If no value is provided for 'question_ID', all question definitons are returned.

        Paramters
        _________
        question_ID : string
            The Qualtrics questionId value for the question to retrieve.

        Returns
        _______
        question_data : dict
            The question definition.
        """
        if not question_ID:
            url_get = f'https://{self._auth._data_center}.qualtrics.com/API/v3/survey-definitions/{self._survey_ID}/questions'
        else:
            url_get = f'https://{self._auth._data_center}.qualtrics.com/API/v3/survey-definitions/{self._survey_ID}/questions/{question_ID}'    
        headers = self._auth._request_headers

        get_response = requests.request("GET", url_get, headers=headers)
        if get_response.status_code == 200:
            question_data = get_response.json()['result']
            if not question_ID:
                question_data = question_data['elements']
                print(f'All questions successfully retrieved.')  
            else:
                print(f'Question {question_ID} successfully retrieved.')    
            return question_data
        else:
            print(f'Unable to retrieve question {question_ID} : {get_response}')
            
    def update_question(self, question_ID, updates):
        """
        Update a question definition.

        Parameters
        __________
        question_ID : string
            The Qualtrics questionId value for the question to update.
        updates : dict
            A dict containg valid key-value pairs to update the question definition with.
            See https://api.qualtrics.com/00d49b25519bb-update-question for valid keys.
        """
        if not isinstance(updates, dict):
            raise TypeError("'updates' must be a dict")
        question_data = self.get_question(question_ID)
        for field in updates:
            if field not in question_data.keys():
                raise KeyError("Please ensure that 'updates' only contains valid keys for the question type.")
            question_data[field] = updates[field]
        headers = self._auth._request_headers
        url_put = f'https://{self._auth._data_center}.qualtrics.com/API/v3/survey-definitions/{self._survey_ID}/questions/{question_ID}'
        question_data_json = json.dumps(question_data)

        put_response = requests.request('PUT', url_put, headers=headers, data=question_data_json)
        if put_response.status_code == 200:
            print(f'Question {question_ID} successfully updated.') 
            url_post = f'https://{self._auth._data_center}.qualtrics.com/API/v3/survey-definitions/{self._survey_ID}/versions'
            publish_data = {
                "Description": "",
                "Published": True
            }
            post_response = requests.request('POST', url_post, headers=headers, data=json.dumps(publish_data))
        elif put_response.status_code == 500:
            max_retries = 5
            while put_response.status_code == 500:
                put_response = requests.request('PUT', url_put, headers=headers, data=question_data_json)
                retry_count += 1
                if retry_count > max_retries:
                    print(f"Exceeded maximum retries. Unable to update question {question_ID} : {put_response}")
                    return
                sleep_interval = 2 ** retry_count
                print(f"Checking again in {sleep_interval} seconds")
                time.sleep(sleep_interval) 
        else:
            print(f'Unable to update question {question_ID} : {put_response}')
            return
        if post_response.status_code == 200:
            print(f'Survey {self._survey_ID} successfully published.') 
        else:
            print(f'Unable to publish survey {self._survey_ID} : {post_response}')

    def pull_survey_responses(self):
        """
        Wrapper function to pull survey responses from Qualtrics and convert to pd.DataFrame.
        """
        base_url = f"https://{self._auth._data_center}.qualtrics.com/API/v3/surveys/{self._survey_ID}/export-responses/"
        progress_id = self._start_response_export(base_url=base_url)
        file_ID = self._get_response_export_progress(base_url=base_url, progress_id=progress_id)
        response_file = self._get_response_export_file(base_url=base_url, file_ID=file_ID)
        self.responses = pd.read_csv(io.BytesIO((response_file.read(response_file.filelist[0].filename))))

    def _start_response_export(self, base_url):
        """
        Initialize the response export.

        Parameters
        __________
        base_url : string
            The base url for sending the export requests.

        Returns
        _______
        string
            The progressId value to use for future requests that check the response export progress.
        """
        progress_status = "inProgress"

        data = {
                "format": "csv",
            }
        download_request_response = requests.request("POST", base_url, json=data, headers=self._auth._request_headers)
        try:
            return download_request_response.json()["result"]["progressId"]
        except KeyError:
            print(download_request_response.json())
            sys.exit(2)

    def _get_response_export_progress(self, base_url, progress_id, limit_retry=True):
        """
        Periodically check the export progress and wait until it is ready.
        
        Parameters
        __________
        base_url : string
            The base url for sending the export requests.
        progress_id : string
            The progressId value to use for checking the response export progress.
        limit_retry : bool
            Whether to let retries occur indefinitely.
        """
        file_ID = None
        max_retries = 10
        retry_count = 0
        while progress_status != "complete" and progress_status != "failed" and file_ID is None:
            request_check_URL = base_url + progress_id
            request_check_response = requests.request("GET", request_check_URL, headers=self._auth._request_headers)
            check_response_result = request_check_response.json()["result"]
            file_ID = check_response_result.get('fileId')
            request_check_progress = request_check_response.json()["result"]["percentComplete"]
            print(f"Export is {int(request_check_progress)}% complete")
            progress_status = request_check_response.json()["result"]["status"]
            if progress_status not in ["complete", "failed"]:
                retry_count += 1
                if limit_retry and retry_count > max_retries:
                    print("Exceeded maximum retries. Exiting.")
                    sys.exit(1)
                sleep_interval = 2 ** retry_count
                print(f"Checking again in {sleep_interval} seconds")
                time.sleep(sleep_interval) 
        print("Ready to download.")
        return file_ID

    def _get_response_export_file(self, base_url, file_ID):
        """
        Download the exported responses.

        Parameters
        __________
        base_url : string
            The base url for sending the export requests.
        file_ID : string
            The file_Id value to use for requesting to download the exported response file.

        Returns
        _______
        zipfile.ZipFile
            The unzipped exported responses.
        """
        request_download_URL = base_url + file_ID + '/file'
        request_download_response = requests.request("GET", request_download_URL, headers=self._auth._request_headers, stream=True)
        return zipfile.ZipFile(io.BytesIO(request_download_response.content))
         

        