"""Form for Configuration Management Database (CMDB) Dependency Edges (11.18)."""

from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.ItAssetManagement._helpers import scope_tenant_querysets
from apps.assets.models.ItAssetManagement.CloudAssetSubscriptions import (
    CloudAssetSubscription,
)
from apps.assets.models.ItAssetManagement.CmdbRelationships import CmdbRelationship
from apps.assets.models.ItAssetManagement.ItHardwareAssets import ItHardwareAsset
from apps.assets.models.ItAssetManagement.SoftwareLicenses import SoftwareLicense
from apps.core.models.Monitoring import ServiceComponent
from apps.scm.models.AssetManagement.Assets import Asset as ScmAsset

User = get_user_model()


class CmdbRelationshipForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for CMDB Dependency Edges [CMDB]."""

    _TENANT_FIELDS = {
        "source_hardware": ItHardwareAsset,
        "source_software": SoftwareLicense,
        "source_cloud": CloudAssetSubscription,
        "source_service": ServiceComponent,
        "source_asset": ScmAsset,
        "target_hardware": ItHardwareAsset,
        "target_software": SoftwareLicense,
        "target_cloud": CloudAssetSubscription,
        "target_service": ServiceComponent,
        "target_asset": ScmAsset,
        "owner": User,
    }

    class Meta:
        model = CmdbRelationship
        fields = [
            "source_ci_type",
            "source_hardware",
            "source_software",
            "source_cloud",
            "source_service",
            "source_asset",
            "relationship_type",
            "target_ci_type",
            "target_hardware",
            "target_software",
            "target_cloud",
            "target_service",
            "target_asset",
            "environment",
            "criticality",
            "impact_severity",
            "is_single_point_of_failure",
            "owner",
            "blast_radius_notes",
        ]
        widgets = {
            "blast_radius_notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Describe upstream/downstream blast radius, failover runbook, or maintenance impact...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FIELDS)

    def _normalize_side(self, cleaned, prefix, ci_type):
        expected_suffix = CmdbRelationship.CI_FIELD_BY_TYPE.get(ci_type)
        for ci_key, suffix in CmdbRelationship.CI_FIELD_BY_TYPE.items():
            field_name = f"{prefix}_{suffix}"
            if ci_key != ci_type:
                cleaned[field_name] = None
                setattr(self.instance, field_name, None)
        if expected_suffix:
            selected_field = f"{prefix}_{expected_suffix}"
            if cleaned.get(selected_field) is None:
                self.add_error(
                    selected_field,
                    f"Select a {prefix} CI matching the chosen CI type.",
                )

    def clean(self):
        cleaned = super().clean()
        self._normalize_side(cleaned, "source", cleaned.get("source_ci_type"))
        self._normalize_side(cleaned, "target", cleaned.get("target_ci_type"))
        reject_foreign(self, cleaned, tuple(self._TENANT_FIELDS.keys()))
        return cleaned
