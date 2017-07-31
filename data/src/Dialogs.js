// $Header: //depot/cs/data/src/Dialogs.js#4 $
//
// This script varies substantially with the format we usually
// use for scripts.  This is due to historical issues:
//
// The script is being used as a replacement for jquery.alerts.js
// (using jquery-ui dialogs), so it maintains the same calling
// interface.
//
(function($) {
  jAlert = function(message, title, callback) {
    var alert_dialog =	'<div id="_alert_dialog" class="ui-widget" style="display: none;">' +
    			'<div class="ui-state-highlight ui-corner-all">' +
			'<span class="ui-icon ui-icon-info" style="position: absolute; left: 8px; top: 0; margin:8px 0px 0px 7px;"></span>' +
			'<div id="_alert_content" style="float: inherit; margin-left: 25px;"></div>' +
			'</div></div>';

    if (!$('#_alert_dialog').length) {
      $('body').append(alert_dialog);
      $('#_alert_dialog').dialog({
	autoOpen: false
      });
    }
    $('#_alert_content').html(message);
    if (!title)
      title = 'Alert';
    $('#_alert_dialog').dialog('option', {
      modal: true,
      title: title,
      buttons: {
	Ok: function() {
	  $(this).dialog('close');
	  if (callback)
	    callback(true);
	}
      }
    });
    $('#_alert_dialog').dialog('open');
  };

  // A version of jAlert, but styled as an error (rather than info) box.
  jError = function(message, title, callback) {
    var error_dialog =	'<div id="_error_dialog" class="ui-widget" style="display: none;">' +
    			'<div class="ui-state-error ui-corner-all">' +
			'<span class="ui-icon ui-icon-info" style="position: absolute; left: 8px; top: 0; margin:8px 0px 0px 7px;"></span>' +
			'<div id="_error_content" style="float: inherit; margin-left: 25px;"></div>' +
			'</div></div>';

    if (!$('#_error_dialog').length) {
      $('body').append(error_dialog);
      $('#_error_dialog').dialog({
	autoOpen: false
      });
    }
    $('#_error_content').html(message);
    if (!title)
      title = 'Error';
    $('#_error_dialog').dialog('option', {
      modal: true,
      title: title,
      buttons: {
	Ok: function() {
	  $(this).dialog('close');
	  if (callback)
	    callback(true);
	}
      }
    });
    $('#_error_dialog').dialog('open');
  };

  jConfirm = function(message, title, callback) {
    var confirm_dialog = '<div id="_confirm_dialog" class="ui-widget" style="display: none;">' +
    			 '<div class="ui-state-highlight ui-corner-all">' +
			 '<span class="ui-icon ui-icon-alert" style="position: absolute; left: 8px; top: 0; margin:8px 0px 0px 7px;"></span>' +
			 '<div id="_confirm_content" style="float: inherit; margin-left: 25px;"></div>' +
			 '</div></div>';

    if (!$('#_confirm_dialog').length) {
      $('body').append(confirm_dialog);
      $('#_confirm_dialog').dialog({
	autoOpen: false
      });
    }
    $('#_confirm_content').html(message);
    if (!title)
      title = 'Please Confirm';
    $('#_confirm_dialog').dialog({
      modal: true,
      title: title,
      buttons: {
	Ok: function() {
	  $(this).dialog('close');
	  if (callback)
	    callback(true);
	},
	Cancel: function() {
	  $(this).dialog('close');
	  if (callback)
	    callback(false);
	}
      }
    });
    $('#_confirm_dialog').dialog('open');
  };
	  
  jPrompt = function(message, value, title, callback) {
    var prompt_dialog =	'<div id="_prompt_dialog" class="ui-widget" style="display: none;">' +
    			'<div class="ui-state-highlight ui-corner-all">' +
			'<span class="ui-icon ui-icon-help" style="position: absolute; left: 8px; top: 0; margin:8px 0px 0px 7px;"></span>' +
			'<div style="float: inherit; margin-left: 25px;">' +
			'<span id="_prompt_content"></span>' +
		        '<input id="_prompt_text" type="text" size="30" style="width: 220px; margin-bottom: 5px;">' +
			'</div></div></div>';

    if (!$('#_prompt_dialog').length) {
      $('body').append(prompt_dialog);
      $('#_prompt_dialog').dialog({
	autoOpen: false
      });
    }
    $('#_prompt_content').html(message);
    $('#_prompt_text').val(value);
    $('#_prompt_text').focus(function() {
      this.select();
    });
    if (!title)
      title = 'Prompt';
    $('#_prompt_dialog').dialog({
      modal: true,
      title: title,
      open: function() {
	$('#_prompt_text').focus();
      },
      buttons: {
	Ok: function() {
	  $(this).dialog('close');
	  if (callback)
	    callback($('#_prompt_text').val());
	},
	Cancel: function() {
	  $(this).dialog('close');
	  if (callback)
	    callback(null);
	}

      },
      open: function() {
	$("#_prompt_text").keypress(function(e) {
	  if (e.keyCode == $.ui.keyCode.ENTER) {
	    $(this).closest('.ui-dialog').find(".ui-dialog-buttonpane").find("button:eq(0)").trigger("click");
	  }
	});
      }
    });
    $('#_prompt_dialog').dialog('open');
  };
})(jQuery);
