==========================
Check Before using Tibanna
==========================


- Before using Tibanna, one must have an **AWS account**.
- An **admin** user with access key and secret key **sets up and deploys Tibanna** for a specific user group and specific buckets.
- A **regular user**, with their own access key and secret key, associated with the user group can upload data to the bucket and **run jobs using Tibanna**.
- In addition, your *workflows* must be written in either *CWL (Common Workflow Language)* or *WDL (Workflow Description Language)* which point to a docker image on *docker hub*. The CWL/WDL files must have a *public url*.

