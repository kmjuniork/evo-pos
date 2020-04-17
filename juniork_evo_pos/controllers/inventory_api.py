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


class InventoryAPIController(http.Controller):

    # inventory listing
    @validate_token
    @http.route("/api/stock/picking", type='http', auth="none", methods=['GET'], csrf=False)
    def inventory_listing(self, **kwargs):
        stock_move_lines = request.env['stock.move.line'].sudo().search(
            [('state', '=', 'done')], order='date desc')
        array = []
        for line in stock_move_lines:
            print(line.product_id)
            if line.location_id.barcode == 'WH-STOCK' and line.location_dest_id.barcode == 'SWH-STOCK':
                array.append({
                    "date": line.date,
                    "product_name": line.product_id.name,
                    "product_id": line.product_id.id,
                    "product_tmpl_id": line.product_id.product_tmpl_id.id,
                    "previous_qty": line.previous_qty,
                    "adjust_qty": line.qty_done,
                    "onhand_qty": line.qty_done + line.previous_qty,
                    "reason": 'Stock Received',
                    "stock_move_line_id": line.id,
                })
            elif line.location_id.barcode == 'SWH-STOCK' and line.location_dest_id.usage == 'inventory':
                array.append({
                    "date": line.date,
                    "product_name": line.product_id.name,
                    "product_id": line.product_id.id,
                    "product_tmpl_id": line.product_id.product_tmpl_id.id,
                    "previous_qty": line.previous_qty,
                    "adjust_qty": line.qty_done,
                    "onhand_qty": line.previous_qty - line.qty_done,
                    "reason": line.location_dest_id.name,
                    "stock_move_line_id": line.id,
                })

        return valid_response(array)

    # inventory listing
    @validate_token
    @http.route("/api/create/stock/picking", type='http', auth="none", methods=['POST'], csrf=False)
    def create_stock_picking(self, **kwargs):

        product_id = kwargs.get('product_id')
        reason = kwargs.get('reason')
        adjust_qty = kwargs.get('adjust_qty')

        company_id = request.env.user.company_id.id

        picking_type = request.env['stock.picking.type'].sudo().search(
            [['warehouse_id', '=', 1], ['code', '=', 'internal'], ['active', '=', 't']])

        pro_name = request.env['product.product'].sudo().search([['id', '=', product_id]]).name
        picking_type_id = picking_type.id
        picking_type_code = picking_type.code

        # receive
        if reason == "receive":
            location_id = picking_type.default_location_src_id.id
            location_dest_id = request.env['stock.location'].sudo().search([['barcode', '=', 'SWH-STOCK']]).id
            values = {
                'picking_type_id': picking_type_id,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
                'move_type': 'one',
                'company_id': company_id,
                'priority': '1',
                'picking_type_code': picking_type_code,
                'origin': 'API Transfer',
                'move_lines': [[0, False,
                                {'product_id': product_id,
                                 'product_uom': 1,
                                 'picking_type_id': picking_type_id,
                                 'product_uom_qty': adjust_qty,
                                 'state': 'draft',
                                 'location_id': location_id,
                                 'location_dest_id': location_dest_id,
                                 'name': pro_name}]],
            }
            picking = request.env['stock.picking'].sudo().create(values)
            if picking:
                picking.action_assign()
                wiz_id = picking.with_context({'pick_id': picking.id, 'active_id': picking.id}).button_validate()[
                    'res_id']
                request.env['stock.immediate.transfer'].sudo().search([('id', '=', wiz_id)]).process()
                stock_move_line = request.env['stock.move.line'].sudo().search([('picking_id', '=', picking.id)])
                data = {
                    "date": stock_move_line.date,
                    "product_name": stock_move_line.product_id.name,
                    "product_id": stock_move_line.product_id.id,
                    "product_tmpl_id": stock_move_line.product_id.product_tmpl_id.id,
                    "previous_qty": stock_move_line.previous_qty,
                    "adjust_qty": stock_move_line.qty_done,
                    "onhand_qty": stock_move_line.previous_qty + stock_move_line.qty_done,
                    "reason": 'Stock Received',
                    "stock_move_line_id": stock_move_line.id,
                }
                return valid_response(data)
            else:
                return valid_response({})

        # damage/loss/theft
        else:
            reason_name = reason.capitalize()
            location_id = request.env['stock.location'].sudo().search([['barcode', '=', 'SWH-STOCK']]).id
            scrap_location_id = request.env['stock.location'].sudo().search([['name', '=', reason_name]]).id
            values = {
                'product_id': product_id,
                'scrap_qty': adjust_qty,
                'product_uom_id': 1,
                'location_id': location_id,
                'scrap_location_id': scrap_location_id
            }

            scrap = request.env['stock.scrap'].sudo().create(values)

            if scrap:
                scrap.do_scrap()
                stock_move_line = request.env['stock.move.line'].sudo().search([('move_id', '=', scrap.move_id.id)])
                data = {
                    "date": stock_move_line.date,
                    "product_name": stock_move_line.product_id.name,
                    "product_id": stock_move_line.product_id.id,
                    "product_tmpl_id": stock_move_line.product_id.product_tmpl_id.id,
                    "previous_qty": stock_move_line.previous_qty,
                    "adjust_qty": stock_move_line.qty_done,
                    "onhand_qty": stock_move_line.previous_qty - stock_move_line.qty_done,
                    "reason": stock_move_line.location_dest_id.name,
                    "stock_move_line_id": stock_move_line.id,
                }
                return valid_response(data)
            else:
                return valid_response({})
