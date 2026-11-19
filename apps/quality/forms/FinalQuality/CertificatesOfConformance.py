from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.FinalQuality.CertificatesOfConformance import CertificateOfConformance

User = get_user_model()


class CertificateOfConformanceForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CertificateOfConformance
        fields = [
            "title",
            "certificate_type",
            "customer",
            "customer_po_number",
            "sales_order_number",
            "sales_order",
            "shipment_number",
            "shipment",
            "item_code",
            "item_name",
            "revision",
            "lot_number",
            "batch_number",
            "serial_numbers_text",
            "certified_quantity",
            "inspection_lot",
            "applicable_specifications",
            "test_results_summary",
            "conformance_statement",
            "signatory_title",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "certificate_type": forms.Select(attrs={"class": "form-select"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "customer_po_number": forms.TextInput(attrs={"class": "form-input"}),
            "sales_order_number": forms.TextInput(attrs={"class": "form-input"}),
            "sales_order": forms.Select(attrs={"class": "form-select"}),
            "shipment_number": forms.TextInput(attrs={"class": "form-input"}),
            "shipment": forms.Select(attrs={"class": "form-select"}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "item_name": forms.TextInput(attrs={"class": "form-input"}),
            "revision": forms.TextInput(attrs={"class": "form-input"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "batch_number": forms.TextInput(attrs={"class": "form-input"}),
            "serial_numbers_text": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "certified_quantity": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "inspection_lot": forms.Select(attrs={"class": "form-select"}),
            "applicable_specifications": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "test_results_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "conformance_statement": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "signatory_title": forms.TextInput(attrs={"class": "form-input"}),
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
                SalesOrder = apps.get_model("scm", "SalesOrder")
                self.fields["sales_order"].queryset = SalesOrder.objects.filter(tenant=self.tenant).select_related("customer").order_by("-created_at")
            except LookupError:
                pass

            try:
                Shipment = apps.get_model("scm", "Shipment")
                self.fields["shipment"].queryset = Shipment.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                FinalInspectionLot = apps.get_model("quality", "FinalInspectionLot")
                self.fields["inspection_lot"].queryset = FinalInspectionLot.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, [
            "customer", "sales_order", "shipment", "inspection_lot"
        ])

        qty = cleaned_data.get("certified_quantity") or 0
        if qty <= 0:
            self.add_error("certified_quantity", "Certified quantity must be at least 1 unit.")

        customer = cleaned_data.get("customer")
        if customer:
            sales_order = cleaned_data.get("sales_order")
            if sales_order and getattr(sales_order, "customer_id", None) and sales_order.customer_id != customer.pk:
                self.add_error("sales_order", "Linked sales order does not belong to the selected customer.")
            inspection_lot = cleaned_data.get("inspection_lot")
            if inspection_lot and getattr(inspection_lot, "customer_id", None) and inspection_lot.customer_id != customer.pk:
                self.add_error("inspection_lot", "Linked inspection lot does not belong to the selected customer.")

        return cleaned_data
