from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataCatalog.CatalogAssets import CatalogAsset
from apps.bi.models.DataCatalog.CatalogLineageEdges import CatalogLineageEdge
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.models.EtlPipelines.TransformationSteps import TransformationStep
from apps.core.forms import TenantModelForm


class CatalogLineageEdgeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CatalogLineageEdge
        fields = [
            "upstream_asset",
            "downstream_asset",
            "lineage_type",
            "upstream_column",
            "downstream_column",
            "impact_criticality",
            "transformation_rule",
            "etl_pipeline",
            "transformation_step",
            "is_automated_extraction",
            "notes",
            "is_active",
        ]
        widgets = {
            "upstream_asset": forms.Select(attrs={"class": "form-select"}),
            "downstream_asset": forms.Select(attrs={"class": "form-select"}),
            "lineage_type": forms.Select(attrs={"class": "form-select"}),
            "upstream_column": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. customer_id, order_total"}),
            "downstream_column": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. client_key, net_sales_amt"}),
            "impact_criticality": forms.Select(attrs={"class": "form-select"}),
            "transformation_rule": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": "SQL expression, e.g. SUM(line_total * (1 - discount_pct))"}),
            "etl_pipeline": forms.Select(attrs={"class": "form-select"}),
            "transformation_step": forms.Select(attrs={"class": "form-select"}),
            "is_automated_extraction": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Lineage notes and lineage impact assessment"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            asset_qs = CatalogAsset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["upstream_asset"].queryset = asset_qs
            self.fields["downstream_asset"].queryset = asset_qs
            self.fields["etl_pipeline"].queryset = EtlPipeline.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["transformation_step"].queryset = TransformationStep.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["upstream_asset", "downstream_asset", "etl_pipeline", "transformation_step"],
        )
        upstream = cleaned.get("upstream_asset")
        downstream = cleaned.get("downstream_asset")
        if upstream and downstream and upstream == downstream:
            raise ValidationError("Upstream and Downstream assets cannot be identical in a directional lineage edge.")
        return cleaned
