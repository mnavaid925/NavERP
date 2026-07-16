"""core — PartyRelationship models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class PartyRelationship(models.Model):
    KIND_CHOICES = [
        ("employee_of", "Employee of"),
        ("contact_of", "Contact of"),
        ("subsidiary_of", "Subsidiary of"),
        ("reports_to", "Reports to"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="party_relationships", db_index=True)
    from_party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="relationships_from")
    to_party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="relationships_to")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)

    class Meta:
        ordering = ["from_party__name"]

    def __str__(self):
        return f"{self.from_party} {self.get_kind_display()} {self.to_party}"
