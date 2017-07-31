from werkzeug.wrappers import Response
from db.Exceptions import EcomSessionExpired
from db.EcomSession import EcomSession
import db.Db as Db
from p.DRequest import DRequest
import db.ImageSet as ImageSet
import simplejson as json
import cgi

def application(environ, start_response):
    """AJAX scripts for (consumer) images."""

    content_type = 'application/json'
    error = normal_error
    form = cgi.FieldStorage(fp = environ['wsgi.input'], environ = environ)

    try:
        Db.start_transaction()
        request = DRequest(environ)

        # If this is a file upload, do additional setup, otherwise
        # treat as a normal get/post.
        if 'files[]' in form:
            content_type = 'text/html; charset=utf-8'
            error = uploader_error
            req = {
                'command': 'image_upload',
                'filename': form['files[]'].filename,
                'f': form['files[]'].file
            }
        elif 'args' in form:
            args = form['args'].value
            req = json.loads(args)

        handler = handlers[req['command']]
        resp = Response(json.dumps(handler(request, req)))
        Db.finish_transaction()

    except EcomSessionExpired:
        Db.cancel_transaction()
        resp = Response(json.dumps(error('Session Expired')))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps(error('Internal Error')))

    request.cookie_freshen(resp)
    resp.headers['content-type'] = content_type
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

# This arguably belongs in ajax_session.wsgi.
def image_upload(request, req):
    ecom_session = EcomSession(session_key = request.ecom_key())

    i_row = ImageSet.add_image(
        ecom_session.image_set_id(),
        req['f'].read(),
        name = 'Consumer image, filename '+req['filename']
    )
    return [{
        'ar': float(i_row['full_width']) / i_row['full_height'],
        'access_id': i_row['access_id'],
        'is_afile' : i_row['s200_col_afile'],
        'col_afile': i_row['l800_col_afile'],
        'baw_afile': i_row['l800_baw_afile'],
        'sep_afile': i_row['l800_sep_afile']
    }]

def image_rotate(request, req):
    """Rotates an image (updates its rotation and ecom afiles) and returns a standard
       image object."""

    image_access_id, rotation = req['image_access_id'], req['rotation']
    assert rotation % 90 == 0, "Bad rotation given: "+rotation
    ecom_session = EcomSession(session_key = request.ecom_key())

    new_vals = ImageSet.rotate_ecom_images(image_access_id, rotation, check_image_set_id=ecom_session.image_set_id())
    ar = float(new_vals['full_width']) / new_vals['full_height']

    return {
        'ar': float(new_vals['full_width']) / new_vals['full_height'],
        'access_id': new_vals['access_id'],
        'is_afile' : new_vals['s200_col_afile'],
        'col_afile': new_vals['l800_col_afile'],
        'baw_afile': new_vals['l800_baw_afile'],
        'sep_afile': new_vals['l800_sep_afile']
    }

handlers = {
    'image_upload': image_upload, 'image_rotate': image_rotate
}

def normal_error(str):
    return { 'Error': str }

def uploader_error(str):
    # Note that we have to return an array here (to support multi-file upload).
    return [{ 'error': str }]

