import functools
import logging
from odoo import http
from odoo.http import request
from odoo.addons.restful.common import valid_response, invalid_response, extract_arguments, extract_value
from datetime import timedelta, datetime, date
from dateutil.relativedelta import relativedelta
import dateutil.relativedelta

_logger = logging.getLogger(__name__)


def validate_token(func):
    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        access_token = request.httprequest.headers.get('access_token')
        if not access_token:
            return invalid_response('access_token_not_found', 'missing access token in request header', 401)

        request.session.authenticate(kwargs['db'], kwargs['login'], kwargs['password'])

        access_token_data = request.env['api.access_token'].sudo().search(
            [('token', '=', access_token)], order='id DESC', limit=1)

        if access_token_data.find_one_or_create_token(user_id=access_token_data.user_id.id) != access_token:
            return invalid_response('access_token', 'token seems to have expired or invalid', 401)

        request.session.uid = access_token_data.user_id.id
        request.uid = access_token_data.user_id.id
        return func(self, *args, **kwargs)

    return wrap

class APIController(http.Controller):

    # sales by product api
    @validate_token
    @http.route("/api/product/sales", type='http', auth="none", methods=['GET'], csrf=False)
    def product_sales(self, **kwargs):
        # today/this_week/this_month
        date_option = kwargs.get('date_option') if kwargs.get('date_option') else 'this_week'
        id = kwargs.get('id')
        warehouse_id = request.env['stock.warehouse'].sudo().search([('id', '!=', 1)], order='id DESC', limit=1).id
        if date_option == 'this_week':
            from_date = date.today() - timedelta(days=date.today().weekday())
            to_date = from_date + timedelta(days=6)

        elif date_option == 'this_month':
            from_date = date.today().replace(day=1)
            to_date = date.today() + dateutil.relativedelta.relativedelta(days=1)

        elif date_option == 'today':
            from_date = date.today()
            to_date = date.today()
        product_ids = request.env['product.product'].search([('product_tmpl_id', '=', int(id))]).ids
        product_ids = str(tuple(product_ids)) if len(product_ids) > 1 else "(" + str(product_ids[0]) + ")"
        print(product_ids)

        query = ("""select so.date_order,inv.number,pt.name,sl.product_uom_qty,
                                        sl.price_subtotal,pd.id,inv.id,sl.id from sale_order_line sl
                                        JOIN sale_order so ON sl.order_id = so.id
                                        JOIN product_product pd on pd.id = sl.product_id
                                        JOIN product_template pt on pt.id = pd.product_tmpl_id
                                        JOIN account_invoice inv on inv.origin = so.name
                                        where so.date_order::DATE >= '%s'::DATE and
                                        so.date_order::DATE <= '%s'::DATE and
                                        sl.state = 'done' and so.warehouse_id = %s
                                        and pd.id in %s""" % (
            from_date, to_date, warehouse_id, product_ids))
        #print(query)
        request.cr.execute(query)
        data = request.cr.fetchall()
        array = []
        try:
            if data:
                for arr in data:
                    variant = request.env['product.product'].search([('id', '=', arr[5])]).attribute_value_ids.name
                    array.append({
                        "date": arr[0],
                        "invoice": arr[1],
                        "name": arr[2],
                        "variant": variant,
                        "qty": arr[3],
                        "subtotal": arr[4],
                        "product_id": arr[5],
                        "invoice_id": arr[6],
                        "sale_line_id": arr[7]
                    })
                return valid_response(array)
            else:
                return valid_response([])
        except ValueError as err:
            return [{
                "error": err,
                "message": err.message,
            }]