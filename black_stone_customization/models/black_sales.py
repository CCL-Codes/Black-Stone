from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import date_utils, email_re, email_split, is_html_empty, groupby



class SalesIncentive(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'sales.incentive'

    @api.model
    def create(self, values):
        values['ref'] = self.env['ir.sequence'].get('sales.incentive') or ' '
        res = super(SalesIncentive, self).create(values)
        return res

    name = fields.Char('Name')
    ref = fields.Char(string='Sequence', default="/", readonly=True)
    request_date = fields.Date(string="Request Date",required=True)
    tot_incentive = fields.Float('Incentive Total',compute='get_tot_incentive',store=True)
    incentive_type = fields.Many2one('incentive.config',string='Incentive Type')
    type_amount = fields.Float(related="incentive_type.amount", string="Amount",required=True)
    note = fields.Text('Note')
    incentive_line_ids = fields.One2many('sales.incentive.line', 'incentive_line_id', string="Incentive")
    date_from = fields.Datetime('Start Date',required=True)
    date_to = fields.Datetime('End Date',required=True)
    state = fields.Selection(
        [('draft', 'To Submit'),
         ('approve', 'Approved'),
         ('done', 'Done'),
         ('refuse', 'Refused')],
        'Status', readonly=True, tracking=True, copy=False,
        help='The status is set to \'To Submit\', when  request is created.\
                      \nThe status is \'Approved\', when request is confirmed by manager.\
                      \nThe status is \'Refused\', when request is refused by manager.\
                      \nThe status is \'Done\', when request is approved by manager.',
        default='draft')

    @api.depends('incentive_line_ids')
    def get_tot_incentive(self):
        for rec in self:
            for record in rec.incentive_line_ids:
                rec.tot_incentive += record.tot_incentive_amount


    def button_draft(self):
        for rec in self:
            rec.state = 'draft'

    def button_approve(self):
        for rec in self:
            rec.state = 'approve'

    def button_done(self):
        for rec in self:
            rec.state = 'done'

    def button_refuse(self):
        for rec in self:
            rec.state = 'refuse'


    def unlink(self):
        for x in self:
            if any(x.filtered(lambda sales_incentive: sales_incentive.state not in ('draft', 'refuse'))):
                raise UserError(_('You cannot delete a Sales incentive which is not draft or refused!'))
            return super(SalesIncentive, x).unlink()


    def get_incentive(self):
        for rec in self:
            sum = 0.0
            sold_qt = 0.0
            incentive_line = self.env['sales.incentive.line']
            partner_ids = self.env['res.partner'].search([])
            for partner in partner_ids:
                sales_ids = self.env['sale.order'].search([('date_order','>=',rec.date_from),('date_order','<=',rec.date_to)
                                                           ,('partner_id','=',partner.id),('state','=','sale')])
                if sales_ids :
                    for sales in sales_ids:
                        sales_line_ids = self.env['sale.order.line'].search(
                            [('order_id', '=', sales.id), ('product_template_id.incentive', '=', True)])
                        for order_line in sales_line_ids:
                            sum += order_line.price_unit
                            sold_qt += order_line.product_uom_qty
                            record = incentive_line.create({
                                'partner_id': sales.partner_id.id,
                                'product_id':order_line.product_template_id.id,
                                'sold_quantity': sold_qt,
                                'tot_invoice_amount': sum,
                                'incentive_line_id':self.id,

                            })
                            print('eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',record)






class SalesIncentiveLine(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'sales.incentive.line'

    incentive_line_id = fields.Many2one('sales.incentive', string="Incentive")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    partner_id = fields.Many2one('res.partner', string="Customer")
    product_id = fields.Many2one('product.template', string="product")
    sold_quantity = fields.Float('Sold Quantity')
    tot_invoice_amount = fields.Float('Total Invoice Amount')
    type_amount = fields.Float(related="incentive_line_id.type_amount", string="Amount")
    tot_incentive_amount = fields.Float('Total Incentive Amount')






class IncentiveConfig(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'incentive.config'

    name = fields.Char('Name',required=True)
    type = fields.Selection([('amount','amount'),('percentage','Percentage')],default='amount',string='Incentive Type')
    amount = fields.Float('Amount',required=True)
    note = fields.Char('Note')
    expence_account = fields.Many2one('account.account')



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    incentive = fields.Boolean(related="product_template_id.incentive",readonly=True,string="Incentive")
    available_qty = fields.Float(related="product_id.qty_available", string="Available QTY", readonly=True)







    # @api.constrains('product_uom_qty', 'available_qty')
    # def qty_constrains(self):
    #     for rec in self:
    #         if rec.product_uom_qty > rec.available_qty:
    #             raise UserError('the quantity is bigger than quantity in stock')

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    stock_number = fields.Char(related="warehouse_id.stock_number",readonly=True, string="Stock Number")


    def action_confirm(self):
        for rec in self:
            print('aml')
            order_line = self.env['sale.order.line'].search([('order_id','=',rec.id)])
            for order in order_line:
                if order.product_uom_qty > order.available_qty:
                    raise UserError('the quantity is bigger than quantity in stock')
                    # self.action_cancel()
        return super(SaleOrder, self).action_confirm()


    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()

        return {
            'ref': self.client_order_ref or '',
            'move_type': 'out_invoice',
            'narration': self.note,
            'currency_id': self.currency_id.id,
            'campaign_id': self.campaign_id.id,
            'medium_id': self.medium_id.id,
            'source_id': self.source_id.id,
            'team_id': self.team_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(self.partner_invoice_id)).id,
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'warehouse_id':self.warehouse_id.id,
            'invoice_user_id': self.user_id.id,
            'payment_reference': self.reference,
            'transaction_ids': [Command.set(self.transaction_ids.ids)],
            'company_id': self.company_id.id,
            'invoice_line_ids': [],
        }


class TotalSalesIncentive(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'total.sales.incentive'

    name = fields.Char('Name')
    ref = fields.Char(string='Sequence', default="/", readonly=True)
    request_date = fields.Date(string="Request Date", required=True,defaullt=fields.Date.today())
    tot_sales = fields.Float('Total Sales order', compute='get_tot_sales', store=True)
    date_from = fields.Datetime('Start Date', required=True)
    date_to = fields.Datetime('End Date', required=True)
    amount = fields.Float(string="Incentive Percentage", required=True)
    tot_incentive = fields.Float('Total incentive', compute='get_tot_sales', store=True)
    note = fields.Text('Note')
    state = fields.Selection(
        [('draft', 'To Submit'),
         ('approve', 'Approved'),
         ('done', 'Done'),
         ('refuse', 'Refused')],
        'Status', readonly=True, tracking=True, copy=False,
        help='The status is set to \'To Submit\', when  request is created.\
                         \nThe status is \'Approved\', when request is confirmed by manager.\
                         \nThe status is \'Refused\', when request is refused by manager.\
                         \nThe status is \'Done\', when request is approved by manager.',
        default='draft')
    department_incen_ids = fields.One2many('total.incentive.department','department_incen_id',string= "Department Incentive")
    job_incen_ids = fields.One2many('total.incentive.job','job_incen_id',string="Job Incentive")
    check_dep = fields.Boolean('Check Department')
    tot_incentive_partner = fields.Float('Total Incentive Partner',compute='get_tot_sales',store=True)




    @api.depends('date_from','date_to')
    def get_tot_sales(self):
        for rec in self:
            sales_ids = self.env['sale.order'].search(
                [('date_order', '>=', rec.date_from), ('date_order', '<=', rec.date_to), ('state', '=', 'sale')])
            rec.tot_sales = sum(sales_ids.mapped('amount_total'))
            rec.tot_incentive = rec.amount * rec.tot_sales
            sales_users_ids = self.env['res.users'].search([])
            for sales_users_id in sales_users_ids:
                part_sales_ids = self.env['sale.order'].search(
                    [('date_order', '>=', rec.date_from), ('date_order', '<=', rec.date_to), ('state', '=', 'sale'),('user_id','=',sales_users_id.id)])
                if part_sales_ids:
                    print('jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj',part_sales_ids)
                    rec.tot_incentive_partner = rec.tot_incentive / sum(part_sales_ids.mapped('amount_total'))



    def get_department_incentive(self):
        for rec in self:
            rec.department_incen_ids.unlink()
            employee_list = []
            job_list = []
            total = 0.0
            total_job = 0.0
            department_ids = self.env['hr.department'].search([('percentage','>',0.0)])
            if department_ids:
                for department in department_ids:
                    total = department.percentage * rec.tot_sales
                    employee_list.append((0, 0, {
                        'department_id': department.id,
                        'percentage': department.percentage,
                        'amount': total
                    }))
                rec.update({'department_incen_ids': employee_list})
                rec.check_dep = True



    def get_job_incentive(self):
        self.job_incen_ids.unlink()
        for rec in self:
            job_list =[]
            total_job = 0.0
            department_ids = self.env['total.incentive.department'].search([])
            for department in department_ids:
                department_id = department.department_id.id
                job_ids = self.env['hr.job'].search([('department_id', '=', department_id), ('percentage', '>', 0.0)])
                if job_ids:
                    for job in job_ids:
                        total_job = job.percentage * department.amount
                        job_list.append((0, 0, {
                            'job_id': job.id,
                            'percentage': job.percentage,
                            'amount': total_job
                        }))
                    rec.update({'job_incen_ids': job_list})


class TotalIncentiveDepartment(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'total.incentive.department'

    department_id = fields.Many2one('hr.department')
    percentage = fields.Float(related="department_id.percentage")
    amount = fields.Float('Amount')
    department_incen_id = fields.Many2one('total.sales.incentive',string="Department Incentive")




class TotalIncentiveJob(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'total.incentive.job'

    job_id = fields.Many2one('hr.job')
    department_id = fields.Many2one(related="job_id.department_id",string="Department",readonly=True)
    percentage = fields.Float(related="job_id.percentage")
    amount = fields.Float('Amount')
    job_incen_id = fields.Many2one('total.sales.incentive',string="job Incentive")

