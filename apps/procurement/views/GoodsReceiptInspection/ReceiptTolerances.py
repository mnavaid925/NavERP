"""Procurement 6.12 Goods Receipt & Inspection — ReceiptTolerancePolicy views.

Reads are member-visible; every WRITE is admin-gated. A tolerance rule decides what the whole
workspace flags on the receiving dock, so it belongs in the same gated class as 5.15's QC routing
rules and 6.3's approval routing rules — a member who can book a receipt must not be able to
quietly widen the band that judges it.

The detail page's "governed lines" panel is the honest test of a rule: it runs the real resolver
over recent receipt lines and shows which ones THIS rule actually wins, rather than asserting a
scope in prose. It costs a fixed handful of queries regardless of how many lines it scans — the
rule list, the SKU map and the cumulative-received map are each fetched ONCE and reused.
"""
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Lower
from django.urls import reverse

from apps.procurement.forms import ReceiptTolerancePolicyForm
from apps.procurement.models import (
    ReceiptTolerancePolicy, evaluate_receipt_tolerance, resolve_receipt_tolerance,
)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import GoodsReceiptLine, Item

#: How many recent receipt lines the detail page scans to find the ones this rule governs, and how
#: many governed rows it then shows. Bounded so the panel stays a fixed cost on a busy workspace.
_GOVERNED_SCAN = 200
_GOVERNED_SHOWN = 20

#: The `?scope=` vocabulary as ORM predicates — ONE definition, used by the filter AND by the
#: catch-all stat card, so a card can never disagree with the list it links to.
_SCOPE_CONDITIONS = {
    "item": Q(item__isnull=False),
    "category": Q(item__isnull=True, category__isnull=False),
    "catchall": Q(item__isnull=True, category__isnull=True),
}


def _scoped(tenant):
    return (ReceiptTolerancePolicy.objects.filter(tenant=tenant)
            .select_related("item", "category", "vendor"))


def _is_admin(request):
    """Mirrors @tenant_admin_required exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _supplier_parties(tenant):
    """Supplier/vendor-role parties for the filter widget — the local-copy convention (peer
    sub-modules mirror this helper rather than importing each other's private names)."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


@login_required
def tolerancepolicy_list(request):
    """The tolerance register. ``?scope=`` narrows the QUERYSET before pagination (a Python-side
    filter over ``page_obj.object_list`` would filter the PAGE and make every count and page
    number describe a different set of rows than the one on screen). An unknown value is ignored
    and echoed back empty, so a hand-edited ``?scope=zzz`` still renders a 200."""
    base = _scoped(request.tenant)

    scope = request.GET.get("scope", "").strip()
    if scope not in _SCOPE_CONDITIONS:
        scope = ""  # unknown value: ignored, and echoed back empty so the widget reads "All"
    qs = base.filter(_SCOPE_CONDITIONS[scope]) if scope else base

    # ONE aggregate over the UNFILTERED tenant queryset — the cards describe the workspace, not
    # the current filter, and therefore never contradict the list they link to.
    stats = base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        flagging=Count("id", filter=Q(action="block_flag")),
        catch_all=Count("id", filter=_SCOPE_CONDITIONS["catchall"]),
    )

    return crud_list(
        request, qs, "procurement/goodsreceiptinspection/tolerancepolicy/list.html",
        search_fields=["name", "notes", "item__sku", "vendor__name"],
        filters=[
            ("action", "action", False),
            ("active", "is_active", False),
            ("item", "item_id", True),
            ("vendor", "vendor_id", True),
        ],
        extra_context={
            "action_choices": ReceiptTolerancePolicy.ACTION_CHOICES,
            "scope_choices": ReceiptTolerancePolicy.SCOPE_CHOICES,
            "items": (Item.objects.filter(tenant=request.tenant).order_by("sku")[:200]
                      if request.tenant is not None else Item.objects.none()),
            "vendors": _supplier_parties(request.tenant),
            "scope": scope,
            "stats": stats,
        },
    )


def _governed_lines(request, obj):
    """Recent receipt lines THIS rule actually wins, with each one's verdict.

    Fixed query cost: the active rule list once, the candidate lines once, the SKU→Item map once,
    and the cumulative received-per-PO-line map once. Resolution then runs in Python over those
    four results — never a query inside the loop.
    """
    tenant = request.tenant
    if tenant is None:
        return []

    rules = list(
        ReceiptTolerancePolicy.objects.filter(tenant=tenant, is_active=True)
        .select_related("item", "category", "vendor").order_by("priority", "id")
    )
    # An inactive rule governs nothing, so the panel would be empty AND misleading. Say so by
    # scanning nothing rather than by scanning and finding nothing.
    if not any(r.pk == obj.pk for r in rules):
        return []

    lines = list(
        GoodsReceiptLine.objects
        .filter(goods_receipt__tenant=tenant)
        .exclude(goods_receipt__status="cancelled")
        .select_related("goods_receipt", "goods_receipt__purchase_order",
                        "goods_receipt__purchase_order__vendor", "po_line")
        .order_by("-goods_receipt__receipt_date", "-id")[:_GOVERNED_SCAN]
    )
    if not lines:
        return []

    # GRN/PO lines are FREE TEXT (no item FK), so item resolution goes through sku_hint — batched
    # into ONE query instead of resolve_line_item() per row.
    skus = {(line.po_line.sku_hint or "").strip().lower()
            for line in lines if (line.po_line.sku_hint or "").strip()}
    item_map = {}
    if skus:
        # Lower() in the DB rather than fetching the whole item master and matching in Python:
        # same case-insensitive semantics as resolve_line_item()'s sku__iexact, one bounded query.
        for item in (Item.objects.filter(tenant=tenant)
                     .annotate(lower_sku=Lower("sku")).filter(lower_sku__in=skus)):
            item_map.setdefault(item.lower_sku, item)

    # Cumulative accepted quantity per PO line, mirroring PurchaseOrder.received_by_line()
    # semantics (a cancelled receipt never counts) across every order involved — ONE query.
    po_line_ids = {line.po_line_id for line in lines}
    received_map = dict(
        GoodsReceiptLine.objects.filter(po_line_id__in=po_line_ids)
        .exclude(goods_receipt__status="cancelled")
        .values("po_line_id").annotate(total=Sum("quantity_received"))
        .values_list("po_line_id", "total")
    )

    rows = []
    for line in lines:
        po_line = line.po_line
        receipt = line.goods_receipt
        order = receipt.purchase_order
        item = item_map.get((po_line.sku_hint or "").strip().lower())
        # `category` is deliberately omitted: the resolver falls back to item.category_id, which is
        # already loaded — passing the category OBJECT would fetch one row per item instead.
        rule, _reason = resolve_receipt_tolerance(
            item, getattr(order, "vendor", None), tenant=tenant, rules=rules,
        )
        if rule is None or rule.pk != obj.pk:
            continue
        received = received_map.get(po_line.pk) or Decimal("0")
        verdict, _v_reason = evaluate_receipt_tolerance(
            rule, ordered_quantity=po_line.quantity, received_quantity=received,
            expected_date=getattr(order, "expected_date", None),
            receipt_date=receipt.receipt_date,
        )
        rows.append({
            "receipt": receipt,
            "receipt_line": line,
            "po_line": po_line,
            "order": order,
            "description": po_line.item_description,
            "ordered": po_line.quantity,
            "received": received,
            "verdict": verdict,
            "verdict_css": ReceiptTolerancePolicy.VERDICT_CSS.get(verdict, "badge-muted"),
        })
        if len(rows) >= _GOVERNED_SHOWN:
            break
    return rows


@login_required
def tolerancepolicy_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    can_write = _is_admin(request)
    return render(request, "procurement/goodsreceiptinspection/tolerancepolicy/detail.html", {
        "obj": obj,
        # Derived on the model — the bands are a property of the rule, not of this page.
        "example": obj.worked_example(),
        "scope_label": obj.scope_label,
        "specificity_tier": obj.specificity_tier,
        "governed_lines": _governed_lines(request, obj),
        "advisory_note": "This policy flags; it never blocks scm:goodsreceipt_receive.",
        "can_edit": can_write,
        "can_delete": can_write,
    })


@login_required
@tenant_admin_required
def tolerancepolicy_create(request):
    return crud_create(
        request, form_class=ReceiptTolerancePolicyForm,
        template="procurement/goodsreceiptinspection/tolerancepolicy/form.html",
        success_url="procurement:tolerancepolicy_list",
    )


@login_required
@tenant_admin_required
def tolerancepolicy_edit(request, pk):
    return crud_edit(
        request, model=ReceiptTolerancePolicy, pk=pk, form_class=ReceiptTolerancePolicyForm,
        template="procurement/goodsreceiptinspection/tolerancepolicy/form.html",
        success_url=reverse("procurement:tolerancepolicy_detail", args=[pk]),
    )


@login_required
@tenant_admin_required
@require_POST
def tolerancepolicy_delete(request, pk):
    return crud_delete(request, model=ReceiptTolerancePolicy, pk=pk,
                       success_url="procurement:tolerancepolicy_list")
