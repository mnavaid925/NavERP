from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.FinalQuality.PackagingLabelVerifications import PackagingLabelVerification

User = get_user_model()


class PackagingLabelVerificationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PackagingLabelVerification
        fields = [
            "title",
            "status",
            "disposition",
            "item_code",
            "item_name",
            "lot_number",
            "carton_count_inspected",
            "label_part_number",
            "label_artwork_revision",
            "artwork_master",
            "barcode_symbology",
            "scanned_barcode_data",
            "iso_iec_print_grade",
            "label_content_accurate",
            "regulatory_symbols_present",
            "serialization_verified",
            "carton_integrity_intact",
            "tamper_evident_seal_intact",
            "cushioning_dunnage_adequate",
            "pallet_stacking_compliant",
            "inspection_lot",
            "shipment",
            "verifier",
            "verified_date",
            "discrepancy_details",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "disposition": forms.Select(attrs={"class": "form-select"}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "item_name": forms.TextInput(attrs={"class": "form-input"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "carton_count_inspected": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "label_part_number": forms.TextInput(attrs={"class": "form-input"}),
            "label_artwork_revision": forms.TextInput(attrs={"class": "form-input"}),
            "artwork_master": forms.Select(attrs={"class": "form-select"}),
            "barcode_symbology": forms.Select(attrs={"class": "form-select"}),
            "scanned_barcode_data": forms.TextInput(attrs={"class": "form-input", "placeholder": "Scan or paste barcode string"}),
            "iso_iec_print_grade": forms.Select(attrs={"class": "form-select"}),
            "label_content_accurate": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "regulatory_symbols_present": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "serialization_verified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "carton_integrity_intact": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "tamper_evident_seal_intact": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "cushioning_dunnage_adequate": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "pallet_stacking_compliant": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "inspection_lot": forms.Select(attrs={"class": "form-select"}),
            "shipment": forms.Select(attrs={"class": "form-select"}),
            "verifier": forms.Select(attrs={"class": "form-select"}),
            "verified_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "discrepancy_details": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            try:
                ControlledDocument = apps.get_model("quality", "ControlledDocument")
                self.fields["artwork_master"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            except LookupError:
                pass

            try:
                FinalInspectionLot = apps.get_model("quality", "FinalInspectionLot")
                self.fields["inspection_lot"].queryset = FinalInspectionLot.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                Shipment = apps.get_model("scm", "Shipment")
                self.fields["shipment"].queryset = Shipment.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            users = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "email")
            self.fields["verifier"].queryset = users

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, [
            "artwork_master", "inspection_lot", "shipment", "verifier"
        ])

        disposition = cleaned_data.get("disposition")
        discrepancy = cleaned_data.get("discrepancy_details")
        if disposition in ("relabel_required", "repack_required", "reject_quarantine") and not discrepancy:
            self.add_error("discrepancy_details", "Discrepancy details are required when relabeling, repacking, or quarantining.")

        return cleaned_data
