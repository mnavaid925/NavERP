"""Accounting 2.2 General Ledger — Currencies views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Currency,
)
from apps.accounting.forms import (
    CurrencyForm,
)


# ============================================================ 2.2 GL — Currencies (global)
@login_required
def currency_list(request):
    return crud_list(
        request, Currency.objects.all(), "accounting/ledger/currency/list.html",
        search_fields=["code", "name"],
        filters=[("is_active", "is_active", False)],
    )


@tenant_admin_required
def currency_create(request):
    if request.method == "POST":
        form = CurrencyForm(request.POST)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("accounting:currency_list")
    else:
        form = CurrencyForm()
    return render(request, "accounting/ledger/currency/form.html", {"form": form, "is_edit": False})


@login_required
def currency_detail(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    return render(request, "accounting/ledger/currency/detail.html", {"obj": obj})


@tenant_admin_required
def currency_edit(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    if request.method == "POST":
        form = CurrencyForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Updated successfully.")
            return redirect("accounting:currency_list")
    else:
        form = CurrencyForm(instance=obj)
    return render(request, "accounting/ledger/currency/form.html", {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required
@require_POST
def currency_delete(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Deleted successfully.")
    return redirect("accounting:currency_list")
