from django import forms

from apps.accounts.models import User
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign, validate_safe_doc_upload
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentLocks import DocumentLock
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


class DocumentLockForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = DocumentLock
        fields = [
            "document",
            "base_version",
            "locked_by",
            "expires_at",
            "lock_type",
            "checkout_note",
            "working_copy_file",
            "status",
        ]
        exclude = [
            "tenant",
            "number",
            "checked_out_at",
            "unlocked_at",
            "unlocked_by",
            "override_reason",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "base_version": forms.Select(attrs={"class": "form-select"}),
            "locked_by": forms.Select(attrs={"class": "form-select"}),
            "expires_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "lock_type": forms.Select(attrs={"class": "form-select"}),
            "checkout_note": forms.TextInput(attrs={"class": "form-input", "placeholder": "Planned edits"}),
            "working_copy_file": forms.FileInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["base_version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["locked_by"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
        self.fields["expires_at"].required = False
        self.fields["checkout_note"].required = False
        self.fields["working_copy_file"].required = False

    def clean_working_copy_file(self):
        f = self.cleaned_data.get("working_copy_file")
        return validate_safe_doc_upload(f)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document", "base_version", "locked_by"])
        return cleaned_data


class CheckoutForm(forms.Form):
    lock_type = forms.ChoiceField(
        choices=DocumentLock.LOCK_TYPE_CHOICES,
        initial="exclusive",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Lock Mode",
    )
    checkout_note = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Brief note on planned modifications"}),
        label="Checkout Note / Intent",
    )
    expires_in_hours = forms.IntegerField(
        initial=24,
        min_value=1,
        max_value=720,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input"}),
        label="Lock Duration (Hours)",
        help_text="After this duration, the lock can be auto-cleared or flagged as stale.",
    )


class CheckinForm(forms.Form):
    INTENT_CHOICES = (
        ("minor", "Minor Revision (e.g. 1.0 -> 1.1) — Recommended for general updates"),
        ("major", "Major Milestone Release (e.g. 1.x -> 2.0) — Significant overhaul"),
        ("patch", "Patch Fix (e.g. 1.0 -> 1.0.1) — Minor typo / formatting fix"),
    )

    increment_intent = forms.ChoiceField(
        choices=INTENT_CHOICES,
        initial="minor",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Version Increment Intent",
    )
    change_summary = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Mandatory description of modifications made"}),
        label="Change Summary *",
    )
    file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-input"}),
        label="New Document File Payload",
    )
    extracted_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Updated text layer for search and redline diff comparison"}),
        label="Extracted Text / Document Content",
    )
    is_official = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        label="Promote to Official Public Baseline",
    )

    def clean_file(self):
        f = self.cleaned_data.get("file")
        return validate_safe_doc_upload(f)


class ForceUnlockForm(forms.Form):
    override_reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Mandatory justification for administrative override..."}),
        label="Override Reason *",
        help_text="An immutable audit record will log your user ID, timestamp, and justification.",
    )
