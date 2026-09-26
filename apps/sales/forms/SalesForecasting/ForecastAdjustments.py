"""8.4 Sales Forecasting — ForecastAdjustment forms.

``tenant``, ``number``, ``created_by``, ``original_value`` / ``original_category`` (the
system snapshot), ``is_reverted``, ``reverted_at`` and ``revert_reason`` are all absent from
``Meta.fields``. The snapshot pair in particular is the point: the user enters the applied
delta, never the "before" figure, so a forged override cannot rewrite what the system said.

Two rulings are enforced server-side rather than in the template:

* ``adjustment_kind`` is ``disabled=True`` and pinned to ``"direct"`` on create. An
  ``indirect`` row is system-written and a ``revert`` row is written by the Reset action --
  a hand-typed kind is exactly the audit-trail forgery the guard exists to stop (4.3).
* ``reason_code`` is required, and the ``target_field`` / ``adjusted_value`` /
  ``adjusted_category`` coherence is re-checked in ``clean()`` so hiding a field in
  ``__init__`` is never the only protection.
"""
from decimal import Decimal

from django import forms

from apps.crm.models import Opportunity
from apps.sales.forms._common import TenantActionForm, TenantModelForm, _reject_foreign
from apps.sales.models.OpportunityPipeline.Pipelines import OpportunityPipelinePlacement
from apps.sales.models.SalesForecasting.ForecastAdjustments import ForecastAdjustment
from apps.sales.models.SalesForecasting.ForecastSubmissions import ForecastSubmission


def _bounded(queryset, limit=500):
    """A ``[:500]``-bounded list of ids, then the queryset itself.

    The ``AccountPlanForm`` pattern: an unbounded submission / opportunity dropdown is a
    page-weight bug, and slicing a queryset the form then re-filters on would evaluate the
    whole table anyway.
    """
    ids = list(queryset.values_list("pk", flat=True)[:limit])
    return queryset.filter(pk__in=ids)


class ForecastAdjustmentForm(TenantModelForm):
    """The manager override. Reason mandatory, kind system-owned."""

    class Meta:
        model = ForecastAdjustment
        fields = [
            "submission", "opportunity", "placement", "adjustment_kind",
            "target_field", "adjusted_value", "adjusted_category",
            "reason_code", "note",
        ]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3}),
            "adjusted_value": forms.NumberInput(attrs={"step": "0.01"}),
        }

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.user = user
        if tenant is None:
            for field_name in ("submission", "opportunity", "placement"):
                self.fields[field_name].queryset = self.fields[field_name].queryset.none()
        else:
            self.fields["submission"].queryset = _bounded(
                ForecastSubmission.objects.filter(tenant=tenant).select_related(
                    "period", "owner",
                ).order_by("-period__period_year", "period__period_number", "number")
            )
            self.fields["opportunity"].queryset = _bounded(
                Opportunity.objects.filter(tenant=tenant).order_by("name")
            )
            self.fields["placement"].queryset = _bounded(
                OpportunityPipelinePlacement.objects.filter(tenant=tenant).select_related(
                    "pipeline", "current_stage",
                ).order_by("opportunity_id")
            )
        # A hand-typed kind is the audit-trail forgery. On create it is pinned to "direct";
        # on edit it is shown read-only so an existing row's kind is never re-typed.
        self.fields["adjustment_kind"].disabled = True
        if not self.instance.pk:
            self.fields["adjustment_kind"].initial = "direct"
        # Only the field pair the chosen target_field actually uses is shown; clean()
        # re-checks the pairing so a tampered POST is still refused.
        if self._selected_target_field() == "amount":
            self.fields["adjusted_category"].widget = forms.HiddenInput()
            self.fields["adjusted_category"].required = False
        else:
            self.fields["adjusted_value"].widget = forms.HiddenInput()
            self.fields["adjusted_value"].required = False

    def _selected_target_field(self):
        """The target_field governing this render -- POST first, then the bound instance."""
        if self.is_bound and self.data.get("target_field"):
            return self.data.get("target_field")
        if self.instance.pk:
            return self.instance.target_field
        return self.initial.get("target_field") or "category"


    def clean(self):
        cleaned = super().clean()
        if self.tenant is None:
            self.add_error(None, "A tenant workspace is required.")
        reason_code = (cleaned.get("reason_code") or "").strip()
        if not reason_code:
            self.add_error("reason_code", "An adjustment requires a reason code.")
        elif reason_code not in dict(ForecastAdjustment.REASON_CODE_CHOICES):
            self.add_error("reason_code", "That reason code is not recognised.")
        _reject_foreign(self, cleaned, ["submission", "opportunity", "placement"])
        target_field = cleaned.get("target_field")
        adjusted_value = cleaned.get("adjusted_value")
        adjusted_category = cleaned.get("adjusted_category")
        if target_field == "amount":
            if adjusted_value is None:
                self.add_error(
                    "adjusted_value", "An amount override must carry the applied amount.",
                )
            if adjusted_category:
                self.add_error(
                    "adjusted_category", "An amount override cannot also carry a category.",
                )
        elif target_field == "category":
            if not adjusted_category:
                self.add_error(
                    "adjusted_category", "A category override must choose a forecast category.",
                )
            if adjusted_value is not None:
                self.add_error(
                    "adjusted_value", "A category override cannot also carry an amount.",
                )
        else:
            self.add_error("target_field", "That target field is not recognised.")
        if adjusted_value is not None and Decimal(adjusted_value) < 0:
            self.add_error("adjusted_value", "The applied amount cannot be negative.")
        # A placement belongs to exactly one opportunity; naming both must agree.
        opportunity = cleaned.get("opportunity")
        placement = cleaned.get("placement")
        if opportunity is not None and placement is not None:
            if placement.opportunity_id != opportunity.pk:
                self.add_error("placement", "That placement belongs to a different opportunity.")
        submission = cleaned.get("submission")
        if submission is not None and submission.period_id and submission.period.is_locked:
            self.add_error(None, "This period is locked, so its forecast calls are read-only.")
        return cleaned


class ForecastRevertForm(TenantActionForm):
    """The mandatory-reason Reset (Dynamics). ``revert_reason`` is never optional."""

    revert_reason = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-input", "maxlength": 255}),
    )

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("revert_reason") or "").strip():
            self.add_error("revert_reason", "A Reset must say why.")
        return cleaned
