# $Header: //depot/cs/s/home.wsgi#22 $
from db.Exceptions import SupportSessionExpired
from db.Support import SupportSession
from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import db.Db as Db


def application(environ, start_response):
    """Display a support home page"""

    try :
        Db.start_transaction()
        request = DRequest(environ)
        support = SupportSession(key=request.support_key())
        request.add_vars({ 'username': support.name })
        t = DTemplate(request, 'home.html')
        resp = Response(t.render(request.get_vars()))
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
