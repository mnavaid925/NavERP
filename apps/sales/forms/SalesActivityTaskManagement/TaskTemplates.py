"""Sales 8.8 — the `TaskTemplate` (`TTPL-`) and `TaskTemplateStep` forms.

Both exist so a playbook can be **authored**, which is the half of the feature a repository of
templates is useless without. The model's `clean()` is the authority on G6/G8/G9; these forms make
the same rules visible so an author is not left to discover them from a validation error.

Excluded from ``TaskTemplateForm.Meta.fields``, with the reason for each:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``.
* ``number`` — ``editable=False``; allocated by ``next_number`` (L22).
* ``last_generated_on`` / ``generated_count`` — **FROZEN RECEIPT**, ``editable=False``. Written only
  by the `task_template_generate` POST view inside the transaction that writes the tasks. A
  template's page must never be able to claim a run it did not have (L22).
* ``created_at`` / ``updated_at`` — ``auto_now*`` stamps.

**`territory` is disabled whenever the target type is not Territory** — the mirror of G9. Disabled,
not hidden, so the author reads the reason; and disabled means Django takes the value from the
instance rather than the POST, so a crafted request cannot attach a territory to an
opportunity-targeted template.

**`cadence_interval` is disabled for a one-off**, because G6 requires it to be 1 and there is nothing
useful for a disabled 1 to do. The model still refuses a posted `once`+`7` pair reached any other way.
"""
from django import forms

from apps.sales.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    _reject_foreign,
    tenant_territories,
    tenant_users,
)
from apps.sales.models.SalesActivityTaskManagement.TaskTemplates import (
    MAX_CADENCE_INTERVAL,
    MAX_STEP_OFFSET_DAYS,
    TaskTemplate,
    TaskTemplateStep,
)

TERRITORY_REQUIRED_HELP = (
    "A territory-targeted template fans out over the accounts in one territory, so the territory is "
    "required here."
)
TERRITORY_NOT_APPLICABLE_HELP = (
    "This template targets opportunities, so naming a territory would say which of the two narrows "
    "the set. Clear it, or change the target type to Territory."
)
INTERVAL_LOCKED_HELP = (
    "A one-off template runs once, so its interval is fixed at 1. Pick a repeating cadence to have "
    "it come back."
)


class TaskTemplateForm(TenantUniqueMixin, TenantModelForm):
    """Create or edit one repeating playbook."""

    class Meta:
        model = TaskTemplate
        # Excluded, with the reason for each — see the module docstring.
        fields = [
            "name",
            "description",
            "task_type",
            "priority",
            "cadence",
            "cadence_interval",
            "default_offset_days",
            "target_type",
            "activity_type",
            "territory",
            "owner",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "The motion this playbook encodes, and who runs it...",
            }),
            "cadence_interval": forms.NumberInput(attrs={
                "class": "form-input", "min": "1", "max": str(MAX_CADENCE_INTERVAL), "step": "1",
            }),
            "default_offset_days": forms.NumberInput(attrs={
                "class": "form-input",
                "min": str(-MAX_STEP_OFFSET_DAYS), "max": str(MAX_STEP_OFFSET_DAYS), "step": "1",
            }),
        }
        help_texts = {
            "cadence": "How often this playbook comes back.",
            "cadence_interval": f"Repeat every N cadences. Between 1 and {MAX_CADENCE_INTERVAL}.",
            "target_type": (
                "What the fan-out iterates over — open opportunities, accounts, or every account in "
                "one territory."
            ),
            "activity_type": (
                "Optional. Used to pre-classify the sales activity recorded against a generated task."
            ),
            "owner": (
                "Optional. Leave blank to have the generation run apply to whoever generates it."
            ),
            "default_offset_days": (
                "Days from the cycle anchor to each generated task's due date."
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["territory"].queryset = tenant_territories(self.tenant).order_by("name")
        self.fields["owner"].queryset = tenant_users(self.tenant).order_by("username")
        self._apply_target_and_cadence_rules()

    def _chosen(self, name):
        """The POSTed value on a bound form, else the rendered initial, else the instance value.

        Reading all three is what makes each rule hold on the first submit of a create form (POST),
        on a re-post (POST) and on a fresh render of an edit form (initial/instance) — the three
        moments a single-source check would miss.
        """
        if self.is_bound:
            return self.data.get(name)
        if name in self.initial:
            return self.initial.get(name)
        return getattr(self.instance, name, None)

    def _apply_target_and_cadence_rules(self):
        if self._chosen("target_type") == "territory":
            self.fields["territory"].help_text = TERRITORY_REQUIRED_HELP
            self.fields["territory"].required = True
        elif self._chosen("target_type"):
            self.fields["territory"].help_text = TERRITORY_NOT_APPLICABLE_HELP
            self.fields["territory"].disabled = True
            self.fields["territory"].required = False
        if self._chosen("cadence") == "once":
            interval = self.fields["cadence_interval"]
            interval.disabled = True
            interval.required = False
            interval.help_text = INTERVAL_LOCKED_HELP
            self.initial["cadence_interval"] = 1

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        elif self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The template must belong to this workspace.")
        _reject_foreign(self, cleaned, ["activity_type", "territory", "owner"])
        return cleaned


class TaskTemplateStepForm(TenantModelForm):
    """One ordered playbook step — the unit that becomes one ``crm.CrmTask`` on generation."""

    class Meta:
        model = TaskTemplateStep
        # `tenant` is excluded like every other form's; `template` is NOT — a step is only ever
        # created from inside the template it belongs to, and the view supplies it as initial.
        fields = ["order", "title", "instructions", "task_type", "priority", "offset_days"]
        widgets = {
            "instructions": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "What the rep should actually say and attach...",
            }),
            "offset_days": forms.NumberInput(attrs={
                "class": "form-input",
                "min": str(-MAX_STEP_OFFSET_DAYS), "max": str(MAX_STEP_OFFSET_DAYS), "step": "1",
            }),
        }
        help_texts = {
            "order": "The sequence this step runs in. Steps run in ascending order.",
            "offset_days": (
                f"Days from the cycle anchor. Negative means before it — a prep step two days "
                f"ahead uses -2. Between -{MAX_STEP_OFFSET_DAYS} and {MAX_STEP_OFFSET_DAYS}."
            ),
        }