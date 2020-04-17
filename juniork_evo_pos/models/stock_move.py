# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.addons import decimal_precision as dp


class EvoStockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    previous_qty = fields.Float('Previous Qty', default=0.0, digits=dp.get_precision('Product Unit of Measure'), copy=False)

    @api.model
    def create(self, values):
        res = super(EvoStockMoveLine, self).create(values)
        if res.location_dest_id.usage == 'internal':
            location_id = res.location_dest_id.id
        else:
            location_id = res.location_id.id
        stock_quant_previous_qty = self.env['stock.quant'].search([('product_id', '=', res.product_id.id), ('location_id', '=', location_id)]).quantity
        res.write({'previous_qty': stock_quant_previous_qty})
        return res



