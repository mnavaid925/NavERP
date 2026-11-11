from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    reject_foreign,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
)
from apps.assets.models.IntegrationApiHub.AssetTelemetryStreams import (
    AssetTelemetryStream,
)
from apps.scm.models import Asset

User = get_user_model()


class AssetTelemetryStreamForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for IoT/SCADA Asset Telemetry Streams."""

    class Meta:
        model = AssetTelemetryStream
        fields = [
            "connector",
            "operational_asset",
            "fixed_asset",
            "tag_address",
            "stream_name",
            "stream_protocol",
            "metric_type",
            "metric_unit",
            "ingestion_mode",
            "polling_interval_seconds",
            "deadband_delta",
            "scale_factor",
            "offset_value",
            "baseline_value",
            "warning_threshold",
            "critical_threshold",
            "auto_trigger_maintenance",
            "stream_status",
            "steward",
            "notes",
        ]
        widgets = {
            "connector": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "tag_address": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. ns=2;s=Line1.Pump01.BearingTemp or plant/line1/vibration",
                }
            ),
            "stream_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Chiller #2 Bearing Temperature Feed",
                }
            ),
            "stream_protocol": forms.Select(attrs={"class": "form-select"}),
            "metric_type": forms.Select(attrs={"class": "form-select"}),
            "metric_unit": forms.Select(attrs={"class": "form-select"}),
            "ingestion_mode": forms.Select(attrs={"class": "form-select"}),
            "polling_interval_seconds": forms.NumberInput(
                attrs={"class": "form-input", "min": 1}
            ),
            "deadband_delta": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.0001"}
            ),
            "scale_factor": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.000001"}
            ),
            "offset_value": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.0001"}
            ),
            "baseline_value": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.0001"}
            ),
            "warning_threshold": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.0001"}
            ),
            "critical_threshold": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.0001"}
            ),
            "auto_trigger_maintenance": forms.CheckboxInput(
                attrs={"class": "form-checkbox"}
            ),
            "stream_status": forms.Select(attrs={"class": "form-select"}),
            "steward": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Tag calibration instructions, PLC register mapping, escalation notes...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["connector"].queryset = (
                AssetIntegrationConnector.objects.filter(
                    tenant=self.tenant
                ).order_by("number")
            )
            self.fields["operational_asset"].queryset = Asset.objects.filter(
                tenant=self.tenant
            ).order_by("code")
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(
                tenant=self.tenant
            ).order_by("number")
            self.fields["steward"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

        for optional_field in (
            "operational_asset",
            "fixed_asset",
            "baseline_value",
            "warning_threshold",
            "critical_threshold",
            "steward",
            "notes",
        ):
            self.fields[optional_field].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["connector", "operational_asset", "fixed_asset", "steward"],
        )

        if not cleaned_data.get("operational_asset") and not cleaned_data.get(
            "fixed_asset"
        ):
            self.add_error(
                "operational_asset",
                "Link either an Operational Asset or a Financial Fixed Asset to ingest telemetry.",
            )

        polling = cleaned_data.get("polling_interval_seconds")
        if polling is not None and polling < 1:
            self.add_error(
                "polling_interval_seconds",
                "Polling interval must be at least 1 second.",
            )

        scale_factor = cleaned_data.get("scale_factor")
        if scale_factor is not None and scale_factor == Decimal("0"):
            self.add_error("scale_factor", "Scale factor cannot be zero.")

        deadband_delta = cleaned_data.get("deadband_delta")
        if deadband_delta is not None and deadband_delta < Decimal("0"):
            self.add_error("deadband_delta", "Deadband delta cannot be negative.")

        warn = cleaned_data.get("warning_threshold")
        crit = cleaned_data.get("critical_threshold")
        if warn is not None and crit is not None and crit < warn:
            self.add_error(
                "critical_threshold",
                "Critical threshold must be greater than or equal to warning threshold.",
            )

        return cleaned_data
