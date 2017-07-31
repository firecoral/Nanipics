import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email(headers, text, html):

    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')

    from_email = headers['from_email']
    to_email = headers['to_email']
    to_addrs = [to_email]

    msg['Subject'] = headers['subject']
    msg['From'] = from_email
    msg['To'] = to_email

    if 'cc' in headers:
        msg['Cc'] = headers['cc']
        to_addrs.append(headers['cc'])

    if 'bcc' in headers:
        to_addrs.append(headers['bcc'])

    # Record the MIME types of both parts - text/plain and text/html.
    if text != None:
        part1 = MIMEText(text, 'plain')
        msg.attach(part1)
    if html != None:
        part2 = MIMEText(html, 'html')
        msg.attach(part2)

    # Send the message via local SMTP server.
    s = smtplib.SMTP('localhost')
    # sendmail function takes 3 arguments: sender's address, recipient's address
    # and message to send - here it is sent as one string.
    s.sendmail(from_email, to_addrs, msg.as_string())
    s.quit()

def email_test():
    text = "cs email test"
    html = """
    <html><head></head><body>
    cs <b>email</b> test
    </body></html>"""

    dict = {'from_email': 'XXXXX@XXXXX.com', 
            'to_email': 'XXXXX@XXXXX.com',
            'bcc': 'XXXXX@XXXXX.com',
            'subject': 'email module test',
            'text': text,
            'html': html
           }

    send_email(dict, text, html)
