from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import db.Statics as Statics
import db.Db as Db
import db.Product as Product
import simplejson as json

def application(environ, start_response):
    """Display a set of product_design entries for a card-select group.

    The cs_group_id is passed as GET parameter 'csg_id';
    hacked values redirect customer to homepage."""

    try:
        Db.start_transaction()
        request = DRequest(environ)
        csg = Product.cs_group_ecom(request.args.get('csg_id'))
        request.add_vars({
            'title': csg['name'],
            'cs_group': json.dumps(csg),
            'menu_data': Statics.menu_data.get()
        })

        t = DTemplate(request, 'card_select.html')
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

