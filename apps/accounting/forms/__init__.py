"""Accounting forms package — split from forms.py + forms_advanced.py.

One sub-package per sub-module (2.1-2.15), one module per entity (mirrors models/ views/ urls/).
This __init__ re-exports every form + the 3 inline formsets, so
``from apps.accounting.forms import InvoiceForm`` is unchanged. The advanced forms are now here
too — the separate ``forms_advanced`` module is gone.
"""
from ._common import *  # noqa: F401,F403

# 2.2 General Ledger
from .GeneralLedger.Currencies import (
    CurrencyForm,
)
from .GeneralLedger.ExchangeRates import (
    ExchangeRateForm,
)
from .GeneralLedger.GLAccounts import (
    GLAccountForm,
)
from .GeneralLedger.FiscalPeriods import (
    FiscalPeriodForm,
)
from .GeneralLedger.JournalEntries import (
    JournalEntryForm,
    JournalLineForm,
    JournalLineFormSet,
)

# 2.3 Accounts Payable
from .AccountsPayable.PaymentTerms import (
    PaymentTermForm,
)
from .AccountsPayable.VendorProfiles import (
    VendorProfileForm,
)
from .AccountsPayable.Bills import (
    BillForm,
    BillLineForm,
    BillLineFormSet,
)
from .AccountsPayable.Payments import (
    PaymentForm,
)

# 2.4 Accounts Receivable
from .AccountsReceivable.CustomerProfiles import (
    CustomerProfileForm,
)
from .AccountsReceivable.Invoices import (
    InvoiceForm,
    InvoiceLineForm,
    InvoiceLineFormSet,
)
from .AccountsReceivable.RecurringInvoices import (
    RecurringInvoiceForm,
)
from .AccountsReceivable.PaymentAllocations import (
    PaymentAllocationForm,
)

# 2.5 Cash Management
from .CashManagement.BankAccounts import (
    BankAccountForm,
)
from .CashManagement.BankTransactions import (
    BankTransactionForm,
    CsvImportForm,
)
from .CashManagement.Reconciliation import (
    ReconciliationMatchForm,
)

# 2.6 Fixed Assets
from .FixedAssets.FixedAssetsRegister import (
    FixedAssetForm,
)
from .FixedAssets.AssetDisposals import (
    AssetDisposalForm,
)

# 2.7 Inventory & Cost Management
from .CostManagement.CostAllocations import (
    CostAllocationForm,
)

# 2.8 Payroll Integration
from .PayrollIntegration.PayrollRuns import (
    PayrollRunForm,
)

# 2.9 Project/Job Costing
from .ProjectCosting.Projects import (
    ProjectForm,
)
from .ProjectCosting.JobCostEntries import (
    JobCostEntryForm,
)

# 2.10 Multi-Entity & Consolidation
from .MultiEntity.IntercompanyTransactions import (
    IntercompanyTransactionForm,
)

# 2.11 Tax
from .Tax.TaxCodes import (
    TaxCodeForm,
)
from .Tax.TaxReturns import (
    TaxReturnForm,
)

# 2.12 Reporting & Compliance
from .Reporting.ScheduledReports import (
    ScheduledReportForm,
)

# 2.13 Budgeting & Planning
from .Budgeting.Budgets import (
    BudgetForm,
)
from .Budgeting.BudgetLines import (
    BudgetLineForm,
)

# 2.14 Audit & Controls
from .AuditControls.InternalControls import (
    InternalControlForm,
)

# 2.15 Integration & API
from .Integration.IntegrationConfigs import (
    IntegrationConfigForm,
)
