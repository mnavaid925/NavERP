"""Procurement 6.15 Budget & Cost Management — CostForecast form.

One shape: ``CostForecastForm``, the INPUTS of a forecast. The three amount columns
(``committed_amount`` / ``historical_amount`` / ``forecast_amount``) are deliberately NOT fields
here: they are stamped by the create view through ``compute_forecast_amounts``, and a hand-typed
figure would be a projection with no computation behind it — the same reason the model marks them
``editable=False`` and there is no edit page at all.

Excluded, each deliberately:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / the create view.
* ``number`` — assigned once by ``TenantNumbered.save()`` (FCST-#####).
* ``created_by`` — the authorship stamp, set from ``request.user`` on create only.
* ``created_at`` / ``updated_at`` — the base timestamps.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly (see the
# BudgetMappings form module for the reason).
from apps.procurement.models.BudgetCostManagement.CostForecasts import CostForecast


class CostForecastForm(TenantUniqueMixin, TenantModelForm):
    """The inputs of one forecast. Amounts are computed, never typed — see the module docstring.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``CostForecast.clean()`` compares the chosen budget's tenant against
    ``self.tenant_id``, and without the stamp every CREATE would be falsely rejected.
    """

    class Meta:
        model = CostForecast
        fields = ["name", "budget", "method", "horizon_months", "as_of", "currency",
                  "assumptions"]
        widgets = {
            "assumptions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "as_of": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            self.fields["budget"].queryset = self.fields["budget"].queryset.none()
            return

        from apps.accounting.models import Budget

        self.fields["budget"].queryset = (
            Budget.objects.filter(tenant=tenant).select_related("fiscal_period").order_by("-id"))
        self.fields["budget"].empty_label = "- whole workspace -"
        # ``currency`` is a GLOBAL table (no tenant column) — TenantModelForm leaves it alone,
        # and the narrowing is active-only ordering, not a tenancy boundary.
        from apps.accounting.models import Currency

        self.fields["currency"].queryset = (
            Currency.objects.filter(is_active=True).order_by("code"))
        self.fields["currency"].empty_label = "- not labelled -"

    def clean(self):
        cleaned = super().clean()
        # The budget FK is the only tenant-scoped choice on this form; a crafted POST naming
        # another workspace's budget becomes a field error here, not a leaked row.
        _reject_foreign(self, cleaned, ["budget"])
        return cleaned
