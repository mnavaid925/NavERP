"""core — ContactMethod models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class ContactMethod(models.Model):
    KIND_CHOICES = [("email", "Email"), ("phone", "Phone"), ("mobile", "Mobile")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="contact_methods", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="contact_methods")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="email")
    value = models.CharField(max_length=255)

    class Meta:
        ordering = ["party__name", "kind"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.value}"
