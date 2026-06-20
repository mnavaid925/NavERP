"""Core forms. ``TenantModelForm`` is the shared base for the whole project:
it scopes every FK dropdown to the active tenant (no cross-tenant leakage in selects),
applies the theme widget classes, and gives date/datetime fields correct HTML5
widgets that round-trip cleanly (L22). ``tenant`` is excluded everywhere (set in the view).
"""
import os

from django import forms

# Document upload safety: allowlist extensions + cap size (defense-in-depth; also keep
# MEDIA_ROOT outside the web root in production — see README).
ALLOWED_DOC_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip",
}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


class TenantModelForm(forms.ModelForm):
    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(
                    attrs={"type": "datetime-local", "class": "form-input"},
                    format="%Y-%m-%dT%H:%M",
                )
                field.input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
            elif isinstance(field, forms.DateField):
                field.widget = forms.DateInput(
                    attrs={"type": "date", "class": "form-input"}, format="%Y-%m-%d"
                )
                field.input_formats = ["%Y-%m-%d"]
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-textarea")
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check")
            else:
                widget.attrs.setdefault("class", "form-input")

            # Scope FK / M2M choice querysets to this tenant.
            if tenant is not None and isinstance(field, forms.ModelChoiceField):
                model = field.queryset.model
                if "tenant" in [f.name for f in model._meta.fields]:
                    field.queryset = field.queryset.filter(tenant=tenant)


from .models import (  # noqa: E402  (after base class so forms can reference it)
    Activity,
    Address,
    ContactMethod,
    Document,
    Employment,
    OrgUnit,
    Party,
    PartyRelationship,
    PartyRole,
)


class OrgUnitForm(TenantModelForm):
    class Meta:
        model = OrgUnit
        fields = ["kind", "name", "parent"]


class PartyForm(TenantModelForm):
    class Meta:
        model = Party
        fields = ["kind", "name", "tax_id"]


class PartyRoleForm(TenantModelForm):
    class Meta:
        model = PartyRole
        fields = ["party", "role", "status", "start_date"]


class AddressForm(TenantModelForm):
    class Meta:
        model = Address
        fields = ["party", "kind", "line1", "city", "country"]


class ContactMethodForm(TenantModelForm):
    class Meta:
        model = ContactMethod
        fields = ["party", "kind", "value"]


class PartyRelationshipForm(TenantModelForm):
    class Meta:
        model = PartyRelationship
        fields = ["from_party", "to_party", "kind"]


class EmploymentForm(TenantModelForm):
    class Meta:
        model = Employment
        fields = ["party", "org_unit", "manager", "job_title", "hired_on", "status"]


class ActivityForm(TenantModelForm):
    class Meta:
        model = Activity
        fields = ["owner", "party", "kind", "subject", "status", "due_at"]


class DocumentForm(TenantModelForm):
    class Meta:
        model = Document
        fields = ["file", "name", "classification", "version"]

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f and hasattr(f, "name"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(f, "size", 0) and f.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError("File exceeds the 20 MB limit.")
        return f
