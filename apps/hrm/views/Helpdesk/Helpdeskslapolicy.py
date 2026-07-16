"""HRM 3.36 Helpdesk — Helpdeskslapolicy views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    HelpdeskCategory,
    HelpdeskSLAPolicy,
    HelpdeskTicket,
)
from apps.hrm.forms import (
    HelpdeskSLAPolicyForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ---- Helpdesk SLA policies (admin-managed catalog) --------------------------------------------
@login_required
def helpdesksla_list(request):
    qs = HelpdeskSLAPolicy.objects.filter(tenant=request.tenant)
    return crud_list(request, qs, "hrm/helpdesk/helpdeskslapolicy/list.html",
                     search_fields=["number", "name", "description"],
                     filters=[("is_active", "is_active", False)],
                     extra_context={"is_admin": _is_admin(request.user)})


@tenant_admin_required
def helpdesksla_create(request):
    return crud_create(request, form_class=HelpdeskSLAPolicyForm,
                       template="hrm/helpdesk/helpdeskslapolicy/form.html", success_url="hrm:helpdesksla_list")


@login_required
def helpdesksla_detail(request, pk):
    return crud_detail(request, model=HelpdeskSLAPolicy, pk=pk,
                       template="hrm/helpdesk/helpdeskslapolicy/detail.html",
                       extra_context={"is_admin": _is_admin(request.user),
                                      "category_count": HelpdeskCategory.objects.filter(
                                          tenant=request.tenant, default_sla_policy_id=pk).count(),
                                      "ticket_count": HelpdeskTicket.objects.filter(
                                          tenant=request.tenant, sla_policy_id=pk).count()})


@tenant_admin_required
def helpdesksla_edit(request, pk):
    return crud_edit(request, model=HelpdeskSLAPolicy, pk=pk, form_class=HelpdeskSLAPolicyForm,
                     template="hrm/helpdesk/helpdeskslapolicy/form.html", success_url="hrm:helpdesksla_list")


@tenant_admin_required
@require_POST
def helpdesksla_delete(request, pk):
    if HelpdeskTicket.objects.filter(tenant=request.tenant, sla_policy_id=pk).exists():
        messages.error(request, "This SLA policy is used by existing tickets and can't be deleted.")
        return redirect("hrm:helpdesksla_detail", pk=pk)
    return crud_delete(request, model=HelpdeskSLAPolicy, pk=pk, success_url="hrm:helpdesksla_list")
