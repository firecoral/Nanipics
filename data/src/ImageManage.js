(function($) {
  var images = [];
  var images_by_access_id = {};
  var image_size;

  $.fn.ImageManage = function(opts) {
    images = opts.images;
    image_size = opts.image_size;
    $.each(images, function(u1, image) {
      _add_dims(image);
      images_by_access_id[image.access_id] = image;
    });
  };

  $.fn.ImageManage.images = function() {
    return images;
  };

  $.fn.ImageManage.image_by_access_id = function(access_id) {
    return images_by_access_id[access_id];
  };

  $.fn.ImageManage.add_image = function(image) {
    _add_dims(image);
    images.push(image);
    images_by_access_id[image.access_id] = image;
  };

  $.fn.ImageManage.update_image = function(new_image) {
    var image = images_by_access_id[new_image.access_id];
    // Since images_by_access_id contains references, these update images[#] as well.
    // (This is a feature.)  Hence we update the individual attributes.
    image.ar        = new_image.ar;
    image.is_afile  = new_image.is_afile;
    image.col_afile = new_image.col_afile;
    image.baw_afile = new_image.baw_afile;
    image.sep_afile = new_image.sep_afile;
    _add_dims(image);
  };

  function _add_dims(image) {
    if (image.ar >= 1) {
      image.width = image_size;
      image.height = Math.round(.5 + image_size / image.ar);
    }
    else {
      image.height = image_size;
      image.width = Math.round(.5 + image_size * image.ar);
    }
  }
})(jQuery);

