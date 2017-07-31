(function($) {
  // Image selector - displays draggable image thumbnails, and allows uploads.
  //
  // Serves as the final backing store for image objects.

  $.widget('dp.imageselector', {
    options: {
    },
    _init: function() {
    },
    // Called when an image has been rotated.
    handle_updated_image: function() {
      this.draw();
    },
    draw: function() {
      var self = this;
      var images = $(document).ImageManage.images();
      $(self.element).html($('#image_select_tmpl').render(
	{ images: images },
	{ bimage_afile: function(bimage) { return self.bimage_afile(bimage); } }
      ));
      // Sadly, this is required to keep the images in a single scrollable row.
      // Google "css horizontal image scroller" (no quotes) to confirm.  There
      // are pure-CSS solutions, but they are CSS3ish and don't work on IE <= 8.
      //
      // 130 is the width of the .im_img container, and 10 is because I distrust
      // browsers.  (Note, one can derive 130 by inspecting the CSS rules, but
      // it's hideous.)
      $('#is_img_dynamic').width(10 + images.length * 130);
      $('.is_img').draggable({ helper: 'clone' });

      $('#is_imgupload').fileuploader({
        title: "Upload Photos",
        url: '/e/ajax_image',
        message: 'Upload photos from your computer.<br /><br />',
        done: function (u1, u2, image) {
	  var num_images = $(document).ImageManage.images().length;
	  $(document).ImageManage.add_image(image);
          self.draw();
          self.element.trigger('imageuploaded', num_images);
        }
      });
    },
    bimage_afile: function(bimage) {
      var image_col = {1: 'col_afile', 2: 'baw_afile', 3: 'sep_afile'}[bimage.tint_id];
      var image = $(document).ImageManage.image_by_access_id(bimage.access_id);
      return image[image_col];
    }
  });
})(jQuery);
