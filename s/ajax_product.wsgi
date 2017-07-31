# $Header: //depot/cs/s/ajax_product.wsgi#28 $

import cgi, csv, pprint
import simplejson as json
from   werkzeug.wrappers import Response

import db.Db as Db
from   db.Exceptions import DbError, SupportSessionExpired
import db.Product as Product
import db.Statics as Statics
from   db.Support import SupportSession
from   p.DRequest import DRequest

def application(environ, start_response):
    """AJAX functions for products and product_designs."""

    content_type = 'application/json'
    error = normal_error
    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ) 

    try:
        Db.start_transaction()
        # If this is a file upload, do additional setup, otherwise
        # treat as a normal get/post.
        if 'files[]' in form:
            content_type = 'text/html; charset=utf-8'
            error = uploader_error
            req = {
                'command': 'csv_upload',
                'filename': form['files[]'].filename,
                'f': form['files[]'].file
            }
        elif 'args' in form:
            args = form['args'].value
            #request.log(args)
            req = json.loads(args)

        support = SupportSession(key=request.support_key())
        handler = handlers[req['command']]
        resp = Response(json.dumps(handler(request, req)))
        Db.finish_transaction()

    except SupportSessionExpired:
        Db.cancel_transaction()
        resp = Response(json.dumps(error('Session Expired')))
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

# Functions for pricing manager

def edit_product(request, req):
    return Product.edit_product(req);

def update_products(request, req):
    fieldnames = ('product_id', 'name', 'is_available')
    for i in range(Product.CSVPRICECOUNT):
	min_quantity = "min_quantity" + str(i)
	price = "price" + str(i)
	sale_price = "sale_price" + str(i)
	fieldnames  =  fieldnames + (min_quantity, price, sale_price)

    reader = csv.DictReader(req['f'], fieldnames=fieldnames, dialect='excel')
    rows = []
    for row in reader:
        if row['product_id'] != 'product_id':          # remove header
            rows.append(row)

    # Note that we have to return an array here (to support multi-file upload).
    return [{ 'products': Product.update_products(rows) }]

def view_product(request, req):
    pp = pprint.PrettyPrinter(indent=4)
    product_dump = Statics.products.get_id(int(req['product_id']))
    dump_html = pp.pformat(product_dump)
    return { 'product_dump': dump_html }

# Functions for product-design deleter.

def delete_product_designs(request, req):
    # Convert comma-separated list of product_design_ids (string) to a native list.
    # All values need to be ints, but spaces are allowed.
    pd_ids = [int(p) for p in req['pd_ids'].replace(' ', '').split(',')]

    orph_plg_ids, build_ids = Product.delete_product_designs(pd_ids)

    if len(orph_plg_ids) > 0:
        return { 'pd_ids': ','.join(map(str, pd_ids)), 'orph_plg_ids': ','.join(map(str, orph_plg_ids)) }
    else:
        return { 'pd_ids': ','.join(map(str, pd_ids)), 'orph_plg_ids': 'none' }

def delete_page_layout_groups(request, req):
    # Convert comma-separated list of page_layout_group_ids (string) to a native list.
    # All values need to be ints, but spaces are allowed.
    plg_ids = [int(p) for p in req['plg_ids'].replace(' ', '').split(',')]

    inv_bp_ids, inv_bi_ids, inv_bt_ids = Product.delete_page_layout_groups(plg_ids)

    return { 'plg_ids': ','.join(map(str, plg_ids)) }

def delete_page_layouts(request, req):
    # Convert comma-separated list of page_layout_ids (string) to a native list.
    # All values need to be ints, but spaces are allowed.
    pl_ids = [int(p) for p in req['pl_ids'].replace(' ', '').split(',')]

    empty_plg_ids, inv_bp_ids, inv_bi_ids, inv_bt_ids = Product.delete_page_layouts(pl_ids)

    if len(empty_plg_ids) > 0:
        return { 'pl_ids': ','.join(map(str, pl_ids)), 'empty_plg_ids': ','.join(map(str, empty_plg_ids)) }
    else:
        return { 'pl_ids': ','.join(map(str, pl_ids)), 'empty_plg_ids': 'none' }


handlers = { 'edit_product': edit_product, 'csv_upload': update_products,
             'view_product': view_product, 'delete_product_designs': delete_product_designs,
             'delete_page_layouts': delete_page_layouts, 'delete_page_layout_groups': delete_page_layout_groups }

def normal_error(str):
    return { 'Error': str }

def uploader_error(str):
    # Note that we have to return an array here (to support multi-file upload).
    return [{ 'error': str }]

