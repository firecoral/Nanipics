from   werkzeug.utils import redirect
from   werkzeug.wrappers import Response

import db.Db as Db
from   db.Exceptions import SupportSessionExpired
import db.Statics as Statics
from   db.Support import SupportSession
from   p.DRequest import DRequest
from   p.DTemplate import DTemplate

def application(environ, start_response):
    """Delete product_designs."""

    request = DRequest(environ)

    try:
        Db.start_transaction()
        support = SupportSession(key=request.support_key())
        t = DTemplate(request, 'product_components_delete.html')
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

