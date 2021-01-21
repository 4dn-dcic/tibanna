==========================
Check Before using Tibanna
==========================


- Before using Tibanna, one must have an **AWS account**.
- An **admin** user with access key and secret key **sets up and deploys Tibanna** for a specific user group and specific buckets.
- A **regular user**, with their own access key and secret key, associated with the user group can upload data to the bucket and **run jobs using Tibanna**.
- In addition, your *workflows* must be written in either *CWL (Common Workflow Language)* or *WDL (Workflow Description Language)* which point to a docker image on *docker hub* or AWS ECR (Elastic Container Registry) on the same AWS account. Alternatively, you can use *Snakemake* workflow to be run as a whole on a single EC2 machine, inside a Snakemake docker image. The CWL/WDL/Snakemake files must have a *public url* unless they are local files. 

