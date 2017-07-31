from werkzeug.wrappers import Response
from db.Support import SupportSession
from db.EcomSession import EcomSession
from p.DTemplate import DTemplate
from p.DRequest import DRequest
from db.Exceptions import DbError, DbKeyInvalid, CartInvalid, CartIncomplete, SupportSessionExpired
import db.Db as Db
import re
import db.Statics as Statics
import p.DJSON as json

def application(environ, start_response):
    """Display an ecom shipping/payment page"""

    try:
        Db.start_transaction()
        request = DRequest(environ)
        # We need to add some features to the payment page if the user
        # is logged in to a valid support account.  This is mildly risky
        # code since we obviously never want to expose this to a normal
        # user.
        try:
            support = SupportSession(key=request.support_key())
            request.add_vars({ 'support_name': support.name })
            try:
                session_key = request.ecom_key()
                if session_key != None:
                    ecom_session = EcomSession(session_key = session_key)
                    cart = ecom_session.get_cart()
                    if cart.get_cc_encrypt():
                        request.add_vars({ 'cc_available': True })
            except Exception as e:
                print e.args[0]
                raise(e)
                #pass
        except SupportSessionExpired:
            pass
	request.add_vars({ 'states': json.dumps(Statics.states.get()) })
	t = DTemplate(request, 'payment.html')
        Db.finish_transaction()
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        t = DTemplate(request, 'error.html')
        request.add_vars({ 'message': 'Internal Error' })

    resp = Response(t.render(request.get_vars()))
    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'text/html; charset=utf-8'
    resp.headers['content-length'] = len(resp.data)
    return resp(environ, start_response)
