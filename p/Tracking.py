# $Header: //depot/cs/p/Tracking.py#2 $
import re

class TrackingInvalid(Exception):
       def __str__(self):
           return ("Invalid Tracking Id")

class Tracking:
    """Used for various Shopping Cart Pages"""

    def __init__(self, tracking_code):
        try:
            tracking_code = tracking_code.upper()
            self.tracking = {
                'tracking': tracking_code
            }
            usps_services = {
                '001': "First Class Mail",
                '055': "Priority Mail"
            }
            ups_services = {
                '01': "Next Day Air",
                '02': "Second Day Air",
                '03': "Ground"
            }

            match = re.search("^1Z(.*)$", tracking_code)
            if match:
                if not self.ups_check_digit(match.group(1)):
                    raise TrackingInvalid
                self.tracking['vendor'] = "UPS"
                match2 = re.search("^.{8}(..).*$", tracking_code)
                self.tracking['service'] = ups_services.get(match2.group(1), "")
                self.tracking['url'] = "http://wwwapps.ups.com/WebTracking/track?track=yes&trackNums={}".format(tracking_code)
                return

            match = re.search("^\d{22}$", tracking_code)
            if match:
                if not self.check_digit(tracking_code):
                    raise TrackingInvalid
                self.tracking['vendor'] = "USPS"
                match2 = re.search("^..(...).*$", tracking_code)
                self.tracking['service'] = usps_services.get(match2.group(1), "")
                self.tracking['url'] = "http://trkcnfrm1.smi.usps.com/PTSInternetWeb/InterLabelInquiry.do?origTrackNum={}".format(tracking_code)
                return

            match = re.search("^420.{5}(\d{22})$", tracking_code)
            if match:
                if not self.check_digit(match.group(1)):
                    raise TrackingInvalid
                self.tracking['vendor'] = "USPS"
                match2 = re.search("^..(...).*$", tracking_code)
                self.tracking['service'] = usps_services.get(match2.group(1), "")
                self.tracking['url'] = "http://trkcnfrm1.smi.usps.com/PTSInternetWeb/InterLabelInquiry.do?origTrackNum={}".format(tracking_code)
                return

            match = re.search("^420.{5}(\d{26})$", tracking_code)
            if match:
                if not self.check_digit(match.group(1)):
                    raise TrackingInvalid
                self.tracking['vendor'] = "USPS"
                match2 = re.search("^..(...).*$", tracking_code)
                self.tracking['service'] = usps_services.get(match2.group(1), "")
                self.tracking['url'] = "http://trkcnfrm1.smi.usps.com/PTSInternetWeb/InterLabelInquiry.do?origTrackNum={}".format(tracking_code)
                return

            match = re.search("^\d{15}$", tracking_code)
            if match:
                if not self.check_digit(tracking_code):
                    raise TrackingInvalid
                self.tracking['vendor'] = "FedEx"
                self.tracking['service'] = "Ground"
                self.tracking['url'] = "http://www.fedex.com/Tracking?action=track&tracknumbers={}".format(tracking_code)
                return


            match = re.search("^\d{12}$", tracking_code)
            if match:
                if not self.check_fedex(tracking_code):
                    raise TrackingInvalid
                self.tracking['vendor'] = "FedEx"
                self.tracking['service'] = ""
                self.tracking['url'] = "http://www.fedex.com/Tracking?action=track&tracknumbers={}".format(tracking_code)
                return

            raise TrackingInvalid

        except TrackingInvalid:
            self.tracking['vendor'] = ""
            self.tracking['service'] = ""
            self.tracking['url'] = ""
            return

    def get_full(self):
        return self.tracking

    def vendor(self):
        return self.tracking.get('vendor', "")

    def service(self):
        return self.tracking.get('service', "")

    def url(self):
        return self.tracking.get('url', "")

    def ups_check_digit(self, value):
        from string import maketrans
        istr = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ostr = "23456789012345678901234567"
        transtab = maketrans(istr, ostr)
        digits = list(value[::-1].translate(transtab))
        end = len(digits)
        total = 0
        for i in range(1, end, 2):
            total += int(digits[i])
        for i in range(0, end, 2):
            total += int(digits[i]) * 2

        total -= int(digits[0])
        total %= 10
        return not total

    # UPS and FedEx Ground
    def check_digit(self, value):
        # reverse and make a list of the characters
        digits = list(value[::-1])
        end = len(digits)
        total = 0

        for i in range(1, end, 2):
            total += int(digits[i])
        total *= 3;
        for i in range(2, end, 2):
            total += int(digits[i])

        total += int(digits[0])
        total %= 10
        return not total

    def check_fedex(self, value):
        # reverse and make a list of the characters
        digits = list(value[::-1])

        # known to be 12 digits.
        total = 0;

        total += int(digits[1])
        total += int(digits[2]) * 3
        total += int(digits[3]) * 7
        total += int(digits[4])
        total += int(digits[5]) * 3
        total += int(digits[6]) * 7
        total += int(digits[7])
        total += int(digits[8]) * 3
        total += int(digits[9]) * 7
        total += int(digits[10])
        total += int(digits[11]) * 3
        total %= 11
        total -= int(digits[0])
        return not total


