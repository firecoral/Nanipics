# $Header: //depot/cs/s/ajax.wsgi#17 $
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired
import db.Db as Db

import cgi
import simplejson as json

def application(environ, start_response):
    """Basic ajax scripts for support session management."""

    request = DRequest(environ)

    resp = None

    try:
        Db.start_transaction()
        form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
        args = form['args'].value
        req = json.loads(args)

        handler = handlers[req['command']]
        support = handler(request, req)
        resp = Response(json.dumps({ 'Success': True }))
        if (support != None):
            request.set_support_key(support.column('session_key'))
            #request.client_session['support_key'] = support.column('session_key')
        else:
            #request.client_session['support_key'] = None
            request.set_support_key(None)
        request.cookie_freshen(resp)
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

    resp.headers['content-type'] = 'application/json'
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

def ping(request, req):
    return SupportSession(key=request.support_key())

def login(request, req):
    name = req.get('name', None)
    password = req.get('password', None)
    if (name == None or password == None):
        raise DbError('Please provide a name and password to log in')
    return SupportSession(name=name, password=password)

def logout(request, req):
    try :
        SupportSession(key=request.support_key()).logout()
    except:
        pass

handlers = { 'login': login, 'ping': ping, 'logout': logout }


