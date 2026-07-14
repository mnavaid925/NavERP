"""Accounting 2.5 Cash Management — BankAccounts views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    BankAccount,
    Currency,
)
from apps.accounting.forms import (
    BankAccountForm,
)


# ============================================================== 2.5 Cash — Bank accounts
@login_required
def bank_account_list(request):
    return crud_list(
        request, BankAccount.objects.filter(tenant=request.tenant).select_related("currency", "gl_account"),
        "accounting/cash/bank_account/list.html",
        search_fields=["name", "bank_name"],
        filters=[("currency", "currency_id", True), ("is_active", "is_active", False)],
        extra_context={"currencies": Currency.objects.filter(is_active=True)},
    )


@login_required
def bank_account_create(request):
    return crud_create(request, form_class=BankAccountForm, template="accounting/cash/bank_account/form.html",
                       success_url="accounting:bank_account_list")


@login_required
def bank_account_detail(request, pk):
    obj = get_object_or_404(BankAccount.objects.select_related("currency", "gl_account"),
                            pk=pk, tenant=request.tenant)
    return render(request, "accounting/cash/bank_account/detail.html", {
        "obj": obj,
        "transactions": obj.transactions.all()[:10],
        "current_balance": obj.current_balance(),
    })


@login_required
def bank_account_edit(request, pk):
    return crud_edit(request, model=BankAccount, pk=pk, form_class=BankAccountForm,
                     template="accounting/cash/bank_account/form.html", success_url="accounting:bank_account_list")


@login_required
@require_POST
def bank_account_delete(request, pk):
    return crud_delete(request, model=BankAccount, pk=pk, success_url="accounting:bank_account_list")
