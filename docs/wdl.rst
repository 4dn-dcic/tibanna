===================================
Workflow Description Language (WDL)
===================================

Tibanna version < ``1.0.0`` supports WDL draft-2, through Cromwell binary version 35. Tibanna version >= ``1.0.0`` supports both WDL draft-2 and v1.0, through Cromwell binary version 35 and 53, respectively. This is because some of our old WDL pipelines written in draft-2 version no longer works with the new Cromwell version and we wanted to ensure the backward compatibility. But if you want to use WDL draft-2, specify ``"language": "wdl_draft2"`` instead of ``"language": "wdl"`` which defaults to WDL v1.0.

Tibanna version >= ``1.7.0`` supports (Caper_) in addition to Cromwell. If you would like to use Caper, add ``"workflow_engine": "caper"`` to the Tibanna job description. Cromwell is the default.

.. _Caper: https://github.com/ENCODE-DCC/caper