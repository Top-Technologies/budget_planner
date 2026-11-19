# -*- coding: utf-8 -*-
from odoo import models, fields

class BudgetCategory(models.Model):
    _name = 'budget.category'
    _description = 'Budget Project Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(string='Sequence', default=10)
    is_stock_sales = fields.Boolean(
        string='Stock Sales',
        default=False,
        help='Mark as Stock Sales. These rows will be badged [Sales] in the Orders Received report.'
    )
    active = fields.Boolean(default=True)
