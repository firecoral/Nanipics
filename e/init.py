import db.Db
import p.DTemplate
import re
import inspect, os

db.Db.init('cs_user', 'XXXXXXXXXX')

# We derive the base file path from the path of this init script.

base = re.sub('e/init.py', '', inspect.getfile(inspect.currentframe()))
p.DTemplate.init([base + 'templates/ecom/', base + 'data'])
