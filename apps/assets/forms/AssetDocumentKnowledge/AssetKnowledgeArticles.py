"""Form for Asset Knowledge Base, Lessons Learned & Failure RCA Articles (11.16)."""

from decimal import Decimal

from django import forms

from apps.accounting.models.FixedAssets.FixedAssetsRegister import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.AssetDocumentKnowledge._helpers import (
    normalize_json_dict_value,
    normalize_json_list_value,
    scope_tenant_querysets,
    validate_safe_doc_upload,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.models.AssetCompliance.AssetComplianceIncidents import (
    AssetComplianceIncident,
)
from apps.assets.models.AssetDocumentKnowledge.AssetDocuments import AssetDocument
from apps.assets.models.AssetDocumentKnowledge.AssetKnowledgeArticles import (
    AssetKnowledgeArticle,
)
from apps.assets.models.AssetDocumentKnowledge.AssetOperatingProcedures import (
    AssetOperatingProcedure,
)
from apps.assets.models.AssetInventoryTracking.AssetIncidentReports import (
    AssetIncidentReport,
)
from apps.assets.models.AssetMaintenance.AssetMaintenanceLogs import AssetMaintenanceLog
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import (
    AssetMaintenanceRequest,
)
from apps.assets.models.AssetReliability.AssetFailureModes import AssetFailureMode
from apps.core.models.OrgUnit import OrgUnit
from apps.scm.models.AssetManagement.Assets import Asset


class AssetKnowledgeArticleForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Asset Knowledge & RCA Articles [AKBA]."""

    _TENANT_FIELDS = {
        "org_unit": OrgUnit,
        "operational_asset": Asset,
        "fixed_asset": FixedAsset,
        "asset_category": AssetCategory,
        "asset_model": AssetModel,
        "failure_mode": AssetFailureMode,
        "maintenance_request": AssetMaintenanceRequest,
        "maintenance_log": AssetMaintenanceLog,
        "incident_report": AssetIncidentReport,
        "compliance_incident": AssetComplianceIncident,
        "related_document": AssetDocument,
        "recommended_procedure": AssetOperatingProcedure,
    }

    class Meta:
        model = AssetKnowledgeArticle
        fields = [
            "title",
            "article_type",
            "rca_methodology",
            "severity",
            "symptom_problem",
            "root_cause_summary",
            "five_whys",
            "contributing_factors",
            "remedy_corrective_action",
            "preventive_lessons",
            "downtime_hours_impacted",
            "recurrence_count",
            "tags",
            "attachment",
            "incident_occurred_on",
            "org_unit",
            "operational_asset",
            "fixed_asset",
            "asset_category",
            "asset_model",
            "failure_mode",
            "maintenance_request",
            "maintenance_log",
            "incident_report",
            "compliance_incident",
            "related_document",
            "recommended_procedure",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Chiller Compressor Bearing Spalling — 5-Why & Lubrication Fix",
                }
            ),
            "symptom_problem": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Observable alarms, vibration spikes, leak indicators, or failure symptoms...",
                }
            ),
            "root_cause_summary": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Confirmed physical, procedural, or design root cause...",
                }
            ),
            "five_whys": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-textarea font-mono text-xs",
                    "placeholder": '[{"why_level":1,"question":"Why did the bearing overheat?","answer":"Insufficient oil flow"}]',
                }
            ),
            "contributing_factors": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-textarea font-mono text-xs",
                    "placeholder": '{"machine":"Misaligned coupling","method":"Missed 90-day alignment check","material":"Contaminated oil"}',
                }
            ),
            "remedy_corrective_action": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Immediate repair steps, OEM parts replaced, and verification test...",
                }
            ),
            "preventive_lessons": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Updated PM intervals, SOP revisions, or operator training takeaways...",
                }
            ),
            "downtime_hours_impacted": forms.NumberInput(
                attrs={"min": "0", "step": "0.25"}
            ),
            "recurrence_count": forms.NumberInput(attrs={"min": "1"}),
            "tags": forms.TextInput(
                attrs={"placeholder": "e.g. chiller, bearing, cavitation, loto"}
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FIELDS)

    def clean_attachment(self):
        return validate_safe_doc_upload(self.cleaned_data.get("attachment"))

    def clean_five_whys(self):
        return normalize_json_list_value(self.cleaned_data.get("five_whys"))

    def clean_contributing_factors(self):
        return normalize_json_dict_value(
            self.cleaned_data.get("contributing_factors")
        )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, self._TENANT_FIELDS.keys())
        dt_hours = cleaned.get("downtime_hours_impacted")
        if dt_hours is not None and dt_hours < Decimal("0.00"):
            self.add_error(
                "downtime_hours_impacted", "Downtime hours impacted cannot be negative."
            )
        rec = cleaned.get("recurrence_count")
        if rec is not None and rec < 1:
            self.add_error("recurrence_count", "Recurrence count must be at least 1.")
        return cleaned
