====================
Amazon Machine Image
====================

Tibanna now uses a single Amazon Machine Image (AMI) `ami-0f06a8358d41c4b9c`, which is made public for CWL v1, CWL draft3 and WDL. One can find them among Community AMIs. (Tibanna automatically finds and uses them, so no need to worry about it.)

Tibanna automatically chooses what to do with this AMI, based on the `language` field and the CWL version specified in the `cwl_version` field of the job description json.

