"""core — Tenant models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class Tenant(models.Model):
    """A customer workspace. Root of all tenant-scoped data."""

    PLAN_CHOICES = [
        ("free", "Free"),
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
