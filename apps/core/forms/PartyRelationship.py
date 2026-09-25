"""core — PartyRelationship forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    Party,
    PartyRelationship,
)


class PartyRelationshipForm(TenantModelForm):
    class Meta:
        model = PartyRelationship
        fields = ["from_party", "to_party", "kind"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            parties = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["from_party"].queryset = parties
            self.fields["to_party"].queryset = parties

    def clean(self):
        cleaned = super().clean()
        from_party = cleaned.get("from_party")
        to_party = cleaned.get("to_party")
        if from_party and to_party:
            if from_party.pk == to_party.pk:
                self.add_error("to_party", "A Party cannot relate to itself.")
            tenant_id = getattr(self.tenant, "pk", None)
            if getattr(from_party, "tenant_id", None) != tenant_id or getattr(to_party, "tenant_id", None) != tenant_id:
                self.add_error("from_party", "Relationship Parties must belong to the same workspace.")
            if cleaned.get("kind") == "reports_to" and (from_party.kind != "person" or to_party.kind != "person"):
                self.add_error("from_party", "Reporting lines require person Parties.")
        return cleaned
