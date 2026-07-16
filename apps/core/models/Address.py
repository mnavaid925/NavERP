"""core — Address models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class Address(models.Model):
    KIND_CHOICES = [("billing", "Billing"), ("shipping", "Shipping"), ("home", "Home")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="addresses", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="addresses")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="billing")
    line1 = models.CharField(max_length=255)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["party__name", "kind"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.line1}, {self.city}" if self.city else self.line1
