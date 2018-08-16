==============
Simple Example
==============

Very simple example
-------------------


Let's try a very simple pipeline that calculates md5sum of an input file. We write a script named ``run.sh`` that calculates two md5sum values for a gzipped input file, one for compressed and one for uncompressed content of the file. The script creates an output file named ``report`` that contains two md5sum values. If the file is not gzipped, it simply repeats a regular md5sum value twice.

The script could look as below.

::

    #!/bin/bash
    
    file=$1
    
    if [[ $file =~ \.gz$ ]]
    then
      MD_OUT=($(md5sum $file))
      CONTENT_MD_OUT=($(gunzip -c $file | md5sum))
    else
      MD_OUT=($(md5sum $file))
      CONTENT_MD_OUT=$MD_OUT
    fi
    
    MD=${MD_OUT[0]}
    CONTENT_MD=${CONTENT_MD_OUT[0]}
    echo "$MD" >> report
    echo "$CONTENT_MD" >> report


Docker image
++++++++++++

We already have a public docker image for this (``duplexa/md5:v2``) that contains script ``run.sh``. You can find it on Docker Hub: https://hub.docker.com/r/duplexa/md5/. If you want to use this public image, you can skip the following.

To create your own, first you need to install docker on your (local) machine.
1. First, create a directory (e.g. named ``md5``)
2. Then, inside this directory create a file named  ``Dockerfile`` with the following content.

::

    # start from ubuntu docker image
    FROM ubuntu:16.04
    
    # general updates & installing necessary Linux components
    RUN apt-get update -y && apt-get install -y unzip
    
    # copy the pipeline script into the image
    # (in this case, /usr/local/bin)
    WORKDIR /usr/local/bin
    COPY run.sh .
    RUN chmod +x run.sh
    
    # default command
    CMD ["run.sh"]

3. Then, build docker image. You can use the same image name (``duplexa/md5:v2``) for this step, but it is recommended to replace ``duplexa`` with your preferred Docker Hub account name, to be able to push the image to Docker Hub later.

::

    docker build -t duplexa/md5:v2 .


4. Check the image

::

    docker images


5. Push the image to Docker Hub. You need an account to Docker Hub.

::

    docker login
    docker push duplexa/md5:v2



CWL
+++

A CWL file could look as below. This CWL file can be found at https://github.com/4dn-dcic/tibanna/examples/md5/md5.cwl. To use your own docker image, replace ``duplexa/md5:v2`` with your docker image name. Put this CWL file in a place where you can access through http, so that Tibanna can download this file to the cloud using ``wget`` command.

::

    ---
    cwlVersion: v1.0
    inputs:
    - id: "#input_file"
      type:
      - File
      inputBinding:
        position: 1
    outputs:
    - id: "#report"
      type:
      - File
      outputBinding:
        glob: report
    hints:
    - dockerPull: duplexa/md5:v2
      class: DockerRequirement
    baseCommand:
    - run.sh
    class: CommandLineTool

    
