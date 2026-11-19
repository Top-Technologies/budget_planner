# -*- coding: utf-8 -*-
{
    'name': 'Budget Planner',
    'version': '19.0.1.0.0',
    'summary': 'Annual Planning, 12-Month Spreads, Orders Received, P&L and Cash Flow in ETB Thousands',
    'description': """
        Budget Planner for Odoo 19 Enterprise & Community
        ==================================================
        Top-down annual budget planning and derived reporting system:
        * 12-Month Spreads (Ethiopian Fiscal Year EFY: Jul to Jun).
        * Quarters (Q1-Q4) and Annual totals automatically computed.
        * Headline project figures (Revenue, Direct Costs, Margin %, Cash In/Out, WHT).
        * 4 Spreads per project: Revenue, Cost by Type (Stock, Local, Import, Other), Receipts, Payments.
        * Stock COGS recognized in P&L but excluded from Cash Outflows.
        * Payment offset support (e.g. -2m lead time for import purchases).
        * Derived Reports:
          - Orders Received (Contract value placed in 1st revenue month)
          - Project Breakdown (Grouped by Department and Status: Pipeline, Committed, PBF)
          - Profit & Loss (Accrual)
          - Cash Flow & Position Analysis (Running Balance & Minimum Opening Balance Required)
        * Full Approval Workflow: Draft -> Under Review -> Approved -> Locked, with Versioning.
    """,
    'category': 'Accounting/Management',
    'author': 'Top Technologies',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/budget_fiscal_year_data.xml',
        'data/budget_category_data.xml',
        'views/budget_category_views.xml',
        'views/budget_fiscal_year_views.xml',
        'views/budget_project_views.xml',
        'views/budget_plan_views.xml',
        'views/budget_reports_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/budget_demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'budget_planner/static/src/css/budget_matrix.css',
        ],
    },
    'installable': True,
    'application': True,
}
