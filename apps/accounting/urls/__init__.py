"""Accounting URLconf package — split from the former monolithic apps/accounting/urls.py.

One sub-package per sub-module (2.1-2.15), one module per entity, mirroring
apps/accounting/views/. Each entity module exposes its own ``urlpatterns``; this __init__
concatenates them GROUPED BY ENTITY and keeps ``app_name = "accounting"``, so every
``accounting:<name>`` reverse and ``include("apps.accounting.urls")`` is unchanged.

Django is first-match-wins, so ORDER IS BEHAVIOUR. Grouping by entity is not necessarily the
monolith's exact sequence; the split was verified to leave every route's resolve()/reverse()
identical. When you ADD a route with a greedy converter, check it against the whole list below,
not just its own module, and keep literal routes before ``<int:pk>`` ones within a module.
"""
from .Dashboard.Dashboard import urlpatterns as _dashboard_dashboard
from .GeneralLedger.TrialBalance import urlpatterns as _generalledger_trialbalance
from .CashManagement.CashForecast import urlpatterns as _cashmanagement_cashforecast
from .AccountsPayable.Payments import urlpatterns as _accountspayable_payments
from .AccountsReceivable.ArAging import urlpatterns as _accountsreceivable_araging
from .AccountsPayable.ApAging import urlpatterns as _accountspayable_apaging
from .GeneralLedger.AccountLedger import urlpatterns as _generalledger_accountledger
from .GeneralLedger.GLAccounts import urlpatterns as _generalledger_glaccounts
from .GeneralLedger.FiscalPeriods import urlpatterns as _generalledger_fiscalperiods
from .GeneralLedger.JournalEntries import urlpatterns as _generalledger_journalentries
from .GeneralLedger.Currencies import urlpatterns as _generalledger_currencies
from .GeneralLedger.ExchangeRates import urlpatterns as _generalledger_exchangerates
from .AccountsPayable.PaymentTerms import urlpatterns as _accountspayable_paymentterms
from .AccountsPayable.VendorProfiles import urlpatterns as _accountspayable_vendorprofiles
from .AccountsPayable.Bills import urlpatterns as _accountspayable_bills
from .AccountsReceivable.CustomerProfiles import urlpatterns as _accountsreceivable_customerprofiles
from .AccountsReceivable.Invoices import urlpatterns as _accountsreceivable_invoices
from .AccountsReceivable.RecurringInvoices import urlpatterns as _accountsreceivable_recurringinvoices
from .AccountsReceivable.PaymentAllocations import urlpatterns as _accountsreceivable_paymentallocations
from .CashManagement.BankAccounts import urlpatterns as _cashmanagement_bankaccounts
from .CashManagement.BankTransactions import urlpatterns as _cashmanagement_banktransactions
from .CashManagement.Reconciliation import urlpatterns as _cashmanagement_reconciliation
from .FixedAssets.FixedAssetsRegister import urlpatterns as _fixedassets_fixedassetsregister
from .FixedAssets.AssetDisposals import urlpatterns as _fixedassets_assetdisposals
from .CostManagement.CostAllocations import urlpatterns as _costmanagement_costallocations
from .PayrollIntegration.PayrollRuns import urlpatterns as _payrollintegration_payrollruns
from .ProjectCosting.Projects import urlpatterns as _projectcosting_projects
from .ProjectCosting.JobCostEntries import urlpatterns as _projectcosting_jobcostentries
from .MultiEntity.IntercompanyTransactions import urlpatterns as _multientity_intercompanytransactions
from .Tax.TaxCodes import urlpatterns as _tax_taxcodes
from .Tax.TaxReturns import urlpatterns as _tax_taxreturns
from .Reporting.BalanceSheet import urlpatterns as _reporting_balancesheet
from .Reporting.ProfitAndLoss import urlpatterns as _reporting_profitandloss
from .Reporting.ScheduledReports import urlpatterns as _reporting_scheduledreports
from .Budgeting.Budgets import urlpatterns as _budgeting_budgets
from .Budgeting.BudgetVariance import urlpatterns as _budgeting_budgetvariance
from .Budgeting.BudgetLines import urlpatterns as _budgeting_budgetlines
from .AuditControls.InternalControls import urlpatterns as _auditcontrols_internalcontrols
from .Integration.IntegrationConfigs import urlpatterns as _integration_integrationconfigs

app_name = "accounting"

urlpatterns = [
    *_dashboard_dashboard,  # Dashboard/Dashboard
    *_generalledger_trialbalance,  # GeneralLedger/TrialBalance
    *_cashmanagement_cashforecast,  # CashManagement/CashForecast
    *_accountspayable_payments,  # AccountsPayable/Payments
    *_accountsreceivable_araging,  # AccountsReceivable/ArAging
    *_accountspayable_apaging,  # AccountsPayable/ApAging
    *_generalledger_accountledger,  # GeneralLedger/AccountLedger
    *_generalledger_glaccounts,  # GeneralLedger/GLAccounts
    *_generalledger_fiscalperiods,  # GeneralLedger/FiscalPeriods
    *_generalledger_journalentries,  # GeneralLedger/JournalEntries
    *_generalledger_currencies,  # GeneralLedger/Currencies
    *_generalledger_exchangerates,  # GeneralLedger/ExchangeRates
    *_accountspayable_paymentterms,  # AccountsPayable/PaymentTerms
    *_accountspayable_vendorprofiles,  # AccountsPayable/VendorProfiles
    *_accountspayable_bills,  # AccountsPayable/Bills
    *_accountsreceivable_customerprofiles,  # AccountsReceivable/CustomerProfiles
    *_accountsreceivable_invoices,  # AccountsReceivable/Invoices
    *_accountsreceivable_recurringinvoices,  # AccountsReceivable/RecurringInvoices
    *_accountsreceivable_paymentallocations,  # AccountsReceivable/PaymentAllocations
    *_cashmanagement_bankaccounts,  # CashManagement/BankAccounts
    *_cashmanagement_banktransactions,  # CashManagement/BankTransactions
    *_cashmanagement_reconciliation,  # CashManagement/Reconciliation
    *_fixedassets_fixedassetsregister,  # FixedAssets/FixedAssetsRegister
    *_fixedassets_assetdisposals,  # FixedAssets/AssetDisposals
    *_costmanagement_costallocations,  # CostManagement/CostAllocations
    *_payrollintegration_payrollruns,  # PayrollIntegration/PayrollRuns
    *_projectcosting_projects,  # ProjectCosting/Projects
    *_projectcosting_jobcostentries,  # ProjectCosting/JobCostEntries
    *_multientity_intercompanytransactions,  # MultiEntity/IntercompanyTransactions
    *_tax_taxcodes,  # Tax/TaxCodes
    *_tax_taxreturns,  # Tax/TaxReturns
    *_reporting_balancesheet,  # Reporting/BalanceSheet
    *_reporting_profitandloss,  # Reporting/ProfitAndLoss
    *_reporting_scheduledreports,  # Reporting/ScheduledReports
    *_budgeting_budgets,  # Budgeting/Budgets
    *_budgeting_budgetvariance,  # Budgeting/BudgetVariance
    *_budgeting_budgetlines,  # Budgeting/BudgetLines
    *_auditcontrols_internalcontrols,  # AuditControls/InternalControls
    *_integration_integrationconfigs,  # Integration/IntegrationConfigs
]
