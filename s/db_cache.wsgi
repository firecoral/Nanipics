# $Header: //depot/cs/s/db_cache.wsgi#13 $
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired
from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import db.Db as Db

def application(environ, start_response):
    """Display a dump of the database cache for support users."""

    request = DRequest(environ)

    try :
        Db.start_transaction()
        support = SupportSession(key=request.support_key())
        db_pretty = {}
        for key, cache in Db.cached_objects.iteritems():
            db_pretty[key] = cache.get_pretty()
        request.add_vars({ 'db_pretty': db_pretty })
        request.add_vars(Db.stats)
        request.add_vars({ 'cache_time': Db.cache_time })
        t = DTemplate(request, 'db_cache.html')
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
