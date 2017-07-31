# $Header: //depot/cs/s/search.wsgi#5 $
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
        if 'search_type' not in form:
            raise DbKeyInvalid("Missing search type");

        search_type = form['search_type'].value
        if search_type == "search": 
            if 'search_str' not in form:
                raise DbKeyInvalid("Missing search string");
            search_str = form['search_str'].value
            search = Cart.Search(search_str=search_str)

            request.add_vars({
                'list_type': "Search Result",
                'carts': search.carts()
            })
        elif search_type == "review": 
            carts = Cart.get_review()

            request.add_vars({
                'list_type': "Carts Awaiting Review",
                'review': '&review=1',
                'carts': carts
            })
        elif search_type == "manual": 
            carts = Cart.get_manual_hold()

            request.add_vars({
                'list_type': "Manually Held Carts",
                'carts': carts
            })
        elif search_type == "recent_complete": 
            carts = Cart.get_recent_complete(30)

            request.add_vars({
                'list_type': "Recently Completed Carts (last 30 days)",
                'carts': carts
            })
        else:
            raise DbKeyInvalid("Missing search type");

        t = DTemplate(request, 'search.html')
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
