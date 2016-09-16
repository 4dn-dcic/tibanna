from __future__ import print_function
import boto3
import paramiko

S3_BUCKET = 'daily-auction-report'
EC2_ID = 'i-add5a232'

def start_ec2(ec2, ec2_id):
    instance = ec2.Instance(id=ec2_id)
    print("starting instance " + ec2_id)
    instance.start()
    instance.wait_until_running()
    print("instance started")
    return instance

def stop_ec2(ec2, ec2_id):
    print("stopping instance " + ec2_id)
    instance = ec2.Instance(id=ec2_id).stop()
    print("instance stopped")

def get_ssh_key_from_s3():
    s3_client = boto3.client('s3')
    tmp_key_name = '/tmp/%s.pem' % (S3_BUCKET)
    s3_client.download_file(S3_BUCKET, S3_BUCKET + ".pem", tmp_key_name)
    key = paramiko.RSAKey.from_private_key_file(tmp_key_name)
    return key


def generate_report_on_server(ip):
    key = get_ssh_key_from_s3()
    conn = paramiko.SSHClient()
    conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print("connecting to " + ip)
    conn.connect( hostname = ip, username = 'ubuntu', pkey = key)
    print("conneccted to " + ip)

    commands = ["cd /home/ubuntu/daily-auction-report/ && git pull",
                "rm -rf /home/ubuntu/daily-auction-report/output",
                "mkdir /home/ubuntu/daily-auction-report/output",
                "python /home/ubuntu/daily-auction-report/py2/make_reports.py",
               ]
    for command in commands:
        print("Running %s" % (command))
        stdin, stdout, stderr = conn.exec_command(command)
        print(stdout.read())
        print(stderr.read())


def lambda_handler(event, context):
    ec2 = boto3.resource('ec2', region_name="ap-northeast-1")
    print('connecting to AWS ec2 resource')
    try:
        instance = start_ec2(ec2, EC2_ID)
        generate_report_on_server(instance.public_ip_address)
        stop_ec2(ec2, EC2_ID)
    except:
        print('something went wrong')
        raise

    return  "All good"
