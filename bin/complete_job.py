#!/usr/local/bin/python

import optparse

import db.Db as Db
import db.Job as Job
import db.Cart as Cart

parser = optparse.OptionParser("usage: %prog [options] <job_id>")
parser.add_option("-t", dest="tracking", help="set this tracking number")
parser.add_option("-d", dest="complete_date", help="set this complete-date (must be valid MySQL datetime)")

(options, args) = parser.parse_args()
try:
    job_id = int(args[0])
except IndexError:
    parser.print_help()
    quit()
except ValueError:
    parser.print_help()
    quit()

Db.init('cs_user', 'XXXXXXXX')
Db.start_transaction()

job = Job.Job(job_id=job_id)
job.complete(tracking=options.tracking, when=options.complete_date)
cart = Cart.ShoppingCart(cart_id=job.cart_id())
cart.handle_completed_jobs()

Db.finish_transaction()

