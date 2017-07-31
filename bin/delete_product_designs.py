#!/usr/local/bin/python

import optparse

import db.Db as Db
import db.Product as Product

parser = optparse.OptionParser("usage: %prog <product_design_id[,product_design_id,...]>")
(options, args) = parser.parse_args()

try:
    pd_ids = [int(p) for p in args[0].split(',')]
except IndexError:
    parser.print_help()
    quit()
except ValueError:
    parser.print_help()
    quit()

Db.init('cs_user', 'XXXXXXXXXXX')
Db.start_transaction()

orph_plg_ids, build_ids = Product.delete_product_designs(pd_ids)

if len(orph_plg_ids) > 0:
    orph_plg_ids_str = ','.join([str(r) for r in orph_plg_ids])
    print 'INFO: some page_layout_groups are now unreferenced: '+orph_plg_ids_str

pd_ids_str = ','.join([str(r) for r in pd_ids])
c.execute("""
    select build_id
    from build
    where product_design_id in ({})""".format(pd_ids_str)
)
build_ids = [b['build_id'] for b in c.fetchall()]
if len(build_ids) > 0:
    build_ids_str = ','.join([str(r) for r in build_ids])
    print 'INFO: some builds are now invalid: '+build_ids_str

Db.finish_transaction()

