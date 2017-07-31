from werkzeug.exceptions import NotFound
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Exceptions import DbError, DbKeyInvalid, EcomSessionExpired
from db.EcomSession import EcomSession
from db.Build import page_img_build_id, page_img_access_id
import db.Db as Db
import StringIO

def application(environ, start_response):
    """Returns a page image of any size, up to 800px in the short dimension.
       Width and height (CGI params 'w' and 'h') denote a fitting size,
       not necessarily a final size; thus they can have any aspect ratio.

       A fit type ('t') is required: 'fb' (full-bleed), or 'ff' (full-frame).
       A sequence ('s') is required, but a build_access_id ('a') is optional;
       if omitted, we use the session's current build."""

    try:
        Db.start_transaction()
        request = DRequest(environ)
        seq, fit_width, fit_height, fit_type = \
            request.args.get('s'), request.args.get('w'), request.args.get('h'), request.args.get('t')
        if int(fit_width) > 800 or int(fit_height) > 800:
            raise Exception('Dimensions given were too big: {}x{}'.format(fit_width, fit_height))
        if fit_type != 'fb' and fit_type != 'ff':
            raise Exception('Bad fit_type given: {}'.format(fit_type))

        build_access_id = request.args.get('a')
        if build_access_id != None:
            image = page_img_access_id(build_access_id, seq, fit_width, fit_height, fit_type)
        else:
            ecom_session = EcomSession(session_key = request.ecom_key())
            image = page_img_build_id(ecom_session.current_build_id(), seq, fit_width, fit_height, fit_type)

        output = StringIO.StringIO()
        image.save(output, format='jpeg', quality=100)
        resp = Response(output.getvalue())
        output.close()
        resp.headers['content-type'] = 'image/jpeg; charset=utf-8'
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

