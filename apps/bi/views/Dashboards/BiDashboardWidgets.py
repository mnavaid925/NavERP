import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.Dashboards.BiDashboardWidgetForms import BiDashboardWidgetForm
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardWidgets import BiDashboardWidget
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def bi_dashboard_widget_list(request):
    qs = (
        bi_scope(BiDashboardWidget.objects.all(), request)
        .select_related("dashboard", "semantic_model", "calculated_measure", "warehouse_table")
        .defer("chart_config_json", "filter_overrides_json")
    )
    total_widgets = qs.count()

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(subtitle__icontains=q)
            | Q(number__icontains=q)
            | Q(dashboard__title__icontains=q)
        )

    dashboard_id = request.GET.get("dashboard", "").strip()
    if dashboard_id and dashboard_id.isdigit():
        qs = qs.filter(dashboard_id=dashboard_id)

    widget_type = request.GET.get("widget_type", "").strip()
    if widget_type:
        qs = qs.filter(widget_type=widget_type)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    dashboards = BiDashboard.objects.filter(tenant=request.tenant, is_active=True).only("id", "title").order_by("title")

    context = {
        "page_obj": page_obj,
        "widgets": page_obj,
        "dashboards": dashboards,
        "widget_type_choices": BiDashboardWidget.WIDGET_TYPE_CHOICES,
        "total_widgets": total_widgets,
        "q": q,
        "dashboard_id": dashboard_id,
        "widget_type": widget_type,
    }
    return render(request, "bi/dashboards/widget/list.html", context)


@login_required
def bi_dashboard_widget_detail(request, pk):
    widget = bi_object(
        request,
        BiDashboardWidget,
        pk,
        select_related=("dashboard", "semantic_model", "calculated_measure", "warehouse_table", "drill_hierarchy"),
    )

    chart_config_pretty = json.dumps(widget.chart_config_json, indent=2)

    # Mock / calculated sample preview data
    data_preview = {
        "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "values": [42000, 56000, 68000, 81000, 94000, 115000],
        "kpi_value": "$115,000" if widget.widget_type == "kpi_card" else None,
        "change_pct": "+14.2%",
    }

    context = {
        "widget": widget,
        "dashboard": widget.dashboard,
        "chart_config_pretty": chart_config_pretty,
        "data_preview": data_preview,
    }
    return render(request, "bi/dashboards/widget/detail.html", context)


@login_required
@tenant_admin_required
def bi_dashboard_widget_create(request):
    initial_data = {}
    dashboard_id = request.GET.get("dashboard")
    if dashboard_id:
        initial_data["dashboard"] = dashboard_id

    if request.method == "POST":
        form = BiDashboardWidgetForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                widget = form.save(commit=False)
                widget.tenant = request.tenant

                # Populate default chart config if not provided
                if not widget.chart_config_json:
                    widget.chart_config_json = {
                        "responsive": True,
                        "maintainAspectRatio": False,
                        "plugins": {"legend": {"position": "top"}},
                    }

                widget.save()
                write_audit_log(
                    request.user,
                    widget,
                    "create",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Widget '{widget.title}' created successfully.")
            return redirect("bi:bi_dashboard_detail", pk=widget.dashboard_id)
    else:
        form = BiDashboardWidgetForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "widget": None,
        "is_edit": False,
    }
    return render(request, "bi/dashboards/widget/form.html", context)


@login_required
@tenant_admin_required
def bi_dashboard_widget_edit(request, pk):
    widget = bi_object(request, BiDashboardWidget, pk)
    if request.method == "POST":
        form = BiDashboardWidgetForm(request.POST, instance=widget, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                widget = form.save()
                write_audit_log(
                    request.user,
                    widget,
                    "update",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Widget '{widget.title}' updated successfully.")
            return redirect("bi:bi_dashboard_detail", pk=widget.dashboard_id)
    else:
        form = BiDashboardWidgetForm(instance=widget, tenant=request.tenant)

    context = {
        "form": form,
        "widget": widget,
        "is_edit": True,
    }
    return render(request, "bi/dashboards/widget/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def bi_dashboard_widget_delete(request, pk):
    widget = bi_object(request, BiDashboardWidget, pk)
    dashboard_id = widget.dashboard_id
    title = widget.title
    with transaction.atomic():
        write_audit_log(
            request.user,
            widget,
            "delete",
            changes={"title": title, "number": widget.number},
            tenant=request.tenant,
        )
        widget.delete()
    messages.success(request, f"Widget '{title}' deleted successfully.")
    return redirect("bi:bi_dashboard_detail", pk=dashboard_id)


@login_required
def bi_dashboard_widget_data(request, pk):
    """API endpoint providing JSON payload for rendering Chart.js on the canvas."""
    widget = bi_object(
        request,
        BiDashboardWidget,
        pk,
        select_related=("calculated_measure", "semantic_model", "warehouse_table"),
    )

    # Dynamic dataset mock / aggregation based on widget type and bound measure
    labels = ["Q1", "Q2", "Q3", "Q4"]
    data = [120000, 145000, 160000, 210000]
    metric_label = widget.calculated_measure.name if widget.calculated_measure else widget.title

    payload = {
        "widget_id": widget.pk,
        "number": widget.number,
        "title": widget.title,
        "widget_type": widget.widget_type,
        "aggregation_type": widget.aggregation_type,
        "labels": labels,
        "datasets": [
            {
                "label": metric_label,
                "data": data,
                "backgroundColor": ["#1e40af", "#0d9488", "#f59e0b", "#6366f1"],
                "borderColor": "#1e40af",
                "borderWidth": 2,
            }
        ],
        "kpi_value": "$210,000",
        "sparkline": [12, 14, 13, 16, 18, 21],
    }
    return JsonResponse(payload)
