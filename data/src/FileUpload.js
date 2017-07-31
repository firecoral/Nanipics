// $Header: //depot/cs/data/src/FileUpload.js#4 $
//
// This script provides a file upload dialog.
// 
// In addition to jquery and jquery-ui, the following scripts are required:
//   <link rel="stylesheet" href="/css/fileupload.css" type="text/css">
//   <script src="/js/fu/jquery.iframe-transport.js"></script>
//   <script src="/js/fu/jquery.fileupload.js"></script>
//
(function($) {
  $.widget("dp.fileuploader", {
    options: {
      title: "Upload File",
      url: undefined,
      message: undefined,
      done: function() {},
      error: function() {},
      pre_show: undefined,
      formData: {}
    },
    _init: function() {
      // Create the dialog if we haven't yet.
      // This could have been called in _create, but we
      // defer to _init simply for performance reasons.
      if (!this.$dialog) {
	var self = this;
	// XXX Move a bunch of this string to the supporting css file.
    	this.$dialog = $('<div class="file-uploader ui-widget">' +
			 '<div class="ui-state-highlight ui-corner-all">' +
			 '<span class="file-uploader-message"></span>' +
			 '<span class="file-wrapper">' +
			 '<input class="fileupload" type="file" name="files[]" multiple>' +
			 '<span class="upbutton ui-corner-all ui-state-default ui-widget">Add Photos...</span>' +
			 '</span>' +
			 '<table class="file-uploader-list"></table><br /><br />' +
			 '</div>' +
			 '</div>');

	var $dialog = this.$dialog;
	$('body').append($dialog);
	$dialog.dialog({
	  autoOpen: false,
	  width: '450px'
	});
	$dialog.find('.upbutton').button();
	$dialog.find('.fileupload').fileupload({
	  dataType: 'json',
	  add: function(e, data) {
	    $.each(data.files, function(i, file) {
	      "use strict";
	      var size = self.formatBytes(file.size);
	      var value = 0;
	      if (!size)
		value = 100;
	      file.$display = $('<tr><td>' + file.name + '</td><td>' + size + '</td><td class="fu_status"><div class="fu_progressbar"></div></td></tr><br />');
	      file.$display.find('.fu_progressbar').progressbar({value: value});
	      $dialog.find('.file-uploader-list').append(file.$display);
	    });
	    data.submit();
	  },
	  done: function(e, data) {
	    // Assuming that data.files parallels data.results here
	    $.each(data.files, function(i, file) {
	      var result = data.result[i];
	      if (result.error) {
		var status_txt = $('<span class="ui-state-error-text">' + result.error + '</span>');
		file.$display.find('.fu_status').html(status_txt);
		self.options.error(e, self.options.element, result);
	      }
	      else {
		var message = 'done';
		if (result.done_message)
		  message = result.done_message;
		//file.$display.find('.fu_progressbar').progressbar('option', 'value', 100);
		var status_txt = $('<span class="ui-state-highlight">' + message + '</span>');
		file.$display.find('.fu_status').html(status_txt);
		self.options.done(e, self.options.element, result);
	      }
	    });
	  },
	  fail: function(e, data) {
	    $.each(data.files, function(i, file) {
	      var status_txt = $('<span class="ui-state-error-text">' + data.textStatus + '</span>');
	      file.$display.find('.fu_status').html(status_txt);
	    });
	  },
	  progress: function (e, data) {
	    var files = data.files.length;
	    var name = "unknowns";
	    var file = data.files[0];
	    if (file)
	      name = file.name;
	    var value = parseInt(data.loaded / data.total * 100, 10);
	    file.$display.find('.fu_progressbar').progressbar('option', 'value', value);
	  },
	  formData: function (form) {
	    if (self.options.formData) {
	      formData = [];
	      $.each(self.options.formData, function (name, value) {
		formData.push({name: name, value: value});
	      });
	      return formData;
	    }
	  }
	});
      }
      $(this.element).on('click', $.proxy(function() {
	self.options.element = this.element;
	//
	// Call this function before showing the dialog box.  Pass
	// the element the file uploader was attached to as an argument.
	//
	if (jQuery.isFunction(self.options.pre_show) && (!self.options.pre_show(this.element))) {
	  return false;
	}
	else {
	  this.$dialog.find('.file-uploader-list').empty();
	  if (self.options.message)
	    this.$dialog.find('.file-uploader-message').html(self.options.message)
	  else
	    this.$dialog.find('.file-uploader-message').empty();
	  this.$dialog.dialog('open');
	  return false;
	}
      }, this));

      if (this.options.url)
	this.$dialog.find('.fileupload').fileupload('option', 'url', this.options.url);
      this.$dialog.dialog('option', {
	modal: true,
	title: this.options.title,
	buttons: {
	  Close: function() {
	    $(this).dialog('close');
	  }
	}
      });
    },
    formatBytes: function (bytes) {
      if (!bytes) {
	return "";
      }
      if (bytes >= 1000000000) {
	return (bytes / 1000000000).toFixed(2) + 'GB';
      }
      if (bytes >= 1000000) {
	return (bytes / 1000000).toFixed(2) + 'MB';
      }
      if (bytes >= 1000) {
	return (bytes / 1000).toFixed(2) + 'KB';
      }
      return bytes + 'B';
    }
  });
})(jQuery);

