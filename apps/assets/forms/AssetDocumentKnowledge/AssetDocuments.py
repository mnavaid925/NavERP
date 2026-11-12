"""Form for controlled Asset Document & Revision uploads and metadata (11.16)."""

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models.FixedAssets.FixedAssetsRegister import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.AssetDocumentKnowledge._helpers import (
    scope_tenant_querysets,
    validate_safe_doc_upload,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.models.AssetClassification.AssetSpecificationTemplates import (
    AssetSpecificationTemplate,
)
from apps.assets.models.AssetCompliance.AssetComplianceFrameworks import (
    AssetComplianceFramework,
)
from apps.assets.models.AssetDocumentKnowledge.AssetDocuments import AssetDocument
from apps.assets.models.AssetWarrantyInsurance.AssetWarranties import AssetWarranty
from apps.core.models.Document import Document
from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party
from apps.scm.models.AssetManagement.Assets import Asset

User = get_user_model()


class AssetDocumentForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for controlled Asset Documents [ADOC]."""

    _TENANT_FIELDS = {
        "supersedes": AssetDocument,
        "reviewer": User,
        "org_unit": OrgUnit,
        "operational_asset": Asset,
        "fixed_asset": FixedAsset,
        "asset_model": AssetModel,
        "asset_category": AssetCategory,
        "specification_template": AssetSpecificationTemplate,
        "warranty": AssetWarranty,
        "compliance_framework": AssetComplianceFramework,
        "vendor_party": Party,
        "core_document": Document,
    }

    class Meta:
        model = AssetDocument
        fields = [
            "title",
            "document_class",
            "access_classification",
            "tag_code",
            "manufacturer_ref",
            "document_language",
            "storage_location_ref",
            "file",
            "revision_label",
            "supersedes",
            "change_request_ref",
            "change_type",
            "redline_summary",
            "spec_delta_notes",
            "effective_date",
            "expiry_date",
            "retention_years",
            "reviewer",
            "review_notes",
            "description",
            "org_unit",
            "operational_asset",
            "fixed_asset",
            "asset_model",
            "asset_category",
            "specification_template",
            "warranty",
            "compliance_framework",
            "vendor_party",
            "core_document",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Chiller Plant #2 OEM Operation & Service Manual",
                }
            ),
            "tag_code": forms.TextInput(attrs={"placeholder": "e.g. P&ID-CHW-002"}),
            "manufacturer_ref": forms.TextInput(
                attrs={"placeholder": "e.g. Trane Model CVHF-770"}
            ),
            "document_language": forms.TextInput(attrs={"placeholder": "en"}),
            "storage_location_ref": forms.TextInput(
                attrs={"placeholder": "e.g. Vault Rack B-04 / DMS Folder 12"}
            ),
            "revision_label": forms.TextInput(attrs={"placeholder": "Rev A"}),
            "change_request_ref": forms.TextInput(
                attrs={"placeholder": "e.g. ECR-2026-014"}
            ),
            "retention_years": forms.NumberInput(attrs={"min": "1", "max": "100"}),
            "redline_summary": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Summarize field redlines or markup deltas...",
                }
            ),
            "spec_delta_notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Document changed operating thresholds, tolerances, or safety limits...",
                }
            ),
            "review_notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Engineering review notes or comments..."}
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Scope, applicable equipment, and controlled distribution notes...",
                }
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FIELDS)
        if "reviewer" in self.fields and self.tenant is not None:
            self.fields["reviewer"].queryset = self.fields["reviewer"].queryset.order_by(
                "username"
            )

    def clean_file(self):
        return validate_safe_doc_upload(self.cleaned_data.get("file"))

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, self._TENANT_FIELDS.keys())
        eff = cleaned.get("effective_date")
        exp = cleaned.get("expiry_date")
        if eff and exp and exp < eff:
            self.add_error(
                "expiry_date", "Expiry date cannot be earlier than the effective date."
            )
        retention = cleaned.get("retention_years")
        if retention is not None and retention < 1:
            self.add_error(
                "retention_years", "Retention period must be at least 1 year."
            )
        return cleaned
