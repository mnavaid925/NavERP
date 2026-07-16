"""core — PartyRole models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class PartyRole(models.Model):
    """The role a Party plays — customer, vendor, employee, lead, etc."""

    ROLE_CHOICES = [
        ("customer", "Customer"),
        ("vendor", "Vendor"),
        ("supplier", "Supplier"),
        ("employee", "Employee"),
        ("lead", "Lead"),
        ("candidate", "Candidate"),
        ("contact", "Contact"),
        ("partner", "Partner"),
    ]
    STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive"), ("archived", "Archived")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="party_roles", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="roles")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    start_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["party__name", "role"]
        unique_together = ("party", "role")

    def __str__(self):
        return f"{self.party} · {self.get_role_display()}"
