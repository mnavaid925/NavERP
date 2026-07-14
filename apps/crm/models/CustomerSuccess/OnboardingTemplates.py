"""CRM 1.11 Customer Success & Retention — OnboardingTemplates models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class OnboardingTemplate(TenantNumbered):
    """A reusable onboarding blueprint (1.11) whose ordered steps clone into a fresh
    OnboardingPlan for any client in one click (Gainsight/ChurnZero success-plan pattern)."""

    NUMBER_PREFIX = "OTPL"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_otpl_tnt_active_idx"),
        ]

    @property
    def step_count(self):
        return self.steps.count()

    def __str__(self):
        return f"{self.number} · {self.name}"


class OnboardingTemplateStep(models.Model):
    """An ordered step within an OnboardingTemplate (1.11). ``offset_days`` sets the cloned
    step's due date relative to the plan start when the template is applied."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    template = models.ForeignKey("crm.OnboardingTemplate", on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    offset_days = models.PositiveSmallIntegerField(default=0)  # cloned step due = plan start + N days
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title
