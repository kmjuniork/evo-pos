import random
from odoo import fields, models, api



class ResUsers(models.Model):
    _inherit = "res.users"

    pin_passwd = fields.Integer(string='PIN', size=6, default=lambda self: random.randint(100000, 999999))

    _sql_constraints = [('pin_passwd_unique', 'unique(pin_passwd)', 'Choose another value - it has to be unique pos pin!')]