"""Accounting models package — split from models.py + models_advanced.py.

One sub-package per sub-module (2.1-2.15), one module per entity (mirrors forms/ views/ urls/).
This __init__ re-exports every model + the ZERO/add_months/TenantOwned/TenantNumbered base, so
``from apps.accounting.models import Invoice`` (CRM, HRM, admin, seeder, tests) is unchanged.
The old separate ``models_advanced`` module is gone — its 14 models live in their sub-modules.
"""
from ._base import *  # noqa: F401,F403

# 2.2 General Ledger
from .GeneralLedger.Currencies import (
    Currency,
)
from .GeneralLedger.ExchangeRates import (
    ExchangeRate,
)
from .GeneralLedger.GLAccounts import (
    GLAccount,
)
from .GeneralLedger.FiscalPeriods import (
    FiscalPeriod,
)
from .GeneralLedger.JournalEntries import (
    JournalEntry,
    JournalLine,
)

# 2.3 Accounts Payable
from .AccountsPayable.PaymentTerms import (
    PaymentTerm,
)
from .AccountsPayable.VendorProfiles import (
    VendorProfile,
)
from .AccountsPayable.Bills import (
    Bill,
    BillLine,
)
from .AccountsPayable.Payments import (
    Payment,
)

# 2.4 Accounts Receivable
from .AccountsReceivable.CustomerProfiles import (
    CustomerProfile,
)
from .AccountsReceivable.Invoices import (
    Invoice,
    InvoiceLine,
)
from .AccountsReceivable.RecurringInvoices import (
    RecurringInvoice,
)
from .AccountsReceivable.PaymentAllocations import (
    PaymentAllocation,
)

# 2.5 Cash Management
from .CashManagement.BankAccounts import (
    BankAccount,
)
from .CashManagement.BankTransactions import (
    BankTransaction,
)
from .CashManagement.Reconciliation import (
    ReconciliationMatch,
)

# 2.6 Fixed Assets
from .FixedAssets.FixedAssetsRegister import (
    FixedAsset,
)
from .FixedAssets.AssetDisposals import (
    AssetDisposal,
)

# 2.7 Inventory & Cost Management
from .CostManagement.CostAllocations import (
    CostAllocation,
)

# 2.8 Payroll Integration
from .PayrollIntegration.PayrollRuns import (
    PayrollRun,
)

# 2.9 Project/Job Costing
from .ProjectCosting.Projects import (
    Project,
)
from .ProjectCosting.JobCostEntries import (
    JobCostEntry,
)

# 2.10 Multi-Entity & Consolidation
from .MultiEntity.IntercompanyTransactions import (
    IntercompanyTransaction,
)

# 2.11 Tax
from .Tax.TaxCodes import (
    TaxCode,
)
from .Tax.TaxReturns import (
    TaxReturn,
)

# 2.12 Reporting & Compliance
from .Reporting.ScheduledReports import (
    ScheduledReport,
)

# 2.13 Budgeting & Planning
from .Budgeting.Budgets import (
    Budget,
)
from .Budgeting.BudgetLines import (
    BudgetLine,
)

# 2.14 Audit & Controls
from .AuditControls.InternalControls import (
    InternalControl,
)

# 2.15 Integration & API
from .Integration.IntegrationConfigs import (
    IntegrationConfig,
)
