# $Header: //depot/cs/db/Build.py#1 $

import re
import MySQLdb

import db.Db as Db
from db.Db import get_cursor
from db.Exceptions import DbError, DbKeyInvalid
import db.ImageRender as ImageRender
import db.Product as Product
import db.Statics as Statics
from p.Utility import new_access_id

def build_full(build_id=None, access_id=None, shallow=False):
    """Returns a fully-populated build object.  Shallow builds contain only
       the build row; deep builds also contain the build_pages, build_images,
       images (with tint), and build_texts (with gravity, font, and font_size).
       See spec at http://sdrv.ms/14ud1k8.

       Raises DbKeyInvalid on invalid database key;
              DbError on database inconsistency (failed assertion)."""

    c = get_cursor()

    if build_id != None:
        build_id = int(build_id)
        c.execute("""
            select *
            from build
            where build.build_id = %s""",
            (build_id,)
        )
        if (c.rowcount == 0):
            raise DbKeyInvalid("Build not found by build_id: {}.".format(build_id))
        if (c.rowcount > 1):
            raise DbError("Multiple builds found by build_id: {}.".format(build_id))
    elif access_id != None:
        access_id = re.sub('[^a-z0-9_-]', '', access_id)
        c.execute("""
            select *
            from build
            where build.access_id = %s""",
            (access_id,)
        )
        if (c.rowcount == 0):
            raise DbKeyInvalid("Build not found by build.access_id: {}.".format(access_id))
        if (c.rowcount > 1):
            raise DbError("Multiple builds found by build.access_id: {}.".format(access_id))
    else:
        print "build_full called with no arguments"
        import traceback
        traceback.print_exc()
        return None

    build = c.fetchone()

    if shallow:
        return build

    c.execute("""
        select *
        from build_page
        where build_id = %s
        order by seq""",
        (build['build_id'],)
    )
    build['build_pages'] = c.fetchall()
    for page in build['build_pages']:
        c.execute("""
            select *
            from build_image
            where build_page_id = %s
            order by seq""",
            (page['build_page_id'],)
        )
        page['build_images'] = c.fetchall()
        for build_image in page['build_images']:
            build_image['tint'] = Statics.tints.get_id(build_image['tint_id'])
            if build_image['image_access_id'] != None:
                c.execute("""
                    select *
                    from image
                    where access_id = %s
                    limit 1""",
                    (build_image['image_access_id'],)
                )
                if (c.rowcount == 0):
                    raise DbKeyInvalid("image not found by access_id: {}.".format(build_image['image_access_id']))
                build_image['image'] = c.fetchone()
        c.execute("""
            select *
            from build_text
            where build_page_id = %s
            order by seq""",
            (page['build_page_id'],)
        )
        page['build_texts'] = c.fetchall()
        for build_text in page['build_texts']:
            build_text['gravity'] = Statics.gravities.get_id(build_text['gravity_id'])
            build_text['font'] = Statics.fonts.get_id(build_text['font_id'])
            build_text['fontsize'] = Statics.fontsizes.get_id(build_text['fontsize_id'])

    return build

def build_ecom(build_id, bounding_width = None, bounding_height = None):
    """Returns an ecom-friendly build object from a build_id.  See http://sdrv.ms/14dwrvQ for spec.
       Pages, images, and texts are ordered by their respective sequences.

       If a bounding box is provided, all coordinates will be modified to fit (full-frame).
       Otherwise, they are unchanged from their default, nom_*-based, values."""

    build = build_full(build_id=build_id)
    be = {
        'build_access_id': build['access_id'],
        'rev': build['revision'],
        'pd_id': build['product_design_id'],
        'pages': []
    }

    for page in build['build_pages']:
        if bounding_width != None and bounding_height != None:
            bp_aspect = 1. * page['nom_width'] / page['nom_height']
            bounding_aspect = 1. * bounding_width / bounding_height
            if bp_aspect > bounding_aspect:
                scale = bounding_width  / page['nom_width']
            else:
                scale = bounding_height / page['nom_height']
        else:
            scale = 1.

        be['pages'].append({
            'dpl_id': page['design_page_layout_id'],
            'seq': page['seq'],
            'page_width': page['nom_width'] * scale,
            'page_height': page['nom_height'] * scale,
            'images': [],
            'texts': []
        })
        for build_image in page['build_images']:
            be['pages'][-1]['images'].append({
                'dis_id': build_image['design_islot_id'],
                'seq': build_image['seq'],
                'access_id': build_image['image_access_id'],
                'tint_id': build_image['tint']['tint_id'],
                'x0': build_image['x0'] * scale if build_image['x0'] != None else None,
                'x1': build_image['x1'] * scale if build_image['x1'] != None else None,
                'y0': build_image['y0'] * scale if build_image['y0'] != None else None,
                'y1': build_image['y1'] * scale if build_image['y1'] != None else None
            })
        for build_text in page['build_texts']:
            be['pages'][-1]['texts'].append({
                'dts_id': build_text['design_tslot_id'],
                'seq': build_text['seq'],
                'content': build_text['content'],
                'font_id': build_text['font']['font_id'],
                'fontsize_id': build_text['fontsize']['fontsize_id'],
                'gravity_id': build_text['gravity']['gravity_id'],
                'color': build_text['color_rgba']
            })

    return be

def create_empty(pd_id, ecom_session_key):
    """Creates an empty build and associates it with a session.  Returns the new build_id.

       Raises DbKeyInvalid on invalid database keys, or KeyError/ValueError/TypeError on invalid
       insert object."""

    c = get_cursor()

    c.execute("""
        select po.lab_product_orientation_id
        from (product_design as pd, product_orientation as po)
        where
            pd.product_design_id = %s and
            po.product_id = pd.product_id and
            po.orientation_id = pd.orientation_id""",
        (pd_id,)
    )
    lpo_id = c.fetchone()['lab_product_orientation_id']

    access_id = None
    build_id = None
    while True:
        try:
            access_id = new_access_id(16)
            c.execute("""
                insert into build
                (access_id, revision, product_design_id, session_key, lab_product_orientation_id)
                values
                (%s, %s, %s, %s, %s)""",
                (access_id, 1, pd_id, ecom_session_key, lpo_id)
            )
            build_id = c.lastrowid
            break
        except MySQLdb.IntegrityError:
            continue

    return build_id

def clone(access_id, new_line_item_id):
    """Clones a build, including subordinate rows, and returns its build_id.  All
       non-primary-key fields will be unchanged, except build.access_id and build.line_item_id """

    c = get_cursor()

    build = build_full(access_id=access_id)
    fields = []
    values = []
    # Rather than specifying fields and breaking this whenever we change one of the
    # tables, I iterate through the fields and handle certain ones specially.
    for field in build:
        if field == 'build_pages': continue
        if field == 'build_id': continue
        if field == 'access_id': continue
        if field == 'line_item_id': continue
        fields.append(field)
        values.append(build[field])

    access_id = None
    build_id = None
    while True:
        try:
            access_id = new_access_id(16)
            c.execute("""
                insert into build
                (access_id, line_item_id, {})
                values
                (%s, %s, {})""".format(
                    ', '.join(fields),
                    ', '.join('%s' for value in values)
                ),
                tuple([access_id] + [new_line_item_id] + values)
            )
            build_id = c.lastrowid
            break
        except MySQLdb.IntegrityError:
            continue

    for build_page in build['build_pages']:
        fields = []
        values = []
        for field in build_page:
            if field == 'build_images': continue
            if field == 'build_texts': continue
            if field == 'build_page_id': continue
            if field == 'build_id': continue
            fields.append(field)
            values.append(build_page[field])
        fields.append('build_id')
        values.append(build_id)
        c.execute("""
            insert into build_page
            ({})
            values
            ({})""".format(
                ', '.join(fields),
                ', '.join('%s' for value in values)
            ),
            tuple(values)
        )
        build_page_id = c.lastrowid

        for build_image in build_page['build_images']:
            fields = []
            values = []
            for field in build_image:
                if field == 'tint': continue
                if field == 'image': continue
                if field == 'build_image_id': continue
                if field == 'build_page_id': continue
                fields.append(field)
                values.append(build_image[field])
            fields.append('build_page_id')
            values.append(build_page_id)
            c.execute("""
                insert into build_image
                ({})
                values
                ({})""".format(
                    ', '.join(fields),
                    ', '.join('%s' for value in values)
                ),
                tuple(values)
            )

        for build_text in build_page['build_texts']:
            fields = []
            values = []
            for field in build_text:
                if field == 'gravity': continue
                if field == 'font': continue
                if field == 'fontsize': continue
                if field == 'build_text_id': continue
                if field == 'build_page_id': continue
                fields.append(field)
                values.append(build_text[field])
            fields.append('build_page_id')
            values.append(build_page_id)
            c.execute("""
                insert into build_text
                ({})
                values
                ({})""".format(
                    ', '.join(fields),
                    ', '.join('%s' for value in values)
                ),
                tuple(values)
            )

    return build_id

def remove(build_id):
    """Removes a build, including subordinate rows.  Also nulls out ecom_session.current_build_id,
       where needed."""

    c = get_cursor()

    build = build_full(build_id=build_id)

    for build_page in build['build_pages']:
        for build_image in build_page['build_images']:
            c.execute("""
                delete from build_image
                where build_image_id = %s""",
                (build_image['build_image_id'],)
            )
        for build_text in build_page['build_texts']:
            c.execute("""
                delete from build_text
                where build_text_id = %s""",
                (build_text['build_text_id'],)
            )
        c.execute("""
            delete from build_page
            where build_page_id = %s""",
            (build_page['build_page_id'],)
        )
    c.execute("""
        delete from build
        where build_id = %s""",
        (build['build_id'],)
    )

    c.execute("""
        update ecom_session
        set current_build_id = null
        where current_build_id = %s""",
        (build['build_id'],)
    )

def reset_images(image_access_id):
    """Resets all build_images with this image_access_id to their initial state
       (fully zoomed out)."""

    c = get_cursor()
    c.execute("""
        select full_width, full_height, rotation
        from image
        where access_id = %s""",
        (image_access_id,)
    )
    ir = c.fetchone();

    if ir['rotation'] % 180 == 90:
        i_ar = 1. * ir['full_height'] / ir['full_width']
    else:
        i_ar = 1. * ir['full_width'] / ir['full_height']

    c.execute("""
        select
            bi.build_image_id,
            di.x0 * bp.nom_width  / dpl.nom_width  as x0,
            di.y0 * bp.nom_height / dpl.nom_height as y0,
            di.x1 * bp.nom_width  / dpl.nom_width  as x1,
            di.y1 * bp.nom_height / dpl.nom_height as y1
        from (build_image as bi, build_page as bp, design_islot as di, design_page_layout as dpl)
        where
            bi.image_access_id = %s and
            bp.build_page_id = bi.build_page_id and
            di.design_islot_id = bi.design_islot_id and
            dpl.design_page_layout_id = di.design_page_layout_id""",
        (image_access_id,)
    )
    birs = c.fetchall()
    for bir in birs:
        di_ar = (bir['x1'] - bir['x0']) / (bir['y1'] - bir['y0'])
        if i_ar > di_ar:
            y0, y1 = bir['y0'], bir['y1']
            w = i_ar * (y1 - y0)
            x0 = (bir['x1'] + bir['x0'] - w) / 2
            x1 = (bir['x1'] + bir['x0'] + w) / 2
        else:
            x0, x1 = bir['x0'], bir['x1']
            h = (x1 - x0) / i_ar
            y0 = (bir['y1'] + bir['y0'] - h) / 2
            y1 = (bir['y1'] + bir['y0'] + h) / 2
        c.execute("""
            update build_image
            set x0 = %s, y0 = %s, x1 = %s, y1 = %s
            where build_image_id = %s""",
            (x0, y0, x1, y1, bir['build_image_id'],)
        )

def update_line_item_id(build_id, line_item_id):
    c = get_cursor()

    c.execute("""
        update build
        set line_item_id = %s
        where build_id = %s""",
        (int(line_item_id), int(build_id))
    )

def update(be, build_id):
    """Updates/inserts one or more build_pages, and creates new build_texts
       and build_images, from an ecom-friendly build object.
       See http://sdrv.ms/14dwrvQ for spec.

       This is a fundamentally destructive update - the build_page, images,
       and texts are deleted and reinserted, for any build_page(s) provided.
       (The build itself is only updated, to avoid a very unlikely race condition
       of another process grabbing our access_id.)

       For each image and text, if an entry is provided in the be, that is used
       to populate.  Otherwise, it is set to an empty state.  This keeps things
       relatively simple, and hacked seq/id values for texts and images are
       gracefully ignored.

       Raises DbKeyInvalid on invalid database keys, or KeyError/ValueError/
       TypeError on invalid update object."""

    c = get_cursor()

    build_id = int(build_id)

    # We use this to grab the current product_design_id, as well as to recognize
    # which pages currently exist in the build (and will therefore be deleted if
    # a replacement is provided).

    b_srow = build_full(build_id=build_id)
    old_pd_id = b_srow['product_design_id']
    new_pd_id = be['pd_id']

    if new_pd_id != old_pd_id:
        c.execute("""
            select po.lab_product_orientation_id
            from (product_design as pd, product_orientation as po)
            where
                pd.product_design_id = %s and
                po.product_id = pd.product_id and
                po.orientation_id = pd.orientation_id""",
            (new_pd_id,)
        )
        new_lpo_id = c.fetchone()['lab_product_orientation_id']

        c.execute("""
            update build
            set revision = revision + 1, product_design_id = %s, lab_product_orientation_id = %s
            where build_id = %s""",
            (new_pd_id, new_lpo_id, build_id)
        )
    else:
        c.execute("""
            update build
            set revision = revision + 1
            where build_id = %s""",
            (build_id,)
        )

    # Form a set of error-checking keys for each page in the product_design
    # referred to by our current build:
    #
    # <design_page.seq>-<design_page_layout_id>
    #
    # We check every page in the provided build object against this.

    c.execute("""
        select concat(dp.seq, '-', dpl.design_page_layout_id) as dpl_key
        from (design_page as dp, page_layout_group as plg, page_layout as pl, design_page_layout as dpl)
        where
            dp.product_design_id = %s and
            plg.page_layout_group_id = dp.page_layout_group_id and
            pl.page_layout_group_id = plg.page_layout_group_id and
            dpl.page_layout_id = pl.page_layout_id""",
        (new_pd_id,)
    )
    dpl_keys = set([r['dpl_key'] for r in c.fetchall()])

    # Form a dictionary of pages from our existing database build:
    # <build_page.seq>: <build_page_id>

    seq_bp_id = {}
    for bp_srow in b_srow['build_pages']:
        seq_bp_id[bp_srow['seq']] = bp_srow['build_page_id']

    # Go through the build-object pages, noting which database build_pages we'll
    # have to delete to make room for them.  Error out if any of the build-object
    # pages are invalid.  (This is non-linear but seems necessary to account for
    # the "delete all pages because pd_id has changed" scenario.)

    del_seqs = {}
    for be_page in be['pages']:
        if be_page['dpl_id'] == None: continue
        dpl_id = int(be_page['dpl_id'])
        seq = int(be_page['seq'])
        dpl_key = str(seq)+'-'+str(dpl_id)
        if dpl_key not in dpl_keys:
            raise DbKeyInvalid("build object has bad dpl_id and/or seq")
        del_seqs[seq] = True

    # Make our deletions.

    for seq in seq_bp_id:
        if seq in del_seqs or new_pd_id != old_pd_id:
            bp_id = seq_bp_id[seq]
            c.execute("""
                delete from build_image
                where build_page_id = %s""",
                (bp_id,)
            )
            c.execute("""
                delete from build_text
                where build_page_id = %s""",
                (bp_id,)
            )
            c.execute("""
                delete from build_page
                where build_page_id = %s""",
                (bp_id,)
            )

    # Make our insertions.

    for be_page in be['pages']:
        if be_page['dpl_id'] == None: continue
        dpl_id = int(be_page['dpl_id'])

        c.execute("""
            select pp.lab_product_islot_id, pp.lab_fit_rotation
            from (design_page_layout as dpl, product_page as pp)
            where
                dpl.design_page_layout_id = %s and
                pp.product_page_id = dpl.product_page_id""",
            (dpl_id,)
        )
        pp_row = c.fetchone()

        seq = int(be_page['seq'])
        c.execute("""
            insert into build_page
            (build_id, design_page_layout_id, seq, nom_width, nom_height, lab_product_islot_id, lab_fit_rotation)
            values (%s, %s, %s, %s, %s, %s, %s)""",
            (b_srow['build_id'], be_page['dpl_id'], seq, float(be_page['page_width']), float(be_page['page_height']), pp_row['lab_product_islot_id'], pp_row['lab_fit_rotation'])
        )
        bp_id = c.lastrowid

        seq_be_image = {}
        for be_image in be_page['images']:
            seq_be_image[int(be_image['seq'])] = be_image

        c.execute("""
            select design_islot_id, seq
            from design_islot
            where design_page_layout_id = %s
            order by seq""",
            (be_page['dpl_id'],)
        )
        dis_srows = c.fetchall()

        for dis_srow in dis_srows:
            seq = dis_srow['seq']
            if seq not in seq_be_image or seq_be_image[seq]['dis_id'] != dis_srow['design_islot_id']:
                c.execute("""
                    insert into build_image
                    (build_page_id, design_islot_id, seq)
                    values (%s, %s, %s)""",
                    (bp_id, dis_srow['design_islot_id'], seq)
                )
            else:
                be_image = seq_be_image[seq]
                c.execute("""
                    insert into build_image
                    (build_page_id, design_islot_id, seq, image_access_id, tint_id, x0, y0, x1, y1)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", (
                        bp_id,
                        int(dis_srow['design_islot_id']),
                        seq,
                        re.sub('[^0-9a-z]', '', be_image['access_id']) if be_image['access_id'] != None else None,
                        int(be_image['tint_id']),
                        float(be_image['x0']) if be_image['x0'] != None else None,
                        float(be_image['y0']) if be_image['y0'] != None else None,
                        float(be_image['x1']) if be_image['x1'] != None else None,
                        float(be_image['y1']) if be_image['y1'] != None else None
                    )
                )

        seq_be_text = {}
        for be_text in be_page['texts']:
            seq_be_text[int(be_text['seq'])] = be_text

        c.execute("""
            select design_tslot_id, seq
            from design_tslot
            where design_page_layout_id = %s
            order by seq""",
            (be_page['dpl_id'],)
        )
        dts_rows = c.fetchall()

        for dts_srow in dts_rows:
            seq = dts_srow['seq']
            if seq not in seq_be_text or seq_be_text[seq]['dts_id'] != dts_srow['design_tslot_id']:
                c.execute("""
                    insert into build_text
                    (build_page_id, design_tslot_id, seq)
                    values (%s, %s, %s)""",
                    (bp_id, dts_srow['design_tslot_id'], seq)
                )
            else:
                fields = ['build_page_id', 'design_tslot_id', 'seq']
                vals = [bp_id, dts_srow['design_tslot_id'], seq]
                be_text = seq_be_text[seq]
                field_var = {
                    'content': 'content', 'font_id': 'font_id',
                    'fontsize_id': 'fontsize_id', 'gravity_id': 'gravity_id',
                    'color': 'color_rgba'
                }
                for field in field_var:
                    if field in be_text and be_text[field] != None:
                        fields.append(field_var[field])
                        vals.append(be_text[field])
                c.execute(
                    "insert into build_text ({}) values ({})".format(
                        ', '.join(fields),
                        ', '.join(['%s'] * len(fields))
                    ),
                    vals
                )

def image_replace_update(image_id):
    """ Update all build revisions associated with the image_id parameter.
        This is to force new calls on composited work to be displayed with
        the new replacement image.  We return a list of build.access_ids
        to help the scripts refresh."""
    image_id = int(image_id)
    c = get_cursor()
    c.execute("""
        select build.access_id as build_access_id, build.build_id, build.revision
        from build, build_page, build_image, image
        where image.image_id = %s
        and build_image.image_access_id = image.access_id
        and build_page.build_page_id = build_image.build_page_id
        and build.build_id = build_page.build_id""",
        (image_id,)
    )
    build_rows = c.fetchall()
    for build in build_rows:
        # This is clearly a race condition, but we are dealing with browser
        # cache issues here, so a failure really doesn't amount to much.
        build['revision'] += 1
        c.execute("""
            update build
            set revision = %s
            where build_id = %s""",
            (build['revision'], build['build_id'])
        )
    return build_rows


def page_img_access_id(build_access_id, seq, fit_width, fit_height, fit_type):
    build_access_id = re.sub('[^a-z0-9_-]', '', build_access_id)
    seq = int(seq)

    c = get_cursor()

    c.execute("""
        select bp.build_page_id
        from (build as b, build_page as bp)
        where
            b.access_id = %s and
            bp.build_id = b.build_id and
            bp.seq = %s""",
        (build_access_id, seq)
    )

    if c.rowcount == 0:
        raise DbKeyInvalid("Build page not found by access_id/seq: {}, {}.".format(build_access_id, seq))
    if c.rowcount > 1:
        raise DbError("Multiple build pages found by access_id/seq: {}, {}.".format(build_access_id, seq))
    r = c.fetchone()

    return ImageRender.page_img(r['build_page_id'], fit_width, fit_height, fit_type)

def page_img_build_id(build_id, seq, fit_width, fit_height, fit_type):
    build_id = int(build_id)
    seq = int(seq)

    c = get_cursor()

    c.execute("""
        select bp.build_page_id
        from (build as b, build_page as bp)
        where
            b.build_id = %s and
            bp.build_id = b.build_id and
            bp.seq = %s""",
        (build_id, seq)
    )

    if c.rowcount == 0:
        raise DbKeyInvalid("Build page not found by build_id/seq.")
    if c.rowcount > 1:
        raise DbError("Multiple build pages found by build_id/seq.")
    r = c.fetchone()

    return ImageRender.page_img(r['build_page_id'], fit_width, fit_height, fit_type)

def page_text_img(build_id, seq, fit_width, fit_height, fit_type):
    """Raises DbKeyInvalid on invalid database key, or DbError on
       inconsistent database."""

    build_id = int(build_id)
    seq = int(seq)

    c = get_cursor()

    c.execute("""
        select bp.build_page_id
        from (build as b, build_page as bp)
        where
            b.build_id = %s and
            bp.build_id = b.build_id and
            bp.seq = %s""",
        (build_id, seq)
    )

    if c.rowcount == 0:
        raise DbKeyInvalid("Build page not found by build_id/seq.")
    if c.rowcount > 1:
        raise DbError("Multiple build pages found by build_id/seq.")
    r = c.fetchone()

    return ImageRender.page_text_img(r['build_page_id'], fit_width, fit_height, fit_type)

@staticmethod
def access_id_to_build_id(build_access_id):
    """Get a build.build_id from a build.access_id."""

    build_access_id = re.sub('[^a-z0-9_-]', '', build_access_id)

    c = get_cursor()

    c.execute("""
        select build.build_id
        from build
        where
            build.access_id = %s
	limit 1""",
        (build_access_id,)
    )

    if c.rowcount == 0:
        raise DbKeyInvalid("Build not found for build_access_id.")
    if c.rowcount > 1:
        raise DbError("Multiple builds found by build_access_id")
    r = c.fetchone()

    return r['build_id']

def get_page_count(build_access_id):
    """ Get a count of the number of build pages for a given build.access_id.
        We are depending on the results of this call being the largest
        build_page.seq for a given build.  build_page.seq always starts with 1."""

    build_access_id = re.sub('[^a-z0-9_-]', '', build_access_id)

    c = get_cursor()

    c.execute("""
        select count(build_page.build_page_id) as page_count
        from build, build_page
        where build.access_id = %s
        and build.build_id = build_page.build_id""",
        (build_access_id,)
    )

    r =  c.fetchone()
    return r['page_count']
