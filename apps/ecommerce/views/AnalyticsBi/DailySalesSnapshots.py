from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.AnalyticsBi.DailySalesSnapshots import DailySalesSnapshotForm
from apps.ecommerce.models.AnalyticsBi.DailySalesSnapshots import DailySalesSnapshot
from apps.ecommerce.views._common import ecommerce_object


@login_required
def dailysalessnapshot_list(request):
    qs = DailySalesSnapshot.objects.filter(tenant=request.tenant)

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(currency__icontains=query)
            | Q(notes__icontains=query)
        )

    selected_currency = request.GET.get("currency", "").strip()
    if selected_currency:
        qs = qs.filter(currency__iexact=selected_currency)

    selected_finalized = request.GET.get("is_finalized", "").strip().lower()
    if selected_finalized in ("1", "true", "yes"):
        qs = qs.filter(is_finalized=True)
    elif selected_finalized in ("0", "false", "no"):
        qs = qs.filter(is_finalized=False)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "ecommerce/analytics_bi/daily_sales_snapshot/list.html",
        {
            "snapshots": page_obj,
            "selected_currency": selected_currency,
            "selected_finalized": selected_finalized,
            "query": query,
            "page_obj": page_obj,
            "paginator": paginator,
        },
    )


@login_required
def dailysalessnapshot_detail(request, pk):
    snapshot = ecommerce_object(request, DailySalesSnapshot, pk)
    return render(
        request,
        "ecommerce/analytics_bi/daily_sales_snapshot/detail.html",
        {"snapshot": snapshot},
    )


@login_required
def dailysalessnapshot_create(request):
    if request.method == "POST":
        form = DailySalesSnapshotForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            snapshot = form.save(commit=False)
            snapshot.tenant = request.tenant
            snapshot.save()
            write_audit_log(
                request.tenant,
                request.user,
                "CREATE",
                "DailySalesSnapshot",
                snapshot.pk,
                f"Created daily sales snapshot {snapshot.number} for {snapshot.snapshot_date}",
            )
            messages.success(request, f"Daily sales snapshot {snapshot.number} created successfully.")
            return redirect("ecommerce:dailysalessnapshot_detail", pk=snapshot.pk)
    else:
        form = DailySalesSnapshotForm(
            tenant=request.tenant,
            initial={"snapshot_date": timezone.now().date(), "currency": "USD"},
        )

    return render(
        request,
        "ecommerce/analytics_bi/daily_sales_snapshot/form.html",
        {"form": form, "snapshot": None},
    )


@login_required
def dailysalessnapshot_edit(request, pk):
    snapshot = ecommerce_object(request, DailySalesSnapshot, pk)
    if request.method == "POST":
        form = DailySalesSnapshotForm(request.POST, instance=snapshot, tenant=request.tenant)
        if form.is_valid():
            snapshot = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "UPDATE",
                "DailySalesSnapshot",
                snapshot.pk,
                f"Updated daily sales snapshot {snapshot.number}",
            )
            messages.success(request, f"Daily sales snapshot {snapshot.number} updated successfully.")
            return redirect("ecommerce:dailysalessnapshot_detail", pk=snapshot.pk)
    else:
        form = DailySalesSnapshotForm(instance=snapshot, tenant=request.tenant)

    return render(
        request,
        "ecommerce/analytics_bi/daily_sales_snapshot/form.html",
        {"form": form, "snapshot": snapshot},
    )


@require_POST
@login_required
@tenant_admin_required
def dailysalessnapshot_delete(request, pk):
    snapshot = ecommerce_object(request, DailySalesSnapshot, pk)
    number = snapshot.number
    snapshot.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "DELETE",
        "DailySalesSnapshot",
        pk,
        f"Deleted daily sales snapshot {number}",
    )
    messages.success(request, f"Daily sales snapshot {number} was deleted.")
    return redirect("ecommerce:dailysalessnapshot_list")


@require_POST
@login_required
def dailysalessnapshot_generate(request):
    """Triggers recalculation and aggregation of today's sales snapshot."""
    today = timezone.now().date()
    snapshot = DailySalesSnapshot.aggregate_for_tenant_date(request.tenant, today)
    write_audit_log(
        request.tenant,
        request.user,
        "GENERATE",
        "DailySalesSnapshot",
        snapshot.pk,
        f"Generated sales aggregation snapshot for {today}",
    )
    messages.success(
        request,
        f"Sales snapshot for {today} generated: {snapshot.orders_count} orders, {snapshot.currency} {snapshot.net_sales} net sales.",
    )
    return redirect("ecommerce:dailysalessnapshot_detail", pk=snapshot.pk)
