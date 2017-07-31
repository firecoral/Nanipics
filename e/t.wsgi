from werkzeug.exceptions import NotFound
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.EcomSession import EcomSession
from db.Build import page_text_img
from db.Exceptions import EcomSessionExpired, DbKeyInvalid, DbError
import db.Db as Db
import StringIO
import simplejson as json

def application(environ, start_response):
    """Returns a text-overlay image - a transparent PNG annotated with text -
       of any size, up to 800px in the long dimension.
       Width and height (CGI params 'w' and 'h') denote a bounding-box size,
       not necessarily a final size; thus they can have any aspect ratio.

       A sequence ('s') is required; we use the session's current build."""

    try:
        Db.start_transaction()
        request = DRequest(environ)
        seq, bounding_width, bounding_height = \
            request.args.get('s'), request.args.get('w'), request.args.get('h')
        if float(bounding_width) > 800 or float(bounding_height) > 800:
            raise Exception('Dimensions given were too big: {}x{}'.format(bounding_width, bounding_height))
        ecom_session = EcomSession(session_key = request.ecom_key())

        image = page_text_img(ecom_session.current_build_id(), seq, bounding_width, bounding_height, 'ff')

        output = StringIO.StringIO()
        image.save(output, format = "PNG")
        resp = Response(output.getvalue())
        output.close()
        resp.headers['content-type'] = 'image/png; charset=utf-8'
        resp.headers['content-length'] = len(resp.data)
        Db.finish_transaction()
    except EcomSessionExpired:
        Db.cancel_transaction()
        resp = NotFound().get_response(environ)
    except DbKeyInvalid as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = NotFound().get_response(environ)
    except DbError as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = NotFound().get_response(environ)
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = NotFound().get_response(environ)

    request.cookie_freshen(resp)
    return resp(environ, start_response)

