========
Overview
========

Tibanna is a software tool that helps you run genomic pipelines on the cloud.
It is also used by 4DN-DCIC (4D Nucleome Data Coordination and Integration Center) to process data.


What do I need to run pipelines using Tibanna?
----------------------------------------------

- Your pipeline
- Your data
- An Amazon Web Services (AWS) cloud account
- Tibanna


Pipeline
++++++++

- Your pipeline and dependencies must be pre-installed in a docker image
- The commands to run your pipeline must be written in Common Workflow Language


Data
++++

- Your data must be pre-uploaded to a permanent storage on the cloud (called S3 bucket).


AWS cloud account
+++++++++++++++++

- check https://aws.amazon.com/ 


Tibanna
+++++++

- Tibanna is open-source and can be found at https://github.com/4dn-dcic/tibanna
- Once installed, tibanna can be run either as a set of commend-line tools or a set of python modules


**Command-line tools**

::

    $ invoke run_workflow --input-json=run1.json


**Python**

::

    >>> from core.utils import run_workflow
    >>> run_workflow(input_json=run1)



Contents:

.. toctree::
   :hidden:

   self


.. toctree::
   :maxdepth: 3

   simple_example
   startaws
   installation
   commands
   execution_json
   monitoring
   cwl
   ami
   pony
   how_it_works

