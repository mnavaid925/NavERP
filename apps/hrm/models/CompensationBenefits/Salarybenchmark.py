"""HRM 3.37 Compensation & Benefits — Salarybenchmark models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.37 Compensation & Benefits — builds ON TOP of the 3.13 salary spine
# (PayComponent/SalaryStructureTemplate/EmployeeSalaryStructure) + the 3.2
# Designation salary bands, never duplicating them. Four new tables cover 4 of the
# 6 NavERP.md bullets: SalaryBenchmark (external market percentile data → compa-ratio),
# BenefitPlan (the benefits catalog incl. flex-credit) + EmployeeBenefitEnrollment
# (per-employee opt-in/opt-out elections), and EquityGrant (ISO/NSO/RSU/ESPP/phantom
# grants with COMPUTED vesting/exercisable — never a stored balance, mirroring
# LeaveAllocation/TravelBooking). Compensation Planning (merit/promotion cycles) and
# a formal monetary RecognitionAward are DEFERRED (peer kudos already live in 3.20
# Feedback/KudosBadge). Money reuses accounting.Currency; GL/payroll posting is owned
# by accounting.PayrollRun — this sub-module posts no JournalEntry.
# ---------------------------------------------------------------------------
class SalaryBenchmark(TenantOwned):
    """External market-salary reference data (P25/P50/P75/P90) keyed to a job grade and/or designation,
    from an internal or purchased survey. Drives compa-ratio checks against the 3.13 EmployeeSalaryStructure
    / 3.2 Designation bands. Small per-tenant catalog (not auto-numbered). A blank job_grade/designation
    means 'applies broadly'."""

    SOURCE_CHOICES = [
        ("internal", "Internal Survey"),
        ("payscale", "Payscale"),
        ("mercer", "Mercer"),
        ("radford", "Radford"),
        ("other", "Other"),
    ]

    job_grade = models.ForeignKey("hrm.JobGrade", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="salary_benchmarks")
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="salary_benchmarks")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="internal")
    region = models.CharField(max_length=100, blank=True, help_text="e.g. US-National, APAC, EMEA.")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_salary_benchmarks")
    percentile_25 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    percentile_50 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    percentile_75 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    percentile_90 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    survey_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-survey_date", "id"]
        indexes = [
            models.Index(fields=["tenant", "job_grade"], name="hrm_sbm_tnt_grade_idx"),
            models.Index(fields=["tenant", "designation"], name="hrm_sbm_tnt_desig_idx"),
        ]

    def __str__(self):
        label = self.designation.name if self.designation_id else (
            self.job_grade.name if self.job_grade_id else "General")
        return f"{label} — {self.get_source_display()} ({self.region or 'all regions'})"

    def compa_ratio(self, current_pay):
        """(current_pay / market median). >1 = above market, <1 = below. None if no median or pay."""
        if not self.percentile_50 or not current_pay:
            return None
        return (Decimal(current_pay) / self.percentile_50).quantize(Decimal("0.01"))
