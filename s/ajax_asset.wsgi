import cgi
import simplejson as json
from   werkzeug.wrappers import Response

import db.Asset as Asset
import db.Db as Db
from   db.Exceptions import SupportSessionExpired
from   db.Support import SupportSession
from   p.DRequest import DRequest

def application(environ, start_response):
    """AJAX script to replace assets."""

    content_type = 'application/json'
    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)

    try:
        Db.start_transaction()
        support = SupportSession(key=request.support_key())
        ra_rv = Asset.replace_asset(form['files[]'].filename, form['files[]'].file.read())
        if 'Error' in ra_rv: ra_rv['error'] = 'error'
        resp = Response(json.dumps([ra_rv]))
        Db.finish_transaction()
    except SupportSessionExpired:
        Db.cancel_transaction()
        resp = Response(json.dumps([{'error': 'error', 'Error': 'Session Expired', 'old_afile': form['files[]'].filename}]))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps([{'error': 'error', 'Error': 'Internal Error', 'old_afile': form['files[]'].filename}]))

    request.cookie_freshen(resp)
    resp.headers['content-type'] = content_type
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

