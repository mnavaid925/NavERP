"""HRM 3.15 Statutory Compliance — Statutoryconfig views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    StatutoryConfig,
)
from apps.hrm.forms import (
    StatutoryConfigForm,
)


# ---------------------------------------------- StatutoryConfig (tenant singleton)
@login_required
def statutoryconfig_detail(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to view statutory configuration.")
        return redirect("dashboard:home")
    config = StatutoryConfig.for_tenant(request.tenant)
    return render(request, "hrm/statutory/statutoryconfig/detail.html", {"obj": config})


@tenant_admin_required  # editing PF/ESI codes, TAN, PAN and rates is privileged org-wide config
def statutoryconfig_edit(request):
    # Dedicated get-or-create-then-edit view: crud_edit takes a pk, but this model is a per-tenant
    # settings singleton reached without one — so the row is resolved via for_tenant() here.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to edit statutory configuration.")
        return redirect("dashboard:home")
    config = StatutoryConfig.for_tenant(request.tenant)
    if request.method == "POST":
        form = StatutoryConfigForm(request.POST, instance=config, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, config, "update", {"action": "edit_config"})
            messages.success(request, "Statutory configuration updated.")
            return redirect("hrm:statutoryconfig_detail")
    else:
        form = StatutoryConfigForm(instance=config, tenant=request.tenant)
    return render(request, "hrm/statutory/statutoryconfig/form.html",
                  {"form": form, "obj": config, "is_edit": True})
