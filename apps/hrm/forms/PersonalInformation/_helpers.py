"""HRM 3.25 Personal Information — _helpers forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403


class _ThemedForm(forms.Form):
    """Plain ``forms.Form`` base that applies the theme widget classes (TenantModelForm does this for
    ModelForms; the change-request forms assemble ``field_changes`` JSON rather than saving a model,
    so they need the same styling loop)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-textarea")
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check")
            else:
                widget.attrs.setdefault("class", "form-input")
