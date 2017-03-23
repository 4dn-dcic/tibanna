=====================
# Tibanna
=====================

Tibanna is the gas mine in Cloud City that makes Hyperdrives zoom.  It's also the pipeline running in the cloud that ensure data is properly processed for 4dn.

[![Build Status](https://travis-ci.org/4dn-dcic/tibanna.svg?branch=master)](https://travis-ci.org/4dn-dcic/tibanna)

[![Code Quality](https://api.codacy.com/project/badge/Grade/d2946b5bc0704e5c9a4893426a7e0314)](https://www.codacy.com/app/4dn/tibanna?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=4dn-dcic/tibanna&amp;utm_campaign=Badge_Grade)

[![Test Coverage](https://api.codacy.com/project/badge/Coverage/d2946b5bc0704e5c9a4893426a7e0314)](https://www.codacy.com/app/4dn/tibanna?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=4dn-dcic/tibanna&amp;utm_campaign=Badge_Coverage)

Tibanna is an AWS step-function-based pipeline scheduler. It connects to either SevenBridgesGenomics or to our own system.
<br><br>
![Tibanna-sbg](tibanna_sbg_animated.gif)
<br><br>
![Tibanna-awsf](tibanna_awsf.png)
<br><br>


## Directory Structure

## core
This is core functionality (a set of lambda functions) that relies on AWS STEP Function to manage the process of running pipelines.  Does stuff like stage files to correct place, run workflow, poll for results, put output files in s3 and update associated metadata on the fourfront system.


## awsf
A set of tools for running docker- and cwl-based pipelines on AWS
* [README](awsf/README.md) for more details

## lambda_sbg
A lambda function integrated with APIGateway, for managing pipelines on AWS and SBG
* [README](lambda_sbg/README.md) for more details

* TODO: have registration function that creates the step-function workflow, ideally storing
  configuration in internal tables so stats an be gathered and d presented to users. 
