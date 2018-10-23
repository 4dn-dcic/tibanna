====================
Amazon Machine Image
====================

Tibanna uses two Amazon Machine Images (AMIs) which are made public. One can find them among Community AMIs.

* ``ami-31caa14e`` for CWL v1 (Ubuntu-based)
* ``ami-cfb14bb5`` for CWL draft3 (Amazon Linux-based)
* ``ami-ami-0f06a8358d41c4b9c`` for WDL draft2 (Ubuntu-based)

Tibanna automatically chooses the right AMI, based on the `language` field and the CWL version specified in the `cwl_version` field of the job description json.


