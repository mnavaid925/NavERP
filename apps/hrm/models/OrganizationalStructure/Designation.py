"""HRM 3.2 Organizational Structure — Designation models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class Designation(TenantOwned):
    """Job title with a job-grade, description and salary band (3.2). Department is reused from
    ``core.OrgUnit``; the grade is reused from ``hrm.JobGrade`` (the free-text ``grade`` stays
    as a fallback). ``budgeted_headcount`` is the lightweight position-slot proxy."""

    name = models.CharField(max_length=255)
    job_grade = models.ForeignKey("hrm.JobGrade", on_delete=models.SET_NULL, null=True, blank=True, related_name="designations")
    grade = models.CharField(max_length=50, blank=True)
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="designations")
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    min_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    mid_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    max_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budgeted_headcount = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_desig_tenant_active_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_desig_tenant_dept_idx"),
            models.Index(fields=["tenant", "job_grade"], name="hrm_desig_tenant_jg_idx"),
        ]

    def clean(self):
        super().clean()
        if self.min_salary is not None and self.max_salary is not None and self.min_salary > self.max_salary:
            raise ValidationError({"max_salary": "Maximum salary must be greater than or equal to the minimum."})
        if self.mid_salary is not None:
            if self.min_salary is not None and self.mid_salary < self.min_salary:
                raise ValidationError({"mid_salary": "Midpoint salary must be at least the minimum."})
            if self.max_salary is not None and self.mid_salary > self.max_salary:
                raise ValidationError({"mid_salary": "Midpoint salary must not exceed the maximum."})

    def __str__(self):
        label = self.job_grade.name if self.job_grade else self.grade
        return f"{self.name} ({label})" if label else self.name
