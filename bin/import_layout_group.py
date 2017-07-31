#!/usr/local/bin/python

# Add a set of design_page_layouts (and possibly a design_page_layout_group)
# from a text file and a set of images.

# NOTE: this is untested as of 11/18/2013!

# This modifies the following database tables:
#
# page_layout_group             insert
# page_layout                   insert
# design_page_layout		insert
# design_islot			insert
# design_tslot			insert
# fontsize			insert
# asset				insert

import sys

import db.Db as Db
import db.ZipImport as ZipImport

Db.init('cs_user', 'XXXXXXXXXXX')
Db.start_transaction()

c = Db.get_cursor()

ZipImport.parse_specfile(sys.argv[1])

Db.finish_transaction()

