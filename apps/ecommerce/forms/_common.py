from django import forms
from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from apps.core.forms import TenantModelForm


class TenantUniqueMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None and getattr(self.instance, "tenant_id", None) is None:
            self.instance.tenant = self.tenant

    def validate_unique(self):
        exclude = set(self._get_validation_exclusions())
        exclude.discard("tenant")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as exc:
            self._update_errors(exc)


def reject_foreign(form, cleaned, names):
    tenant_id = form.tenant.pk if getattr(form, "tenant", None) is not None else None
    for name in names:
        value = cleaned.get(name)
        if value is None:
            continue
        values = value if isinstance(value, QuerySet) else [value]
        for chosen in values:
            if getattr(chosen, "tenant_id", None) != tenant_id:
                form.add_error(name, "That record belongs to another workspace.")
