"""HRM 3.36 Helpdesk — Helpdeskcategory models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class HelpdeskCategory(TenantOwned):
    """Ticket routing taxonomy (HR / IT / Admin / Facilities / …) that also serves as the knowledge-base
    taxonomy. Carries the ``default_assignee`` + ``default_sla_policy`` a new ticket in this category
    inherits. Small per-tenant catalog identified by name — not auto-numbered."""

    DEPARTMENT_CHOICES = [
        ("hr", "Human Resources"),
        ("it", "IT"),
        ("admin", "Administration"),
        ("facilities", "Facilities"),
        ("finance", "Finance"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=100)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, default="hr")
    description = models.TextField(blank=True)
    default_assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name="hrm_helpdesk_categories")
    default_sla_policy = models.ForeignKey("hrm.HelpdeskSLAPolicy", on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name="categories")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["department", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_hdcat_tnt_active_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_hdcat_tnt_dept_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_department_display()})"
