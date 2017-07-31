from p.DRequest import DRequest
from decimal import Decimal
import jinja2

def init(path):
    global env
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(path))
    env.finalize = silent_none
    env.filters['currency_format'] = currency_format

# Keep jinja2 from blowing up when variables evaluate to 'None'
def silent_none(value):
    if value is None:
        return ''
    return value

def currency_format(value, currency):
    value = Decimal(value)
    if value < 0:
        value = -1 * value
        return '({}{:20,.2f})'.format(currency, value)
    else:
        return '{}{:20,.2f}'.format(currency, value)

class DTemplate:
    """HTML file Templating Support"""
    
    def __init__(self, request, template):
        self.environ = request.environ
        try:
            self.t = env.get_template(template)
        except jinja2.TemplateNotFound:
            request.log("Template not found: {0}".format(template))
            raise(Exception)   # pass the buck
        except jinja2.TemplateError:
            request.log("Template problem: {0}".format(template))

    # We want to include the original environment variables in
    # the dictionary for rendering.

    def render(self, vars):
        return self.t.render(vars)
