#!/bin/bash
name=$1
zipfilepath=$2
desc=$name
role_arn='arn:aws:iam::643366669028:role/service-role/readS3'
#source ~/bin/awscli/bin/activate
aws lambda create-function  \
    --region us-east-1          \
    --runtime python2.7       \
    --role $role_arn  \
    --description "$desc" \
    --timeout 60      \
    --memory-size 128 \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://$zipfilepath  \
    --function-name $name

