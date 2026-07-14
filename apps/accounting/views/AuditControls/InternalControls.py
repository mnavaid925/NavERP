"""Accounting 2.14 Audit & Controls — InternalControls views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    InternalControl,
)
from apps.accounting.forms import (
    InternalControlForm,
)


# ================================================================= 2.14 Audit & Controls
@login_required
def internal_control_list(request):
    return crud_list(
        request, InternalControl.objects.filter(tenant=request.tenant),
        "accounting/audit/internal_control/list.html",
        search_fields=["code", "name"],
        filters=[("control_type", "control_type", False), ("risk_level", "risk_level", False),
                 ("status", "status", False), ("last_result", "last_result", False)],
        extra_context={"control_type_choices": InternalControl.CONTROL_TYPE_CHOICES,
                       "risk_choices": InternalControl.RISK_CHOICES,
                       "status_choices": InternalControl.STATUS_CHOICES,
                       "result_choices": InternalControl.RESULT_CHOICES},
    )


@login_required
def internal_control_create(request):
    return crud_create(request, form_class=InternalControlForm, template="accounting/audit/internal_control/form.html",
                       success_url="accounting:internal_control_list")


@login_required
def internal_control_detail(request, pk):
    obj = get_object_or_404(InternalControl.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/audit/internal_control/detail.html", {"obj": obj})


@login_required
def internal_control_edit(request, pk):
    return crud_edit(request, model=InternalControl, pk=pk, form_class=InternalControlForm,
                     template="accounting/audit/internal_control/form.html", success_url="accounting:internal_control_list")


@login_required
@require_POST
def internal_control_delete(request, pk):
    return crud_delete(request, model=InternalControl, pk=pk, success_url="accounting:internal_control_list")
