from django import forms

from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail


class DocumentAuditTrailFilterForm(forms.Form):
    """Filter form for searching and filtering the immutable document audit trail."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Search action, actor, document, IP, or details...",
            }
        ),
    )
    action_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Action Types")] + list(DocumentAuditTrail.ACTION_TYPE_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_success = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All Results"),
            ("1", "Success"),
            ("0", "Failed / Blocked"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
    )
