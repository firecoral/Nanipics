from werkzeug.wrappers import Response
from p.DRequest import DRequest
import db.Db as Db
from db.EcomSession import EcomSession
from db.Support import SupportSession
from db.Exceptions import DbError, DbKeyInvalid, CartInvalid, CartIncomplete, EcomSessionExpired, SupportSessionExpired, PromotionInvalid
import db.Cart as Cart
import p.DJSON as json
import cgi

ecom_session = None

def application(environ, start_response):
    """AJAX scripts for carts."""

    try:
	Db.start_transaction()
        request = DRequest(environ)
        form = cgi.FieldStorage(fp = environ['wsgi.input'], environ = environ)
        args = form['args'].value
        req = json.loads(args)
        handler = handlers[req['command']]
        session_key = request.ecom_key()
	if session_key == None:
	    resp = Response(json.dumps({ 'Error': 'Session Expired' }))
	else:
	    global ecom_session
	    ecom_session = EcomSession(session_key = session_key)
	    cart = ecom_session.get_cart()
	    if (cart):
		resp = Response(json.dumps(handler(request, cart, req)))
	    elif (ecom_session.get_complete_info()):
		# Most scripts will force people with this value to the order_complete
		# page.  The order_complete page will just display the order information.
		resp = Response(json.dumps({ 'Complete': ecom_session.get_complete_info() }))
	    else:
		resp = Response(json.dumps({ 'Error': 'You have no Shopping Cart.' }))
        Db.finish_transaction()

    except EcomSessionExpired as e:
        Db.cancel_transaction()
        resp = Response(json.dumps({ 'Error': 'You have no Shopping Cart.' }))
    except DbKeyInvalid as e:
        Db.cancel_transaction()
        resp = Response(json.dumps({ 'Error': e.args[0] }))
    except DbError as e:
        Db.cancel_transaction()
        resp = Response(json.dumps({ 'Error': e.args[0] }))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()

    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'application/json'
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

def get(request, cart, req):
    cart_ecom = cart.cart_ecom()
    ret = {
        'Success': True,
        'cart': cart_ecom
    }
    # an existing promo may be removed upstream.  
    try:
        promo = cart.ecom_promo()
        if promo:
            cart.validate_existing_promo()
            ret.update({'promo': promo})
    except PromotionInvalid as e:
        ret.update({'invalid_promo_message': str(e)})
    return ret

def ship_state_update(request, cart, req):
    cart.ship_state_update(req['state_id'])
    return { 'finance': cart.cart_full()['finance'] }

def shipping_update(request, cart, req):
    cart.shipping_update(req['shipping_id'])
    return { 'finance': cart.cart_full()['finance'] }

def address_update(request, cart, req):
    cart.address_update(req['address'])
    return { }

def shipping_update(request, cart, req):
    cart.shipping_update(req['shipping_id'])
    return { 'finance': cart.cart_full()['finance'] }

def line_item_delete(request, cart, req):
    return cart.line_item_delete(req['build_access_id'])

def discount_update(request, cart, req):
    # This function mustn't be run unless the user is logged into a support account.
    try:
        support = SupportSession(key=request.support_key())
        cart.discount_update(req['discount'], support.name)
        return { 'finance': cart.cart_full()['finance'] }
    except SupportSessionExpired:
        return { 'Error': "Not logged in." }

def apply_promo(request, cart, req):
    try:
        promo_ecom = cart.apply_promo(req['code'])
        return {
            'finance': cart.cart_full()['finance'],
            'promo': promo_ecom
        }
    except PromotionInvalid as e:
        return { 'Error': str(e) }
    except Exception as e:
        return { 'Error': str(e) }

def remove_promo(request, cart, req):
    try:
        cart.remove_promo()
        return {
            'finance': cart.cart_full()['finance']
        }
    except Exception as e:
        #return { 'Error': "Promo Error" }
        return { 'Error': str(e) }

def order_submit(request, cart, req):
    try:
        # Most verification should have happened in the javascript, so this is just
        # a crude backup.
        full = cart.cart_full()
        address = req['address']
        cc = req['cc']
        if not address['email']:
            return { 'Error': "Please provide an email address" }
        if not filled_address(address):
            return { 'Error': "Required information missing from address" }

        passphrase = req.get('cc_key', "")
        if passphrase:
            try:
                support = SupportSession(key=request.support_key())
                cipher = cart.get_cc_encrypt()
                public_key_id = full.get('public_key_id', None)
                if cipher == None:
                    return { 'Error': "No stored credit card." }

                from db.Key import Key
                key = Key(key_id=public_key_id)
                cc_str = key.decrypt(passphrase, cipher)
                cc_vals = cc_str.split('/');
                cc = {
                    'card_num': cc_vals[0],
                    'exp_month': cc_vals[1],
                    'exp_year': cc_vals[2],
                    'ccv': cc_vals[3]
                }
            except ValueError as e:
                return { 'Error': "Bad CC Passphrase" }
            except SupportSessionExpired:
                pass

        if full['finance']['total_cost'] > 0 and not filled_cc(cc):
            return { 'Error': "Required credit card information missing" }
        try:
            promo = cart.ecom_promo()
            if promo:
                cart.validate_existing_promo()
        except PromotionInvalid as e:
            return {
                'InvalidPromo': str(e),
                'finance': cart.cart_full()['finance']
            }

        res = cart.order_submit(address, cc)
	ecom_session.submit_cart()		# update the session
	return {}
    except CartIncomplete as e:
	return { 'Error': str(e) }

def filled_address(address):
    if not address['ship_first_name']:
        return false
    if not address['ship_last_name']:
        return false
    if not address['ship_address1']:
        return false
    if not address['ship_city']:
        return false
    if not address['ship_state_id']:
        return false
    if not address['ship_postal_code']:
        return false
    if not address['ship_phone']:
        return false
    if not address['bill_first_name']:
        return false
    if not address['bill_last_name']:
        return false
    if not address['bill_address1']:
        return false
    if not address['bill_city']:
        return false
    if not address['bill_state_id']:
        return false
    if not address['bill_postal_code']:
        return false
    if not address['bill_phone']:
        return false
    return True;

def filled_cc(cc):
    if not cc['card_num']:
        return false
    if not cc['exp_month']:
        return false
    if not cc['exp_year']:
        return false
    if not cc['ccv']:
        return false
    return True;

def get_complete_info(request, cart, req):
    """This should never get called!  This call is used only by order_complete.html
       which expects to get the completed info much earlier in this call.  The only
       way to get here is if a new shopping cart exists in which case we want to
       replace the order_complete.html page with the homepage.  So return an error."""

    return { 'Error': "You have a new cart" }



handlers = { 'get': get, 'address_update': address_update, 'shipping_update': shipping_update,
             'order_submit': order_submit, 'line_item_delete': line_item_delete,
	     'ship_state_update': ship_state_update, 'shipping_update': shipping_update,
	     'get_complete_info': get_complete_info, 'discount_update': discount_update,
             'apply_promo': apply_promo, 'remove_promo': remove_promo }

