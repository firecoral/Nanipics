(function($) {
  $.widget('dp.layoutselector', {
    options: {
      layout_group: undefined,
      layout: undefined
    },
    _init: function() {
      var self = this;
      $(document).on('click', '.ls_icon', function() {
	var layout = $(this).data('layout');
	self.select_layout(layout);
	self.element.trigger('layout_clicked', layout);
      });
    },
    set_layout_group: function(layout_group) {
      this.options.layout_group = layout_group;
    },
    select_layout: function(layout) {
      this.options.layout = layout;
      for (var i = 0; i < this.options.layout_group.length; i++) {
	if (this.options.layout_group[i] == this.options.layout) {
	  this.options.layout_group[i].is_current = true;
	}
	else {
	  this.options.layout_group[i].is_current = false;
	}
      }
      this.draw();
    },
    draw: function() {
      var self = this;
      $(self.element).html($('#layout_select_tmpl').render(self.options.layout_group));
      $(self.element).find('.ls_icon').each(function(i, ls_icon) {
	$(this).data('layout', self.options.layout_group[i]);
      });
      $(self.element).find('.ls_icon').draggable({
	helper: 'clone',
	distance: 5
      });
    }
  });
})(jQuery);
