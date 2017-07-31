import re
import MySQLdb
import Image, ImageDraw, ImageFont, ImageOps

import db.Db as Db
import db.Statics as Statics
from db.Db import get_cursor

def lab_page_img(build_id, lab_product_page_id):
    """Creates and returns an Image for a lab_product_page."""

    c = get_cursor()

    c.execute("""
        select nom_width, nom_height, fixed_width, fixed_height, color_rgb, overlay_image_afile
        from lab_product_page
        where lab_product_page_id = %s""",
        (lab_product_page_id,)
    )
    lpp_row = c.fetchone()

    c.execute("""
        select bp.build_page_id, bp.lab_fit_rotation, lpi.x0, lpi.y0, lpi.x1, lpi.y1, lpi.is_full_bleed
        from (build_page as bp, lab_product_islot as lpi)
        where
            lpi.lab_product_page_id = %s and
            bp.lab_product_islot_id = lpi.lab_product_islot_id and
            bp.build_id = %s""",
        (lab_product_page_id, build_id)
    )
    lpi_rows = c.fetchall()
    if len(lpi_rows) == 0: return None   # e.g., incomplete build

    page_width = page_height = None
    for lpi_row in lpi_rows:
        islot_width = lpi_row['x1'] - lpi_row['x0']
        islot_height = lpi_row['y1'] - lpi_row['y0']
        islot_ar = islot_width / islot_height
        # If the lab product page has a fixed size, we use that to determine the size of the build pages.
        # Otherwise, we let the build pages determine their own sizes, and we set our lab product page
        # size accordingly.  (If a multi-islot lab product page gets back build pages which imply multiple
        # lab product page sizes, we go with the largest.)
        #
        # In any situation where we could conceivably have lab product pages of different sizes for a
        # single product, *and* this is forbidden by the lab, we avoid this by setting the same fixed size
        # for all lab product pages.
        if lpp_row['fixed_width'] == None or lpp_row['fixed_height'] == None:
            lpi_row['page_img'] = page_img(lpi_row['build_page_id'], None, None, 'fb', for_lab=True)
        else:
            lpi_row['page_img'] = page_img(
                lpi_row['build_page_id'],
                lpp_row['fixed_width'] * islot_width / lpp_row['nom_width'],
                lpp_row['fixed_height'] * islot_height / lpp_row['nom_height'],
                'fb' if lpi_row['is_full_bleed'] == 1 else 'ff',
                for_lab=True
            )

        if lpi_row['lab_fit_rotation'] == 180:
            lpi_row['page_img'] = lpi_row['page_img'].rotate(lpi_row['lab_fit_rotation'])
        elif lpi_row['lab_fit_rotation'] == 90 or lpi_row['lab_fit_rotation'] == 270:
            pim_ar = 1. * lpi_row['page_img'].size[0] / lpi_row['page_img'].size[1]
            if (pim_ar - 1) * (islot_ar - 1) < 0:   # compactly check for crossed aspects
                lpi_row['page_img'] = lpi_row['page_img'].rotate(lpi_row['lab_fit_rotation'])

        if lpp_row['fixed_width'] == None or lpp_row['fixed_height'] == None:
            implied_page_width = 1. * lpp_row['nom_width'] * lpi_row['page_img'].size[0] / islot_width
            implied_page_height = 1. * lpp_row['nom_height'] * lpi_row['page_img'].size[1] / islot_height
            nom_ar = 1. * lpp_row['nom_width'] / lpp_row['nom_height']
            if implied_page_height * nom_ar > implied_page_width:
                implied_page_width = implied_page_height * nom_ar
            else:
                implied_page_height = implied_page_width / nom_ar
            if page_width == None or page_width < implied_page_width:
                page_width = implied_page_width
                page_height = implied_page_height
        else:
            page_width = lpp_row['fixed_width']
            page_height = lpp_row['fixed_height']

    # '0.58,1.00,0.02' -> (148, 255, 5)
    color = tuple(int(round(255 * float(c))) for c in lpp_row['color_rgb'].split(','))
    im = Image.new(
        'RGB',
        (int(.5 + page_width), int(.5 + page_height)),
        color
    )
    for lpi_row in lpi_rows:
        islot_x0 = int(.5 + page_width  * lpi_row['x0'] / lpp_row['nom_width'])
        islot_y0 = int(.5 + page_height * lpi_row['y0'] / lpp_row['nom_height'])
        islot_x1 = int(.5 + page_width  * lpi_row['x1'] / lpp_row['nom_width'])
        islot_y1 = int(.5 + page_height * lpi_row['y1'] / lpp_row['nom_height'])
        islot_width = islot_x1 - islot_x0
        islot_height = islot_y1 - islot_y0
        islot_ar = 1. * islot_width / islot_height
        pim = lpi_row['page_img']
        pim_ar = 1. * pim.size[0] / pim.size[1]

        if lpi_row['is_full_bleed'] == 1 and pim_ar >= islot_ar:
            pim = pim.resize((int(.5 + islot_height * pim_ar), islot_height), Image.ANTIALIAS)
            cx0 = int(.5 + (pim.size[0] - islot_width) / 2)
            pim = pim.crop((cx0, 0, cx0 + islot_width - 1, islot_height - 1))
            im.paste(pim, (islot_x0, islot_y0))
        elif lpi_row['is_full_bleed'] == 1 and pim_ar < islot_ar:
            pim = pim.resize((islot_width, int(.5 + islot_width / pim_ar)), Image.ANTIALIAS)
            cy0 = int(.5 + (pim.size[1] - islot_height) / 2)
            pim = pim.crop((0, cy0, islot_width - 1, cy0 + islot_height - 1))
            im.paste(pim, (islot_x0, islot_y0))
        elif lpi_row['is_full_bleed'] == 0 and pim_ar >= islot_ar:
            pim = pim.resize((islot_width, int(.5 + islot_width / pim_ar)), Image.ANTIALIAS)
            sy0 = int(.5 + (islot_height - pim.size[1]) / 2)
            im.paste(pim, (islot_x0, sy0))
        elif lpi_row['is_full_bleed'] == 0 and pim_ar < islot_ar:
            pim = pim.resize((int(.5 + islot_height * pim_ar), islot_height), Image.ANTIALIAS)
            sx0 = int(.5 + (islot_width - pim.size[0]) / 2)
            im.paste(pim, (sx0, islot_y0))

    return im

def page_img(build_page_id, fit_width, fit_height, fit_type, for_lab=False):
    """Create and return an Image for a build_page.  Requires a fit type ('fb' or 'ff' for full-bleed or full-frame).
       Note, 'fb' will return an image that is >= the fit size; 'ff' will return one that is <=.  fit_width and
       fit_height are optional; if omitted, a size is chosen based on nominal size and/or customer image size."""

    c = get_cursor()

    # I hardcode the dpl overlay column names here (and the sizes later).  We could add a layer to
    # make them easily changeable, but there's no obvious need for it.
    c.execute("""
        select
            bp.nom_width as bp_nom_width, bp.nom_height as bp_nom_height,
            dpl.base_overlay_afile, dpl.s800_overlay_afile, dpl.s200_overlay_afile,
            dpl.nom_width as dpl_nom_width, dpl.nom_height as dpl_nom_height,
            pp.lab_frame_x0, pp.lab_frame_y0, pp.lab_frame_x1, pp.lab_frame_y1,
            pp.nom_width as pp_nom_width, pp.nom_height as pp_nom_height
        from (build_page as bp, design_page_layout as dpl, product_page as pp)
        where
            bp.build_page_id = %s and
            dpl.design_page_layout_id = bp.design_page_layout_id and
            pp.product_page_id = dpl.product_page_id""",
        (build_page_id,)
    )

    r = c.fetchone()
    base_overlay_afile, s800_overlay_afile, s200_overlay_afile = r['base_overlay_afile'], r['s800_overlay_afile'], r['s200_overlay_afile']

    if fit_width != None and fit_height != None:
        fit_width  = float(fit_width)
        fit_height = float(fit_height)
    else:
        # Ideally I would size the page so that all customer images are either scaled up or left at the same size -
        # this would save us on bandwidth on lab pages.  For now, I just use the nominal size.
        if for_lab:
            fit_width = r['lab_frame_x1'] - r['lab_frame_x0']
            fit_height = r['lab_frame_y1'] - r['lab_frame_y0']
        else:
            fit_width  = r['nom_width']
            fit_height = r['nom_height']

    fit_aspect = fit_width / fit_height
    if for_lab:
        page_aspect = (r['lab_frame_x1'] - r['lab_frame_x0']) / (r['lab_frame_y1'] - r['lab_frame_y0'])
    else:
        page_aspect = r['bp_nom_width'] / r['bp_nom_height']

    # In the case of lab product pages, lab_page_img() requests its size naively - that is, oriented
    # according to lab_product_islot.  If it conflicts with the build page nominal size, build page
    # wins out; this is okay because lab_page_img() knows how to rotate build pages as needed.

    if for_lab and (fit_aspect - 1) * (page_aspect - 1) < 0:   # compactly check for crossed aspects
        fit_width, fit_height = fit_height, fit_width
        fit_aspect = fit_width / fit_height

    if fit_type == 'fb' and page_aspect >= fit_aspect:
        render_width, render_height = fit_height * page_aspect, fit_height
    elif fit_type == 'fb' and page_aspect < fit_aspect:
        render_width, render_height = fit_width, fit_width / page_aspect
    elif fit_type == 'ff' and page_aspect >= fit_aspect:
        render_width, render_height = fit_width, fit_width / page_aspect
    elif fit_type == 'ff' and page_aspect < fit_aspect:
        render_width, render_height = fit_height * page_aspect, fit_height
    else:
        raise Exception('Bad fit_type given: {}'.format(fit_type))

    im = Image.new(
        'RGB',
        (int(.5 + render_width), int(.5 + render_height)),
        (255, 255, 255)
    )

    c.execute("""
        select
            dis.x0 as dis_x0, dis.y0 as dis_y0, dis.x1 as dis_x1, dis.y1 as dis_y1,
            bi.x0 as bi_x0, bi.y0 as bi_y0, bi.x1 as bi_x1, bi.y1 as bi_y1, bi.tint_id,
            i.full_col_afile, i.rotation, i.l800_col_afile, i.l800_baw_afile, i.l800_sep_afile,
            ri.full_col_afile as ri_full_col_afile, ri.rotation as ri_rotation,
            ri.l800_col_afile as ri_l800_col_afile, ri.l800_baw_afile as ri_l800_baw_afile, ri.l800_sep_afile as ri_l800_sep_afile
        from (
            build_page as bp,
            build_image as bi,
            image as i,
            design_islot as dis
        )
        left join (image as ri) on
            ri.image_id = i.replace_image_id
        where
            bp.build_page_id = %s and
            bi.build_page_id = bp.build_page_id and
            i.access_id = bi.image_access_id and
            dis.design_islot_id = bi.design_islot_id
        order by bi.seq""",
        (build_page_id,)
    )
    bi_rows = c.fetchall()

    for bi_row in bi_rows:
        if bi_row['ri_full_col_afile'] != None:
            bi_row['full_col_afile'], bi_row['rotation'], bi_row['l800_col_afile'], bi_row['l800_baw_afile'], bi_row['l800_sep_afile'] = \
                bi_row['ri_full_col_afile'], bi_row['ri_rotation'], bi_row['ri_l800_col_afile'], bi_row['ri_l800_baw_afile'], bi_row['ri_l800_sep_afile']
        # Increase readability of some later dense computations!
        if for_lab:
            # XXX - this is incredibly magical.  I intend to greatly simplify the nominal stuff, and then, this.
            dis_x0_part = ((r['pp_nom_width']  * bi_row['dis_x0'] / r['dpl_nom_width'])  - r['lab_frame_x0']) / (r['lab_frame_x1'] - r['lab_frame_x0'])
            dis_y0_part = ((r['pp_nom_height'] * bi_row['dis_y0'] / r['dpl_nom_height']) - r['lab_frame_y0']) / (r['lab_frame_y1'] - r['lab_frame_y0'])
            dis_x1_part = ((r['pp_nom_width']  * bi_row['dis_x1'] / r['dpl_nom_width'])  - r['lab_frame_x0']) / (r['lab_frame_x1'] - r['lab_frame_x0'])
            dis_y1_part = ((r['pp_nom_height'] * bi_row['dis_y1'] / r['dpl_nom_height']) - r['lab_frame_y0']) / (r['lab_frame_y1'] - r['lab_frame_y0'])
            bi_x0_part  = ((r['pp_nom_width']  * bi_row['bi_x0']  / r['bp_nom_width'])   - r['lab_frame_x0']) / (r['lab_frame_x1'] - r['lab_frame_x0'])
            bi_y0_part  = ((r['pp_nom_height'] * bi_row['bi_y0']  / r['bp_nom_height'])  - r['lab_frame_y0']) / (r['lab_frame_y1'] - r['lab_frame_y0'])
            bi_x1_part  = ((r['pp_nom_width']  * bi_row['bi_x1']  / r['bp_nom_width'])   - r['lab_frame_x0']) / (r['lab_frame_x1'] - r['lab_frame_x0'])
            bi_y1_part  = ((r['pp_nom_height'] * bi_row['bi_y1']  / r['bp_nom_height'])  - r['lab_frame_y0']) / (r['lab_frame_y1'] - r['lab_frame_y0'])
        else:
            dis_x0_part = bi_row['dis_x0'] / r['dpl_nom_width']
            dis_y0_part = bi_row['dis_y0'] / r['dpl_nom_height']
            dis_x1_part = bi_row['dis_x1'] / r['dpl_nom_width']
            dis_y1_part = bi_row['dis_y1'] / r['dpl_nom_height']
            bi_x0_part  = bi_row['bi_x0']  / r['bp_nom_width']
            bi_y0_part  = bi_row['bi_y0']  / r['bp_nom_height']
            bi_x1_part  = bi_row['bi_x1']  / r['bp_nom_width']
            bi_y1_part  = bi_row['bi_y1']  / r['bp_nom_height']

        # I believe it's faster to crop than to scale, especially for big images.
        # So, do a rough crop (error < 2px) first, then scale to the exact final
        # size in one dimension (error < 2px * scale factor in other dimension),
        # then do a second crop of a few rows/columns.
        if for_lab:
            c_im_name = bi_row['full_col_afile']
            m = re.match('(.)(.)', c_im_name)
            c_im_path = '/data/csasset/{}/{}/{}'.format(m.group(1), m.group(2), c_im_name)
            c_im = Image.open(c_im_path)
            if bi_row['rotation'] != 0: c_im = c_im.rotate(bi_row['rotation'])
            if bi_row['tint_id'] == 2:
                c_im = ImageOps.grayscale(c_im)
            elif bi_row['tint_id'] == 3:
                c_im = ImageOps.grayscale(c_im)
                c_im = ImageOps.colorize(c_im, 'rgb(0%,0%,0%)', 'rgb(100%,95%,80%)')
        else:
            if   bi_row['tint_id'] == 1: c_im_name = bi_row['l800_col_afile']
            elif bi_row['tint_id'] == 2: c_im_name = bi_row['l800_baw_afile']
            elif bi_row['tint_id'] == 3: c_im_name = bi_row['l800_sep_afile']
            m = re.match('(.)(.)', c_im_name)
            c_im_path = '/data/csasset/{}/{}/{}'.format(m.group(1), m.group(2), c_im_name)
            c_im = Image.open(c_im_path)

        # Crop customer image as close as possible at this size.
        xmagic = c_im.size[0] / (bi_x1_part  - bi_x0_part)
        ix0 = int(     xmagic * (dis_x0_part - bi_x0_part))
        ix1 = int(.5 + xmagic * (dis_x1_part - bi_x0_part))
        ymagic = c_im.size[1] / (bi_y1_part  - bi_y0_part)
        iy0 = int(     ymagic * (dis_y0_part - bi_y0_part))
        iy1 = int(.5 + ymagic * (dis_y1_part - bi_y0_part))
        c_im = c_im.crop((ix0, iy0, ix1, iy1))

        # Resize cropped image chunk to slightly larger than slot.
        # Also compute the subsequent crop while it's convenient.
        sx0 = dis_x0_part * render_width
        sx1 = dis_x1_part * render_width
        sy0 = dis_y0_part * render_height
        sy1 = dis_y1_part * render_height

        sw = sx1 - sx0
        sh = sy1 - sy0
        s_aspect = sw / sh
        i_aspect = 1. * c_im.size[0] / c_im.size[1]

        if i_aspect >= s_aspect:
            h = int(.5 + sh)
            w = int(.5 +  h * i_aspect)
            cx0 = int(.5 + (sw - w) / 2.)
            cy0 = 0
            cx1 = cx0 + w - 1
            cy1 = h - 1
        else:
            w = int(.5 + sw)
            h = int(.5 +  w / i_aspect)
            cx0 = 0
            cy0 = int(.5 + (sh - h) / 2.)
            cx1 = w - 1
            cy1 = cy0 + h - 1

        c_im = c_im.resize((w, h), Image.ANTIALIAS)
        c_im = c_im.crop((cx0, cy0, cx1, cy1))
        im.paste(c_im, (int(.5 + sx0), int(.5 + sy0)))

    short_length = im.size[0] if im.size[0] <= im.size[1] else im.size[1]
    if for_lab: overlay_afile = base_overlay_afile
    elif short_length > 200: overlay_afile = s800_overlay_afile
    else: overlay_afile = s200_overlay_afile

    if overlay_afile != None:
        m = re.match('(.)(.)', overlay_afile)
        o_im_path = '/data/csasset/'+m.group(1)+'/'+m.group(2)+'/'+overlay_afile
        o_im = Image.open(o_im_path)
        o_im = o_im.resize(im.size, Image.ANTIALIAS)
        im.paste(o_im, (0, 0), o_im)

    # We know that page_text_img does the same fitting computations that we do, so pass
    # through the original values to get the same render_* therein.
    text_img = page_text_img(build_page_id, fit_width, fit_height, fit_type, for_lab)
    im.paste(text_img, (0, 0), text_img)
    return im

def page_text_img(build_page_id, fit_width, fit_height, fit_type, for_lab=False):
    """Creates and returns an RGBA Image of rendered text on a transparent background for a
       given build-page.  This can be returned to a web browser for use on the build page,
       or composited over an in-render design for use on the preview page or fulfillment.

       Requires a fit size and a fit type ('fb' or 'ff' for full-bleed or full-frame).
       Note, 'fb' will return an image that is >= the fit size; 'ff' will return one that is <=.

       Raises DbError on inconsistent database."""

    fit_width  = float(fit_width)
    fit_height = float(fit_height)
    fit_aspect = fit_width / fit_height

    c = get_cursor()

    # I hardcode the dpl overlay column names here (and the sizes later).  We could add a layer to
    # make them easily changeable, but there's no obvious need for it.
    c.execute("""
        select
            bp.nom_width as bp_nom_width, bp.nom_height as bp_nom_height,
            dpl.nom_width as dpl_nom_width, dpl.nom_height as dpl_nom_height,
            pp.lab_frame_x0, pp.lab_frame_y0, pp.lab_frame_x1, pp.lab_frame_y1,
            pp.nom_width as pp_nom_width, pp.nom_height as pp_nom_height
        from (build_page as bp, design_page_layout as dpl, product_page as pp)
        where
            bp.build_page_id = %s and
            dpl.design_page_layout_id = bp.design_page_layout_id and
            pp.product_page_id = dpl.product_page_id""",
        (build_page_id,)
    )
    r = c.fetchone()

    if for_lab:
        page_aspect = (r['lab_frame_x1'] - r['lab_frame_x0']) / (r['lab_frame_y1'] - r['lab_frame_y0'])
    else:
        page_aspect = r['bp_nom_width'] / r['bp_nom_height']

    if fit_type == 'fb' and page_aspect >= fit_aspect:
        render_width, render_height = fit_height * page_aspect, fit_height
    elif fit_type == 'fb' and page_aspect < fit_aspect:
        render_width, render_height = fit_width, fit_width / page_aspect
    elif fit_type == 'ff' and page_aspect >= fit_aspect:
        render_width, render_height = fit_width, fit_width / page_aspect
    elif fit_type == 'ff' and page_aspect < fit_aspect:
        render_width, render_height = fit_height * page_aspect, fit_height
    else:
        raise Exception('Bad fit_type given: {}'.format(fit_type))

    if for_lab:
        scale = render_width * r['pp_nom_width'] / (r['lab_frame_x1'] - r['lab_frame_x0']) / r['dpl_nom_width']
    else:
        scale = render_width / r['dpl_nom_width']

    # Getting a deep build seemed too heavy (builds are dynamic and
    # not cached).
    c.execute("""
        select
            bt.design_tslot_id, bt.content, bt.font_id, bt.fontsize_id, bt.gravity_id, bt.color_rgba,
            dts.run_horizontally, dts.max_rows, dts.rotation, dts.x0, dts.y0, dts.x1, dts.y1
        from (build_page as bp, build_text as bt, design_tslot as dts)
        where
            bp.build_page_id = %s and
            bt.build_page_id = bp.build_page_id and
            dts.design_tslot_id = bt.design_tslot_id
        order by bt.seq""",
        (build_page_id,)
    )
    t_rows = c.fetchall()

    im = Image.new(
        'RGBA',
        (int(.5 + render_width), int(.5 + render_height)),
        (255, 255, 255, 0)
    )

    for t_row in t_rows:
        # '0.58,1.00,0.02' -> (148, 255, 5)
        color = tuple(int(round(255 * float(c))) for c in t_row['color_rgba'].split(',')[0:3])
        gravity = Statics.gravities.get_id(t_row['gravity_id'])
        font = Statics.fonts.get_id(t_row['font_id'])
        fontsize = Statics.fontsizes.get_id(t_row['fontsize_id'])
        m = re.match('(.)(.)', font['afile'])
        font_path = '/data/csasset/'+m.group(1)+'/'+m.group(2)+'/'+font['afile']
        max_size = fontsize['max_pointsize'] * scale
        if fontsize['autoscale'] == 1:
            min_size = max_size / 2
        else:
            min_size = max_size

        slot_width  = (t_row['x1'] - t_row['x0']) * scale
        slot_height = (t_row['y1'] - t_row['y0']) * scale

        if t_row['rotation'] % 180 == 90:
            slot_width, slot_height = slot_height, slot_width
        if t_row['run_horizontally'] != 1:
            content = '\n'.join(list(t_row['content']))
        else: content = t_row['content']

        text_im = best_fit_image(
            content,
            color,
            gravity['internal_name'],
            font_path,
            int(.5 + min_size),
            int(.5 + max_size),
            slot_width,
            slot_height,
            t_row['max_rows'],
            h_offset=font['h_offset']
        )
        (w, h) = text_im.size
        slot_width_i, slot_height_i = int(.5 + slot_width), int(.5 + slot_height)
        if w > slot_width_i:
            x0 = int(.5 + (w - slot_width) / 2.0)   # Floating-point is correct (avoids rounding error).
            x1 = x0 + slot_width_i   # Don't subtract 1; PIL uses corner-based coordinates when cropping.
            text_im = text_im.crop((x0, 0, x1, h))
            (w, h) = text_im.size
        if h > slot_height_i:
            y0 = int(.5 + (h - slot_height) / 2.0)
            y1 = y0 + slot_height_i
            text_im = text_im.crop((0, y0, w, y1))
            (w, h) = text_im.size

        if re.search('West$', gravity['internal_name']): x0 = 0
        elif re.search('East$', gravity['internal_name']): x0 = slot_width_i - w
        else: x0 = int(.5 + (slot_width - w) / 2.0)
        if re.search('^North', gravity['internal_name']): y0 = 0
        elif re.search('^South', gravity['internal_name']): y0 = slot_height_i - h
        else: y0 = int(.5 + (slot_height - h) / 2.0)

        slot_im = Image.new('RGBA', (slot_width_i, slot_height_i), color + (0,))
        slot_im.paste(color, (int(x0 + .5), int(y0 + .5)), text_im)
        if t_row['rotation'] != 0:
            slot_im = slot_im.rotate(t_row['rotation'])

        if for_lab:
            base_x0 = int(.5 + (t_row['x0'] - r['lab_frame_x0']) * scale)
            base_y0 = int(.5 + (t_row['y0'] - r['lab_frame_y0']) * scale)
        else:
            base_x0 = int(.5 + t_row['x0'] * scale)
            base_y0 = int(.5 + t_row['y0'] * scale)
        mask_im = Image.new('RGBA', slot_im.size, (0, 0, 0, 255))   # RGB is "don't care"
        im.paste(slot_im, (base_x0, base_y0), mask_im)

    return im

diff_limit = 1.05

def best_fit_image(text, color, gravity, font_path, min_size, max_size, slot_width, slot_height, max_rows, h_offset=None):
    prov_size = max_size

    while True:
        text_lines = lineify_text(text, font_path, int(prov_size), slot_width, max_rows)
        text_im = draw_text_lines(text_lines, color, gravity, font_path, int(prov_size), slot_width, h_offset=h_offset)
        (layout_width, layout_height) = text_im.size
        fits = False
        if layout_width <= slot_width and layout_height <= slot_height:
            return text_im
        elif prov_size == min_size:
            return text_im
        else:
            prov_size /= diff_limit
            if prov_size < min_size: prov_size = min_size

# "Lineifying the text" is somewhat different between single-line and
# multi-line slots:
#
# For single-line slots, the words for all customer lines are concatenated
# into one long customer line - in other words, embedded newlines are
# stripped.  Then, the customer line is laid out at the given size in one
# line.
#
# For multi-line slots, each customer line is broken according to the width
# of the slot, that is, words are added until the next word would overflow
# the right edge of the slot.  If not even one word would fit, the single
# word is allowed to overflow.  Embedded newlines start a new layout line.
#
# Briefly put, single lines overflow more horizontally, and multiple lines
# overflow more vertically.

def lineify_text(text, font_path, font_size, slot_width, max_rows):
    # Tokenize text.
    text = re.sub('\n$', '', text, count = 1)
    cont_lines = []
    for line_str in text.split('\n'):
        line_str = re.sub(' +$', '', line_str)
        sm = re.match('^( *) ', line_str)
        words = re.split(' +', line_str)
        if words[0] == '' and sm != None:
            words[0] = sm.group(1)
        cont_lines.append(words)

    base_im = Image.new('RGBA', (0, 0), (255, 255, 255, 0))
    base_idraw = ImageDraw.Draw(base_im)

    ifont = ImageFont.truetype(font_path, font_size)

    text_lines = []
    if max_rows == 1:
        words = []
        for cont_line in cont_lines:
            words.extend(cont_line)
        text_lines.append(words)
    else:
        for cont_line in cont_lines:
            if len(text_lines) == max_rows: break
            words = []
            while len(text_lines) < max_rows:
                next_word = cont_line[0] if len(cont_line) > 0 else ''
                tstr = ' '.join(words + [next_word])
                (w, h) = base_idraw.textsize(tstr, font = ifont)
                if w < slot_width:
                    if len(cont_line) > 0:
                        words.append(cont_line.pop(0))
                    if len(cont_line) == 0:
                        text_lines.append(words)
                        words = []
                        break
                else:
                    if len(words) == 0:
                        # Not even one word would fit.
                        words.append(cont_line.pop(0))
                    text_lines.append(words)
                    words = []
                    continue

    return text_lines

def draw_text_lines(text_lines, color, gravity, font_path, font_size, slot_width, h_offset=None):
    base_im = Image.new('RGBA', (0, 0), color + (0,))
    base_idraw = ImageDraw.Draw(base_im)

    ifont = ImageFont.truetype(font_path, font_size)

    h_text_adj = 0
    if h_offset != None:
        h_text_adj = h_offset * font_size

    text_ims = []
    for text_line in text_lines:
        text_ims.append(draw_line(text_line, base_idraw, ifont, color, h_text_adj=h_text_adj))

    tw = th = 0
    for text_im in text_ims:
        (w, h) = text_im.size
        tw = max(tw, w)
        th += h
    if tw > 0 and th > 0:
        base_im = base_im.resize((tw, th), Image.ANTIALIAS)
    else:
        # There appears to be a bug in PIL whereby scaling to a size with a zero-sided
        # length throws a MemoryError (probably an infinite loop somewhere) when using
        # Image.ANTIALIAS.  Working around it.
        base_im = base_im.resize((tw, th))
    y = 0
    for text_im in text_ims:
        (w, h) = text_im.size
        if re.search('West$', gravity):
            base_im.paste(color, (0, y), text_im)
        elif re.search('East$', gravity):
            base_im.paste(color, (tw - w, y), text_im)
        else:
            base_im.paste(color, ((tw - w) / 2, y), text_im)
        y += h

    return base_im

def draw_line(words, idraw, ifont, color, h_text_adj=0):
    tstr = ' '.join(words)
    (w, h) = idraw.textsize(tstr, font = ifont)
    text_im = Image.new('RGBA', (w, h), color + (0,))
    text_idraw = ImageDraw.Draw(text_im)
    text_idraw.text((h_text_adj, 0), tstr, font = ifont, fill = color)
    return text_im

