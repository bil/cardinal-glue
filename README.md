# Overview
```cardinal_glue``` is an integrative python package that provides easy authentication with Google and Qualtrics, as well as Stanford-specific services. This is coupled with straightforward, pythonic file-management capabilties for Google Drive and Google Cloud Storage. Additional functionality allows for effective UID management within the Stanford computing ecosystem.

# 'Glued' services
- Qualtrics API
- Stanford Workgroup API
- Stanford CAP API

# Additional functionality
- Easy Google authentication flows
- File management through ```gdrivefs``` and ```gcsfs```

# Planned functionality
- Integration with the Canvas API
- File management through ```s3fs``` and ```sshfs```

# Environment variables modified for Google auth
- CLOUDSDK_CONFIG = Used by the Google Cloud CLI for authentication purposes. Set to the cardinal_glue directory by default.
- USE_AUTH_EPHEM = Modifies which authentication flow is used by Google Colab. When set to 0 (as is done in this package), it tells Google to look for credentials in the path specified by the environment variable 'GOOGLE_APPLICATION_CREDENTIALS'.
- GOOGLE_APPLICATION_CREDENTIALS = A path pointing to the cardinal_glue directory by default.

The location of the cardinal_glue directory is set programmatically depending on the IDE being used, but it can be modified by the user.

