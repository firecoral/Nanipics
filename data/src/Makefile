JS =	../js/Dialogs.js ../js/Utility.js ../js/FileUpload.js \
	../js/BuildManage.js ../js/ImageManage.js \
	../js/PageBuild.js ../js/PageSelect.js ../js/LayoutSelect.js \
	../js/ImageSelect.js ../js/ProductBuild.js \
	../js/TextEdit.js ../js/ProductQuantity.js ../js/ImageEdit.js \
	../js/OrientationSelect.js

all: ../js $(JS)

clean:
	rm -f $(JS)

../js:
	mkdir ../js

../js/%.js: ./%.js
	yuicompressor $^ -o $@
