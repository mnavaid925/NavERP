"""core — 0.8 forms (privacy & data protection)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    ConsentPurpose,
    ConsentRecord,
    DataSubjectRequest,
    DisposalRecord,
    PiiClassification,
    RegulatoryFramework,
    RetentionPolicy,
)


class ConsentPurposeForm(TenantModelForm):
    class Meta:
        model = ConsentPurpose
        fields = ["name", "code", "lawful_basis", "is_optional", "description", "is_active"]


class ConsentRecordForm(TenantModelForm):
    """Records ONE consent event. `recorded_by` and `tenant` are set by the view.

    Both a grant and a withdrawal are entered through this form — a withdrawal is a new ROW, never an
    edit of the grant, because the history is the evidence.
    """

    class Meta:
        model = ConsentRecord
        fields = ["party", "purpose", "action", "source", "evidence", "occurred_at", "expires_at"]


class DataSubjectRequestForm(TenantModelForm):
    """`status`, `due_at`, the stamps and `identity_verified` are all excluded.

    Verification is a VERB, not a checkbox on a create form: it has to be an explicit act by a named
    person, which is what makes it worth relying on. `due_at` is stamped from the workspace's
    enabled frameworks at creation.
    """

    class Meta:
        model = DataSubjectRequest
        fields = ["subject", "kind", "detail", "received_at"]


class DsarVerificationForm(forms.Form):
    """The verification note. Required — 'verified' with no note is not a record of anything."""

    verification_note = forms.CharField(
        max_length=255, widget=forms.TextInput(attrs={"class": "form-input"}),
        help_text="How identity was established (document checked, callback, known contact).",
    )
    response_notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
    )


class DsarRefusalForm(forms.Form):
    """A refusal must cite a ground; an unexplained refusal is not a lawful one."""

    refusal_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        help_text="The lawful ground for refusing (e.g. legal obligation, manifestly unfounded).",
    )


class RetentionPolicyForm(TenantModelForm):
    class Meta:
        model = RetentionPolicy
        fields = ["name", "data_category", "model_label", "retention_months", "action", "basis",
                  "is_active", "notes"]

    def clean_retention_months(self):
        months = self.cleaned_data["retention_months"]
        if months < 1:
            raise forms.ValidationError("A retention period of zero months means 'keep forever' — "
                                        "deactivate the policy instead.")
        return months


class DisposalRecordForm(TenantModelForm):
    class Meta:
        model = DisposalRecord
        fields = ["policy", "model_label", "record_count", "method", "performed_at", "evidence",
                  "notes"]


class PiiClassificationForm(TenantModelForm):
    """The human confirmation step. `reviewed_by` / `reviewed_at` are stamped by the view."""

    class Meta:
        model = PiiClassification
        fields = ["category", "sensitivity", "confirmation", "notes"]


class RegulatoryFrameworkForm(TenantModelForm):
    class Meta:
        model = RegulatoryFramework
        fields = ["code", "label", "is_enabled", "dsar_window_days", "data_residency_region", "notes"]

    def clean_dsar_window_days(self):
        days = self.cleaned_data["dsar_window_days"]
        if days < 1:
            raise forms.ValidationError("A statutory window must be at least one day.")
        return days
