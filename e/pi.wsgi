from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from db.Exceptions import EcomSessionExpired
from db.EcomSession import EcomSession
import db.Statics as Statics
import db.Db as Db
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import db.Product as Product
import simplejson as json

def application(environ, start_response):
    """Display an ecom product-info page."""

    # The product_info page may be displayed in two ways:
    #  From a nav_tile click (using a pi_product_group_id)
    #  From a product select (using a product_design_id to determine a pd_design_group_id).
    #
    # There is no session needed here.  If it has not yet been created,
    # it will happen just before visiting the build page (next).

    try:
        Db.start_transaction()
        request = DRequest(environ)
        pd_id = int(request.args.get('pd_id', 0))
        pi_pgid = int(request.args.get('pi_pgid', 0))
        ppdg = Product.pi_ecom(product_design_id = pd_id, pi_product_group_id = pi_pgid)
        request.add_vars({
            'pd_id': pd_id,
	    'ecom_name': ppdg['ecom_name'],
	    'choose_text': ppdg['choose_text'],
            'design_group': json.dumps(ppdg),
            'menu_data': Statics.menu_data.get()
        })

        t = DTemplate(request, 'product_info.html')
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

