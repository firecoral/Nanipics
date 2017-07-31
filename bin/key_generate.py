#!/usr/local/bin/python

import getopt, sys
import db.Db
from db.Key import Key


def main():
    """This generates a new public key and stores it in the database
	for future use.  To enable the key, change settings.public_key_id
	to the new public_key_id generated here.
    """

    try:
	opts, args = getopt.getopt(sys.argv[1:], 'p:')
    except getopt.GetoptError as e:
	print str(e)
	usage()

    passphrase = None;

    for o, a in opts:
	if o == "-p":
	    passphrase = a

    if passphrase == None:
	usage()
	sys.exit(0)

    db.Db.init('cs_user', 'XXXXXXXXXXX')
    db.Db.start_transaction()

    key = Key(passphrase = passphrase, new = True)

    db.Db.finish_transaction()
    print "Set the new key_id ({}) in settings.public_key_id to use the key for encrypting future credit cards".format(key.get_key_id())

def usage():
    print "usage: {} -p passphrase".format(sys.argv[0])
    sys.exit(1)

if __name__ == "__main__":
    main()
