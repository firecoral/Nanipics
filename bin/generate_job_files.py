#!/usr/local/bin/python

"Create populated job directories.  The database is not updated."

import argparse, os

import db.Db as Db
import db.Job as Job
import db.Lab as Lab
import db.Statics as Statics

parser = argparse.ArgumentParser(description='Create populated job directories.')
parser.add_argument('job_ids', metavar='job_id', type=int, nargs='+', help='job_ids to create directories for')
parser.add_argument('-d', dest='job_base_path', default='.', help='create the job directories under this path (default: current directory)')
args = parser.parse_args()

Db.init('cs_user', 'XXXXXXXXXXX')
Db.start_transaction()
c = Db.get_cursor()

for job_id in args.job_ids:
    job = Job.Job(job_id)
    job.set_base_path(args.job_base_path)
    lab_line = Statics.lab_lines.get_id(job.get_full()['lab_line_id'])

    if lab_line['lab_id'] == Lab.LAB_DPI:
        job.populate_dpi_dir()
    elif lab_line['lab_id'] == Lab.LAB_IYP:
        job.populate_iyp_dir()

Db.finish_transaction()

