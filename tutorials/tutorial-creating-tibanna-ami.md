
## Creating AMI for Tibanna
A Tibanna AWSEM AMI can be created automatically using `AMI/create_tibanna_ami.py`.


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
* The return value from a create-image operation is printed as after the run completes. The output contains AMI ID that you can use in the 'config' field of Tibanna input json.
* Alternatively, check the AWS Console the following two.
    1. An ec2 instance named 'tibanna-ami' must have been launched and you should be able to see it from the EC2 Console.
      ![](../images/tibanna_ami_instance_scsh.png)
    2. After 10min or so, an AMI named your `ami_name` must have been created and you should be able to see it from the AMI Console.
      ![](../images/tibanna_ami_image_scsh.png)


