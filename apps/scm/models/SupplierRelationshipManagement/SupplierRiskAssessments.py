"""SCM 4.2 Supplier Relationship Management — SupplierRiskAssessment model.

A point-in-time risk review of a supplier across four factors (financial, geopolitical, compliance,
operational). Each factor is scored 1 (low) to 5 (critical); the overall ``risk_level`` is DERIVED
from the worst-weighted picture, never hand-set, so two assessors can't disagree on the headline.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class SupplierRiskAssessment(TenantNumbered):
    """A dated risk assessment of a supplier [SRA-]."""

    NUMBER_PREFIX = "SRA"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("reviewed", "Reviewed"),
        ("archived", "Archived"),
    ]
    LEVEL_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    # Each factor scored on this 1-5 scale.
    SCORE_CHOICES = [(1, "1 — Low"), (2, "2 — Guarded"), (3, "3 — Elevated"), (4, "4 — High"), (5, "5 — Critical")]
    FACTORS = ("financial_score", "geopolitical_score", "compliance_score", "operational_score")

    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="scm_risk_assessments")
    assessment_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")

    financial_score = models.PositiveSmallIntegerField(choices=SCORE_CHOICES, default=1)
    geopolitical_score = models.PositiveSmallIntegerField(choices=SCORE_CHOICES, default=1)
    compliance_score = models.PositiveSmallIntegerField(choices=SCORE_CHOICES, default=1)
    operational_score = models.PositiveSmallIntegerField(choices=SCORE_CHOICES, default=1)

    risk_level = models.CharField(max_length=8, choices=LEVEL_CHOICES, default="low", editable=False)
    risk_index = models.DecimalField(max_digits=4, decimal_places=2, default=0, editable=False,
                                     help_text="Averaged factor score, 1.00-5.00")

    mitigation_plan = models.TextField(blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_risk_assessments", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-assessment_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_sra_tnt_status_idx"),
            models.Index(fields=["tenant", "risk_level"], name="scm_sra_tnt_level_idx"),
        ]

    def recompute_risk_level(self, save=True):
        """Derive risk_index (mean) and risk_level. A single critical factor forces at least High —
        an averaged 'medium' must never hide a 5/5 compliance or financial red flag."""
        scores = [getattr(self, f) for f in self.FACTORS]
        mean = Decimal(sum(scores)) / Decimal(len(scores))
        self.risk_index = mean.quantize(Decimal("0.01"))
        worst = max(scores)
        if mean >= Decimal("4") or worst >= 5:
            level = "critical" if mean >= Decimal("4") else "high"
        elif mean >= Decimal("3") or worst >= 4:
            level = "high" if mean >= Decimal("3") else "medium"
        elif mean >= Decimal("2"):
            level = "medium"
        else:
            level = "low"
        self.risk_level = level
        if save:
            self.save(update_fields=["risk_index", "risk_level", "updated_at"])

    def __str__(self):
        return f"{self.number or 'SRA'} · {self.party_id and self.party.name} ({self.get_risk_level_display()})"
