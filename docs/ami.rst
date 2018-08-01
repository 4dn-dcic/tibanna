====================
Amazon Machine Image
====================

Tibanna uses two Amazon Machine Images (AMIs) which are made public. One can find them among Community AMIs.

* ``ami-31caa14e`` for CWL v1 (Ubunti-based)
* ``ami-cfb14bb5`` for CWL draft3 (Amazon Linux-based)

Tibanna automatically chooses the right AMI, based on the CWL version specified in the `cwl_version` field of the input json.


