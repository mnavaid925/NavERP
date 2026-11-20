from django import forms
from django.contrib.auth import get_user_model

from apps.core.models.OrgUnit import OrgUnit
from apps.quality.forms._common import reject_foreign
from apps.quality.models.AuditManagement.AuditFindings import AuditFinding
from apps.quality.models.AuditManagement.QualityAudits import QualityAudit
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport

User = get_user_model()


class AuditFindingForm(forms.ModelForm):
    class Meta:
        model = AuditFinding
        fields = [
            "audit",
            "finding_number_in_audit",
            "title",
            "severity",
            "standard_clause",
            "requirement_statement",
            "condition_evidence",
            "audited_org_unit",
            "assignee",
            "response_due_date",
            "containment_action",
            "root_cause_summary",
            "corrective_action_plan",
            "linked_capa",
            "linked_ncr",
        ]
        widgets = {
            "audit": forms.Select(attrs={"class": "form-select"}),
            "finding_number_in_audit": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Failure to establish calibration interval for torque wrenches"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "standard_clause": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ISO 13485:2016 §7.6, 21 CFR 820.72"}),
            "requirement_statement": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Specified requirement from standard, SOP, or regulation..."}),
            "condition_evidence": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Objective evidence observed proving the deficiency..."}),
            "audited_org_unit": forms.Select(attrs={"class": "form-select"}),
            "assignee": forms.Select(attrs={"class": "form-select"}),
            "response_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "containment_action": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Immediate containment or quarantine actions..."}),
            "root_cause_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Root cause analysis summary..."}),
            "corrective_action_plan": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Proposed corrective and preventive actions..."}),
            "linked_capa": forms.Select(attrs={"class": "form-select"}),
            "linked_ncr": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["audit"].queryset = QualityAudit.objects.filter(tenant=self.tenant)
            self.fields["audited_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["assignee"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["linked_capa"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)
            self.fields["linked_ncr"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, [
            "audit",
            "audited_org_unit",
            "assignee",
            "linked_capa",
            "linked_ncr",
        ])
        return cleaned_data


class AuditFindingResponseForm(forms.ModelForm):
    class Meta:
        model = AuditFinding
        fields = [
            "containment_action",
            "root_cause_summary",
            "corrective_action_plan",
        ]
        widgets = {
            "containment_action": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Immediate actions taken to contain the non-conformance..."}),
            "root_cause_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe the root cause determined through 5-Why or Fishbone..."}),
            "corrective_action_plan": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Specific actions, responsible owners, and completion dates..."}),
        }
