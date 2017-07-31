(function($) {
  $.widget('dp.orientationselector', {
    options: {
      designs: undefined
    },
    _init: function() {
      var self = this;
      $(document).on('change', '.os_radio', function() {
	self.element.trigger('changed', $(this).data('i'));
      });
    },
    set_designs: function(designs) {
      this.options.designs = designs;
    },
    draw: function() {
      var self = this;
      $(self.element).html($('#orientation_select_tmpl').render({designs: self.options.designs}));
    }
  });
})(jQuery);
