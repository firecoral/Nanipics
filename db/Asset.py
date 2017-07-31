# $Header: //depot/cs/db/Asset.py#1 $

import errno, hashlib, re, MySQLdb
from   os import environ, makedirs, urandom

import db.Db as Db
from   db.Db import get_cursor
from   db.Exceptions import DbKeyInvalid
import db.ImageSet as ImageSet
import db.Product as Product

def get_asset(afile):
    """Raises DbKeyInvalid on invalid database key."""

    afile = re.sub('[^A-Za-z0-9\.]', '', afile)
    c = get_cursor()
    c.execute("""
        select *
        from asset
        where afile = %s""",
        (afile,)
    )
    if (c.rowcount == 0):
        raise DbKeyInvalid("asset not found by afile: {}.".format(afile))
    # no check for > 1; assuming unique
    row = c.fetchone()
    return row

def insert_asset(
    data,
    name = None,
    keep_forever = 0,   # 0 or 1
    referrers = None,   # CSV string
    extension = None,   # include initial '.'
    mime_type = None):
    """Insert a new asset, from data and some options."""

    c = get_cursor()

    asset_id = None
    while True:
        try:
            asset_id = ''
            src = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            src_len = len(src)
            for n in range(16):
                asset_id = asset_id + src[ord(urandom(1)) % src_len]
            afile = asset_id
            if extension != None:
                afile = afile+extension
            c.execute("""
                insert into asset
                (afile, name, upload_date, keep_forever,
                 referrers, mime_type, file_size, md5sum)
                values (%s, %s, now(), %s, %s, %s, %s, %s)""",
                (afile, name, keep_forever,
                 referrers, mime_type, len(data),
                 hashlib.md5(data).hexdigest())
            )
            break
        except MySQLdb.IntegrityError:
            continue

    asset_dir = Db.asset_path+'/'+asset_id[0]+'/'+asset_id[1]
    asset_file = asset_dir+'/'+afile

    # mkdir -p
    try:
        makedirs(asset_dir)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise

    asset = open(asset_file, 'w')
    asset.write(data)
    asset.close

    return afile

def assetize_image(name, referrers, filename=None, imdata=None, extension=None):
    """Assetize a JPEG or PNG.  Either a filename must be provided, or the image data
       and an extension ('.jpg' or '.png' only).  MIME type is determined from the
       extension (from the filename if necessary)."""

    if imdata == None or extension == None:
        imfile = open(filename, 'r')
        imdata = imfile.read()
        imfile.close()

        if re.match('.*\.jpg$', filename, flags = re.I): extension = '.jpg'
        elif re.match('.*\.jpeg$', filename, flags = re.I): extension = '.jpg'
        elif re.match('.*\.png$', filename, flags = re.I): extension = '.png'

    if extension.lower() == '.jpg': mime_type = 'image/jpeg'
    elif extension.lower() == '.png': mime_type = 'image/png'
    else: raise Exception("Extension should be .jpg, .jpeg, or .png.")

    afile = insert_asset(
        imdata,
        name=name,
        referrers=referrers,
        extension=extension,
        mime_type=mime_type
    )

    return afile

def replace_asset(old_afile, data):
    """Replace an existing asset.  asset.name, .keep_forever, .referrers, and
       .mime_type are copied from the old asset in most cases.  No checking is
       done to make sure that the old and new assets are of the same type (e.g.,
       jpeg or png).

       Smaller images are automatically generated for certain image assets, as
       determined by referrer."""

    try:
        old_asset = get_asset(old_afile)
    except DbKeyInvalid:
        return {'Error': 'no asset found by name "{}".'.format(old_afile), 'old_afile': old_afile}
    dot_comps = old_afile.split('.')
    extension = '.'+dot_comps[-1] if len(dot_comps) > 1 else None
    new_afile = insert_asset(
        data,
        name=old_asset['name'],
        keep_forever=old_asset['keep_forever'],
        referrers=old_asset['referrers'],
        extension=extension,
        mime_type=old_asset['mime_type']
    )
    rv = {'old_afile': old_afile, 'new_afile': new_afile, 'repointed': 'none'}
    if old_asset['referrers'] == None: return rv

    repointed = []
    c = get_cursor()
    for referrer in old_asset['referrers'].split(','):
        table, column = referrer.split('.')

        if table == 'design_page_layout' and column == 'base_overlay_afile':
            # XXX - I believe this is doable if I inspect the appropriate product_page,
            # but it's probably not worth the time at the moment.
            return {'Error': 'design_page_layout.base_overlay_afile requires special handling.  Talk to Brian.', 'old_afile': old_afile}
        if table == 'design_page_layout' and column in set(['s800_overlay_afile', 's200_overlay_afile']):
            return {'Error': 'design_page_layout.{} should not be replaced directly.  Replace design_page_layout.base_overlay_afile instead (currently disabled), or talk to Brian.'.format(column), 'old_afile': old_afile}

        if table == 'image' and column in set(['l800_col_afile', 'l800_baw_afile', 'l800_sep_afile', 's200_col_afile', 's200_baw_afile', 's200_sep_afile']):
            return {'Error': 'image.{} should not be replaced directly.  Replace image.full_col_afile instead, or talk to Brian.'.format(column), 'old_afile': old_afile}

        if table == 'product_design_detail_image' and column in set(['b480x430_afile', 'b96x96_afile']):
            return {'Error': 'product_design_detail_image.{} should not be replaced directly.  Replace product_design_detail_image.base_afile instead, or talk to Brian.'.format(column), 'old_afile': old_afile}

        c.execute("""
            select count(*) as c
            from {}
            where {} = %s""".format(table, column),
            (old_asset['afile'],)
        )
        rc = c.fetchone()['c']
        if rc == 0: continue

        # special-handling columns

        if table == 'image' and column == 'full_col_afile':
            new_vals = {}
            new_vals.update(ImageSet.assetize_image(data, name=old_asset['name']))
            # Assuming that replacements will generally by right-side-up, until proven otherwise.
            new_vals.update(ImageSet.assetize_ecom_images(image_data=data, name=old_asset['name']))
            c.execute("""
                update image set
                    full_width = %s, full_height = %s,
                    full_col_afile = %s, rotation = 0,
                    l800_col_afile = %s, l800_baw_afile = %s, l800_sep_afile = %s,
                    s200_col_afile = %s, s200_baw_afile = %s, s200_sep_afile = %s
                where full_col_afile = %s""",
                (new_vals['full_width'], new_vals['full_height'], new_vals['full_col_afile'],
                 new_vals['l800_col_afile'], new_vals['l800_baw_afile'], new_vals['l800_sep_afile'],
                 new_vals['s200_col_afile'], new_vals['s200_baw_afile'], new_vals['s200_sep_afile'],
                 old_asset['afile'])
            )
            repointed.append('{}.{}: {} row{}'.format(table, column, rc, '' if rc == 1 else 's'))
        elif table == 'product_design_detail_image' and column == 'base_afile':
            afiles = Product.assetize_detail_images(imdata=data)
            c.execute("""
                update product_design_detail_image
                set base_afile = %s, b480x430_afile = %s, b96x96_afile = %s
                where base_afile = %s""",
                (afiles[0], afiles[1], afiles[2], old_asset['afile'])
            )
            repointed.append('{}.{}: {} row{}'.format(table, column, rc, '' if rc == 1 else 's'))

        # all other columns

        else:
            c.execute("""
                update {}
                set {} = %s
                where {} = %s""".format(table, column, column),
                (new_afile, old_asset['afile'])
            )
            repointed.append('{}.{}: {} row{}'.format(table, column, rc, '' if rc == 1 else 's'))

    if len(repointed) > 0: rv['repointed'] = '; '.join(repointed)
    return rv

