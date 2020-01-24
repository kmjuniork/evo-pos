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

        date_option = kwargs.get('date_option') if kwargs.get('date_option') else '7days'

        # company_id = request.env.user.company_id.id
        company_id = 1
        warehouse_ids = request.env['stock.warehouse'].sudo().search([('company_id', '=', company_id)]).mapped('id')
        print(warehouse_ids)
        warehouse_id = kwargs.get('warehouse') if kwargs.get('warehouse') else warehouse_ids

        from_date = date.today() - dateutil.relativedelta.relativedelta(years=100)
        to_date = date.today() + dateutil.relativedelta.relativedelta(days=1)

        if date_option == '7days':
            from_date = date.today() - dateutil.relativedelta.relativedelta(days=7)
            to_date = date.today() + dateutil.relativedelta.relativedelta(days=1)

        elif date_option == 'last_month':
            date_limit = date.today() - dateutil.relativedelta.relativedelta(months=1)
            from_date = date_limit.replace(day=1)
            to_date = (date_limit + relativedelta(months=1, day=1)) - timedelta(1)

        elif date_option == 'curr_month':
            from_date = date.today().replace(day=1)
            to_date = date.today() + dateutil.relativedelta.relativedelta(days=1)

        elif date_option == 'last_year':
            date_limit = date.today() - dateutil.relativedelta.relativedelta(years=1)
            from_date = date_limit.replace(day=1)
            to_date = (date_limit + relativedelta(months=12, day=1)) - timedelta(1)

        elif date_option == 'curr_year':
            date_limit = date.today() - dateutil.relativedelta.relativedelta(years=1)
            from_date = date.today().replace(month=1, day=1)
            to_date = date.today() + dateutil.relativedelta.relativedelta(days=1)

        elif date_option == 'select_period':
            from_date = kwargs.get('from_date')
            to_date = kwargs.get('to_date')

        data = {
            'company_id': company_id,
            'warehouse_id': warehouse_id,
            'from_date': from_date,
            'to_date': to_date
        }
        return data

    # sales profit and loss report api
    @validate_token
    @http.route("/api/profit/loss/report", type='http', auth="none", methods=['GET'], csrf=False)
    def profit_loss_report(self, **payload):
        data = {'used_context': {'journal_ids': False, 'state': 'posted', 'date_from': False, 'date_to': False,
                                 'strict_range': True, 'company_id': 1, 'lang': 'en_US'}}
        if payload.get('date_from'):
            data['used_context']['date_from'] = payload['date_from']
        if payload.get('date_to'):
            data['used_context']['date_to'] = payload['date_to']
        print(data)
        lines = []
        account_report = request.env['account.financial.report'].sudo().search([('id', '=', 1)])
        child_reports = account_report.sudo()._get_children_by_order()
        res = request.env['report.accounting_pdf_reports.report_financial'].sudo().with_context(
            data.get('used_context'))._compute_report_balance(child_reports)
        for report in child_reports:
            vals = {
                'name': report.name,
                'balance': res[report.id]['balance'] * report.sign,
                'type': 'report',
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type or False,  # used to underline the financial report balances
            }

            lines.append(vals)
            if report.display_detail == 'no_detail':
                # the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue

            if res[report.id].get('account'):
                sub_lines = []
                for account_id, value in res[report.id]['account'].items():
                    # if there are accounts to display, we add them to the lines with a level equals to their level in
                    # the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
                    # financial reports for Assets, liabilities...)
                    flag = False
                    account = request.env['account.account'].sudo().browse(account_id)
                    vals = {
                        'name': account.code + ' ' + account.name,
                        'balance': value['balance'] * report.sign or 0.0,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and 4,
                        'account_type': account.internal_type,
                    }
                    if not account.company_id.currency_id.is_zero(vals['balance']):
                        flag = True
                    if flag:
                        sub_lines.append(vals)
                lines += sorted(sub_lines, key=lambda sub_line: sub_line['name'])

        return valid_response(lines)

    # top 5 selling product api
    @validate_token
    @http.route("/api/top/selling/product", type='http', auth="none", methods=['GET'], csrf=False)
    def top_selling_product(self, **kwargs):

        limit_value = 5
        data = self.get_filter(**kwargs)
        company_id = data.get('company_id')
        warehouse_id = data.get('warehouse_id')
        from_date = data.get('from_date')
        to_date = data.get('to_date')

        order = 'desc'
        warehouse_id = str(tuple(warehouse_id)) if len(warehouse_id) > 1 else "(" + str(warehouse_id[0]) + ")"
        limit_clause = " limit'%s'" % limit_value if limit_value else ""

        query = ("""select sl.name as product_name,sum(product_uom_qty),pu.name from sale_order_line sl
                           JOIN sale_order so ON sl.order_id = so.id
                           JOIN uom_uom pu on sl.product_uom = pu.id
                           where so.date_order::DATE >= '%s'::DATE and
                           so.date_order::DATE <= '%s'::DATE and
                           sl.state = 'sale' and so.company_id = %s
                           and so.warehouse_id in %s
                           group by sl.name,pu.name order by sum %s""" % (
        from_date, to_date, company_id, warehouse_id, order)) + limit_clause

        request.cr.execute(query)
        data = request.cr.fetchall()
        array = []
        try:
            if data:
                for arr in data:
                    array.append({"name": arr[0], "sold-qty": arr[1], "uom": arr[2]})
                return valid_response(array)
        except Exception as e:
            return invalid_response('exception', e.name)

    # top selling customer api
    @validate_token
    @http.route("/api/top/selling/customer", type='http', auth="none", methods=['GET'], csrf=False)
    def top_selling_customer(self, **kwargs):

        data = self.get_filter(**kwargs)
        company_id = data.get('company_id')
        warehouse_id = data.get('warehouse_id')
        from_date = data.get('from_date')
        to_date = data.get('to_date')

        order = 'desc'
        warehouse_id = str(tuple(warehouse_id)) if len(warehouse_id) > 1 else "(" + str(warehouse_id[0]) + ")"

        query = ("""select cu.name,count(so.name) from sale_order so JOIN res_partner cu ON so.partner_id = cu.id where so.date_order::DATE >= '%s'::DATE and so.date_order::DATE <= '%s'::DATE and
                           so.state = 'sale' and so.company_id = %s
                           and so.warehouse_id in %s group by so.partner_id,cu.name order by count(so.name) %s""" % (
            from_date, to_date, company_id, warehouse_id, order))

        request.cr.execute(query)
        data = request.cr.fetchall()
        array = []
        try:
            if data:
                for arr in data:
                    array.append({"name": arr[0],"count": arr[1]})
                return valid_response(array)
        except Exception as e:
            return invalid_response('exception', e.name)

        # top selling customer api
        # @validate_token
        @http.route("/api/top/selling/customer", type='http', auth="none", methods=['GET'], csrf=False)
        def top_selling_customer(self, **kwargs):

            data = self.get_filter(**kwargs)
            company_id = data.get('company_id')
            warehouse_id = data.get('warehouse_id')
            from_date = data.get('from_date')
            to_date = data.get('to_date')

            order = 'desc'
            warehouse_id = str(tuple(warehouse_id)) if len(warehouse_id) > 1 else "(" + str(warehouse_id[0]) + ")"

            query = ("""select cu.name,count(so.name) from sale_order so JOIN res_partner cu ON so.partner_id = cu.id where so.date_order::DATE >= '%s'::DATE and so.date_order::DATE <= '%s'::DATE and
                               so.state = 'sale' and so.company_id = %s
                               and so.warehouse_id in %s group by so.partner_id,cu.name order by count(so.name) %s""" % (
                from_date, to_date, company_id, warehouse_id, order))

            request.cr.execute(query)
            data = request.cr.fetchall()
            array = []
            try:
                if data:
                    for arr in data:
                        array.append({"name": arr[0], "count": arr[1]})
                    return valid_response(array)
            except Exception as e:
                return invalid_response('exception', e.name)

    # selling amount total by warehouse
    @validate_token
    @http.route("/api/warehouse/selling/report", type='http', auth="none", methods=['GET'], csrf=False)
    def warehouse_selling_report(self, **kwargs):

        data = self.get_filter(**kwargs)
        company_id = data.get('company_id')
        warehouse_id = data.get('warehouse_id')
        from_date = data.get('from_date')
        to_date = data.get('to_date')
        warehouse_id = str(tuple(warehouse_id)) if len(warehouse_id) > 1 else "(" + str(warehouse_id[0]) + ")"

        print('from_date', from_date)
        print('to_date', to_date)

        query = ("""select warehouse_id,sum(amount_total) from sale_order where date_order::DATE >= '%s'::DATE and date_order::DATE <= '%s'::DATE and
                                       state = 'sale' and company_id = %s
                                       and warehouse_id in %s group by warehouse_id""" % (
            from_date, to_date, company_id, warehouse_id))

        print(query)
        request.cr.execute(query)
        data = request.cr.fetchall()
        array = []
        try:
            if data:
                for arr in data:
                    array.append({"warehouse_id": arr[0], "amount_total": arr[1]})
                return valid_response(array)
        except Exception as e:
            return invalid_response('exception', e.name)





