==========================
Check Before using Tibanna
==========================


- Before using Tibanna, one must have an **AWS account** and some **S3 buckets** for storing input/output data and Tibanna logs.
- An **admin** user with access key and secret key **sets up and deploys Tibanna** for a specific user group and specific buckets.
- A **regular user**, with their own access key and secret key, associated with the user group can upload data to the bucket and **run jobs using Tibanna**.
- In addition, your *workflows* must be written in *CWL (Common Workflow Language)* which points to a docker image on *docker hub*. The CWL file must have a *public url*.

