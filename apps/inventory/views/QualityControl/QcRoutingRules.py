"""Inventory 5.15 Quality Control (QC) & Inspection — QcRoutingRule views.

Standard CRUD. Rule writes are ``@tenant_admin_required`` — a routing rule IS the
receiving gate (the 5.3 approval-rule reasoning); list/detail stay member-readable.
The detail page resolves the rule engine LIVE for one item so an operator can verify
what would fire before trusting it.
"""
from apps.core.crud import as_db_int
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import QcRoutingRuleForm
from apps.inventory.models import QcRoutingRule, resolve_qc_routing
from apps.inventory.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    """Tenant-scoped queryset with the joins every list page renders."""
    return (QcRoutingRule.objects.filter(tenant=tenant)
            .select_related("item", "category", "vendor", "qc_location"))


@login_required
def qcroutingrule_list(request):
    qs = _scoped(request.tenant)

    is_active = request.GET.get("is_active", "").strip()
    if is_active == "active":
        qs = qs.filter(is_active=True)
    elif is_active == "inactive":
        qs = qs.filter(is_active=False)

    verdict = request.GET.get("verdict", "").strip()
    if verdict in ("inspect", "bypass"):
        qs = qs.filter(verdict=verdict)

    return crud_list(
        request,
        qs,
        "inventory/qc/qcroutingrule/list.html",
        search_fields=["name", "notes", "item__sku", "item__name",
                       "category__name", "vendor__name"],
        filters=(),
        extra_context={
            "is_active_choices": [["active", "Active"], ["inactive", "Inactive"]],
            "is_active": is_active,
            "verdict_choices": QcRoutingRule.VERDICT_CHOICES,
            "verdict": verdict,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def qcroutingrule_detail(request, pk):
    from apps.scm.models import Item

    obj = get_object_or_404(_scoped(request.tenant), pk=pk)

    # Live resolution preview: ?item=<pk> runs the FULL engine exactly as the receiving
    # flow would, so the operator sees whether THIS rule or a more specific rival wins —
    # and an inactive rule honestly shows as never firing (the engine filters it).
    preview_item = None
    preview = None
    item_id = as_db_int(request.GET.get("item"))
    if item_id:
        preview_item = (Item.objects.filter(tenant=request.tenant)
                        .filter(pk=item_id).first())
    if preview_item is not None:
        winner, verdict, qc_location, reason = resolve_qc_routing(preview_item)
        preview = {"item": preview_item, "verdict": verdict,
                   "qc_location": qc_location, "reason": reason,
                   "is_this_rule": winner is not None and winner.pk == obj.pk}
    return render(request, "inventory/qc/qcroutingrule/detail.html", {
        "obj": obj,
        "preview": preview,
        "preview_item_id": item_id or "",
        # The resolver preview's picker — capped so a huge catalog can't bloat the page.
        "preview_items": Item.objects.filter(tenant=request.tenant).order_by("sku")[:50],
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@tenant_admin_required
def qcroutingrule_create(request):
    """Create a new inspection-routing rule."""
    return crud_create(
        request,
        form_class=QcRoutingRuleForm,
        template="inventory/qc/qcroutingrule/form.html",
        success_url="inventory:qcroutingrule_list",
    )


@tenant_admin_required
def qcroutingrule_edit(request, pk):
    """Edit an existing inspection-routing rule."""
    return crud_edit(
        request,
        model=QcRoutingRule,
        pk=pk,
        form_class=QcRoutingRuleForm,
        template="inventory/qc/qcroutingrule/form.html",
        success_url="inventory:qcroutingrule_list",
    )


@tenant_admin_required
@require_POST
def qcroutingrule_delete(request, pk):
    """Delete a routing rule."""
    return crud_delete(
        request,
        model=QcRoutingRule,
        pk=pk,
        success_url="inventory:qcroutingrule_list",
    )
