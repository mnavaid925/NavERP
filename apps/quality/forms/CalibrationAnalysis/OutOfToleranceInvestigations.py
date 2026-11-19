from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import CalibrationRecord
from apps.quality.models.CalibrationAnalysis.OutOfToleranceInvestigations import OutOfToleranceInvestigation
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.scm.models.Manufacturing.WorkCenters import WorkCenter

User = get_user_model()


class OutOfToleranceInvestigationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = OutOfToleranceInvestigation
        exclude = ("tenant", "number", "created_at", "updated_at")
        widgets = {
            "calibration_record": forms.Select(attrs={"class": "form-select"}),
            "gage": forms.Select(attrs={"class": "form-select"}),
            "discovery_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "risk_level": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 0-150mm Caliper OOT Deviation on Jaw Parallelism"}),
            "as_found_error_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "suspect_window_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "suspect_window_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "suspect_work_center": forms.Select(attrs={"class": "form-select"}),
            "suspect_production_orders": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "WO-00102, WO-00105, Batch #8812"}),
            "suspect_lots_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "products_affected": forms.TextInput(attrs={"class": "form-input", "placeholder": "Turbine Blade P/N 8841-A"}),
            "consumer_risk_rating": forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "5"}),
            "producer_risk_rating": forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "5"}),
            "containment_actions_taken": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "product_disposition": forms.Select(attrs={"class": "form-select"}),
            "customer_notification_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "product_recall_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "linked_ncr": forms.Select(attrs={"class": "form-select"}),
            "linked_capa": forms.Select(attrs={"class": "form-select"}),
            "investigator": forms.Select(attrs={"class": "form-select"}),
            "quality_approver": forms.Select(attrs={"class": "form-select"}),
            "closure_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "conclusion_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["calibration_record"].queryset = CalibrationRecord.objects.filter(tenant=self.tenant).select_related("gage")
            self.fields["gage"].queryset = CalibrationGage.objects.filter(tenant=self.tenant)
            self.fields["suspect_work_center"].queryset = WorkCenter.objects.filter(tenant=self.tenant)
            self.fields["linked_ncr"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant)
            self.fields["linked_capa"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)
            self.fields["investigator"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["quality_approver"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self, cleaned,
            ["calibration_record", "gage", "suspect_work_center", "linked_ncr", "linked_capa", "investigator", "quality_approver"]
        )
        cal_rec = cleaned.get("calibration_record")
        gage = cleaned.get("gage")
        if cal_rec and gage and cal_rec.gage_id != gage.pk:
            self.add_error("calibration_record", "Calibration record does not belong to the selected gage.")

        start = cleaned.get("suspect_window_start")
        end = cleaned.get("suspect_window_end")
        if start and end and start > end:
            self.add_error("suspect_window_start", "Suspect window start cannot be after end date.")
        return cleaned
