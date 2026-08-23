"""Inventory 5.10 Returns Management — DispositionRoutingRule CRUD views."""
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import DispositionRoutingRuleForm
from apps.inventory.models import DispositionRoutingRule
from apps.inventory.views._common import *  # noqa: F401,F403


@login_required
def dispositionrule_list(request):
    """List disposition routing rules with filtering and sorting."""
    qs = (
        DispositionRoutingRule.objects.filter(tenant=request.tenant)
        .select_related("item", "category", "destination_location")
    )

    is_active = request.GET.get("is_active", "").strip()
    if is_active == "active":
        qs = qs.filter(is_active=True)
    elif is_active == "inactive":
        qs = qs.filter(is_active=False)

    grade = request.GET.get("condition_grade", "").strip()
    if grade:
        qs = qs.filter(condition_grade=grade)

    return crud_list(
        request,
        qs,
        "inventory/returns/dispositionrule/list.html",
        search_fields=["name", "item__sku", "item__name", "category__name", "notes"],
        filters=(),
        extra_context={
            "is_active_choices": [["active", "Active"], ["inactive", "Inactive"]],
            "is_active": is_active,
            "grade_choices": DispositionRoutingRule.GRADE_FILTER_CHOICES,
            "condition_grade": grade,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def dispositionrule_create(request):
    """Create a new disposition routing rule."""
    return crud_create(
        request,
        form_class=DispositionRoutingRuleForm,
        template="inventory/returns/dispositionrule/form.html",
        success_url="inventory:dispositionrule_list",
    )


@login_required
def dispositionrule_detail(request, pk):
    """View details of a disposition routing rule."""
    return crud_detail(
        request,
        model=DispositionRoutingRule,
        pk=pk,
        template="inventory/returns/dispositionrule/detail.html",
        select_related=("item", "category", "destination_location"),
        extra_context={
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def dispositionrule_edit(request, pk):
    """Edit an existing disposition routing rule."""
    return crud_edit(
        request,
        model=DispositionRoutingRule,
        pk=pk,
        form_class=DispositionRoutingRuleForm,
        template="inventory/returns/dispositionrule/form.html",
        success_url="inventory:dispositionrule_list",
    )


@tenant_admin_required
@require_POST
def dispositionrule_delete(request, pk):
    """Delete a disposition routing rule."""
    return crud_delete(
        request,
        model=DispositionRoutingRule,
        pk=pk,
        success_url="inventory:dispositionrule_list",
    )
