"""CRM 1.3 Marketing Automation — FormSubmissions models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class FormSubmission(models.Model):
    """A web-to-lead capture from a public LandingPage (1.3 Landing Pages & Forms).

    Read-mostly: rows are created only by the public ``landing_public`` endpoint, so there is
    no internal create/edit form (mirrors the ``WorkflowLog`` read-only precedent). They can be
    converted into a ``crm.Lead`` (routed to the rep) or deleted as spam.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("routed", "Routed"),
        ("converted", "Converted"),
        ("spam", "Spam"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    landing_page = models.ForeignKey("LandingPage", on_delete=models.CASCADE, related_name="submissions")
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="new")
    routed_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_routed_submissions")
    converted_lead = models.ForeignKey("Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_form_submissions")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_fsub_tnt_status_idx"),
            models.Index(fields=["tenant", "landing_page"], name="crm_fsub_tnt_lp_idx"),
        ]

    def __str__(self):
        return f"{self.name} · {self.get_status_display()}"
