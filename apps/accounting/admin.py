"""Admin registration for the accounting ledger. System-set fields (numbers, ``*_at``/``*_by``,
``normal_balance``, totals) are read-only so an admin can't bypass the posting workflow."""
from django.contrib import admin

from .models import (
    BankAccount,
    BankTransaction,
    Bill,
    BillLine,
    Currency,
    CustomerProfile,
    ExchangeRate,
    FiscalPeriod,
    GLAccount,
    Invoice,
    InvoiceLine,
    JournalEntry,
    JournalLine,
    Payment,
    PaymentAllocation,
    PaymentTerm,
    ReconciliationMatch,
    VendorProfile,
)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("currency", "rate_date", "rate", "source", "tenant")
    list_filter = ("source", "tenant", "currency")
    search_fields = ("currency__code",)


@admin.register(GLAccount)
class GLAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "normal_balance", "is_active", "tenant")
    list_filter = ("account_type", "is_active", "tenant")
    search_fields = ("code", "name")
    readonly_fields = ("normal_balance", "created_at", "updated_at")


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "period_type", "start_date", "end_date", "status", "tenant")
    list_filter = ("status", "period_type", "tenant")
    search_fields = ("name",)
    readonly_fields = ("closed_by", "closed_at", "created_at", "updated_at")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("number", "entry_date", "entry_type", "status", "fiscal_period", "tenant")
    list_filter = ("status", "entry_type", "tenant")
    search_fields = ("number", "description", "reference")
    readonly_fields = ("number", "status", "reversal_of", "created_by", "approved_by",
                       "posted_at", "created_at", "updated_at")
    inlines = [JournalLineInline]


@admin.register(JournalLine)
class JournalLineAdmin(admin.ModelAdmin):
    list_display = ("entry", "gl_account", "debit", "credit")
    search_fields = ("gl_account__code", "description")


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display = ("name", "days_due", "discount_pct", "discount_days", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("name",)


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ("party", "payment_terms", "currency", "is_1099", "is_active", "tenant")
    list_filter = ("is_1099", "is_active", "tenant")
    search_fields = ("party__name",)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("party", "payment_terms", "credit_limit", "credit_on_hold", "is_active", "tenant")
    list_filter = ("credit_on_hold", "is_active", "tenant")
    search_fields = ("party__name",)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "bank_name", "currency", "gl_account", "opening_balance", "is_active", "tenant")
    list_filter = ("is_active", "tenant", "currency")
    search_fields = ("name", "bank_name")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "kind", "party", "issue_date", "due_date", "status", "total", "tenant")
    list_filter = ("status", "kind", "tenant")
    search_fields = ("number", "party__name")
    readonly_fields = ("number", "journal_entry", "subtotal", "tax_total", "total",
                       "created_at", "updated_at")
    inlines = [InvoiceLineInline]


class BillLineInline(admin.TabularInline):
    model = BillLine
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "bill_date", "due_date", "status", "total", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "party__name")
    readonly_fields = ("number", "journal_entry", "subtotal", "tax_total", "total", "approved_by",
                       "created_at", "updated_at")
    inlines = [BillLineInline]


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("number", "direction", "party", "bank_account", "payment_date", "amount", "status", "tenant")
    list_filter = ("direction", "status", "payment_method", "tenant")
    search_fields = ("number", "party__name")
    readonly_fields = ("number", "journal_entry", "created_at", "updated_at")
    inlines = [PaymentAllocationInline]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ("payment", "invoice", "bill", "allocated_amount", "discount_taken")
    search_fields = ("payment__number", "invoice__number", "bill__number")


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_date", "bank_account", "description", "amount", "direction", "status", "tenant")
    list_filter = ("direction", "status", "source", "tenant")
    search_fields = ("description", "external_ref")
    readonly_fields = ("status",)


@admin.register(ReconciliationMatch)
class ReconciliationMatchAdmin(admin.ModelAdmin):
    list_display = ("bank_transaction", "payment", "journal_line", "is_confirmed", "matched_by", "tenant")
    list_filter = ("is_confirmed", "tenant")
    readonly_fields = ("matched_by", "matched_at")
