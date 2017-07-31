import cgi, datetime, os, sys
from   werkzeug.wrappers import Response
import xml.etree.ElementTree as ElementTree
from   xml.sax.saxutils import escape, quoteattr

import db.Db as Db
from   db.Exceptions import DbError
import db.Job as Job
import db.Lab as Lab
from   p.DRequest import DRequest

def application(environ, start_response):
    "Functions to allow IYP to post shipping updates."

    request = DRequest(environ)
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)

    try:
        Db.start_transaction()
        resp = Response(RETURN)
        Db.finish_transaction()
    except DbError as e:
        Db.cancel_transaction()
        resp = Response(json.dumps(error(e.args[0])))
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp = Response(json.dumps(error('Internal Error')))

    resp.headers['content-type'] = content_type
    return resp(environ, start_response)

def ship_jobs(xml):
    c = Db.get_cursor()

    job_ships = {}
    sn_nodes = ElementTree.fromstring(xml).findall('.//ShippingNotification')
    for sn_node in sn_nodes:
        job_key = sn_node.find('./OrderIdentifier/Identifier/').text
        job_item_key, ship_date, ship_carrier, ship_method, tracking_number = None, None, None, None, None
        if job_key not in job_ships:
            job_ships[job_key] = {
                job_item_keys: set(),
                ship_date: None,
                ship_carrier: None,
                ship_method: None,
                tracking_number: None
            }
        # By default, IYP doesn't post a job back to us until all of its lines have shipped.
        # They still could have shipped in multiple shipments, but we've never seen this on
        # the events side, even though we've been prepared for it.  So I assume that will hold
        # true here, as well.
        #
        # If they ever do send multiple shipments, I replace the old shipping information with
        # the new only if we would be adding a tracking number.  In all multiple-shipment cases,
        # I log.
        lineidentifier_node = sn_node.find('./LineIdentifier')
        if lineidentifier_node != None:
            job_item_key = int(lineidentifier_node.text)
        shipdate_node = sn_node.find('./ShipDate')
        if shipdate_node != None:
            ship_date = shipdate_node.text
        shipcarrier_node = sn_node.find('./ShipCarrier')
        if shipcarrier_node != None:
            ship_carrier = shipcarrier_node.text
        shipmethod_node = sn_node.find('./ShipMethod')
        if shipmethod_node != None:
            ship_method = shipmethod_node.text
        trackingnumber_node = sn_node.find('./TrackingNumber')
        if trackingnumber_node != None:
            tracking_number = trackingnumber_node.text

        job_ship = job_ships[job_key]
        # Will be true unless IYP gave us bad XML.
        if job_item_key != None and ship_date != None and ship_carrier != None and ship_method != None:
            # Add this job-item to the job.
            job_ship['job_item_keys'].add(job_item_key)
            if job_ship['ship_date'] == None and job_ship['ship_carrier'] == None and job_ship['ship_method'] == None:
                # First job-item encountered for this job; update job's shipping info.
                job_ship['ship_date'] = ship_date
                job_ship['ship_carrier'] = ship_carrier
                job_ship['ship_method'] = ship_method
                job_ship['tracking_number'] = tracking_number
            else:
                if job_ship['ship_date'] == ship_date and job_ship['ship_carrier'] == ship_carrier and \
                   job_ship['ship_method'] == ship_method and job_ship['tracking_number'] == tracking_number:
                    # Not the first job-item for this job, but it's in the same shipment.
                    pass
                else:
                    # Uh-oh, this job-item is in a different shipment.  Print to the logs:
                    sys.stderr.write('iyp_shipping_update.wsgi WARNING: job-item {} in unexpected shipment for job {}\n'.format(job_item_key, job_key)
                    sys.stderr.write('  Old values: ship_date {}, ship_carrier {}, ship_method {}, tracking_number {}\n'.format(
                        job_ship['ship_date'], job_ship['ship_carrier'], job_ship['ship_method'], job_ship['tracking_number']))
                    sys.stderr.write('  New values: ship_date {}, ship_carrier {}, ship_method {}, tracking_number {}\n'.format(
                        ship_date, ship_carrier, ship_method, tracking_number))
                    sys.stderr.flush()
                    # ... and update the job if this one is "better".
                    if tracking_number != None and job_ship['tracking_number'] == None:
                        job_ship['ship_date'] = ship_date
                        job_ship['ship_carrier'] = ship_carrier
                        job_ship['ship_method'] = ship_method
                        job_ship['tracking_number'] = tracking_number
        else:
            sys.stderr.write('iyp_shipping_update.wsgi WARNING: job-item missing some fields for job {}\n'.format(job_key)
            sys.stderr.write('  Values: job_item_key {}, ship_date {}, ship_carrier {}, ship_method {}, tracking_number {}\n'.format(
                job_item_key, ship_date, ship_carrier, ship_method, tracking_number))
            sys.stderr.flush()

    for job_key in job_ships:
        job_ship = job_ships[job_key]
        cart_id, seq = job_key.split('-')
        job = Job.Job(cart_id=cart_id, seq=seq)
        job_full = job.get_full()
        # Tersely build a set of all job_item_keys in the job.
        job_item_keys = set(['{}-{}'.format(ji['job_id'], ji['seq']) for ji in job_full['job_items']])
        if not job_item_keys.issubset(job_ship['job_item_keys']):
            sys.stderr.write('iyp_shipping_update.wsgi ERROR: job {} XML is missing some job-items\n'.format(job_key)
            sys.stderr.write('  XML job_item_keys: {}\n'.format(job_ship['job_item_keys']))
            sys.stderr.write('  DB  job_item_keys: {}\n'.format(job_item_keys))
            sys.stderr.flush()
            continue
        c.execute("""
            select lab_shipping_id
            from lab_shipping
            where iyp_carrier = %s and iyp_method = %s""",
            (job_ship['ship_carrier'], job_ship['ship_method'])
        )
        if c.rowcount == 1:
            actual_lab_shipping_id = c.fetchone()['lab_shipping_id']
        else:
            # Possibly because they changed to a type we don't offer our customers.
            actual_lab_shipping_id = None
        job.complete(tracking=tracking_number, actual_lab_shipping_id=actual_lab_shipping_id, when=ship_date)
        image_path = '{}/{:02d}/{:02d}/{:06d}'.format(Db.lab_path, Lab.LAB_IYP, int(str(job_full['job_id'])[-2:]), job_full['job_id'])
        if not os.path.isdir(image_path): os.makedirs(image_path)
        xml_filepath = '{}/ship_{}.xml'.format(datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        xml_file = open(xml_filepath, 'w')
        xml_file.write(xml)
        xml_file.close()
    return

