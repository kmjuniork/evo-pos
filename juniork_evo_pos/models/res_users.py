import random
from odoo import fields, models, api



class ResUsers(models.Model):
    _inherit = "res.users"

    pin_passwd = fields.Integer(string='PIN', size=6, default=lambda self: random.randint(100000, 999999))

    _sql_constraints = [('pin_passwd_unique', 'unique(pin_passwd)', 'Choose another value - it has to be unique pos pin!')]



    @api.model
    def create(self, vals):
        if vals.get('login_user', False):
            vals['login'] = vals.get('login_user', False)
        res = super(ResUsers, self).create(vals)
        return res