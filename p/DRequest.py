from werkzeug.utils import cached_property
from werkzeug.wrappers import Request
from werkzeug.contrib.securecookie import SecureCookie
from time import time
from db.Exceptions import SupportSessionExpired, EcomSessionExpired
from p.Utility import session_key
import simplejson as json
from os import getpid

SUPPORT_SECRET = ''
ECOM_SECRET = ''

SUPPORT_TIMEOUT = 60 * 60 * 24 * 1
ECOM_TIMEOUT = 60 * 60 * 24 * 21

class JSONSecureCookie(SecureCookie):
    serialization_method = json

class DRequest(Request):
    def __init__(self, environ):
        Request.__init__(self, environ)
        if 'wsgi.errors' in environ:
            self.logFile = environ['wsgi.errors']
        self.support_cookie = JSONSecureCookie.load_cookie(self, key="support_session", secret_key=SUPPORT_SECRET)
        self.ecom_cookie = JSONSecureCookie.load_cookie(self, key="ecom_session", secret_key=ECOM_SECRET)
        # manage template variables here
        self.template_vars = dict(self.args)
        # Add the cgi environment to the template variables
        self.add_vars(environ)
        # Add the process Id to the template variables
        self.add_vars({ 'pid': getpid() })

    def add_vars(self, vars):
        """Set variables used for template display."""
        self.template_vars.update(vars)

    def get_vars(self):
        """Retrieve the variables for template display."""
        return self.template_vars

    def log(self, string):
        if self.logFile != None:
            self.logFile.write(string + '\n')

    def support_key(self):
        try:
            return self.support_cookie['support_key']
        except KeyError:
            raise SupportSessionExpired

    def set_support_key(self, key):
        self.support_cookie['support_key'] = key

    def ecom_key(self, new = False):
        # new should only be set from e/pi.wsgi - all other scripts should throw an exception
        try:
            return self.ecom_cookie['ecom_key']
        except KeyError:
            if new:
                self.ecom_cookie['ecom_key'] = session_key(30)
                return self.ecom_cookie['ecom_key']
            raise EcomSessionExpired

    def cookie_freshen(self, response):
        """Refresh the session cookie expiration dates."""
        support_exp = time() + SUPPORT_TIMEOUT
        self.support_cookie.save_cookie(response, key="support_session", expires=support_exp)
        ecom_exp = time() + ECOM_TIMEOUT
        self.ecom_cookie.save_cookie(response, key="ecom_session", expires=ecom_exp)


