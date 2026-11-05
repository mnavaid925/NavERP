import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardWidgets import BiDashboardWidget
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_object
from apps.core.utils import write_audit_log


@login_required
def bi_dashboard_canvas_view(request, pk):
    dashboard = bi_object(
        request,
        BiDashboard,
        pk,
        select_related=("created_by", "org_unit"),
        prefetch_related=("widgets", "filters", "bookmarks"),
    )

    # Permission check for role restriction
    if dashboard.role_required and dashboard.role_required != "all":
        # Check if user has role or is admin/superuser
        user_roles = getattr(request.user, "roles", None)
        has_role = request.user.is_superuser or getattr(request, "is_tenant_admin", False)
        if user_roles and hasattr(user_roles, "filter"):
            has_role = has_role or user_roles.filter(code=dashboard.role_required).exists()
        if not has_role and dashboard.created_by != request.user:
            return HttpResponseForbidden("Access restricted by dashboard role policy.")

    # Telemetry
    BiDashboard.objects.filter(pk=dashboard.pk).update(
        view_count=dashboard.view_count + 1,
        last_viewed_at=timezone.now(),
    )

    widgets = dashboard.widgets.filter(is_active=True).select_related(
        "calculated_measure", "semantic_model", "warehouse_table"
    ).order_by("pos_y", "pos_x", "sort_order")

    filters = dashboard.filters.filter(is_active=True).order_by("order")

    bookmarks = dashboard.bookmarks.filter(is_active=True).filter(
        Q(user=request.user) | Q(is_shared=True)
    ).order_by("-is_default", "name")

    # Apply bookmark if specified in GET query
    active_bookmark = None
    bookmark_id = request.GET.get("bookmark")
    if bookmark_id:
        active_bookmark = dashboard.bookmarks.filter(pk=bookmark_id, is_active=True).first()
        if active_bookmark:
            active_bookmark.view_count += 1
            active_bookmark.last_viewed_at = timezone.now()
            active_bookmark.save(update_fields=["view_count", "last_viewed_at"])
    elif not request.GET:
        # Default user bookmark
        active_bookmark = dashboard.bookmarks.filter(
            user=request.user, is_default=True, is_active=True
        ).first()

    # Determine active filter values from GET or active bookmark
    filter_values = {}
    if active_bookmark and active_bookmark.filter_state_json:
        filter_values.update(active_bookmark.filter_state_json)

    for f in filters:
        if f.filter_key in request.GET:
            filter_values[f.filter_key] = request.GET[f.filter_key]
        elif f.filter_key not in filter_values and f.default_value:
            filter_values[f.filter_key] = f.default_value

    context = {
        "dashboard": dashboard,
        "widgets": widgets,
        "filters": filters,
        "bookmarks": bookmarks,
        "active_bookmark": active_bookmark,
        "filter_values_json": json.dumps(filter_values),
        "refresh_interval": dashboard.refresh_interval_seconds,
        "is_kiosk": False,
        "theme": dashboard.theme,
    }
    return render(request, "bi/dashboards/canvas/viewer.html", context)


@login_required
def bi_dashboard_kiosk_view(request, pk):
    dashboard = bi_object(
        request,
        BiDashboard,
        pk,
        prefetch_related=("widgets",),
    )

    widgets = dashboard.widgets.filter(is_active=True).select_related(
        "calculated_measure", "semantic_model", "warehouse_table"
    ).order_by("pos_y", "pos_x", "sort_order")

    context = {
        "dashboard": dashboard,
        "widgets": widgets,
        "refresh_interval": dashboard.refresh_interval_seconds or 60,
        "is_kiosk": True,
        "theme": dashboard.theme,
    }
    return render(request, "bi/dashboards/canvas/kiosk.html", context)


@login_required
def bi_dashboard_canvas_builder(request, pk):
    dashboard = bi_object(
        request,
        BiDashboard,
        pk,
        prefetch_related=("widgets", "filters"),
    )

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        # Handle AJAX drag-and-drop position updates
        try:
            payload = json.loads(request.body.decode("utf-8"))
            widget_positions = payload.get("positions", [])
            with transaction.atomic():
                for item in widget_positions:
                    w_id = item.get("id")
                    BiDashboardWidget.objects.filter(
                        pk=w_id, dashboard=dashboard, tenant=request.tenant
                    ).update(
                        pos_x=item.get("pos_x", 0),
                        pos_y=item.get("pos_y", 0),
                        width_cols=item.get("width_cols", 4),
                        height_rows=item.get("height_rows", 4),
                    )
            return JsonResponse({"status": "ok", "message": "Positions saved"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    widgets = dashboard.widgets.filter(is_active=True).order_by("pos_y", "pos_x", "sort_order")
    filters = dashboard.filters.filter(is_active=True).order_by("order")

    semantic_models = SemanticModel.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    warehouse_tables = WarehouseTable.objects.filter(tenant=request.tenant).order_by("table_name")
    calculated_measures = CalculatedMeasure.objects.filter(tenant=request.tenant, is_active=True).order_by("name")

    context = {
        "dashboard": dashboard,
        "widgets": widgets,
        "filters": filters,
        "widget_type_choices": BiDashboardWidget.WIDGET_TYPE_CHOICES,
        "semantic_models": semantic_models,
        "warehouse_tables": warehouse_tables,
        "calculated_measures": calculated_measures,
    }
    return render(request, "bi/dashboards/canvas/builder.html", context)
