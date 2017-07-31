# $Header: //depot/cs/s/ajax_lab_product.wsgi#14 $
from werkzeug.wrappers import Response
import cgi
from p.DRequest import DRequest
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired
import db.Db as Db
import db.Lab as Lab
import db.Statics as Statics

import simplejson as json

def application(environ, start_response):
    """AJAX scripts for product templates."""

    content_type = 'application/json'
    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ) 

    try :
        Db.start_transaction()
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
    resp.headers['content-type'] = content_type
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

# Functions for lab product manager

def get(request, req):
    return { 'lab_products': Statics.lab_products.get() }

def edit(request, req):
    return Lab.edit(req);

# Functions for the shipping cost table
def shipping_cost_edit(request, req):
    return Lab.shipping_cost_edit(req);

# Functions for shipping testing

def shipping_test(request, req):
    return Lab.shipping_compute(req['shipping_classes'], "CA")

handlers = { 'get': get, 'edit': edit, 'shipping_cost_edit': shipping_cost_edit,
             'shipping_test': shipping_test }

