from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardWidgets import BiDashboardWidget
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure
from apps.bi.models.SemanticLayer.DrillHierarchies import DrillHierarchy
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class BiDashboardWidgetForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiDashboardWidget
        fields = [
            "dashboard",
            "title",
            "subtitle",
            "widget_type",
            "semantic_model",
            "calculated_measure",
            "warehouse_table",
            "drill_hierarchy",
            "aggregation_type",
            "pos_x",
            "pos_y",
            "width_cols",
            "height_rows",
            "refresh_interval_seconds",
            "drilldown_target_url",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Total Revenue (YTD)"}),
            "subtitle": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Compared to Previous Fiscal Year"}),
            "widget_type": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "calculated_measure": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "drill_hierarchy": forms.Select(attrs={"class": "form-select"}),
            "aggregation_type": forms.Select(attrs={"class": "form-select"}),
            "pos_x": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 11, "placeholder": "0-11"}),
            "pos_y": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100, "placeholder": "0-100"}),
            "width_cols": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 12, "placeholder": "1-12"}),
            "height_rows": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 12, "placeholder": "1-12"}),
            "refresh_interval_seconds": forms.NumberInput(attrs={"class": "form-input", "placeholder": "0 (inherits dashboard)"}),
            "drilldown_target_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. /bi/reports/revenue-breakdown/"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input", "placeholder": "10"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["semantic_model"].empty_label = "— None (No Semantic Model) —"
            self.fields["calculated_measure"].queryset = CalculatedMeasure.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["calculated_measure"].empty_label = "— None (No Calculated Measure) —"
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)
            self.fields["warehouse_table"].empty_label = "— None (No Warehouse Table) —"
            self.fields["drill_hierarchy"].queryset = DrillHierarchy.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["drill_hierarchy"].empty_label = "— None (No Drill Path) —"

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, [
            "dashboard", "semantic_model", "calculated_measure", "warehouse_table", "drill_hierarchy"
        ])
        return cleaned_data


class BiDashboardWidgetPositionForm(forms.Form):
    pos_x = forms.IntegerField(min_value=0, max_value=11)
    pos_y = forms.IntegerField(min_value=0, max_value=100)
    width_cols = forms.IntegerField(min_value=1, max_value=12)
    height_rows = forms.IntegerField(min_value=1, max_value=12)
