from core import ec2_utils

# TODO: generate a user-data script
run_instance_cmd = ('ec2 run-instances --image-id ami-7ff26968 --instance-type t2.nano '
                    '--instance-initiated-shutdown-behavior terminate --count 1 --enable-api-termination '
                    '--iam-instance-profile Arn=arn:aws:iam::643366669028:instance-profile/S3_access '
                    '--user-data=file:///tmp/userdata/run_workflow.15WPQwPmfMQL.sh --block-device-mappings '
                    'DeviceName=/dev/sdb,Ebs={VolumeSize=20,VolumeType=io1,Iops=500,DeleteOnTermination=true}')


def test_launch_and_get_instance_id():
    res = ec2_utils.launch_and_get_instance_id(run_instance_cmd, 'test1234')
    print(res)
