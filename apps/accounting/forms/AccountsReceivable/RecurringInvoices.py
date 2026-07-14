"""Accounting 2.4 Accounts Receivable — RecurringInvoices forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    RecurringInvoice,
)


class RecurringInvoiceForm(TenantModelForm):
    class Meta:
        model = RecurringInvoice
        # `number`, `next_run_date` default + advance, `last_generated_at`, `occurrences_generated`
        # are system-managed; `party` is scoped to customers below.
        fields = ["party", "description", "amount", "currency", "payment_terms", "cadence",
                  "start_date", "next_run_date", "status", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        self.fields["next_run_date"].required = False  # create: defaults to start_date in model.save()
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer").distinct()
            )

    def clean_next_run_date(self):
        # On edit, a blank Next Run keeps the schedule's current value rather than rewinding it
        # (review F2). On create (no pk) blank falls through to the start-date default in save().
        val = self.cleaned_data.get("next_run_date")
        if not val and self.instance and self.instance.pk:
            return self.instance.next_run_date
        return val
