from django import forms
from django.contrib.auth import get_user_model

from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party
from apps.quality.forms._common import reject_foreign
from apps.quality.models.AuditManagement.AuditPrograms import AuditProgram
from apps.quality.models.AuditManagement.QualityAudits import QualityAudit
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument

User = get_user_model()


class QualityAuditForm(forms.ModelForm):
    class Meta:
        model = QualityAudit
        fields = [
            "program",
            "title",
            "audit_type",
            "audit_method",
            "standard_framework",
            "target_org_unit",
            "external_entity",
            "lead_auditor",
            "auditee_lead",
            "audit_checklist_sop",
            "planned_start_date",
            "planned_end_date",
            "actual_start_date",
            "actual_end_date",
            "scope_objectives",
            "product_scope",
            "lot_number_sampled",
            "status",
            "outcome",
            "executive_summary",
            "notes",
        ]
        widgets = {
            "program": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ISO 13485 Internal Audit - Design & Document Control"}),
            "audit_type": forms.Select(attrs={"class": "form-select"}),
            "audit_method": forms.Select(attrs={"class": "form-select"}),
            "standard_framework": forms.Select(attrs={"class": "form-select"}),
            "target_org_unit": forms.Select(attrs={"class": "form-select"}),
            "external_entity": forms.Select(attrs={"class": "form-select"}),
            "lead_auditor": forms.Select(attrs={"class": "form-select"}),
            "auditee_lead": forms.Select(attrs={"class": "form-select"}),
            "audit_checklist_sop": forms.Select(attrs={"class": "form-select"}),
            "planned_start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "planned_end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "actual_start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "actual_end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "scope_objectives": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Audit criteria, processes, procedures, and scope boundaries..."}),
            "product_scope": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Orthopedic Implant Series V2 / Infusion Pump FG"}),
            "lot_number_sampled": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LOT-2026-0881"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "outcome": forms.Select(attrs={"class": "form-select"}),
            "executive_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Management summary of findings, strengths, and conclusions..."}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Internal audit logistics or coordination notes..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["program"].queryset = AuditProgram.objects.filter(tenant=self.tenant)
            self.fields["target_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["external_entity"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["lead_auditor"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["auditee_lead"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["audit_checklist_sop"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        pstart = cleaned_data.get("planned_start_date")
        pend = cleaned_data.get("planned_end_date")
        if pstart and pend and pend < pstart:
            self.add_error("planned_end_date", "Planned end date cannot be earlier than start date.")

        astart = cleaned_data.get("actual_start_date")
        aend = cleaned_data.get("actual_end_date")
        if astart and aend and aend < astart:
            self.add_error("actual_end_date", "Actual end date cannot be earlier than actual start date.")

        lead_auditor = cleaned_data.get("lead_auditor")
        auditee_lead = cleaned_data.get("auditee_lead")
        audit_type = cleaned_data.get("audit_type")
        if lead_auditor and auditee_lead and lead_auditor == auditee_lead and audit_type in ("internal_system", "internal_process", "internal_product"):
            self.add_error("auditee_lead", "Auditor independence violation: Lead auditor cannot audit their own role (ISO 19011).")

        reject_foreign(self, cleaned_data, [
            "program",
            "target_org_unit",
            "external_entity",
            "lead_auditor",
            "auditee_lead",
            "audit_checklist_sop",
        ])
        return cleaned_data
