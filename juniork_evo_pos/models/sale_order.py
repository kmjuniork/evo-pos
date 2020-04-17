from odoo import fields, models, api, _
from datetime import datetime

class EvoSaleOrder(models.Model):
    _inherit = 'sale.order'

    voucher_no = fields.Char(string='Voucher No', size=6)
    table = fields.Char(string='Table')
    round_off = fields.Monetary(string='Round Off', store=True, readonly=True, compute='_amount_all', track_visibility='always')
    employee_id = fields.Many2one('hr.employee', 'Marker', change_default=1, readonly=True, states={'draft': [('readonly', False)]})

    @api.model
    def create(self, values):
        order = super(EvoSaleOrder, self).create(values)
        if self._context.get('auto', False):
            if self._context.get('state') == 'sale':
                order.action_confirm()

                domain = [('origin', '=', order.name)]

                # stock process
                picking = self.env['stock.picking'].search(domain)
                if picking:
                    picking.action_assign()
                    wiz_id = picking.with_context({'pick_id': picking.id, 'active_id': picking.id}).button_validate()[
                        'res_id']
                    self.env['stock.immediate.transfer'].search([('id', '=', wiz_id)]).process()

                # account process
                self.env['sale.advance.payment.inv'].with_context({'active_ids': [order.id], 'active_id': order.id}).create(
                    {}).create_invoices()
                invoice = self.env['account.invoice'].search(domain)
                invoice.action_invoice_open()

                # register payment process
                journal_ids = self.env['account.journal'].search([('type', '=', 'cash')]).mapped('id')
                journal_id = journal_ids[0] if len(journal_ids) else False
                payment_method_ids = self.env['account.journal'].browse(journal_id).mapped('inbound_payment_method_ids.id')

                raw_payment = {
                    'amount': order.amount_total,
                    'journal_id': journal_id,
                    'payment_method_id': payment_method_ids[0] if len(payment_method_ids) else False
                }
                payment = self.env['account.payment'].with_context({'default_invoice_ids': [(4, invoice.id, None)]}).create(
                    raw_payment)
                payment.post()

                order.action_done()
            elif self._context.get('state') == 'cancel':
                order.action_cancel()
        return order

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


    @api.depends('order_line.price_total', 'round_off')
    def _amount_all(self):
        for rec in self:
            res = super(EvoSaleOrder, rec)._amount_all()
            rec.calculate_round_off()
        return res

    @api.multi
    def _prepare_invoice(self):
        for rec in self:
            res = super(EvoSaleOrder, rec)._prepare_invoice()
            res['round_off'] = rec.round_off
        return res


class EvoSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    start_time = fields.Datetime(string="Start Time")
    end_time = fields.Datetime(string="End Time")
    flag = fields.Boolean(string="Flag Status")

    @api.model
    def create(self, vals):
        tax = self.env['account.tax'].search([('type_tax_use', '=', 'sale'), ('active', '=', True)], order='id desc', limit=1)
        if not vals.get('start_time'):
            vals['tax_id'] = [(6, 0, tax.ids)]
        order_lines = super(EvoSaleOrderLine, self).create(vals)
        return order_lines

    @api.onchange('product_id')
    def onchange_product(self):
        if(self.product_id.categ_id.name == 'Table' or self.product_id.categ_id.name == 'Marker'):
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
            self.product_uom_qty = minutes

    @api.one
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        super(EvoSaleOrderLine, self)._compute_amount()
        if self.end_time:
            qty = self.product_uom_qty / 60
            self.price_subtotal = self.price_unit * qty

    @api.multi
    def _prepare_invoice_line(self, qty):
        res = super(EvoSaleOrderLine, self)._prepare_invoice_line(qty)
        if self.end_time:
            res.update({
                'start_time': self.start_time,
                'end_time': self.end_time,
            })
        return res

class EvoSaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    @api.multi
    def _create_invoice(self, order, so_line, amount):
        invoice = super(EvoSaleAdvancePaymentInv, self)._create_invoice(order, so_line, amount)
        if invoice:
            invoice['round_off'] = order.round_off

        return invoice

