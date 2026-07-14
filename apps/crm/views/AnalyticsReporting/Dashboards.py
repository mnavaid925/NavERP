"""CRM 1.6 Analytics & Reporting — Dashboards views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    AnalyticsDashboard,
)
from apps.crm.forms import (
    AnalyticsDashboardForm,
)
from apps.crm.analytics import compute_widget


# ----- Dashboards -----------------------------------------------------------
@login_required
def dashboard_list(request):
    qs = AnalyticsDashboard.objects.filter(tenant=request.tenant).select_related("owner")
    return crud_list(
        request, qs, "crm/analytics/dashboard/list.html",
        search_fields=["name", "number", "description"],
        filters=[("owner", "owner_id", True)],
        extra_context={"owners": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


def _can_share_dashboards(user):
    # Publishing (is_shared) / defaulting (is_default) a dashboard is a tenant-wide setting,
    # so it is restricted to tenant admins (or superuser) — security-review finding.
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


@login_required
def dashboard_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    can_share = _can_share_dashboards(request.user)
    if request.method == "POST":
        form = AnalyticsDashboardForm(request.POST, tenant=request.tenant, can_share=can_share)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("crm:dashboard_detail", pk=obj.pk)
    else:
        form = AnalyticsDashboardForm(tenant=request.tenant, can_share=can_share)
    return render(request, "crm/analytics/dashboard/form.html", {"form": form, "is_edit": False})


@login_required
def dashboard_detail(request, pk):
    dashboard = get_object_or_404(
        AnalyticsDashboard.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    cols = {"one": 1, "two": 2, "three": 3}.get(dashboard.layout, 2)
    span_map = {"small": 1, "medium": 2, "large": 3, "full": cols}
    rendered, chart_configs = [], []
    for w in dashboard.widgets.filter(tenant=request.tenant):
        result = compute_widget(w)
        rendered.append({"widget": w, "result": result, "span": min(span_map.get(w.size, 1), cols)})
        # Only true Chart.js charts go to JS; KPI/gauge/table render as HTML.
        if result.get("kind") == "series" and w.chart_type in ("bar", "line", "pie", "doughnut"):
            chart_configs.append({"id": w.pk, "type": w.chart_type,
                                  "labels": result.get("labels", []), "data": result.get("data", [])})
    return render(request, "crm/analytics/dashboard/detail.html",
                  {"obj": dashboard, "rendered_widgets": rendered, "chart_configs": chart_configs, "cols": cols})


@login_required
def dashboard_edit(request, pk):
    obj = get_object_or_404(AnalyticsDashboard, pk=pk, tenant=request.tenant)
    can_share = _can_share_dashboards(request.user)
    if request.method == "POST":
        form = AnalyticsDashboardForm(request.POST, instance=obj, tenant=request.tenant, can_share=can_share)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Updated successfully.")
            return redirect("crm:dashboard_detail", pk=obj.pk)
    else:
        form = AnalyticsDashboardForm(instance=obj, tenant=request.tenant, can_share=can_share)
    return render(request, "crm/analytics/dashboard/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def dashboard_delete(request, pk):
    return crud_delete(request, model=AnalyticsDashboard, pk=pk, success_url="crm:dashboard_list")
