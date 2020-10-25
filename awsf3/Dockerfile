FROM 4dndcic/ubuntu16.04-miniconda-python36-docker:v1
MAINTAINER Soo Lee (duplexa@gmail.com)

# general updates & installing necessary Linux components
RUN apt-get update -y && apt-get install -y \
    bzip2 \
    curl \
    fuse \
    gcc \
    g++ \
    git \
    less \
    libncurses-dev \
    make \
    time \
    unzip \
    vim \
    wget \
    zlib1g-dev \
    liblz4-tool \
    libbz2-dev \
    liblzma-dev \
    locales \
    autoconf \
    autogen \
    autotools-dev \
    automake \
    pkg-config \
    yasm

WORKDIR /usr/local/bin

# python 3.6
RUN conda install python=3.6.8 && \
    conda clean -a -y -f

# python packages
RUN pip install --use-feature=2020-resolver boto3==1.15 awscli==1.18.152 urllib3==1.22 botocore==1.18.11
RUN conda uninstall --force ruamel_yaml  # version conflict with cwltool
RUN pip install --use-feature=2020-resolver schema-salad==7.0.20200811075006 cwltool==3.0.20201017180608

# goofys
RUN curl -O -L http://bit.ly/goofys-latest && chmod +x goofys-latest

# awsf scripts
COPY aws_run_workflow_generic.sh *.py ./
RUN chmod +x aws_run_workflow_generic.sh
RUN python setup.py install

# supporting UTF-8
RUN locale-gen "en_US.UTF-8" && update-locale LC_ALL="en_US.UTF-8"
ENV LC_ALL=en_US.UTF-8

CMD ["bash"]
