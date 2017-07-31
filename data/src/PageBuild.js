// dp.pagebuilder - a widget that draws a consumer page (a design_page_layout,
// with a build_page applied to it), and handles all events on it.
//
// It also instantiates dp.imageeditor and dp.texteditor widgets,
// and drives them as needed.

(function($) {
  $.widget('dp.pagebuilder', {
    options: {
      design_page: undefined,
      design_page_layout: undefined,
      // copies of the current design_page_layout's islots, with bimages attached.
      islots: [],
      islot_by_seq: {},
      // copies of the current design_page_layout's tslots, with btexts attached.
      tslots: []
    },
    _init: function() {
      $('#ie_popup').imageeditor();
      $('#ie_popup').draggable();

      $('#te_popup').texteditor();
      $('#te_popup').draggable({handle: '.te_h1'});

      var self = this;
      $(document).on('click', '.pb_iuitarg_full', function() {
	var islots = self.options.islots;
	for (var i = 0; i < islots.length; i++) {
	  if (islots[i].seq == $(this).data('seq')) {
	    $('#ie_popup').imageeditor('set_islot', islots[i]);
	    var access_id = islots[i].bimage.access_id;
	    $('#ie_popup').imageeditor('set_image', $(document).ImageManage.image_by_access_id(access_id));
	    break;
	  }
	}
	$('#ie_popup').imageeditor('draw');
	$('#ie_popup').imageeditor('show');
      });

      $(document).on('updated', '#ie_popup', function(u1, islot) {
	self.draw_islot(islot);
      });
      $(document).on('rotated', '#ie_popup', function(u1, image) {
	$(document).ImageManage.update_image(image);
	// get the updated image (not guaranteed to be identical to what we passed)
	image = $(document).ImageManage.image_by_access_id(image.access_id);

	$.each(self.options.islots, function(u1, islot) {
	  if (islot.bimage.access_id != image.access_id) return;
	  $(document).BuildManage.reset_image(islot.bimage, islot, image.access_id, image.ar, false);
	  self.draw_islot(islot);
	});

	$('#ie_popup').imageeditor('set_image', image);
	$('#ie_popup').imageeditor('draw');
	self.element.trigger('image_updated', image);
      });

      $(document).on('textselected', '#te_popup', function(u1, tslot) {
	self.update_tuitargs(tslot);
      });
      $(document).on('textunselected', '#te_popup', function(u1, text_changed) {
	self.update_tuitargs(undefined);   // clear all tuitarg borders
	if (text_changed) {
	  $(document).BuildManage.update_db(
	    self.options.design_page.seq,
	    function() { self.draw(); }
	  );
	}
      });
      $(document).on('fontchanged fontsizechanged gravitychanged', '#te_popup', function() {
	$(document).BuildManage.update_db(
	  self.options.design_page.seq,
	  function() { self.update_overlay(); }
	);
      });
    },

    select_design_page_layout: function(page_layout) {
      for (var i = 0; i < page_layout.dpls.length; i++) {
	if (page_layout.dpls[i].pp_id == this.options.design_page.pp_id) {
	  this.options.design_page_layout = page_layout.dpls[i];
	  break;
	}
      }

      var build_page = $(document).BuildManage.page_by_seq(this.options.design_page.seq);
      if (build_page.dpl_id == null || build_page.dpl_id != this.options.design_page_layout.dpl_id) {
	$(document).BuildManage.init_page(this.options.design_page.seq, this.options.design_page_layout);
	this.element.trigger('build_page_updated', build_page);
      }

      // (re-)set the local islots and tslots.
      this.options.islots = [];
      var islots = this.options.design_page_layout.islots;
      for (var i = 0; i < islots.length; i++) {
	var islot = $.extend({}, islots[i]);
	islot.bimage = $(document).BuildManage.image_by_seqs(this.options.design_page.seq, islot.seq);
	this.options.islots.push(islot);
	this.options.islot_by_seq[islot.seq] = islot;
      }
      // (re-)set the local tslots, as well as the text editor's.
      this.options.tslots = [];
      var tslots = this.options.design_page_layout.tslots;
      for (var i = 0; i < tslots.length; i++) {
	var tslot = $.extend({}, tslots[i]);
	tslot.btext = $(document).BuildManage.text_by_seqs(this.options.design_page.seq, tslot.seq);
	this.options.tslots.push(tslot);
      }
      $('#te_popup').texteditor('set_tslots', this.options.tslots);

      this.draw();
      $('#te_popup').texteditor('set_ttype', this.options.design_page_layout.ttype);
    },
    handle_updated_image: function(event_elem) {
      if (event_elem != this.element.get(0)) {
        this.draw();
      }
    },
    set_design_page: function(design_page) {
      this.options.design_page = design_page;
    },
    update_tuitargs: function(cur_tslot) {
      $(this.element).find('.pb_tuitarg').removeClass('pb_tuitarg_current');
      if (cur_tslot != undefined) {
	$(this.element).find('.pb_tuitarg[data-seq='+cur_tslot.seq+']').addClass('pb_tuitarg_current');
      }
    },
    design_page: function() {
      return this.options.design_page;
    },
    update_overlay: function() {
      var build_page = $(document).BuildManage.page_by_seq(this.options.design_page.seq);
      if (build_page.dpl_id != null) {
	var build_access_id = $(document).BuildManage.build().access_id;
        var text_key = 'b='+build_access_id+'&s='+build_page.seq+'&r='+Math.random();
        text_key += '&w='+parseInt($(this.element).width());
        text_key += '&h='+parseInt($(this.element).height());
        $('#pb_text_overlay').css('background-image', "url('/e/t?"+text_key+"')");
      }
    },
    // Draw the page, from the current design_layout_page and build_page.
    //
    // Calling this cavalierly may cause dropped events in some cases.  For
    // example, say the text editor calls it when a field blurs.  If you enter
    // text in the text editor then click a slot on the page, the blur handler
    // fires before the click.  So the page redraws and your slot click is
    // lost.  Beware!  Better to update only what you need.
    draw: function() {
      var self = this;
      var design_page = self.options.design_page;
      var design_page_layout = self.options.design_page_layout;
      var build_page = $(document).BuildManage.page_by_seq(this.options.design_page.seq);

      var pw = design_page_layout.page_width;
      var ph = design_page_layout.page_height;
      $(self.element).width(pw+'px');
      $(self.element).height(ph+'px');

      var text_key;
      if (build_page.dpl_id != null) {
	var build_access_id = $(document).BuildManage.build().access_id;
        text_key = 'b='+build_access_id+'&s='+build_page.seq+'&r='+Math.random()+'&w='+pw+'&h='+ph;
      }
      var cur_tseq;
      var cur_tslot = $('#te_popup').texteditor('cur_tslot');
      if (cur_tslot != undefined) cur_tseq = cur_tslot.seq;
      $(self.element).html($('#page_build_tmpl').render(
	{
	  page_width: pw,
	  page_height: ph,
	  overlay_image: design_page_layout.overlay_image,
	  blockout_image: design_page.blockout,
	  islots: self.options.islots,
	  tslots: self.options.tslots,
	  cur_tseq: cur_tseq,
	  text_key: text_key,
          num_images: $(document).ImageManage.images().length
	},
	{
	  bimage_afile: function(bimage) { return self.bimage_afile(bimage); }
	}
      ));
      $(self.element).droppable({
	accept: '.ls_icon',
	drop: function(event, ui) {
	  self.select_design_page_layout(ui.draggable.data('layout'));
	  self.element.trigger('layout_dropped', ui.draggable.data('layout'));
	},
	hoverClass: 'pb_layout_hover'
      });
      // Handle an image dragged from the image-selector, and dropped
      // on one of our slots.
      $(self.element).find('.pb_iuitarg').droppable({
	accept: '.is_img',
	drop: function(u1, ui) {
          var build_page = $(document).BuildManage.page_by_seq(self.options.design_page.seq);
	  var islot  = self.options.islot_by_seq[$(this).data('seq')];
	  var image  = ui.draggable.data();
	  $(document).BuildManage.reset_image(islot.bimage, islot, image.access_id, image.ar, true);
	  self.element.trigger('build_page_updated', build_page);
	  self.draw();
	},
	hoverClass: 'pb_islot_hover'
      });
      // Set up the draggables on our slotted images - limit movement, and
      // pass events to them correctly.
      $('.pb_img').each(function() {
	var i = $(this).data('i');
	$(this).draggable({
	  containment: $('.pb_img_contain[data-i='+i+']'),
	  stop: function() {
            var build_page = $(document).BuildManage.page_by_seq(self.options.design_page.seq);
	    var image = build_page.images[i];
	    var islot = self.options.islots[i];
	    image.x0 = islot.x0 + parseFloat($(this).css('left'));
	    image.y0 = islot.y0 + parseFloat($(this).css('top'));
	    image.x1 = image.x0 + parseFloat($(this).css('width'));
	    image.y1 = image.y0 + parseFloat($(this).css('height'));
	  }
	});
	// Since the UI target is a div floating above the canvas, rather than
	// the image, we have to do some event trickery to make drags on the
	// UI target affect the image.
	var telem = $('.pb_iuitarg[data-i='+i+']');
	var img = this;
	$(telem).on('mousedown touchstart touchmove touchend', function(event) {
	  $(img).trigger(event);
	  self.element.trigger('imageselected', i);
	});
      });
      $(self.element).find('.pb_tuitarg').on('click', function() {
	var tslots = self.options.tslots;
	for (var i = 0; i < tslots.length; i++) {
	  if (tslots[i].seq == $(this).data('seq')) {
	    self.update_tuitargs(tslots[i]);
	    $('#te_popup').texteditor('set_cur_tslot', tslots[i]);
	  }
	}
        $('#te_popup').texteditor('draw');
        $('#te_popup').texteditor('show');
        $('#te_popup').texteditor('focus_current');
      });
      // Add on-click file uploaders to our empty slots.
      $('.pb_iuitarg_empty').fileuploader({
 	title: "Upload Images",
	url: '/e/ajax_image',
	message: 'Upload photos from your computer.<br /><br />',
	done: function (u1, u2, image) {
	  var islot  = self.options.islot_by_seq[$(this.element).data('seq')];
	  $(document).BuildManage.reset_image(islot.bimage, islot, image.access_id, image.ar, true);
          $(self.element).trigger('imageuploaded', image);
	  self.draw();
        }
      });
    },
    draw_islot: function(islot) {
      var $self = this;
      var $container = $('.pb_slot_container[data-seq='+islot.seq+']');
      $container.html($('#page_build_img_contain_tmpl').render(islot));
      $container.html($('#page_build_islot_tmpl').render(islot, {
	bimage_afile: function(bimage) { return $self.bimage_afile(bimage); }
      }));
    },
    bimage_afile: function(bimage) {
      var image_col = {1: 'col_afile', 2: 'baw_afile', 3: 'sep_afile'}[bimage.tint_id];
      var image = $(document).ImageManage.image_by_access_id(bimage.access_id);
      return image[image_col];
    }
  });
})(jQuery);

