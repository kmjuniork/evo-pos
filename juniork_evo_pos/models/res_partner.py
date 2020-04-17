from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"

    is_default = fields.Boolean(string='Is Default')

    @api.constrains('is_default')
    def check_default(self):
        if self.search_count([('is_default', '=', True)]) > 1:
            raise ValidationError(_("Default customer should be only one record."))

    def get_default_branch(self):
        return self.search([('is_default', '=', True)], limit=1)