## Tibanna tutorial
* I have followed the following steps to set up Tibanna for Su Wang.

### 1. Created an account for Su Wang 'suwang' with the following IAM configuration and sent her her keys (for cli/tibanna) and password (for console access).
  * I added her to group 'step_functions' which has the following three policies.
    * AWSStepFunctionsFullAccess
    * AWSStepFunctionsConsoleFullAccess
    * AWSLambdaBasicExecutionRole-b840d4f3-6ef5-45ef-b7b7-2c12884aeb23
    ```
    {
      "Version": "2012-10-17",
      "Statement": [
        {
            "Effect": "Allow",
            "Action": "logs:CreateLogGroup",
            "Resource": "arn:aws:logs:us-east-1:643366669028:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": [
                "arn:aws:logs:us-east-1:643366669028:log-group:/aws/lambda/check-md5:*"
            ]
        }
      ]
    }
    ```

  * Additionally, I created and added a policy for accessing her S3 bucket.
    * s3-access-suwang
    ```
    {
      "Version": "2012-10-17",
      "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::suwang"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::suwang/*"
            ]
        }
      ]
    }
    ```

    * In addition, I modified the IAM-Passrole policy of the lambda as below (adding the new role)
    ```
    {
      "Version": "2012-10-17",
      "Statement": [
        {
            "Sid": "Stmt1478801396000",
            "Effect": "Allow",
            "Action": [
                "iam:PassRole"
            ],
            "Resource": [
                "arn:aws:iam::643366669028:role/S3_access",
                "arn:aws:iam::643366669028:role/s3_access_suwang"
            ]
        }
      ]
    }
    ```

### 2. Created a bucket named 'suwang' to which she is granted access.

### 3. Created a role to attach to an EC2 instance for the specific bucket access, to be fed to tibanna.
  * The role (named 's3_access_suwang') contains the policy I created above ('s3-access-suwang')

### 4. Sent her this user instruction

#### set up AWS CLI

* Install `awscli` on your computer (or your server) (https://aws.amazon.com/cli/)
* Create your credential and config files in one of the two ways below:
    * Option 1: `aws configure` and enter your access key, secret key, region('us-east-1'), output type('json'). This will automatically create the files described in Option 2.
    * Option 2: 
        * have your AWS keys in file `~/.aws/credentials` with the following content - replace the keys with the keys I sent you.
        ```
        [default]
        aws_access_key_id=<your_access_key>
        aws_secret_access_key=<your_secret_key>
        ```
        
        * Also create file `~/.aws/config` with the following content.
        ```
        [default]
        region=us-east-2
        output=json
        ```

* Upload your files to S3 by using the following
```
aws s3 cp <filename> s3://suwang/<filename>
aws s3 cp -R <dirname> s3://suwang/<dirname>
```

* log into the console (https://console.aws.amazon.com) with password as below and change the password.
    * account: 4dn-dcic
    * login: suwang
    * password: <your_password>

* You can check your bucket content on the Console by going to https://s3.console.aws.amazon.com/s3/buckets/<bucket_name>/. In this case, https://s3.console.aws.amazon.com/s3/buckets/suwang/. Alternatively, from the command line:
```
aws s3 ls s3://suwang
```


#### set up Tibanna

* clone tibanna repo and install dependencies
```
git clone https://github.com/4dn-dcic/tibanna
cd tibanna
pip install -r requirements.txt
```

* create an input json file with the following content, replace output ('output_target') and input file names and 'ebs_size'. The 'ebs_size' should be in GB and if it is set to 0, it will be auto-determined by the benchmark function. Likewise, 'instance_type' and 'EBS_optimized' can be set to be "", which allows the Benchmark function to auto-determine these parameters. One could override it by specifically assigning values to these fields (e.g. "EBS_optimized": true, "instance_type": "c2.xlarge", "ebs_size": 500). For a high IO performance, it is recommended to use "ebs_iops" to be higher (e.g. 20000), but 500 should be fine for regular jobs. More examples are in `test_json/suwang*json`. 
```
{
  "config": {
    "ebs_size": 0,
    "ami_id": "ami-cfb14bb5",
    "json_bucket": "suwang",
    "EBS_optimized": "",
    "ebs_iops": 500,
    "shutdown_min": 30,
    "instance_type": "",
    "s3_access_arn": "arn:aws:iam::643366669028:instance-profile/s3_access_suwang",
    "ebs_type": "io1",
    "copy_to_s3": true,
    "script_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/",
    "launch_instance": true,
    "password": "whateverpasswordworks",
    "log_bucket": "suwang",
    "key_name": ""
  },
  "args": {
    "secondary_output_target": {},
    "app_name": "pairsam-parse-sort",
    "input_parameters": {
      "nThreads": 16
    },
    "cwl_child_filenames": [],
    "output_target": {
      "out_pairsam": "7b932aca-62f6-4d42-841b-0d7496567103/4DNFIPJMZ922.sam.pairs.gz"
    },
    "cwl_main_filename": "pairsam-parse-sort.cwl",
    "secondary_files": {},
    "output_S3_bucket": "suwang",
    "app_version": "0.2.0",
    "cwl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/pipelines-cwl/0.2.0/cwl_awsem/",
    "input_files": {
      "bam": {
        "bucket_name": "suwang",
        "object_key": "5ae5edb2-8917-445a-b93f-46936a1478a8/4DNFI3F894Y3.bam"
      },
      "chromsize": {
        "bucket_name": "suwang",
        "object_key": "4a6d10ee-2edb-4402-a98f-0edb1d58f5e9/4DNFI823LSII.chrom.sizes"
      }
    }
  }
}
```

* run a workflow run as below
```
invoke run_workflow --workflow=run_awsem_workflow_with_unicorns --input-json=<json_file_name>
```
The link to the step function run is printed out to STDOUT and you can copy and paste it onto your browser to check the status of your run.


* checking progress
    * Once the step function passes the first step ('RunTaskAsem'), you can check the 'input' of the 'CheckTaskAwsem' which contains a field called 'jobid'. This is your job ID and you can check your S3 bucket to see if you can find a file named `<jobid>.log`. This will happen 5~10min after you start the process, because it takes time for an instance to be ready and send the log file to S3. The log file gets updated, so you can re-download this file and check the progress.
    ```
    aws s3 cp s3://suwang/<jobid>.log .
    ```
    
    * You can also ssh into your running instance. The 'instance_ip' field in the 'input' of 'CheckTaskAwsem' contains the IP.
    ```
    ssh ec2-user@<ip>
    ```
    The password is the password you entered as part of the input json (inside 'config' field, in this case, 'whateverpasswordworks')
    The purpose of the ssh is to monitor things, so refrain from doing various things there, which could interfere with the run. It is recommended, unless you're a developer, to use the log file than ssh. 
    
    * You can also check from the Console the instance that is running which has a name `awsem-<jobid>`. It will terminate itself when the run finishes. You won't have access to terminate this or any other instance, but if something is hanging for too long, please contact the admin to resolve the issue.
    
    * When the run finishes successfully, you'll see in your bucket a file `<jobid>.success`. If there was an error, you will see a file `<jobid>.error` instead. The step functions will look green on every step, if the run was successful. If one of the steps is red, it means it failed at that step.
    
    
    Success                                                |Fail
    :-----------------------------------------------------:|:--------------------------------------------------------:
    ![Success](images/stepfunction_unicorn_screenshot.png) | ![Fail](images/stepfunction_unicorn_screenshot_fail.png)
    
    
