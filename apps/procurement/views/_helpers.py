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
    # 6.17 Risk & Compliance Management. These belong on the procurement activity feed precisely
    # because they are the integrity records: a screening decision, a fraud disposition, a policy
    # sign-off and a seal are exactly the actions an auditor comes looking for. ``auditseal`` is
    # included for its CREATE rows — the seal itself is never edited or deleted.
    "compliancescreening",
    "screeninghit",
    "supplierrisksignal",
    "fraudalert",
    "policyattestation",
    "auditseal",
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


#: Leading characters a spreadsheet treats as the start of a formula. ``=+-@`` are the obvious
#: four; TAB and CR are here because Excel strips leading whitespace BEFORE deciding, so a cell
#: beginning with one of them followed by ``=`` still executes (the full OWASP set).
_CSV_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """Neutralize spreadsheet formula injection: prefix dangerous leading characters.

    Shared by more than one sub-module (Backend rule 5), which is why it lives here rather than in
    an entity module: 6.1's self-service requisition export, 6.14's spend export and 6.14's saved
    report / snapshot downloads all write user-authored text into a CSV. Supplier names, line
    descriptions, rule names and report titles are typed by people, and a reader's spreadsheet
    EXECUTES a cell that opens with ``=``, ``+``, ``-`` or ``@``. Prefixing an apostrophe makes the
    cell a string; nothing else about the value changes.

    The leading set is the full OWASP one, TAB and CR included: Excel strips leading whitespace
    before it decides what a cell is, so a cell opening TAB then ``=cmd|'/c calc'!A1`` reaches the reader as a formula
    while ``=cmd|...`` alone is caught. Four characters was the gap this inherited from 6.1.

    Supersedes the definition it replaced in ``views/DashboardPortal/SelfServiceReports.py``,
    which aliases this one — so every export in the app is covered by this single edit.
    """
    text = str(value)
    if text[:1] in _CSV_DANGEROUS:
        return f"'{text}"
    return text


# ---------------------------------------------------------------------------------------------
# 6.19 Document & Knowledge Management. Both helpers below are read by TWO entity modules of that
# one sub-module (Documents and Revisions), which is what puts them here rather than in either
# one (Backend rule 5). Neither is 6.19-only in spirit: a read rule and a "who holds it" label
# are exactly the things that must not be spelled two ways on two pages of the same register.
# ---------------------------------------------------------------------------------------------

#: The classifications every member of the workspace may read. ``confidential`` and ``restricted``
#: are deliberately absent - see :func:`readable_document_q`.
OPEN_CLASSIFICATIONS = ("public", "internal")

#: Printed on the document register, its detail page and its form, so the three places somebody
#: learns what a classification DOES cannot disagree - and so the tier documented as "the tier
#: above confidential, for records only a named few may read" describes what is enforced.
CLASSIFICATION_NOTE = (
    "Public and Internal documents are visible to everyone in the workspace. Confidential and "
    "Restricted ones are visible only to the document's owner, whoever created it, and workspace "
    "administrators - to everybody else they are absent from the register, from search, from the "
    "revision chain and from the text read out of the file."
)


def readable_document_q(user, prefix=""):
    """``Q()`` narrowing a ProcurementDocument queryset to what ``user`` is allowed to READ.

    ``classification`` used to be a label and nothing else: it was rendered as a badge, offered
    as a facet and stored on the row, and not one queryset, decorator or branch in the codebase
    read it to decide anything. That made ``?q=indemnity+cap`` a search INSIDE the body text of a
    restricted document for any member with an ordinary login, and ``?classification=restricted``
    an enumeration of exactly the need-to-know set.

    The rule, in one place so both entity modules enforce the same one:

    * ``public`` / ``internal`` - every member of the workspace, as before;
    * ``confidential`` / ``restricted`` - the named owner, whoever created the row, and workspace
      administrators. Everybody else gets a queryset that does not contain the document, so the
      register, the search, the facets, the detail page and every verb 404 identically. There is
      no separate "hidden" state to keep in sync.

    ``prefix`` reaches the same columns through a relation: pass ``"document__"`` from the
    revision side, where the parent's classification is what governs the child.

    This is deliberately NOT the full permission matrix - named readers, groups and inheritance
    are Module 13.7. It is the smallest rule that makes the tier mean something today, and it is
    stated to the user in :data:`CLASSIFICATION_NOTE` rather than left to be discovered.
    """
    if user is None or not user.is_authenticated:
        return Q(pk__in=[])
    if user.is_superuser or getattr(user, "is_tenant_admin", False):
        return Q()
    return (Q(**{f"{prefix}classification__in": OPEN_CLASSIFICATIONS})
            | Q(**{f"{prefix}owner_id": user.pk})
            | Q(**{f"{prefix}created_by_id": user.pk}))


def holder_name(user):
    """A person's name for a refusal message - never a bare pk.

    One definition for the two 6.19 view modules that refuse an action because somebody else
    holds a document's advisory checkout: the document verbs and the revision upload have to name
    the same person the same way, or the two refusals read like two different rules.
    """
    return (user.get_full_name() or user.username) if user is not None else "someone else"
