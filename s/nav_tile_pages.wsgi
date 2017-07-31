# $Header: //depot/cs/s/nav_tile_pages.wsgi#4 $
from db.Exceptions import SupportSessionExpired
from db.Support import SupportSession
from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
from db.NavTilePage import get_landing_pages
import db.Db as Db

def application(environ, start_response):
    """Edit and manage nav tile pages"""

    request = DRequest(environ)

    try :
        Db.start_transaction()
        request.add_vars({ 'landing_pages': get_landing_pages() })
        support = SupportSession(key=request.support_key())
        t = DTemplate(request, 'nav_tile_pages.html')
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
