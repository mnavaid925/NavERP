"""CRM 1.11 Customer Success & Retention — OnboardingPlans models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ----------------------------------------------------- 1.11 Customer Success & Retention
class OnboardingPlan(TenantNumbered):
    """A per-client onboarding checklist (1.11). ``progress_pct`` is derived from steps."""

    NUMBER_PREFIX = "CS"

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("on_hold", "On Hold"),
        ("cancelled", "Cancelled"),
    ]

    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_onboarding_plans")
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    target_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set when all steps done
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_onboarding_plans")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "account"], name="crm_obp_tnt_account_idx"),
            models.Index(fields=["tenant", "status"], name="crm_obp_tnt_status_idx"),
        ]

    @property
    def progress_pct(self):
        steps = list(self.steps.all())
        if not steps:
            return 0
        done = sum(1 for s in steps if s.completed_at is not None)
        return round(done / len(steps) * 100)

    def __str__(self):
        return f"{self.number} · {self.name}"


class OnboardingStep(models.Model):
    """An ordered checklist item within an OnboardingPlan (1.11)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    plan = models.ForeignKey("crm.OnboardingPlan", on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_onboarding_steps")
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set on completion
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title
