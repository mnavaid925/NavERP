"""HRM 3.13 Salary Structure — SalaryStructureLines forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PayComponent,
    SalaryStructureLine,
)


class SalaryStructureLineForm(TenantModelForm):
    # `template` is set by the view from the URL, never a form field (no cross-template injection).
    class Meta:
        model = SalaryStructureLine
        fields = ["pay_component", "calculation_type", "amount", "percentage", "sequence"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "pay_component" in self.fields:
            self.fields["pay_component"].queryset = (
                PayComponent.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("display_order", "name"))
        # Blank calc-type defers to the component's own calculation_type.
        if "calculation_type" in self.fields:
            self.fields["calculation_type"].required = False

    def clean(self):
        cleaned = super().clean()
        # `template` is excluded from the form (set by the view), so Django's
        # (tenant, template, pay_component) unique_together check is skipped by validate_unique. Do the
        # duplicate check here — otherwise a repeated component surfaces as a raw IntegrityError 500 on
        # save instead of a friendly field error. The view presets instance.template before validation.
        pc = cleaned.get("pay_component")
        if self.instance.template_id and pc is not None and self.tenant is not None:
            dupes = (SalaryStructureLine.objects
                     .filter(tenant=self.tenant, template_id=self.instance.template_id, pay_component=pc)
                     .exclude(pk=self.instance.pk))
            if dupes.exists():
                raise forms.ValidationError(
                    {"pay_component": "This component is already in this salary structure."})
        return cleaned
