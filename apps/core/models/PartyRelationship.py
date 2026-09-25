"""core — PartyRelationship models (split from apps/core/models.py)."""
from django.core.exceptions import ValidationError
from django.db import transaction

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

    def _validate_relationship(self, *, lock=False):
        if not self.tenant_id or not self.from_party_id or not self.to_party_id:
            raise ValidationError({"from_party": "Both relationship Parties are required."})
        if self.from_party_id == self.to_party_id:
            raise ValidationError({"to_party": "A Party cannot relate to itself."})
        if self.kind not in dict(self.KIND_CHOICES):
            raise ValidationError({"kind": "Unsupported relationship kind."})
        tenant_model = self._meta.get_field("tenant").remote_field.model
        party_model = self._meta.get_field("from_party").remote_field.model
        if lock:
            with transaction.atomic():
                tenant_model._default_manager.select_for_update().only("pk").get(pk=self.tenant_id)
                party_model._default_manager.select_for_update().filter(
                    pk__in=(self.from_party_id, self.to_party_id),
                    tenant_id=self.tenant_id,
                )
                self._validate_relationship()
            return
        parties = list(
            party_model._default_manager.filter(
                pk__in=(self.from_party_id, self.to_party_id),
                tenant_id=self.tenant_id,
            ).values("pk", "kind")
        )
        if len({party["pk"] for party in parties}) != 2:
            raise ValidationError({"from_party": "Relationship Parties must belong to the same workspace."})
        if self.kind == "reports_to" and any(party["kind"] != "person" for party in parties):
            raise ValidationError({"from_party": "Reporting lines require person Parties."})

    def clean(self):
        super().clean()
        self._validate_relationship()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self._validate_relationship(lock=True)
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.from_party} {self.get_kind_display()} {self.to_party}"
