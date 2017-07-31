from werkzeug.wrappers import Response
import cgi
from p.DRequest import DRequest
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired, ZipImportError
import db.Db as Db
import db.ZipImport as ZipImport
import db.Product as Product
import db.Statics as Statics

import simplejson as json

def application(environ, start_response):
    """AJAX scripts for product designs."""

    content_type = 'application/json'
    error = normal_error
    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ) 

    try:
        Db.start_transaction()
        # If this is a file upload, do additional setup, otherwise
        # treat as a normal get/post.
        if 'files[]' in form:
            content_type = 'text/html; charset=utf-8'
            error = uploader_error
            req = {
                'command': 'import_design',
                'filename': form['files[]'].filename,
                'f': form['files[]'].file
            }
        elif 'args' in form:
            args = form['args'].value
            req = json.loads(args)

        support = SupportSession(key=request.support_key())
        handler = handlers[req['command']]
        resp = Response(json.dumps(handler(request, req)))
        Db.cache_invalidate()
        Db.finish_transaction()

    except SupportSessionExpired:
        Db.cancel_transaction()
        resp = Response(json.dumps(error('Session Expired')))
    except ZipImportError as e:
        Db.cancel_transaction()
        resp = Response(json.dumps(error('Import Error', long_error=e.args[0], filename=req['filename'])))
    except DbError as e:
        Db.cancel_transaction()
        resp = Response(json.dumps(error(e.args[0])))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps(error('Internal Error')))

    request.cookie_freshen(resp)
    resp.headers['content-type'] = content_type
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

def import_design(request, req):
    ZipImport.import_zip(
        req['f']
    )
    return [{'filename': req['filename']}]

handlers = { 'import_design': import_design }

def normal_error(str, long_error=None, filename=None):
    rv = { 'Error': str }
    if long_error != None: rv['long_error'] = long_error
    if filename != None: rv['filename'] = filename
    return rv

def uploader_error(str, long_error=None, filename=None):
    # Note that we have to return an array here (to support multi-file upload).
    rv = [{ 'error': str }]
    if long_error != None: rv[0]['long_error'] = long_error
    if filename != None: rv[0]['filename'] = filename
    return rv

