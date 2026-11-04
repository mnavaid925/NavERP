from django import forms

from apps.bi.forms._common import TenantUniqueMixin
from apps.bi.models.DataWarehouse.WarehouseStoragePolicies import WarehouseStoragePolicy
from apps.core.forms import TenantModelForm


class WarehouseStoragePolicyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = WarehouseStoragePolicy
        fields = [
            "name",
            "partition_strategy",
            "partition_key",
            "partition_granularity",
            "compression_codec",
            "enable_zone_maps",
            "hot_tier_days",
            "warm_tier_days",
            "cold_tier_days",
            "time_travel_days",
            "auto_purge_enabled",
            "vacuum_cadence",
            "is_default",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Financial Statutory 7-Year Retention"}),
            "partition_strategy": forms.Select(attrs={"class": "form-select"}),
            "partition_key": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. posting_date, created_at"}),
            "partition_granularity": forms.Select(attrs={"class": "form-select"}),
            "compression_codec": forms.Select(attrs={"class": "form-select"}),
            "enable_zone_maps": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "hot_tier_days": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "warm_tier_days": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "cold_tier_days": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "time_travel_days": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 90}),
            "auto_purge_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "vacuum_cadence": forms.Select(attrs={"class": "form-select"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Tiering objectives, statutory compliance notes, and storage SLAs..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        hot = cleaned_data.get("hot_tier_days")
        warm = cleaned_data.get("warm_tier_days")
        cold = cleaned_data.get("cold_tier_days")

        if hot and warm and hot > warm:
            self.add_error("warm_tier_days", "Warm tier threshold must be greater than or equal to Hot tier days.")
        if warm and cold and warm > cold:
            self.add_error("cold_tier_days", "Cold tier threshold must be greater than or equal to Warm tier days.")

        strategy = cleaned_data.get("partition_strategy")
        key = cleaned_data.get("partition_key")
        if strategy and strategy != "none" and not key:
            self.add_error("partition_key", "A partition key column must be specified when partition strategy is not None.")

        return cleaned_data
