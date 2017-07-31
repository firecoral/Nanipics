# $Header: //depot/cs/s/cart.wsgi#22 $
from db.Support import SupportSession
from db.Exceptions import DbKeyInvalid, SupportSessionExpired
from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import p.DJSON as json
import db.Db as Db
import db.Cart as Cart
import db.Statics as Statics
import cgi


def application(environ, start_response):
    """Display a cart summary"""

    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ) 

    try :
        Db.start_transaction()
        support = SupportSession(key=request.support_key())
        if 'cart_id' not in form:
            raise DbKeyInvalid("Missing cart_id");
        cart_id = form['cart_id'].value
        cart = Cart.ShoppingCart(cart_id=cart_id)

        request.add_vars({ 'cart_id': cart_id })

        if 'review' in form:
            request.add_vars({ 'review': "true" })
        else:
            request.add_vars({ 'review': "false" })

        taxes = Statics.taxes.get()
        request.add_vars({ 'taxes_json': json.dumps(taxes) })
        shippings = Statics.shippings.get()
        request.add_vars({ 'shippings_json': json.dumps(shippings) })

        t = DTemplate(request, 'cart.html')
        resp = Response(t.render(request.get_vars()))
        Db.finish_transaction()
    except SupportSessionExpired:
        Db.cancel_transaction()
        resp = redirect('/s/login', 307)
        return resp(environ, start_response)
    except DbKeyInvalid as e:
        Db.cancel_transaction()
        t = DTemplate(request, 'error.html')
        resp =  Response(t.render({'message': e.args[0]}))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        t = DTemplate(request, 'error.html')
        resp =  Response(t.render({'message': 'Internal Error'}))

    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'text/html; charset=utf-8'
    resp.headers['content-length'] = len(resp.data)

    return resp(environ, start_response)
