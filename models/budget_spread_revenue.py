# -*- coding: utf-8 -*-
from odoo import models, fields, api

class BudgetSpreadRevenue(models.Model):
    _name = 'budget.spread.revenue'
    _description = 'Budget Revenue 12-Month Accrual Spread'

    project_id = fields.Many2one('budget.plan.project', string='Project', required=True, ondelete='cascade')
    plan_id = fields.Many2one('budget.plan', string='Budget Plan', related='project_id.plan_id', store=True)
    department_id = fields.Many2one('hr.department', string='Department', related='project_id.department_id', store=True)

    # Monthly Amounts in ETB '000 (Directly Editable by User)
    m01 = fields.Float(string='Jul', digits=(16, 2), default=0.0)
    m02 = fields.Float(string='Aug', digits=(16, 2), default=0.0)
    m03 = fields.Float(string='Sep', digits=(16, 2), default=0.0)
    q1 = fields.Float(string='Q1', compute='_compute_amounts', store=True, digits=(16, 2))

    m04 = fields.Float(string='Oct', digits=(16, 2), default=0.0)
    m05 = fields.Float(string='Nov', digits=(16, 2), default=0.0)
    m06 = fields.Float(string='Dec', digits=(16, 2), default=0.0)
    q2 = fields.Float(string='Q2', compute='_compute_amounts', store=True, digits=(16, 2))

    m07 = fields.Float(string='Jan', digits=(16, 2), default=0.0)
    m08 = fields.Float(string='Feb', digits=(16, 2), default=0.0)
    m09 = fields.Float(string='Mar', digits=(16, 2), default=0.0)
    q3 = fields.Float(string='Q3', compute='_compute_amounts', store=True, digits=(16, 2))

    m10 = fields.Float(string='Apr', digits=(16, 2), default=0.0)
    m11 = fields.Float(string='May', digits=(16, 2), default=0.0)
    m12 = fields.Float(string='Jun', digits=(16, 2), default=0.0)
    q4 = fields.Float(string='Q4', compute='_compute_amounts', store=True, digits=(16, 2))

    annual_total = fields.Float(string='Annual Total', compute='_compute_amounts', store=True, digits=(16, 2))
    first_revenue_month = fields.Integer(string='1st Revenue Month', compute='_compute_amounts', store=True)

    # Monthly % shares (Computed automatically from amounts)
    m01_pct = fields.Float(string='Jul %', compute='_compute_amounts', store=True, digits=(16, 2))
    m02_pct = fields.Float(string='Aug %', compute='_compute_amounts', store=True, digits=(16, 2))
    m03_pct = fields.Float(string='Sep %', compute='_compute_amounts', store=True, digits=(16, 2))
    m04_pct = fields.Float(string='Oct %', compute='_compute_amounts', store=True, digits=(16, 2))
    m05_pct = fields.Float(string='Nov %', compute='_compute_amounts', store=True, digits=(16, 2))
    m06_pct = fields.Float(string='Dec %', compute='_compute_amounts', store=True, digits=(16, 2))
    m07_pct = fields.Float(string='Jan %', compute='_compute_amounts', store=True, digits=(16, 2))
    m08_pct = fields.Float(string='Feb %', compute='_compute_amounts', store=True, digits=(16, 2))
    m09_pct = fields.Float(string='Mar %', compute='_compute_amounts', store=True, digits=(16, 2))
    m10_pct = fields.Float(string='Apr %', compute='_compute_amounts', store=True, digits=(16, 2))
    m11_pct = fields.Float(string='May %', compute='_compute_amounts', store=True, digits=(16, 2))
    m12_pct = fields.Float(string='Jun %', compute='_compute_amounts', store=True, digits=(16, 2))
    total_pct = fields.Float(string='Total %', compute='_compute_amounts', store=True, digits=(16, 2))
    is_valid = fields.Boolean(string='Valid', compute='_compute_amounts', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(vals.get(f'm{i:02d}_pct') for i in range(1, 13)) and not any(vals.get(f'm{i:02d}') for i in range(1, 13)):
                proj = self.env['budget.plan.project'].browse(vals.get('project_id'))
                rev = proj.revenue_planned if proj else 0.0
                if rev > 0:
                    for i in range(1, 13):
                        pct_key = f'm{i:02d}_pct'
                        if pct_key in vals:
                            vals[f'm{i:02d}'] = rev * (vals[pct_key] / 100.0)
        return super().create(vals_list)

    def write(self, vals):
        if any(f'm{i:02d}_pct' in vals for i in range(1, 13)) and not any(f'm{i:02d}' in vals for i in range(1, 13)):
            for rec in self:
                rev = rec.project_id.revenue_planned or 0.0
                if rev > 0:
                    for i in range(1, 13):
                        pct_key = f'm{i:02d}_pct'
                        if pct_key in vals:
                            vals[f'm{i:02d}'] = rev * (vals[pct_key] / 100.0)
        return super().write(vals)

    @api.depends(
        'm01', 'm02', 'm03', 'm04', 'm05', 'm06',
        'm07', 'm08', 'm09', 'm10', 'm11', 'm12'
    )
    def _compute_amounts(self):
        for rec in self:
            rec.q1 = rec.m01 + rec.m02 + rec.m03
            rec.q2 = rec.m04 + rec.m05 + rec.m06
            rec.q3 = rec.m07 + rec.m08 + rec.m09
            rec.q4 = rec.m10 + rec.m11 + rec.m12
            ann_tot = rec.q1 + rec.q2 + rec.q3 + rec.q4
            rec.annual_total = ann_tot

            if ann_tot > 0:
                rec.m01_pct = (rec.m01 / ann_tot) * 100.0
                rec.m02_pct = (rec.m02 / ann_tot) * 100.0
                rec.m03_pct = (rec.m03 / ann_tot) * 100.0
                rec.m04_pct = (rec.m04 / ann_tot) * 100.0
                rec.m05_pct = (rec.m05 / ann_tot) * 100.0
                rec.m06_pct = (rec.m06 / ann_tot) * 100.0
                rec.m07_pct = (rec.m07 / ann_tot) * 100.0
                rec.m08_pct = (rec.m08 / ann_tot) * 100.0
                rec.m09_pct = (rec.m09 / ann_tot) * 100.0
                rec.m10_pct = (rec.m10 / ann_tot) * 100.0
                rec.m11_pct = (rec.m11 / ann_tot) * 100.0
                rec.m12_pct = (rec.m12 / ann_tot) * 100.0
                rec.total_pct = 100.0
                rec.is_valid = True
            else:
                rec.m01_pct = rec.m02_pct = rec.m03_pct = 0.0
                rec.m04_pct = rec.m05_pct = rec.m06_pct = 0.0
                rec.m07_pct = rec.m08_pct = rec.m09_pct = 0.0
                rec.m10_pct = rec.m11_pct = rec.m12_pct = 0.0
                rec.total_pct = 0.0
                rec.is_valid = True

            # Detect first non-zero revenue month (1..12)
            first_m = 0
            month_vals = [
                rec.m01, rec.m02, rec.m03, rec.m04, rec.m05, rec.m06,
                rec.m07, rec.m08, rec.m09, rec.m10, rec.m11, rec.m12
            ]
            for idx, val in enumerate(month_vals, start=1):
                if val > 0.001:
                    first_m = idx
                    break
            rec.first_revenue_month = first_m
