#!/bin/bash
shopt -s extglob
export TIBANNA_VERSION=
export AWSF_IMAGE=
export SHUTDOWN_MIN=now
export PASSWORD=
export ACCESS_KEY=
export SECRET_KEY=
export REGION=
export SINGULARITY_OPTION_TO_PASS=
export DISABLE_METRICS_COLLECTION=false
export S3_ENCRYPT_KEY_ID=
export SCRIPT_URL=
export CW_CONFIG_SHA256=
export SPOT_SCRIPT_SHA256=
export DISABLE_SCRIPT_VERIFICATION=false

printHelpAndExit() {
    echo "Usage: ${0##*/} -i JOBID -l LOGBUCKET -V VERSION -A AWSF_IMAGE [-m SHUTDOWN_MIN] [-p PASSWORD] [-a ACCESS_KEY] [-s SECRET_KEY] [-r REGION] [-g] [-c] [-k S3_ENCRYPT_KEY_ID] [-u SCRIPT_URL] [-w CW_CONFIG_SHA256] [-z SPOT_SCRIPT_SHA256] [-x]"
    echo "-i JOBID : awsem job id (required)"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-V TIBANNA_VERSION : tibanna version (used in the run_task lambda that launched this instance)"
    echo "-A AWSF_IMAGE : docker image name for awsf3 (e.g. 4dn-dcic/tibanna-awsf3:1.0.0)"
    echo "-m SHUTDOWN_MIN : Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging. (default 'now')"
    echo "-p PASSWORD : Password for ssh connection for user ec2-user (if not set, no password-based ssh)"
    echo "-a ACCESS_KEY : access key for certain s3 bucket access (if not set, use IAM permission only)"
    echo "-s SECRET_KEY : secret key for certian s3 bucket access (if not set, use IAM permission only)"
    echo "-r REGION : region for the profile set for certain s3 bucket access (if not set, use IAM permission only)"
    echo "-g : use singularity"
    echo "-c : Metrics collection is disabled if flag is set"
    echo "-k S3_ENCRYPT_KEY_ID : KMS key to encrypt s3 files with"
    echo "-u SCRIPT_URL : base URL this script was fetched from, reused to fetch the cloudwatch agent config and spot failure detection script from the same pinned location"
    echo "-w CW_CONFIG_SHA256 : expected sha256 of cloudwatch_agent_config.json; the download is rejected on mismatch"
    echo "-z SPOT_SCRIPT_SHA256 : expected sha256 of spot_failure_detection.sh; the download is rejected on mismatch"
    echo "-x : (development only) disable sha256 verification of downloaded monitoring assets"
    exit "$1"
}
while getopts "i:m:l:p:a:s:r:gcV:A:k:u:w:z:x" opt; do
    case $opt in
        i) export JOBID=$OPTARG;;
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        V) export TIBANNA_VERSION=$OPTARG;;  # version of tibanna used in the run_task lambda that launched this instance
        A) export AWSF_IMAGE=$OPTARG;;  # docker image name for awsf3 (e.g. 4dn-dcic/tibanna-awsf3:1.0.0)
        m) export SHUTDOWN_MIN=$OPTARG;;  # Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging.
        p) export PASSWORD=$OPTARG ;;  # Password for ssh connection for user ec2-user
        a) export ACCESS_KEY=$OPTARG;;  # access key for certain s3 bucket access
        s) export SECRET_KEY=$OPTARG;;  # secret key for certian s3 bucket access
        r) export REGION=$OPTARG;;  # region for the profile set for certian s3 bucket access
        g) export SINGULARITY_OPTION_TO_PASS=-g;;  # use singularity
        c) export DISABLE_METRICS_COLLECTION=true;;  # disable metrics collection
        k) export S3_ENCRYPT_KEY_ID=$OPTARG;;  # KMS key ID to encrypt s3 files with
        u) export SCRIPT_URL=$OPTARG;;  # base URL to fetch pinned monitoring assets from
        w) export CW_CONFIG_SHA256=$OPTARG;;  # expected sha256 of cloudwatch_agent_config.json
        z) export SPOT_SCRIPT_SHA256=$OPTARG;;  # expected sha256 of spot_failure_detection.sh
        x) export DISABLE_SCRIPT_VERIFICATION=true;;  # development-only override, see printHelpAndExit
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

export EBS_DIR=/data1  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_OUTDIR=$EBS_DIR/out
export LOGFILE1=templog___  # log before mounting ebs
export LOGFILE2=$LOCAL_OUTDIR/$JOBID.log
export STATUS=0
# ERRFILE1 lives under the home directory, which exists from boot, so a
# pre-mount failure can still persist a durable error marker. ERRFILE2 (under
# the data EBS) is switched to once that volume is mounted, mirroring LOGFILE.
export ERRFILE1=/home/ubuntu/$JOBID.error
export ERRFILE2=$LOCAL_OUTDIR/$JOBID.error  # if this is found on s3, that means something went wrong.
export ERRFILE=$ERRFILE1
#IMDSv2 Addition
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AZ=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/availability-zone)
export INSTANCE_REGION=${AZ::-1}
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity| grep Account | sed 's/[^0-9]//g')


# function that executes a command and collecting log
exl(){ $@ >> $LOGFILE 2>> $LOGFILE; handle_error $?; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3.
exlo(){ $@ 2>> /dev/null >> $LOGFILE; handle_error $?; } ## usage: exlo command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3. This one eats stderr. Useful for hiding long errors or credentials.
exl_no_error(){ $@ >> $LOGFILE 2>> $LOGFILE; } ## same as exl but will not exit on error

# function that sends log to s3 (it requires LOGBUCKET to be defined, which is done by sourcing $ENV_FILE.)
## usage: send_log (no argument)
send_log() {
  if [ -z "$S3_ENCRYPT_KEY_ID" ];
  then
    aws s3 cp $LOGFILE s3://$LOGBUCKET &>/dev/null;
  else
    aws s3 cp $LOGFILE s3://$LOGBUCKET --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID" &>/dev/null;
  fi
}

# function that sends error file to s3 to notify something went wrong.
## usage: send_error (no argument)
send_error(){
  touch $ERRFILE;
  if [ -z "$S3_ENCRYPT_KEY_ID" ];
  then
    aws s3 cp $ERRFILE s3://$LOGBUCKET;
  else
    aws s3 cp $ERRFILE s3://$LOGBUCKET --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID";
  fi
}

# function that sends job_started file to s3, notifying that the job successfully started
## usage: send_job_started (no argument)
send_job_started() {
  touch $JOBID.job_started;
  if [ -z "$S3_ENCRYPT_KEY_ID" ];
  then
    aws s3 cp $JOBID.job_started s3://$LOGBUCKET/$JOBID.job_started
  else
    aws s3 cp $JOBID.job_started s3://$LOGBUCKET/$JOBID.job_started --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID";
  fi
}

# function that handles errors - this function calls send_error and send_log,
# then fails closed: it exits immediately so a fatal error never falls through
# into mounting/formatting disks, pulling/running Docker, or running the
# workload. Best-effort logging failures (send_error/send_log/shutdown) do not
# mask the original error code, since exit is always the last statement.
## usage: handle_error <error_code>  (a missing/empty code is treated as an error, not silently skipped)
handle_error() {
  ERRCODE=${1:-1}
  STATUS+=,$ERRCODE
  if [ "$ERRCODE" -ne 0 ]; then
    send_error
    send_log
    shutdown -h $SHUTDOWN_MIN
    exit "$ERRCODE"
  fi
}

# function that verifies a downloaded file's sha256 against an expected value
# and fails closed (via handle_error) on mismatch or a missing expected value.
# DISABLE_SCRIPT_VERIFICATION is a development-only escape hatch (e.g. for a
# custom TIBANNA_REPO_BRANCH fork where the expected hash is not known ahead
# of time) and must never be the default in a real deployment.
## usage: verify_sha256 <file> <expected_sha256>
verify_sha256() {
  local file="$1"
  local expected="$2"
  if [ "$DISABLE_SCRIPT_VERIFICATION" = true ]; then
    exl echo "## WARNING: sha256 verification disabled (development override) for $file"
    return 0
  fi
  if [ -z "$expected" ]; then
    exl echo "Error: no expected sha256 provided for $file - refusing to use it"
    handle_error 1
    return 1
  fi
  local actual
  actual=$(sha256sum "$file" | awk '{print $1}')
  if [ "$actual" != "$expected" ]; then
    exl echo "Error: sha256 mismatch for $file (expected $expected, got $actual)"
    handle_error 1
    return 1
  fi
  return 0
}

# used to compare Tibanna version strings
version() { echo "$@" | awk -F. '{ printf("%d%03d%03d%03d\n", $1,$2,$3,$4); }'; }

### start with a log under the home directory for ubuntu. Later this will be moved to the output directory, once the ebs is mounted.
export LOGFILE=$LOGFILE1
cd /home/ubuntu/
touch $LOGFILE


# make sure log bucket is defined
if [ -z "$LOGBUCKET" ]; then
    exl echo "Error: log bucket not defined";  # just add this message to the log file, which may help debugging by ssh
    # LOGBUCKET is unset, so send_error/send_log cannot upload anywhere; still
    # fail closed instead of continuing into mount/Docker/workload setup.
    shutdown -h $SHUTDOWN_MIN;
    exit 1
fi
# tibanna version and awsf image should also be defined
if [ -z "$TIBANNA_VERSION" ]; then
    exl echo "Error: tibanna lambda version is not defined";
    handle_error 1;
fi
if [ -z "$AWSF_IMAGE" ]; then
    exl echo "Error: awsf docker image is not defined";
    handle_error 1;
fi


### send job start message to S3
send_job_started;

### start logging
### env
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id)

INSTANCE_TYPE=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-type)

AMI_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/ami-id)

AVAILABILITY_ZONE=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/availability-zone)

# For security groups, this returns a newline-separated list
SECURITY_GROUPS_RAW=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/security-groups)
SECURITY_GROUPS=$(echo "$SECURITY_GROUPS_RAW" | paste -sd "," -)

exl echo "## Tibanna version: $TIBANNA_VERSION"
exl echo "## job id: $JOBID"
exl echo "## instance type: $INSTANCE_TYPE"
exl echo "## instance id: $INSTANCE_ID"
exl echo "## instance region: $INSTANCE_REGION"
exl echo "## tibanna lambda version: $TIBANNA_VERSION"
exl echo "## awsf image: $AWSF_IMAGE"
exl echo "## ami id: $AMI_ID"
exl echo "## availability zone: $AVAILABILITY_ZONE"
exl echo "## security groups: $SECURITY_GROUPS"
exl echo "## log bucket: $LOGBUCKET"
exl echo "## shutdown min: $SHUTDOWN_MIN"
exl echo "## kms_key_id: $S3_ENCRYPT_KEY_ID"
exl echo
exl echo "## Starting..."
exl date


### sshd configure for password recognition
exl echo
exl echo "## Configuring and starting ssh"
if [ ! -z $PASSWORD ]; then
  echo -ne "$PASSWORD\n$PASSWORD\n" | sudo passwd ubuntu
  sed 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config | sed 's/#PasswordAuthentication no/PasswordAuthentication yes/g' > tmpp
  mv tmpp /etc/ssh/sshd_config
  exl service ssh restart
fi


###  mount the EBS volume to the EBS_DIR (This has changed and only works with the new ubuntu 20.04 AMI)
exl echo
exl echo "## Mounting EBS"
exl lsblk $TMPLOGFILE
exl export ROOT_EBS=$(lsblk -o PKNAME | tail +2 | awk '$1!=""')
exl export EBS_DEVICE=/dev/$(lsblk -o TYPE,KNAME | tail +2 | grep disk | grep -v $ROOT_EBS | cut -f2 -d' ')
exl mkfs -t ext4 $EBS_DEVICE # creating a file system
exl mkdir /mnt/$EBS_DIR
exl mount $EBS_DEVICE /mnt/$EBS_DIR  # mount
exl ln -s /mnt/$EBS_DIR $EBS_DIR
exl chown -R ubuntu $EBS_DIR
exl chmod -R +x $EBS_DIR
exl echo "Mounting finished."
exl echo "Data EBS file system: $EBS_DEVICE"


### create local outdir under the mounted ebs directory and move log file into that output directory
exl mkdir -p $LOCAL_OUTDIR
mv $LOGFILE1 $LOGFILE2
export LOGFILE=$LOGFILE2
export ERRFILE=$ERRFILE2

exl echo
cwd0=$(pwd)
cd ~

if [ "$DISABLE_METRICS_COLLECTION" = false ] ; then
  exl echo "## Installing and activating Cloudwatch agent to collect metrics"
  ARCHITECTURE="$(dpkg --print-architecture)"
  CW_AGENT_LINK="https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/${ARCHITECTURE}/latest/amazon-cloudwatch-agent.deb"
  apt install -y wget
  exl echo "Loading Cloudwatch Agent from ${CW_AGENT_LINK}"
  wget "${CW_AGENT_LINK}"
  sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
  # If we want to collect new metrics, the following file has to be modified.
  # Fetched from the same pinned SCRIPT_URL this script itself was fetched
  # from (not a hardcoded /master/ URL) and verified against CW_CONFIG_SHA256
  # before use (D1) - fails closed on mismatch/unavailability.
  exl echo "## Using CW Agent config: ${SCRIPT_URL}cloudwatch_agent_config.json"
  wget "${SCRIPT_URL}cloudwatch_agent_config.json"
  verify_sha256 ./cloudwatch_agent_config.json "$CW_CONFIG_SHA256"
  mv ./cloudwatch_agent_config.json /opt/aws/amazon-cloudwatch-agent/bin/config.json
  # This starts the agent with the downloaded configuration file
  sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/bin/config.json
else
  exl echo "## Metrics collection is disabled"
fi



# Set up cronjob to monitor AWS spot instance termination notice.
# Works only in deployed Tibanna version >=1.6.0 since the ec2 needed more permissions to call `aws ec2 describe-spot-instance-requests`
# Since cron only has a resolution of 1 min, we set up 2 jobs and let one sleep for 30s, to get a resolution of 30s.
if [ $(version $TIBANNA_VERSION) -ge $(version "1.6.0") ]; then
  # Get IMDSv2 token and instance ID
  TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
  INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/instance-id)
  is_spot_instance=$(aws ec2 describe-spot-instance-requests \
    --filters Name=instance-id,Values="$INSTANCE_ID" \
    --region "$INSTANCE_REGION" \
    | python3 -c "import sys, json; print(len(json.load(sys.stdin)['SpotInstanceRequests']))")
  if [ "$is_spot_instance" = "1" ]; then
    exl echo
    exl echo "## Turning on Spot instance failure detection"
    cd ~
    # Fetched from the same pinned SCRIPT_URL and verified against
    # SPOT_SCRIPT_SHA256 before being made executable (D1).
    curl "${SCRIPT_URL}spot_failure_detection.sh" -O
    verify_sha256 ./spot_failure_detection.sh "$SPOT_SCRIPT_SHA256"
    chmod +x spot_failure_detection.sh
    if [ -z "$S3_ENCRYPT_KEY_ID" ];
    then
      echo "* * * * * ~/spot_failure_detection.sh -s 0 -l $LOGBUCKET -j $JOBID  >> /var/log/spot_failure_detection.log 2>&1" >> ~/recurring.jobs
      echo "* * * * * ~/spot_failure_detection.sh -s 30 -l $LOGBUCKET -j $JOBID  >> /var/log/spot_failure_detection.log 2>&1" >> ~/recurring.jobs
    else
      echo "* * * * * ~/spot_failure_detection.sh -s 0 -l $LOGBUCKET -j $JOBID -k $S3_ENCRYPT_KEY_ID  >> /var/log/spot_failure_detection.log 2>&1" >> ~/recurring.jobs
      echo "* * * * * ~/spot_failure_detection.sh -s 30 -l $LOGBUCKET -j $JOBID -k $S3_ENCRYPT_KEY_ID  >> /var/log/spot_failure_detection.log 2>&1" >> ~/recurring.jobs
    fi
  fi
fi

# Send the collected jobs to cron
cat ~/recurring.jobs | crontab -

cd $cwd0

# set additional profile
if [ -z $REGION ]; then
  export REGION=$INSTANCE_REGION
fi
if [ ! -z $ACCESS_KEY -a ! -z $SECRET_KEY -a ! -z $REGION ]; then
  echo -ne "$ACCESS_KEY\n$SECRET_KEY\n$REGION\njson" | aws configure --profile user1
fi

### log into ECR if necessary
exl echo
exl echo "## Logging into ECR"
exl echo "Logging into ECR $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com..."
exlo docker login --username AWS --password $(aws ecr get-login-password --region $INSTANCE_REGION) $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com;
send_log

# send log before starting docker
exl echo
exl echo "## Running dockerized awsf scripts"
send_log

# run dockerized awsf scripts
# wrap docker pull in some retry logic in case of
# network failures (seen frequently) - Will Sept 22 2021
exl echo "## Pulling Docker image"
tries=0
pull_success=false
until [ $tries -ge 3 ]; do
  if exl_no_error docker pull $AWSF_IMAGE; then
    exl echo "## Pull successfull on try $tries"
    pull_success=true
    break
  else
    ((tries++))
    sleep 60
  fi
done
send_log
# fail closed here if docker pull did not succeed after multiple attempts,
# instead of silently falling through into `docker run` with a missing image
if [ "$pull_success" != true ]; then
  exl echo "Error: failed to pull docker image $AWSF_IMAGE after $tries tries"
  handle_error 1
fi
# pass S3_ENCRYPT_KEY_ID if desired
if [ -z "$S3_ENCRYPT_KEY_ID" ];
then
  docker run --privileged --net host -v /home/ubuntu/:/home/ubuntu/:rw -v /mnt/:/mnt/:rw $AWSF_IMAGE run.sh -i $JOBID -l $LOGBUCKET -f $EBS_DEVICE -S $STATUS $SINGULARITY_OPTION_TO_PASS
else
  docker run --privileged --net host -v /home/ubuntu/:/home/ubuntu/:rw -v /mnt/:/mnt/:rw $AWSF_IMAGE run.sh -i $JOBID -l $LOGBUCKET -f $EBS_DEVICE -S $STATUS $SINGULARITY_OPTION_TO_PASS -k $S3_ENCRYPT_KEY_ID
fi

handle_error $?

### self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
shutdown -h $SHUTDOWN_MIN
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
