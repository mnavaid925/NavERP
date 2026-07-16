"""HRM 3.16 Tax & Investment — Taxcomputation models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.PayrollProcessing.Payslip import PayslipLine
from apps.hrm.models.StatutoryCompliance.Statutoryreturn import StatutoryReturn
from apps.hrm.models.TaxInvestment.NEW_REGIME_ALLOWED_SECTIONSs import NEW_REGIME_ALLOWED_SECTIONS
from apps.hrm.models.TaxInvestment.SECTION_CAPSs import SECTION_CAPS
from apps.hrm.models.TaxInvestment.Taxregimeconfig import TaxRegimeConfig
from apps.hrm.models.TaxInvestment._helpers import _progressive_tax
from apps.hrm.models.PayrollProcessing.Payslip import PayslipLine
from apps.hrm.models.StatutoryCompliance.Statutoryreturn import StatutoryReturn
from apps.hrm.models.TaxInvestment.NEW_REGIME_ALLOWED_SECTIONSs import NEW_REGIME_ALLOWED_SECTIONS
from apps.hrm.models.TaxInvestment.SECTION_CAPSs import SECTION_CAPS
from apps.hrm.models.TaxInvestment.Taxregimeconfig import TaxRegimeConfig
from apps.hrm.models.TaxInvestment._helpers import _progressive_tax


class TaxComputation(TenantNumbered):
    """The per-employee-per-FY annual tax projection engine (3.16) — ``TXC-#####``. ``recompute()``
    derives ``tax_payable``/``tax_paid_ytd``/``monthly_tds_amount`` (mirroring ``Payslip.recompute()``/
    ``StatutoryReturn.recompute()``); the regime-comparison and taxable-income build-up are DERIVED
    @property methods (never stored). Links to the existing ``StatutoryReturn(scheme="tds_form16")`` row
    via ``link_form16()`` — no new Form-16 table. Recomputed in place, one row per employee per FY."""

    NUMBER_PREFIX = "TXC"

    COMPUTATION_TYPE_CHOICES = [
        ("provisional", "Provisional"),
        ("final", "Final"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="tax_computations")
    declaration = models.ForeignKey("hrm.InvestmentDeclaration", on_delete=models.PROTECT, related_name="tax_computations")
    financial_year = models.CharField(max_length=10, help_text="Denormalized from the declaration for filtering.")
    computation_type = models.CharField(max_length=15, choices=COMPUTATION_TYPE_CHOICES, default="provisional")
    manual_override_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Overrides the derived monthly TDS when set (edge cases the formula can't cover).")
    override_reason = models.TextField(blank=True)
    remaining_pay_periods = models.PositiveSmallIntegerField(default=12,
        help_text="Pay periods left in the FY the projected tax is spread across.")
    tax_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    tax_paid_ytd = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    monthly_tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    statutory_return = models.ForeignKey(
        "hrm.StatutoryReturn", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tax_computations", editable=False,
        help_text="The tds_form16 StatutoryReturn row this Part-B detail belongs to (set by link_form16).")
    computed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-financial_year", "employee__party__name"]
        unique_together = ("tenant", "employee", "financial_year")
        indexes = [
            models.Index(fields=["tenant", "financial_year"], name="hrm_txc_tenant_fy_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_txc_tenant_emp_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Per-instance memo for the engine's DB primitives — the derived @property methods access them
        # many times per render (a detail page reads ~9 properties), so without this the same
        # structure/regime-config/declaration-lines/slab-bands lookups fire dozens of times. Only the
        # QUERY boundaries are cached (not the pure-Python tax properties), so recompute() stays correct.
        self._engine_cache = {}

    def save(self, *args, **kwargs):
        # financial_year is a denormalized copy of the declaration's — derive it here so it is always
        # populated regardless of the entry path (the form excludes it). A blank FY would make
        # _regime_config() find no TaxRegimeConfig and silently compute zero tax.
        if not self.financial_year and self.declaration_id:
            self.financial_year = self.declaration.financial_year
        return super().save(*args, **kwargs)

    # ----- resolved inputs (query the employee's active salary structure / regime config), memoized -----
    def _active_structure(self):
        if "structure" not in self._engine_cache:
            self._engine_cache["structure"] = (
                self.employee.salary_structures.filter(status="active")
                .select_related("template").order_by("-effective_from").first())
        return self._engine_cache["structure"]

    def _structure_lines(self):
        """The active structure's template lines (fetched once with the pay component preloaded)."""
        if "structure_lines" not in self._engine_cache:
            struct = self._active_structure()
            self._engine_cache["structure_lines"] = (
                list(struct.template.lines.select_related("pay_component"))
                if struct and struct.template_id else [])
        return self._engine_cache["structure_lines"]

    def _declaration_lines(self):
        """The declaration's section lines (fetched once — read by hra/chapter-via/capped-sections)."""
        if "declaration_lines" not in self._engine_cache:
            self._engine_cache["declaration_lines"] = list(self.declaration.lines.all())
        return self._engine_cache["declaration_lines"]

    def _component_annual(self, code, name_substr):
        """Resolve a pay component's annual amount from the employee's active structure (basic/HRA)."""
        struct = self._active_structure()
        if not struct or not struct.template_id:
            return ZERO
        for line in self._structure_lines():
            pc = line.pay_component
            if (pc.code or "").upper() == code or name_substr in pc.name.lower():
                return line.resolved_amount(struct.annual_ctc_amount)
        return ZERO

    def _regime_config(self, regime):
        key = ("regime_config", regime)
        if key not in self._engine_cache:
            self._engine_cache[key] = TaxRegimeConfig.objects.filter(
                tenant_id=self.tenant_id, financial_year=self.financial_year, regime=regime
            ).prefetch_related("slab_bands").first()
        return self._engine_cache[key]

    def _fy_date_range(self):
        """Parse ``"YYYY-YY"`` → (Apr 1 start, Mar 31 next-year end) of the Indian FY."""
        try:
            start_year = int(str(self.financial_year).split("-")[0])
        except (ValueError, IndexError, AttributeError):
            return date(1900, 1, 1), date(2999, 12, 31)
        return date(start_year, 4, 1), date(start_year + 1, 3, 31)

    @property
    def gross_annual_income(self):
        struct = self._active_structure()
        base = struct.annual_ctc_amount if struct else ZERO
        return (base + self.declaration.previous_employer_income).quantize(Decimal("0.01"))

    # ----- per-regime deduction helpers (regime-parameterized so both regimes can be compared) -----
    def _hra_exemption(self, regime):
        """Standard 3-way HRA exemption minimum (annual). Zero under the new regime or with no HRA line."""
        if regime == "new":
            return ZERO
        hra_line = next((ln for ln in self._declaration_lines() if ln.section_code == "hra"), None)
        if hra_line is None or not hra_line.monthly_rent_amount:
            return ZERO
        basic = self._component_annual("BASIC", "basic")
        annual_rent = hra_line.monthly_rent_amount * Decimal("12")
        pct = Decimal("50") if hra_line.is_metro_city else Decimal("40")
        candidates = [
            max(annual_rent - basic * Decimal("10") / Decimal("100"), ZERO),  # rent − 10% of basic
            basic * pct / Decimal("100"),                                      # 50%/40% of basic
        ]
        actual_hra = self._component_annual("HRA", "house rent")              # actual HRA received
        if actual_hra > 0:
            candidates.append(actual_hra)
        return max(min(candidates), ZERO).quantize(Decimal("0.01"))

    def _chapter_via(self, regime):
        """Sum the effective (verified-else-declared) Chapter VI-A deductions valid for ``regime``,
        capped per ``SECTION_CAPS``, excluding HRA (handled separately)."""
        total = ZERO
        for line in self._declaration_lines():
            if line.section_code == "hra":
                continue
            if regime == "new" and line.section_code not in NEW_REGIME_ALLOWED_SECTIONS:
                continue
            amt = line.effective_amount
            cap = SECTION_CAPS.get(line.section_code)
            if cap is not None:
                amt = min(amt, cap)
            total += amt
        return total.quantize(Decimal("0.01"))

    @property
    def capped_sections(self):
        """(label, claimed, cap) tuples for sections whose claim exceeded its statutory cap — surfaced
        as a warning, never silently dropped."""
        out = []
        for line in self._declaration_lines():
            cap = SECTION_CAPS.get(line.section_code)
            if cap is not None and line.effective_amount > cap:
                out.append((line.get_section_code_display(), line.effective_amount, cap))
        return out

    def _taxable_income(self, regime):
        config = self._regime_config(regime)
        std = config.standard_deduction if config else ZERO
        taxable = (self.gross_annual_income - std - self._hra_exemption(regime) - self._chapter_via(regime))
        return max(taxable, ZERO).quantize(Decimal("0.01"))

    def _regime_tax(self, regime):
        config = self._regime_config(regime)
        if config is None:
            return ZERO
        taxable = self._taxable_income(regime)
        # Sort the prefetched slab bands in Python (config is loaded via _regime_config's
        # prefetch_related("slab_bands"), so .order_by() would defeat the prefetch with a fresh query).
        bands = [(b.income_from, b.income_to, b.rate_percent)
                 for b in sorted(config.slab_bands.all(), key=lambda b: (b.sequence, b.income_from))]
        tax = _progressive_tax(taxable, bands)
        # Section 87A rebate — zero out (capped) when taxable income is at/below the threshold.
        if config.rebate_income_threshold is not None and taxable <= config.rebate_income_threshold:
            rebate = min(tax, config.rebate_max_tax if config.rebate_max_tax is not None else tax)
            tax = max(tax - rebate, ZERO)
        # Health & Education cess on the post-rebate tax.
        tax = (tax * (Decimal("1") + config.cess_rate / Decimal("100"))).quantize(Decimal("0.01"))
        return tax

    @property
    def hra_exemption(self):
        return self._hra_exemption(self.declaration.regime_elected)

    @property
    def total_chapter_via_deductions(self):
        return self._chapter_via(self.declaration.regime_elected)

    @property
    def taxable_income_old(self):
        return self._taxable_income("old")

    @property
    def taxable_income_new(self):
        return self._taxable_income("new")

    @property
    def tax_old_regime(self):
        return self._regime_tax("old")

    @property
    def tax_new_regime(self):
        return self._regime_tax("new")

    @property
    def cheaper_regime(self):
        """Which regime costs less (for the comparison nudge); ties resolve to 'new'."""
        return "old" if self.tax_old_regime < self.tax_new_regime else "new"

    def _tds_paid_ytd(self):
        """Sum this employee's TDS ``PayslipLine``s across the FY's cycles — reuses 3.15's TDS keyword
        list and the employee-bucket rule (everything not employer-side), scoped to this employee."""
        start, end = self._fy_date_range()
        lines = PayslipLine.objects.filter(
            tenant_id=self.tenant_id, component_type="statutory_deduction",
            payslip__employee_id=self.employee_id,
            payslip__cycle__pay_date__gte=start, payslip__cycle__pay_date__lte=end,
        ).exclude(contribution_side="employer")
        cond = Q()
        for kw in StatutoryReturn.SCHEME_KEYWORDS["tds_24q"]:
            cond |= Q(component_name__icontains=kw)
        return lines.filter(cond).aggregate(s=Sum("amount"))["s"] or ZERO

    def recompute(self):
        """Derive tax_payable (under the elected regime) + tax_paid_ytd + monthly_tds_amount. A ``final``
        computation requires the declaration's proof window to have closed (the provisional/final gate)."""
        if (self.computation_type == "final" and self.declaration.proof_window_close
                and self.declaration.proof_window_close > timezone.localdate()):
            raise ValidationError("A final computation requires the proof window to have closed.")
        self.tax_paid_ytd = self._tds_paid_ytd()
        self.tax_payable = (self.tax_old_regime if self.declaration.regime_elected == "old"
                            else self.tax_new_regime)
        if self.manual_override_amount is not None:
            self.monthly_tds_amount = self.manual_override_amount
        elif self.remaining_pay_periods:
            self.monthly_tds_amount = max(
                (self.tax_payable - self.tax_paid_ytd) / Decimal(self.remaining_pay_periods), ZERO
            ).quantize(Decimal("0.01"))
        else:
            self.monthly_tds_amount = ZERO
        self.computed_at = timezone.now()
        self.save(update_fields=["tax_payable", "tax_paid_ytd", "monthly_tds_amount",
                                 "computed_at", "updated_at"])

    def link_form16(self, user=None):
        """Get-or-create the ``StatutoryReturn(scheme="tds_form16")`` row for this employee/FY (Part A
        source) and link it. Recomputes that row's Part-A aggregates only while it is still pending."""
        start, end = self._fy_date_range()
        ret, _ = StatutoryReturn.objects.update_or_create(
            tenant_id=self.tenant_id, scheme="tds_form16", period_start=start, employee=self.employee,
            defaults={"period_type": "annual", "period_end": end,
                      "notes": f"Form 16 for {self.employee} · FY {self.financial_year}."})
        if ret.status == "pending":
            ret.recompute()
        self.statutory_return = ret
        self.save(update_fields=["statutory_return", "updated_at"])
        return ret

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.financial_year}"
