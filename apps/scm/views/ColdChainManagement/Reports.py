"""SCM 4.15 Cold Chain Management — three COMPUTED pages. **No new table, no new column.**

Three of this sub-module's five NavERP bullets are PAGES rather than tables, and that is the headline
fact about 4.15. Everything below is derived from rows that already exist — the
``sparepart_list`` / ``labor_board`` / ``valuation_report`` precedent:

* :func:`cold_storage_report` — "Cold Storage Inventory", computed over **4.3**. On-hand comes from
  the append-only ``StockMove`` ledger (there is no stored quantity anywhere to drift from it), the
  condition mismatch comes from the two ``storage_condition`` columns, expiry comes from
  ``LotSerial.expiry_date`` and quarantine comes from ``LotSerial.status`` — **which 4.9's
  non-conformance verb writes and 4.15 only ever READS.** 4.15 declares no zone table, no shelf-life
  table and no second stock figure.
* :func:`cold_chain_compliance_report` — "Compliance Reporting". The excursion log is 4.15's own
  rows filtered by window; the temperature profile (min / max / mean, % time in range, time out of
  range, MKT) is fully derived over ``TemperatureReading`` through ``apps/scm/coldchain.py``; the
  audit trail is ``core.AuditLog`` via ``write_audit_log()`` — **there is no second audit table.**
  The only genuinely persistent artefact is the monitor's calibration triple, because an
  uncalibrated sensor invalidates every record it produced.
* :func:`reefer_board` — "Maintenance of Reefers", computed over **4.13**. Every column on it is
  4.13's: ``MaintenancePlan.due_status()``, the open ``MaintenanceWorkOrder`` queue, the run-hours
  meter through ``Asset.latest_reading()`` and ``Asset.warranty_chip()``. **4.15 declares ZERO
  maintenance entities and adds no value to any 4.13 vocabulary.** What identifies a reefer is
  *an Asset that has an active ColdChainMonitor* — which needs no change to 4.13 at all and cannot go
  stale the way a hand-set ``asset_type`` would.

--------------------------------------------------------------------------------------------------
TWO STANDING RULES THIS MODULE IS BUILT AROUND
--------------------------------------------------------------------------------------------------
**1. Coverage, not a confident zero** (the 4.11 lesson, restated by 4.12's carbon report and 4.13's
depreciation report). A monitor with no readings has no % time in range; a frozen monitor has no MKT
(USP <1079.2>); a lot with no expiry date has no days-to-expiry. Those rows are COUNTED and reported
as excluded rather than folded in as zero — a green 0 that actually means "we had no data" is worse
than a blank, because a blank makes somebody go and look. **All three pages render 200 on an EMPTY
tenant** with honest zero-coverage lines and ``None`` totals; none of them may 500 on a first run.

**2. These pages WRITE NOTHING.** No ``StockMove``, no ``JournalEntry`` (L29), no ``LotSerial``
status, no ``Asset`` column, no ``MaintenancePlan``. They are GET pages with query-string options and
one CSV download; there is not a POST route between them.

--------------------------------------------------------------------------------------------------
QUERY HYGIENE
--------------------------------------------------------------------------------------------------
Nothing here calls a per-row method that queries. ``Item.on_hand()``, ``LotSerial.on_hand()`` and
``Asset.latest_reading()`` are all correct and all fire their own query, so each is replaced by ONE
grouped aggregate over the page's ids (or, for the reefer board's meter, by a scalar subquery whose
result PRIMES ``MaintenancePlan._latest_reading_cache`` — so the model still answers ``due_status()``
and simply never has to ask the database). Every section is capped with a queryset SLICE, so the cap
bounds what is FETCHED rather than merely what is rendered (L40 §1).
"""
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _item_qs, _location_qs, _report_window

from apps.scm import coldchain
from apps.scm.models import (
    ASSESSMENT_CHOICES,
    Asset,
    CALIBRATION_NOTICE_DAYS,
    COLD_CONDITIONS,
    CRITICALITY_CHOICES,
    ColdChainMonitor,
    EXCURSION_STATUS_CHOICES,
    Item,
    Location,
    LotSerial,
    MAX_READING_WINDOW_DAYS,
    MaintenancePlan,
    MaintenanceWorkOrder,
    MeterReading,
    OPEN_EXCURSION_STATUSES,
    STORAGE_CONDITION_CHOICES,
    StockMove,
    TemperatureExcursion,
    TemperatureReading,
)
from apps.scm.models._base import ZERO
# The ONE CSV writer in the app: it applies the formula-injection escape to every cell and writes the
# UTF-8 BOM Excel needs to render the prose in these exports without mojibake. Imported rather than
# copied — the 4.14 payroll export does exactly the same (`LaborManagement/Reports.py:163`).
from apps.scm.views.SupplyChainAnalytics.Reports import _csv_response
from apps.scm.views.ColdChainManagement.ColdChainMonitors import (
    CALIBRATION_NOTE,
    FROZEN_MKT_NOTE,
    _latest_reading_pk,
    _monitor_qs,
)


# =================================================================================================
# Page constants
# =================================================================================================

#: Rows each section of a report page shows. Applied as a queryset SLICE and reported when it bites,
#: so the page can say it is showing a window rather than pretending the window is the total.
MAX_REPORT_ROWS = 100

#: Monitors the compliance report will PROFILE. Each profile is two bounded queries plus a walk of up
#: to ``MAX_EPISODE_READINGS`` rows, so this is the one figure on these pages that scales with the
#: number of rows — and it is therefore the one that has to be capped rather than paginated. The page
#: says so and points at the ``?monitor=`` filter for a specific point.
MAX_PROFILED_MONITORS = 12

#: The expiry horizon on the cold-storage page, in days. CLAMPED, never trusted: the value is fed to
#: ``timedelta(days=…)`` and an unbounded one out of the query string is an ``OverflowError`` — a
#: 500, from a URL anybody can type (the 4.10 finding).
DEFAULT_EXPIRING_DAYS = 30
MIN_EXPIRING_DAYS = 1
MAX_EXPIRING_DAYS = 365
EXPIRING_DAY_OPTIONS = [7, 14, 30, 60, 90, 180, 365]

#: The cold-storage page's five sections. ``?view=`` chooses which one opens; ALL five are computed
#: either way, because the header chips have to describe the same data the table shows and a page
#: whose chips counted something else would contradict itself (the ``reorder_alerts`` posture).
COLD_STORAGE_VIEWS = [
    ("on_hand", "Cold on-hand by location"),
    ("mismatch", "Condition mismatches"),
    ("expiring", "Expiring and expired"),
    ("quarantined", "Quarantined lots"),
    ("unmonitored", "Unmonitored cold storage"),
]

#: Warm -> cold, taken from the order ``STORAGE_CONDITION_CHOICES`` is declared in. Used for ONE
#: thing: labelling a mismatch as "too warm" or "too cold". It is deliberately NOT a compatibility
#: rule — a frozen room does not "satisfy" a chilled item, it freeze-damages it — so the mismatch
#: test itself is exact inequality and this rank only decides which sentence to print.
_CONDITION_RANK = {value: index for index, (value, _label) in enumerate(STORAGE_CONDITION_CHOICES)}

#: Wide output field for the ``quantity x unit_cost`` sums below. A value over a whole workspace
#: routinely exceeds the 14-digit shape of either operand, and Django sizes the expression from the
#: FIRST operand's field unless told otherwise — which is a ``DataError`` on a report, from data that
#: is individually perfectly valid.
_MONEY = models.DecimalField(max_digits=24, decimal_places=4)


def _aware_bounds(date_from, date_to):
    """A date pair as the inclusive AWARE datetime range covering both days end to end.

    ``time.max`` on the upper bound so an episode that started at 16:00 on the closing day is inside
    the window somebody asked for — a bare date resolves to midnight and would drop the final day.
    An explicit range rather than ``__date__gte``: ``__date`` compiles to ``CONVERT_TZ`` on MariaDB
    and returns NULL when the timezone tables are not loaded, which on XAMPP they are not.
    """
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
        end = timezone.make_aware(end)
    return start, end


def _expiry_horizon(request):
    """``(days, raw, invalid)`` — ``?expiring_within=N`` clamped to 1..365.

    Four bad inputs, one posture: ``?expiring_within=abc``, ``=-5`` and ``=²`` are all refused by
    ``as_db_int`` (``isdecimal()`` is precisely ``int()``'s accepted set, and a minus sign is not in
    it), an over-range value is refused as such, and an in-range but absurd one is CLAMPED. Nothing
    raises. ``invalid`` is returned so the page can say "showing the default horizon" instead of
    silently ignoring what somebody asked for.
    """
    raw = (request.GET.get("expiring_within") or "").strip()
    if not raw:
        return DEFAULT_EXPIRING_DAYS, "", False
    number = as_db_int(raw)
    if number is None:
        return DEFAULT_EXPIRING_DAYS, raw, True
    clamped = min(max(number, MIN_EXPIRING_DAYS), MAX_EXPIRING_DAYS)
    return clamped, raw, clamped != number


def _mismatch_kind(item_condition, location_condition):
    """``("too_warm" | "too_cold" | "unclassified", sentence)`` for one mismatched row.

    The rank only decides the wording — see :data:`_CONDITION_RANK`. An UNCLASSIFIED location is its
    own kind and never "too warm": a blank ``storage_condition`` means nobody has said what that bin
    provides, which is a data gap somebody can close in one edit, not a measured breach.
    """
    item_label = dict(STORAGE_CONDITION_CHOICES).get(item_condition, item_condition)
    if not location_condition:
        return ("unclassified",
                f"This bin has no temperature class recorded, and the item requires {item_label}. "
                "Classify the location, or move the stock.")
    location_label = dict(STORAGE_CONDITION_CHOICES).get(location_condition, location_condition)
    if _CONDITION_RANK.get(location_condition, 0) < _CONDITION_RANK.get(item_condition, 0):
        return ("too_warm",
                f"Stored at {location_label} but the item requires {item_label} — this bin is too "
                "warm for it.")
    return ("too_cold",
            f"Stored at {location_label} but the item requires {item_label} — this bin is colder "
            "than the item is rated for, which is its own kind of damage.")


def _lot_on_hand(tenant, lots):
    """``{lot_id: Decimal}`` from ONE grouped aggregate over the ledger.

    ``LotSerial.on_hand()`` is correct and fires its own aggregate, so asking it per row is one query
    per lot. The explicit ``tenant=`` narrows nothing (the lots are this workspace's) and is stated
    anyway so the query holds to the module-wide rule mechanically.

    ``.order_by()`` is load-bearing: an inherited ``Meta.ordering`` column would be dragged into the
    GROUP BY and split the sum per item SKU.
    """
    ids = [lot.pk for lot in lots]
    if not ids:
        return {}
    return dict(StockMove.objects
                .filter(tenant=tenant, lot_serial_id__in=ids)
                .order_by()
                .values_list("lot_serial_id")
                .annotate(qty=Sum("quantity")))


# =================================================================================================
# Report 1 — Cold Storage Inventory (computed over 4.3, and over 4.9's lot status)
# =================================================================================================
@login_required
def cold_storage_report(request):
    """Five real questions about refrigerated stock, all of them derived and none of them stored.

    **Filter GET params:**

    * ``storage_condition`` — one of ``STORAGE_CONDITION_CHOICES``; narrows every section
    * ``location`` — a pk, through :func:`as_db_int` (L11)
    * ``expiring_within`` — days, CLAMPED to 1..365 (see :func:`_expiry_horizon`)
    * ``view`` — ``on_hand`` / ``mismatch`` / ``expiring`` / ``quarantined`` / ``unmonitored``; picks
      which section opens. All five are computed regardless, so the header chips and the table cannot
      disagree.

    **The five sections, and why each earns its place:**

    1. ``on_hand_rows`` — cold on-hand by location: what is actually in the refrigerated bins, from
       the ``StockMove`` ledger. Rows whose moves net to zero or below are DROPPED, not printed as
       0 — an empty bin is not a stocking location.
    2. ``mismatch_rows`` — **the single most useful derived view in this bullet**: which item that
       declares a cold requirement is sitting somewhere that does not match it.
    3. ``expiring_rows`` — FEFO visibility over ``LotSerial.expiry_date``: lots expiring inside the
       horizon, and lots already expired but still on hand.
    4. ``quarantine_rows`` — lots whose status is ``quarantine``. **4.9's non-conformance verb is
       what writes that column; this page only reads it.**
    5. ``unmonitored_rows`` — a location classified chilled/frozen/deep-frozen/cryogenic with **no
       active ``ColdChainMonitor`` on it**. That is a genuine GDP audit finding and it exists only
       because both halves — the classification and the monitor — are now in the same database.

    **Context**, exhaustively: ``view`` (the resolved section), ``view_choices``,
    ``storage_condition_choices``, ``cold_conditions`` (the frozenset the page filters on),
    ``locations`` / ``items`` (querysets for the dropdowns), ``days`` / ``days_raw`` /
    ``days_invalid`` / ``day_options`` / ``min_days`` / ``max_days`` (the expiry horizon),
    ``today`` (date), the five row lists above, a ``*_truncated`` bool and a ``*_count`` int beside
    each, ``stats`` (a dict of the header chips: ``cold_locations``, ``monitored_locations``,
    ``unmonitored_locations``, ``cold_items``, ``mismatches``, ``expiring``, ``expired``,
    ``quarantined`` — all ints), ``row_cap`` (int), ``reads_only_note`` and ``lot_status_note``
    (strs).

    Each ``on_hand_rows`` / ``mismatch_rows`` entry is a dict with ``item`` / ``location``
    (instances), ``quantity`` (Decimal), ``value`` (Decimal — quantity x unit cost from the ledger),
    ``item_condition`` / ``location_condition`` (the raw values) and, on a mismatch, ``kind``
    (``too_warm`` / ``too_cold`` / ``unclassified``) and ``reason`` (a sentence).
    ``expiring_rows`` / ``quarantine_rows`` carry ``lot`` (a ``LotSerial``, item joined),
    ``on_hand`` (Decimal) and ``days_to_expiry`` (int, negative once past, or **``None``** when the
    lot carries no expiry date — never 0, which would read as "expires today").

    NOT PAGINATED, deliberately: five sections whose chips have to describe the same set the tables
    show. Each section is capped by a SLICE and says when it truncated.
    """
    tenant = request.tenant
    today = timezone.localdate()
    days, days_raw, days_invalid = _expiry_horizon(request)

    view = (request.GET.get("view") or "on_hand").strip()
    if view not in dict(COLD_STORAGE_VIEWS):
        view = "on_hand"

    condition = (request.GET.get("storage_condition") or "").strip()
    if condition not in dict(STORAGE_CONDITION_CHOICES):
        condition = ""
    location_pk = as_db_int(request.GET.get("location"))

    # --- 1. cold on-hand by location, ONE grouped query -------------------------------------------
    moves = StockMove.objects.filter(tenant=tenant, location__storage_condition__in=COLD_CONDITIONS)
    if condition:
        moves = moves.filter(location__storage_condition=condition)
    if location_pk is not None:
        moves = moves.filter(location_id=location_pk)
    on_hand_raw = list(moves
                       .order_by()
                       .values("item_id", "item__sku", "item__name", "item__storage_condition",
                               "location_id", "location__code", "location__name",
                               "location__storage_condition")
                       # `qty`, NEVER `quantity`. An annotation alias that matches a column name
                       # SHADOWS that column for every later expression in the same statement, so
                       # `F("quantity")` inside the second Sum would resolve to the FIRST Sum and
                       # Django refuses with "Cannot compute Sum(...): ... is an aggregate". 4.13's
                       # `sparepart_list` names it `qty` for exactly this reason.
                       .annotate(qty=Sum("quantity"),
                                 value=Sum(F("quantity") * F("unit_cost"), output_field=_MONEY))
                       # A location whose moves net to nothing is not a place this item is held.
                       # Printing it as a 0 row would make an empty bin look like a stocking one.
                       .filter(qty__gt=ZERO)
                       .order_by("location__code", "item__sku")[:MAX_REPORT_ROWS + 1])
    on_hand_truncated = len(on_hand_raw) > MAX_REPORT_ROWS
    del on_hand_raw[MAX_REPORT_ROWS:]
    on_hand_rows = [{
        "item_id": row["item_id"], "sku": row["item__sku"], "item_name": row["item__name"],
        "location_id": row["location_id"], "location_code": row["location__code"],
        "location_name": row["location__name"],
        "item_condition": row["item__storage_condition"],
        "location_condition": row["location__storage_condition"],
        "quantity": row["qty"] or ZERO,
        "value": row["value"] or ZERO,
    } for row in on_hand_raw]

    # --- 2. condition mismatches, ONE grouped query ------------------------------------------------
    # Only ITEMS that declare a cold requirement — an unclassified item makes no claim about where it
    # must live, so it cannot be in the wrong place. The location side is deliberately NOT restricted
    # to cold bins: a chilled item sitting in an ambient or unclassified bin is exactly the finding.
    mismatch_moves = StockMove.objects.filter(tenant=tenant,
                                              item__storage_condition__in=COLD_CONDITIONS)
    if condition:
        mismatch_moves = mismatch_moves.filter(item__storage_condition=condition)
    if location_pk is not None:
        mismatch_moves = mismatch_moves.filter(location_id=location_pk)
    mismatch_raw = list(mismatch_moves
                        .exclude(item__storage_condition=F("location__storage_condition"))
                        .order_by()
                        .values("item_id", "item__sku", "item__name", "item__storage_condition",
                                "location_id", "location__code", "location__name",
                                "location__storage_condition")
                        # `qty`, never `quantity` — see the on-hand query above.
                        .annotate(qty=Sum("quantity"),
                                  value=Sum(F("quantity") * F("unit_cost"), output_field=_MONEY))
                        .filter(qty__gt=ZERO)
                        .order_by("item__sku", "location__code")[:MAX_REPORT_ROWS + 1])
    mismatch_truncated = len(mismatch_raw) > MAX_REPORT_ROWS
    del mismatch_raw[MAX_REPORT_ROWS:]
    mismatch_rows = []
    for row in mismatch_raw:
        kind, reason = _mismatch_kind(row["item__storage_condition"],
                                      row["location__storage_condition"])
        mismatch_rows.append({
            "item_id": row["item_id"], "sku": row["item__sku"], "item_name": row["item__name"],
            "location_id": row["location_id"], "location_code": row["location__code"],
            "location_name": row["location__name"],
            "item_condition": row["item__storage_condition"],
            "location_condition": row["location__storage_condition"],
            "quantity": row["qty"] or ZERO, "value": row["value"] or ZERO,
            "kind": kind, "reason": reason,
        })

    # --- 3 + 4. the lot sections, TWO queries for the lots + ONE for all their on-hand -------------
    lot_base = LotSerial.objects.filter(tenant=tenant,
                                        item__storage_condition__in=COLD_CONDITIONS)
    if condition:
        lot_base = lot_base.filter(item__storage_condition=condition)

    horizon = today + timedelta(days=days)
    expiring_lots = list(lot_base
                         .filter(expiry_date__isnull=False, expiry_date__lte=horizon)
                         .exclude(status="consumed")
                         .select_related("item")
                         .order_by("expiry_date", "item__sku")[:MAX_REPORT_ROWS + 1])
    expiring_truncated = len(expiring_lots) > MAX_REPORT_ROWS
    del expiring_lots[MAX_REPORT_ROWS:]

    quarantine_lots = list(lot_base.filter(status="quarantine")
                           .select_related("item")
                           .order_by("item__sku", "number")[:MAX_REPORT_ROWS + 1])
    quarantine_truncated = len(quarantine_lots) > MAX_REPORT_ROWS
    del quarantine_lots[MAX_REPORT_ROWS:]

    on_hand_by_lot = _lot_on_hand(tenant, expiring_lots + quarantine_lots)

    def _lot_row(lot):
        quantity = on_hand_by_lot.get(lot.pk) or ZERO
        return {
            "lot": lot,
            "on_hand": quantity,
            # None, never 0, when the lot carries no expiry date: 0 would read as "expires today".
            "days_to_expiry": (lot.expiry_date - today).days if lot.expiry_date else None,
            "is_expired": bool(lot.expiry_date and lot.expiry_date < today),
        }

    # Only what is actually still on hand — a fully consumed lot is history, not a FEFO problem.
    expiring_rows = [row for row in (_lot_row(lot) for lot in expiring_lots)
                     if row["on_hand"] > ZERO]
    quarantine_rows = [_lot_row(lot) for lot in quarantine_lots]

    # --- 5. unmonitored cold storage --------------------------------------------------------------
    cold_locations = Location.objects.filter(tenant=tenant, storage_condition__in=COLD_CONDITIONS)
    if condition:
        cold_locations = cold_locations.filter(storage_condition=condition)
    if location_pk is not None:
        cold_locations = cold_locations.filter(pk=location_pk)
    has_monitor = Exists(ColdChainMonitor.objects.filter(
        tenant=tenant, location_id=OuterRef("pk"), status="active"))
    unmonitored_qs = cold_locations.annotate(monitored=has_monitor).filter(monitored=False)
    unmonitored_rows = list(unmonitored_qs.order_by("code")[:MAX_REPORT_ROWS + 1])
    unmonitored_truncated = len(unmonitored_rows) > MAX_REPORT_ROWS
    del unmonitored_rows[MAX_REPORT_ROWS:]

    # --- header chips ------------------------------------------------------------------------------
    cold_location_count = cold_locations.count()
    unmonitored_count = unmonitored_qs.count()
    stats = {
        "cold_locations": cold_location_count,
        "monitored_locations": cold_location_count - unmonitored_count,
        "unmonitored_locations": unmonitored_count,
        "cold_items": Item.objects.filter(tenant=tenant,
                                          storage_condition__in=COLD_CONDITIONS).count(),
        "mismatches": len(mismatch_rows),
        "expiring": sum(1 for row in expiring_rows if not row["is_expired"]),
        "expired": sum(1 for row in expiring_rows if row["is_expired"]),
        "quarantined": len(quarantine_rows),
    }

    return render(request, "scm/coldchain/cold_storage_report.html", {
        "view": view,
        "view_choices": COLD_STORAGE_VIEWS,
        "storage_condition_choices": STORAGE_CONDITION_CHOICES,
        "storage_condition": condition,
        "cold_conditions": sorted(COLD_CONDITIONS),
        "locations": _location_qs(tenant),
        "items": _item_qs(tenant),
        "days": days,
        "days_raw": days_raw,
        "days_invalid": days_invalid,
        "day_options": EXPIRING_DAY_OPTIONS,
        "min_days": MIN_EXPIRING_DAYS,
        "max_days": MAX_EXPIRING_DAYS,
        "today": today,
        "on_hand_rows": on_hand_rows,
        "on_hand_truncated": on_hand_truncated,
        "mismatch_rows": mismatch_rows,
        "mismatch_truncated": mismatch_truncated,
        "expiring_rows": expiring_rows,
        "expiring_truncated": expiring_truncated,
        "quarantine_rows": quarantine_rows,
        "quarantine_truncated": quarantine_truncated,
        "unmonitored_rows": unmonitored_rows,
        "unmonitored_truncated": unmonitored_truncated,
        "stats": stats,
        "row_cap": MAX_REPORT_ROWS,
        "reads_only_note": READS_ONLY_NOTE,
        "lot_status_note": LOT_STATUS_NOTE,
    })


# =================================================================================================
# Report 2 — Compliance Reporting (the excursion log + calibration + per-monitor profile)
# =================================================================================================
@login_required
def cold_chain_compliance_report(request):
    """The compliance pack: what happened, against what limits, on whose calibrated probe.

    **Filter GET params:** ``date_from`` / ``date_to`` (through the shared ``_report_window``, which
    swaps a reversed pair and FLAGS a rejected value so the page can say "showing the default
    window"), ``monitor`` (a pk, L11-guarded), ``status`` (``EXCURSION_STATUS_CHOICES``),
    ``assessment`` (``ASSESSMENT_CHOICES``), and ``format=csv`` for the download.

    **Three blocks, and each answers a different auditor's question:**

    1. ``excursions`` — the episode log for the window, with **the limits that were in force when
       each one fired** snapshotted onto the row. That is why the record still reads correctly next
       year after somebody legitimately re-bands the fridge.
    2. ``calibration_rows`` — every monitor's certificate state. ``not_recorded`` is its own bucket
       and never green: an uncalibrated sensor invalidates every record it produced, and "we never
       wrote the certificate down" is a different finding from "it is in date".
    3. ``profiles`` — per-monitor % time in range and MKT over the window, from
       ``coldchain.profile()``. **Capped at :data:`MAX_PROFILED_MONITORS`** because each profile is
       two bounded queries plus a row walk; the page says it capped and points at ``?monitor=``.

    **Context**, exhaustively: everything in the ``_report_window`` dict (``date_from`` /
    ``date_to`` as dates, ``date_from_raw`` / ``date_to_raw`` as the echoed strings,
    ``window_invalid`` as a bool, ``period_label`` as a string), ``excursions`` (a LIST of dicts:
    ``obj``, ``duration_minutes`` int, ``excess_c`` Decimal-or-**``None``**, ``is_reportable`` bool),
    ``excursions_truncated`` (bool), ``excursion_count`` (int), ``stats`` (a dict of ints:
    ``total`` / ``reportable`` / ``open`` / ``critical`` / ``product_affected`` / ``dismissed``),
    ``calibration_rows`` (a LIST of dicts: ``monitor``, ``chip`` a ``(label, css)`` 2-tuple,
    ``days`` int-or-**``None``**), ``calibration_stats`` (ints: ``ok`` / ``due`` / ``overdue`` /
    ``not_recorded``), ``profiles`` (a LIST of dicts: ``monitor`` plus the whole
    ``coldchain.profile()`` result under ``profile`` — **``pct_in_range`` and ``mkt`` are ``None``
    on an empty window and ``mkt`` is ``None`` for every frozen monitor; render an em dash plus
    ``frozen_mkt_note``, never 0.00**), ``profiles_truncated`` (bool), ``profiled_cap`` (int),
    ``monitors`` (queryset), ``status_choices`` / ``assessment_choices``, ``max_window_days`` (int),
    ``export_qs`` (the filter query string for the CSV link), ``generated_at`` (datetime),
    ``calibration_note`` / ``frozen_mkt_note`` / ``no_claim_note`` / ``reads_only_note`` (strs).

    **``no_claim_note`` must be rendered as visible page text.** An over-claiming compliance page is
    worse than a missing one: this is a record of what was measured and decided, not a validated
    Part 11 / Annex 11 system, and it contains no electronic signature.
    """
    tenant = request.tenant
    today = timezone.localdate()
    now = timezone.now()
    window = _report_window(request.GET, today - timedelta(days=29), today)
    start, end = _aware_bounds(window["date_from"], window["date_to"])

    monitor_pk = as_db_int(request.GET.get("monitor"))
    status = (request.GET.get("status") or "").strip()
    if status not in dict(EXCURSION_STATUS_CHOICES):
        status = ""
    assessment = (request.GET.get("assessment") or "").strip()
    if assessment not in dict(ASSESSMENT_CHOICES):
        assessment = ""

    # --- 1. the excursion log ----------------------------------------------------------------------
    log_qs = (TemperatureExcursion.objects
              .filter(tenant=tenant, started_at__gte=start, started_at__lte=end)
              .select_related("monitor", "monitor__location", "monitor__asset",
                              "monitor__shipment", "non_conformance", "maintenance_work_order",
                              "lot_serial", "lot_serial__item", "assessed_by"))
    if monitor_pk is not None:
        log_qs = log_qs.filter(monitor_id=monitor_pk)
    if status:
        log_qs = log_qs.filter(status=status)
    if assessment:
        log_qs = log_qs.filter(assessment=assessment)

    episodes = list(log_qs.order_by("-started_at", "-id")[:MAX_REPORT_ROWS + 1])
    excursions_truncated = len(episodes) > MAX_REPORT_ROWS
    del episodes[MAX_REPORT_ROWS:]
    excursions = [{
        "obj": episode,
        "duration_minutes": episode.live_duration_minutes(now),
        "excess_c": episode.excess_c(),
        "is_reportable": episode.is_reportable,
    } for episode in episodes]

    counts = log_qs.aggregate(
        total=Count("id"),
        open_triage=Count("id", filter=Q(status__in=OPEN_EXCURSION_STATUSES)),
        critical=Count("id", filter=Q(severity="critical")),
        product_affected=Count("id", filter=Q(assessment="product_affected")),
        dismissed=Count("id", filter=Q(status="dismissed")))
    stats = {
        "total": counts["total"] or 0,
        "open": counts["open_triage"] or 0,
        "critical": counts["critical"] or 0,
        "product_affected": counts["product_affected"] or 0,
        "dismissed": counts["dismissed"] or 0,
        # Counted over the RENDERED window only, and the page says so: `is_reportable` is derived
        # against the monitor's live grace period, so a SQL count would need the same per-grace
        # union the queue page builds — and this figure describes the log being read, not the
        # workspace.
        "reportable": sum(1 for row in excursions if row["is_reportable"]),
    }

    # --- 2. calibration ----------------------------------------------------------------------------
    monitor_qs = ColdChainMonitor.objects.filter(tenant=tenant).select_related(
        "location", "asset", "shipment")
    if monitor_pk is not None:
        monitor_qs = monitor_qs.filter(pk=monitor_pk)
    # `nulls_last` so "no certificate recorded" sorts to the bottom rather than to the top as the
    # most urgent thing on the page — it IS a finding, but it is not an overdue date.
    monitors = list(monitor_qs.order_by(F("calibration_due_on").asc(nulls_last=True), "name"))
    calibration_rows = [{
        "monitor": monitor,
        "chip": monitor.calibration_chip(today),
        "days": monitor.days_to_calibration_due(today),
    } for monitor in monitors]
    calibration_stats = {"ok": 0, "due": 0, "overdue": 0, "not_recorded": 0}
    for row in calibration_rows:
        days = row["days"]
        if days is None:
            calibration_stats["not_recorded"] += 1
        elif days < 0:
            calibration_stats["overdue"] += 1
        elif days <= CALIBRATION_NOTICE_DAYS:
            calibration_stats["due"] += 1
        else:
            calibration_stats["ok"] += 1

    # --- 3. the per-monitor profile ----------------------------------------------------------------
    # THE ONE FIGURE ON THIS PAGE THAT SCALES WITH ROWS. Capped rather than paginated, and the cap is
    # reported — see MAX_PROFILED_MONITORS.
    profiled = monitors[:MAX_PROFILED_MONITORS]
    profiles = [{
        "monitor": monitor,
        "profile": coldchain.profile(monitor, date_from=window["date_from"],
                                     date_to=window["date_to"]),
    } for monitor in profiled]

    context = {
        **window,
        "window": window,
        "excursions": excursions,
        "excursions_truncated": excursions_truncated,
        "excursion_count": stats["total"],
        "stats": stats,
        "calibration_rows": calibration_rows,
        "calibration_stats": calibration_stats,
        "profiles": profiles,
        "profiles_truncated": len(monitors) > len(profiled),
        "profiled_cap": MAX_PROFILED_MONITORS,
        "monitors": _monitor_qs(tenant),
        "status_choices": EXCURSION_STATUS_CHOICES,
        "assessment_choices": ASSESSMENT_CHOICES,
        "status": status,
        "assessment": assessment,
        "max_window_days": MAX_READING_WINDOW_DAYS,
        "row_cap": MAX_REPORT_ROWS,
        "export_qs": _encode(request.GET,
                             ("date_from", "date_to", "monitor", "status", "assessment")),
        "generated_at": timezone.localtime(),
        "calibration_note": CALIBRATION_NOTE,
        "frozen_mkt_note": FROZEN_MKT_NOTE,
        "no_claim_note": NO_CLAIM_NOTE,
        "reads_only_note": READS_ONLY_NOTE,
    }
    if (request.GET.get("format") or "").strip().lower() == "csv":
        return _compliance_csv(context)
    return render(request, "scm/coldchain/cold_chain_compliance_report.html", context)


def _encode(data, params):
    """Re-encode a WHITELIST of filter params as a query string for the CSV link.

    A whitelist rather than an echo of the whole query string: echoing would put anything an attacker
    appended into a URL that lands in the browser history, the referrer header and the server log.
    Same rule the 4.14 payroll export states.
    """
    return urlencode({key: value for key, value in
                      ((key, (data.get(key) or "").strip()) for key in params) if value})


def _compliance_csv(context):
    """The same figures as a spreadsheet, provenance first — from the SAME context the page renders.

    The header block is not decoration: a file that leaves the building has to carry the window it
    covers, when it was generated and the explicit NON-CLAIM, or the first person to open it in a
    quality office has no way to know any of that.

    ``None`` is written as ``n/a``, **never as 0**. A blank cell in a column somebody is about to
    average is the one place the "unanswerable, not zero" rule matters most — an MKT of 0 °C in a
    spreadsheet reads as a perfectly cold shipment.
    """
    def cell(value):
        return "n/a" if value is None else value

    def body():
        yield ["NavERP", "Cold chain compliance report", context["period_label"]]
        yield ["Generated", context["generated_at"].isoformat(timespec="seconds")]
        yield ["Window", context["date_from"].isoformat(), context["date_to"].isoformat()]
        yield ["Excursions in window", context["stats"]["total"]]
        yield ["Reportable (of those listed)", context["stats"]["reportable"]]
        yield ["Product affected", context["stats"]["product_affected"]]
        yield ["Notice", context["no_claim_note"]]
        yield []

        yield ["Excursion log"]
        yield ["Number", "Monitor", "Watches", "Started", "Ended", "Duration (min)",
               "Direction", "Extreme C", "Limit min C", "Limit max C", "Excess C",
               "Readings", "MKT C", "Severity", "Status", "Assessment", "Cause",
               "Reportable", "Non-conformance", "Work order", "Lot"]
        for row in context["excursions"]:
            obj = row["obj"]
            yield [
                obj.number, obj.monitor.number, obj.monitor.subject_label,
                obj.started_at.isoformat(timespec="minutes"),
                obj.ended_at.isoformat(timespec="minutes") if obj.ended_at else "still running",
                row["duration_minutes"],
                obj.get_breach_direction_display(),
                cell(obj.extreme_temperature), cell(obj.limit_min), cell(obj.limit_max),
                cell(row["excess_c"]), obj.reading_count, cell(obj.mkt),
                obj.get_severity_display(), obj.get_status_display(),
                obj.get_assessment_display(), obj.get_cause_display() or "n/a",
                row["is_reportable"],
                obj.non_conformance.number if obj.non_conformance_id else "n/a",
                obj.maintenance_work_order.number if obj.maintenance_work_order_id else "n/a",
                obj.lot_serial.number if obj.lot_serial_id else "n/a",
            ]
        yield []

        yield ["Monitor calibration"]
        yield ["Monitor", "Name", "Watches", "Status", "Calibrated on", "Due on", "Days left",
               "Certificate", "State"]
        for row in context["calibration_rows"]:
            monitor = row["monitor"]
            yield [monitor.number, monitor.name, monitor.subject_label,
                   monitor.get_status_display(),
                   monitor.calibrated_on.isoformat() if monitor.calibrated_on else "n/a",
                   monitor.calibration_due_on.isoformat() if monitor.calibration_due_on else "n/a",
                   cell(row["days"]), monitor.calibration_reference or "n/a", row["chip"][0]]
        yield []

        yield ["Temperature profile", f"first {context['profiled_cap']} monitors"]
        yield ["Monitor", "Readings", "Min C", "Max C", "Mean C", "In-range minutes",
               "Out-of-range minutes", "% time in range", "MKT C", "Limit min C", "Limit max C",
               "Frozen (MKT not applicable)"]
        for row in context["profiles"]:
            profile = row["profile"]
            yield [row["monitor"].number, profile["count"], cell(profile["min"]),
                   cell(profile["max"]), cell(profile["mean"]),
                   cell(profile["in_range_minutes"]), cell(profile["out_minutes"]),
                   cell(profile["pct_in_range"]), cell(profile["mkt"]),
                   cell(profile["limit_min"]), cell(profile["limit_max"]), profile["frozen"]]

    return _csv_response(
        f"cold-chain-compliance-{context['date_from'].isoformat()}-to-"
        f"{context['date_to'].isoformat()}.csv",
        body())


# =================================================================================================
# Report 3 — Maintenance of Reefers (a BOARD over 4.13; 4.15 declares zero maintenance entities)
# =================================================================================================
def _asset_newest_reading_case(tenant):
    """The pk of an asset's latest meter reading, as a scalar expression to annotate onto the asset.

    The asset-side twin of the plan-side ``_newest_reading_case`` in
    ``views/AssetManagement/Reports.py`` (which correlates on ``OuterRef("asset_id")`` because it
    annotates a ``MaintenancePlan`` queryset). Same rule, restated one join up rather than imported,
    because the correlation target differs.

    It mirrors ``Asset.latest_reading()`` exactly, including the rule that matters most: an asset
    with a NAMED primary meter does **not** fall back to readings logged under another name. An
    odometer value handed to a plan whose interval is in running hours would schedule a service
    roughly never, and the failure would be silent.

    ``tenant`` is a LITERAL rather than ``OuterRef("tenant_id")``: the scoping is identical, and a
    correlated tenant reference is one more outer column MySQL must resolve inside a dependent
    subquery. It is load-bearing either way — ``scm_mtr_tnt_asset_idx`` is ``(tenant, asset,
    read_at)`` and ``tenant_id`` is its LEADING column.
    """
    named = (MeterReading.objects
             .filter(tenant=tenant, asset_id=OuterRef("pk"), meter_name=OuterRef("meter_name"))
             .order_by("-read_at", "-id"))
    any_meter = (MeterReading.objects
                 .filter(tenant=tenant, asset_id=OuterRef("pk"))
                 .order_by("-read_at", "-id"))
    return models.Case(
        models.When(meter_name="", then=models.Subquery(any_meter.values("pk")[:1])),
        default=models.Subquery(named.values("pk")[:1]),
        output_field=models.IntegerField())


@login_required
def reefer_board(request):
    """One row per REEFER — and a reefer is *an ``Asset`` with an active ``ColdChainMonitor``*.

    **4.15 declares no maintenance table and adds no value to any 4.13 vocabulary.** There is no
    ``reefer`` asset type and there deliberately never will be: a hand-set type goes stale the day a
    unit is repurposed, while "has a live monitor pointed at it" cannot. Every maintenance column
    below is 4.13's own — ``MaintenancePlan.due_status()``, the open ``MaintenanceWorkOrder`` queue,
    ``Asset.latest_reading()`` and ``Asset.warranty_chip()`` — and this page writes none of them.

    **Filter GET params:** ``q`` (asset code / name / the monitor's name or serial),
    ``criticality`` (``CRITICALITY_CHOICES``), ``pm_due`` (``overdue`` / ``due_soon``, DERIVED from
    ``MaintenancePlan.due_status()``) and ``range`` (``in`` / ``out`` / ``unknown``, DERIVED from the
    cargo probe's newest reading against the monitor's limits).

    ``pm_due`` and ``range`` are applied in PYTHON, after the rows are built, and that is a
    deliberate exception to the "filter before pagination" rule with a reason: **this board is not
    paginated.** It is bounded instead by there being one row per monitored asset — a workspace has
    tens of reefers, not thousands — and the header chips have to describe the same set the table
    shows (the ``pm_forecast`` posture). ``due_status()`` also consults the meter and condition axes,
    which no ``WHERE`` clause on ``next_due_on`` can see: a plan comes due because the MACHINE moved.

    **Context**, exhaustively: ``rows`` (below), ``row_count`` (int), ``truncated`` (bool),
    ``row_cap`` (int), ``criticality_choices`` / ``pm_due_choices`` / ``range_choices`` (lists of
    pairs), the resolved ``criticality`` / ``pm_due`` / ``range_bucket`` values, ``q``, ``stats``
    (ints: ``reefers`` / ``out_of_range`` / ``open_excursions`` / ``pm_overdue`` / ``open_jobs``),
    ``today`` (date), and ``owned_by_4_13_note`` / ``reads_only_note`` (strs).

    Each ``rows`` entry is a dict:

    * ``asset`` — the ``Asset`` (location and custodian joined). Safe to ask for ``status_css`` /
      ``criticality_css`` — neither queries.
    * ``monitors`` — a LIST of the asset's ACTIVE monitors (usually one).
    * ``monitor`` — the primary one (the first), or **``None``** if a monitor was deactivated between
      the two queries.
    * ``latest_reading`` — the newest ``TemperatureReading`` on that monitor, or **``None``**.
    * ``range_chip`` — a ``(label, css)`` 2-tuple; muted "Not recorded" when there is no reading.
    * ``setpoint_gap`` — Decimal or **``None``** (no setpoint recorded, or no reading).
    * ``open_excursions`` — int (outstanding TRIAGE on this asset's monitors).
    * ``running_episode`` — ``TemperatureExcursion`` or **``None``** — set means the cargo is out of
      limits RIGHT NOW.
    * ``plans`` — a LIST of ``MaintenancePlan``, each already primed so ``due_status_label`` /
      ``due_status_css`` / ``days_until_due`` / ``meter_gap`` are free to call.
    * ``pm_status`` — the worst ``due_status()`` across those plans, or ``"none"`` when the asset has
      no plan at all. **``"none"`` is not ``"scheduled"``**: a reefer nobody has written a PM
      programme for is a finding, not a compliant machine.
    * ``open_jobs`` — int; ``open_job_rows`` — a LIST of the open ``MaintenanceWorkOrder``s.
    * ``meter_reading`` — the asset's newest ``MeterReading`` on its PRIMARY meter, or **``None``**;
      ``meter_name`` / ``meter_unit`` — strings (possibly empty).
    * ``warranty_chip`` — a ``(label, css)`` 2-tuple; muted "Not recorded" when no warranty date is
      on file.

    Link every reefer into ``scm:asset_detail``, every plan into ``scm:maintenanceplan_detail``,
    every job into ``scm:maintenanceworkorder_detail`` and every monitor into
    ``scm:coldchainmonitor_detail`` — the record lives in the module that owns it, and this board
    only assembles the view.

    QUERIES: one for the active monitors, one for the assets, one for the monitors' latest readings,
    one for the open episodes, one grouped count for the open triage, one for the plans, one for the
    plans' primed readings, one for the open jobs and one for the assets' own meter readings. NINE,
    flat — not one of them per row.
    """
    tenant = request.tenant
    today = timezone.localdate()
    now = timezone.now()

    q = (request.GET.get("q") or "").strip()
    criticality = (request.GET.get("criticality") or "").strip()
    if criticality not in dict(CRITICALITY_CHOICES):
        criticality = ""
    pm_due = (request.GET.get("pm_due") or "").strip()
    if pm_due not in ("overdue", "due_soon"):
        pm_due = ""
    range_bucket = (request.GET.get("range") or "").strip()
    if range_bucket not in ("in", "out", "unknown"):
        range_bucket = ""

    # --- who is a reefer ---------------------------------------------------------------------------
    monitor_qs = (ColdChainMonitor.objects
                  .filter(tenant=tenant, status="active", asset__isnull=False)
                  .select_related("asset"))
    if q:
        monitor_qs = monitor_qs.filter(
            Q(asset__code__icontains=q) | Q(asset__name__icontains=q)
            | Q(name__icontains=q) | Q(device_serial__icontains=q) | Q(number__icontains=q))
    monitors = list(monitor_qs.order_by("asset_id", "name", "id"))

    monitors_by_asset = {}
    for monitor in monitors:
        monitors_by_asset.setdefault(monitor.asset_id, []).append(monitor)
    asset_ids = list(monitors_by_asset)

    assets_qs = (Asset.objects.filter(tenant=tenant, pk__in=asset_ids)
                 .select_related("location", "custodian")
                 .annotate(newest_reading_pk=_asset_newest_reading_case(tenant)))
    if criticality:
        assets_qs = assets_qs.filter(criticality=criticality)
    assets = list(assets_qs.order_by("code")[:MAX_REPORT_ROWS + 1])
    truncated = len(assets) > MAX_REPORT_ROWS
    del assets[MAX_REPORT_ROWS:]
    asset_ids = [asset.pk for asset in assets]
    monitor_ids = [monitor.pk for asset_id in asset_ids
                   for monitor in monitors_by_asset.get(asset_id, [])]

    # --- the cargo probes ---------------------------------------------------------------------------
    latest_by_monitor = {}
    if monitor_ids:
        # The SAME correlated subquery the monitor register uses, imported rather than restated: one
        # annotated pass for the newest reading's pk, then ONE `in_bulk` for the rows themselves. Two
        # queries for every probe on the board, not one per probe.
        pairs = list(ColdChainMonitor.objects
                     .filter(tenant=tenant, pk__in=monitor_ids)
                     .annotate(latest_reading_pk=_latest_reading_pk(tenant))
                     .values_list("pk", "latest_reading_pk"))
        by_reading = {reading_pk: monitor_pk for monitor_pk, reading_pk in pairs if reading_pk}
        reading_rows = (TemperatureReading.objects
                        .filter(tenant=tenant, pk__in=list(by_reading))
                        .in_bulk()) if by_reading else {}
        for reading_pk, monitor_pk in by_reading.items():
            reading = reading_rows.get(reading_pk)
            if reading is not None:
                latest_by_monitor[monitor_pk] = reading

    running_by_monitor = {
        episode.monitor_id: episode
        for episode in (TemperatureExcursion.objects
                        .filter(tenant=tenant, monitor_id__in=monitor_ids, ended_at__isnull=True)
                        .order_by("monitor_id", "started_at"))
    } if monitor_ids else {}
    open_triage = dict(
        TemperatureExcursion.objects
        .filter(tenant=tenant, monitor_id__in=monitor_ids, status__in=OPEN_EXCURSION_STATUSES)
        .order_by().values_list("monitor_id").annotate(n=Count("id"))) if monitor_ids else {}

    # --- 4.13: the PM programme, the open jobs and the run-hours meter ------------------------------
    plans_by_asset, jobs_by_asset = {}, {}
    asset_readings = {}
    if asset_ids:
        reading_pks = {asset.newest_reading_pk for asset in assets if asset.newest_reading_pk}
        meter_rows = (MeterReading.objects
                      .filter(tenant=tenant, pk__in=reading_pks)
                      .select_related("recorded_by")
                      .in_bulk()) if reading_pks else {}
        for asset in assets:
            asset_readings[asset.pk] = meter_rows.get(asset.newest_reading_pk)

        for plan in (MaintenancePlan.objects
                     .filter(tenant=tenant, asset_id__in=asset_ids, is_active=True)
                     .select_related("asset", "assigned_to")
                     .order_by("asset_id", F("next_due_on").asc(nulls_last=True), "id")):
            # THE PRIME. `MaintenancePlan.latest_reading()` is `self.asset.latest_reading()` — the
            # asset's PRIMARY meter — which is exactly what `asset_readings` already holds. Set
            # unconditionally, `None` included: leaving it unset on the plans with no reading would
            # put the per-row query straight back for the rows most likely to have one.
            plan._latest_reading_cache = asset_readings.get(plan.asset_id)
            plans_by_asset.setdefault(plan.asset_id, []).append(plan)

        for job in (MaintenanceWorkOrder.objects
                    .filter(tenant=tenant, asset_id__in=asset_ids,
                            status__in=MaintenanceWorkOrder.OPEN_STATUSES)
                    .select_related("assigned_to", "plan")
                    .order_by("asset_id", "-reported_at", "-id")):
            jobs_by_asset.setdefault(job.asset_id, []).append(job)

    # --- assemble ----------------------------------------------------------------------------------
    # Worst-first, so the board's own ordering matches the colour a reader scans for.
    pm_rank = {"overdue": 0, "due_today": 1, "due_soon": 2, "scheduled": 3,
               "not_scheduled": 4, "none": 5}
    rows = []
    for asset in assets:
        asset_monitors = monitors_by_asset.get(asset.pk, [])
        monitor = asset_monitors[0] if asset_monitors else None
        reading = latest_by_monitor.get(monitor.pk) if monitor is not None else None
        plans = plans_by_asset.get(asset.pk, [])

        statuses = [plan.due_status(today) for plan in plans]
        pm_status = min(statuses, key=lambda s: pm_rank.get(s, 9)) if statuses else "none"

        running = next((running_by_monitor[m.pk] for m in asset_monitors
                        if m.pk in running_by_monitor), None)

        rows.append({
            "asset": asset,
            "monitors": asset_monitors,
            "monitor": monitor,
            "latest_reading": reading,
            # The MODEL's own verdict, over a reading this page already paid for. `_NoReading` is not
            # needed here: a monitor with no reading takes the explicit muted pair below, because a
            # `None` handed to `range_chip()` would mean "go and look it up".
            "range_chip": (monitor.range_chip(reading) if (monitor is not None and reading is not None)
                           else ("Not recorded", "badge-muted")),
            "setpoint_gap": (monitor.setpoint_gap(reading)
                             if (monitor is not None and reading is not None) else None),
            "open_excursions": sum(open_triage.get(m.pk, 0) for m in asset_monitors),
            "running_episode": running,
            "plans": plans,
            "pm_status": pm_status,
            "pm_status_label": MaintenancePlan.DUE_STATUS_LABELS.get(pm_status, "No PM plan"),
            "pm_status_css": MaintenancePlan.DUE_STATUS_CSS.get(pm_status, "badge-muted"),
            "open_jobs": len(jobs_by_asset.get(asset.pk, [])),
            "open_job_rows": jobs_by_asset.get(asset.pk, []),
            "meter_reading": asset_readings.get(asset.pk),
            "meter_name": asset.meter_name,
            "meter_unit": asset.meter_unit,
            "warranty_chip": asset.warranty_chip(today),
        })

    # The two derived filters, after the rows exist — see the docstring for why that is right here.
    if pm_due == "overdue":
        rows = [row for row in rows if row["pm_status"] in ("overdue", "due_today")]
    elif pm_due == "due_soon":
        rows = [row for row in rows if row["pm_status"] == "due_soon"]
    if range_bucket:
        def _bucket(row):
            monitor, reading = row["monitor"], row["latest_reading"]
            if monitor is None or reading is None:
                return "unknown"
            verdict = monitor.is_in_range(reading)
            return "unknown" if verdict is None else ("in" if verdict else "out")
        rows = [row for row in rows if _bucket(row) == range_bucket]

    rows.sort(key=lambda row: (0 if row["running_episode"] is not None else 1,
                               pm_rank.get(row["pm_status"], 9),
                               row["asset"].code))

    stats = {
        "reefers": len(rows),
        "out_of_range": sum(1 for row in rows if row["range_chip"][0] == "Out of range"),
        "open_excursions": sum(row["open_excursions"] for row in rows),
        "pm_overdue": sum(1 for row in rows if row["pm_status"] in ("overdue", "due_today")),
        "open_jobs": sum(row["open_jobs"] for row in rows),
    }

    return render(request, "scm/coldchain/reefer_board.html", {
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "row_cap": MAX_REPORT_ROWS,
        "q": q,
        "criticality_choices": CRITICALITY_CHOICES,
        "criticality": criticality,
        "pm_due_choices": [("overdue", "PM overdue or due today"),
                           ("due_soon", "PM due soon")],
        "pm_due": pm_due,
        "range_choices": [("out", "Cargo out of range"), ("in", "Cargo in range"),
                          ("unknown", "Unknown")],
        "range_bucket": range_bucket,
        "stats": stats,
        "today": today,
        "now": now,
        "owned_by_4_13_note": REEFER_NOTE,
        "reads_only_note": READS_ONLY_NOTE,
    })


# =================================================================================================
# Prose the templates print
# =================================================================================================

#: On all three pages. The single most important thing a reader has to understand about them.
READS_ONLY_NOTE = (
    "This page is computed, not stored. It writes nothing: no stock movement, no journal entry, no "
    "lot status, no asset or maintenance record. Every figure is derived on read from rows another "
    "part of the system already owns, so there is no second number here to drift from the first."
)

#: On the cold-storage page, beside the quarantine section.
LOT_STATUS_NOTE = (
    "Quarantine is 4.9's. A non-conformance is what moves a lot into or out of quarantine, and cold "
    "chain only READS that status — it never writes it. If an excursion means product was affected, "
    "record the assessment on the excursion and raise or link the non-conformance that acts on it."
)

#: On the compliance report, as VISIBLE page text. An over-claiming compliance page is worse than a
#: missing one.
NO_CLAIM_NOTE = (
    "This report is a record of what was measured and what was decided. It is NOT a validated 21 CFR "
    "Part 11 / EU Annex 11 system: it contains no electronic signature, there is no re-authentication "
    "at the point of signing, no stated meaning of signature and no database-level immutability "
    "guarantee. What it does carry is an audit trail — every change to every record below is written "
    "to the application audit log with the user, the moment and the fields that changed."
)

#: On the reefer board.
REEFER_NOTE = (
    "Cold chain declares no maintenance table. A reefer here is simply an asset with an active "
    "cold-chain monitor pointed at it — nothing is flagged by hand, so nothing can go stale when a "
    "unit is repurposed. Every maintenance column on this board is Asset Management's own record: "
    "its preventive plans, its open work orders, its meter log and its warranty. Follow the links to "
    "act on any of them."
)
