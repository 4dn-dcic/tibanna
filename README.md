# Tibanna

[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/) [![Build Status](https://travis-ci.org/4dn-dcic/tibanna.svg?branch=master)](https://travis-ci.org/4dn-dcic/tibanna) [![Code Quality](https://api.codacy.com/project/badge/Grade/d2946b5bc0704e5c9a4893426a7e0314)](https://www.codacy.com/app/4dn/tibanna?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=4dn-dcic/tibanna&amp;utm_campaign=Badge_Grade) [![Test Coverage](https://api.codacy.com/project/badge/Coverage/d2946b5bc0704e5c9a4893426a7e0314)](https://www.codacy.com/app/4dn/tibanna?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=4dn-dcic/tibanna&amp;utm_campaign=Badge_Coverage) [![Documentation Status](https://readthedocs.org/projects/tibanna/badge/?version=latest)](https://tibanna.readthedocs.io/en/latest/?badge=latest)

***

Tibanna runs portable pipelines (in CWL/WDL/Snakemake/shell) on the AWS Cloud.

<br>

Install Tibanna.
```bash
pip install tibanna
```

<br>

Use CLI to set up the cloud component and run workflow.
```bash
# Deploy Unicorn to the Cloud (Unicorn = serverless scheduler/resource allocator).
tibanna deploy_unicorn --usergroup=mygroup

# Run CWL/WDL workflow on the Cloud.
tibanna run_workflow --input-json=myrun.json
```

<br>

Alternatively, use Python API.

```python
from tibanna.core import API

# Deploy Unicorn to the Cloud.
API().deploy_unicorn(usergroup='mygroup')

# Run CWL/WDL workflow on the Cloud.
API().run_workflow(input_json='myrun.json')
```

<br>

---
Note: Starting `0.8.2`, Tibanna supports local CWL/WDL files as well as shell commands and Snakemake workflows.

Note 2: As of Tibanna version `2.0.0`, Python 3.6 is no longer supported. Please switch to Python 3.8! Python 3.7 is also supported as a fallback, but please prefer 3.8 if you can.

Note 3: Starting `0.8.0`, one no longer needs to `git clone` the Tibanna repo. 
* Please switch from `invoke <command>` to `tibanna <command>`! 
* We also renovated the Python API as an inheritable class to allow development around tibanna.


For more details, see Tibanna [**Documentation**](http://tibanna.readthedocs.io/en/latest).
* Also check out our [**paper in _Bioinformatics_**](https://doi.org/10.1093/bioinformatics/btz379).
* A preprint can also be found on [**biorxiv**](https://www.biorxiv.org/content/10.1101/440974v3).

