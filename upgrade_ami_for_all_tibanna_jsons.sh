#!/bin/bash

OLD_AMI=$1  # e.g. ami-7ff26968
NEW_AMI=$2  #.e.g  ami-cfb14bb5

ls -1 test_json/*json | xargs -I{} sh -c "sed 's/$OLD_AMI/$NEW_AMI/g' '{}' > '{}'.2"
ls -1 test_json/*json | xargs -I{} sh -c "mv '{}'.2 '{}'"

ls -1 core/*awsf/event.json | xargs -I{} sh -c "sed 's/$OLD_AMI/$NEW_AMI/g' '{}' > '{}'.2"
ls -1 core/*awsf/event.json | xargs -I{} sh -c "mv '{}'.2 '{}'"

ls -1 notebooks/*.ipynb | xargs -I{} sh -c "sed 's/$OLD_AMI/$NEW_AMI/g' '{}' > '{}'.2"
ls -1 notebooks/*.ipynb | xargs -I{} sh -c "mv '{}'.2 '{}'"
