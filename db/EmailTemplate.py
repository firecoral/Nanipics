# $Header: //depot/cs/db/EmailTemplate.py#10 $
import re
from db.Db import get_cursor
from os import urandom

class EmailTemplate:
    """Prepare and send an email message using the email_template"""

    def __init__(self, template_key=None, from_email=None, to_email=None):
        c = get_cursor()
        c.execute("""select * from email_template where template_key = %s""", template_key)
        if c.rowcount == 0:
            raise Exception, "Email Template not found: {}".format(template_key)
        template = c.fetchone()

        # Put the email addresses in both dictionaries
        self.dict = {
            'from_email': from_email,
            'to_email': to_email
        }
        self.headers = {
            'from_email': from_email,
            'to_email': to_email
        }

        if 'subject' in template:
            self.headers['subject'] = template['subject']

        if 'cc' in template:
            self.headers['cc'] = template['cc']

        if 'bcc' in template:
            self.headers['bcc'] = template['bcc']

        if 'text_template' in template:
            self.text_template = template['text_template']
        else:
            raise Exception, "Email template missing required text template"

        if 'html_template' in template:
            self.html_template = template['html_template']
        else:
            self.html_template = None

    def subject(self, subject):
        """Set the subject. Overrides the subject in the template"""
        self.headers['subject'] = subject
        self.dict['subject'] = subject

    # We could add methods to add the from and to addresses, but we'll
    # assume they get set in the initialization for now.

    def add_vars(self, vars):
        """Set variables used for template display."""
        self.dict.update(vars)

    def send(self):
        from jinja2 import Template
        from p.Email import send_email
        if 'from_email' not in self.headers:
            raise Exception, "No recipient email address"

        if 'to_email' not in self.headers:
            raise Exception, "No sender email address"

        self.add_vars(self.headers)

        t_template = Template(self.text_template)
        text = t_template.render(self.dict)

        if self.html_template:
            h_template = Template(self.html_template)
            html = h_template.render(self.dict)
        else:
            html = None

        send_email(self.headers, text, html)

#
# Support and local email template calls.
#

def get_all():
    c = get_cursor()
    c.execute("""select * from email_template""")
    rows = c.fetchall()
    return { 'email_templates': rows }

def new():
    src = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    key = ''
    for n in range(16):
        key = key +  src[ord(urandom(1)) % 36]

    c = get_cursor()
    c.execute("""insert into email_template
                 (name, template_key)
                 values
                 ('New Email Template', %s)""",
                 (key,))
    email_template_id = c.lastrowid
    c.execute("""select * from email_template where email_template_id = %s""", email_template_id)
    row = c.fetchone()
    return { 'email_template': row }

def delete(email_template_id):
    email_template_id = re.sub('[^0-9]', '', email_template_id)
    c = get_cursor()
    c.execute("""delete from email_template
                 where email_template_id = %s""",
                 (email_template_id,))
    return { 'email_template_id': email_template_id }

def edit(req):
    """Update the given email template based on the data in the req object."""
    template_key = req.get('template_key', "")
    name = req.get('name', "")
    subject = req.get('subject', "")
    cc = req.get('cc', "")
    bcc = req.get('bcc', "")
    text_template = req.get('text_template', "")
    html_template = req.get('html_template', "")
    email_template_id = re.sub('[^0-9]', '', req['email_template_id'])
    c = get_cursor()
    c.execute("""update email_template
                 set template_key = %s,
                 name = %s,
                 subject = %s,
                 cc = %s,
                 bcc = %s,
                 text_template = %s,
                 html_template = %s
                 where email_template_id = %s""",
                 (template_key, name, subject, cc, bcc, text_template, html_template, email_template_id))
    c.execute("""select * from email_template where email_template_id = %s""", email_template_id)
    row = c.fetchone()
    return { 'email_template': row }
