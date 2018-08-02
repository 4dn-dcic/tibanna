====================
Before using Tibanna
====================


Before using Tibanna, one must have an **AWS account** and some **S3 buckets** for storing input/output data and Tibanna logs.
An **admin** user with access key and secret key **sets up and deploys Tibanna** for a specific user group and specific buckets.
A **regular user**, with their own access key and secret key, associated with the user group can upload data to the bucket and **run jobs using Tibanna**.


Setting up awscli
-----------------

To use Tibanna, one needs a user account on AWS and ``awscli`` configured on the local machine on which Tibanna is installed.

First, install ``awscli`` on your computer (or your server) (https://aws.amazon.com/cli/)

Then, create your credential and config files in one of the two ways below:

**Option 1:**

``aws configure`` and enter your access key, secret key, region('us-east-1'), output type('json'). This will automatically create the files described in Option 2.


**Option 2:**

have your AWS keys in file ``~/.aws/credentials`` with the following content.

::

    [default]
    aws_access_key_id=<your_access_key>
    aws_secret_access_key=<your_secret_key>
    

Also create file ``~/.aws/config`` with the following content.

::

    [default]
    region=us-east-2
    output=json


Uploading files to bucket
-------------------------

If you are an admin or have a permission to create a bucket, you can either use the Console or use the following command using `awscli`. For example, a data (input/output) bucket and a tibanna log bucket may be created. You could also separate input and output buckets, or have multiple input buckets, etc. Bucket names are globally unique.

::

    aws s3api create-bucket --bucket <bucketname>


**Example**

::

    aws s3api create-bucket --bucket suwangs_data_bucket
    aws s3api create-bucket --bucket suwangs_tibanna_log_bucket



Upload your files to the data bucket by using the following

::

    aws s3 cp <filename> s3://<bucketname>/<filename>
    aws s3 cp -R <dirname> s3://<bucketname>/<dirname>


**Example**

::

    aws s3 cp somebamfile.bam s3://suwangs_data_bucket/somebamfile.bam
    aws s3 cp -R suwangs_input_data_folder s3://suwangs_data_bucket/suwangs_input_data_folder


