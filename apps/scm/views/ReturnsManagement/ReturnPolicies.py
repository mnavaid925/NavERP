"""SCM 4.10 Returns Management — ReturnPolicy views (the published promise).

No sidebar key, same precedent as ``ReturnReason``: a policy is configuration, reached from the
return-portal console where the customer-facing promise is reviewed alongside it.

``returnpolicy_delete`` uses the GENERIC ``except ProtectedError`` (§7.4) —
``ReturnAuthorization.policy`` is PROTECT, and deliberately so: a policy that could be deleted out
from under a frozen ``policy_snapshot`` would leave a decision nobody can trace back to its rules.
"""
from django.db.models import ProtectedError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import ItemCategory, ReturnAuthorization, ReturnPolicy
from apps.scm.forms import ReturnPolicyForm


@login_required
def returnpolicy_list(request):
    qs = (ReturnPolicy.objects.filter(tenant=request.tenant)
          .select_related("item_category")
          # `_agg` suffix per §7.3 — never a bare `return_authorizations`, which is the reverse
          # accessor's own name and would shadow it on the row.
          .annotate(rma_count_agg=Count("return_authorizations", distinct=True))
          # Explicit: annotate() sets a GROUP BY, which unsets QuerySet.ordered and drops
          # Meta.ordering from the SQL, so the paginator warns and the page split is unstable.
          .order_by("priority", "name"))
    stats = ReturnPolicy.objects.filter(tenant=request.tenant).aggregate(
        active=Count("id", filter=Q(is_active=True)),
        default=Count("id", filter=Q(is_default=True)),
        auto_approve=Count("id", filter=Q(auto_approve=True)),
        keep_item=Count("id", filter=Q(allow_keep_item=True)),
    )
    return crud_list(
        request, qs, "scm/returns/returnpolicy/list.html",
        search_fields=["name", "return_to_address", "portal_instructions"],
        filters=[("window_basis", "window_basis", False), ("is_active", "is_active", False),
                 ("refund_basis", "refund_basis", False),
                 ("restocking_fee_type", "restocking_fee_type", False),
                 ("item_category", "item_category_id", True)],
        extra_context={
            "basis_choices": ReturnPolicy.WINDOW_BASIS_CHOICES,
            "refund_basis_choices": ReturnPolicy.REFUND_BASIS_CHOICES,
            "fee_choices": ReturnPolicy.RESTOCKING_FEE_CHOICES,
            "categories": ItemCategory.objects.filter(tenant=request.tenant).order_by("name"),
            "stats": stats,
        },
    )


@login_required
def returnpolicy_create(request):
    if _need_tenant(request):
        return redirect("scm:returnpolicy_list")
    return crud_create(request, form_class=ReturnPolicyForm,
                       template="scm/returns/returnpolicy/form.html",
                       success_url="scm:returnpolicy_list")


@login_required
def returnpolicy_edit(request, pk):
    return crud_edit(request, model=ReturnPolicy, pk=pk, form_class=ReturnPolicyForm,
                     template="scm/returns/returnpolicy/form.html",
                     success_url="scm:returnpolicy_list")


@login_required
def returnpolicy_detail(request, pk):
    obj = get_object_or_404(ReturnPolicy.objects.select_related("item_category"),
                            pk=pk, tenant=request.tenant)
    return render(request, "scm/returns/returnpolicy/detail.html", {
        "obj": obj,
        "allowed_resolutions": obj.allowed_resolutions,
        # The grade ladder rendered as rows so the template does not have to know four field names.
        "grade_ladder": [
            {"grade": grade.upper(), "label": label, "pct": obj.grade_cost_pct(grade)}
            for grade, label in (("a", "As new, sellable"), ("b", "Light wear, refurbishable"),
                                 ("c", "Heavy wear, secondary channel"), ("d", "Unsellable"))
        ],
        "return_authorizations": (
            ReturnAuthorization.objects.filter(tenant=request.tenant, policy=obj)
            .select_related("customer")[:25]),
    })


@login_required
@require_POST
def returnpolicy_delete(request, pk):
    """Generic ProtectedError guard (§7.4). See ``returnreason_delete`` for why not ``.exists()``."""
    get_object_or_404(ReturnPolicy.objects.only("pk"), pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            return crud_delete(request, model=ReturnPolicy, pk=pk,
                               success_url="scm:returnpolicy_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"This policy is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "deactivate it instead so past decisions keep the rules they were made under.")
        return redirect("scm:returnpolicy_detail", pk=pk)
