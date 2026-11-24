from datetime import timedelta
from django import forms
from django.utils import timezone

from apps.documents.forms._common import reject_foreign
from apps.documents.models.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExport
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document


class ChainOfCustodyExportForm(forms.ModelForm):
    """Builder form for packaging defensible evidence packages and granting auditor access."""

    portal_passcode = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Optional guest passcode protection...",
            }
        ),
        help_text="If set, the auditor must enter this passcode before viewing documents.",
    )

    class Meta:
        model = ChainOfCustodyExport
        fields = [
            "title",
            "regulatory_framework",
            "scope",
            "document",
            "folder",
            "start_date",
            "end_date",
            "auditor_name",
            "auditor_email",
            "auditor_organization",
            "expires_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2026 Annual SOC 2 Evidence Package"}),
            "regulatory_framework": forms.Select(attrs={"class": "form-select"}),
            "scope": forms.Select(attrs={"class": "form-select"}),
            "document": forms.Select(attrs={"class": "form-select"}),
            "folder": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "auditor_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Lead Inspector / Auditor Full Name"}),
            "auditor_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "auditor@regulatory-agency.gov"}),
            "auditor_organization": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Ernst & Young, FDA ORA, PwC"}),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=tenant).order_by("title")
            self.fields["folder"].queryset = DocumentFolder.objects.filter(tenant=tenant).order_by("name")
        else:
            self.fields["document"].queryset = Document.objects.none()
            self.fields["folder"].queryset = DocumentFolder.objects.none()
        self.fields["document"].required = False
        self.fields["folder"].required = False

        if not self.initial.get("expires_at") and not getattr(self.instance, "expires_at", None):
            self.initial["expires_at"] = (timezone.now() + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document", "folder"])

        scope = cleaned_data.get("scope")
        document = cleaned_data.get("document")
        folder = cleaned_data.get("folder")

        if scope == "single_document" and not document:
            self.add_error("document", "Please select a target document for single document scope.")
        elif scope == "folder_tree" and not folder:
            self.add_error("folder", "Please select a target folder for folder tree scope.")

        return cleaned_data


class AuditorPortalPasscodeForm(forms.Form):
    """Authentication form for guest auditor passcode gate."""

    passcode = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input w-full text-center text-lg tracking-widest font-mono",
                "placeholder": "&bull;&bull;&bull;&bull;&bull;&bull;",
                "autofocus": "autofocus",
            }
        ),
    )
