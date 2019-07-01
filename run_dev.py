from gevent import monkey
monkey.patch_all(thread=False)

import sys
import os

from werkzeug.serving import WSGIRequestHandler
from flask import render_template

from pcgserver.app import create_app
from pychunkedgraph.api import testing

app = create_app()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':

    HOME = os.path.expanduser("~")

    port = 4000
    if len(sys.argv) == 2:
        port = int(sys.argv[1])

    # Set HTTP protocol
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    # WSGIRequestHandler.protocol_version = "HTTP/2.0"

    print("Table: %s; Port: %d" %
          (app.config['CHUNKGRAPH_TABLE_ID'], port))

    app.run(host='0.0.0.0',
            port=port,
            debug=True,
            threaded=False,
            ssl_context='adhoc')