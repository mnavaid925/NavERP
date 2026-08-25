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
from decimal import Decimal

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
    "sourcingevent",
    "sourcingbid",
    "rfxevent",
    "rfxresponse",
    "eauction",
    "eaucbid",
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

#: Cap on how many window candidates one check may load. The engine is O(window) by design (two
#: queries, then in-memory matching); without a ceiling a tenant with thousands of live requests
#: would materialize all of them on every register render. Newest N is the right cut: duplicates
#: are about what the workspace has been raising LATELY, and the register itself is newest-first.
DUPLICATE_CANDIDATE_CAP = 1000


def _duplicate_maps(tenant_id, window_days):
    """One-pass index of every LIVE requisition raised inside the window for a tenant, newest
    ``DUPLICATE_CANDIDATE_CAP`` rows at most.

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
    ).order_by("-id").values_list("id", "number", "title")[:DUPLICATE_CANDIDATE_CAP])
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
    # Tenant filter is defense-in-depth: the pks already come from the tenant-scoped map, but the
    # fetch itself should not RELY on that to stay inside the workspace.
    found = (PurchaseRequisition.objects
             .filter(pk__in=[pk for pk, _ in ordered], tenant_id=requisition.tenant_id)
             .select_related("requester", "org_unit"))
    reasons = dict(ordered)
    return [{"requisition": pr, "reasons": sorted(reasons[pr.pk])} for pr in found]


def _requisition_item_pairs(requisition_pks):
    """(requisition_pk, item_description) pairs for the given requisitions — one query."""
    from apps.scm.models import PurchaseRequisitionLine

    return list(PurchaseRequisitionLine.objects.filter(
        requisition_id__in=requisition_pks).values_list("requisition_id", "item_description"))


# -- 6.5 Sourcing & Tendering: evaluation + award math ---------------------------------------------
#
# The **Bid Evaluation Matrix** and **Award Recommendation** bullets are consumed by THREE
# surfaces — the event detail page (bid table scores), the bid detail page (one matrix) and the
# award board (scenarios across every closable event) — so the ranking lives HERE as one
# implementation. The math is deliberately simple and explainable; the single formula lives in
# ``models/SourcingTendering/Bids.weighted_total`` and every path below delegates to it, so the
# per-bid convenience method and the batch paths cannot drift apart.

def event_scores_map(event):
    """(criteria, {bid_id: {criterion_id: Decimal}}) for one event — two queries total.

    Batch form of ``SourcingBid.weighted_score`` for surfaces that render MANY bids: the
    per-bid method costs one query PER ROW, which is an N+1 on exactly the pages this module
    is about.
    """
    from collections import defaultdict

    from apps.procurement.models import BidScore

    criteria = list(event.criteria.all())
    score_map = defaultdict(dict)
    for bid_id, criterion_id, score in BidScore.objects.filter(
            bid__event=event).values_list("bid_id", "criterion_id", "score"):
        score_map[bid_id][criterion_id] = score
    return criteria, score_map


def weighted_from_map(score_map_row, criteria):
    """Weighted 0..100 score from ONE pre-fetched {criterion_id: score} row (or None).

    Delegates to the model-layer implementation — this wrapper exists only so the view
    modules keep one name for the batch path.
    """
    from apps.procurement.models.SourcingTendering.Bids import weighted_total

    return weighted_total(score_map_row, criteria)


def candidate_sort_key(row):
    """Deterministic award-scenario order: scored before unscored, higher score first,
    then cheaper whole-package price, then pk — a partial score never flatters itself."""
    return (
        row["score"] is None,                      # unscored candidates last, never first
        -(row["score"] or Decimal("0")),           # higher score wins
        row["bid"].total_price,                    # then cheaper whole-package price
        row["bid"].pk,                             # total order → stable page renders
    )


def evaluate_event(event, criteria=None, score_map=None):
    """Ranked **award scenarios** for one closed event.

    Returns rows of ``{"bid": bid, "score": Decimal|None}`` over COMPLIANT still-evaluable
    bids only, ranked by :func:`candidate_sort_key`. Callers that already hold the matrix
    (event detail re-uses its own fetch) pass ``criteria``/``score_map`` to skip the refetch.
    """
    from apps.procurement.models import SourcingBid

    if criteria is None or score_map is None:
        fetched_criteria, fetched_scores = event_scores_map(event)
        criteria = criteria if criteria is not None else fetched_criteria
        score_map = score_map if score_map is not None else fetched_scores
    bids = list(event.bids.filter(
        status__in=SourcingBid.EVALUABLE_STATUSES, is_compliant=True,
    ).select_related("supplier"))
    rows = [{"bid": bid, "score": weighted_from_map(score_map.get(bid.pk, {}), criteria)}
            for bid in bids]
    rows.sort(key=candidate_sort_key)
    return rows


def evaluate_events_batch(events):
    """Award scenarios for MANY events at ~4 queries total (the board's page budget).

    Returns ``{event_id: rows}`` with the same row shape as :func:`evaluate_event`.
    Criteria, scores and live compliant bids are each fetched once across the page's pks.
    """
    from collections import defaultdict

    from apps.procurement.models import BidScore, EventCriterion, SourcingBid

    pks = [e.pk for e in events]
    if not pks:
        return {}
    criteria_by_event = defaultdict(list)
    for criterion in EventCriterion.objects.filter(event_id__in=pks).order_by("id"):
        criteria_by_event[criterion.event_id].append(criterion)
    score_map = defaultdict(lambda: defaultdict(dict))
    for bid_id, criterion_id, event_id, score in BidScore.objects.filter(
            bid__event_id__in=pks).values_list(
                "bid_id", "criterion_id", "bid__event_id", "score"):
        score_map[event_id][bid_id][criterion_id] = score
    bids_by_event = defaultdict(list)
    for bid in (SourcingBid.objects
                .filter(event_id__in=pks,
                        status__in=SourcingBid.EVALUABLE_STATUSES, is_compliant=True)
                .select_related("supplier")):
        bids_by_event[bid.event_id].append(bid)

    result = {}
    for event in events:
        criteria = criteria_by_event.get(event.pk, [])
        rows = [{"bid": bid,
                 "score": weighted_from_map(score_map.get(event.pk, {}).get(bid.pk, {}), criteria)}
                for bid in bids_by_event.get(event.pk, [])]
        rows.sort(key=candidate_sort_key)
        result[event.pk] = rows
    return result
