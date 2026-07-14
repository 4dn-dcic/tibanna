import argparse
from tibanna.__main__ import Subcommands


def _build_subparser(subcommand):
    """Build a standalone parser for one subcommand using the exact same
    arg-spec list __main__.main() uses, without touching the dispatch logic
    (which would otherwise hit live AWS via API()).
    """
    scs = Subcommands()
    parser = argparse.ArgumentParser(prog='tibanna')
    for argdict in scs.args[subcommand]:
        argdict = dict(argdict)
        flag = argdict.pop('flag')
        parser.add_argument(flag[0], flag[1], **argdict)
    return parser


def test_rerun_many_offset_parses_as_int():
    """C13 regression: -o/--offset must parse to an int (like its siblings
    --stophour/--stopminute) or core.rerun_many's `stophour + offset` raises
    TypeError (int + str) for every `tibanna rerun_many -o N` invocation.
    """
    parser = _build_subparser('rerun_many')
    args = parser.parse_args(['-o', '5'])
    assert args.offset == 5
    assert isinstance(args.offset, int)
    # exercise the exact computation rerun_many performs with it
    stophour = 13 + args.offset
    assert stophour == 18


def test_list_sfns_sfn_type_flag_reaches_handler_signature():
    """C16 regression: list_sfns declares -s/--sfn-type but the dispatcher only
    forwards args whose names match the handler's parameter list - make sure
    the handler (tibanna.__main__.list_sfns) actually has an sfn_type parameter
    so the declared CLI flag is not silently dropped.
    """
    import inspect
    from tibanna.__main__ import list_sfns
    assert 'sfn_type' in inspect.getfullargspec(list_sfns).args

    parser = _build_subparser('list_sfns')
    args = parser.parse_args(['-s', 'pony'])
    assert args.sfn_type == 'pony'
