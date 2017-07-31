# $Header: //depot/cs/db/EcomSession.py#22 $
import re
import Cart
from db.Db import get_cursor
from db.Exceptions import DbError, DbKeyInvalid, EcomSessionExpired

# Cart statuses must match cart_status.cart_status_id in the database.
STATUS_NEW = 1
STATUS_REVIEW = 2
STATUS_LAB_READY = 3
STATUS_INPROCESS = 4
STATUS_COMPLETE = 5
STATUS_CANCELLED = 6

class EcomSession:
    """Return a ecom session."""
    # Either find an existing ecom session (in the ecom_session table)
    # or create a new session.
    # If the passed in key represents a previously existing session, we
    # will return the database record for that session or create a new
    # one if that session is gone.
    # If the passed in key is new (created by the calling function), the
    # check for an existing session will clearly fail and we will generate
    # a new one.
    
    def __init__(self, session_key):
        try:
            c = get_cursor()
            c.execute("""select * from ecom_session
                         where session_key = %s""",
                       (session_key,))
            if (c.rowcount == 0):
                c.execute("insert into image_set values ()")
                image_set_id = c.lastrowid

                c.execute("""insert into ecom_session
                             (session_key, image_set_id)
                             values
                             (%s, %s)""",
                             (session_key, image_set_id))
                c.execute("""select * from ecom_session
                             where session_key = %s""",
                           (session_key,))

            self.ecom_session = c.fetchone()
            assert not (self.ecom_session['cart_id'] and self.ecom_session['complete_cart_id'])
            if self.ecom_session['cart_id']:
                try:
                    self.cart = Cart.ShoppingCart(cart_id=self.ecom_session['cart_id'])
                    if int(self.cart.cart_full()['cart_status']['cart_status_id']) != STATUS_NEW:
                        # Normally, sessions will not have a cart_id in them that has
                        # been submitted.  However, a cart_summary page might exhibit
                        # this condition.  So we post an error, but leave self.cart set.
                        # If we want to reuse the session, it is up to the calling function
                        # to call self.unlink_cart().
                        raise CartInvalid("Order has already been submitted")
                except:
                    # If there are any issues fetching the cart, remove it.
                    self.unlink_cart()
            else:
                self.cart = None

            # Only the order complete page is really interested in the complete cart.
            if self.ecom_session['complete_cart_id']:
                self.complete_cart = Cart.CompleteCart(cart_id=self.ecom_session['complete_cart_id'])
            else:
                self.complete_cart = None
        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except CartInvalid as e:
            raise CartInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        # print "ecom_session_id: {}, current_build_id: {}, image_set_id: {}".format(self.ecom_session.get('ecom_session_id', None), self.ecom_session.get('current_build_id', None), self.ecom_session.get('image_set_id', None))
        return

    def current_build_id(self):
        return self.ecom_session['current_build_id']

    def image_set_id(self):
        return self.ecom_session['image_set_id']

    def set_image_set_id(self, image_set_id = None):
        try:
            c = get_cursor()
            c.execute("""
                update ecom_session
                set image_set_id = %s
                where ecom_session_id = %s""",
                (image_set_id, self.ecom_session['ecom_session_id']))
            self.ecom_session['image_set_id'] = image_set_id
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def set_current_build_id(self, build_id = None, build_access_id = None):
        try:
            assert(bool(build_id) != bool(build_access_id)) # only one argument allowed.
            if build_id != None:
                c = get_cursor()
                c.execute("""
                    update ecom_session
                    set current_build_id = %s
                    where ecom_session_id = %s""",
                    (build_id, self.ecom_session['ecom_session_id']))
            if build_access_id != None:
                c = get_cursor()
            # I preferred this statement, but it caused an (apparently) incorrect warning
            # message so I've separated the select from the update.
            #    c.execute("""
            #	update ecom_session
            #	set current_build_id =
            #	    (select build_id from build where build.access_id = %s limit 1)
            #	where ecom_session_id = %s""",
            #	(build_access_id, self.ecom_session['ecom_session_id']))

                c.execute("""select build_id from build where build.access_id = %s""",
                           (build_access_id,))
                build_id = c.fetchone()['build_id']
                c = get_cursor()
                c.execute("""
                    update ecom_session
                    set current_build_id = %s
                    where ecom_session_id = %s""",
                    (build_id, self.ecom_session['ecom_session_id']))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def set_cart_id(self, cart_id):
        try:
            c = get_cursor()
            c.execute("""
                update ecom_session
                set cart_id = %s,
                complete_cart_id = null
                where ecom_session_id = %s""",
                (cart_id, self.ecom_session['ecom_session_id']))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def unlink_cart(self):
	"""Remove the associated cart from this session (if it exists)."""
        try:
            c = get_cursor()
            if self.ecom_session['cart_id']:
                c.execute("""update ecom_session
                             set cart_id = null
                             where ecom_session_id = %s""",
                             (self.ecom_session['ecom_session_id'],))
                self.ecom_session['cart_id'] = None
            self.cart = None
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def submit_cart(self):
	"""This should only be called with the cart is successfully submitted:
	   Copy cart_id to complete_cart_id.
	   Remove cart_id from the session.
	   Remove current_build_id from the session."""
        try:
            c = get_cursor()
            if self.ecom_session['cart_id']:
                c.execute("""update ecom_session
                             set complete_cart_id = cart_id,
                             current_build_id = null,
                             cart_id = null
                             where ecom_session_id = %s""",
                             (self.ecom_session['ecom_session_id'],))
                self.ecom_session['complete_cart_id'] = self.ecom_session['cart_id']
                self.ecom_session['cart_id'] = None
                self.ecom_session['current_build_id'] = None
            self.cart = None
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def new_cart(self):
        try:
            # This creates a new cart.
            self.cart = Cart.ShoppingCart(image_set_id=self.ecom_session['image_set_id'])

            c = get_cursor()
            c.execute("""update ecom_session
                         set cart_id = %s,
                         complete_cart_id = null
                         where ecom_session_id = %s""",
                         (self.cart.cart_full()['cart_id'], self.ecom_session['ecom_session_id']))
            return self.cart
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def get_cart(self):
        return self.cart

    def get_complete_info(self):
	"""Returns information from the completed cart"""
        return self.complete_cart.info()
