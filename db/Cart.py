# $Header: //depot/cs/db/Cart.py#121 $
import re
from decimal import *
import MySQLdb
from db.Db import get_cursor, Cache
from db.Exceptions import DbError, DbKeyInvalid, CartInvalid, CartIncomplete, AuthError, PromotionInvalid
import db.Build as Build
import db.Job as Job
import db.Lab as Lab
import db.Product as Product
import db.Promo as Promo
import db.Statics as Statics
from p.Utility import new_access_id
import p.DJSON as json

# Cart statuses must match cart_status.cart_status_id in the database.
STATUS_NEW = 1
STATUS_REVIEW = 2
STATUS_LAB_READY = 3
STATUS_INPROCESS = 4
STATUS_COMPLETE = 5
STATUS_CANCELLED = 6

# Super Cart
class ShoppingCart:
    """Used for various Shopping Cart Pages"""

    def __init__(self, cart_id=None, access_id=None, image_set_id=None):
        try:
            if (cart_id):
                cart_id = re.sub('[^0-9]', '', str(cart_id))
                c = get_cursor()
                c.execute("""select * from cart
                             where cart_id = %s""",
                             (cart_id,))
                if (c.rowcount == 0):
                    raise DbKeyInvalid("Cart not found: {}.".format(cart_id))
                self.cart = c.fetchone()

            elif (access_id):
                access_id = re.sub('[^A-Za-z0-9_-]', '', access_id)
                c = get_cursor()
                c.execute("""select * from cart
                             where access_id = %s""",
                             (access_id,))
                if (c.rowcount == 0):
                    raise DbKeyInvalid("Invalid access_id: {}.".format(access_id))
                self.cart = c.fetchone()
                cart_id = self.cart['cart_id']

            else:
                c = get_cursor()
                while True:
                    try:
                        access_id = new_access_id(16)
                        c.execute("""insert into cart
                                     (access_id, image_set_id)
                                     values
                                     (%s, %s)""",
                                     (access_id, image_set_id))
                        break
                    except MySQLdb.IntegrityError:
                        continue

                cart_id = c.lastrowid
                c.execute("""insert into address
                             (cart_id)
                             values
                             (%s)""",
                             (cart_id,))
                c.execute("""select * from cart
                             where cart_id = %s""",
                             (cart_id,))
                if (c.rowcount == 0):
                    raise DbKeyInvalid("Cart not found: {}.".format(cart_id))
                self.cart = c.fetchone()

            self.fill_line_items()

            c = get_cursor()

            c.execute("""
                select *
                from address
                where cart_id = %s""",
                (cart_id,)
            )
            self.cart['address'] = c.fetchone()

            self.invalid_promo_message = ""
            if self.cart['promo_id']:
                self.promo = Promo.Promo(promo_id=self.cart['promo_id'])

            # Create a subordinate dictionary for the cart_status
            self.cart['cart_status'] = Statics.cart_statuses.get_id(self.cart['cart_status_id'])
            del self.cart['cart_status_id']

            # Drop the financial columns (including shipping and tax) into
            # another subordinate dictionary.
            finance = {
                'promo_incomplete': self.cart['promo_incomplete'] == 1,
                'prod_cost': self.cart['prod_cost'],
                'prod_credit': self.cart['prod_credit'],
                'shipping_id': self.cart['shipping_id'],
                'shipping_cost': self.cart['shipping_cost'],
                'shipping_credit': self.cart['shipping_credit'],
                'discount_cost': self.cart['discount_cost'],
                'tax_cost': self.cart['tax_cost'],
                'total_cost': self.cart['total_cost']
            }
            self.cart['finance'] = finance
            del self.cart['prod_cost'], self.cart['shipping_cost'], self.cart['tax_cost'], self.cart['shipping_id'], self.cart['discount_cost']
            # We called recompute here, but this seems like a bad idea, and was leading to
            # some crashes.  Commented out for now, in case something actually depended on it.
            # This should be removed eventually.
            #self.recompute()

        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def fill_line_items(self):
        c = get_cursor()
        c.execute("""
            select line_item.*,
                build.access_id as build_access_id,
                build.revision as build_revision
            from (line_item)
            left join (build)
                on build.line_item_id = line_item.line_item_id
            where line_item.cart_id = %s
            order by line_item.seq""",
            (self.cart['cart_id'],)
        )
        self.cart['line_items'] = list(c.fetchall())

        # Create a subordinate dictionary for the line_items
        for li_row in self.cart['line_items']:
            li_row['product'] = Statics.products.get_id(li_row['product_id'])
            li_row['page_count'] = Build.get_page_count(li_row['build_access_id'])

        # move cc_encrypt out of the cart data structure.  If access is needed, use
        # cart.get_cc_encrypt().  Sometimes the full cart is sent back to support functions
        # and we would rather not send the encrypted credit card.  (In addition, cc_encrypt
        # is binary and blows up json).
        if 'cc_encrypt' in self.cart:
            self.cc_encrypt = self.cart['cc_encrypt']
            del self.cart['cc_encrypt']
        else:
            self.cc_encrypt = ""

    def cart_full(self):
        return self.cart

    def get_cc_encrypt(self):
        return self.cc_encrypt

    def line_item_ecom(self, line_item):
        """return a simplified line_item suitable for consumer scripts"""
        product = Statics.products.get_id(line_item['product_id'])
        lab_product = Statics.lab_products.get_id(product['lab_product_id'])
        return {
            'line_item_id': line_item['line_item_id'],
            'name': product['name'],
            'price': line_item['price'],
            'quantity': line_item['quantity'],
            'quantity_units': lab_product['quantity_units'],
            'quantity_name': lab_product['quantity_name'],
            'build_access_id': line_item['build_access_id']
        }

    def cart_ecom(self):
        """Return a simplified representation of the cart, suitable for consumer scripts."""

        line_items = []
        for line_item in self.cart['line_items']:
            line_items.append(self.line_item_ecom(line_item))
	shippings = []
        for shipping in Statics.shippings.get():
	    selected = ""
	    if (shipping['shipping_id'] == self.cart['finance']['shipping_id']):
		selected = "checked"
	    shippings.append({
		'shipping_id': shipping['shipping_id'],
		'name': shipping['name'],
		'instructions': shipping['instructions'],
		'trackable': shipping['trackable'],
		'selected': selected
	    })
        cart_ecom = {
            'cart_id': self.cart['cart_id'],
            'cart_status_id': self.cart['cart_status']['cart_status_id'],
            'address': self.cart['address'],
            'line_items': line_items,
            'finance': self.cart['finance'],
	    # shippings are the  textual display of shipping fields but
	    # exclude the prices (which are displayed in the finance record).
	    'shipping': shippings
        }
        return cart_ecom

    def ship_state_update(self, state_id):
	"""Called when a consumer changes the shipping state on the payment page."""
        try:
	    c = get_cursor()
	    if not state_id:
		c.execute("""
		    update address
		    set ship_state_id = null
		    where cart_id = %s""",
		    (self.cart['cart_id']))
	    else:
		state = Statics.states.get_id(state_id)	# validate
		c.execute("""
		    update address
		    set ship_state_id = %s
		    where cart_id = %s""",
		    (state_id, self.cart['cart_id']))

	    self.cart['address']['ship_state_id'] = state_id
            c.execute("""
                select *
                from address
                where cart_id = %s""",
                (self.cart['cart_id'],)
            )
            self.cart['address'] = c.fetchone()
            self.recompute()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return


    def address_update(self, address, actor=None):
        """Update this cart's address database record."""

        try:
            specials = 'n'
            if address['specials']:
                specials = 'y'

            c = get_cursor()
            c.execute("""
                update address
                set bill_first_name = %s,
                bill_last_name = %s,
                bill_address1 = %s,
                bill_address2 = %s,
                bill_city = %s,
                bill_state_id = %s,
                bill_postal_code = %s,
                bill_phone = %s,
                ship_first_name = %s,
                ship_last_name = %s,
                ship_address1 = %s,
                ship_address2 = %s,
                ship_city = %s,
                ship_state_id = %s,
                ship_postal_code = %s,
                ship_phone = %s,
		email = %s,
		specials = %s
                where cart_id = %s""",
                (address['bill_first_name'],
                address['bill_last_name'],
                address['bill_address1'],
                address['bill_address2'],
                address['bill_city'],
                address['bill_state_id'],
                address['bill_postal_code'],
                address['bill_phone'],
                address['ship_first_name'],
                address['ship_last_name'],
                address['ship_address1'],
                address['ship_address2'],
                address['ship_city'],
                address['ship_state_id'],
                address['ship_postal_code'],
                address['ship_phone'],
                address['email'],
                specials,
                self.cart['cart_id']))
            c.execute("""
                select *
                from address
                where cart_id = %s""",
                (self.cart['cart_id'],)
            )
            self.cart['address'] = c.fetchone()
            self.recompute()
            if actor:
                self.log("Address Updated", actor)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def address_verify(self):
        """Check to make sure that the required fields in the address are set."""
        pass

    def shipping_update(self, shipping_id):
        """Update this cart's shipping_id."""

        finance = self.cart['finance']
        try:
            # verify shipping_id
            shipping_id = int(shipping_id)
	    # throws error if it doesn't exist.
            shipping = Statics.shippings.get_id(shipping_id)

            c = get_cursor()
            c.execute("""
                update cart
                set shipping_id = %s
                where cart_id = %s""",
                (shipping_id,
                self.cart['cart_id']))
            finance['shipping_id'] = shipping_id
            self.recompute()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def discount_update(self, discount, actor):
        """Update this cart's discount."""

        finance = self.cart['finance']
        try:
            # validate discount value
            try:
                discount = Decimal(discount)
            except:
                discount = Decimal(0)

            subtotal = finance['prod_cost'] + finance['shipping_cost']
            if discount > subtotal:
                discount = subtotal
            if discount < 0:
                discount = Decimal(0)

            # we store and display discounts as a negative value
            discount *= -1
            c = get_cursor()
            c.execute("""
                update cart
                set discount_cost = %s
                where cart_id = %s""",
                (discount, self.cart['cart_id']))
            finance['discount_cost'] = discount
            self.recompute()
            self.log("Discount set to {}".format(discount), actor)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def line_item_update(self, line_item_id, quantity):
        """Update this line_item's quantity."""

        try:
            result = False
            for line_item in self.cart['line_items']:
                if line_item['line_item_id'] == line_item_id:
                    result = line_item
                    break

            if not result:
                raise DbError("Invalid line_item")
            else:
                line_item = result

            line_item['quantity'] = quantity
            # we have to update the price here in case the quantities have changed.
            # XXX We will probably have to keep the price fixed on credit carts.
            price = Product.unit_price(line_item['product_id'], quantity)
            line_item['price'] = price

            c = get_cursor()
            c.execute("""
                update line_item
                set quantity = %s,
                price = %s
                where line_item_id = %s""",
                (quantity, price, line_item['line_item_id']))
            self.recompute()
        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return line_item

    def line_item_add(self, product_id, build_id):
        """ Insert a new line-item, with default quantity into this cart.
            build_id must be provided so we can associate it with the line_item.
        """

        try:
	    c = get_cursor()
            try:
                seq = 1 + max(li['seq'] for li in self.cart['line_items'])
            except ValueError:
                seq = 1

            product = Statics.products.get_id(product_id)
            lab_product = Statics.lab_products.get_id(product['lab_product_id'])
            quantity = lab_product['quantity_base']
            price = Product.unit_price(product_id, quantity)
            wholesale_cost = lab_product['price']

	    c.execute("""
		insert into line_item
		(cart_id, product_id, price, wholesale_cost, quantity, seq)
		values (%s, %s, %s, %s, %s, %s)""",
		(self.cart['cart_id'], product_id, price, wholesale_cost, quantity, seq)
	    )
	    line_item_id = c.lastrowid

            Build.update_line_item_id(build_id, line_item_id)
     
	    self.fill_line_items()
	    self.recompute()
            lis = [li for li in self.cart['line_items'] if li['line_item_id'] == line_item_id]
            return lis[0]
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def line_item_delete(self, build_access_id):
        """Delete the line_item associated with this build."""

        try:
            for line_item in self.cart['line_items']:
                if line_item['build_access_id'] == build_access_id:
		    c = get_cursor()
                    c.execute("""update build
                                 set build.line_item_id = null
                                 where build.line_item_id = %s""",
                             (line_item['line_item_id']))
                    c.execute("""delete from line_item
                                 where line_item_id = %s""",
                             (line_item['line_item_id']))
                    self.cart['line_items'].remove(line_item)
                    self.recompute()
                    return { 'finance': self.cart['finance'] }
            return { 'Error': "Line Item does not exist" }
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def cancel(self, actor, reason):
        """Change the cart's cart_status_id to canceled.  Return the new status."""

        try:
            if (self.cart['cart_status']['cancelable'] == 0):
                raise CartInvalid("Cart may not be canceled.")

            if (self.cart['transaction_id']):
                self.void(actor)

            self.set_status_id(STATUS_CANCELLED)
            c = get_cursor()
            c.execute("""
                update cart
                set manual_hold = ""
                where cart_id = %s""",
                (self.cart['cart_id'],))
            self.log("Cart Cancelled: " + reason, actor)
            return { 'cart_status': self.cart['cart_status'], 'cart_logs': self.get_logs() }
        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def release(self, actor):
        """Release the cart from review to lab ready."""

        try:
            cart_status_id = self.cart['cart_status']['cart_status_id']
            # Currently we're moving all carts into STATUS_REVIEW upon submit,
            # but we may allow carts to transition from new to ready eventually.
            if (cart_status_id != STATUS_REVIEW and cart_status_id != STATUS_NEW):
                raise CartInvalid("Cart must be in new or review to submit.")
            if self.cart['manual_hold']:
                raise CartInvalid("Cannot release a held cart.")

            self.jobs_del()
            self.jobs_add()

            self.set_status_id(STATUS_LAB_READY)
            self.log("Cart released for lab: " + actor)
            return { 'cart_status_id': STATUS_LAB_READY }
        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def manual_hold(self, actor, reason):
        """Set the manual_hold field in the cart.  Use an empty reason ("") to
           clear the manual hold.  Return the reason."""

        try:
            if (self.cart['cart_status']['manual_hold'] == 0):
                raise CartInvalid("Cart may not be held.")
            c = get_cursor()
            c.execute("""
                update cart
                set manual_hold = %s
                where cart_id = %s""",
                (reason,
                self.cart['cart_id']))
            self.cart['manual_hold'] = reason
            if (reason):
                self.log("Manual Hold: " + reason, actor)
            else:
                self.log("Manual Hold Released", actor)
            return { 'manual_hold': reason, 'cart_logs': self.get_logs() }
        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def confirmation_resend_email(self, actor, email):
        """Resend the confirmation email associated with this cart.  Used by the support tool."""

        try:
            cart_status = self.cart['cart_status']
            if (cart_status['confirmation_email_resend'] == 0):
                raise CartInvalid("Cannot resend email for cart status {}".format(cart_status['name']))
            c = get_cursor()

            # If the support user has changed the email address, save the new email.
            cur_email = self.cart['address']['email']
            if cur_email != email:
                c.execute("""
                    update address
                    set email = %s
                    where cart_id = %s""",
                (email, self.cart['cart_id']))
                self.cart['address']['email'] = email

            try:
                self.confirmation_email()
                self.log("Confirmation Email resent to {}".format(email), actor)
            except Exception as e:
                self.log("Could not resend confirmation email: {}".format(e.args[0]))

            return { 'cart_logs': self.get_logs() }

        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def complete_resend_email(self, actor, email):
        """Resend the order complete email associated with this cart.  Used by the support tool."""

        try:
            cart_status = self.cart['cart_status']
            if (cart_status['complete_email_resend'] == 0):
                raise CartInvalid("Cannot resend email for cart status {}".format(cart_status['name']))
            c = get_cursor()

            # If the support user has changed the email address, save the new email.
            cur_email = self.cart['address']['email']
            if cur_email != email:
                c.execute("""
                    update address
                    set email = %s
                    where cart_id = %s""",
                (email, self.cart['cart_id']))
                self.cart['address']['email'] = email

            try:
                self.complete_email()
                self.log("Order Complete Email resent to {}".format(email), actor)
            except Exception as e:
                self.log("Could not resend order complete email: {}".format(e.args[0]))

            return { 'cart_logs': self.get_logs() }

        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")


    def apply_promo(self, code):
        """ Try to apply a promotional code to this cart."""
        try:
            promo = Promo.Promo(code=code)
            if promo.is_expired():
                raise PromotionInvalid, "This Promotion expired on {}.".format(promo.get_expire_date().strftime("%x"))
            if promo.is_used():
                raise PromotionInvalid, "This Promotion has already been used."

            self.promo = promo
            self.validate_promo()
            c = get_cursor()
            c.execute("""
                update cart
                set promo_id = %s
                where cart_id = %s""",
            (self.promo.get_promo_id(), self.cart['cart_id']))
            self.recompute()
            self.log("Promo Code successfully added to cart: {}".format(code))
            return self.promo.get_ecom()
        except PromotionInvalid as e:
            self.log("Failed to add promo to cart: {}".format(code))
            raise PromotionInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def remove_promo(self):
        """ Handle consumer requests to remove the promo.  (We don't even bother to
            see if there really was one.)"""
        c = get_cursor()
        c.execute("""
            update cart
            set promo_id = null
            where cart_id = %s""",
            (self.cart['cart_id'],)
        )
        self.log("Consumer removed promo {} from cart".format(self.promo.get_code()))
        del self.promo 
        self.recompute()

    def validate_promo(self):
        """ Make sure the current promotion is valid for this cart.  This might be
            done during the initial application, or later in case the cart has changed.
            Note that some promos have no requirements and we have already tested for
            expiration date and use count when the promo is instantiated."""
        promo = self.promo
        cart = self.cart
        reqs = promo.get_requirements()
        if reqs['req_dollar'] > 0:
            finance = self.cart['finance']
            if reqs['req_dollar'] > finance['prod_cost']:
                raise PromotionInvalid("Your Order does not meet the promotion's ${} requirement.".format(reqs['req_dollar']))
        elif reqs['req_quantity'] > 0:
            cart_quantity = 0
            for line_item in self.cart['line_items']:
                if reqs['req_product_id'] == line_item['product_id']:
                    cart_quantity += line_item['quantity']
            if cart_quantity < reqs['req_quantity']:
                raise PromotionInvalid("Your Order does not contain the required product(s) for the promotion:<br />{}".format(promo.get_consumer_text()))
        elif reqs['req_promo_category_quantity'] > 0:
            c = get_cursor()
            c.execute("""select sum(line_item.quantity) as quantity
                         from line_item, product
                         where product.promo_category_id = %s
                         and product.product_id = line_item.product_id
                         and line_item.cart_id = %s""",
                     (reqs['req_promo_category_id'], self.cart['cart_id']))
            quantity = c.fetchone()['quantity']
            if quantity < reqs['req_promo_category_quantity']:
                raise PromotionInvalid("Your Order does not contain the required product(s) for the promotion:<br />{}".format(promo.get_consumer_text()))
        return True

    def validate_existing_promo(self):
        """ This function re-evaluates a promo that already exists in the cart.
            Typically, it will be called when a page is loaded and we want to
            make sure the promo is still valid."""
        try:
            if self.cart['cart_status']['cart_status_id'] == STATUS_NEW:
                if self.promo.is_expired():
                    raise PromotionInvalid, "This Promotion expired on {}.".format(self.promo.get_expire_date().strftime("%x"))
                if self.promo.is_used():
                    raise PromotionInvalid, "This Promotion has already been used."
                self.validate_promo()

        except PromotionInvalid as e:
            c = get_cursor()
            c.execute("""
                update cart
                set promo_id = null
                where cart_id = %s""",
                (self.cart['cart_id'],)
            )
            self.log("Removed promo {} from cart: {}".format(self.promo.get_code(), str(e)))
            del self.promo 
            self.recompute()
            raise PromotionInvalid("""
                Your promotion is no longer valid had has been removed from your shopping cart.<br />
                Please adjust your order to match the promotion requirements and reenter the promotion code<br />
                The following issue was found:<br />
                {}<br />""".format(str(e)))

    def ecom_promo(self):
        try:
            if not hasattr(self, 'promo'):
                return None
            return self.promo.get_ecom()
        except PromotionInvalid as e:
            raise PromotionInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def get_invalid_promo_message(self):
        """ Return a promo message that will be displayed to a customer if the
            existing promo has been removed from their cart."""
        return self.invalid_promo_message

    def get_logs(self):
        """Get the cart's log entries."""
        try:
            c = get_cursor()
            c.execute("""select * from cart_log
                         where cart_id = %s
                         order by create_date desc""",
                     (self.cart['cart_id']))
            rows = c.fetchall()
            return rows
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def log(self, message, actor = ""):
        try:
            from socket import gethostname
            server = gethostname()
            server = re.sub('\..*', '', server)
            if not actor:
                import os
                actor = os.path.abspath( __file__ )
	    c = get_cursor()
            c.execute("""insert into cart_log
                         ( cart_id, server, actor, log )
                         values
                         (%s, %s, %s, %s)""",
                     (self.cart['cart_id'],
                      server,
                      actor,
                      message))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def recompute(self):
        """Use the current data in the cart to recompute the various costs"""

        try:
            finance = self.cart['finance']

            # Compute the product costs and get shipping class quantities to compute
            # shipping charges.
            shipping_classes = dict()
            prod_cost = Decimal(0)
            for line_item in self.cart['line_items']:
                prod_cost += line_item['price'] * line_item['quantity']
                product = Statics.products.get_id(line_item['product_id'])
                lab_product = Statics.lab_products.get_id(product['lab_product_id'])
                shipping_class_id = lab_product['shipping_class_id']
                if shipping_class_id not in shipping_classes:
                    shipping_classes[shipping_class_id] = line_item['quantity']
                else:
                    shipping_classes[shipping_class_id] += line_item['quantity']


            selected_shipping_cost = Decimal(0)
            state_id = self.cart['address']['ship_state_id']
            finance['shipping_costs'] = dict()
            if state_id:
                shipping_totals = Lab.shipping_compute(shipping_classes, state_id)['shipping_totals']
                for shipping_cost in shipping_totals:
                    shipping_id = shipping_cost['shipping_id']
                    total = shipping_cost['total']
                    finance['shipping_costs'][shipping_id] = total
                    if shipping_id == finance['shipping_id']:
                        selected_shipping_cost = Decimal(total)

            # Handle promo (if it exists).  We will be computing the value of the reward
            # portions of the promo.  Note that with the exception of the shipping_credit,
            # you can't stack multiple rewards into a promo.
            prod_credit = Decimal(0.00)
            shipping_credit = Decimal(0.00)
            finance['promo_incomplete'] = False
            if hasattr(self, 'promo'):
                promo = self.promo.get_full()
                if promo['rew_percent']:
                    prod_credit = Decimal((prod_cost * -promo['rew_percent']) / Decimal(100.0)).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)
                elif promo['rew_dollar']:
                    if promo['rew_dollar'] <= prod_cost:
                        prod_credit = -promo['rew_dollar']
                    else:
                        prod_credit = -prod_cost
                        finance['promo_incomplete'] = True
                elif promo['rew_product_id']:
                    quantity = promo['rew_product_quantity']
                    product_id = promo['rew_product_id']
                    percent = promo['rew_product_percent']
                    dollar = promo['rew_product_dollar']
                    # We're going to build a list of prices here for every product
                    # in the cart that matches this promo.  Note that this list will
                    # contain line_item quantity * matching line_items elements.  Later
                    # we will apply the promo to the correct number of items in the list.
                    prices = []
                    for line_item in self.cart['line_items']:
                        if line_item['product_id'] == product_id:
                            for i in range(line_item['quantity']):
                                prices.append(line_item['price'])
                    # put the highest prices first
                    prices.sort()
                    prices.reverse()
                    if quantity > 0:
                        prices = prices[0:quantity]
                    if percent > 0:
                        total = sum(prices)
                        prod_credit = Decimal((total * -percent) / Decimal(100.0)).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)
                    elif dollar > 0:
                        prices = map(lambda x: max(-dollar, -x), prices)
                        prod_credit = sum(prices)
                    else:
                        print "promo_id {} (type product) lacks a reward type.".format(promo['promo_id'])
                elif promo['rew_promo_category_id']:
                    quantity = promo['rew_promo_category_quantity']
                    promo_category_id = promo['rew_promo_category_id']
                    percent = promo['rew_promo_category_percent']
                    dollar = promo['rew_promo_category_dollar']
                    # We're going to build a list of prices here for every product
                    # in the cart that matches this promo category.  Note that this list will
                    # contain line_item quantity * matching line_items elements.  Later
                    # we will apply the promo to the correct number of items in the list.
                    prices = []
                    for line_item in self.cart['line_items']:
                        li_promo_category_id = Statics.products.get_id(line_item['product_id'])['promo_category_id']
                        if li_promo_category_id == promo_category_id:
                            for i in range(line_item['quantity']):
                                prices.append(line_item['price'])
                    # put the highest prices first
                    prices.sort()
                    prices.reverse()
                    if quantity > 0:
                        prices = prices[0:quantity]
                    if percent > 0:
                        total = sum(prices)
                        prod_credit = Decimal((total * -percent) / Decimal(100.0)).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)
                    elif dollar > 0:
                        prices = map(lambda x: max(-dollar, -x), prices)
                        prod_credit = sum(prices)
                    else:
                        print "promo_id {} (type promo_category) lacks a reward type.".format(promo['promo_id'])
                elif promo['rew_shipping_credit'] <= 0:
                    print "promo_id {} lacks a reward".format(promo['promo_id'])
                # Handle shipping
                if promo['rew_shipping_credit'] > 0:
                    if promo['rew_shipping_credit'] <= selected_shipping_cost:
                        shipping_credit = -promo['rew_shipping_credit']
                    else:
                        shipping_credit = -selected_shipping_cost


            sub_total = prod_cost + selected_shipping_cost + prod_credit + shipping_credit

            discount_cost = finance['discount_cost']
            try:
                tax = Statics.taxes.get_id(self.cart['address']['ship_state_id'])
                # The use of discount cost in this expression is questionable. XXX
                # Since discounts are only applied by support, I'm not going to work it out.
                tax_cost = Decimal(tax['tax'] * (sub_total + discount_cost) / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)
            except KeyError:
                tax = None
                tax_cost = Decimal(0)

            # apply discount last
            # discount is stored and displayed as a negative value
            if discount_cost + sub_total < 0:
                discount_cost = -sub_total
                tax_cost = Decimal(0)

            finance['prod_cost'] = prod_cost
            finance['prod_credit'] = prod_credit
            finance['shipping_cost'] = selected_shipping_cost
            finance['shipping_credit'] = shipping_credit
            finance['tax_cost'] = tax_cost
            finance['discount_cost'] = discount_cost
            finance['tax'] = tax
            finance['total_cost'] = sub_total + tax_cost + discount_cost

            # Should probably not do this if no change has occurred.
	    c = get_cursor()
            c.execute("""update cart 
                         set prod_cost = %s,
                         prod_credit = %s,
                         shipping_cost = %s,
                         shipping_credit = %s,
                         discount_cost = %s,
                         tax_cost = %s,
                         total_cost = %s,
                         promo_incomplete = %s
                         where cart_id = %s""",
                     (prod_cost,
                      prod_credit,
                      selected_shipping_cost,
                      shipping_credit,
                      discount_cost,
                      tax_cost,
                      finance['total_cost'],
                      1 if finance['promo_incomplete'] else 0,
                      self.cart['cart_id']))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def remove_empty(self):
        try:
            cart = self.cart

            quantity = 0
            for line_item in self.cart['line_items']:
                # Remove empty line_items from cart
                if (line_item['quantity'] <= 0):
		    c = get_cursor()
                    c.execute("""update build
                                 set build.line_item_id = null
                                 where build.line_item_id = %s""",
                             (line_item['line_item_id']))
                    c.execute("""delete from line_item
                                 where line_item_id = %s""",
                             (line_item['line_item_id']))
                    cart['line_items'].remove(line_item)
                    next
                else:
                    quantity += line_item['quantity']
            return quantity
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def order_submit(self, address, cc):
	"""Final step of the payment page, order submission includes the
	   address (in case we haven't updated changes to it), and the
	   credit card information."""

        try:
            self.recompute()
            cart = self.cart
            if cart['cart_status']['cart_status_id'] != STATUS_NEW:
                raise CartInvalid("Order has already been submitted")
            finance = self.cart['finance']
            if not finance['shipping_id']:
                raise CartIncomplete("Please select a form of shipping")
            quantity = self.remove_empty()

            if quantity <= 0:
                raise CartIncomplete("Please add some items to your order")
            if finance['total_cost'] < 0.0:
                print "{}: attempt to submit a cart with a total cost of {}".format(cart['cart_id'], finance['total_cost'])
                raise CartInvalid("Cart price is less than 0.")
            self.address_update(address)
            address = cart['address']
            if finance['total_cost'] > 0:
                try:
                    # Checking should be done in javascript, but check it again here.
                    if not cc['card_num']:
                        raise CartIncomplete("Please provide your credit card number")
                    if not cc['exp_month']:
                        raise CartIncomplete("Please provide your expiration date")
                    if not cc['exp_year']:
                        raise CartIncomplete("Please provide your expiration date")
                    if not cc['ccv']:
                        raise CartIncomplete("Please Provide the Security Code on your card")
                    self.authorize(cc['card_num'], cc['exp_year'], cc['exp_month'], cc['ccv'])
                except AuthError as e:
                    raise CartIncomplete(e)
                except CartInvalid as e:
                    raise CartIncomplete(e)
                except CartIncomplete as e:
                    raise CartIncomplete(e)
            self.complete_checkout()
        except CartInvalid as e:
            raise CartInvalid(e)
        except CartIncomplete as e:
            raise CartIncomplete(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def authorize(self, card_number, exp_year, exp_month, ccv):
        """Authorize a payment for this cart, using Authorize.net"""

	from authorize import AuthorizeClient, CreditCard, Address, exceptions
	from db.Key import Key
	import db.Db as Db
        try :
            cart = self.cart
            transaction_amount = cart['total_cost']
            client = AuthorizeClient(Db.auth_id, Db.auth_key, debug=False)
            address = self.cart['address']
            card_address = Address(street=address['bill_address1'], city=address['bill_city'], state=address['bill_state_id'], zip_code=address['bill_postal_code'], country=address['bill_country_id'])
            cc = CreditCard(card_number, exp_year, exp_month, ccv, address['bill_first_name'], address['bill_last_name'])
            card = client.card(cc, address=card_address)
            transaction = card.auth(transaction_amount, self.cart['cart_id'])

	    # Encrypt the credit card for saving
	    key = Key()
	    cc_enc = key.encrypt(card_number + '/' + exp_month + '/' + exp_year + '/' + ccv)

            m = re.search('(....)$', card_number) 
            card_short = m.group(0)

            # print repr(transaction.full_response)
            c = get_cursor()
            # At some point we want to check the cost of the cart and put
            # it into STATUS_REVIEW if the price exceeds a certain threshold. XXX
            c.execute("""
                update cart
                set transaction_id = %s,
                transaction_amount = %s,
                public_key_id = %s,
                card_num = %s,
		cc_encrypt = %s
                where cart_id = %s""",
                (transaction.uid,
                 transaction_amount,
                 key.get_key_id(),
                 card_short,
		 cc_enc,
                self.cart['cart_id']))
            self.log("Cart Authorized: {}".format(transaction.uid))
        except exceptions.AuthorizeConnectionError as e:
            print "authorize connection error"
            raise AuthError("Internal Error: could not authorize your credit card. Please try again later.")
        except exceptions.AuthorizeResponseError as e:
            print repr(e.full_response)
            reason_code = e.full_response['response_reason_code']
            reason_text = e.full_response['response_reason_text']
            self.log("Authorize Failed: {} ({})".format(reason_text, reason_code))
            if reason_code == 11:
                # This is a duplicate transaction, so let's show the confirmation page.
                return
            raise AuthError(reason_text)
        except exceptions.AuthorizeInvalidError as e:
            raise AuthError("Internal Error: could not authorize your credit card.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
    
    def order_complete(self):
	"""Order has been completed.  Capture (if needed) and complete the cart."""

        try:
            cart = self.cart
            finance = cart['finance']
            if cart['cart_status']['cart_status_id'] != STATUS_INPROCESS:
                raise CartInvalid("Order is not in process")
            if finance['total_cost'] < 0.0:
                print "{}: attempt to complete a cart with a total cost of {}".format(cart['cart_id'], finance['total_cost'])
                raise CartInvalid("Cart price is less than 0.")
            if cart['transaction_amount'] > 0 and cart['total_cost'] > 0:
                # assume we need to settle here
                self.capture(cart['total_cost'])

            self.set_status_id(STATUS_COMPLETE)
            c = get_cursor()
            c.execute("""
                update cart
                set complete_date = now()
                where cart_id = %s""",
                ( self.cart['cart_id'],))
            self.log("Cart Completed.")
            c.execute("""
                select complete_date
                from cart
                where cart_id = %s""",
                (self.cart['cart_id'],))
            self.cart['complete_date'] = c.fetchone()['complete_date']
            try:
                self.complete_email()
                self.log("Order Complete email sent to {}".format(self.cart['address']['email']))

            except Exception as e:
                self.log("Could not send order complete email: {}".format(e.args[0]))
        except CartInvalid as e:
            raise CartInvalid(e)
        except CartIncomplete as e:
            raise CartIncomplete(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def capture(self, amount):
        """Capture a payment for this cart, using Authorize.net"""

	from authorize import AuthorizeClient, AuthorizeTransaction, CreditCard, Address, exceptions
	import db.Db as Db
        try :
            cart = self.cart
            transaction_amount = amount
            transaction_uid = cart['transaction_id']
            client = AuthorizeClient(Db.auth_id, Db.auth_key, debug=False)
            transaction = AuthorizeTransaction(client, transaction_uid)
            # transaction.settle() returns a transaction_id for the settle.
            # We don't currently save it, since we don't know what we would
            # do with it.
            settle_transaction = transaction.settle(transaction_amount)

            # print repr(settle_transaction.full_response)
            self.log("Cart Captured: {}".format(settle_transaction.uid))
        except exceptions.AuthorizeConnectionError as e:
            print "authorize connection error"
            raise AuthError("Internal Error: could not authorize your credit card. Please try again later.")
        except exceptions.AuthorizeResponseError as e:
            print repr(e.full_response)
            reason_code = e.full_response['response_reason_code']
            reason_text = e.full_response['response_reason_text']
            self.log("Authorize Failed: {} ({})".format(reason_text, reason_code))
            raise AuthError(reason_text)
        except exceptions.AuthorizeInvalidError as e:
            raise AuthError("Internal Error: could not authorize your credit card.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
    
    def complete_checkout(self):
        """Move this cart out of the new state."""

	import db.Db as Db
        try :
            cart = self.cart
            self.set_status_id(STATUS_REVIEW)
            c = get_cursor()
            c.execute("""
                select sum(line_item.wholesale_cost * line_item.quantity) as wholesale_sum
                from line_item
                where cart_id = %s""",
                (self.cart['cart_id'],))
            if (c.rowcount == 0):
                wholesale_cost = Decimal(0.00)
            else:
                wholesale_cost = c.fetchone()['wholesale_sum']
            # For launch we are dropping all carts into review status.
            # In the future, we may choose to put only some carts into
            # review:
            #  High cost carts
            #  Carts with a discount
            c.execute("""
                update cart
                set submit_date = now(),
                wholesale_cost = %s
                where cart_id = %s""",
                (wholesale_cost,
                 self.cart['cart_id']))
            self.log("Cart Submitted.")
            c.execute("""
                select submit_date
                from cart
                where cart_id = %s""",
                (self.cart['cart_id'],))
            self.cart['submit_date'] = c.fetchone()['submit_date']
            try:
                self.confirmation_email()
                self.log("Confirmation email sent to {}".format(self.cart['address']['email']))
            except Exception as e:
                self.log("Could not send email confirmation: {}".format(e.args[0]))

        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def confirmation_email(self):
        """ Send a confirmation email to the consumer."""
        import EmailTemplate
        to_email = self.cart['address']['email']
        template = EmailTemplate.EmailTemplate('ORDER_CONFIRMATION', 'XXXXX@XXXXX.com', to_email)
        template.subject('Order Confirmation: {}'.format(self.cart['cart_id']))
        template.add_vars({ 'cart': self.cart })
        template.send()

    def complete_email(self):
        """ Send an order complete email to the consumer."""
        import EmailTemplate
        to_email = self.cart['address']['email']
        jobs = self.jobs_get()
        shipments = []
        for job in jobs:
            shipment_info = job.shipment_info()
            if shipment_info != None:
                shipments.append(shipment_info)

        template = EmailTemplate.EmailTemplate('ORDER_COMPLETE', 'XXXXX@XXXXX.com', to_email)
        template.subject('Order Complete: {}'.format(self.cart['cart_id']))
        template.add_vars({
            'cart': self.cart,
            'shipments': shipments
        })
        template.send()

    def get_next_review(self):
        """ Get the cart_id for the next reviewable cart.  This is used
            by the support tool to determine the next cart to go to when
            a cart is submitted or skipped.  It should closely match the
            code in Search.cart_review (below)."""
        try:

            c = get_cursor()
            c.execute("""select cart.cart_id
                         from cart
                         where cart.cart_status_id = %s
                         and cart.manual_hold = ''
                         and cart.cart_id > %s
                         order by cart.cart_id limit 1""",
                         (STATUS_REVIEW, self.cart['cart_id']))
            if (c.rowcount == 0):
                return 0
            cart = c.fetchone()
            return cart['cart_id']

        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def jobs_get(self):
        """ Get a list of jobs for this cart.  We refresh this for every call
            since jobs can change at any time."""
        try:
            cart = self.cart
            jobs = []

            c = get_cursor()
            c.execute(""" select job_id from job
                          where job.cart_id = %s""",
                          (self.cart['cart_id'],))
            job_ids = c.fetchall()

            for job_id in job_ids:
                jobs.append(Job.Job(job_id=job_id))
            return jobs
        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def jobs_add(self):
        """Create jobs for this cart."""

        try:
            cart = self.cart

            c = get_cursor()
            c.execute("""
                select lp.lab_line_id, ls.lab_shipping_id
                from (line_item as li, product as p, lab_product as lp, lab_shipping as ls)
                where
                    li.cart_id = %s and
                    p.product_id = li.product_id and
                    lp.lab_product_id = p.lab_product_id and
                    ls.lab_id = lp.lab_id and
                    ls.shipping_id = %s
                group by lp.lab_line_id
                order by lp.lab_line_id""",
                (cart['cart_id'], cart['finance']['shipping_id'])
            )
            j_rows = c.fetchall()

            for j_row in j_rows:
                job = Job.Job(job_dict={'cart_id': cart['cart_id'], 'lab_line_id': j_row['lab_line_id'], 'lab_shipping_id': j_row['lab_shipping_id']})
                c.execute("""
                     select li.line_item_id
                     from (line_item as li, product as p, lab_product as lp)
                     where
                         li.cart_id = %s and
                         p.product_id = li.product_id and
                         lp.lab_product_id = p.lab_product_id and
                         lp.lab_line_id = %s""",
                     (cart['cart_id'], j_row['lab_line_id'])
                )
                line_item_ids = [r['line_item_id'] for r in c.fetchall()]
                for line_item_id in line_item_ids:
                    job.add_item(line_item_id)
        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def jobs_del(self):
        """Delete all jobs from this cart."""

        try:
            cart = self.cart
            c = get_cursor()
            c.execute("""
                select distinct job_id
                from job
                where cart_id = %s""",
                (cart['cart_id'],)
            )
            job_ids = [r['job_id'] for r in c.fetchall()]
            for job_id in job_ids:
                job = Job.Job(job_id=job_id)
                job.delete()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def handle_submitted_jobs(self):
        """React to newly-submitted jobs for this cart - set the cart to INPROCESS
           if it's not already."""

        try:
            cart = self.cart

            if cart['cart_status']['cart_status_id'] == STATUS_INPROCESS:
                return

            if cart['cart_status']['cart_status_id'] != STATUS_LAB_READY:
                raise CartInvalid("Jobs should not have been submitted while cart in state {}.".format(cart['cart_status']['cart_status_id']))
            self.set_status_id(STATUS_INPROCESS)
        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def handle_completed_jobs(self):
        """React to newly-completed jobs for this cart - possibly complete cart,
           and/or send out an email.

           For now, I assume that if we add partial-shipment emails, we'll just
           list the current status of all jobs, rather than singling out the
           jobs that have just shipped (which would require us to be passed a
           list of job_ids)."""

        try:
            cart = self.cart
            c = get_cursor()
            c.execute("""
                select distinct job_id
                from job
                where cart_id = %s""",
                (cart['cart_id'],)
            )
            job_ids = [r['job_id'] for r in c.fetchall()]
            jobs_unshipped = False
            for job_id in job_ids:
                job = Job.Job(job_id=job_id)
                if not job.is_complete_or_cancelled():
                    jobs_unshipped = True
                    break
            if not jobs_unshipped:
                self.order_complete()
        except CartInvalid as e:
            raise CartInvalid(e)
        except CartIncomplete as e:
            raise CartIncomplete(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def void(self, actor):
        """Void an existing transaction for this cart, using Authorize.net"""

	from authorize import AuthorizeClient, CreditCard, Address, exceptions
	import db.Db as Db
        try:
            try:
                cart = self.cart
                from authorize import AuthorizeClient, CreditCard, Address, exceptions
                client = AuthorizeClient(Db.auth_id, Db.auth_key, debug=False)
                transaction = client.transaction(cart['transaction_id'])
                transaction.void()
                self.log("Transaction {} voided.".format(self.cart['transaction_id']), actor)
            except Exception as e:
                self.log("Could not void transaction {}: {}".format(self.cart['transaction_id'], e.args[0]), actor)

	    c = get_cursor()
            c.execute("""
                update cart
                set transaction_id = null
                where cart_id = %s""",
                (self.cart['cart_id']))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
    
    def set_status_id(self, status_id):
            """ This sets a new status_id on the cart.  Since changes in status
                often affect more than just the status_id, this function should
                probably only be used by Cart.py unless you know exactly what
                you are doing."""
            c = get_cursor()
            c.execute("""
                update cart
                set cart_status_id = %s
                where cart_id = %s""",
                (status_id,
                self.cart['cart_id']))
            self.cart['cart_status'] = Statics.cart_statuses.get_id(status_id)

    def attach(self, actor):
        """Attach this cart to the support user's session.
           If the cart was in the review or ready state, set
           it back to new and void the transaction.
           Note that this work is prepatory.  The actual
           attachment to the EcomSession still needs to be
           done."""

        try:
            if (self.cart['cart_status']['attachable'] == 0):
                raise CartInvalid("Cart may not be attached.")
            c = get_cursor()

            if (self.cart['transaction_id']):
                self.void(actor)

            # Cart status may already be NEW, but this query can still be used.
            self.set_status_id(STATUS_NEW)
            c.execute("""
                update cart
                set submit_date = null,
                manual_hold = ''
                where cart_id = %s""",
                (self.cart['cart_id'],))
            self.log("Cart attached.",  actor)

        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def clone(self, actor):
        """Creates a clone of this cart available through
           the support user's session.
           Note that this work is prepatory.  The actual
           attachment to the EcomSession still needs to be
           done."""

        try:
            c = get_cursor()

            access_id = new_access_id(16)
            c.execute("""
                insert into cart
                (
                    access_id,
                    cart_status_id,
                    shipping_id,
                    cc_encrypt
                )
                select %s, %s, shipping_id, cc_encrypt from cart
                    where cart_id = %s""",
                (access_id, STATUS_NEW, self.cart['cart_id']))
            new_cart_id = c.lastrowid

            for line_item in self.cart['line_items']:
                c.execute("""
                    insert into line_item (
                        cart_id,
                        product_id,
                        price,
                        quantity,
                        seq
                    )
                    values ( %s, %s, %s, %s, %s )""",
                    (new_cart_id, line_item['product_id'], line_item['price'],
                        line_item['quantity'], line_item['seq']))
                new_line_item_id = c.lastrowid
                new_build_id = Build.clone(line_item['build_access_id'], new_line_item_id)

            c.execute("""
                insert into address
                (
                    cart_id,
                    bill_first_name,
                    bill_last_name,
                    bill_company_name,
                    bill_address1,
                    bill_address2,
                    bill_city,
                    bill_state_id,
                    bill_province,
                    bill_postal_code,
                    bill_country_id,
                    bill_phone,
                    ship_first_name,
                    ship_last_name,
                    ship_company_name,
                    ship_address1,
                    ship_address2,
                    ship_city,
                    ship_state_id,
                    ship_province,
                    ship_postal_code,
                    ship_country_id,
                    ship_phone,
                    email
                )
                select %s,
                    bill_first_name,
                    bill_last_name,
                    bill_company_name,
                    bill_address1,
                    bill_address2,
                    bill_city,
                    bill_state_id,
                    bill_province,
                    bill_postal_code,
                    bill_country_id,
                    bill_phone,
                    ship_first_name,
                    ship_last_name,
                    ship_company_name,
                    ship_address1,
                    ship_address2,
                    ship_city,
                    ship_state_id,
                    ship_province,
                    ship_postal_code,
                    ship_country_id,
                    ship_phone,
                    email
                from address
                    where address.cart_id = %s""",
                (new_cart_id, self.cart['cart_id']))

            import db.Cart as Cart
            new_cart = Cart.ShoppingCart(cart_id=new_cart_id)
            new_cart.recompute()
            new_cart.log("Cloned from cart {}.".format(self.cart['cart_id']),  actor)
            self.log("Cloned into cart {}.".format(new_cart_id),  actor)
            return new_cart_id

        except Exception as e:
            print "Internal error: " + e.args[0]
            import traceback
            traceback.print_exc()
            raise DbError("Internal error: " + e.args[0])

    def order_status(self):
        """return the cart's order status."""
        try:
            status = Statics.cart_statuses.get_id(self.cart['cart_status']['cart_status_id'])
            jobs = self.jobs_get()
            shipments = []
            for job in jobs:
                shipment_info = job.shipment_info()
                if shipment_info != None:
                    shipments.append(shipment_info)

            ret = {
                'status': status['external_name'],
                'cart_status_id': status['cart_status_id'],
                'shipments': shipments
            }
                
            return ret

        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def get_images(self):
        """ Returns a list of all images used for building the designs in this cart.
            This is used on the support cart page (to allow support to fetch hi-res
            images), and should not be made available on the ecom site - we don't ever
            want hires asset keys in the hands of consumers."""
        try:
            c = get_cursor()
            c.execute("""select distinct image.full_col_afile as full_asset_id,
                         image.s200_col_afile as thumb_asset_id,
                         i2.s200_col_afile as replace_asset_id,
                         image.image_id as image_id
                         from (image, build_image, build_page, build, line_item)
                         left join (image as i2) on
                           i2.image_id = image.replace_image_id
                         where line_item.cart_id = %s
                         and build.line_item_id = line_item.line_item_id
                         and build.build_id = build_page.build_id
                         and build_page.build_page_id = build_image.build_page_id
                         and build_image.image_access_id = image.access_id
                         order by line_item.line_item_id""",
                     (self.cart['cart_id']))
            rows = c.fetchall()
            return rows
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")


class CompleteCart:
    """Used for order complete page."""

    def __init__(self, cart_id = None):
        try:
            if (cart_id):
                cart_id = re.sub('[^0-9]', '', str(cart_id))
                c = get_cursor()
                c.execute("""select * from cart
                             where cart_id = %s""",
                             (cart_id,))
                if (c.rowcount == 0):
                    raise DbKeyInvalid("Cart not found: {}.".format(cart_id))
                self.cart = c.fetchone()

        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def info(self):
	"""Provide an object with required information for the order complete page."""

	cart = self.cart
	return {
	    'cart_id': cart['cart_id'],
	    'submit_date': cart['submit_date'],
	    'complete_date': cart['complete_date']
	}
	
class Search:
    """Search for a set of carts"""

    def __init__(self, search_str):
        try:
            if (search_str):

		# These have not been well tested.  Probably broken.
                #search_str = re.sub('\\\\', '\\\\\\\\', search_str)
                search_str = re.sub('%', '\\%', search_str)
		# $glob_query =~ s/'/\\'/g;  # necessary?
                search_str = "%" + search_str + "%"

                c = get_cursor()
                c.execute("""select cart.cart_id, cart.cart_status_id, cart.total_cost,
                                cart.manual_hold,
				address.bill_first_name, address.bill_last_name,
				address.bill_phone, address.email
			     from cart, address
                             where cart.cart_id = address.cart_id
			     and ( address.bill_first_name like %s
				 or address.bill_last_name like %s
				 or address.bill_phone like %s
				 or address.email like %s )
			     order by cart.cart_id""",
                             (search_str, search_str, search_str, search_str))
                if (c.rowcount == 0):
                    self.cart_list = []
                    return
		self.cart_list = list(c.fetchall())
		for cart in self.cart_list:
		    cart['cart_id'] = int(cart['cart_id'])
		    cart['total_cost'] = str(cart['total_cost'])
		    cart['cart_status'] = Statics.cart_statuses.get_id(cart['cart_status_id'])['name']
		    del cart['cart_status_id']
                    # We don't want 'None' passed through as json.
                    if not cart['manual_hold']:
                        del cart['manual_hold']

        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def carts(self):
	"""Provide a list of all carts matching the original search."""

	return self.cart_list


def get_review():
    """ Get a list of carts that are ready for review."""
    try:

        c = get_cursor()
        c.execute("""select cart.cart_id, cart.cart_status_id, cart.total_cost,
                        cart.manual_hold,
                        address.bill_first_name, address.bill_last_name,
                        address.bill_phone, address.email
                     from cart, address
                     where cart.cart_id = address.cart_id
                     and cart.cart_status_id = %s
                     and cart.manual_hold = ''
                     order by cart.cart_id""",
                     (STATUS_REVIEW))
        if (c.rowcount == 0):
            return []
        cart_list = list(c.fetchall())
        for cart in cart_list:
            cart['cart_id'] = int(cart['cart_id'])
            cart['total_cost'] = str(cart['total_cost'])
            cart['cart_status'] = Statics.cart_statuses.get_id(cart['cart_status_id'])['name']
            del cart['cart_status_id']
        return cart_list

    except DbKeyInvalid as e:
        raise DbKeyInvalid(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print e.__class__.__name__ + ": " + str(e)
        raise DbError("Internal error")


def get_manual_hold():
    """ Get a list of carts that are in manual hold."""
    try:

        c = get_cursor()
        c.execute("""select cart.cart_id, cart.cart_status_id, cart.total_cost,
                        cart.manual_hold,
                        address.bill_first_name, address.bill_last_name,
                        address.bill_phone, address.email
                     from cart, address
                     where cart.cart_id = address.cart_id
                     and cart.manual_hold != ""
                     order by cart.cart_id""")
        if (c.rowcount == 0):
            return []
        cart_list = list(c.fetchall())
        for cart in cart_list:
            cart['cart_id'] = int(cart['cart_id'])
            cart['total_cost'] = str(cart['total_cost'])
            cart['cart_status'] = Statics.cart_statuses.get_id(cart['cart_status_id'])['name']
            del cart['cart_status_id']
        return cart_list

    except DbKeyInvalid as e:
        raise DbKeyInvalid(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print e.__class__.__name__ + ": " + str(e)
        raise DbError("Internal error")


def get_recent_complete(days):
    """ Get a list of recently completed carts."""
    try:

        c = get_cursor()
        c.execute("""select cart.cart_id, cart.cart_status_id, cart.total_cost,
                        cart.manual_hold,
                        address.bill_first_name, address.bill_last_name,
                        address.bill_phone, address.email
                     from cart, address
                     where cart.cart_id = address.cart_id
                     and cart.complete_date > date_sub(now(), interval %s day)
                     order by cart.cart_id""",
                     (days,))
        if (c.rowcount == 0):
            return []
        cart_list = list(c.fetchall())
        for cart in cart_list:
            cart['cart_id'] = int(cart['cart_id'])
            cart['total_cost'] = str(cart['total_cost'])
            cart['cart_status'] = Statics.cart_statuses.get_id(cart['cart_status_id'])['name']
            del cart['cart_status_id']
        return cart_list

    except DbKeyInvalid as e:
        raise DbKeyInvalid(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print e.__class__.__name__ + ": " + str(e)
        raise DbError("Internal error")


def find_cart(cart_id = None, last_name = None, zip_code = None):
    """Search for an order typically to get the order status"""
    # We assume the input has already be checked for syntax
    try:
        c = get_cursor()
        c.execute("""select cart.cart_id
                     from cart, address
                     where cart.cart_id = %s
                     and cart.cart_id = address.cart_id
                     and (address.ship_last_name = %s or address.ship_postal_code = %s)""",
                     (cart_id, last_name, zip_code))
        if (c.rowcount == 0):
            raise CartInvalid("Could not find order.  Please check the information provided")
        return

    except DbKeyInvalid as e:
        raise DbKeyInvalid(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print e.__class__.__name__ + ": " + str(e)
        raise DbError("Internal error")


