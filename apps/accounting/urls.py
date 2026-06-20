from django.urls import path

from . import views

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
]
