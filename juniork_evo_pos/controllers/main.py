import functools
import logging
from odoo import http
from odoo.http import request
from odoo.addons.restful.common import valid_response, invalid_response, extract_arguments, extract_value

_logger = logging.getLogger(__name__)


def validate_token(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
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

    @validate_token
    @http.route("/api/profit/loss/report/", type='http', auth="none", methods=['GET'], csrf=False)
    def get(self, **payload):
        data = {'used_context': {'journal_ids': False, 'state': 'posted', 'date_from': False, 'date_to': False, 'strict_range': True, 'company_id': 1, 'lang': 'en_US'}}
        if payload.get('date_from'):
            data['used_context']['date_from'] = payload['date_from']
        if payload.get('date_to'):
            data['used_context']['date_to'] = payload['date_to']
        print(data)
        lines = []
        account_report = request.env['account.financial.report'].sudo().search([('id', '=', 1)])
        child_reports = account_report.sudo()._get_children_by_order()
        res = request.env['report.accounting_pdf_reports.report_financial'].sudo().with_context(data.get('used_context'))._compute_report_balance(child_reports)
        for report in child_reports:
            vals = {
                'name': report.name,
                'balance': res[report.id]['balance'] * report.sign,
                'type': 'report',
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type or False, #used to underline the financial report balances
            }

            lines.append(vals)
            if report.display_detail == 'no_detail':
                #the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue

            if res[report.id].get('account'):
                sub_lines = []
                for account_id, value in res[report.id]['account'].items():
                    #if there are accounts to display, we add them to the lines with a level equals to their level in
                    #the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
                    #financial reports for Assets, liabilities...)
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



