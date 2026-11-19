# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class BudgetPlan(models.Model):
    _name = 'budget.plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Annual Budget & Earnings Plan'
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Plan Title', required=True, copy=False, tracking=True, default=lambda self: _('New Plan'))
    code = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    fiscal_year_id = fields.Many2one('budget.fiscal.year', string='Fiscal Year (EFY)', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id')

    version = fields.Float(string='Version', default=1.0, digits=(16, 1), tracking=True)
    parent_id = fields.Many2one('budget.plan', string='Previous Version / Baseline', readonly=True, copy=False)
    revision_ids = fields.One2many('budget.plan', 'parent_id', string='Plan Revisions')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('locked', 'Locked'),
    ], string='Status', default='draft', tracking=True, required=True)

    project_ids = fields.One2many('budget.plan.project', 'plan_id', string='Project Plans')
    project_count = fields.Integer(string='Projects Count', compute='_compute_plan_aggregates', store=True)

    notes = fields.Text(string='Internal Notes')

    # Aggregated Financial Metrics (in ETB '000)
    total_contract_value = fields.Float(string='Total Contract Value (\'000)', compute='_compute_plan_aggregates', store=True, digits=(16, 2))
    total_revenue = fields.Float(string='Total Planned Revenue (\'000)', compute='_compute_plan_aggregates', store=True, digits=(16, 2))
    total_direct_costs = fields.Float(string='Total Direct Costs (\'000)', compute='_compute_plan_aggregates', store=True, digits=(16, 2))
    total_gross_margin = fields.Float(string='Gross Margin (\'000)', compute='_compute_plan_aggregates', store=True, digits=(16, 2))
    margin_pct = fields.Float(string='Overall Margin %', compute='_compute_plan_aggregates', store=True, digits=(16, 2))

    total_cash_in = fields.Float(string='Total Cash Receipts (\'000)', compute='_compute_plan_aggregates', store=True, digits=(16, 2))
    total_cash_out = fields.Float(string='Total Cash Payments (\'000)', compute='_compute_plan_aggregates', store=True, digits=(16, 2))
    net_cash_flow = fields.Float(string='Net Cash Flow (\'000)', compute='_compute_plan_aggregates', store=True, digits=(16, 2))

    min_opening_balance = fields.Float(
        string='Min Opening Cash Required (\'000)',
        compute='_compute_plan_aggregates',
        store=True,
        digits=(16, 2),
        help='Lowest cumulative running balance (negative) turned positive to ensure cash never dips below zero.'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('budget.plan') or _('New')
            if vals.get('name', _('New Plan')) == _('New Plan'):
                fy = self.env['budget.fiscal.year'].browse(vals.get('fiscal_year_id'))
                fy_name = fy.name if fy else ''
                vals['name'] = f"{vals.get('code', '')} - {fy_name} Plan v{vals.get('version', 1.0):.1f}"
        return super().create(vals_list)

    @api.depends('project_ids.contract_value', 'project_ids.revenue_planned',
                 'project_ids.direct_costs_planned', 'project_ids.cash_in_planned',
                 'project_ids.cash_out_planned', 'project_ids.cost_spread_ids.cash_m01',
                 'project_ids.cost_spread_ids.cash_m02', 'project_ids.cost_spread_ids.cash_m03',
                 'project_ids.cost_spread_ids.cash_m04', 'project_ids.cost_spread_ids.cash_m05',
                 'project_ids.cost_spread_ids.cash_m06', 'project_ids.cost_spread_ids.cash_m07',
                 'project_ids.cost_spread_ids.cash_m08', 'project_ids.cost_spread_ids.cash_m09',
                 'project_ids.cost_spread_ids.cash_m10', 'project_ids.cost_spread_ids.cash_m11',
                 'project_ids.cost_spread_ids.cash_m12',
                 'project_ids.revenue_spread_ids.m01', 'project_ids.revenue_spread_ids.m02',
                 'project_ids.revenue_spread_ids.m03', 'project_ids.revenue_spread_ids.m04',
                 'project_ids.revenue_spread_ids.m05', 'project_ids.revenue_spread_ids.m06',
                 'project_ids.revenue_spread_ids.m07', 'project_ids.revenue_spread_ids.m08',
                 'project_ids.revenue_spread_ids.m09', 'project_ids.revenue_spread_ids.m10',
                 'project_ids.revenue_spread_ids.m11', 'project_ids.revenue_spread_ids.m12',
                 'project_ids.revenue_spread_ids.annual_total',
                 'project_ids.receipt_term_ids.gross_amount',
                 'project_ids.receipt_term_ids.net_amount', 'project_ids.receipt_term_ids.month',
                 'project_ids.receipt_term_ids.month_index')
    def _compute_plan_aggregates(self):
        for plan in self:
            projects = plan.project_ids
            plan.project_count = len(projects)
            t_contract = sum(projects.mapped('contract_value'))
            t_rev = sum(projects.mapped('revenue_planned'))
            t_cost = sum(projects.mapped('direct_costs_planned'))
            t_gm = t_rev - t_cost

            plan.total_contract_value = t_contract
            plan.total_revenue = t_rev
            plan.total_direct_costs = t_cost
            plan.total_gross_margin = t_gm
            plan.margin_pct = (t_gm / t_rev * 100.0) if t_rev else 0.0

            # Cash flow calculation by month
            monthly_receipts = [0.0] * 12
            monthly_payments = [0.0] * 12

            for p in projects:
                # Receipts from receipt terms
                if p.receipt_term_ids:
                    for term in p.receipt_term_ids:
                        m_idx = term.month_index - 1
                        if 0 <= m_idx < 12:
                            monthly_receipts[m_idx] += term.net_amount
                else:
                    # If no receipt terms, distribute net cash according to revenue spread
                    if p.revenue_spread_ids:
                        rs = p.revenue_spread_ids[0]
                        spread_amts = [
                            rs.m01, rs.m02, rs.m03, rs.m04, rs.m05, rs.m06,
                            rs.m07, rs.m08, rs.m09, rs.m10, rs.m11, rs.m12
                        ]
                        wht_mult = (1.0 - (p.wht_rate or 0.0) / 100.0)
                        if rs.annual_total > 0:
                            for idx, amt in enumerate(spread_amts):
                                monthly_receipts[idx] += amt * wht_mult
                        else:
                            monthly_receipts[0] += p.cash_in_planned
                    else:
                        monthly_receipts[0] += p.cash_in_planned

                # Payments from cost spreads
                for cs in p.cost_spread_ids:
                    monthly_payments[0] += cs.cash_m01
                    monthly_payments[1] += cs.cash_m02
                    monthly_payments[2] += cs.cash_m03
                    monthly_payments[3] += cs.cash_m04
                    monthly_payments[4] += cs.cash_m05
                    monthly_payments[5] += cs.cash_m06
                    monthly_payments[6] += cs.cash_m07
                    monthly_payments[7] += cs.cash_m08
                    monthly_payments[8] += cs.cash_m09
                    monthly_payments[9] += cs.cash_m10
                    monthly_payments[10] += cs.cash_m11
                    monthly_payments[11] += cs.cash_m12

            tot_in = sum(monthly_receipts)
            tot_out = sum(monthly_payments)
            plan.total_cash_in = tot_in
            plan.total_cash_out = tot_out
            plan.net_cash_flow = tot_in - tot_out

            # Running balance & minimum opening balance required
            running = 0.0
            lowest_balance = 0.0
            for m in range(12):
                running += (monthly_receipts[m] - monthly_payments[m])
                if running < lowest_balance:
                    lowest_balance = running

            plan.min_opening_balance = -lowest_balance if lowest_balance < 0.0 else 0.0

    # Workflow Actions
    def action_submit(self):
        self.write({'state': 'under_review'})
        self.message_post(body=_("Budget Plan submitted for Finance Review."))

    def action_approve(self):
        self.write({'state': 'approved'})
        self.message_post(body=_("Budget Plan officially approved by Management."))

    def action_lock(self):
        self.write({'state': 'locked'})
        self.message_post(body=_("Budget Plan locked as official baseline."))

    def action_reset_draft(self):
        self.write({'state': 'draft'})
        self.message_post(body=_("Budget Plan reset to Draft."))

    def action_create_revision(self):
        self.ensure_one()
        new_version = self.version + 0.1
        new_name = f"{self.code} - {self.fiscal_year_id.name} Plan v{new_version:.1f}"
        
        # Copy plan record
        new_plan = self.copy({
            'name': new_name,
            'version': new_version,
            'parent_id': self.id,
            'state': 'draft',
        })

        # Deep copy projects and spreads
        for proj in self.project_ids:
            new_proj = proj.copy({
                'plan_id': new_plan.id,
            })
            # Copy revenue spread
            if proj.revenue_spread_ids:
                new_proj.revenue_spread_ids.unlink()  # clear default auto-created
                proj.revenue_spread_ids[0].copy({'project_id': new_proj.id})
            # Copy cost spreads
            if proj.cost_spread_ids:
                new_proj.cost_spread_ids.unlink()  # clear default auto-created
                for cs in proj.cost_spread_ids:
                    cs.copy({'project_id': new_proj.id})
            # Copy receipt terms
            new_proj.receipt_term_ids.unlink()  # ensure clean state before copy
            for rt in proj.receipt_term_ids:
                rt.copy({'project_id': new_proj.id})

        self.message_post(body=_("Created revision version %s (%s).") % (new_version, new_plan.name))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget Plan Revision'),
            'res_model': 'budget.plan',
            'res_id': new_plan.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # Derived Reports Direct Actions
    def action_view_orders_received(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Orders Received — %s') % self.name,
            'res_model': 'budget.report.viewer',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_plan_id': self.id,
                'default_report_type': 'orders',
            },
        }

    def action_view_project_breakdown(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Breakdown — %s') % self.name,
            'res_model': 'budget.report.viewer',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_plan_id': self.id,
                'default_report_type': 'breakdown',
            },
        }

    def action_view_pnl(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Profit & Loss (Accrual) — %s') % self.name,
            'res_model': 'budget.report.viewer',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_plan_id': self.id,
                'default_report_type': 'pnl',
            },
        }

    def action_view_cash_flow(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cash Flow & Position — %s') % self.name,
            'res_model': 'budget.report.viewer',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_plan_id': self.id,
                'default_report_type': 'cashflow',
            },
        }
