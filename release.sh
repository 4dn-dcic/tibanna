#!/bin/bash

# build and upload awsf docker image
export BUILD_LOG=/tmp/build-log
export VERSION=$(python -c 'from tibanna._version import __version__; print(__version__)')
export AWSF_IMAGE=$(python -c 'from tibanna.vars import DEFAULT_AWSF_IMAGE; print(DEFAULT_AWSF_IMAGE)')
docker build -t $AWSF_IMAGE --build-arg version=$VERSION awsf3-docker/ > $BUILD_LOG
docker push $AWSF_IMAGE
