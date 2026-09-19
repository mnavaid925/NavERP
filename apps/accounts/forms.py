"""Auth + user-management forms."""
from django import forms
from django.contrib.auth import password_validation
from django.utils.text import slugify

from apps.core.forms import TenantModelForm
from apps.core.models import Tenant

from .models import (
    AccessRequest,
    AccessReview,
    AccessReviewItem,
    ElevationGrant,
    PasswordPolicy,
    Role,
    User,
    UserInvite,
)


class LoginForm(forms.Form):
    identifier = forms.CharField(
        label="Email or username",
        widget=forms.TextInput(attrs={"class": "form-input", "autofocus": True, "placeholder": "you@company.com"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "••••••••"})
    )


class TenantRegisterForm(forms.Form):
    """Self-service onboarding: create a workspace + its first admin user."""

    company_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-input"}))
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-input"}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-input"}))
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"class": "form-input"}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"class": "form-input"}))

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            password_validation.validate_password(p1)
        return cleaned

    def _unique_slug(self, name):
        base = slugify(name) or "tenant"
        slug = base
        i = 2
        while Tenant.objects.filter(slug=slug).exists():
            slug = f"{base}-{i}"
            i += 1
        return slug

    def save(self):
        tenant = Tenant.objects.create(name=self.cleaned_data["company_name"],
                                       slug=self._unique_slug(self.cleaned_data["company_name"]),
                                       plan="free")
        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data.get("last_name", ""),
            tenant=tenant,
            is_tenant_admin=True,
        )
        return user


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "you@company.com"}))


class SetPasswordForm(forms.Form):
    new_password1 = forms.CharField(label="New password", widget=forms.PasswordInput(attrs={"class": "form-input"}))
    new_password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput(attrs={"class": "form-input"}))

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("new_password1"), cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", "Passwords do not match.")
        if p1:
            password_validation.validate_password(p1)
        return cleaned


class UserForm(TenantModelForm):
    """Create/edit a member. Password optional on edit (blank keeps current)."""

    password = forms.CharField(
        required=False, widget=forms.PasswordInput(attrs={"class": "form-input"}),
        help_text="Required when creating. Leave blank when editing to keep the current password.",
    )

    class Meta:
        model = User
        fields = ["email", "username", "first_name", "last_name", "role",
                  "is_tenant_admin", "status", "is_active"]

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and not cleaned.get("password"):
            self.add_error("password", "Password is required when creating a user.")
        if cleaned.get("password"):
            password_validation.validate_password(cleaned["password"])
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get("password")
        if pw:
            user.set_password(pw)
        elif not user.pk:
            user.set_unusable_password()
        if commit:
            user.save()
            self.save_m2m()
        return user


class RoleForm(TenantModelForm):
    class Meta:
        model = Role
        fields = ["name", "description", "permissions"]
        widgets = {"permissions": forms.CheckboxSelectMultiple()}


class UserInviteForm(TenantModelForm):
    class Meta:
        model = UserInvite
        fields = ["email", "role"]


class InviteAcceptForm(forms.Form):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-input"}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-input"}))
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"class": "form-input"}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"class": "form-input"}))

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            password_validation.validate_password(p1)
        return cleaned


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "username": forms.TextInput(attrs={"class": "form-input"}),
        }


# ==================================================== 0.2 bullet 3: access requests
class AccessRequestForm(TenantModelForm):
    """What a member may ask for. `requester` is the logged-in user and is set by the view, never
    chosen here — a form field for it would let anyone request access on someone else's behalf.
    `status`, the decision stamps and `granted_until` are verb-written and excluded."""

    class Meta:
        model = AccessRequest
        fields = ["requested_role", "justification", "requested_days"]


class AccessDecisionForm(forms.Form):
    """The approve/reject note. Required on reject: a denial with no stated reason is not a
    decision anyone can act on or appeal."""

    note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        help_text="Required when rejecting.",
    )

    def __init__(self, *args, require_note=False, **kwargs):
        self.require_note = require_note
        super().__init__(*args, **kwargs)
        if require_note:
            self.fields["note"].required = True

    def clean_note(self):
        note = (self.cleaned_data.get("note") or "").strip()
        if self.require_note and not note:
            raise forms.ValidationError("Give a reason for the rejection.")
        return note


# ==================================================== 0.2 bullet 5: privileged elevation
class ElevationGrantForm(TenantModelForm):
    """A JIT elevation request. `status` and the approve/revoke stamps are verb-written."""

    class Meta:
        model = ElevationGrant
        fields = ["user", "scope", "reason", "starts_at", "expires_at"]


# ==================================================== 0.2 bullet 4: certification
class AccessReviewForm(TenantModelForm):
    class Meta:
        model = AccessReview
        fields = ["name", "scope_role", "due_on"]


class AccessReviewItemForm(TenantModelForm):
    """The per-row attestation note. `decision` itself is written by ari_attest / ari_revoke."""

    class Meta:
        model = AccessReviewItem
        fields = ["note"]


# ==================================================== 0.2 bullet 2: bulk provisioning
class UserImportForm(forms.Form):
    """Bulk CSV user import. Columns: email, username, first_name, last_name, role (optional).

    A plain Form, not a ModelForm: the upload is validated row by row and only then handed to
    `UserImportBatch`, so nothing is written until the batch is committed.
    """

    csv_file = forms.FileField(
        label="CSV file",
        widget=forms.ClearableFileInput(attrs={"class": "form-input", "accept": ".csv"}),
        help_text="Header row required. Columns: email, username, first_name, last_name, role.",
    )

    MAX_BYTES = 2 * 1024 * 1024

    def clean_csv_file(self):
        upload = self.cleaned_data["csv_file"]
        if upload.size > self.MAX_BYTES:
            raise forms.ValidationError("Files are capped at 2 MB.")
        if not (upload.name or "").lower().endswith(".csv"):
            raise forms.ValidationError("Only .csv files are accepted.")
        return upload


# ==================================================== 0.4 forms
class MfaChallengeForm(forms.Form):
    """The step-up code, or a backup code."""

    code = forms.CharField(
        label="Verification code",
        widget=forms.TextInput(attrs={"class": "form-input", "autofocus": True,
                                      "autocomplete": "one-time-code",
                                      "placeholder": "123456"}),
        help_text="Enter the 6-digit code from your authenticator app, or a backup code.",
    )


class MfaSetupForm(forms.Form):
    """Names the device. The secret itself is generated server-side, never chosen by the user."""

    name = forms.CharField(
        required=False, max_length=120, label="Device name",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "iPhone"}),
    )


class PasswordPolicyForm(TenantModelForm):
    """The per-tenant credential policy. `is_enforced` is the switch that starts applying it."""

    class Meta:
        model = PasswordPolicy
        fields = ["is_enforced", "min_length", "require_upper", "require_lower", "require_digit",
                  "require_symbol", "max_age_days", "prevent_reuse_count"]

    def clean_min_length(self):
        value = self.cleaned_data["min_length"]
        if value < 8:
            raise forms.ValidationError("A minimum length below 8 is not a policy.")
        return value
