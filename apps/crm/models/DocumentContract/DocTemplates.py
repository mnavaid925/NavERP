"""CRM 1.9 Document & Contract Management — DocTemplates models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ----------------------------------------------------- 1.9 Document & Contract Management
class DocTemplate(TenantNumbered):
    """A reusable HTML document template with Django merge variables (1.9)."""

    NUMBER_PREFIX = "TPL"

    TYPE_CHOICES = [
        ("nda", "NDA"),
        ("proposal", "Proposal"),
        ("contract", "Contract"),
        ("quote", "Quote"),
        ("receipt", "Receipt"),
    ]

    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="contract")
    body = models.TextField(blank=True)  # HTML with {{ account.name }} / {{ opportunity.amount }} / {{ today }}
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_doc_templates")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "template_type"], name="crm_tpl_tnt_type_idx"),
            models.Index(fields=["tenant", "is_active"], name="crm_tpl_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"
