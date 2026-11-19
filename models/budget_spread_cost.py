# -*- coding: utf-8 -*-
from odoo import models, fields, api

class BudgetSpreadCost(models.Model):
    _name = 'budget.spread.cost'
    _description = 'Budget Direct Cost 12-Month Spread'
    _order = 'cost_type asc'

    project_id = fields.Many2one('budget.plan.project', string='Project', required=True, ondelete='cascade')
    plan_id = fields.Many2one('budget.plan', string='Budget Plan', related='project_id.plan_id', store=True)
    department_id = fields.Many2one('hr.department', string='Department', related='project_id.department_id', store=True)

    cost_type = fields.Selection([
        ('stock', 'Materials (Stock)'),
        ('local', 'Materials (Local Purchase)'),
        ('import', 'Materials (Import Purchase)'),
        ('other', 'Other Direct Costs'),
    ], string='Cost Type', required=True)

    payment_offset = fields.Integer(
        string='Payment Offset (Months)',
        default=0,
        help='Shift in cash payment month relative to accrual month (e.g. -2 means cash is paid 2 months earlier).'
    )

    planned_amount = fields.Float(string='Planned Cost (\'000)', compute='_compute_amounts', store=True, digits=(16, 2), default=0.0)

    # Monthly Cost Amounts in ETB '000 (Directly Editable by User)
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

    # Cash Payment Amounts (Shifted by offset, Stock = 0)
    cash_m01 = fields.Float(string='Pay Jul', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_m02 = fields.Float(string='Pay Aug', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_m03 = fields.Float(string='Pay Sep', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_q1 = fields.Float(string='Pay Q1', compute='_compute_amounts', store=True, digits=(16, 2))

    cash_m04 = fields.Float(string='Pay Oct', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_m05 = fields.Float(string='Pay Nov', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_m06 = fields.Float(string='Pay Dec', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_q2 = fields.Float(string='Pay Q2', compute='_compute_amounts', store=True, digits=(16, 2))

    cash_m07 = fields.Float(string='Pay Jan', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_m08 = fields.Float(string='Pay Feb', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_m09 = fields.Float(string='Pay Mar', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_q3 = fields.Float(string='Pay Q3', compute='_compute_amounts', store=True, digits=(16, 2))

    cash_m10 = fields.Float(string='Pay Apr', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_m11 = fields.Float(string='Pay May', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_m12 = fields.Float(string='Pay Jun', compute='_compute_amounts', store=True, digits=(16, 2))
    cash_q4 = fields.Float(string='Pay Q4', compute='_compute_amounts', store=True, digits=(16, 2))

    cash_annual_total = fields.Float(string='Cash Annual Total', compute='_compute_amounts', store=True, digits=(16, 2))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'planned_amount' in vals and vals['planned_amount'] > 0:
                has_month_amount = any(vals.get(f'm{i:02d}') for i in range(1, 13))
                if not has_month_amount:
                    amt = vals['planned_amount']
                    for i in range(1, 13):
                        pct_key = f'm{i:02d}_pct'
                        if pct_key in vals:
                            vals[f'm{i:02d}'] = amt * (vals[pct_key] / 100.0)
        return super().create(vals_list)

    def write(self, vals):
        if ('planned_amount' in vals or any(f'm{i:02d}_pct' in vals for i in range(1, 13))) and not any(f'm{i:02d}' in vals for i in range(1, 13)):
            for rec in self:
                amt = vals.get('planned_amount', rec.planned_amount)
                if amt > 0:
                    for i in range(1, 13):
                        pct_key = f'm{i:02d}_pct'
                        if pct_key in vals:
                            vals[f'm{i:02d}'] = amt * (vals[pct_key] / 100.0)
        return super().write(vals)

    @api.depends(
        'cost_type', 'payment_offset',
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
            rec.planned_amount = ann_tot

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

            # Cash payments calculation:
            # If stock -> zero cash outflow
            if rec.cost_type == 'stock':
                rec.cash_m01 = rec.cash_m02 = rec.cash_m03 = rec.cash_q1 = 0.0
                rec.cash_m04 = rec.cash_m05 = rec.cash_m06 = rec.cash_q2 = 0.0
                rec.cash_m07 = rec.cash_m08 = rec.cash_m09 = rec.cash_q3 = 0.0
                rec.cash_m10 = rec.cash_m11 = rec.cash_m12 = rec.cash_q4 = 0.0
                rec.cash_annual_total = 0.0
            else:
                offset = rec.payment_offset or 0
                cash_buckets = [0.0] * 12
                accrual_vals = [
                    rec.m01, rec.m02, rec.m03, rec.m04, rec.m05, rec.m06,
                    rec.m07, rec.m08, rec.m09, rec.m10, rec.m11, rec.m12
                ]
                for idx, cost_val in enumerate(accrual_vals, start=1):
                    target_m = idx + offset
                    if target_m < 1:
                        # Lead time falls at or before start of year -> allocate to M01
                        cash_buckets[0] += cost_val
                    elif target_m <= 12:
                        cash_buckets[target_m - 1] += cost_val
                    # If target_m > 12, falls into next fiscal year

                rec.cash_m01 = cash_buckets[0]
                rec.cash_m02 = cash_buckets[1]
                rec.cash_m03 = cash_buckets[2]
                rec.cash_q1 = rec.cash_m01 + rec.cash_m02 + rec.cash_m03

                rec.cash_m04 = cash_buckets[3]
                rec.cash_m05 = cash_buckets[4]
                rec.cash_m06 = cash_buckets[5]
                rec.cash_q2 = rec.cash_m04 + rec.cash_m05 + rec.cash_m06

                rec.cash_m07 = cash_buckets[6]
                rec.cash_m08 = cash_buckets[7]
                rec.cash_m09 = cash_buckets[8]
                rec.cash_q3 = rec.cash_m07 + rec.cash_m08 + rec.cash_m09

                rec.cash_m10 = cash_buckets[9]
                rec.cash_m11 = cash_buckets[10]
                rec.cash_m12 = cash_buckets[11]
                rec.cash_q4 = rec.cash_m10 + rec.cash_m11 + rec.cash_m12

                rec.cash_annual_total = rec.cash_q1 + rec.cash_q2 + rec.cash_q3 + rec.cash_q4
