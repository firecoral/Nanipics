#!/usr/local/bin/python

import getopt, sys
import db.Db
from db.Key import Key
from db.Cart import ShoppingCart as Cart

def main():

    try:
	opts, args = getopt.getopt(sys.argv[1:], 'p:c:k:')
    except getopt.GetoptError as e:
	print str(e)
	usage()

    passphrase = None;
    cart_id = None;
    key_id = None;

    for o, a in opts:
	if o == "-p":
	    passphrase = a
	if o == "-c":
	    cart_id = a
	if o == "-k":
	    key_id = a


    if cart_id == None:
	usage()

    if passphrase == None:
	usage()

    db.Db.init('cs_user', 'XXXXXXXXXXXXXXX')
    db.Db.start_transaction()

    try:
	key = Key(key_id=key_id)
	cart = Cart(cart_id = cart_id)
    except Exception as e:
	print str(e)
	sys.exit(0)

    cipher = cart.cart_full()["cc_encrypt"]
    if cipher == None:
	print "Cart {} has no encrypted credit card.".format(cart_id)
	sys.exit(0)

    try:
	print "Credit card: {}".format(key.decrypt(passphrase, cipher))
    except ValueError as e:
	print "Bad passphrase"
    db.Db.finish_transaction()
    sys.exit(0)

def usage():
    print "usage: {} -p passphrase -c cart [-k key_id]".format(sys.argv[0])
    sys.exit(1)

if __name__ == "__main__":
    main()
