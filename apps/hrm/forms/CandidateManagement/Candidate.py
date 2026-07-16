"""HRM 3.6 Candidate Management — Candidate forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    CandidateProfile,
    CandidateSkill,
    CandidateTag,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_resume, _validate_upload


# ----------------------------------------------------------------------- 3.6 Candidate Management
class CandidateTagForm(TenantModelForm):
    class Meta:
        model = CandidateTag
        fields = ["name", "color", "description"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def clean_color(self):
        # Defense-in-depth: the value is interpolated into a CSS `style=` attribute on the badge, so a
        # non-hex value (e.g. "red;background:url(//evil)") would be CSS-injection. Enforce strict hex
        # here too, not only via the model validator.
        color = (self.cleaned_data.get("color") or "").strip()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise forms.ValidationError("Enter a valid hex color, e.g. #3B82F6.")
        return color


class CandidateProfileForm(TenantModelForm):
    # SECURITY: `party` is set in the view (a fresh person Party is minted per candidate); `status`,
    # `gdpr_consent_date` are workflow-owned; `tags` are managed via inline POST actions on the hub.
    class Meta:
        model = CandidateProfile
        fields = ["first_name", "last_name", "email", "phone", "linkedin_url", "current_job_title",
                  "current_employer", "city", "country", "years_of_experience", "highest_qualification",
                  "skill_set", "resume_file", "resume_text", "photo", "gender", "source",
                  "expected_salary", "notice_period_days", "sourced_by", "do_not_contact",
                  "gdpr_consent", "gdpr_consent_expires", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["sourced_by"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username"))
        else:
            self.fields["sourced_by"].queryset = get_user_model().objects.none()

    def clean_email(self):
        # Enforce the (tenant, email) uniqueness as a friendly form error rather than a 500 on the
        # DB constraint (mirrors the duplicate-detection anchor in every ATS product).
        email = self.cleaned_data["email"]
        if self.tenant is not None:
            qs = CandidateProfile.objects.filter(tenant=self.tenant, email__iexact=email)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A candidate with this email already exists in this workspace.")
        return email

    def clean_resume_file(self):
        return _validate_resume(self.cleaned_data.get("resume_file"))

    def clean_photo(self):
        return _validate_upload(self.cleaned_data.get("photo"),
                                allowed_ext=ALLOWED_PHOTO_EXTENSIONS, max_bytes=MAX_PHOTO_BYTES, label="Photo")


class CandidateSkillForm(TenantModelForm):
    # Inline-add on the candidate detail hub; `candidate` is set in the view.
    class Meta:
        model = CandidateSkill
        fields = ["skill_name", "proficiency", "source"]
