#!/usr/bin/env python3
# -*- coding: latin-1 -*-
import os.path
import argparse
from wranglertools import fdnDCIC
import attr
import xlwt
import sys


EPILOG = '''
    To create an xls file with sheets to be filled use the example and modify to your needs.
    It will accept the following parameters.
        --type           use for each sheet that you want to add to the excel workbook
        --descriptions   adds the descriptions in the second line (by default True)
        --enums          adds the list of options for a fields if it has a controlled vocabulary (by default True)
        --comments       adds the comments together with enums (by default False)
        --writexls       creates the xls file (by default True)
        --outfile        change the default file name "fields.xls" to a specified one
        --order          create an ordered and filtered version of the excel (by default True)

    This program graphs uploadable fields (i.e. not calculated properties)
    for a type with optionally included description and enum values.

    To get multiple objects use the '--type' argument multiple times

            %(prog)s --type Biosample --type Biosource

    to include comments (useful tips) for all types use the appropriate flag at the end

            %(prog)s --type Biosample --comments
            %(prog)s --type Biosample --type Biosource --comments

    To change the result filename use --outfile flag followed by the new file name

            %(prog)s --type Biosample --outfile biosample_only.xls
            %(prog)s --type Biosample --type Experiment --outfile my_selection.xls

    '''


def getArgs():  # pragma: no cover
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--type',
                        help="Add a separate --type for each type you want to get.",
                        action="append")
    parser.add_argument('--descriptions',
                        default=True,
                        action='store_true',
                        help="Include descriptions for fields.")
    parser.add_argument('--comments',
                        default=False,
                        action='store_true',
                        help="Include comments for fields")
    parser.add_argument('--enums',
                        default=True,
                        action='store_true',
                        help="Include enums for fields.")
    parser.add_argument('--writexls',
                        default=True,
                        action='store_true',
                        help="Create an xls with the columns and sheets"
                             "based on the data returned from this command.")
    parser.add_argument('--key',
                        default='default',
                        help="The keypair identifier from the keyfile.  \
                        Default is --key=default")
    parser.add_argument('--keyfile',
                        default=os.path.expanduser("~/keypairs.json"),
                        help="The keypair file.  Default is --keyfile=%s" %
                             (os.path.expanduser("~/keypairs.json")))
    parser.add_argument('--debug',
                        default=False,
                        action='store_true',
                        help="Print debug messages.  Default is False.")
    parser.add_argument('--outfile',
                        default='fields.xls',
                        help="The name of the output file. Default is fields.xls")
    parser.add_argument('--order',
                        default=True,
                        action='store_true',
                        help="A reference file is used for ordering and filtering fields")
    args = parser.parse_args()
    return args


@attr.s
class FieldInfo(object):
    name = attr.ib()
    ftype = attr.ib()
    desc = attr.ib(default=u'')
    comm = attr.ib(default=u'')
    enum = attr.ib(default=u'')

# additional fields for experiment sheets to capture experiment_set related information
exp_set_addition = [FieldInfo('*replicate_set', 'Item:ExperimentSetReplicate', 'Grouping for replicate experiments'),
                    FieldInfo('*bio_rep_no', 'number', 'Biological replicate number'),
                    FieldInfo('*tec_rep_no', 'number', 'Technical replicate number'),
                    FieldInfo('experiment_set', 'array of Item:ExperimentSet', 'Grouping for non-replicate experiments')
                    ]


def get_field_type(field):
    field_type = field.get('type', '')
    if field_type == 'string':
        if field.get('linkTo', ''):
            return "Item:" + field.get('linkTo')
        # if multiple objects are linked by "anyOf"
        if field.get('anyOf', ''):
            links = filter(None, [d.get('linkTo', '') for d in field.get('anyOf')])
            if links:
                return "Item:" + ' or '.join(links)
        # if not object return string
        return 'string'
    elif field_type == 'array':
        return 'array of ' + get_field_type(field.get('items'))
    return field_type


def is_subobject(field):
    try:
        return field['items']['type'] == 'object'
    except:
        return False


def dotted_field_name(field_name, parent_name=None):
    if parent_name:
        return "%s.%s" % (parent_name, field_name)
    else:
        return field_name


def build_field_list(properties, required_fields=None, include_description=False,
                     include_comment=False, include_enums=False, parent='', is_submember=False):
    fields = []
    for name, props in properties.items():
        is_member_of_array_of_objects = False
        if not props.get('calculatedProperty', False):
            if 'submit4dn' not in props.get('exclude_from', [""]):
                if is_subobject(props):
                    if get_field_type(props).startswith('array'):
                        is_member_of_array_of_objects = True
                    fields.extend(build_field_list(props['items']['properties'],
                                                   required_fields,
                                                   include_description,
                                                   include_comment,
                                                   include_enums,
                                                   name,
                                                   is_member_of_array_of_objects)
                                  )
                else:
                    field_name = dotted_field_name(name, parent)
                    if required_fields is not None:
                        if field_name in required_fields:
                            field_name = '*' + field_name
                    field_type = get_field_type(props)
                    if is_submember:
                        field_type = "array of embedded objects, " + field_type
                    desc = '' if not include_description else props.get('description', '')
                    comm = '' if not include_comment else props.get('comment', '')
                    enum = '' if not include_enums else props.get('enum', '')
                    # if array of string with enum
                    if field_type == "array of strings":
                        sub_props = props.get('items', '')
                        enum = '' if not include_enums else sub_props.get('enum', '')
                    # copy paste exp set for ease of keeping track of different types in experiment objects
                    fields.append(FieldInfo(field_name, field_type, desc, comm, enum))
    return fields


def get_uploadable_fields(connection, types, include_description=False,
                          include_comments=False, include_enums=False):
    fields = {}
    for name in types:
        schema_name = name + '.json'
        uri = '/profiles/' + schema_name
        schema_grabber = fdnDCIC.FDN_Schema(connection, uri)
        required_fields = schema_grabber.required
        fields[name] = build_field_list(schema_grabber.properties,
                                        required_fields,
                                        include_description,
                                        include_comments,
                                        include_enums)
        if name.startswith('Experiment') and not name.startswith('ExperimentSet'):
            fields[name].extend(exp_set_addition)
    return fields


def create_xls(all_fields, filename):
    '''
    fields being a dictionary of sheet -> FieldInfo(objects)
    create one sheet per dictionary item, with three columns of fields
    for fieldname, description and enum
    '''
    wb = xlwt.Workbook()
    for obj_name, fields in all_fields.items():
        ws = wb.add_sheet(obj_name)
        ws.write(0, 0, "#Field Name:")
        ws.write(1, 0, "#Field Type:")
        ws.write(2, 0, "#Description:")
        ws.write(3, 0, "#Additional Info:")
        for col, field in enumerate(fields):
            ws.write(0, col+1, str(field.name))
            ws.write(1, col+1, str(field.ftype))
            if field.desc:
                ws.write(2, col+1, str(field.desc))
            # combine comments and Enum
            add_info = ''
            if field.comm:
                add_info += str(field.comm)
            if field.enum:
                add_info += "Choices:" + str(field.enum)
            if not field.comm and not field.enum:
                add_info = "-"
            ws.write(3, col+1, add_info)
    wb.save(filename)


def main():  # pragma: no cover
    args = getArgs()
    key = fdnDCIC.FDN_Key(args.keyfile, args.key)
    if key.error:
        sys.exit(1)
    connection = fdnDCIC.FDN_Connection(key)
    connection = fdnDCIC.FDN_Connection(key)
    # test connection
    if not connection.check:
        print("CONNECTION ERROR: Please check your keys.")
        return
    fields = get_uploadable_fields(connection, args.type,
                                   args.descriptions,
                                   args.comments,
                                   args.enums)

    if args.debug:
        print("retrieved fields as")
        from pprint import pprint
        pprint(fields)

    if args.writexls:
        file_name = args.outfile
        create_xls(fields, file_name)
        if args.order:
            fdnDCIC.order_FDN(file_name, connection)

if __name__ == '__main__':
    main()
