"""SCM 4.14 Labor Management — ``LaborStandard`` views: the standards library and its two verbs.

**This is the sub-module's master data, and every number 4.14 prints is measured against it.** A
labor module without a standard is a timeclock; ``LaborStandard.minutes_for()`` is the one place the
earned-minutes formula exists, and the pages below only *feed* it and *explain* it. Nothing here
re-derives a minute, a cost or a units-per-hour figure from the four determinants — the detail page's
worked example takes its total from ``minutes_for()`` and lays the named parts out around it (see
:func:`_worked_example`), so the screen that teaches people the formula cannot itself be a second
copy of it.

**4.14 writes no ``StockMove`` and no ``JournalEntry``, and this module writes neither of them nor
anything at all outside ``apps/scm``.** It also carries no pointer into ``hrm``: ``labour_rate`` is a
CHARGE-OUT rate on a standard, never a person's wage — ``hrm.SalaryStructureTemplate`` owns
compensation, SCM does not read it, and the payroll hand-off elsewhere in 4.14 is a CSV rather than
a foreign key.

--------------------------------------------------------------------------------------------------
THE LADDER, AND WHY BOTH VERBS ARE ADMIN-GATED
--------------------------------------------------------------------------------------------------
``status`` is ``editable=False`` and absent from ``LaborStandardForm.Meta.fields``, so the ONLY way
it moves is through the two verbs here. A crafted ``status=active`` in a POST body cannot land —
not because a view checks for it, but because there is no path from form data to the column.

The ladder, stated once — the module constants below are what BOTH the guard inside each verb and
the ``can_*`` flag on the detail page read, so a button and the route behind it cannot disagree about
whether an action is available (the 4.10 "two of three shapes" finding)::

    activate   draft -> active        archived -> active     (re-published; overlap RE-CHECKED)
    archive    active -> archived     draft -> archived      (shelved, not deleted)
    edit       draft, active                                 (archived is frozen)
    delete     draft, archived                               (never a live row)

Both verbs are ``@tenant_admin_required`` because both change what every FUTURE ``LaborActivity``
snapshots: ``select_standard()`` considers ``active`` rows and nothing else, so activating redefines
what a scope earns from that moment on, and archiving silently removes the scope's measuring stick —
work booked afterwards is recorded as UNMEASURED (``earned_minutes`` ``None``) with nothing on any
screen announcing it. The archive verb therefore says so out loud when it leaves a scope uncovered,
which is the whole reason it does the extra lookup.

**Re-activating an archived standard re-runs the model's own validation, and that is the point of
:func:`_activation_refusal`.** ``LaborStandard.clean()``'s overlap refusal — the guard that keeps
``select_standard()`` deterministic — deliberately ignores archived rows on both sides. So a draft
may legitimately be saved across an archived row's date range, and bringing that archived row back
would recreate exactly the ambiguity the guard exists to prevent, without any save ever having been
refused. The verb asks the model, as an *active* row, whether it may exist; the model answers with
its own sentence.

**Editing is refused once archived**, for the same reason and stated on the model
(``EDITABLE_STATUSES = ("draft", "active")``). An ACTIVE standard stays editable on purpose: every
``LaborActivity`` snapshots the determinants at booking time, so a re-time changes what future work
earns and cannot restate a single minute already recorded.

**Deleting is refused while ACTIVE.** A live standard is what the resolver is answering with right
now; archive it first. Delete is still admin-gated and still loud, because the FKs pointing at this
row are ``SET_NULL``: deleting does not corrupt one figure (``LaborActivity.has_standard`` asks the
SNAPSHOTS, never ``standard_id``) but it does erase the trail from a measurement back to the rule it
was measured under, and nothing reconstructs that.

--------------------------------------------------------------------------------------------------
THE THREE-BUCKET "EFFECTIVE" FILTER — DERIVED, NOT A COLUMN
--------------------------------------------------------------------------------------------------
``current`` / ``future`` / ``expired`` is a DATE-RANGE question, not a stored flag, and deliberately
so: the answer changes by the calendar rolling over, and a column would need something running every
night to stay true (4.13's ``warranty`` filter, same reasoning, same shape). :func:`_effective_state`
and :func:`_apply_effective_filter` are the same rule in two dialects — one in Python for a fetched
row, one in SQL for the queryset — and the Python half is built ON TOP of
``LaborStandard.is_effective_on()`` so "in force" has exactly one definition. A row the filter puts
in a bucket must render that bucket's chip, or the page argues with itself.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/labor/laborstandard/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``). Filter context: ``activity_choices`` / ``basis_choices`` / ``source_choices`` /
  ``status_choices`` / ``effective_choices`` (all lists of ``(value, label)`` pairs), ``locations``
  and ``item_categories`` (querysets for the two pk dropdowns — compare with
  ``|stringformat:"d"``, NEVER ``|slugify``), and ``effective`` (the RESOLVED bucket, ``""`` when
  the param is absent or junk — bind the select to THIS, not to ``request.GET.effective``, so a
  filter that did not happen is not shown as selected). Header chips: ``stats``, a dict with keys
  ``active`` / ``draft`` / ``archived`` / ``lapsed`` — ``lapsed`` counts rows that are still
  ``active`` yet whose window has already closed, i.e. live-looking standards the resolver can never
  pick again. Also ``today`` (for the chip's help text). Filter params: ``q`` / ``activity`` /
  ``basis`` / ``source`` / ``status`` (strings — compare with ``request.GET.<param>`` directly),
  ``location`` / ``item_category`` (pks) and ``effective``.
* ``scm/labor/laborstandard/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path, from
  ``crud_edit``).
* ``scm/labor/laborstandard/detail.html`` — see :func:`laborstandard_detail`'s docstring for the
  full key list; it is long enough to belong beside the code that builds it.

Badge colours come from the model's own ``status_css`` property and from ``effective_chip.1``.
``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css and render as
completely unstyled text (L33).

``laborstandard_activate``, ``_archive`` and ``_delete`` are ``@tenant_admin_required``, so wrap
those three buttons in ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` —
showing a member a button they will 403 on is the 4.11 finding.
"""
from decimal import InvalidOperation

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _location_qs, _need_tenant

from apps.scm.forms import LaborStandardForm
# The clamped quantizers every writer AND every printer of a computed figure goes through. Imported
# from `_base` (the MaintenanceWorkOrders precedent) rather than reimplemented: q4 CLAMPS as well as
# quantizes, so a hostile `?quantity=` degrades to a capped figure on the page instead of a
# DataError-shaped 500 out of the arithmetic.
from apps.scm.models._base import q2, q4
# The three shared vocabularies come from `_choices` via the models package's re-export, NOT from
# `_meta.get_field(...).choices`: they are the same lists the form renders from, and naming them
# directly is what keeps "the filter offers what the column accepts" a fact rather than a
# coincidence. `STATUS_CHOICES` is genuinely model-local (nothing outside a standard has an opinion
# about draft/active/archived) and is read off the class.
from apps.scm.models import (ACTIVITY_CHOICES, ItemCategory, LaborStandard,
                             STANDARD_BASIS_CHOICES, STANDARD_SOURCE_CHOICES, select_standard)

ZERO = Decimal("0")
SIXTY = Decimal("60")

#: How many sibling standards the detail page's ladder panel shows. A queryset SLICE, so the
#: DATABASE applies it — it bounds what is FETCHED, not merely what is rendered (L40 §1: a guard
#: that first builds the whole thing is the payload, not a guard). One more than the cap is fetched
#: so the page can say it is showing a window without paying for a second COUNT.
MAX_PANEL_ROWS = 25

#: The quantity the detail page's worked example uses when the reader has not asked for one. 100
#: rather than 1 on purpose: the entire reason a standard splits fixed time from variable time is
#: that setup and travel AMORTISE, and at a quantity of one they do not — the example would show the
#: one case that makes a per-unit standard look identical to a per-task one.
SAMPLE_QUANTITY = Decimal("100")

#: Ceiling on a hand-typed ``?quantity=``. A constant, not something derived from the row (L40).
#: It is not a correctness guard — ``minutes_for()`` goes through ``q4()``, which clamps — it is a
#: legibility one: a worked example computed for 1e600 units teaches nobody anything, and the page
#: should show a bounded figure rather than a wall of nines.
MAX_SAMPLE_QUANTITY = Decimal("1000000")

# ================================================================================== the two verbs
# Declared ONCE and read by BOTH the guard inside each verb and the `can_*` flag handed to the
# detail template, so a button and the route behind it can never disagree about whether an action is
# available (the 4.10 "two of three shapes" finding).

#: `archived` is included, and that is the interesting half: bringing a superseded standard back is
#: a real operation (a re-time that was reverted, a seasonal standard that returns), and refusing it
#: outright would push people towards editing dates on a live row instead — which is worse. It is
#: safe only because :func:`_activation_refusal` re-runs the model's overlap guard as an active row;
#: see there.
ACTIVATABLE_STATUSES = ("draft", "archived")

#: `draft` as well as `active`: a draft that turned out wrong but is worth keeping as a record is
#: shelved, not deleted. Archiving a draft is a no-op for the resolver (a draft was never selected),
#: which is exactly why it is harmless.
ARCHIVABLE_STATUSES = ("draft", "active")

#: Deliberately NOT `active`. A live standard is what `select_standard()` is answering with right
#: now; removing it mid-flight leaves its scope unmeasured with nothing on screen saying so. Archive
#: is the reversible move that does the same job, so delete is one rung further down the ladder.
DELETABLE_STATUSES = ("draft", "archived")

#: The three derived effectivity buckets. NOT a model vocabulary: there is no `effective_status`
#: column and there must not be one — the answer changes when the calendar rolls over, so a stored
#: flag would need a nightly job to stay true (4.13's `WARRANTY_CHOICES`, same reasoning).
EFFECTIVE_CHOICES = [
    ("current", "In force today"),
    ("future", "Starts later"),
    ("expired", "Window closed"),
]

#: Colour per bucket, decided in one place so the list chip and the detail chip cannot drift. Only
#: the six classes that exist in theme.css may appear (L33). `future` is info rather than green
#: because a standard that has not started yet is not measuring anything.
EFFECTIVE_CSS = {
    "current": "badge-green",
    "future": "badge-info",
    "expired": "badge-slate",
}

_EFFECTIVE_LABELS = dict(EFFECTIVE_CHOICES)


# ================================================================================== small helpers
def _detail(pk):
    """The one redirect target every verb and refusal in this module answers with."""
    return redirect("scm:laborstandard_detail", pk=pk)


def _effective_state(standard, today):
    """Which of :data:`EFFECTIVE_CHOICES` this row's window puts it in on ``today``.

    Built ON TOP of ``LaborStandard.is_effective_on()`` rather than beside it, so "is this standard
    in force" has exactly one definition and this function only names which side of it a row falls
    on. Says nothing about ``status`` — deliberately, and the detail page depends on the separation:
    "was this standard in force then?" and "is this standard live now?" are different questions, and
    an archived row still has an honest answer to the first.
    """
    if standard.is_effective_on(today):
        return "current"
    if standard.effective_from and today < standard.effective_from:
        return "future"
    return "expired"


def _effective_chip(standard, today):
    """``(label, css)`` for :func:`_effective_state` — the ``warranty_chip`` 2-tuple shape.

    Templates read ``.0`` and ``.1``. A tuple rather than two context keys so a row and its colour
    are handed over together and cannot be paired up wrongly by the template.
    """
    state = _effective_state(standard, today)
    return _EFFECTIVE_LABELS[state], EFFECTIVE_CSS[state]


def _apply_effective_filter(queryset, value, today):
    """Narrow to one effectivity bucket — the SQL dialect of :func:`_effective_state`.

    The two are the same rule written twice because they answer for different things (a queryset
    the database has not sent yet vs. a row already in hand), and they are kept adjacent so a change
    to one is visibly a change to both. A row this puts in ``expired`` must render the slate chip, or
    the filter and the badge under it are describing different facts.

    ``current`` is "started, and either open-ended or not yet closed" — the identical pair of
    predicates ``select_standard()`` applies. A junk or absent value narrows NOTHING and is echoed
    back as ``""``: the ``crud_list`` posture on a bad filter (L11) — skip it, never 500, and never
    silently show an empty page while the select claims a bucket was chosen.
    """
    if value == "current":
        return (queryset.filter(effective_from__lte=today)
                .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)), value)
    if value == "future":
        return queryset.filter(effective_from__gt=today), value
    if value == "expired":
        # `effective_to__lt` also excludes the open-ended rows for free: NULL fails the comparison,
        # which is correct — a standard with no end date has not expired and never will.
        return queryset.filter(effective_to__lt=today), value
    return queryset, ""


def _scope_label(standard):
    """The standard's scope as one sentence, so the template does not carry four branches.

    Both pointers blank is the network-wide default and is a first-class answer, not a gap — which
    is why it gets words of its own rather than two em dashes.
    """
    where = standard.location.code if standard.location_id and standard.location else "Every location"
    what = (standard.item_category.name
            if standard.item_category_id and standard.item_category else "Every item category")
    if not standard.location_id and not standard.item_category_id:
        return "Network-wide — every location, every item category"
    return f"{where} · {what}"


def _sample_quantity(raw):
    """A hand-typed ``?quantity=`` as a usable Decimal, or the default. Never raises.

    Three separate things have to be refused here and only the first is obvious:

    * ``?quantity=abc`` raises ``InvalidOperation`` out of ``Decimal()``;
    * ``?quantity=NaN`` and ``?quantity=Infinity`` PARSE CLEANLY — ``Decimal`` accepts both — and
      then raise ``InvalidOperation`` from the ``min``/``max`` comparison below, one line further on,
      which is the same 500 wearing a different hat. ``is_finite()`` is what closes it;
    * ``?quantity=1E+600`` is finite, converts fine, and would render a worked example nobody can
      read. It is clamped rather than refused, because a clamped example is still a true statement
      about the standard.

    This is a URL anybody can type into the address bar, so all three take the same answer the read
    side takes everywhere else in this codebase (L11): fall back, never raise.
    """
    raw = (raw or "").strip()
    if not raw:
        return SAMPLE_QUANTITY
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return SAMPLE_QUANTITY
    if not value.is_finite():
        return SAMPLE_QUANTITY
    return min(max(value, ZERO), MAX_SAMPLE_QUANTITY)


def _worked_example(standard, quantity):
    """The earned-minutes formula, laid open for one quantity — the glass box.

    **The TOTAL is never recomputed here.** ``standard.minutes_for(quantity)`` is the sub-module's
    single definition of earned minutes and this function calls it; what it adds is the *named
    parts* around that answer, because a supervisor arguing with a standard needs to see which
    determinant the minutes came from. The allowance line is deliberately the RESIDUAL
    (``total − measured``) rather than a second application of ``× (100 + pct) / 100``: written that
    way the parts always sum to exactly what the model said, including the ``q4()`` rounding step,
    so this page cannot show a breakdown that disagrees with the figure printed above it. If
    ``minutes_for()`` is ever re-timed, the total moves and the allowance row moves with it.

    Returns a dict; every ratio in it is ``None`` — never ``0`` — when its denominator is zero.
    A standard cannot have zero total minutes (``clean()`` refuses one at the door), but a quantity
    of zero is legitimate and asks a different question ("what does the fixed time alone cost?"),
    and 0 units/hour would read as "this work is impossible" rather than "you asked for none of it".

    ``cost`` and ``cost_per_unit`` are ``None`` when no rate has been set, which is the model's own
    posture: an unpriced activity means nobody has costed it, and the page says so with a blank
    instead of inventing a confident 0.00 (the 4.11 lesson).
    """
    per_unit = standard.minutes_per_unit or ZERO
    setup = standard.setup_minutes or ZERO
    travel = standard.travel_minutes or ZERO

    variable = q4(quantity * per_unit)
    measured = q4(setup + travel + variable)
    total = standard.minutes_for(quantity)          # THE definition — see the docstring
    priced = bool(standard.labour_rate)
    cost = standard.cost_for(quantity) if priced else None

    return {
        "quantity": quantity,
        "setup_minutes": setup,
        "travel_minutes": travel,
        "minutes_per_unit": per_unit,
        "variable_minutes": variable,
        "measured_minutes": measured,
        "allowance_pct": standard.allowance_pct or ZERO,
        "allowance_minutes": q4(total - measured),
        "total_minutes": total,
        "total_hours": q2(total / SIXTY),
        # What one unit ACTUALLY costs in minutes once the fixed time is spread over the batch —
        # the figure that makes a per-task standard's economics visible, and the reason the example
        # defaults to 100 units rather than 1.
        "effective_minutes_per_unit": q4(total / quantity) if quantity > ZERO else None,
        "units_per_hour": q2(quantity * SIXTY / total) if quantity > ZERO and total > ZERO else None,
        "cost": cost,
        "cost_per_unit": (q4(cost / quantity) if cost is not None and quantity > ZERO else None),
    }


def _activation_refusal(standard):
    """Ask the model, AS AN ACTIVE ROW, whether it may exist. Returns the refusal sentence or ``""``.

    This is the whole reason re-activating an archived standard is safe. ``LaborStandard.clean()``'s
    overlap refusal — the only thing keeping ``select_standard()`` deterministic — skips archived
    rows on BOTH sides: it does not run for an archived instance, and it does not see archived rows
    when it does run. So a draft can legitimately be saved across an archived row's date range, no
    save is ever refused, and switching the archived row back to ``active`` would then produce two
    live standards covering one scope on one day — the exact ambiguity the guard exists to prevent,
    arrived at without a single validation error along the way.

    ``status`` is set on the in-memory instance BEFORE calling ``clean()`` because that is the input
    the guard branches on: asking an archived row whether it may become active without telling it so
    is the one question it cannot answer. The caller stamps the same value a moment later, so
    nothing is left mutated that was not already going to be.

    The model's own sentences are returned verbatim — it names the clashing standard and its date
    span, which is what somebody has to act on. Re-running the WHOLE ``clean()`` rather than the
    overlap branch alone is deliberate: a row written by a fixture, a data migration or a direct DB
    edit could fail the zero-standard or basis-pairing rules too, and publishing it would put a
    standard that earns nothing into the resolver.
    """
    standard.status = "active"
    try:
        standard.clean()
    except ValidationError as exc:
        return " ".join(exc.messages)
    return ""


def _announce_activation(request, standard):
    """After activating: say whether this row actually governs anything YET.

    An active standard whose window opens next month is a perfectly sensible thing to publish and a
    confusing thing to be shown, because the button said "activate" and the scope's numbers did not
    move. Saying it plainly here is cheaper than the support question.
    """
    today = timezone.localdate()
    if _effective_state(standard, today) == "future":
        messages.info(request, f"It takes effect on {standard.effective_from:%d %b %Y} — until then "
                               f"{standard.get_activity_display().lower()} work in this scope is "
                               "still measured against whatever governs it today.")


def _announce_archive(request, standard):
    """After archiving: name the successor, or warn that the scope now has NO standard at all.

    Archiving removes the row from ``select_standard()``, and an activity with no standard has
    ``earned_minutes = None`` — not zero. That is the honest answer and it is also invisible: the
    work still gets booked, the session still closes, and the scorecard simply stops having a
    performance figure for that scope with nothing anywhere announcing why. One resolver call at the
    moment of the decision is what turns a silent consequence into a sentence.
    """
    successor = select_standard(standard.tenant, standard.activity,
                                location=standard.location_id,
                                item_category=standard.item_category_id)
    scope = _scope_label(standard)
    activity = standard.get_activity_display().lower()
    if successor is not None:
        messages.info(request, f"{activity.capitalize()} work for {scope} is now measured against "
                               f"{successor.number} · {successor.name}.")
        return
    messages.warning(
        request,
        f"No active standard now covers {activity} for {scope}. Work booked against it will be "
        "recorded as UNMEASURED — no earned minutes and no performance figure, on the scorecard or "
        "in any plan — until a replacement is published. The minutes already recorded keep their "
        "own snapshots and are unaffected.")


def _transition(request, pk, *, from_statuses, to_status, action, verb, precheck=None, after=None):
    """Guard, stamp, audit, redirect — the shape both status verbs in this file share.

    ``action`` and ``verb`` are two different things and both are needed. ``action`` is the SLUG the
    audit row is keyed on (``activate`` / ``archive``), matching the trail 4.12/4.13 leave so the log
    stays filterable; ``verb`` is the past participle the two human sentences read with ("… cannot
    be activated", "LST-00001 activated.").

    The row is taken ``FOR UPDATE`` and its status re-read INSIDE ``transaction.atomic()``, so a
    double-click, a retry or a replay cannot walk one standard through the ladder twice. ``precheck``
    is called INSIDE that lock rather than by the caller before it, for the reason the 4.13 fix
    records: a guard evaluated outside the lock answers about the state the request started in, and
    the write then simply waits for the lock and lands anyway.

    **What the lock does NOT close, stated so nobody assumes it does:** two admins activating two
    DIFFERENT standards covering one scope at the same moment lock different rows, so each one's
    overlap query can miss the other's uncommitted write. No row lock closes that — it would take a
    lock over the scope, which is not a row. It is survivable rather than merely unlikely, and that
    is by design: ``select_standard()`` breaks ties on ``-effective_from`` then ``-id``, so even two
    live standards for one scope still resolve to exactly ONE deterministic answer. The overlap
    guard is what keeps that answer *arguable*; the tie-break is what keeps it *reproducible*.

    The object is resolved BEFORE the status guard so a cross-tenant pk answers **404 rather than a
    302** that would leak "there is a row there, you just cannot move it" (the 4.12 finding).

    ``save(update_fields=…)`` is narrow on purpose — a full ``save()`` would write back every
    in-memory column, including any a concurrent edit had just changed. ``updated_at`` is
    ``auto_now``, so it only fires when it is IN the list.
    """
    with transaction.atomic():
        obj = get_object_or_404(LaborStandard.objects.select_for_update().select_related(
            "location", "item_category"), pk=pk, tenant=request.tenant)
        if obj.status not in from_statuses:
            messages.error(request, f"{obj.number} cannot be {verb} — it is "
                                    f"{obj.get_status_display().lower()}.")
            return _detail(pk)
        if precheck is not None:
            refusal = precheck(obj)
            if refusal:
                messages.error(request, refusal)
                return _detail(pk)

        obj.status = to_status
        obj.save(update_fields=["status", "updated_at"])

    write_audit_log(request.user, obj, "update", {"action": action, "status": to_status})
    messages.success(request, f"{obj.number} {verb}.")
    # Flashed AFTER the commit, so a message describing the new state can never survive a rollback
    # of the change it describes.
    if after is not None:
        after(request, obj)
    return _detail(pk)


# ======================================================================================= the list
@login_required
def laborstandard_list(request):
    """The standards library: search, six column filters and one derived effectivity bucket.

    EVERY filter is applied BEFORE ``crud_list`` paginates. A filter applied afterwards would page
    over the unfiltered set and quietly show the wrong rows on page 2.

    The two pk filters go through ``crud_list``'s ``is_int=True`` spec, which applies the L11 guard:
    ``?location=abc``, ``?location=²`` (a Unicode superscript — ``isdigit()`` says yes, ``int()``
    says no) and ``?location=99999999999999999999`` (converts fine, then overflows inside the
    driver) all SKIP the filter rather than raise on a URL anybody can type into the address bar.
    ``?effective=`` is the one filter that spec cannot express — it is a date-range question against
    two columns, not an equality — so it is pre-applied through :func:`_apply_effective_filter` and
    the RESOLVED value is echoed back for the select to bind to.

    ``.defer("notes")`` drops the one ``TextField`` no list row renders. ``defer`` touches the SELECT
    list ONLY, so the search below is unaffected — and ``name`` and ``number`` must NOT be deferred,
    because they are exactly what it searches.

    ``stats`` is counted over the WHOLE workspace rather than the filtered page, on purpose: "3
    lapsed standards" is a fact somebody has to act on, and recomputing it per filter would make the
    number change as you browse. ``lapsed`` is the one worth having — a row still marked ``active``
    whose window has already closed looks live on every screen and can never be picked by
    ``select_standard()`` again, so its scope has silently stopped being measured.
    """
    today = timezone.localdate()

    queryset = (LaborStandard.objects.filter(tenant=request.tenant)
                .select_related("location", "item_category")
                .defer("notes")
                # STATED, not inherited. It is the same tuple as Meta.ordering and it ends in `-id`,
                # so it is a total order and page 2 is deterministic — saying so here saves the next
                # reader a trip to the model to find that out.
                .order_by("activity", "-effective_from", "-id"))

    queryset, effective = _apply_effective_filter(
        queryset, (request.GET.get("effective") or "").strip(), today)

    stats = LaborStandard.objects.filter(tenant=request.tenant).aggregate(
        active=Count("id", filter=Q(status="active")),
        draft=Count("id", filter=Q(status="draft")),
        archived=Count("id", filter=Q(status="archived")),
        lapsed=Count("id", filter=Q(status="active", effective_to__lt=today)),
    )

    return crud_list(
        request, queryset, "scm/labor/laborstandard/list.html",
        search_fields=["name", "number"],
        filters=[("activity", "activity", False),
                 ("basis", "basis", False),
                 ("source", "source", False),
                 ("status", "status", False),
                 # is_int=True -> the L11 guard above.
                 ("location", "location_id", True),
                 ("item_category", "item_category_id", True)],
        extra_context={
            "activity_choices": ACTIVITY_CHOICES,
            "basis_choices": STANDARD_BASIS_CHOICES,
            "source_choices": STANDARD_SOURCE_CHOICES,
            "status_choices": LaborStandard.STATUS_CHOICES,
            "effective_choices": EFFECTIVE_CHOICES,
            # The RESOLVED bucket, not request.GET — a junk `?effective=soon` narrowed nothing, so
            # the select must show "All" rather than an option that did not happen.
            "effective": effective,
            # Both querysets are ordered by their own Meta (`Location` by code, `ItemCategory` by
            # name) and neither `__str__` walks a second FK, so neither dropdown owes an
            # `order_by` or a `select_related` — checked, not assumed.
            "locations": _location_qs(request.tenant),
            "item_categories": ItemCategory.objects.filter(tenant=request.tenant),
            "stats": stats,
            "today": today,
        },
    )


# ======================================================================================= the CRUD
@login_required
def laborstandard_create(request):
    """Write a standard. It starts as a ``draft`` and measures nothing until somebody activates it.

    ``crud_create`` stamps the tenant, audits and refuses a tenant-less user; ``_need_tenant`` is
    still called first so the refusal lands back on this module's list rather than the dashboard.

    ``LaborStandardForm`` ALSO stamps the tenant onto the unsaved instance, and that is not
    redundancy: ``crud_create`` assigns ``obj.tenant`` only AFTER ``is_valid()``, so without the
    form-side stamp ``LaborStandard.clean()``'s cross-tenant FK guard and — far more importantly —
    its OVERLAP REFUSAL would both skip themselves on the create path, which is precisely the path
    that creates overlaps.
    """
    if _need_tenant(request):
        return redirect("scm:laborstandard_list")
    return crud_create(request, form_class=LaborStandardForm,
                       template="scm/labor/laborstandard/form.html",
                       success_url="scm:laborstandard_list")


@login_required
def laborstandard_edit(request, pk):
    """Editable while ``draft`` or ``active``; frozen once archived.

    An ACTIVE standard staying editable looks wrong until you know that every ``LaborActivity``
    snapshots the determinants at booking time: a re-time changes what FUTURE work earns and cannot
    restate a single minute already recorded, so there is no history here for an edit to rewrite.

    ``archived`` is the frozen one, for the reason that is easy to miss and is stated on the model:
    the overlap guard in ``clean()`` deliberately ignores archived rows, so editing an archived
    standard back into a live date range would slip past the one check that keeps
    ``select_standard()`` deterministic. Bringing one back is the activate verb's job, and that verb
    re-runs the guard.
    """
    obj = get_object_or_404(LaborStandard.objects.only("pk", "number", "status"),
                            pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is archived and can no longer be edited — an "
                                "archived standard is the rule last quarter's numbers were measured "
                                "under. Activate it first if it should apply again, or write a new "
                                "standard starting today.")
        return _detail(pk)
    return crud_edit(request, model=LaborStandard, pk=pk, form_class=LaborStandardForm,
                     template="scm/labor/laborstandard/form.html",
                     success_url="scm:laborstandard_list")


@login_required
def laborstandard_detail(request, pk):
    """Explain the standard: the worked formula, the scope, the window, and who actually governs.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.LaborStandard`, both scope FKs joined. Badge colour is
      ``obj.status_css``.
    * **The worked example** — ``worked``, a dict from :func:`_worked_example` with keys
      ``quantity`` / ``setup_minutes`` / ``travel_minutes`` / ``minutes_per_unit`` /
      ``variable_minutes`` / ``measured_minutes`` / ``allowance_pct`` / ``allowance_minutes`` /
      ``total_minutes`` / ``total_hours`` / ``effective_minutes_per_unit`` / ``units_per_hour`` /
      ``cost`` / ``cost_per_unit``. The four ratios are ``None`` — never ``0`` — when they have no
      denominator, and ``cost`` / ``cost_per_unit`` are ``None`` when no charge-out rate is set.
      Print an em dash for each; a ``0.00`` in a cost tile reads as "this work is free", which is
      the opposite of "nobody has priced it". Plus ``sample_quantity`` (the Decimal the example was
      computed for — bind the quantity input's ``value`` to this, NOT to ``request.GET.quantity``,
      which may have been junk) and ``max_sample_quantity``.
    * **Scope** — ``scope_label`` (one sentence, already resolved; blank pointers read as
      "Network-wide", which is a first-class answer rather than a gap).
    * **The window** — ``effective_chip`` (a plain ``(label, css)`` 2-tuple: render
      ``effective_chip.0`` and ``effective_chip.1``), ``effective_state`` (the raw
      ``current`` / ``future`` / ``expired`` token, for a conditional), ``is_effective_today``
      (bool) and ``today``.
    * **Who governs** — ``resolved_standard`` (what ``select_standard()`` returns for THIS activity
      and THIS scope today: a :class:`LaborStandard`, possibly this very row, or ``None`` when the
      scope has no standard at all), ``governs_now`` (bool — True when the resolver's answer IS this
      row) and ``resolution_reason`` (a sentence explaining why it is not, ``""`` when it is). This
      block is the page's headline: a standard can be perfectly configured and still measure
      nothing, and this is the only place that says so.
    * **The ladder** — ``scope_siblings`` (a LIST of the workspace's other standards for the same
      activity, newest window first, capped at :data:`MAX_PANEL_ROWS`; each row carries an attached
      ``effective_chip`` 2-tuple — read THAT, never recompute it in the template),
      ``scope_siblings_truncated`` (bool) and ``sibling_count``. This is what makes "why does another
      row win?" answerable on the page instead of by reading ``select_standard()``.
    * **Usage** — ``activity_count`` (how many booked activities snapshot this standard) and
      ``plan_line_count``. Both feed the delete confirmation: deleting does not change one recorded
      figure (``LaborActivity.has_standard`` asks the SNAPSHOTS, never ``standard_id``) but it does
      erase the trail from each of those rows back to the rule it was measured under.
    * **Action gates** — ``can_edit`` / ``can_activate`` / ``can_archive`` / ``can_delete``, read
      from the same tuples the verbs guard on so a button and its route cannot disagree. The last
      three are tenant-admin only, so ALSO wrap them in
      ``{% if request.user.is_superuser or request.user.is_tenant_admin %}``.
    """
    today = timezone.localdate()
    obj = get_object_or_404(
        LaborStandard.objects.select_related("location", "item_category"),
        pk=pk, tenant=request.tenant)

    quantity = _sample_quantity(request.GET.get("quantity"))

    # --- who actually governs this scope today ----------------------------------------------------
    # The resolver is asked with this row's OWN scope, so the question is precisely "if somebody
    # books this activity here today, does this standard measure it?". The pks are passed rather
    # than the instances (select_standard accepts either) purely to avoid re-touching the two
    # already-joined FKs.
    resolved = select_standard(request.tenant, obj.activity,
                               location=obj.location_id, item_category=obj.item_category_id,
                               on_date=today)
    governs_now = resolved is not None and resolved.pk == obj.pk
    resolution_reason = ""
    if not governs_now:
        # Ordered narrowest-cause-first: status is checked before the window because an archived row
        # is out of the resolver whatever its dates say, and reporting the dates would send somebody
        # to fix the wrong thing.
        if obj.status != "active":
            resolution_reason = (
                f"This standard is {obj.get_status_display().lower()}, and the resolver considers "
                "active standards only — nothing is measured against it.")
        elif not obj.is_effective_on(today):
            resolution_reason = (
                f"It takes effect on {obj.effective_from:%d %b %Y}."
                if _effective_state(obj, today) == "future"
                else f"Its window closed on {obj.effective_to:%d %b %Y}.")
        elif resolved is not None:
            # The winner is necessarily on the SAME rung of the ladder, which is why the sentence can
            # say so flatly: the resolver was asked with this row's own scope, so if this row is
            # active and in force it matches the narrowest rung the query reaches — the only thing
            # that can beat it there is another row with the same scope and a later start date. Two
            # of those existing at once is what LaborStandard.clean()'s overlap guard refuses; this
            # branch is what the tie-break looks like when a row slipped in before that guard did.
            resolution_reason = (
                f"{resolved.number} · {resolved.name} is selected instead — it covers the same "
                "activity and the same scope and takes effect later "
                f"({resolved.effective_from:%d %b %Y}), and the resolver breaks a tie on the latest "
                "start date. Two live standards for one scope is what the overlap check refuses; "
                "close one of them off.")
        else:
            # Unreachable in a consistent read — an active, in-force row always matches its own rung
            # — and kept anyway, because the alternative when it IS reached is an empty explanation
            # sitting under a "does not govern" heading, which tells the reader nothing at all.
            resolution_reason = ("No standard is selected for this activity and scope today — check "
                                 "the effective window and the scope pointers.")

    # --- the ladder around it ---------------------------------------------------------------------
    # Every standard for the same ACTIVITY, whatever its scope: the resolver walks
    # location+category -> category -> location -> network-wide, so a row that "should" have won is
    # very often one sitting on a different rung, and a panel narrowed to this row's exact scope
    # would hide precisely the rows that explain the answer. Meta.ordering (activity,
    # -effective_from, -id) is already the reading order.
    siblings = list(LaborStandard.objects
                    .filter(tenant=request.tenant, activity=obj.activity)
                    .exclude(pk=obj.pk)
                    .select_related("location", "item_category")
                    .defer("notes")[:MAX_PANEL_ROWS + 1])
    siblings_truncated = len(siblings) > MAX_PANEL_ROWS
    del siblings[MAX_PANEL_ROWS:]
    for sibling in siblings:
        # Attached rather than recomputed per render: the chip is pure date arithmetic and touches
        # no table, but the template must not carry a second copy of the bucket rule (L33 + the
        # "filter and badge agree" rule at the top of this module).
        sibling.effective_chip = _effective_chip(sibling, today)
    # The COUNT is only paid for when the slice actually hid something — otherwise the list length
    # IS the count, and a round trip to learn what we already hold is a query for nothing.
    sibling_count = (LaborStandard.objects.filter(tenant=request.tenant, activity=obj.activity)
                     .exclude(pk=obj.pk).count() if siblings_truncated else len(siblings))

    # --- what points at it ------------------------------------------------------------------------
    # The explicit `tenant=` / `plan__tenant=` narrow nothing (both children are reached through this
    # standard, which is already this workspace's) and are the house idiom for a reason: they hold
    # the module-wide scoping rule mechanically, and `LaborPlanLine` carries NO tenant column of its
    # own, so `plan__tenant` is the only shape that can express the question at all.
    activity_count = obj.measured_activities.filter(tenant=request.tenant).count()
    plan_line_count = obj.plan_lines.filter(plan__tenant=request.tenant).count()

    return render(request, "scm/labor/laborstandard/detail.html", {
        "obj": obj,

        "worked": _worked_example(obj, quantity),
        "sample_quantity": quantity,
        "max_sample_quantity": MAX_SAMPLE_QUANTITY,

        "scope_label": _scope_label(obj),

        "effective_chip": _effective_chip(obj, today),
        "effective_state": _effective_state(obj, today),
        "is_effective_today": obj.is_effective_on(today),
        "today": today,

        "resolved_standard": resolved,
        "governs_now": governs_now,
        "resolution_reason": resolution_reason,

        "scope_siblings": siblings,
        "scope_siblings_truncated": siblings_truncated,
        "sibling_count": sibling_count,

        "activity_count": activity_count,
        "plan_line_count": plan_line_count,

        # The exact conditions the four routes enforce — see each one's docstring.
        "can_edit": obj.is_editable,
        "can_activate": obj.status in ACTIVATABLE_STATUSES,
        "can_archive": obj.status in ARCHIVABLE_STATUSES,
        "can_delete": obj.status in DELETABLE_STATUSES,
    })


@tenant_admin_required
@require_POST
def laborstandard_delete(request, pk):
    """Delete a standard — refused while it is ACTIVE, and loud about what it takes with it.

    **Refused while active** because a live standard is what ``select_standard()`` is answering with
    right now: removing it mid-flight leaves its scope unmeasured with nothing on any screen saying
    so. Archive it first — that is the reversible move which does the same job, and it announces the
    consequence.

    **Not refused when rows point at it**, and that is a deliberate difference from the PROTECT-shaped
    deletes elsewhere in ``scm``. ``LaborActivity.standard`` and ``LaborPlanLine.standard`` are both
    ``SET_NULL``, so deleting cannot corrupt a single recorded figure: every measurement carries its
    own determinant snapshots and ``LaborActivity.has_standard`` asks THOSE, never ``standard_id``.
    What is destroyed is the trail from a measurement back to the rule it was measured under, and
    nothing reconstructs that — so the counts are read BEFORE the delete, while the rows still exist
    to be counted, and named in the message afterwards.

    Hand-rolled rather than delegated to ``crud_delete``, and the reason is the whole point of the
    view: ``crud_delete`` re-fetches by pk WITHOUT a lock and re-checks a guard it was never told
    about. Read from an unlocked snapshot the status guard is advisory — it answers about the state
    this request started in, and the DELETE then waits on the lock and executes anyway, so firing
    activate and delete back to back removes a live standard out from under the resolver (the 4.13
    TOCTOU fix, priced in advance rather than after).
    """
    with transaction.atomic():
        obj = get_object_or_404(LaborStandard.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in DELETABLE_STATUSES:
            messages.error(
                request,
                f"{obj.number} is active and cannot be deleted — it is the standard this scope's "
                "work is being measured against right now. Archive it first; an archived standard "
                "leaves the resolver but keeps the rule last quarter's numbers were measured under.")
            return _detail(pk)

        # Counted inside the lock and before the delete, while the rows still exist to be counted.
        activities = obj.measured_activities.filter(tenant=request.tenant).count()
        plan_lines = obj.plan_lines.filter(plan__tenant=request.tenant).count()
        number, name = obj.number, obj.name
        # Inside the transaction so it rolls back with a failed delete rather than recording a
        # deletion that did not happen.
        write_audit_log(request.user, obj, "delete")
        obj.delete()

    messages.success(request, f"{number} · {name} deleted.")
    if activities or plan_lines:
        messages.info(
            request,
            f"{activities} booked activity line(s) and {plan_lines} plan line(s) lost their pointer "
            "to it. Every recorded figure is unchanged — each row carries its own snapshot of the "
            "determinants it was measured under — but the link back to this rule is gone and cannot "
            "be restored.")
    return redirect("scm:laborstandard_list")


# ================================================================================== the two verbs
@tenant_admin_required
@require_POST
def laborstandard_activate(request, pk):
    """draft | archived -> active. Admin-gated: this decides what every future booking earns.

    Activating is not a cosmetic state change. ``select_standard()`` considers ``active`` rows and
    nothing else, so from this moment every ``LaborActivity`` filed for this activity in this scope
    snapshots THESE determinants as its earned minutes — and no page anywhere announces that the
    measuring stick moved. That is why it is a button with its consequence printed beside it rather
    than a dropdown on the edit form, and why it is tenant-admin only.

    :func:`_activation_refusal` re-runs the model's own validation as an active row INSIDE the lock.
    That is what makes re-activating an archived standard safe rather than the one move that can
    manufacture the ambiguity ``select_standard()`` is guaranteed to be free of — see there for the
    full argument.
    """
    return _transition(request, pk, from_statuses=ACTIVATABLE_STATUSES, to_status="active",
                       action="activate", verb="activated",
                       precheck=_activation_refusal, after=_announce_activation)


@tenant_admin_required
@require_POST
def laborstandard_archive(request, pk):
    """draft | active -> archived. Admin-gated for the same reason, in the opposite direction.

    Archiving removes the row from ``select_standard()``. Nothing already recorded moves — every
    ``LaborActivity`` carries its own snapshot of the determinants — but from now on, work in this
    scope with no other standard covering it is booked UNMEASURED: ``earned_minutes`` ``None``, no
    performance figure, and no error. :func:`_announce_archive` spends one resolver call to turn
    that silence into a sentence naming either the successor or the gap.

    This is the move to reach for instead of delete, and instead of editing dates on a live row. It
    is reversible (the activate verb accepts ``archived``, re-checking the overlap guard on the way
    back), and it keeps the rule last quarter's numbers were measured under readable.
    """
    return _transition(request, pk, from_statuses=ARCHIVABLE_STATUSES, to_status="archived",
                       action="archive", verb="archived", after=_announce_archive)
