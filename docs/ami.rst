====================
Amazon Machine Image
====================

Tibanna now uses the Amazon Machine Images (AMI) ``ami-06e2266f85063aabc`` (``x86``) and ``ami-0f3e90ad8e76c7a32`` (``Arm``), which are made public for ``us-east-1``. One can find them among Community AMIs. (Tibanna automatically finds and uses them, so no need to worry about it.)

For regions that are not ``us-east-1``, copies of these AMIs are publicly available (different AMI IDs) and are auto-detected by Tibanna.

If you want to use your own AMI, you can overwrite the default values in the ``config`` field of the Job Description JSON:
::

    {
      "args": {
        ...
      },
      "config": {
        ...
        "ami_per_region": {
          "x86": {
            "us-east-1": "my_x86_ami_ue1",
            "us-east-2": "my_x86_ami_ue2",
            ...
          },
          "Arm": {
            "us-east-1": "my_arm_ami_ue1",
            "us-east-2": "my_arm_ami_ue2",
            ...
          }
        },
      }
    }

