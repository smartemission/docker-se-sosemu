import os, sys
from functools import wraps, update_wrapper
from datetime import datetime
from flask import Flask, render_template, request, make_response
from reverseproxied import ReverseProxied

if __name__ != '__main__':
    # When run with WSGI in Apache we need to extend the PYTHONPATH to find Python modules relative to index.py
    sys.path.insert(0, os.path.dirname(__file__))

from postgis import PostGIS
from config import config

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.debug = True
application = app


# Wrapper to disable any kind of caching for all pages
# See http://arusahni.net/blog/2014/03/flask-nocache.html
def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = datetime.now()
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return update_wrapper(no_cache, view)


# Shorthand to get stations array from DB
def get_stations():
    # Do query from DB
    db = PostGIS(config)
    return db.do_query('SELECT * from v_cur_stations', 'v_cur_stations')


# Shorthand to get (last values) array from DB
def get_last_values(station):
    # Do query from DB
    db = PostGIS(config)

    # Default is to get all current measurements
    query = 'SELECT * from v_cur_measurements'
    if station:
        # stations = station.split(',')

        # Last measurements for single station
        query = query + ' WHERE device_id = ' + station

        # May have provided multiple comma-separated stations
        # if len(stations) > 1:
        #     for i in range(1, len(stations)-1):
        #         query = query + ' OR device_id = ' + stations[i]
    return db.do_query(query, 'v_cur_measurements')

# Shorthand to create proper JSON HTTP response
def make_json_response(json_doc):
    response = make_response(json_doc)
    response.headers["Content-Type"] = "application/json"
    return response

# Shorthand to create proper JSONP HTTP response
def make_jsonp_response(json_doc, callback):
    # TODO: make smart wrapper: http://flask.pocoo.org/snippets/79/
    json_doc = str(callback) + '(' + json_doc + ')'
    response = make_response(json_doc)
    response.headers["Content-Type"] = "application/javascript"
    return response


# Home page
@app.route('/')
@nocache
def home():
    return render_template('home.html')


# Get list of all stations with locations (as JSON or HTML)
@app.route('/api/v1/stations')
@nocache
def stations():
    # Fetch stations from DB
    stations_list = get_stations()

    # Determine response format: JSON (default) or HTML
    format = request.args.get('format', 'json')
    if format == 'html':
        return render_template('stations.html', stations=stations_list)
    else:
        # Construct JSON response: JSON doc via Jinja2 template with JSON content type
        json_doc = render_template('stations.json', stations=stations_list)

        # To enable X-domain: JSONP with callback
        # TODO: make smart wrapper: http://flask.pocoo.org/snippets/79/
        jsonp_cb = request.args.get('callback', False)
        if jsonp_cb:
            return make_jsonp_response(json_doc, jsonp_cb)
        else:
            return make_json_response(json_doc)



# Get last values for single station  (as JSON or HTML)
# Example: /api/v1/timeseries?station=23&expanded=true
@app.route('/api/v1/timeseries')
@nocache
def timeseries(package=None):
    # Get last values, all or for single station if 'station=' arg in query string
    last_values = get_last_values(request.args.get('station', None))

    # Determine response format: JSON (default) or HTML
    format = request.args.get('format', 'json')
    if format == 'html':
        return render_template('timeseries.html', last_values=last_values)
    else:
        # Construct JSON response: JSON doc via Jinja2 template with JSON content type
        json_doc = render_template('timeseries.json', last_values=last_values)

        # To enable X-domain: JSONP with callback
        # TODO: make smart wrapper: http://flask.pocoo.org/snippets/79/
        jsonp_cb = request.args.get('callback', False)
        if jsonp_cb:
            return make_jsonp_response(json_doc, jsonp_cb)
        else:
            return make_json_response(json_doc)


if __name__ == '__main__':
    # Run as main via python index.py
    app.run(debug=True, host='0.0.0.0')
