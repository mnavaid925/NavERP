"""Accounting views package — split from views.py + views_advanced.py.

One sub-package per sub-module (2.1-2.15), one module per entity (mirrors models/ forms/ urls/).
This __init__ re-exports every view, so the apps/accounting/urls/ package (``views.<name>``)
works unchanged; it also re-exports the 3 private helpers the test-suite imports.
The separate ``views_advanced`` module is gone — its 79 views live in their sub-modules.
"""
from ._helpers import *  # noqa: F401,F403

# 2.1 Dashboard & Analytics
from .Dashboard.Dashboard import (
    accounting_dashboard,
)

# 2.2 General Ledger
from .GeneralLedger.TrialBalance import (
    trial_balance,
)
from .GeneralLedger.AccountLedger import (
    gl_account_ledger,
)
from .GeneralLedger.GLAccounts import (
    glaccount_list,
    glaccount_create,
    glaccount_detail,
    glaccount_edit,
    glaccount_delete,
)
from .GeneralLedger.FiscalPeriods import (
    fiscal_period_list,
    fiscal_period_create,
    fiscal_period_detail,
    fiscal_period_edit,
    fiscal_period_delete,
    fiscal_period_close,
)
from .GeneralLedger.JournalEntries import (
    journal_entry_list,
    journal_entry_create,
    journal_entry_detail,
    journal_entry_edit,
    journal_entry_delete,
    journal_entry_post,
    journal_entry_void,
)
from .GeneralLedger.Currencies import (
    currency_list,
    currency_create,
    currency_detail,
    currency_edit,
    currency_delete,
)
from .GeneralLedger.ExchangeRates import (
    exchange_rate_list,
    exchange_rate_create,
    exchange_rate_detail,
    exchange_rate_edit,
    exchange_rate_delete,
)

# 2.3 Accounts Payable
from .AccountsPayable.Bills import (
    _vendor_parties,
    bill_list,
    bill_create,
    bill_edit,
    _bill_form,
    bill_detail,
    bill_delete,
    bill_approve,
)
from .AccountsPayable.ApAging import (
    ap_aging,
)
from .AccountsPayable.Payments import (
    payment_schedule,
    payment_list,
    payment_create,
    payment_detail,
    payment_edit,
    payment_delete,
    payment_confirm,
    payment_void,
)
from .AccountsPayable.PaymentTerms import (
    payment_term_list,
    payment_term_create,
    payment_term_detail,
    payment_term_edit,
    payment_term_delete,
)
from .AccountsPayable.VendorProfiles import (
    vendor_profile_list,
    vendor_profile_create,
    vendor_profile_detail,
    vendor_profile_edit,
    vendor_profile_delete,
)

# 2.4 Accounts Receivable
from .AccountsReceivable.Invoices import (
    _customer_parties,
    invoice_list,
    invoice_create,
    invoice_edit,
    _invoice_form,
    invoice_detail,
    invoice_delete,
    invoice_post,
)
from .AccountsReceivable.ArAging import (
    ar_aging,
)
from .AccountsReceivable.RecurringInvoices import (
    recurringinvoice_list,
    recurringinvoice_create,
    recurringinvoice_detail,
    recurringinvoice_edit,
    recurringinvoice_delete,
    recurringinvoice_generate,
)
from .AccountsReceivable.CustomerProfiles import (
    customer_profile_list,
    customer_profile_create,
    customer_profile_detail,
    customer_profile_edit,
    customer_profile_delete,
)
from .AccountsReceivable.PaymentAllocations import (
    allocation_list,
    allocation_create,
    allocation_detail,
    allocation_edit,
    allocation_delete,
)

# 2.5 Cash Management
from .CashManagement.CashForecast import (
    cash_forecast,
)
from .CashManagement.BankAccounts import (
    bank_account_list,
    bank_account_create,
    bank_account_detail,
    bank_account_edit,
    bank_account_delete,
)
from .CashManagement.BankTransactions import (
    bank_transaction_list,
    bank_transaction_create,
    bank_transaction_detail,
    bank_transaction_edit,
    bank_transaction_delete,
    bank_transaction_import_csv,
)
from .CashManagement.Reconciliation import (
    reconciliation_list,
    reconciliation_create,
    reconciliation_detail,
    reconciliation_edit,
    reconciliation_delete,
    reconciliation_confirm,
)

# 2.6 Fixed Assets
from .FixedAssets.FixedAssetsRegister import (
    fixed_asset_list,
    fixed_asset_create,
    fixed_asset_detail,
    fixed_asset_edit,
    fixed_asset_delete,
    fixed_asset_depreciate,
)
from .FixedAssets.AssetDisposals import (
    asset_disposal_list,
    asset_disposal_create,
    asset_disposal_detail,
    asset_disposal_edit,
    asset_disposal_delete,
    asset_disposal_post,
)

# 2.7 Inventory & Cost Management
from .CostManagement.CostAllocations import (
    cost_allocation_list,
    cost_allocation_create,
    cost_allocation_detail,
    cost_allocation_edit,
    cost_allocation_delete,
    cost_allocation_post,
)

# 2.8 Payroll Integration
from .PayrollIntegration.PayrollRuns import (
    payroll_run_list,
    payroll_run_create,
    payroll_run_detail,
    payroll_run_edit,
    payroll_run_delete,
    payroll_run_post,
)

# 2.9 Project/Job Costing
from .ProjectCosting.Projects import (
    project_list,
    project_create,
    project_detail,
    project_edit,
    project_delete,
)
from .ProjectCosting.JobCostEntries import (
    job_cost_entry_list,
    job_cost_entry_create,
    job_cost_entry_detail,
    job_cost_entry_edit,
    job_cost_entry_delete,
    job_cost_entry_post,
)

# 2.10 Multi-Entity & Consolidation
from .MultiEntity.IntercompanyTransactions import (
    intercompany_list,
    intercompany_create,
    intercompany_detail,
    intercompany_edit,
    intercompany_delete,
    intercompany_post,
    intercompany_toggle_eliminated,
)

# 2.11 Tax
from .Tax.TaxCodes import (
    tax_code_list,
    tax_code_create,
    tax_code_detail,
    tax_code_edit,
    tax_code_delete,
)
from .Tax.TaxReturns import (
    tax_return_list,
    tax_return_create,
    tax_return_detail,
    tax_return_edit,
    tax_return_delete,
)

# 2.12 Reporting & Compliance
from .Reporting.BalanceSheet import (
    balance_sheet,
)
from .Reporting.ProfitAndLoss import (
    profit_and_loss,
)
from .Reporting.ScheduledReports import (
    scheduled_report_list,
    scheduled_report_create,
    scheduled_report_detail,
    scheduled_report_edit,
    scheduled_report_delete,
)

# 2.13 Budgeting & Planning
from .Budgeting.Budgets import (
    budget_list,
    budget_create,
    budget_detail,
    budget_edit,
)
from .Budgeting.BudgetVariance import (
    budget_delete,
    budget_variance,
)
from .Budgeting.BudgetLines import (
    budget_line_create,
    budget_line_edit,
    budget_line_delete,
)

# 2.14 Audit & Controls
from .AuditControls.InternalControls import (
    internal_control_list,
    internal_control_create,
    internal_control_detail,
    internal_control_edit,
    internal_control_delete,
)

# 2.15 Integration & API
from .Integration.IntegrationConfigs import (
    integration_list,
    integration_create,
    integration_detail,
    integration_edit,
    integration_delete,
    integration_rotate_key,
)

# private helpers imported directly by the test-suite
from ._helpers import _account_balances, _aging, _cash_position  # noqa: F401
