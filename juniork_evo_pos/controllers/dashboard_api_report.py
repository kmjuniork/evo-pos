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

    # common function
    def get_filter(self, **kwargs):

        from_date = kwargs.get('from_date')
        to_date = kwargs.get('to_date')
        category_id = kwargs.get('category') if kwargs.get('category') else 25
        category_ids = request.env['product.category'].sudo().search([('id', 'child_of', int(category_id)), ('category_type', 'not in', ('table','marker'))]).ids
        category_ids = str(tuple(category_ids)) if len(category_ids) > 1 else "(" + str(category_ids[0]) + ")"
        print(category_ids)

        all_user_ids = request.env['res.users'].sudo().search([]).ids
        all_user_ids = str(tuple(all_user_ids))
        cashier_id = "(" + str(kwargs.get('cashier_id'))+")" if kwargs.get('cashier_id') else all_user_ids

        # default last 7 days
        if not from_date or not to_date:
            date = datetime.now()
            from_date = date - dateutil.relativedelta.relativedelta(days=8)
            to_date = date + dateutil.relativedelta.relativedelta(days=1)
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d") - dateutil.relativedelta.relativedelta(days=1)
            to_date = datetime.strptime(to_date, "%Y-%m-%d") + dateutil.relativedelta.relativedelta(days=1)
        data = {
            'from_date': from_date,
            'to_date': to_date,
            'category_ids': category_ids,
            'cashier_id': cashier_id
        }
        return data

    # top 5 selling product api
    @validate_token
    @http.route("/api/top/selling/product", type='http', auth="none", methods=['GET'], csrf=False)
    def top_selling_product(self, **kwargs):

        limit_value = 10
        data = self.get_filter(**kwargs)
        from_date = data.get('from_date')
        to_date = data.get('to_date')
        category_ids = data.get('category_ids')
        cashier_id = data.get('cashier_id')
        warehouse_id = request.env['stock.warehouse'].sudo().search([('id', '!=', 1)], order='id DESC', limit=1).id

        order = 'desc'
        limit_clause = " limit'%s'" % limit_value if limit_value else ""

        query = ("""select sl.name as product_name,sum(product_uom_qty),pu.name from sale_order_line sl
                           JOIN sale_order so ON sl.order_id = so.id
                           JOIN uom_uom pu on sl.product_uom = pu.id
                           JOIN product_product pd on pd.id = sl.product_id
                           JOIN product_template pt on pt.id = pd.product_tmpl_id
                           where so.date_order::DATE > '%s'::DATE and
                           so.date_order::DATE < '%s'::DATE and
                           sl.state = 'done' and so.warehouse_id = %s
                           and pt.categ_id in %s and so.user_id in %s
                           group by sl.name,pu.name order by sum %s""" % (
            from_date, to_date, warehouse_id, category_ids, cashier_id, order)) + limit_clause
        print(query)
        request.cr.execute(query)
        data = request.cr.fetchall()
        array = []
        try:
            if data:
                for arr in data:
                    array.append({"name": arr[0], "sold-qty": arr[1], "uom": arr[2]})
                return valid_response(array)
            else:
                return valid_response({'message': 'No record Found!'})
        except Exception as e:
            return invalid_response('exception', e.name)

    # category statistics
    @validate_token
    @http.route("/api/selling/category", type='http', auth="none", methods=['GET'], csrf=False)
    def dashboard_category_reports(self, **kwargs):
        data = self.get_filter(**kwargs)
        from_date = data.get('from_date')
        to_date = data.get('to_date')
        category_ids = data.get('category_ids')
        cashier_id = data.get('cashier_id')
        warehouse_id = request.env['stock.warehouse'].sudo().search([('id', '!=', 1)], order='id DESC', limit=1).id

        order = 'desc'
        query = ("""select pc.name,sum(product_uom_qty) from sale_order_line sl
                                   JOIN sale_order so ON sl.order_id = so.id
                                   JOIN uom_uom pu on sl.product_uom = pu.id
                                   JOIN product_product pd on pd.id = sl.product_id
                                   JOIN product_template pt on pt.id = pd.product_tmpl_id
                                   JOIN product_category pc on pc.id = pt.categ_id
                                   where so.date_order::DATE > '%s'::DATE and
                                   so.date_order::DATE < '%s'::DATE and
                                   sl.state = 'done' and so.warehouse_id = %s
                                   and pt.categ_id in %s and so.user_id in %s
                                   group by pc.name order by sum %s""" % (
            from_date, to_date, warehouse_id, category_ids, cashier_id, order))
        print(query)
        request.cr.execute(query)
        data = request.cr.fetchall()
        array = []
        try:
            if data:
                for arr in data:
                    array.append({"categ_name": arr[0], "sold-qty": arr[1]})
                return valid_response(array)
            else:
                return valid_response({'message': 'No record Found!'})
        except Exception as e:
            return invalid_response('exception', e.name)

    def get_dashboard_report_data(self, from_date, to_date):
        sales_income = 0
        cost_of_sales = 0
        sale_obj = request.env['sale.order']
        warehouse_id = request.env['stock.warehouse'].sudo().search([('id', '!=', 1)], order='id DESC', limit=1).id

        sale_domain = [('state', '=', 'done'), ('warehouse_id', '=', warehouse_id), ('date_order', '>=', from_date),
                       ('date_order', '<=', to_date)]
        sales_income = sum(sale_obj.sudo().search(sale_domain).mapped('amount_total'))
        sale_ids = sale_obj.sudo().search(sale_domain).ids
        sale_lines = request.env['sale.order.line'].search([('order_id', 'in', tuple(sale_ids))], order='id DESC')
        for sale_line in sale_lines:
            product_id = sale_line['product_id']
            if product_id.categ_id.category_type:
                qty = sale_line['product_uom_qty'] / 60
            else:
                qty = sale_line['product_uom_qty']
            standard_price = product_id.standard_price

            cost_of_sales += (qty*standard_price)
        sales_profit = sales_income - cost_of_sales if sales_income else 0
        return sales_income, cost_of_sales, sales_profit

    @validate_token
    @http.route("/api/dashboard/reports", type='http', auth="none", methods=['GET'], csrf=False)
    def dashboard_reports(self, **kwargs):
        # last month
        last_month = date.today() - dateutil.relativedelta.relativedelta(months=1)
        last_month_from_date = last_month.replace(day=1)
        last_month_to_date = (last_month + relativedelta(months=1, day=1)) - timedelta(1)

        # last week/7 days
        last_week_from_date = date.today() - dateutil.relativedelta.relativedelta(days=7)
        last_week_to_date = date.today() + dateutil.relativedelta.relativedelta(days=1)

        last_month_sales_income, last_month_cost_of_sales, last_month_sales_profit = 0 , 0, 0
        last_week_sales_income, last_week_cost_of_sales, last_week_sales_profit = 0, 0, 0
        last_month_sales_income, last_month_cost_of_sales, last_month_sales_profit = self.get_dashboard_report_data(last_month_from_date, last_month_to_date)
        last_week_sales_income, last_week_cost_of_sales, last_week_sales_profit = self.get_dashboard_report_data(last_week_from_date, last_week_to_date)

        vals = {
            'last_month_sales_income': last_month_sales_income,
            'last_month_cost_of_sales': last_month_cost_of_sales,
            'last_month_sales_profit': last_month_sales_profit,
            'last_week_sales_income': last_week_sales_income,
            'last_week_cost_of_sales': last_week_cost_of_sales,
            'last_week_sales_profit': last_week_sales_profit
        }

        return valid_response(vals)



