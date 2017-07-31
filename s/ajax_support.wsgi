# $Header: //depot/cs/s/ajax_support.wsgi#10 $
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired
import db.Db as Db
import db.Support

import cgi
import simplejson as json

def application(environ, start_response):
    """AJAX scripts for email templates."""

    request = DRequest(environ)

    resp = None

    try :
        Db.start_transaction()
        form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
        args = form['args'].value
        req = json.loads(args)

        support = SupportSession(key=request.support_key())
        handler = handlers[req['command']]
        resp = Response(json.dumps(handler(request, req)))
        Db.finish_transaction()

    except SupportSessionExpired:
        Db.cancel_transaction()
        resp = Response(json.dumps({ 'Error': 'Session Expired' }))
    except DbError as e:
        Db.cancel_transaction()
        resp = Response(json.dumps({ 'Error': e.args[0]}))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps({ 'Error': "Internal Error"}))

    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'application/json'
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)


def get(request, req):
    return db.Support.get_all()

def edit(request, req):
    return db.Support.edit(req);

def delete(request, req):
    return db.Support.delete(req['support_id'])

def add(request, req):
    return db.Support.new()


handlers = { 'get': get, 'edit': edit, 'delete': delete, 'add': add }

