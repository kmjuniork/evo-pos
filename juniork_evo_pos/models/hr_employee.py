from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class Employee(models.Model):
    _inherit = "hr.employee"

    is_default = fields.Boolean(string="Is Default")
    date_join = fields.Date(string="Join Date")
    date_termination = fields.Date(string="Termination Date")
    work_shift = fields.Selection([('day', 'Day'), ('night', 'Night')], default='day')

    @api.constrains('is_default')
    def check_default(self):
        if self.search_count([('is_default', '=', True)]) > 1:
            raise ValidationError(_("Default customer should be only one record."))

    def get_default_branch(self):
        return self.search([('is_default', '=', True)], limit=1)

