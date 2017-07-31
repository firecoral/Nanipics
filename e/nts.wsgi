from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import db.Db as Db
import db.NavTilePage as NavTilePage
import db.Statics as Statics
import simplejson as json

def application(environ, start_response):
    """Display a page of navigation tiles.

    Nav_tile_page_id is passed as GET parameter ntp_id;
    hacked values redirect customer to homepage."""

    try:
        Db.start_transaction()
        request = DRequest(environ)

        ntp = NavTilePage.nav_tile_page_ecom(request.args.get('ntp_id'))
        request.add_vars({ 
            'name': ntp['name'],
            'splash_html': ntp['splash_html'],
            'instr_html': ntp['instr_html'],
            'menu_data': Statics.menu_data.get()
        })
        request.add_vars({ 
            'nts': json.dumps(ntp['tiles'])
        })

        t = DTemplate(request, 'nav_tiles.html')
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

