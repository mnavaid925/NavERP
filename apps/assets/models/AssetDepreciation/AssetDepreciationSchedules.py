from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetDepreciationSchedule(TenantNumbered):
    """Periodic multi-method depreciation calculation schedule and GL posting record [ADEP-]."""

    NUMBER_PREFIX = "ADEP"

    METHOD_CHOICES = [
        ("straight_line", "Straight-Line (SL)"),
        ("declining_balance_150", "Declining Balance (150%)"),
        ("declining_balance_200", "Double Declining Balance (200%)"),
        ("sum_of_years", "Sum-of-the-Years'-Digits (SYD)"),
        ("units_of_production", "Units-of-Production (UOP)"),
    ]

    PERIOD_FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Schedule"),
        ("calculated", "Calculated / Pending Post"),
        ("posted", "Posted to General Ledger"),
        ("superseded", "Superseded (Revaluation/Transfer)"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "calculated": "badge-amber",
        "posted": "badge-green",
        "superseded": "badge-muted",
        "cancelled": "badge-red",
    }

    METHOD_CSS = {
        "straight_line": "badge-info",
        "declining_balance_150": "badge-amber",
        "declining_balance_200": "badge-purple",
        "sum_of_years": "badge-blue",
        "units_of_production": "badge-slate",
    }

    # Core Asset References
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.CASCADE,
        related_name="depreciation_schedules",
        help_text="Financial Fixed Asset in accounting subledger",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="depreciation_schedules",
        help_text="Operational physical asset in plant register",
    )

    # Period Identification
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_depreciation_schedules",
    )
    fiscal_year = models.PositiveIntegerField(default=2026, help_text="Fiscal Year, e.g. 2026")
    period_number = models.PositiveSmallIntegerField(default=1, help_text="Period number within fiscal year (1-12)")
    period_frequency = models.CharField(max_length=20, choices=PERIOD_FREQUENCY_CHOICES, default="monthly")
    schedule_date = models.DateField(default=timezone.now, help_text="Calculation / posting run date")

    # Method & Financial Balances
    depreciation_method = models.CharField(max_length=30, choices=METHOD_CHOICES, default="straight_line")
    starting_book_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net book value before current period depreciation",
    )
    depreciation_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Depreciation charge calculated for this period",
    )
    accumulated_depreciation_after = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Cumulative depreciation after this period charge",
    )
    ending_book_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Carrying amount after this period charge",
    )

    # Units of Production Parameters
    total_units_expected = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="For UOP method: total lifetime expected units / hours",
    )
    units_produced_period = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="For UOP method: units consumed / produced in this period",
    )

    # General Ledger & Cost Allocation
    expense_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_depreciation_expenses",
        help_text="Debit: Depreciation Expense GL Account",
    )
    accumulated_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_accumulated_depreciations",
        help_text="Credit: Accumulated Depreciation GL Account",
    )
    cost_center = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_depreciation_expenses",
        help_text="Cost center charged for depreciation",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="depreciation_schedules",
        help_text="Posted balanced GL Journal Entry",
    )

    # Execution & Audit
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posted_depreciations",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "assets_depreciation_schedule"
        ordering = ["-fiscal_year", "-period_number", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_adep_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "fixed_asset"], name="idx_adep_ten_fa"),
            models.Index(fields=["tenant", "status"], name="idx_adep_ten_stat"),
            models.Index(fields=["tenant", "fiscal_year", "period_number"], name="idx_adep_ten_fpyr"),
            models.Index(fields=["tenant", "schedule_date"], name="idx_adep_ten_date"),
        ]

    def __str__(self):
        return f"{self.number} - {self.fixed_asset.name} (FY{self.fiscal_year} P{self.period_number})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def method_css(self):
        return self.METHOD_CSS.get(self.depreciation_method, "badge-slate")

    def calculate_depreciation(self, force=False):
        """Perform exact mathematical depreciation computation."""
        fa = self.fixed_asset
        acq_cost = fa.acquisition_cost or Decimal("0.00")
        salvage = fa.salvage_value or Decimal("0.00")
        depreciable_base = max(acq_cost - salvage, Decimal("0.00"))
        accum_before = fa.accumulated_depreciation or Decimal("0.00")
        current_book = max(acq_cost - accum_before, Decimal("0.00"))

        if not self.starting_book_value or self.starting_book_value == Decimal("0.00"):
            self.starting_book_value = current_book

        months = fa.useful_life_months or 60
        factor = Decimal("1.0")
        if self.period_frequency == "quarterly":
            factor = Decimal("3.0")
        elif self.period_frequency == "annual":
            factor = Decimal("12.0")

        method = self.depreciation_method
        calculated_amount = Decimal("0.00")

        if not force and self.depreciation_amount and self.depreciation_amount > Decimal("0.00"):
            calculated_amount = self.depreciation_amount
        elif method == "straight_line":
            if months > 0:
                monthly_rate = depreciable_base / Decimal(months)
                calculated_amount = (monthly_rate * factor).quantize(Decimal("0.01"))
        elif method == "declining_balance_150":
            if months > 0:
                annual_rate = Decimal("1.5") / (Decimal(months) / Decimal("12.0"))
                period_rate = annual_rate * (factor / Decimal("12.0"))
                calculated_amount = (self.starting_book_value * period_rate).quantize(Decimal("0.01"))
        elif method == "declining_balance_200":
            if months > 0:
                annual_rate = Decimal("2.0") / (Decimal(months) / Decimal("12.0"))
                period_rate = annual_rate * (factor / Decimal("12.0"))
                calculated_amount = (self.starting_book_value * period_rate).quantize(Decimal("0.01"))
        elif method == "sum_of_years":
            total_years = max(Decimal(months) / Decimal("12.0"), Decimal("1.0"))
            syd_denominator = (total_years * (total_years + Decimal("1.0"))) / Decimal("2.0")
            years_elapsed = Decimal(self.period_number - 1) / (Decimal("12.0") / factor)
            remaining_years = max(total_years - years_elapsed, Decimal("1.0"))
            fraction = remaining_years / syd_denominator
            annual_charge = depreciable_base * fraction
            calculated_amount = (annual_charge * (factor / Decimal("12.0"))).quantize(Decimal("0.01"))
        elif method == "units_of_production":
            total_u = self.total_units_expected or Decimal("0.00")
            period_u = self.units_produced_period or Decimal("0.00")
            if total_u > Decimal("0.00"):
                rate_per_unit = depreciable_base / total_u
                calculated_amount = (rate_per_unit * period_u).quantize(Decimal("0.01"))

        # Cap depreciation so ending book value does not drop below salvage value
        max_allowable = max(self.starting_book_value - salvage, Decimal("0.00"))
        self.depreciation_amount = min(calculated_amount, max_allowable)
        self.accumulated_depreciation_after = accum_before + self.depreciation_amount
        self.ending_book_value = self.starting_book_value - self.depreciation_amount
        if self.status == "draft":
            self.status = "calculated"
        return self.depreciation_amount

    def post_to_gl(self, user=None):
        """Generate balanced GL Journal Entry and update FixedAsset subledger."""
        from apps.accounting.models import JournalEntry, JournalLine

        if self.status == "posted":
            raise ValidationError("This depreciation schedule is already posted to the General Ledger.")

        if not self.depreciation_amount or self.depreciation_amount <= Decimal("0.00"):
            self.calculate_depreciation()

        if self.depreciation_amount <= Decimal("0.00"):
            raise ValidationError("Cannot post a zero or negative depreciation charge.")

        exp_acc = self.expense_account or self.fixed_asset.expense_account
        accum_acc = self.accumulated_account or self.fixed_asset.accumulated_account

        if not exp_acc or not accum_acc:
            raise ValidationError(
                "Both Depreciation Expense and Accumulated Depreciation GL accounts are required to post to the General Ledger."
            )

        with transaction.atomic():
            je = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_type="recurring",
                status="posted",
                entry_date=self.schedule_date,
                description=f"Depreciation for {self.fixed_asset.number} - {self.fixed_asset.name} (FY{self.fiscal_year} P{self.period_number})",
                reference=f"{self.number}",
                created_by=user,
                approved_by=user,
                posted_at=timezone.now(),
                fiscal_period=self.fiscal_period,
            )
            # Debit Depreciation Expense
            JournalLine.objects.create(
                entry=je,
                gl_account=exp_acc,
                debit=self.depreciation_amount,
                credit=Decimal("0.00"),
                description=f"Deprec Expense - {self.fixed_asset.name}",
                org_unit=self.cost_center,
            )
            # Credit Accumulated Depreciation
            JournalLine.objects.create(
                entry=je,
                gl_account=accum_acc,
                debit=Decimal("0.00"),
                credit=self.depreciation_amount,
                description=f"Accum Deprec - {self.fixed_asset.name}",
                org_unit=self.cost_center,
            )

            self.journal_entry = je
            self.status = "posted"
            self.posted_at = timezone.now()
            self.posted_by = user
            self.save()

            # Update FixedAsset ledger
            fa = self.fixed_asset
            fa.accumulated_depreciation = self.accumulated_depreciation_after
            fa.last_depreciation_date = self.schedule_date
            fa.save(update_fields=["accumulated_depreciation", "last_depreciation_date"])

        return je
