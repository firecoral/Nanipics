// $Header: //depot/cs/data/src/Utility.js#3 $
//
// Utility javascripts
// 
//


//
// Generalized ajax function for our scripts
// (using jquery-ui dialogs), so it maintains the same calling
// interface.
//
// We expect the calling function will return data.Error on failure.
// The data format for success can be any object (without an Error property).
//

function DPAjax(url, args, success_callback, error_callback) {
  document.body.style.cursor = 'wait';
  $.ajax({
    url: url,
    type: "POST",
    data: ({
      args: $.toJSON(args)
    }),
    dataType: "html",
    success:  function(data) {
      data = $.evalJSON(data);
      $('body').css('cursor', 'auto');
      if (data.Error) {
	if (error_callback)
	  error_callback(data);
        else
          alert("Error: " + data.Error);
      }
      else {
	if (success_callback) {
	  success_callback(data);
	}
      }
    },
    error:  function(req) {
      $('body').css('cursor', 'auto');
      if (error_callback)
	// There are issues when a request is interrupted (say by a browser
	// reload) and this error is returned.  Make sure it can be recognized
	// further downstream so a failure to connect can be handled differently.
	// This particularly helps the 'ping' requests.
	error_callback({Error: "Could not connect to server", unavailable: true});
      else
	alert("Could not connect to server");
    }
  });
};

