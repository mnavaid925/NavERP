"""Form for Controlled Standard Operating Procedures & LOTO Protocols (11.16)."""

from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.AssetDocumentKnowledge._helpers import (
    normalize_json_list_value,
    scope_tenant_querysets,
    validate_safe_doc_upload,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.models.AssetCompliance.AssetComplianceFrameworks import (
    AssetComplianceFramework,
)
from apps.assets.models.AssetDocumentKnowledge._validators import (
    readable_asset_document_q,
)
from apps.assets.models.AssetDocumentKnowledge.AssetDocuments import AssetDocument
from apps.assets.models.AssetDocumentKnowledge.AssetOperatingProcedures import (
    AssetOperatingProcedure,
)
from apps.assets.models.AssetMaintenance.AssetMaintenanceSchedules import (
    AssetMaintenanceSchedule,
)
from apps.core.models.OrgUnit import OrgUnit
from apps.scm.models.AssetManagement.Assets import Asset

User = get_user_model()


class AssetOperatingProcedureForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Controlled Asset Operating Procedures [ASOP]."""

    _TENANT_FIELDS = {
        "supersedes": AssetOperatingProcedure,
        "safety_reviewer": User,
        "org_unit": OrgUnit,
        "operational_asset": Asset,
        "asset_category": AssetCategory,
        "asset_model": AssetModel,
        "maintenance_schedule": AssetMaintenanceSchedule,
        "compliance_framework": AssetComplianceFramework,
        "primary_document": AssetDocument,
    }

    class Meta:
        model = AssetOperatingProcedure
        fields = [
            "title",
            "procedure_type",
            "safety_level",
            "revision_label",
            "supersedes",
            "purpose_scope",
            "hazard_warnings",
            "required_ppe",
            "loto_required",
            "loto_isolation_points",
            "procedure_steps",
            "required_qualification_code",
            "estimated_duration_minutes",
            "attachment",
            "effective_date",
            "review_cycle_months",
            "next_review_date",
            "safety_reviewer",
            "review_notes",
            "org_unit",
            "operational_asset",
            "asset_category",
            "asset_model",
            "maintenance_schedule",
            "compliance_framework",
            "primary_document",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Chiller Plant #2 LOTO Electrical & Ammonia Isolation SOP",
                }
            ),
            "revision_label": forms.TextInput(attrs={"placeholder": "Rev 1.0"}),
            "required_ppe": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Arc-flash visor, insulated gloves Class 0, lockable hasp",
                }
            ),
            "required_qualification_code": forms.TextInput(
                attrs={"placeholder": "e.g. QUAL-LOTO-HV"}
            ),
            "estimated_duration_minutes": forms.NumberInput(
                attrs={"min": "1", "max": "1440"}
            ),
            "review_cycle_months": forms.NumberInput(attrs={"min": "1", "max": "120"}),
            "purpose_scope": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Operational scope, pre-conditions, and crew responsibilities...",
                }
            ),
            "hazard_warnings": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Stored energy, pressure, arc-flash, chemical, or thermal warnings...",
                }
            ),
            "loto_isolation_points": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-textarea font-mono text-xs",
                    "placeholder": '[{"energy_source":"Electrical 480V","tag_id":"MCC-3B","isolation_point":"Main Breaker","lock_device":"Red padlock + tag","verification_step":"Zero-voltage test"}]',
                }
            ),
            "procedure_steps": forms.Textarea(
                attrs={
                    "rows": 5,
                    "class": "form-textarea font-mono text-xs",
                    "placeholder": '[{"step_no":1,"title":"Pre-check","instruction":"Verify system standby","expected_reading":"0 PSI","is_mandatory_signoff":true}]',
                }
            ),
            "review_notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "EHS / safety committee review remarks..."}
            ),
        }

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        self.user = user
        super().__init__(*args, tenant=tenant, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FIELDS)
        if "primary_document" in self.fields and self.tenant is not None:
            self.fields["primary_document"].queryset = self.fields[
                "primary_document"
            ].queryset.filter(readable_asset_document_q(self.user))
        if "safety_reviewer" in self.fields and self.tenant is not None:
            self.fields["safety_reviewer"].queryset = self.fields[
                "safety_reviewer"
            ].queryset.order_by("username")

    def clean_attachment(self):
        return validate_safe_doc_upload(self.cleaned_data.get("attachment"))

    def clean_loto_isolation_points(self):
        return normalize_json_list_value(self.cleaned_data.get("loto_isolation_points"))

    def clean_procedure_steps(self):
        return normalize_json_list_value(self.cleaned_data.get("procedure_steps"))

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, self._TENANT_FIELDS.keys())
        eff = cleaned.get("effective_date")
        nxt = cleaned.get("next_review_date")
        if eff and nxt and nxt < eff:
            self.add_error(
                "next_review_date",
                "Next review date cannot precede the effective date.",
            )
        return cleaned
