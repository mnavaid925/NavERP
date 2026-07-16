"""HRM 3.36 Helpdesk — Knowledgearticle models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class KnowledgeArticle(TenantNumbered):
    """Internal knowledge-base FAQ / self-help article (``KBA-#####``). Categorized by
    ``HelpdeskCategory``; draft -> published -> archived lifecycle. ``view_count`` / ``helpful_count``
    are engagement counters bumped by the read / mark-helpful actions (never hand-edited on the form).
    Internal-only — no public portal token (trimmed from ``crm.KnowledgeArticle``)."""

    NUMBER_PREFIX = "KBA"

    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")]

    title = models.CharField(max_length=255)
    category = models.ForeignKey("hrm.HelpdeskCategory", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="articles")
    summary = models.CharField(max_length=500, blank=True)
    body = models.TextField()
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords for search.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="hrm_kb_articles")
    view_count = models.PositiveIntegerField(default=0)
    helpful_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_kba_tnt_status_idx"),
            models.Index(fields=["tenant", "category"], name="hrm_kba_tnt_cat_idx"),
            # Backs the default ``-updated_at`` ordering on the self-help list landing page.
            models.Index(fields=["tenant", "-updated_at"], name="hrm_kba_tnt_updated_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}" if self.number else self.title
