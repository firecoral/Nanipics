#!/usr/local/bin/python

import optparse

import db.Db as Db
import db.Job as Job
import db.Cart as Cart

parser = optparse.OptionParser("usage: %prog [options]")
parser.add_option("-l", dest="lab_ids", help="only submit jobs belonging to these labs (comma-separated)")

(options, args) = parser.parse_args()
lab_ids = None
if options.lab_ids != None:
    try:
        lab_ids = [int(l) for l in options.lab_ids.split(',')]
    except ValueError:
        parser.print_help()
        quit()

Db.init('cs_user', 'XXXXXXXXXXX')
Db.start_transaction()

c = Db.get_cursor()

if lab_ids == None:
    c.execute("""
        select job_id
        from job
        where job_status_id = %s
        order by job_id""",
        (Job.JOB_STATUS_NEW,)
    )
else:
    c.execute("""
        select j.job_id
        from (job as j, lab_line as ll)
        where
            j.job_status_id = %s and
            ll.lab_line_id = j.lab_line_id and
            ll.lab_id in ({})
        order by j.job_id""".format(', '.join(map(str, lab_ids))),
        (Job.JOB_STATUS_NEW,)
    )
job_ids = [r['job_id'] for r in c.fetchall()]

for job_id in job_ids:
    job = Job.Job(job_id=job_id)
    # This automatically updates the cart to INPROCESS, if appropriate.  (This is unlike
    # the update (ship) process, where we don't want to consider sending email until all
    # the jobs have been processed, lest we send multiples.)
    job.submit()

Db.finish_transaction()

print "Jobs submitted: "+' '.join(map(str, job_ids))

