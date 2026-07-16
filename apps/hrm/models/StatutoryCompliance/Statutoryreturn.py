"""HRM 3.15 Statutory Compliance — Statutoryreturn models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.PayrollProcessing.Payslip import PayslipLine
from apps.hrm.models.StatutoryCompliance.Statutoryconfig import StatutoryConfig
from apps.hrm.models.StatutoryCompliance.Statutorystaterule import StatutoryStateRule
from apps.hrm.models.PayrollProcessing.Payslip import PayslipLine
from apps.hrm.models.StatutoryCompliance.Statutoryconfig import StatutoryConfig
from apps.hrm.models.StatutoryCompliance.Statutorystaterule import StatutoryStateRule


class StatutoryReturn(TenantNumbered):
    """A per-scheme, per-period statutory return / challan / register record (3.15) —
    ``SCR-#####``. One shared table covers all five schemes (PF/ESI/PT/TDS/LWF). The
    contribution totals are DERIVED by ``recompute()`` — an aggregate over the already-computed
    ``PayslipLine`` rows for the period, mirroring 3.14's ``payrollcycle_lock`` roll-up — never
    hand-typed. ``registration_number_used`` is snapshotted at generation time so a later config/
    rule edit never rewrites a historical return (the ``PayslipLine`` snapshot convention).

    v1 scheme matching: ``PayslipLine`` has no per-line scheme tag yet (PF/ESI/PT/LWF are all
    ``component_type='statutory_deduction'``), so ``recompute()`` matches lines by a
    ``component_name`` substring per ``SCHEME_KEYWORDS``. A proper per-line scheme tag is a
    deferred fast-follow (would require a 3.14 model change)."""

    NUMBER_PREFIX = "SCR"

    SCHEME_CHOICES = [
        ("pf", "Provident Fund"),
        ("esi", "ESI"),
        ("pt", "Professional Tax"),
        ("tds_24q", "TDS — Form 24Q"),
        ("tds_form16", "TDS — Form 16"),
        ("lwf", "Labour Welfare Fund"),
    ]
    PERIOD_TYPE_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("half_yearly", "Half-Yearly"),
        ("annual", "Annual"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("filed", "Filed"),
        ("paid", "Paid"),
        ("late", "Late"),
    ]
    # v1 name-substring heuristic mapping a scheme to the PayComponent.name fragments that
    # identify its PayslipLine rows. NOTE: "pf" is NOT a substring of "Provident Fund" — the
    # working keyword for PF is "provident". tds/esi/lwf have no seeded component (aggregate 0).
    SCHEME_KEYWORDS = {
        "pf": ["provident", "epf"],
        "esi": ["esi", "state insurance"],
        "pt": ["professional tax", "profession tax"],
        "tds_24q": ["tds", "income tax", "tax deducted"],
        "tds_form16": ["tds", "income tax", "tax deducted"],
        "lwf": ["lwf", "labour welfare", "labor welfare"],
    }

    scheme = models.CharField(max_length=15, choices=SCHEME_CHOICES)
    period_type = models.CharField(max_length=15, choices=PERIOD_TYPE_CHOICES, default="monthly")
    period_start = models.DateField()
    period_end = models.DateField()
    cycle = models.ForeignKey(
        "hrm.PayrollCycle", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="statutory_returns",
        help_text="Set for the single-cycle monthly case; null for multi-cycle rollups (e.g. quarterly 24Q).")
    employee = models.ForeignKey(
        "hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="statutory_returns", help_text="Set only for per-employee Form 16; null for org-level returns.")
    employee_contribution_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    employer_contribution_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    headcount = models.PositiveIntegerField(default=0, editable=False)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    filed_on = models.DateField(null=True, blank=True, editable=False)
    paid_on = models.DateField(null=True, blank=True, editable=False)
    payment_reference = models.CharField(max_length=100, blank=True)
    registration_number_used = models.CharField(max_length=50, blank=True, editable=False,
        help_text="Snapshot of the config/rule registration number at generation time.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_start", "scheme"]
        unique_together = ("tenant", "scheme", "period_start", "employee")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_scr_tenant_status_idx"),
            models.Index(fields=["tenant", "due_date"], name="hrm_scr_tenant_duedate_idx"),
            models.Index(fields=["tenant", "scheme"], name="hrm_scr_tenant_scheme_idx"),
        ]

    def clean(self):
        super().clean()
        if self.period_end and self.period_start and self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period-end cannot be before period-start."})

    @property
    def is_locked(self):
        """Filed/paid/late returns are immutable — only a pending return can be re-aggregated/edited."""
        return self.status != "pending"

    @property
    def is_overdue(self):
        """Still pending past its due date — drives a "late" visual flag before status is flipped."""
        return self.status == "pending" and self.due_date is not None and self.due_date < timezone.localdate()

    def _scheme_lines(self):
        """The ``PayslipLine`` queryset backing this return: statutory-deduction lines for the
        period (by cycle when set, else by cycle.pay_date range), narrowed by the v1 scheme
        keyword match and — for Form 16 — the single employee."""
        lines = PayslipLine.objects.filter(
            tenant_id=self.tenant_id, component_type="statutory_deduction")
        if self.cycle_id:
            lines = lines.filter(payslip__cycle_id=self.cycle_id)
        else:
            lines = lines.filter(
                payslip__cycle__pay_date__gte=self.period_start,
                payslip__cycle__pay_date__lte=self.period_end)
        keywords = self.SCHEME_KEYWORDS.get(self.scheme, [])
        if keywords:
            cond = Q()
            for kw in keywords:
                cond |= Q(component_name__icontains=kw)
            lines = lines.filter(cond)
        if self.employee_id:
            lines = lines.filter(payslip__employee_id=self.employee_id)
        return lines

    def _resolve_registration_number(self):
        """Best-effort registration number for the scheme, snapshotted at generation time."""
        config = StatutoryConfig.objects.filter(tenant_id=self.tenant_id).first()
        if self.scheme == "pf":
            return config.pf_establishment_code if config else ""
        if self.scheme == "esi":
            return config.esi_employer_code if config else ""
        if self.scheme in ("tds_24q", "tds_form16"):
            return config.tan_number if config else ""
        if self.scheme in ("pt", "lwf"):
            state = config.pt_default_state if config else ""
            base = StatutoryStateRule.objects.filter(
                tenant_id=self.tenant_id, scheme=self.scheme, is_active=True,
                registration_number__gt="")
            # Prefer the org's default-state rule; fall back to any state with a registration number.
            rule = (base.filter(state=state).first() if state else None) or base.order_by("state").first()
            return rule.registration_number if rule else ""
        return ""

    def recompute(self):
        """Derive the contribution totals + headcount from the backing ``PayslipLine`` rows and
        snapshot the registration number. Mirrors 3.14's ``payrollcycle_lock`` bucketing exactly:
        ``employer`` = ``contribution_side="employer"``; ``employee`` = everything else
        (employee/both/blank) — so a "both" line is never double-counted. Immutable once filed."""
        if self.is_locked:
            raise ValidationError("Only a pending return can be re-aggregated.")
        lines = self._scheme_lines()
        self.employer_contribution_total = (
            lines.filter(contribution_side="employer").aggregate(s=Sum("amount"))["s"] or ZERO)
        self.employee_contribution_total = (
            lines.exclude(contribution_side="employer").aggregate(s=Sum("amount"))["s"] or ZERO)
        self.headcount = lines.values("payslip__employee_id").distinct().count()
        self.registration_number_used = self._resolve_registration_number()
        self.save(update_fields=[
            "employee_contribution_total", "employer_contribution_total", "headcount",
            "registration_number_used", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.get_scheme_display()} · {self.period_start}–{self.period_end}"
