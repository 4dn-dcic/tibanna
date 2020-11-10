FROM ubuntu:20.04
MAINTAINER Soo Lee (duplexa@gmail.com)

ARG version

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
    gcc \
    g++ \
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
    build-essential \
    libssl-dev \
    uuid-dev \
    libgpgme11-dev \
    squashfs-tools \
    libseccomp-dev \
    pkg-config \
    openjdk-8-jre-headless

RUN ln -s /usr/bin/python3.8 /usr/bin/python
RUN ln -s /usr/bin/pip3 /usr/bin/pip

WORKDIR /usr/local/bin

# docker inside docker
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - \
    && apt-key fingerprint 0EBFCD88 \
    && add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
RUN apt-get update -y \
    && apt-cache policy docker-ce \
    && apt-get install -y docker-ce

# singularity
RUN wget https://golang.org/dl/go1.15.3.linux-amd64.tar.gz && \
    tar -xzf go1.15.3.linux-amd64.tar.gz && \
    rm go1.15.3.linux-amd64.tar.gz
RUN export SINGULARITY_VERSION=3.3.0 && \
    export PATH=/usr/local/bin/go/bin/:$PATH && \
    wget https://github.com/sylabs/singularity/releases/download/v${SINGULARITY_VERSION}/singularity-${SINGULARITY_VERSION}.tar.gz && \
    tar -xzf singularity-${SINGULARITY_VERSION}.tar.gz && \
    rm singularity-${SINGULARITY_VERSION}.tar.gz && \
    cd singularity && \
    ./mconfig && \
    make -C ./builddir && \
    make -C ./builddir install && \
    cd .. && \
    rm -rf go && \
    mv singularity/singularity singularity2 && \
    rm -rf singularity && \
    mv singularity2 singularity

# goofys
RUN curl -O -L http://bit.ly/goofys-latest && chmod +x goofys-latest

# python packages
RUN pip install boto3==1.15 awscli==1.18.152 botocore==1.18.11
RUN pip install psutil==5.7.3
RUN pip install schema-salad==7.0.20200811075006 cwltool==3.0.20201017180608

# cromwell
RUN wget https://github.com/broadinstitute/cromwell/releases/download/53.1/cromwell-53.1.jar && \
    ln -s cromwell-53.1.jar cromwell.jar

# awsf scripts
COPY run.sh .
COPY cron.sh .
RUN chmod +x run.sh cron.sh
RUN pip install tibanna==$version

# Move default docker daemon location to mounted EBS
COPY daemon.json /etc/docker/daemon.json


# supporting UTF-8
RUN locale-gen "en_US.UTF-8" && update-locale LC_ALL="en_US.UTF-8"
ENV LC_ALL=en_US.UTF-8

CMD ["bash"]
