from django import forms

from apps.documents.models.SecurityAccessControl.DlpIncidents import DlpIncident


class DlpIncidentResolveForm(forms.ModelForm):
    class Meta:
        model = DlpIncident
        fields = [
            "resolution_status",
            "resolution_notes",
        ]
        widgets = {
            "resolution_status": forms.Select(attrs={"class": "form-select"}),
            "resolution_notes": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Document investigation steps, justification, or remedial actions taken...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resolution_notes"].required = True
