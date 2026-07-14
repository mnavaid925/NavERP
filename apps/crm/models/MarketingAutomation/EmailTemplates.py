"""CRM 1.3 Marketing Automation — EmailTemplates models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class EmailTemplate(TenantNumbered):
    """A reusable marketing-email template (1.3 Email Marketing) with merge variables.

    ``body`` is raw HTML with merge tokens (e.g. ``{{first_name}}``); it is shown ESCAPED
    as a source preview on the detail page (never ``|safe``) and deferred on the list QS.
    """

    NUMBER_PREFIX = "EMT"

    CATEGORY_CHOICES = [
        ("newsletter", "Newsletter"),
        ("promotional", "Promotional"),
        ("transactional", "Transactional"),
        ("drip", "Drip / Nurture"),
        ("announcement", "Announcement"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default="promotional")
    subject = models.CharField(max_length=255)
    preheader = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    from_name = models.CharField(max_length=120, blank=True)
    from_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_email_templates")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "category"], name="crm_etpl_tnt_cat_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_etpl_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"
