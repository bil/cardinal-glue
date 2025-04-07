# Cardinal Glue
## Background
Stanford affiliates have access to a wide variety of tools that facilitate data and metadata curation, identity and access management, data sharing, and more. Unfortunately, these tools do not natively communicate with each other, and linking them together manually is cumbersome. ```cardinal_glue``` seeks to simplify authentication with these services and provide conventient data transfer between these services at multiple levels.

## Current 'glued' services
Qualtrics  
Stanford Workgroups  
Stanford Profile (CAP)  

## Additional functionality
Google authentication flows  
```fsspec``` integration (```gdrivefs``` and ```gcsfs```)  

## Planned future integrations
Canvas  
support for local filesystem management with ```fsspec```
```s3fs```

## Environment variables modified for Google auth
- CLOUDSDK_CONFIG = Used by the Google Cloud CLI for authentication purposes. points to the cardinal_glue directory  
- USE_AUTH_EPHEM = Modifies which authentication flow is used by Google Colab. when set to 0 (as is done in this package), it tells Google to look for credentials in the path specified by the environment variable 'GOOGLE_APPLICATION_CREDENTIALS'  
- GOOGLE_APPLICATION_CREDENTIALS = A path pointing to the cardinal_glue directory . The location of the cardinal_glue directory is set programmatically depending on the IDE being used, but it can be modified by the user.

