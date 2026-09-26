"""8.4 Sales Forecasting — ForecastSubmission form.

``status``, ``tenant``, ``number``, ``submitted_by`` / ``reviewed_by`` / ``submitted_at`` /
``reviewed_at`` and the whole ``ai_*`` block are absent from ``Meta.fields``. The three
snapshot amounts (``weighted_amount`` / ``quota_amount`` / ``actual_amount``) are absent
too: they are service-written, and a user typing one is the drift bug the derived-vs-stored
ruling exists to prevent.

Server-side is the only real guard. A locked period, an approved call and a tampered POST
are all refused in ``clean()`` through ``self.locked_fields`` — the ``PipelineStageForm``
pattern — so hiding the Edit button is never the only protection (R9).
"""
from decimal import Decimal

from django import forms

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.crm.models import SalesQuota, Territory
from apps.sales.forms._common import TenantActionForm, TenantModelForm, _reject_foreign
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod
from apps.sales.models.SalesForecasting.ForecastSubmissions import (
    CATEGORY_AMOUNT_FIELDS,
    ForecastSubmission,
)

#: Money inputs get a step and a floor; the browser is the first guard, ``clean()`` the real one.
AMOUNT_WIDGETS = {
    name: forms.NumberInput(attrs={"step": "0.01", "min": "0"})
    for _category, name in CATEGORY_AMOUNT_FIELDS
}


def _bounded(queryset, limit=500):
    """A ``[:500]``-bounded list of ids, then the queryset itself.

    The ``AccountPlanForm`` pattern: an unbounded user / territory / org-unit dropdown is a
    page-weight bug, and slicing a queryset the form then re-filters on would evaluate the
    whole table anyway.
    """
    ids = list(queryset.values_list("pk", flat=True)[:limit])
    return queryset.filter(pk__in=ids)


class ForecastSubmissionForm(TenantModelForm):
    class Meta:
        model = ForecastSubmission
        fields = [
            "period", "owner", "org_unit", "territory", "pipeline", "quota_ref",
            "omitted_amount", "pipeline_amount", "best_case_amount",
            "commit_amount", "closed_amount", "review_note", "notes",
        ]
        widgets = {
            "review_note": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            **AMOUNT_WIDGETS,
        }

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.user = user
        self.locked_fields = []
        if tenant is None:
            for field_name in ("period", "owner", "org_unit", "territory", "pipeline", "quota_ref"):
                self.fields[field_name].queryset = self.fields[field_name].queryset.none()
        else:
            self.fields["period"].queryset = _bounded(
                ForecastPeriod.objects.filter(tenant=tenant).order_by(
                    "-period_year", "period_number", "name",
                )
            )
            self.fields["owner"].queryset = _bounded(
                User.objects.filter(tenant=tenant, is_active=True).order_by("username")
            )
            self.fields["org_unit"].queryset = _bounded(
                OrgUnit.objects.filter(tenant=tenant).order_by("name")
            )
            self.fields["territory"].queryset = _bounded(
                Territory.objects.filter(tenant=tenant, is_active=True).order_by("name")
            )
            self.fields["pipeline"].queryset = _bounded(
                Pipeline.objects.filter(tenant=tenant, is_active=True).order_by("name")
            )
            # 8.4 only READS crm.SalesQuota (quota design is 8.7's) and snapshots it by value.
            self.fields["quota_ref"].queryset = _bounded(
                SalesQuota.objects.filter(tenant=tenant).order_by("-period_year", "period_number")
            )
        # A non-admin forecasts their own call: owner is pinned to them and disabled, and a
        # crafted POST cannot move it (the same narrowing AccountPlanForm applies).
        if user is not None and not (
            getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False)
        ):
            self.fields["owner"].queryset = User.objects.filter(
                pk=user.pk, tenant=tenant, is_active=True,
            )
            self.fields["owner"].disabled = True
            if not self.instance.pk:
                self.initial["owner"] = user.pk
        # A frozen record is fully read-only: every field disabled AND re-checked in clean().
        if self.instance.pk and self.instance.is_frozen:
            self.locked_fields = list(self.fields)
            for field_name in self.locked_fields:
                self.fields[field_name].disabled = True

    def _locked_value(self, field_name, expected):
        """What the POST claims for a frozen field, compared to what is stored.

        Decimals are compared numerically, not as strings: a browser posts ``1000.5`` for a
        stored ``1000.50`` and a string compare would raise a false "cannot be changed"
        error on a record the user did nothing wrong to.
        """
        submitted = self.data.get(field_name)
        if isinstance(expected, bool):
            submitted = forms.CheckboxInput().value_from_datadict(
                self.data, self.files, field_name,
            )
            return bool(submitted) == expected
        if isinstance(expected, Decimal) and submitted not in (None, ""):
            try:
                return Decimal(str(submitted)) == expected
            except (ArithmeticError, ValueError, TypeError):
                return False
        expected_value = expected.pk if hasattr(expected, "pk") else expected
        return str(submitted or "") == str(expected_value or "")

    def clean(self):
        cleaned = super().clean()
        if self.tenant is None:
            self.add_error(None, "A tenant workspace is required.")
        for field_name in self.locked_fields:
            if not self._locked_value(field_name, getattr(self.instance, field_name)):
                self.add_error(field_name, "This field cannot be changed for the current record.")
        _reject_foreign(self, cleaned, ["period", "owner", "org_unit", "territory", "pipeline", "quota_ref"])
        for _category, field_name in CATEGORY_AMOUNT_FIELDS:
            value = cleaned.get(field_name)
            if value is not None and value < 0:
                self.add_error(field_name, "An amount cannot be negative.")
        period = cleaned.get("period")
        if period is not None and period.is_locked and self.instance.pk:
            self.add_error(None, "This period is locked, so the forecast call is read-only.")
        elif self.instance.pk and self.instance.status in ForecastSubmission.FROZEN_STATES:
            self.add_error(None, f"A {self.instance.get_status_display().lower()} forecast call is read-only.")
        elif self.instance.pk and self.instance.status == "submitted":
            self.add_error(None, "A submitted forecast call is read-only until it is reviewed.")
        # The (tenant, period, owner) uniqueness a NULL-tolerant DB constraint could never
        # give us. The model's clean() also enforces it; this surfaces it as a form error.
        owner = cleaned.get("owner")
        if period is not None and self.tenant is not None:
            siblings = ForecastSubmission.objects.filter(
                tenant=self.tenant, period=period,
            ).exclude(pk=self.instance.pk)
            siblings = (
                siblings.filter(owner=owner) if owner is not None
                else siblings.filter(owner__isnull=True)
            )
            if siblings.exists():
                self.add_error("owner", "This workspace already has a forecast call for that owner and period.")
        return cleaned


class ForecastReviewForm(TenantActionForm):
    """The note on approve / reject. Required when rejecting, optional when approving."""

    note = forms.CharField(
        required=False,
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
    )

    def __init__(self, *args, tenant=None, approved=True, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.approved = approved
        # The declarative `required` is the whole rule. A clean() re-check on top of it
        # produced a SECOND error for the same blank field ("This field is required."
        # plus "A rejection must say why."), so the user saw one mistake twice.
        self.fields["note"].required = not approved

