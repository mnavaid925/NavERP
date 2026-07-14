"""CRM 1.4 Customer Service & Support — KnowledgeBase models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class KnowledgeArticle(TenantNumbered):
    """A help-desk solution / FAQ (1.4) with internal vs external visibility."""

    NUMBER_PREFIX = "KB"

    VISIBILITY_CHOICES = [("internal", "Internal"), ("external", "External")]
    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")]

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=120, blank=True)  # legacy free-text (kept; kb_category preferred)
    kb_category = models.ForeignKey("KbCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="articles")
    slug = models.SlugField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="internal")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    views_count = models.PositiveIntegerField(default=0)  # system-set on detail view
    helpful_count = models.PositiveIntegerField(default=0)  # system-set via public vote
    not_helpful_count = models.PositiveIntegerField(default=0)  # system-set via public vote
    # null=True (not blank="") so existing rows stay distinct under the unique index until backfilled.
    public_token = models.CharField(max_length=64, unique=True, editable=False, null=True, blank=True)  # public article URL key
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_articles")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_kb_tenant_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_kb_tenant_created_idx"),
            models.Index(fields=["tenant", "kb_category"], name="crm_kb_tnt_category_idx"),
        ]

    @property
    def is_public(self):
        return self.status == "published" and self.visibility == "external"

    def save(self, *args, **kwargs):
        if not self.public_token:  # unguessable public-share URL key, generated once
            self.public_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.title}"
