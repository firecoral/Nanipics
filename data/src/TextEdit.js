(function($) {
  $.widget('dp.texteditor', {
    options: {
      ttype: undefined,
      tslots: undefined,
      cur_tslot: undefined
    },
    _init: function() {
    },
    set_ttype: function(ttype) {
      this.options.ttype = ttype;
    },
    set_tslots: function(tslots) {
      this.options.tslots = tslots;
    },
    set_cur_tslot: function(cur_tslot) {
      this.options.cur_tslot = cur_tslot;
    },
    cur_tslot: function() {
      return this.options.cur_tslot;
    },
    focus_current: function() {
      var seq = this.options.cur_tslot.btext.seq;
      $(this.element).find('.te_text[data-seq='+seq+']').focus();
    },
    draw: function() {
      var self = this;
      $(this.element).html($('#text_edit_tmpl').render({
	'tslots'  : self.options.tslots,
	'cur_tseq': self.options.cur_tslot.seq,
	'ttype'   : self.options.ttype
      }));
      $(this.element).find('#te_close').on('click', function() {
	var cur_tslot = self.options.cur_tslot;
	if (cur_tslot != undefined) {   // undef if "EDIT TEXT" then "close"
	  // hide() doesn't blur, so have to call explicitly.
	  $(self.element).find('.te_text[data-seq='+cur_tslot.seq+']').triggerHandler('blur');
	}
	$(self.element).hide();
	self.options.cur_tslot = undefined;
      });
      $(this.element).find('.te_text').on('focus', function() {
	for (var i = 0; i < self.options.tslots.length; i++) {
	  if (self.options.tslots[i].seq == $(this).data('seq')) {
	    self.options.cur_tslot = self.options.tslots[i];
	    self.element.trigger('textselected', self.options.cur_tslot);
	    return false;
	  }
	}
      });
      $(this.element).find('.te_text').on('blur', function() {
	var cur_tslot = self.options.cur_tslot;
	// XXX - (why) is this necessary?
        if (cur_tslot == null) return;
	var text_changed = cur_tslot.btext.content != $(this).val();
	cur_tslot.btext.content = $(this).val();
	self.element.trigger('textunselected', text_changed);
      });
      $(this.element).find('.te_fonts_select').on('change', function() {
	var cur_tslot = self.options.cur_tslot;
	// XXX - (why) is this necessary?
        if (cur_tslot == null) return;
	cur_tslot.btext.font_id = $(this).val();
	self.element.trigger('fontchanged');
      });
      $(this.element).find('.te_fontsizes_select').on('change', function() {
	var cur_tslot = self.options.cur_tslot;
	// XXX - (why) is this necessary?
        if (cur_tslot == null) return;
	cur_tslot.btext.fontsize_id = $(this).val();
	self.element.trigger('fontsizechanged');
      });
      $(this.element).find('.te_gravity').on('click', function() {
	var cur_tslot = self.options.cur_tslot;
	// XXX - (why) is this necessary?
        if (cur_tslot == null) return;
	cur_tslot.btext.gravity_id = $(this).data('gravity_id');

	var click_i = $(this).data('i');
	$(self.element).find('.te_gravity').each(function() {
	  if ($(this).data('i') == click_i) {
	    $(this).removeClass('te_gravity_notcur').addClass('te_gravity_cur');
	  }
	  else {
	    $(this).removeClass('te_gravity_cur').addClass('te_gravity_notcur');
	  }
        });
	self.element.trigger('gravitychanged');
      });
    },
    show: function() {
      $(this.element).show();
    }
  });
})(jQuery);
