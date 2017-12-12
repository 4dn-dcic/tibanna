
## Creating AMI for Tibanna
A Tibanna AWSEM AMI can be created automatically using `AMI/create_tibanna_ami.py`.
You need to have an AWS account and a permission (access_key and secret_key) in order to do this operation. It involves launching an instance, creating an image out of an instance and terminating an instance.

### Usage:
```
python AMI/create_tibanna_ami.py -k <key_name> -a <ami_name>
```
* key_name: Use a key that you have (.pem file)
* ami_name: Choose any AMI name you'd like to serve as Tibanna AWSEM AMI.

### Example usage:
```
python AMI/create_tibanna_ami.py -k duplexa.4dn -a docker_cwlrunner3
```
* The return jsons from the create-image and terminate-instance operations are printed to stdout after the run completes. The output contains AMI ID that you can use in the 'config' field of Tibanna input json.
```
waiting for 10min for the instance to install everything and reboot..
creating an image...
{'ResponseMetadata': {'RetryAttempts': 0, 'HTTPStatusCode': 200, 'RequestId': '3fa65b89-6300-42c3-9d1b-f0632c683402', 'HTTPHeaders': {'transfer-encoding': 'chunked', 'vary': 'Accept-Encoding', 'server': 'AmazonEC2', 'content-type': 'text/xml;charset=UTF-8', 'date': 'Tue, 03 Oct 2017 17:23:17 GMT'}}, u'ImageId': 'ami-5c4eb526'}
waiting for 10min for the image to be created..
{u'TerminatingInstances': [{u'InstanceId': 'i-0ed0ef67846a6f7f3', u'CurrentState': {u'Code': 32, u'Name': 'shutting-down'}, u'PreviousState': {u'Code': 16, u'Name': 'running'}}], 'ResponseMetadata': {'RetryAttempts': 0, 'HTTPStatusCode': 200, 'RequestId': '59dd5c26-b4ce-4111-abbe-e80e25dd7271', 'HTTPHeaders': {'transfer-encoding': 'chunked', 'vary': 'Accept-Encoding', 'server': 'AmazonEC2', 'content-type': 'text/xml;charset=UTF-8', 'date': 'Tue, 03 Oct 2017 17:33:18 GMT'}}}
```
* Alternatively, check the AWS Console the following two.
    1. An ec2 instance named 'tibanna-ami' must have been launched and you should be able to see it from the EC2 Console. It uses a t2.micro instance.
      * ![](../images/tibanna_ami_instance_scsh.png)
    2. After 10min or so, an AMI named your `ami_name` must have been created and you should be able to see it from the AMI Console.
      * ![](../images/tibanna_ami_image_scsh.png)


### Update json files inside tibanna repo
* Once you have a new AMI, the following command would automatically update all json files and notebooks so they use the new AMI.
```
upgrade_ami_for_all_tibanna_jsons.sh <old_ami_id> <new_ami_id>
```
