# $Header: //depot/cs/db/Product.py#117 $

import re, Image, StringIO

import db.Db as Db
import db.Statics as Statics
from   db.Db import get_cursor
from   db.Exceptions import DbError, DbKeyInvalid

#
# Database calls for the following database tables:
#       product
#       product_page
#       product_design
#       product_design_detail_image
#       cs_group
#       pi_product_group
#       pi_design_group
#       design_page
#       page_layout_group
#       page_layout
#       design_page_layout
#       design_islot
#       design_tslot
#

# Used for the CSV product editing to determine how many columns of
# variable pricing we will show.  Note that there is no actual database
# limit on the number of prices - just the number editable in CSV.
CSVPRICECOUNT = 10

# product calls:

def product_ecom(product_id):
    """Returns an ecom-friendly product object.  See spec at http://sdrv.ms/14wYR3Q.

       Raises DbKeyInvalid on invalid database key;
              DbError on database inconsistency (failed assertion)."""

    c = get_cursor()

    product_id = int(product_id)

    p_row = Statics.products.get_id(product_id)
    lab_product = Statics.lab_products.get_id(product_id)

    pages = []
    for product_page in p_row['product_orientations'][0]['product_pages']:
        pages.append({
            'seq': product_page['seq'],
            'blockout_afile': product_page['blockout_afile'],
            'aspect': product_page['nom_width'] / product_page['nom_height']
        })
    product = {
        'name': p_row['name'],
        'prices': p_row['product_pricing'],
        'price_range': p_row.get('price_range', {}),
        'sale_image': None,   # placeholder; TBD/TBI
        'pages': pages,
        'pi_show_icon': p_row['pi_show_icon'] == 1,
        'pb_view_descs': p_row['pb_view_descs'],
        'quantity_base': lab_product['quantity_base'],
        'quantity_incr': lab_product['quantity_incr'],
        'quantity_name': lab_product['quantity_name'],
        'uplifts': [
          # placeholder; TBD/TBI
        ]
    }

    return product

def base_quantity(product_id):
    """Returns lab_product.quantity_base for the given product."""
    lab_product = Statics.lab_products.get_id(product_id)
    return lab_product['quantity_base']

def unit_price(product_id, quantity):
    """Returns the unit price for this product based on the quantity."""
    product = Statics.products.get_id(product_id)
    for price in product['product_pricing']:
        # Assumes that product.prices is sorted by max_quantity, ascending.
        if price['max_quantity'] == 0 or price['max_quantity'] >= quantity:
            if price['sale_price'] > 0:
                return price['sale_price']
            else:
                return price['price']
    raise DbError("No pricing available for product_id: {}, quantity: {}".format(product_id, quantity))


def product_design(product_design_id):
    "Returns a product_design row."

    product_design_id = int(product_design_id)

    c = get_cursor()

    c.execute("""
        select *
        from product_design
        where product_design_id = %s""",
        (product_design_id,)
    )
    if (c.rowcount == 0):
        raise DbKeyInvalid("Product_design not found by product_design_id: {}.".format(product_design_id))
    if (c.rowcount > 1):
        raise DbError("Multiple product_designs found by product_design_id: {}.".format(product_design_id))
    pd = c.fetchone()

    return pd

def product_designs_ecom(product_design_id):
    """Returns a set of ecom-friendly, orientation-linked product_designs, from a passed-in
       product_design_id.  Pages, and slots within the pages, are ordered by their respective
       sequences."""

    product_design_id = int(product_design_id)

    c = get_cursor()

    c.execute("""
        select pd.product_design_id, pd.product_id,
            pd.orientation_id, pd.pb_product_design_pair_id,
            pd.ecom_name
        from (product_design as pd, product as p)
        where pd.product_design_id = %s
        and pd.product_id = p.product_id
        and p.is_available = 1
        order by pd.orientation_id""",
        (product_design_id,)
    )
    pd_rows = c.fetchall()
    if pd_rows[0]['pb_product_design_pair_id'] != None:
        c.execute("""
            select product_design_id, product_id, orientation_id, ecom_name
            from product_design
            where pb_product_design_pair_id = %s""",
            (pd_rows[0]['pb_product_design_pair_id'],)
        )
        pd_rows = c.fetchall()

    pds = []
    for pd_row in pd_rows:
        product = Statics.products.get_id(pd_row['product_id'])
        pd = {
            'pd_id': pd_row['product_design_id'],
            'ecom_name': pd_row['ecom_name'],
            'orientation': Statics.orientations.get_id(pd_row['orientation_id'])['name'],
            'open_pages': product['pb_open_pages'] == 1,
            'pages': []
        }

        c.execute("""
            select dp.product_page_id, dp.page_layout_group_id, pp.seq, pp.ecom_name, pp.icon_afile, pp.blockout_afile
            from (design_page as dp, product_page as pp)
            where
                dp.product_design_id = %s and
                pp.product_page_id = dp.product_page_id
            order by pp.seq""",
            (pd_row['product_design_id'],)
        )
        dp_rows = c.fetchall()
        for dp_row in dp_rows:
            page = {
                'pp_id': dp_row['product_page_id'],
                'layout_group_id': dp_row['page_layout_group_id'],
                'seq': dp_row['seq'],
                'name': dp_row['ecom_name'],
                'icon': dp_row['icon_afile'],
                'blockout': dp_row['blockout_afile'],
                'options': []
            }
            pd['pages'].append(page)
        pds.append(pd)

    return pds

def delete_product_designs(product_design_ids):
    """Deletes a set of product_designs, including subordinate rows.
       Returns lists of newly-orphaned page_layout_groups and newly-invalid builds."""

    c = get_cursor()

    pd_ids_str = ','.join([str(r) for r in product_design_ids])
    c.execute("""
        select distinct page_layout_group_id
        from design_page
        where product_design_id in ({})""".format(pd_ids_str)
    )
    pre_plg_ids = set([r['page_layout_group_id'] for r in c.fetchall()])
    
    c.execute("""
        delete from design_page
        where product_design_id in ({})""".format(pd_ids_str)
    )
    c.execute("""
        delete from product_design_detail_image
        where product_design_id in ({})""".format(pd_ids_str)
    )
    c.execute("""
        delete from product_design
        where product_design_id in ({})""".format(pd_ids_str)
    )
    
    pre_plg_ids_str = ','.join([str(r) for r in pre_plg_ids])
    c.execute("""
        select distinct page_layout_group_id
        from design_page
        where page_layout_group_id in ({})""".format(pre_plg_ids_str)
    )
    post_plg_ids = set([r['page_layout_group_id'] for r in c.fetchall()])
    orph_plg_ids = pre_plg_ids - post_plg_ids

    c.execute("""
        select build_id
        from build
        where product_design_id in ({})""".format(pd_ids_str)
    )
    build_ids = [b['build_id'] for b in c.fetchall()]

    return list(orph_plg_ids), list(build_ids)

def delete_page_layout_groups(page_layout_group_ids):
    """Deletes a set of page_layout_groups, including subordinate rows.
       Returns lists of newly-invalid build_pages, build_images, and build_texts."""

    if len(page_layout_group_ids) == 0:
        return [], [], []

    c = get_cursor()

    plg_ids_str = ','.join([str(p) for p in page_layout_group_ids])
    c.execute("""
        select distinct page_layout_id
        from page_layout
        where page_layout_group_id in ({})""".format(plg_ids_str)
    )
    pl_ids = [r['page_layout_id'] for r in c.fetchall()]

    empty_plg_ids, inv_bp_ids, inv_bi_ids, inv_bt_ids = delete_page_layouts(pl_ids)

    c.execute("""
        delete from page_layout_group
        where page_layout_group_id in ({})""".format(plg_ids_str)
    )

    return inv_bp_ids, inv_bi_ids, inv_bt_ids

def delete_page_layouts(page_layout_ids):
    """Deletes a set of page_layouts, including subordinate rows.
       Returns lists of newly-emptied page_layout_groups and newly-invalid
       build_pages, build_images, and build_texts."""

    if len(page_layout_ids) == 0:
        return [], [], [], []

    c = get_cursor()

    pl_ids_str = ','.join([str(p) for p in page_layout_ids])

    # Grab page_layout_ids to see if we've emptied any later.
    c.execute("""
        select distinct page_layout_group_id
        from page_layout
        where page_layout_id in ({})""".format(pl_ids_str)
    )
    plg_ids_str = ','.join([str(r['page_layout_group_id']) for r in c.fetchall()])

    c.execute("""
        select distinct design_page_layout_id
        from design_page_layout
        where page_layout_id in ({})""".format(pl_ids_str)
    )
    dpl_ids_str = ','.join([str(r['design_page_layout_id']) for r in c.fetchall()])

    c.execute("""
        select design_islot_id
        from design_islot
        where design_page_layout_id in ({})""".format(dpl_ids_str)
    )
    di_ids = [r['design_islot_id'] for r in c.fetchall()]
    if len(di_ids) > 0:
        di_ids_str = ','.join([str(di_id) for di_id in di_ids])
        c.execute("""
            delete from design_islot
            where design_islot_id in ({})""".format(di_ids_str)
        )

    c.execute("""
        select design_tslot_id
        from design_tslot
        where design_page_layout_id in ({})""".format(dpl_ids_str)
    )
    dt_ids = [r['design_tslot_id'] for r in c.fetchall()]
    if len(dt_ids) > 0:
        dt_ids_str = ','.join([str(dt_id) for dt_id in dt_ids])
        c.execute("""
            delete from design_tslot
            where design_tslot_id in ({})""".format(dt_ids_str)
        )

    c.execute("""
        delete from design_page_layout
        where design_page_layout_id in ({})""".format(dpl_ids_str)
    )

    c.execute("""
        delete from page_layout
        where page_layout_id in ({})""".format(pl_ids_str)
    )

    c.execute("""
        select plg.page_layout_group_id, count(pl.page_layout_id) as c
        from (page_layout_group as plg)
        left join (page_layout as pl) on
             pl.page_layout_group_id = plg.page_layout_group_id
        where plg.page_layout_group_id in ({})
        group by plg.page_layout_group_id
        having c = 0
        order by plg.page_layout_group_id""".format(plg_ids_str)
    )
    empty_plg_ids = [r['page_layout_group_id'] for r in c.fetchall()]

    c.execute("""
        select distinct build_page_id
        from build_page
        where design_page_layout_id in ({})""".format(dpl_ids_str)
    )
    inv_bp_ids = [b['build_page_id'] for b in c.fetchall()]

    inv_bi_ids = []
    if len(di_ids) > 0:
        di_ids_str = ','.join([str(di_id) for di_id in di_ids])
        c.execute("""
            select distinct build_image_id
            from build_image
            where design_islot_id in ({})""".format(di_ids_str)
        )
        inv_bi_ids = [b['build_image_id'] for b in c.fetchall()]

    inv_bt_ids = []
    if len(dt_ids) > 0:
        dt_ids_str = ','.join([str(dt_id) for dt_id in dt_ids])
        c.execute("""
            select distinct build_text_id
            from build_text
            where design_tslot_id in ({})""".format(dt_ids_str)
        )
        inv_bt_ids = [b['build_text_id'] for b in c.fetchall()]

    return empty_plg_ids, inv_bp_ids, inv_bi_ids, inv_bt_ids

def cs_group_ecom(cs_group_id):
    """Returns an ecom-friendly card-selection group.
       Entries are ordered by product_design_id."""

    c = get_cursor()

    cg = Statics.cs_groups.get_id(int(cs_group_id))
    cge = {
        # csgi_key is used as a key to store the last page visited.
        'csgi_key': "csgi.{}".format(cs_group_id),
        'name': cg['name'],
        'pds': [],
        'traits': None   # populated from 'traits' variable below
    }

    c.execute("""
        select
            pd.product_design_id, pd.orientation_id, pd.icon_afile, pd.card_color_id, pd.ecom_name as design_name,
            p.name as prod_name, p.card_format_id, p.card_size_id, pd.product_id
        from (product_design as pd, product as p)
        where
            pd.cs_group_id = %s and
            p.product_id = pd.product_id
        order by pd.cs_seq""",
        (cs_group_id,)
    )
    rows = c.fetchall()

    # This will be used to drive the left-side filtering menus on the product-info page.
    # This is actually an intermediate data structure which is easy to populate in python
    # from the database.  After we're done, we rearrange it into a form that is friendlier
    # to the product-info page, and attach it to cge['trait_groups'].
    #
    # This structure compactly illustrated (other entries are similar):
    #
    # '# of Photos': [{'num_slots_2': { <name and qty> }, 'num_slots_0': { <name and qty> }, etc.}]

    trait_groups = {
        '# of Photos': {},
        'Card Orientation': {},
        'Card Format': {},
        'Sizes': {},
        'Colors': {}
    }

    for row in rows:
        product = Statics.products.get_id(row['product_id'])
        pd = {
            'pd_id': row['product_design_id'],
            'icon': row['icon_afile'],
            'design_name': row['design_name'],
            'prod_name': row['prod_name'],
            'price': {
                'price': product['price_range']['price_min'],
                'sale_price': product['price_range'].get('sale_price_min', 0)
            },
            # In the Javascript, these traits will get iterated through and attached to the
            # product-design div as data-orientation_id-#, etc.  Note that we could also use
            # card_color_seq (for example) if we had a card_color.seq; whatever we use, we're
            # going to order the entries in cge['trait_groups'] by its numeric component.

            # Most traits are single-value; a card has a single orientation, color, format,
            # and size.  However, a card might have multiple "number of [front] image slots"
            # values, since the front can have different layouts.  So we split the traits
            # into two chunks for the JS to handle them properly.

            # If any of these are not selected in the JS - keeping in mind that "no checkbox in
            # the group is selected" is treated as "ALL checkboxes in the group are selected" -
            # the product-design is not shown.  Then from there...:
            'svtraits': [
              'orientation_id-'+str(row['orientation_id']),
              'card_color_id-'+str(row['card_color_id']),
              'card_format_id-'+str(row['card_format_id']),
              'card_size_id-'+str(row['card_size_id'])
            ],

            # If any of these are selected in the JS, and the product-design hasn't been hidden
            # based on single-value traits, the product-design is shown.
            'mvtraits': [
              # 'num_islots-*' get added below
            ]
        }

        c.execute("""
            select distinct count(di.design_islot_id) as c
            from (design_page as dp, page_layout as pl, design_page_layout as dpl)
            left join (design_islot as di) on
                di.design_page_layout_id = dpl.design_page_layout_id
            where
                dp.product_design_id = %s and
                dp.seq = 1 and
                pl.page_layout_group_id = dp.page_layout_group_id and
                dpl.page_layout_id = pl.page_layout_id
            group by dpl.design_page_layout_id""",
            (row['product_design_id'],)
        )
        for r in c.fetchall():
            num_islots = r['c'] if r['c'] < 3 else 3
            attr = 'num_islots-'+str(num_islots)
            if attr not in trait_groups['# of Photos']:
                trait_groups['# of Photos'][attr] = {
                    'name': ['No Photos', 'One Photo', 'Two Photos', 'Three+ Photos'][num_islots],
                    'num_pds': 0
                }
            trait_groups['# of Photos'][attr]['num_pds'] += 1
            pd['mvtraits'].append(attr)

        attr = 'orientation_id-'+str(row['orientation_id'])
        if attr not in trait_groups['Card Orientation']:
            trait_groups['Card Orientation'][attr] = {
                'name': Statics.orientations.get_id(row['orientation_id'])['name'],
                'num_pds': 0
            }
        trait_groups['Card Orientation'][attr]['num_pds'] += 1

        card_color = Statics.card_colors.get_id(row['card_color_id'])
        attr = 'card_color_id-'+str(row['card_color_id'])
        if attr not in trait_groups['Colors']:
            trait_groups['Colors'][attr] = {
                'name': card_color['name'],
                'image': card_color['image'],
                'num_pds': 0
            }
        trait_groups['Colors'][attr]['num_pds'] += 1

        card_format = Statics.card_formats.get_id(row['card_format_id'])
        attr = 'card_format_id-'+str(row['card_format_id'])
        if attr not in trait_groups['Card Format']:
            trait_groups['Card Format'][attr] = {
                'name': card_format['name'],
                'num_pds': 0
            }
        trait_groups['Card Format'][attr]['num_pds'] += 1

        card_size = Statics.card_sizes.get_id(row['card_size_id'])
        attr = 'card_size_id-'+str(row['card_size_id'])
        if attr not in trait_groups['Sizes']:
            trait_groups['Sizes'][attr] = {
                'name': card_size['name'],
                'num_pds': 0
            }
        trait_groups['Sizes'][attr]['num_pds'] += 1
        cge['pds'].append(pd)

    # Now, rearrange the trait_groups structure from something like:
    #
    # { '# of Photos': {'num_slots_2': { <name and qty> }, 'num_slots_0': { <name and qty> }, etc.}, etc. }
    #
    # ... to:
    #
    # [ { 'name': '# of Photos', 'traits': [{ 'attr': 'num_slots_0', <name and qty> }, { 'attr': 'num_slots_1', <name and qty> }, etc.] }, etc. ]
    #
    # ... and put it in cge['trait_groups'].

    cge['trait_groups'] = []
    for tg_name in ['# of Photos', 'Card Orientation', 'Card Format', 'Sizes', 'Colors']:
        trait_group = {
          'name': tg_name,
          'traits': []
        }
        traits = []
        # Flatten the traits first; it's easier to sort that way.
        for attr in trait_groups[tg_name]:
            trait = {'attr': attr}
            # Copy (function-global) trait_groups fields into trait.
            trait.update(trait_groups[tg_name][attr])
            traits.append(trait)
        # traits is now a flat, unsorted list.  Following sorts by numeric component of <element>['attr'].
        traits.sort(key=lambda t: int(re.sub('[^0-9]', '', t['attr'])))
        trait_group['traits'] = traits
        cge['trait_groups'].append(trait_group)

    return cge

def pi_ecom(product_design_id = 0, pi_product_group_id = 0):
    """ Returns an ecom-friendly product info group.
        Entries are ordered by product_design_id."""

    c = get_cursor()

    product_design_id = int(product_design_id)
    pi_product_group_id = int(pi_product_group_id)

    rows = []
    ppdg = {}

    if product_design_id > 0:

        c.execute("""
            select pi_design_group.*
            from pi_design_group, product_design
            where product_design_id = %s
            and product_design.pi_design_group_id = pi_design_group.pi_design_group_id""",
            (product_design_id,)
        )
        pi_design_group = c.fetchone()

        ppdg = {
            # ppdg_key is used as a key to store the pd_id in localstorage.
            'ppdg_key': "pdgi.{}".format(pi_design_group['pi_design_group_id']),
            'ecom_name': pi_design_group['ecom_name'],
            'choose_text': pi_design_group['choose_text'],
            'pds': []
        }

        c.execute("""
            select pd.product_design_id, pd.product_id, pd.orientation_id, pd.detail_html, pd.pi_show
            from (product_design as pd, product as p)
            where pd.pi_design_group_id = %s
            and pd.product_id = p.product_id
            and p.is_available = 1
            order by pd.pi_seq""",
            (pi_design_group['pi_design_group_id'],)
        )

        rows = c.fetchall()

    elif pi_product_group_id > 0:
        pi_pg = Statics.pi_product_groups.get_id(pi_product_group_id)
        ppdg = {
            # ppdg_key is used as a key to store the pd_id in localstorage.
            'ppdg_key': "ppgi.{}".format(pi_product_group_id),
            'ecom_name': pi_pg['ecom_name'],
            'choose_text': pi_pg['choose_text'],
            'pds': []
        }

        c.execute("""
            select pd.product_design_id, pd.product_id, pd.orientation_id, pd.detail_html, pd.pi_show
            from (product_design as pd, product as p)
            where pd.pi_product_group_id = %s
            and pd.product_id = p.product_id
            and p.is_available = 1
            order by pd.pi_seq""",
            (pi_product_group_id,)
        )

        rows = c.fetchall()

    else:
        raise DbKeyInvalid("Product Info: no key")

    for row in rows:
        icon_afile = None
        c.execute("""
            select icon_afile
            from product_orientation
            where
                product_id = %s and
                orientation_id = %s""",
            (row['product_id'], row['orientation_id'])
        )
        if c.rowcount != 0:
            icon_afile = c.fetchone()['icon_afile']

        c.execute("""select b480x430_afile as large_afile, b96x96_afile as small_afile
                     from product_design_detail_image
                     where product_design_id = %s
                     order by seq""",
                     (row['product_design_id'],))
        row['detail_images'] = c.fetchall()

        try:
            product = product_ecom(row['product_id'])
            pd = {
                'pd_id': row['product_design_id'],
                'orientation_id': row['orientation_id'],
                'detail_html': row['detail_html'],
                'product': product,
                'pi_show': row['pi_show'] == 0,
                'icon': icon_afile,
                'detail_images': row['detail_images']
            }
            ppdg['pds'].append(pd)
        except KeyError:
            print "Product (product_id {}) not loaded. No price?".format(row['product_id'])

    return ppdg


def page_layout_groups_ecom(product_design_id, bounding_width = None, bounding_height = None):
    """Returns a dictionary of ecom-friendly page_layout_group objects for every PLG available
       in a product-design and its orientation siblings (if any), using page_layout_group_id as
       the key.  See http://sdrv.ms/19lK3KF for spec.  DPLs are ordered by seq within the PLG,
       as are islots and tslots within the DPL.

       If a bounding box is provided, all coordinates will be modified to fit.  Otherwise, they are
       unchanged from their default, nom_*-based, values."""

    c = get_cursor()

    c.execute("""
        select product_design_id
        from product_design
        where pb_product_design_pair_id = (
            select pb_product_design_pair_id
            from product_design
            where product_design_id = %s)""",
        (product_design_id,)
    )
    if c.rowcount == 0:
        # product_design.pb_product_design_pair_id is NULL
        product_design_ids = str(product_design_id)
    else:
        product_design_ids = ', '.join([str(r['product_design_id']) for r in c.fetchall()])

    c.execute("""
        select distinct page_layout_group_id
        from design_page
        where product_design_id in ({})""".format(product_design_ids)
    )
    plg_ids = [r['page_layout_group_id'] for r in c.fetchall()]

    plgs_ecom = {}
    for plg_id in plg_ids:
        plgs_ecom[plg_id] = []
        c.execute("""
            select page_layout_id, icon_afile, texter_type
            from page_layout
            where page_layout_group_id = %s
            order by seq""",
            (plg_id,)
        )
        pls = c.fetchall()
        for pl in pls:
            pl_ecom = {
                'icon': pl['icon_afile'],
                'dpls': []
            }

            c.execute("""
                select
                    design_page_layout_id, product_page_id, nom_width, nom_height,
                    s800_overlay_afile, s200_overlay_afile
                from design_page_layout
                where page_layout_id = %s""",
                (pl['page_layout_id'],)
            )
            dpls = c.fetchall()
            for dpl in dpls:
                if bounding_width != None and bounding_height != None:
                    dpl_aspect = 1. * dpl['nom_width'] / dpl['nom_height']
                    bounding_aspect = 1. * bounding_width / bounding_height
                    if dpl_aspect > bounding_aspect:
                        scale = 1. * bounding_width  / dpl['nom_width']
                    else:
                        scale = 1. * bounding_height / dpl['nom_height']
                else:
                    scale = 1.
    
                page_width, page_height = dpl['nom_width'] * scale, dpl['nom_height'] * scale
                short_length = page_width if page_width <= page_height else page_height
                if short_length > 200: overlay_image = dpl['s800_overlay_afile']
                else: overlay_image = dpl['s200_overlay_afile']
    
                dpl_ecom = {
                    'dpl_id': dpl['design_page_layout_id'],
                    'pp_id': dpl['product_page_id'],
                    'overlay_image': overlay_image,
                    'page_width': float("{:0.2f}".format(dpl['nom_width'] * scale)),
                    'page_height': float("{:0.2f}".format(dpl['nom_height'] * scale)),
                    # XXX - I should probably move this column.
                    'ttype': pl['texter_type'],
                    'islots': [],
                    'tslots': []
                }
    
                c.execute("""
                    select design_islot_id, seq, x0, y0, x1, y1, is_full_bleed
                    from design_islot
                    where design_page_layout_id = %s
                    order by seq""",
                    (dpl['design_page_layout_id'],)
                )
                dis_rows = c.fetchall()
    
                for dis_row in dis_rows:
                    dpl_ecom['islots'].append({
                        'dis_id': dis_row['design_islot_id'],
                        'seq': dis_row['seq'],
                        'x0': float("{:0.2f}".format(dis_row['x0'] * scale)),
                        'y0': float("{:0.2f}".format(dis_row['y0'] * scale)),
                        'x1': float("{:0.2f}".format(dis_row['x1'] * scale)),
                        'y1': float("{:0.2f}".format(dis_row['y1'] * scale)),
                        'ifb': dis_row['is_full_bleed']
                    })
    
                c.execute("""
                    select
                        design_tslot_id, seq, name, placeholder, initial_content,
                        allow_multiline_input, max_chars, font_id, fontsize_id,
                        gravity_id, color_rgba, x0, y0, x1, y1
                    from design_tslot
                    where design_page_layout_id = %s
                    order by seq""",
                    (dpl['design_page_layout_id'],)
                )
                dts_rows = c.fetchall()
    
                for dts_row in dts_rows:
                    dts_fonts = []
                    if pl['texter_type'] == 1:
                        font = Statics.fonts.get_id(dts_row['font_id'])
                        dts_fonts.append({
                            'font_id': font['font_id'],
                            'name': font['name']
                        })
                    else:
                        for font in Statics.type2_fonts.get():
                            dts_fonts.append({
                                'font_id': font['font_id'],
                                'name': font['name']
                            })
                    dts_fontsizes = []
                    if pl['texter_type'] == 1:
                        fontsize = Statics.fontsizes.get_id(dts_row['fontsize_id'])
                        dts_fontsizes.append({
                            'fontsize_id': fontsize['fontsize_id'],
                            'name': fontsize['name']
                        })
                    else:
                        for fontsize in Statics.type2_fontsizes.get():
                            dts_fontsizes.append({
                                'fontsize_id': fontsize['fontsize_id'],
                                'name': fontsize['name']
                            })
                    dts_gravities = []
                    if pl['texter_type'] == 1:
                        gravity = Statics.gravities.get_id(dts_row['gravity_id'])
                        dts_gravities.append({
                            'gravity_id': gravity['gravity_id'],
                            'image_afile': gravity['image_afile']
                        })
                    else:
                        for gravity in Statics.type2_gravities.get():
                            dts_gravities.append({
                                'gravity_id': gravity['gravity_id'],
                                'image_afile': gravity['image_afile']
                            })
                    dpl_ecom['tslots'].append({
                        'dts_id': dts_row['design_tslot_id'],
                        'seq': dts_row['seq'],
                        'x0': float("{:0.2f}".format(dts_row['x0'] * scale)),
                        'y0': float("{:0.2f}".format(dts_row['y0'] * scale)),
                        'x1': float("{:0.2f}".format(dts_row['x1'] * scale)),
                        'y1': float("{:0.2f}".format(dts_row['y1'] * scale)),
                        'name': dts_row['name'],
                        'ph': dts_row['placeholder'],
                        'ic': dts_row['initial_content'],
                        'ami': dts_row['allow_multiline_input'],
                        'mc': dts_row['max_chars'],
                        'fonts': dts_fonts,
                        'fontsizes': dts_fontsizes,
                        'gravities': dts_gravities,
                        'color': dts_row['color_rgba']
                    })
                pl_ecom['dpls'].append(dpl_ecom)
            plgs_ecom[plg_id].append(pl_ecom)

    return plgs_ecom

def edit_product(req):
    """Update the given product based on the data in the req object."""

    name = req.get('name', "")
    promo_category_id = req.get('promo_category_id', None)
    product_prices = req.get('product_prices', [])
    is_available = req.get('is_available', 1)
    product_id = int(req['product_id'])
    c = get_cursor()
    c.execute("""delete from product_price
                 where product_id = %s""",
                 (product_id, ))
    c.execute("""update product
                 set name = %s,
                 promo_category_id = %s,
                 is_available = %s
                 where product_id = %s""",
                 (name, promo_category_id, is_available, product_id))
    for price in product_prices:
        c.execute("""insert into product_price 
                     (product_id, min_quantity, price, sale_price)
                     values (%s, %s, %s, %s)""",
                     (product_id, price['min_quantity'], price['price'], price['sale_price']))
    Db.cache_invalidate()
    return { 'product': Statics.products.get_id(product_id) }

def update_products(rows):
    """Update the product rows based on a dictionary (probably from csv) in the req object."""

    if len(rows) == 0:
        raise DbError("No products provided in CSV file.")
    product_ids = []
    c = get_cursor()
    for r in rows:
        name = r.get('name', "")
        promo_category_id = r.get('promo_category_id', None)
        is_available = r.get('is_available', 1)
        product_id = int(r['product_id'])
        product_ids.append(product_id)
        c.execute("""update product
                     set name = %s,
                     promo_category_id = %s,
                     is_available = %s
                     where product_id = %s""",
                     (name, promo_category_id, is_available, product_id))
        c.execute("""delete from product_price
                     where product_id = %s""",
                     (product_id, ))
        for i in range(CSVPRICECOUNT):
            min_quantity = int(r.get("min_quantity" + str(i), 0))
            price = r.get("price" + str(i), 0)
            sale_price = r.get("sale_price" + str(i), 0)
            if min_quantity > 0:
                c.execute("""insert into product_price 
                             (product_id, min_quantity, price, sale_price)
                             values (%s, %s, %s, %s)""",
                             (product_id, min_quantity, price, sale_price))
    Db.cache_invalidate()

    rows = []
    for product_id in product_ids:
        rows.append(Statics.products.get_id(product_id))
    return rows

def assetize_detail_images(filename=None, imdata=None):
    """Assetize a product-detail JPEG image, along with its smaller sizes.  Either a
       filename must be provided, or the image data."""

    import db.Asset as Asset
    if imdata == None:
        base_im = Image.open(filename)
        desc_suffix = ', '+filename
        base_afile = Asset.assetize_image('base detail image'+desc_suffix, 'product_design_detail_image.base_afile', filename=filename)
    else:
        base_im = Image.open(StringIO.StringIO(imdata))
        desc_suffix = ''
        base_afile = Asset.assetize_image('base detail image'+desc_suffix, 'product_design_detail_image.base_afile', imdata=imdata, extension='.jpg')

    [bw, bh] = base_im.size
    bar = 1. * bw / bh

    if bar >= 480. / 430:
        b480x430_afile = base_im.resize((480, int(.5 + 480 / bar)), Image.ANTIALIAS)
    else:
        b480x430_afile = base_im.resize((int(.5 + 430 * bar), 430), Image.ANTIALIAS)

    sio = StringIO.StringIO()
    # XXX - quality TBD
    b480x430_afile.save(sio, format='JPEG')
    b480x430_afile = Asset.assetize_image('b480x430 detail image'+desc_suffix, 'product_design_detail_image.b480x430_afile', imdata=sio.getvalue(), extension='.jpg')

    if bar >= 96. / 96:
        b96x96_im = base_im.resize((96, int(.5 + 96 / bar)), Image.ANTIALIAS)
    else:
        b96x96_im = base_im.resize((int(.5 + 96 * bar), 96), Image.ANTIALIAS)

    sio = StringIO.StringIO()
    # XXX - quality TBD
    b96x96_im.save(sio, format='JPEG')
    b96x96_afile = Asset.assetize_image('b96x96 detail image'+desc_suffix, 'product_design_detail_image.b96x96_afile', imdata=sio.getvalue(), extension='.jpg')

    return [base_afile, b480x430_afile, b96x96_afile]

def pi_group_browser():
    """Returns a hierarchical lists of pi_design_groups and pi_product_groups and their
       subordinate records for the support browser."""

    c = get_cursor()

    c.execute("""select * from pi_design_group""")

    rows = c.fetchall()
    # now grab the associated product designs
    for row in rows:
        c.execute("""select pd.*, p.name as product_name
                     from (product_design as pd, product as p)
                     where pd.pi_design_group_id = %s
                     and p.product_id = pd.product_id
                     order by product_design_id""",
                     (row['pi_design_group_id'],))

        row['product_designs'] = c.fetchall()
        for product_design in row['product_designs']:
            c.execute("""select b480x430_afile, b96x96_afile
                         from product_design_detail_image
                         where product_design_id = %s
                         order by seq""",
                         (product_design['product_design_id'],))
            product_design['detail_images'] = c.fetchall()

    pi_groups = {
        'pi_design_groups': rows
    }

    c.execute("""select * from pi_product_group""")

    rows = c.fetchall()
    # now grab the associated product designs
    for row in rows:
        c.execute("""select pd.*, p.name as product_name
                     from (product_design as pd, product as p)
                     where pd.pi_product_group_id = %s
                     and p.product_id = pd.product_id
                     order by product_design_id""",
                     (row['pi_product_group_id'],))

        row['product_designs'] = c.fetchall()
        for product_design in row['product_designs']:
            c.execute("""select b480x430_afile, b96x96_afile
                         from product_design_detail_image
                         where product_design_id = %s
                         order by seq""",
                         (product_design['product_design_id'],))
            product_design['detail_images'] = c.fetchall()

    pi_groups['pi_product_groups'] = rows

    return pi_groups

