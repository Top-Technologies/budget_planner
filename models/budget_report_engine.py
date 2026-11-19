# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

MONTH_NAMES = [
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'
]

class BudgetReportViewer(models.TransientModel):
    _name = 'budget.report.viewer'
    _description = 'Budget Planner Report Viewer'

    plan_id = fields.Many2one('budget.plan', string='Budget Plan', required=True, default=lambda self: self._default_plan())
    department_id = fields.Many2one('hr.department', string='Department Filter', help='Filter report by department (leave empty for company-wide).')
    report_type = fields.Selection([
        ('orders', '1. Orders Received'),
        ('breakdown', '2. Project Breakdown'),
        ('pnl', '3. Profit & Loss (Accrual)'),
        ('cashflow', '4. Cash Flow & Position'),
    ], string='Report Type', required=True, default='orders')
    period_type = fields.Selection([
        ('quarterly', 'Quarterly View'),
        ('monthly', 'Monthly View'),
        ('both', 'Both (Monthly & Quarterly)'),
    ], string='Period View', required=True, default='quarterly')

    html_content = fields.Html(string='Report Preview', compute='_compute_html_content', sanitize=False)

    def _default_plan(self):
        active_id = self.env.context.get('active_id')
        if active_id and self.env.context.get('active_model') == 'budget.plan':
            return active_id
        return self.env['budget.plan'].search([('state', 'in', ['draft', 'under_review', 'approved'])], order='id desc', limit=1).id

    @api.depends('plan_id', 'department_id', 'report_type', 'period_type')
    def _compute_html_content(self):
        for rec in self:
            if not rec.plan_id:
                rec.html_content = "<div class='alert alert-warning'>Please select a Budget Plan.</div>"
                continue

            projects = rec.plan_id.project_ids
            if rec.department_id:
                projects = projects.filtered(lambda p: p.department_id == rec.department_id)

            if rec.report_type == 'orders':
                rec.html_content = rec._render_orders_received(projects)
            elif rec.report_type == 'breakdown':
                rec.html_content = rec._render_project_breakdown(projects)
            elif rec.report_type == 'pnl':
                rec.html_content = rec._render_pnl(projects)
            elif rec.report_type == 'cashflow':
                rec.html_content = rec._render_cashflow(projects)

    # ----------------------------------------------------
    # Helper: Dynamic Column Layout based on Period Type
    # ----------------------------------------------------
    def _get_columns_config(self):
        """
        Returns (headers, colgroup_html, total_cols, bold_indices, pct_idx)
        Explicit column widths are assigned to prevent browser table squeeze.
        """
        label_width = 280
        if self.period_type == 'quarterly':
            headers = ['Q1', 'Q2', 'Q3', 'Q4', 'Total', '%']
            col_widths = [label_width, 110, 110, 110, 110, 120, 80]
            bold_indices = {0, 1, 2, 3, 4}
            pct_idx = 5
        elif self.period_type == 'monthly':
            headers = ['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Total', '%']
            col_widths = [label_width] + [85] * 12 + [100, 80]
            bold_indices = {12}
            pct_idx = 13
        else:  # 'both'
            headers = ['Jul', 'Aug', 'Sep', 'Q1', 'Oct', 'Nov', 'Dec', 'Q2', 'Jan', 'Feb', 'Mar', 'Q3', 'Apr', 'May', 'Jun', 'Q4', 'Total', '%']
            col_widths = [label_width] + [80, 80, 80, 90] * 4 + [100, 80]
            bold_indices = {3, 7, 11, 15, 16}
            pct_idx = 17

        total_cols = len(headers) + 1
        colgroup_tags = "".join([f"<col style='width: {w}px; min-width: {w}px;'/>" for w in col_widths])
        colgroup_html = f"<colgroup>{colgroup_tags}</colgroup>"

        return headers, colgroup_html, total_cols, bold_indices, pct_idx

    def _build_row_values(self, m, grand_total=0.0, pct_val=None):
        """
        Transforms 12 monthly values m into a row value list according to period_type.
        """
        q1 = sum(m[0:3])
        q2 = sum(m[3:6])
        q3 = sum(m[6:9])
        q4 = sum(m[9:12])
        annual = q1 + q2 + q3 + q4

        if pct_val is not None:
            pct = pct_val
        else:
            pct = (annual / grand_total * 100.0) if grand_total else 0.0

        if self.period_type == 'quarterly':
            return [q1, q2, q3, q4, annual, pct]
        elif self.period_type == 'monthly':
            return [m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11], annual, pct]
        else:  # 'both'
            return [
                m[0], m[1], m[2], q1,
                m[3], m[4], m[5], q2,
                m[6], m[7], m[8], q3,
                m[9], m[10], m[11], q4,
                annual, pct
            ]

    # ----------------------------------------------------
    # Report 1: Orders Received
    # ----------------------------------------------------
    def _render_orders_received(self, projects):
        headers, colgroup_html, total_cols, bold_indices, pct_idx = self._get_columns_config()

        dept_data = {}
        for p in projects:
            dept_name = p.department_id.name or 'General'
            if dept_name not in dept_data:
                dept_data[dept_name] = []

            p_buckets = [0.0] * 12
            rs = p.revenue_spread_ids[:1]
            if p.is_stock_sales:
                if rs:
                    p_buckets = [
                        rs.m01, rs.m02, rs.m03, rs.m04, rs.m05, rs.m06,
                        rs.m07, rs.m08, rs.m09, rs.m10, rs.m11, rs.m12
                    ]
            else:
                first_m = rs.first_revenue_month if rs else 1
                target_idx = (first_m - 1) if (1 <= first_m <= 12) else 0
                p_buckets[target_idx] = p.contract_value or p.revenue_planned

            dept_data[dept_name].append({
                'project': p,
                'code': p.code or '',
                'name': p.name,
                'is_sales': p.is_stock_sales,
                'buckets': p_buckets,
            })

        company_buckets = [0.0] * 12
        dept_totals = {}
        for dname, proj_list in dept_data.items():
            d_buckets = [0.0] * 12
            for item in proj_list:
                for idx in range(12):
                    d_buckets[idx] += item['buckets'][idx]
                    company_buckets[idx] += item['buckets'][idx]
            dept_totals[dname] = d_buckets

        company_annual = sum(company_buckets)

        def make_row(label, buckets, is_bold=False, is_highlight=False, badge=''):
            cols = self._build_row_values(buckets, grand_total=company_annual)

            cell_bg = "#ffffff"
            if is_highlight:
                cell_bg = "#f1f5f9"
            if is_bold and is_highlight:
                cell_bg = "#e2e8f0"

            style = "font-weight: bold;" if is_bold else ""
            badge_html = f" <span class='badge bg-info text-dark' style='font-size:0.75rem; margin-left: 4px;'>{badge}</span>" if badge else ""

            label_td = (
                f"<td style='width: 280px; min-width: 280px; max-width: 280px; padding: 6px 12px; border: 1px solid #cbd5e1; "
                f"text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; position: sticky; left: 0; "
                f"background-color: {cell_bg}; z-index: 2; box-shadow: 2px 0 4px rgba(0,0,0,0.06); {style}' "
                f"title='{label}'>{label}{badge_html}</td>"
            )

            tds = []
            for idx, c in enumerate(cols):
                is_col_bold = (idx in bold_indices)
                col_bg = "background-color: #f1f3f5;" if (is_col_bold and not is_highlight) else f"background-color: {cell_bg};"
                val_str = f"{c:.1f}%" if idx == pct_idx else f"{c:,.1f}"
                tds.append(
                    f"<td style='text-align: right; padding: 6px 8px; border: 1px solid #cbd5e1; white-space: nowrap; {col_bg} {'font-weight: bold;' if is_col_bold else ''}'>{val_str}</td>"
                )

            return f"<tr style='{style} background-color: {cell_bg};'>{label_td}{''.join(tds)}</tr>"

        th_cells = "".join([
            f"<th style='text-align: right; padding: 6px 8px; border: 1px solid #cbd5e1; white-space: nowrap; {'background-color: #f1f3f5; font-weight: bold;' if col in ['Q1','Q2','Q3','Q4','Total'] else ''}'>{col}</th>"
            for col in headers
        ])

        html = f"""
        <div style='font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif; font-size: 0.85rem;'>
            <div style='margin-bottom: 12px;'>
                <h4 style='margin: 0; color: #1e293b; font-weight: 700;'>Orders Received Report (ETB '000)</h4>
                <div style='color: #64748b; font-size: 0.8rem; margin-top: 2px;'>Contract value recognized in month revenue begins. Stock Sales marked [Sales].</div>
            </div>
            <div class='o_budget_report_wrapper' style='overflow-x: auto !important; width: 100% !important; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff; -webkit-overflow-scrolling: touch;'>
                <table class='o_budget_report_table' style='width: max-content !important; min-width: 100% !important; max-width: none !important; margin: 0 !important; border-collapse: collapse !important; table-layout: fixed !important;'>
                    {colgroup_html}
                    <thead>
                        <tr style='background-color: #f8fafc; border-bottom: 2px solid #cbd5e1;'>
                            <th style='padding: 6px 12px; width: 280px; min-width: 280px; max-width: 280px; border: 1px solid #cbd5e1; text-align: left; white-space: nowrap; position: sticky; left: 0; background-color: #f8fafc; z-index: 3; box-shadow: 2px 0 4px rgba(0,0,0,0.06);'>Department / Project</th>
                            {th_cells}
                        </tr>
                    </thead>
                    <tbody>
                        <tr style='background-color: #e2e8f0; font-weight: bold;'>
                            <td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>1. DEPARTMENT SUMMARY</td>
                        </tr>
        """

        for dname, d_b in dept_totals.items():
            html += make_row(dname, d_b, is_bold=True)
        html += make_row("COMPANY TOTAL", company_buckets, is_bold=True, is_highlight=True)

        html += f"""
                        <tr style='background-color: #e2e8f0; font-weight: bold;'>
                            <td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>2. PROJECT DETAIL</td>
                        </tr>
        """

        for dname, p_list in dept_data.items():
            html += f"<tr style='background-color: #f1f5f9; font-weight: bold;'><td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>{dname}</td></tr>"
            for item in p_list:
                badge = "Sales" if item['is_sales'] else ""
                code_prefix = f"[{item['code']}] " if item.get('code') else ""
                lbl = f"{code_prefix}{item['name']}"
                html += make_row(lbl, item['buckets'], badge=badge)
            html += make_row(f"{dname} Total", dept_totals[dname], is_bold=True, is_highlight=True)

        html += make_row("COMPANY TOTAL", company_buckets, is_bold=True, is_highlight=True)
        html += "</tbody></table></div></div>"
        return html

    # ----------------------------------------------------
    # Report 2: Project Breakdown
    # ----------------------------------------------------
    def _render_project_breakdown(self, projects):
        headers, colgroup_html, total_cols, bold_indices, pct_idx = self._get_columns_config()

        th_cells = "".join([
            f"<th style='text-align: right; padding: 6px 8px; border: 1px solid #cbd5e1; white-space: nowrap; {'background-color: #f1f3f5; font-weight: bold;' if col in ['Q1','Q2','Q3','Q4','Total'] else ''}'>{col}</th>"
            for col in headers
        ])

        def format_row(title, vals, indent=0, is_bold=False, bg='#ffffff', grand_total=None, text_color=None):
            if grand_total is not None and grand_total > 0:
                pct = (sum(vals) / grand_total * 100.0)
                cols = self._build_row_values(vals, pct_val=pct)
            else:
                cols = self._build_row_values(vals, pct_val=(100.0 if sum(vals) else 0.0))

            indent_px = indent * 16 + 12
            style = "font-weight: bold;" if is_bold else ""
            if text_color:
                style += f" color: {text_color};"

            label_td = (
                f"<td style='padding-left: {indent_px}px; padding-right: 12px; padding-top: 5px; padding-bottom: 5px; width: 280px; min-width: 280px; max-width: 280px; "
                f"border: 1px solid #cbd5e1; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; position: sticky; left: 0; "
                f"background-color: {bg}; z-index: 2; box-shadow: 2px 0 4px rgba(0,0,0,0.06); {style}' title='{title}'>{title}</td>"
            )

            tds = []
            for idx, c in enumerate(cols):
                is_col_bold = (idx in bold_indices)
                val_str = f"{c:.1f}%" if idx == pct_idx else f"{c:,.1f}"
                td_style = f"text-align: right; padding: 5px 8px; border: 1px solid #cbd5e1; white-space: nowrap; background-color: {bg}; {'font-weight: bold;' if is_col_bold else ''}"
                if text_color and not is_bold:
                    td_style += f" color: {text_color};"
                tds.append(
                    f"<td style='{td_style}'>{val_str}</td>"
                )

            return f"<tr style='background-color: {bg};'>{label_td}{''.join(tds)}</tr>"

        html = f"""
        <div style='font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif; font-size: 0.82rem;'>
            <div style='margin-bottom: 12px;'>
                <h4 style='margin: 0; color: #1e293b; font-weight: 700;'>Project Breakdown Report (ETB '000)</h4>
                <div style='color: #64748b; font-size: 0.8rem; margin-top: 2px;'>Grouped by Department &amp; Status (Pipeline, Committed, PBF)</div>
            </div>
            <div class='o_budget_report_wrapper' style='overflow-x: auto !important; width: 100% !important; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff; -webkit-overflow-scrolling: touch;'>
                <table class='o_budget_report_table' style='width: max-content !important; min-width: 100% !important; max-width: none !important; margin: 0 !important; border-collapse: collapse !important; table-layout: fixed !important;'>
                    {colgroup_html}
                    <thead>
                        <tr style='background-color: #f8fafc; border-bottom: 2px solid #cbd5e1;'>
                            <th style='padding: 6px 12px; width: 280px; min-width: 280px; max-width: 280px; border: 1px solid #cbd5e1; text-align: left; white-space: nowrap; position: sticky; left: 0; background-color: #f8fafc; z-index: 3; box-shadow: 2px 0 4px rgba(0,0,0,0.06);'>Line Item</th>
                            {th_cells}
                        </tr>
                    </thead>
                    <tbody>
        """

        dept_dict = {}
        for p in projects:
            d_name = p.department_id.name or 'General'
            dept_dict.setdefault(d_name, []).append(p)

        for d_name, d_projects in dept_dict.items():
            html += f"<tr style='background-color: #334155; color: white; font-weight: bold;'><td colspan='{total_cols}' style='padding: 8px 12px; border: 1px solid #334155;'>DEPARTMENT: {d_name}</td></tr>"

            for status_key, status_label in [('pipeline', 'PIPELINE'), ('committed', 'COMMITTED'), ('pbf', 'PBF')]:
                s_projects = [p for p in d_projects if p.status_group == status_key]
                if not s_projects:
                    continue

                html += f"<tr style='background-color: #e2e8f0; font-weight: bold;'><td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>Status Group: {status_label}</td></tr>"

                for p in s_projects:
                    rs = p.revenue_spread_ids[:1]
                    rev_vals = [
                        rs.m01 if rs else 0.0, rs.m02 if rs else 0.0, rs.m03 if rs else 0.0,
                        rs.m04 if rs else 0.0, rs.m05 if rs else 0.0, rs.m06 if rs else 0.0,
                        rs.m07 if rs else 0.0, rs.m08 if rs else 0.0, rs.m09 if rs else 0.0,
                        rs.m10 if rs else 0.0, rs.m11 if rs else 0.0, rs.m12 if rs else 0.0,
                    ]

                    code_str = f"[{p.code}] " if p.code else ""
                    html += f"""
                    <tr style='background-color: #f8fafc; font-weight: bold; border-top: 2px solid #94a3b8;'>
                        <td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>
                            {code_str}{p.name} · Contract: {p.contract_value:,.1f} | Category: {p.category_id.name or ''} | Client: {p.client_id.name or 'N/A'}
                        </td>
                    </tr>
                    """

                    html += format_row("Revenue (Accrual)", rev_vals, indent=1, is_bold=True)

                    cost_totals = [0.0] * 12
                    for cs in p.cost_spread_ids:
                        c_vals = [
                            cs.m01, cs.m02, cs.m03, cs.m04, cs.m05, cs.m06,
                            cs.m07, cs.m08, cs.m09, cs.m10, cs.m11, cs.m12
                        ]
                        for idx in range(12):
                            cost_totals[idx] += c_vals[idx]
                        type_label = dict(cs._fields['cost_type'].selection).get(cs.cost_type, cs.cost_type)
                        html += format_row(f"Cost: {type_label}", c_vals, indent=2)

                    gm_vals = [rev_vals[i] - cost_totals[i] for i in range(12)]
                    html += format_row(f"Gross Margin ({p.margin_pct:.1f}%)", gm_vals, indent=1, is_bold=True, bg='#f0fdf4')

                    receipt_vals = [0.0] * 12
                    receipt_sub_rows = []
                    if p.receipt_term_ids:
                        for term in p.receipt_term_ids.sorted(key=lambda r: (r.month_index, r.id)):
                            m_idx = term.month_index - 1
                            t_vals = [0.0] * 12
                            if 0 <= m_idx < 12:
                                t_vals[m_idx] = term.net_amount
                                receipt_vals[m_idx] += term.net_amount
                            term_type_label = dict(term._fields['term_type'].selection).get(term.term_type, term.term_type)
                            m_label = dict(term._fields['month'].selection).get(term.month, f"M{term.month_index:02d}")
                            receipt_sub_rows.append((f"Receipt: {term_type_label} ({m_label})", t_vals))
                    elif p.cash_in_planned:
                        if p.revenue_spread_ids:
                            rs = p.revenue_spread_ids[0]
                            spread_amts = [
                                rs.m01, rs.m02, rs.m03, rs.m04, rs.m05, rs.m06,
                                rs.m07, rs.m08, rs.m09, rs.m10, rs.m11, rs.m12
                            ]
                            wht_mult = (1.0 - (p.wht_rate or 0.0) / 100.0)
                            if rs.annual_total > 0:
                                for idx, amt in enumerate(spread_amts):
                                    net_amt = amt * wht_mult
                                    receipt_vals[idx] += net_amt
                                    if net_amt > 0:
                                        t_vals = [0.0] * 12
                                        t_vals[idx] = net_amt
                                        m_name = MONTH_NAMES[idx]
                                        receipt_sub_rows.append((f"Receipt: Sales Accrual ({m_name})", t_vals))
                            else:
                                receipt_vals[0] += p.cash_in_planned
                                t_vals = [0.0] * 12
                                t_vals[0] = p.cash_in_planned
                                receipt_sub_rows.append(("Receipt: Planned Inflow (M01 - Jul)", t_vals))
                        else:
                            receipt_vals[0] += p.cash_in_planned
                            t_vals = [0.0] * 12
                            t_vals[0] = p.cash_in_planned
                            receipt_sub_rows.append(("Receipt: Planned Inflow (M01 - Jul)", t_vals))

                    total_receipt_sum = sum(receipt_vals)
                    html += format_row("Cash Receipts (net of WHT)", receipt_vals, indent=1, is_bold=True)
                    for r_title, r_vals in receipt_sub_rows:
                        html += format_row(r_title, r_vals, indent=2, grand_total=total_receipt_sum, text_color='#475569')

                    pay_vals = [0.0] * 12
                    pay_sub_rows = []
                    for cs in p.cost_spread_ids:
                        if cs.cost_type != 'stock':
                            c_cash = [
                                cs.cash_m01, cs.cash_m02, cs.cash_m03, cs.cash_m04,
                                cs.cash_m05, cs.cash_m06, cs.cash_m07, cs.cash_m08,
                                cs.cash_m09, cs.cash_m10, cs.cash_m11, cs.cash_m12
                            ]
                            for idx in range(12):
                                pay_vals[idx] += c_cash[idx]

                            if any(v != 0 for v in c_cash):
                                type_label = dict(cs._fields['cost_type'].selection).get(cs.cost_type, cs.cost_type)
                                offset_str = f" [{cs.payment_offset:+d}m offset]" if cs.payment_offset else ""
                                active_months = [MONTH_NAMES[i] for i, v in enumerate(c_cash) if v > 0]
                                if active_months:
                                    if len(active_months) <= 3:
                                        m_str = f" ({', '.join(active_months)})"
                                    else:
                                        m_str = f" ({active_months[0]}..{active_months[-1]})"
                                else:
                                    m_str = ""
                                pay_sub_rows.append((f"Payment: {type_label}{offset_str}{m_str}", c_cash))

                    total_pay_sum = sum(pay_vals)
                    html += format_row("Cash Payments", pay_vals, indent=1, is_bold=True)
                    for p_title, p_cash_vals in pay_sub_rows:
                        html += format_row(p_title, p_cash_vals, indent=2, grand_total=total_pay_sum, text_color='#475569')

                    net_vals = [receipt_vals[i] - pay_vals[i] for i in range(12)]
                    html += format_row("Net Cash Flow", net_vals, indent=1, is_bold=True, bg='#eff6ff')

        html += "</tbody></table></div></div>"
        return html

    # ----------------------------------------------------
    # Report 3: Profit and Loss (Accrual)
    # ----------------------------------------------------
    def _render_pnl(self, projects):
        headers, colgroup_html, total_cols, bold_indices, pct_idx = self._get_columns_config()

        th_cells = "".join([
            f"<th style='text-align: right; padding: 6px 8px; border: 1px solid #cbd5e1; white-space: nowrap; {'background-color: #f1f3f5; font-weight: bold;' if col in ['Q1','Q2','Q3','Q4','Total'] else ''}'>{col}</th>"
            for col in headers
        ])

        tot_rev = [0.0] * 12
        tot_cost = [0.0] * 12

        for p in projects:
            rs = p.revenue_spread_ids[:1]
            if rs:
                p_rev_pre = [
                    rs.m01, rs.m02, rs.m03, rs.m04, rs.m05, rs.m06,
                    rs.m07, rs.m08, rs.m09, rs.m10, rs.m11, rs.m12
                ]
                for i in range(12):
                    tot_rev[i] += p_rev_pre[i]

            for cs in p.cost_spread_ids:
                tot_cost[0] += cs.m01
                tot_cost[1] += cs.m02
                tot_cost[2] += cs.m03
                tot_cost[3] += cs.m04
                tot_cost[4] += cs.m05
                tot_cost[5] += cs.m06
                tot_cost[6] += cs.m07
                tot_cost[7] += cs.m08
                tot_cost[8] += cs.m09
                tot_cost[9] += cs.m10
                tot_cost[10] += cs.m11
                tot_cost[11] += cs.m12

        annual_rev = sum(tot_rev)

        def row_html(title, vals, is_bold=False, bg='#ffffff', indent=0, pct_override=None):
            pct = pct_override if pct_override is not None else ((sum(vals) / annual_rev * 100.0) if annual_rev else 0.0)
            cols = self._build_row_values(vals, pct_val=pct)

            indent_px = indent * 16 + 12
            style = "font-weight: bold;" if is_bold else ""

            label_td = (
                f"<td style='padding-left: {indent_px}px; padding-right: 12px; padding-top: 5px; padding-bottom: 5px; width: 280px; min-width: 280px; max-width: 280px; "
                f"border: 1px solid #cbd5e1; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; position: sticky; left: 0; "
                f"background-color: {bg}; z-index: 2; box-shadow: 2px 0 4px rgba(0,0,0,0.06); {style}' title='{title}'>{title}</td>"
            )

            tds = []
            for idx, c in enumerate(cols):
                is_col_bold = (idx in bold_indices)
                val_str = f"{c:.1f}%" if idx == pct_idx else f"{c:,.1f}"
                tds.append(
                    f"<td style='text-align: right; padding: 5px 8px; border: 1px solid #cbd5e1; white-space: nowrap; background-color: {bg}; {'font-weight: bold;' if is_col_bold else ''}'>{val_str}</td>"
                )

            return f"<tr style='background-color: {bg};'>{label_td}{''.join(tds)}</tr>"

        html = f"""
        <div style='font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif; font-size: 0.85rem;'>
            <div style='margin-bottom: 12px;'>
                <h4 style='margin: 0; color: #1e293b; font-weight: 700;'>Profit &amp; Loss Report (Accrual) — ETB '000</h4>
                <div style='color: #64748b; font-size: 0.8rem; margin-top: 2px;'>Accrual revenue recognition vs total direct costs (including Stock COGS)</div>
            </div>
            <div class='o_budget_report_wrapper' style='overflow-x: auto !important; width: 100% !important; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff; -webkit-overflow-scrolling: touch;'>
                <table class='o_budget_report_table' style='width: max-content !important; min-width: 100% !important; max-width: none !important; margin: 0 !important; border-collapse: collapse !important; table-layout: fixed !important;'>
                    {colgroup_html}
                    <thead>
                        <tr style='background-color: #f8fafc; border-bottom: 2px solid #cbd5e1;'>
                            <th style='padding: 6px 12px; width: 280px; min-width: 280px; max-width: 280px; border: 1px solid #cbd5e1; text-align: left; white-space: nowrap; position: sticky; left: 0; background-color: #f8fafc; z-index: 3; box-shadow: 2px 0 4px rgba(0,0,0,0.06);'>Account / Project Line</th>
                            {th_cells}
                        </tr>
                    </thead>
                    <tbody>
                        <tr style='background-color: #f1f5f9; font-weight: bold;'><td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>PROJECT REVENUE</td></tr>
        """

        for p in projects:
            rs = p.revenue_spread_ids[:1]
            p_rev = [
                rs.m01 if rs else 0.0, rs.m02 if rs else 0.0, rs.m03 if rs else 0.0,
                rs.m04 if rs else 0.0, rs.m05 if rs else 0.0, rs.m06 if rs else 0.0,
                rs.m07 if rs else 0.0, rs.m08 if rs else 0.0, rs.m09 if rs else 0.0,
                rs.m10 if rs else 0.0, rs.m11 if rs else 0.0, rs.m12 if rs else 0.0,
            ]
            p_label = f"[{p.code}] {p.name}" if p.code else p.name
            html += row_html(p_label, p_rev, indent=1)

        html += row_html("TOTAL PROJECT REVENUE", tot_rev, is_bold=True, bg='#e2e8f0')

        html += f"<tr style='background-color: #f1f5f9; font-weight: bold;'><td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>PROJECT DIRECT COSTS</td></tr>"

        for p in projects:
            p_cost = [0.0] * 12
            for cs in p.cost_spread_ids:
                p_cost[0] += cs.m01
                p_cost[1] += cs.m02
                p_cost[2] += cs.m03
                p_cost[3] += cs.m04
                p_cost[4] += cs.m05
                p_cost[5] += cs.m06
                p_cost[6] += cs.m07
                p_cost[7] += cs.m08
                p_cost[8] += cs.m09
                p_cost[9] += cs.m10
                p_cost[10] += cs.m11
                p_cost[11] += cs.m12
            p_label = f"[{p.code}] {p.name}" if p.code else p.name
            html += row_html(p_label, p_cost, indent=1)

        html += row_html("TOTAL PROJECT DIRECT COSTS", tot_cost, is_bold=True, bg='#e2e8f0')

        gm = [tot_rev[i] - tot_cost[i] for i in range(12)]
        annual_gm = sum(gm)
        overall_pct = (annual_gm / annual_rev * 100.0) if annual_rev else 0.0

        html += row_html(f"GROSS MARGIN ({overall_pct:.1f}%)", gm, is_bold=True, bg='#dcfce7', pct_override=overall_pct)
        html += "</tbody></table></div></div>"
        return html

    # ----------------------------------------------------
    # Report 4: Cash Flow & Position Analysis
    # ----------------------------------------------------
    def _render_cashflow(self, projects):
        headers, colgroup_html, total_cols, bold_indices, pct_idx = self._get_columns_config()

        th_cells = "".join([
            f"<th style='text-align: right; padding: 6px 8px; border: 1px solid #cbd5e1; white-space: nowrap; {'background-color: #f1f3f5; font-weight: bold;' if col in ['Q1','Q2','Q3','Q4','Total'] else ''}'>{col}</th>"
            for col in headers
        ])

        tot_receipts = [0.0] * 12
        tot_payments = [0.0] * 12
        stock_memo = [0.0] * 12

        terms_dict = {
            'monthly_sales': [0.0] * 12,
            'advance': [0.0] * 12,
            'progress': [0.0] * 12,
            'final': [0.0] * 12,
        }

        pay_dict = {
            'local': [0.0] * 12,
            'import': [0.0] * 12,
            'other': [0.0] * 12,
        }

        for p in projects:
            if p.receipt_term_ids:
                for term in p.receipt_term_ids:
                    m_idx = term.month_index - 1
                    if 0 <= m_idx < 12:
                        amt = term.net_amount
                        tot_receipts[m_idx] += amt
                        tt = term.term_type
                        if tt == 'monthly_sales':
                            terms_dict['monthly_sales'][m_idx] += amt
                        elif tt == 'advance':
                            terms_dict['advance'][m_idx] += amt
                        elif tt.startswith('progress'):
                            terms_dict['progress'][m_idx] += amt
                        elif tt == 'final':
                            terms_dict['final'][m_idx] += amt
            elif p.cash_in_planned:
                if p.revenue_spread_ids:
                    rs = p.revenue_spread_ids[0]
                    spread_amts = [
                        rs.m01, rs.m02, rs.m03, rs.m04, rs.m05, rs.m06,
                        rs.m07, rs.m08, rs.m09, rs.m10, rs.m11, rs.m12
                    ]
                    wht_mult = (1.0 - (p.wht_rate or 0.0) / 100.0)
                    if rs.annual_total > 0:
                        for idx, amt in enumerate(spread_amts):
                            net_amt = amt * wht_mult
                            tot_receipts[idx] += net_amt
                            terms_dict['monthly_sales'][idx] += net_amt
                    else:
                        tot_receipts[0] += p.cash_in_planned
                        terms_dict['monthly_sales'][0] += p.cash_in_planned
                else:
                    tot_receipts[0] += p.cash_in_planned
                    terms_dict['monthly_sales'][0] += p.cash_in_planned

            for cs in p.cost_spread_ids:
                if cs.cost_type == 'stock':
                    stock_memo[0] += cs.m01
                    stock_memo[1] += cs.m02
                    stock_memo[2] += cs.m03
                    stock_memo[3] += cs.m04
                    stock_memo[4] += cs.m05
                    stock_memo[5] += cs.m06
                    stock_memo[6] += cs.m07
                    stock_memo[7] += cs.m08
                    stock_memo[8] += cs.m09
                    stock_memo[9] += cs.m10
                    stock_memo[10] += cs.m11
                    stock_memo[11] += cs.m12
                else:
                    target_list = pay_dict.get(cs.cost_type, pay_dict['other'])
                    c_vals = [
                        cs.cash_m01, cs.cash_m02, cs.cash_m03, cs.cash_m04, cs.cash_m05, cs.cash_m06,
                        cs.cash_m07, cs.cash_m08, cs.cash_m09, cs.cash_m10, cs.cash_m11, cs.cash_m12
                    ]
                    for i in range(12):
                        target_list[i] += c_vals[i]
                        tot_payments[i] += c_vals[i]

        annual_receipts = sum(tot_receipts)

        def row_html(title, vals, is_bold=False, bg='#ffffff', indent=0, is_memo=False):
            pct = (sum(vals) / annual_receipts * 100.0) if annual_receipts else 0.0
            cols = self._build_row_values(vals, pct_val=pct)

            indent_px = indent * 16 + 12
            font_style = "font-style: italic; color: #64748b;" if is_memo else ""
            style = f"{font_style} {'font-weight: bold;' if is_bold else ''}"

            label_td = (
                f"<td style='padding-left: {indent_px}px; padding-right: 12px; padding-top: 5px; padding-bottom: 5px; width: 280px; min-width: 280px; max-width: 280px; "
                f"border: 1px solid #cbd5e1; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; position: sticky; left: 0; "
                f"background-color: {bg}; z-index: 2; box-shadow: 2px 0 4px rgba(0,0,0,0.06); {style}' title='{title}'>{title}</td>"
            )

            tds = []
            for idx, c in enumerate(cols):
                is_col_bold = (idx in bold_indices)
                val_str = f"{c:.1f}%" if idx == pct_idx else f"{c:,.1f}"
                tds.append(
                    f"<td style='text-align: right; padding: 5px 8px; border: 1px solid #cbd5e1; white-space: nowrap; background-color: {bg}; {'font-weight: bold;' if is_col_bold else ''}'>{val_str}</td>"
                )

            return f"<tr style='background-color: {bg};'>{label_td}{''.join(tds)}</tr>"

        html = f"""
        <div style='font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif; font-size: 0.85rem;'>
            <div style='margin-bottom: 12px;'>
                <h4 style='margin: 0; color: #1e293b; font-weight: 700;'>Cash Flow &amp; Position Analysis (ETB '000)</h4>
                <div style='color: #64748b; font-size: 0.8rem; margin-top: 2px;'>Receipts net of WHT, cash payments shifted with offset, Stock COGS excluded from outflows</div>
            </div>
            <div class='o_budget_report_wrapper' style='overflow-x: auto !important; width: 100% !important; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff; -webkit-overflow-scrolling: touch;'>
                <table class='o_budget_report_table' style='width: max-content !important; min-width: 100% !important; max-width: none !important; margin: 0 !important; border-collapse: collapse !important; table-layout: fixed !important;'>
                    {colgroup_html}
                    <thead>
                        <tr style='background-color: #f8fafc; border-bottom: 2px solid #cbd5e1;'>
                            <th style='padding: 6px 12px; width: 280px; min-width: 280px; max-width: 280px; border: 1px solid #cbd5e1; text-align: left; white-space: nowrap; position: sticky; left: 0; background-color: #f8fafc; z-index: 3; box-shadow: 2px 0 4px rgba(0,0,0,0.06);'>Cash Category / Line Item</th>
                            {th_cells}
                        </tr>
                    </thead>
                    <tbody>
                        <tr style='background-color: #f1f5f9; font-weight: bold;'><td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>CASH RECEIPTS (NET OF WHT)</td></tr>
        """

        html += row_html("Monthly Sales", terms_dict['monthly_sales'], indent=1)
        html += row_html("Advance Payments", terms_dict['advance'], indent=1)
        html += row_html("Progress Payments", terms_dict['progress'], indent=1)
        html += row_html("Final Payments", terms_dict['final'], indent=1)
        html += row_html("TOTAL CASH RECEIPTS", tot_receipts, is_bold=True, bg='#e2e8f0')

        html += f"<tr style='background-color: #f1f5f9; font-weight: bold;'><td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>CASH PAYMENTS</td></tr>"
        html += row_html("Local Purchase", pay_dict['local'], indent=1)
        html += row_html("Import Purchase (Lead Offset)", pay_dict['import'], indent=1)
        html += row_html("Other Direct Costs", pay_dict['other'], indent=1)
        html += row_html("Materials (Stock) — Non-Cash Memo", stock_memo, indent=1, is_memo=True)
        html += row_html("TOTAL CASH PAYMENTS", tot_payments, is_bold=True, bg='#e2e8f0')

        net_cf = [tot_receipts[i] - tot_payments[i] for i in range(12)]
        html += row_html("NET CASH FLOW", net_cf, is_bold=True, bg='#eff6ff')

        running = [0.0] * 12
        cum = 0.0
        lowest_point = 0.0
        for i in range(12):
            cum += net_cf[i]
            running[i] = cum
            if cum < lowest_point:
                lowest_point = cum

        min_opening = -lowest_point if lowest_point < 0.0 else 0.0

        html += f"<tr style='background-color: #f1f5f9; font-weight: bold;'><td colspan='{total_cols}' style='padding: 6px 12px; border: 1px solid #cbd5e1;'>CASH POSITION ANALYSIS</td></tr>"

        if self.period_type == 'quarterly':
            r_cols = [running[2], running[5], running[8], running[11], running[11]]
        elif self.period_type == 'monthly':
            r_cols = [
                running[0], running[1], running[2], running[3], running[4], running[5],
                running[6], running[7], running[8], running[9], running[10], running[11],
                running[11]
            ]
        else:  # 'both'
            r_cols = [
                running[0], running[1], running[2], running[2],
                running[3], running[4], running[5], running[5],
                running[6], running[7], running[8], running[8],
                running[9], running[10], running[11], running[11],
                running[11]
            ]

        r_label_td = (
            f"<td style='padding: 6px 12px; width: 280px; min-width: 280px; max-width: 280px; border: 1px solid #cbd5e1; "
            f"font-weight: bold; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; "
            f"position: sticky; left: 0; background-color: #fef3c7; z-index: 2; box-shadow: 2px 0 4px rgba(0,0,0,0.06);' "
            f"title='Running Cash Balance (Cumulative)'>Running Cash Balance (Cumulative)</td>"
        )
        r_tds = "".join([
            f"<td style='text-align: right; padding: 6px 8px; font-weight: bold; border: 1px solid #cbd5e1; white-space: nowrap; background-color: #fef3c7;'>{c:,.1f}</td>"
            for c in r_cols
        ])
        html += f"<tr style='background-color: #fef3c7;'>{r_label_td}{r_tds}<td style='text-align: right; padding: 6px 8px; border: 1px solid #cbd5e1; white-space: nowrap; background-color: #fef3c7;'>-</td></tr>"

        html += f"""
                    </tbody>
                </table>
            </div>
            <div style='margin-top: 15px; padding: 12px 16px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px;'>
                <div style='font-weight: bold; font-size: 1rem; color: #166534;'>
                    Minimum Opening Cash Balance Required: {min_opening:,.2f} ETB ('000)
                </div>
                <div style='color: #15803d; font-size: 0.8rem; margin-top: 4px;'>
                    This is the cash reserve needed at July 1st to ensure the company cash balance never drops below zero during the fiscal year.
                </div>
            </div>
        </div>
        """
        return html
