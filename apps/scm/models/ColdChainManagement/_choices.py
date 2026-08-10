"""SCM 4.15 Cold Chain Management — the vocabularies and bounds shared across the sub-module.

**Why this file exists.** Same rule as ``AssetManagement/_choices.py`` and
``LaborManagement/_choices.py``: a vocabulary read by exactly one model stays on that model.
Everything below is read from **two or more directions at once** —

* ``MONITOR_STATUS_CHOICES`` — declared on ``ColdChainMonitor``, filtered on its list page and read
  by ``coldchain.detect_excursions()``, whose scope is ``status="active"`` monitors.
* ``EXCURSION_STATUS_CHOICES`` / ``OPEN_EXCURSION_STATUSES`` / ``EDITABLE_EXCURSION_STATUSES`` —
  written by the excursion's four triage verbs, read by the queue page, the compliance report and
  ``ColdChainMonitor.open_excursion_count()``.
* ``READING_SOURCE_CHOICES`` — stamped by the manual create verb and by the logger import.
* ``BREACH_DIRECTION_CHOICES`` / ``EXCURSION_SEVERITY_CHOICES`` — written by the detector in
  ``coldchain.py`` and rendered on three pages.
* The bounds — enforced as validators and in ``clean()``, quoted back in the messages the views,
  the importer and the templates print.

**``STORAGE_CONDITION_CHOICES`` is NOT here.** It lives at the models package root
(``apps/scm/models/_choices.py``) because 4.3's ``Item`` and ``Location`` read it too, and an older
sub-module must never reach into a newer sub-module's private module. See that file's docstring.

**Pure data — no queries, no model imports, not even ``_base``.** Nothing here imports a sibling
model, so the dependency edge inside the sub-module can only ever run one way
(``ColdChainMonitors`` / ``TemperatureReadings`` / ``TemperatureExcursions`` -> ``_choices``) and no
import cycle is possible. In particular this module must never import ``apps.scm.coldchain``: that
module imports the model layer, so the edge has to run one way or the package will not import (the
``SupplyChainAlerts.py:9-11`` rule, verbatim).

**``__all__`` is explicit, and the parent re-exports these BY NAME rather than with ``import *``.**
``apps/scm/models/__init__.py`` already star-imports 4.12's and 4.13's ``_choices``; a second
star-imported ``_choices`` re-declaring a shared token would **silently shadow** it, and which one
won would depend on import order (``models/__init__.py:292-298``).

**The CSS dicts.** Colour is decided in exactly one place per vocabulary (the ``KpiSnapshot.BAND_CSS``
precedent) so a badge cannot be styled one way on the list page and another on the detail page. Only
the six classes that actually exist in ``static/css/theme.css`` may appear —
``badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate``. There is no
``badge-success`` / ``badge-warning`` / ``badge-danger``; those render completely unstyled (L33).
"""
from decimal import Decimal

__all__ = [
    "DEVICE_TYPE_CHOICES",
    "MONITOR_STATUS_CHOICES", "MONITOR_STATUS_CSS",
    "READING_SOURCE_CHOICES",
    "EXCURSION_STATUS_CHOICES", "EXCURSION_STATUS_CSS",
    "OPEN_EXCURSION_STATUSES", "EDITABLE_EXCURSION_STATUSES",
    "EXCURSION_SEVERITY_CHOICES", "EXCURSION_SEVERITY_CSS",
    "BREACH_DIRECTION_CHOICES", "BREACH_DIRECTION_CSS",
    "ASSESSMENT_CHOICES", "ASSESSMENT_CSS",
    "EXCURSION_CAUSE_CHOICES",
    "MIN_TEMPERATURE_C", "MAX_TEMPERATURE_C",
    "MIN_HUMIDITY_PCT", "MAX_HUMIDITY_PCT",
    "MAX_WARNING_MARGIN_C",
    "MIN_LOGGING_INTERVAL_MINUTES", "MAX_LOGGING_INTERVAL_MINUTES",
    "MAX_EXCURSION_GRACE_MINUTES", "MAX_EXCURSION_MINUTES",
    "MAX_SAMPLE_COUNT", "MAX_BATCH_READINGS", "MAX_READING_WINDOW_DAYS",
    "MAX_EPISODE_READINGS", "STALE_INTERVAL_MULTIPLIER", "CALIBRATION_NOTICE_DAYS",
    "MKT_ACTIVATION_ENERGY_KJ", "GAS_CONSTANT_KJ", "MKT_EA_OVER_R", "KELVIN_OFFSET",
]


# --------------------------------------------------------------------------------------------
# Monitor vocabulary
# --------------------------------------------------------------------------------------------

#: What kind of device is watching. ELPRO runs single-use, Bluetooth and real-time devices into ONE
#: database rather than three; Controlant ships reusable circular loggers; Tive reassigns a tracker
#: from shipment to shipment; SmartSense fixes sensors to a walk-in. All four shapes are the same
#: row here — a device type is a property of the DEPLOYMENT, not a reason for a second table.
#:
#: ``max_length=20`` against a 17-char longest value (``single_use_logger``) — headroom, the 4.10
#: column-widen lesson.
DEVICE_TYPE_CHOICES = [
    ("fixed_sensor", "Fixed sensor / probe"),
    ("multi_use_logger", "Re-usable data logger"),
    ("single_use_logger", "Single-use data logger"),
    ("realtime_tracker", "Real-time tracker"),
    ("gateway_probe", "Gateway probe"),
    ("manual", "Manual readings only"),
]

#: The monitor's lifecycle. **The user owns this column and is its only writer** — the detector never
#: flips it (the ``Asset.status`` ruling: one writer per column, no drift). ``in_calibration`` and
#: ``lost`` are the two states that stop a monitor being detected against without deleting the
#: deployment or its history.
#:
#: ``max_length=16`` against a 14-char longest value (``in_calibration``).
MONITOR_STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("in_calibration", "In Calibration"),
    ("retired", "Retired"),
    ("lost", "Lost"),
]

#: ``lost`` is RED because a device nobody can find is watching nothing while the page still lists
#: the thing it was meant to watch as monitored — the one state on this list worth seeing from
#: across a room.
MONITOR_STATUS_CSS = {
    "active": "badge-green",
    "inactive": "badge-muted",
    "in_calibration": "badge-info",
    "retired": "badge-muted",
    "lost": "badge-red",
}


# --------------------------------------------------------------------------------------------
# Reading vocabulary
# --------------------------------------------------------------------------------------------

#: How a reading reached the system. Stamped by whichever verb files the row and **never a form
#: field**, for the reason 4.13's ``MeterReading.source`` stopped being one: a provenance a user can
#: type is not a provenance, and this record ends up in an audit pack.
#:
#: ``sensor_api`` is written by **NOTHING this pass** — it is the ingestion seam declared now so a
#: live feed lands as a new *row source* rather than a schema change. Exactly the
#: ``METER_SOURCE_CHOICES["sensor"]`` precedent (``AssetManagement/_choices.py:151-158``).
READING_SOURCE_CHOICES = [
    ("manual", "Manual entry"),
    ("logger_import", "Logger file import"),
    ("gateway", "Gateway batch"),
    ("sensor_api", "Sensor / IoT feed"),
]


# --------------------------------------------------------------------------------------------
# Excursion vocabulary
# --------------------------------------------------------------------------------------------

#: The triage lifecycle every surveyed product ships in some form: Sensitech's Handling & Excursion
#: Management, SmartSense's prescriptive corrective-action workflow, Controlant's investigation
#: queue. ``dismissed`` is the honest close for a blip judged not worth acting on — without it,
#: closing a nothing-burger and closing a real spoilage event look identical on the report.
#:
#: ``max_length=16`` against a 13-char longest value (``investigating``).
EXCURSION_STATUS_CHOICES = [
    ("open", "Open"),
    ("investigating", "Investigating"),
    ("assessed", "Assessed"),
    ("closed", "Closed"),
    ("dismissed", "Dismissed"),
]

#: ``open`` is RED because open means **unattended** — the ``SupplyChainAlert.STATUS_CSS`` reasoning.
EXCURSION_STATUS_CSS = {
    "open": "badge-red",
    "investigating": "badge-amber",
    "assessed": "badge-info",
    "closed": "badge-green",
    "dismissed": "badge-muted",
}

#: Triage still outstanding. Owned here so the detector, the model and every page that filters on it
#: cannot drift apart (the ``SupplyChainAlert.OPEN_STATUSES`` precedent).
#:
#: **Note carefully that this is a TRIAGE question, not "is the breach still happening".** An
#: episode whose ``ended_at`` is set stopped breaching, and its triage can still be wide open; an
#: episode with ``ended_at IS NULL`` is still breaching right now. The model names the two apart
#: (``is_open`` vs ``is_episode_running``) and so must every caller.
OPEN_EXCURSION_STATUSES = ("open", "investigating", "assessed")

#: Statuses in which the human triage block may still be edited. Once an episode is closed or
#: dismissed the assessment is the record, and an editable record is not one.
EDITABLE_EXCURSION_STATUSES = ("open", "investigating")

#: How bad it was. Seeded by the detector at open time from ``severity_for()`` and **human-writable
#: afterwards** — a triager's downgrade has to survive the next detection pass, so the detector
#: never re-writes this column on a later run.
EXCURSION_SEVERITY_CHOICES = [
    ("critical", "Critical"),
    ("major", "Major"),
    ("minor", "Minor"),
]

EXCURSION_SEVERITY_CSS = {
    "critical": "badge-red",
    "major": "badge-amber",
    "minor": "badge-info",
}

#: Which side of the band was broken. ``both`` exists because one episode genuinely can swing
#: through the band and out the other side (a defrost cycle overshooting, then a compressor
#: overcorrecting), and forcing it into one direction would misfile the cause.
#:
#: ``low`` is INFO rather than green or red: too cold is a real excursion for chilled product
#: (freeze damage) but it is not the runaway-warming case the red is reserved for.
BREACH_DIRECTION_CHOICES = [
    ("high", "Above the upper limit"),
    ("low", "Below the lower limit"),
    ("both", "Both directions"),
]

BREACH_DIRECTION_CSS = {
    "high": "badge-red",
    "low": "badge-info",
    "both": "badge-amber",
}

#: The **product-level release decision**, which is the whole reason a cold-chain excursion queue
#: earns its keep: ELPRO sells "assess shipments at product level to reduce unnecessary
#: quarantines", Sensitech "faster, more precise release decisions", and Tive is explicit that "the
#: quality team maintains decision authority for disposition".
#:
#: **The DISPOSITION itself is 4.9's ``DISPOSITION_CHOICES`` and is deliberately NOT redeclared
#: here.** 4.15 records the VERDICT (was the product affected?) and links out to the
#: ``NonConformance`` that acts on it — 4.9 owns disposition, the quarantine verb that flips
#: ``LotSerial.status``, and ``cost_of_quality``. Two disposition vocabularies would be two answers
#: to one question, and the one on the excursion would be the one nobody acted on.
ASSESSMENT_CHOICES = [
    ("pending", "Pending assessment"),
    ("product_ok", "Product unaffected — release"),
    ("product_affected", "Product affected"),
]

ASSESSMENT_CSS = {
    "pending": "badge-muted",
    "product_ok": "badge-green",
    "product_affected": "badge-red",
}

#: Why it happened. **Closed on purpose**: a closed vocabulary is what makes "which cause costs us
#: the most spoilage?" a ``GROUP BY`` rather than a pile of free-text nobody can total — the same
#: Maximo failure-code reasoning as ``AssetManagement/_choices.py:98-104``. ``unknown`` and ``other``
#: are BOTH present so nobody is ever forced into a wrong code; a coder pushed into a wrong value
#: makes every other value untrustworthy.
#:
#: Drivers: SmartSense's audit-ready corrective action, ORBCOMM's alarm-to-rapid-repair loop, Tive's
#: CAPA documentation. ``max_length=20`` against a 17-char longest value (``packaging_failure``).
EXCURSION_CAUSE_CHOICES = [
    ("equipment_failure", "Equipment failure"),
    ("power_loss", "Power loss"),
    ("door_left_open", "Door left open"),
    ("packaging_failure", "Packaging failure"),
    ("transit_delay", "Transit delay"),
    ("loading_delay", "Loading / dwell delay"),
    ("wrong_setpoint", "Wrong setpoint"),
    ("sensor_fault", "Sensor fault"),
    ("unknown", "Unknown"),
    ("other", "Other"),
]


# --------------------------------------------------------------------------------------------
# Physical + policy bounds
# --------------------------------------------------------------------------------------------
#
# EVERY ONE of these is a validator or an explicit refusal, NEVER a silent clamp. That distinction is
# the first half of this sub-module's central trap: ``q2()``/``q4()`` clamp, which is right for a
# COMPUTED figure (one poisoned row degrades only itself) and wrong for an ASSERTION ABOUT THE WORLD.
# A quietly clamped temperature is a measurement nobody took, wearing the costume of one somebody
# did — see ``TemperatureReadings.py`` for the full statement of the rule.

#: Physical bounds on any temperature column in this sub-module. Wide on purpose: -196 °C is liquid
#: nitrogen and a real cryogenic setpoint, so the floor cannot be anywhere near 0.
#:
#: **``MinValueValidator(ZERO)`` MUST NEVER APPEAR ON A TEMPERATURE COLUMN.** Every other decimal in
#: ``apps/scm`` carries it, so "restoring consistency" is the exact wrong instinct here: -18 °C is
#: the normal operating point of half of 4.15, and a non-negative validator would reject every
#: frozen reading in the module.
MIN_TEMPERATURE_C = Decimal("-200")
MAX_TEMPERATURE_C = Decimal("200")

#: Relative humidity is a percentage and genuinely IS non-negative — unlike the temperatures above.
#: Four of the eleven surveyed products (Emerson GO, Tive, ORBCOMM, ELPRO) treat humidity as
#: co-equal with temperature, so it is recorded. **Humidity EXCURSIONS are out of scope this pass:**
#: a humidity breach is a second episode type with its own duration and grace rules, and no bullet
#: asks for one.
MIN_HUMIDITY_PCT = Decimal("0")
MAX_HUMIDITY_PCT = Decimal("100")

#: Ceiling on ``ColdChainMonitor.warning_margin_c``. **A margin is a MAGNITUDE, not a temperature**,
#: so this one is bounded below by a positive number while the temperature columns beside it are
#: signed. ``clean()`` additionally requires it to be strictly under half the band width, because a
#: warning band wider than the band itself would fire warnings inside the safe zone.
MAX_WARNING_MARGIN_C = Decimal("50")

#: Logging interval bounds, in minutes. One minute is the finest any surveyed logger offers; a day
#: is the coarsest interval that can still be called monitoring.
MIN_LOGGING_INTERVAL_MINUTES = 1
MAX_LOGGING_INTERVAL_MINUTES = 1440

#: How long a breach may run before it is worth reporting, ceiling seven days. The grace period is
#: **the single most important setting in the sub-module**: without it every door-open is an
#: incident and the queue is ignored within a week. ELPRO's duration-outside-limits alarm criterion,
#: Tive and Controlant all delay on duration for exactly this reason.
MAX_EXCURSION_GRACE_MINUTES = 10080

#: Ceiling on a stored episode duration — one year, the ``MaintenanceWorkOrder.MAX_DOWNTIME_MINUTES``
#: idiom. ``PositiveIntegerField`` accepts 4294967295 on MariaDB and this figure is fed to
#: ``timedelta(minutes=...)`` on the reports, where an out-of-range value is an uncaught
#: ``OverflowError`` — a 500, not a validation error (the 4.10 DoS finding).
MAX_EXCURSION_MINUTES = 60 * 24 * 365

#: Ceiling on ``TemperatureReading.sample_count`` — how many raw samples one interval summary rolled
#: up. A 30-minute window sampling every second is 1800; 10 000 is generous headroom and still far
#: from a number that means somebody mis-mapped a column during an import.
MAX_SAMPLE_COUNT = 10000

#: Rows accepted by ONE logger-file import. Measured **before any DB work** — an unbounded upload is
#: an unbounded ``bulk_create`` any logged-in member can fire, and counting after the first query has
#: already lost (the ``MAX_BULK_ASSIGN`` precedent).
MAX_BATCH_READINGS = 5000

#: Hard cap on any chart / profile window. The reading table is the fastest-growing one in the
#: sub-module (~17.5k rows per monitor per year at the 30-minute default), so an unbounded date range
#: is a full scan on a page anyone can open. The profile RETURNS the fact that it truncated
#: (``window_capped``) rather than silently pretending the range was honoured.
MAX_READING_WINDOW_DAYS = 90

#: Hard cap on the reading walk inside one detector pass, per monitor. The detector reports
#: ``more_remain`` when it hits this rather than running until the request times out.
MAX_EPISODE_READINGS = 20000

#: A monitor is "not reporting" once the newest reading is older than this many logging intervals.
#: Three intervals tolerates one missed transmission plus a retry before crying wolf.
#:
#: Drivers: Controlant's device-health assessments, ELPRO's missing-logger alerts, Berlinger's device
#: delivery rates. **There is no stored ``offline`` flag** — the fact changes by the clock ticking,
#: and a stored flag needs something to run every night to stay true (the 4.12 licence-expiry /
#: ``Asset.warranty_chip()`` ruling).
STALE_INTERVAL_MULTIPLIER = 3

#: How far ahead a calibration certificate starts reading as "due" — the ``Asset.WARRANTY_NOTICE_DAYS``
#: idiom, fixed rather than per-row because a calibration has no renewal workflow to configure it
#: from. Drivers: ELPRO's ILAC/NIST/ISO 17025 three-point certificates, Tive's per-tracker NIST
#: certificate, Controlant's validated loggers.
CALIBRATION_NOTICE_DAYS = 30


# --------------------------------------------------------------------------------------------
# Mean kinetic temperature (USP <1079.2>)
# --------------------------------------------------------------------------------------------
#
#     MKT = (dH/R) / -ln( SUM( w_i * exp( -(dH/R) / T_i ) ) / SUM( w_i ) )      [T in kelvin]
#
# where ``w_i`` is the row's SNAPSHOTTED ``interval_minutes`` — that is the entire reason that column
# exists. A single hot hour inside a cold month must weigh one hour, not "one row", or a monitor
# whose logging interval changed mid-window silently reports a different MKT for the same weather.

#: The USP <1079.2> default activation energy, in kJ/mol.
MKT_ACTIVATION_ENERGY_KJ = Decimal("83.144")

#: The universal gas constant in the matching units, kJ/(mol*K).
GAS_CONSTANT_KJ = Decimal("0.0083144")

#: ``83.144 / 0.0083144 == 10000`` EXACTLY — which is precisely why the USP chose those two figures.
#: The code uses this constant directly rather than dividing two ``Decimal`` s on every call, so the
#: arithmetic is both faster and free of a rounding step that has no business existing.
MKT_EA_OVER_R = Decimal("10000")

#: Celsius <-> kelvin. Stated once so no caller re-types 273.15 and lands on 273.
KELVIN_OFFSET = Decimal("273.15")
