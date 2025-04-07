# Environment variables modified for Google auth
- CLOUDSDK_CONFIG = used by the Google Cloud CLI for authentication purposes. points to the cardinal_glue directory
- USE_AUTH_EPHEM = modifies which authentication flow is used by Google Colab. when set to 0 (as is done in this package), it tells Google to look for credentials in the path specified by the environment variable 'GOOGLE_APPLICATION_CREDENTIALS'
- GOOGLE_APPLICATION_CREDENTIALS = a path pointing to the cardinal_glue directory

The location of the cardinal_glue directory is set programmatically depending on the IDE being used, but it can be modified by the user.

