import json
from decimal import Decimal

from django import forms
from django.db.models import Q

from apps.accounting.models import Currency, FiscalPeriod, FixedAsset, GLAccount
from apps.assets.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    reject_foreign,
)
from apps.assets.models.AssetDepreciation.AssetDepreciationSchedules import (
    AssetDepreciationSchedule,
)
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import (
    AssetMaintenanceRequest,
)
from apps.assets.models.AssetProcurement.AssetCapitalizations import (
    AssetCapitalization,
)
from apps.assets.models.IntegrationApiHub.AssetGlSyncBatches import (
    AssetGlSyncBatch,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
)
from apps.core.models import OrgUnit
from apps.scm.models import PurchaseOrder


class AssetGlSyncBatchForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Asset GL Sync Batches with cross-tenant FK and JSON validation."""

    class Meta:
        model = AssetGlSyncBatch
        fields = [
            "connector",
            "sync_domain",
            "sync_direction",
            "external_batch_ref",
            "fiscal_period",
            "gl_account",
            "offset_gl_account",
            "fixed_asset",
            "purchase_order",
            "capitalization",
            "depreciation_schedule",
            "maintenance_request",
            "cost_center",
            "currency",
            "batch_date",
            "source_amount",
            "target_gl_amount",
            "field_mapping_json",
            "payload_summary",
            "notes",
        ]
        widgets = {
            "connector": forms.Select(attrs={"class": "form-select"}),
            "sync_domain": forms.Select(attrs={"class": "form-select"}),
            "sync_direction": forms.Select(attrs={"class": "form-select"}),
            "external_batch_ref": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. SAP-BELNR-2026-00412 or NS-JE-882",
                }
            ),
            "fiscal_period": forms.Select(attrs={"class": "form-select"}),
            "gl_account": forms.Select(attrs={"class": "form-select"}),
            "offset_gl_account": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "purchase_order": forms.Select(attrs={"class": "form-select"}),
            "capitalization": forms.Select(attrs={"class": "form-select"}),
            "depreciation_schedule": forms.Select(attrs={"class": "form-select"}),
            "maintenance_request": forms.Select(attrs={"class": "form-select"}),
            "cost_center": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "batch_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "source_amount": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "target_gl_amount": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "field_mapping_json": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-xs",
                    "rows": 3,
                    "placeholder": '{"asset_class": "ANLKL", "cost_center": "KOSTL"}',
                }
            ),
            "payload_summary": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "Summary of subledger lines mapped in this batch...",
                }
            ),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["connector"].queryset = (
                AssetIntegrationConnector.objects.filter(
                    tenant=self.tenant
                ).order_by("number")
            )
            self.fields["fiscal_period"].queryset = FiscalPeriod.objects.filter(
                tenant=self.tenant
            ).order_by("-start_date")

            gl_q = Q(is_active=True)
            if self.instance and self.instance.gl_account_id:
                gl_q = gl_q | Q(pk=self.instance.gl_account_id)
            self.fields["gl_account"].queryset = GLAccount.objects.filter(
                gl_q, tenant=self.tenant
            ).order_by("code")

            off_q = Q(is_active=True)
            if self.instance and self.instance.offset_gl_account_id:
                off_q = off_q | Q(pk=self.instance.offset_gl_account_id)
            self.fields["offset_gl_account"].queryset = GLAccount.objects.filter(
                off_q, tenant=self.tenant
            ).order_by("code")

            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(
                tenant=self.tenant
            ).order_by("number")
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.filter(
                tenant=self.tenant
            ).order_by("-order_date", "-number")
            self.fields["capitalization"].queryset = AssetCapitalization.objects.filter(
                tenant=self.tenant
            ).order_by("-number")
            self.fields["depreciation_schedule"].queryset = (
                AssetDepreciationSchedule.objects.filter(
                    tenant=self.tenant
                ).order_by("-schedule_date", "-number")
            )
            self.fields["maintenance_request"].queryset = (
                AssetMaintenanceRequest.objects.filter(
                    tenant=self.tenant
                ).order_by("-number")
            )
            self.fields["cost_center"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")

        if self.instance and self.instance.currency_id:
            self.fields["currency"].queryset = Currency.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.currency_id)
            ).order_by("code")
        else:
            self.fields["currency"].queryset = Currency.objects.filter(
                is_active=True
            ).order_by("code")

        for optional_field in (
            "external_batch_ref",
            "fiscal_period",
            "gl_account",
            "offset_gl_account",
            "fixed_asset",
            "purchase_order",
            "capitalization",
            "depreciation_schedule",
            "maintenance_request",
            "cost_center",
            "currency",
            "field_mapping_json",
            "payload_summary",
            "notes",
        ):
            self.fields[optional_field].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "connector",
                "fiscal_period",
                "gl_account",
                "offset_gl_account",
                "fixed_asset",
                "purchase_order",
                "capitalization",
                "depreciation_schedule",
                "maintenance_request",
                "cost_center",
            ],
        )

        src = cleaned_data.get("source_amount")
        tgt = cleaned_data.get("target_gl_amount")
        if src is not None and src < Decimal("0.00"):
            self.add_error("source_amount", "Source amount cannot be negative.")
        if tgt is not None and tgt < Decimal("0.00"):
            self.add_error("target_gl_amount", "Target GL amount cannot be negative.")

        gl_acc = cleaned_data.get("gl_account")
        off_acc = cleaned_data.get("offset_gl_account")
        if gl_acc is not None and off_acc is not None and gl_acc.pk == off_acc.pk:
            self.add_error(
                "offset_gl_account",
                "Offset GL account must differ from primary GL account.",
            )

        raw_json = (cleaned_data.get("field_mapping_json") or "").strip()
        if raw_json:
            try:
                parsed = json.loads(raw_json)
            except ValueError:
                self.add_error(
                    "field_mapping_json", "Field mapping must be valid JSON syntax."
                )
            else:
                if not isinstance(parsed, dict):
                    self.add_error(
                        "field_mapping_json",
                        "Field mapping must be a JSON object ({...}).",
                    )

        return cleaned_data
