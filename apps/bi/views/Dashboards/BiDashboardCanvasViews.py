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
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def bi_dashboard_canvas_view(request, pk):
    dashboard = bi_object(
        request,
        BiDashboard,
        pk,
        select_related=("created_by", "org_unit"),
    )

    # Published status guard
    if not dashboard.is_published and not (
        request.user.is_superuser
        or getattr(request, "is_tenant_admin", False)
        or dashboard.created_by == request.user
    ):
        return HttpResponseForbidden("Dashboard is currently in draft status.")

    # Permission check for role restriction
    if dashboard.role_required and dashboard.role_required.lower() != "all":
        user_role_name = getattr(getattr(request.user, "role", None), "name", "")
        has_role = (
            request.user.is_superuser
            or getattr(request, "is_tenant_admin", False)
            or (user_role_name and user_role_name.lower() == dashboard.role_required.lower())
        )
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
    if bookmark_id and bookmark_id.isdigit():
        active_bookmark = dashboard.bookmarks.filter(
            Q(user=request.user) | Q(is_shared=True),
            pk=int(bookmark_id),
            is_active=True,
        ).first()
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
            val = request.GET[f.filter_key]
            filter_values[f.filter_key] = val
            f.current_value = val
        elif f.filter_key in filter_values:
            f.current_value = filter_values[f.filter_key]
        elif f.default_value:
            filter_values[f.filter_key] = f.default_value
            f.current_value = f.default_value
        else:
            f.current_value = ""

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
    )

    if not dashboard.is_kiosk_enabled:
        return HttpResponseForbidden("Kiosk mode is disabled for this dashboard.")

    if not dashboard.is_published and not (
        request.user.is_superuser
        or getattr(request, "is_tenant_admin", False)
        or dashboard.created_by == request.user
    ):
        return HttpResponseForbidden("Dashboard is currently in draft status.")

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
@tenant_admin_required
def bi_dashboard_canvas_builder(request, pk):
    dashboard = bi_object(
        request,
        BiDashboard,
        pk,
    )

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        # Handle AJAX drag-and-drop position updates
        try:
            payload = json.loads(request.body.decode("utf-8"))
            widget_positions = payload.get("positions", [])
            updated_count = 0
            with transaction.atomic():
                for item in widget_positions:
                    w_id = item.get("id") or item.get("widget_id")
                    if not w_id:
                        continue
                    pos_x = max(0, min(11, int(item.get("pos_x", 0))))
                    pos_y = max(0, min(100, int(item.get("pos_y", 0))))
                    width_cols = max(1, min(12, int(item.get("width_cols", 4))))
                    height_rows = max(1, min(12, int(item.get("height_rows", 4))))
                    BiDashboardWidget.objects.filter(
                        pk=w_id, dashboard=dashboard, tenant=request.tenant
                    ).update(
                        pos_x=pos_x,
                        pos_y=pos_y,
                        width_cols=width_cols,
                        height_rows=height_rows,
                    )
                    updated_count += 1
                write_audit_log(
                    request.user,
                    dashboard,
                    "update",
                    changes={"widget_positions_updated": updated_count},
                    tenant=request.tenant,
                )
            return JsonResponse({"status": "ok", "message": "Positions saved"})
        except Exception:
            return JsonResponse({"status": "error", "message": "Failed to update widget positions."}, status=400)

    widgets = dashboard.widgets.filter(is_active=True).order_by("pos_y", "pos_x", "sort_order")
    filters = dashboard.filters.filter(is_active=True).order_by("order")

    semantic_models = SemanticModel.objects.filter(tenant=request.tenant, is_active=True).only("id", "name")[:10]
    calculated_measures = CalculatedMeasure.objects.filter(tenant=request.tenant, is_active=True).only("id", "name")[:10]

    context = {
        "dashboard": dashboard,
        "widgets": widgets,
        "filters": filters,
        "widget_type_choices": BiDashboardWidget.WIDGET_TYPE_CHOICES,
        "semantic_models": semantic_models,
        "calculated_measures": calculated_measures,
    }
    return render(request, "bi/dashboards/canvas/builder.html", context)
