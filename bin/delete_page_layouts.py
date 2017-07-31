#!/usr/local/bin/python

import optparse

import db.Db as Db
import db.Product as Product

parser = optparse.OptionParser("usage: %prog <page_layout_id[,page_layout_id,...]>")
(options, args) = parser.parse_args()

try:
    pl_ids = [int(p) for p in args[0].split(',')]
except IndexError:
    parser.print_help()
    quit()
except ValueError:
    parser.print_help()
    quit()

Db.init('cs_user', 'XXXXXXXXXXX')
Db.start_transaction()

empty_plg_ids, inv_bp_ids, inv_bi_ids, inv_bt_ids = Product.delete_page_layouts(pl_ids)

if len(empty_plg_ids) > 0:
    empty_plg_ids_str = ','.join([str(r) for r in empty_plg_ids])
    print 'INFO: some product_layout_groups are now empty: '+empty_plg_ids

if len(inv_bp_ids) > 0:
    inv_bp_ids_str = ','.join([str(r) for r in inv_bp_ids])
    print 'INFO: some build_pages are now invalid: '+inv_bp_ids_str

if len(inv_bi_ids) > 0:
    inv_bi_ids_str = ','.join([str(r) for r in inv_bi_ids])
    print 'INFO: some build_images are now invalid: '+inv_bi_ids_str

if len(inv_bt_ids) > 0:
    inv_bt_ids_str = ','.join([str(r) for r in inv_bt_ids])
    print 'INFO: some build_texts are now invalid: '+inv_bt_ids_str

Db.finish_transaction()

