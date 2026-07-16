"""HRM 3.32 Analytics Dashboard — Dashboard views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.AnalyticsDashboard._helpers import _can_manage_hrdash, _can_share_hrdash
from apps.hrm.models import (
    HRDashboard,
)
from apps.hrm.forms import (
    HRDashboardForm,
)
from apps.hrm.views.AnalyticsDashboard._helpers import _can_manage_hrdash, _can_share_hrdash
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _compute_widget, _get_user_model


@login_required
def hr_dashboard_list(request):
    qs = (HRDashboard.objects.filter(tenant=request.tenant)
          .filter(Q(owner=request.user) | Q(is_shared=True)).select_related("owner")
          .annotate(widget_total=Count("widgets")))  # avoid the widget_count property N+1 in the list
    # Owner filter dropdown lists only owners of VISIBLE dashboards (never leaks a private one's owner).
    owner_ids = set(qs.values_list("owner_id", flat=True))
    owners = _get_user_model().objects.filter(pk__in=owner_ids).order_by("username")
    return crud_list(
        request, qs, "hrm/analytics/dashboard/list.html",
        search_fields=["name", "number", "description"],
        filters=[("owner", "owner_id", True)],
        extra_context={"owners": owners, "current_user_id": request.user.pk,
                       "is_admin": _can_share_hrdash(request.user)},
    )


@login_required
def hr_dashboard_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    can_share = _can_share_hrdash(request.user)
    if request.method == "POST":
        form = HRDashboardForm(request.POST, tenant=request.tenant, can_share=can_share)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.owner = request.user  # owner is ALWAYS the creator, never a form field
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Dashboard created.")
            return redirect("hrm:hr_dashboard_detail", pk=obj.pk)
    else:
        form = HRDashboardForm(tenant=request.tenant, can_share=can_share)
    return render(request, "hrm/analytics/dashboard/form.html", {"form": form, "is_edit": False})


@login_required
def hr_dashboard_detail(request, pk):
    obj = get_object_or_404(HRDashboard.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    if not (obj.is_shared or obj.owner_id == request.user.pk or _can_share_hrdash(request.user)):
        raise PermissionDenied("You do not have access to this dashboard.")
    cols = {"one": 1, "two": 2, "three": 3}.get(obj.layout, 2)
    span_map = {"small": 1, "medium": 2, "large": 3, "full": cols}
    rendered, chart_configs = [], []
    for w in obj.widgets.filter(tenant=request.tenant):
        result = _compute_widget(w)
        rendered.append({"widget": w, "result": result, "span": min(span_map.get(w.size, 1), cols)})
        if result.get("kind") == "series" and w.chart_type in ("bar", "line", "pie", "doughnut"):
            chart_configs.append({"id": w.pk, "type": w.chart_type,
                                  "labels": result.get("labels", []), "data": result.get("data", [])})
    return render(request, "hrm/analytics/dashboard/detail.html",
                  {"obj": obj, "rendered_widgets": rendered, "chart_configs": chart_configs,
                   "cols": cols, "can_manage": _can_manage_hrdash(request.user, obj)})


@login_required
def hr_dashboard_edit(request, pk):
    obj = get_object_or_404(HRDashboard, pk=pk, tenant=request.tenant)
    if not _can_manage_hrdash(request.user, obj):
        raise PermissionDenied("Only the dashboard owner or a tenant admin can edit this dashboard.")
    can_share = _can_share_hrdash(request.user)
    if request.method == "POST":
        form = HRDashboardForm(request.POST, instance=obj, tenant=request.tenant, can_share=can_share)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Dashboard updated.")
            return redirect("hrm:hr_dashboard_detail", pk=obj.pk)
    else:
        form = HRDashboardForm(instance=obj, tenant=request.tenant, can_share=can_share)
    return render(request, "hrm/analytics/dashboard/form.html", {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def hr_dashboard_delete(request, pk):
    obj = get_object_or_404(HRDashboard, pk=pk, tenant=request.tenant)
    if not _can_manage_hrdash(request.user, obj):
        raise PermissionDenied("Only the dashboard owner or a tenant admin can delete this dashboard.")
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Dashboard deleted.")
    return redirect("hrm:hr_dashboard_list")
