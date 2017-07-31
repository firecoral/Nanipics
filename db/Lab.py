# $Header: //depot/cs/db/Lab.py#17 $
import re
import db.Db as Db
from db.Db import get_cursor
import db.Statics as Statics
from os import urandom

#
# Database calls for the following database tables:
#       lab
#       lab_product
#       shipping_class
#       shipping_cost
#       shipping

# Labs must match lab.lab_id in the database.
LAB_DPI = 1
LAB_IYP = 2

def edit(req):
    """Update the given lab product based on the data in the req object."""

    name = req.get('name', "")
    shipping_class_id = req.get('shipping_class_id', "")
    price = req.get('price', "")
    quantity_base = req.get('quantity_base', 1)
    quantity_incr = req.get('quantity_incr', 1)
    quantity_text = req.get('quantity_text', "")
    lab_product_id = re.sub('[^0-9]', '', req['lab_product_id'])
    c = get_cursor()
    c.execute("""update lab_product
                 set name = %s,
                 shipping_class_id = %s,
                 price = %s,
                 quantity_base = %s,
                 quantity_incr = %s,
                 quantity_text = %s
                 where lab_product_id = %s""",
                 (name, shipping_class_id, price, quantity_base, quantity_incr, quantity_text, lab_product_id))
    Db.cache_invalidate()
    c.execute("""select * from lab_product where lab_product_id = %s""", lab_product_id)
    row = c.fetchone()
    return { 'lab_product': row }

def shipping_cost_edit(req):
    """Update the given shipping_cost based on the data in the req object."""

    first_units = req.get('first_units', "")
    first_set = req.get('first_set', "")
    addl_units = req.get('addl_units', "")
    addl_set = req.get('addl_set', "")
    shipping_cost_id = re.sub('[^0-9]', '', req['shipping_cost_id'])
    c = get_cursor()
    c.execute("""update shipping_cost
                 set first_units = %s,
                 first_set = %s,
                 addl_units = %s,
                 addl_set = %s
                 where shipping_cost_id = %s""",
                 (first_units, first_set, addl_units, addl_set, shipping_cost_id))
    Db.cache_invalidate()
    c.execute("""select * from shipping_cost where shipping_cost_id = %s""", shipping_cost_id)
    row = c.fetchone()
    return { 'shipping_cost': row }

# This returns a complex hierarchical view of shipping costs
# based on lab and shipping_class.  It's used for support
# displaying.

def get_lab_shipping_costs():
    labs = Statics.labs.get()
    c = get_cursor()
    for lab in labs:
        c.execute("""select * from shipping_class where lab_id = %s""", lab['lab_id'])
        lab['shipping_classes'] = c.fetchall()
        for sc in lab['shipping_classes']:
            c.execute("""select shipping_cost_id from shipping_cost where shipping_class_id = %s""", sc['shipping_class_id'])
            sc['shipping_costs'] = c.fetchall()
    return labs

def shipping_compute(shipping_classes, state_id):
    """Compute shipping costs for a given set of products.
       Input is an array of shipping_classes and quantities,
       along with a state_id for handling surcharges."""

    # I'm building two tables here - one showing customer shipping costs
    # (based on shipping_id), and one broken down by specific lab_shipping_ids
    # for debugging purposes.
    from decimal import Decimal
    from math import ceil
    lab_shipping_totals = []
    shipping_totals = dict()
    for shipping_class_id, quantity in shipping_classes.items():
        if quantity > 0:
            shipping_class_id = int(shipping_class_id)
            for shipping_cost in Statics.shipping_costs.get():
                total = Decimal(0.00)
                if shipping_class_id == shipping_cost['shipping_class_id']:
                    total = total + shipping_cost['first_set']
                    if quantity > shipping_cost['first_units']:
                        remainder = quantity - shipping_cost['first_units']
                        addl_sets = int(ceil(float(remainder) / shipping_cost['addl_units']))
                        total = total + Decimal(addl_sets * shipping_cost['addl_set'])
                if total > 0.0:
                   lab_shipping_id = int(shipping_cost['lab_shipping_id'])
                   lab_shipping_totals.append({
                       'shipping_class_id': shipping_class_id,
                       'lab_shipping_id': lab_shipping_id,
                       'quantity': quantity,
                       'total': total
                   })
                   shipping_id = Statics.lab_shippings.get_id(lab_shipping_id)['shipping_id']
                   shipping_totals[shipping_id] = shipping_totals.get(shipping_id, 0) + total

    shipping_totals_dict = []
    for shipping_id, total in shipping_totals.items():
        for surcharge in  Statics.shipping_surcharges.get(): # Linear search, but it's a small table.
	    if int(surcharge['shipping_id']) == shipping_id and surcharge['state_id'] == state_id:
		total += surcharge['surcharge']
        shipping_totals_dict.append({ 'shipping_id': shipping_id, 'total': total })

    return { 'lab_shipping_totals': lab_shipping_totals, 'shipping_totals': shipping_totals_dict }

