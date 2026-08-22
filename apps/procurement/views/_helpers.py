"""Private helpers shared by the procurement pages.

The activity feed over ``core.AuditLog`` is rendered on TWO surfaces — the overview widget and the
full Recent Activity Feed — so its queryset builder lives here rather than being duplicated with
the two definitions inevitably drifting. 6.2 adds its cross-entity engine to the same rule: the
duplicate requisition check is consumed by the tracking register (badge per row), the tracking
detail (panel with match reasons) and the template apply flow (post-apply warning), so it must be
ONE implementation, not three near-copies.

Helpers used by exactly one entity stay in that entity's module.
"""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.core.models import AuditLog

#: The audit trail is filtered to PROCUREMENT-relevant content types, not "everything the tenant
#: did": the feed answers "what happened to the things I buy". Requisition / PO / GRN / RFQ rows
#: are written by 4.1's views through the shared CRUD helpers; ``procurementalert`` covers this
#: module's own rows, and 6.2 adds its template/amendment layer. The list is the whitelist — new
#: procurement sub-modules append their models' lowercase table names here as they land.
PROCUREMENT_CONTENT_MODELS = (
    "purchaserequisition",
    "purchaseorder",
    "goodsreceiptnote",
    "rfq",
    "rfqquote",
    "procurementalert",
    "requisitiontemplate",
    "requisitionamendment",
)

#: Printed on both feed surfaces. One constant so the two cannot explain the trail differently.
ACTIVITY_FEED_NOTE = (
    "This feed is derived from the append-only audit trail — one row per create, update or "
    "delete on procurement documents. It is never edited or deleted here; corrections appear as "
    "new entries, which is what makes the sequence trustworthy."
)


def procurement_activity_qs(tenant):
    """Procurement-relevant ``core.AuditLog`` rows for a tenant, newest first.

    ``select_related`` covers every column the feed renders (user name, content-type label) —
    without it a full page of rows costs two queries PER ROW. The explicit ``-id`` tie-break makes
    the order TOTAL so a row never repeats or vanishes across a page boundary.
    """
    return (AuditLog.objects
            .filter(tenant=tenant)
            .filter(Q(content_type__app_label="procurement")
                    | Q(content_type__app_label="scm",
                        content_type__model__in=PROCUREMENT_CONTENT_MODELS))
            .select_related("user", "content_type")
            .order_by("-at", "-id"))


# -- 6.2 Duplicate Requisition Check --------------------------------------------------------------
#
# **Duplicate Requisition Check** bullet: "Automated flags for potential duplicate requests within
# a specific timeframe." The check is deliberately an EXPLAINABLE heuristic, not a score: two live
# requisitions are flagged as potential duplicates when they were raised inside the window AND
# match on the title or on any line item description (case/space-insensitive). Every flag names
# WHY it fired ("same title", "same item(s)"), so a reviewer can confirm or dismiss it in seconds.

#: "Within a specific timeframe" — the window the bullet leaves to configuration.
DUPLICATE_WINDOW_DAYS = 30

#: Only requests that could still turn into spend are worth flagging; rejected/cancelled ones are
#: noise by definition.
DUPLICATE_ACTIVE_STATUSES = ("draft", "pending_approval", "approved", "converted")

#: Cap on how many matches the detail panel renders — it is a review aid, not an export.
DUPLICATE_MATCH_LIMIT = 5


def _duplicate_maps(tenant_id, window_days):
    """One-pass index of every LIVE requisition raised inside the window for a tenant.

    Returns ``(by_pk, title_map, item_map)`` where ``title_map``/``item_map`` key the
    normalised title / item description to the pks that carry them. Two queries total,
    independent of how many rows are being checked — that is what lets the tracking register
    badge a whole page without an N+1.
    """
    from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine

    cutoff = timezone.now() - timedelta(days=window_days)
    rows = list(PurchaseRequisition.objects.filter(
        tenant_id=tenant_id,
        created_at__gte=cutoff,
        status__in=DUPLICATE_ACTIVE_STATUSES,
    ).values_list("id", "number", "title"))
    item_rows = list(PurchaseRequisitionLine.objects.filter(
        requisition_id__in=[r[0] for r in rows],
    ).values_list("requisition_id", "item_description"))

    by_pk = {r[0]: {"number": r[1], "title": r[2]} for r in rows}
    title_map = defaultdict(list)
    item_map = defaultdict(list)
    for pk, _number, title in rows:
        key = " ".join((title or "").split()).lower()
        if key:
            title_map[key].append(pk)
    for req_pk, description in item_rows:
        key = " ".join((description or "").split()).lower()
        if key:
            item_map[key].append(req_pk)
    return by_pk, title_map, item_map


def duplicate_pk_set(tenant_id, requisitions, window_days=DUPLICATE_WINDOW_DAYS):
    """Which of ``requisitions`` (one page's worth) have at least one potential duplicate."""
    pks = [r.pk for r in requisitions]
    if not pks:
        return set()
    by_pk, title_map, item_map = _duplicate_maps(tenant_id, window_days)
    items_by_req = defaultdict(set)
    for req_pk, description in _requisition_item_pairs(pks):
        items_by_req[req_pk].add(description)
    flagged = set()
    for pk in pks:
        if pk not in by_pk:
            continue  # older than the window / terminal status — outside the check's reach
        title_key = " ".join((by_pk[pk]["title"] or "").split()).lower()
        others = {other for other in title_map.get(title_key, []) if other != pk}
        for key in items_by_req.get(pk, ()):
            others.update(other for other in item_map.get(key, []) if other != pk)
        if others:
            flagged.add(pk)
    return flagged


def find_duplicate_requisitions(requisition, window_days=DUPLICATE_WINDOW_DAYS):
    """Full explanation for ONE requisition: ``[{"requisition": pr, "reasons": [str, …]}, …]``.

    Reasons are human phrases ("same title", "same item: '…'") so the panel can show its work;
    nothing here pretends to be more than a deterministic text match.
    """
    from apps.scm.models import PurchaseRequisition

    by_pk, title_map, item_map = _duplicate_maps(requisition.tenant_id, window_days)
    if requisition.pk not in by_pk:
        return []  # terminal status or outside the window — the check does not apply to it

    title_key = " ".join((requisition.title or "").split()).lower()
    candidates = defaultdict(set)  # other_pk -> set of reason strings
    if title_key:
        for other in title_map.get(title_key, []):
            if other != requisition.pk:
                candidates[other].add("same title")
    my_items = {}
    for req_pk, description in _requisition_item_pairs([requisition.pk]):
        if req_pk == requisition.pk:
            my_items[" ".join((description or "").split()).lower()] = description
    for key, original in my_items.items():
        for other in item_map.get(key, []):
            if other != requisition.pk and key:
                candidates[other].add(f"same item: '{original}'")

    ordered = sorted(candidates.items(), key=lambda kv: kv[0], reverse=True)[:DUPLICATE_MATCH_LIMIT]
    if not ordered:
        return []
    found = (PurchaseRequisition.objects.filter(pk__in=[pk for pk, _ in ordered])
             .select_related("requester", "org_unit"))
    reasons = dict(ordered)
    return [{"requisition": pr, "reasons": sorted(reasons[pr.pk])} for pr in found]


def _requisition_item_pairs(requisition_pks):
    """(requisition_pk, item_description) pairs for the given requisitions — one query."""
    from apps.scm.models import PurchaseRequisitionLine

    return list(PurchaseRequisitionLine.objects.filter(
        requisition_id__in=requisition_pks).values_list("requisition_id", "item_description"))
