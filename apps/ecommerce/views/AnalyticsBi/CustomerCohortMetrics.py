from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.AnalyticsBi.CustomerCohortMetrics import CustomerCohortMetricForm
from apps.ecommerce.models.AnalyticsBi.CustomerCohortMetrics import CustomerCohortMetric
from apps.ecommerce.views._common import ecommerce_object


@login_required
def customercohortmetric_list(request):
    qs = CustomerCohortMetric.objects.filter(tenant=request.tenant)

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(acquisition_channel_tag__icontains=query)
        )

    selected_channel = request.GET.get("channel", "").strip()
    if selected_channel:
        qs = qs.filter(acquisition_channel_tag__icontains=selected_channel)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "ecommerce/analytics_bi/customer_cohort_metric/list.html",
        {
            "cohort_metrics": page_obj,
            "selected_channel": selected_channel,
            "query": query,
            "page_obj": page_obj,
            "paginator": paginator,
        },
    )


@login_required
def customercohortmetric_detail(request, pk):
    cohort_metric = ecommerce_object(request, CustomerCohortMetric, pk)
    return render(
        request,
        "ecommerce/analytics_bi/customer_cohort_metric/detail.html",
        {"cohort_metric": cohort_metric},
    )


@login_required
def customercohortmetric_create(request):
    if request.method == "POST":
        form = CustomerCohortMetricForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            metric = form.save(commit=False)
            metric.tenant = request.tenant
            metric.recalculate_rates()
            metric.save()
            write_audit_log(
                request.user,
                metric,
                "create",
                {"number": metric.number, "cohort": str(metric.cohort_month)},
                tenant=request.tenant,
            )
            messages.success(request, f"Cohort metric {metric.number} created successfully.")
            return redirect("ecommerce:customercohortmetric_detail", pk=metric.pk)
    else:
        # Default first day of current month
        today = timezone.now().date()
        month_start = today.replace(day=1)
        form = CustomerCohortMetricForm(
            tenant=request.tenant,
            initial={"cohort_month": month_start, "period_offset_months": 0},
        )

    return render(
        request,
        "ecommerce/analytics_bi/customer_cohort_metric/form.html",
        {"form": form, "cohort_metric": None},
    )


@login_required
def customercohortmetric_edit(request, pk):
    cohort_metric = ecommerce_object(request, CustomerCohortMetric, pk)
    if request.method == "POST":
        form = CustomerCohortMetricForm(request.POST, instance=cohort_metric, tenant=request.tenant)
        if form.is_valid():
            metric = form.save(commit=False)
            metric.recalculate_rates()
            metric.save()
            write_audit_log(
                request.user,
                metric,
                "update",
                {"number": metric.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Cohort metric {metric.number} updated successfully.")
            return redirect("ecommerce:customercohortmetric_detail", pk=metric.pk)
    else:
        form = CustomerCohortMetricForm(instance=cohort_metric, tenant=request.tenant)

    return render(
        request,
        "ecommerce/analytics_bi/customer_cohort_metric/form.html",
        {"form": form, "cohort_metric": cohort_metric},
    )


@require_POST
@login_required
@tenant_admin_required
def customercohortmetric_delete(request, pk):
    cohort_metric = ecommerce_object(request, CustomerCohortMetric, pk)
    number = cohort_metric.number
    cohort_metric.delete()
    write_audit_log(
        request.user,
        cohort_metric,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Cohort metric {number} was deleted.")
    return redirect("ecommerce:customercohortmetric_list")


@require_POST
@login_required
def customercohortmetric_recalculate(request):
    """Batch recalculates retention percentages, churn rates, and LTV on all cohort rows."""
    metrics = CustomerCohortMetric.objects.filter(tenant=request.tenant)
    count = 0
    for m in metrics:
        m.recalculate_rates()
        m.save(update_fields=["retention_rate_pct", "churn_rate_pct", "cumulative_ltv_per_customer"])
        count += 1

    write_audit_log(
        request.user,
        None,
        "recalc",
        f"Recalculated {count} cohort metrics",
        tenant=request.tenant,
    )
    messages.success(request, f"Recalculated retention and LTV metrics across {count} cohort entries.")
    return redirect("ecommerce:customercohortmetric_list")
