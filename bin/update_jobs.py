#!/usr/local/bin/python

import csv, datetime, ftplib, optparse, os, re, shutil, sys, tempfile

import db.Cart as Cart
import db.Db as Db
from   db.Exceptions import CartIncomplete, CartInvalid, DbKeyInvalid, JobInvalid
import db.Job as Job
import db.Statics as Statics

parser = optparse.OptionParser("usage: %prog [options]")
parser.add_option("-l", dest="lab_ids", help="only update jobs belonging to these labs (comma-separated)")
parser.add_option("-f", dest="csv_file", help="parse this CSV file (overrides -l)")

Db.init('cs_user', 'XXXXXXXXXXX')
Db.start_transaction()

c = Db.get_cursor()

(options, args) = parser.parse_args()
lab_ids = None
if options.csv_file == None:
    if options.lab_ids == None:
        lab_ids = [int(l['lab_id']) for l in Statics.labs.get()]
    else:
        try:
            lab_ids = [int(l) for l in options.lab_ids.split(',')]
        except ValueError:
            parser.print_help()
            quit()

def process_csv(csvfn):
    csv_job_ids = set()
    csv_cart_ids = set()
    errors = False
    with open(csvfn, 'rb') as csvfile:
        csvreader = csv.reader(csvfile, quotechar="'")
        for row in csvreader:
            if row[1] != 'Picked' or row[2] == '': continue
            cart_id, job_seq = row[0].split('-')
            tracking = row[2]
            when = row[3]
            try:
                job = Job.Job(cart_id=cart_id, job_seq=job_seq)
                if job.is_complete_or_cancelled(): continue
                job.complete(tracking=tracking, when=when)
                csv_job_ids.add(job.job_id())
                csv_cart_ids.add(job.cart_id())
            except DbKeyInvalid:
                print "Couldn't get job for cart_id {} and seq {}; skipping.".format(cart_id, job_seq)
                errors = True
                continue
            except JobInvalid:
                print "Invalid job {}; skipping.".format(job.job_id())
                errors = True
                continue
            except Exception:
                print "Unhandled exception for job for cart_id {} and seq {}; skipping.".format(cart_id, job_seq)
                errors = True
                continue
    return csv_job_ids, csv_cart_ids, errors

completed_job_ids = set()
notify_cart_ids = set()
notified_cart_ids = set()
rm_dir = False

csvdir = None
if options.csv_file != None:
    csv_job_ids, csv_cart_ids, errors = process_csv(options.csv_file)
    completed_job_ids |= csv_job_ids
    notify_cart_ids |= csv_cart_ids
else:
    for lab_id in lab_ids:
        csvdir = tempfile.mkdtemp(suffix='-csv-{}-{}'.format(datetime.date.today().strftime('%Y%m%d'), lab_id), dir=Db.tmp_path)
    
        lab = Statics.labs.get_id(lab_id)
        ftp = ftplib.FTP(lab['status_host'])
        ftp.login(lab['status_login'], lab['status_password'])
        ents = []
        ftp.retrlines('MLSD', ents.append)
        for ent in ents:
            m = re.match('^type=file;.*? (.*\.csv)$', ent)
            if m != None:
                rfile = m.group(1)
                lfile = '{}/{}'.format(csvdir, rfile)
                ftp.retrbinary('RETR '+rfile, open(lfile, 'wb').write)
                ftp.delete(rfile)
        ftp.quit()
    
        csvfns = ['{}/{}'.format(csvdir, f) for f in os.listdir(csvdir)]
        for csvfn in csvfns:
            csv_job_ids, csv_cart_ids, errors = process_csv(csvfn)
            completed_job_ids |= csv_job_ids
            notify_cart_ids |= csv_cart_ids
            if errors: rm_dir = False

for notify_cart_id in notify_cart_ids:
    try:
        cart = Cart.ShoppingCart(cart_id=notify_cart_id)
        cart.handle_completed_jobs()
        notified_cart_ids.add(notify_cart_id)
    except CartInvalid:
        print "Invalid cart {}; skipping.".format(notify_cart_id)
        rm_dir = False
        continue
    except CartIncomplete:
        print "Incomplete cart {}; skipping.".format(notify_cart_id)
        rm_dir = False
        continue
    except Exception:
        print "Unhandled exception for cart_id {}; skipping.".format(notify_cart_id)
        rm_dir = False
        continue

if csvdir != None:
    if rm_dir:
        shutil.rmtree(csvdir, False)
    else:
        print "Errors encountered: keeping dir {}.".format(csvdir)

Db.finish_transaction()
print "Jobs completed: "+' '.join(map(str, completed_job_ids))
print "Carts notified: "+' '.join(map(str, notified_cart_ids))

