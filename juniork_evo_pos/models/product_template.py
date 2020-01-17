# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import itertools

from odoo.addons import decimal_precision as dp

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, UserError
from odoo.osv import expression
from odoo.tools import pycompat


class ProductTemplate(models.Model):
    _inherit = "product.template"

    image_path = fields.Char(string='Image Path', readonly=True)

    def get_url(self, model, id):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/web/image/' + model + '/' + str(id) + '/image'
        return  url

    @api.model
    def create(self, values):
        res = super(ProductTemplate, self).create(values)
        # image path in file instead of binary code.
        if values.get('image_medium'):
            url = self.get_url('product.template', res.id)
            res.write({'image_path': url})
        return res


