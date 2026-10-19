"""Sales 8.12 — Views for `FunnelConversionRecord`.

Function-based views over the 8.12 Funnel Conversion Record. Every queryset is
tenant-scoped, every write is audit-logged, and every integer FK filter is
guarded with ``.isdigit()`` so a hand-edited URL is ignored rather than a 500
(L11).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Territory
from apps.sales.forms.SalesAnalytics.FunnelConversionRecords import FunnelConversionRecordForm
from apps.sales.models.OpportunityPipeline.Pipelines import PipelineStage
from apps.sales.models.SalesAnalytics.FunnelConversionRecords import (
    FUNNEL_SCOPE_CHOICES,
    FunnelConversionRecord,
)


@login_required
def funnel_conversion_record_list(request):
    qs = FunnelConversionRecord.objects.filter(tenant=request.tenant).select_related(
        "from_stage",
        "to_stage",
        "territory",
        "owner",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(label__icontains=q)
            | Q(number__icontains=q)
            | Q(source_channel__icontains=q)
            | Q(notes__icontains=q)
        )

    scope = request.GET.get("funnel_scope", "").strip()
    if scope:
        qs = qs.filter(funnel_scope=scope)

    from_id = request.GET.get("from_stage", "").strip()
    if from_id and from_id.isdigit():
        qs = qs.filter(from_stage_id=int(from_id))

    to_id = request.GET.get("to_stage", "").strip()
    if to_id and to_id.isdigit():
        qs = qs.filter(to_stage_id=int(to_id))

    territory_id = request.GET.get("territory", "").strip()
    if territory_id and territory_id.isdigit():
        qs = qs.filter(territory_id=int(territory_id))

    owner_id = request.GET.get("owner", "").strip()
    if owner_id and owner_id.isdigit():
        qs = qs.filter(owner_id=int(owner_id))

    aggregate = qs.aggregate(
        total_count=Count("id"),
        avg_conversion_rate_pct=Avg("conversion_rate_pct"),
        total_dropoff=Sum("dropoff_count"),
    )
    # "Below benchmark" is a ROW-WISE comparison (this row's rate against this
    # row's benchmark), which an aggregate `filter=` cannot express. `F()` makes
    # it a DB-side comparison — no user input reaches the SQL — and it works on
    # MariaDB as well as SQLite.
    below_benchmark_count = (
        qs.filter(benchmark_pct__isnull=False)
        .filter(conversion_rate_pct__lt=F("benchmark_pct"))
        .count()
    )
    stats = {
        "total_count": aggregate["total_count"],
        "avg_conversion_rate_pct": aggregate["avg_conversion_rate_pct"],
        "total_dropoff": aggregate["total_dropoff"],
        "below_benchmark_count": below_benchmark_count,
    }

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    pipeline_stages = (
        PipelineStage.objects.filter(tenant=request.tenant, is_active=True)
        .select_related("pipeline")
        .order_by("pipeline__name", "sequence")
    )
    territories = Territory.objects.filter(tenant=request.tenant).order_by("name")
    owners = User.objects.filter(tenant=request.tenant, is_active=True).order_by("username")

    context = {
        "records": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "scope_choices": FUNNEL_SCOPE_CHOICES,
        "from_stages": pipeline_stages,
        "to_stages": pipeline_stages,
        "territories": territories,
        "owners": owners,
        "stats": stats,
        "active_filters": {
            "q": q,
            "funnel_scope": scope,
            "from_stage": from_id,
            "to_stage": to_id,
            "territory": territory_id,
            "owner": owner_id,
        },
    }
    return render(request, "sales/salesanalytics/funnelconversionrecord/list.html", context)


@login_required
def funnel_conversion_record_detail(request, pk):
    obj = get_object_or_404(
        FunnelConversionRecord.objects.filter(tenant=request.tenant).select_related(
            "from_stage",
            "to_stage",
            "territory",
            "owner",
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/salesanalytics/funnelconversionrecord/detail.html",
        {"obj": obj, "record": obj},
    )


@login_required
def funnel_conversion_record_create(request):
    if request.method == "POST":
        form = FunnelConversionRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Recorded funnel conversion {obj.number} for {obj.label}",
                tenant=request.tenant,
            )
            messages.success(request, f"Funnel conversion record {obj.number} created successfully.")
            return redirect("sales:funnel_conversion_record_detail", pk=obj.pk)
    else:
        form = FunnelConversionRecordForm(tenant=request.tenant)

    return render(
        request,
        "sales/salesanalytics/funnelconversionrecord/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def funnel_conversion_record_edit(request, pk):
    obj = get_object_or_404(
        FunnelConversionRecord.objects.filter(tenant=request.tenant).select_related(
            "from_stage",
            "to_stage",
            "territory",
            "owner",
        ),
        pk=pk,
    )
    if request.method == "POST":
        form = FunnelConversionRecordForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated funnel conversion {obj.number} for {obj.label}",
                tenant=request.tenant,
            )
            messages.success(request, f"Funnel conversion record {obj.number} updated successfully.")
            return redirect("sales:funnel_conversion_record_detail", pk=obj.pk)
    else:
        form = FunnelConversionRecordForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/salesanalytics/funnelconversionrecord/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def funnel_conversion_record_delete(request, pk):
    obj = get_object_or_404(
        FunnelConversionRecord.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    number = obj.number
    label = obj.label
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted funnel conversion {number} for {label}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Funnel conversion record {number} deleted.")
    return redirect("sales:funnel_conversion_record_list")
