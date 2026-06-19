"""Auth + user-management forms."""
from django import forms
from django.contrib.auth import password_validation
from django.utils.text import slugify

from apps.core.forms import TenantModelForm
from apps.core.models import Tenant

from .models import Role, User, UserInvite


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
