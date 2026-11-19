# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestBudgetPlan(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Department = self.env['hr.department']
        self.BudgetCategory = self.env['budget.category']
        self.BudgetFiscalYear = self.env['budget.fiscal.year']
        self.BudgetPlan = self.env['budget.plan']
        self.BudgetProject = self.env['budget.plan.project']

        self.dept_test = self.Department.create({'name': 'Engineering Test Dept'})
        self.cat_gov = self.BudgetCategory.create({
            'name': 'Government Projects',
            'code': 'GOV',
            'is_stock_sales': False,
        })
        self.fy_test = self.BudgetFiscalYear.create({
            'name': 'EFY 2019 Test',
            'code': 'EFY2019_TEST',
            'date_from': '2026-07-08',
            'date_to': '2027-07-07',
        })

    def test_01_project_kpi_and_spread_creation(self):
        """Test headline calculations, gross margin, WHT net receipts, and auto spread initialization"""
        plan = self.BudgetPlan.create({
            'name': 'Test Annual Plan',
            'fiscal_year_id': self.fy_test.id,
        })

        proj = self.BudgetProject.create({
            'plan_id': plan.id,
            'name': 'Smart City Traffic Lights',
            'code': 'SCT-01',
            'department_id': self.dept_test.id,
            'category_id': self.cat_gov.id,
            'status_group': 'committed',
            'contract_value': 100000.0,
            'wht_rate': 2.0,
            'vat_rate': 15.0,
            'revenue_planned': 100000.0,
            'direct_costs_planned': 65000.0,
        })

        # Test Gross Margin and Margin %
        self.assertAlmostEqual(proj.gross_margin, 35000.0)
        self.assertAlmostEqual(proj.margin_pct, 35.0)

        # Test Cash In net of 2% WHT = 98,000
        self.assertAlmostEqual(proj.cash_in_planned, 98000.0)

        # Verify auto-created revenue spread & 4 cost lines
        self.assertEqual(len(proj.revenue_spread_ids), 1)
        self.assertEqual(len(proj.cost_spread_ids), 4)

        # Check stock cost is present and non-cash
        stock_cost = proj.cost_spread_ids.filtered(lambda c: c.cost_type == 'stock')
        self.assertTrue(stock_cost)
        stock_cost.write({'planned_amount': 20000.0, 'm01_pct': 50.0, 'm02_pct': 50.0})
        self.assertAlmostEqual(stock_cost.cash_annual_total, 0.0, msg="Stock COGS must have zero cash outflow")

        # Check import cost with -2m offset
        import_cost = proj.cost_spread_ids.filtered(lambda c: c.cost_type == 'import')
        self.assertTrue(import_cost)
        self.assertEqual(import_cost.payment_offset, -2)
        import_cost.write({'planned_amount': 10000.0, 'm03_pct': 100.0})  # M03 cost paid in M01 (3 - 2 = 1)
        self.assertAlmostEqual(import_cost.cash_m01, 10000.0)
        self.assertAlmostEqual(import_cost.cash_m03, 0.0)

    def test_02_minimum_opening_cash_calculation(self):
        """Test running cash balance and minimum opening cash requirement formula"""
        plan = self.BudgetPlan.create({
            'name': 'Test Cash Flow Plan',
            'fiscal_year_id': self.fy_test.id,
        })

        proj = self.BudgetProject.create({
            'plan_id': plan.id,
            'name': 'Solar Substation Project',
            'code': 'SOL-01',
            'department_id': self.dept_test.id,
            'category_id': self.cat_gov.id,
            'status_group': 'committed',
            'contract_value': 50000.0,
            'revenue_planned': 50000.0,
            'wht_rate': 2.0,
        })

        # Add heavy upfront costs in M01 (Local purchase 20k) and M02 (15k)
        local_cost = proj.cost_spread_ids.filtered(lambda c: c.cost_type == 'local')
        local_cost.write({
            'planned_amount': 35000.0,
            'm01_pct': 57.14,  # ~20,000
            'm02_pct': 42.86,  # ~15,000
        })

        # Add receipt in M04 (Final progress payment 49,000 net)
        self.env['budget.receipt.term'].create({
            'project_id': proj.id,
            'term_type': 'progress_1',
            'month': '4',
            'pct_contract': 100.0,
        })

        plan._compute_plan_aggregates()
        # Because outpayments occur in M01/M02 before receipts in M04, running cash dips negative
        self.assertGreater(plan.min_opening_balance, 0.0, "Minimum opening balance must be positive to cover early deficit")

    def test_03_plan_revision_no_duplication(self):
        """Test that action_create_revision copies spreads and receipt terms cleanly without duplication"""
        plan = self.BudgetPlan.create({
            'name': 'Baseline Plan',
            'fiscal_year_id': self.fy_test.id,
            'state': 'approved',
        })

        proj = self.BudgetProject.create({
            'plan_id': plan.id,
            'name': 'Core Switch Refresh',
            'code': 'CSR-01',
            'department_id': self.dept_test.id,
            'category_id': self.cat_gov.id,
            'contract_value': 80000.0,
            'revenue_planned': 80000.0,
            'wht_rate': 2.0,
        })

        # Create two distinct receipt terms
        term1 = self.env['budget.receipt.term'].create({
            'project_id': proj.id,
            'term_type': 'advance',
            'month': '1',
            'pct_contract': 30.0,
        })
        term2 = self.env['budget.receipt.term'].create({
            'project_id': proj.id,
            'term_type': 'final',
            'month': '10',
            'pct_contract': 70.0,
        })

        self.assertEqual(len(proj.receipt_term_ids), 2)
        # Test month_index sorting: term1 (month 1, index 1) before term2 (month 10, index 10)
        self.assertEqual(term1.month_index, 1)
        self.assertEqual(term2.month_index, 10)

        # Create revision
        res = plan.action_create_revision()
        rev_plan_id = res['res_id']
        rev_plan = self.BudgetPlan.browse(rev_plan_id)

        self.assertEqual(len(rev_plan.project_ids), 1)
        rev_proj = rev_plan.project_ids[0]

        # Verify receipt terms count is NOT duplicated (must remain exactly 2)
        self.assertEqual(len(rev_proj.receipt_term_ids), 2, "Receipt terms must not be duplicated upon plan revision")
        self.assertEqual(len(rev_proj.revenue_spread_ids), 1, "Revenue spread must be exactly 1")
        self.assertEqual(len(rev_proj.cost_spread_ids), 4, "Cost spreads must be exactly 4")

    def test_04_reports_with_and_without_receipt_terms(self):
        """Test Cash Flow & Position report rendering for projects with and without explicit receipt terms"""
        plan = self.BudgetPlan.create({
            'name': 'Reporting Test Plan',
            'fiscal_year_id': self.fy_test.id,
        })

        # Project 1: Has revenue spread but NO manual receipt terms
        proj_no_rt = self.BudgetProject.create({
            'plan_id': plan.id,
            'name': 'Cloud Subscriptions',
            'code': 'CS-01',
            'department_id': self.dept_test.id,
            'category_id': self.cat_gov.id,
            'contract_value': 12000.0,
            'revenue_planned': 12000.0,
            'wht_rate': 2.0,
        })
        rs = proj_no_rt.revenue_spread_ids[0]
        # Spread 50% in M01, 50% in M02
        rs.write({'m01_pct': 50.0, 'm02_pct': 50.0})

        # Check plan totals include proj_no_rt's cash in
        plan.invalidate_recordset()
        self.assertAlmostEqual(plan.total_cash_in, 12000.0 * 0.98)

        # Render cashflow report viewer
        viewer = self.env['budget.report.viewer'].create({
            'plan_id': plan.id,
            'report_type': 'cashflow',
            'period_type': 'quarterly',
        })
        viewer._compute_html_content()
        self.assertTrue(viewer.html_content)
        # Verify non-zero receipts are present in HTML (12,000 * 0.98 = 11,760.0)
        self.assertIn("TOTAL CASH RECEIPTS", viewer.html_content)
        self.assertIn("11,760.0", viewer.html_content)

        # Test Project Breakdown report breakdown of receipts and payments
        # Add a project with explicit receipt terms and cost lines
        proj_rt = self.BudgetProject.create({
            'plan_id': plan.id,
            'name': 'Pro_2 Substation',
            'code': 'PRJ-02',
            'department_id': self.dept_test.id,
            'category_id': self.cat_gov.id,
            'contract_value': 1000.0,
            'wht_rate': 0.0,
        })
        self.env['budget.receipt.term'].create([
            {
                'project_id': proj_rt.id,
                'term_type': 'advance',
                'month': '1',
                'gross_amount': 700.0,
            },
            {
                'project_id': proj_rt.id,
                'term_type': 'progress_1',
                'month': '7',
                'gross_amount': 200.0,
            },
            {
                'project_id': proj_rt.id,
                'term_type': 'final',
                'month': '10',
                'gross_amount': 100.0,
            },
        ])
        cost_line = proj_rt.cost_spread_ids.filtered(lambda c: c.cost_type == 'other')
        cost_line.write({'m04': 400.0})

        breakdown_viewer = self.env['budget.report.viewer'].create({
            'plan_id': plan.id,
            'report_type': 'breakdown',
            'period_type': 'quarterly',
        })
        breakdown_viewer._compute_html_content()
        self.assertTrue(breakdown_viewer.html_content)
        self.assertIn("Cash Receipts (net of WHT)", breakdown_viewer.html_content)
        self.assertIn("Receipt: Advance Payment (M01 - Jul)", breakdown_viewer.html_content)
        self.assertIn("Receipt: Progress 1 (M07 - Jan)", breakdown_viewer.html_content)
        self.assertIn("Receipt: Final Payment (M10 - Apr)", breakdown_viewer.html_content)
        self.assertIn("Cash Payments", breakdown_viewer.html_content)
        self.assertIn("Payment: Other Direct Costs (Oct)", breakdown_viewer.html_content)

    def test_05_direct_amount_submission_and_editable_revenue(self):
        """Test submitting correct direct amounts into monthly fields and verify editable revenue"""
        plan = self.BudgetPlan.create({
            'name': 'Direct Amount Test Plan',
            'fiscal_year_id': self.fy_test.id,
        })

        proj = self.BudgetProject.create({
            'plan_id': plan.id,
            'name': 'Data Center Fiber Expansion',
            'code': 'DCF-01',
            'department_id': self.dept_test.id,
            'category_id': self.cat_gov.id,
            'contract_value': 100000.0,
            'wht_rate': 2.0,
        })

        # 1. Test Direct Revenue Spread Entry (Jul = 300, Aug = 700)
        rs = proj.revenue_spread_ids[0]
        rs.write({'m01': 300.0, 'm02': 700.0})
        self.assertAlmostEqual(rs.q1, 1000.0)
        self.assertAlmostEqual(rs.annual_total, 1000.0)
        self.assertAlmostEqual(rs.m01_pct, 30.0)
        self.assertAlmostEqual(rs.m02_pct, 70.0)

        # Verify revenue_planned automatically reflects the spread total
        proj.invalidate_recordset()
        self.assertAlmostEqual(proj.revenue_planned, 1000.0)

        # Verify revenue_planned can also be directly edited
        proj.write({'revenue_planned': 1200.0})
        self.assertAlmostEqual(proj.revenue_planned, 1200.0)

        # 2. Test Direct Cost Spread Entry (Jul = 100, Sep = 500) like in user screenshot
        cost_line = proj.cost_spread_ids.filtered(lambda c: c.cost_type == 'other')
        cost_line.write({'m01': 100.0, 'm03': 500.0})
        self.assertAlmostEqual(cost_line.q1, 600.0)
        self.assertAlmostEqual(cost_line.annual_total, 600.0)
        self.assertAlmostEqual(cost_line.planned_amount, 600.0)
        self.assertAlmostEqual(cost_line.cash_m01, 100.0)
        self.assertAlmostEqual(cost_line.cash_m03, 500.0)
        self.assertAlmostEqual(cost_line.cash_annual_total, 600.0)

        # Verify direct_costs_planned on project automatically equals 600
        proj.invalidate_recordset()
        self.assertAlmostEqual(proj.direct_costs_planned, 600.0)

        # 3. Test Direct Receipt Term Gross Amount Entry
        term = self.env['budget.receipt.term'].create({
            'project_id': proj.id,
            'term_type': 'advance',
            'month': '1',
            'gross_amount': 25000.0,
        })
        self.assertAlmostEqual(term.pct_contract, 25.0)  # 25,000 / 100,000 = 25%
        self.assertAlmostEqual(term.wht_amount, 500.0)   # 2% of 25,000
        self.assertAlmostEqual(term.net_amount, 24500.0)

        # 4. Verify Cash Flow report reflects the cash payments
        viewer = self.env['budget.report.viewer'].create({
            'plan_id': plan.id,
            'report_type': 'cashflow',
            'period_type': 'quarterly',
        })
        viewer._compute_html_content()
        # Verify 600.0 cash payment is reflected
        self.assertIn("600.0", viewer.html_content)
