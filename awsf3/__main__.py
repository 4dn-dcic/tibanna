"""
CLI for tibanna awsf3 package
"""

# -*- coding: utf-8 -*-
import argparse
import inspect
from tibanna._version import __version__  # for now use the same version as tibanna
from . import utils


PACKAGE_NAME = 'awsf3'


class Subcommands(object):

    def __init__(self):
        pass

    @property
    def descriptions(self):
        return {
            'decode_run_json': 'decode run json',
            'download_workflow': 'download workflow files',
            'update_postrun_json_init': 'update json json with instance ID and file system',
            'upload_postrun_json': 'upload postrun json file',
            'update_postrun_json_upload_output': 'update json json with output paths/target/md5 and upload outupt',
            'update_postrun_json_final': 'update postrun json with status, time stamp etc'
        }

    @property
    def args(self):
        return {
            'decode_run_json':
                [{'flag': ["-i", "--input-run-json"], 'help': "input run json file"},
                 {'flag': ["-k", "--kms-key-id"], 'help': "kms-key-id to use for encrypting s3 files"}],
            'download_workflow':
                [],
            'update_postrun_json_init':
                [{'flag': ["-i", "--input-json"], 'help': "input run/postrun json file"},
                 {'flag': ["-o", "--output-json"], 'help': "output postrun json file"}],
            'update_postrun_json_upload_output':
                [{'flag': ["-i", "--input-json"], 'help': "input run/postrun json file"},
                 {'flag': ["-e", "--execution-metadata-file"],
                  'help': "execution metadata file (output json of cwltool / cromwell)"},
                 {'flag': ["-m", "--md5file"], 'help': "text file storing md5 values for output files"},
                 {'flag': ["-o", "--output-json"], 'help': "output postrun json file"},
                 {'flag': ["-L", "--language"], 'help': "language", 'default': "cwl_v1"},
                 {'flag': ["-u", "--endpoint-url"], 'help': "s3 vpc endpoint url"}],
            'upload_postrun_json':
                [{'flag': ["-i", "--input-json"], 'help': "input postrun json file to upload to s3"}],
            'update_postrun_json_final':
                [{'flag': ["-i", "--input-json"], 'help': "input run/postrun json file"},
                 {'flag': ["-o", "--output-json"], 'help': "output postrun json file"},
                 {'flag': ["-l", "--logfile"], 'help': "Tibanna awsem log file"}],
        }


def decode_run_json(input_run_json, kms_key_id=None):
    utils.decode_run_json(input_run_json, kms_key_id=kms_key_id)


def download_workflow():
    utils.download_workflow()


def update_postrun_json_init(input_json, output_json):
    utils.update_postrun_json_init(input_json, output_json)


def update_postrun_json_upload_output(input_json, execution_metadata_file, md5file, output_json, language, endpoint_url):
    utils.update_postrun_json_upload_output(input_json, execution_metadata_file, md5file, output_json, language, endpoint_url=endpoint_url)


def upload_postrun_json(input_json):
    utils.upload_postrun_json(input_json)


def update_postrun_json_final(input_json, output_json, logfile):
    utils.update_postrun_json_final(input_json, output_json, logfile)


def main(Subcommands=Subcommands):
    """
    Execute the program from the command line
    """
    scs = Subcommands()

    # the primary parser is used for awsf -v or -h
    primary_parser = argparse.ArgumentParser(prog=PACKAGE_NAME, add_help=False)
    primary_parser.add_argument('-v', '--version', action='version',
                                version='%(prog)s ' + __version__)
    # the secondary parser is used for the specific run mode
    secondary_parser = argparse.ArgumentParser(prog=PACKAGE_NAME, parents=[primary_parser])
    subparsers = secondary_parser.add_subparsers(
        title=PACKAGE_NAME + ' subcommands',
        description='choose one of the following subcommands to run ' + PACKAGE_NAME,
        dest='subcommand',
        metavar='subcommand: {%s}' % ', '.join(scs.descriptions.keys())
    )
    subparsers.required = True

    def add_arg(name, flag, **kwargs):
        subparser[name].add_argument(flag[0], flag[1], **kwargs)

    def add_args(name, argdictlist):
        for argdict in argdictlist:
            add_arg(name, **argdict)

    subparser = dict()
    for sc, desc in scs.descriptions.items():
        subparser[sc] = subparsers.add_parser(sc, help=desc, description=desc)
        if sc in scs.args:
            add_args(sc, scs.args[sc])

    # two step argument parsing
    # first check for top level -v or -h (i.e. `tibanna -v`)
    (primary_namespace, remaining) = primary_parser.parse_known_args()
    # get subcommand-specific args
    args = secondary_parser.parse_args(args=remaining, namespace=primary_namespace)
    subcommandf = eval(args.subcommand)
    sc_args = [getattr(args, sc_arg) for sc_arg in inspect.getargspec(subcommandf).args]
    # run subcommand
    subcommandf(*sc_args)


if __name__ == '__main__':
    main()
