"""HRM 3.13 Salary Structure — Salarystructuretemplate models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class SalaryStructureTemplate(TenantNumbered):
    """A grade-wise CTC structure template (3.13) — ``SST-#####``. Its total CTC is DERIVED from the
    resolved breakdown lines (``computed_ctc_total``), never stored editable."""

    NUMBER_PREFIX = "SST"

    name = models.CharField(max_length=150)
    job_grade = models.ForeignKey("hrm.JobGrade", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="salary_structure_templates")
    annual_ctc_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Target annual CTC — the base for %-of-CTC lines.")
    currency = models.CharField(max_length=10, default="USD")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "job_grade"], name="hrm_sst_tenant_grade_idx"),
        ]

    @property
    def computed_ctc_total(self):
        """Derived total CTC — the sum of every line's resolved amount. Never a stored field."""
        return sum((line.resolved_amount() for line in self.lines.select_related("pay_component").all()),
                   Decimal("0"))

    def __str__(self):
        return f"{self.number} · {self.name}"
