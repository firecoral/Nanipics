#!/usr/local/bin/python

import getopt, sys
import db.Db
from db.Key import Key

def main():

    try:
	opts, args = getopt.getopt(sys.argv[1:], 'p:k:')
    except getopt.GetoptError as e:
	print str(e)
	usage()

    passphrase = None;
    cart_id = None;
    key_id = None;

    for o, a in opts:
	if o == "-p":
	    passphrase = a
	if o == "-k":
	    key_id = a

    if passphrase == None:
	usage()

    db.Db.init('cs_user', 'XXXXXXXXXXX')
    db.Db.start_transaction()

    key = Key(key_id=key_id)

    cipher = key.encrypt("Test message successfully decoded")

    try:
	print "Decrypted message: {}".format(key.decrypt(passphrase, cipher))
    except ValueError as e:
	print "Bad passphrase"
	sys.exit(1)

    db.Db.finish_transaction()
    sys.exit(0)

def usage():
    print "usage: {} -p passphrase [-k key_id]".format(sys.argv[0])
    sys.exit(1)

if __name__ == "__main__":
    main()
