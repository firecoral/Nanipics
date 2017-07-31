(function($) {
  var build = {};
  var pages_by_seq = {};
  var images_by_seqs = {};
  var texts_by_seqs = {};

  $.fn.BuildManage = function(opts) {
    build = opts.build;
  };

  $.fn.BuildManage.build = function() {
    return build;
  };

  $.fn.BuildManage.page_by_seq = function(seq) {
    return pages_by_seq[seq];
  };

  $.fn.BuildManage.image_by_seqs = function(page_seq, image_seq) {
    return images_by_seqs[page_seq][image_seq];
  };

  $.fn.BuildManage.images_by_seqs = function() {
    return images_by_seqs;
  };

  $.fn.BuildManage.text_by_seqs = function(page_seq, text_seq) {
    return texts_by_seqs[page_seq][text_seq];
  };

  $.fn.BuildManage.clear_pages = function(design) {
    _init_pages(design, false);
  };

  $.fn.BuildManage.add_empty_pages = function(design) {
    _init_pages(design, true);
  };

  $.fn.BuildManage.init_page = function(seq, design_page_layout) {
    page = pages_by_seq[seq];

    page.dpl_id = design_page_layout.dpl_id;
    page.page_width = design_page_layout.page_width;
    page.page_height = design_page_layout.page_height;
    page.images = [];
    page.texts = [];
    for (var i = 0; i < design_page_layout.islots.length; i++) {
      var islot = design_page_layout.islots[i];
      page.images.push({
	dis_id: islot.dis_id,
	seq: islot.seq,
	tint_id: 1,
	x0: null,
	x1: null,
	y0: null,
	y1: null,
	access_id: null
      });
      var image = page.images[page.images.length - 1];
      if (images_by_seqs[page.seq] == undefined) images_by_seqs[page.seq] = {};
      images_by_seqs[page.seq][image.seq] = image;
    }
    for (var i = 0; i < design_page_layout.tslots.length; i++) {
      var tslot = design_page_layout.tslots[i];
      page.texts.push({
	dts_id: tslot.dts_id,
	seq: tslot.seq,
	placeholder: tslot.ph,
	content: tslot.ic == null ? '' : tslot.ic,
	font_id: tslot.fonts[0]['font_id'],
	fontsize_id: tslot.fontsizes[0]['fontsize_id'],
	gravity_id: tslot.gravities[0]['gravity_id'],
	color: tslot.color
      });
      var text = page.texts[page.texts.length - 1];
      if (texts_by_seqs[page.seq] == undefined) texts_by_seqs[page.seq] = {};
      texts_by_seqs[page.seq][text.seq] = text;
    }
  };

  function _init_pages(design, empty_only) {
    $.each(design.pages, function(i, design_page) {
      var page = build.pages[i];
      if (page != null && empty_only) {
	pages_by_seq[page.seq] = page;
	images_by_seqs[design_page.seq] = {};
	$.each(page.images, function(j, image) {
	  images_by_seqs[design_page.seq][image.seq] = image;
	});
	texts_by_seqs[design_page.seq] = {};
	$.each(page.texts, function(j, text) {
	  texts_by_seqs[design_page.seq][text.seq] = text;
	});
	return;
      }
      page = {
	dpl_id: null,
	seq: design_page.seq,
	page_width: null,
	page_height: null,
	images: [],
	texts: []
      };
      build.pages[i] = page;
      pages_by_seq[page.seq] = page;
      images_by_seqs[design_page.seq] = {};
      texts_by_seqs[design_page.seq] = {};
    });
  }

  $.fn.BuildManage.set_product_design_id = function(pd_id) {
    build.pd_id = pd_id;
  };

  // Update the build in the database - either a single page (page_seq designates it)
  // or the whole build (page_seq is undefined) - and call a function on success.
  $.fn.BuildManage.update_db = function(page_seq, success_func) {
    var up_build;
    if (page_seq == undefined) {
      up_build = build;
    }
    else {
      up_build = {
	'build_access_id': build.build_access_id,
	'pd_id': build.pd_id,
	'pages': [ pages_by_seq[page_seq] ]
      };
    }

    DPAjax(
      '/e/ajax_session', {
	command: 'update_build',
	build: up_build
      },
      success_func
    );
  };

  $.fn.BuildManage.reset_image = function(image, islot, access_id, ar, reset_tint) {
    image.access_id = access_id;
    var sar = (islot.x1 - islot.x0) / (islot.y1 - islot.y0);
    if (ar > sar) {
      image.y0 = islot.y0;
      image.y1 = islot.y1;
      var w = ar * (image.y1 - image.y0);
      image.x0 = (islot.x1 + islot.x0 - w) / 2;
      image.x1 = (islot.x1 + islot.x0 + w) / 2;
    }
    else {
      image.x0 = islot.x0;
      image.x1 = islot.x1;
      var h = (image.x1 - image.x0) / ar;
      image.y0 = (islot.y1 + islot.y0 - h) / 2;
      image.y1 = (islot.y1 + islot.y0 + h) / 2;
    }
    if (reset_tint) image.tint_id = 1;
  };
})(jQuery);

