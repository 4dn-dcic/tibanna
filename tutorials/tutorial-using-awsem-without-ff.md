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
  * [../README.md#how_to_use_awsem]

