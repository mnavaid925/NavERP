from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.TraceabilitySerialization.BatchRecords import BatchRecord

User = get_user_model()


class BatchRecordForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BatchRecord
        fields = [
            "title",
            "batch_number",
            "product_code",
            "product_name",
            "status",
            "production_order_number",
            "work_order",
            "master_document",
            "planned_quantity",
            "actual_quantity",
            "unit_of_measure",
            "manufacturing_date",
            "expiration_date",
            "retest_date",
            "supervisor",
            "qa_reviewer",
            "electronic_signature",
            "linked_ncr",
            "linked_deviation",
            "linked_fqc",
            "checklist_passed",
            "is_quarantined",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "batch_number": forms.TextInput(attrs={"class": "form-input"}),
            "product_code": forms.TextInput(attrs={"class": "form-input"}),
            "product_name": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "production_order_number": forms.TextInput(attrs={"class": "form-input"}),
            "work_order": forms.Select(attrs={"class": "form-select"}),
            "master_document": forms.Select(attrs={"class": "form-select"}),
            "planned_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "actual_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input"}),
            "manufacturing_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "retest_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "supervisor": forms.Select(attrs={"class": "form-select"}),
            "qa_reviewer": forms.Select(attrs={"class": "form-select"}),
            "electronic_signature": forms.Select(attrs={"class": "form-select"}),
            "linked_ncr": forms.Select(attrs={"class": "form-select"}),
            "linked_deviation": forms.Select(attrs={"class": "form-select"}),
            "linked_fqc": forms.Select(attrs={"class": "form-select"}),
            "checklist_passed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_quarantined": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["supervisor"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["qa_reviewer"].queryset = User.objects.filter(tenant=self.tenant)

            WorkOrder = apps.get_model("scm", "WorkOrder")
            self.fields["work_order"].queryset = WorkOrder.objects.filter(tenant=self.tenant)

            ControlledDocument = apps.get_model("quality", "ControlledDocument")
            self.fields["master_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)

            ElectronicSignatureRecord = apps.get_model("quality", "ElectronicSignatureRecord")
            self.fields["electronic_signature"].queryset = ElectronicSignatureRecord.objects.filter(tenant=self.tenant)

            NonConformanceReport = apps.get_model("quality", "NonConformanceReport")
            self.fields["linked_ncr"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant)

            ProcessDeviation = apps.get_model("quality", "ProcessDeviation")
            self.fields["linked_deviation"].queryset = ProcessDeviation.objects.filter(tenant=self.tenant)

            FinalInspectionLot = apps.get_model("quality", "FinalInspectionLot")
            self.fields["linked_fqc"].queryset = FinalInspectionLot.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "supervisor",
                "qa_reviewer",
                "work_order",
                "master_document",
                "electronic_signature",
                "linked_ncr",
                "linked_deviation",
                "linked_fqc",
            ],
        )
        status = cleaned_data.get("status")
        if status == "released" and (not self.instance.pk or self.instance.status != "released"):
            self.add_error(
                "status",
                "Batch record cannot be transitioned to 'released' via edit form. Use the Release Batch workflow action.",
            )
        return cleaned_data
