"""Accounting 2.2 General Ledger — Currencies views (split from views.py/views_advanced.py)."""
from django.db.models import ProtectedError

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
    # SCM 4.10's `ReturnAuthorization.currency` is the ONLY PROTECT reference onto this global
    # master anywhere in the repo — every one of the twenty sibling currency FKs is SET_NULL — so
    # this bare delete became an uncaught ProtectedError (a 500) the moment any return existed in
    # that currency. Deleting a currency is an ordinary admin act, so it has to fail with a message.
    # Generic catch rather than an .exists() enumeration, matching the shape item/location/lot use.
    try:
        with transaction.atomic():
            write_audit_log(request.user, obj, "delete")
            obj.delete()
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"This currency is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "deactivate it instead.")
        return redirect("accounting:currency_list")
    messages.success(request, "Deleted successfully.")
    return redirect("accounting:currency_list")
