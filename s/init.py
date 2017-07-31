import db.Db
import p.DTemplate
import re
import inspect, os

db.Db.init('cs_support', 'XXXXXXXXXX')

# We derive the base file path from the path of this init script.

base = re.sub('s/init.py', '', inspect.getfile(inspect.currentframe()))
p.DTemplate.init([base + 'templates/support/', base + 'data'])
