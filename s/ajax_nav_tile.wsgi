# $Header: //depot/cs/s/ajax_nav_tile.wsgi#6 $
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired
import db.Db as Db
import db.NavTilePage
import db.Asset as Asset
from jinja2 import Template

import cgi
import simplejson as json

def application(environ, start_response):
    """AJAX scripts for nav tiles and nav tile pages."""

    content_type = 'application/json'
    error = normal_error
    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ) 

    resp = None

    try :
        Db.start_transaction()
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

# Process tile image upload.
def image_upload(request, req):
    name = "Nav Tile"   # I'd like to insert nav_tile.name here.
    image_afile = Asset.insert_asset(
        req['f'].read(),
        name = name,
        referrers = 'nav_tile.image_afile',
        extension = '.jpg',
        mime_type = 'image/jpeg'
    )
    # XXX - throw exception if not JPEG
    # XXX - throw exception if has poison-null byte
    # Array is required here due to multi-file upload.
    # We don't need multi here, but still need to support it.
    return [{ 'image_afile': image_afile }]

# Page requests
def get(request, req):
    return db.NavTilePage.get_all()

def edit(request, req):
    return db.NavTilePage.edit(req)

def delete(request, req):
    return db.NavTilePage.delete(req['nav_tile_page_id'])

def add(request, req):
    return db.NavTilePage.new()

def resort_tiles(request, req):
    return db.NavTilePage.resort_tiles(req['nav_tile_page_id'], req['nav_tile_ids'])

# Individual Tile requests
def get_tiles(request, req):
    return db.NavTilePage.get_all_tiles(req['nav_tile_page_id'])

def edit_tile(request, req):
    return db.NavTilePage.edit_tile(req)

def delete_tile(request, req):
    return db.NavTilePage.delete_tile(req['nav_tile_page_id'], req['nav_tile_id'])

def add_tile(request, req):
    return db.NavTilePage.new_tile(req['nav_tile_page_id'])

handlers = { 'get': get, 'edit': edit, 'delete': delete, 'add': add,
	     'get_tiles': get_tiles, 'edit_tile': edit_tile,
	     'delete_tile': delete_tile, 'add_tile': add_tile,
             'image_upload': image_upload, 'resort_tiles': resort_tiles }

def normal_error(str):
    return { 'Error': str }

def uploader_error(str):
    # Note that we have to return an array here (to support multi-file upload).
    return [{ 'error': str }]
