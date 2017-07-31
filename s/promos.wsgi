# $Header: //depot/cs/s/promos.wsgi#2 $
from db.Exceptions import SupportSessionExpired
from db.Support import SupportSession
from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import db.Db as Db
import db.Promo as Promo
import db.Statics as Statics

def application(environ, start_response):
    """Edit and manage promos"""

    request = DRequest(environ)

    try :
        Db.start_transaction()
        support = SupportSession(key=request.support_key())

        products = []
        for product in Statics.products.get():
            products.append({
                'product_id': product['product_id'],
                'name': product['name']
            })
        request.add_vars({
            'products': products,
            'promo_categories': Promo.get_promo_categories()['promo_categories']
        })

        t = DTemplate(request, 'promos.html')
        resp =  Response(t.render(request.get_vars()))
        Db.finish_transaction()
    except SupportSessionExpired:
        Db.cancel_transaction()
        resp = redirect('/s/login', 307)
        return resp(environ, start_response)
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


