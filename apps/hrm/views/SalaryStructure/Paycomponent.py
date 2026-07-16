"""HRM 3.13 Salary Structure — Paycomponent views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    PayComponent,
)
from apps.hrm.forms import (
    PayComponentForm,
)


# ============================================================ Pay Components (3.13)
@login_required
def paycomponent_list(request):
    return crud_list(
        request,
        PayComponent.objects.filter(tenant=request.tenant),
        "hrm/salary/paycomponent/list.html",
        search_fields=["name", "code", "description"],
        filters=[("component_type", "component_type", False), ("calculation_type", "calculation_type", False),
                 ("frequency", "frequency", False), ("is_active", "is_active", False)],
        extra_context={
            "component_type_choices": PayComponent.COMPONENT_TYPE_CHOICES,
            "calculation_type_choices": PayComponent.CALCULATION_TYPE_CHOICES,
            "frequency_choices": PayComponent.FREQUENCY_CHOICES,
        },
    )


@login_required
def paycomponent_create(request):
    return crud_create(request, form_class=PayComponentForm,
                       template="hrm/salary/paycomponent/form.html", success_url="hrm:paycomponent_list")


@login_required
def paycomponent_detail(request, pk):
    obj = get_object_or_404(PayComponent, pk=pk, tenant=request.tenant)
    return render(request, "hrm/salary/paycomponent/detail.html", {
        "obj": obj,
        # Templates whose breakdown references this component (PROTECT FK → default reverse accessor).
        "usage_lines": (obj.salarystructureline_set.select_related("template")
                        .order_by("template__name")[:10]),
    })


@login_required
def paycomponent_edit(request, pk):
    return crud_edit(request, model=PayComponent, pk=pk, form_class=PayComponentForm,
                     template="hrm/salary/paycomponent/form.html", success_url="hrm:paycomponent_list")


@login_required
@require_POST
def paycomponent_delete(request, pk):
    # SalaryStructureLine.pay_component is PROTECT — guard so an in-use component gives a friendly
    # message instead of a raw ProtectedError 500.
    obj = get_object_or_404(PayComponent, pk=pk, tenant=request.tenant)
    if obj.salarystructureline_set.exists():
        messages.error(request, "This component is used by one or more salary structures — remove those lines first.")
        return redirect("hrm:paycomponent_detail", pk=obj.pk)
    return crud_delete(request, model=PayComponent, pk=pk, success_url="hrm:paycomponent_list")
