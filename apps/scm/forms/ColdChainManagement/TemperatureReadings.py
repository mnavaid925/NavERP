"""SCM 4.15 Cold Chain Management — the ``TemperatureReading`` create form and the logger importer.

``TemperatureReading`` is append-only, the ``scm.StockMove`` / ``scm.MeterReading`` posture: list,
create, detail and import, with **NO edit form and NO delete form**. A wrong reading is corrected by
posting a later, correct one; the mistaken row stays visible, which is the point of an append-only
log rather than a defect in it, and it is the only posture that survives an ALCOA+ review where a
silently editable measurement IS the finding. **This is a documented CRUD exception. Do not let a
review agent "complete the CRUD" here.**

**``monitor`` is NOT a field — it comes from the URL.** A parent pk in a POST body is how a caller
grafts a reading onto somebody else's cold room, and this child's compliance figures are the whole
product (the ``AssetSparePart.asset`` / ``ComplianceCheck.requirement`` posture). The form takes it
as a ``monitor=`` keyword instead, and stamps it onto the instance BEFORE validation — which is what
makes ``TemperatureReading.clean()``'s no-predate-``deployed_on`` rule actually run, since that rule
reads through the pointer.

**``interval_minutes`` is snapshotted onto the row here, from the monitor, at construction.** That is
Decision B: editing the monitor's logging interval next month must not retroactively re-weight last
month's MKT or its time-out-of-range. Stamping it in ``__init__`` rather than leaving it to the view
is deliberate — a forgotten stamp does not fail, it silently files every row at the model default of
30 minutes, and nothing downstream would ever say so. Same rule as
``LaborActivity.standard_minutes_snapshot`` and ``CycleCountTaskLine.expected_quantity``.

**``source`` and ``recorded_by`` are PROVENANCE and are stamped by whichever verb files the row**
(L20/L22) — the 4.13 ``MeterReading`` fix applied from the start. A member must not be able to forge
a system-filed reading by POSTing ``source=sensor_api&recorded_by=<pk>`` onto a record that ends up
in an audit pack: a provenance a user can choose is not a provenance. The view stamps ``recorded_by``
AFTER ``is_valid()``, on the object returned by ``save(commit=False)``, for the reason
``MeterReadings.py:15-21`` gives.

--------------------------------------------------------------------------------------------------
THE IMPORTER NEVER INVENTS A NUMBER — A BLANK TEMPERATURE CELL IS SKIPPED AND COUNTED
--------------------------------------------------------------------------------------------------
``q4()`` is ``min(max(Decimal(value or ZERO), -MAX_Q4), MAX_Q4)``. The *sign* survives the clamp, so
at a glance it looks safe for a signed column. It is not: **``value or ZERO`` turns ``None`` into
``Decimal("0")``, and 0 °C is a perfectly plausible temperature.** A logger row with a blank
temperature cell would import as "the fridge was at freezing" — a wrong measurement that reads
exactly like a real one, which is the worst possible failure mode for an audit record. So
:meth:`TemperatureReadingImportForm.parse_rows` **skips and counts** every unusable row and reports
the tally back, and **nothing in this module passes a temperature through ``q2()`` or ``q4()``.**

The importer is bounded three times over before it touches the database: the extension allowlist and
``MAX_UPLOAD_BYTES`` from ``apps/core/forms/_common.py``, and a data-row count measured on the RAW
BYTES — before a single value is parsed — against ``MAX_BATCH_READINGS``. Counting after the first
query has already lost (the ``MAX_BULK_ASSIGN`` precedent).
"""
import csv
import io
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.core.forms import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms.ColdChainManagement.ColdChainMonitors import _ModelErrorSafe

from apps.scm.models import (
    MAX_BATCH_READINGS,
    MAX_HUMIDITY_PCT,
    MAX_LOGGING_INTERVAL_MINUTES,
    MAX_SAMPLE_COUNT,
    MAX_TEMPERATURE_C,
    MIN_HUMIDITY_PCT,
    MIN_LOGGING_INTERVAL_MINUTES,
    MIN_TEMPERATURE_C,
    TemperatureReading,
)


#: The two sources a FILE may claim. ``manual`` is what a typed row gets and ``sensor_api`` is the
#: declared ingestion seam that NOTHING writes this pass — offering either here would let an upload
#: wear a provenance it does not have.
IMPORT_SOURCE_CHOICES = [
    ("logger_import", "Logger file import"),
    ("gateway", "Gateway batch"),
]

#: Column headers this importer understands, per target field. Aliases rather than one rigid spelling
#: because every logger vendor names these differently and the alternative is a support ticket per
#: brand: ELPRO exports ``Date/Time``, Sensitech ``Timestamp``, a gateway batch ``datetime``. Matched
#: case-insensitively with punctuation stripped, so ``Temperature (°C)`` finds ``temperature``.
COLUMN_ALIASES = {
    "reading_at": ("reading_at", "readingat", "timestamp", "datetime", "date_time", "date", "time",
                   "recorded_at", "measured_at"),
    "temperature": ("temperature", "temp", "temp_c", "temperature_c", "celsius", "value", "reading"),
    "humidity_pct": ("humidity_pct", "humidity", "rh", "relative_humidity", "humidity_percent"),
    "min_temperature": ("min_temperature", "min_temp", "minimum", "min", "temp_min"),
    "max_temperature": ("max_temperature", "max_temp", "maximum", "max", "temp_max"),
    "sample_count": ("sample_count", "samples", "n", "count"),
    "notes": ("notes", "note", "comment", "remarks"),
}

#: Without these two a row is not a reading at all, so their absence is a FILE error rather than a
#: per-row skip: a header that names neither means the wrong file was uploaded, and importing 5000
#: blank rows to discover that is not a diagnosis.
REQUIRED_COLUMNS = ("reading_at", "temperature")

#: What a malformed CSV is told. Stated once because BOTH readers below refuse with it — the header
#: map and the row walk — and two spellings of the same refusal is two support tickets.
UNREADABLE_CSV = "That file is not readable as CSV — re-export it from the logger software."


def _records(text):
    """Yield every record of ``text``, with ``_csv.Error`` turned into a form refusal.

    ``csv`` is a C reader carrying refusals of its own — an embedded NUL byte, a field past its
    128 KB limit — and every one of them surfaces as ``_csv.Error`` **from the iterator**, not from
    the reader's construction. A bare ``for record in reader`` therefore 500s the upload page
    halfway through a walk on a crafted file, which is a stack trace where the rest of this importer
    would have given a sentence. ``ValidationError`` keeps a bad file a statement about the file.
    """
    reader = csv.reader(io.StringIO(text))
    while True:
        try:
            record = next(reader)
        except StopIteration:
            return
        except csv.Error:
            raise ValidationError(UNREADABLE_CSV) from None
        yield record


# -------------------------------------------------------------------------------------------------
# Cell readers — pure, and every one of them answers None rather than a plausible-looking number
# -------------------------------------------------------------------------------------------------

def _normalise_header(raw):
    """``"Temperature (°C)"`` -> ``"temperature_c"`` — lower-cased, punctuation collapsed."""
    kept = [char.lower() if char.isalnum() else "_" for char in (raw or "").strip()]
    return "_".join(part for part in "".join(kept).split("_") if part)


def _cell(record, columns, name):
    """One cell of one CSV row by TARGET FIELD name, or ``""``.

    A short row is a fact of life in exported logger files (trailing optional columns simply stop
    being written), so a column index past the end of this row answers ``""`` rather than raising
    ``IndexError`` and taking the whole upload down with it.
    """
    index = columns.get(name)
    if index is None or index >= len(record):
        return ""
    return record[index] or ""


def _parse_decimal(raw):
    """A ``Decimal`` or ``None``. **A blank or unreadable cell is ``None``, never ``0``.**

    Accepts a comma decimal separator (every European logger export uses one) and strips a trailing
    unit, so ``-18,50 °C`` reads as ``-18.50``. It does NOT accept a thousands separator: no
    temperature, humidity or sample count in this sub-module is ever four digits, and guessing
    between the two comma meanings is how an importer invents a number.
    """
    text = (raw or "").strip()
    if not text:
        return None
    for suffix in ("°c", "°f", "c", "f", "%", "degc"):
        if text.lower().endswith(suffix):
            text = text[:-len(suffix)].strip()
            break
    text = text.replace(",", ".")
    try:
        value = Decimal(text)
    except (ArithmeticError, ValueError, TypeError):
        return None
    # `Decimal("nan")` and `Decimal("sNaN")` PARSE CLEANLY and then raise `InvalidOperation` on the
    # first ordering comparison — so a crafted cell reading `nan` would sail past this function and
    # 500 the whole upload at the bounds check, taking the other 4,999 rows with it. Answering
    # `None` drops it into the existing skip counters instead, which is what every other unreadable
    # cell already gets. `Infinity` compares fine and is skipped as out-of-bounds on its own;
    # NaN is the only gap, and `is_finite()` closes both at once.
    if not value.is_finite():
        return None
    return value


def _parse_int(raw):
    """A positive ``int`` or ``None`` — the sibling of :func:`_parse_decimal` for a count."""
    value = _parse_decimal(raw)
    if value is None:
        return None
    try:
        return int(value)
    except (ArithmeticError, ValueError, TypeError):
        return None


def _parse_moment(raw):
    """An AWARE ``datetime`` or ``None``.

    ``parse_datetime`` first (it eats ISO-8601 including an offset), then ``parse_date`` for a
    date-only cell — a daily logger summary is a legitimate row and refusing it would push somebody
    into hand-editing the file. A naive value is made aware in the CURRENT timezone, which is the
    only honest reading of a logger export that carries no offset: the device was in the workspace's
    world, not in UTC.

    ``make_aware`` raises on a moment that does not exist or is ambiguous in the local zone (the two
    daylight-saving hours). That is a per-row problem, so it answers ``None`` and the row is skipped
    and counted rather than failing the whole upload.
    """
    text = (raw or "").strip()
    if not text:
        return None
    moment = None
    try:
        moment = parse_datetime(text)
        if moment is None:
            day = parse_date(text)
            if day is not None:
                moment = datetime.combine(day, datetime.min.time())
    except ValueError:
        return None
    if moment is None:
        return None
    if timezone.is_naive(moment):
        try:
            moment = timezone.make_aware(moment, timezone.get_current_timezone())
        except Exception:  # noqa: BLE001 - AmbiguousTimeError / NonExistentTimeError, per-row
            return None
    return moment


class TemperatureReadingForm(_ModelErrorSafe, TenantModelForm):
    """One interval summary, typed by a human. **Create only** — see the module docstring.

    ``_ModelErrorSafe`` is mixed in FIRST so a model error keyed on ``monitor`` (a name this form
    deliberately does not carry) renders as a form-level message instead of raising ``ValueError``
    out of ``Form.add_error``. That leg is unreachable on the normal path — the view resolves the
    monitor with ``get_object_or_404(..., tenant=request.tenant)`` before handing it over — and the
    mixin is what keeps "unreachable" from meaning "a 500 the day it stops being".
    """

    class Meta:
        model = TemperatureReading
        # A WHITELIST, never `Meta.exclude`. A whitelist fails CLOSED when a column is added later;
        # an exclude list fails open, and the column it would silently admit here is the next
        # provenance stamp somebody adds.
        #
        # Deliberately ABSENT, and why: `monitor` (it comes from the URL — see the module docstring);
        # `interval_minutes` (snapshotted from the monitor in __init__ — a weight a user can type is
        # not a snapshot); `source` and `recorded_by` (provenance, `editable=False`, stamped by the
        # filing verb); `tenant` (stamped by `crud_create`, and in __init__ below so the model's
        # guards can read it); `created_at` / `updated_at`. `TemperatureReading` is `TenantOwned` and
        # carries no `number` — a reading is a data point in a series, not a document anybody quotes.
        fields = ["reading_at", "temperature", "humidity_pct",
                  "min_temperature", "max_temperature", "sample_count", "notes"]

    def __init__(self, *args, monitor=None, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. `crud_create` assigns the tenant only AFTER `is_valid()`, so without this an
        # unsaved reading reaches `TemperatureReading.clean()` with `tenant_id` None — the exact case
        # its cross-tenant guard skips — and the guard would be dead code on the create path, which
        # is the only path this model has.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # THE PARENT, from the ROUTE. Assigned before validation because two of the model's four
        # rules read through it: the cross-tenant guard and the no-predate-`deployed_on` rule, the
        # latter being what stops a re-usable logger's earlier consignment being filed against this
        # deployment.
        self.monitor = monitor
        if monitor is not None and self.instance.monitor_id is None:
            self.instance.monitor = monitor

        # THE WEIGHT, snapshotted. See the module docstring — a forgotten stamp does not fail, it
        # silently files every row at the model default and no report would ever say so.
        if monitor is not None and self.instance.pk is None:
            self.instance.interval_minutes = monitor.logging_interval_minutes

        # `reading_at` gets its `datetime-local` widget from `TenantModelForm.__init__`, which
        # REPLACES the widget of every DateTimeField after Meta.widgets have been applied — so a
        # Meta declaration for it would be silently discarded and there is deliberately none. The
        # base sets the matching `format`/`input_formats` pair, which is the half 4.8's
        # `ProductionTimeLogForm` was missing (a stored value renders as an EMPTY box without it).

    def clean(self):
        """Re-check the ROUTE's monitor against this workspace, at the form boundary.

        There is no ``_reject_foreign`` call here and that is not an omission: that helper keys its
        error on a FIELD, and ``monitor`` is deliberately not one. The check is the same one, keyed
        on the form itself so it renders — a reading hung off another workspace's monitor would
        drive that workspace's compliance figures, and the route is the only thing standing between
        a crafted POST and that outcome.

        Everything else — the future-date refusal, the interval-statistics bracket and the
        no-predate-``deployed_on`` rule — stays in ``TemperatureReading.clean()``, once, where it
        also holds against the importer, a management command and a shell.
        """
        cleaned = super().clean()
        monitor = self.instance.monitor if self.instance.monitor_id else None
        tenant_id = self.tenant.pk if self.tenant is not None else None
        if monitor is not None and monitor.tenant_id != tenant_id:
            self.add_error(None, "That monitor belongs to another workspace.")
        return cleaned


class TemperatureReadingImportForm(forms.Form):
    """A logger / gateway CSV, validated and bounded BEFORE anything is parsed or written.

    Expected columns (case-insensitive, punctuation ignored, order irrelevant, extras ignored)::

        reading_at, temperature, humidity_pct, min_temperature, max_temperature,
        sample_count, notes

    ``reading_at`` and ``temperature`` are required in the HEADER; every other column is optional.
    A row missing either VALUE is skipped and counted — never filled in with a default, and never
    with a zero (see the module docstring).

    The monitor is NOT a field here either: the import route is
    ``cold-chain-monitors/<int:pk>/readings/import/``, so the parent comes from the URL exactly as it
    does on the single-row create.
    """

    file = forms.FileField(
        label="Logger CSV",
        help_text=f"Up to {MAX_BATCH_READINGS:,} data rows. Columns: reading_at, temperature, "
                  f"humidity_pct, min_temperature, max_temperature, sample_count, notes.",
        widget=forms.ClearableFileInput(attrs={"class": "form-input", "accept": ".csv"}))
    source = forms.ChoiceField(
        choices=IMPORT_SOURCE_CHOICES, initial="logger_import",
        help_text="How this batch reached the system — stamped onto every row it files",
        widget=forms.Select(attrs={"class": "form-select"}))
    interval_minutes_override = forms.IntegerField(
        required=False, min_value=MIN_LOGGING_INTERVAL_MINUTES,
        max_value=MAX_LOGGING_INTERVAL_MINUTES,
        label="Interval override (minutes)",
        help_text="Leave blank to snapshot the monitor's own logging interval onto every row",
        widget=forms.NumberInput(attrs={"class": "form-input"}))

    def __init__(self, *args, tenant=None, monitor=None, **kwargs):
        # `tenant` and `monitor` are accepted and held so this form has the same call signature as
        # every other 4.15 form — the views instantiate them all the same way, and a plain
        # `forms.Form` that rejected `tenant=` would be the one that needs a special case.
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.monitor = monitor
        self._text = ""
        self._columns = {}

    def clean_file(self):
        """Extension, size, ROW COUNT and header — all before a single value is parsed.

        The row count is measured on the **raw bytes**, by counting newlines, which is the only way
        to honour "refuse a file with more than ``MAX_BATCH_READINGS`` data rows *before parsing any
        of them*". An unbounded upload is an unbounded ``bulk_create`` any logged-in member can fire,
        and counting after the first query has already lost.
        """
        upload = self.cleaned_data.get("file")
        if upload is None:
            return upload

        name = (getattr(upload, "name", "") or "").lower()
        if not name.endswith(".csv"):
            raise ValidationError("Only .csv files are accepted here.")
        # Belt and braces against the house allowlist, so this route can never become the one that
        # accepts an extension the rest of the application refuses.
        if ".csv" not in ALLOWED_DOC_EXTENSIONS:
            raise ValidationError("CSV upload is not permitted by this installation.")
        if getattr(upload, "size", 0) > MAX_UPLOAD_BYTES:
            raise ValidationError(
                f"That file is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")

        raw = upload.read()
        upload.seek(0)
        if not raw:
            raise ValidationError("That file is empty.")

        # One header line plus the data. Counted on bytes, cheaply, with no parsing at all.
        lines = raw.count(b"\n") + (0 if raw.endswith(b"\n") else 1)
        if lines - 1 > MAX_BATCH_READINGS:
            raise ValidationError(
                f"That file holds about {lines - 1:,} data rows — this importer accepts at most "
                f"{MAX_BATCH_READINGS:,} in one upload. Split it and import the parts.")

        try:
            # utf-8-sig strips the BOM Excel writes on every CSV it saves, which would otherwise
            # make the first header cell unrecognisable.
            self._text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError(
                "That file is not UTF-8 text — re-export it as UTF-8 CSV.") from None

        self._columns = self._map_columns()
        missing = [name for name in REQUIRED_COLUMNS if name not in self._columns]
        if missing:
            raise ValidationError(
                "The header row must name " + " and ".join(missing).replace("_", " ")
                + ". Expected columns: reading_at, temperature, humidity_pct, min_temperature, "
                  "max_temperature, sample_count, notes.")
        return upload

    def _map_columns(self):
        """``{target field: column index}`` from the header row, by alias. Unknown columns ignored.

        Read through :func:`_records` rather than ``csv.reader`` directly: a header line the C
        reader refuses outright (an embedded NUL, an enormous field) raises ``_csv.Error``, which is
        neither a ``UnicodeDecodeError`` nor a ``ValidationError``. Uncaught it is a 500 on a page
        any member can post to; through the helper it is the same kind of message every other bad
        file already gets, and — because this runs inside ``clean_file`` — it lands on the field.
        """
        reader = _records(self._text)
        header = next(reader, None) or []
        lookup = {}
        for index, cell in enumerate(header):
            key = _normalise_header(cell)
            if not key:
                continue
            for target, aliases in COLUMN_ALIASES.items():
                if key in aliases and target not in lookup:
                    lookup[target] = index
        return lookup

    def resolved_interval(self, monitor):
        """The ``interval_minutes`` to SNAPSHOT onto every row this batch files.

        The override when one was given, otherwise the monitor's own logging interval. Resolved here
        rather than in the view so the two import paths (the button and the seeder) cannot disagree,
        and so the snapshot can never silently fall back to the model default of 30.
        """
        override = self.cleaned_data.get("interval_minutes_override")
        return override or monitor.logging_interval_minutes

    def parse_rows(self):
        """``(rows, skipped)`` — clean field dicts, and a tally of everything that was NOT imported.

        ``rows`` is a list of ``{"reading_at", "temperature", "humidity_pct", "min_temperature",
        "max_temperature", "sample_count", "notes"}`` dicts, every one of which already satisfies
        ``TemperatureReading.clean()``'s value rules, so the view can build and save them without
        discovering a bad row halfway through a batch.

        ``skipped`` is ``{"total", "no_temperature", "bad_timestamp", "future", "out_of_bounds",
        "before_deployment", "duplicate_in_file", "dropped_humidity", "dropped_interval_stats"}`` —
        **counted, not silenced.** A skip nobody can see is how an import quietly loses a third of a
        logger file.

        **Raises ``ValidationError`` on a file the C reader refuses** (see :func:`_records`) — the
        caller turns that into a message rather than letting it 500 the upload.

        The rules, and why each is a skip rather than a substitution:

        * **blank or unreadable temperature -> SKIP.** This is the trap the whole sub-module is
          built around: substituting 0 would file "the fridge was at freezing" as a measurement.
        * **unreadable or missing timestamp -> SKIP.** An interval summary always states its own
          window; defaulting it to "now" would turn a back-dated shipment log into a claim that the
          whole journey happened during the upload.
        * **future timestamp -> SKIP.** ``clean()`` refuses one, and a future row sorts to the top of
          an append-only log and becomes "the current value" for a fridge that has not reached it.
        * **temperature outside the physical bounds -> SKIP.** The column's validators would reject
          it; skipping keeps the other 4,999 rows.
        * **timestamp before the monitor's ``deployed_on`` -> SKIP.** ``clean()`` rule 4 refuses one
          on the single-row path, and this batch path writes through ``bulk_create`` — which runs no
          validation at all — so the rule has to be restated here or the two paths disagree. A
          re-usable logger has one deployment per consignment, and re-uploading its whole memory
          would file the PREVIOUS shipment's journey against this deployment, where it is counted in
          this consignment's % time-in-range and its MKT.
        * **duplicate timestamp inside one file -> SKIP.** ``unique_together (monitor, reading_at)``
          would raise ``IntegrityError`` on the second, which fails the whole batch rather than the
          one row.
        * **out-of-range humidity / non-bracketing interval statistics -> the FIELD is dropped, the
          row is kept.** Losing a real temperature because its optional metadata is nonsense would be
          the importer inventing a different kind of wrong answer.

        Duplicates already in the DATABASE are not this function's business — the view's
        ``bulk_create(ignore_conflicts=…)`` or its per-row save is where a re-uploaded file becomes
        idempotent, which is exactly what the ``unique_together`` exists for.
        """
        skipped = {"total": 0, "no_temperature": 0, "bad_timestamp": 0, "future": 0,
                   "out_of_bounds": 0, "before_deployment": 0, "duplicate_in_file": 0,
                   "dropped_humidity": 0, "dropped_interval_stats": 0}
        rows = []
        if not self._text or not self._columns:
            return rows, skipped

        now = timezone.now()
        # The deployment date this batch is being filed against, resolved once. `self.monitor` is the
        # one from the ROUTE (the import URL carries it), which is the same parent the single-row
        # form stamps before validation — so both paths judge against the same deployment.
        deployed_on = getattr(self.monitor, "deployed_on", None) if self.monitor else None
        seen = set()
        reader = _records(self._text)
        next(reader, None)  # the header, already mapped in clean_file

        for record in reader:
            if not any((value or "").strip() for value in record):
                continue  # a blank separator line is not a skipped reading

            def cell(name, record=record):
                return _cell(record, self._columns, name)

            temperature = _parse_decimal(cell("temperature"))
            if temperature is None:
                skipped["total"] += 1
                skipped["no_temperature"] += 1
                continue
            if not (MIN_TEMPERATURE_C <= temperature <= MAX_TEMPERATURE_C):
                skipped["total"] += 1
                skipped["out_of_bounds"] += 1
                continue

            moment = _parse_moment(cell("reading_at"))
            if moment is None:
                skipped["total"] += 1
                skipped["bad_timestamp"] += 1
                continue
            if moment > now:
                skipped["total"] += 1
                skipped["future"] += 1
                continue
            # `TemperatureReading.clean()` rule 4, restated on the BATCH path — `bulk_create` never
            # calls `full_clean()`, so a rule stated only on the model holds on the single-row form
            # and nowhere else. Compared in LOCAL time exactly as the model compares it: a
            # `deployed_on` is a calendar date somebody wrote down in their own world, and reading
            # the moment in UTC would move the boundary by the offset.
            if deployed_on and timezone.localtime(moment).date() < deployed_on:
                skipped["total"] += 1
                skipped["before_deployment"] += 1
                continue
            if moment in seen:
                skipped["total"] += 1
                skipped["duplicate_in_file"] += 1
                continue
            seen.add(moment)

            humidity = _parse_decimal(cell("humidity_pct"))
            if humidity is not None and not (MIN_HUMIDITY_PCT <= humidity <= MAX_HUMIDITY_PCT):
                humidity = None
                skipped["dropped_humidity"] += 1

            lowest = _parse_decimal(cell("min_temperature"))
            highest = _parse_decimal(cell("max_temperature"))
            dropped = False
            for bound in (lowest, highest):
                if bound is not None and not (MIN_TEMPERATURE_C <= bound <= MAX_TEMPERATURE_C):
                    dropped = True
            if dropped:
                lowest = highest = None
            if lowest is not None and lowest > temperature:
                lowest, dropped = None, True
            if highest is not None and highest < temperature:
                highest, dropped = None, True
            if lowest is not None and highest is not None and highest < lowest:
                lowest, highest, dropped = None, None, True
            if dropped:
                skipped["dropped_interval_stats"] += 1

            samples = _parse_int(cell("sample_count"))
            if samples is None or samples < 1:
                samples = 1
            samples = min(samples, MAX_SAMPLE_COUNT)

            rows.append({
                "reading_at": moment,
                "temperature": temperature.quantize(Decimal("0.01")),
                "humidity_pct": humidity.quantize(Decimal("0.01")) if humidity is not None else None,
                "min_temperature": lowest.quantize(Decimal("0.01")) if lowest is not None else None,
                "max_temperature": highest.quantize(Decimal("0.01")) if highest is not None else None,
                "sample_count": samples,
                "notes": (cell("notes") or "").strip()[:255],
            })
        return rows, skipped
