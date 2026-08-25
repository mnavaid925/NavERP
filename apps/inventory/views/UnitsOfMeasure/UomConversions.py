"""Inventory 5.20 Units of Measure (UOM) — UomConversion views.

CRUD over the conversion catalog. Rule WRITES are admin-gated
(``@tenant_admin_required``) — a wrong factor silently re-prices every converted
quantity in the workspace, which is a config decision, not an operator one; list and
detail stay member-readable.
"""
from decimal import Decimal

from django.db.models import Q

from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import UomConversionForm
from apps.inventory.models import UomConversion
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import Item


def _scoped(tenant):
    return (UomConversion.objects.filter(tenant=tenant)
            .select_related("item", "from_uom", "to_uom"))


def _is_admin(request):
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


@login_required
def uomconversion_list(request):
    qs = _scoped(request.tenant)
    # Scope lens parsed BEFORE pagination (filter rules): all | default | item.
    scope = request.GET.get("scope", "").strip()
    if scope == "default":
        qs = qs.filter(item__isnull=True)
    elif scope == "item":
        qs = qs.filter(item__isnull=False)
    else:
        scope = ""
    return crud_list(
        request, qs, "inventory/uom/uomconversion/list.html",
        search_fields=["item__sku", "item__name", "from_uom__code", "to_uom__code", "notes"],
        filters=[("item", "item_id", True), ("active", "is_active", False)],
        extra_context={
            "scope": scope,
            "is_admin": _is_admin(request),
            "default_count": UomConversion.objects.filter(
                tenant=request.tenant, item__isnull=True).count(),
            "rule_count": UomConversion.objects.filter(tenant=request.tenant).count(),
            "items": Item.objects.filter(tenant=request.tenant).order_by("sku"),
        },
    )


@login_required
def uomconversion_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    # Sibling rules over the same units — the detail page shows which tier wins.
    rivals = (_scoped(request.tenant)
              .filter(from_uom_id=obj.from_uom_id, to_uom_id=obj.to_uom_id)
              .exclude(pk=obj.pk)[:10])
    # The edges this rule's scope could hop through (its item's rows + defaults).
    if obj.item_id:
        neighbours = (_scoped(request.tenant)
                      .filter(Q(item_id=obj.item_id) | Q(item__isnull=True))
                      .exclude(pk=obj.pk)[:10])
    else:
        neighbours = _scoped(request.tenant).exclude(pk=obj.pk)[:10]
    return render(request, "inventory/uom/uomconversion/detail.html", {
        "obj": obj,
        "rivals": rivals,
        "neighbours": neighbours,
        "is_admin": _is_admin(request),
        # Sample ladder through this one rule — the reading a dock operator wants.
        "ladder": [(qty, obj.convert(qty)) for qty in (Decimal("1"), Decimal("5"),
                                                       Decimal("10"), Decimal("100"))],
    })


@tenant_admin_required
def uomconversion_create(request):
    return crud_create(
        request, form_class=UomConversionForm,
        template="inventory/uom/uomconversion/form.html",
        success_url="inventory:uomconversion_list",
    )


@tenant_admin_required
def uomconversion_edit(request, pk):
    return crud_edit(
        request, model=UomConversion, pk=pk, form_class=UomConversionForm,
        template="inventory/uom/uomconversion/form.html",
        success_url="inventory:uomconversion_list",
    )


@tenant_admin_required
@require_POST
def uomconversion_delete(request, pk):
    return crud_delete(request, model=UomConversion, pk=pk,
                       success_url="inventory:uomconversion_list")
