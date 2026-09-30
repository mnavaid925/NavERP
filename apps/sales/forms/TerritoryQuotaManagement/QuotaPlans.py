"""Sales 8.7 — the quota-plan derivation form (`QPA-`).

This form records **how** a CRM quota target was derived — method, baseline, growth, relief,
uplift, phasing. It never edits the money: `quota_ref.target_amount` belongs to `crm.SalesQuota`,
and the two derived figures (`derived_baseline`, `derived_stretch_amount`) are **view-computed
context keys**, never stored columns. A second stored target is a second source of truth for the
same number (L37).

**OWNERSHIP (L29/L36/L37).** ``quota_ref`` is `crm.SalesQuota`` and ``territory`` is
`crm.Territory` — both CRM 1.2's, both read-only to 8.7 — and ``forecast_period`` is 8.4's
`sales.ForecastPeriod`, which is where the window, the period vocabulary and the reporting
currency are inherited from rather than re-spelled. 8.7 EXTENDS all three and declares none of
them again — see ``apps/sales/models/TerritoryQuotaManagement/__init__.py``.

Excluded from ``Meta.fields``, with the reason for each:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``, never from input.
* ``number`` — ``editable=False`` on ``TenantNumbered``; allocated by ``next_number`` (L22).
* ``status`` — **action-driven BY DECISION** (it is not ``editable=False``; it is simply off the
  form). Only the ``quota_plan_submit`` / ``_approve`` / ``_reject`` / ``_lock`` POST views move it,
  so a plan can never be typed straight into "approved" by hand. Mirrors ``scm.SalesOrder.status``
  being off its own form.
* ``submitted_by`` / ``submitted_at`` — **FROZEN EVIDENCE**, ``editable=False``; stamped by the
  submit view from ``request.user`` and ``timezone.now()`` (L22).
* ``approved_by`` / ``approved_at`` — **FROZEN EVIDENCE**, ``editable=False``; stamped by the
  approve view (L22).
* ``calculated_at`` — **FROZEN EVIDENCE**, ``editable=False``; written by the allocation path
  only, never by a form.
* ``created_at`` / ``updated_at`` — ``auto_now*`` stamps.

A plan in ``FROZEN_STATES`` (approved / locked) has **every field disabled** here, and
``locked_fields`` is exposed for the edit view to re-check the same rule server-side — a disabled
field is a UI affordance, not a guard.
"""
import json

from django import forms

from apps.crm.models import SalesQuota
from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod
from apps.sales.models.TerritoryQuotaManagement.QuotaPlans import PLAN_PARAMETER_KEYS, QuotaPlan

#: The `parameters` keys, read from the model's own allow-list so this help text cannot drift from
#: the dict the model validates against (the `AMOUNT_WIDGETS` pattern in 8.4). The union is taken
#: over every method, so a future method with its own keys shows up here for free.
PLAN_PARAMETER_KEY_LIST = ", ".join(sorted(set().union(*PLAN_PARAMETER_KEYS.values())))


class QuotaPlanForm(TenantUniqueMixin, TenantModelForm):
    """Record how one CRM quota target for one forecast period was derived."""

    class Meta:
        model = QuotaPlan
        # Excluded, with the reason for each — see the module docstring.
        fields = [
            "quota_ref",
            "forecast_period",
            "owner",
            "territory",
            "method",
            "allocation_basis",
            "baseline_source",
            "growth_target_pct",
            "attrition_relief_pct",
            "stretch_target_pct",
            "uplift_allowed",
            "target_type",
            "phasing",
            "parameters",
            "is_active",
            "notes",
        ]
        widgets = {
            "growth_target_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "attrition_relief_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "stretch_target_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "parameters": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 6,
                "placeholder": '{"seasonal_weights": [1, 2, 3, 4, 5, 6]}',
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "How this number was agreed, and with whom...",
            }),
        }
        help_texts = {
            "quota_ref": (
                "The CRM 1.2 quota this plan explains. 8.7 annotates the quota; it never writes "
                "the amount — the target is edited on the CRM quota, in CRM's form."
            ),
            "forecast_period": (
                "The 8.4 window this plan covers. It must be the SAME period as the quota: a "
                "mismatched pair is an attainment board quietly comparing Q2 against Q1."
            ),
            "territory": "Optional. When set it must match the territory on the quota itself.",
            "method": "A plan must declare its method. Uplift applies to a top-down plan only.",
            "baseline_source": "Previous period, previous year, or a custom baseline in parameters.",
            "growth_target_pct": "Percentage growth over the baseline.",
            "attrition_relief_pct": "Percentage set aside for attrition.",
            "stretch_target_pct": (
                "A percentage UPLIFT, not a second money column. Requires uplift to be allowed."
            ),
            "target_type": "What the CRM money number means. It adds no unit-count column.",
            "parameters": (
                "A JSON object. Allowed keys: "
                f"{PLAN_PARAMETER_KEY_LIST}. Unknown keys are ignored, so a plan written by a "
                "newer build still loads."
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # A None tenant must render EMPTY dropdowns. TenantModelForm only narrows when a tenant
        # is given, so without these two lines a tenant-less form would offer every quota and
        # every period in the platform (the ForecastSubmissionForm rule).
        if self.tenant is None:
            self.fields["quota_ref"].queryset = SalesQuota.objects.none()
            self.fields["forecast_period"].queryset = ForecastPeriod.objects.none()
        else:
            self.fields["quota_ref"].queryset = SalesQuota.objects.filter(
                tenant=self.tenant,
            ).order_by("-period_year", "period_number")
            self.fields["forecast_period"].queryset = ForecastPeriod.objects.filter(
                tenant=self.tenant,
            ).order_by("-period_year", "period_number", "name")
        # An edit otherwise renders the stored DICT as a Python repr — single quotes, `False` —
        # which is not valid JSON and not something a JSON textarea should ever show.
        if not self.is_bound and self.instance.pk and isinstance(self.instance.parameters, dict):
            self.initial["parameters"] = json.dumps(
                self.instance.parameters, indent=2, sort_keys=True,
            )
        # A frozen plan is fully read-only. Disabled, not hidden, so the reason stays on the page;
        # `locked_fields` is handed to the edit view so it can re-check the same rule server-side
        # (the ForecastSubmissionForm pattern) rather than trusting the widgets alone.
        self.locked_fields = []
        if self.instance.pk and self.instance.status in QuotaPlan.FROZEN_STATES:
            self.locked_fields = list(self.fields)
            for field_name in self.locked_fields:
                self.fields[field_name].disabled = True

    def clean_parameters(self):
        """``parameters`` must be a JSON **object** — the ``OrderValidationRule.parameters`` discipline.

        A bare string or a JSON array parses happily and would be handed to readers that call
        ``.get()`` on the blob, so it is refused here as a FIELD error the author sees and fixes,
        rather than becoming a 500 somewhere downstream.
        """
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
                    'Enter valid JSON, for example: {"cut_off_day": 15}'
                )
        if not isinstance(value, dict):
            raise forms.ValidationError(
                "Parameters must be a JSON object, for example: "
                f'{{"cut_off_day": 15}}. Allowed keys: {PLAN_PARAMETER_KEY_LIST}.'
            )
        return value

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        elif self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The quota plan must belong to this workspace.")
        # The dropdowns above are already narrowed; this catches a POST that bypasses the widget
        # and says WHY in the author's own terms. The period/owner cross-check between the quota
        # and the forecast window stays in the model's clean(), where both sides are named.
        _reject_foreign(self, cleaned, ["quota_ref", "forecast_period", "owner", "territory"])
        return cleaned
