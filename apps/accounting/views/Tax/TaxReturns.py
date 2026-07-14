"""Accounting 2.11 Tax — TaxReturns views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    TaxCode,
    TaxReturn,
)
from apps.accounting.forms import (
    TaxReturnForm,
)


@login_required
def tax_return_list(request):
    return crud_list(
        request, TaxReturn.objects.filter(tenant=request.tenant).select_related("tax_code"),
        "accounting/tax/return/list.html",
        search_fields=["number", "tax_code__name"],
        filters=[("status", "status", False), ("tax_code", "tax_code_id", True)],
        extra_context={"status_choices": TaxReturn.STATUS_CHOICES,
                       "tax_codes": TaxCode.objects.filter(tenant=request.tenant)},
    )


@login_required
def tax_return_create(request):
    return crud_create(request, form_class=TaxReturnForm, template="accounting/tax/return/form.html",
                       success_url="accounting:tax_return_list")


@login_required
def tax_return_detail(request, pk):
    obj = get_object_or_404(TaxReturn.objects.select_related("tax_code"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/tax/return/detail.html", {"obj": obj})


@tenant_admin_required
def tax_return_edit(request, pk):
    return crud_edit(request, model=TaxReturn, pk=pk, form_class=TaxReturnForm,
                     template="accounting/tax/return/form.html", success_url="accounting:tax_return_list")


@tenant_admin_required
@require_POST
def tax_return_delete(request, pk):
    return crud_delete(request, model=TaxReturn, pk=pk, success_url="accounting:tax_return_list")
