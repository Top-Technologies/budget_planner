# -*- coding: utf-8 -*-
from odoo import models, fields, api

class BudgetFiscalYear(models.Model):
    _name = 'budget.fiscal.year'
    _description = 'Budget Fiscal Year (EFY)'
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Fiscal Year', required=True)
    code = fields.Char(string='Code', required=True)
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    active = fields.Boolean(default=True)
    month_ids = fields.One2many('budget.fiscal.month', 'fiscal_year_id', string='Fiscal Months')

    _code_unique = models.Constraint(
        'unique(code)',
        'Fiscal year code must be unique!',
    )

class BudgetFiscalMonth(models.Model):
    _name = 'budget.fiscal.month'
    _description = 'Budget Fiscal Month'
    _order = 'month_number asc'

    fiscal_year_id = fields.Many2one('budget.fiscal.year', string='Fiscal Year', required=True, ondelete='cascade')
    month_number = fields.Integer(string='Month #', required=True)
    code = fields.Char(string='Month Code', required=True)
    name = fields.Char(string='Month Name', required=True)
    local_name = fields.Char(string='Ethiopian Month Name')
    quarter = fields.Selection([
        ('q1', 'Q1'),
        ('q2', 'Q2'),
        ('q3', 'Q3'),
        ('q4', 'Q4'),
    ], string='Quarter', required=True)
