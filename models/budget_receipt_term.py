# -*- coding: utf-8 -*-
from odoo import models, fields, api

class BudgetReceiptTerm(models.Model):
    _name = 'budget.receipt.term'
    _description = 'Budget Cash Receipt Payment Term'
    _order = 'month_index asc, id asc'

    project_id = fields.Many2one('budget.plan.project', string='Project', required=True, ondelete='cascade')
    plan_id = fields.Many2one('budget.plan', string='Budget Plan', related='project_id.plan_id', store=True)
    department_id = fields.Many2one('hr.department', string='Department', related='project_id.department_id', store=True)

    term_type = fields.Selection([
        ('monthly_sales', 'Monthly Sales'),
        ('advance', 'Advance Payment'),
        ('progress_1', 'Progress 1'),
        ('progress_2', 'Progress 2'),
        ('progress_3', 'Progress 3'),
        ('progress_4', 'Progress 4'),
        ('final', 'Final Payment'),
    ], string='Payment Term', required=True)

    month = fields.Selection([
        ('1', 'M01 - Jul'),
        ('2', 'M02 - Aug'),
        ('3', 'M03 - Sep'),
        ('4', 'M04 - Oct'),
        ('5', 'M05 - Nov'),
        ('6', 'M06 - Dec'),
        ('7', 'M07 - Jan'),
        ('8', 'M08 - Feb'),
        ('9', 'M09 - Mar'),
        ('10', 'M10 - Apr'),
        ('11', 'M11 - May'),
        ('12', 'M12 - Jun'),
    ], string='Receipt Month', required=True, default='1')

    month_index = fields.Integer(string='Month Index', compute='_compute_month_index', store=True)

    gross_amount = fields.Float(string='Gross Receipt (\'000)', digits=(16, 2), default=0.0)
    pct_contract = fields.Float(string='% of Contract', digits=(16, 2), default=0.0)
    wht_rate = fields.Float(string='WHT %', related='project_id.wht_rate', store=True)

    wht_amount = fields.Float(string='WHT Deducted (\'000)', compute='_compute_amounts', store=True, digits=(16, 2))
    net_amount = fields.Float(string='Net Receipt (\'000)', compute='_compute_amounts', store=True, digits=(16, 2))

    @api.depends('month')
    def _compute_month_index(self):
        for rec in self:
            rec.month_index = int(rec.month or 1)

    @api.onchange('gross_amount')
    def _onchange_gross_amount(self):
        contract_val = self.project_id.contract_value or 0.0
        if contract_val > 0 and self.gross_amount:
            self.pct_contract = (self.gross_amount / contract_val) * 100.0
        wht_rate = self.wht_rate or 0.0
        self.wht_amount = (self.gross_amount or 0.0) * (wht_rate / 100.0)
        self.net_amount = (self.gross_amount or 0.0) - self.wht_amount

    @api.onchange('pct_contract')
    def _onchange_pct_contract(self):
        contract_val = self.project_id.contract_value or 0.0
        if contract_val > 0 and self.pct_contract:
            self.gross_amount = contract_val * (self.pct_contract / 100.0)
        wht_rate = self.wht_rate or 0.0
        self.wht_amount = (self.gross_amount or 0.0) * (wht_rate / 100.0)
        self.net_amount = (self.gross_amount or 0.0) - self.wht_amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            proj = self.env['budget.plan.project'].browse(vals.get('project_id'))
            contract_val = proj.contract_value if proj else 0.0
            if vals.get('gross_amount') and contract_val > 0:
                if not vals.get('pct_contract'):
                    vals['pct_contract'] = (vals['gross_amount'] / contract_val) * 100.0
            elif vals.get('pct_contract') and contract_val > 0:
                if not vals.get('gross_amount'):
                    vals['gross_amount'] = contract_val * (vals['pct_contract'] / 100.0)
        return super().create(vals_list)

    def write(self, vals):
        if 'gross_amount' in vals and 'pct_contract' not in vals:
            for rec in self:
                contract_val = rec.project_id.contract_value or 0.0
                if contract_val > 0:
                    vals['pct_contract'] = (vals['gross_amount'] / contract_val) * 100.0
        elif 'pct_contract' in vals and 'gross_amount' not in vals:
            for rec in self:
                contract_val = rec.project_id.contract_value or 0.0
                if contract_val > 0:
                    vals['gross_amount'] = contract_val * (vals['pct_contract'] / 100.0)
        return super().write(vals)

    @api.depends('gross_amount', 'wht_rate')
    def _compute_amounts(self):
        for rec in self:
            gross = rec.gross_amount or 0.0
            wht_pct = rec.wht_rate or 0.0
            wht = gross * (wht_pct / 100.0)
            rec.wht_amount = wht
            rec.net_amount = gross - wht
