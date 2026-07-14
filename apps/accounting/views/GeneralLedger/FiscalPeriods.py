"""Accounting 2.2 General Ledger — FiscalPeriods views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    FiscalPeriod,
)
from apps.accounting.forms import (
    FiscalPeriodForm,
)


# ============================================================== 2.2 GL — Fiscal periods
@login_required
def fiscal_period_list(request):
    return crud_list(
        request, FiscalPeriod.objects.filter(tenant=request.tenant),
        "accounting/ledger/fiscal_period/list.html",
        search_fields=["name"],
        filters=[("status", "status", False), ("period_type", "period_type", False)],
        extra_context={"status_choices": FiscalPeriod.STATUS_CHOICES,
                       "period_type_choices": FiscalPeriod.PERIOD_TYPE_CHOICES},
    )


@login_required
def fiscal_period_create(request):
    return crud_create(request, form_class=FiscalPeriodForm, template="accounting/ledger/fiscal_period/form.html",
                       success_url="accounting:fiscal_period_list")


@login_required
def fiscal_period_detail(request, pk):
    obj = get_object_or_404(FiscalPeriod.objects.select_related("closed_by"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/ledger/fiscal_period/detail.html", {
        "obj": obj,
        "entry_count": obj.journal_entries.count(),
    })


@login_required
def fiscal_period_edit(request, pk):
    return crud_edit(request, model=FiscalPeriod, pk=pk, form_class=FiscalPeriodForm,
                     template="accounting/ledger/fiscal_period/form.html", success_url="accounting:fiscal_period_list")


@login_required
@require_POST
def fiscal_period_delete(request, pk):
    return crud_delete(request, model=FiscalPeriod, pk=pk, success_url="accounting:fiscal_period_list")


@tenant_admin_required
@require_POST
def fiscal_period_close(request, pk):
    period = get_object_or_404(FiscalPeriod, pk=pk, tenant=request.tenant)
    if period.status != "open":
        messages.info(request, "This period is not open.")
        return redirect("accounting:fiscal_period_detail", pk=pk)
    draft = period.journal_entries.filter(status__in=["draft", "pending_approval"]).count()
    if draft:
        messages.error(request, f"Cannot close: {draft} unposted journal entr{'y' if draft == 1 else 'ies'} remain in this period.")
        return redirect("accounting:fiscal_period_detail", pk=pk)
    period.status = "closed"
    period.closed_by = request.user
    period.closed_at = timezone.now()
    period.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    write_audit_log(request.user, period, "update", {"action": "close_period"})
    messages.success(request, f"{period.name} closed.")
    return redirect("accounting:fiscal_period_detail", pk=pk)
