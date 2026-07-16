"""core — Party models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class Party(models.Model):
    """One record per real-world person or organization. Roles are attached via PartyRole."""

    KIND_CHOICES = [("person", "Person"), ("organization", "Organization")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="parties", db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="person")
    name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "parties"

    def __str__(self):
        return self.name
