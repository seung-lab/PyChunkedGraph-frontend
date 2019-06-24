from flask import Blueprint, request, make_response, jsonify, current_app,\
    redirect, url_for, after_this_request, Response

import json
import numpy as np
import time
from datetime import datetime
from pytz import UTC
import traceback
import collections
import requests
import threading

from pcgserver.app import app_utils, meshing_app_blueprint
from pychunkedgraph.backend import chunkedgraph_exceptions as cg_exceptions, \
    chunkedgraph_comp as cg_comp
from pychunkedgraph.api import segmentation
from middle_auth_client import auth_required, auth_requires_roles

__version__ = 'fafb.1.2'
bp = Blueprint('pcgserver', __name__, url_prefix="/segmentation")

# -------------------------------
# ------ Access control and index
# -------------------------------


@bp.route('/')
@bp.route("/index")
def index():
    return "PyChunkedGraph Server -- " + __version__


@bp.route
def home():
    resp = make_response()
    resp.headers['Access-Control-Allow-Origin'] = '*'
    acah = "Origin, X-Requested-With, Content-Type, Accept"
    resp.headers["Access-Control-Allow-Headers"] = acah
    resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    resp.headers["Connection"] = "keep-alive"
    return resp


# -------------------------------
# ------ Measurements and Logging
# -------------------------------

@bp.before_request
def before_request():
    current_app.request_start_time = time.time()
    current_app.request_start_date = datetime.utcnow()


@bp.after_request
def after_request(response):
    dt = (time.time() - current_app.request_start_time) * 1000

    current_app.logger.debug("Response time: %.3fms" % dt)

    try:
        log_db = app_utils.get_log_db(current_app.table_id)
        log_db.add_success_log(user_id="", user_ip="",
                               request_time=current_app.request_start_date,
                               response_time=dt, url=request.url,
                               request_data=request.data,
                               request_type=current_app.request_type)
    except:
        current_app.logger.debug("LogDB entry not successful")

    return response


@bp.errorhandler(Exception)
def unhandled_exception(e):
    status_code = 500
    response_time = (time.time() - current_app.request_start_time) * 1000
    user_ip = str(request.remote_addr)
    tb = traceback.format_exception(etype=type(e), value=e,
                                    tb=e.__traceback__)

    current_app.logger.error({
        "message": str(e),
        "user_id": user_ip,
        "user_ip": user_ip,
        "request_time": current_app.request_start_date,
        "request_url": request.url,
        "request_data": request.data,
        "response_time": response_time,
        "response_code": status_code,
        "traceback": tb
    })

    resp = {
        'timestamp': current_app.request_start_date,
        'duration': response_time,
        'code': status_code,
        'message': str(e),
        'traceback': tb
    }

    return jsonify(resp), status_code


@bp.errorhandler(cg_exceptions.ChunkedGraphAPIError)
def api_exception(e):
    response_time = (time.time() - current_app.request_start_time) * 1000
    user_ip = str(request.remote_addr)
    tb = traceback.format_exception(etype=type(e), value=e,
                                    tb=e.__traceback__)

    current_app.logger.error({
        "message": str(e),
        "user_id": user_ip,
        "user_ip": user_ip,
        "request_time": current_app.request_start_date,
        "request_url": request.url,
        "request_data": request.data,
        "response_time": response_time,
        "response_code": e.status_code.value,
        "traceback": tb
    })

    resp = {
        'timestamp': current_app.request_start_date,
        'duration': response_time,
        'code': e.status_code.value,
        'message': str(e)
    }

    return jsonify(resp), e.status_code.value


# -------------------
# ------ Applications
# -------------------


@bp.route("/sleep/<int:sleep>")
def sleep_me(sleep):
    current_app.request_type = "sleep"

    time.sleep(sleep)
    return "zzz... {} ... awake".format(sleep)


@bp.route('/1.0/<table_id>/info', methods=['GET'])
def handle_info(table_id):
    current_app.request_type = "info"

    cg = app_utils.get_cg(table_id)

    return jsonify(cg.dataset_info)


@bp.route('/1.0/<table_id>/graph/root', methods=['POST', 'GET'])
def handle_root_1(table_id):
    atomic_id = np.uint64(json.loads(request.data)[0])

    # Convert seconds since epoch to UTC datetime
    try:
        timestamp = float(request.args.get('timestamp', time.time()))
        timestamp = datetime.fromtimestamp(timestamp, UTC)
    except (TypeError, ValueError) as e:
        raise(cg_exceptions.BadRequest("Timestamp parameter is not a valid"
                                       " unix timestamp"))

    return handle_root_main(table_id, atomic_id, timestamp)


@bp.route('/1.0/<table_id>/graph/<atomic_id>/root', methods=['POST', 'GET'])
def handle_root_2(table_id, atomic_id):

    # Convert seconds since epoch to UTC datetime
    try:
        timestamp = float(request.args.get('timestamp', time.time()))
        timestamp = datetime.fromtimestamp(timestamp, UTC)
    except (TypeError, ValueError) as e:
        raise(cg_exceptions.BadRequest("Timestamp parameter is not a valid"
                                       " unix timestamp"))

    return handle_root_main(table_id, np.uint64(atomic_id), timestamp)


def handle_root_main(table_id, atomic_id, timestamp):
    current_app.request_type = "root"

    cg = app_utils.get_cg(table_id)
    root_id = cg.get_root(np.uint64(atomic_id), time_stamp=timestamp)

    return app_utils.tobinary(root_id)


@bp.route('/1.0/<table_id>/graph/merge', methods=['POST', 'GET'])
@auth_requires_roles('edit_all')
def handle_merge(table_id):
    current_app.request_type = "merge"

    nodes = json.loads(request.data)
    user_id = str(g.auth_user['id'])

    current_app.logger.debug(nodes)
    assert len(nodes) == 2

    cg = app_utils.get_cg(table_id)
    new_root = segmentation.merge(cg, nodes, user_id)

    return app_utils.tobinary(new_root)


@bp.route('/1.0/<table_id>/graph/split', methods=['POST', 'GET'])
@auth_requires_roles('edit_all')
def handle_split(table_id):
    current_app.request_type = "split"

    data = json.loads(request.data)
    user_id = str(g.auth_user['id'])

    current_app.logger.debug(data)

    # Call ChunkedGraph
    cg = app_utils.get_cg(table_id)
    new_roots = segmentation.split(cg, data, user_id)

    return app_utils.tobinary(new_roots)


@bp.route('/1.0/<table_id>/segment/<parent_id>/children',
          methods=['POST', 'GET'])
def handle_children(table_id, parent_id):
    current_app.request_type = "children"

    cg = app_utils.get_cg(table_id)

    parent_id = np.uint64(parent_id)
    children = segmentation.get_children(cg, parent_id)
    
    return app_utils.tobinary(children)


@bp.route('/1.0/<table_id>/segment/<root_id>/leaves', methods=['POST', 'GET'])
def handle_leaves(table_id, root_id):
    current_app.request_type = 'leaves'

    bounds = request.args.get('bounds', None)

    cg = app_utils.get_cg(table_id)
    atomic_ids = segmentation.get_leaf_nodes(cg, root_id, bounds)

    return app_utils.tobinary(atomic_ids)


@bp.route('/1.0/<table_id>/segment/<root_id>/subgraph', methods=['POST', 'GET'])
def handle_subgraph(table_id, root_id):
    current_app.request_type = 'subgraph'

    bounds = request.args.get('bounds', None)

    cg = app_utils.get_cg(table_id)
    atomic_edges = segmentation.get_atomic_edges(cg, root_id, bounds)

    return app_utils.tobinary(atomic_ids)    


@bp.route('/1.0/<table_id>/segment/<root_id>/change_log', methods=['POST', 'GET'])
def change_log(table_id, root_id):
    current_app.request_type = 'change_log'

    cg = app_utils.get_cg(table_id)

    change_log = segmentation.get_change_log(
        cg, root_id,
        float(request.args.get('timestamp', 0)))

    return jsonify(change_log)


@bp.route('/1.0/<table_id>/segment/<root_id>/merge_log',
          methods=["POST", "GET"])
def merge_log(table_id, root_id):
    current_app.request_type = 'merge_log'

    cg = app_utils.get_cg(table_id)

    merge_log = segmentation.get_merge_log(
        cg, root_id,
        float(request.args.get('timestamp', 0)))

    return jsonify(merge_log)


@bp.route('/1.0/<table_id>/segment/<root_id>/contact_sites',
          methods=["POST", "GET"])
def handle_contact_sites(table_id, root_id):
    partners = request.args.get('partners', False)  

    bounding_box = None
    if 'bounds' in request.args:
        bounds = request.args['bounds']
        bounding_box = np.array(
            [b.split('-') for b in bounds.split('_')], dtype=np.int).T
        

    cg = app_utils.get_cg(table_id)

    cs_dict = cg_comp.get_contact_sites(cg, np.uint64(root_id),
                                        bounding_box = bounding_box,
                                        compute_partner=partners)

    return jsonify(cs_dict)