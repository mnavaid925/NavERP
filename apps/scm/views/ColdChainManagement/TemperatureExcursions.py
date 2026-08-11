"""SCM 4.15 Cold Chain Management — the ``TemperatureExcursion`` triage queue and its five verbs.

An excursion has **two halves written by two different owners**, and every view in this module is
shaped by keeping them apart (the ``SupplyChainAlert`` detector-vs-triage split, one domain over):

* **the measured half is DETECTOR-WRITTEN and read-only here.** ``started_at`` / ``ended_at`` /
  ``duration_minutes`` / ``breach_direction`` / ``extreme_temperature`` / ``limit_min`` /
  ``limit_max`` / ``reading_count`` / ``mkt`` / ``last_detected_at`` are computed by
  ``apps/scm/coldchain.py`` from the reading ledger and are ``editable=False`` on the model. No form
  in this sub-module carries one, **and neither does the back-dated create page** — it takes a
  monitor and a window and asks ``coldchain.window_stats()`` for every number. A measurement a user
  can retype is not a measurement.
* **the human half is the only writable block:** severity, the product assessment, the cause code,
  the corrective action, the notes, and the three links out to the NCR / work order / lot that
  somebody else acts on.

``limit_min`` / ``limit_max`` are a SNAPSHOT of the band that was in force when the episode fired.
The detail page must say so: editing the monitor's limits today cannot and must not change what this
record says about last month.

--------------------------------------------------------------------------------------------------
THE VERBS USE THE SHARED ``_status_transition``, AND THE REFUSALS GO IN ``precheck``
--------------------------------------------------------------------------------------------------
``apps/scm/views/_helpers.py`` already does guard -> ``select_for_update()`` -> status re-read INSIDE
the lock -> stamp -> ``write_audit_log`` -> message -> redirect, and its own docstring says the whole
point is that there is ONE copy: *"with three copies, the next lock or audit fix has to be found and
landed three times, and the one that gets missed fails silently under load rather than at import."*
So :func:`temperatureexcursion_acknowledge`, ``_close`` and ``_dismiss`` delegate to it.

**The "still running" refusal on ``close`` is a ``precheck``, not a check in this module.** That is
exactly what the parameter is for: a guard reading anything other than the row's own status is a
plain snapshot read when it runs outside the lock — it answers about the state the request started
in, and the write then lands the moment the competing transaction commits (the 4.13 cancel/delete
TOCTOU fix). ``ended_at`` is moved by the DETECTOR, concurrently, which is precisely the racing
writer that makes this matter.

**``close`` / ``dismiss`` deliberately do NOT stamp ``acknowledged_by`` / ``acknowledged_at``.** The
model's own ``_stamp_seen`` fills those only when they are blank ("the first acknowledger always
wins"), and ``_status_transition`` resolves its ``stamps`` dict BEFORE the lock — so reproducing that
rule here would mean reading the row outside the lock to decide, which is the one thing the lock
exists to prevent. Who closed it is recorded where it belongs: the ``core.AuditLog`` row this
transition writes, keyed on the ``close`` / ``dismiss`` action. Do not "fix" this by stamping
unconditionally; that overwrites the first acknowledger, which the model forbids in as many words.

``_assess`` is the one hand-rolled verb, because it consumes typed input. It opens its own
``transaction.atomic()`` + ``select_for_update()`` and then calls ``TemperatureExcursion.assess()``,
which is the **only** writer of ``assessment`` / ``assessed_by`` / ``assessed_on`` and re-validates
every value it is handed.

``_raise_work_order`` delegates to ``coldchain.raise_work_order()``, which is idempotent under its
own lock. It is the sub-module's ONLY cross-sub-module write: one ``scm.MaintenanceWorkOrder`` with
an EXISTING ``SOURCE_CHOICES`` value, and no reciprocal edit to any 4.13 vocabulary.

--------------------------------------------------------------------------------------------------
PERMISSIONS
--------------------------------------------------------------------------------------------------
``_acknowledge`` stays ``@login_required``: seeing something is not a privileged act, and gating it
would slow the one response you want to be fast. ``_assess`` (the product release/reject decision),
``_close`` and ``_dismiss`` (both terminal), ``_delete`` and ``_raise_work_order`` (it writes another
sub-module's table — the ``labor_board_assign`` precedent) are all ``@tenant_admin_required``.

**Every verb is ``@require_POST``**, so a GET is a 405 rather than a silent state change, and every
one resolves its object with ``tenant=request.tenant`` BEFORE any status guard — a cross-tenant pk
must be 404 before any 302, because a 302 leaks "there is a row there, you just cannot move it" (the
4.12 finding). Wrap the admin-only buttons in
``{% if request.user.is_superuser or request.user.is_tenant_admin %}``: showing a member a button
they will 403 on is the 4.11 finding.
"""
from datetime import datetime, time, timedelta

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import (_acting_party, _date_window, _need_tenant, _report_day,
                                     _status_transition)

from apps.scm import coldchain
from apps.scm.forms import (TemperatureExcursionAssessForm, TemperatureExcursionForm,
                            TemperatureExcursionWindowForm)
from apps.scm.models import (
    ASSESSMENT_CHOICES,
    BREACH_DIRECTION_CHOICES,
    ColdChainMonitor,
    EXCURSION_CAUSE_CHOICES,
    EXCURSION_SEVERITY_CHOICES,
    EXCURSION_STATUS_CHOICES,
    OPEN_EXCURSION_STATUSES,
    TemperatureExcursion,
)
from apps.scm.views.ColdChainManagement.ColdChainMonitors import (
    FROZEN_MKT_NOTE,
    MAX_PANEL_ROWS,
    _monitor_qs,
)


# =================================================================================================
# The ladder
#
# Declared ONCE and read by BOTH the guard inside each verb and the `can_*` flag handed to the detail
# template, so a button and the route behind it can never disagree about whether an action is
# available (the 4.10 "two of three shapes" finding).
#
#     open ── acknowledge ──▸ investigating ── assess ──▸ assessed ── close ──▸ closed
#       └──────────────────── dismiss ────────────────────────────────────────▸ dismissed
#
# `assess` and `close` are reachable from EVERY open status, not only from the one before them: a
# triager who assesses straight off the queue has still assessed it, and forcing an acknowledge first
# would be ceremony that buys nothing. `close` additionally refuses while the episode is still
# running — the one STATE refusal in the sub-module worth being loud about.
# =================================================================================================

#: Only from `open`. Re-acknowledging must not overwrite the first acknowledger, and the model says
#: the same thing from the other side (`acknowledge()` is a no-op once past `open`).
ACKNOWLEDGE_STATUSES = ("open",)

#: Every open status. The verb writes the product verdict; which triage step preceded it is not a
#: precondition for having one.
ASSESS_STATUSES = OPEN_EXCURSION_STATUSES

#: Every open status, plus the running-episode refusal in `precheck`.
CLOSE_STATUSES = OPEN_EXCURSION_STATUSES

#: Every open status. Kept apart from `close` so the compliance report can tell "we fixed it" from
#: "we judged it a non-event" — collapsing the two would make the excursion count meaningless.
DISMISS_STATUSES = OPEN_EXCURSION_STATUSES

#: What the excursion list and detail pages join. Every one of these is rendered; none of the five
#: `__str__` methods walks a second FK except `LotSerial`, which reads `self.item.sku` — hence the
#: `lot_serial__item` join beside it.
_EXCURSION_SELECT = ("monitor", "monitor__location", "monitor__asset", "monitor__shipment",
                     "non_conformance", "maintenance_work_order", "lot_serial", "lot_serial__item")

#: The derived list filters. Neither is a column, and neither ever will be: `reportable` depends on
#: the monitor's grace period (editing that setting has to move the answer — a stored flag would
#: freeze last month's policy onto this month's episodes) and `running` is `ended_at IS NULL`.
REPORTABLE_CHOICES = [
    ("yes", "Reportable (outlived the grace period)"),
    ("no", "Under grace (a blip)"),
]
RUNNING_CHOICES = [
    ("open_episode", "Still breaching now"),
    ("ended", "Back in range"),
]

#: Printed above the measured block on the detail page.
SNAPSHOT_NOTE = (
    "The limits on this record are the ones that were IN FORCE when the episode fired — they are "
    "snapshotted at open time and never rewritten, not even when the episode extends. Editing the "
    "monitor's limits today changes what happens next; it cannot change what this record says about "
    "what already happened."
)

#: Printed above the triage block.
TRIAGE_NOTE = (
    "Everything above is written by the detector from the reading ledger and cannot be typed or "
    "edited. Everything below is the human judgement: how bad it was, whether the product was "
    "affected, why it happened, what was done — and the links out to the records another team owns. "
    "The DISPOSITION of affected product is 4.9's non-conformance, and quarantining a lot is that "
    "module's verb: 4.15 records the verdict and links to the row somebody else acts on."
)


def _detail(pk):
    """The redirect every verb answers with — one statement of it, passed to
    ``_status_transition``."""
    return redirect("scm:temperatureexcursion_detail", pk=pk)


def _transition(request, pk, *, from_statuses, to_status, action, verb, stamps=None,
                audit=None, message=None, precheck=None):
    """Delegates to the shared :func:`_status_transition` — see it for the locking contract.

    Kept as a two-line local so every verb below still reads ``_transition(request, pk, ...)`` and
    neither the model nor :func:`_detail` is repeated five times. This is 4.14's shape verbatim
    (``LaborSessions.py:258``); the body lives in ``views/_helpers.py`` because it IS the concurrency
    guard and a guard maintained in four places is a guard fixed in one and missed in three.
    """
    return _status_transition(
        request, TemperatureExcursion, pk, _detail,
        from_statuses=from_statuses, to_status=to_status, action=action, verb=verb,
        stamps=stamps, audit=audit, message=message, precheck=precheck)


def _refuse_running(obj):
    """``precheck`` for ``close``: refuse while the monitor is still outside its limits.

    Evaluated INSIDE ``_status_transition``'s row lock, which is the whole reason it is a callable
    rather than an ``if`` in the view. ``ended_at`` is written by the DETECTOR, concurrently and
    from another transaction, so a check that ran before the lock would answer about the state the
    request started in and the close would land the instant the detector's commit released the row.

    This is the one STATE refusal in the sub-module worth being loud about: closing an incident that
    is still happening files a compliance record saying the product was back in range while the
    freezer is still warming, and every duration on the report would be understated.
    """
    if obj.ended_at is None:
        return (f"{obj.number} is still running — the monitor has not come back inside its limits, "
                "so it cannot be closed yet. Run Detect on the monitor once it has recovered (or "
                "wait for the next pass), which is what writes the end time.")
    return ""


def _aware_bounds(date_from, date_to):
    """A date pair as the inclusive AWARE datetime range covering both days end to end.

    ``started_at`` is a ``DateTimeField`` while the two filter boxes post plain dates. A bare
    ``2026-08-04`` on the UPPER bound resolves to MIDNIGHT and would drop every episode that started
    during the day somebody asked about. An explicit aware range rather than ``started_at__date__``:
    ``__date`` compiles to ``CONVERT_TZ`` on MariaDB and returns NULL when the timezone tables are
    not loaded, which on XAMPP they are not (the 4.12 carbon-report finding).
    """
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
        end = timezone.make_aware(end)
    return start, end


def _reportable_q(tenant, bucket, now):
    """``Q`` for ``?reportable=`` — "did this episode outlive its monitor's grace period", or ``None``.

    ``TemperatureExcursion.is_reportable`` is ``live_duration_minutes() >=
    monitor.excursion_grace_minutes``, and ``live_duration_minutes()`` is two different expressions:
    the STORED ``duration_minutes`` once the episode has ended, and ``now - started_at`` while it is
    still running. So the filter is built in two halves.

    The closed half is a plain column comparison against ``monitor__excursion_grace_minutes``. The
    running half needs ``started_at <= now - grace minutes``, which is per-row datetime arithmetic no
    portable ORM expression gives us — so it is assembled as **one OR'd term per DISTINCT grace
    period in the workspace**, with the subtraction done in Python where it is trivial. One extra
    tiny query, and two or three terms in practice: a workspace runs a handful of grace periods, not
    a hundred.

    A grace of 0 makes every running episode reportable, which is exactly what a zero grace period
    means ("every breach counts").
    """
    if bucket not in ("yes", "no"):
        return None

    closed_reportable = Q(ended_at__isnull=False,
                          duration_minutes__gte=F("monitor__excursion_grace_minutes"))
    running_reportable = Q(pk__in=[])  # matches nothing — the honest identity for an OR fold
    graces = (ColdChainMonitor.objects.filter(tenant=tenant)
              .order_by()
              .values_list("excursion_grace_minutes", flat=True)
              .distinct())
    for grace in graces:
        cutoff = now - timedelta(minutes=grace or 0)
        running_reportable |= Q(ended_at__isnull=True,
                                monitor__excursion_grace_minutes=grace,
                                started_at__lte=cutoff)

    reportable = closed_reportable | running_reportable
    return reportable if bucket == "yes" else ~reportable


# =================================================================================================
# The queue
# =================================================================================================
@login_required
def temperatureexcursion_list(request):
    """The triage queue, newest first.

    **Filter GET params** (all applied BEFORE pagination):

    * ``q`` — free text over ``number`` and the monitor's ``name`` / ``number``
    * ``status`` — ``EXCURSION_STATUS_CHOICES`` (string)
    * ``severity`` — ``EXCURSION_SEVERITY_CHOICES`` (string)
    * ``assessment`` — ``ASSESSMENT_CHOICES`` (string)
    * ``cause`` — ``EXCURSION_CAUSE_CHOICES`` (string)
    * ``breach_direction`` — ``BREACH_DIRECTION_CHOICES`` (string)
    * ``monitor`` — a pk, through :func:`as_db_int` (L11)
    * ``reportable`` — ``yes`` / ``no``, DERIVED against the monitor's ``excursion_grace_minutes``
    * ``running`` — ``open_episode`` / ``ended``, DERIVED from ``ended_at IS NULL``
    * ``date_from`` / ``date_to`` — ``YYYY-MM-DD``, inclusive, on ``started_at``

    **Context:** ``object_list`` (the page slice) and ``rows``, ``page_obj``, ``q``, plus
    ``status_choices`` / ``severity_choices`` / ``assessment_choices`` / ``cause_choices`` /
    ``breach_direction_choices`` / ``reportable_choices`` / ``running_choices`` (lists of
    ``(value, label)`` pairs), ``monitors`` (queryset for the dropdown), the RESOLVED
    ``reportable`` / ``running`` buckets, ``date_from`` / ``date_to`` (raw echoed strings), and the
    workspace-wide chips ``open_count`` / ``running_count`` / ``critical_count`` / ``total_count``
    (ints, deliberately NOT recomputed per filter — "4 still breaching" is a fact somebody must act
    on, and a number that changed as you browsed would be useless).

    Each entry in ``rows`` is a dict: ``obj`` (the excursion), ``duration_minutes`` (int — the LIVE
    figure for a running episode, the stored one once closed), ``excess_c`` (Decimal or **``None``**:
    no extreme recorded, or no limit on the breached side — an excess of 0 means "it touched the
    limit exactly", which is a different statement) and ``is_reportable`` (bool). ``obj.mkt`` is
    **``None``** for a frozen monitor and for a window with no readable rows — render an em dash plus
    ``frozen_mkt_note``, never 0.00.

    ``select_related`` covers every FK a row renders, ``lot_serial__item`` included because
    ``LotSerial.__str__`` reads ``self.item.sku``; without it a page of 15 rows is up to 120 extra
    queries for four columns (L18).

    ``duration_minutes`` and ``excess_c`` are resolved in the VIEW rather than left to the template:
    both are model methods, and a Django template re-evaluates a method call every time it appears.
    Neither queries — ``is_reportable`` reads ``self.monitor.excursion_grace_minutes`` through the
    join above — so this costs nothing beyond calling each once.
    """
    tenant = request.tenant
    now = timezone.now()

    qs = (TemperatureExcursion.objects.filter(tenant=tenant)
          .select_related(*_EXCURSION_SELECT))

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(monitor__name__icontains=q)
                       | Q(monitor__number__icontains=q))

    for param in ("status", "severity", "assessment", "cause", "breach_direction"):
        value = (request.GET.get(param) or "").strip()
        if value:
            qs = qs.filter(**{param: value})

    monitor_pk = as_db_int(request.GET.get("monitor"))
    if monitor_pk is not None:
        qs = qs.filter(monitor_id=monitor_pk)

    running = (request.GET.get("running") or "").strip()
    if running == "open_episode":
        qs = qs.filter(ended_at__isnull=True)
    elif running == "ended":
        qs = qs.filter(ended_at__isnull=False)
    else:
        running = ""

    reportable = (request.GET.get("reportable") or "").strip()
    condition = _reportable_q(tenant, reportable, now)
    if condition is not None:
        qs = qs.filter(condition)
    else:
        reportable = ""

    raw_from = (request.GET.get("date_from") or "").strip()
    raw_to = (request.GET.get("date_to") or "").strip()
    widened = {}
    for param, raw, end_of_day in (("date_from", raw_from, False), ("date_to", raw_to, True)):
        # `_report_day` is the SHARED parser: junk drops the filter rather than 500-ing (L11), and it
        # clamps to the analytics bounds, without which a date near `date.min` makes the
        # `- timedelta(...)` arithmetic below raise OverflowError — a 500 from a URL anybody can type.
        day = _report_day(raw)
        if day is None:
            continue
        start, end = _aware_bounds(day, day)
        widened[param] = (end if end_of_day else start).isoformat()
    # The SHARED two-bound walk, never a second copy — junk input SKIPS the filter rather than
    # raising out of `.filter()` (L11), which is the whole posture `_date_window` exists to hold.
    qs = _date_window(qs, widened, "started_at")

    # STATED, not inherited: `-started_at, -id` is Meta.ordering, and saying it here keeps page 2
    # deterministic without the reader having to go and check.
    page_obj = paginate(request, qs.order_by("-started_at", "-id"))
    excursions = list(page_obj.object_list)
    rows = [{
        "obj": excursion,
        "duration_minutes": excursion.live_duration_minutes(now),
        "excess_c": excursion.excess_c(),
        "is_reportable": excursion.is_reportable,
    } for excursion in excursions]

    chips = TemperatureExcursion.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        open_triage=Count("id", filter=Q(status__in=OPEN_EXCURSION_STATUSES)),
        running=Count("id", filter=Q(ended_at__isnull=True)),
        critical=Count("id", filter=Q(severity="critical",
                                      status__in=OPEN_EXCURSION_STATUSES)))

    return render(request, "scm/coldchain/temperatureexcursion/list.html", {
        "object_list": excursions,
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "status_choices": EXCURSION_STATUS_CHOICES,
        "severity_choices": EXCURSION_SEVERITY_CHOICES,
        "assessment_choices": ASSESSMENT_CHOICES,
        "cause_choices": EXCURSION_CAUSE_CHOICES,
        "breach_direction_choices": BREACH_DIRECTION_CHOICES,
        "reportable_choices": REPORTABLE_CHOICES,
        "running_choices": RUNNING_CHOICES,
        "monitors": _monitor_qs(tenant),
        # The RESOLVED buckets, not request.GET — junk narrowed nothing, so the <select> shows "All".
        "reportable": reportable,
        "running": running,
        "date_from": raw_from,
        "date_to": raw_to,
        "total_count": chips["total"] or 0,
        "open_count": chips["open_triage"] or 0,
        "running_count": chips["running"] or 0,
        "critical_count": chips["critical"] or 0,
        "frozen_mkt_note": FROZEN_MKT_NOTE,
    })


# =================================================================================================
# CRUD
# =================================================================================================
@login_required
def temperatureexcursion_create(request):
    """The MANUAL, BACK-DATED create — a monitor and a window, and **not one measured number**.

    Somebody legitimately has to file an episode the detector cannot see: a logger whose file was
    lost, an event witnessed on a mechanical chart, an incident carried over from another system. So
    the form takes the two things a human genuinely knows — which monitor, and between when and when
    — plus the triage fields, and **this view asks ``coldchain.window_stats()`` for every measured
    figure** (``duration_minutes`` / ``breach_direction`` / ``extreme_temperature`` / ``limit_min`` /
    ``limit_max`` / ``reading_count`` / ``mkt``) computed from the readings actually in that window.

    That is the ONLY way both house rules survive at once: CRUD Completeness wants a create view for
    every model with a list page, and every measured column on this model is ``editable=False``
    because a measurement a user can retype is not a measurement. **Do not "simplify" this into typed
    numbers.**

    ``severity`` is the one exception, and deliberately: ``window_stats()`` SUGGESTS one from the
    same ``severity_for()`` the detector opens with, the form pre-selects it, and a triager may
    override it — the suggestion is recorded in the audit payload beside whatever was chosen, so the
    override is visible rather than silent.

    ``full_clean()`` runs before the save so ``TemperatureExcursion.clean()``'s belt-and-braces rules
    (the episode ordering, the future-start refusal, the snapshotted-band ordering, the
    affected-product-needs-an-action rule and the open-episode clash check) hold on this path too.
    They are NOT the concurrency guard — a form runs outside the detector's transaction and its row
    lock — and the docstring on the model says so; this is the ordinary single-user path.

    Hand-rolled means this view owes its own :func:`write_audit_log`.

    Context: ``form``, ``is_edit`` (``False``), ``computed_note`` (str — the page must explain that
    the numbers are computed from the readings in the window, not typed) and ``monitors``.
    """
    if _need_tenant(request):
        return redirect("scm:temperatureexcursion_list")

    if request.method == "POST":
        form = TemperatureExcursionWindowForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            data = form.cleaned_data
            monitor = data["monitor"]
            stats = coldchain.window_stats(monitor, data["started_at"], data["ended_at"])

            obj = TemperatureExcursion(
                tenant=request.tenant,
                monitor=monitor,
                started_at=data["started_at"],
                ended_at=data["ended_at"],
                # EVERY ONE of these comes from the service. None is typed, and none may become a
                # form field — see the module docstring.
                duration_minutes=stats["duration_minutes"],
                breach_direction=stats["breach_direction"],
                extreme_temperature=stats["extreme_temperature"],
                limit_min=stats["limit_min"],
                limit_max=stats["limit_max"],
                reading_count=stats["reading_count"],
                mkt=stats["mkt"],
                last_detected_at=stats["last_detected_at"],
                severity=data["severity"],
                cause=data.get("cause") or "",
                corrective_action=data.get("corrective_action") or "",
                notes=data.get("notes") or "",
            )
            try:
                obj.full_clean()
            except ValidationError as exc:
                # Re-keyed onto the form so the page renders the message instead of 500-ing on a
                # field this form does not carry.
                for field, errors in getattr(exc, "message_dict", {"__all__": exc.messages}).items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                obj.save()
                write_audit_log(request.user, obj, "create", {
                    "action": "manual_window",
                    "monitor": monitor.number,
                    "started_at": obj.started_at.isoformat(),
                    "ended_at": obj.ended_at.isoformat() if obj.ended_at else None,
                    "duration_minutes": obj.duration_minutes,
                    "reading_count": obj.reading_count,
                    "extreme_temperature": (str(obj.extreme_temperature)
                                            if obj.extreme_temperature is not None else None),
                    "mkt": str(obj.mkt) if obj.mkt is not None else None,
                    "severity": obj.severity,
                    # The service's own grade, beside the one that was chosen, so an override is a
                    # visible fact rather than an invisible one.
                    "severity_suggested": stats["severity"],
                })
                if not obj.reading_count:
                    messages.warning(
                        request,
                        f"{obj.number} was filed, but there are NO readings in that window on "
                        f"{monitor.number} — so the extreme temperature, the mean kinetic "
                        "temperature and the reading count are blank rather than zero. Import the "
                        "logger file for that period if you have it.")
                messages.success(request, f"{obj.number} recorded from the readings in that window.")
                return redirect("scm:temperatureexcursion_detail", pk=obj.pk)
    else:
        form = TemperatureExcursionWindowForm(tenant=request.tenant)

    return render(request, "scm/coldchain/temperatureexcursion/form.html", {
        "form": form,
        "is_edit": False,
        "computed_note": COMPUTED_NOTE,
        "monitors": _monitor_qs(request.tenant),
    })


@login_required
def temperatureexcursion_edit(request, pk):
    """Edit the TRIAGE half only — severity, cause, action, notes and the three links.

    The form is a whitelist of exactly those seven fields; every detector-written column is
    ``editable=False`` on the model, so a crafted POST naming one cannot reach ``cleaned_data``. The
    whitelist is the second lock, not the only one.

    **``assessment`` is NOT one of the seven.** This view is ``@login_required`` while
    ``temperatureexcursion_assess`` is ``@tenant_admin_required``, so a field for it here was a
    member's route to marking product released for sale — with no ``assessed_by`` / ``assessed_on``
    signature on the decision. ``TemperatureExcursion.assess()`` is the only writer of that column,
    and the form's whitelist is what makes that true.

    **Refused once the episode is CLOSED or DISMISSED.** ``EDITABLE_EXCURSION_STATUSES`` is
    ``("open", "investigating", "assessed")``: the terminal pair is where the record stops being
    rewritable, and an assessed episode is deliberately still editable so the non-conformance the
    verdict points at can be linked afterwards without reopening the release decision (which this
    form can no longer touch anyway). The refusal is a message plus a redirect to the detail page,
    not a 403 — the row is legitimately visible, it simply cannot be rewritten.

    Context: ``form``, ``obj``, ``is_edit`` (``True``), ``snapshot_note``, ``triage_note``.
    """
    obj = get_object_or_404(TemperatureExcursion.objects.select_related("monitor"),
                            pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} and its triage block can no longer "
            "be edited — the assessment on a terminal excursion IS the record, and an editable "
            "record is not one.")
        return redirect("scm:temperatureexcursion_detail", pk=pk)

    return crud_edit(request, model=TemperatureExcursion, pk=pk,
                     form_class=TemperatureExcursionForm,
                     template="scm/coldchain/temperatureexcursion/form.html",
                     success_url="scm:temperatureexcursion_list",
                     extra_context={"snapshot_note": SNAPSHOT_NOTE, "triage_note": TRIAGE_NOTE})


@tenant_admin_required
@require_POST
def temperatureexcursion_delete(request, pk):
    """Delete an excursion — refused while it is still running, and refused once it raised a repair.

    Two pre-checks, both of them about the record staying meaningful rather than about referential
    integrity:

    * **still running** (``ended_at is None``): the next detection pass would simply re-open the
      episode from the same readings, so the delete is futile — and in the meantime the board would
      show a freezer as fine while it is still warming.
    * **a maintenance work order was raised from it**: 4.13 owns that job and it outlives this row.
      Deleting the excursion would leave a repair whose stated reason points at nothing. Unlink it
      first if the job was raised in error.

    Nothing PROTECTs this table, so there is no ``ProtectedError`` to catch: the three links out are
    all ``SET_NULL`` and the monitor is on the other side of the PROTECT edge.

    Tenant-admin gated because an excursion is an evidence record. ``dismiss`` — the honest terminal
    state for a blip judged not worth acting on — is the move that keeps it.
    """
    obj = get_object_or_404(TemperatureExcursion.objects.select_related("monitor"),
                            pk=pk, tenant=request.tenant)

    if obj.ended_at is None:
        messages.error(
            request,
            f"{obj.number} is still running and cannot be deleted — the next detection pass would "
            "re-open it from the same readings. Dismiss it instead if it is not worth acting on; "
            "that keeps the record and takes it off the queue.")
        return redirect("scm:temperatureexcursion_detail", pk=pk)

    if obj.maintenance_work_order_id:
        messages.error(
            request,
            f"{obj.number} raised maintenance work order "
            f"{obj.maintenance_work_order.number} and cannot be deleted — that job is 4.13's record "
            "and its stated reason points here. Clear the link on the edit form first if the job "
            "was raised in error.")
        return redirect("scm:temperatureexcursion_detail", pk=pk)

    with transaction.atomic():
        # atomic() so the audit row `crud_delete` writes BEFORE deleting rolls back with a delete
        # that then fails.
        return crud_delete(request, model=TemperatureExcursion, pk=pk,
                           success_url="scm:temperatureexcursion_list")


@login_required
def temperatureexcursion_detail(request, pk):
    """The measured block, the human block, and the ladder — visually separated on the page.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.TemperatureExcursion`, with the monitor (and its three
      subjects), the NCR, the work order and the lot (and its item) joined. Safe to ask for
      ``status_css`` / ``severity_css`` / ``assessment_css`` / ``breach_direction_css`` /
      ``is_open`` / ``is_episode_running`` / ``is_editable`` — none of them queries.
    * **The measured half** (label it detector-written and read-only): ``duration_minutes`` (int —
      the LIVE figure while it runs, the stored one once closed), ``excess_c`` (Decimal or
      **``None``**), ``is_reportable`` (bool), ``limit_min`` / ``limit_max`` (Decimal or **``None``**
      — the SNAPSHOT; print ``snapshot_note`` beside them), and ``obj.mkt`` (Decimal or **``None``**
      — for a FROZEN monitor USP <1079.2> says MKT does not apply, so print an em dash plus
      ``frozen_mkt_note``, never 0.00). ``obj.extreme_temperature`` is likewise ``None``-able when
      the window held no readable temperature.
    * **The human half**: ``triage_note`` (str), ``assess_form``
      (:class:`TemperatureExcursionAssessForm`, unbound — it POSTs to
      ``scm:temperatureexcursion_assess``), and the three outward links off ``obj``.
    * **The ladder** — ``can_acknowledge`` / ``can_assess`` / ``can_close`` / ``can_dismiss`` /
      ``can_edit`` / ``can_delete`` / ``can_raise_work_order`` (bools). **Render only the legal next
      moves.** ``can_close`` is ``False`` while the episode is still running, which is exactly what
      :func:`_refuse_running` enforces inside the lock — offering a one-click failure is worse than
      not offering it.
    * ``work_order_blocked_reason`` — ``""`` when a repair can be raised, else the sentence saying
      why not (the monitor watches a cold room or a shipment, neither of which is a maintainable
      thing; or a job was already raised).
    * **Readings panel** — ``readings`` (a LIST inside the episode window, oldest first, capped at
      :data:`MAX_PANEL_ROWS`), ``readings_truncated`` (bool), ``panel_cap`` (int).
    * ``monitor_range_chip`` — the monitor's CURRENT ``(label, css)``, so the page can show whether
      the fridge is fine now as well as what it did then.

    All of the admin-only buttons (Assess / Close / Dismiss / Delete / Raise work order) must be
    wrapped in ``{% if request.user.is_superuser or request.user.is_tenant_admin %}``.
    """
    obj = get_object_or_404(TemperatureExcursion.objects.select_related(*_EXCURSION_SELECT),
                            pk=pk, tenant=request.tenant)
    now = timezone.now()
    monitor = obj.monitor

    # `readings()` is the model's own bounded window query (it carries the "redundant" tenant_id
    # that makes `scm_tmp_tnt_mon_idx` reachable). Capped with a SLICE so the database applies it.
    readings = list(obj.readings().select_related("recorded_by")[:MAX_PANEL_ROWS + 1])
    readings_truncated = len(readings) > MAX_PANEL_ROWS
    del readings[MAX_PANEL_ROWS:]

    latest = monitor.latest_reading()
    work_order_blocked = ""
    if obj.maintenance_work_order_id:
        work_order_blocked = (f"A repair job ({obj.maintenance_work_order.number}) has already been "
                              "raised from this excursion.")
    elif monitor.asset_id is None:
        work_order_blocked = (
            f"{monitor.number} watches "
            f"{'a cold room or zone' if monitor.location_id else 'an in-transit consignment'}, not "
            "a maintainable unit — there is no asset to raise a repair against. A reefer or chiller "
            "monitor is the one that can.")

    return render(request, "scm/coldchain/temperatureexcursion/detail.html", {
        "obj": obj,
        "duration_minutes": obj.live_duration_minutes(now),
        "excess_c": obj.excess_c(),
        "is_reportable": obj.is_reportable,
        "limit_min": obj.limit_min,
        "limit_max": obj.limit_max,
        "assess_form": TemperatureExcursionAssessForm(initial={
            "assessment": obj.assessment,
            "cause": obj.cause,
            "corrective_action": obj.corrective_action,
        }),
        "readings": readings,
        "readings_truncated": readings_truncated,
        "panel_cap": MAX_PANEL_ROWS,
        "monitor_range_chip": monitor.range_chip(latest) if latest is not None else
                              ("Not recorded", "badge-muted"),
        "can_acknowledge": obj.status in ACKNOWLEDGE_STATUSES,
        "can_assess": obj.status in ASSESS_STATUSES,
        "can_close": obj.status in CLOSE_STATUSES and obj.ended_at is not None,
        "can_dismiss": obj.status in DISMISS_STATUSES,
        "can_edit": obj.is_editable,
        "can_delete": obj.ended_at is not None and not obj.maintenance_work_order_id,
        "can_raise_work_order": not work_order_blocked,
        "work_order_blocked_reason": work_order_blocked,
        "snapshot_note": SNAPSHOT_NOTE,
        "triage_note": TRIAGE_NOTE,
        "frozen_mkt_note": FROZEN_MKT_NOTE,
    })


# =================================================================================================
# The verbs
# =================================================================================================
@login_required
@require_POST
def temperatureexcursion_acknowledge(request, pk):
    """Somebody has seen it -> ``investigating``. Takes no payload.

    ``@login_required`` rather than ``@tenant_admin_required``, deliberately: seeing something is not
    a privileged act, and gating the fastest response in the ladder behind an admin role would slow
    the one step you most want to happen immediately.

    Only from ``open``. The first acknowledger is the true one, and ``_status_transition``'s status
    re-read inside the lock is what makes that hold under a double-click.
    """
    return _transition(
        request, pk,
        from_statuses=ACKNOWLEDGE_STATUSES, to_status="investigating",
        action="acknowledge", verb="acknowledged",
        stamps={"acknowledged_by": request.user, "acknowledged_at": timezone.now()},
        message=None)


@tenant_admin_required
@require_POST
def temperatureexcursion_assess(request, pk):
    """Record the PRODUCT-LEVEL release decision -> ``assessed``. The one hand-rolled verb.

    **POST payload** (``TemperatureExcursionAssessForm``): ``assessment`` (required, from
    ``ASSESSMENT_CHOICES``), ``cause`` (optional, from ``EXCURSION_CAUSE_CHOICES``),
    ``corrective_action`` (optional text — REQUIRED for an ``product_affected`` verdict unless a
    non-conformance is already linked).

    Hand-rolled rather than ``_status_transition`` because it consumes typed input: it opens its own
    ``transaction.atomic()`` + ``select_for_update()``, then calls
    ``TemperatureExcursion.assess()`` — the **only** writer of ``assessment`` / ``assessed_by`` /
    ``assessed_on``, which re-validates every value it is handed and returns the
    ``{field: [before, after]}`` diff this view audits. Binding a second form to the instance would
    give those columns a second writer and the model's own refusals would be reachable from only one
    of the two.

    ``assessed_by`` is the acting user's ``core.Party``, resolved by :func:`_acting_party` — never a
    form field (L22). A signature somebody can choose whose name to put on it is not a signature.
    The AuditLog row records the real ``request.user`` either way, so a login with no party link
    still leaves a trail.

    ``@tenant_admin_required``: this is the release/reject decision on product.

    **This makes no Part 11 / Annex 11 claim.** Recording who assessed what and when is an audit
    TRAIL — there is no re-authentication at signing, no stated meaning of signature and no
    tamper-evident record. No label on the page may say otherwise.
    """
    form = TemperatureExcursionAssessForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return _detail(pk)

    party = _acting_party(request)
    with transaction.atomic():
        # The object is resolved BEFORE any state guard so a cross-tenant pk answers 404 rather than
        # a 302 that leaks "there is a row there, you just cannot move it" (the 4.12 finding).
        obj = get_object_or_404(TemperatureExcursion.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in ASSESS_STATUSES:
            messages.error(request, f"{obj.number} cannot be assessed — it is "
                                    f"{obj.get_status_display().lower()}.")
            return _detail(pk)
        try:
            changes = obj.assess(party, form.cleaned_data["assessment"],
                                 cause=form.cleaned_data.get("cause") or "",
                                 corrective_action=form.cleaned_data.get("corrective_action") or "")
        except ValidationError as exc:
            for message in exc.messages:
                messages.error(request, message)
            return _detail(pk)

    if not changes:
        messages.info(request, f"{obj.number} already carries that assessment — nothing changed.")
        return _detail(pk)

    # Hand-rolled save path -> it owes its own audit row.
    write_audit_log(request.user, obj, "update", {"action": "assess", **changes})
    messages.success(request, f"{obj.number} assessed as "
                              f"{obj.get_assessment_display().lower()}.")
    if obj.assessment == "product_affected" and obj.non_conformance_id is None:
        messages.info(
            request,
            "Product was judged affected. The DISPOSITION is 4.9's — raise or link a "
            "non-conformance on the edit form so the quarantine, the disposition and the cost of "
            "quality are recorded where that module owns them. 4.15 records the verdict and never "
            "writes a lot's status.")
    return _detail(pk)


@tenant_admin_required
@require_POST
def temperatureexcursion_close(request, pk):
    """Close it as dealt with -> ``closed``. Optional ``note`` in the POST body.

    **Refuses while the episode is still running**, through :func:`_refuse_running` passed as
    ``precheck`` — evaluated INSIDE the row lock, because ``ended_at`` is written by the detector
    from another transaction and a check outside the lock would answer about the state the request
    started in.

    The optional ``note`` is recorded in the AUDIT payload rather than appended to ``obj.notes``:
    ``_status_transition``'s ``stamps`` set the value of a column outright, and appending to a text
    field is a read-modify-write that would clobber a concurrent triage edit. The model's own
    ``close(user, note=…)`` appends because it holds the whole instance; this path keeps the note
    where it cannot be lost.

    Who closed it is on the AuditLog row. ``acknowledged_by`` / ``acknowledged_at`` are deliberately
    NOT stamped here — see the module docstring.
    """
    note = (request.POST.get("note") or "").strip()[:500]
    return _transition(
        request, pk,
        from_statuses=CLOSE_STATUSES, to_status="closed",
        action="close", verb="closed",
        precheck=_refuse_running,
        audit={"note": note} if note else None)


@tenant_admin_required
@require_POST
def temperatureexcursion_dismiss(request, pk):
    """Close it as NOT worth acting on -> ``dismissed``. Optional ``reason`` in the POST body.

    Kept apart from ``closed`` on purpose, and the compliance report reads them apart: "we fixed it"
    and "we judged it a non-event" are different facts, and collapsing them would make the excursion
    count meaningless. This is the honest terminal state for a blip that never outlived its grace
    period.

    Deliberately does NOT refuse a still-running episode, where ``close`` does. Dismissing says "this
    is not worth a person's time", which can be true while the breach continues — a door propped open
    during a stock take is the ordinary case. The detector keeps extending the episode either way;
    it never writes ``status``, so the judgement survives every later pass.
    """
    reason = (request.POST.get("reason") or "").strip()[:500]
    return _transition(
        request, pk,
        from_statuses=DISMISS_STATUSES, to_status="dismissed",
        action="dismiss", verb="dismissed",
        audit={"reason": reason} if reason else None)


@tenant_admin_required
@require_POST
def temperatureexcursion_raise_work_order(request, pk):
    """Raise one 4.13 repair job against the failing unit and point this excursion at it.

    The whole verb is ``coldchain.raise_work_order()``: it takes the excursion
    ``select_for_update()``, re-reads ``maintenance_work_order_id`` INSIDE the lock so a double-click
    cannot raise two jobs (the 4.13 TOCTOU fix), creates the job with an EXISTING 4.13
    ``SOURCE_CHOICES`` value and writes its own audit row. This view resolves the object, calls it
    once and messages the outcome.

    **``@tenant_admin_required`` because it writes ANOTHER SUB-MODULE'S TABLE** — the
    ``labor_board_assign`` precedent.

    Three outcomes, three different messages, and the caller can tell them apart because the existing
    link is read BEFORE the call:

    * the monitor's subject is not an ``Asset`` -> nothing is created (a cold room and a consignment
      are not maintainable things), and the page says which kind of monitor this is;
    * a job already existed -> the SAME job comes back and the message says so rather than implying a
      second one was raised;
    * otherwise the new job's number is quoted with a link into 4.13.

    **One-way link out, no reciprocal edit.** 4.13's ``SOURCE_CHOICES`` and
    ``Asset.ASSET_TYPE_CHOICES`` are both left exactly as they are — a reefer is DERIVED as "an Asset
    with an active ColdChainMonitor pointed at it", which cannot go stale the way a hand-set type
    would.
    """
    obj = get_object_or_404(
        TemperatureExcursion.objects.select_related("monitor", "monitor__asset",
                                                    "maintenance_work_order"),
        pk=pk, tenant=request.tenant)

    already = obj.maintenance_work_order_id
    work_order = coldchain.raise_work_order(obj, user=request.user)

    if work_order is None:
        monitor = obj.monitor
        watches = ("a cold room or zone" if monitor.location_id
                   else "an in-transit consignment" if monitor.shipment_id
                   else "nothing this workspace can maintain")
        messages.error(
            request,
            f"No repair job was raised: {monitor.number} watches {watches}, not a maintainable "
            "unit. Only a monitor pointed at an asset (a reefer, a chiller, a freezer) has "
            "something for a work order to be raised against.")
    elif already:
        messages.info(
            request,
            f"{work_order.number} was already raised from {obj.number} — the same job is linked, "
            "not a second one.")
    else:
        messages.success(
            request,
            f"Raised maintenance work order {work_order.number} against "
            f"{work_order.asset.code}. 4.13 owns the repair from here — approve, schedule and close "
            "it on that job.")
    return _detail(pk)


#: Printed on the create page, above the form.
COMPUTED_NOTE = (
    "Nothing measured is typed here. Choose the monitor and the window, and the extreme temperature, "
    "the duration, the breach direction, the reading count, the mean kinetic temperature and the "
    "limits in force are all computed from the readings that actually fall inside it. If the window "
    "holds no readings, those figures come back BLANK rather than zero — file the logger data first "
    "if you have it. The severity is suggested from the same rule the detector uses; override it "
    "only if you know better, and the suggestion is kept in the audit trail beside your choice."
)
