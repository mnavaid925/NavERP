from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetLeaseBuyAnalysis(TenantNumbered):
    """
    Asset Lease vs. Buy Analysis [ALBA-].
    Comparative capital acquisition financial decision model calculating discounted after-tax
    cash flows (NPV), undiscounted Total Cost of Ownership (TCO), and Net Advantage to Leasing (NAL)
    under corporate WACC discount rates.
    """

    NUMBER_PREFIX = "ALBA"

    RECOMMENDATION_CHOICES = [
        ("buy", "Acquire via Outright Purchase / Loan"),
        ("lease", "Acquire via Lease Financing"),
        ("neutral", "Financial Parity / Neutral Indifference"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Scenario"),
        ("evaluated", "Evaluated (Metrics Computed)"),
        ("approved", "Approved Recommendation"),
        ("rejected", "Rejected"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "evaluated": "badge-info",
        "approved": "badge-green",
        "rejected": "badge-red",
    }

    RECOMMENDATION_CSS = {
        "buy": "badge-green",
        "lease": "badge-info",
        "neutral": "badge-slate",
    }

    title = models.CharField(
        max_length=255,
        help_text="Capital acquisition analysis title or project name",
    )
    description = models.TextField(
        blank=True,
        help_text="Project description and asset requirement background",
    )
    target_asset_name = models.CharField(
        max_length=255,
        help_text="Name, make, model or description of target asset",
    )
    category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lease_buy_analyses",
        help_text="Asset category classification",
    )
    expected_useful_life_years = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=Decimal("5.0"),
        help_text="Expected operational life of target equipment in years",
    )

    # Purchase / Loan Financing Assumptions
    purchase_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Outright purchase price / capitalized equipment quote",
    )
    down_payment_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        help_text="Down payment required for debt purchase financing (%)",
    )
    loan_interest_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("6.00"),
        help_text="Annual loan financing interest rate (%)",
    )
    loan_term_years = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=Decimal("5.0"),
        help_text="Commercial loan term in years",
    )
    estimated_salvage_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Estimated residual salvage proceeds at end of life",
    )
    annual_maintenance_cost_buy = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Annual owner-incurred preventive maintenance expense",
    )
    annual_insurance_tax_buy = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Annual property tax and insurance premium incurred under ownership",
    )

    # Lease Financing Assumptions
    lease_term_months = models.PositiveIntegerField(
        default=36,
        help_text="Proposed lease agreement duration in months",
    )
    monthly_lease_payment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Monthly lease installment payment quote",
    )
    upfront_lease_fees = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Upfront documentation, delivery, or origination fees",
    )
    end_of_lease_purchase_option = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Stipulated buyout option price at lease conclusion",
    )
    lessor_covers_maintenance = models.BooleanField(
        default=True,
        help_text="Flag indicating whether maintenance is included in lease fee",
    )
    annual_maintenance_cost_lease = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Any supplemental lessee-incurred maintenance under lease",
    )

    # Corporate Hurdle & Tax Parameters
    discount_rate_wacc_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("8.00"),
        help_text="Corporate Weighted Average Cost of Capital (WACC) hurdle rate (%)",
    )
    corporate_tax_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("21.00"),
        help_text="Effective marginal corporate income tax rate (%)",
    )

    # Calculated Financial Results
    npv_purchase_option = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net Present Value of cash outflows for purchase/borrow scenario",
    )
    npv_lease_option = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net Present Value of cash outflows for lease scenario",
    )
    tco_purchase_option = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Undiscounted nominal Total Cost of Ownership under purchase",
    )
    tco_lease_option = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Undiscounted nominal Total Cost of Ownership under lease",
    )
    net_advantage_to_leasing = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net Present Value Advantage to Leasing: NPV(Buy) - NPV(Lease)",
    )
    recommendation = models.CharField(
        max_length=20,
        choices=RECOMMENDATION_CHOICES,
        default="neutral",
    )

    # Governance
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_lease_buy_analyses",
        help_text="Financial analyst performing evaluation",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_lease_buy_analyses",
        help_text="CFO or Treasurer approving acquisition method",
    )
    evaluation_notes = models.TextField(
        blank=True,
        help_text="Executive summary and qualitative evaluation narrative",
    )

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_alba_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_alba_ten_stat"),
            models.Index(fields=["tenant", "recommendation"], name="idx_alba_ten_recom"),
            models.Index(fields=["tenant", "category"], name="idx_alba_ten_cat"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def recommendation_css(self):
        return self.RECOMMENDATION_CSS.get(self.recommendation, "badge-slate")

    def evaluate_financial_models(self):
        """
        Calculates discounted after-tax Net Present Values (NPV) and undiscounted TCO
        for both Outright Purchase / Loan Financing and Operating / Finance Lease options.
        """
        wacc = float(self.discount_rate_wacc_pct or Decimal("8.0")) / 100.0
        tax_rate = float(self.corporate_tax_rate_pct or Decimal("21.0")) / 100.0
        years = int(max(1, round(float(self.expected_useful_life_years or Decimal("5.0")))))

        # ----------------------------------------------------
        # 1. Purchase Scenario
        # ----------------------------------------------------
        price = float(self.purchase_price or 0)
        down_pct = float(self.down_payment_pct or 0) / 100.0
        loan_rate = float(self.loan_interest_rate_pct or 0) / 100.0
        loan_years = int(max(1, round(float(self.loan_term_years or Decimal("5.0")))))
        salvage = float(self.estimated_salvage_value or 0)
        maint_buy = float(self.annual_maintenance_cost_buy or 0)
        tax_ins = float(self.annual_insurance_tax_buy or 0)

        down_payment = price * down_pct
        loan_principal = price - down_payment

        # Annual loan payment
        if loan_rate > 0 and loan_years > 0:
            denom = 1.0 - (1.0 + loan_rate) ** (-loan_years)
            if denom > 1e-9:
                annual_loan_pmt = loan_principal * (loan_rate / denom)
            else:
                annual_loan_pmt = loan_principal / loan_years
        else:
            annual_loan_pmt = loan_principal / loan_years if loan_years > 0 else 0.0

        # Straight-line tax depreciation per year
        annual_deprec = max(0.0, (price - salvage) / years)
        deprec_tax_shield = annual_deprec * tax_rate

        buy_npv = down_payment
        buy_tco = down_payment
        remaining_debt = loan_principal

        for y in range(1, years + 1):
            if y <= loan_years and remaining_debt > 0:
                interest_component = remaining_debt * loan_rate
                principal_component = annual_loan_pmt - interest_component
                remaining_debt = max(0.0, remaining_debt - principal_component)
                # Interest is tax-deductible
                after_tax_loan_pmt = annual_loan_pmt - (interest_component * tax_rate)
                buy_tco += annual_loan_pmt
            else:
                after_tax_loan_pmt = 0.0

            # Maintenance & insurance (after-tax)
            after_tax_operating = (maint_buy + tax_ins) * (1.0 - tax_rate)
            buy_tco += (maint_buy + tax_ins)

            # Net cash outflow for year y
            net_cash_flow = after_tax_loan_pmt + after_tax_operating - deprec_tax_shield

            # Terminal salvage value recovery in final year
            if y == years:
                # Under straight-line depreciation down to salvage, book value equals salvage
                # (no taxable gain/loss on sale at salvage value)
                after_tax_salvage = salvage
                net_cash_flow -= after_tax_salvage
                buy_tco -= salvage

            # Discount to present value
            df = (1.0 + wacc) ** (-y) if wacc > 0 else 1.0
            buy_npv += net_cash_flow * df

        # ----------------------------------------------------
        # 2. Lease Scenario
        # ----------------------------------------------------
        lease_months = max(1, self.lease_term_months or 36)
        lease_years = int(max(1, round(lease_months / 12.0)))
        monthly_pmt = float(self.monthly_lease_payment or 0)
        upfront_fee = float(self.upfront_lease_fees or 0)
        buyout_option = float(self.end_of_lease_purchase_option or 0)
        maint_lease = float(self.annual_maintenance_cost_lease or 0) if not self.lessor_covers_maintenance else 0.0

        annual_lease_pmt = monthly_pmt * 12.0
        lease_npv = upfront_fee * (1.0 - tax_rate)
        lease_tco = upfront_fee

        horizon = min(years, lease_years)
        for y in range(1, horizon + 1):
            after_tax_rent = annual_lease_pmt * (1.0 - tax_rate)
            after_tax_maint = maint_lease * (1.0 - tax_rate)
            net_lease_cf = after_tax_rent + after_tax_maint
            lease_tco += annual_lease_pmt + maint_lease

            if y == horizon and buyout_option > 0:
                net_lease_cf += buyout_option
                lease_tco += buyout_option

            df = (1.0 + wacc) ** (-y) if wacc > 0 else 1.0
            lease_npv += net_lease_cf * df

        # ----------------------------------------------------
        # 3. Decision Metric: Net Advantage to Leasing (NAL)
        # ----------------------------------------------------
        # NAL = NPV(Cost of Buying) - NPV(Cost of Leasing)
        # Positive NAL favors leasing; Negative NAL favors buying.
        nal = buy_npv - lease_npv

        if abs(nal) < 100.0:
            rec = "neutral"
        elif nal > 0:
            rec = "lease"
        else:
            rec = "buy"

        self.npv_purchase_option = Decimal(str(round(buy_npv, 2)))
        self.npv_lease_option = Decimal(str(round(lease_npv, 2)))
        self.tco_purchase_option = Decimal(str(round(buy_tco, 2)))
        self.tco_lease_option = Decimal(str(round(lease_tco, 2)))
        self.net_advantage_to_leasing = Decimal(str(round(nal, 2)))
        self.recommendation = rec
        self.status = "evaluated"

        return self.recommendation
