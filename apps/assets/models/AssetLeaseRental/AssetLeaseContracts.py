import calendar
import datetime
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetLeaseContract(TenantNumbered):
    """
    Asset Lease & Rental Contract [ALC-].
    Master lease agreement and lease schedule administration for enterprise plant machinery,
    equipment, and facilities with automated ASC 842 / IFRS 16 statutory classification,
    present value capitalization of Right-of-Use (ROU) assets and lease liabilities.
    """

    NUMBER_PREFIX = "ALC"

    CLASSIFICATION_CHOICES = [
        ("operating", "Operating Lease"),
        ("finance", "Finance / Capital Lease"),
    ]

    PAYMENT_FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("semi_annual", "Semi-Annual"),
        ("annual", "Annual"),
    ]

    PAYMENT_TIMING_CHOICES = [
        ("advance", "Payment in Advance (Beginning of Period)"),
        ("arrears", "Payment in Arrears (End of Period)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Pending Inception)"),
        ("pending_approval", "Pending Authorization"),
        ("active", "Active (Capitalized)"),
        ("modified", "Modified / Remeasured"),
        ("expired", "Expired (Completed)"),
        ("terminated", "Early Terminated"),
        ("buyout", "Asset Purchased / Buyout"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "pending_approval": "badge-amber",
        "active": "badge-green",
        "modified": "badge-info",
        "expired": "badge-muted",
        "terminated": "badge-red",
        "buyout": "badge-info",
    }

    CLASSIFICATION_CSS = {
        "operating": "badge-info",
        "finance": "badge-slate",
    }

    PAYMENT_FREQUENCY_CSS = {
        "monthly": "badge-info",
        "quarterly": "badge-slate",
        "semi_annual": "badge-slate",
        "annual": "badge-slate",
    }

    title = models.CharField(
        max_length=255,
        help_text="Lease agreement title or descriptive identification",
    )
    master_lease_agreement_ref = models.CharField(
        max_length=100,
        blank=True,
        help_text="Master Lease Agreement (MLA) or master facility reference",
    )
    lessor = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="leased_asset_contracts",
        help_text="Lessor, financial institution, or equipment rental vendor",
    )
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lease_contracts",
        help_text="Operational plant machinery or equipment leased",
    )
    category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lease_contracts",
        help_text="Asset category classification",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lease_contracts",
        help_text="Capitalized Right-of-Use (ROU) Fixed Asset record",
    )

    # Key Dates
    inception_date = models.DateField(
        default=timezone.now,
        help_text="Agreement execution / contract signature date",
    )
    commencement_date = models.DateField(
        default=timezone.now,
        help_text="Date asset is placed in service and lease term starts",
    )
    expiration_date = models.DateField(
        help_text="Stipulated base lease term expiration date",
    )
    first_payment_date = models.DateField(
        default=timezone.now,
        help_text="Date of initial lease payment installment",
    )
    early_termination_notice_date = models.DateField(
        null=True,
        blank=True,
        help_text="Cutoff deadline for exercising early termination or return",
    )

    # Term & Horizon
    lease_term_months = models.PositiveIntegerField(
        default=36,
        validators=[MinValueValidator(1), MaxValueValidator(600)],
        help_text="Base non-cancellable lease duration in months (max 600 months / 50 years)",
    )
    economic_life_months = models.PositiveIntegerField(
        default=60,
        help_text="Estimated economic useful life of the leased asset",
    )

    # Financial Terms
    payment_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Periodic base rental installment payment amount",
    )
    payment_frequency = models.CharField(
        max_length=20,
        choices=PAYMENT_FREQUENCY_CHOICES,
        default="monthly",
    )
    payment_timing = models.CharField(
        max_length=20,
        choices=PAYMENT_TIMING_CHOICES,
        default="arrears",
    )
    discount_rate_pct = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal("5.0000"),
        help_text="Annual Incremental Borrowing Rate (IBR) or rate implicit in lease (%)",
    )
    fair_market_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Estimated fair market value of leased asset at commencement",
    )
    initial_direct_costs = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Ancillary origination fees, commissions, or legal setup costs capitalized into ROU asset",
    )
    lease_incentives = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Incentive rebates received from lessor offsetting ROU asset value",
    )
    residual_value_guarantee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Lessee guaranteed residual amount payable at lease expiration",
    )
    purchase_option_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fixed bargain purchase option price if applicable",
    )

    # Statutory Classification Criteria (ASC 842 / IFRS 16)
    transfer_of_ownership = models.BooleanField(
        default=False,
        help_text="Criterion 1: Ownership transfers to lessee by end of term",
    )
    has_purchase_option = models.BooleanField(
        default=False,
        help_text="Criterion 2: Option to purchase reasonably certain to be exercised",
    )
    is_specialized_asset = models.BooleanField(
        default=False,
        help_text="Criterion 5: Asset has no alternative use to lessor at end of term",
    )
    classification = models.CharField(
        max_length=20,
        choices=CLASSIFICATION_CHOICES,
        default="operating",
    )
    classification_overridden = models.BooleanField(
        default=False,
        help_text="Flag indicating manual override of automated statutory classification",
    )
    classification_notes = models.TextField(
        blank=True,
        help_text="Technical accounting justification for lease classification",
    )

    # Capitalized Balances
    initial_lease_liability = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated Present Value of lease payments at commencement",
    )
    initial_rou_asset_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Capitalized initial Right-of-Use asset carrying value",
    )
    current_lease_liability = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Current remaining lease liability principal",
    )
    current_rou_asset_carrying_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Current net book value of ROU asset after amortization",
    )

    # Workflow Status
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_asset_leases",
        help_text="Authorizing corporate controller or finance executive",
    )
    notes = models.TextField(
        blank=True,
        help_text="Administrative remarks, terms, or operational stipulations",
    )

    class Meta:
        ordering = ["-commencement_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_alc_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_alc_ten_stat"),
            models.Index(fields=["tenant", "classification"], name="idx_alc_ten_class"),
            models.Index(fields=["tenant", "lessor"], name="idx_alc_ten_lessor"),
            models.Index(fields=["tenant", "commencement_date"], name="idx_alc_ten_cdate"),
            models.Index(fields=["tenant", "expiration_date"], name="idx_alc_ten_edate"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def classification_css(self):
        return self.CLASSIFICATION_CSS.get(self.classification, "badge-info")

    @property
    def periods_per_year(self):
        freq_map = {
            "monthly": 12,
            "quarterly": 4,
            "semi_annual": 2,
            "annual": 1,
        }
        return freq_map.get(self.payment_frequency, 12)

    @property
    def total_periods(self):
        months_per_period = 12 // self.periods_per_year
        return max(1, self.lease_term_months // months_per_period)

    @property
    def periodic_discount_rate(self):
        annual_rate = (self.discount_rate_pct or Decimal("5.0")) / Decimal("100.0")
        return annual_rate / Decimal(str(self.periods_per_year))

    def calculate_present_value(self):
        """
        Computes the actuarial Present Value (PV) of lease installment payments
        discounted by the Incremental Borrowing Rate (IBR) taking into account
        advance vs arrears payment timing.
        """
        r = float(self.periodic_discount_rate)
        pmt = float(self.payment_amount or 0)
        n = self.total_periods

        if r <= 0 or n <= 0 or pmt <= 0:
            pv = Decimal(str(round(pmt * n, 2)))
        else:
            # Ordinary annuity PV factor = (1 - (1 + r)^(-n)) / r
            annuity_pv = pmt * (1.0 - (1.0 + r) ** (-n)) / r
            if self.payment_timing == "advance":
                # Annuity due factor = Ordinary Annuity * (1 + r)
                annuity_pv *= (1.0 + r)

            # Add present value of guaranteed residual or purchase option
            balloon = float(self.purchase_option_price or self.residual_value_guarantee or 0)
            balloon_pv = balloon * ((1.0 + r) ** (-n)) if balloon > 0 else 0.0

            pv = Decimal(str(round(annuity_pv + balloon_pv, 2)))

        initial_liability = pv
        initial_rou = (
            initial_liability
            + (self.initial_direct_costs or Decimal("0.00"))
            - (self.lease_incentives or Decimal("0.00"))
        )

        self.initial_lease_liability = initial_liability
        self.initial_rou_asset_value = initial_rou

        # Only reset current amortized balances if draft or no payments paid/accrued yet
        should_reset_current = False
        if not self.pk or self.current_lease_liability is None or self.status in ["draft", "pending_approval"]:
            should_reset_current = True
        elif not self.payment_schedules.filter(status__in=["paid", "accrued"]).exists():
            should_reset_current = True

        if should_reset_current:
            self.current_lease_liability = initial_liability
            self.current_rou_asset_carrying_value = initial_rou
        return initial_liability, initial_rou

    def evaluate_statutory_classification(self):
        """
        Evaluates the 5 statutory criteria under ASC 842 & IFRS 16:
        1. Ownership transfer at end of term
        2. Purchase option reasonably certain
        3. Lease term >= 75% of asset economic life
        4. PV of lease payments >= 90% of fair market value
        5. Specialized asset with no alternative use
        """
        if self.classification_overridden:
            return self.classification

        # Criterion 3: 75% of useful life
        term_ratio = Decimal(str(self.lease_term_months)) / Decimal(str(max(1, self.economic_life_months)))
        meets_term_criterion = term_ratio >= Decimal("0.75")

        # Criterion 4: 90% of fair market value
        fmv = self.fair_market_value or Decimal("0.00")
        pv_liability = self.initial_lease_liability
        if pv_liability <= 0:
            pv_liability, _ = self.calculate_present_value()

        meets_pv_criterion = False
        if fmv > 0:
            meets_pv_criterion = (pv_liability / fmv) >= Decimal("0.90")

        is_finance = (
            self.transfer_of_ownership
            or self.has_purchase_option
            or meets_term_criterion
            or meets_pv_criterion
            or self.is_specialized_asset
        )

        self.classification = "finance" if is_finance else "operating"
        self.classification_notes = (
            f"Automated evaluation: Ownership Transfer={self.transfer_of_ownership}, "
            f"Purchase Option={self.has_purchase_option}, "
            f"Term/Life Ratio={term_ratio * 100:.1f}%, "
            f"PV/FMV Ratio={(pv_liability / fmv * 100):.1f}% if FMV>0 else N/A, "
            f"Specialized Asset={self.is_specialized_asset}."
        )
        return self.classification

    def generate_amortization_schedule(self):
        """
        Generates periodic payment amortization rows for the contract.
        """
        from apps.assets.models.AssetLeaseRental.AssetLeaseSchedules import AssetLeaseSchedule

        with transaction.atomic():
            # Delete any existing scheduled lines
            self.payment_schedules.filter(status="scheduled").delete()

            r = self.periodic_discount_rate
            pmt = self.payment_amount
            liability = self.initial_lease_liability
            rou_balance = self.initial_rou_asset_value
            n = self.total_periods
            rou_deprec_per_period = (
                rou_balance / Decimal(str(n)) if n > 0 else Decimal("0.00")
            )

            months_per_period = 12 // self.periods_per_year
            current_date = self.first_payment_date or self.commencement_date
            base_day = current_date.day

            schedules = []
            for period in range(1, n + 1):
                beginning_liability = liability

                if self.payment_timing == "advance" and period == 1:
                    # First payment in advance incurs zero interest for period 1
                    interest = Decimal("0.00")
                    principal = min(beginning_liability, pmt)
                    ending_liability = max(Decimal("0.00"), beginning_liability - principal)
                else:
                    interest = Decimal(str(round(float(beginning_liability) * float(r), 2)))
                    principal = min(beginning_liability, pmt - interest)
                    ending_liability = max(Decimal("0.00"), beginning_liability - principal)

                ending_rou = max(Decimal("0.00"), rou_balance - rou_deprec_per_period)
                if period == n:
                    # Force clean zeroing on final period
                    ending_liability = Decimal("0.00")
                    ending_rou = Decimal("0.00")

                schedule = AssetLeaseSchedule(
                    tenant=self.tenant,
                    lease_contract=self,
                    period_number=period,
                    due_date=current_date,
                    payment_amount=pmt,
                    beginning_liability=beginning_liability,
                    interest_expense=interest,
                    principal_reduction=principal,
                    ending_liability=ending_liability,
                    rou_depreciation=rou_deprec_per_period,
                    ending_rou_asset_value=ending_rou,
                    status="scheduled",
                )
                schedules.append(schedule)

                liability = ending_liability
                rou_balance = ending_rou
                # Add months safely using calendar
                _m = current_date.month - 1 + months_per_period
                _y = current_date.year + _m // 12
                _m = _m % 12 + 1
                _d = min(base_day, calendar.monthrange(_y, _m)[1])
                current_date = datetime.date(_y, _m, _d)

            for schedule in schedules:
                schedule.save()
            return len(schedules)
