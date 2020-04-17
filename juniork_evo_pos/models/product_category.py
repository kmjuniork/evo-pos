# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EvoProductCategory(models.Model):
    _inherit = "product.category"

    category_type = fields.Selection([('table', 'Table'), ('marker', 'Marker')], string="Category Type")