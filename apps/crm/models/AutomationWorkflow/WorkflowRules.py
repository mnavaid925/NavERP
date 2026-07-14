"""CRM 1.10 Automation & Workflow Engine — WorkflowRules models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ------------------------------------------------------ 1.10 Automation & Workflow Engine
class WorkflowRule(TenantNumbered):
    """A declarative trigger-condition-action automation rule (1.10)."""

    NUMBER_PREFIX = "WFR"

    ENTITY_CHOICES = [
        ("lead", "Lead"),
        ("opportunity", "Opportunity"),
        ("case", "Case"),
        ("expense", "Expense"),
        ("contract", "Contract"),
        ("health_score", "Health Score"),
    ]
    EVENT_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("status_changed", "Status Changed"),
        ("field_value", "Field Value Matches"),
        ("date_reached", "Date Reached"),
    ]
    DELAY_CHOICES = [("minutes", "Minutes"), ("hours", "Hours"), ("days", "Days")]

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    trigger_entity = models.CharField(max_length=20, choices=ENTITY_CHOICES, default="opportunity")
    trigger_event = models.CharField(max_length=20, choices=EVENT_CHOICES, default="created")
    trigger_field = models.CharField(max_length=100, blank=True)
    trigger_value = models.CharField(max_length=255, blank=True)
    conditions = models.JSONField(default=list, blank=True)  # [{field, operator, value}] (AND)
    actions = models.JSONField(default=list, blank=True)      # [{type, params}]
    delay_value = models.PositiveSmallIntegerField(null=True, blank=True)
    delay_unit = models.CharField(max_length=10, choices=DELAY_CHOICES, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_workflow_rules")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_wfr_tnt_active_idx"),
            models.Index(fields=["tenant", "trigger_entity"], name="crm_wfr_tnt_entity_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"
