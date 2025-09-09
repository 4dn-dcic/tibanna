FROM ubuntu:20.04

# general updates & installing necessary Linux components
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
RUN apt update -y && apt upgrade -y &&  apt install -y \
    apt-transport-https \
    bzip2 \
    ca-certificates \
    cron \
    curl \
    fuse \
    git \
    less \
    locales \
    make \
    python3 \
    python3-pip \
    time \
    unzip \
    vim \
    wget \
    software-properties-common \
    libssl-dev \
    libwww-perl \
    libdatetime-perl \
    uuid-dev \
    libgpgme11-dev \
    squashfs-tools \
    libseccomp-dev \
    pkg-config \
    openjdk-8-jre-headless \
    nodejs \
    gnupg \
    lsb-release

RUN ln -s /usr/bin/python3.8 /usr/bin/python
#RUN ln -s /usr/bin/pip3 /usr/bin/pip

WORKDIR /usr/local/bin

# install docker inside docker
RUN mkdir -p /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

RUN echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

RUN apt-get update
RUN apt-get --assume-yes install docker-ce=5:24.0.7-1~ubuntu.20.04~focal

# Singularity
RUN ARCH="$(dpkg --print-architecture)" && \
    SINGULARITY_VERSION=3.10.4 && \
    wget https://tibanna-dependencies.s3.amazonaws.com/singularity/singularity-ce_${SINGULARITY_VERSION}-focal_${ARCH}.deb && \
    apt install -y ./singularity-ce_${SINGULARITY_VERSION}-focal_${ARCH}.deb && \
    rm singularity-ce_${SINGULARITY_VERSION}-focal_${ARCH}.deb

# goofys
# RUN wget https://github.com/kahing/goofys/releases/download/v0.24.0/goofys && chmod +x goofys
RUN ARCH="$(dpkg --print-architecture)" && \
    wget https://tibanna-dependencies.s3.amazonaws.com/goofys/v0.24.0/${ARCH}/goofys && chmod +x goofys

# python packages
RUN pip install boto3==1.15 awscli==1.18.152 botocore==1.18.11
RUN pip install psutil==5.7.3
RUN pip install cwltool==3.1.20211103193132
RUN pip install ec2-metadata

# cromwell for WDL 1.0
RUN wget https://github.com/broadinstitute/cromwell/releases/download/53.1/cromwell-53.1.jar && \
    ln -s cromwell-53.1.jar cromwell.jar
# Old cromwell for WDL draft-2
RUN wget https://github.com/broadinstitute/cromwell/releases/download/35/cromwell-35.jar
RUN wget https://github.com/broadinstitute/cromwell/blob/develop/LICENSE.txt  # cromwell license

# Caper - uses cromwell 59 under the hood
RUN pip install caper==1.6.3

# Dependency of cwltool that requires a specific version of ruamel.yaml
RUN pip install ruamel.yaml==0.17.16

# awsf scripts
COPY run.sh .
COPY cron.sh .
RUN chmod +x run.sh cron.sh
ARG version
RUN pip install tibanna==$version

# Move default docker daemon location to mounted EBS
COPY daemon.json /etc/docker/daemon.json


# supporting UTF-8
RUN locale-gen "en_US.UTF-8" && update-locale LC_ALL="en_US.UTF-8"
ENV LC_ALL=en_US.UTF-8

CMD ["bash"]
