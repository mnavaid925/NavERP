from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.Dashboards.BiDashboardFilterForms import BiDashboardFilterForm
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardFilters import BiDashboardFilter
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def bi_dashboard_filter_list(request):
    qs = bi_scope(BiDashboardFilter.objects.all(), request).select_related("dashboard").defer("static_options_json")
    total_filters = qs.count()

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(filter_label__icontains=q)
            | Q(filter_key__icontains=q)
            | Q(number__icontains=q)
            | Q(dashboard__title__icontains=q)
            | Q(target_field__icontains=q)
        )

    dashboard_id = request.GET.get("dashboard", "").strip()
    if dashboard_id and dashboard_id.isdigit():
        qs = qs.filter(dashboard_id=dashboard_id)

    filter_type = request.GET.get("filter_type", "").strip()
    if filter_type:
        qs = qs.filter(filter_type=filter_type)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    dashboards = BiDashboard.objects.filter(tenant=request.tenant, is_active=True).only("id", "title").order_by("title")

    context = {
        "page_obj": page_obj,
        "filters": page_obj,
        "dashboards": dashboards,
        "filter_type_choices": BiDashboardFilter.FILTER_TYPE_CHOICES,
        "total_filters": total_filters,
        "q": q,
        "dashboard_id": dashboard_id,
        "filter_type": filter_type,
    }
    return render(request, "bi/dashboards/filter/list.html", context)


@login_required
def bi_dashboard_filter_detail(request, pk):
    filter_obj = bi_object(
        request,
        BiDashboardFilter,
        pk,
        select_related=("dashboard",),
    )

    context = {
        "filter_obj": filter_obj,
        "dashboard": filter_obj.dashboard,
    }
    return render(request, "bi/dashboards/filter/detail.html", context)


@login_required
@tenant_admin_required
def bi_dashboard_filter_create(request):
    initial_data = {}
    dashboard_id = request.GET.get("dashboard")
    if dashboard_id:
        initial_data["dashboard"] = dashboard_id

    if request.method == "POST":
        form = BiDashboardFilterForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                filter_obj = form.save(commit=False)
                filter_obj.tenant = request.tenant
                filter_obj.save()
                write_audit_log(
                    request.user,
                    filter_obj,
                    "create",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Filter control '{filter_obj.filter_label}' created successfully.")
            return redirect("bi:bi_dashboard_detail", pk=filter_obj.dashboard_id)
    else:
        form = BiDashboardFilterForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "filter_obj": None,
        "is_edit": False,
    }
    return render(request, "bi/dashboards/filter/form.html", context)


@login_required
@tenant_admin_required
def bi_dashboard_filter_edit(request, pk):
    filter_obj = bi_object(request, BiDashboardFilter, pk)
    if request.method == "POST":
        form = BiDashboardFilterForm(request.POST, instance=filter_obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                filter_obj = form.save()
                write_audit_log(
                    request.user,
                    filter_obj,
                    "update",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Filter control '{filter_obj.filter_label}' updated successfully.")
            return redirect("bi:bi_dashboard_detail", pk=filter_obj.dashboard_id)
    else:
        form = BiDashboardFilterForm(instance=filter_obj, tenant=request.tenant)

    context = {
        "form": form,
        "filter_obj": filter_obj,
        "is_edit": True,
    }
    return render(request, "bi/dashboards/filter/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def bi_dashboard_filter_delete(request, pk):
    filter_obj = bi_object(request, BiDashboardFilter, pk)
    dashboard_id = filter_obj.dashboard_id
    label = filter_obj.filter_label
    with transaction.atomic():
        write_audit_log(
            request.user,
            filter_obj,
            "delete",
            changes={"filter_label": label, "number": filter_obj.number},
            tenant=request.tenant,
        )
        filter_obj.delete()
    messages.success(request, f"Filter control '{label}' removed.")
    return redirect("bi:bi_dashboard_detail", pk=dashboard_id)
