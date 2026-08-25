"""Procurement 6.3 Approval Workflow Engine — ApprovalDelegation (DOA) views.

Grant WRITES are admin-gated like every other rule table; list/detail stay
member-readable so approvers can see whose authority they hold and until when.
"""
from django.db.models import Count, Q

from apps.core.decorators import tenant_admin_required
from apps.procurement.forms import ApprovalDelegationForm
from apps.procurement.models import ApprovalDelegation
from apps.procurement.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    return (ApprovalDelegation.objects.filter(tenant=tenant)
            .select_related("delegator", "delegate", "scope_org_unit"))


def _is_admin(request):
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


@login_required
def delegation_list(request):
    qs = _scoped(request.tenant)
    totals = qs.aggregate(
        grants=Count("id"),
        active_now=Count("id", filter=Q(is_active=True,
                                        valid_from__lte=timezone.localdate(),
                                        valid_until__gte=timezone.localdate())),
    )
    return crud_list(
        request, qs, "procurement/approvalworkflow/delegation/list.html",
        search_fields=["delegator__username", "delegate__username", "reason",
                       "scope_org_unit__name"],
        filters=[("state", "is_active", False)],
        extra_context={
            "grant_count": totals["grants"],
            "active_count": totals["active_now"],
            "today": timezone.localdate(),
            "is_admin": _is_admin(request),
        },
    )


@login_required
def delegation_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    credited = obj.approvals.select_related("requisition", "approver")[:10]
    return render(request, "procurement/approvalworkflow/delegation/detail.html", {
        "obj": obj,
        "credited": credited,
        "credit_count": obj.approvals.count(),
        "today": timezone.localdate(),
        "is_admin": _is_admin(request),
    })


@tenant_admin_required
def delegation_create(request):
    return crud_create(
        request, form_class=ApprovalDelegationForm,
        template="procurement/approvalworkflow/delegation/form.html",
        success_url="procurement:delegation_list",
    )


@tenant_admin_required
def delegation_edit(request, pk):
    return crud_edit(
        request, model=ApprovalDelegation, pk=pk, form_class=ApprovalDelegationForm,
        template="procurement/approvalworkflow/delegation/form.html",
        success_url="procurement:delegation_list",
    )


@tenant_admin_required
@require_POST
def delegation_delete(request, pk):
    return crud_delete(request, model=ApprovalDelegation, pk=pk,
                       success_url="procurement:delegation_list")
