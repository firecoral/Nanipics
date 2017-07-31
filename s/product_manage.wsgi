# $Header: //depot/cs/s/product_manage.wsgi#30 $
from db.Support import SupportSession
import db.Db as Db
import db.Product as Product
import db.Promo as Promo
from db.Exceptions import SupportSessionExpired
from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import db.Statics as Statics
import simplejson as json

def application(environ, start_response):
    """Edit and manage products"""

    request = DRequest(environ)

    try:
        Db.start_transaction()
        support = SupportSession(key = request.support_key())

        request.add_vars({
            'products': json.dumps(Statics.products.get_ids()),
            'orientations': json.dumps(Statics.orientations.get_ids()),
            'labs': json.dumps(Statics.labs.get_ids()),
            'lab_products': json.dumps(Statics.lab_products.get_ids()),
            'CSVPRICECOUNT': Product.CSVPRICECOUNT,
            'promo_categories': Promo.get_promo_categories()['promo_categories']
        })

        t = DTemplate(request, 'product_manage.html')
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
        resp =  Response(t.render({'message': "Internal Error"}))

    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'text/html; charset=utf-8'
    resp.headers['content-length'] = len(resp.data)

    return resp(environ, start_response)
