from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Exceptions import DbError, DbKeyInvalid, EcomSessionExpired
from db.EcomSession import EcomSession
import db.Db as Db
import db.Build as Build
import db.Cart as Cart
import db.Product as Product
import db.ImageSet as ImageSet
import db.Statics as Statics

import cgi
import simplejson as json
import re

ecom_session = None

def application(environ, start_response):
    "AJAX script for sessions."

    content_type = 'application/json'
    request = DRequest(environ)
    resp = None

    try:
        Db.start_transaction()
        form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
        args = form['args'].value
        req = json.loads(args)
        global ecom_session
        ecom_session = EcomSession(session_key = request.ecom_key(new = req['command'] == 'create_build'))
        handler = handlers[req['command']]
        resp = Response(json.dumps(handler(request, req)))
        Db.finish_transaction()
    except EcomSessionExpired:
        Db.finish_transaction()
        resp = Response(json.dumps(error('Session Expired')))
    except DbKeyInvalid as e:
        Db.finish_transaction()
        resp = Response(json.dumps(error(e.args[0])))
    except DbError as e:
        Db.cancel_transaction()
        resp = Response(json.dumps(error(e.args[0])))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps(error('Internal Error')))

    request.cookie_freshen(resp)
    resp.headers['content-type'] = content_type
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

def create_build(request, req):
    "Create and attach a build for this session."

    build_id = Build.create_empty(req['pd_id'], request.ecom_key())
    ecom_session.set_current_build_id(build_id = build_id)

    return { 'Success': True }

def update_li_qty(request, req):
    """Called when from the cart_quantity page to update the line_item_quantity.
       This function will create the line_item and cart, if necessary."""

    cart = ecom_session.get_cart()
    if cart == None:
        cart = ecom_session.new_cart()

    build = Build.build_full(build_id=ecom_session.current_build_id(), shallow=True)

    create_li = False
    if build['line_item_id'] == None:
        create_li = True
    else:
        # assertion - session's build's line_item is in session's cart?
        lis = [li for li in cart.cart_full()['line_items'] if li['line_item_id'] == build['line_item_id']]
        if len(lis) == 0:
            create_li = True

    if create_li:
        product_design = Product.product_design(build['product_design_id'])
        line_item = cart.line_item_add(product_design['product_id'], build['build_id'])
        #  XXX I think this wouldn't have to happen if Build were an object.
        #  cart.line_item_add now calls Build.update_line_item_id so the database
        #  is properly updated, but the current build object doesn't have the
        #  line_item_id (which will be used shortly).  Set it here for now.
        build['line_item_id'] = line_item['line_item_id']
        # This is now done in line_item_add, above.
        #Build.update_line_item_id(build['build_id'], line_item['line_item_id'])

    # now actually update the quantity
    cart.line_item_update(build['line_item_id'], int(req['li_qty']))

    return { 'Success': True }

def get_product(request, req):
    """Return an ecom-friendly product structure, based on the session's current build.

       On request, also include ecom-friendly current information:
       * a build structure                      ('include_build'  param);
       * product_design structures              ('include_pds'    param);
         (all PDs in the pb "pair")
       * a list of page_layout_group structures ('include_plgs'   param);
       * a list of image structures             ('include_images' param);
       * the quantity of the line-item          ('include_li_qty' param);
       * the special text for the quantity page ('include_qty_text' param);"""

    rv = { 'Success': True }

    build = Build.build_full(build_id=ecom_session.current_build_id(), shallow=True)
    product_design = Product.product_design(build['product_design_id'])
    product = Product.product_ecom(product_design['product_id'])
    rv['product'] = product

    if 'include_build' in req:
        if 'bounding_width' in req and 'bounding_height' in req:
            rv['build'] = Build.build_ecom(
                ecom_session.current_build_id(),
                bounding_width  = req['bounding_width'],
                bounding_height = req['bounding_height']
            )
        else:
            rv['build'] = Build.build_ecom(ecom_session.current_build_id())

    if 'include_pds' in req:
        rv['pds'] = Product.product_designs_ecom(build['product_design_id'])

    if 'include_plgs' in req:
        if 'bounding_width' in req and 'bounding_height' in req:
            rv['plgs'] = Product.page_layout_groups_ecom(
                build['product_design_id'],
                bounding_width  = req['bounding_width'],
                bounding_height = req['bounding_height']
            )
        else:
            rv['plgs'] = Product.page_layout_groups_ecom(build['product_design_id'])

    if 'include_images' in req:
        rv['images'] = ImageSet.image_set_ecom(ecom_session.image_set_id())['images']

    if 'include_li_qty' in req:
        cart = ecom_session.get_cart()
        if cart == None:
            lis = []
        else:
            lis = [li for li in cart.cart_full()['line_items'] if li['line_item_id'] == build['line_item_id']]
	if (len(lis) > 0):
	    rv['li_qty'] = lis[0]['quantity']
	    rv['no_li'] = False
	else:
	    rv['li_qty'] = Product.base_quantity(product_design['product_id'])
	    # let the calling function know there is no line_item for this build.
	    rv['no_li'] = True

    if 'include_qty_text' in req:
        # We need to get the full product to obtain the quantity_text information.
        full_product = Statics.products.get_id(product_design['product_id'])
        lab_product = Statics.lab_products.get_id(full_product['lab_product_id'])
        rv['quantity_text'] = lab_product.get('quantity_text', "")

    return rv

def update_build(request, req):
    Build.update(req['build'], ecom_session.current_build_id())
    return { 'Success': True }

def set_build_id(request, req):
    """Set the session's current_build_id in anticipation of jumping to a new
	   page."""

    # Could potentially do a lot of error checking here.
    build_access_id = re.sub('[^a-z0-9_-]', '', req['build_access_id'])
    ecom_session.set_current_build_id(build_access_id = build_access_id)
    return { 'Success': True }

handlers = {
    'create_build': create_build, 'update_li_qty': update_li_qty, 'get_product': get_product,
    'update_build': update_build, 'set_build_id': set_build_id
}

def error(str):
    return { 'Error': str }

