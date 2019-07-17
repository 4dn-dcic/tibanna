import uuid
from tibanna.utils import printlog

###########################################
# These utils exclusively live in Tibanna #
###########################################


def number(astring):
    """Convert a string into a float or integer

    Returns original string if it can't convert it.
    """
    try:
        num = float(astring)
        if num % 1 == 0:
            num = int(num)
        return num
    except ValueError:
        return astring


def parse_qc_table(data_list, qc_schema, url=None):
    """ Return a quality_metric metadata dictionary
    given a list of qc table file dumps (data_list),
    url for the report html and
    quality_metric property as a dictionary
    """
    qc_json = {}

    def parse_item(name, value):
        """Add item to qc_json if it's in the schema"""
        printlog("qc item : %s = %s" % (name, str(value)))
        qc_type = qc_schema.get(name, {}).get('type', None)
        if qc_type == 'string':
            qc_json.update({name: str(value)})
        elif qc_type == 'number':
            qc_json.update({name: number(value.replace(',', ''))})
        printlog("qc json : %s" % str(qc_json))

    for data in data_list:
        print(type(data))
        for line in data.split('\n'):
            items = line.strip().split('\t')
            # flagstat qc handling - e.g. each line could look like "0 + 0 blah blah blah"
            space_del = line.strip().split(' ')
            flagstat_items = [' '.join(space_del[0:3]), ' '.join(space_del[3:])]
            try:
                parse_item(items[0], items[1])
                parse_item(items[1], items[0])
                parse_item(flagstat_items[1], flagstat_items[0])
            except IndexError:  # pragma: no cover
                # maybe a blank line or something
                pass

    # overall quality status
    # (do this before uuid, lab & award, so we'll use only quality
    # metric to determind this. (e.g. if all PASS then PASS))
    qc_json = determine_overall_status(qc_json)

    # add uuid, lab & award
    qc_json.update({"award": "1U01CA200059-01",
                    "lab": "4dn-dcic-lab",
                    "uuid": str(uuid.uuid4())})
    if url:
        qc_json.update({"url": url})

    return qc_json


def determine_overall_status(qc_json):
    """Currently PASS no matter what """
    qc_json.update({'overall_quality_status': 'PASS'})
    return qc_json
