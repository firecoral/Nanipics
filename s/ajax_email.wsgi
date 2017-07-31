# $Header: //depot/cs/s/ajax_email.wsgi#14 $
from werkzeug.wrappers import Response
from p.DRequest import DRequest
from p.Email import send_email
from db.Support import SupportSession
from db.Exceptions import DbError, SupportSessionExpired
import db.Db as Db
import db.EmailTemplate
from jinja2 import Template

import cgi
import simplejson as json

def application(environ, start_response):
    """AJAX scripts for email templates."""

    request = DRequest(environ)

    resp = None

    try :
        Db.start_transaction()
        form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
        args = form['args'].value
        req = json.loads(args)

        support = SupportSession(key=request.support_key())
        handler = handlers[req['command']]
        resp = Response(json.dumps(handler(request, req)))
        Db.finish_transaction()

    except SupportSessionExpired:
        resp = Response(json.dumps({ 'Error': 'Session Expired' }))
        Db.cancel_transaction()
    except DbError as e:
        resp = Response(json.dumps({ 'Error': e.args[0]}))
        Db.cancel_transaction()
    except Exception as e:
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps({ 'Error': "Internal Error"}))
        Db.cancel_transaction()

    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'application/json'
    resp.headers['cache-control'] = 'no-cache, must-revalidate, no-store'
    return resp(environ, start_response)

def get(request, req):
    return db.EmailTemplate.get_all()

def edit(request, req):
    return db.EmailTemplate.edit(req)

def delete(request, req):
    return db.EmailTemplate.delete(req['email_template_id'])

def add(request, req):
    return db.EmailTemplate.new()

def test(request, req):
    try:
        if 'data' in req:
            data = req['data']
            dict = eval(data, {"__builtins__": None }, {})
            if 'to_email' not in dict:
                raise Exception, "Email recipient (to_email) is required"
            if 'from_email' not in dict:
                raise Exception, "Email sender (from_email) is required"
        else:
            raise Exception, "Template data is required"

        if 'subject' in req:
            dict['subject'] = req['subject']
        else:
            raise Exception, "Subject is required"

        if 'cc' in req:
            dict['cc'] = req['cc']

        if 'bcc' in req:
            dict['bcc'] = req['bcc']

        if 'text_template' in req:
            text_t = Template(req['text_template'])
            text_template = text_t.render(dict)
        else:
            raise Exception, "Text template is required"

        if 'html_template' in req:
            html_t = Template(req['html_template'])
            html_template = html_t.render(dict)
        else:
            html_template = None

        send_email(dict, text_template, html_template)
        to_email = dict['to_email']

    except Exception, arg:
        return { 'Error': arg[0] }
    return { 'complete': "Email sent to: " + to_email }

handlers = { 'get': get, 'edit': edit, 'delete': delete, 'add': add, 'test': test }

