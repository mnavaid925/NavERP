"""HRM 3.32 Analytics Dashboard — Widget views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.AnalyticsDashboard._helpers import _can_manage_hrdash
from apps.hrm.models import (
    HRDashboard,
    HRDashboardWidget,
)
from apps.hrm.forms import (
    HRDashboardWidgetForm,
)
from apps.hrm.views.AnalyticsDashboard._helpers import _can_manage_hrdash


@login_required
def hr_widget_create(request, dash_pk):
    dashboard = get_object_or_404(HRDashboard, pk=dash_pk, tenant=request.tenant)
    if not _can_manage_hrdash(request.user, dashboard):
        raise PermissionDenied("Only the dashboard owner or a tenant admin can add widgets.")
    if request.method == "POST":
        form = HRDashboardWidgetForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            widget = form.save(commit=False)
            widget.tenant = request.tenant
            widget.dashboard = dashboard
            last = dashboard.widgets.order_by("-position").first()
            widget.position = (last.position + 1) if last else 0
            widget.save()
            write_audit_log(request.user, widget, "create")
            messages.success(request, "Widget added.")
            return redirect("hrm:hr_dashboard_detail", pk=dashboard.pk)
    else:
        form = HRDashboardWidgetForm(tenant=request.tenant)
    return render(request, "hrm/analytics/widget/form.html",
                  {"form": form, "is_edit": False, "dashboard": dashboard})


@login_required
def hr_widget_edit(request, pk):
    widget = get_object_or_404(HRDashboardWidget.objects.select_related("dashboard"),
                               pk=pk, tenant=request.tenant)
    if not _can_manage_hrdash(request.user, widget.dashboard):
        raise PermissionDenied("Only the dashboard owner or a tenant admin can edit widgets.")
    if request.method == "POST":
        form = HRDashboardWidgetForm(request.POST, instance=widget, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Widget updated.")
            return redirect("hrm:hr_dashboard_detail", pk=widget.dashboard_id)
    else:
        form = HRDashboardWidgetForm(instance=widget, tenant=request.tenant)
    return render(request, "hrm/analytics/widget/form.html",
                  {"form": form, "is_edit": True, "obj": widget, "dashboard": widget.dashboard})


@login_required
@require_POST
def hr_widget_delete(request, pk):
    widget = get_object_or_404(HRDashboardWidget.objects.select_related("dashboard"),
                               pk=pk, tenant=request.tenant)
    if not _can_manage_hrdash(request.user, widget.dashboard):
        raise PermissionDenied("Only the dashboard owner or a tenant admin can remove widgets.")
    dash_pk = widget.dashboard_id
    write_audit_log(request.user, widget, "delete")
    widget.delete()
    messages.success(request, "Widget removed.")
    return redirect("hrm:hr_dashboard_detail", pk=dash_pk)


@login_required
@require_POST
def hr_widget_move(request, pk, direction):
    """Reorder a widget one slot up/down; normalize positions to 0..n-1 (one bulk_update, not N)."""
    widget = get_object_or_404(HRDashboardWidget.objects.select_related("dashboard"),
                               pk=pk, tenant=request.tenant)
    if not _can_manage_hrdash(request.user, widget.dashboard):
        raise PermissionDenied("Only the dashboard owner or a tenant admin can reorder widgets.")
    order = list(widget.dashboard.widgets.filter(tenant=request.tenant).order_by("position", "id"))
    idx = next((i for i, w in enumerate(order) if w.pk == widget.pk), None)
    if idx is not None and direction in ("up", "down"):
        swap = idx - 1 if direction == "up" else idx + 1
        if 0 <= swap < len(order):
            order[idx], order[swap] = order[swap], order[idx]
            to_update = []
            for i, w in enumerate(order):
                if w.position != i:
                    w.position = i
                    to_update.append(w)
            if to_update:
                HRDashboardWidget.objects.bulk_update(to_update, ["position"])
                write_audit_log(request.user, widget, "update", {"action": "move", "direction": direction})
    return redirect("hrm:hr_dashboard_detail", pk=widget.dashboard_id)
