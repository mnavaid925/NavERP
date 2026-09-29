"""Form for the 8.6 typed order-validation rule.

``parameters`` is the one field with teeth here. It is a ``JSONField`` rendered as a textarea,
and Django's own JSON form field is forgiving enough that a user can hand it something which
parses to a JSON *array* or a bare string — which the model's readers, all of which call
``.get()`` on the blob, would then choke on at evaluation time rather than at save time. So
``clean_parameters`` re-parses, insists the result is a mapping, and reports a FIELD error.

That is the difference the contract cares about: a malformed blob is a form error the author
sees and fixes, never a 500 raised out of ``JSONField`` on save.
"""
import json

from django import forms

from apps.core.models import Party
from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.sales.models.OrderManagement.OrderValidationRules import OrderValidationRule


class OrderValidationRuleForm(TenantUniqueMixin, TenantModelForm):
    """Create / edit one validation rule. Thresholds are a JSON blob, not a column per type."""

    class Meta:
        model = OrderValidationRule
        # Excluded, with the reason:
        #   tenant       — set by the mixin from the view's request.tenant, never from input.
        #   number       — auto-numbered OVR- by TenantNumbered.save().
        #   created_at / updated_at — auto_now* stamps.
        fields = [
            "name",
            "rule_type",
            "severity",
            "active_on",
            "parameters",
            "party",
            "priority",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "e.g. Standard Credit Gate",
            }),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "active_on": forms.Select(attrs={"class": "form-select"}),
            "parameters": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 6,
                "placeholder": '{"amount": 5000}',
            }),
            "party": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "min": 0, "step": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
            "description": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Why this rule exists, and who asked for it...",
            }),
        }
        help_texts = {
            "parameters": (
                'JSON thresholds for this rule type, e.g. {"amount": 5000} or {"pct": 12.5}. '
                "Unknown keys are ignored, so a rule written by a newer build still loads."
            ),
            "party": "Leave blank to apply this rule to every customer.",
            "priority": "Lower numbers are evaluated first. Default 10.",
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # TenantModelForm already narrows ModelChoiceFields to the tenant; party is spelled out
        # anyway because it is nullable and must offer an explicit blank ("every customer")
        # rather than implying one.
        if self.tenant is not None:
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
        self.fields["party"].required = False
        self.fields["parameters"].required = False
        # An edit renders the stored dict as a mapping repr unless it is stringified, which is
        # not something a JSON textarea should ever show.
        if not self.is_bound and self.instance.pk and isinstance(self.instance.parameters, dict):
            self.initial["parameters"] = json.dumps(self.instance.parameters, indent=2, sort_keys=True)

    def clean_parameters(self):
        raw = self.cleaned_data.get("parameters")
        if raw in (None, ""):
            return {}
        # A bound textarea hands back the string; an unbound form hands back the dict Django
        # already parsed. Both reach here, so normalise on the string form only.
        if isinstance(raw, (dict, list, int, float, bool)):
            value = raw
        else:
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                raise forms.ValidationError(
                    "Enter valid JSON, for example: {\"amount\": 5000}"
                )
        if not isinstance(value, dict):
            raise forms.ValidationError(
                "Parameters must be a JSON object of thresholds, for example: {\"amount\": 5000}"
            )
        return value

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        elif self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The validation rule must belong to this workspace.")
        # Belt and braces on top of the narrowed queryset: a queryset filter alone would reject
        # a cross-tenant pk with "Select a valid choice", and this says WHY in the author's own
        # terms — the same helper every other 8.6 form uses.
        _reject_foreign(self, cleaned, ["party"])
        return cleaned
