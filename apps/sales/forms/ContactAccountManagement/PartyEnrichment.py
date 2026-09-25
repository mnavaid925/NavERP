from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import ConsentPurpose, Party
from apps.sales.forms._common import TenantActionForm, _reject_foreign
from apps.sales.models.ContactAccountManagement.PartyEnrichment import (
    ENRICHMENT_FIELD_CHOICES,
    EXTERNAL_SOURCE_KINDS,
    PartyEnrichmentEvent,
    validate_enrichment_changes,
)


class PartyEnrichmentProposalForm(TenantActionForm):
    party = forms.ModelChoiceField(queryset=Party.objects.none(), label="Party")
    kind = forms.ChoiceField(choices=PartyEnrichmentEvent.KIND_CHOICES)
    source_kind = forms.ChoiceField(choices=PartyEnrichmentEvent.SOURCE_KIND_CHOICES)
    source_name = forms.CharField(max_length=120, required=False)
    source_reference = forms.CharField(max_length=255, required=False)
    changes = forms.JSONField(
        required=False,
        label="Proposed fields",
        widget=forms.Textarea(attrs={"rows": 8, "class": "form-textarea"}),
    )
    legal_basis_purpose = forms.ModelChoiceField(
        queryset=ConsentPurpose.objects.none(),
        required=False,
        label="Lawful basis purpose",
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is None:
            self.fields["party"].queryset = Party.objects.none()
            self.fields["legal_basis_purpose"].queryset = ConsentPurpose.objects.none()
        else:
            party_ids = list(Party.objects.filter(
                tenant=tenant
            ).order_by("name").values_list("pk", flat=True)[:500])
            purpose_ids = list(ConsentPurpose.objects.filter(
                tenant=tenant, is_active=True
            ).order_by("name").values_list("pk", flat=True)[:500])
            self.fields["party"].queryset = Party.objects.filter(pk__in=party_ids)
            self.fields["legal_basis_purpose"].queryset = ConsentPurpose.objects.filter(pk__in=purpose_ids)
        self.fields["changes"].initial = {}

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["party", "legal_basis_purpose"])
        try:
            cleaned["changes"] = validate_enrichment_changes(cleaned.get("changes") or {})
        except ValidationError as exc:
            self.add_error(None, exc)
        if cleaned.get("source_kind") in EXTERNAL_SOURCE_KINDS and not cleaned.get("legal_basis_purpose"):
            self.add_error("legal_basis_purpose", "External enrichment requires a lawful basis purpose.")
        return cleaned


class PartyEnrichmentApplyForm(TenantActionForm):
    selected_fields = forms.MultipleChoiceField(
        choices=ENRICHMENT_FIELD_CHOICES,
        label="Fields to apply",
    )
    review_note = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3, "id": "enrichment-apply-note"}),
    )

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        if event is not None:
            available = tuple(event.changes or {})
            self.fields["selected_fields"].choices = tuple(
                choice for choice in ENRICHMENT_FIELD_CHOICES if choice[0] in available
            )
        self.fields["selected_fields"].widget.attrs.update({"id": "enrichment-apply-fields"})


class PartyEnrichmentRejectForm(TenantActionForm):
    review_note = forms.CharField(
        label="Rejection reason",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3, "id": "enrichment-reject-note"}),
    )
