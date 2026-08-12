"""SCM 4.15 Cold Chain Management — the fixtures and builders the three ``test_coldchain_*`` modules
share.

**Why this module exists rather than an addition to ``conftest.py``.** ``apps/scm/tests/conftest.py``
is owned by another workstream in this tree and must not be written to, so 4.15's fixtures live here
and each test module star-imports them (``from apps.scm.tests._coldchain import *``). ``__all__`` is
explicit so nothing incidental — ``Decimal``, ``datetime``, ``pytest`` — leaks into an importer's
namespace and shadows a name the test module already carries. A fixture function bound into a test
module's namespace is discovered by pytest exactly as if it had been declared there.

The tenant / user / client fixtures (``tenant_a``, ``tenant_b``, ``admin_user``, ``member_user``,
``admin_b``, ``client_a``, ``client_b``, ``member_client``) come from the ROOT ``conftest.py`` and
the SCM domain fixtures (``location_a``, ``location_a2``, ``location_b``, ``asset_a``, ``asset_b``,
``shipment_a``, ``shipment_b``, ``lot_a``, ``nonconformance_a``, ``item_a`` …) come from
``apps/scm/tests/conftest.py``. Nothing here re-declares one of them.

**Every reference moment is derived from ``timezone.now()`` / ``timezone.localdate()``** — the SAME
basis ``ColdChainMonitor.is_reporting()``, ``TemperatureReading.clean()``,
``coldchain.detect_excursions()`` and every 4.15 window read (lesson L16). A literal date or a
``datetime.date.today()`` basis disagrees with the code for the hours around local midnight, and
``deployed_on`` in particular is compared against ``timezone.localtime(reading_at).date()``.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

__all__ = [
    # builders
    "cc_moment", "cc_day", "cc_local", "cc_file_reading", "cc_series", "cc_make_excursion",
    "cc_csv", "cc_monitor_post", "cc_window_post",
    # fixtures
    "cc_monitor_a", "cc_monitor_a2", "cc_monitor_asset_a", "cc_monitor_frozen_a",
    "cc_monitor_unlimited_a", "cc_monitor_b",
    "cc_reading_a", "cc_reading_b",
    "cc_excursion_a", "cc_excursion_running_a", "cc_excursion_b",
]


# =================================================================================================
# Time basis — L16. Never datetime.date.today(), never a literal.
# =================================================================================================

def cc_moment(minutes_ago=0):
    """An aware datetime that many minutes in the past, truncated to the minute.

    Truncated because ``unique_together (monitor, reading_at)`` and every window bound in the
    sub-module compare exact moments: a microsecond of drift between a fixture and an assertion is
    the kind of flake that only shows up on a slow machine.
    """
    return (timezone.now() - datetime.timedelta(minutes=minutes_ago)).replace(second=0,
                                                                              microsecond=0)


def cc_day(days=0):
    """Today (or days from it) on ``timezone.localdate()`` — the basis ``deployed_on``,
    ``calibration_due_on`` and every report window are read against."""
    return timezone.localdate() + datetime.timedelta(days=days)


def cc_local(moment):
    """A moment as the ``YYYY-MM-DD HH:MM`` string the datetime-local form fields parse."""
    return timezone.localtime(moment).strftime("%Y-%m-%d %H:%M")


# =================================================================================================
# Builders
# =================================================================================================

def cc_file_reading(monitor, minutes_ago, temperature, **overrides):
    """File one interval summary on ``monitor``, the way the create verb does.

    ``interval_minutes`` is SNAPSHOTTED from the monitor rather than left to the model default,
    because that column is the row's own weight in every MKT and time-in-range figure and a fixture
    that let it drift would silently measure a different thing from production.
    """
    from apps.scm.models import TemperatureReading
    data = {
        "tenant": monitor.tenant,
        "monitor": monitor,
        "reading_at": cc_moment(minutes_ago),
        "temperature": Decimal(str(temperature)),
        "interval_minutes": monitor.logging_interval_minutes,
        "source": "manual",
    }
    data.update(overrides)
    return TemperatureReading.objects.create(**data)


def cc_series(monitor, temperatures, *, first_minutes_ago=None, step_minutes=None):
    """A run of readings, OLDEST FIRST, one logging interval apart.

    Returns the list in filing order. ``first_minutes_ago`` defaults to one interval per reading
    plus a five-minute cushion, so the newest row is recent enough that
    ``ColdChainMonitor.is_reporting()`` answers ``True`` without a test having to arrange it.
    """
    step = step_minutes or monitor.logging_interval_minutes
    start = first_minutes_ago if first_minutes_ago is not None else step * len(temperatures) + 5
    return [cc_file_reading(monitor, start - index * step, value)
            for index, value in enumerate(temperatures)]


def cc_make_excursion(monitor, *, started_minutes_ago=180, duration_minutes=60, ended=True,
                      **overrides):
    """One episode with a plausible MEASURED block, written directly.

    Written with ``objects.create`` on purpose: every column below is ``editable=False`` and
    ``coldchain.py`` is its only production writer, so a fixture that went through a form would be
    testing a path that does not exist. The detector's own writes are exercised in
    ``test_coldchain_service.py`` against real readings.
    """
    from apps.scm.models import TemperatureExcursion
    started = cc_moment(started_minutes_ago)
    ended_at = started + datetime.timedelta(minutes=duration_minutes) if ended else None
    data = {
        "tenant": monitor.tenant,
        "monitor": monitor,
        "started_at": started,
        "ended_at": ended_at,
        "duration_minutes": duration_minutes if ended else 0,
        "breach_direction": "high",
        "extreme_temperature": Decimal("12.50"),
        "limit_min": monitor.min_temperature,
        "limit_max": monitor.max_temperature,
        "reading_count": 3,
        "mkt": Decimal("9.10"),
        "last_detected_at": ended_at or started,
        "severity": "major",
    }
    data.update(overrides)
    return TemperatureExcursion.objects.create(**data)


def cc_csv(rows, *, header="reading_at,temperature,humidity_pct,sample_count,notes",
           name="logger.csv"):
    """A logger CSV as an uploaded file. ``rows`` is an iterable of already-joined lines."""
    body = "\n".join([header] + list(rows)) + "\n"
    return SimpleUploadedFile(name, body.encode("utf-8"), content_type="text/csv")


def cc_monitor_post(**overrides):
    """A complete, VALID ``ColdChainMonitorForm`` POST body — a chilled cold room, 2 to 8 °C.

    Every field on the whitelist is present, blank where it is optional, so a test that overrides one
    is changing exactly one thing. ``location`` is deliberately left for the caller: the
    exactly-one-subject rule is the point of most of the tests that use this.
    """
    data = {
        "name": "Cold Room 9", "device_serial": "", "device_type": "fixed_sensor",
        "location": "", "asset": "", "shipment": "",
        "storage_condition": "chilled", "min_temperature": "2.00", "max_temperature": "8.00",
        "warning_margin_c": "", "humidity_min": "", "humidity_max": "",
        "setpoint_temperature": "", "excursion_grace_minutes": "30",
        "logging_interval_minutes": "30",
        "calibrated_on": "", "calibration_due_on": "", "calibration_reference": "",
        "status": "active", "deployed_on": "", "retired_on": "", "notes": "",
    }
    data.update(overrides)
    return data


def cc_window_post(**overrides):
    """A complete ``TemperatureExcursionWindowForm`` POST body — a closed, back-dated window.

    Not one measured number is in it, and that is the contract the create view exists to hold: the
    view asks ``coldchain.window_stats()`` for every one of them.
    """
    data = {
        "monitor": "", "started_at": cc_local(cc_moment(240)),
        "ended_at": cc_local(cc_moment(180)), "severity": "major",
        "cause": "", "corrective_action": "", "notes": "",
    }
    data.update(overrides)
    return data


# =================================================================================================
# Monitors
# =================================================================================================

@pytest.fixture
def cc_monitor_a(db, tenant_a, location_a):
    """The workhorse: a cold room watched at 2 to 8 °C, 30-minute intervals, 30-minute grace.

    ``deployed_on`` is 30 days back because ``TemperatureReading.clean()`` rule (4) and the
    importer's ``before_deployment`` counter both refuse a row dated before it, and
    ``coldchain._watermark`` starts a first sweep from that day. A fixture deployed "today" would
    make every back-dated reading in the suite illegal.
    """
    from apps.scm.models import ColdChainMonitor
    return ColdChainMonitor.objects.create(
        tenant=tenant_a, name="Cold Room 2 - top probe", device_serial="ELP-0001",
        device_type="fixed_sensor", location=location_a, storage_condition="chilled",
        min_temperature=Decimal("2.00"), max_temperature=Decimal("8.00"),
        warning_margin_c=Decimal("1.00"), setpoint_temperature=Decimal("5.00"),
        excursion_grace_minutes=30, logging_interval_minutes=30,
        calibrated_on=cc_day(-90), calibration_due_on=cc_day(275),
        calibration_reference="ISO17025-9911", status="active", deployed_on=cc_day(-30),
    )


@pytest.fixture
def cc_monitor_a2(db, tenant_a, location_a2):
    """A SECOND tenant_a monitor — the sweep cursor, the list filters and the "many monitors, one
    workspace" assertions all need two."""
    from apps.scm.models import ColdChainMonitor
    return ColdChainMonitor.objects.create(
        tenant=tenant_a, name="Overflow chiller", device_serial="ELP-0002",
        device_type="multi_use_logger", location=location_a2, storage_condition="chilled",
        min_temperature=Decimal("2.00"), max_temperature=Decimal("8.00"),
        excursion_grace_minutes=60, logging_interval_minutes=30,
        status="active", deployed_on=cc_day(-30),
    )


@pytest.fixture
def cc_monitor_asset_a(db, tenant_a, asset_a):
    """A monitor whose subject is an ASSET — the only shape ``raise_work_order`` can act on, and the
    only shape the reefer board counts as a reefer."""
    from apps.scm.models import ColdChainMonitor
    return ColdChainMonitor.objects.create(
        tenant=tenant_a, name="REEF-01 cargo probe", device_serial="TIVE-0001",
        device_type="realtime_tracker", asset=asset_a, storage_condition="frozen",
        min_temperature=Decimal("-25.00"), max_temperature=Decimal("-15.00"),
        excursion_grace_minutes=30, logging_interval_minutes=15,
        status="active", deployed_on=cc_day(-30),
    )


@pytest.fixture
def cc_monitor_frozen_a(db, tenant_a, shipment_a):
    """A FROZEN, shipment-borne monitor — MKT must answer ``None`` for it (USP <1079.2>)."""
    from apps.scm.models import ColdChainMonitor
    return ColdChainMonitor.objects.create(
        tenant=tenant_a, name="Consignment logger", device_type="single_use_logger",
        shipment=shipment_a, storage_condition="deep_frozen",
        min_temperature=Decimal("-45.00"), max_temperature=Decimal("-25.00"),
        excursion_grace_minutes=30, logging_interval_minutes=60,
        status="active", deployed_on=cc_day(-30),
    )


@pytest.fixture
def cc_monitor_unlimited_a(db, tenant_a, location_a2):
    """An INACTIVE monitor with no limits at all — legal (rule 5 only bites on ``active``) and the
    row the detector's ``skipped`` counter exists for once it is switched on."""
    from apps.scm.models import ColdChainMonitor
    return ColdChainMonitor.objects.create(
        tenant=tenant_a, name="Unbanded probe", device_type="manual", location=location_a2,
        status="inactive", logging_interval_minutes=30, deployed_on=cc_day(-30),
    )


@pytest.fixture
def cc_monitor_b(db, tenant_b, location_b):
    """The tenant_b monitor every cross-tenant assertion in 4.15 points at."""
    from apps.scm.models import ColdChainMonitor
    return ColdChainMonitor.objects.create(
        tenant=tenant_b, name="Globex cold room", device_serial="GBX-0001",
        location=location_b, storage_condition="chilled",
        min_temperature=Decimal("2.00"), max_temperature=Decimal("8.00"),
        excursion_grace_minutes=30, logging_interval_minutes=30,
        status="active", deployed_on=cc_day(-30),
    )


# =================================================================================================
# Readings and episodes
# =================================================================================================

@pytest.fixture
def cc_reading_a(db, cc_monitor_a):
    """One in-range reading, recent enough that the monitor reads as REPORTING."""
    return cc_file_reading(cc_monitor_a, 10, "5.00")


@pytest.fixture
def cc_reading_b(db, cc_monitor_b):
    return cc_file_reading(cc_monitor_b, 10, "5.00")


@pytest.fixture
def cc_excursion_a(db, cc_monitor_a):
    """A CLOSED episode in ``open`` triage — editable, deletable, closable."""
    return cc_make_excursion(cc_monitor_a)


@pytest.fixture
def cc_excursion_running_a(db, cc_monitor_a2):
    """A STILL-RUNNING episode (``ended_at IS NULL``) — close and delete must both refuse it.

    On its own monitor deliberately: "one open episode per monitor" is the detector's rule, and a
    fixture that parked a running episode next to a closed one on the same probe would make every
    de-dupe assertion ambiguous.
    """
    return cc_make_excursion(cc_monitor_a2, started_minutes_ago=90, ended=False)


@pytest.fixture
def cc_excursion_b(db, cc_monitor_b):
    return cc_make_excursion(cc_monitor_b)
