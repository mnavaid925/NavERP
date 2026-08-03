"""SCM 4.13 Asset Management — the ``MeterReading`` log: list, create and detail. Nothing else.

**THE ABSENT ROUTES ARE A DECISION, NOT AN OMISSION.** This module deliberately ships no
``meterreading_edit`` and no ``meterreading_delete``, and there is no template, no form and no url
for either. It is the ``scm.StockMove`` posture, verbatim (``InventoryManagement/StockMoves.py:1-9``,
``views/InventoryManagement/Reports.py:stock_ledger``): the ledger is append-only, so a wrong entry
is corrected by **posting a later, correct one**, exactly the way a wrong stock movement is corrected
by a compensating move and a wrong journal entry by a reversal.

Three things make that the right call rather than a missing feature:

* ``Asset.latest_reading()`` reads the NEWEST row, so a correction takes effect the moment it is
  posted — nothing has to be edited for the fix to be believed;
* the mistaken row stays visible in the history, which is the *point* of an append-only log. An
  editable meter reading is a number a scheduler already acted on, changed after the fact, with no
  trace that it ever said anything else;
* a meter-based ``MaintenancePlan`` and a ``condition`` trigger both compare a reading against a
  target. Silently rewriting the reading rewrites every due date derived from it, retroactively,
  with no audit row that says which figure the schedule was actually built on.

``admin.py`` registers the model read-only for the same reason. **If a later pass is tempted to add
an edit route here, the answer is a second reading, not a mutable first one.**

WHAT THIS MODULE OWNS BESIDES CRUD:

* ``recorded_by`` is **stamped by the view** from the request user's ``core.Party``
  (:func:`apps.scm.views._helpers._acting_party`) and is not a form field — "who took this reading"
  is an audit fact, not an input (L22, the ``ComplianceCheck.performed_by`` posture). It is stamped
  on the object returned by ``form.save(commit=False)`` and **never before ``is_valid()``**:
  ``MeterReading.clean()`` tenant-checks ``recorded_by``, and a model error keyed on a column the
  FORM does not carry raises ``ValueError`` out of ``Form.add_error`` — a 500 instead of a field
  error. The guard's ``recorded_by_id is None`` leg skips it during validation, which is exactly why
  the stamp has to come after (``forms/AssetManagement/MeterReadings.py:15-21``).
* the create page accepts ``?asset=<pk>`` and pre-fills the asset plus its declared meter
  name/unit, so the asset detail page's "Record a reading" button lands on a form that is already
  about the right machine.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so every key each
page consumes is listed here):

* ``scm/assets/meterreading/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``), plus ``assets`` (this tenant's ``Asset`` queryset for the asset dropdown),
  ``source_choices`` (pairs), ``date_from`` / ``date_to`` (the raw GET strings, echoed back into the
  two date inputs) and ``append_only_note``. Filter params are ``q`` / ``asset`` / ``source`` /
  ``date_from`` / ``date_to``; ``asset`` is a pk, so compare it with
  ``{% if request.GET.asset == a.pk|stringformat:"d" %}`` — never ``|slugify``. ``source`` is a
  string, compared directly. **The list has no Edit and no Delete action** — render View only, and
  print ``append_only_note`` on the page so the absence reads as the decision it is.
* ``scm/assets/meterreading/detail.html`` — ``obj``, ``previous`` (the prior reading on the same
  asset+meter, or ``None``), ``delta`` (this reading minus that one, ``None`` when there is no
  previous row — never 0, which would claim the meter did not move), ``superseded_by`` (the next
  reading on the same meter, or ``None``), ``is_current`` (bool — this row IS what
  ``Asset.latest_reading()`` answers with) and ``append_only_note``. **Back to List only** — no
  Edit button, no Delete form.
* ``scm/assets/meterreading/form.html`` — ``form``, ``is_edit`` (always ``False``; there is no edit
  path into this template), ``asset`` (the pre-filled ``Asset`` when ``?asset=`` resolved, else
  ``None``) and ``append_only_note``.

Badge colours come from the model's own vocabularies. theme.css ships ``badge-green`` /
``badge-red`` / ``badge-amber`` / ``badge-info`` / ``badge-muted`` / ``badge-slate`` ONLY —
``badge-success`` / ``badge-warning`` / ``badge-danger`` do not exist and render unstyled (L33).
"""
import datetime

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _acting_party, _date_window, _need_tenant

from apps.scm.forms import MeterReadingForm
from apps.scm.models import Asset, METER_SOURCE_CHOICES, MeterReading
# q4 lives in the MODELS toolkit — views/_common.py deliberately does not re-export the quantizers.
# Same import shape the 4.12 carbon report uses for q2 (ContractCompliance/Reports.py:53).
from apps.scm.models._base import ZERO, q4

#: Said once, read by all three templates, so the list, the form and the detail page cannot explain
#: the missing Edit/Delete three different ways (or, worse, two of them not at all).
APPEND_ONLY_NOTE = (
    "Meter readings are append-only. There is no edit and no delete: a wrong reading is corrected "
    "by recording a later, correct one, exactly like a compensating stock movement. The current "
    "value is always the newest row, so the correction takes effect immediately — and the mistaken "
    "reading stays in the history, which is the point of a log."
)

#: 30 rather than the app-wide 15, the ``stock_ledger`` precedent: this is a high-volume append-only
#: trail people SCAN for a trend rather than a register they page through one record at a time.
READINGS_PER_PAGE = 30


def _reading_window(qs, data):
    """Apply an optional ``?date_from=&date_to=`` window to ``read_at``, inclusively.

    ``_date_window`` (``views/_helpers.py:88``) hands its raw value straight to ``.filter()``, which
    is exactly right on the ``DateField``s every other 4.x list page uses it on. ``read_at`` is a
    ``DateTimeField``, and there a bare ``2026-08-04`` on the UPPER bound resolves to **midnight** —
    silently dropping every reading taken during the day somebody asked for, which on a page whose
    whole job is "what did this meter say on the 4th" is the answer being wrong. So the two raw
    values are widened to an inclusive AWARE datetime pair first and the shared helper still does
    the filtering, keeping one implementation of the two-bound walk.

    An explicit aware range rather than ``read_at__date__gte``: ``__date`` compiles to ``CONVERT_TZ``
    on MariaDB and returns NULL when the timezone tables are not loaded, which on XAMPP they are not
    (the 4.12 carbon-report finding).

    Junk is SKIPPED, never raised on — the same L11 posture ``_date_window`` and ``as_db_int`` take:
    a hand-edited ``?date_from=lastweek`` must narrow nothing rather than 500 on a value anybody can
    type into the address bar.
    """
    widened = {}
    for param, end_of_day in (("date_from", False), ("date_to", True)):
        raw = (data.get(param) or "").strip()
        if not raw:
            continue
        try:
            day = datetime.date.fromisoformat(raw)
        except (ValueError, TypeError):
            continue
        moment = datetime.datetime.combine(
            day, datetime.time.max if end_of_day else datetime.time.min)
        widened[param] = timezone.make_aware(moment).isoformat()
    return _date_window(qs, widened, "read_at")


def _prefill_asset(request):
    """The ``Asset`` named by ``?asset=<pk>`` on the create page, or ``None``.

    Deliberately ``.first()`` and NOT ``get_object_or_404``: this is a convenience pre-fill on a
    CREATE screen, so a stale bookmark, a junk value or another workspace's pk must land the user on
    a blank form rather than on a 404 — the form itself is the authorization boundary, and its asset
    queryset is tenant-scoped with ``MeterReading.clean()`` re-checking the chosen row behind it.
    ``as_db_int`` first (L11): ``?asset=abc``, ``?asset=²`` and a 21-digit value all skip the lookup
    rather than raising out of ``.filter()``.
    """
    pk = as_db_int(request.GET.get("asset"))
    if pk is None:
        return None
    return Asset.objects.filter(tenant=request.tenant, pk=pk).first()


def _same_meter(request, obj):
    """Every other reading of the SAME meter on the SAME asset, in this workspace.

    Keyed on ``meter_name`` and not just on the asset, because an asset legitimately carries several
    meters (hours AND temperature AND pressure). Comparing an odometer row against a bearing-temp row
    would produce a delta that means nothing at all.
    """
    return (MeterReading.objects
            .filter(tenant=request.tenant, asset_id=obj.asset_id, meter_name=obj.meter_name)
            .exclude(pk=obj.pk))


def _older_than(obj):
    """``Q`` for the rows that precede ``obj`` under ``MeterReading.Meta.ordering``.

    The ``-read_at, -id`` tie-break is copied deliberately: a bulk import can land several readings
    on the identical timestamp, and "the previous reading" has to be a single deterministic row
    rather than whichever one the database felt like returning.
    """
    return Q(read_at__lt=obj.read_at) | Q(read_at=obj.read_at, pk__lt=obj.pk)


def _newer_than(obj):
    """The mirror of :func:`_older_than` — the rows that supersede ``obj``."""
    return Q(read_at__gt=obj.read_at) | Q(read_at=obj.read_at, pk__gt=obj.pk)


# ============================================================================== the log
@login_required
def meterreading_list(request):
    """The append-only reading log: search, asset, source and an inclusive date window.

    ``select_related("asset", "recorded_by")`` covers the two FKs every row renders; without it a
    page of 30 readings is up to 60 extra queries for two columns (L18).

    The date window is applied BEFORE ``crud_list`` paginates — a filter applied afterwards would
    page over the unfiltered set and quietly show the wrong rows on page 2. ``asset`` goes through
    ``crud_list``'s ``is_int`` spec so ``?asset=abc`` / ``?asset=²`` /
    ``?asset=999999999999999999999`` all SKIP the filter instead of raising (L11).

    Search covers ``meter_name`` and ``reference`` only, per the plan: the asset is a dropdown on
    this page, so folding its code into the free-text box would make ``q`` mean two different things
    at once.
    """
    qs = (MeterReading.objects.filter(tenant=request.tenant)
          .select_related("asset", "recorded_by"))
    qs = _reading_window(qs, request.GET)

    return crud_list(
        request, qs, "scm/assets/meterreading/list.html",
        search_fields=["meter_name", "reference"],
        filters=[("asset", "asset_id", True), ("source", "source", False)],
        extra_context={
            # Every dropdown the template renders gets its data from here. A filter <select> with no
            # context is the recurring bug this rule exists to stop.
            "assets": Asset.objects.filter(tenant=request.tenant),
            "source_choices": METER_SOURCE_CHOICES,
            # Echoed back verbatim so the two date inputs keep what was typed, including a value
            # that was rejected — silently blanking it looks like the page ignored the request.
            "date_from": (request.GET.get("date_from") or "").strip(),
            "date_to": (request.GET.get("date_to") or "").strip(),
            "append_only_note": APPEND_ONLY_NOTE,
        },
        per_page=READINGS_PER_PAGE,
    )


@login_required
def meterreading_create(request):
    """Record one observation. Hand-rolled rather than ``crud_create`` — and that is the point.

    ``crud_create`` stamps the tenant and audits, but it gives no seam between ``is_valid()`` and
    ``save()``, which is exactly where ``recorded_by`` has to be written: stamping the party onto
    ``form.instance`` BEFORE validation would put a model error on a column the form does not carry,
    and ``Form.add_error`` raises ``ValueError`` on that — a 500 instead of a field error. Stamping
    it on the object ``form.save(commit=False)`` returns cannot, because
    ``MeterReading.clean()``'s ``recorded_by_id is None`` leg skips the check during validation.

    Hand-rolled means this path owes its own :func:`write_audit_log` — the ``crud_*`` helpers write
    one for you and nothing else does.

    The tenant is assigned again here even though ``MeterReadingForm.__init__`` already stamped it
    (so ``clean()``'s cross-tenant guard is live on the only path this model has). Restating it is
    deliberate: this view must not depend on a form's constructor for the column that decides which
    workspace owns the row.
    """
    if _need_tenant(request):
        return redirect("scm:meterreading_list")

    asset = _prefill_asset(request)

    if request.method == "POST":
        form = MeterReadingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            # Stamped, never posted — "who took this reading" is an audit fact (L22). None when the
            # login is not tied to a party; the AuditLog row below records the real user either way.
            obj.recorded_by = _acting_party(request)
            obj.save()
            write_audit_log(request.user, obj, "create")

            unit = f" {obj.unit}" if obj.unit else ""
            messages.success(
                request,
                f"Recorded {obj.meter_name} {obj.reading}{unit} on {obj.asset.code} at "
                f"{timezone.localtime(obj.read_at):%b %d, %Y %H:%M}.")
            # A back-dated reading is legitimate and supported, but it does NOT become the current
            # value — Asset.latest_reading() answers with the newest row. Saying so here is the
            # difference between a planner trusting the schedule and quietly wondering why it did
            # not move. One indexed EXISTS on scm_mtr_tnt_asset_idx.
            if _same_meter(request, obj).filter(_newer_than(obj)).exists():
                messages.info(
                    request,
                    f"A later {obj.meter_name} reading already exists on {obj.asset.code}, so this "
                    "one is filed in the history and does not change the current value. To correct "
                    "the current value, record a new reading dated now.")
            return redirect("scm:meterreading_detail", pk=obj.pk)
    else:
        initial = {}
        if asset is not None:
            # The asset's declared PRIMARY meter, pre-filled but fully editable: a secondary meter
            # (temperature, pressure) on the same machine is an ordinary reading, and forcing the
            # primary name here would make the secondary one impossible to file.
            initial = {"asset": asset.pk, "meter_name": asset.meter_name, "unit": asset.meter_unit}
        form = MeterReadingForm(tenant=request.tenant, initial=initial)

    return render(request, "scm/assets/meterreading/form.html", {
        "form": form,
        # Always False. There is no edit route into this template — see the module docstring.
        "is_edit": False,
        "asset": asset,
        "append_only_note": APPEND_ONLY_NOTE,
    })


@login_required
def meterreading_detail(request, pk):
    """One observation, what the meter said before it, and whether it is still the current value.

    The three derived facts are what make an append-only row readable on its own: ``previous`` gives
    the reading this one moved from, ``delta`` gives the movement, and ``superseded_by`` /
    ``is_current`` say out loud whether ``Asset.latest_reading()`` is still answering with this row.
    Without the last pair, a reader looking at a corrected mistake has no way to tell that it was
    corrected — which would make the append-only design look like a bug instead of the record it is.

    ``delta`` is ``None`` — never ``0`` — when there is no previous reading. Zero means "the meter
    did not move", which is a measurement; a blank means "there is nothing to compare against",
    which is the honest answer for the first reading of a meter (the 4.11 lesson).
    """
    obj = get_object_or_404(
        MeterReading.objects.select_related("asset", "recorded_by"),
        pk=pk, tenant=request.tenant)

    siblings = _same_meter(request, obj)
    # Two indexed probes on scm_mtr_tnt_asset_idx, not a scan of the meter's whole history.
    previous = (siblings.filter(_older_than(obj))
                .select_related("recorded_by").order_by("-read_at", "-pk").first())
    superseded_by = (siblings.filter(_newer_than(obj))
                     .select_related("recorded_by").order_by("read_at", "pk").first())

    delta = None
    if previous is not None:
        # q4 CLAMPS as well as quantizes, so a poisoned pair can only degrade this one figure
        # instead of raising out of a page that is otherwise fine.
        delta = q4(Decimal(obj.reading or ZERO) - Decimal(previous.reading or ZERO))

    return render(request, "scm/assets/meterreading/detail.html", {
        "obj": obj,
        "previous": previous,
        "delta": delta,
        "superseded_by": superseded_by,
        "is_current": superseded_by is None,
        "append_only_note": APPEND_ONLY_NOTE,
    })
