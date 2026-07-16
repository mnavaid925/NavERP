"""tenants — HealthMetric views (split from apps/tenants/views.py)."""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    HealthMetric,
)
from apps.tenants.forms import (
    HealthMetricForm,
)


# ============================================================ Health metrics
@tenant_admin_required
def healthmetric_list(request):
    return crud_list(
        request, HealthMetric.objects.filter(tenant=request.tenant),
        "tenants/healthmetric/list.html",
        search_fields=["metric"],
        filters=[("metric", "metric", False), ("status", "status", False)],
        extra_context={"metric_choices": HealthMetric.METRIC_CHOICES,
                       "status_choices": HealthMetric.STATUS_CHOICES},
    )


@tenant_admin_required
def healthmetric_create(request):
    return crud_create(request, form_class=HealthMetricForm, template="tenants/healthmetric/form.html",
                       success_url="tenants:healthmetric_list")


@tenant_admin_required
def healthmetric_detail(request, pk):
    obj = get_object_or_404(HealthMetric, pk=pk, tenant=request.tenant)
    return render(request, "tenants/healthmetric/detail.html", {"obj": obj})


@tenant_admin_required
def healthmetric_edit(request, pk):
    return crud_edit(request, model=HealthMetric, pk=pk, form_class=HealthMetricForm,
                     template="tenants/healthmetric/form.html", success_url="tenants:healthmetric_list")


@tenant_admin_required
@require_POST
def healthmetric_delete(request, pk):
    return crud_delete(request, model=HealthMetric, pk=pk, success_url="tenants:healthmetric_list")
