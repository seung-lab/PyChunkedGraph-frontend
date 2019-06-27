import sys
import os

from werkzeug.serving import WSGIRequestHandler
from flask import render_template

from pcgserver.app import create_app

app = create_app()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':

    assert len(sys.argv) == 2
    HOME = os.path.expanduser("~")

    port = int(sys.argv[1])

    # Set HTTP protocol
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    # WSGIRequestHandler.protocol_version = "HTTP/2.0"

    print("Table: %s; Port: %d" %
          (app.config['CHUNKGRAPH_TABLE_ID'], port))

    app.run(host='0.0.0.0',
            port=port,
            debug=True,
            threaded=True,
            ssl_context='adhoc')