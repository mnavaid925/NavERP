from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.InProcessQuality.LayeredProcessAudits import LayeredProcessAudit

User = get_user_model()


class LayeredProcessAuditForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = LayeredProcessAudit
        fields = [
            "title",
            "audit_layer",
            "focus_area",
            "status",
            "work_center_code",
            "work_center",
            "org_unit",
            "shift",
            "scheduled_date",
            "conducted_at",
            "auditor",
            "total_questions_audited",
            "questions_conforming",
            "questions_non_conforming",
            "controlled_document",
            "findings_summary",
            "on_the_spot_mitigation",
            "mitigation_details",
            "non_conformance",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Tier 1 Daily Line Audit - Turning Cell"}),
            "audit_layer": forms.Select(attrs={"class": "form-select"}),
            "focus_area": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "work_center_code": forms.TextInput(attrs={"class": "form-input"}),
            "work_center": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "shift": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Shift 1 (Morning)"}),
            "scheduled_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "conducted_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "auditor": forms.Select(attrs={"class": "form-select"}),
            "total_questions_audited": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "questions_conforming": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "questions_non_conforming": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "controlled_document": forms.Select(attrs={"class": "form-select"}),
            "findings_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "on_the_spot_mitigation": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "mitigation_details": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "non_conformance": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["auditor"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "email")

            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")

            try:
                ControlledDocument = apps.get_model("quality", "ControlledDocument")
                self.fields["controlled_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            except LookupError:
                pass

            try:
                NonConformanceReport = apps.get_model("quality", "NonConformanceReport")
                self.fields["non_conformance"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                WorkCenter = apps.get_model("scm", "WorkCenter")
                self.fields["work_center"].queryset = WorkCenter.objects.filter(tenant=self.tenant).order_by("code")
            except LookupError:
                pass

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, [
            "auditor", "org_unit", "controlled_document", "non_conformance", "work_center"
        ])

        total_q = cleaned_data.get("total_questions_audited") or 0
        conf_q = cleaned_data.get("questions_conforming") or 0
        non_conf_q = cleaned_data.get("questions_non_conforming") or 0

        if (conf_q + non_conf_q) > total_q:
            self.add_error(
                "questions_conforming",
                "Total conforming plus non-conforming questions cannot exceed total questions audited."
            )

        if non_conf_q > 0:
            if not cleaned_data.get("findings_summary"):
                self.add_error("findings_summary", "Findings summary is required when non-conforming items are observed.")
            if cleaned_data.get("on_the_spot_mitigation") and not cleaned_data.get("mitigation_details"):
                self.add_error("mitigation_details", "Mitigation details are required when on-the-spot mitigation is checked.")

        return cleaned_data
