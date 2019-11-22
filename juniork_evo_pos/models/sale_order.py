from odoo import fields, models, api, _


class EvoSaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def create(self, values):
        order = super(EvoSaleOrder, self).create(values)
        if self._context.get('auto', False):
            order.action_confirm()

            domain = [('origin', '=', order.name)]

            # stock process
            picking = self.env['stock.picking'].search(domain)
            picking.action_assign()
            wiz_id = picking.with_context({'pick_id': picking.id, 'active_id': picking.id}).button_validate()['res_id']
            self.env['stock.immediate.transfer'].search([('id', '=', wiz_id)]).process()

            # account process
            self.env['sale.advance.payment.inv'].with_context({'active_ids': [order.id], 'active_id': order.id}).create({}).create_invoices()
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
            payment = self.env['account.payment'].with_context({'default_invoice_ids': [(4, invoice.id, None)]}).create(raw_payment)
            payment.post()

            order.action_done()

        return order