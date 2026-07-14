"""Accounting 2.2 General Ledger — GLAccounts views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    GLAccount,
)
from apps.accounting.forms import (
    GLAccountForm,
)


# ============================================================ 2.2 GL — Chart of Accounts
@login_required
def glaccount_list(request):
    return crud_list(
        request, GLAccount.objects.filter(tenant=request.tenant).select_related("parent"),
        "accounting/ledger/glaccount/list.html",
        search_fields=["code", "name"],
        filters=[("account_type", "account_type", False), ("is_active", "is_active", False)],
        extra_context={"account_type_choices": GLAccount.ACCOUNT_TYPE_CHOICES},
    )


@login_required
def glaccount_create(request):
    return crud_create(request, form_class=GLAccountForm, template="accounting/ledger/glaccount/form.html",
                       success_url="accounting:glaccount_list")


@login_required
def glaccount_detail(request, pk):
    obj = get_object_or_404(GLAccount.objects.select_related("parent"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/ledger/glaccount/detail.html", {
        "obj": obj,
        "children": obj.children.all(),
        "balance": obj.balance(),
        "has_lines": obj.journal_lines.exists(),
    })


@login_required
def glaccount_edit(request, pk):
    return crud_edit(request, model=GLAccount, pk=pk, form_class=GLAccountForm,
                     template="accounting/ledger/glaccount/form.html", success_url="accounting:glaccount_list")


@login_required
@require_POST
def glaccount_delete(request, pk):
    obj = get_object_or_404(GLAccount, pk=pk, tenant=request.tenant)
    if obj.journal_lines.exists():
        messages.error(request, "Cannot delete an account that has posted journal lines.")
        return redirect("accounting:glaccount_detail", pk=pk)
    return crud_delete(request, model=GLAccount, pk=pk, success_url="accounting:glaccount_list")
