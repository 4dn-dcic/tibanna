FROM 4dndcic/ubuntu16.04-miniconda-python36-docker:v1
MAINTAINER Soo Lee (duplexa@gmail.com)

# general updates & installing necessary Linux components
RUN apt-get update -y && apt-get install -y \
    bzip2 \
    curl \
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
    parallel \
    autoconf \
    autogen \
    autotools-dev \
    automake \
    pkg-config \
    tabix \
    yasm

WORKDIR /usr/local/bin

# python 3.6
RUN conda install python=3.6.8 && \
    conda clean -a -y -f

RUN pip install --use-feature=2020-resolver boto3==1.15 awscli==1.18.152 urllib3==1.22 botocore==1.18.11

# awsf scripts
COPY aws_run_workflow_generic.sh .
RUN chmod +x aws_run_workflow_generic.sh


# supporting UTF-8
RUN locale-gen "en_US.UTF-8" && update-locale LC_ALL="en_US.UTF-8"
ENV LC_ALL=en_US.UTF-8

CMD ["bash"]
