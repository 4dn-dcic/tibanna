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

printHelpAndExit() {
    echo "Usage: ${0##*/} -i JOBID -l LOGBUCKET -V VERSION -A AWSF_IMAGE [-m SHUTDOWN_MIN] [-p PASSWORD] [-a ACCESS_KEY] [-s SECRET_KEY] [-r REGION] [-g] [-c] [-k S3_ENCRYPT_KEY_ID]"
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
    exit "$1"
}
while getopts "i:m:l:p:a:s:r:gcV:A:k:" opt; do
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
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

export EBS_DIR=/data1  ## WARNING: also hardcoded in aws_decode_run_json.py

# Locate the docker binary (docker is installed on both the Ubuntu and RHEL AMIs)
CONTAINER_CMD=$(command -v docker 2>/dev/null)
# Detect instance user and home directory (ubuntu on Debian/Ubuntu, ec2-user on RHEL)
INSTANCE_USER=$(getent passwd ubuntu 2>/dev/null | cut -d: -f1)
[ -z "$INSTANCE_USER" ] && INSTANCE_USER=$(getent passwd ec2-user 2>/dev/null | cut -d: -f1)
# Fall back to "ubuntu" if neither known user exists. Record the fallback so we can
# warn once logging is up: on such an image /home/ubuntu likely does not exist and
# later steps (e.g. chown of $EBS_DIR) will fail with a non-obvious cause.
INSTANCE_USER_FALLBACK=false
[ -z "$INSTANCE_USER" ] && { INSTANCE_USER="ubuntu"; INSTANCE_USER_FALLBACK=true; }
INSTANCE_HOME="/home/$INSTANCE_USER"
export LOCAL_OUTDIR=$EBS_DIR/out
export LOGFILE1=templog___  # log before mounting ebs
export LOGFILE2=$LOCAL_OUTDIR/$JOBID.log
export STATUS=0
export ERRFILE=$LOCAL_OUTDIR/$JOBID.error  # if this is found on s3, that means something went wrong.
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

# function that handles errors - this function calls send_error and send_log
handle_error() {  ERRCODE=$1; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 ]; then send_error; send_log; shutdown -h $SHUTDOWN_MIN; fi; }  ## usage: handle_error <error_code>

# used to compare Tibanna version strings
version() { echo "$@" | awk -F. '{ printf("%d%03d%03d%03d\n", $1,$2,$3,$4); }'; }

### start with a log under the home directory for the instance user. Later this will be moved to the output directory, once the ebs is mounted.
export LOGFILE=$LOGFILE1
cd $INSTANCE_HOME/
touch $LOGFILE


# make sure log bucket is defined
if [ -z "$LOGBUCKET" ]; then
    exl echo "Error: log bucket not defined";  # just add this message to the log file, which may help debugging by ssh
    shutdown -h $SHUTDOWN_MIN;
fi
# tibanna version and awsf image should also be defined
if [ -z "$TIBANNA_VERSION" ]; then
    exl echo "Error: tibanna lambda version is not defined";
    handle_error;
fi
if [ -z "$AWSF_IMAGE" ]; then
    exl echo "Error: awsf docker image is not defined";
    handle_error;
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
exl echo "## instance user: $INSTANCE_USER"
if [ "$INSTANCE_USER_FALLBACK" = true ]; then
  exl echo "## WARNING: could not detect a known instance user (neither 'ubuntu' nor 'ec2-user' exists); defaulting to 'ubuntu'. $INSTANCE_HOME may not exist and subsequent steps (e.g. chown of $EBS_DIR) may fail."
fi
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
  echo -ne "$PASSWORD\n$PASSWORD\n" | sudo passwd $INSTANCE_USER
  sed 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config | sed 's/#PasswordAuthentication no/PasswordAuthentication yes/g' > tmpp
  mv tmpp /etc/ssh/sshd_config
  # SSH service unit differs by distro: "ssh" on Debian/Ubuntu, "sshd" on RHEL
  if systemctl list-unit-files 2>/dev/null | grep -q '^ssh\.service'; then
    SSH_SERVICE=ssh
  else
    SSH_SERVICE=sshd
  fi
  exl service $SSH_SERVICE restart
fi


###  mount the EBS volume to the EBS_DIR (This has changed and only works with the new ubuntu 20.04 AMI)
exl echo
exl echo "## Mounting EBS"
exl lsblk $TMPLOGFILE
exl export ROOT_EBS=$(lsblk -o PKNAME | tail -n +2 | awk '$1!=""' | sort -u)
# Select the data EBS to format/mount. Tibanna attaches a single blank data EBS, but
# some instance types also expose instance-store (ephemeral) NVMe disks, so more than
# one non-root disk can be present. Pick exactly one device (a multi-line EBS_DEVICE
# would break mkfs): prefer a disk with no filesystem and no mountpoint (the freshly
# attached, unformatted data EBS), falling back to the first candidate.
CANDIDATE_DISKS=$(lsblk -o TYPE,KNAME | tail -n +2 | grep disk | grep -v "$ROOT_EBS" | awk '{print $2}')
exl echo "## Data EBS candidate disks: $(echo $CANDIDATE_DISKS | tr '\n' ' ')"
EBS_DEVICE=
for _disk in $CANDIDATE_DISKS; do
  _fstype=$(lsblk -no FSTYPE "/dev/$_disk" | grep -v '^$' | head -n 1)
  _mnt=$(lsblk -no MOUNTPOINT "/dev/$_disk" | grep -v '^$' | head -n 1)
  if [ -z "$_fstype" ] && [ -z "$_mnt" ]; then
    EBS_DEVICE=/dev/$_disk
    break
  fi
done
[ -z "$EBS_DEVICE" ] && EBS_DEVICE=/dev/$(echo "$CANDIDATE_DISKS" | head -n 1)
export EBS_DEVICE
exl mkfs -t ext4 $EBS_DEVICE # creating a file system
exl mkdir /mnt/$EBS_DIR
exl mount $EBS_DEVICE /mnt/$EBS_DIR  # mount
exl ln -s /mnt/$EBS_DIR $EBS_DIR
exl chown -R $INSTANCE_USER $EBS_DIR
exl chmod -R +x $EBS_DIR
exl echo "Mounting finished."
exl echo "Data EBS file system: $EBS_DEVICE"


### create local outdir under the mounted ebs directory and move log file into that output directory
exl mkdir -p $LOCAL_OUTDIR
mv $LOGFILE1 $LOGFILE2
export LOGFILE=$LOGFILE2

exl echo
cwd0=$(pwd)
cd ~

if [ "$DISABLE_METRICS_COLLECTION" = false ] ; then
  exl echo "## Installing and activating Cloudwatch agent to collect metrics"
  # Normalize architecture string used in CW agent download URLs (amd64 / arm64)
  _RAW_ARCH="$(uname -m)"
  case "$_RAW_ARCH" in
    x86_64)  CW_ARCH="amd64" ;;
    aarch64) CW_ARCH="arm64" ;;
    *)       CW_ARCH="$_RAW_ARCH" ;;
  esac
  if command -v dpkg &>/dev/null; then
    CW_AGENT_LINK="https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/${CW_ARCH}/latest/amazon-cloudwatch-agent.deb"
    exl echo "Loading Cloudwatch Agent from ${CW_AGENT_LINK}"
    curl -fsSL "${CW_AGENT_LINK}" -o amazon-cloudwatch-agent.deb
    dpkg -i -E ./amazon-cloudwatch-agent.deb
  else
    CW_AGENT_LINK="https://s3.amazonaws.com/amazoncloudwatch-agent/redhat/${CW_ARCH}/latest/amazon-cloudwatch-agent.rpm"
    exl echo "Loading Cloudwatch Agent from ${CW_AGENT_LINK}"
    curl -fsSL "${CW_AGENT_LINK}" -o amazon-cloudwatch-agent.rpm
    rpm -U ./amazon-cloudwatch-agent.rpm
  fi
  # If we want to collect new metrics, the following file has to be modified
  exl echo "## Using CW Agent config: https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf3/cloudwatch_agent_config.json"
  curl -fsSL https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf3/cloudwatch_agent_config.json \
    -o /opt/aws/amazon-cloudwatch-agent/bin/config.json
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
    curl https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf3/spot_failure_detection.sh -O
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

### Wait for the docker daemon to be ready before using it.
### On the RHEL AMI, Docker is started at boot by systemd and this userdata can
### race ahead of dockerd; "docker info" only succeeds once the daemon is up,
### otherwise the ECR login below fails with "Cannot connect to the Docker daemon".
### On the Ubuntu AMI Docker is already up, so this loop passes on the first try.
if [ -z "$CONTAINER_CMD" ]; then
  exl echo "Error: docker not found on this instance"
  handle_error 1
fi
exl echo
exl echo "## Waiting for container engine ($CONTAINER_CMD) to be ready"
container_tries=0
until $CONTAINER_CMD info >/dev/null 2>&1; do
  container_tries=$((container_tries+1))
  if [ $container_tries -ge 30 ]; then
    exl echo "Error: container engine ($CONTAINER_CMD) did not become ready after $container_tries attempts"
    handle_error 1
    break
  fi
  sleep 2
done
exl echo "## Container engine ready after $container_tries attempt(s)"

### Load the host kernel modules the nested (in-container) dockerd needs.
### The AWSF container starts its own dockerd to run the workflow's tool images.
### That dockerd uses iptables-legacy and overlayfs and shares the host kernel,
### but RHEL 9 doesn't load the legacy netfilter modules by default (it uses
### nftables) and 'modprobe' isn't available inside the container -- so without
### this the nested dockerd dies with "can't initialize iptables table 'nat'".
### Each module is loaded independently so one failure can't block the rest.
### Harmless on the Ubuntu AMI, where these are typically already loaded.
exl echo
exl echo "## Loading kernel modules for nested docker"
for _mod in overlay br_netfilter ip_tables iptable_nat iptable_filter iptable_mangle; do
  modprobe "$_mod" 2>/dev/null || exl echo "## note: could not load kernel module $_mod (may be built-in or unavailable)"
done

### log into ECR if necessary
exl echo
exl echo "## Logging into ECR"
exl echo "Logging into ECR $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com..."
exlo $CONTAINER_CMD login --username AWS --password $(aws ecr get-login-password --region $INSTANCE_REGION) $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com;
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
until [ $tries -ge 3 ]; do
  if exl_no_error $CONTAINER_CMD pull $AWSF_IMAGE; then
    exl echo "## Pull successfull on try $tries"
    break
  else
    ((tries++))
    sleep 60
  fi
done
send_log
# will fail here now if docker pull is not successful after multiple attempts
# pass S3_ENCRYPT_KEY_ID if desired
if [ -z "$S3_ENCRYPT_KEY_ID" ];
then
  $CONTAINER_CMD run --privileged --net host -e HOST_HOME=$INSTANCE_HOME -v $INSTANCE_HOME/:$INSTANCE_HOME/:rw -v /mnt/:/mnt/:rw $AWSF_IMAGE run.sh -i $JOBID -l $LOGBUCKET -f $EBS_DEVICE -S $STATUS $SINGULARITY_OPTION_TO_PASS
else
  $CONTAINER_CMD run --privileged --net host -e HOST_HOME=$INSTANCE_HOME -v $INSTANCE_HOME/:$INSTANCE_HOME/:rw -v /mnt/:/mnt/:rw $AWSF_IMAGE run.sh -i $JOBID -l $LOGBUCKET -f $EBS_DEVICE -S $STATUS $SINGULARITY_OPTION_TO_PASS -k $S3_ENCRYPT_KEY_ID
fi

handle_error $?

### self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
shutdown -h $SHUTDOWN_MIN
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
