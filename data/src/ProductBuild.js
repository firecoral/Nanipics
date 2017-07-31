// ProductBuild.js - draws and maintains a product-build page.
//
// The main function is to set up and coordinate widgets.

(function($) {
  var product;
  var designs;         // all designs in the orientation set
  var design;          // design is the current one
  var layout_groups;
  var dpls = {};       // built once from layout_groups, for convenience
  // XXX - this is a hack workaround for bug 959.
  var page_selector_updates_build = true;

  $.fn.ProductBuild = function(opts) {
    layout_groups = opts.layout_groups;
    product = opts.product;
    designs = opts.designs;

    for (var layout_group_id in layout_groups) {
      var layout_group = layout_groups[layout_group_id];
      for (var i = 0; i < layout_group.length; i++) {
	for (var j = 0; j < layout_group[i].dpls.length; j++) {
	  var dpl = layout_group[i].dpls[j];
	  dpl.pl = layout_group[i];
	  dpls[dpl.dpl_id] = dpl;
	}
      }
    }

    for (var i = 0; i < designs.length; i++) {
      if (designs[i].pd_id == $(document).BuildManage.build().pd_id) {
	designs[i].is_current = 1;
	design = designs[i];
      }
      else {
	designs[i].is_current = 0;
      }
    }

    $(document).on('changed', '#os_canvas', function(e, i) {
      design = designs[i];
      $(document).BuildManage.clear_pages(design);

      for (var j = 0; j < designs.length; j++) {
	if (designs[j].pd_id == $(document).BuildManage.build().pd_id) designs[j].is_current = 1;
	else designs[j].is_current = 0;
      }
      $(document).BuildManage.set_product_design_id(design.pd_id);
      $('.prod_title').html($('#prod_title_tmpl').render({product_name: product.name, design_name: design.ecom_name}));
      if (design.pages.length == 1) {
	$('#ips_show_ps').hide();
      }
      else {
	$('#ips_show_ps').show();
      }
      $('#ips_canvas').pageselector('set_design_pages', design.pages);
      // This triggers the 'pageselected' event, as if the consumer had clicked the first page.
      // We catch that and draw the layout selector.
      $('#ips_canvas').pageselector('set_cur_design_page_i', 0);
    });

    $(document).on('layout_clicked', '#pc_canvas', function(e, layout) {
      $('#page_build').pagebuilder('select_design_page_layout', layout);
      $('#pc_canvas').layoutselector('select_layout', layout);
    });

    $(document).on('click touchstart', '#ips_show_is', function() {
      $('#ips_canvas').imageselector('draw');
      $('#ips_show_is').addClass('ips_show_is_selected').removeClass('ips_show_is_unselected');
      var descs = product.pb_view_descs.split('/');   // [singular, plural]
      $('#ips_show_ps').addClass('ips_show_ps-'+descs[1]+'_unselected');
      $('#ips_show_ps').removeClass('ips_show_ps-'+descs[1]+'_selected');
    });
    $(document).on('click touchstart', '#ips_show_ps', function() {
      $('#ips_canvas').pageselector('draw');
      $('#ips_show_is').addClass('ips_show_is_unselected').removeClass('ips_show_is_selected');
      var descs = product.pb_view_descs.split('/');   // [singular, plural]
      $('#ips_show_ps').addClass('ips_show_ps-'+descs[1]+'_selected');
      $('#ips_show_ps').removeClass('ips_show_ps-'+descs[1]+'_unselected');
    });

    $(document).on('imageuploaded', '#ips_canvas', function(e, num_images) {
      if (num_images == 0) {
	$('#page_build').pagebuilder('draw');
      }
    });

    $(document).on('build_page_updated', '#page_build', function(build_page) {
      // XXX - this is a hack workaround for bug 959.
      if (! page_selector_updates_build) return;
      $(document).BuildManage.update_db(
	build_page.seq,
	function() { $('#page_build').pagebuilder('draw'); }
      );
    });
    $(document).on('image_updated', '.page_build', function(e, image) {
      $('#ips_canvas').imageselector('handle_updated_image');

      var bimages_by_seqs = $(document).BuildManage.images_by_seqs();
      var affected_pseqs = {};
      for (var pseq in bimages_by_seqs) {
	for (var iseq in bimages_by_seqs[pseq]) {
	  var bimage = bimages_by_seqs[pseq][iseq];
	  if (bimage.access_id != image.access_id) continue;
	  var islot = islot_by_seqs(pseq, iseq);
	  $(document).BuildManage.reset_image(bimage, islot, image.access_id, image.ar, false);
	  affected_pseqs[pseq] = 1;
	}
      }

      $('.page_build').each(function() {
	var pseq = $(this).pagebuilder('design_page').seq;
	if (pseq in affected_pseqs) {
	  $(this).pagebuilder('handle_updated_image', e.target);
	}
      });
      $(document).BuildManage.update_db(
	undefined,
	// No post-update callback; only the text overlay needs an up-to-date database
	undefined
      );
    });

    $(document).on('layout_dropped', '#page_build', function(e, layout) {
      $('#pc_canvas').layoutselector('select_layout', layout);
    });
    $(document).on('imageuploaded', '#page_build', function(e, image) {
      var num_images = $(document).ImageManage.images().length;
      $(document).ImageManage.add_image(image);
      $('#ips_canvas').imageselector('draw');
      $('#ips_show_is').addClass('ips_show_is_selected').removeClass('ips_show_is_unselected');
      var descs = product.pb_view_descs.split('/');   // [singular, plural]
      $('#ips_show_ps').addClass('ips_show_ps-'+descs[1]+'_unselected');
      $('#ips_show_ps').removeClass('ips_show_ps-'+descs[1]+'_selected');
      if (num_images == 0) {
	$('#page_build').pagebuilder('draw');
      }
    });

    $(document).on('pageselected', '#ips_canvas', function(e, design_page) {
      select_design_page(design_page);
    });

    $(document).on('click', '.pb_card_nav_l', function() {
      $('#ips_canvas').pageselector('prev');
    });
    $(document).on('click', '.pb_card_nav_r', function() {
      $('#ips_canvas').pageselector('next');
    });

    $('#submit_product').button();
    $(document).on('click', '#submit_product', function() {
      handle_submit();
    });
  };

  $.fn.ProductBuild.draw = function() {
    $(document).BuildManage.add_empty_pages(design);
    hide_layout_selector = true;
    for (var i = 0; i < design.pages.length; i++) {
      var layout_group = layout_groups[design.pages[i].layout_group_id];
      if (layout_group.length > 1) {
	hide_layout_selector = false;
	break;
      }
    }

    $('.prod_title').html($('#prod_title_tmpl').render({product_name: product.name, design_name: design.ecom_name}));

    if (designs.length > 1) {
      $('#os_canvas').orientationselector();
      $('#os_canvas').orientationselector('set_designs', designs);
      $('#os_canvas').orientationselector('draw');
    }

    $('#ips_canvas').imageselector();

    $('#page_build').pagebuilder();

    // We don't need to do anything more with the layout selector here; it gets the appropriate
    // layout group (the one that matches the build, or the first if we're starting fresh) set
    // when the first design-page is selected, below.
    $('#pc_canvas').layoutselector();
    if (hide_layout_selector) {
      $('#pc_container').hide();
      $('#pc_show_layouts').hide();
      $('#page_build_container').addClass('page_build_container_wo_layout').removeClass('page_build_container_w_layout');
    }
    else {
      $('#page_build_container').addClass('page_build_container_w_layout').removeClass('page_build_container_wo_layout');
    }

    if (design.pages.length == 1) {
      $('#ips_show_ps').hide();
    }
    else {
      $('#ips_show_ps').show();
    }

    $('#ips_canvas').pageselector();
    $('#ips_canvas').pageselector('set_design_pages', design.pages);
    // This triggers the 'pageselected' event, as if the consumer had clicked the first page.
    // We catch that and draw the layout selector.
    $('#ips_canvas').pageselector('set_cur_design_page_i', 0);

    if (design.open_pages && design.pages.length > 1) {
      $('#ips_show_ps').trigger('click');
    }
    else {
      $('#ips_show_is').trigger('click');
    }
  }

  function handle_submit() {
    var ups = [];    // unvisited pages (implicitly visit these before submitting)
    var cups = [];   // customizable unvisited pages (notify user of these)
    var pages = $(document).BuildManage.build().pages;
    for (var i = 0; i < pages.length; i++) {
      if (pages[i].dpl_id == null) {
	ups.push(i);
	// Make sure the page is somehow customizable, lest we make a customer
	// visit a page where they can't do anything.
        var c_able = false;
	var lg = layout_groups[design.pages[i].layout_group_id];
	for (var j = 0; j < lg.length; j++) {
	  var dpls = lg[j].dpls;
	  for (var k = 0; k < dpls.length; k++) {
	    if (dpls[k].islots.length > 0 || dpls[k].tslots.length > 0) {
	      c_able = true;
	      break;
	    }
	  }
	  if (c_able) break;
	}
	if (c_able) cups.push(i);
      }
    }

    if (cups.length == 0) {
      // XXX - this is a hack workaround for bug 959.
      page_selector_updates_build = false;
      for (var i = 0; i < ups.length; i++) {
        select_design_page(design.pages[ups[i]]);
      }
      $(document).BuildManage.update_db(
	undefined,
	function() { document.location.href = '/e/pp'; }
      );
    }
    else {
      $('#ips_show_ps').trigger('click');
      $('#ips_canvas').pageselector('notify_pages', cups, 500);
      var descs = product.pb_view_descs.split('/');   // [singular, plural]
      var pb_views_have = (cups == 1) ? descs[0]+' has' : descs[1]+' have';
      var personalizing_it = (cups == 1) ? 'personalizing it' : 'personalizing them';
      jConfirm(
	"The highlighted "+pb_views_have+" not been personalized.  Click 'Cancel' to continue "+personalizing_it+", or 'Ok' if you are finished.",
	"Unvisited "+descs[1].charAt(0).toUpperCase()+descs[1].slice(1),
	function(ok) {
	  if (ok) {
	    // XXX - this is a hack workaround for bug 959.
	    page_selector_updates_build = false;
	    for (var i = 0; i < cups.length; i++) {
	      select_design_page(design.pages[cups[i]]);
	    }
	    $(document).BuildManage.update_db(
	      undefined,
	      function() { document.location.href = '/e/pp'; }
	    );
	  }
	}
      );
    }
  }

  function select_design_page(design_page) {
    $('#page_build').pagebuilder('set_design_page', design_page);

    $('#ips_canvas').pageselector('on_first') ? $('.pb_card_nav_l').hide() : $('.pb_card_nav_l').show();
    $('#ips_canvas').pageselector('on_last') ? $('.pb_card_nav_r').hide() : $('.pb_card_nav_r').show();
    design_page.name == null ? $('.pb_card_nav_txt').html('') : $('.pb_card_nav_txt').html(design_page.name);

    var layout_group = layout_groups[design_page.layout_group_id];
    $('#pc_canvas').layoutselector('set_layout_group', layout_group);

    var pl;
    var build_page = $(document).BuildManage.page_by_seq(design_page.seq);
    if (build_page.dpl_id == null) pl = layout_group[0];
    else pl = dpls[build_page.dpl_id].pl;

    $('#pc_canvas').layoutselector('draw');
    $('#pc_canvas').layoutselector('select_layout', pl);
    $('#page_build').pagebuilder('select_design_page_layout', pl);
  }

  // XXX - this is iterative and should probably be pushed into a LayoutManage.js
  //       with a "by seqs" variable and lookup function.
  function islot_by_seqs(pseq, iseq) {
    var bpage = $(document).BuildManage.page_by_seq(pseq);
    var dpl = dpls[bpage.dpl_id];
    for (var i = 0; i < dpl.islots.length; i++) {
      if (dpl.islots[i].seq == iseq) return dpl.islots[i];
    }
  }

})(jQuery);
