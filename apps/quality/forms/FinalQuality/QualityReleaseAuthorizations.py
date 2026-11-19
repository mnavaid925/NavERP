from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.FinalQuality.QualityReleaseAuthorizations import QualityReleaseAuthorization

User = get_user_model()


class QualityReleaseAuthorizationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = QualityReleaseAuthorization
        fields = [
            "title",
            "status",
            "release_disposition",
            "customer",
            "destination_country",
            "destination_facility",
            "shipment_number",
            "shipment",
            "sales_order_number",
            "sales_order",
            "lot_number",
            "quantity_authorized",
            "inspection_lot",
            "certificate_of_conformance",
            "packaging_verification",
            "is_on_hold",
            "hold_reason",
            "final_inspection_passed",
            "no_open_ncrs_or_capas",
            "packaging_label_approved",
            "coc_issued_and_signed",
            "export_compliance_verified",
            "certificate_of_origin_attached",
            "shipping_container_security_seal",
            "carrier_name",
            "tracking_reference",
            "releasing_officer",
            "release_date",
            "concession_rationale",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "release_disposition": forms.Select(attrs={"class": "form-select"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "destination_country": forms.TextInput(attrs={"class": "form-input"}),
            "destination_facility": forms.TextInput(attrs={"class": "form-input"}),
            "shipment_number": forms.TextInput(attrs={"class": "form-input"}),
            "shipment": forms.Select(attrs={"class": "form-select"}),
            "sales_order_number": forms.TextInput(attrs={"class": "form-input"}),
            "sales_order": forms.Select(attrs={"class": "form-select"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "quantity_authorized": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "inspection_lot": forms.Select(attrs={"class": "form-select"}),
            "certificate_of_conformance": forms.Select(attrs={"class": "form-select"}),
            "packaging_verification": forms.Select(attrs={"class": "form-select"}),
            "is_on_hold": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "hold_reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "final_inspection_passed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "no_open_ncrs_or_capas": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "packaging_label_approved": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "coc_issued_and_signed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "export_compliance_verified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "certificate_of_origin_attached": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "shipping_container_security_seal": forms.TextInput(attrs={"class": "form-input"}),
            "carrier_name": forms.TextInput(attrs={"class": "form-input"}),
            "tracking_reference": forms.TextInput(attrs={"class": "form-input"}),
            "releasing_officer": forms.Select(attrs={"class": "form-select"}),
            "release_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "concession_rationale": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            try:
                Party = apps.get_model("core", "Party")
                self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            except LookupError:
                pass

            try:
                Shipment = apps.get_model("scm", "Shipment")
                self.fields["shipment"].queryset = Shipment.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                SalesOrder = apps.get_model("scm", "SalesOrder")
                self.fields["sales_order"].queryset = SalesOrder.objects.filter(tenant=self.tenant).select_related("customer").order_by("-created_at")
            except LookupError:
                pass

            try:
                FinalInspectionLot = apps.get_model("quality", "FinalInspectionLot")
                self.fields["inspection_lot"].queryset = FinalInspectionLot.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                CertificateOfConformance = apps.get_model("quality", "CertificateOfConformance")
                self.fields["certificate_of_conformance"].queryset = CertificateOfConformance.objects.filter(tenant=self.tenant).select_related("customer").order_by("-created_at")
            except LookupError:
                pass

            try:
                PackagingLabelVerification = apps.get_model("quality", "PackagingLabelVerification")
                self.fields["packaging_verification"].queryset = PackagingLabelVerification.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            users = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "email")
            self.fields["releasing_officer"].queryset = users

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, [
            "customer", "shipment", "sales_order", "inspection_lot",
            "certificate_of_conformance", "packaging_verification", "releasing_officer",
        ])

        is_on_hold = cleaned_data.get("is_on_hold")
        hold_reason = cleaned_data.get("hold_reason")
        status = cleaned_data.get("status")
        release_disposition = cleaned_data.get("release_disposition")

        if is_on_hold and not hold_reason:
            self.add_error("hold_reason", "A hold reason is mandatory when shipment release is on hold.")

        if is_on_hold and (status == "authorized" or release_disposition == "released_full"):
            self.add_error("status", "Cannot authorize or fully release a shipment while an active quality hold is engaged.")

        concession = cleaned_data.get("concession_rationale")
        if release_disposition == "conditional_release" and not concession:
            self.add_error("concession_rationale", "Concession rationale is mandatory for conditional release approvals.")

        customer = cleaned_data.get("customer")
        if customer:
            sales_order = cleaned_data.get("sales_order")
            if sales_order and getattr(sales_order, "customer_id", None) and sales_order.customer_id != customer.pk:
                self.add_error("sales_order", "Linked sales order does not belong to the selected customer.")
            inspection_lot = cleaned_data.get("inspection_lot")
            if inspection_lot and getattr(inspection_lot, "customer_id", None) and inspection_lot.customer_id != customer.pk:
                self.add_error("inspection_lot", "Linked inspection lot does not belong to the selected customer.")
            coc = cleaned_data.get("certificate_of_conformance")
            if coc and getattr(coc, "customer_id", None) and coc.customer_id != customer.pk:
                self.add_error("certificate_of_conformance", "Linked Certificate of Conformance does not belong to the selected customer.")

        return cleaned_data
