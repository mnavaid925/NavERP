from decimal import Decimal

from django import forms

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetRisk.AssetCyberSecurityProfiles import AssetCyberSecurityProfile
from apps.scm.models import Asset


class AssetCyberSecurityProfileForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetCyberSecurityProfile
        fields = [
            "asset",
            "device_type",
            "ip_address",
            "mac_address",
            "network_zone",
            "firmware_version",
            "latest_available_firmware",
            "firmware_update_status",
            "protocol_used",
            "exposure_level",
            "known_vulnerabilities_cve",
            "cve_risk_score",
            "compensating_controls",
            "last_vulnerability_scan_date",
            "security_posture_status",
            "patch_freeze_until",
        ]
        widgets = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "device_type": forms.Select(attrs={"class": "form-select"}),
            "ip_address": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. 192.168.10.45"}
            ),
            "mac_address": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. 00:1B:44:11:3A:B7"}
            ),
            "network_zone": forms.Select(attrs={"class": "form-select"}),
            "firmware_version": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. v2.9.4"}
            ),
            "latest_available_firmware": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. v3.1.0"}
            ),
            "firmware_update_status": forms.Select(attrs={"class": "form-select"}),
            "protocol_used": forms.Select(attrs={"class": "form-select"}),
            "exposure_level": forms.Select(attrs={"class": "form-select"}),
            "known_vulnerabilities_cve": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "e.g. CVE-2026-1192: Unauthenticated Modbus buffer overflow..."}
            ),
            "cve_risk_score": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.1", "min": "0", "max": "10", "placeholder": "0.0 to 10.0"}
            ),
            "compensating_controls": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "e.g. In-line industrial deep-packet inspection firewall; read-only physical key switch enabled"}
            ),
            "last_vulnerability_scan_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "security_posture_status": forms.Select(attrs={"class": "form-select"}),
            "patch_freeze_until": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)

    def clean_cve_risk_score(self):
        score = self.cleaned_data.get("cve_risk_score")
        if score is not None:
            if score < Decimal("0.0") or score > Decimal("10.0"):
                raise forms.ValidationError("CVSS CVE risk score must be between 0.0 and 10.0.")
        return score

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["asset"])
        return cleaned
