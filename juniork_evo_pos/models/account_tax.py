# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
from datetime import datetime

class EvoAccountTax(models.Model):
    _inherit = 'account.tax'

    date_start = fields.Date(string='Start Date', required=True, default=lambda self: self._context.get('date', fields.Date.context_today(self)))
    date_end = fields.Date(string='End Date')

    @api.model
    def create(self, vals):
        if vals.get('type_tax_use') == 'sale':
            taxes = self.env['account.tax'].search([('type_tax_use', '=', 'sale'), ('active', '=', True)])
            for tax in taxes:
                tax.write({'date_end': datetime.now(), 'active': 0})
        account_tax = super(EvoAccountTax, self).create(vals)
        return account_tax


