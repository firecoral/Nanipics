from werkzeug.utils import redirect
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest

def application(environ, start_response):
    """Display an ecom product-build page.

       Unexpected problems redirect customer to homepage."""

    try:
        request = DRequest(environ)
        request.add_vars({
            'image_size': 800
        })
        t = DTemplate(request, 'product_build.html')
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

