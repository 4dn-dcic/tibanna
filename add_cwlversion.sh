#!/bin/bash
sed 's/"config".*: {$/"config": {\'$'\n    "cwl_version": "draft3",/g' $1

