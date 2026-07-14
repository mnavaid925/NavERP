"""Accounting 2.11 Tax — TaxCodes views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    TaxCode,
)
from apps.accounting.forms import (
    TaxCodeForm,
)


# ============================================================================ 2.11 Tax
@login_required
def tax_code_list(request):
    return crud_list(
        request, TaxCode.objects.filter(tenant=request.tenant),
        "accounting/tax/code/list.html",
        search_fields=["name", "jurisdiction"],
        filters=[("tax_type", "tax_type", False), ("is_active", "is_active", False)],
        extra_context={"tax_type_choices": TaxCode.TAX_TYPE_CHOICES},
    )


@login_required
def tax_code_create(request):
    return crud_create(request, form_class=TaxCodeForm, template="accounting/tax/code/form.html",
                       success_url="accounting:tax_code_list")


@login_required
def tax_code_detail(request, pk):
    obj = get_object_or_404(TaxCode.objects.select_related("payable_account"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/tax/code/detail.html", {"obj": obj, "returns": obj.returns.all()[:5]})


@login_required
def tax_code_edit(request, pk):
    return crud_edit(request, model=TaxCode, pk=pk, form_class=TaxCodeForm,
                     template="accounting/tax/code/form.html", success_url="accounting:tax_code_list")


@login_required
@require_POST
def tax_code_delete(request, pk):
    return crud_delete(request, model=TaxCode, pk=pk, success_url="accounting:tax_code_list")
