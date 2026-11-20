from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import reject_foreign
from apps.quality.models.AuditManagement.QualityAudits import QualityAudit
from apps.quality.models.AuditManagement.RegulatoryInspectionHosts import RegulatoryInspectionHost

User = get_user_model()


class RegulatoryInspectionHostForm(forms.ModelForm):
    class Meta:
        model = RegulatoryInspectionHost
        fields = [
            "audit",
            "inspection_title",
            "agency_or_body",
            "agency_name",
            "lead_inspector_name",
            "inspector_credentials",
            "inspection_purpose",
            "announcement_status",
            "scheduled_start_date",
            "scheduled_end_date",
            "actual_start_date",
            "actual_end_date",
            "front_room_lead",
            "back_room_lead",
            "scribe_user",
            "war_room_location",
            "status",
            "form_483_issued",
            "observations_count",
            "formal_outcome",
            "closeout_memo",
        ]
        widgets = {
            "audit": forms.Select(attrs={"class": "form-select"}),
            "inspection_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FDA QSIT / cGMP Medical Device Inspection"}),
            "agency_or_body": forms.Select(attrs={"class": "form-select"}),
            "agency_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. US FDA - San Francisco District Office, TÜV SÜD"}),
            "lead_inspector_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Lead investigator / lead auditor name"}),
            "inspector_credentials": forms.TextInput(attrs={"class": "form-input", "placeholder": "Badge #, division, or registration ID"}),
            "inspection_purpose": forms.Select(attrs={"class": "form-select"}),
            "announcement_status": forms.Select(attrs={"class": "form-select"}),
            "scheduled_start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "scheduled_end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "actual_start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "actual_end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "front_room_lead": forms.Select(attrs={"class": "form-select"}),
            "back_room_lead": forms.Select(attrs={"class": "form-select"}),
            "scribe_user": forms.Select(attrs={"class": "form-select"}),
            "war_room_location": forms.TextInput(attrs={"class": "form-input", "placeholder": "Conference Room A (War Room) / Virtual Bridge Link"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "form_483_issued": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "observations_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "formal_outcome": forms.Select(attrs={"class": "form-select"}),
            "closeout_memo": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Exit conference debrief, commitments, and executive action plan..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["audit"].queryset = QualityAudit.objects.filter(tenant=self.tenant)
            self.fields["front_room_lead"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["back_room_lead"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["scribe_user"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        sstart = cleaned_data.get("scheduled_start_date")
        send = cleaned_data.get("scheduled_end_date")
        if sstart and send and send < sstart:
            self.add_error("scheduled_end_date", "Scheduled end date cannot be earlier than start date.")

        astart = cleaned_data.get("actual_start_date")
        aend = cleaned_data.get("actual_end_date")
        if astart and aend and aend < astart:
            self.add_error("actual_end_date", "Actual end date cannot be earlier than actual start date.")

        reject_foreign(self, cleaned_data, [
            "audit",
            "front_room_lead",
            "back_room_lead",
            "scribe_user",
        ])
        return cleaned_data


class InspectionLogRequestForm(forms.Form):
    request_description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Requested document, DHF section, training record, or batch ticket..."}),
        label="Inspector Document / Evidence Request",
    )
    assigned_sme = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Assigned SME / Scribe",
    )
    priority = forms.ChoiceField(
        choices=(("urgent", "Urgent (< 30 Mins)"), ("standard", "Standard (< 2 Hours)"), ("end_of_day", "End of Day")),
        initial="standard",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["assigned_sme"].queryset = User.objects.filter(tenant=tenant)
