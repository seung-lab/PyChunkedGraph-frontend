from flask import current_app
from google.auth import credentials, default as default_creds
from google.cloud import bigtable, datastore

import sys
import numpy as np
import logging
import time
import functools
import json
import datetime

import redis

from pcgserver.logging import jsonformatter, flask_log_db
from pychunkedgraph.backend import chunkedgraph
from pychunkedgraph.utils.cg_utils import get_cg as get_cg_instance

cache = {}


class DoNothingCreds(credentials.Credentials):
    def refresh(self, request):
        pass


class CustomJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, datetime.datetime):
            return obj.__str__()
        return json.JSONEncoder.default(self, obj)        


def get_cg(table_id):
    assert table_id.startswith("fly")

    if table_id not in cache:
        cache[table_id] = get_cg_instance(current_app.config, table_id = table_id)
    
    current_app.table_id = table_id
    return cache[table_id]


def get_log_db(table_id):
    if 'log_db' not in cache:
        client = get_datastore_client(current_app.config)
        cache["log_db"] = flask_log_db.FlaskLogDatabase(table_id,
                                                        client=client)

    return cache["log_db"]


def tobinary(ids):
    """ Transform id(s) to binary format

    :param ids: uint64 or list of uint64s
    :return: binary
    """
    return np.array(ids).tobytes()


def tobinary_multiples(arr):
    """ Transform id(s) to binary format

    :param arr: list of uint64 or list of uint64s
    :return: binary
    """
    return [np.array(arr_i).tobytes() for arr_i in arr]