"""CRM 1.3 Marketing Automation — LandingPages models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.CoreData.Leads import Lead


class LandingPage(TenantNumbered):
    """A public landing page + web-to-lead form (1.3 Landing Pages & Forms).

    Served at an unguessable ``public_token`` URL; only ``status='published'`` pages resolve
    publicly. ``body`` is tenant-authored and rendered to the public ESCAPED (via the
    ``linebreaks`` filter, never ``|safe``) to avoid stored XSS against visitors. Captured
    leads route to ``routing_owner``.
    """

    NUMBER_PREFIX = "LP"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    campaign = models.ForeignKey("Campaign", on_delete=models.SET_NULL, null=True, blank=True, related_name="landing_pages")
    slug = models.SlugField(max_length=160, blank=True)
    public_token = models.CharField(max_length=64, unique=True, editable=False, blank=True)
    headline = models.CharField(max_length=255)
    subheadline = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    capture_phone = models.BooleanField(default=True)
    capture_company = models.BooleanField(default=True)
    capture_message = models.BooleanField(default=False)
    cta_label = models.CharField(max_length=60, default="Submit")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    routing_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_routed_landing_pages")
    lead_source = models.CharField(max_length=20, choices=Lead.SOURCE_CHOICES, default="web")
    submission_count = models.PositiveIntegerField(default=0)  # system-set (F()-bumped on submit)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_landing_pages")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_lp_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_lp_tnt_created_idx"),
        ]

    @property
    def is_published(self):
        return self.status == "published"

    def save(self, *args, **kwargs):
        # Unguessable public URL key — 256-bit, generated once, never user-editable
        # (matches the project-wide token convention: SignerRecord/UserInvite use token_urlsafe(32)).
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.name}"
