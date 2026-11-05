from django import forms
from django.contrib.auth import get_user_model

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataCatalog.CatalogAssets import CatalogAsset
from apps.bi.models.DataCatalog.CatalogTrustEndorsements import CatalogTrustEndorsement
from apps.core.forms import TenantModelForm


class CatalogTrustEndorsementForm(TenantUniqueMixin, TenantModelForm):
    check_schema_documented = forms.BooleanField(
        required=False,
        label="Schema Documented",
        help_text="Dataset columns, types, and descriptions verified",
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )
    check_quality_sla_passed = forms.BooleanField(
        required=False,
        label="Quality SLA Passed",
        help_text="Data quality profile & scorecards meet enterprise threshold",
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )
    check_ownership_verified = forms.BooleanField(
        required=False,
        label="Stewardship & Ownership Verified",
        help_text="Data steward and owning org unit formally confirmed",
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )
    check_lineage_complete = forms.BooleanField(
        required=False,
        label="Lineage Traceability Complete",
        help_text="Source-to-target dependencies documented without breaks",
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )

    class Meta:
        model = CatalogTrustEndorsement
        fields = [
            "asset",
            "endorsement_type",
            "verdict",
            "rating_value",
            "attested_by",
            "valid_until",
            "review_comments",
            "is_active",
        ]
        widgets = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "endorsement_type": forms.Select(attrs={"class": "form-select"}),
            "verdict": forms.Select(attrs={"class": "form-select"}),
            "rating_value": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 5, "placeholder": "5"}),
            "attested_by": forms.Select(attrs={"class": "form-select"}),
            "valid_until": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "review_comments": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Detailed evaluation remarks and verification notes"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.criteria_checklist_json:
            chk = self.instance.criteria_checklist_json
            self.fields["check_schema_documented"].initial = chk.get("schema_documented", False)
            self.fields["check_quality_sla_passed"].initial = chk.get("quality_sla_passed", False)
            self.fields["check_ownership_verified"].initial = chk.get("ownership_verified", False)
            self.fields["check_lineage_complete"].initial = chk.get("lineage_complete", False)

        if self.tenant is not None:
            self.fields["asset"].queryset = CatalogAsset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["attested_by"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant).order_by("first_name", "username")
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["asset", "attested_by"])

        self.instance.criteria_checklist_json = {
            "schema_documented": bool(cleaned.get("check_schema_documented")),
            "quality_sla_passed": bool(cleaned.get("check_quality_sla_passed")),
            "ownership_verified": bool(cleaned.get("check_ownership_verified")),
            "lineage_complete": bool(cleaned.get("check_lineage_complete")),
        }
        return cleaned
