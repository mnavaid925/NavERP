import json
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataCatalog.CatalogAssets import CatalogAsset
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.models.SemanticLayer.BusinessGlossaryTerms import BusinessGlossaryTerm
from apps.bi.models.DataQuality.DataQualityScorecards import DataQualityScorecard
from apps.bi.models.MasterData.MdmGoldenRecords import MdmGoldenRecord
from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit


class CatalogAssetForm(TenantUniqueMixin, TenantModelForm):
    search_tags_raw = forms.CharField(
        required=False,
        label="Search Tags",
        help_text="Comma-separated tags (e.g. finance, arr, quarterly, audit)",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "finance, pii, revenue, quarterly"}),
    )

    class Meta:
        model = CatalogAsset
        fields = [
            "name",
            "code",
            "domain",
            "asset_type",
            "data_sensitivity",
            "enterprise_tier",
            "warehouse_table",
            "semantic_model",
            "golden_record",
            "business_glossary_term",
            "data_steward",
            "owning_org_unit",
            "quality_scorecard",
            "deprecation_replacement",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Enterprise Monthly Recurring Revenue Mart"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. dim_monthly_recurring_rev"}),
            "domain": forms.Select(attrs={"class": "form-select"}),
            "asset_type": forms.Select(attrs={"class": "form-select"}),
            "data_sensitivity": forms.Select(attrs={"class": "form-select"}),
            "enterprise_tier": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "golden_record": forms.Select(attrs={"class": "form-select"}),
            "business_glossary_term": forms.Select(attrs={"class": "form-select"}),
            "data_steward": forms.Select(attrs={"class": "form-select"}),
            "owning_org_unit": forms.Select(attrs={"class": "form-select"}),
            "quality_scorecard": forms.Select(attrs={"class": "form-select"}),
            "deprecation_replacement": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Detailed description of dataset grain, update cadence, and business context"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "code" in self.fields:
            self.fields["code"].required = False
        if self.instance and self.instance.pk and self.instance.search_tags_json:
            self.fields["search_tags_raw"].initial = ", ".join(self.instance.search_tags_json)

        if self.tenant is not None:
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["golden_record"].queryset = MdmGoldenRecord.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["business_glossary_term"].queryset = BusinessGlossaryTerm.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["owning_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["quality_scorecard"].queryset = DataQualityScorecard.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["data_steward"].queryset = get_user_model().objects.filter(tenant=self.tenant).order_by("first_name", "username")
            
            replacement_qs = CatalogAsset.objects.filter(tenant=self.tenant)
            if self.instance and self.instance.pk:
                replacement_qs = replacement_qs.exclude(pk=self.instance.pk)
            self.fields["deprecation_replacement"].queryset = replacement_qs.order_by("name")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "warehouse_table",
                "semantic_model",
                "golden_record",
                "business_glossary_term",
                "data_steward",
                "owning_org_unit",
                "quality_scorecard",
                "deprecation_replacement",
            ],
        )

        name = cleaned.get("name")
        code = cleaned.get("code")
        if name and not code:
            base_slug = slugify(name).replace("-", "_")[:80]
            cleaned["code"] = base_slug
            self.instance.code = base_slug

        tags_raw = cleaned.get("search_tags_raw", "")
        if tags_raw:
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            self.instance.search_tags_json = tags
        else:
            self.instance.search_tags_json = []

        return cleaned


class CatalogAssetCertifyForm(forms.Form):
    certification_status = forms.ChoiceField(
        choices=[
            ("certified", "Certified Production-Ready"),
            ("endorsed", "Peer Endorsed"),
            ("under_review", "Under Stewardship Review"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Certification Decision",
    )
    certification_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Steward certification attestation notes"}),
        label="Steward Notes",
    )


class CatalogAssetDeprecateForm(forms.Form):
    deprecation_replacement = forms.ModelChoiceField(
        queryset=CatalogAsset.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Recommended Replacement Asset",
        help_text="Direct users and report creators to this successor asset.",
    )
    deprecation_reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Reason for deprecation and retirement timeline"}),
        label="Deprecation Rationale",
    )

    def __init__(self, *args, tenant=None, current_asset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            qs = CatalogAsset.objects.filter(tenant=tenant)
            if current_asset:
                qs = qs.exclude(pk=current_asset.pk)
            self.fields["deprecation_replacement"].queryset = qs.order_by("name")
