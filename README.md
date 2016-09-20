# Tibanna
Tibanna is the gas mine in Cloud City that makes Hyperdrives zoom.  It's also the pipeline running in the cloud that ensure data is properly processed for 4dn.


# Goal
The goal is to construct a version zero framework for executing a cwl pipeline directly on aws without using SBG (nor DNA nexus), that can be used as an independent module.
 
# Summary diagram
The module works as a diagram below:
First, create a JOBID, a run.json file, a tiny shell script (run_workflow.sh) file and upload the run.json file to S3. (This part has yet to be implemented, currently I manually created the JOBID, run.json file and the shell script.)
Then, launch a self-executing EC2 instance with a JOB ID and run_workflow.sh passed to it.
The self-executing EC2 instance will download necessary scripts and workflow codes from github and run.json, data from S3 and run the workflow and upload the output and status to S3 and then terminate itself.
The log files will be sent to S3 intermittently but not in real time.

--diagram--

# Launching a self-executing EC2 instance
From anywhere you have aws configured with the right credentials and region, you can run the following command to launch an instance of the desired type. (For more details, see Test12. The content of ths page is an upgraded version of Test12.) 
Basically, this command launches an instance based on a CWL-Docker-toil AMI (AMI with docker daemon and cwl-runner and toil installed based on Amazon Linux AMI), with shut-down-behavior 'terminate' and read/write access to S3 and has run_workflow.sh as user-data. Those are critical requirements. Most likely an additional EBS volume must be attached (in the below example to 100GB, io1 type with 5000 IOPS) because the default 8GB is not sufficient for most data. The exact volume size can be determined based on the data size and the workflow (e.g. which determines intermediate and output file sizes). The instance type is set to i2.xlarge in the case below, but it could also be flexible depending on the data size.

Given a config file (./.tibanna.connfig), the following command would do everything from creating a json file, copying it to S3, launching an instance and executing a workflow.
```
python create_json.py -c hictool-bam2hdf5.cwl -a hictool-bam2hdf5 -i '{"input_bam1":"GM12878_SRR1658581_pair1.bam","input_bam2":"GM12878_SRR1658581_pair2.bam"}' -id 4dn-tool-evaluation-files -ir '{"bowtie_index":"hg19.bowtieIndex.tgz","chrlen_file":"hg19.chrlen_file","RE_bed":"HindIII_hg19_liftover.bed"}' -ip '{"contact_matrix_binsize":50000,"chromosome":["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","X"]}' -o 4dn-tool-evaluation-files/output/20160918.v989328isyrbag02 -J v989328isyrbag02 -ue

```
This command would also add an entry to a job_list file (./.job_list) describing the job ID, instance ID, instance IP and the app name.


To check status, use awstat:
```
./awstat
C24WkGoVKfg9    i-5dcba74b      c4.large        54.172.226.225  gatk-gvcf       2016-09-20T03:18:00.000Z        terminated
LQEfk3yazaa5    i-75145b44      c4.xlarge       54.162.54.77    gatk-gvcf       2016-09-20T03:18:17.000Z        terminated
JBxTdOKKDMnt    i-dbc3afcd      i2.xlarge       52.91.238.116   hictool-bam2hdf5        2016-09-20T03:34:05.000Z        running

```
The columns are jobID, instanceID, instance_type, public_IP, tag (app_name), launch time and status.
It has launch time directly taken from the instance report, but keep in mind that AWS has many issues with time zones. 


A less automated way would be as follows. This will not add an entry to a job_list file.

```
INSTANCE_TYPE=i2.xlarge
EBS_SIZE=100  ## in GB
EBS_TYPE=io1
EBS_IOPS=5000
AMI_ID=ami-7ff26968
KEYPAIR=duplexa.4dn
JSON_BUCKET=4dn-aws-pipeline-run-json
USERDATA_DIR=./userdata

# 1. A json file specifying workflow, inputs and other details must be created and sent to S3.
# The json-generating script is create_json.py and it assumes python 2.7 or higher.
# JOBID can be manually assigned (-j) or randomly generated.
# The following command generates a json file ./json/v989328isyrbag02.run.json (and stores the job ID to env variable JOBID) is actually runnable (given the files and buckets exist).
# JOBID is in this case manually assigned to be v989328isyrbag02.
JOBID=`python ./create_json.py -c hictool-bam2hdf5.cwl -cd https://raw.githubusercontent.com/SooLee/gitar.workflow/master/cwl.20160712.draft3/ -i '{"input_bam1":"GM12878_SRR1658581_pair1.bam","input_bam2":"GM12878_SRR1658581_pair2.bam"}' -id 4dn-tool-evaluation-files -ir '{"bowtie_index":"hg19.bowtieIndex.tgz","chrlen_file":"hg19.chrlen_file","RE_bed":"HindIII_hg19_liftover.bed"}' -ird 4dn-tool-evaluation-files -ip '{"contact_matrix_binsize":50000,"chromosome":["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","X"]}' -o 4dn-tool-evaluation-files/output/20160918.v989328isyrbag02 -s $EBS_SIZE -IO $EBS_IOPS -t $INSTANCE_TYPE -J v989328isyrbag02`

# 2. Copy the json file to a designated bucket so it can be accssed by the worker instance
aws s3 cp ./json/$JOBID.run.json s3://$JSON_BUCKET/$JOBID.run.json

# 3. Create a userdata script to pass to the instance. The userdata script is run_workflow.$JOBID.sh.
./create_run_workflow.sh $JOBID $USERDATA_DIR

# 4. The following command launches a self-terminating instance that executes the workflow (assuming the json file is already on S3)
aws ec2 run-instances --image-id $AMI_ID --instance-type $INSTANCE_TYPE --instance-initiated-shutdown-behavior terminate --count 1 --monitoring Enabled=true --enable-api-termination --block-device-mappings DeviceName=/dev/sdb,Ebs="{VolumeSize=$EBS_SIZE,VolumeType=$EBS_TYPE,Iops=$EBS_IOPS,DeleteOnTermination=true}" --iam-instance-profile Arn=arn:aws:iam::643366669028:instance-profile/S3_access --ebs-optimized --user-data file://run_workflow.$JOBID.sh --key-name $KEYPAIR >> launch.$JOBID.log
#The same kind of command can be executed to launch an instance in other ways (e.g. using python, with different security handling, etc, but the requirements stated above must be kept.)
#Once you call the EC2 instance, the rest is completely independent of how you called it.
```

For example, ``run_workflow.v989328isyrbag02.sh`` looks as below:
```
#!/bin/bash
JOBID=v989328isyrbag02  
RUN_SCRIPT=aws_run_workflow.sh
SCRIPT_URL=https://raw.githubusercontent.com/hms-dbmi/tibanna/master/
wget SCRIPT_URL/$RUN_SCRIPT
chmod +x $RUN_SCRIPT
source $RUN_SCRIPT $JOBID
```
The second line should depend on the JOBID and this script should be generated on the fly by create_run_workflow.sh, after a JOBID is assigned. This script will be passed to EC2 and executed at the beginning. It will first download aws_run_workflow.sh from github and run it with the specified JOBID. The rest will be taken care of by aws_run_workflow.sh.


# Usage for create_json.py
The full usage and a simple example command for create_json.py is as below: 
```
usage: create_json.py [-h] [-c CWL] [-cd CWL_DIRECTORY] [-co CWL_CHILDREN]
                      [-a APP_NAME] [-av APP_VERSION] [-i INPUT_FILES]
                      [-ir INPUT_REFERENCE_FILES] [-ip INPUT_PARAMETERS]
                      [-id INPUT_FILES_DIRECTORY]
                      [-ird INPUT_REFERENCE_FILES_DIRECTORY]
                      [-o OUTPUT_BUCKET_DIRECTORY] [-t INSTANCE_TYPE]
                      [-s STORAGE_SIZE] [-IO STORAGE_IOPS] [-jd JSON_DIR]
                      [-J JOB_ID] [-u] [-e]

optional arguments:
  -h, --help            show this help message and exit
  -c CWL, --cwl CWL     main cwl file name
  -cd CWL_DIRECTORY, --cwl_directory CWL_DIRECTORY
                        the url and subdirectories for the main cwl file
                        (override config)
  -co CWL_CHILDREN, --cwl_children CWL_CHILDREN
                        names of the other cwl files used by main cwl file,
                        delimiated by comma
  -a APP_NAME, --app_name APP_NAME
                        name of the app
  -av APP_VERSION, --app_version APP_VERSION
                        version of the app
  -i INPUT_FILES, --input_files INPUT_FILES
                        input files in json format (parametername:filename)
  -ir INPUT_REFERENCE_FILES, --input_reference_files INPUT_REFERENCE_FILES
                        input reference files in json format
                        (parametername:filename)
  -ip INPUT_PARAMETERS, --input_parameters INPUT_PARAMETERS
                        input parameters in json format (parametername:value)
  -id INPUT_FILES_DIRECTORY, --input_files_directory INPUT_FILES_DIRECTORY
                        bucket name and subdirectory for input files
  -ird INPUT_REFERENCE_FILES_DIRECTORY, --input_reference_files_directory INPUT_REFERENCE_FILES_DIRECTORY
                        bucket name and subdirectory for input reference files
                        (override config)
  -o OUTPUT_BUCKET_DIRECTORY, --output_bucket_directory OUTPUT_BUCKET_DIRECTORY
                        bucket name and subdirectory for output files and logs
                        (override config)
  -t INSTANCE_TYPE, --instance_type INSTANCE_TYPE
                        EC2 instance type (default set in config)
  -s STORAGE_SIZE, --storage_size STORAGE_SIZE
                        EBS storage size in GB (default set in config)
  -IO STORAGE_IOPS, --storage_iops STORAGE_IOPS
                        EBS storage IOPS (default set in config)
  -jd JSON_DIR, --json_dir JSON_DIR
                        Local directory in which the output json file will be
                        written (default set in config)
  -J JOB_ID, --job_id JOB_ID
                        Manually assign job ID as specififed (default:
                        randomly generated)
  -u, --copy_to_s3      Upload or copy the json file to S3 bucket json_bucket
  -e, --launch_instance
                        Launch instance based on the json file.
```

```
# A simple example command is shown below. Without -ue, it will only create a json file and will not connect to AWS.
# python ./create_json.py -c some.cwl -a some_app -cd http://some_cwl_url -co other1.cwl,other2.cwl -i '{"input_bam1":"lalala.1.bam","input_bam2":"lalala.1.bam"}' -ir '{"reference_genome":"hg19.fassta"}' -id some_iput_bucket -ird some_reference_bucket -ip '{"binsize":5000,"chr":[1,2,3,4,5]}' -o some_output_bucket -t m2.xlarge -s 200 -IO 6000 -J fhfhfhfh
```


 
# Scripts that will be downloaded to the worker instance
Basically, aws_run_workflow.sh downloads two python scripts that parses and updates json files from github and these three scripts together will do all the works and terminate the EC2 instance once everything is finished.
The three codes are:

 ``aws_run_workflow.sh``

 ``aws_decode_run_json.py``

 ``aws_update_run_json.py``

 
# Assumptions (requirements)
The only assumptions required for this module to work are as below:
1) Must have the above three scripts in the specified SCRIPT_URL. This url can change, if it is changed inside both create_run_workflow.sh and aws_run_workflow.sh. (hard-coded once in each script as an environmental variable)
2) The run json file must be in S3 bucket named 4dn-aws-pipeline-run-json. This bucket name can change, if it is changed inside aws_run_workflow.sh (appearing once in the script as an environmental variable).
3) The run json file name must be $JOBID.run.json (replace $JOBID with the actual job ID).
4) The run json file must be in the following format:
```
{
 "Job": {
   "JOBID": "v989328isyrbag02", 
   "App": {
       "App_name": "Gitar",
       "App_version": "0.2",
       "cwl_url": "https://raw.githubusercontent.com/SooLee/gitar.workflow/master/cwl.draft3_v0.2/",
       "main_cwl": "hictool-bam2hdf5.cwl",
       "other_cwl_files": []
   },
   "Input": {
       "Input_files_data": {
           "input_bam1" : {
               "class": "File",
               "dir": "4dn-tool-evaluation-files",
               "path": "GM12878_SRR1658581_pair1.bam"
           },
           "input_bam2" : {
               "class": "File",
               "dir": "4dn-tool-evaluation-files",
               "path": "GM12878_SRR1658581_pair2.bam"
           }
       },
       "Input_files_reference": {
           "bowtie_index" : {
               "class": "File",
               "dir": "4dn-tool-evaluation-files",
               "path": "hg19.bowtieIndex.tgz"
           },
           "chrlen_file" : {
               "class": "File",
               "dir": "4dn-tool-evaluation-files",
               "path": "hg19.chrlen_file"
           },
           "RE_bed" : {
               "class": "File",
               "dir": "4dn-tool-evaluation-files",
               "path": "HindIII_hg19_liftover.bed"
           }
       },
       "Input_parameters": {
           "contact_matrix_binsize": 50000,
           "chromosome": ["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","X"]
       }
   },
   "Output" : {
       "output_bucket_directory": "4dn-tool-evaluation-files/output/20160918.v989328isyrbag02"
   },
   "Instance_type": "i2.xlarge",
   "EBS_SIZE": "800",
   "EBS_TYPE": "io1",
   "EBS_IOPS": 5000,
   "AMI_ID": "ami-78c13615",
   "start_time" : "20160711-155396-EDT"
 }
}
```

The fields required by the script include
* "App" / "cwl_url" : name of github directory that contains the cwl files (directory for raw files).
* "App" / "main_cwl" : name of the cwl file to run (wither workflow cwl or a command (single-step) cwl).
* "App" / "other_cwl_files" : name of the other cwl files needed to run (e.g. called by main_cwl).
* "Output" / "output_bucket_directory" : name of bucket and subdirectories where output files will be put. The bucket must exist. Subdirectories can be created on the fly.
* "Input" / "Input_files_data" / "class" : always 'File' unless array of files. It follows CWL convention used to define a file input in the meta data file used by cwl-runner.
* "Input" / "Input_files_reference" / "class"  : same.
* "Input" / "Input_files_data" / "dir" : name of bucket and subdirectories where a corresponding input data file is stored.
* "Input" / "Input_files_data" / "path" : name of the input data file. It's called 'path' following the CWL convention but it actually means just the file name (without directories).
* "Input" / "Input_files_reference" : Same structure as "Input_files_data". "Input_files_data" and "Input_files_reference" are not differentiated in these scripts. This distinction is mainly for (potential) convenience when generating this json file, because Input_files_data should contain actual data files like fastq and bam files, whereas Input_files_reference should contain non-experimental data like bowtie index, restriction enzyme site file, chromosome length file, etc, which can be chosen by the user or could be dependent on the experiment (e.g. species, restriction enzyme used, etc) but will constantly reside in some S3 bucket and shared across runs. If there is no reference file, still include this field with null as its value.
* "Input_parameters" : In case the workflow has input parameters other than files, then they can be entered. For a parameter that is scattered according to the workflow, you can use an array representation in square brackets (e.g. chromosomes in the above example)
Other fields are good to have, but not assumed by the above three scripts.
 
# Output
It produces and uploads the following output files in the specified output directory in S3, in addition to the actual output files from the pipeline execution.
* log : stdout and stderr capture from all commands run on the EC2, up to the point before output files are uploaded to S3.
* md5sum.txt : md5sum of all output files except log and md5sum.txt itself.
* $JOBID.postrun.json : This is the same as run.json but with added information of end time and status. The status is either zero (if every command run on EC2 had exit status zero) or a string of exit statuses (e.g. 21,0,0,0,0,1,0,1,1,1,1) that represent the exit status of the commands in the order of execution.
 
