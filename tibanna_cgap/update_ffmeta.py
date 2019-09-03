# -*- coding: utf-8 -*-
import copy
from .zebra_utils import FourfrontUpdater


def update_ffmeta(input_json):
    """Check output and update fourfront metadata"""
    input_json_copy = copy.deepcopy(input_json)

    # metadata-only info may be in 'metadat_only' or in 'config'->'runmode'->'metadata_only'
    # if metadata_only is True, that means the job did not actually run - we're creating/updating metadata
    # as if the job has run.
    if not input_json_copy.get('metadata_only', False):
        input_json_copy['metadata_only'] = input_json_copy['config'].get('runmode', {}).get('metadata_only', False)

    # actual metadata update
    updater = FourfrontUpdater(**input_json_copy)
    if input_json_copy.get('error', False):
        updater.handle_error(input_json_copy['error'])
    try:
        updater.update_metadata()
    except Exception as e:
        updater.handle_error(str(e))

    # lambda output
    input_json_copy['ff_meta'] = updater.ff_meta.as_dict()
    input_json_copy['pf_meta'] = [v.as_dict() for _, v in updater.pf_output_files.items()]
    return input_json_copy
