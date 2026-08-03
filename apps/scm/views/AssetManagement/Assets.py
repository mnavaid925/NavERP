"""SCM 4.13 Asset Management — the ``Asset`` register, its 360° page, and its spare-parts list.

**This is the sub-module's root entity, and the other three view modules read from it.** The four
small scoping helpers below (:func:`_asset_qs`, :func:`_work_center_qs`, :func:`_org_unit_qs`,
:func:`_party_qs`) are the querysets every 4.13 list page's filter dropdowns need; they live here
rather than in ``views/_helpers.py`` for the same reason the three form helpers live in
``forms/AssetManagement/Assets.py`` — the other three modules already point at ``Asset``, so
importing from this module adds no dependency edge that did not already exist, and the alternative
was the same four lines copied four times. (``views/_helpers.py`` is for helpers shared across
*sub-modules*; these are shared inside one.)

--------------------------------------------------------------------------------------------------
WHAT THIS MODULE DELIBERATELY DOES NOT DO
--------------------------------------------------------------------------------------------------
**It computes no reliability figure of its own.** MTBF, MTTR, availability, downtime, failure count
and maintenance cost to date are all methods on :class:`~apps.scm.models.Asset`, and every one of
them can answer ``None`` — an asset that has never failed has no MTBF, and 0 h would read as "fails
constantly". This module calls them and passes the ``None`` STRAIGHT THROUGH to the template, which
must print an em dash. A view that helpfully substituted ``0`` would put a confident, wrong number
in a red tile (the 4.11 lesson).

**It never asks a per-row method a question the database can answer once.** ``Asset.is_down_now()``
and ``Asset.open_job_count()`` are one query EACH, so calling them inside a 15-row list loop is 30
queries for two chips. :func:`asset_list` therefore annotates both — ``down_now`` as an
``Exists()`` subquery and ``open_jobs_count`` as ONE grouped ``Count``. ``warranty_chip()`` is called
per row and that is fine: it is pure date arithmetic and touches no table.

**It writes no stock move and drafts no accounting document** (L29). ``fixed_asset`` is READ for the
book-value card and nothing here writes back to it — ``accounting.FixedAsset`` owns the acquisition
cost, the accumulated depreciation and the journal that produced them.

--------------------------------------------------------------------------------------------------
THE SPARE-PARTS CHILD, AND WHY IT IS RESOLVED THE WAY IT IS
--------------------------------------------------------------------------------------------------
``AssetSparePart`` carries **no ``tenant`` column** (the ``ComplianceCheck`` / ``TradeDocumentLine``
precedent), so every view that touches one resolves it as
``get_object_or_404(AssetSparePart, pk=pk, asset__tenant=request.tenant)`` — never on the child's own
pk alone, which would be a cross-tenant read with no query that would ever reveal it. That is also
why the edit and delete paths are hand-rolled instead of using ``crud_edit`` / ``crud_delete``: both
filter ``tenant=request.tenant`` **on the model**, which raises ``FieldError`` on a model that has no
such column. Hand-rolled means these paths owe their own ``write_audit_log`` — the ``crud_*`` helpers
write one for you and nothing else does.

The **add** route takes the parent from the URL and the edit/delete routes take the child's own pk
(the ``compliance-checks/`` rationale): a child pk already identifies its parent, and nesting the
edit route under a parent pk would invite a caller to pair a real child with somebody else's asset.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/assets/asset/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from ``crud_list``), where
  every row additionally carries the two annotations ``down_now`` (bool — render the "Down" chip from
  THIS, never from ``asset.is_down_now``, which is a query per row) and ``open_jobs_count`` (int).
  Plus ``status_choices`` / ``criticality_choices`` / ``asset_type_choices`` / ``warranty_choices``
  (all ``(value, label)`` pairs), ``warranty`` (the RESOLVED warranty-filter value, ``""`` when
  absent or junk — bind the select to this, not to ``request.GET.warranty``), ``locations`` /
  ``work_centers`` / ``org_units`` (querysets for the three pk dropdowns — compare with
  ``|stringformat:"d"``, NEVER ``|slugify``), ``warranty_notice_days`` (int, for the filter's help
  text) and the four header chips ``down_count`` / ``warranty_expiring_count`` /
  ``warranty_expired_count`` / ``critical_count`` (counted over the WHOLE workspace, not the filtered
  page). Filter params: ``q`` / ``status`` / ``criticality`` / ``asset_type`` / ``location`` /
  ``work_center`` / ``org_unit`` / ``warranty`` / ``is_active`` (the ``is_active`` select's option
  values are the strings ``True`` and ``False`` — the ``crud_list`` convention).
* ``scm/assets/asset/detail.html`` — see :func:`asset_detail`'s docstring for the full key list; it
  is long enough to belong beside the code that builds it.
* ``scm/assets/asset/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path).
* ``scm/assets/assetsparepart/form.html`` — ``form``, ``is_edit`` (False on add, True on edit),
  ``asset`` (the PARENT, for the breadcrumb and the cancel link — the child form has no ``asset``
  field, so the template cannot get it from the form) and ``obj`` (the line, edit path only).

Badge colours come from the models' own ``status_css`` / ``criticality_css`` / ``due_status_css`` /
``work_type_css`` / ``priority_css`` properties and from ``warranty_chip.1``. ``badge-success`` /
``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css and render as unstyled text (L33).
"""
from datetime import timedelta

from django.db.models import ProtectedError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _location_qs, _need_tenant

from apps.core.models import OrgUnit
from apps.scm.forms import AssetForm, AssetSparePartForm
from apps.scm.models import (
    Asset,
    AssetSparePart,
    # The shared 4.13 vocabularies live in `models/AssetManagement/_choices.py` and are re-exported
    # by `apps.scm.models`. `CRITICALITY_CHOICES` is imported from THERE and not read as
    # `Asset.CRITICALITY_CHOICES`: the model uses it to build a field's `choices` but never binds it
    # as a class attribute, so the attribute access would be an AttributeError at request time.
    CRITICALITY_CHOICES,
    MaintenanceWorkOrder,
    PROBLEM_CODE_CHOICES,
    StockMove,
    WorkCenter,
)

ZERO = Decimal("0")

#: How many rows each child panel on the detail page shows. The cap is a queryset SLICE, so the
#: DATABASE applies it — it bounds what is FETCHED, not merely what is rendered (L40 §1: a guard
#: that first builds the whole thing is the payload, not a guard). One more than the cap is fetched
#: so the page can say it is showing a window without paying for a second COUNT.
MAX_PANEL_ROWS = 25

#: The meter log is the fastest-growing table hanging off an asset and the panel is a "what does it
#: say lately" strip, not a register — the full history is the readings page's job.
MAX_READING_ROWS = 15

#: The warranty filter's three buckets. NOT a model vocabulary: ``warranty_expires_on`` is a DATE and
#: there is no ``warranty_status`` column to filter on — deliberately, because the fact changes by
#: the calendar rolling over and a stored flag would need something to run every night to stay true
#: (``Asset.warranty_chip``'s reasoning). So the filter is a DATE-RANGE query whose boundaries are
#: derived from the same ``WARRANTY_NOTICE_DAYS`` the chip reads, and the two are written from one
#: statement of the rule in :func:`_apply_warranty_filter` — a row the filter puts in the "expiring"
#: bucket must render the amber chip, or the page argues with itself.
WARRANTY_CHOICES = [
    ("expired", "Expired"),
    ("expiring", "Expiring soon"),
    ("in_force", "In warranty"),
]

#: ``problem_code`` -> label, for the failure-analysis panel. Django templates cannot look a choice
#: label up from a raw token on an aggregate row (``get_FOO_display`` only exists on a model
#: instance), so the panel is built as dicts carrying the label already resolved.
_PROBLEM_LABELS = dict(PROBLEM_CODE_CHOICES)

#: Every FK a LIST row renders. Without these joins a page of 15 assets is up to 75 extra queries
#: for five columns. None of the five ``__str__`` methods walks a SECOND FK (checked: Location
#: "code · name", WorkCenter "code · name", OrgUnit name, Party name, Asset "code · name"), so
#: nothing deeper is owed.
_ASSET_LIST_SELECT = ("location", "work_center", "org_unit", "custodian", "parent")

#: The detail page renders the three commercial pointers as well.
_ASSET_DETAIL_SELECT = _ASSET_LIST_SELECT + ("supplier", "service_vendor", "fixed_asset")


# =================================================================================================
# Shared scoping helpers for the 4.13 view modules — see the module docstring for why they live
# here. Each returns ``.none()`` for a tenant-less caller rather than a filter on NULL, so a
# superuser (``tenant=None``) gets an empty dropdown instead of a filter that silently matches every
# workspace's rows (the ``_item_qs`` / ``_location_qs`` idiom, verbatim).
# =================================================================================================
def _asset_qs(tenant):
    """This workspace's assets, for an ``?asset=`` filter dropdown on any 4.13 list page."""
    if tenant is None:
        return Asset.objects.none()
    return Asset.objects.filter(tenant=tenant).order_by("code")


def _work_center_qs(tenant):
    """4.8's work-centre master, scoped — the asset list's ``?work_center=`` dropdown."""
    if tenant is None:
        return WorkCenter.objects.none()
    return WorkCenter.objects.filter(tenant=tenant).order_by("code")


def _org_unit_qs(tenant):
    """The spine's org units, scoped — the asset list's ``?org_unit=`` dropdown."""
    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant).order_by("name")


def _party_qs(tenant):
    """This workspace's parties, for an ``?assigned_to=`` / ``?reported_by=`` filter dropdown.

    Deliberately WIDER than the forms' role-narrowed dropdowns: you cannot ASSIGN work to somebody
    who is not an employee, but "what is still assigned to them" stays a fair question after the
    role is removed (the 4.12 ``_owner_qs`` reading of the same asymmetry).
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant).order_by("name")


def _open_downtime_jobs(tenant):
    """Work orders with an OPEN downtime window — the queryset behind every "down now" answer.

    One statement of the rule, read by the list's ``Exists()`` annotation AND by the header chip, so
    the chip and the rows under it cannot disagree about what "down" means. It mirrors
    ``Asset.is_down_now()`` exactly: an OPEN job (i.e. one whose status is not in
    ``CLOSED_JOB_STATUSES`` — an unknown status therefore counts as open, which errs towards showing
    the job) that has a ``downtime_start`` and no ``downtime_end``.

    Deliberately NOT restricted to ``work_type="breakdown"``: what makes an asset down is an open
    outage, not the label on the job.

    ``tenant`` is applied UNCONDITIONALLY and is not optional. A ``None`` resolves to
    ``tenant IS NULL`` on a NOT NULL column and matches nothing — which is the point: the chip is
    counted from this queryset directly, so a "skip the filter when there is no tenant" convenience
    would show a tenant-less superuser a count of every workspace's downed machines.
    """
    return (MaintenanceWorkOrder.objects
            .filter(tenant=tenant, downtime_start__isnull=False, downtime_end__isnull=True)
            .exclude(status__in=Asset.CLOSED_JOB_STATUSES))


def _apply_warranty_filter(queryset, value, today):
    """Narrow to one warranty bucket, derived from the date — see :data:`WARRANTY_CHOICES`.

    The boundaries are written from ``Asset.WARRANTY_NOTICE_DAYS``, the same constant
    ``Asset.warranty_chip()`` reads, so the bucket a row lands in and the chip it renders always
    agree: ``expired`` = past, ``expiring`` = today through today+notice (the chip's amber band,
    which INCLUDES "expires today"), ``in_force`` = beyond that.

    An asset with **no** warranty date matches none of the three, and that is correct rather than an
    omission — "not recorded" is its own state and is never green (``warranty_chip``'s rule). A junk
    or absent value narrows nothing and is echoed back as ``""``, the ``crud_list`` posture on a bad
    filter: skip it, never 500, and never silently show an empty page.
    """
    horizon = today + timedelta(days=Asset.WARRANTY_NOTICE_DAYS)
    if value == "expired":
        return queryset.filter(warranty_expires_on__lt=today), value
    if value == "expiring":
        return (queryset.filter(warranty_expires_on__gte=today,
                                warranty_expires_on__lte=horizon), value)
    if value == "in_force":
        return queryset.filter(warranty_expires_on__gt=horizon), value
    return queryset, ""


def _hours(minutes):
    """``minutes`` as hours to 2dp — the one piece of arithmetic a Django template cannot do.

    Django ships no arithmetic filter, and "4 380 minutes" is not a figure anybody reads off a
    reliability card. ``Decimal`` throughout: mixing float division into a page that otherwise
    renders exact decimal hours and money is how two totals stop reconciling.
    """
    return (Decimal(minutes or 0) / Decimal("60")).quantize(Decimal("0.01"))


# =================================================================================================
# Asset — CRUD
# =================================================================================================
@login_required
def asset_list(request):
    """The plant register: search, eight filters, four header chips.

    EVERY filter is applied BEFORE ``crud_list`` paginates. A filter applied afterwards would page
    over the unfiltered set and quietly show the wrong rows on page 2.

    The three pk filters go through ``crud_list``'s ``is_int=True`` spec, which applies the L11
    guard: ``?location=abc``, ``?location=²`` (a Unicode superscript — ``isdigit()`` says yes,
    ``int()`` says no) and ``?location=99999999999999999999`` (converts fine, then overflows inside
    the driver) all SKIP the filter rather than raise on a URL anybody can type into the address bar.

    **Two annotations, and neither is a per-row method call.** ``down_now`` is an ``Exists()``
    subquery — a correlated EXISTS stops at the first matching row, where a ``Count`` would GROUP BY
    the whole child table to answer a yes/no. ``open_jobs_count`` is ONE grouped ``Count``, and it is
    one deliberately: a SECOND aggregate over a second reverse relation would LEFT JOIN both children
    into a cartesian product per asset and multiply both figures (the 4.8 WorkCenter finding, and the
    same fan-out ``Asset.maintenance_cost_to_date`` documents). The negated filter is safe here —
    ``Q.resolve_expression`` passes ``split_subq=False``, so ``~Q(...)`` inside an aggregate ``filter``
    compiles inline rather than into an exclusion subquery — and it is written as the negation of
    ``CLOSED_JOB_STATUSES`` rather than as ``OPEN_STATUSES`` so it matches ``Asset.open_jobs()``
    token for token: an unknown status counts as OPEN, which errs towards showing a job.
    """
    today = timezone.localdate()
    horizon = today + timedelta(days=Asset.WARRANTY_NOTICE_DAYS)

    queryset = (Asset.objects.filter(tenant=request.tenant)
                .select_related(*_ASSET_LIST_SELECT)
                .annotate(
                    down_now=Exists(_open_downtime_jobs(request.tenant)
                                    .filter(asset=OuterRef("pk"))),
                    open_jobs_count=Count(
                        "work_orders",
                        filter=~Q(work_orders__status__in=Asset.CLOSED_JOB_STATUSES)),
                )
                # STATED, not inherited, and this line is load-bearing. Django IGNORES Meta.ordering
                # on any query carrying an aggregate (3.1+), so the moment the Count above was added
                # this queryset became genuinely unordered — `QuerySet.ordered` goes False, the
                # Paginator raises UnorderedObjectListWarning, and page 2 is whatever the database
                # felt like returning. `code` is unique per tenant, so it is a total order and needs
                # no tie-break. (Caught by the smoke run, and exactly the 4.8 WorkCenter note.)
                .order_by("code"))

    # The one filter crud_list's equality spec cannot express — a derived date bucket, not a column.
    queryset, warranty = _apply_warranty_filter(
        queryset, (request.GET.get("warranty") or "").strip(), today)

    # ONE aggregate for three of the four chips, over the UNFILTERED workspace on purpose: "6
    # warranties expiring" is a fact somebody has to act on, and recomputing it per filter would make
    # the number change as you browse.
    chips = Asset.objects.filter(tenant=request.tenant).aggregate(
        warranty_expiring=Count("id", filter=Q(warranty_expires_on__gte=today,
                                               warranty_expires_on__lte=horizon)),
        warranty_expired=Count("id", filter=Q(warranty_expires_on__lt=today)),
        critical=Count("id", filter=Q(criticality="critical", is_active=True)),
    )
    # Counted from the JOB side and de-duplicated: two open outages on one machine is one machine
    # down, and counting jobs would report a number the "Down" chips on the rows cannot add up to.
    down_count = _open_downtime_jobs(request.tenant).values("asset_id").distinct().count()

    return crud_list(
        request, queryset, "scm/assets/asset/list.html",
        search_fields=["code", "name", "serial_number", "tag_code", "manufacturer", "model_number"],
        filters=[("status", "status", False),
                 ("criticality", "criticality", False),
                 ("asset_type", "asset_type", False),
                 # is_int=True -> the L11 guard above.
                 ("location", "location_id", True),
                 ("work_center", "work_center_id", True),
                 ("org_unit", "org_unit_id", True),
                 ("is_active", "is_active", False)],
        extra_context={
            "status_choices": Asset.STATUS_CHOICES,
            "criticality_choices": CRITICALITY_CHOICES,
            "asset_type_choices": Asset.ASSET_TYPE_CHOICES,
            "warranty_choices": WARRANTY_CHOICES,
            # The RESOLVED value, not request.GET — a junk ?warranty=foo narrowed nothing, so the
            # select must show "All" rather than an option that did not happen.
            "warranty": warranty,
            "warranty_notice_days": Asset.WARRANTY_NOTICE_DAYS,
            "locations": _location_qs(request.tenant),
            "work_centers": _work_center_qs(request.tenant),
            "org_units": _org_unit_qs(request.tenant),
            "down_count": down_count,
            "warranty_expiring_count": chips["warranty_expiring"] or 0,
            "warranty_expired_count": chips["warranty_expired"] or 0,
            "critical_count": chips["critical"] or 0,
        },
    )


@login_required
def asset_create(request):
    """Register an asset. ``crud_create`` stamps the tenant, audits, and refuses a tenant-less user.

    ``AssetForm`` ALSO stamps the tenant onto the unsaved instance (``TenantUniqueMixin``), and that
    is not redundancy: ``crud_create`` assigns ``obj.tenant`` only AFTER ``is_valid()``, so without
    the form-side stamp ``Asset.clean()``'s cross-tenant FK guard, its ``tag_code`` uniqueness rule
    and its hierarchy-cycle walk would all validate an instance whose ``tenant_id`` is None — the
    exact case every one of them skips — and would be dead code on the create path.
    """
    if _need_tenant(request):
        return redirect("scm:asset_list")
    return crud_create(request, form_class=AssetForm,
                       template="scm/assets/asset/form.html",
                       success_url="scm:asset_list")


@login_required
def asset_edit(request, pk):
    """Editable at any status, deliberately.

    An asset record describes a physical thing that gets moved, re-tagged, re-assigned and
    re-purposed, and a retired machine is often the row that most needs correcting. Nothing an edit
    can reach is a derived figure: MTBF, availability, downtime and maintenance cost have no columns
    at all, so there is nothing here for a form to restate. ``status`` IS on the form and that is the
    design — it has exactly one writer and it is the user; no work-order verb touches it, because
    "is this machine down right now" is answered from the open downtime windows instead.
    """
    return crud_edit(request, model=Asset, pk=pk, form_class=AssetForm,
                     template="scm/assets/asset/form.html",
                     success_url="scm:asset_list")


@login_required
def asset_detail(request, pk):
    """The 360° page: what it is, how it has behaved, what it costs and what it owes.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.Asset`, with all eight FKs joined.
    * **Warranty** — ``warranty_chip`` (a plain ``(label, css)`` 2-tuple: render ``warranty_chip.0``
      and ``warranty_chip.1``) and ``days_to_warranty_expiry`` (int, negative once past, ``None``
      when no warranty date is recorded).
    * **Reliability panel** — ``mtbf_hours``, ``mttr_hours``, ``availability_pct``,
      ``maintenance_cost_to_date``, ``downtime_minutes`` (int), ``downtime_hours`` (Decimal),
      ``failure_count`` (int), ``is_down_now`` (bool), ``open_job_count`` (int). **The first three
      are ``None`` whenever the question has no honest answer** — an asset that has never failed has
      no MTBF, and one whose observation window cannot be established has no availability. Print an
      em dash for ``None``; a ``0`` there reads as "fails constantly, never available", which is the
      exact opposite of the truth (L: the 4.11 confident-zero lesson).
    * **Spare parts** — ``spare_parts`` (a LIST of :class:`AssetSparePart`, ``item`` joined, each row
      carrying an attached ``on_hand`` Decimal — see below) and ``spare_part_count``.
    * **Job history** — ``work_orders`` (a LIST, capped at :data:`MAX_PANEL_ROWS`, newest first,
      ``parts`` prefetched so ``wo.parts_cost`` / ``wo.total_cost`` are safe to print;
      ``wo.open_task_count`` is NOT — it walks ``tasks``, which is not prefetched),
      ``work_orders_truncated`` (bool), ``work_order_count`` and ``open_work_order_count``.
    * **Meter** — ``readings`` (a LIST, capped at :data:`MAX_READING_ROWS`, newest first),
      ``readings_truncated``, ``reading_count`` and ``latest_reading``
      (a :class:`MeterReading` on the asset's PRIMARY meter, or ``None``).
    * **Hierarchy** — ``children`` (a LIST, capped), ``children_truncated``, ``child_count``.
    * **PM programme** — ``plans`` (a LIST of :class:`MaintenancePlan`; each is safe to ask for
      ``due_status_label`` / ``due_status_css`` / ``days_until_due`` / ``meter_gap`` — see the
      priming note below) and ``plan_count``, plus ``next_pm_due`` (a date, or ``None``).
    * **Book value** — ``acquisition_cost``, ``accumulated_depreciation`` and ``book_value``, read
      from the linked ``accounting.FixedAsset``. All three are ``None`` when no book record is
      linked; that is a MISSING LINK, not a zero-value asset, and must render as an em dash or a
      "Link a fixed asset" prompt.
    * **Failure analysis** — ``failure_codes``: a list of dicts ``{"code", "label", "jobs",
      "downtime_minutes"}``, one per recorded problem code, busiest first. Empty list when nothing
      has been coded.
    * ``can_delete`` — ``True`` only when no work order references this asset. **Gate the Delete
      button on it**: that is exactly the condition :func:`asset_delete` enforces, and offering a
      one-click failure is worse than not offering it. Delete is tenant-admin only, so wrap it in
      ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` as well (a member shown
      a button they will 403 on is the 4.11 finding).

    **Two priming steps keep this page's query count flat**, and both are worth knowing about:

    * every plan is handed the already-fetched ``obj`` as its ``asset`` and the single
      ``latest_reading`` this page already paid for, so ``due_status()`` — which consults the meter
      axis before the calendar one — does not re-query the reading table once per plan; and
    * on-hand for the parts list is ONE grouped aggregate over ``StockMove``, attached to each row as
      ``part.on_hand``. The template must read that attribute and **must not** call
      ``part.item.on_hand()``, which is a fresh aggregate per row.

    The reliability block itself is around a dozen small queries (each model method owns its own
    arithmetic and re-derives what it needs). That is the deliberate trade: one page, one asset, and
    the alternative is a view that re-implements MTBF and drifts from the model that defines it.
    """
    obj = get_object_or_404(
        Asset.objects.select_related(*_ASSET_DETAIL_SELECT), pk=pk, tenant=request.tenant)

    # --- the parts list, plus on-hand in ONE grouped aggregate -------------------------------------
    spare_parts = list(obj.spare_parts.select_related("item"))
    if spare_parts:
        # on_hand is the SUM of an append-only ledger (Item.on_hand()); asking it per row would be
        # one aggregate per part. The explicit tenant= is redundant (the items are the asset's own
        # tenant's) and is stated anyway so this query holds to the module-wide rule mechanically.
        totals = dict(
            StockMove.objects
            .filter(tenant=request.tenant, item_id__in=[p.item_id for p in spare_parts])
            .values("item_id").annotate(q=Sum("quantity")).values_list("item_id", "q"))
        for part in spare_parts:
            part.on_hand = totals.get(part.item_id) or ZERO

    # --- the job history --------------------------------------------------------------------------
    # `parts` prefetched because MaintenanceWorkOrder.parts_cost iterates self.parts.all() by design
    # (it reuses the page's cache rather than firing a Sum per print). One extra query for the whole
    # panel instead of one per row.
    work_orders = list(obj.work_orders
                       .select_related("plan", "assigned_to", "service_vendor")
                       .prefetch_related("parts")[:MAX_PANEL_ROWS + 1])
    work_orders_truncated = len(work_orders) > MAX_PANEL_ROWS
    del work_orders[MAX_PANEL_ROWS:]
    # ONE aggregate for both counters rather than two round trips.
    job_counts = obj.work_orders.aggregate(
        total=Count("id"),
        open=Count("id", filter=~Q(status__in=Asset.CLOSED_JOB_STATUSES)))

    # --- the meter --------------------------------------------------------------------------------
    readings = list(obj.meter_readings.select_related("recorded_by")[:MAX_READING_ROWS + 1])
    readings_truncated = len(readings) > MAX_READING_ROWS
    del readings[MAX_READING_ROWS:]
    # The asset's own answer to "what does the meter say now" — which, when a primary meter is named,
    # deliberately does NOT fall back to readings logged under another name.
    latest_reading = obj.latest_reading()

    # --- the hierarchy ----------------------------------------------------------------------------
    children = list(obj.children.filter(tenant=request.tenant)
                    .select_related("location")[:MAX_PANEL_ROWS + 1])
    children_truncated = len(children) > MAX_PANEL_ROWS
    del children[MAX_PANEL_ROWS:]
    # The COUNT is only paid for when the slice actually hid something — otherwise the list length IS
    # the count, and a second round trip to learn what we already know is a query for nothing.
    child_count = (obj.children.filter(tenant=request.tenant).count()
                   if children_truncated else len(children))

    # --- the PM programme -------------------------------------------------------------------------
    plans = list(obj.maintenance_plans.select_related("assigned_to", "parts_location"))
    for plan in plans:
        # Prime BOTH caches. `plan.asset` would otherwise be a fetch per plan (they are all this same
        # row), and `MaintenancePlan.latest_reading()` — consulted by due_status() before the
        # calendar axis, and again by meter_gap() — delegates to `self.asset.latest_reading()`, which
        # is one query per plan for a value this page has already read exactly once. The cache
        # attribute is the model's own documented mechanism, not a private detail invented here.
        plan.asset = obj
        plan._latest_reading_cache = latest_reading

    # --- the failure hierarchy, in ONE grouped query ----------------------------------------------
    # Cancelled jobs excluded, for the reason Asset._jobs() gives: a cancelled job can still carry a
    # downtime window typed before it was called off, and counting it charges the asset for work
    # nobody did. Labels resolved here because a template cannot call get_FOO_display on a dict.
    failure_codes = [
        {"code": row["problem_code"],
         "label": _PROBLEM_LABELS.get(row["problem_code"], row["problem_code"]),
         "jobs": row["jobs"],
         "downtime_minutes": row["downtime"] or 0}
        for row in (obj.work_orders
                    .exclude(status="cancelled").exclude(problem_code="")
                    .values("problem_code")
                    .annotate(jobs=Count("id"), downtime=Sum("downtime_minutes"))
                    .order_by("-jobs", "problem_code"))
    ]

    # --- the accounting link, READ ONLY (4.13 owns no depreciation figure — L29) --------------------
    book = obj.fixed_asset
    downtime_minutes = obj.downtime_minutes()

    return render(request, "scm/assets/asset/detail.html", {
        "obj": obj,
        # A plain 2-tuple: templates read .0 (label) and .1 (css class).
        "warranty_chip": obj.warranty_chip(),
        "days_to_warranty_expiry": obj.days_to_warranty_expiry(),

        # None is passed straight through on all four — see the docstring. Never substitute 0.
        "mtbf_hours": obj.mtbf_hours(),
        "mttr_hours": obj.mttr_hours(),
        "availability_pct": obj.availability_pct(),
        "maintenance_cost_to_date": obj.maintenance_cost_to_date(),
        "downtime_minutes": downtime_minutes,
        "downtime_hours": _hours(downtime_minutes),
        "failure_count": obj.failure_count(),
        "is_down_now": obj.is_down_now(),
        "open_job_count": job_counts["open"] or 0,

        "spare_parts": spare_parts,
        "spare_part_count": len(spare_parts),

        "work_orders": work_orders,
        "work_orders_truncated": work_orders_truncated,
        "work_order_count": job_counts["total"] or 0,
        "open_work_order_count": job_counts["open"] or 0,

        "readings": readings,
        "readings_truncated": readings_truncated,
        "reading_count": obj.meter_readings.count(),
        "latest_reading": latest_reading,

        "children": children,
        "children_truncated": children_truncated,
        "child_count": child_count,

        "plans": plans,
        "plan_count": len(plans),
        "next_pm_due": obj.next_pm_due(),

        # None, not 0, when there is no book record: a missing LINK is not a worthless asset.
        "acquisition_cost": book.acquisition_cost if book else None,
        "accumulated_depreciation": book.accumulated_depreciation if book else None,
        "book_value": book.book_value() if book else None,

        "failure_codes": failure_codes,

        # The exact condition asset_delete enforces — see its docstring.
        "can_delete": not (job_counts["total"] or 0),
    })


@tenant_admin_required
@require_POST
def asset_delete(request, pk):
    """Delete an asset — refused while any maintenance job references it.

    ``MaintenanceWorkOrder.asset`` is ``PROTECT`` deliberately: a finished job is HISTORY, carrying
    the cost, the downtime and the failure codes every reliability figure in this sub-module is
    derived from, and losing that must not be one click away. So this pre-checks and refuses with a
    sentence naming the blocker, and ALSO catches ``ProtectedError`` — the pre-check is the good
    message, the catch is what stops a job raised between the check and the delete from becoming an
    uncaught 500 (the 4.10 ``currency_delete`` finding, priced in advance rather than after).

    What DOES go with the asset is said out loud, and only after the delete actually succeeded:
    ``MaintenancePlan.asset``, ``AssetSparePart.asset`` and ``MeterReading.asset`` are all
    ``CASCADE``, so the PM programme, the parts list and the entire append-only meter history are
    removed with it — and the meter log cannot be reconstructed from anything. ``Asset.parent`` is
    ``SET_NULL`` by contrast, so child assets SURVIVE and merely lose their place in the hierarchy.

    Tenant-admin gated for that reason, and because retiring an asset (``status="retired"``, a plain
    edit) is the move that keeps the history — which is why the status vocabulary has ``retired``
    and ``disposed`` in it at all.
    """
    obj = get_object_or_404(Asset, pk=pk, tenant=request.tenant)

    jobs = obj.work_orders.count()
    if jobs:
        messages.error(
            request,
            f"{obj.code} still has {jobs} maintenance work order(s) and cannot be deleted — that "
            "history is what every reliability and cost figure on this page is derived from. Set "
            "its status to Retired or Disposed instead; a retired asset stops appearing as live "
            "plant and keeps its record.")
        return redirect("scm:asset_detail", pk=pk)

    # Counted BEFORE the delete, while the rows still exist to be counted.
    plans = obj.maintenance_plans.count()
    parts = obj.spare_parts.count()
    readings = obj.meter_readings.count()
    orphaned = obj.children.count()

    try:
        with transaction.atomic():
            # atomic() so the audit row crud_delete writes BEFORE deleting rolls back with a delete
            # that then fails.
            response = crud_delete(request, model=Asset, pk=pk, success_url="scm:asset_list")
    except ProtectedError as exc:
        # Generic, not an enumeration: nothing but MaintenanceWorkOrder PROTECTs this table today,
        # but Module 11 is a declared FK extender of it and an enumeration would go stale silently —
        # as a 500 on a mainline delete.
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(request, f"{obj.code} is still referenced by {', '.join(blockers)} and "
                                "cannot be deleted — retire it instead.")
        return redirect("scm:asset_detail", pk=pk)

    if plans or parts or readings:
        messages.info(
            request,
            f"Removed with {obj.code}: {plans} maintenance plan(s), {parts} spare-part line(s) and "
            f"{readings} meter reading(s). The meter log was append-only and cannot be "
            "reconstructed.")
    if orphaned:
        messages.info(request, f"{orphaned} component asset(s) lost their parent and are now "
                               "top-level — re-point them at the replacement assembly.")
    return response


# =================================================================================================
# AssetSparePart — the machine's parts list.
#
# A tenant-less child throughout: resolved via ``asset__tenant``, hand-rolled rather than crud_*,
# and therefore owing its own audit row. See the module docstring for the full rationale.
# =================================================================================================
@login_required
def asset_add_spare_part(request, pk):
    """Add one item to an asset's parts list. The PARENT comes from the route, never from POST.

    ``AssetSparePartForm`` has no ``asset`` field by design: a parent pk in the POST body is how a
    caller grafts a line onto somebody else's machine, and the child carries no ``tenant`` column of
    its own to catch it. Passing ``asset=`` here is also what makes the form's ``clean()`` (the item
    must belong to the ASSET's workspace) and its ``validate_unique()`` (the
    ``unique_together ("asset", "item")`` check Django would otherwise skip entirely, turning a
    duplicate line into an uncaught ``IntegrityError``) run at all on the create path.

    Hand-rolled rather than ``crud_create``, which would pass no ``asset=`` and would try to stamp a
    ``tenant`` this model has not got — so the audit row is written here.
    """
    asset = get_object_or_404(Asset, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = AssetSparePartForm(request.POST, tenant=request.tenant, asset=asset)
        if form.is_valid():
            line = form.save(commit=False)
            # Re-stated rather than trusted to the constructor's stamp: the parent is the one fact
            # this form must not be able to disagree with the URL about.
            line.asset = asset
            line.save()
            # Tenant passed explicitly — write_audit_log resolves it from obj.tenant, and this child
            # has none, so without it the row would be filed against the USER's tenant by fallback.
            write_audit_log(request.user, line, "create", {
                "asset": str(asset),
                "item": str(line.item),
                "quantity_per_service": str(line.quantity_per_service),
                "is_critical": line.is_critical,
            }, tenant=request.tenant)
            messages.success(request, f"{line.item} added to {asset.code}'s parts list.")
            return redirect("scm:asset_detail", pk=asset.pk)
        # No messages.error here: the bound form is re-rendered below with its own field errors, and
        # a banner repeating them is noise that pushes the actual fields off the screen.
    else:
        form = AssetSparePartForm(tenant=request.tenant, asset=asset)

    return render(request, "scm/assets/assetsparepart/form.html", {
        "form": form,
        "is_edit": False,
        # The form has no `asset` field, so the breadcrumb and the cancel link can only get the
        # parent from here.
        "asset": asset,
    })


@login_required
def assetsparepart_edit(request, pk):
    """Correct one parts-list line.

    **Resolved through ``asset__tenant`` and nothing else.** ``AssetSparePart`` carries no ``tenant``
    column (it is a pure child), so a bare ``pk`` lookup would be a cross-tenant read.
    ``request.tenant`` of ``None`` resolves to ``asset__tenant IS NULL``, and that column is NOT
    NULL, so a tenant-less user gets a 404 rather than somebody else's machine's parts list.

    ``asset=obj.asset`` is passed so the form's tenant check and its unique-together repair are live
    on the edit path too. The form's constructor stamps the parent only when it is UNSET, so this
    cannot re-point an existing line at another asset.
    """
    obj = get_object_or_404(AssetSparePart.objects.select_related("asset", "item"),
                            pk=pk, asset__tenant=request.tenant)

    if request.method == "POST":
        form = AssetSparePartForm(request.POST, instance=obj, tenant=request.tenant,
                                  asset=obj.asset)
        if form.is_valid():
            line = form.save()
            write_audit_log(request.user, line, "update", _changed(form), tenant=request.tenant)
            messages.success(request, "Spare part updated.")
            return redirect("scm:asset_detail", pk=obj.asset_id)
        # Re-rendered below with the form's own field errors — see the add path's note.
    else:
        form = AssetSparePartForm(instance=obj, tenant=request.tenant, asset=obj.asset)

    return render(request, "scm/assets/assetsparepart/form.html", {
        "form": form,
        "is_edit": True,
        "asset": obj.asset,
        "obj": obj,
    })


@tenant_admin_required
@require_POST
def assetsparepart_delete(request, pk):
    """Remove one item from an asset's parts list.

    Same ``asset__tenant`` resolution as the edit, and hand-rolled for the same reason
    (``crud_delete`` filters ``tenant=`` on the model, which this child has not got) — so the audit
    row is written HERE, before the delete, while the row still exists to be described.

    Deleting the association deletes nothing else: ``AssetSparePart.item`` is ``PROTECT``, pointing
    the other way, so the ``Item`` and every stock move against it are untouched. What is lost is the
    statement that this machine consumes this part — which is what the storeroom reads before a
    service — so the write is tenant-admin gated like every other delete in the sub-module.
    """
    obj = get_object_or_404(AssetSparePart.objects.select_related("asset", "item"),
                            pk=pk, asset__tenant=request.tenant)
    asset_pk = obj.asset_id
    label = f"{obj.item} on {obj.asset.code}"
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Removed {label} from the parts list. The item itself and its stock "
                              "history are untouched.")
    return redirect("scm:asset_detail", pk=asset_pk)
