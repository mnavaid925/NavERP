"""CRM 1.4 Customer Service & Support — KbCategories models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class KbCategory(TenantNumbered):
    """A knowledge-base category (1.4) with an optional parent for a section hierarchy."""

    NUMBER_PREFIX = "KBC"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=160, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_categories")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_kbc_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"
