# $Header: //depot/cs/s/login.wsgi#18 $
import sys

from werkzeug.wrappers import Response
from werkzeug.contrib.securecookie import SecureCookie
from p.DTemplate import DTemplate
from p.DRequest import DRequest

def application(environ, start_response):
    """Display a support login page"""

    request = DRequest(environ)

    try :
        t = DTemplate(request, 'login.html')
    except Exception as e:
        import traceback
        traceback.print_exc()
        t = DTemplate(request, 'error.html')
        request.add_vars({ 'message': 'Internal Error' })

    resp =  Response(t.render(request.get_vars()))
    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'text/html; charset=utf-8'
    resp.headers['content-length'] = len(resp.data)

    return resp(environ, start_response)

