# $Header: //depot/cs/db/EmailTemplate.py#9 $
import re
import db.Db as Db
from db.Db import get_cursor
from p.Utility import validate_input_int
import db.Statics as Statics

#
# Database calls for the following database tables:
#       nav_tile_page
#       nav_tile
#

# product calls:

def nav_tile_page_ecom(nav_tile_page_id):
    """Returns an ecom-friendly nav_tile_page, from a passed-in
       nav_tile_page_id.  Nav tiles are ordered by their respective
       sequences.  See XXX for spec."""

    nav_tile_page_id = int(nav_tile_page_id)

    c = get_cursor()

    ntp = Statics.nav_tile_pages.get_id(nav_tile_page_id)
    ntpe = {
        'name': ntp['name'],
        'splash_html': ntp['splash_html'],
        'instr_html': ntp['instr_html'],
        'tiles': []
    }
    # Iterate through the children (nav_tiles) of this nav_tile_page.
    for nt in ntp['nav_tiles']:
        ntpe['tiles'].append({
            'seq': nt['seq'],
            'link': nt['link'],
            'top_html': nt['top_html'],
            'image_afile': nt['image_afile'],
            'bottom_html': nt['bottom_html']
        })

    return ntpe


#
# Support management page calls for nav tile pages.
#

def get_all():
    return { 'nav_tile_pages': Statics.nav_tile_pages.get() }

def new():
    c = get_cursor()
    c.execute("""insert into nav_tile_page
                 (name)
                 values
                 ('New Nav Tile Page')""")
    nav_tile_page_id = c.lastrowid
    Db.cache_invalidate()
    return { 'nav_tile_page': Statics.nav_tile_pages.get_id(nav_tile_page_id) }

def delete(nav_tile_page_id):
    nav_tile_page_id = int(nav_tile_page_id)
    c = get_cursor()
    c.execute("""delete from nav_tile_page
                 where nav_tile_page_id = %s""",
                 (nav_tile_page_id,))
    Db.cache_invalidate()
    return { 'nav_tile_page_id': nav_tile_page_id }

def edit(req):
    """Update the given nav_tile_page based on the data in the req object."""
    name = req.get('name', "")
    menu_name = req.get('menu_name', "")
    top_menu_seq = validate_input_int(req.get('top_menu_seq', None))
    if top_menu_seq <= 0:
	top_menu_seq = None
    link = req.get('link', "")
    splash_html = req.get('splash_html', "")
    instr_html = req.get('instr_html', "")
    nav_tile_page_id = int(req['nav_tile_page_id'])
    c = get_cursor()
    c.execute("""update nav_tile_page
                 set name = %s,
		 menu_name = %s,
		 top_menu_seq = %s,
                 link = %s,
                 splash_html = %s,
                 instr_html = %s
                 where nav_tile_page_id = %s""",
                 (name, menu_name, top_menu_seq, link, splash_html, instr_html, nav_tile_page_id))
    Db.cache_invalidate()
    return { 'nav_tile_page': Statics.nav_tile_pages.get_id(nav_tile_page_id) }

def resort_tiles(nav_tile_page_id, nav_tile_ids):
    # We use the nav_tile_page_id here just as a safety.  If the 
    # nav_tile doesn't belong to this page, the database isn't changed
    # for it.
    nav_tile_page_id = int(nav_tile_page_id)
    c = get_cursor()
    seq = 1
    for nav_tile_id in nav_tile_ids.split(','):
        nav_tile_id = int(nav_tile_id)
        c.execute("""update nav_tile
                     set seq = %s
                     where nav_tile_page_id = %s
                     and nav_tile_id = %s""",
                     (seq, nav_tile_page_id, nav_tile_id))
        seq += 1

    Db.cache_invalidate()
    # Returning this for no particularly good reason. XXX
    return { 'nav_tile_page_id': nav_tile_page_id }

#
# Support management page calls for nav tiles.
#

def get_all_tiles(nav_tile_page_id):
    nav_tile_page_id = int(nav_tile_page_id)
    ntp = Statics.nav_tile_pages.get_id(nav_tile_page_id)
    return { 'nav_tiles': ntp['nav_tiles'] }

def new_tile(nav_tile_page_id):
    nav_tile_page_id = int(nav_tile_page_id)
    c = get_cursor()
    c.execute("""insert into nav_tile
                 (nav_tile_page_id, name, seq)
		 select
		    %s,
		    "New Nav Tile",
		    1 + coalesce(max(nav_tile.seq), 0) from nav_tile where nav_tile.nav_tile_page_id = %s""",
                 (nav_tile_page_id, nav_tile_page_id))
    nav_tile_id = c.lastrowid
    Db.cache_invalidate()
    return { 'nav_tile': get_tile(nav_tile_page_id, nav_tile_id) }

def delete_tile(nav_tile_page_id, nav_tile_id):
    nav_tile_page_id = int(nav_tile_page_id)
    nav_tile_id = int(nav_tile_id)
    nav_tile = get_tile(nav_tile_page_id, nav_tile_id)
    c = get_cursor()
    c.execute("""delete from nav_tile
                 where nav_tile_id = %s""",
                 (nav_tile_id,))

    c.execute("""update nav_tile
                 set seq = seq - 1
		 where nav_tile_page_id = %s
		 and seq > %s""",
                 (nav_tile_page_id, nav_tile['seq']))
    Db.cache_invalidate()
    return { 'nav_tile_id': nav_tile_id }

def edit_tile(req):
    """Update the given nav_tile based on the data in the req object."""
    name = req.get('name', "")
    menu_name = req.get('menu_name', "")
    link = req.get('link', "")
    image_afile = req.get('image_afile', "")
    top_html = req.get('top_html', "")
    bottom_html = req.get('bottom_html', "")
    nav_tile_id = int(req.get('nav_tile_id', ""))
    nav_tile_page_id = int(req.get('nav_tile_page_id', ""))
    c = get_cursor()
    c.execute("""update nav_tile
                 set name = %s,
                 menu_name = %s,
                 link = %s,
                 image_afile = %s,
                 top_html = %s,
                 bottom_html = %s
                 where nav_tile_id = %s""",
                 (name, menu_name, link, image_afile, top_html, bottom_html, nav_tile_id))
    Db.cache_invalidate()
    return { 'nav_tile': get_tile(nav_tile_page_id, nav_tile_id) }

def get_tile(nav_tile_page_id, nav_tile_id):
    """ This is really only useful here since we never go looking for individual
	tiles anywhere else."""

    # Iterating here is somewhat annoying, but there's not really any
    # justification to improving it since it's a rare event that we need
    # an individual tile.
    ntp = Statics.nav_tile_pages.get_id(nav_tile_page_id)
    for nav_tile in ntp['nav_tiles']:
	if (nav_tile['nav_tile_id'] == nav_tile_id):
	    return nav_tile

def get_landing_pages():
    """ Get a list of names/urls of Product Info Groups, Card Groups, and nav_tile_pages.
	These are useful as pulldowns on the nav_tile editor page."""
    url_list = [];
    ntps = Statics.nav_tile_pages.get()
    for ntp in ntps:
	url_list.append({ 'name': 'Nav Tile Page: {}'.format(ntp['name']), 'url': '/e/nts?ntp_id={}'.format(ntp['nav_tile_page_id']) })

    pdgs = Statics.pi_product_groups.get()
    for pdg in pdgs:
	url_list.append({ 'name': 'Product Info Page: {}'.format(pdg['support_name']), 'url': '/e/pi?pi_pgid={}'.format(pdg['pi_product_group_id']) })

    csgs = Statics.cs_groups.get()
    for csg in csgs:
	url_list.append({ 'name': 'Card Selection Page: {}'.format(csg['name']), 'url': '/e/cs?csg_id={}'.format(csg['cs_group_id']) })
    return url_list

