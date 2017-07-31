(function($) {
  var li_qty;
  var product;
  var no_li;

  $.fn.ProductQuantity = function(opts) {
    li_qty = opts.li_qty;
    product = opts.product;
    build = opts.build;
    no_li = opts.no_li;
    quantity_text = opts.quantity_text;
  };

  $.fn.ProductQuantity.draw = function() {
    // Change the continue button based on whether we are here to update a quantity
    // or actually insert the initial line_item.
    if (no_li) {
      $("#add_to_order").button("option", "label", "+ Add to Order");
    }
    else {
      $("#add_to_order").button("option", "label", "Update Quantity");
    }

    // Show the first preview image.
    var cw = parseInt($('#preview_img').width());
    var ch = parseInt($('#preview_img').height());
    var ca = cw / ch;
    var page = product.pages[0];
    var pw, ph, pt, pl;
    if (page.aspect >= ca) {
      pw = cw;
      ph = Math.round(pw / page.aspect);
      pl = 0;
      pt = Math.round((ch - ph) / 2);
    }
    else {
      ph = ch;
      pw = Math.round(ph * page.aspect);
      pt = 0;
      pl = Math.round((cw - pw) / 2);
    }

    var url = '/e/p?s=1&w='+cw+'&h='+ch+'&t=ff&a='+build.build_access_id+'&r='+build.rev;
    $('#preview_img').html($('#preview_img_tmpl').render([{
      url: url,
      blockout_afile: page.blockout_afile,
      pw: pw,
      ph: ph,
      pl: pl,
      pt: pt
    }]));

    // Show the variable pricing table if there is more than one.
    if (product.prices.length > 1) {
      $('.prices').empty();
      $('.price_container').show();
      $('.prices').append($('#pq_pricing').render(product.prices));
    }
    else {
      $('.price_container').hide();
      $('.prices').empty();
    }


    $('#product_name').html(product.name);
    setPrice(li_qty);
    setQuantityText(quantity_text);
    if (product.quantity_incr > 1) {
      $('#quantity').prop("readonly", true);
      $('#quantity').spinner({
	min: 0,
	step: product.quantity_incr,
	stop: function (event, ui) {
	  setPrice($(this).val());
	},
	spin: function (event, ui) {
	  if (ui.value < product.quantity_base) {
	    // If we are moving downwards, set the value to 0
	    if ($(this).val() > ui.value) {
	      $(this).val(0);
	      setPrice(0);
	    }
	    // If we are moving upwards, set the value to product.quantity_base
	    else if ($(this).val() < ui.value) {
	      $(this).val(product.quantity_base);
	      setPrice(product.quantity_base);
	    }
	    return false;
	  }
	}
      }).val(li_qty);
    }
    else {
      $('#quantity').prop("readonly", false);
      $('#quantity').val(li_qty);
    }
  };

  $.fn.ProductQuantity.getValue = function() {
    return $('#quantity').val();
  };

  function setPrice(quantity) {
    $.each(product.prices, function(i, price) {
      if (price.max_quantity == 0 || quantity <= price.max_quantity) {
	$('#price').html($.views.converters.price(price));
	return false;
      }
    });
  };

  function setQuantityText(quantity_text) {
    if (quantity_text) {
      $('#quantity_text').html($('#qty_text_tmpl').render({ quantity_text: quantity_text }));
    }
    else {
      $('#quantity_text').html("");
    }
  }

})(jQuery);
