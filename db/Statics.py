import db.Db as Db
from db.Db import get_cursor

def get_card_colors():
    c = get_cursor()
    c.execute("select * from card_color order by card_color_id")
    card_colors = c.fetchall()
    return card_colors

def get_card_formats():
    c = get_cursor()
    c.execute("select * from card_format order by card_format_id")
    card_formats = c.fetchall()
    return card_formats

def get_card_sizes():
    c = get_cursor()
    c.execute("select * from card_size order by card_size_id")
    card_sizes = c.fetchall()
    return card_sizes

def get_cart_statuses():
    c = get_cursor()
    c.execute("select * from cart_status order by cart_status_id")
    cart_statuses = c.fetchall()
    return cart_statuses

def get_job_statuses():
    c = get_cursor()
    c.execute("select * from job_status order by job_status_id")
    job_statuses = c.fetchall()
    return job_statuses

def get_cs_groups():
    c = get_cursor()
    c.execute("select * from cs_group order by cs_group_id")
    cs_groups = c.fetchall()
    return cs_groups

def get_fonts():
    c = get_cursor()
    c.execute("select * from font order by font_id")
    fonts = c.fetchall()
    return fonts

def get_fontsizes():
    c = get_cursor()
    c.execute("select * from fontsize order by fontsize_id")
    fontsizes = c.fetchall()
    return fontsizes

def get_gravities():
    c = get_cursor()
    c.execute("select * from gravity order by gravity_id")
    gravities = c.fetchall()
    return gravities

def get_lab_lines():
    c = get_cursor()
    c.execute("select * from lab_line order by lab_line_id")
    lab_lines = c.fetchall()
    return lab_lines

def get_lab_product_orientations():
    c = get_cursor()
    c.execute("select * from lab_product_orientation")
    lpos = c.fetchall()
    for lpo in lpos:
        c.execute("""
            select *
            from lab_product_orientation_data
            where lab_product_orientation_id = %s""",
            (lpo['lab_product_orientation_id'],)
        )
        lpo['lab_product_orientation_data'] = c.fetchone()
        c.execute("""
            select *
            from lab_product_page
            where lab_product_orientation_id = %s
            order by seq""",
            (lpo['lab_product_orientation_id'],)
        )
        lpo['lab_product_pages'] = c.fetchall()
        for lpp in lpo['lab_product_pages']:
            c.execute("""
                select *
                from lab_product_page_data
                where lab_product_page_id = %s""",
                (lpp['lab_product_page_id'],)
            )
            lpp['lab_product_page_data'] = c.fetchone()
            c.execute("""
                select *
                from lab_product_islot
                where lab_product_page_id = %s""",
                (lpp['lab_product_page_id'],)
            )
            lpp['lab_product_islots'] = c.fetchall()
    return lpos

def get_lab_products():
    c = get_cursor()
    c.execute("select * from lab_product order by lab_product_id")
    lps = c.fetchall()
    return lps

def get_lab_shippings():
    c = get_cursor()
    c.execute("select * from lab_shipping order by lab_shipping_id")
    lab_shippings = c.fetchall()
    return lab_shippings

def get_labs():
    c = get_cursor()
    c.execute("select * from lab order by lab_id")
    labs = c.fetchall()
    return labs

def get_menu_data():
    data = '<ul class="sf-menu">'
    c = get_cursor()
    c.execute("select * from nav_tile_page where top_menu_seq > 0 order by top_menu_seq")
    ntps = c.fetchall()
    for ntp in ntps:
        data += '<li><a href="{}">{}</a>'.format(ntp['link'], ntp['menu_name'])
        c.execute("""select * from nav_tile
                     where nav_tile_page_id = %s
                     and menu_name != ''
                     order by seq""",
                     (ntp['nav_tile_page_id'],))
        nts = c.fetchall()
	if c.rowcount > 0:
            data += '<ul>'
            for nt in nts: 
                data += '<li><a href="{}">{}</a>'.format(nt['link'], nt['menu_name'])

            data += '</ul>'
        data += '</li>'
    data += '</ul>'
    return data

def get_nav_tile_pages():
    c = get_cursor()
    c.execute("select * from nav_tile_page order by nav_tile_page_id")
    nav_tile_pages = c.fetchall()
    # Get the individual tiles for each page.
    for nav_tile_page in nav_tile_pages:
        c.execute("""select * from nav_tile
                     where nav_tile.nav_tile_page_id = %s
                     order by nav_tile.seq""",
                     (nav_tile_page['nav_tile_page_id'],))
	if (c.rowcount == 0):
	    nav_tile_page['nav_tiles'] = []
	else:
	    nav_tiles = c.fetchall()
	    nav_tile_page['nav_tiles'] = nav_tiles

    return nav_tile_pages

def get_orientations():
    c = get_cursor()
    c.execute("select * from orientation order by orientation_id")
    orientations = c.fetchall()
    return orientations

# We cache pi_product_groups since they are a relatively small, frequently accessed table.
# The pi_design_groups table serves a similar function but may be a lot larger and a lot
# less frequently accessed, so we'll continue to do direct database access for them.

def get_pi_product_groups():
    c = get_cursor()
    c.execute("select * from pi_product_group order by pi_product_group_id")
    pi_product_groups = c.fetchall()
    return pi_product_groups

#
# All product pricing is now stored in a separate table, product_price,
# even products with single prices. We're including the array of prices
# in the static products table.  The quantity specified in the product_price
# table represents the point where the given unit price value begins.  One(1)
# is the default value.
#

def get_products():
    c = get_cursor()
    c.execute("""select *
                 from product
                 where is_available = 1
                 order by product_id""")
    products = c.fetchall()
    for product in products:
        c.execute("""select *
                     from product_orientation
                     where product_id = %s
                     order by orientation_id""",
                     (product['product_id'],))
        product['product_orientations'] = c.fetchall()
        for po in product['product_orientations']:
            c.execute("""select *
                         from product_page
                         where product_orientation_id = %s
                         order by seq""",
                         (po['product_orientation_id'],))
            po['product_pages'] = c.fetchall()

	product['product_pricing'] = []
        c.execute("""select * from product_price
                     where product_id = %s
                     order by min_quantity""",
                     (product['product_id'],))
	if (c.rowcount == 0):
            print "Missing price (product_id {}): {}".format(product['product_id'], product['name'])
            product['is_available'] = 0
	    product['product_pricing'] = []
	else:
	    from decimal import Decimal
	    price_min = Decimal(1000000.00)
	    price_max = Decimal(0.00)
	    sale_price_min = Decimal(1000000.00)
	    sale_price_max = Decimal(0.00)
	    prices = c.fetchall()
	    # derive a 'max_quantity' for these prices
	    max_price = len(prices)
	    for i in range(max_price):
		price = prices[i]

		cur_price = price['price']
		cur_sale = price['sale_price']
		if cur_price > 0 and cur_price < price_min:
		    price_min = cur_price
		if cur_price > price_max:
		    price_max = cur_price
		if cur_sale > 0 and cur_sale < sale_price_min:
		    sale_price_min = cur_sale
		if cur_sale > sale_price_max:
		    sale_price_max = cur_sale

		if i == max_price - 1:
		    price['max_quantity'] = 0;
		else:
		    price['max_quantity'] = prices[i+1]['min_quantity'] - 1
	    price_range = {}
            # Originally, we showed an entire price range for price and sale
            # price (as set up below).  Andrew has decided only to show the
            # minimum price, so we've added that to the object below.  The
            # older price range is still around if we ever decide to use it
            # in the future, but it is probably no longer used.
            if price_min < 0.00:
                print "Price $0.00: {}".format(product['name'])
                product['is_available'] = 0
                product['product_pricing'] = []
            else:
                if price_min < 1000000 and price_max > 0:
                    if price_min != price_max:
                        price_range['price'] = '$' + str(price_min) + ' - $' + str(price_max)
                    price_range['price_min'] = price_min;
                if sale_price_min < 1000000 and sale_price_max > 0:
                    if sale_price_min != sale_price_max:
                        price_range['sale_price'] = '$' + str(sale_price_min) + ' - $' + str(sale_price_max)
                    price_range['sale_price_min'] = sale_price_min;
                product['price_range'] = price_range
                product['product_pricing'] = prices
    products = [product for product in products if product['is_available']]
    return products

def get_product_orientations():
    c = get_cursor()
    c.execute("select * from product_orientation order by product_orientation_id")
    product_orientations = c.fetchall()
    return product_orientations

def get_shipping_classes():
    c = get_cursor()
    c.execute("select * from shipping_class order by shipping_class_id")
    shipping_classes = c.fetchall()
    return shipping_classes

def get_shipping_costs():
    c = get_cursor()
    c.execute("select * from shipping_cost order by shipping_cost_id")
    shipping_costs = c.fetchall()
    return shipping_costs

def get_shipping_surcharges():
    c = get_cursor()
    c.execute("select * from shipping_surcharge order by shipping_surcharge_id")
    shipping_surcharges = c.fetchall()
    return shipping_surcharges

def get_shippings():
    c = get_cursor()
    c.execute("select * from shipping order by shipping_id")
    shippings = c.fetchall()
    return shippings

def get_states():
    c = get_cursor()
    # Limit severely for now
    c.execute("""
        select state_id, name
        from state
        where country_id = 'US'
        and available = 'y'
        order by seq""")
    states = c.fetchall()
    return states

def get_taxes():
    c = get_cursor()
    # Limit severely for now
    c.execute("""
        select state_id, tax_name, tax
        from tax
        where country_id = 'US'""")
    taxes = c.fetchall()
    return taxes

def get_tints():
    c = get_cursor()
    c.execute("select * from tint order by tint_id")
    tints = c.fetchall()
    return tints

def get_type2_fonts():
    c = get_cursor()
    c.execute("select * from font where is_type2_usable = 1 order by name")
    type2_fonts = c.fetchall()
    return type2_fonts

def get_type2_fontsizes():
    c = get_cursor()
    c.execute("select * from fontsize where is_type2_usable = 1 order by max_pointsize")
    type2_fontsizes = c.fetchall()
    return type2_fontsizes

def get_type2_gravities():
    c = get_cursor()
    c.execute("select * from gravity where is_type2_usable = 1 order by gravity_id")
    type2_gravities = c.fetchall()
    return type2_gravities

# registration functions; Db.Cache.__init__() adds an entry for each,
# but doesn't populate the data.

card_colors = Db.Cache("card_colors", "card_color_id", get_card_colors)
card_formats = Db.Cache("card_formats", "card_format_id", get_card_formats)
card_sizes = Db.Cache("card_sizes", "card_size_id", get_card_sizes)
cart_statuses = Db.Cache("cart_statuses", "cart_status_id", get_cart_statuses)
job_statuses = Db.Cache("job_statuses", "job_status_id", get_job_statuses)
cs_groups = Db.Cache("cs_groups", "cs_group_id", get_cs_groups)
fonts = Db.Cache("fonts", "font_id", get_fonts)
fontsizes = Db.Cache("fontsizes", "fontsize_id", get_fontsizes)
gravities = Db.Cache("gravities", "gravity_id", get_gravities)
lab_lines = Db.Cache("lab_lines", "lab_line_id", get_lab_lines)
lab_product_orientations = Db.Cache("lab_product_orientations", "lab_product_orientation_id", get_lab_product_orientations)
lab_products = Db.Cache("lab_products", "lab_product_id", get_lab_products)
lab_shippings = Db.Cache("lab_shippings", "lab_shipping_id", get_lab_shippings)
labs = Db.Cache("labs", "lab_id", get_labs)
menu_data = Db.Cache("menu_data", None, get_menu_data)
nav_tile_pages = Db.Cache("nav_tile_pages", "nav_tile_page_id", get_nav_tile_pages)
orientations = Db.Cache("orientations", "orientation_id", get_orientations)
pi_product_groups = Db.Cache("pi_product_groups", "pi_product_group_id", get_pi_product_groups)
products = Db.Cache("products", "product_id", get_products)
product_orientations = Db.Cache("product_orientations", "product_orientation_id", get_product_orientations)
shipping_classes = Db.Cache("shipping_classes", "shipping_class_id", get_shipping_classes)
shipping_costs = Db.Cache("shipping_costs", "shipping_cost_id", get_shipping_costs)
shipping_surcharges = Db.Cache("shipping_surcharges", "shipping_surcharge_id", get_shipping_surcharges)
shippings = Db.Cache("shippings", "shipping_id", get_shippings)
states = Db.Cache("states", "state_id", get_states)
taxes = Db.Cache("taxes", "state_id", get_taxes)
tints = Db.Cache("tints", "tint_id", get_tints)
type2_fonts = Db.Cache("font", "font_id", get_type2_fonts)
type2_fontsizes = Db.Cache("fontsize", "fontsize_id", get_type2_fontsizes)
type2_gravities = Db.Cache("gravity", "gravity_id", get_type2_gravities)

