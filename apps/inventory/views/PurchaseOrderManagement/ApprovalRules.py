"""Inventory 5.3 Purchase Order (PO) Management — PurchaseOrderApprovalRule views.

Plain thin CRUD over ``apps.core.crud`` like every other inventory catalog page. The rule
catalog is policy, not workflow: deciding outcomes happens on the approvals queue
(``Approvals.py``), never here.
"""
from apps.core.models import OrgUnit
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import PurchaseOrderApprovalRuleForm
from apps.inventory.models import PurchaseOrderApprovalRule


def _org_units(tenant):
    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant).order_by("name")


@login_required
def approvalrule_list(request):
    qs = PurchaseOrderApprovalRule.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "inventory/po/approvalrule/list.html",
        search_fields=["name"],
        filters=[("org_unit", "org_unit_id", True), ("active", "is_active", False)],
        extra_context={
            "org_units": _org_units(request.tenant),
            "max_tiers": PurchaseOrderApprovalRule.MAX_TIERS,
        },
    )


@login_required
def approvalrule_create(request):
    return crud_create(
        request, form_class=PurchaseOrderApprovalRuleForm,
        template="inventory/po/approvalrule/form.html",
        success_url="inventory:approvalrule_list",
    )


@login_required
def approvalrule_detail(request, pk):
    obj = get_object_or_404(
        PurchaseOrderApprovalRule.objects.select_related("org_unit"), pk=pk,
        tenant=request.tenant)
    return render(request, "inventory/po/approvalrule/detail.html", {
        "obj": obj,
        # Decisions taken under this rule, newest first — the audit of what the policy did.
        "decisions": (obj.decisions.select_related("purchase_order", "decided_by")
                      .order_by("-decided_at", "-id")[:10]),
    })


@login_required
def approvalrule_edit(request, pk):
    return crud_edit(
        request, model=PurchaseOrderApprovalRule, pk=pk,
        form_class=PurchaseOrderApprovalRuleForm,
        template="inventory/po/approvalrule/form.html",
        success_url="inventory:approvalrule_list",
    )


@login_required
@require_POST
def approvalrule_delete(request, pk):
    return crud_delete(request, model=PurchaseOrderApprovalRule, pk=pk,
                       success_url="inventory:approvalrule_list")
