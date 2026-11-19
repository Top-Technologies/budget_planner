# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class BudgetPlanProject(models.Model):
    _name = 'budget.plan.project'
    _description = 'Budget Plan Project Headline & Spreads'
    _order = 'department_id, status_group, code, name'

    plan_id = fields.Many2one('budget.plan', string='Budget Plan', required=True, ondelete='cascade', index=True)
    plan_state = fields.Selection(related='plan_id.state', string='Plan Status', store=True)
    fiscal_year_id = fields.Many2one(related='plan_id.fiscal_year_id', string='Fiscal Year', store=True)

    code = fields.Char(string='Project Ref / Code')
    name = fields.Char(string='Project Description / Title', required=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True, index=True)
    category_id = fields.Many2one('budget.category', string='Category', required=True)
    is_stock_sales = fields.Boolean(related='category_id.is_stock_sales', string='Is Stock Sales', store=True)
    client_id = fields.Many2one('res.partner', string='Client')

    status_group = fields.Selection([
        ('pipeline', 'Pipeline'),
        ('committed', 'Committed'),
        ('pbf', 'PBF'),
    ], string='Status Group', required=True, default='pipeline')

    pipeline_substatus = fields.Selection([
        ('planning', 'Planning'),
        ('bidding', 'Bidding'),
        ('on_hold', 'On Hold'),
    ], string='Pipeline Sub-Status', default='planning')

    # Headline figures (in ETB '000)
    contract_value = fields.Float(string='Contract Value (\'000)', digits=(16, 2), default=0.0)
    wht_rate = fields.Float(string='WHT Rate %', digits=(16, 2), default=2.0)
    vat_rate = fields.Float(string='VAT Rate %', digits=(16, 2), default=15.0)

    revenue_planned = fields.Float(
        string='Planned Revenue (\'000)',
        compute='_compute_revenue_planned',
        store=True,
        readonly=False,
        digits=(16, 2),
        default=0.0
    )
    direct_costs_planned = fields.Float(
        string='Planned Direct Costs (\'000)',
        compute='_compute_direct_costs_planned',
        store=True,
        readonly=False,
        digits=(16, 2),
        default=0.0
    )

    gross_margin = fields.Float(string='Gross Margin (\'000)', compute='_compute_headline_kpis', store=True, digits=(16, 2))
    margin_pct = fields.Float(string='Margin %', compute='_compute_headline_kpis', store=True, digits=(16, 2))

    cash_in_planned = fields.Float(string='Cash In (\'000)', compute='_compute_headline_kpis', store=True, digits=(16, 2))
    cash_out_planned = fields.Float(string='Cash Out (\'000)', compute='_compute_headline_kpis', store=True, digits=(16, 2))
    net_cash_planned = fields.Float(string='Net Cash (\'000)', compute='_compute_headline_kpis', store=True, digits=(16, 2))

    # Child Spreads
    revenue_spread_ids = fields.One2many('budget.spread.revenue', 'project_id', string='Revenue Spread', copy=False)
    cost_spread_ids = fields.One2many('budget.spread.cost', 'project_id', string='Cost Spreads', copy=False)
    receipt_term_ids = fields.One2many('budget.receipt.term', 'project_id', string='Cash Receipt Terms', copy=False)

    # Spread Validation Status
    revenue_spread_valid = fields.Boolean(compute='_compute_spread_validations', store=True, string='Revenue 100% Valid')
    costs_spread_valid = fields.Boolean(compute='_compute_spread_validations', store=True, string='Costs 100% Valid')

    @api.depends('revenue_spread_ids.annual_total')
    def _compute_revenue_planned(self):
        for rec in self:
            spread_rev = sum(rec.revenue_spread_ids.mapped('annual_total'))
            if spread_rev > 0:
                rec.revenue_planned = spread_rev
            elif not rec.revenue_planned:
                rec.revenue_planned = 0.0

    @api.depends('cost_spread_ids.annual_total')
    def _compute_direct_costs_planned(self):
        for rec in self:
            spread_costs = sum(rec.cost_spread_ids.mapped('annual_total'))
            if spread_costs > 0:
                rec.direct_costs_planned = spread_costs
            elif not rec.direct_costs_planned:
                rec.direct_costs_planned = 0.0

    @api.depends('revenue_planned', 'direct_costs_planned', 'contract_value', 'wht_rate',
                 'receipt_term_ids.net_amount', 'cost_spread_ids.cash_annual_total')
    def _compute_headline_kpis(self):
        for rec in self:
            rev = rec.revenue_planned or 0.0
            cost = rec.direct_costs_planned or 0.0
            gm = rev - cost
            rec.gross_margin = gm
            rec.margin_pct = (gm / rev * 100.0) if rev else 0.0

            # Cash in: from receipt terms if entered, otherwise default from contract value net of WHT
            if rec.receipt_term_ids:
                cash_in = sum(rec.receipt_term_ids.mapped('net_amount'))
            else:
                base_val = rec.contract_value or rev
                wht = rec.wht_rate or 0.0
                cash_in = base_val * (1.0 - wht / 100.0)
            rec.cash_in_planned = cash_in

            # Cash out: sum of shifted cash payments from cost spreads
            cash_out = sum(rec.cost_spread_ids.mapped('cash_annual_total'))
            rec.cash_out_planned = cash_out

            rec.net_cash_planned = cash_in - cash_out

    @api.depends('revenue_spread_ids.is_valid', 'cost_spread_ids.is_valid')
    def _compute_spread_validations(self):
        for rec in self:
            rec.revenue_spread_valid = all(rec.revenue_spread_ids.mapped('is_valid')) if rec.revenue_spread_ids else False
            rec.costs_spread_valid = all(rec.cost_spread_ids.mapped('is_valid')) if rec.cost_spread_ids else False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Auto-create revenue spread if missing
            if not rec.revenue_spread_ids:
                self.env['budget.spread.revenue'].create({
                    'project_id': rec.id,
                })
            # Auto-create standard 4 cost lines if missing
            if not rec.cost_spread_ids:
                default_costs = [
                    {'cost_type': 'stock', 'payment_offset': 0},
                    {'cost_type': 'local', 'payment_offset': 0},
                    {'cost_type': 'import', 'payment_offset': -2},
                    {'cost_type': 'other', 'payment_offset': 0},
                ]
                for c in default_costs:
                    self.env['budget.spread.cost'].create({
                        'project_id': rec.id,
                        'cost_type': c['cost_type'],
                        'payment_offset': c['payment_offset'],
                        'planned_amount': 0.0,
                    })
        return records
