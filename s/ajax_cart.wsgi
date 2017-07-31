# $Header: //depot/cs/s/ajax_cart.wsgi#24 $
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired, DbKeyInvalid
import db.Db as Db
import db.Build as Build
import db.Cart as Cart
import db.ImageSet as ImageSet

import cgi
import p.DJSON as json

def application(environ, start_response):
    """AJAX scripts for email templates."""

    request = DRequest(environ)
    error = normal_error

    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)

    try :
        Db.start_transaction()
        if 'files[]' in form:
            content_type = 'text/html; charset=utf-8'
            error = uploader_error
            req = {
                'command': 'image_upload',
                'filename': form['files[]'].filename,
                'f': form['files[]'].file,
                'cart_id': form['cart_id'].value,
                'image_id': form['image_id'].value
            }
        elif 'args' in form:
            args = form['args'].value
            req = json.loads(args)

        if 'cart_id' not in req:
            raise DbKeyInvalid("Missing cart_id")
        cart_id = req['cart_id']
        cart = Cart.ShoppingCart(cart_id=cart_id)

        support = SupportSession(key=request.support_key())
        command = req['command']
        if not command in handlers:
            print "No handler for {}".format(command)
            raise Exception("No handler for {}".format(command))

        handler = handlers[command]
        resp = Response(json.dumps(handler(request, support, cart, req)))
        Db.finish_transaction()

    except SupportSessionExpired:
        Db.cancel_transaction()
        resp = Response(json.dumps(error('Session Expired', True)))
    except DbKeyInvalid as e:
        Db.cancel_transaction()
        resp = Response(json.dumps(error(e.args[0], False)))
    except DbError as e:
        Db.cancel_transaction()
        resp = Response(json.dumps(error(e.args[0], False)))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps(error('Internal Error', False)))

    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'application/json'
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

# Process tile image upload.
def image_upload(request, support, cart, req):
    image_id = req['image_id']
    image_row = ImageSet.add_image(
        None,
        req['f'].read(),
        name = "image {} replacement".format(image_id)
    )
    new_image_id = image_row['image_id']
    ImageSet.set_replace_image(image_id, new_image_id)
    builds = Build.image_replace_update(image_id)
    cart.log("Image {} replaced with {}".format(image_id, new_image_id), support.name)
    # Must be an array since the uploader potentially has multiple files.
    return [{ 'replace_asset_id': image_row['s200_col_afile'], 'builds': builds, 'cart_logs': cart.get_logs() }]

def get(request, support, cart, req):
    jobs = []
    for job in cart.jobs_get():
        jobs.append(job.get_full())
    return { 'cart': cart.cart_full(),
             'next_cart_id': cart.get_next_review(),
             'cart_logs': cart.get_logs(),
             'cart_images': cart.get_images(),
             'jobs': jobs
           }

def cancel(request, support, cart, req):
    return cart.cancel(support.name, req['reason'])

def release(request, support, cart, req):
    return cart.release(support.name)

def manual_hold(request, support, cart, req):
    return cart.manual_hold(support.name, req['reason'])

def attach(request, support, cart, req):
    from db.EcomSession import EcomSession
    # Use an existing session or create a new one.
    ecom_session = EcomSession(request.ecom_key(new = True))
    cart.attach(support.name)
    ecom_session.set_image_set_id(cart.cart_full()['image_set_id'])
    ecom_session.set_cart_id(cart.cart_full()['cart_id'])
    return {}

def clone(request, support, cart, req):
    from db.EcomSession import EcomSession
    # Use an existing session or create a new one.
    ecom_session = EcomSession(request.ecom_key(new = True))
    ecom_session.set_image_set_id(cart.cart_full()['image_set_id'])
    new_cart_id = cart.clone(support.name)
    ecom_session.set_cart_id(new_cart_id)
    return {}

def log_entry(request, support, cart, req):
    cart.log(req['entry'], support.name)
    return { 'cart_logs': cart.get_logs() }

def confirmation_resend_email(request, support, cart, req):
    return cart.confirmation_resend_email(support.name, req['email'])

def complete_resend_email(request, support, cart, req):
    return cart.complete_resend_email(support.name, req['email'])

handlers = { 'get': get, 'cancel': cancel, 'manual_hold': manual_hold,
             'attach': attach, 'clone': clone, 'log_entry': log_entry,
             'release': release, 'confirmation_resend_email': confirmation_resend_email,
             'complete_resend_email': complete_resend_email, 'image_upload': image_upload }

def normal_error(message, force_login):
    if force_login:
        return { 'Error': message, 'unavailable': True }
    return { 'Error': message }

def uploader_error(message, force_login):
    # Note that we have to return an array here (to support multi-file upload).
    return [{ 'error': message }]
