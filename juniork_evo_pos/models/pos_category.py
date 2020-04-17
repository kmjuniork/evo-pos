# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools, _

class PosCategory(models.Model):
    _inherit = "pos.category"

    image_path = fields.Char(string='Image Path', readonly=True)

    def get_url(self, model, id):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/web/image/' + model + '/' + str(id) + '/image'
        return url

    @api.model
    def create(self, values):
        res = super(PosCategory, self).create(values)
        # image path in file instead of binary code.
        if values.get('image_medium'):
            url = self.get_url('pos.category', res.id)
            res.write({'image_path': url})
        return res

    @api.multi
    def write(self, values):
        res = super().write(values)
        if values.get('image_medium'):
            url = self.get_url('pos.category', self.id)
            self.write({'image_path': url})
        return res
