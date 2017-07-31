from werkzeug.wrappers import Response
from werkzeug.utils import redirect
from p.DTemplate import DTemplate
from p.DRequest import DRequest

def application(environ, start_response):
    """Display an ecom shopping-cart page"""

    try:
        request = DRequest(environ)
	t = DTemplate(request, 'shopping_cart.html')
    except Exception as e:
        import traceback
        traceback.print_exc()
        t = DTemplate(request, 'error.html')
        request.add_vars({ 'message': 'Internal Error' })

    resp = Response(t.render(request.get_vars()))
    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'text/html; charset=utf-8'
    resp.headers['content-length'] = len(resp.data)
    return resp(environ, start_response)
