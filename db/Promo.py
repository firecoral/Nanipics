# $Header: //depot/cs/db/Promo.py#8 $
import re
from db.Db import get_cursor
from db.Exceptions import PromotionInvalid
from os import urandom
from datetime import date, timedelta
import db.Statics as Statics

class Promo:

    def __init__(self, code=None, promo_id=None):
        c = get_cursor()
        if code != None:
            c.execute("""select * from promo where code = %s""", code.upper())
        elif promo_id != None:
            c.execute("""select * from promo where promo_id = %s""", promo_id)
        else:
            print "Promo called without valid arguments"

        if c.rowcount == 0:
            raise PromotionInvalid, "Promotion not found. Please check your code: {}".format(code)
        self.promo = c.fetchone()

    def get_full(self):
        """Get a version of the promo"""
        return self.promo

    def get_ecom(self):
        """Get a version of the promo suitable for ecom ajax."""

        promo = self.promo
        ecom_promo = {
            'code': promo['code'],
            'consumer_text': promo.get('consumer_text', ""),
            'rew_percent': promo.get('rew_percent', 0),
            'rew_dollar': promo.get('rew_dollar', 0.00),
            'rew_shipping_credit': promo.get('rew_shipping_credit', 0.00)
        }
        products = []
        if promo['rew_quantity1'] > 0:
            products.append({
                'quantity': promo['rew_quantity1'],
                'product_id': promo['rew_product_id1'],
                'name': Statics.products.get_id(promo['rew_product_id1'])['name']
            })
        if len(products) > 0:
            ecom_promo['products'] = products
        return ecom_promo

    def get_requirements(self):
        """ Return the requirements fields from the promo. """
        return ({
            'req_dollar': self.promo.get('req_dollar', 0.00),
            'req_quantity': self.promo.get('req_quantity', 0),
            'req_product_id': self.promo.get('req_product_id', None),
            'req_promo_category_quantity': self.promo.get('req_promo_category_quantity', 0),
            'req_promo_category_id': self.promo.get('req_promo_category_id', None)
        })

    def get_promo_id(self):
        """Get the promo_id for this promo"""
        return self.promo['promo_id']

    def is_expired(self):
        """ Return True if this promo is beyond it's expire date."""
        today = date.today()
        expire = self.promo['expire_date']
        if expire - today < timedelta(0):
            return True
        return False

    def use_count(self):
        """ Return the number of times this promo has been used."""
        import db.Cart as Cart

        c = get_cursor()
        c.execute("""select count(cart.cart_id) as total from cart
                     where cart.promo_id = %s
                     and cart.cart_status_id not in (%s, %s)""",
                     (self.promo['promo_id'], Cart.STATUS_NEW, Cart.STATUS_CANCELLED))
        r = c.fetchone()
        return r['total']

    def is_used(self):
        """ Return True if this promo has been completely used up."""
        if self.promo['total_uses'] > 0 and self.use_count() >= self.promo['total_uses']:
            return True
        return False

    def get_expire_date(self):
        return self.promo['expire_date']

    def get_code(self):
        return self.promo['code']

    def get_consumer_text(self):
        return self.promo['consumer_text']
#
# Support promo calls
#

def get_all():
    c = get_cursor()
    c.execute("""select * from promo""")
    rows = c.fetchall()
    return { 'promos': list(rows) }

def new():
    c = get_cursor()
    c.execute("""insert into promo
                 (name, expire_date)
                 values
                 ('New Promo', date(date_add(now(), interval 60 day)))""")
    promo_id = c.lastrowid
    c.execute("""select * from promo where promo_id = %s""", promo_id)
    row = c.fetchone()
    return { 'promo': row }

def edit(req):
    """Update the given promo based on the data in the req object."""
    name = req.get('name', "")
    code = req.get('code', "")
    expire_date = req.get('expire_date', "")
    total_uses = req.get('total_uses', 0) or 0
    consumer_text = req.get('consumer_text', "")
    # requirements
    req_dollar = req.get('req_dollar', 0.00) or 0.00
    req_quantity = req.get('req_quantity', 0) or 0
    req_product_id = req.get('req_product_id', None)
    if req_product_id == "":
        req_product_id = None
    req_promo_category_quantity = req.get('req_promo_category_quantity', 0) or 0
    req_promo_category_id = req.get('req_promo_category_id', None)
    if req_promo_category_id == "":
        req_promo_category_id = None
    # rewards
    rew_shipping_credit = req.get('rew_shipping_credit', 0.00) or 0.00
    rew_percent = req.get('rew_percent', 0) or 0
    rew_dollar = req.get('rew_dollar', 0) or 0

    rew_product_id = req.get('rew_product_id', None)
    rew_product_quantity = req.get('rew_product_quantity', 0) or 0
    rew_product_percent = req.get('rew_product_percent', 0) or 0
    rew_product_dollar = req.get('rew_product_dollar', 0) or 0
    if rew_product_id == "":
        rew_product_id = None
        rew_product_quantity = 0
        rew_product_percent = 0
        rew_product_dollar = 0

    rew_promo_category_id = req.get('rew_promo_category_id', None)
    rew_promo_category_quantity = req.get('rew_promo_category_quantity', 0) or 0
    rew_promo_category_percent = req.get('rew_promo_category_percent', 0) or 0
    rew_promo_category_dollar = req.get('rew_promo_category_dollar', 0) or 0
    if rew_promo_category_id == "":
        rew_promo_category_id = None
        rew_promo_category_quantity = 0
        rew_promo_category_percent = 0
        rew_promo_category_dollar = 0

    promo_id = re.sub('[^0-9]', '', req['promo_id'])
    c = get_cursor()
    c.execute("""update promo
                 set name = %s,
                 code = %s,
                 expire_date = %s,
                 total_uses = %s,
                 consumer_text = %s,
                 req_dollar = %s,
                 req_quantity = %s,
                 req_product_id = %s,
                 req_promo_category_quantity = %s,
                 req_promo_category_id = %s,
                 rew_shipping_credit = %s,
                 rew_percent = %s,
                 rew_dollar = %s,
                 rew_product_id = %s,
                 rew_product_quantity = %s,
                 rew_product_percent = %s,
                 rew_product_dollar = %s,
                 rew_promo_category_id = %s,
                 rew_promo_category_quantity = %s,
                 rew_promo_category_percent = %s,
                 rew_promo_category_dollar = %s
                 where promo_id = %s""",
                 (name, code.upper(), expire_date, total_uses, consumer_text,
                  req_dollar, req_quantity, req_product_id,
                  req_promo_category_quantity, req_promo_category_id,
                  rew_shipping_credit, rew_percent, rew_dollar,
                  rew_product_id, rew_product_quantity,
                  rew_product_percent, rew_product_dollar,
                  rew_promo_category_id, rew_promo_category_quantity,
                  rew_promo_category_percent, rew_promo_category_dollar,
                  promo_id))
    c.execute("""select * from promo where promo_id = %s""", promo_id)
    row = c.fetchone()
    return { 'promo': row }

def get_promo_categories():
    """Get a list of the promo categories.  This is used so infrequently,
       that we don't want to use Statics for it."""

    c = get_cursor()
    c.execute("""select * from promo_category""")
    rows = c.fetchall()
    return { 'promo_categories': list(rows) }
