"""CRM 1.6 Analytics & Reporting — Widgets views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    AnalyticsDashboard,
    DashboardWidget,
)
from apps.crm.forms import (
    DashboardWidgetForm,
)


# ----- Dashboard widgets (children of a dashboard) --------------------------
@login_required
def widget_create(request, dash_pk):
    dashboard = get_object_or_404(AnalyticsDashboard, pk=dash_pk, tenant=request.tenant)
    if request.method == "POST":
        form = DashboardWidgetForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            widget = form.save(commit=False)
            widget.tenant = request.tenant
            widget.dashboard = dashboard
            last = dashboard.widgets.order_by("-position").first()
            widget.position = (last.position + 1) if last else 0
            widget.save()
            write_audit_log(request.user, widget, "create")
            messages.success(request, "Widget added.")
            return redirect("crm:dashboard_detail", pk=dashboard.pk)
    else:
        form = DashboardWidgetForm(tenant=request.tenant)
    return render(request, "crm/analytics/widget/form.html",
                  {"form": form, "is_edit": False, "dashboard": dashboard})


@login_required
def widget_edit(request, pk):
    widget = get_object_or_404(DashboardWidget, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = DashboardWidgetForm(request.POST, instance=widget, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Widget updated.")
            return redirect("crm:dashboard_detail", pk=widget.dashboard_id)
    else:
        form = DashboardWidgetForm(instance=widget, tenant=request.tenant)
    return render(request, "crm/analytics/widget/form.html",
                  {"form": form, "is_edit": True, "obj": widget, "dashboard": widget.dashboard})


@login_required
@require_POST
def widget_delete(request, pk):
    widget = get_object_or_404(DashboardWidget, pk=pk, tenant=request.tenant)
    dash_pk = widget.dashboard_id
    write_audit_log(request.user, widget, "delete")
    widget.delete()
    messages.success(request, "Widget removed.")
    return redirect("crm:dashboard_detail", pk=dash_pk)


@login_required
@require_POST
def widget_move(request, pk, direction):
    """Reorder a widget one slot up/down. Normalizes positions to 0..n-1 so it is robust even
    when several widgets share the default position 0."""
    widget = get_object_or_404(DashboardWidget, pk=pk, tenant=request.tenant)
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
                DashboardWidget.objects.bulk_update(to_update, ["position"])  # one statement, not N
                write_audit_log(request.user, widget, "update", {"action": "move", "direction": direction})
    return redirect("crm:dashboard_detail", pk=widget.dashboard_id)
