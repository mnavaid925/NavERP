"""HRM 3.6 Candidate Management — Emailtemplate models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.CandidateManagement.EMAIL_TEMPLATE_TYPE_CHOICESs import EMAIL_TEMPLATE_TYPE_CHOICES
from apps.hrm.models.CandidateManagement.EMAIL_TEMPLATE_TYPE_CHOICESs import EMAIL_TEMPLATE_TYPE_CHOICES


class CandidateEmailTemplate(TenantNumbered):
    """Reusable recruiting email template (3.6). HRM-owned (peer apps don't cross-import crm's). An
    ``is_auto_send`` template whose ``template_type`` matches a stage transition is fired automatically
    by the application stage-move actions."""

    NUMBER_PREFIX = "CETMPL"

    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=30, choices=EMAIL_TEMPLATE_TYPE_CHOICES, default="general")
    subject = models.CharField(max_length=500)
    body_html = models.TextField(
        help_text="Merge fields: {{candidate_name}}, {{job_title}}, {{company_name}}, "
                  "{{recruiter_name}}, {{application_number}}.")
    is_active = models.BooleanField(default=True)
    is_auto_send = models.BooleanField(default=False,
        help_text="Auto-send when a JobApplication stage transition matches this template type.")

    class Meta:
        ordering = ["template_type", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "template_type", "is_active"], name="hrm_cetmpl_type_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}" if self.number else self.name
