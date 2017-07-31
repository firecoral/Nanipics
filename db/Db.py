import MySQLdb
import MySQLdb.cursors
from datetime import datetime
import pprint

cached_objects = {}
cache_time = datetime(1970, 1, 1)
stats = { 'try': 0, 'miss': 0, 'invalidate': 0 }
# We'd rather have these paths in the httpd config, but we couldn't find a way to
# have them appear in os.environ.  We could put them in /etc/profile during server
# deploy, but we decided that putting them in the settings table, though awkward,
# is better than further complicating our deploy process.
asset_path = None
lab_path = None
tmp_path = None
public_key_id = None
auth_id = None
auth_key = None

def init(luser, lpasswd, lhost='d1-cs.nanipics.local'):
    global user, passwd, host
    user = luser
    passwd = lpasswd
    host = lhost
    from timeit import Timer
    t = Timer("precache()", "from db.Db import precache")
    from os import getpid
    # Turn off for now.
    #print "{0}: Db precache built {1:4.2f} seconds".format(getpid(), t.timeit(number=1))

def start_transaction():
    global cursor, cache_time, asset_path, lab_path, tmp_path, public_key_id, auth_id, auth_key

    conn = get_conn()
    cursor = conn.cursor()

    # Force datetime values in this connection to UTC
    cursor.execute("set time_zone='UTC'")
    cursor.execute("""
        select db_cache, asset_path, lab_path, tmp_path, public_key_id, auth_id, auth_key
        from settings limit 1""")
    date = cursor.fetchone()
    conn.commit()
    if date['db_cache'] > cache_time:
        from os import getpid
        # off for now.
        # print "{}: Flushing cache {} > {}".format(getpid(), date['db_cache'], cache_time)
        cache_time = date['db_cache']
        asset_path = date['asset_path']
        lab_path = date['lab_path']
        tmp_path = date['tmp_path']
        public_key_id = date['public_key_id']
        auth_id = date['auth_id']
        auth_key = date['auth_key']
        for key, cache in cached_objects.iteritems():
            cache.invalidate()

def get_conn():
    global conn

    try:
        if 'conn' not in globals():
            raise MySQLdb.OperationalError
        conn.ping()
    except (MySQLdb.OperationalError, MySQLdb.InterfaceError):
        conn = MySQLdb.connect(
            host = host,
            user = user,
            passwd = passwd,
            db = 'cs',
            cursorclass = MySQLdb.cursors.DictCursor
        )

    return conn

def get_cursor():
    global cursor

    assert cursor != None, 'Cursor is not defined'
    return cursor

def finish_transaction():
    global cursor

    conn = get_conn()
    conn.commit()
    cursor.close()
    cursor = None

def cancel_transaction():
    global cursor

    conn = get_conn()
    conn.rollback()
    cursor.close()
    cursor = None


class Cache:
    """We want to build some tables and cache them in the thread's memory.
       This really should only be used with relatively non-volatile tables.
       Originally, this was designed to index mult-row database tables, but
       has now be extended to just manage blobs of data.  Use key = None for
       non-table data."""

    def __init__(self, table, key, builder):
        if table in cached_objects:
            return None
        self.table = table
        self.key = key
        self.builder = builder
        self.data = None
        self.index = None
        cached_objects[self.table] = self

    def build(self):
        # print "building {}".format(self.table)
        stats['miss'] += 1
        self.data = self.builder()
        self.index = {}
        # Only build the index table if a key string was provided.
        # This check was added because we wanted to cache non-table objects.
        if self.key != None:
            for row in self.data:
                self.index[row[self.key]] = row
        # these calls add about 10 seconds to build time.
        # they should probably be off by default
        #pp = pprint.PrettyPrinter(indent=4)
        #self.pretty = pp.pformat(self.data)
        self.pretty = "Not Available"
	#from pympler.asizeof import asizeof
        #print "built {}, cache_size: {}, length: {}".format(self.table, asizeof(self), len(self.data))

    def invalidate(self):
        # print "invalidating {}".format(self.table)
        self.data = None

    def get(self):
        stats['try'] += 1
        if not self.data:
            self.build()
        return self.data

    def get_id(self, id):
        if self.key == None:
            raise Exception("Unindexed cache item does not support get_id()");

        stats['try'] += 1
        if not self.data:
            self.build()
        return self.index[id]

    def get_ids(self):
        if self.key == None:
            raise Exception("Unindexed cache item does not support get_ids()");

        stats['try'] += 1
        if not self.data:
            self.build()
        return self.index

    def get_pretty(self):
        return self.pretty


def cache_invalidate():
    global cache_time
    stats['invalidate'] += 1
    c = get_cursor()
    c.execute("update settings set db_cache=now()")
    c.execute("select db_cache, asset_path, lab_path, tmp_path from settings limit 1")
    date = c.fetchone()
    cache_time = date['db_cache']
    asset_path = date['asset_path']
    lab_path = date['lab_path']
    tmp_path = date['tmp_path']
    for key, cache in cached_objects.iteritems():
        cache.data = None
        cache.index = None

def precache():
    """Build a precache on startup"""
    import db.Statics as Statics

    # data populating functions

    Statics.card_colors.get()
    Statics.card_formats.get()
    Statics.card_sizes.get()
    Statics.cart_statuses.get()
    Statics.cs_groups.get()
    Statics.fonts.get()
    Statics.fontsizes.get()
    Statics.gravities.get()
    Statics.lab_lines.get()
    Statics.lab_product_orientations.get()
    Statics.lab_products.get()
    Statics.lab_shippings.get()
    Statics.labs.get()
    Statics.menu_data.get()
    Statics.nav_tile_pages.get()
    Statics.orientations.get()
    Statics.pi_product_groups.get()
    Statics.products.get()
    Statics.product_orientations.get()
    Statics.shipping_classes.get()
    Statics.shipping_costs.get()
    Statics.shipping_surcharges.get()
    Statics.shippings.get()
    Statics.states.get()
    Statics.taxes.get()
    Statics.tints.get()
    Statics.type2_fonts.get()
    Statics.type2_fontsizes.get()
    Statics.type2_gravities.get()

