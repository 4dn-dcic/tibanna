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


KMS-encrypted AMIs
==================

If your custom AMI is encrypted with a KMS key (for example, an encrypted base AMI
provided by your IT department, possibly with the key owned by a different AWS account),
the EC2 instance must be able to decrypt the AMI's EBS snapshot at launch time. If it
cannot, the instance starts and is terminated immediately, and the EC2 console shows::

    Client.InvalidKMSKey.InvalidState: The KMS key provided is in an incorrect state

Note that being able to launch the AMI manually from the EC2 console does **not** mean
Tibanna can launch it. The console launches the instance as *your* IAM user, while
Tibanna launches it via an EC2 Fleet created by the ``run_task_awsem`` Lambda. That
Lambda's role is the principal that must hold the KMS permissions, and it must be able
to call ``kms:CreateGrant`` on the key (this is the permission most commonly missing).

To grant the ``run_task_awsem`` Lambda role the required permissions on the AMI's KMS
key, set the ``AMI_KMS_KEY_ID`` environment variable **before deploying Tibanna**, then
deploy (or redeploy):
::

    # bare key id -> assumed to live in your account / region
    export AMI_KMS_KEY_ID=abcd1234-...

    # or a full ARN -> required when the key lives in another account (e.g. owned by IT)
    export AMI_KMS_KEY_ID=arn:aws:kms:us-east-1:111122223333:key/abcd1234-...

    tibanna deploy_unicorn ...

When ``AMI_KMS_KEY_ID`` is set, ``deploy_unicorn`` attaches a policy to the
``run_task_awsem`` Lambda role granting ``kms:Decrypt``, ``kms:DescribeKey``,
``kms:GenerateDataKeyWithoutPlaintext``, ``kms:ReEncrypt*`` and ``kms:CreateGrant`` on
that key. If the variable is unset, nothing changes from the default behavior.

For a **cross-account** key, this is only half of what AWS requires: the key's owner
(e.g. IT) must also grant your account access in the key policy (typically by allowing
the ``arn:aws:iam::<your-account>:root`` principal). The ``AMI_KMS_KEY_ID`` setting takes
care of the identity-based half in your account; it cannot grant access the key owner
has not delegated.

Alternatively, you can avoid the cross-account dependency entirely by copying the AMI
into your own account and re-encrypting it with a key you control
(``aws ec2 copy-image --encrypted --kms-key-id <your-own-key>``), then pointing
``ami_per_region`` at the copy. You still need ``AMI_KMS_KEY_ID`` set to your own key so
the Lambda role gets ``kms:CreateGrant``.

