import sys
import logging
import os
import time
import json
import datetime

import redis
import numpy as np

from flask import Flask
from flask.logging import default_handler
from flask_cors import CORS
from flask_socketio import SocketIO, send, emit
from rq import Queue

from . import config
from pcgserver.utils import CustomJsonEncoder
from pcgserver.app.blueprints import index, segmentation, meshing
from pcgserver.logging import jsonformatter

os.environ['TRAVIS_BRANCH'] = "IDONTKNOWWHYINEEDTHIS"
socketio = SocketIO()


@socketio.on('test1')
def test(data):
    print('########## Received ' + str(data))


@socketio.on('connect')
def test():
    print('########## connected!')
    emit('test2', {'data':'kablooey'})


def create_app(test_config=None):
    template_dir = os.path.abspath('../templates')
    app = Flask(__name__)
    app.json_encoder = CustomJsonEncoder
    app.sio = socketio

    CORS(app, expose_headers='WWW-Authenticate')

    configure_app(app)

    if test_config is not None:
        app.config.update(test_config)

    # register blueprints
    app.register_blueprint(index.bp)
    app.register_blueprint(segmentation.bp)
    app.register_blueprint(meshing.bp)

    with app.app_context():
        if app.config['USE_REDIS_JOBS']:
            socketio.init_app(app,
                            message_queue=app.config['REDIS_URL'],
                            logger=True,
                            engineio_logger=True,
                            channel='socktest')

    return app


def configure_app(app):
    # Load logging scheme from config.py
    app_settings = os.getenv('APP_SETTINGS')
    if not app_settings:
        app.config.from_object(config.BaseConfig)
    else:
        app.config.from_object(app_settings)


    # Configure logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(app.config['LOGGING_LEVEL'])
    formatter = jsonformatter.JsonFormatter(
        fmt=app.config['LOGGING_FORMAT'],
        datefmt=app.config['LOGGING_DATEFORMAT'])
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    app.logger.removeHandler(default_handler)
    app.logger.addHandler(handler)
    app.logger.setLevel(app.config['LOGGING_LEVEL'])
    app.logger.propagate = False

    if app.config['USE_REDIS_JOBS']:
        app.redis = redis.Redis.from_url(app.config['REDIS_URL'])
        app.test_q = Queue('test' ,connection=app.redis)