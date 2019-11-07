import random
from odoo import fields, models, api


class ResUsers(models.Model):
    _inherit = "res.users"

    pin_passwd = fields.Integer(string='PIN', size=6, default=random.randint(100000, 999999))