# $Header: //depot/cs/s/nav_tiles.wsgi#2 $
from db.Exceptions import SupportSessionExpired
from db.Support import SupportSession
from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import db.Db as Db
import db.Statics as Statics
from db.NavTilePage import get_landing_pages
import cgi

def application(environ, start_response):
    """Edit and manage nav tiles"""

    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ) 

    try :
        Db.start_transaction()
        support = SupportSession(key=request.support_key())
        if 'ntp_id' not in form:
            raise DbKeyInvalid("Missing Nav Tile Page");
	ntp = Statics.nav_tile_pages.get_id(int(form['ntp_id'].value))
        request.add_vars({ 'nav_tile_page_id': ntp['nav_tile_page_id'] })
        request.add_vars({ 'page_name': ntp['name'] })
        request.add_vars({ 'landing_pages': get_landing_pages() })

        t = DTemplate(request, 'nav_tiles.html')
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
