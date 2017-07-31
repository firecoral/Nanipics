# $Header: //depot/cs/s/pd_browser.wsgi#3 $
from db.Support import SupportSession
from db.Exceptions import DbKeyInvalid, SupportSessionExpired
from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import p.DJSON as json
import db.Db as Db
import db.Cart as Cart
import db.Product as Product
import cgi


def application(environ, start_response):
    """Product Design Browser"""

    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ) 

    try :
        Db.start_transaction()
        support = SupportSession(key=request.support_key())
	pi_groups = Product.pi_group_browser()
	request.add_vars({ 'pi_design_groups': json.dumps(pi_groups['pi_design_groups']) })
	request.add_vars({ 'pi_product_groups': json.dumps(pi_groups['pi_product_groups']) })

        t = DTemplate(request, 'pd_browser.html')
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
