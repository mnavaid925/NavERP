"""Inventory 5.4 Receiving & Putaway — PutawayRule CRUD + the computed suggestions queue.

Five thin CRUD wrappers over apps.core.crud, plus ONE genuinely custom page:
``putaway_suggestions`` is a COMPUTED view over SCM 4.4's open putaway tasks — it owns no
table and writes NOTHING into scm (the only action offered is ``scm:putawaytask_edit``).
Every row is resolved by :func:`resolve_putaway_suggestion`, so what the page shows is an
explainable suggestion or the honest "No Suggestion Found" refusal, never a guess.

Like sibling 5.3's approval rules, the RULE WRITES are tenant-admin gated (a routing rule
decides where every arrival goes): reads stay open to every signed-in member, while
create/edit/delete carry ``core.decorators.tenant_admin_required`` and the list/detail
templates hide the affordances to match.

Ordering of operations on the queue is deliberate: search + warehouse filter apply to the
queryset BEFORE pagination; pagination happens at 25/page in the database via
core.crud.paginate; only then does the resolver run — one pass over the full filtered set
feeds BOTH the stats strip and the current page's rows, so a page render never pays for
resolution twice and stats always describe the whole queue, not just the visible page.
"""
from django.db.models import Q, Sum

from apps.core.decorators import tenant_admin_required
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.core.crud import as_db_int, paginate
# Direct entity-module paths rather than the package roots: the package __init__ re-export
# blocks are integrate-phase wiring; both spellings resolve to the same objects once landed.
from apps.inventory.forms.ReceivingPutaway.PutawayRules import PutawayRuleForm
from apps.inventory.models.ReceivingPutaway.PutawayRules import (
    PutawayRule,
    resolve_putaway_suggestion,
)
from apps.scm.models import Location, PutawayTask, StockMove

#: Ancestry-walk budget for the warehouse filter — same posture as the model's resolver.
_MAX_ANCESTRY_HOPS = 8


@login_required
def putawayrule_list(request):
    qs = (PutawayRule.objects.filter(tenant=request.tenant)
          .select_related("item", "category", "source_location", "destination"))
    # The Active/Inactive chip maps to a boolean BEFORE crud_list runs (house filter rule:
    # parse GET, shape the queryset, THEN let the helper paginate/render it).
    is_active = request.GET.get("is_active", "").strip()
    if is_active == "active":
        qs = qs.filter(is_active=True)
    elif is_active == "inactive":
        qs = qs.filter(is_active=False)
    return crud_list(
        request, qs, "inventory/receiving/putawayrule/list.html",
        search_fields=["item__sku", "item__name", "destination__code"],
        filters=(),
        extra_context={
            "is_active_choices": [["active", "Active"], ["inactive", "Inactive"]],
            "is_active": is_active,
            # Writes are tenant-admin gated server-side; hide the affordances to match.
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def putawayrule_create(request):
    return crud_create(
        request, form_class=PutawayRuleForm,
        template="inventory/receiving/putawayrule/form.html",
        success_url="inventory:putawayrule_list",
    )


@login_required
def putawayrule_detail(request, pk):
    return crud_detail(
        request, model=PutawayRule, pk=pk,
        template="inventory/receiving/putawayrule/detail.html",
        select_related=("item", "category", "source_location", "destination"),
        extra_context={
            # Same flag as the list: Edit/Delete render only for admins.
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def putawayrule_edit(request, pk):
    return crud_edit(
        request, model=PutawayRule, pk=pk, form_class=PutawayRuleForm,
        template="inventory/receiving/putawayrule/form.html",
        success_url="inventory:putawayrule_list",
    )


@tenant_admin_required
@require_POST
def putawayrule_delete(request, pk):
    return crud_delete(request, model=PutawayRule, pk=pk,
                       success_url="inventory:putawayrule_list")


def _ancestry_contains(parent_map, start_pk, ancestor_pk):
    """True when ``ancestor_pk`` IS ``start_pk`` or sits anywhere on its parent chain —
    a task staged AT the warehouse row itself belongs to that warehouse's filter too.
    Walks a preloaded {pk: parent_pk} map — dict hops, zero queries — cycle-guarded exactly
    like ``Location.path()`` so a malformed self-parent row costs a few hops, not a hung page."""
    if start_pk == ancestor_pk:
        return True
    node, seen, hops = parent_map.get(start_pk), {start_pk}, 0
    while node is not None and node not in seen and hops <= _MAX_ANCESTRY_HOPS:
        if node == ancestor_pk:
            return True
        seen.add(node)
        node = parent_map.get(node)
        hops += 1
    return False


@login_required
def putaway_suggestions(request):
    """The directed-putaway queue: every open task with its best bin and why.

    Read-only by construction — nothing here mutates a PutawayTask. The operator either
    accepts the suggestion by editing the task IN SCM (scm:putawaytask_edit) or reads the
    refusal and overrides the destination by hand there too.
    """
    qs = (PutawayTask.objects.filter(tenant=request.tenant,
                                     status__in=PutawayTask.OPEN_STATUSES)
          .select_related("item", "from_location", "to_location", "goods_receipt"))

    # --- filters BEFORE pagination -------------------------------------------------------
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(item__sku__icontains=q))

    # as_db_int guard: ?warehouse=abc / ?warehouse=² / ?warehouse=<2^63> are all "not a pk"
    # and skip the filter instead of raising inside the driver (L11). An unknown-but-valid
    # pk is treated the same way — junk ignored beats an silently-empty page.
    warehouse = request.GET.get("warehouse", "").strip()
    warehouse_pk = as_db_int(warehouse)
    if warehouse_pk is not None and Location.objects.filter(
            tenant=request.tenant, pk=warehouse_pk).exists():
        parent_map = dict(Location.objects.filter(tenant=request.tenant)
                          .values_list("pk", "parent_id"))
        open_pks = list(qs.values_list("from_location_id", flat=True))
        under = {pk for pk in open_pks
                 if _ancestry_contains(parent_map, pk, warehouse_pk)}
        qs = qs.filter(from_location_id__in=under)

    # --- paginate FIRST, then resolve ------------------------------------------------------
    page_obj = paginate(request, qs, 25)

    # One resolution pass over the FULL filtered set feeds the stats strip AND the page
    # rows (cached by pk) — stats must describe the whole queue, and re-running the
    # resolver twice per task would double the cost for the identical numbers.
    #
    # The three resolver inputs are PRELOADED once for the whole request so a task count
    # of N costs 3 queries total instead of ~3N: active rules, the tenant location map,
    # and ONE StockMove GROUP BY over every distinct task item feeding an
    # {item_id: {location_id: qty}} map. Resolution itself stays in the model layer.
    tasks = list(qs)
    rules, by_pk, on_hand = [], {}, {}
    if tasks:
        rules = list(
            PutawayRule.objects.filter(tenant=request.tenant, is_active=True)
            .select_related("item", "category", "source_location", "destination")
            .order_by("priority", "id"))
        by_pk = {loc.pk: loc for loc in Location.objects.filter(tenant=request.tenant)}
        for item_id, location_id, held in (
                StockMove.objects.filter(
                    tenant=request.tenant,
                    item_id__in={t.item_id for t in tasks})
                .values("item", "location").annotate(held=Sum("quantity"))
                .values_list("item", "location", "held")):
            on_hand.setdefault(item_id, {})[location_id] = held

    resolved, open_tasks, covered_by_rule = {}, 0, 0
    for task in tasks:
        open_tasks += 1
        suggestion, reason, candidates = resolve_putaway_suggestion(
            task, rules=rules, by_pk=by_pk, on_hand=on_hand)
        resolved[task.pk] = (suggestion, reason, candidates)
        if reason.startswith("Rule:"):
            covered_by_rule += 1

    rows = []
    for task in page_obj.object_list:
        suggestion, reason, candidates = resolved[task.pk]
        rows.append({
            "task": task,
            "receipt": task.goods_receipt,
            "item": task.item,
            "staging": task.from_location,
            "candidates": candidates,
            "suggestion": suggestion,
            "suggestion_reason": reason,
        })

    return render(request, "inventory/receiving/putaway_suggestions.html", {
        "rows": rows,
        "stats": {
            "open_tasks": open_tasks,
            "covered_by_rule": covered_by_rule,
            "uncovered": open_tasks - covered_by_rule,
        },
        "page_obj": page_obj,
        "warehouses": Location.objects.filter(tenant=request.tenant,
                                              location_type="warehouse").order_by("code"),
        "q": q,
        "warehouse": warehouse,
    })
