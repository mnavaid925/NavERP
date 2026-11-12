"""Form for Asset Operator Training, Competency & Certification Records (11.16)."""

from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.AssetDocumentKnowledge._helpers import (
    scope_tenant_querysets,
    validate_safe_doc_upload,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.models.AssetCompliance.AssetComplianceFrameworks import (
    AssetComplianceFramework,
)
from apps.assets.models.AssetDocumentKnowledge.AssetOperatingProcedures import (
    AssetOperatingProcedure,
)
from apps.assets.models.AssetDocumentKnowledge.AssetOperatorCertifications import (
    AssetOperatorCertification,
)
from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.hrm.models.TrainingAdministration.Trainingcertificate import TrainingCertificate
from apps.scm.models.AssetManagement.Assets import Asset

User = get_user_model()


class AssetOperatorCertificationForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Asset Operator Certifications [AOCT]."""

    _TENANT_FIELDS = {
        "org_unit": OrgUnit,
        "operator_party": Party,
        "operator_user": User,
        "employee_profile": EmployeeProfile,
        "hrm_certificate": TrainingCertificate,
        "issuing_party": Party,
        "assessor": User,
        "operational_asset": Asset,
        "asset_category": AssetCategory,
        "asset_model": AssetModel,
        "operating_procedure": AssetOperatingProcedure,
        "compliance_framework": AssetComplianceFramework,
    }

    class Meta:
        model = AssetOperatorCertification
        fields = [
            "title",
            "qualification_code",
            "qualification_type",
            "proficiency_level",
            "org_unit",
            "operator_party",
            "operator_user",
            "employee_profile",
            "hrm_certificate",
            "issuing_authority",
            "issuing_party",
            "certificate_reference",
            "certificate_file",
            "operational_asset",
            "asset_category",
            "asset_model",
            "operating_procedure",
            "compliance_framework",
            "issued_date",
            "expires_on",
            "renewal_lead_days",
            "last_assessed_date",
            "assessor",
            "training_hours",
            "assessment_score",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "e.g. LOTO Authorized Technician — Chiller Plant High-Voltage",
                }
            ),
            "qualification_code": forms.TextInput(
                attrs={"placeholder": "e.g. QUAL-LOTO-HV"}
            ),
            "issuing_authority": forms.TextInput(
                attrs={"placeholder": "e.g. OSHA Training Institute / OEM Academy"}
            ),
            "certificate_reference": forms.TextInput(
                attrs={"placeholder": "e.g. CERT-2026-88412"}
            ),
            "renewal_lead_days": forms.NumberInput(attrs={"min": "1", "max": "365"}),
            "training_hours": forms.NumberInput(attrs={"min": "0", "step": "0.5"}),
            "assessment_score": forms.NumberInput(
                attrs={"min": "0", "max": "100", "step": "0.1"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Practical sign-off remarks, restrictions, or supervised hour requirements...",
                }
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FIELDS)
        if self.tenant is not None:
            for user_field in ("operator_user", "assessor"):
                if user_field in self.fields:
                    self.fields[user_field].queryset = self.fields[
                        user_field
                    ].queryset.order_by("username")

    def clean_certificate_file(self):
        return validate_safe_doc_upload(self.cleaned_data.get("certificate_file"))

    def clean(self):
        cleaned = super().clean()
        for field_name in self._TENANT_FIELDS:
            reject_foreign(self, cleaned, self.tenant, field_name)
        if not (
            cleaned.get("operator_party")
            or cleaned.get("operator_user")
            or cleaned.get("employee_profile")
        ):
            self.add_error(
                None,
                "Select at least one operator reference (Operator Party, User, or Employee Profile).",
            )
        issued = cleaned.get("issued_date")
        expires = cleaned.get("expires_on")
        if issued and expires and expires < issued:
            self.add_error(
                "expires_on", "Expiry date cannot precede the issued date."
            )
        hours = cleaned.get("training_hours")
        if hours is not None and hours < Decimal("0.00"):
            self.add_error("training_hours", "Training hours cannot be negative.")
        score = cleaned.get("assessment_score")
        if score is not None and (score < Decimal("0.00") or score > Decimal("100.00")):
            self.add_error(
                "assessment_score", "Assessment score must be between 0 and 100."
            )
        lead = cleaned.get("renewal_lead_days")
        if lead is not None and lead < 1:
            self.add_error(
                "renewal_lead_days", "Renewal lead days must be at least 1."
            )
        return cleaned
