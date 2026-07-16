"""HRM 3.6 Candidate Management — Application forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    CANDIDATE_SOURCE_CHOICES,
    CandidateProfile,
    EmployeeProfile,
    JobApplication,
    JobRequisition,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_resume


class JobApplicationForm(TenantModelForm):
    # SECURITY: `stage`, `stage_changed_at`, `hired_on`, `rejection_reason`, `rejection_notes` are
    # workflow-owned (set only by the stage-move / reject actions). `screening_answers` is captured by
    # the public apply flow, not hand-edited here.
    class Meta:
        model = JobApplication
        fields = ["candidate", "requisition", "source", "referred_by", "cover_letter_text",
                  "cover_letter_file", "rating", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["candidate"].queryset = (
                CandidateProfile.objects.filter(tenant=self.tenant).order_by("-created_at"))
            # Explicit tenant scope (not just the TenantModelForm base) — a recruiter can only file an
            # application against a requisition in their own workspace.
            self.fields["requisition"].queryset = (
                JobRequisition.objects.filter(tenant=self.tenant).order_by("-created_at"))
            self.fields["referred_by"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))

    def clean_cover_letter_file(self):
        return _validate_resume(self.cleaned_data.get("cover_letter_file"))

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not (1 <= rating <= 5):
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating


class PublicApplicationForm(forms.Form):
    """Unauthenticated career-portal application form (3.6) — a plain ``forms.Form`` (no tenant binding;
    the requisition's public_token already pins the tenant in the view). Resume is required."""

    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-input"}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-input"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-input"}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    linkedin_url = forms.URLField(required=False, widget=forms.URLInput(attrs={"class": "form-input"}))
    city = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    resume_file = forms.FileField(widget=forms.ClearableFileInput(attrs={"class": "form-input",
                                                                         "accept": ".pdf,.doc,.docx"}))
    cover_letter_text = forms.CharField(required=False, widget=forms.Textarea(
        attrs={"class": "form-textarea", "rows": 5}))
    source = forms.ChoiceField(choices=CANDIDATE_SOURCE_CHOICES, initial="careers_page",
                               widget=forms.Select(attrs={"class": "form-select"}))
    gdpr_consent = forms.BooleanField(required=True, widget=forms.CheckboxInput(attrs={"class": "form-check"}),
        label="I consent to the storage and processing of my personal data for recruitment purposes.")

    def clean_resume_file(self):
        return _validate_resume(self.cleaned_data.get("resume_file"))
