"""HRM 3.5 Job Requisition — Jobdescriptiontemplate models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.JobRequisition.EMPLOYMENT_TYPE_CHOICESs import EMPLOYMENT_TYPE_CHOICES
from apps.hrm.models.JobRequisition.EMPLOYMENT_TYPE_CHOICESs import EMPLOYMENT_TYPE_CHOICES


class JobDescriptionTemplate(TenantNumbered):
    """Reusable job-description library (3.5). Optionally tied to a ``Designation`` so a
    requisition raised for that role can auto-suggest the template (mirrors
    ``OnboardingTemplate.designation``). Applying a template copies its ``jd_*`` text onto the
    requisition (copy-on-apply, not a live link), so editing the template never silently mutates
    open requisitions."""

    NUMBER_PREFIX = "JDTMPL"

    name = models.CharField(max_length=255)
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="jd_templates")
    employment_type = models.CharField(max_length=20, blank=True, choices=EMPLOYMENT_TYPE_CHOICES)
    jd_summary = models.TextField(blank=True)
    jd_responsibilities = models.TextField(blank=True)
    jd_requirements = models.TextField(blank=True)
    jd_nice_to_have = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "designation"], name="hrm_jdtmpl_tenant_desig_idx"),
            models.Index(fields=["tenant", "is_active"], name="hrm_jdtmpl_tenant_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"
