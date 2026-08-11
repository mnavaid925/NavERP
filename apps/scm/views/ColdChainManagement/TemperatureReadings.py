"""SCM 4.15 Cold Chain Management — the ``TemperatureReading`` ledger: list, create, detail, import.

**THE ABSENT EDIT AND DELETE VIEWS ARE A DECISION, NOT AN OMISSION.** This module ships no
``temperaturereading_edit`` and no ``temperaturereading_delete``, and there is no template, no form
and no url for either. It is the ``scm.StockMove`` / ``scm.MeterReading`` posture, verbatim
(``StockMoves.py:1-9``, ``AssetManagement/MeterReadings.py:1-22``): the ledger is append-only, so a
wrong reading is corrected by **filing a later, correct one**, exactly the way a wrong stock movement
is corrected by a compensating move and a wrong journal entry by a reversal.

Four things make that the right call rather than a missing feature:

* ``ColdChainMonitor.latest_reading()`` reads the NEWEST row, so a correction takes effect the moment
  it is filed — nothing has to be edited for the fix to be believed;
* the mistaken row stays visible, which is the *point* of an append-only log;
* every compliance figure in the sub-module — time in range, mean kinetic temperature, the excursion
  episodes themselves — is derived from these rows. Silently rewriting one retroactively restates all
  of them, with no audit row saying which figure the record was actually built on;
* it is the only posture that survives an ALCOA+ review, where a silently editable measurement IS the
  finding.

``admin.py`` registers the model read-only for the same reason. **If a later pass is tempted to add
an edit route here, the answer is a second reading, not a mutable first one. Do not let a review
agent "complete the CRUD".**

--------------------------------------------------------------------------------------------------
WHAT THIS MODULE STAMPS, AND WHY NONE OF IT IS A FORM FIELD
--------------------------------------------------------------------------------------------------
* ``monitor`` comes from the URL, never from the POST body. A parent pk in a POST body is how a
  caller grafts a reading onto somebody else's cold room, and this child's readings ARE that
  workspace's compliance figures.
* ``source`` and ``recorded_by`` are PROVENANCE (L20/L22) — the 4.13 ``MeterReading`` fix applied
  from the start. A member must not be able to forge a system-filed reading by POSTing
  ``source=sensor_api&recorded_by=<pk>`` onto a record that ends up in an audit pack.
* ``interval_minutes`` is SNAPSHOTTED from the monitor by the form's ``__init__`` (single row) or by
  ``TemperatureReadingImportForm.resolved_interval()`` (a batch). A weight a user can retype is not a
  snapshot, and editing the monitor's logging interval next month must not re-weight last month's
  arithmetic.

``recorded_by`` is stamped on the object ``form.save(commit=False)`` returns and **never before
``is_valid()``**: ``TemperatureReading.clean()`` tenant-checks it, and a model error keyed on a
column the FORM does not carry raises ``ValueError`` out of ``Form.add_error`` — a 500 instead of a
field error. The guard's ``recorded_by_id is None`` leg skips it during validation, which is exactly
why the stamp has to come after (``AssetManagement/MeterReadings.py:26-33``).

--------------------------------------------------------------------------------------------------
THE IMPORTER NEVER INVENTS A NUMBER
--------------------------------------------------------------------------------------------------
``q4()`` is ``min(max(Decimal(value or ZERO), -MAX_Q4), MAX_Q4)`` — and ``value or ZERO`` turns
``None`` into ``Decimal("0")``, while **0 °C is a perfectly plausible temperature**. A logger row
with a blank temperature cell would import as "the fridge was at freezing", a wrong measurement that
reads exactly like a real one. ``TemperatureReadingImportForm.parse_rows()`` therefore SKIPS AND
COUNTS every unusable row, and this view reports the tally back on the page rather than swallowing
it: a skip nobody can see is how an import quietly loses a third of a logger file. **Nothing in this
module passes a temperature through ``q2()`` or ``q4()``.**

Duplicates already in the database are filtered out BEFORE the insert — one indexed lookup over the
file's own timestamps — and ``ignore_conflicts=True`` is kept as the belt-and-braces guard for a
concurrent import racing this one. That is what ``unique_together (monitor, reading_at)`` exists for:
re-uploading the same logger file cannot double the series.
"""
from datetime import datetime, time, timedelta

from django.db import IntegrityError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _acting_party, _need_tenant, _report_day

# The service, at module scope. `apps.scm.coldchain` imports the MODEL layer and never a view module
# (its own docstring makes that a one-way rule), so there is no cycle to route around with a
# function-local import.
from apps.scm import coldchain
from apps.scm.forms import TemperatureReadingForm, TemperatureReadingImportForm
from apps.scm.models import (
    ColdChainMonitor,
    MAX_BATCH_READINGS,
    READING_SOURCE_CHOICES,
    TemperatureReading,
)
from apps.scm.views.ColdChainManagement.ColdChainMonitors import (
    APPEND_ONLY_NOTE,
    PROVENANCE_NOTE,
    _monitor_qs,
)


#: 30 rather than the app-wide 15, the ``stock_ledger`` / ``meterreading_list`` precedent: this is a
#: high-volume append-only trail people SCAN for a trend, not a register they page through one record
#: at a time.
READINGS_PER_PAGE = 30

#: The default window when the page is opened with neither a monitor nor a date. The reading table is
#: the fastest-growing one in the sub-module (~17.5k rows per monitor per year at the 30-minute
#: default), so **this page always has a window** — and it says so on the page rather than quietly
#: showing a week when somebody asked for everything.
DEFAULT_WINDOW_DAYS = 7

#: The derived band filter. NOT a column: nothing is stored on a reading about whether it was in
#: range, deliberately — that answer belongs to the monitor's limits and would go stale the moment a
#: limit was edited (``TemperatureReadings.py:66-69``).
BAND_CHOICES = [
    ("out", "Outside the monitor's limits"),
    ("in", "Inside the monitor's limits"),
]


def _aware_bounds(date_from, date_to):
    """A date pair as the inclusive AWARE datetime range covering both days end to end.

    ``reading_at`` is a ``DateTimeField`` while the two filter boxes post plain dates, so somebody
    has to widen one into the other. A bare ``2026-08-04`` on the UPPER bound resolves to MIDNIGHT
    and would silently drop every reading taken during the day somebody asked for — on a page whose
    whole job is "what did this probe say on the 4th", that is the answer being wrong.

    An explicit aware range rather than ``reading_at__date__gte``: ``__date`` compiles to
    ``CONVERT_TZ`` on MariaDB and returns NULL when the timezone tables are not loaded, which on
    XAMPP they are not (the 4.12 carbon-report finding). It also cannot use
    ``scm_tmp_tnt_read_idx`` — a function of the column is not a range on it — and this table is the
    one place in 4.15 where that matters.
    """
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
        end = timezone.make_aware(end)
    return start, end


def _band_q(bucket):
    """``Q`` for ``?band=`` — a reading against ITS OWN monitor's limits, or ``None``.

    Joined through ``monitor__min_temperature`` / ``monitor__max_temperature`` rather than compared
    against a value the view carries, because the list legitimately spans many monitors with
    different bands. Strict comparisons, matching ``coldchain.out_of_range``: a reading exactly ON
    the limit is IN range.

    Each leg carries its own ``isnull=False`` so a one-sided band is judged on the side it has and
    the expression can never evaluate to SQL NULL — which is what makes ``~out`` a clean complement.
    A monitor with NO limits at all falls into neither bucket, which is the honest answer: those rows
    cannot be in or out of a band that does not exist.
    """
    out = (Q(monitor__min_temperature__isnull=False,
             temperature__lt=F("monitor__min_temperature"))
           | Q(monitor__max_temperature__isnull=False,
               temperature__gt=F("monitor__max_temperature")))
    banded = (Q(monitor__min_temperature__isnull=False)
              | Q(monitor__max_temperature__isnull=False))
    if bucket == "out":
        return out
    if bucket == "in":
        return banded & ~out
    return None


# =================================================================================================
# The ledger
# =================================================================================================
@login_required
def temperaturereading_list(request):
    """The append-only reading log — **always windowed**, always paginated.

    **Filter GET params** (all applied BEFORE pagination; a filter applied afterwards would page over
    the unfiltered set and quietly show the wrong rows on page 2):

    * ``q`` — free text over ``notes``
    * ``monitor`` — a pk, through ``crud_list``'s ``is_int`` leg, so ``?monitor=abc``, ``?monitor=²``
      and ``?monitor=999999999999999999999`` all SKIP the filter rather than raising (L11)
    * ``source`` — ``READING_SOURCE_CHOICES`` (string)
    * ``date_from`` / ``date_to`` — ``YYYY-MM-DD``, inclusive of both days, on ``reading_at``
    * ``band`` — ``in`` / ``out``, DERIVED against each row's own monitor limits

    **The page is ALWAYS bounded.** Opened with no usable date it defaults to the last
    :data:`DEFAULT_WINDOW_DAYS` days and sets ``window_defaulted`` so the page can SAY so — a silent
    default is indistinguishable from a page that ignored what was asked. ``?monitor=`` does NOT
    exempt a page from the window: narrowing to one probe narrows the rows but does not bound them,
    and a single 15-minute sensor is the fastest-growing thing in this table.

    **Context:** ``object_list`` / ``page_obj`` / ``q`` (from ``crud_list``), plus ``monitors``
    (queryset for the monitor dropdown), ``source_choices`` and ``band_choices`` (lists of
    ``(value, label)`` pairs), ``band`` (the RESOLVED bucket — a junk value narrowed nothing, so the
    ``<select>`` must show "All"), ``date_from`` / ``date_to`` (the raw GET strings, echoed back into
    the two date inputs so a rejected value stays visible), ``window_from`` / ``window_to`` (the
    resolved dates actually applied; either may be ``None`` when only ONE end was given),
    ``window_defaulted`` (bool), ``window_days`` (int) and ``append_only_note`` (str).

    **The list has NO Edit and NO Delete action** — render View only, and print
    ``append_only_note`` on the page so the absence reads as the decision it is.

    ``select_related("monitor", "recorded_by")`` covers the two FKs every row renders; without it a
    page of 30 readings is up to 60 extra queries for two columns (L18).
    """
    qs = (TemperatureReading.objects.filter(tenant=request.tenant)
          .select_related("monitor", "recorded_by"))

    raw_from = (request.GET.get("date_from") or "").strip()
    raw_to = (request.GET.get("date_to") or "").strip()
    date_from, date_to = _report_day(raw_from), _report_day(raw_to)

    # The bound. A page with no usable date gets the default window rather than a walk of the whole
    # history — and that applies to `?monitor=<pk>` too, which was the ONE direction that actually
    # grows: a probe on a 15-minute interval is ~35k rows a year, so `?monitor=7&page=3000` had the
    # database counting off a huge OFFSET for a URL anybody can type. The monitor filter narrows the
    # rows; it does not bound them. `window_defaulted` still tells the page to SAY it defaulted.
    window_defaulted = False
    if date_from is None and date_to is None:
        today = timezone.localdate()
        date_from, date_to = today - timedelta(days=DEFAULT_WINDOW_DAYS - 1), today
        window_defaulted = True
    if date_from is not None and date_to is not None and date_from > date_to:
        # A `from` after a `to` is a typo, not an empty result.
        date_from, date_to = date_to, date_from
    if date_from is not None:
        start, _ = _aware_bounds(date_from, date_from)
        qs = qs.filter(reading_at__gte=start)
    if date_to is not None:
        _, end = _aware_bounds(date_to, date_to)
        qs = qs.filter(reading_at__lte=end)

    band = (request.GET.get("band") or "").strip()
    condition = _band_q(band)
    if condition is not None:
        qs = qs.filter(condition)
    else:
        band = ""  # junk narrowed nothing; the <select> must show "All"

    return crud_list(
        request, qs, "scm/coldchain/temperaturereading/list.html",
        search_fields=["notes"],
        filters=[("monitor", "monitor_id", True), ("source", "source", False)],
        extra_context={
            "monitors": _monitor_qs(request.tenant),
            "source_choices": READING_SOURCE_CHOICES,
            "band_choices": BAND_CHOICES,
            "band": band,
            # Echoed VERBATIM so the two date inputs keep what was typed, including a value that was
            # rejected — silently blanking it looks like the page ignored the request.
            "date_from": raw_from,
            "date_to": raw_to,
            "window_from": date_from,
            "window_to": date_to,
            "window_defaulted": window_defaulted,
            "window_days": DEFAULT_WINDOW_DAYS,
            "append_only_note": APPEND_ONLY_NOTE,
        },
        per_page=READINGS_PER_PAGE,
    )


@login_required
def temperaturereading_detail(request, pk):
    """One interval summary, what it was judged against, and whether it is still the current value.

    Scoped on ``tenant`` **and** ``monitor__tenant``. The two cannot disagree today —
    ``TemperatureReading.clean()`` refuses a cross-tenant parent — but a child fetched by its own pk
    alone is exactly the lookup that stops being safe the day somebody adds a second write path, and
    stating both costs nothing.

    Context:

    * ``obj`` — the reading, with ``monitor`` (and its three subjects) and ``recorded_by`` joined.
    * ``breach`` — ``""`` / ``"high"`` / ``"low"`` from ``coldchain.out_of_range``, judged against
      the monitor's CURRENT limits. ``""`` also means "this monitor has no limits", which the page
      must render as "no band configured" rather than as "in range".
    * ``limit_min`` / ``limit_max`` — Decimal or **``None``** (a one-sided band is legitimate; render
      "no lower limit", never 0).
    * ``previous`` / ``superseded_by`` — the neighbouring readings on the SAME monitor, or ``None``.
    * ``delta`` — this temperature minus the previous one, or **``None``** when there is no previous
      row. Never 0: zero means "the probe did not move", which is a measurement; blank means "there
      is nothing to compare against", which is the honest answer for a monitor's first reading.
    * ``is_current`` — bool; ``True`` when this row IS what ``ColdChainMonitor.latest_reading()``
      answers with.
    * ``episode`` — the ``TemperatureExcursion`` whose window contains this reading, or ``None``.
    * ``provenance_note`` / ``append_only_note`` — strs.

    **Actions sidebar: Back to List only** — no Edit button, no Delete form.

    The delta is computed with plain ``Decimal`` subtraction and ``.quantize()``, **never through
    ``q4()``**: that helper's ``value or ZERO`` would turn a missing neighbour into 0 °C, which is
    the whole trap this sub-module is built around.
    """
    obj = get_object_or_404(
        TemperatureReading.objects.select_related(
            "monitor", "monitor__location", "monitor__asset", "monitor__shipment", "recorded_by"),
        pk=pk, tenant=request.tenant, monitor__tenant=request.tenant)

    monitor = obj.monitor
    limit_min, limit_max = monitor.effective_limits()

    # The `-reading_at, -id` tie-break is copied from `TemperatureReading.Meta.ordering`
    # deliberately: a bulk import can land several rows on one timestamp, and "the previous reading"
    # has to be a single deterministic row rather than whichever one the database felt like
    # returning. Two indexed probes on `scm_tmp_tnt_mon_idx`, not a scan of the whole history.
    siblings = (TemperatureReading.objects
                .filter(tenant=request.tenant, monitor_id=obj.monitor_id)
                .exclude(pk=obj.pk))
    older = Q(reading_at__lt=obj.reading_at) | Q(reading_at=obj.reading_at, pk__lt=obj.pk)
    newer = Q(reading_at__gt=obj.reading_at) | Q(reading_at=obj.reading_at, pk__gt=obj.pk)
    previous = siblings.filter(older).order_by("-reading_at", "-pk").first()
    superseded_by = siblings.filter(newer).order_by("reading_at", "pk").first()

    delta = None
    if previous is not None and previous.temperature is not None and obj.temperature is not None:
        delta = (obj.temperature - previous.temperature).quantize(Decimal("0.01"))

    episode = (monitor.excursions
               .filter(tenant=request.tenant, started_at__lte=obj.reading_at)
               .filter(Q(ended_at__isnull=True) | Q(ended_at__gte=obj.reading_at))
               .order_by("-started_at").first())

    return render(request, "scm/coldchain/temperaturereading/detail.html", {
        "obj": obj,
        "breach": coldchain.out_of_range(obj.temperature, limit_min, limit_max),
        "limit_min": limit_min,
        "limit_max": limit_max,
        "previous": previous,
        "superseded_by": superseded_by,
        "delta": delta,
        "is_current": superseded_by is None,
        "episode": episode,
        "provenance_note": PROVENANCE_NOTE,
        "append_only_note": APPEND_ONLY_NOTE,
    })


# =================================================================================================
# Filing a reading — one by hand, or a logger file
# =================================================================================================
@login_required
def coldchainmonitor_add_reading(request, pk):
    """File ONE interval summary against the monitor named by the ROUTE.

    Hand-rolled rather than ``crud_create``, and that is the point. ``crud_create`` stamps the tenant
    and audits, but it gives no seam between ``is_valid()`` and ``save()`` — which is exactly where
    ``recorded_by`` has to be written (see the module docstring), and it cannot pass ``monitor=`` into
    the form's constructor either. Hand-rolled means this path owes its own
    :func:`write_audit_log`; the ``crud_*`` helpers write one for you and nothing else does.

    The tenant is assigned again here even though ``TemperatureReadingForm.__init__`` already stamped
    it. Restating it is deliberate: this view must not depend on a form's constructor for the column
    that decides which workspace owns the row.

    ``unique_together (monitor, reading_at)`` is the idempotence guard for the importer, and it can
    fire here too when somebody re-types a timestamp that already exists. That is caught and rendered
    as a field error rather than a 500 — a duplicate is a thing the user can fix, not a crash.

    Context: ``form``, ``is_edit`` (**always ``False``** — there is no edit path into this template),
    ``monitor`` (the parent from the route), ``interval_minutes`` (int — the weight that will be
    snapshotted onto the row), ``provenance_note`` and ``append_only_note``.
    """
    if _need_tenant(request):
        return redirect("scm:coldchainmonitor_list")
    monitor = get_object_or_404(
        ColdChainMonitor.objects.select_related("location", "asset", "shipment"),
        pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = TemperatureReadingForm(request.POST, tenant=request.tenant, monitor=monitor)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.monitor = monitor
            # SNAPSHOTTED, never typed. The form's __init__ already did this; restating it keeps the
            # weight independent of a constructor a future refactor could change.
            obj.interval_minutes = monitor.logging_interval_minutes
            # Stamped, never posted (L20/L22). `manual` is the only honest source for a typed row —
            # `logger_import` and `gateway` belong to the importer and `sensor_api` is written by
            # nothing this pass.
            obj.source = "manual"
            obj.recorded_by = _acting_party(request)
            try:
                obj.save()
            except IntegrityError:
                form.add_error(None, "A reading already exists on this monitor at that exact "
                                     "timestamp. The ledger allows one interval summary per moment "
                                     "per monitor — change the timestamp, or file the correction at "
                                     "the next interval.")
            else:
                write_audit_log(request.user, obj, "create", {
                    "monitor": monitor.number,
                    "reading_at": obj.reading_at.isoformat(),
                    "temperature": str(obj.temperature),
                    "source": obj.source,
                    "interval_minutes": obj.interval_minutes,
                })
                messages.success(
                    request,
                    f"Filed {obj.temperature} °C on {monitor.number} at "
                    f"{timezone.localtime(obj.reading_at):%b %d, %Y %H:%M}.")
                # Back-dating is legitimate and supported — that is what a logger download IS — but
                # it does NOT become the current value, and saying so is the difference between
                # somebody trusting the chip and quietly wondering why it did not move.
                if (TemperatureReading.objects
                        .filter(tenant=request.tenant, monitor_id=monitor.pk)
                        .filter(Q(reading_at__gt=obj.reading_at)
                                | Q(reading_at=obj.reading_at, pk__gt=obj.pk))
                        .exists()):
                    messages.info(
                        request,
                        "A later reading already exists on this monitor, so this one is filed in "
                        "the history and does not change the current value. Run Detect on the "
                        "monitor if this row should be considered for an excursion.")
                return redirect("scm:temperaturereading_detail", pk=obj.pk)
    else:
        form = TemperatureReadingForm(tenant=request.tenant, monitor=monitor)

    return render(request, "scm/coldchain/temperaturereading/form.html", {
        "form": form,
        # Always False. There is no edit route into this template — see the module docstring.
        "is_edit": False,
        "monitor": monitor,
        "interval_minutes": monitor.logging_interval_minutes,
        "provenance_note": PROVENANCE_NOTE,
        "append_only_note": APPEND_ONLY_NOTE,
    })


@tenant_admin_required
def coldchainmonitor_import_readings(request, pk):
    """Import a logger / gateway CSV against the monitor named by the ROUTE.

    ``@tenant_admin_required`` because one press writes up to :data:`~apps.scm.models.
    MAX_BATCH_READINGS` rows into the record a regulator reads, and because the batch carries a
    provenance (``logger_import`` / ``gateway``) that says the system filed it.

    **Bounded three times over before a single row is written**: the extension and
    ``MAX_UPLOAD_BYTES`` checks, and a data-row count measured on the RAW BYTES — before any value is
    parsed — against ``MAX_BATCH_READINGS`` (all three in ``TemperatureReadingImportForm``), plus the
    duplicate pre-filter here. An unbounded upload is an unbounded ``bulk_create`` any member could
    otherwise fire, and counting after the first query has already lost.

    **Nothing is invented.** The form skips and COUNTS every row it cannot read; this view reports
    that tally back verbatim, alongside the rows already in the database, so "5,000 rows in, 300
    filed" is never a silent outcome.

    On success the page RE-RENDERS with a result panel rather than redirecting: the tally is the
    output of the action, and a redirect would throw it away in the one place somebody needs it.

    Context: ``form``, ``monitor``, ``max_rows`` (int), ``interval_minutes`` (int — the monitor's own
    weight, which the optional override replaces), ``result`` (**``None`` before an import**, else a
    dict: ``imported`` (int), ``duplicates`` (int — already in the ledger), ``skipped`` (the form's
    tally dict: ``total`` / ``no_temperature`` / ``bad_timestamp`` / ``future`` / ``out_of_bounds`` /
    ``before_deployment`` / ``duplicate_in_file`` / ``dropped_humidity`` /
    ``dropped_interval_stats``), ``parsed`` (int),
    ``source`` (str — the raw token that was stamped), ``source_label`` (str — that token's own
    human label, resolved off the form field's choices so the panel never prints ``logger_import``)
    and ``interval_minutes`` (int — what was actually snapshotted)),
    ``zero_note`` (str — a blank temperature cell is reported as SKIPPED and never imported as 0),
    ``provenance_note`` and ``append_only_note``.
    """
    monitor = get_object_or_404(
        ColdChainMonitor.objects.select_related("location", "asset", "shipment"),
        pk=pk, tenant=request.tenant)

    result = None
    if request.method == "POST":
        form = TemperatureReadingImportForm(request.POST, request.FILES,
                                            tenant=request.tenant, monitor=monitor)
        rows = skipped = None
        if form.is_valid():
            try:
                rows, skipped = form.parse_rows()
            except ValidationError as exc:
                # The walk itself can still refuse the file: `csv` is a C reader with its own
                # refusals (an embedded NUL byte, a field past its 128 KB limit) and they surface
                # mid-walk, after `clean_file` has already passed the header. Caught here it is a
                # message on the field, exactly like the size and extension refusals; uncaught it is
                # a 500 on a page any member can post to.
                form.add_error("file", exc)
        # `rows` is `[]` for a header-only file — a legitimate import of nothing, which still gets
        # its tally — and `None` only when there is nothing to import at all.
        if rows is not None:
            interval = form.resolved_interval(monitor)
            source = form.cleaned_data["source"]
            # The result panel reports the provenance it stamped, and `logger_import` is a database
            # token, not a sentence — printed raw it read as an internal identifier leaking onto a
            # page an auditor uses. Resolved off the FIELD'S OWN choices rather than a second copy of
            # the mapping, so the label can never drift from the whitelist that produced the value.
            source_label = dict(form.fields["source"].choices).get(source, source)
            party = _acting_party(request)

            moments = [row["reading_at"] for row in rows]
            # ONE indexed lookup over the file's own timestamps, bounded by MAX_BATCH_READINGS. This
            # is what makes a re-uploaded logger file a no-op with an honest COUNT rather than a
            # silent `ignore_conflicts` swallow — the tally is the whole product of this page.
            existing = set()
            if moments:
                existing = set(TemperatureReading.objects
                               .filter(tenant=request.tenant, monitor_id=monitor.pk,
                                       reading_at__in=moments)
                               .values_list("reading_at", flat=True))

            fresh = [row for row in rows if row["reading_at"] not in existing]
            objects = [TemperatureReading(
                tenant=request.tenant, monitor=monitor,
                interval_minutes=interval, source=source, recorded_by=party, **row)
                for row in fresh]

            with transaction.atomic():
                # `ignore_conflicts` is belt and braces for a concurrent import racing this one:
                # the pre-filter above already removed everything this transaction can see, and
                # `unique_together (monitor, reading_at)` is what makes the race harmless instead of
                # an IntegrityError that fails all 5,000 rows over one.
                TemperatureReading.objects.bulk_create(objects, ignore_conflicts=True)

            # Hand-rolled save path -> it owes its own audit row. Written against the MONITOR: the
            # batch is one act on one deployment, and 5,000 rows of audit for one button press is a
            # trail nobody can read.
            write_audit_log(request.user, monitor, "update", {
                "action": "import_readings",
                "imported": len(objects),
                "duplicates_in_ledger": len(rows) - len(fresh),
                "skipped": skipped["total"],
                "source": source,
                "interval_minutes": interval,
            })

            result = {
                "imported": len(objects),
                "duplicates": len(rows) - len(fresh),
                "skipped": skipped,
                "parsed": len(rows),
                "source": source,
                "source_label": source_label,
                "interval_minutes": interval,
            }
            messages.success(
                request,
                f"Imported {len(objects)} reading(s) onto {monitor.number}. "
                f"{result['duplicates']} were already in the ledger and {skipped['total']} could "
                "not be read.")
            if skipped["no_temperature"]:
                messages.warning(
                    request,
                    f"{skipped['no_temperature']} row(s) had no readable temperature and were "
                    "SKIPPED — never filed as 0 °C, which would read as a measurement somebody "
                    "took. Fix those rows and re-upload; the ones already imported will not double.")
            if skipped["before_deployment"]:
                # Named separately from the rest of the tally because it is the one skip that is
                # usually CORRECT and still needs saying: a re-usable logger's file holds every
                # consignment it has ever ridden, and those rows belong to the earlier deployment.
                messages.warning(
                    request,
                    f"{skipped['before_deployment']} row(s) predate {monitor.number}'s deployment "
                    f"on {monitor.deployed_on} and were SKIPPED — a re-usable logger carries its "
                    "earlier consignments too, and filing them here would count another shipment's "
                    "journey in this deployment's time-in-range and MKT.")
            # A fresh unbound form beside the result panel, so the page is immediately usable again.
            form = TemperatureReadingImportForm(tenant=request.tenant, monitor=monitor)
    else:
        form = TemperatureReadingImportForm(tenant=request.tenant, monitor=monitor)

    return render(request, "scm/coldchain/temperaturereading/import.html", {
        "form": form,
        "monitor": monitor,
        "max_rows": MAX_BATCH_READINGS,
        "interval_minutes": monitor.logging_interval_minutes,
        "result": result,
        "zero_note": ZERO_TEMPERATURE_NOTE,
        "provenance_note": PROVENANCE_NOTE,
        "append_only_note": APPEND_ONLY_NOTE,
    })


#: Printed on the import page, ABOVE the button. The single most important thing a reader of this
#: screen has to understand about what it will and will not do with a half-empty file.
ZERO_TEMPERATURE_NOTE = (
    "A row whose temperature cell is blank or unreadable is SKIPPED and counted — it is never "
    "imported as 0 °C. Zero is a perfectly plausible temperature, so a substituted zero would file "
    "'the fridge was at freezing' as a measurement nobody took, which is the worst thing that can "
    "happen to a record that ends up in an audit pack. Out-of-range humidity and interval statistics "
    "that do not bracket the reading are dropped from the row while the temperature is kept."
)
