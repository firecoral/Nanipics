# $Header: //depot/cs/s/ajax_promo.wsgi#3 $
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired
import db.Db as Db
import db.Promo as Promo

import cgi
import p.DJSON as json

def application(environ, start_response):
    """AJAX scripts for promos."""

    request = DRequest(environ)

    resp = None

    try :
        Db.start_transaction()
        form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
        args = form['args'].value
        req = json.loads(args)

        support = SupportSession(key=request.support_key())
        handler = handlers[req['command']]
        resp = Response(json.dumps(handler(request, req)))
        Db.finish_transaction()

    except SupportSessionExpired:
        resp = Response(json.dumps({ 'Error': 'Session Expired' }))
        Db.cancel_transaction()
    except DbError as e:
        resp = Response(json.dumps({ 'Error': e.args[0]}))
        Db.cancel_transaction()
    except Exception as e:
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps({ 'Error': "Internal Error"}))
        Db.cancel_transaction()

    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'application/json'
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

def get(request, req):
    import re
    promos = Promo.get_all()
    # convert the dates into something that the jquery datepicker can handle.
    # (This also avoids problems with json since it converts the date into a
    # string).
    # It also gets a use count for the promotion since that is no longer stored
    # in the database.  (It's computed as needed).
    for promo in promos['promos']:
        m = re.match('(\d\d\d\d)-(\d\d)-(\d\d)', str(promo['expire_date']))
        promo['expire_date'] = "{}/{}/{}".format(m.group(2), m.group(3), m.group(1));
        p = Promo.Promo(promo_id=promo['promo_id'])
        promo['used'] = p.use_count()
    return promos

def edit(request, req):
    import re
    # convert the expire_date back into an SQL format
    expire_date = req.get('expire_date', "")
    m = re.match('(\d\d)/(\d\d)/(\d\d\d\d)', expire_date)
    req['expire_date'] = "{}-{}-{}".format(m.group(3), m.group(1), m.group(2));

    # and convert the resulting date back to a jquery-ui datepicker string.
    promo = Promo.edit(req)
    m = re.match('(\d\d\d\d)-(\d\d)-(\d\d)', str(promo['promo']['expire_date']))
    promo['promo']['expire_date'] = "{}/{}/{}".format(m.group(2), m.group(3), m.group(1));
    return promo

def add(request, req):
    return Promo.new()

handlers = { 'get': get, 'edit': edit, 'add': add }

