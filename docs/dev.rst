=================
Developers' guide
=================

This section is for developers who want to understand the structure of the code arragements and details of the features and behaviors that are intended for Tibanna Unicorn, Pony and Zebra (the latter two specifically designed for 4DNucleome and CGAP (Clinical Genome Analysis Platform) data portals).


Overview of the Tibanna code structure
--------------------------------------

Tibanna Pony (4DN) and Zebra (CGAP) are built upon Tibanna Unicorn (public, independent of any data portal). Code for Pony and Zebra uses code for Unicorn by either importing or inheriting. The code shared between Pony and Zebra that are not a part of Unicorn is stored in the shared component ``ffcommon``. All of these use AWSEM (Automonous Workflow Step Executor Machine) at the core, which is an EC2 instance that is auto-configured by Tibanna that does its job automonously and terminates itself at the end.


Directory structure
+++++++++++++++++++

- tibanna : code for Unicorn
- tibanna_4dn : code for Pony
- tibanna_cgap : code for Zebra
- tibanna_ffcommon : code shared between Pony and Zebra that are not part of Unicorn
- awsf : code that runs on AWSEM (commonly used by Unicorn, Pony and Zebra)


Each of the three variants (Unicorn, Pony or Zebra) consists of a core API (``core.py``), CLI (``__main__.py``), lambdas (``/lambdas``) and set of python modules that are used by the former three.


Installation
------------

Installation and dependencies
+++++++++++++++++++++++++++++

``pip install tibanna`` would install only ``tibanna`` but not ``tibanna_cgap`` or ``tibanna_4dn``, though it specifies the latter two as entry points as well. In order to use ``tibanna_4dn`` or ``tibanna_cgap``, one should additionally install ``dcicutils`` (currently equivalent to the more official way). Alternatively (official), the dependencies for pony or zebra must be intalled by ``pip install -r requirements-4dn.txt`` or ``pip install -r requiremnets-cgap.txt`` in the repo directory (after ``git clone https://github.com/4dn-dcic/tibanna; cd tibanna``)


Environment variables
+++++++++++++++++++++

The following environment variables are required for ``tibanna``, unless ``.aws/credentials`` and ``.aws/config`` are set up.


::

    export AWS_ACCESS_KEY_ID=<aws_key>
    export AWS_SECRET_ACCESS_KEY=<aws_secret_key>
    export AWS_DEFAULT_REGION=<aws_region>


To use ``tibanna_4dn`` or ``tibanna_cgap``, the following environment variable is additionally required. (This is available only for the 4DN/CGAP developer team.)


::

    export S3_ENCRYPT_KEY=<fourfront_s3_encrypt_key>




Key functions
-------------

Tibanna Deployment
++++++++++++++++++

::

    tibanna deploy_unicorn [options]


::

    tibanna_4dn deploy_pony [options]


::

    tibanna_cgap deploy_zebra [options]



The above three are *not* interchangeable and each should be used to deploy a tibanna stepfunction of its own kind.

Even for deploying a single lambda function, we should use the right entry point as below.


::

    tibanna deploy_core -n <lambda_name> [options]


::

    tibanna_4dn deploy_core -n <lambda_name> [options]


::

    tibanna_cgap deploy_core -n <lambda_name> [options]




Running Workflow
++++++++++++++++

::

    tibanna run_workflow -i <input_json> --sfn=<stepfunctionname>


::

    tibanna_4dn run_workflow -i <input_json> --sfn=<stepfunctionname>


::

    tibanna_cgap run_workflow -i <input_json> --sfn=<stepfunctionname>



The above three can be used interchageably, as long as the correct stepfunctionname is used. i.e. the following command still works and would submit a job to ``tibanna_pony`` even if the entry point ``tibanna_cgap`` was used.


::

    tibanna_cgap run_workflow -i <input_json> --sfn=tibanna_pony




