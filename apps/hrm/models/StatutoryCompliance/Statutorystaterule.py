"""HRM 3.15 Statutory Compliance — Statutorystaterule models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.StatutoryCompliance.INDIAN_STATE_CHOICESs import INDIAN_STATE_CHOICES
from apps.hrm.models.StatutoryCompliance.INDIAN_STATE_CHOICESs import INDIAN_STATE_CHOICES


class StatutoryStateRule(TenantOwned):
    """State-wise PT + LWF slab/rate table (3.15) — one shared table for both state-scoped
    schemes (mirrors greytHR's editable PT slab grid + the LWF state-applicability/periodicity/
    amount pattern). Rate changes are a NEW row (supersede via ``is_active=False``), never an
    in-place edit, so prior-period returns stay historically correct (the greytHR "Odisha PT
    discontinued from April 2026" pattern).

    NULL note: for LWF, ``income_from`` stays ``None`` — and DB unique constraints treat NULLs as
    distinct, so ``clean()`` additionally enforces one active LWF row per ``(tenant, state)``."""

    SCHEME_CHOICES = [
        ("pt", "Professional Tax"),
        ("lwf", "Labour Welfare Fund"),
    ]
    LWF_PERIODICITY_CHOICES = [
        ("monthly", "Monthly"),
        ("half_yearly", "Half-Yearly"),
        ("annual", "Annual"),
    ]

    state = models.CharField(max_length=50, choices=INDIAN_STATE_CHOICES)
    scheme = models.CharField(max_length=10, choices=SCHEME_CHOICES, default="pt")
    # PT-only (blank/null when scheme="lwf") — the income bracket → monthly tax amount.
    income_from = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    income_to = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pt_monthly_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pt_deduction_month = models.CharField(max_length=20, blank=True,
        help_text="Optional — some states deduct PT only in specific months (e.g. an annual lump sum).")
    # LWF-only (blank/null when scheme="pt").
    lwf_employee_contribution = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lwf_employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lwf_periodicity = models.CharField(max_length=20, choices=LWF_PERIODICITY_CHOICES, blank=True)
    lwf_due_month_1 = models.CharField(max_length=20, blank=True, help_text="e.g. July.")
    lwf_due_month_2 = models.CharField(max_length=20, blank=True, help_text="e.g. January (half-yearly states).")
    registration_number = models.CharField(max_length=50, blank=True,
        help_text="State-specific PT/LWF employer registration number, where applicable.")
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["state", "scheme", "income_from"]
        unique_together = ("tenant", "state", "scheme", "income_from")
        indexes = [
            models.Index(fields=["tenant", "scheme"], name="hrm_ssr_tenant_scheme_idx"),
            models.Index(fields=["tenant", "state"], name="hrm_ssr_tenant_state_idx"),
        ]

    def clean(self):
        super().clean()
        if self.scheme == "pt":
            missing = [f for f in ("income_from", "income_to", "pt_monthly_amount")
                       if getattr(self, f) is None]
            if missing:
                raise ValidationError({m: "Required for a Professional Tax slab." for m in missing})
            if (self.income_from is not None and self.income_to is not None
                    and self.income_to < self.income_from):
                raise ValidationError({"income_to": "Income-to cannot be below income-from."})
        elif self.scheme == "lwf":
            if self.lwf_employee_contribution is None or self.lwf_employer_contribution is None:
                raise ValidationError({
                    "lwf_employee_contribution": "Employee + employer LWF contributions are required.",
                })
            if not self.lwf_periodicity:
                raise ValidationError({"lwf_periodicity": "LWF periodicity is required."})
            # App-level guard on top of the (NULL-distinct) DB constraint: at most one active LWF
            # row per (tenant, state) — a rate change supersedes the old row (is_active=False).
            if self.is_active and self.tenant_id:
                clash = StatutoryStateRule.objects.filter(
                    tenant_id=self.tenant_id, state=self.state, scheme="lwf", is_active=True)
                if self.pk:
                    clash = clash.exclude(pk=self.pk)
                if clash.exists():
                    raise ValidationError(
                        "An active LWF rule already exists for this state — deactivate it first.")

    def __str__(self):
        label = f"{self.get_state_display()} · {self.get_scheme_display()}"
        if self.scheme == "pt" and self.income_from is not None:
            label += f" ({self.income_from}–{self.income_to})"
        return label
