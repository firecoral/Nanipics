(function($) {
  // Image editor - displays an image and allows changes.
  //
  // This is mostly a bimage editor, although rotation is an image-based operation.

  $.widget('dp.imageeditor', {
    options: {
      islot: undefined,
      image: undefined
    },
    _init: function() {
      var $self = this;
      this.element.on('click', '.ie_tint', function() {
	$self._tint($(this).data('tint_id'));
	$self._update_controls();
	$self.draw();
      });
      this.element.on('click', '.ie_rotate', function() {
	var bimage = $self.options.islot.bimage;
	DPAjax(
	  '/e/ajax_image', {
	    command: 'image_rotate',
	    image_access_id: bimage.access_id,
	    rotation: $(this).data('rotation')
	  },
	  function(image) {
	    // The image editor is grouped with the page builder, so let the page builder
	    // update our islot (and its bimage) and tell us to redraw.  Otherwise we'd
	    // have to use the build manager ourselves, and that seems a little serious
	    // for a piddly one-image-based widget.
	    $self.element.trigger('rotated', image);
	  }
	);
      });
      this.element.on('click', '#ie_close', function() {
	$self.options.islot = undefined;
	$self.element.hide();
	$self.element.trigger('dismissed');
      });
    },
    set_islot: function(islot) {
      this.options.islot = islot;
      this._update_controls();
    },
    set_image: function(image) {
      this.options.image = image;
    },
    draw: function() {
      var $self = this;
      var islot = $self.options.islot;
      var bimage = islot.bimage;
      var iw = (bimage.x1 - bimage.x0);
      var ih = (bimage.y1 - bimage.y0);
      var iar = iw / ih;
      // hardcoding for now
      var bw = 360;
      var bh = 300;
      var bar = bw / bh;
      var w, h, l, t;
      if (iar > bar) {
	w = bw;
	h = bw / iar;
	l = 0;
	t = .5 * (bh - h);
      }
      else {
	w = bh * iar;
	h = bh;
	l = .5 * (bw - w);
	t = 0;
      }
      w = Math.round(w);
      h = Math.round(h);
      l = Math.round(l);
      t = Math.round(t);
      var image_col = {1: 'col_afile', 2: 'baw_afile', 3: 'sep_afile'}[bimage.tint_id];
      $self.element.html($('#image_edit_tmpl').render({
	bimage_afile: this.options.image[image_col],
	img_place: { width: w+'px', height: h+'px', left: l+'px', top: t+'px' }
      }));
      var image = $self.options.image;
      var cx0 = image.width  * (islot.x0 - bimage.x0) / (bimage.x1 - bimage.x0);
      var cy0 = image.height * (islot.y0 - bimage.y0) / (bimage.y1 - bimage.y0);
      var cx1 = image.width  * (islot.x1 - bimage.x0) / (bimage.x1 - bimage.x0);
      var cy1 = image.height * (islot.y1 - bimage.y0) / (bimage.y1 - bimage.y0);
      var sar = (islot.x1 - islot.x0) / (islot.y1 - islot.y0);
      $('#ie_img').Jcrop(
        {
	  aspectRatio: sar,
	  boxWidth: w,
	  boxHeight: h,
	  createHandles: ['nw', 'ne', 'se', 'sw'],
	  createDragbars: [],
	  onSelect: function(e) {
	    bimage.x0 = islot.x0 - e.x * (islot.x1 - islot.x0) / (e.x2 - e.x);
	    bimage.y0 = islot.y0 - e.y * (islot.y1 - islot.y0) / (e.y2 - e.y);
	    bimage.x1 = islot.x1 + (image.width  - e.x2) * (islot.x1 - islot.x0) / (e.x2 - e.x);
	    bimage.y1 = islot.y1 + (image.height - e.y2) * (islot.y1 - islot.y0) / (e.y2 - e.y);
	    $self.element.trigger('updated', islot);
	  },
	  setSelect: [Math.round(cx0), Math.round(cy0), Math.round(cx1), Math.round(cy1)]
	}
      );
      this._update_controls();
    },
    show: function() {
      this.element.show();
    },
    _update_controls: function() {
      var bimage = this.options.islot.bimage;
      var selector = {1: '#ie_col', 2: '#ie_baw', 3: '#ie_sep'}[bimage.tint_id];
      this._unselect('.ie_tint');
      this._select(selector);
    },
    _select: function(selector) {
      this.element.find(selector).removeClass('ie_elem_unselected');
      this.element.find(selector).addClass('ie_elem_selected');
    },
    _unselect: function(selector) {
      this.element.find(selector).removeClass('ie_elem_selected');
      this.element.find(selector).addClass('ie_elem_unselected');
    },
    _tint: function(tint_id) {
      var bimage = this.options.islot.bimage;
      bimage.tint_id = tint_id;
      bimage.tint = {1: 'col', 2: 'baw', 3: 'sep'}[bimage.tint_id];
    }
  });
})(jQuery);
