# $Header: //depot/cs/s/csv_upload.wsgi#8 $
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Support import SupportSession
from db.Exceptions import SupportSessionExpired


import simplejson as json
import cgi

def application(environ, start_response):
    """Basic ajax scripts for support session management."""

    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)

    try:
        if 'files[]' in form:
            filename = form['files[]'].filename
            filehndl = form['files[]'].file
        foo = filehndl.read()
        resp = Response(json.dumps({ 'Success': True }))
        request.cookie_freshen(resp)
    except SupportSessionExpired:
        resp = Response(json.dumps({ 'Error': "Session Expired" }))
    except Exception as e:
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps({ 'Error': 'Internal Error'}))

    resp.headers['content-type'] = 'application/json'
    return resp(environ, start_response)

