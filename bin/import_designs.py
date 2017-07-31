#!/usr/local/bin/python

# Add a set of designs (and possibly a pi_product_design_group) from a text file
# and a set of images.

# NOTE: this is untested as of 11/18/2013!

# This modifies the following database tables:
#
# pi_product_design_group	insert
# product_design		insert
# product_design_detail_image	insert
# design_page			insert
# asset				insert
# pb_product_design_pair_id     insert

import sys

import db.Db as Db
import db.ZipImport as ZipImport

Db.init('cs_user', 'XXXXXXXXXXX')
Db.start_transaction()

c = Db.get_cursor()

ZipImport.parse_specfile(sys.argv[1])

Db.finish_transaction()

