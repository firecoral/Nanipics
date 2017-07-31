import os, math, re, urllib2
import xml.etree.ElementTree as ElementTree
from   xml.sax.saxutils import escape, quoteattr

import db.Db as Db
import db.ImageRender as ImageRender
import db.Lab as Lab
import db.Statics as Statics
from   db.Exceptions import DbError, DbKeyInvalid, JobInvalid
from   p.Tracking import Tracking

# Job statuses must match job_status.job_status_id in the database.
JOB_STATUS_NEW = 1
JOB_STATUS_SUBMITTED = 2
JOB_STATUS_INPROCESS = 3
JOB_STATUS_COMPLETE = 4
JOB_STATUS_CANCELLED = 5

# Job errors must match job_error.job_error_id in the database.
JOB_ERROR_SUBMIT = 1
JOB_ERROR_ASPECT = 2

class Job:
    """Used to add and delete jobs."""

    # the last-created XML file (if any)
    xml = None
    # the path under which we create our populated directory (default: Db.lab_path)
    base_path = None

    def __init__(self, job_id=None, cart_id=None, job_seq=None, job_dict=None):
        try:
            if job_id != None:
                job_id = int(re.sub('[^0-9]', '', str(job_id)))
                c = Db.get_cursor()
                c.execute("""
                    select *
                    from job
                    where job_id = %s""",
                    (job_id,)
                )
                if (c.rowcount == 0):
                    raise DbKeyInvalid("Job not found: {}.".format(job_id))
                self.job = c.fetchone()
            elif cart_id != None and job_seq != None:
                cart_id = int(re.sub('[^0-9]', '', str(cart_id)))
                job_seq = int(re.sub('[^0-9]', '', str(job_seq)))
                c = Db.get_cursor()
                c.execute("""
                    select *
                    from job
                    where
                        cart_id = %s and
                        seq = %s""",
                    (cart_id, job_seq)
                )
                if c.rowcount == 0:
                    raise DbKeyInvalid("Job not found by cart_id {} and seq {}.".format(cart_id, job_seq))
                if c.rowcount > 1:
                    raise DbError("{} jobs found by cart_id {} and seq {}.".format(c.rowcount, cart_id, job_seq))
                self.job = c.fetchone()
            elif job_dict != None:
                cart_id = int(re.sub('[^0-9]', '', str(job_dict['cart_id'])))
                lab_line_id = int(re.sub('[^0-9]', '', str(job_dict['lab_line_id'])))
                lab_shipping_id = int(re.sub('[^0-9]', '', str(job_dict['lab_shipping_id'])))
                c = Db.get_cursor()
                c.execute("""
                    select ifnull(max(seq) + 1, 1) as next_seq
                    from job
                    where cart_id = %s""",
                    (cart_id,)
                )
                next_seq = c.fetchone()['next_seq']
                while True:
                    try:
                        c.execute("""
                            insert into job
                            (cart_id, seq, job_status_id, lab_line_id, lab_shipping_id, create_date)
                            values (%s, %s, %s, %s, %s, now())""",
                            (cart_id, next_seq, JOB_STATUS_NEW, lab_line_id, lab_shipping_id)
                        )
                        break
                    except MySQLdb.IntegrityError:
                        next_seq += 1
                        continue

                job_id = c.lastrowid
                c.execute("""
                    select *
                    from job
                    where job_id = %s""",
                    (job_id,)
                )
                if (c.rowcount == 0):
                    raise DbKeyInvalid('Job not found: {}.'.format(job_id))
                self.job = c.fetchone()
            else:
                raise DbKeyInvalid('Bad arguments given.')

            # Create a subordinate dictionary for the job_status
            self.job['job_status'] = Statics.job_statuses.get_id(self.job['job_status_id'])
            del self.job['job_status_id']

            # Create a tracking record if there is a tracking code
            if self.job['tracking']:
                tracking = Tracking(self.job['tracking'])
                self.job['tracking_data'] = tracking.get_full()

            # We are going to pad the job structures with a lot of extra information here.
            c.execute("""
                select job_item.*, product.name as product_name,
                    line_item.quantity
                from job_item, line_item, product 
                where job_item.job_id = %s
                and job_item.line_item_id = line_item.line_item_id
                and line_item.product_id = product.product_id
                order by job_item.job_item_id""",
                (job_id,)
            )
            self.job['job_items'] = list(c.fetchall())

            # Add the design name
            for job_item in self.job['job_items']:
                c.execute("""
                    select product_design.ecom_name
                    from product_design, build
                    where build.line_item_id = %s
                    and build.product_design_id = product_design.product_design_id
                    limit 1""",
                    (job_item['line_item_id'],)
                )
                job_item['design_name'] = c.fetchone()['ecom_name']

            # Get the lab and lab_line names, mostly for the support tool
            lab_line = Statics.lab_lines.get_id(self.job['lab_line_id'])
            self.job['lab_name'] = Statics.labs.get_id(lab_line['lab_id'])['name']
            self.job['lab_line_name'] = lab_line['name']

        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def get_full(self):
        return self.job

    def shipment_info(self):
        """ Returns a data structure containing shipment information appropriate
            for a consumer. """

        # If the job is not complete, there is no shipping information to return.
        if not self.job['complete_date']:
            return None
        if self.job['job_status']['job_status_id'] != JOB_STATUS_COMPLETE:
            return None
        if not self.job['tracking_data']:
            return None
        products = []
        for job_item in self.job['job_items']:
            products.append({
                'quantity': job_item['quantity'],
                'product_name': job_item['product_name'],
                'design_name': job_item['design_name']
            })

        tracking_data = self.job['tracking_data']
        return {
                'ship_date': self.job['complete_date'],
                'vendor': tracking_data.get('vendor', None),
                'service': tracking_data.get('service', None),
                'url': tracking_data.get('url', None),
                'tracking': tracking_data.get('tracking', None),
                'products': products
            }

    def add_item(self, line_item_id):
        try:
            line_item_id = int(re.sub('[^0-9]', '', str(line_item_id)))
            c = Db.get_cursor()
            c.execute("""
                select ifnull(max(seq) + 1, 1) as next_seq
                from job_item
                where job_id = %s""",
                (self.job['job_id'],)
            )
            next_seq = c.fetchone()['next_seq']
            c.execute("""
                insert into job_item
                (job_id, seq, line_item_id)
                values (%s, %s, %s)""",
                (self.job['job_id'], next_seq, line_item_id)
            )
            job_item_id = c.lastrowid
            c.execute("""
                select *
                from job_item
                where job_item_id = %s""",
                (job_item_id,)
            )
            if (c.rowcount == 0):
                raise DbKeyInvalid('Job-item not found: {}.'.format(job_id))
            self.job['job_items'].append(c.fetchone())
        except DbKeyInvalid as e:
            raise DbKeyInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def delete(self):
        try:
            c = Db.get_cursor()
            c.execute("""
                delete from job_item
                where job_id = %s""",
                (self.job['job_id'],)
            )
            c.execute("""
                delete from job
                where job_id = %s""",
                (self.job['job_id'],)
            )
            self.job = None
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")
        return

    def set_base_path(self, base_path):
        self.base_path = base_path

    def submit(self):
        """Submits a job to a lab.  This includes creating a job_directory, populating it
           with composited images, generating lab-specific XML, posting the XML to the lab,
           and updating the job's status."""

        try:
            job_status_id = self.job['job_status']['job_status_id']
            if job_status_id != JOB_STATUS_NEW:
                raise JobInvalid('Job must be in new state to be submitted.')

            c = Db.get_cursor()
            lab_line = Statics.lab_lines.get_id(self.job['lab_line_id'])
            lab = Statics.labs.get_id(lab_line['lab_id'])

            if lab['lab_id'] == Lab.LAB_DPI:
                self.populate_dpi_dir()
                req = urllib2.Request(lab['submit_url'], self.xml, {'Content-type': 'application/octet-stream'})
                resp = urllib2.urlopen(req).read()
                success, message = self.check_dpi_resp(resp)
            elif lab['lab_id'] == Lab.LAB_IYP:
                self.populate_iyp_dir()
                req = urllib2.Request(lab['submit_url'], self.xml, {'Content-type': 'text/xml; charset=utf-8', 'SOAPAction': '"http://XXXXX/XXXXX/XXXXX"'})
                resp = urllib2.urlopen(req).read()
                success, message = self.check_iyp_resp(resp)

            import db.Cart as Cart
            cart = Cart.ShoppingCart(cart_id = self.job['cart_id'])
            if success:
                self.set_status_id(JOB_STATUS_SUBMITTED)
                c.execute("""
                    update job
                    set job_error_id = null, submit_date = now()
                    where job_id = %s""",
                    (self.job['job_id'],)
                )
                cart.log('Job {} submitted'.format(self.job['job_id']))
                cart.handle_submitted_jobs()
            else:
                c.execute("""
                    update job
                    set job_error_id = %s
                    where job_id = %s""",
                    (JOB_ERROR_SUBMIT, self.job['job_id'])
                )
                cart.log('Job {} submit failed: "{}"'.format(self.job['job_id'], message))

        except JobInvalid as e:
            raise JobInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def populate_dpi_dir(self, dir=None):
        """Creates and populates a DPI-friendly directory (under self.base_path
           or Db.lab_path), which includes the images and the order XML file.
           self.xml is set to the contents of the XML file."""

        c = Db.get_cursor()
        lab_line = Statics.lab_lines.get_id(self.job['lab_line_id'])
        lab = Statics.labs.get_id(lab_line['lab_id'])
        lab_shipping = Statics.lab_shippings.get_id(self.job['lab_shipping_id'])

        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<order orbvendorpassword={} orbvendorid={} labid={} customernumber={} OrderNumber={}>\n'.format(
            quoteattr(lab['submit_password']), quoteattr(lab['submit_login1']), quoteattr('ProDPI3'), quoteattr(str(lab['submit_login2'])), quoteattr('{}-{}'.format(self.job['cart_id'], self.job['seq']))
        )
        # Billing-customer boilerplate, faked (DPI doesn't need or want the real information).
        xml += '  <customer>\n'
        xml += '    <firstname>Nanipics</firstname>\n    <lastname>Orders</lastname>\n    <email>XXXXXX@XXXXXX.com</email>\n'
        xml += '  </customer>\n'
        # "storeid" boilerplate
        xml += '  <extra>\n'
        xml += '    <storeid>Nanipics</storeid>\n'
        xml += '  </extra>\n'

        c.execute("""
            select
                ifnull(ship_first_name, '') as ship_first_name, ifnull(ship_last_name, '') as ship_last_name,
                ship_address1, ifnull(ship_address2, '') as ship_address2, ship_city, ship_state_id,
                ship_postal_code, ifnull(ship_phone, '') as ship_phone, ifnull(email, '') as email
            from address
            where cart_id = %s""",
            (self.job['cart_id'],)
        )
        a_row = c.fetchone()
        xml += '  <shippingaddress>\n'
        xml += '    <firstname>{}</firstname>\n'.format(escape(a_row['ship_first_name']))
        xml += '    <lastname>{}</lastname>\n'.format(escape(a_row['ship_last_name']))
        xml += '    <address1>{}</address1>\n'.format(escape(a_row['ship_address1']))
        xml += '    <address2>{}</address2>\n'.format(escape(a_row['ship_address2']))
        xml += '    <city>{}</city>\n'.format(escape(a_row['ship_city']))
        xml += '    <state>{}</state>\n'.format(escape(a_row['ship_state_id']))
        xml += '    <zip>{}</zip>\n'.format(escape(a_row['ship_postal_code']))
        xml += '    <countrycode>United States</countrycode>\n'
        xml += '    <phone>{}</phone>\n'.format(escape(a_row['ship_phone']))
        xml += '    <email>{}</email>\n'.format(escape(a_row['email']))
        xml += '  </shippingaddress>\n'
        xml += '  <shippingmethod>{}</shippingmethod>\n'.format(escape(lab_shipping['dpi_method']))

        image_dir = '{:02d}/{:02d}/{:06d}'.format(lab['lab_id'], int(str(self.job['job_id'])[-2:]), self.job['job_id'])
        if self.base_path != None:
            image_path = '{}/{}'.format(self.base_path, image_dir)
        else:
            image_path = '{}/{}'.format(Db.lab_path, image_dir)
        if not os.path.isdir(image_path): os.makedirs(image_path)

        job_item_ids = ', '.join([str(ji['job_item_id']) for ji in self.job['job_items']])
        c.execute("""
            select li.product_id, li.quantity, b.build_id, b.lab_product_orientation_id
            from (job_item as ji, line_item as li, build as b)
            where
                ji.job_item_id in ({}) and
                li.line_item_id = ji.line_item_id and
                b.line_item_id = li.line_item_id
            order by ji.seq""".format(job_item_ids)
        )
        ji_rows = c.fetchall()

        # I'd prefer to alternate image and item XML for simplicity, and technically XML
        # is orderless by definition and ROES should be able to handle this.  But all of
        # DPI's other partners strictly follow the ordering shown in the ROES spec - which
        # is "all images" followed by "all items" - and it's quite possible that the ROES
        # implementors expect it.  So I'm playing along.
        image_xml = ''
        item_xml = ''

        # Add the images and items (line_items) to the XML.
        item_id = 1
        for ji_row in ji_rows:
            lpo = Statics.lab_product_orientations.get_id(ji_row['lab_product_orientation_id'])
            lpo_data = lpo['lab_product_orientation_data']

            quantity = ji_row['quantity']
            if lpo_data['dpi_incr_qty'] == 1:
                quantity += 1
            if lpo_data['dpi_div_qty_by'] != None:
                quantity = int(math.ceil(1. * quantity / lpo_data['dpi_div_qty_by']))

            item_xml += '  <item id={} quantity={} price="0.00" totalprice="0.00">\n'.format(quoteattr(str(item_id)), quoteattr(str(quantity)))
            item_xml += '    <template id={} layoutfile={} bounds={} label={}{}>\n'.format(
                quoteattr(lpo_data['dpi_id']), quoteattr(lpo_data['dpi_layoutfile']), quoteattr(lpo_data['dpi_bounds']), quoteattr(lpo_data['dpi_label']),
                ' isdp2book={}'.format(quoteattr(lpo_data['dpi_isdp2book'])) if lpo_data['dpi_isdp2book'] != None else ''
            )
            for lpp in lpo['lab_product_pages']:
                lpp_id = lpp['lab_product_page_id']
                lpp_data = lpp['lab_product_page_data']
                image_id = '{:06d}-{:03d}'.format(ji_row['build_id'], lpp_id)
                lpp_image = ImageRender.lab_page_img(ji_row['build_id'], lpp_id)
                fq_image_name = '{}/{}.jpg'.format(image_path, image_id)
                lpp_image.save(fq_image_name, format='JPEG', quality=100)
                url = 'http://www.nanipics.com/li/{}/{}.jpg'.format(image_dir, image_id)
                filename = '{}.jpg'.format(image_id)
                image_xml += '  <image id={} url={} urlun="" urlpw="" filename={} size={} width={} height={}/>\n'.format(
                    quoteattr(image_id), quoteattr(url), quoteattr(filename), quoteattr(str(os.stat(fq_image_name).st_size)),
                    quoteattr(str(lpp_image.size[0])), quoteattr(str(lpp_image.size[1]))
                )
                item_xml += '      <node id={} input="image" bounds={} rotation="0">\n'.format(quoteattr(lpp_data['dpi_id']), quoteattr(lpp_data['dpi_bounds']))
                item_xml += '        <image id={} crop="0,0,1.0,1.0,0"/>\n'.format(quoteattr(image_id))
                item_xml += '      </node>\n'
            if lpo_data['dpi_option_id'] != None:
                item_xml += '      <option id={} quantity={} price="0.00" label={}/>\n'.format(
                    quoteattr(lpo_data['dpi_option_id']), quoteattr(str(ji_row['quantity'])), quoteattr(lpo_data['dpi_option_label'])
                )
            item_xml += '    </template>\n'
            item_xml += '  </item>\n'
            item_id += 1

        xml += image_xml
        xml += item_xml
        xml += '  <totals totalprice="0.00" taxtotal="0.00" shippingtotal="0.00" producttotal="0.00" orderoptionstotal="0.00"/>\n'
        xml += '</order>\n'

        xml_filepath = '{}/{}.xml'.format(image_path, self.job['job_id'])
        xml_file = open(xml_filepath, 'w')
        xml_file.write(xml)
        xml_file.close()
        self.xml = xml

        return

    def check_dpi_resp(self, resp):
        success = None
        message = None
        for line in resp.splitlines():
            if re.match('<status>success</status>', line) and success == None:
                success = True
            if re.match('<status>failure</status>', line):
                success = False
            m = re.match('<message>(.*)</message>', line)
            if m != None:
                message = m.group(1)
        return success, message

    def populate_iyp_dir(self):
        """Creates and populates a DPI-friendly directory (under self.base_path
           or Db.lab_path), which includes the images and the order XML file.
           self.xml is set to the contents of the XML file."""

        c = Db.get_cursor()
        lab_line = Statics.lab_lines.get_id(self.job['lab_line_id'])
        lab = Statics.labs.get_id(lab_line['lab_id'])
        lab_shipping = Statics.lab_shippings.get_id(self.job['lab_shipping_id'])

        xml  = '<?xml version="1.0" encoding="utf-8"?>\n\n'
        xml += '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n'
        xml += '  <soap:Body>\n'
        xml += '    <SubmitOrder xmlns="http://SellSystems/MfgOrderEntry">\n'
        xml += '      <MfgOrder xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://SellSystems/MfgSchema">\n'
        xml += '        <OrderIdentifier>\n'
        xml += '          <Requestor>{}</Requestor>\n'.format(escape(lab['submit_login1']))
        xml += '          <Identifier>{}-{}</Identifier>\n'.format(escape(self.job['cart_id']), escape(self.job['seq']))
        xml += '        </OrderIdentifier>\n'
        xml += '        <Manufacturer>ImagineYourPhotos</Manufacturer>\n'

        c.execute("""
            select
                ship_first_name, ship_last_name, ship_company_name,
                ifnull(ship_phone, '') as ship_phone, email,
                ship_country_id, ifnull(ship_state_id, '') as ship_state_id, ship_city,
                ship_postal_code, ship_address1, ship_address2
            from address
            where cart_id = %s""",
            (self.job['cart_id'],)
        )
        a_row = c.fetchone()
        xml += '        <DefaultShippingInfo>\n'
        xml += '          <Company>{}</Company>\n'.format(escape(a_row['ship_company_name']))
        xml += '          <FirstMiddleLast>\n'
        xml += '            <FirstName>{}</FirstName>\n'.format(escape(a_row['ship_first_name']))
        xml += '            <LastName>{}</LastName>\n'.format(escape(a_row['ship_last_name']))
        xml += '          </FirstMiddleLast>\n'
        xml += '          <Address1>{}</Address1>\n'.format(escape(a_row['bill_address1']))
        xml += '          <Address2>{}</Address2>\n'.format(escape(a_row['bill_address2']))
        xml += '          <City>{}</City>\n'.format(escape(a_row['ship_city']))
        xml += '          <State-Province>{}</State-Province>\n'.format(escape(a_row['ship_state_id']))
        xml += '          <PostalCode>{}</PostalCode>\n'.format(escape(a_row['ship_postal_code']))
        xml += '          <Country>{}</Country>\n'.format(escape(a_row['ship_country_id']))
        xml += '          <ShippingCarrier>{}</ShippingCarrier>\n'.format(escape(lab_shipping['iyp_carrier']))
        xml += '          <ShippingMethod>{}</ShippingMethod>\n'.format(escape(lab_shipping['iyp_method']))
        xml += '          <Instructions></Instructions>\n'
        xml += '          <ContactPhone>{}</ContactPhone>\n'.format(escape(a_row['ship_phone']))
        xml += '          <ContactEmail>{}</ContactEmail>\n'.format(escape(a_row['email']))
        xml += '        </DefaultShippingInfo>\n'

        image_dir = '{:02d}/{:02d}/{:06d}'.format(lab['lab_id'], int(str(self.job['job_id'])[-2:]), self.job['job_id'])
        if self.base_path != None:
            image_path = '{}/{}'.format(self.base_path, image_dir)
        else:
            image_path = '{}/{}'.format(Db.lab_path, image_dir)
        if not os.path.isdir(image_path): os.makedirs(image_path)

        job_item_ids = ', '.join([str(ji['job_item_id']) for ji in self.job['job_items']])
        c.execute("""
            select ji.seq, li.product_id, li.quantity, b.build_id, b.lab_product_orientation_id
            from (job_item as ji, line_item as li, build as b)
            where
                ji.job_item_id in ({}) and
                li.line_item_id = ji.line_item_id and
                b.line_item_id = li.line_item_id
            order by ji.seq""".format(job_item_ids)
        )
        ji_rows = c.fetchall()

        # Add the images and items to the XML.
        for ji_row in ji_rows:
            lpo = Statics.lab_product_orientations.get_id(ji_row['lab_product_orientation_id'])
            lpo_data = lpo['lab_product_orientation_data']

            xml += '        <MfgLine xsi:type="MfgLineMultiImageType">\n'
            xml += '          <Identifier>{}-{}</Identifier>\n'.format(escape(self.job['job_id']), escape(ji_row['seq']))
            xml += '          <ProductCode>{}</ProductCode>\n'.format(escape(lpo_data['iyp_product_code']))
            xml += '          <Quantity>{}</Quantity>\n'.format(escape(ji_row['quantity']))
            xml += '          <RetailerProductCode>{}</RetailerProductCode>\n'.format(escape(lpo_data['iyp_retailer_product_code']))

            for lpp in lpo['lab_product_pages']:
                lpp_id = lpp['lab_product_page_id']
                lpp_image = ImageRender.lab_page_img(ji_row['build_id'], lpp_id)

                image_id = '{:06d}-{:03d}'.format(ji_row['build_id'], lpp_id)
                fq_image_name = '{}/{}.jpg'.format(image_path, image_id)
                lpp_image.save(fq_image_name, format='JPEG', quality=100)
                url = 'http://www.nanipics.com/li/{}/{}.jpg'.format(image_dir, image_id)

                xml += '          <ImageData>\n'
                xml += '            <ProductImageLocation>{}</ProductImageLocation>\n'.format(escape(url))
                xml += '            <UsageIndex>1</UsageIndex>\n'
                xml += '            <Usage></Usage>\n'
                xml += '            <PlateColor></PlateColor>\n'
                xml += '            <ImageText></ImageText>\n'
                xml += '          </ImageData>\n'

            xml += '      </MfgLine>\n'

        xml += '      </MfgOrder>\n'
        xml += '      <Requestor>{}</Requestor>\n'.format(escape(lab['submit_login1']))
        xml += '    </SubmitOrder>\n'
        xml += '  </soap:Body>\n'
        xml += '</soap:Envelope>\n'

        xml_filepath = '{}/{}.xml'.format(image_path, self.job['job_id'])
        xml_file = open(xml_filepath, 'w')
        xml_file.write(xml)
        xml_file.close()
        self.xml = xml

        return

    def check_iyp_resp(self, resp):
        # A bad xmlns URL from IYP causes node-finding to fail.  (They had bad
        # URLs at some point; not sure if they still do.)
        resp = re.sub(r'xmlns=".*?"', '', resp);
        resp = re.sub(r"xmlns='.*?'", '', resp);

        result_node = ElementTree.fromstring(resp).find('.//SubmitOrderResult')

        success_node = result_node.find('./Success')
        if success_node != None:
            return True, None
        errorinfo_node = result_node.find('./ErrorInfo')
        if errorinfo_node != None:
            extra_info = []
            code_node = errorinfo_node.find('./Code')
            if code_node != None:
                extra_info.append('Code: "{}"'.format(code_node.text))
            message_node = errorinfo_node.find('./Message')
            if message_node != None:
                extra_info.append('Message: "{}"'.format(message_node.text))
            additionalinfo_node = errorinfo_node.find('./AdditionalInfo')
            if additionalinfo_node != None:
                extra_info.append('AdditionalInfo: "{}"'.format(additionalinfo_node.text))
            message = None
            if len(extra_info) > 0:
                return False, '; '.join(extra_info)
            else:
                return False, None
        return False, 'No Success or ErrorInfo nodes found'

    def set_inprocess(self, when=None):
        """Set job to INPROCESS."""

        try:
            job_status_id = self.job['job_status']['job_status_id']
            if job_status_id != JOB_STATUS_SUBMITTED:
                raise JobInvalid('Job must be in submitted state to be set in-process.')

            self.set_status_id(JOB_STATUS_INPROCESS)
            c = Db.get_cursor()
            if when == None:
                c.execute("""
                    update job
                    set job_error_id = null, inprocess_date = now()
                    where job_id = %s""",
                    (self.job['job_id'],)
                )
            else:
                c.execute("""
                    update job
                    set job_error_id = null, inprocess_date = %s
                    where job_id = %s""",
                    (when, self.job['job_id'])
                )

        except JobInvalid as e:
            raise JobInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def complete(self, tracking=None, actual_lab_shipping_id=None, when=None):
        """Set job to COMPLETE."""

        try:
            job_status_id = self.job['job_status']['job_status_id']
            if job_status_id != JOB_STATUS_SUBMITTED and job_status_id != JOB_STATUS_INPROCESS:
                raise JobInvalid('Job must be in submitted or in-process state to be completed.')

            self.set_status_id(JOB_STATUS_COMPLETE)
            c = Db.get_cursor()
            if when == None:
                c.execute("""
                    update job
                    set job_error_id = null, complete_date = now(), tracking = %s, actual_lab_shipping_id = %s
                    where job_id = %s""",
                    (tracking, self.job['job_id'], actual_lab_shipping_id)
                )
            else:
                c.execute("""
                    update job
                    set job_error_id = null, complete_date = %s, tracking = %s, actual_lab_shipping_id = %s
                    where job_id = %s""",
                    (when, tracking, self.job['job_id'], actual_lab_shipping_id)
                )

        except JobInvalid as e:
            raise JobInvalid(e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print e.__class__.__name__ + ": " + str(e)
            raise DbError("Internal error")

    def is_complete_or_cancelled(self):
        job_status_id = self.job['job_status']['job_status_id']
        return job_status_id == JOB_STATUS_COMPLETE or job_status_id == JOB_STATUS_CANCELLED

    def job_id(self):
        return self.job['job_id']

    def cart_id(self):
        return self.job['cart_id']

    def set_status_id(self, status_id):
            """ This sets a new job_status_id on the job.  Since changes in status
                often affect more than just the job_status_id, this function should
                probably only be used by Job.py unless you know exactly what
                you are doing."""
            c = Db.get_cursor()
            c.execute("""
                update job
                set job_status_id = %s
                where job_id = %s""",
                (status_id,
                self.job['job_id']))
            self.job['job_status'] = Statics.job_statuses.get_id(status_id)

