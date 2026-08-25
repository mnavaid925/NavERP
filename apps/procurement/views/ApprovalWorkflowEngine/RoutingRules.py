"""Procurement 6.3 Approval Workflow Engine — ApprovalRoutingRule views.

Rule WRITES are admin-gated (a rule decides how many signatures spend needs);
list/detail member-readable.
"""
from django.db.models import Count, Q

from apps.core.decorators import tenant_admin_required
from apps.procurement.forms import ApprovalRoutingRuleForm
from apps.procurement.models import ApprovalRoutingRule
from apps.procurement.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    return ApprovalRoutingRule.objects.filter(tenant=tenant).select_related("org_unit")


def _is_admin(request):
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


@login_required
def routingrule_list(request):
    qs = _scoped(request.tenant)
    totals = _scoped(request.tenant).aggregate(
        rules=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    return crud_list(
        request, qs, "procurement/approvalworkflow/routingrule/list.html",
        search_fields=["commodity", "notes", "org_unit__name"],
        filters=[("org", "org_unit_id", True), ("active", "is_active", False)],
        extra_context={
            "rule_count": totals["rules"],
            "active_count": totals["active"],
            "is_admin": _is_admin(request),
        },
    )


@login_required
def routingrule_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    # Neighbouring rules — the page shows what else competes for the same requisitions.
    sample = (ApprovalRoutingRule.objects.filter(tenant=request.tenant)
              .select_related("org_unit").exclude(pk=obj.pk)[:10])
    return render(request, "procurement/approvalworkflow/routingrule/detail.html", {
        "obj": obj,
        "other_rules": sample,
        "is_admin": _is_admin(request),
    })


@tenant_admin_required
def routingrule_create(request):
    return crud_create(
        request, form_class=ApprovalRoutingRuleForm,
        template="procurement/approvalworkflow/routingrule/form.html",
        success_url="procurement:routingrule_list",
    )


@tenant_admin_required
def routingrule_edit(request, pk):
    return crud_edit(
        request, model=ApprovalRoutingRule, pk=pk, form_class=ApprovalRoutingRuleForm,
        template="procurement/approvalworkflow/routingrule/form.html",
        success_url="procurement:routingrule_list",
    )


@tenant_admin_required
@require_POST
def routingrule_delete(request, pk):
    return crud_delete(request, model=ApprovalRoutingRule, pk=pk,
                       success_url="procurement:routingrule_list")
