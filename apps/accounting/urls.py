from django.urls import path

from . import views
from . import views_advanced as adv

app_name = "accounting"

urlpatterns = [
    # 2.1 Dashboard & reports
    path("", views.accounting_dashboard, name="accounting_dashboard"),
    path("dashboard/", views.accounting_dashboard, name="dashboard"),
    path("reports/trial-balance/", views.trial_balance, name="trial_balance"),
    path("reports/ar-aging/", views.ar_aging, name="ar_aging"),
    path("reports/ap-aging/", views.ap_aging, name="ap_aging"),
    path("reports/ledger/<int:account_pk>/", views.gl_account_ledger, name="gl_account_ledger"),

    # 2.2 GL — Chart of Accounts
    path("glaccounts/", views.glaccount_list, name="glaccount_list"),
    path("glaccounts/add/", views.glaccount_create, name="glaccount_create"),
    path("glaccounts/<int:pk>/", views.glaccount_detail, name="glaccount_detail"),
    path("glaccounts/<int:pk>/edit/", views.glaccount_edit, name="glaccount_edit"),
    path("glaccounts/<int:pk>/delete/", views.glaccount_delete, name="glaccount_delete"),

    # 2.2 GL — Fiscal periods
    path("fiscal-periods/", views.fiscal_period_list, name="fiscal_period_list"),
    path("fiscal-periods/add/", views.fiscal_period_create, name="fiscal_period_create"),
    path("fiscal-periods/<int:pk>/", views.fiscal_period_detail, name="fiscal_period_detail"),
    path("fiscal-periods/<int:pk>/edit/", views.fiscal_period_edit, name="fiscal_period_edit"),
    path("fiscal-periods/<int:pk>/delete/", views.fiscal_period_delete, name="fiscal_period_delete"),
    path("fiscal-periods/<int:pk>/close/", views.fiscal_period_close, name="fiscal_period_close"),

    # 2.2 GL — Journal entries
    path("journal-entries/", views.journal_entry_list, name="journal_entry_list"),
    path("journal-entries/add/", views.journal_entry_create, name="journal_entry_create"),
    path("journal-entries/<int:pk>/", views.journal_entry_detail, name="journal_entry_detail"),
    path("journal-entries/<int:pk>/edit/", views.journal_entry_edit, name="journal_entry_edit"),
    path("journal-entries/<int:pk>/delete/", views.journal_entry_delete, name="journal_entry_delete"),
    path("journal-entries/<int:pk>/post/", views.journal_entry_post, name="journal_entry_post"),
    path("journal-entries/<int:pk>/void/", views.journal_entry_void, name="journal_entry_void"),

    # 2.2 GL — Currencies & exchange rates
    path("currencies/", views.currency_list, name="currency_list"),
    path("currencies/add/", views.currency_create, name="currency_create"),
    path("currencies/<int:pk>/", views.currency_detail, name="currency_detail"),
    path("currencies/<int:pk>/edit/", views.currency_edit, name="currency_edit"),
    path("currencies/<int:pk>/delete/", views.currency_delete, name="currency_delete"),
    path("exchange-rates/", views.exchange_rate_list, name="exchange_rate_list"),
    path("exchange-rates/add/", views.exchange_rate_create, name="exchange_rate_create"),
    path("exchange-rates/<int:pk>/", views.exchange_rate_detail, name="exchange_rate_detail"),
    path("exchange-rates/<int:pk>/edit/", views.exchange_rate_edit, name="exchange_rate_edit"),
    path("exchange-rates/<int:pk>/delete/", views.exchange_rate_delete, name="exchange_rate_delete"),

    # 2.3 AP — Payment terms
    path("payment-terms/", views.payment_term_list, name="payment_term_list"),
    path("payment-terms/add/", views.payment_term_create, name="payment_term_create"),
    path("payment-terms/<int:pk>/", views.payment_term_detail, name="payment_term_detail"),
    path("payment-terms/<int:pk>/edit/", views.payment_term_edit, name="payment_term_edit"),
    path("payment-terms/<int:pk>/delete/", views.payment_term_delete, name="payment_term_delete"),

    # 2.3 AP — Vendor profiles
    path("vendor-profiles/", views.vendor_profile_list, name="vendor_profile_list"),
    path("vendor-profiles/add/", views.vendor_profile_create, name="vendor_profile_create"),
    path("vendor-profiles/<int:pk>/", views.vendor_profile_detail, name="vendor_profile_detail"),
    path("vendor-profiles/<int:pk>/edit/", views.vendor_profile_edit, name="vendor_profile_edit"),
    path("vendor-profiles/<int:pk>/delete/", views.vendor_profile_delete, name="vendor_profile_delete"),

    # 2.3 AP — Bills
    path("bills/", views.bill_list, name="bill_list"),
    path("bills/add/", views.bill_create, name="bill_create"),
    path("bills/<int:pk>/", views.bill_detail, name="bill_detail"),
    path("bills/<int:pk>/edit/", views.bill_edit, name="bill_edit"),
    path("bills/<int:pk>/delete/", views.bill_delete, name="bill_delete"),
    path("bills/<int:pk>/approve/", views.bill_approve, name="bill_approve"),

    # 2.4 AR — Customer profiles
    path("customer-profiles/", views.customer_profile_list, name="customer_profile_list"),
    path("customer-profiles/add/", views.customer_profile_create, name="customer_profile_create"),
    path("customer-profiles/<int:pk>/", views.customer_profile_detail, name="customer_profile_detail"),
    path("customer-profiles/<int:pk>/edit/", views.customer_profile_edit, name="customer_profile_edit"),
    path("customer-profiles/<int:pk>/delete/", views.customer_profile_delete, name="customer_profile_delete"),

    # 2.4 AR — Invoices
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/add/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/edit/", views.invoice_edit, name="invoice_edit"),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),
    path("invoices/<int:pk>/post/", views.invoice_post, name="invoice_post"),

    # 2.3+2.4 — Payments + cash application
    path("payments/", views.payment_list, name="payment_list"),
    path("payments/add/", views.payment_create, name="payment_create"),
    path("payments/<int:pk>/", views.payment_detail, name="payment_detail"),
    path("payments/<int:pk>/edit/", views.payment_edit, name="payment_edit"),
    path("payments/<int:pk>/delete/", views.payment_delete, name="payment_delete"),
    path("payments/<int:pk>/confirm/", views.payment_confirm, name="payment_confirm"),
    path("payments/<int:pk>/void/", views.payment_void, name="payment_void"),
    path("allocations/", views.allocation_list, name="allocation_list"),
    path("allocations/add/", views.allocation_create, name="allocation_create"),
    path("allocations/<int:pk>/", views.allocation_detail, name="allocation_detail"),
    path("allocations/<int:pk>/edit/", views.allocation_edit, name="allocation_edit"),
    path("allocations/<int:pk>/delete/", views.allocation_delete, name="allocation_delete"),

    # 2.5 Cash — Bank accounts
    path("bank-accounts/", views.bank_account_list, name="bank_account_list"),
    path("bank-accounts/add/", views.bank_account_create, name="bank_account_create"),
    path("bank-accounts/<int:pk>/", views.bank_account_detail, name="bank_account_detail"),
    path("bank-accounts/<int:pk>/edit/", views.bank_account_edit, name="bank_account_edit"),
    path("bank-accounts/<int:pk>/delete/", views.bank_account_delete, name="bank_account_delete"),

    # 2.5 Cash — Bank transactions
    path("bank-transactions/", views.bank_transaction_list, name="bank_transaction_list"),
    path("bank-transactions/add/", views.bank_transaction_create, name="bank_transaction_create"),
    path("bank-transactions/import-csv/", views.bank_transaction_import_csv, name="bank_transaction_import_csv"),
    path("bank-transactions/<int:pk>/", views.bank_transaction_detail, name="bank_transaction_detail"),
    path("bank-transactions/<int:pk>/edit/", views.bank_transaction_edit, name="bank_transaction_edit"),
    path("bank-transactions/<int:pk>/delete/", views.bank_transaction_delete, name="bank_transaction_delete"),

    # 2.5 Cash — Reconciliation
    path("reconciliation/", views.reconciliation_list, name="reconciliation_list"),
    path("reconciliation/add/", views.reconciliation_create, name="reconciliation_create"),
    path("reconciliation/<int:pk>/", views.reconciliation_detail, name="reconciliation_detail"),
    path("reconciliation/<int:pk>/edit/", views.reconciliation_edit, name="reconciliation_edit"),
    path("reconciliation/<int:pk>/delete/", views.reconciliation_delete, name="reconciliation_delete"),
    path("reconciliation/<int:pk>/confirm/", views.reconciliation_confirm, name="reconciliation_confirm"),

    # ===================== Advanced sub-modules 2.6–2.15 =====================
    # 2.6 Fixed Assets
    path("fixed-assets/", adv.fixed_asset_list, name="fixed_asset_list"),
    path("fixed-assets/add/", adv.fixed_asset_create, name="fixed_asset_create"),
    path("fixed-assets/<int:pk>/", adv.fixed_asset_detail, name="fixed_asset_detail"),
    path("fixed-assets/<int:pk>/edit/", adv.fixed_asset_edit, name="fixed_asset_edit"),
    path("fixed-assets/<int:pk>/delete/", adv.fixed_asset_delete, name="fixed_asset_delete"),
    path("fixed-assets/<int:pk>/depreciate/", adv.fixed_asset_depreciate, name="fixed_asset_depreciate"),
    path("asset-disposals/", adv.asset_disposal_list, name="asset_disposal_list"),
    path("asset-disposals/add/", adv.asset_disposal_create, name="asset_disposal_create"),
    path("asset-disposals/<int:pk>/", adv.asset_disposal_detail, name="asset_disposal_detail"),
    path("asset-disposals/<int:pk>/edit/", adv.asset_disposal_edit, name="asset_disposal_edit"),
    path("asset-disposals/<int:pk>/delete/", adv.asset_disposal_delete, name="asset_disposal_delete"),
    path("asset-disposals/<int:pk>/post/", adv.asset_disposal_post, name="asset_disposal_post"),

    # 2.7 Cost allocation
    path("cost-allocations/", adv.cost_allocation_list, name="cost_allocation_list"),
    path("cost-allocations/add/", adv.cost_allocation_create, name="cost_allocation_create"),
    path("cost-allocations/<int:pk>/", adv.cost_allocation_detail, name="cost_allocation_detail"),
    path("cost-allocations/<int:pk>/edit/", adv.cost_allocation_edit, name="cost_allocation_edit"),
    path("cost-allocations/<int:pk>/delete/", adv.cost_allocation_delete, name="cost_allocation_delete"),
    path("cost-allocations/<int:pk>/post/", adv.cost_allocation_post, name="cost_allocation_post"),

    # 2.8 Payroll
    path("payroll-runs/", adv.payroll_run_list, name="payroll_run_list"),
    path("payroll-runs/add/", adv.payroll_run_create, name="payroll_run_create"),
    path("payroll-runs/<int:pk>/", adv.payroll_run_detail, name="payroll_run_detail"),
    path("payroll-runs/<int:pk>/edit/", adv.payroll_run_edit, name="payroll_run_edit"),
    path("payroll-runs/<int:pk>/delete/", adv.payroll_run_delete, name="payroll_run_delete"),
    path("payroll-runs/<int:pk>/post/", adv.payroll_run_post, name="payroll_run_post"),

    # 2.9 Project / Job costing
    path("projects/", adv.project_list, name="project_list"),
    path("projects/add/", adv.project_create, name="project_create"),
    path("projects/<int:pk>/", adv.project_detail, name="project_detail"),
    path("projects/<int:pk>/edit/", adv.project_edit, name="project_edit"),
    path("projects/<int:pk>/delete/", adv.project_delete, name="project_delete"),
    path("job-cost-entries/", adv.job_cost_entry_list, name="job_cost_entry_list"),
    path("job-cost-entries/add/", adv.job_cost_entry_create, name="job_cost_entry_create"),
    path("job-cost-entries/<int:pk>/", adv.job_cost_entry_detail, name="job_cost_entry_detail"),
    path("job-cost-entries/<int:pk>/edit/", adv.job_cost_entry_edit, name="job_cost_entry_edit"),
    path("job-cost-entries/<int:pk>/delete/", adv.job_cost_entry_delete, name="job_cost_entry_delete"),
    path("job-cost-entries/<int:pk>/post/", adv.job_cost_entry_post, name="job_cost_entry_post"),

    # 2.10 Multi-entity / Intercompany
    path("intercompany/", adv.intercompany_list, name="intercompany_list"),
    path("intercompany/add/", adv.intercompany_create, name="intercompany_create"),
    path("intercompany/<int:pk>/", adv.intercompany_detail, name="intercompany_detail"),
    path("intercompany/<int:pk>/edit/", adv.intercompany_edit, name="intercompany_edit"),
    path("intercompany/<int:pk>/delete/", adv.intercompany_delete, name="intercompany_delete"),
    path("intercompany/<int:pk>/post/", adv.intercompany_post, name="intercompany_post"),
    path("intercompany/<int:pk>/toggle-eliminated/", adv.intercompany_toggle_eliminated, name="intercompany_toggle_eliminated"),

    # 2.11 Tax
    path("tax-codes/", adv.tax_code_list, name="tax_code_list"),
    path("tax-codes/add/", adv.tax_code_create, name="tax_code_create"),
    path("tax-codes/<int:pk>/", adv.tax_code_detail, name="tax_code_detail"),
    path("tax-codes/<int:pk>/edit/", adv.tax_code_edit, name="tax_code_edit"),
    path("tax-codes/<int:pk>/delete/", adv.tax_code_delete, name="tax_code_delete"),
    path("tax-returns/", adv.tax_return_list, name="tax_return_list"),
    path("tax-returns/add/", adv.tax_return_create, name="tax_return_create"),
    path("tax-returns/<int:pk>/", adv.tax_return_detail, name="tax_return_detail"),
    path("tax-returns/<int:pk>/edit/", adv.tax_return_edit, name="tax_return_edit"),
    path("tax-returns/<int:pk>/delete/", adv.tax_return_delete, name="tax_return_delete"),

    # 2.12 Reporting & compliance
    path("reports/balance-sheet/", adv.balance_sheet, name="balance_sheet"),
    path("reports/profit-and-loss/", adv.profit_and_loss, name="profit_and_loss"),
    path("scheduled-reports/", adv.scheduled_report_list, name="scheduled_report_list"),
    path("scheduled-reports/add/", adv.scheduled_report_create, name="scheduled_report_create"),
    path("scheduled-reports/<int:pk>/", adv.scheduled_report_detail, name="scheduled_report_detail"),
    path("scheduled-reports/<int:pk>/edit/", adv.scheduled_report_edit, name="scheduled_report_edit"),
    path("scheduled-reports/<int:pk>/delete/", adv.scheduled_report_delete, name="scheduled_report_delete"),

    # 2.13 Budgeting & planning
    path("budgets/", adv.budget_list, name="budget_list"),
    path("budgets/add/", adv.budget_create, name="budget_create"),
    path("budgets/<int:pk>/", adv.budget_detail, name="budget_detail"),
    path("budgets/<int:pk>/edit/", adv.budget_edit, name="budget_edit"),
    path("budgets/<int:pk>/delete/", adv.budget_delete, name="budget_delete"),
    path("budget-lines/add/", adv.budget_line_create, name="budget_line_create"),
    path("budget-lines/<int:pk>/edit/", adv.budget_line_edit, name="budget_line_edit"),
    path("budget-lines/<int:pk>/delete/", adv.budget_line_delete, name="budget_line_delete"),
    path("reports/budget-variance/", adv.budget_variance, name="budget_variance"),

    # 2.14 Audit & controls
    path("controls/", adv.internal_control_list, name="internal_control_list"),
    path("controls/add/", adv.internal_control_create, name="internal_control_create"),
    path("controls/<int:pk>/", adv.internal_control_detail, name="internal_control_detail"),
    path("controls/<int:pk>/edit/", adv.internal_control_edit, name="internal_control_edit"),
    path("controls/<int:pk>/delete/", adv.internal_control_delete, name="internal_control_delete"),

    # 2.15 Integration & API
    path("integrations/", adv.integration_list, name="integration_list"),
    path("integrations/add/", adv.integration_create, name="integration_create"),
    path("integrations/<int:pk>/", adv.integration_detail, name="integration_detail"),
    path("integrations/<int:pk>/edit/", adv.integration_edit, name="integration_edit"),
    path("integrations/<int:pk>/delete/", adv.integration_delete, name="integration_delete"),
    path("integrations/<int:pk>/rotate-key/", adv.integration_rotate_key, name="integration_rotate_key"),
]
