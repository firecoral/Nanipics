from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Exceptions import DbError, DbKeyInvalid, CartInvalid
import db.Db as Db
import db.Cart as Cart

import cgi
import p.DJSON as json

ecom_session = None

def application(environ, start_response):
    "AJAX script for order status queries."

    content_type = 'application/json'
    request = DRequest(environ)
    resp = None

    try:
        Db.start_transaction()
        form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
        args = form['args'].value
        req = json.loads(args)

        cart_id = req.get('cart_id', None)
        last_name = req.get('last_name', None)
        zip_code = req.get('zip_code', None)
        if cart_id and (last_name or zip_code):
            Cart.find_cart(cart_id, last_name, zip_code)
            cart = Cart.ShoppingCart(cart_id=cart_id)
            resp = Response(json.dumps(cart.order_status()))
        else:
            resp = Response(json.dumps({ 'IncompleteData': True }))

        Db.finish_transaction()
    except CartInvalid as e:
        Db.finish_transaction()
        resp = Response(json.dumps({ 'Error': "Could not find order.  Please check the information provided" }))
    except DbKeyInvalid as e:
        Db.finish_transaction()
        resp = Response(json.dumps(error(e.args[0])))
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


def error(str):
    return { 'Error': str }

