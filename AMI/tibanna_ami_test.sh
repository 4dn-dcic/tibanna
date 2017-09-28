#!/bin/bash
source ~/venv/cwl/bin/activate
git clone https://github.com/4dn-dcic/pipelines-cwl
cd pipelines-cwl
source tests/tests.sh md5

