import Image, ImageOps
import MySQLdb
import StringIO
from os import urandom

import db.Db as Db
import db.Build as Build
from   db.Db import get_cursor
from   p.Utility import new_access_id

def image_set_full(image_set_id):
    """Returns a fully-populated image_set object.  See spec at XXX."""

    c = get_cursor()

    image_set_id = int(image_set_id)

    c.execute("""
        select *
        from image_set
        where image_set_id = %s""",
        (image_set_id,)
    )
    image_set = c.fetchone()

    c.execute("""
        select *
        from image
        where image_set_id = %s
        order by image_id""",
        (image_set_id,)
    )
    image_set['images'] = c.fetchall()

    return image_set

def image_set_ecom(image_set_id):
    """Get an ecom-friendly image-set structure.  See spec at XXX."""
    c = get_cursor()

    image_set_id = int(image_set_id)
    image_set = { }
    c.execute("""
        select *
        from image
        where image_set_id = %s
        order by image_id""",
        (image_set_id,)
    )
    i_rows = c.fetchall()

    image_set['images'] = []
    for i_row in i_rows:
        if i_row['rotation'] % 180 == 90:
            ar = float(i_row['full_height']) / i_row['full_width']
        else:
            ar = float(i_row['full_width']) / i_row['full_height']
        image_set['images'].append({
            'ar': ar,
            'access_id': i_row['access_id'],
            'is_afile' : i_row['s200_col_afile'],
            'col_afile': i_row['l800_col_afile'],
            'baw_afile': i_row['l800_baw_afile'],
            'sep_afile': i_row['l800_sep_afile']
        })
    return image_set

def clone(image_set_id):
    """Clones an image_set, including subordinate rows, and returns its image_set_id.
       All non-primary-key fields will be unchanged, except image.access_id."""

    c = get_cursor()

    image_set = image_set_full(image_set_id)
    fields = []
    values = []
    # Rather than specifying fields and breaking this whenever we change one of the
    # tables, I iterate through the fields and handle certain ones specially.
    for field in image_set:
        if field == 'images': continue
        if field == 'image_set_id': continue
        fields.append(field)
        values.append(image_set[field])
    c.execute("""
        insert into image_set
        ({})
        values
        ({})""".format(
            ', '.join(fields),
            ', '.join('%s' for value in values)
        ),
        tuple(values)
    )
    image_set_id = c.lastrowid

    for image in image_set['images']:
        fields = []
        values = []
        for field in image:
            if field == 'image_id': continue
            if field == 'image_set_id': continue
            if field == 'access_id': continue
            fields.append(field)
            values.append(image[field])
        fields.append('image_set_id')
        values.append(image_set_id)
        while True:
            try:
                access_id = new_access_id(24)
                c.execute("""
                    insert into image
                    ({})
                    values
                    ({})""".format(
                        ', '.join(['access_id'] + fields),
                        ', '.join(['%s'] + list('%s' for value in values))
                    ),
                    tuple([access_id] + values)
                )
                break
            except MySQLdb.IntegrityError:
                continue

    return image_set_id

def add_image(image_set_id, image_data, name=None):
    c = get_cursor()

    image_row = {
        'image_set_id': image_set_id
    }

    image_row.update(assetize_image(image_data, name=name))
    image_row.update(assetize_ecom_images(image_data=image_data, name=name))

    while True:
        try:
            image_row['access_id'] = new_access_id(24)
            c.execute("""
                insert into image
                (full_width, full_height, image_set_id, access_id,
                 full_col_afile,
                 l800_col_afile, l800_baw_afile, l800_sep_afile,
                 s200_col_afile, s200_baw_afile, s200_sep_afile)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (image_row['full_width'], image_row['full_height'],
                 image_row['image_set_id'], image_row['access_id'],
                 image_row['full_col_afile'],
                 image_row['l800_col_afile'], image_row['l800_baw_afile'], image_row['l800_sep_afile'],
                 image_row['s200_col_afile'], image_row['s200_baw_afile'], image_row['s200_sep_afile'])
            )
            image_row['image_id'] = c.lastrowid
            break
        except MySQLdb.IntegrityError:
            continue

    return image_row

def assetize_image(image_data, name=None):
    """Create an asset for the full (color) customer image, and return the afile and dimensions.

       The provided image data is assumed to describe a JPEG, with no error checking made."""

    rv = {}
    full_image = Image.open(StringIO.StringIO(image_data))
    # XXX - throw exception if not JPEG
    # XXX - throw exception if has poison-null byte
    rv['full_width'], rv['full_height'] = full_image.size

    import db.Asset as Asset
    rv['full_col_afile'] = Asset.insert_asset(
        image_data,
        name=name,
        referrers = 'image.full_col_afile',
        extension = '.jpg',
        mime_type = 'image/jpeg'
    )

    return rv

def assetize_ecom_images(image_data=None, afile=None, rotation=0, name=None):
    """Create assets for the smaller color, black-and-white, and sepia images, and return the afiles
       and full_col_afile dimensions.  The ecom images will be rotated if requested; rotation is
       relative to the full_col_afile.

       The provided image data or afile is assumed to describe a JPEG, with no error checking made."""

    rv = {'rotation': rotation}

    if image_data != None:
        full_image = Image.open(StringIO.StringIO(image_data))
        if name == None: name = 'Consumer image'
    else:
        full_image = Image.open("{}/{}/{}/{}".format(Db.asset_path, afile[0], afile[1], afile))
        if name == None: name = 'Consumer image, afile '+afile

    # XXX - throw exception if not JPEG
    # XXX - throw exception if has poison-null byte
    if rotation != 0: full_image = full_image.rotate(rotation)
    fw, fh = full_image.size
    rv['full_width'], rv['full_height'] = fw, fh

    # Scaling should be more expensive than tinting a small image,
    # so scale before tinting.
    if fw >= fh:
        l800_image = full_image.resize((800, int(.5 + 800. * fh / fw)), Image.ANTIALIAS)
        s200_image = full_image.resize((int(.5 + 200. * fw / fh), 200), Image.ANTIALIAS)
    else:
        l800_image = full_image.resize((int(.5 + 800. * fw / fh), 800), Image.ANTIALIAS)
        s200_image = full_image.resize((200, int(.5 + 200. * fh / fw)), Image.ANTIALIAS)

    import db.Asset as Asset
    image_sio = StringIO.StringIO()
    l800_image.save(image_sio, 'jpeg', quality=100)
    rv['l800_col_afile'] = Asset.insert_asset(
        image_sio.getvalue(),
        name = name+', 800px',
        referrers = 'image.l800_col_afile',
        extension = '.jpg',
        mime_type = 'image/jpeg'
    )

    image_sio = StringIO.StringIO()
    l800_image = ImageOps.grayscale(l800_image)
    l800_image.save(image_sio, 'jpeg', quality=100)
    rv['l800_baw_afile'] = Asset.insert_asset(
        image_sio.getvalue(),
        name = name+', 800px, b/w',
        referrers = 'image.l800_baw_afile',
        extension = '.jpg',
        mime_type = 'image/jpeg'
    )

    image_sio = StringIO.StringIO()
    l800_image = ImageOps.colorize(l800_image, 'rgb(0%,0%,0%)', 'rgb(100%,95%,80%)')
    l800_image.save(image_sio, 'jpeg', quality=100)
    rv['l800_sep_afile'] = Asset.insert_asset(
        image_sio.getvalue(),
        name = name+', 800px, sepia',
        referrers = 'image.l800_sep_afile',
        extension = '.jpg',
        mime_type = 'image/jpeg'
    )

    image_sio = StringIO.StringIO()
    s200_image.save(image_sio, 'jpeg', quality=100)
    rv['s200_col_afile'] = Asset.insert_asset(
        image_sio.getvalue(),
        name = name+', 200px',
        referrers = 'image.s200_col_afile',
        extension = '.jpg',
        mime_type = 'image/jpeg'
    )

    image_sio = StringIO.StringIO()
    s200_image = ImageOps.grayscale(s200_image)
    s200_image.save(image_sio, 'jpeg', quality=100)
    rv['s200_baw_afile'] = Asset.insert_asset(
        image_sio.getvalue(),
        name = name+', 200px, b/w',
        referrers = 'image.s200_baw_afile',
        extension = '.jpg',
        mime_type = 'image/jpeg'
    )

    image_sio = StringIO.StringIO()
    s200_image = ImageOps.colorize(s200_image, 'rgb(0%,0%,0%)', 'rgb(100%,95%,80%)')
    s200_image.save(image_sio, 'jpeg', quality=100)
    rv['s200_sep_afile'] = Asset.insert_asset(
        image_sio.getvalue(),
        name = name+', 200px, sepia',
        referrers = 'image.s200_sep_afile',
        extension = '.jpg',
        mime_type = 'image/jpeg'
    )

    return rv

def rotate_ecom_images(image_access_id, add_rotation, check_image_set_id=None):
    """Rotate the ecom images for a consumer image, update the image, and return the
       new afiles, rotated full_col_image dimensions, and the new rotation.  (The
       full_col_image itself is unchanged.)  The add_rotation is relative to the
       current value, so calling this twice with "90" will leave the ecom images
       upside-down, and image.rotation at (<old image.rotation> + 180) % 360.

       This also resets the cropping for all build-images containing this image to
       the initial, fully-zoomed-out, state.

       If check_image_set_id is supplied, assert that the image belongs to that image_set
       before proceeding."""

    c = get_cursor()

    if check_image_set_id == None:
        image_set_id_clause = "isnull(%s)"
    else:
        image_set_id_clause = "image_set_id = %s"

    c.execute("""
        select image_id, full_col_afile, rotation
        from image
        where
            access_id = %s and
            {}""".format(image_set_id_clause),
        (image_access_id, check_image_set_id)
    )
    assert c.rowcount == 1, "Row-count {} for access_id {}, image_set_id {}".format(c.rowcount, image_access_id, check_image_set_id)
    ir = c.fetchone()

    # "% 360" works for negatives as well: (90 - 360 * 3) % 360 == 90.
    new_vals = {
      'rotation': (ir['rotation'] + add_rotation) % 360,
      'access_id': image_access_id
    }
    new_vals.update(assetize_ecom_images(afile=ir['full_col_afile'], rotation=new_vals['rotation']))

    c.execute("""
        update image set
            rotation = %s,
            l800_col_afile = %s, l800_baw_afile = %s, l800_sep_afile = %s,
            s200_col_afile = %s, s200_baw_afile = %s, s200_sep_afile = %s
        where image_id = %s""",
        (new_vals['rotation'],
         new_vals['l800_col_afile'], new_vals['l800_baw_afile'], new_vals['l800_sep_afile'],
         new_vals['s200_col_afile'], new_vals['s200_baw_afile'], new_vals['s200_sep_afile'],
         ir['image_id'])
    )

    Build.reset_images(image_access_id)

    return new_vals

def set_replace_image(image_id, replace_image_id):
    """Sets the replace_image_id field for this image to the new image_id."""

    c = get_cursor()
    c.execute("""
        update image
        set image.replace_image_id = %s
        where image_id = %s""",
        (replace_image_id, image_id)
    )
