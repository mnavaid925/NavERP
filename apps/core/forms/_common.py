"""Shared toolkit for the core forms package.

apps/core/forms.py was split into this package. core is a Module 0 FOUNDATION app with
no NavERP sub-modules, so entity files sit FLAT at the package root (mirroring its already-
flat templates/core/<entity>/). The package __init__ re-exports everything, so
``from apps.core.forms import X`` is unchanged.

The import block below is the ORIGINAL forms.py header, verbatim.
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
