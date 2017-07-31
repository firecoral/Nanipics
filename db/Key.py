# $Header: //depot/cs/db/Key.py#3 $
import re
from db.Db import get_cursor
import db.Db as Db
import p.PubKey

class Key:
    """Manage and use public keys"""

    def __init__(self, key_id = None, passphrase = None, new = False):
	"""Retrieve a public key object.

	   Args:
	      key_id: key to retrieve.  If None, return the default key.
	      new: create a new key, using the passphrase.
	      passphrase: used to encrypt the secure key, only if creating a new key.

	   Returns:
	      The public_key table row, as a dictionary.
	"""
	
	global key
        c = get_cursor()
	if new == True:
	    new_key = p.PubKey.new_key(passphrase)
	    c.execute("""insert into public_key
		      	 values (null, null, %s, %s)""",
			 (new_key['sec_key'], new_key['pub_key']))
	    key_id = c.lastrowid
	if key_id == None:
	    key_id = Db.public_key_id

	c.execute("""select * from public_key where public_key_id = %s""", key_id)
	if c.rowcount == 0:
	    raise Exception, "Key not found: {}".format(key_id)
	key = c.fetchone()

    def get_key_id(self):
        """Return the key_id for this key"""
	return key['public_key_id']

    def encrypt(self, message):
        """Encrypt the given message returning the cipher string."""
	return p.PubKey.encrypt(key['pub_key'], message)

    def decrypt(self, passphrase, message):
        """Decrypt the given cipher string returning the cleartext."""
	return p.PubKey.decrypt(key['sec_key'], passphrase, message)
