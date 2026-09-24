"""CRM 1.2 Sales Force Automation — Opportunities forms (split from apps/crm/forms.py)."""
from django import forms
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError

from apps.accounting.models import Currency
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Opportunity,
    OpportunitySplit,
)


def _sales_model(model_name):
    try:
        return django_apps.get_model("sales", model_name)
    except LookupError:
        return None


def _sales_model_has_rows(model_name, instance, tenant):
    model = _sales_model(model_name)
    if model is None or tenant is None or not instance.pk:
        return False
    return model.objects.filter(tenant=tenant, opportunity_id=instance.pk).exists()


def _submitted_value_matches(form, field_name):
    if field_name not in form.data:
        return True
    try:
        submitted = form.fields[field_name].to_python(form.data.get(field_name))
    except ValidationError:
        return False
    return submitted == getattr(form.instance, field_name, None)


class OpportunityForm(TenantModelForm):
    class Meta:
        model = Opportunity
        fields = ["name", "account", "primary_contact", "stage", "forecast_category", "amount",
                  "probability", "close_date", "competitor", "loss_reason", "territory", "owner",
                  "source_lead", "campaign", "next_step", "description", "next_step_due_date",
                  "currency"]

    def __init__(self, *args, **kwargs):
        self.pipeline_managed = False
        self.competitor_managed = False
        self.loss_reason_managed = False
        super().__init__(*args, **kwargs)
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")
        self.fields["next_step_due_date"].widget = forms.DateInput(
            attrs={"type": "date", "class": "form-input"},
            format="%Y-%m-%d",
        )
        self.fields["next_step_due_date"].input_formats = ["%Y-%m-%d"]
        tenant = self.tenant or getattr(self.instance, "tenant", None)
        if self.instance.pk and tenant is not None:
            self.pipeline_managed = _sales_model_has_rows(
                "OpportunityPipelinePlacement", self.instance, tenant
            )
            self.competitor_managed = _sales_model_has_rows(
                "OpportunityCompetitor", self.instance, tenant
            )
            self.loss_reason_managed = _sales_model_has_rows(
                "OpportunityOutcome", self.instance, tenant
            )
        if self.pipeline_managed:
            for field_name in ("stage", "probability", "forecast_category"):
                self.fields[field_name].disabled = True
                self.fields[field_name].help_text = (
                    "Managed in the Sales workspace; change the pipeline there."
                )
        if self.competitor_managed:
            self.fields["competitor"].disabled = True
            self.fields["competitor"].help_text = (
                "Structured competitor data exists in the Sales workspace."
            )
        if self.loss_reason_managed:
            self.fields["loss_reason"].disabled = True
            self.fields["loss_reason"].help_text = (
                "Structured win/loss outcomes exist in the Sales workspace."
            )

    def clean(self):
        cleaned = super().clean()
        if self.pipeline_managed:
            if any(
                not _submitted_value_matches(self, field_name)
                for field_name in ("stage", "probability", "forecast_category")
            ):
                self.add_error(
                    None,
                    "Stage, probability, and forecast category are managed in the Sales workspace.",
                )
        if self.competitor_managed and not _submitted_value_matches(self, "competitor"):
            self.add_error(None, "Competitor data is managed in the Sales workspace.")
        if self.loss_reason_managed and not _submitted_value_matches(self, "loss_reason"):
            self.add_error(None, "Loss reason data is managed in the Sales workspace.")
        return cleaned


class OpportunitySplitForm(TenantModelForm):
    """Inline on the opportunity detail page; tenant/opportunity set in the view."""

    class Meta:
        model = OpportunitySplit
        fields = ["user", "split_type", "percentage", "notes"]
