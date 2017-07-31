# $Header: //depot/cs/s/product_csv.wsgi#21 $
from db.Support import SupportSession
from db.Exceptions import SupportSessionExpired
import db.Db as Db
import db.Statics as Statics
import db.Product as Product
from werkzeug.wrappers import Response
from p.DTemplate import DTemplate
from p.DRequest import DRequest
import csv
import StringIO

def application(environ, start_response):
    """Download a CSV file containing the products."""

    request = DRequest(environ)

    try:
        Db.start_transaction()
        support = SupportSession(key=request.support_key())
        products = Statics.products.get()
        output = StringIO.StringIO()
        fieldnames = ('product_id', 'name', 'promo_category_id', 'is_available')
	for i in range(Product.CSVPRICECOUNT):
	    min_quantity =   "min_quantity" + str(i)
	    price = "price" + str(i)
	    sale_price = "sale_price" + str(i)
	    fieldnames  =  fieldnames + (min_quantity, price, sale_price)
	    for product in products:
		product_prices = product['product_pricing']
		if i < len(product_prices):
		    product[min_quantity] = product_prices[i]['min_quantity']
		    product[price] = product_prices[i]['price']
		    product[sale_price] = product_prices[i]['sale_price']
		else:
		    product[min_quantity] = 0
		    product[price] = 0.00
		    product[sale_price] = 0.00

        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore', dialect='excel')
        headers = dict( (n,n) for n in fieldnames )
        writer.writerow(headers)
        for r in products:
            writer.writerow(r)
        resp =  Response(output.getvalue())
        output.close()
        Db.finish_transaction()
    except SupportSessionExpired:
        Db.cancel_transaction()
        resp =  Response("Session Expired")
    except Exception as e:
        Db.cancel_transaction()
        import traceback
        traceback.print_exc()
        resp =  Response("Internal Error")

    request.cookie_freshen(resp)
    resp.headers['content-type'] = 'text/csv; charset=utf-8'
    resp.headers['cache-control'] = 'no-cache'
    resp.headers['content-length'] = len(resp.data)
    return resp(environ, start_response)
