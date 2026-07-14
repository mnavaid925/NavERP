"""Accounting 2.2 General Ledger — ExchangeRates views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Currency,
    ExchangeRate,
)
from apps.accounting.forms import (
    ExchangeRateForm,
)


# --------------------------------------------------------------- Exchange rates
@login_required
def exchange_rate_list(request):
    return crud_list(
        request, ExchangeRate.objects.filter(tenant=request.tenant).select_related("currency"),
        "accounting/ledger/exchange_rate/list.html",
        search_fields=["currency__code"],
        filters=[("currency", "currency_id", True), ("source", "source", False)],
        extra_context={"currencies": Currency.objects.filter(is_active=True),
                       "source_choices": ExchangeRate.SOURCE_CHOICES},
    )


@login_required
def exchange_rate_create(request):
    return crud_create(request, form_class=ExchangeRateForm, template="accounting/ledger/exchange_rate/form.html",
                       success_url="accounting:exchange_rate_list")


@login_required
def exchange_rate_detail(request, pk):
    obj = get_object_or_404(ExchangeRate.objects.select_related("currency"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/ledger/exchange_rate/detail.html", {"obj": obj})


@login_required
def exchange_rate_edit(request, pk):
    return crud_edit(request, model=ExchangeRate, pk=pk, form_class=ExchangeRateForm,
                     template="accounting/ledger/exchange_rate/form.html", success_url="accounting:exchange_rate_list")


@login_required
@require_POST
def exchange_rate_delete(request, pk):
    return crud_delete(request, model=ExchangeRate, pk=pk, success_url="accounting:exchange_rate_list")
