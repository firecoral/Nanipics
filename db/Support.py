# $Header: //depot/cs/db/Support.py#19 $
import re
from db.Db import get_cursor
from db.Exceptions import DbError, SupportSessionExpired
from p.Utility import session_key

class SupportSession:
    """Return a support session (which includes the database table row) for the logged in support account."""

    def __init__(self, key = None, name = None, password = None):
        if (name):
            if (password == None):
                raise DbError("Name and Password Required")

            c = get_cursor()
            c.execute("""select * from support
                         where name = %s
                         and password = password(%s)""",
                         (name, password))
            if (c.rowcount == 0):
                raise DbError("Invalid Name or Password.  Please try again.")
            self.row = c.fetchone()
            self.name = self.row['name']
            self.row['session_key'] = session_key(30)
            c.execute("""update support set session_key = %s
                         where support_id = %s""",
                         (self.row['session_key'], self.row['support_id']))
            return

        if (key):
            c = get_cursor()
            c.execute("""select * from support
                         where session_key = %s""",
            (key,))
            if (c.rowcount == 0):
                raise SupportSessionExpired()
            self.row = c.fetchone()
            self.name = self.row['name']
            return

        raise SupportSessionExpired()

    def logout():
        """Remove the session key from the support table to log the support account out."""
# Always assume the logout is successful.
        try:
            c = get_cursor()
            c.execute("""update support set session_key = null
                         where support_id = %s""",
                         (self.row['support_id'],))
        except:
            pass

    def column(self, column_name):
        """Retrieve the value of the column specified in column_name."""
        return self.row[column_name]

#
# These functions are used by the support management script.
#

def get_all():
    c = get_cursor()
    c.execute("""select support.support_id, support.name from support""")
    rows = c.fetchall()
    return { 'supports': rows }

def new():
    c = get_cursor()
    c.execute("""insert into support values () """)
                 
    support_id = c.lastrowid
    c.execute("""select support.support_id, support.name from support where support_id = %s""", support_id)
    row = c.fetchone()
    return { 'support': row }

def delete(support_id):
    support_id = re.sub('[^0-9]', '', support_id)
    c = get_cursor()
    c.execute("""delete from support
                 where support_id = %s""",
                 (support_id,))
    return { 'support_id': support_id }

def edit(req):
    """Update the given email template based on the data in the req object."""
    name = req.get('name', "")
    password = req.get('password', "")
    support_id = re.sub('[^0-9]', '', req['support_id'])
    c = get_cursor()
    c.execute("""update support
                 set name = %s,
                 password = password(%s)
                 where support_id = %s""",
                 (name, password, support_id))
    c.execute("""select support.support_id, support.name from support where support_id = %s""", support_id)
    row = c.fetchone()
    return { 'support': row }
