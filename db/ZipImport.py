import os, re, sys, shutil, stat, tempfile
from   zipfile import ZipFile
import Image, StringIO

import db.Asset as Asset
import db.Db as Db
from   db.Exceptions import ZipImportError
import db.Product as Product

# XXX (20131021): this needs a minor refactoring:
#
# * use Db.get_cursor() instead of passing 'c' around;
# * move import_zip() into ajax_design_zip.wsgi;
# * move a few functions into a different (possibly new) file (e.g., assetize_overlay_images()),
#   or possibly Statics (e.g., font_to_font_id());
# * rename this file to reflect that it now only processes spec files.

#
# Calls to import layout groups and designs from ZIP files.
#
# Inserts into the following tables:
#     layout group mode:
#         page_layout_group
#         page_layout
#         design_page_layout
#         design_islot
#         design_tslot
#         fontsize
#         asset
#     design mode:
#         pi_product_group
#         pi_design_group
#         cs_group
#         product_design
#         product_design_detail_image
#         design_page
#         pb_product_design_pair
#         asset
#

def import_zip(zipfile):
    zipdir = tempfile.mkdtemp(dir=Db.tmp_path)
    os.chdir(zipdir)
    zip = ZipFile(zipfile, 'r')
    zip.extractall()
    zip.close()
    try:
        # specfiles = ./*.txt, regular files only
        specfiles = [f for f in os.listdir('.') if re.search('\.txt$', f) and stat.S_ISREG(os.stat(f).st_mode)]
        assert len(specfiles) != 0, "No specfiles (files ending in '.txt') found in ZIP file!"
        assert len(specfiles) == 1, "{} specfiles (files ending in '.txt') found in ZIP file!".format(len(specfiles))
        parse_specfile(specfiles[0])
        shutil.rmtree(zipdir, False)
    except Exception as e:
        shutil.rmtree(zipdir, False)
        raise e

def parse_specfile(filename):
    c = Db.get_cursor()

    tops = set(['LAYOUT GROUP', 'DESIGN', 'ORIENTATION PAIR', 'CARD GROUP', 'PRODUCT INFO DESIGN GROUP', 'PRODUCT INFO PRODUCT GROUP', 'eof'])
    transitions = {
        '<top level>': tops,
        'LAYOUT GROUP': tops | set(['LAYOUT']),   # inline merge
        'LAYOUT': tops | set(['LAYOUT', 'ISLOT', 'TSLOT', 'FOR PAGE']),
        'ISLOT': tops | set(['LAYOUT', 'ISLOT', 'TSLOT']),
        'TSLOT': tops | set(['LAYOUT', 'ISLOT', 'TSLOT']),
        'FOR PAGE': tops | set(['LAYOUT', 'ISLOT', 'TSLOT', 'FOR PAGE']),
        'DESIGN': set(['DETAIL IMAGE', 'PAGE']),
        'DETAIL IMAGE': set(['DETAIL IMAGE', 'PAGE']),
        'PAGE': tops | set(['PAGE']),
        'ORIENTATION PAIR': tops,
        'PRODUCT INFO PRODUCT GROUP': tops,
        'PRODUCT INFO DESIGN GROUP': tops,
        'CARD GROUP': tops
    }

    # Our current entry level, e.g., '<top level>', 'LAYOUT GROUP', 'LAYOUT', etc.
    level = '<top level>'
    # The line number of the input file that started our current level.
    level_line_num = 0
    # The variables we've found at this level.  At the end of an ISLOT level, e.g.,
    # this might be { 'coordinates': '(1100,100)-(2000,1400)', 'full-bleed': 'yes' }.
    vals = {}
    # A free-form dictionary for communicating information across process functions.
    # It might look like this while processing a PAGE:
    # {
    #   'last pd_id': 17,
    #   'last dp_id': 23   # if we've already processed a PAGE anywhere
    # }
    saved_state = {}

    sfile = open(filename, 'r')
    lines = sfile.readlines()
    sfile.close()

    line_num = 0
    for line in lines:
        try:
            line_num += 1
            if re.match('\s*$', line): continue
            if re.match('\s*?#', line): continue
        
            m = re.match('\s*(.*?):\s*(.*?)\s*$', line)
            if m == None:
                raise ZipImportError("Couldn't parse line '{}'.".format(line))
            var = m.group(1)
            val = m.group(2)
            if val == '': val = None   # make int/float(val) and val+'' raise exceptions
        
            if var in transitions and var != '<top level>':
                new_level = var
                if new_level in transitions[level]:
                    process_entry(c, level, vals, saved_state)
                    vals = {}
                    level = new_level
                    level_line_num = line_num
                else:
                    raise ZipImportError("Can't go from level '{}' to '{}'.".format(level, new_level))
            else:
                vals[var] = val
        except Exception as e:
            raise ZipImportError(exception_text(e, level, level_line_num))
    
    try:
        if 'eof' in transitions[level]:
            process_entry(c, level, vals, saved_state)
        else:
            raise ZipImportError("Reached end-of-file while in unexpected level '{}'.".format(level))
    except Exception as e:
        raise ZipImportError(exception_text(e, level, level_line_num))

def process_entry(c, level, vals, saved_state):
    if level == '<top level>': pass

    elif level == 'LAYOUT GROUP':
        process_layout_group(c, vals, saved_state)
    elif level == 'LAYOUT':
        # no point in, e.g.:
        #     saved_state['last pl_id'] = process_layout(c, vals, saved_state['last plg_id'])
        # ... right?
        process_layout(c, vals, saved_state)
    elif level == 'ISLOT':
        process_islot(c, vals, saved_state)
    elif level == 'TSLOT':
        process_tslot(c, vals, saved_state)
    elif level == 'FOR PAGE':
        process_for_page(c, vals, saved_state)

    elif level == 'PRODUCT INFO PRODUCT GROUP':
        process_product_info_product_group(c, vals, saved_state)
    elif level == 'PRODUCT INFO DESIGN GROUP':
        process_product_info_design_group(c, vals, saved_state)
    elif level == 'CARD GROUP':
        process_card_group(c, vals, saved_state)
    elif level == 'DESIGN':
        process_design(c, vals, saved_state)
    elif level == 'PAGE':
        process_page(c, vals, saved_state)
    elif level == 'DETAIL IMAGE':
        process_detail_image(c, vals, saved_state)
    elif level == 'ORIENTATION PAIR':
        process_orientation_pair(c, vals, saved_state)

    else:
        raise Exception("Unexpected level '{}' found processing input.".format(level))

def process_layout_group(c, vals, saved_state):
    c.execute("""
        select page_layout_group_id
        from page_layout_group
        where name = %s""",
        (vals['name']+'',)
    )
    # page_layout_group.name is unique
    rs = c.fetchone()
    if rs != None:
        saved_state['last plg_id'] = rs['page_layout_group_id']
        return

    c.execute("""
        insert into page_layout_group
        (name) values (%s)""",
        (vals['name']+'',)
    )
    saved_state['last plg_id'] = c.lastrowid

def process_layout(c, vals, saved_state):
    ecom_name = vals['label']
    support_name = vals['name']

    nom_width, nom_height = vals['nominal size'].split('x')
    nom_width, nom_height = int(nom_width), int(nom_height)

    if vals['super overlay image'] != None:
        filename = vals['super overlay image']
        super_overlay_afile = Asset.assetize_image('super overlay, '+filename, 'page_layout.super_overlay_afile', filename=filename)
    else:
        super_overlay_afile = None
    if vals['icon image'] != None:
        filename = vals['icon image']
        icon_afile = Asset.assetize_image('icon, '+filename, 'page_layout.icon_afile', filename=filename)
    else:
        icon_afile = None

    if vals['enhanced text editor'] == 'yes':
        texter_type = 2
    else:
        texter_type = 1

    c.execute("""
        select ifnull(max(seq) + 1, 1) as next_seq
        from page_layout
        where page_layout_group_id = %s""",
        (saved_state['last plg_id'],)
    )
    r = c.fetchone()

    c.execute("""
        insert into page_layout
        (page_layout_group_id, seq, support_name, ecom_name, icon_afile, texter_type, super_overlay_afile)
        values (%s, %s, %s, %s, %s, %s, %s)""",
        (saved_state['last plg_id'], r['next_seq'], support_name, ecom_name, icon_afile, texter_type, super_overlay_afile)
    )
    saved_state['last pl_id'] = c.lastrowid
    saved_state['last pl.texter_type'] = texter_type
    saved_state['last dpl_ids'] = []
    saved_state['last nw'] = nom_width
    saved_state['last nh'] = nom_height

def process_for_page(c, vals, saved_state):
    c.execute("""
        select super_overlay_afile
        from page_layout
        where page_layout_id = %s""",
        (saved_state['last pl_id'],)
    )
    super_overlay_afile = c.fetchone()['super_overlay_afile']

    c.execute("""
        select
            product_page_id, nom_width, nom_height,
            super_frame_x0, super_frame_y0, super_frame_x1, super_frame_y1,
            lab_frame_x0, lab_frame_y0, lab_frame_x1, lab_frame_y1
        from product_page
        where support_name = %s""",
        (vals['name'],)
    )
    assert c.rowcount != 0, "No product-page found by name '{}'.".format(vals['name'])
    assert c.rowcount == 1, "Multiple product-pages found by name '{}'.".format(vals['name'])
    r = c.fetchone()

    if super_overlay_afile != None:
        pp_size = (r['nom_width'], r['nom_height'])
        pp_sf_coords = (r['super_frame_x0'], r['super_frame_y0'], r['super_frame_x1'], r['super_frame_y1'])
        dpl_size = (saved_state['last nw'], saved_state['last nh'])
	super_overlay_afile = Db.asset_path+'/'+super_overlay_afile[0]+'/'+super_overlay_afile[1]+'/'+super_overlay_afile
        base_overlay_afile, s800_overlay_afile, s200_overlay_afile = assetize_overlay_images(super_overlay_afile, pp_size, pp_sf_coords, dpl_size)
        c.execute("""
            insert into design_page_layout
            (product_page_id, page_layout_id, nom_width, nom_height, base_overlay_afile, s800_overlay_afile, s200_overlay_afile)
            values (%s, %s, %s, %s, %s, %s, %s)""",
            (r['product_page_id'], saved_state['last pl_id'], saved_state['last nw'], saved_state['last nh'], base_overlay_afile, s800_overlay_afile, s200_overlay_afile)
        )
    else:
        c.execute("""
            insert into design_page_layout
            (product_page_id, page_layout_id, nom_width, nom_height)
            values (%s, %s, %s, %s)""",
            (r['product_page_id'], saved_state['last pl_id'], saved_state['last nw'], saved_state['last nh'])
        )

    saved_state['last dpl_ids'].append(c.lastrowid)

def process_islot(c, vals, saved_state):
    # Support provides us with coordinates that come directly out of Photoshop, relative to a super-image;
    # this is less error-prone.  In the database, we want our islots to be specified relative to the consumer
    # viewport, which has an implicit upper-left of (0, 0).  We also want to clip our islots based on which
    # product_page it's associated with.  (There may be multiple product_pages to associate with, based on the
    # "FOR PAGE"s we've been provided.)
    #
    # The basic technique is to translate the islot to the upper left of the product_page's super-frame, then
    # clip the islot by the product_page's lab-frame.  In both cases, we have to be aware that the design_page_layout
    # and the product_page may have different nominal sizes.

    m = re.match('\((.*?),(.*?)\)-\((.*?),(.*?)\)$', vals['coordinates'])
    x0, y0, x1, y1 = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    is_full_bleed = 1 if vals['full-bleed'] == 'yes' else 0

    for dpl_id in saved_state['last dpl_ids']:
        c.execute("""
            select
                dpl.nom_width as dpl_nw, dpl.nom_height as dpl_nh,
                pp.nom_width as pp_nw, pp.nom_height as pp_nh,
                pp.super_frame_x0 as pp_sf_x0, pp.super_frame_y0 as pp_sf_y0,
                pp.lab_frame_x0 as pp_lf_x0, pp.lab_frame_y0 as pp_lf_y0,
                pp.lab_frame_x1 as pp_lf_x1, pp.lab_frame_y1 as pp_lf_y1
            from (design_page_layout as dpl, product_page as pp)
            where
                dpl.design_page_layout_id = %s and
                pp.product_page_id = dpl.product_page_id""",
            (dpl_id,)
        )
        r = c.fetchone()
        px0 = x0 + r['pp_sf_x0'] * r['dpl_nw'] / r['pp_nw']
        py0 = y0 + r['pp_sf_y0'] * r['dpl_nh'] / r['pp_nh']
        px1 = x1 + r['pp_sf_x0'] * r['dpl_nw'] / r['pp_nw']
        py1 = y1 + r['pp_sf_y0'] * r['dpl_nh'] / r['pp_nh']
        if px0 < r['pp_lf_x0'] * r['dpl_nw'] / r['pp_nw']:
            px0 = r['pp_lf_x0'] * r['dpl_nw'] / r['pp_nw']
        if py0 < r['pp_lf_y0'] * r['dpl_nh'] / r['pp_nh']:
            py0 = r['pp_lf_y0'] * r['dpl_nh'] / r['pp_nh']
        if px1 > r['pp_lf_x1'] * r['dpl_nw'] / r['pp_nw']:
            px1 = r['pp_lf_x1'] * r['dpl_nw'] / r['pp_nw']
        if py1 > r['pp_lf_y1'] * r['dpl_nh'] / r['pp_nh']:
            py1 = r['pp_lf_y1'] * r['dpl_nh'] / r['pp_nh']

        c.execute("""
            select ifnull(max(seq) + 1, 1) as next_seq
            from design_islot
            where design_page_layout_id = %s""",
            (dpl_id,)
        )
        next_seq = c.fetchone()['next_seq']

        c.execute("""
            insert into design_islot
            (design_page_layout_id, seq, x0, y0, x1, y1, is_full_bleed)
            values (%s, %s, %s, %s, %s, %s, %s)""",
            (dpl_id, next_seq, px0, py0, px1, py1, is_full_bleed)
        )

def process_tslot(c, vals, saved_state):
    # Support provides us with coordinates that come directly out of Photoshop, relative to a super-image;
    # this is less error-prone.  In the database, we want our tslots to be specified relative to the consumer
    # viewport, which has an implicit upper-left of (0, 0).  We also want to clip our tslots based on which
    # product_page it's associated with.  (There may be multiple product_pages to associate with, based on the
    # "FOR PAGE"s we've been provided.)
    #
    # The basic technique is to translate the tslot to the upper left of the product_page's super-frame, then
    # clip the tslot by the product_page's lab-frame.  In both cases, we have to be aware that the design_page_layout
    # and the product_page may have different nominal sizes.

    name = vals['name']
    placeholder = vals['placeholder text']
    initial_content = vals['initial content']
    honor_initial_content = 1 if vals['honor initial content']+'' == 'yes' else 0
    allow_multiline_input = 1 if vals['allow multi-line input']+'' == 'yes' else 0
    max_chars = int(vals['maximum characters'])
    if saved_state['last pl.texter_type'] == 2:
        font_id = fontsize_id = gravity_id = None
    else:
        font_id = font_to_font_id(c, vals['font']+'')
        fontsize_id = fontsize_to_fontsize_id(c, 300 * float(vals['font size']) / 72)
        gravity_id = gravity_to_gravity_id(c, vals['gravity']+'')
    # Not yet implemented
    skew_x = None
    skew_y = None

    color_comps = vals['color'].split(',')
    assert len(color_comps) == 4 or len(color_comps) == 3, 'Bad color {}; expected three or four comma-separated components, got {}.'.format(vals['color'], len(color_comps))
    if len(color_comps) == 3: color_comps.append(0)
    color_rgba = ','.join("{0:.2f}".format(float(c) / 255) for c in color_comps)
    # Not yet implemented
    shadow_color_rgba = None
    shadow_xoff = None
    shadow_yoff = None

    run_horizontally = 0 if vals['run horizontally']+'' == 'no' else 1
    max_rows = int(vals['maximum rows'])
    rotation = int(vals['rotation degrees'])
    assert rotation % 90 == 0, 'Bad rotation {}; expected a multiple of 90.'.format(vals['rotation degrees'])
    m = re.match('\((.*?),(.*?)\)-\((.*?),(.*?)\)$', vals['coordinates'])
    x0, y0, x1, y1 = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))

    for dpl_id in saved_state['last dpl_ids']:
        c.execute("""
            select
                dpl.nom_width as dpl_nw, dpl.nom_height as dpl_nh,
                pp.nom_width as pp_nw, pp.nom_height as pp_nh,
                pp.super_frame_x0 as pp_sf_x0, pp.super_frame_y0 as pp_sf_y0,
                pp.lab_frame_x0 as pp_lf_x0, pp.lab_frame_y0 as pp_lf_y0,
                pp.lab_frame_x1 as pp_lf_x1, pp.lab_frame_y1 as pp_lf_y1
            from (design_page_layout as dpl, product_page as pp)
            where
                dpl.design_page_layout_id = %s and
                pp.product_page_id = dpl.product_page_id""",
            (dpl_id,)
        )
        r = c.fetchone()
        px0 = x0 + r['pp_sf_x0'] * r['dpl_nw'] / r['pp_nw']
        py0 = y0 + r['pp_sf_y0'] * r['dpl_nh'] / r['pp_nh']
        px1 = x1 + r['pp_sf_x0'] * r['dpl_nw'] / r['pp_nw']
        py1 = y1 + r['pp_sf_y0'] * r['dpl_nh'] / r['pp_nh']
        if px0 < r['pp_lf_x0'] * r['dpl_nw'] / r['pp_nw']:
            px0 = r['pp_lf_x0'] * r['dpl_nw'] / r['pp_nw']
        if py0 < r['pp_lf_y0'] * r['dpl_nh'] / r['pp_nh']:
            py0 = r['pp_lf_y0'] * r['dpl_nh'] / r['pp_nh']
        if px1 > r['pp_lf_x1'] * r['dpl_nw'] / r['pp_nw']:
            px0 = r['pp_lf_x1'] * r['dpl_nw'] / r['pp_nw']
        if py1 > r['pp_lf_y1'] * r['dpl_nh'] / r['pp_nh']:
            py0 = r['pp_lf_y1'] * r['dpl_nh'] / r['pp_nh']

        c.execute("""
            select ifnull(max(seq) + 1, 1) as next_seq
            from design_tslot
            where design_page_layout_id = %s""",
            (dpl_id,)
        )
        next_seq = c.fetchone()['next_seq']
    
        c.execute("""
            insert into design_tslot
            (design_page_layout_id, seq, name, placeholder, initial_content, honor_initial_content,
             allow_multiline_input, max_chars, font_id, fontsize_id, gravity_id, skew_x, skew_y,
             color_rgba, shadow_color_rgba, shadow_xoff, shadow_yoff, run_horizontally, max_rows,
             rotation, x0, y0, x1, y1)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (dpl_id, next_seq, name, placeholder, initial_content, honor_initial_content,
             allow_multiline_input, max_chars, font_id, fontsize_id, gravity_id, skew_x, skew_y,
             color_rgba, shadow_color_rgba, shadow_xoff, shadow_yoff, run_horizontally, max_rows,
             rotation, px0, py0, px1, py1)
        )

def font_to_font_id(c, font):
    c.execute("""
        select font_id
        from font
        where filename = %s""",
        (font,)
    )
    assert c.rowcount > 0, "No font '{}' found, and the layout importer doesn't support uploading new fonts.".format(font)
    r = c.fetchone()

    return r['font_id']

def fontsize_to_fontsize_id(c, fontsize):
    # See if there's an equivalent-enough existing size.
    c.execute("""
        select fontsize_id, abs(max_pointsize / %s - 1) as distance
        from fontsize
        where is_type2_usable = 0
        having distance < .005
        order by distance
        limit 1""",
        (fontsize,)
    )
    if c.rowcount > 0:
        r = c.fetchone()
        return r['fontsize_id']

    c.execute("""
        insert into fontsize
        (max_pointsize, name, is_type2_usable, autoscale)
        values
        (%s, %s, %s, %s)""",
        (fontsize, None, 0, 1)
    )
    return c.lastrowid

def gravity_to_gravity_id(c, gravity):
    c.execute("""
        select gravity_id
        from gravity
        where name = %s""",
        (gravity,)
    )
    assert c.rowcount > 0, "No gravity '{}' found.".format(gravity)
    r = c.fetchone()

    return r['gravity_id']

def assetize_overlay_images(filename, pp_size, pp_sf_coords, dpl_size):
    lab_im = Image.open(filename)
    [lw, lh] = lab_im.size

    lasp = 1. * lw / lh
    pasp = (pp_sf_coords[2] - pp_sf_coords[0]) / (pp_sf_coords[3] - pp_sf_coords[1])
    assert abs(1 - lasp / pasp) < .005, 'Bad image {}; expected aspect-ratio of {}, got {}.'.format(filename, pasp, lasp)

    lx0 = lw * (         0 - pp_sf_coords[0]) / (pp_sf_coords[2] - pp_sf_coords[0])
    ly0 = lh * (         0 - pp_sf_coords[1]) / (pp_sf_coords[3] - pp_sf_coords[1])

    ilx0 = int(lx0 + .5)
    ily0 = int(ly0 + .5)
    ilx1 = ilx0 + dpl_size[0] - 1
    ily1 = ily0 + dpl_size[1] - 1

    base_im = lab_im.crop((ilx0, ily0, ilx1, ily1))
    base_afile = Asset.assetize_image('base overlay, '+filename, 'design_page_layout.base_overlay_afile', filename=filename)
    [bw, bh] = base_im.size

    if bw >= bh:
        s800_im = base_im.resize((int(.5 + 1. * 800 * bw / bh), 800), Image.ANTIALIAS)
    else:
        s800_im = base_im.resize((800, int(.5 + 1. * 800 * bh / bw)), Image.ANTIALIAS)

    sio = StringIO.StringIO()
    # XXX - quality TBD
    s800_im.save(sio, format = 'PNG')
    s800_afile = Asset.assetize_image('s800 overlay, '+filename, 'design_page_layout.s800_overlay_afile', imdata=sio.getvalue(), extension='.png')

    if bw >= bh:
        s200_im = base_im.resize((int(.5 + 1. * 200 * bw / bh), 200), Image.ANTIALIAS)
    else:
        s200_im = base_im.resize((200, int(.5 + 1. * 200 * bh / bw)), Image.ANTIALIAS)

    sio = StringIO.StringIO()
    # XXX - quality TBD
    s200_im.save(sio, format = 'PNG')
    s200_afile = Asset.assetize_image('s200 overlay, '+filename, 'design_page_layout.s200_overlay_afile', imdata=sio.getvalue(), extension='.png')

    return [base_afile, s800_afile, s200_afile]

def process_product_info_product_group(c, vals, saved_state):
    c.execute("""
        select ecom_name
        from pi_product_group
        where support_name = %s""",
        (vals['support name'],)
    )
    choose_text = None
    if 'choose text' in vals: choose_text = vals['choose text']
    if c.rowcount == 0:
        c.execute("""
            insert into pi_product_group
            (support_name, ecom_name, choose_text)
            values (%s, %s, %s)""",
            (vals['support name'], vals['ecom name'], choose_text)
        )
    elif c.rowcount == 1:
        ecom_name = c.fetchone()['ecom_name']
        assert vals['ecom name'] == ecom_name, "Bad product-info product-group provided: a group for '{}' exists, but its ecom_name '{}' doesn't match provided ecom name '{}'.".format(vals['support name'], ecom_name, vals['ecom name'])
    else:
        raise Exception("Multiple product-info groups found for name '{}'.".format(vals['support name']))

def process_product_info_design_group(c, vals, saved_state):
    c.execute("""
        select ecom_name
        from pi_design_group
        where support_name = %s""",
        (vals['support name'],)
    )
    choose_text = None
    if 'choose text' in vals: choose_text = vals['choose text']
    if c.rowcount == 0:
        c.execute("""
            insert into pi_design_group
            (support_name, ecom_name, choose_text)
            values (%s, %s, %s)""",
            (vals['support name'], vals['ecom name'], choose_text)
        )
    elif c.rowcount == 1:
        ecom_name = c.fetchone()['ecom_name']
        assert vals['ecom name'] == ecom_name, "Bad product-info design-group provided: a group for '{}' exists, but its ecom_name '{}' doesn't match provided ecom name '{}'.".format(vals['support name'], ecom_name, vals['ecom name'])
    else:
        raise Exception("Multiple product-info groups found for name '{}'.".format(vals['support name']))

def process_card_group(c, vals, saved_state):
    c.execute("""
        select cs_group_id
        from cs_group
        where name = %s""",
        (vals['name'],)
    )
    if c.rowcount == 0:
        c.execute("""
            insert into cs_group
            (name)
            values (%s)""",
            (vals['name'])
        )
    elif c.rowcount > 1:
        raise Exception("Multiple card groups found for name '{}'.".format(vals['name']))

def process_design(c, vals, saved_state):
    c.execute("""
        select product_id
        from product
        where name = %s""",
        (vals['for product'],)
    )
    assert c.rowcount != 0, "No product found by name '{}'.".format(vals['for product'])
    assert c.rowcount == 1, "Multiple products found by name '{}'.".format(vals['for product'])
    product_id = c.fetchone()['product_id']

    c.execute("""
        select orientation_id
        from orientation
        where name = %s""",
        (vals['orientation'],)
    )
    assert c.rowcount != 0, "No orientation found by name '{}'.".format(vals['orientation'])
    assert c.rowcount == 1, "Multiple orientations found by name '{}'.".format(vals['orientation'])
    orientation_id = c.fetchone()['orientation_id']

    if vals['card color'] != None:
        c.execute("""
            select card_color_id
            from card_color
            where name = %s""",
            (vals['card color'],)
        )
        assert c.rowcount != 0, "No card color found by name '{}'.".format(vals['card color'])
        assert c.rowcount == 1, "Multiple card colors found by name '{}'.".format(vals['card color'])
        card_color_id = c.fetchone()['card_color_id']
    else:
        card_color_id = None

    if vals['card-group name'] != None:
        c.execute("""
            select cs_group_id
            from cs_group
            where name = %s""",
            (vals['card-group name'],)
        )
        assert c.rowcount != 0, "No card group found by name '{}'.".format(vals['card-group name'])
        assert c.rowcount == 1, "Multiple card groups found by name '{}'.".format(vals['card-group name'])
        cs_group_id = c.fetchone()['cs_group_id']
        c.execute("""
            select 1 + ifnull(max(cs_seq), 0) as next_cs_seq
            from product_design
            where cs_group_id = %s""",
            (cs_group_id,)
        )
        cs_seq = c.fetchone()['next_cs_seq']
    else:
        cs_group_id = None
        cs_seq = None

    pi_seq = None
    if vals['product-info product-group name'] != None:
        c.execute("""
            select pi_product_group_id
            from pi_product_group
            where support_name = %s""",
            (vals['product-info product-group name'],)
        )
        assert c.rowcount != 0, "No product-info product-group found by name '{}'.".format(vals['product-info product-group name'])
        assert c.rowcount == 1, "Multiple product-info product-groups found by name '{}'.".format(vals['product-info product-group name'])
        pi_product_group_id = c.fetchone()['pi_product_group_id']
        c.execute("""
            select 1 + ifnull(max(pi_seq), 0) as next_pi_seq
            from product_design
            where pi_product_group_id = %s""",
            (pi_product_group_id,)
        )
        pi_seq = c.fetchone()['next_pi_seq']
    else:
        pi_product_group_id = None

    if vals['product-info design-group name'] != None:
        c.execute("""
            select pi_design_group_id
            from pi_design_group
            where support_name = %s""",
            (vals['product-info design-group name'],)
        )
        assert c.rowcount != 0, "No product-info design-group found by name '{}'.".format(vals['product-info design-group name'])
        assert c.rowcount == 1, "Multiple product-info design-groups found by name '{}'.".format(vals['product-info design-group name'])
        pi_design_group_id = c.fetchone()['pi_design_group_id']
        c.execute("""
            select 1 + ifnull(max(pi_seq), 0) as next_pi_seq
            from product_design
            where pi_design_group_id = %s""",
            (pi_design_group_id,)
        )
        pi_seq = c.fetchone()['next_pi_seq']
    else:
        pi_design_group_id = None

    if vals['show in product-info page'] == 'yes':
        pi_show = 1
    else:
        pi_show = 0

    icon_afile = None
    if vals['icon image'] != None:
        m = re.match('^afile:(.*)$', vals['icon image'])
        if m != None:
            icon_afile = m.group(1)
            c.execute("""
                select count(*) as a_count
                from asset
                where afile = %s""",
                (icon_afile,)
            )
            assert c.fetchone()['a_count'] == 1, "No asset image found for icon afile '{}'.".format(icon_afile)
        else:
            icon_afile = Asset.assetize_image('product-design icon, '+vals['icon image'], 'product_design.icon_afile', filename=vals['icon image'])

    c.execute("""
        insert into product_design
        (product_id, orientation_id, support_name, ecom_name, pi_show, icon_afile, card_color_id, detail_html, cs_group_id, cs_seq, pi_product_group_id, pi_design_group_id, pi_seq)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (product_id, orientation_id, vals['support name'], vals['name'], pi_show, icon_afile, card_color_id, vals['detail html'], cs_group_id, cs_seq, pi_product_group_id, pi_design_group_id, pi_seq)
    )
    saved_state['last pd_id'] = c.lastrowid

def process_detail_image(c, vals, saved_state):
    base_afile, b480x430_afile, b96x96_afile = Product.assetize_detail_images(filename=vals['image'])

    c.execute("""
        select ifnull(max(seq) + 1, 1) as next_seq
        from product_design_detail_image
        where product_design_id = %s""",
        (saved_state['last pd_id'],)
    )
    next_seq = c.fetchone()['next_seq']

    c.execute("""
        insert into product_design_detail_image
        (product_design_id, seq, base_afile, b480x430_afile, b96x96_afile)
        values (%s, %s, %s, %s, %s)""",
        (saved_state['last pd_id'], next_seq, base_afile, b480x430_afile, b96x96_afile)
    )
    saved_state['last pddi_id'] = c.lastrowid

def process_page(c, vals, saved_state):
    c.execute("""
        select product_page_id
        from product_page
        where support_name = %s""",
        (vals['name'],)
    )
    assert c.rowcount != 0, "No product-page found by name '{}'.".format(vals['name'])
    assert c.rowcount == 1, "Multiple product-pages found by name '{}'.".format(vals['name'])
    product_page_id = c.fetchone()['product_page_id']

    c.execute("""
        select page_layout_group_id
        from page_layout_group
        where name = %s""",
        (vals['layout group name'],)
    )
    assert c.rowcount != 0, "No page_layout_group found by name '{}'.".format(vals['layout group name'])
    assert c.rowcount == 1, "Multiple page_layout_groups found by name '{}'.".format(vals['layout group name'])
    page_layout_group_id = c.fetchone()['page_layout_group_id']

    c.execute("""
        select ifnull(max(seq) + 1, 1) as next_seq
        from design_page
        where product_design_id = %s""",
        (saved_state['last pd_id'],)
    )
    next_seq = c.fetchone()['next_seq']

    c.execute("""
        insert into design_page
        (product_design_id, product_page_id, page_layout_group_id, seq)
        values (%s, %s, %s, %s)""",
        (saved_state['last pd_id'], product_page_id, page_layout_group_id, next_seq)
    )
    saved_state['last dp_id'] = c.lastrowid

def process_orientation_pair(c, vals, saved_state):
    c.execute("""
        select product_design_id
        from product_design
        where support_name = %s""",
        (vals['product-design 1 name'],)
    )
    assert c.rowcount != 0, "No product_design found by name '{}'.".format(vals['product-design 1 name'])
    assert c.rowcount == 1, "Multiple product_designs found by name '{}'.".format(vals['product-design 1 name'])
    product_design_id1 = c.fetchone()['product_design_id']

    c.execute("""
        select product_design_id
        from product_design
        where support_name = %s""",
        (vals['product-design 2 name'],)
    )
    assert c.rowcount != 0, "No product_design found by name '{}'.".format(vals['product-design 2 name'])
    assert c.rowcount == 1, "Multiple product_designs found by name '{}'.".format(vals['product-design 2 name'])
    product_design_id2 = c.fetchone()['product_design_id']

    c.execute("insert into pb_product_design_pair values ()")
    pb_product_design_pair_id = c.lastrowid

    c.execute("""
        update product_design
        set pb_product_design_pair_id = %s
        where product_design_id in (%s, %s)""",
        (pb_product_design_pair_id, product_design_id1, product_design_id2)
    )

def exception_text(e, level, level_line_num):
    import sys, traceback
    tb = traceback.extract_tb(sys.exc_traceback)[-1]
    st, sv = sys.exc_info()[0:2]

    if str(st) == "<type 'exceptions.KeyError'>":
        text = "An error occurred processing the '{}' starting at line {}.  It appears that there was no entry for {} (required).\n\n".format(level, level_line_num, sv)
    else:
        text = "An error occurred processing the '{}' starting at line {}.  The error was:\n\n".format(level, level_line_num)
        text += "  {} {}\n\n".format(st, sv)
    text += "The statement that failed was:\n\n"
    text += "  {}\n\n".format(tb[3])
    text += "... and it occurred in the function '{}', at {} line {}.\n\n".format(tb[2], tb[0], tb[1])

    return text

