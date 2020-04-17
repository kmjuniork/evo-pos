# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import UserError


class EvoAccountInvoice(models.Model):
    _inherit = "account.invoice"

    round_off = fields.Monetary(string='Round Off', store=True, readonly=True, compute='_compute_amount', track_visibility='always')

    @api.multi
    def calculate_round_off(self):
        for rec in self:
            round_off = 0.0;
            amount_total = self.amount_total
            subtotal = amount_total % 50
            if subtotal == 0:
                round_off = 0.0
            elif subtotal < 25:
                round_off = -subtotal
            elif subtotal >= 25 and subtotal < 50:
                round_off = (50 - subtotal)
            elif subtotal >= 50 and subtotal < 75:
                round_off = -subtotal
            else:
                round_off = (50 - subtotal)
            rec.round_off = round_off
            rec.amount_total = rec.round_off + rec.amount_total


    @api.multi
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
                 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        for rec in self:
            res = super(EvoAccountInvoice, rec)._compute_amount()
            rec.calculate_round_off()
            sign = rec.type in ['in_refund', 'out_refund'] and -1 or 1
            rec.amount_total_company_signed = rec.amount_total * sign
            rec.amount_total_signed = rec.amount_total * sign
        return res


    @api.model
    def invoice_line_move_line_get(self):
        res = super(EvoAccountInvoice, self).invoice_line_move_line_get()
        if self.round_off != 0 and (self.type == "out_invoice" or self.type == "out_refund"):
            acc_id = self.env['ir.config_parameter'].sudo().get_param('roundoff.round_off_account')
            if not acc_id:
                raise UserError(_('Please configure Round Off Account in Account Setting.'))
            dict = {
                'invl_id': self.number,
                'type': 'src',
                'name': 'Round Off',
                'price': self.round_off,
                'account_id': int(acc_id),
                'invoice_id': self.id,
            }
            res.append(dict)
        return res



class EvoAccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    start_time = fields.Datetime(string="Start Time")
    end_time = fields.Datetime(string="End Time")
    flag = fields.Boolean(string="Flag Status")

    @api.onchange('product_id')
    def onchange_product(self):
        if (self.product_id.categ_id.name == 'Table'):
            self.flag = True
            self.start_time = datetime.now()

    @api.onchange('end_time')
    def onchange_time(self):
        if self.end_time:
            difference = self.end_time - self.start_time
            seconds_in_day = 24 * 60 * 60
            # returns(minutes, seconds)
            minutes = divmod(difference.days * seconds_in_day + difference.seconds, 60)
            minutes = minutes[0]
            self.quantity = minutes

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
                 'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
                 'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        super(EvoAccountInvoiceLine, self)._compute_price()
        if self.end_time:
            qty = self.quantity / 60
            self.price_subtotal = self.price_unit * qty
