import datetime
import json
import time
from uuid import uuid4
import random
import os
from wranglertools import fdnDCIC


### COME BACK TO
def patch_metadata(patch_item, obj_id='', key='', connection=None, url_addon=None):
    '''
    obj_id can be uuid or @id for most object
    '''

    connection = fdn_connection(key, connection)

    obj_id = obj_id if obj_id else patch_item['uuid']

    try:
        response = fdnDCIC.patch_FDN(obj_id, connection, patch_item, url_addon=url_addon)

        if response.get('status') == 'error':
            raise Exception("error %s \n unable to patch obj: %s \n with  data: %s" %
                            (response, obj_id, patch_item))
    except Exception as e:
        raise Exception("error %s \nunable to patch object %s \ndata: %s" % (e, obj_id, patch_item))
    return response

### COME BACK TO
def get_metadata(obj_id, key='', connection=None, frame="object"):
    # default to always get from database
    try:
        connection = fdn_connection(key, connection)
    except Exception as e:
        raise FdnConnectionException("%s" % e)
    sleep = [2, 4, 6]
    for wait in sleep:
        try:
            res = fdnDCIC.get_FDN(obj_id, connection, frame=frame, url_addon='?datastore=database')
        except:
            time.sleep(wait)
            continue

        if 'error' in res.get('@type', []):
            time.sleep(wait)
            continue
        else:
            return res
    # if loop did not solve the problem
    print('get_metdata is not working for', obj_id)
    return

### COME BACK TO
def post_to_metadata(post_item, schema_name, key='', connection=None):
    connection = fdn_connection(key, connection)
    if schema_name == 'file_processed':
        url_addon = '?force_md5'
    else:
        url_addon = None
    try:
        response = fdnDCIC.new_FDN(connection, schema_name, post_item, url_addon=url_addon)
        if (response.get('status') == 'error' and response.get('detail') == 'UUID conflict'):
            # item already posted lets patch instead
            response = patch_metadata(post_item, connection=connection, url_addon=url_addon)
        elif response.get('status') == 'error':
            raise Exception("error %s \n unable to post data to schema %s, data: %s" %
                            (response, schema_name, post_item))
    except Exception as e:
        raise Exception("error %s \nunable to post data to schema %s, data: %s" %
                        (e, schema_name, post_item))
    return response

### COME BACK TO
def delete_field(post_json, del_field, connection=None):
    """Does a put to delete the given field."""
    # make sure we get from database
    url_addon = '&datastore=database'
    my_uuid = post_json.get("uuid")
    my_accession = post_json.get("accesion")
    raw_json = fdnDCIC.get_FDN(my_uuid, connection, frame="raw", url_addon=url_addon)
    # check if the uuid is in the raw_json
    if not raw_json.get("uuid"):
        raw_json["uuid"] = my_uuid
    # if there is an accession, add it to raw so it does not created again
    if my_accession:
        if not raw_json.get("accession"):
            raw_json["accession"] = my_accession
    # remove field from the raw_json
    if raw_json.get(del_field):
        del raw_json[del_field]
    # Do the put with raw_json
    try:
        response = fdnDCIC.put_FDN(my_uuid, connection, raw_json)
        if response.get('status') == 'error':
            raise Exception("error %s \n unable to delete field: %s \n of  item: %s" %
                            (response, del_field, my_uuid))
    except Exception as e:
        raise Exception("error %s \n unable to delete field: %s \n of  item: %s" %
                        (e, del_field, my_uuid))
    return response
