(function($) {
  $.widget('dp.pageselector', {
    options: {
      design_pages: undefined,
      cur_design_page_i: undefined
    },
    _init: function() {
      var self = this;
      $(document).on('click', '.ps_page', function() {
	self.set_cur_design_page_i($(this).data('i'));
      });
    },
    set_design_pages: function(design_pages) {
      this.options.design_pages = design_pages;
    },
    set_cur_design_page_i: function(design_page_i) {
      var self = this;
      $(self.element).find('.ps_page').each(function() {
	if ($(this).data('i') == design_page_i) {
	  $(this).addClass('ps_page_cur');
	  $(this).removeClass('ps_page_notcur');
	}
	else {
	  $(this).addClass('ps_page_notcur');
	  $(this).removeClass('ps_page_cur');
	}
      });
      self.options.cur_design_page_i = design_page_i;
      self.unnotify_pages([design_page_i], 1000);
      self.element.trigger('pageselected', self.get_cur_design_page());
    },
    on_first: function() {
      return this.options.cur_design_page_i == 0;
    },
    on_last: function() {
      return this.options.cur_design_page_i == this.options.design_pages.length - 1;
    },
    prev: function() {
      if (this.on_first()) return;
      this.set_cur_design_page_i(this.options.cur_design_page_i - 1);
    },
    next: function() {
      if (this.on_last()) return;
      this.set_cur_design_page_i(this.options.cur_design_page_i + 1);
    },
    get_cur_design_page_i: function() {
      return this.options.cur_design_page_i;
    },
    get_cur_design_page: function() {
      return this.options.design_pages[this.options.cur_design_page_i];
    },
    draw: function() {
      var design_pages = this.options.design_pages;
      for (var i in design_pages) {
	design_pages[i].is_current = i == this.options.cur_design_page_i;
      }
      $(this.element).html($('#page_select_tmpl').render(design_pages));
    },
    notify_pages: function(page_is, duration) {
      var self = this;
      for (var i = 0; i < page_is.length; i++) {
	$(self.element).find('.ps_page:eq('+page_is[i]+')').each(function() {
	  $(this).data('old_bkg', $(this).css('background-color'));
	  $(this).animate(
	    {'background-color': '#FA0'},
	    duration
	  );
	});
      }
    },
    unnotify_pages: function(page_is, duration) {
      var self = this;
      for (var i = 0; i < page_is.length; i++) {
	$(self.element).find('.ps_page:eq('+page_is[i]+')').each(function() {
	  var old_bkg = $(this).data('old_bkg');
	  if (old_bkg == null) return;
	  $(this).animate(
	    {'background-color': old_bkg},
	    duration
	  );
	});
      }
    }
  });
})(jQuery);
