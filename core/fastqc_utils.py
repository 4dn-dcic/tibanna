import uuid

###########################################
# These utils exclusively live in Tibanna #
###########################################

def number(astring):
    try:
        num = float(astring)
        if num % 1 == 0:
            num = int(num)
        return num
    except:
        return astring


def parse_qc_table(data_list, qc_schema, url=None):
    """ Return a quality_metric metadata dictionary
    given a list of qc table file dumps (data_list),
    url for the report html and
    quality_metric property as a dictionary
    """
    qc_json = {}
    for data in data_list:
        for line in data.split('\n'):
            a = line.strip().split('\t')
            try:
                if a[0] in qc_schema and qc_schema.get(a[0]).get('type') == 'string':
                    qc_json.update({a[0]: str(a[1])})
                elif a[0] in qc_schema and qc_schema.get(a[0]).get('type') == 'number':
                    qc_json.update({a[0]: number(a[1].replace(',', ''))})
                if a[1] in qc_schema and qc_schema.get(a[1]).get('type') == 'string':
                    qc_json.update({a[1]: str(a[0])})
                elif a[1] in qc_schema and qc_schema.get(a[1]).get('type') == 'number':
                    qc_json.update({a[1]: number(a[0].replace(',', ''))})
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

    return(qc_json)


def determine_overall_status(qc_json):
    """Currently PASS no matter what """
    qc_json.update({'overall_quality_status': 'PASS'})
    return(qc_json)
