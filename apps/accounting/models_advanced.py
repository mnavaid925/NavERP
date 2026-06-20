"""Accounting & Finance — advanced sub-modules 2.6–2.15.

Extends `apps/accounting` (which owns the GL ledger spine, lesson L29) with Fixed Assets,
Cost Allocation, Payroll journal, Project/Job costing, Multi-entity intercompany, Tax,
Scheduled reports, Budgeting, Internal controls, and Integration config. Every *workflow*
action (depreciation run, disposal, allocation, payroll post, job-cost post, intercompany
post) posts a **balanced** ``JournalEntry`` (Σdebit==Σcredit) via the helpers in ``views.py``
— this file holds only the data model + small derived helpers.

Reuses by string FK: ``accounting.GLAccount``/``JournalEntry``/``FiscalPeriod``/``Currency``,
``core.Party`` (employee/customer/custodian via PartyRole), ``core.OrgUnit`` (the cost-centre /
department / legal-entity / consolidation dimension — no new Entity table), ``core.Document``.
No dependency on the still-unbuilt Inventory/HRM/Projects masters (L28).
"""
import hashlib
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models

from .models import ZERO, TenantNumbered, TenantOwned


# ============================================================== 2.6 Fixed Assets
class FixedAsset(TenantNumbered):
    """A capitalised asset with a depreciation method. ``accumulated_depreciation`` is advanced by
    the ``depreciation_run`` action (which posts Dr Depreciation Expense / Cr Accumulated Deprec.)."""

    NUMBER_PREFIX = "FA"

    METHOD_CHOICES = [
        ("straight_line", "Straight Line"),
        ("declining_balance", "Declining Balance (200%)"),
        ("units_of_production", "Units of Production"),
    ]
    STATUS_CHOICES = [
        ("cip", "Construction in Progress"),
        ("active", "In Service"),
        ("disposed", "Disposed"),
    ]

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=120, blank=True)
    acquisition_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    salvage_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    useful_life_months = models.PositiveIntegerField(default=60)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="straight_line")
    in_service_date = models.DateField(null=True, blank=True)
    accumulated_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    last_depreciation_date = models.DateField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    asset_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="fixed_assets_cost")
    accumulated_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name="fixed_assets_accum")
    expense_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="fixed_assets_expense")
    custodian = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="custodian_assets")
    location = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="located_assets")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_fa_tenant_status_idx")]

    @property
    def depreciable_base(self):
        return (self.acquisition_cost or ZERO) - (self.salvage_value or ZERO)

    def book_value(self):
        return (self.acquisition_cost or ZERO) - (self.accumulated_depreciation or ZERO)

    def remaining_depreciable(self):
        return max(self.depreciable_base - (self.accumulated_depreciation or ZERO), ZERO)

    def period_depreciation(self):
        """One period's depreciation, capped so accumulated never exceeds the depreciable base."""
        base = self.depreciable_base
        life = self.useful_life_months or 1
        if self.method == "declining_balance":
            rate = Decimal(2) / Decimal(life)
            amount = (self.book_value() * rate).quantize(Decimal("0.01"))
        else:  # straight_line and units_of_production (fallback)
            amount = (base / Decimal(life)).quantize(Decimal("0.01"))
        return min(amount, self.remaining_depreciable())

    def __str__(self):
        return f"{self.number} · {self.name}"


class AssetDisposal(TenantNumbered):
    """Retirement/sale of a FixedAsset — posts a balanced JE that removes cost + accumulated
    depreciation, records proceeds, and books the gain or loss."""

    NUMBER_PREFIX = "DISP"
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    asset = models.ForeignKey("accounting.FixedAsset", on_delete=models.PROTECT, related_name="disposals")
    disposal_date = models.DateField()
    proceeds = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="asset_disposals", editable=False)
    gain_loss = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-disposal_date", "-id"]
        unique_together = ("tenant", "number")

    @property
    def is_locked(self):
        return self.status == "posted"

    def computed_gain_loss(self):
        """Proceeds minus net book value at disposal (positive = gain, negative = loss)."""
        return (self.proceeds or ZERO) - self.asset.book_value()

    def __str__(self):
        return f"{self.number} · {self.asset_id and self.asset.name}"


# ====================================================== 2.7 Inventory & Cost Management
class CostAllocation(TenantNumbered):
    """Distributes a cost from a source GL account to a target account/cost-centre — posts
    Dr target / Cr source. (The accounting slice of inventory/cost management; the Item master
    arrives with Inventory, Module 5.)"""

    NUMBER_PREFIX = "CALLOC"
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    description = models.CharField(max_length=255)
    allocation_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    source_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="cost_alloc_source")
    target_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="cost_alloc_target")
    target_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="cost_allocations")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="cost_allocations", editable=False)

    class Meta:
        ordering = ["-allocation_date", "-id"]
        unique_together = ("tenant", "number")

    @property
    def is_locked(self):
        return self.status == "posted"

    def __str__(self):
        return self.number


# ============================================================= 2.8 Payroll Integration
class PayrollRun(TenantNumbered):
    """A pay-period payroll accrual. ``net_pay`` is DERIVED (gross − employee_tax − deductions) so
    the posted JE always balances. Post → Dr Wages/Tax/Benefits Expense / Cr Cash + Taxes Payable
    + Deductions Payable."""

    NUMBER_PREFIX = "PRUN"
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    period_start = models.DateField()
    period_end = models.DateField()
    pay_date = models.DateField()
    headcount = models.PositiveIntegerField(default=0)
    gross_wages = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    employee_tax = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="Withheld from employees")
    employer_tax = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="Employer-paid payroll tax")
    benefits = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="Employer benefit cost")
    deductions = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="Other employee deductions")
    net_pay = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="payroll_runs", editable=False)

    class Meta:
        ordering = ["-pay_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_prun_tenant_status_idx")]

    @property
    def is_locked(self):
        return self.status == "posted"

    def save(self, *args, **kwargs):
        # Net pay is always derived so the payroll JE balances by construction.
        self.net_pay = (self.gross_wages or ZERO) - (self.employee_tax or ZERO) - (self.deductions or ZERO)
        super().save(*args, **kwargs)

    def total_expense(self):
        return (self.gross_wages or ZERO) + (self.employer_tax or ZERO) + (self.benefits or ZERO)

    def __str__(self):
        return f"{self.number} · {self.pay_date}"


# ============================================================ 2.9 Project / Job Costing
class Project(TenantNumbered):
    """A costing/billing project (job). Actuals are DERIVED from posted ``JobCostEntry`` rows."""

    NUMBER_PREFIX = "PRJ"
    BILLING_CHOICES = [("fixed", "Fixed Price"), ("time_materials", "Time & Materials"), ("milestone", "Milestone")]
    STATUS_CHOICES = [("planning", "Planning"), ("active", "Active"), ("on_hold", "On Hold"), ("closed", "Closed")]

    name = models.CharField(max_length=255)
    client = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="costing_projects")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="costing_projects")
    billing_method = models.CharField(max_length=16, choices=BILLING_CHOICES, default="time_materials")
    budget_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="planning")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_prj_tenant_status_idx")]

    def _posted_sum(self, kind):
        from django.db.models import Sum
        return self.cost_entries.filter(status="posted", kind=kind).aggregate(s=Sum("amount"))["s"] or ZERO

    def actual_cost(self):
        return self._posted_sum("cost")

    def actual_revenue(self):
        return self._posted_sum("revenue")

    def budget_variance(self):
        return (self.budget_amount or ZERO) - self.actual_cost()

    def margin(self):
        return self.actual_revenue() - self.actual_cost()

    def __str__(self):
        return f"{self.number} · {self.name}"


class JobCostEntry(TenantNumbered):
    """A single cost or revenue posting against a Project — posts a balanced JE (cost: Dr expense /
    Cr cash; revenue: Dr cash / Cr income)."""

    NUMBER_PREFIX = "JCE"
    KIND_CHOICES = [("cost", "Cost"), ("revenue", "Revenue")]
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    project = models.ForeignKey("accounting.Project", on_delete=models.CASCADE, related_name="cost_entries")
    entry_date = models.DateField()
    kind = models.CharField(max_length=8, choices=KIND_CHOICES, default="cost")
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="job_cost_entries")
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="job_cost_entries", editable=False)

    class Meta:
        ordering = ["-entry_date", "-id"]
        unique_together = ("tenant", "number")

    @property
    def is_locked(self):
        return self.status == "posted"

    def __str__(self):
        return f"{self.number} · {self.get_kind_display()} {self.amount}"


# ===================================================== 2.10 Multi-Entity & Consolidation
class IntercompanyTransaction(TenantNumbered):
    """A due-to/due-from movement between two ``OrgUnit`` entities — posts Dr due-from (lender) /
    Cr due-to (borrower). ``eliminated`` flags it for the consolidation report."""

    NUMBER_PREFIX = "ICT"
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    description = models.CharField(max_length=255)
    transaction_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    from_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.PROTECT, related_name="ic_transactions_from")
    to_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.PROTECT, related_name="ic_transactions_to")
    due_from_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="ic_due_from")
    due_to_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="ic_due_to")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    eliminated = models.BooleanField(default=False)
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="ic_transactions", editable=False)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        unique_together = ("tenant", "number")

    @property
    def is_locked(self):
        return self.status == "posted"

    def __str__(self):
        return self.number


# ============================================================================ 2.11 Tax
class TaxCode(TenantOwned):
    """A tax rate master (sales/VAT/GST/use) pointing at its payable GL account."""

    TAX_TYPE_CHOICES = [("sales", "Sales Tax"), ("vat", "VAT"), ("gst", "GST"), ("use", "Use Tax")]

    name = models.CharField(max_length=120)
    jurisdiction = models.CharField(max_length=120, blank=True)
    tax_type = models.CharField(max_length=8, choices=TAX_TYPE_CHOICES, default="sales")
    rate_pct = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    payable_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="tax_codes")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.rate_pct}%)"


class TaxReturn(TenantNumbered):
    """A tax filing for a period — tracks taxable amount, tax due, filing and payment status."""

    NUMBER_PREFIX = "TAXR"
    STATUS_CHOICES = [("draft", "Draft"), ("filed", "Filed"), ("paid", "Paid")]

    tax_code = models.ForeignKey("accounting.TaxCode", on_delete=models.PROTECT, related_name="returns")
    period_start = models.DateField()
    period_end = models.DateField()
    taxable_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_due = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="draft")
    filed_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_taxr_tenant_status_idx")]

    def __str__(self):
        return f"{self.number} · {self.tax_code_id and self.tax_code.name}"


# ============================================================= 2.12 Reporting & Compliance
class ScheduledReport(TenantOwned):
    """Configuration for an automated financial report (the delivery worker is deferred)."""

    REPORT_CHOICES = [
        ("balance_sheet", "Balance Sheet"),
        ("profit_and_loss", "Profit & Loss"),
        ("trial_balance", "Trial Balance"),
        ("ar_aging", "AR Aging"),
        ("ap_aging", "AP Aging"),
        ("budget_variance", "Budget Variance"),
    ]
    FREQUENCY_CHOICES = [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"), ("quarterly", "Quarterly")]

    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=20, choices=REPORT_CHOICES, default="balance_sheet")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="monthly")
    recipients = models.TextField(blank=True, help_text="Comma-separated email addresses")
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# =============================================================== 2.13 Budgeting & Planning
class Budget(TenantNumbered):
    """A budget version for a fiscal period. Lines are entered as standalone ``BudgetLine`` rows;
    the budget-variance report compares them to posted actuals."""

    NUMBER_PREFIX = "BUD"
    VERSION_CHOICES = [("original", "Original"), ("revised", "Revised"), ("forecast", "Forecast")]
    STATUS_CHOICES = [("draft", "Draft"), ("approved", "Approved"), ("archived", "Archived")]

    name = models.CharField(max_length=255)
    fiscal_period = models.ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="budgets")
    version = models.CharField(max_length=10, choices=VERSION_CHOICES, default="original")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")

    def total(self):
        from django.db.models import Sum
        return self.lines.aggregate(s=Sum("amount"))["s"] or ZERO

    def __str__(self):
        return f"{self.number} · {self.name}"


class BudgetLine(TenantOwned):
    """One budgeted amount for an account (optionally a cost-centre) within a Budget."""

    budget = models.ForeignKey("accounting.Budget", on_delete=models.CASCADE, related_name="lines")
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="budget_lines")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="budget_lines")
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["gl_account__code"]

    def __str__(self):
        return f"{self.gl_account_id and self.gl_account.code}: {self.amount}"


# ================================================================= 2.14 Audit & Controls
class InternalControl(TenantOwned):
    """A documented SOX-style internal control with its latest test result (audit trail reuses
    ``core.AuditLog``)."""

    CONTROL_TYPE_CHOICES = [("preventive", "Preventive"), ("detective", "Detective"), ("corrective", "Corrective")]
    FREQUENCY_CHOICES = [("transactional", "Per Transaction"), ("daily", "Daily"), ("monthly", "Monthly"),
                         ("quarterly", "Quarterly"), ("annual", "Annual")]
    RISK_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
    RESULT_CHOICES = [("na", "Not Tested"), ("pass", "Pass"), ("fail", "Fail")]
    STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive")]

    code = models.CharField(max_length=40)
    name = models.CharField(max_length=255)
    control_type = models.CharField(max_length=12, choices=CONTROL_TYPE_CHOICES, default="preventive")
    frequency = models.CharField(max_length=14, choices=FREQUENCY_CHOICES, default="monthly")
    risk_level = models.CharField(max_length=8, choices=RISK_CHOICES, default="medium")
    owner = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="owned_controls")
    last_tested_date = models.DateField(null=True, blank=True)
    last_result = models.CharField(max_length=4, choices=RESULT_CHOICES, default="na")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="active")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_ctrl_tenant_status_idx")]

    def __str__(self):
        return f"{self.code} · {self.name}"


# ================================================================= 2.15 Integration & API
class IntegrationConfig(TenantOwned):
    """An external-service connector configuration. The API secret is NEVER stored — only a prefix
    + SHA-256 hash (lessons L20/L25); the plaintext is revealed exactly once on rotate. Live sync
    against the provider is deferred."""

    PROVIDER_CHOICES = [
        ("plaid", "Plaid"), ("stripe", "Stripe"), ("paypal", "PayPal"), ("square", "Square"),
        ("avalara", "Avalara"), ("vertex", "Vertex"), ("shopify", "Shopify"), ("woocommerce", "WooCommerce"),
        ("salesforce", "Salesforce"), ("hubspot", "HubSpot"), ("quickbooks", "QuickBooks"),
        ("netsuite", "NetSuite"), ("workday", "Workday"), ("custom", "Custom API"),
    ]
    CATEGORY_CHOICES = [
        ("banking", "Banking"), ("payments", "Payments"), ("tax", "Tax"), ("ecommerce", "E-commerce"),
        ("crm", "CRM"), ("erp", "ERP"), ("hris", "HRIS"), ("storage", "Document Storage"), ("other", "Other"),
    ]
    STATUS_CHOICES = [("disconnected", "Disconnected"), ("connected", "Connected"), ("error", "Error")]

    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES, default="custom")
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default="other")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="disconnected")
    api_key_prefix = models.CharField(max_length=12, blank=True, editable=False)
    api_key_hash = models.CharField(max_length=64, blank=True, editable=False)
    last_sync = models.DateTimeField(null=True, blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    @staticmethod
    def hash_secret(secret):
        return hashlib.sha256(secret.encode()).hexdigest()

    def set_secret(self, secret):
        """Store only prefix + hash — never the plaintext (L20/L25)."""
        self.api_key_prefix = secret[:6]
        self.api_key_hash = self.hash_secret(secret)

    @property
    def masked(self):
        if not self.api_key_hash:
            return ""
        return f"{self.api_key_prefix}{'•' * 8}"

    @staticmethod
    def generate_secret():
        return secrets.token_urlsafe(24)

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"
