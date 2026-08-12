"""SCM 4.15 Cold Chain Management — the model layer.

Three tables: ``ColdChainMonitor`` [CCM-] (one device, watching one thing, against these limits),
``TemperatureReading`` (the append-only product-environment log) and ``TemperatureExcursion`` [EXC-]
(one out-of-limits episode plus what a human decided about it).

The classes marked **INVARIANT** each pin a rule the sub-module's own docstrings state in as many
words, and every one of them is a rule a later "consistency fix" would break:

* a temperature column is SIGNED — ``MinValueValidator(ZERO)`` on one would reject every frozen
  reading in the module, and ``q2()`` / ``q4()`` would turn a missing measurement into 0 °C;
* a derived answer is tri-state and answers ``None`` for "we cannot say", never ``False`` or ``0``;
* the measured block on an excursion is ``editable=False`` and the detector is its only writer;
* ``limit_min`` / ``limit_max`` are a SNAPSHOT and are never re-written;
* ``TemperatureReading`` is append-only — no edit, no delete, no admin write.

Fixtures come from ``apps/scm/tests/_coldchain.py`` (4.15's own), from ``apps/scm/tests/conftest.py``
(the SCM domain records) and from the ROOT ``conftest.py`` (tenants, users, clients). Nothing here
writes to either conftest.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.scm.tests._coldchain import *  # noqa: F401,F403


# =================================================================================================
# 4.15 · numbering, identity and the tenant key
# =================================================================================================
class TestColdChainNumbering:
    def test_a_monitor_mints_its_own_ccm_number(self, cc_monitor_a):
        assert cc_monitor_a.number == "CCM-00001"

    def test_a_second_monitor_takes_the_next_one(self, cc_monitor_a, cc_monitor_a2):
        assert cc_monitor_a2.number == "CCM-00002"

    def test_the_sequence_restarts_per_workspace(self, cc_monitor_a, cc_monitor_b):
        """``unique_together ("tenant", "number")`` — the counter is per tenant, so two workspaces
        both legitimately hold a CCM-00001."""
        assert cc_monitor_a.number == cc_monitor_b.number == "CCM-00001"

    def test_an_excursion_mints_its_own_exc_number(self, cc_excursion_a):
        assert cc_excursion_a.number == "EXC-00001"

    def test_the_monitor_str_leads_with_its_number(self, cc_monitor_a):
        assert str(cc_monitor_a) == "CCM-00001 · Cold Room 2 - top probe"

    def test_the_excursion_str_names_the_breach_direction(self, cc_excursion_a):
        assert str(cc_excursion_a) == "EXC-00001 · Above the upper limit"

    def test_the_reading_str_is_the_measurement_and_the_moment(self, cc_reading_a):
        assert str(cc_reading_a).startswith("5.00 °C @ ")

    def test_a_reading_carries_no_document_number_at_all(self):
        """``TenantOwned``, not ``TenantNumbered`` — the ``StockMove`` / ``MeterReading``
        precedent. A reading is a data point in a series, not something anybody quotes."""
        from apps.scm.models import TemperatureReading
        assert "number" not in {f.name for f in TemperatureReading._meta.get_fields()}
        assert getattr(TemperatureReading, "NUMBER_PREFIX", "") == ""

    def test_the_monitor_number_is_not_a_form_writable_column(self):
        from apps.scm.models import ColdChainMonitor
        assert ColdChainMonitor._meta.get_field("number").editable is False


# =================================================================================================
# 4.15 · INVARIANT — a monitor watches EXACTLY ONE thing, and the choice freezes
# =================================================================================================
class TestColdChainMonitorSubjectRule:
    """Zero subjects and two subjects are different mistakes and take different messages, and the
    pointer is FIXED once readings exist — an audit report must not be rewritable by moving it."""

    def test_zero_subjects_is_refused(self, tenant_a):
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Nothing at all",
                                   min_temperature=Decimal("2"), max_temperature=Decimal("8"))
        with pytest.raises(ValidationError) as exc:
            monitor.full_clean()
        assert "location" in exc.value.message_dict

    def test_two_subjects_are_refused_and_the_error_names_the_second(self, tenant_a, location_a,
                                                                     asset_a):
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Two things", location=location_a,
                                   asset=asset_a, min_temperature=Decimal("2"),
                                   max_temperature=Decimal("8"))
        with pytest.raises(ValidationError) as exc:
            monitor.full_clean()
        assert "asset" in exc.value.message_dict

    def test_all_three_at_once_are_refused(self, tenant_a, location_a, asset_a, shipment_a):
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Everything", location=location_a,
                                   asset=asset_a, shipment=shipment_a,
                                   min_temperature=Decimal("2"), max_temperature=Decimal("8"))
        with pytest.raises(ValidationError):
            monitor.full_clean()

    @pytest.mark.parametrize("field", ["location", "asset", "shipment"])
    def test_exactly_one_of_each_kind_is_legal(self, tenant_a, location_a, asset_a, shipment_a,
                                               field):
        from apps.scm.models import ColdChainMonitor
        subject = {"location": location_a, "asset": asset_a, "shipment": shipment_a}[field]
        monitor = ColdChainMonitor(tenant=tenant_a, name=f"Watches a {field}",
                                   min_temperature=Decimal("2"), max_temperature=Decimal("8"),
                                   **{field: subject})
        monitor.full_clean()  # must not raise
        monitor.save()
        assert monitor.subject_kind == field
        assert monitor.subject == subject
        assert monitor.subject_label == str(subject)

    def test_the_subject_freezes_once_a_reading_exists(self, cc_monitor_a, cc_reading_a, asset_a):
        """Last quarter's "Cold Room 2 was in range 99.4 % of the time" must not silently become a
        statement about a reefer."""
        cc_monitor_a.location = None
        cc_monitor_a.asset = asset_a
        with pytest.raises(ValidationError) as exc:
            cc_monitor_a.full_clean()
        assert "location" in exc.value.message_dict

    def test_the_subject_is_still_editable_while_the_monitor_has_no_readings(self, cc_monitor_a,
                                                                            location_a2):
        cc_monitor_a.location = location_a2
        cc_monitor_a.full_clean()  # must not raise
        cc_monitor_a.save()
        assert cc_monitor_a.subject == location_a2

    def test_an_unrelated_edit_is_still_allowed_after_readings_exist(self, cc_monitor_a,
                                                                    cc_reading_a):
        cc_monitor_a.name = "Cold Room 2 - renamed"
        cc_monitor_a.full_clean()  # must not raise
        cc_monitor_a.save()

    def test_the_subject_is_protected_and_cannot_be_deleted_under_the_monitor(self, cc_monitor_a,
                                                                              location_a):
        """PROTECT, not SET_NULL: a monitor with no subject is uninterpretable AND instantly
        violates its own exactly-one rule, so it could never be saved again."""
        with pytest.raises(ProtectedError):
            with transaction.atomic():
                location_a.delete()

    def test_subject_label_is_the_honest_fallback_on_a_pointerless_row(self, tenant_a):
        from apps.scm.models import ColdChainMonitor
        assert ColdChainMonitor(tenant=tenant_a, name="orphan").subject_label == "Unassigned"


# =================================================================================================
# 4.15 · INVARIANT — the band. A ONE-SIDED band is legal; a zero-width one is not
# =================================================================================================
class TestColdChainMonitorBand:
    @pytest.mark.parametrize("limits", [
        {"min_temperature": None, "max_temperature": Decimal("8")},
        {"min_temperature": Decimal("2"), "max_temperature": None},
    ])
    def test_a_one_sided_band_is_legal(self, tenant_a, location_a, limits):
        """A freezer that only ever needs a ceiling is an ordinary configuration, and the detector
        treats a null side as "no limit on that side" rather than as zero."""
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="One-sided", location=location_a,
                                   status="active", **limits)
        monitor.full_clean()  # must not raise
        monitor.save()
        assert monitor.effective_limits() == (limits["min_temperature"], limits["max_temperature"])

    def test_a_frozen_band_is_legal_and_no_validator_refuses_a_negative(self, tenant_a, asset_a):
        """-18 °C is the normal operating point of half this sub-module. A
        ``MinValueValidator(ZERO)`` on a temperature column is a BUG here, not a consistency fix."""
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Blast freezer", asset=asset_a,
                                   min_temperature=Decimal("-25.00"),
                                   max_temperature=Decimal("-15.00"),
                                   setpoint_temperature=Decimal("-18.00"))
        monitor.full_clean()  # must not raise

    @pytest.mark.parametrize("name", ["min_temperature", "max_temperature", "setpoint_temperature"])
    def test_no_temperature_column_carries_a_non_negative_validator(self, name):
        from django.core.validators import MinValueValidator
        from apps.scm.models import ColdChainMonitor
        field = ColdChainMonitor._meta.get_field(name)
        floors = [v.limit_value for v in field.validators if isinstance(v, MinValueValidator)]
        assert floors and all(limit < 0 for limit in floors), name

    def test_the_warning_margin_is_the_one_field_bounded_below_by_a_positive(self):
        """A margin is a MAGNITUDE, not a temperature — this asymmetry is deliberate."""
        from django.core.validators import MinValueValidator
        from apps.scm.models import ColdChainMonitor
        field = ColdChainMonitor._meta.get_field("warning_margin_c")
        floors = [v.limit_value for v in field.validators if isinstance(v, MinValueValidator)]
        assert floors and all(limit > 0 for limit in floors)

    def test_equal_limits_are_refused(self, tenant_a, location_a):
        """A band nothing can sit inside makes every reading an excursion in one direction."""
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Zero width", location=location_a,
                                   min_temperature=Decimal("5"), max_temperature=Decimal("5"))
        with pytest.raises(ValidationError) as exc:
            monitor.full_clean()
        assert "max_temperature" in exc.value.message_dict

    def test_an_inverted_band_is_refused(self, tenant_a, location_a):
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Inverted", location=location_a,
                                   min_temperature=Decimal("8"), max_temperature=Decimal("2"))
        with pytest.raises(ValidationError):
            monitor.full_clean()

    def test_an_active_monitor_with_no_limit_at_all_is_refused(self, tenant_a, location_a):
        """The 4.11 "an alert with no threshold" finding: without a limit nothing can ever be in or
        out of range, so every chip reads unknown forever."""
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Unbanded", location=location_a,
                                   status="active")
        with pytest.raises(ValidationError) as exc:
            monitor.full_clean()
        assert "min_temperature" in exc.value.message_dict

    @pytest.mark.parametrize("status", ["inactive", "in_calibration", "retired", "lost"])
    def test_a_parked_monitor_may_be_limitless(self, tenant_a, location_a, status):
        """That is how a point is parked while somebody works out what its band should be."""
        from apps.scm.models import ColdChainMonitor
        ColdChainMonitor(tenant=tenant_a, name="Parked", location=location_a,
                         status=status).full_clean()

    def test_a_warning_margin_at_half_the_band_width_is_refused(self, tenant_a, location_a):
        """The two warning zones would meet in the middle, so the monitor warns while sitting
        exactly where it is supposed to be."""
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Always warning", location=location_a,
                                   min_temperature=Decimal("2"), max_temperature=Decimal("8"),
                                   warning_margin_c=Decimal("3"))
        with pytest.raises(ValidationError) as exc:
            monitor.full_clean()
        assert "warning_margin_c" in exc.value.message_dict

    def test_an_inverted_humidity_band_is_refused(self, tenant_a, location_a):
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor(tenant=tenant_a, name="Damp", location=location_a,
                                   min_temperature=Decimal("2"), max_temperature=Decimal("8"),
                                   humidity_min=Decimal("80"), humidity_max=Decimal("20"))
        with pytest.raises(ValidationError) as exc:
            monitor.full_clean()
        assert "humidity_max" in exc.value.message_dict

    def test_retiring_before_deploying_is_refused(self, cc_monitor_a):
        cc_monitor_a.retired_on = cc_monitor_a.deployed_on - datetime.timedelta(days=1)
        with pytest.raises(ValidationError) as exc:
            cc_monitor_a.full_clean()
        assert "retired_on" in exc.value.message_dict

    def test_a_calibration_due_before_the_certificate_is_refused(self, cc_monitor_a):
        cc_monitor_a.calibration_due_on = cc_monitor_a.calibrated_on - datetime.timedelta(days=1)
        with pytest.raises(ValidationError) as exc:
            cc_monitor_a.full_clean()
        assert "calibration_due_on" in exc.value.message_dict


# =================================================================================================
# 4.15 · one ACTIVE deployment per physical device — clean()'s rule, never a DB constraint
# =================================================================================================
class TestColdChainMonitorSerialRule:
    def test_a_second_active_monitor_may_not_claim_the_same_probe(self, cc_monitor_a, tenant_a,
                                                                  location_a2):
        from apps.scm.models import ColdChainMonitor
        clash = ColdChainMonitor(tenant=tenant_a, name="Same probe", location=location_a2,
                                 device_serial=cc_monitor_a.device_serial, status="active",
                                 min_temperature=Decimal("2"), max_temperature=Decimal("8"))
        with pytest.raises(ValidationError) as exc:
            clash.full_clean()
        assert "device_serial" in exc.value.message_dict

    def test_a_historic_deployment_of_the_same_re_usable_logger_is_fine(self, cc_monitor_a,
                                                                       tenant_a, location_a2):
        """A re-usable logger has one deployment per consignment — that is the whole reason the
        serial is not unique per tenant."""
        from apps.scm.models import ColdChainMonitor
        cc_monitor_a.status = "retired"
        cc_monitor_a.save(update_fields=["status", "updated_at"])
        ColdChainMonitor(tenant=tenant_a, name="Next consignment", location=location_a2,
                         device_serial=cc_monitor_a.device_serial, status="active",
                         min_temperature=Decimal("2"),
                         max_temperature=Decimal("8")).full_clean()

    def test_two_serial_less_monitors_are_legal(self, tenant_a, location_a, location_a2):
        """MariaDB stores a blank CharField as "" rather than NULL, so a (tenant, device_serial)
        unique_together would permit exactly ONE untagged monitor per workspace."""
        from apps.scm.models import ColdChainMonitor
        for name, place in (("A", location_a), ("B", location_a2)):
            monitor = ColdChainMonitor(tenant=tenant_a, name=name, location=place,
                                       min_temperature=Decimal("2"), max_temperature=Decimal("8"))
            monitor.full_clean()
            monitor.save()
        assert ColdChainMonitor.objects.filter(tenant=tenant_a, device_serial="").count() == 2

    def test_the_serial_rule_never_reaches_across_workspaces(self, cc_monitor_a, tenant_b,
                                                             location_b):
        from apps.scm.models import ColdChainMonitor
        ColdChainMonitor(tenant=tenant_b, name="Globex, same serial", location=location_b,
                         device_serial=cc_monitor_a.device_serial, status="active",
                         min_temperature=Decimal("2"),
                         max_temperature=Decimal("8")).full_clean()

    def test_no_conditional_unique_constraint_was_declared_on_either_table(self):
        """MariaDB SILENTLY omits a partial index while the SQLite test settings honour it — a guard
        that exists only under test is more dangerous than no guard."""
        from apps.scm.models import ColdChainMonitor, TemperatureExcursion
        for model in (ColdChainMonitor, TemperatureExcursion):
            for constraint in model._meta.constraints:
                assert getattr(constraint, "condition", None) is None, model.__name__


# =================================================================================================
# 4.15 · the cross-tenant guard on every outward pointer
# =================================================================================================
class TestColdChainCrossTenantGuards:
    @pytest.mark.parametrize("field", ["location", "asset", "shipment"])
    def test_a_monitor_may_not_point_at_another_workspace(self, tenant_a, location_b, asset_b,
                                                          shipment_b, field):
        from apps.scm.models import ColdChainMonitor
        subject = {"location": location_b, "asset": asset_b, "shipment": shipment_b}[field]
        monitor = ColdChainMonitor(tenant=tenant_a, name="Crafted", min_temperature=Decimal("2"),
                                   max_temperature=Decimal("8"), **{field: subject})
        with pytest.raises(ValidationError) as exc:
            monitor.full_clean()
        assert field in exc.value.message_dict

    def test_a_reading_may_not_hang_off_another_workspaces_monitor(self, tenant_a, cc_monitor_b):
        from apps.scm.models import TemperatureReading
        row = TemperatureReading(tenant=tenant_a, monitor=cc_monitor_b,
                                 reading_at=cc_moment(10), temperature=Decimal("5"))
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "monitor" in exc.value.message_dict

    def test_an_excursion_may_not_link_another_workspaces_non_conformance(self, cc_excursion_a,
                                                                          nonconformance_b):
        cc_excursion_a.non_conformance = nonconformance_b
        with pytest.raises(ValidationError) as exc:
            cc_excursion_a.full_clean()
        assert "non_conformance" in exc.value.message_dict

    def test_the_guard_walks_a_named_tuple_so_a_new_pointer_is_covered(self):
        from apps.scm.models import ColdChainMonitor, TemperatureExcursion
        assert ColdChainMonitor.TENANT_SCOPED_FKS == ("location", "asset", "shipment")
        assert TemperatureExcursion.TENANT_SCOPED_FKS == (
            "monitor", "non_conformance", "maintenance_work_order", "lot_serial")


# =================================================================================================
# 4.15 · INVARIANT — every derived answer is TRI-STATE. None means "we cannot say", never False/0
# =================================================================================================
class TestColdChainMonitorDerivedAnswers:
    def test_in_range_is_none_with_no_reading_at_all(self, cc_monitor_a):
        assert cc_monitor_a.is_in_range() is None

    def test_in_range_is_none_when_the_monitor_has_no_band(self, cc_monitor_unlimited_a):
        cc_file_reading(cc_monitor_unlimited_a, 5, "5.00")
        assert cc_monitor_unlimited_a.is_in_range() is None

    def test_in_range_is_true_inside_the_band(self, cc_monitor_a, cc_reading_a):
        assert cc_monitor_a.is_in_range() is True

    @pytest.mark.parametrize("temperature", ["1.99", "8.01", "-18.00", "40.00"])
    def test_in_range_is_false_outside_the_band(self, cc_monitor_a, temperature):
        cc_file_reading(cc_monitor_a, 5, temperature)
        assert cc_monitor_a.is_in_range() is False

    @pytest.mark.parametrize("temperature", ["2.00", "8.00"])
    def test_a_reading_exactly_on_the_limit_is_in_range(self, cc_monitor_a, temperature):
        """Strict comparisons — which is what "2 to 8 °C" means everywhere it is printed."""
        cc_file_reading(cc_monitor_a, 5, temperature)
        assert cc_monitor_a.is_in_range() is True

    def test_a_one_sided_band_is_judged_on_the_side_it_has(self, tenant_a, location_a):
        from apps.scm.models import ColdChainMonitor
        monitor = ColdChainMonitor.objects.create(
            tenant=tenant_a, name="Ceiling only", location=location_a,
            max_temperature=Decimal("8"), logging_interval_minutes=30)
        cc_file_reading(monitor, 5, "-40.00")
        assert monitor.is_in_range() is True
        cc_file_reading(monitor, 1, "9.00")
        assert monitor.is_in_range() is False

    def test_the_warning_band_is_none_without_a_margin(self, cc_monitor_a2):
        cc_file_reading(cc_monitor_a2, 5, "5.00")
        assert cc_monitor_a2.warning_margin_c is None
        assert cc_monitor_a2.is_in_warning_band() is None

    def test_the_warning_band_fires_inside_the_limits_only(self, cc_monitor_a):
        cc_file_reading(cc_monitor_a, 5, "7.50")
        assert cc_monitor_a.is_in_warning_band() is True
        assert cc_monitor_a.range_chip()[0] == "Near limit"

    def test_an_already_breaching_point_is_not_double_badged_as_a_warning(self, cc_monitor_a):
        cc_file_reading(cc_monitor_a, 5, "12.00")
        assert cc_monitor_a.is_in_warning_band() is False
        assert cc_monitor_a.range_chip() == ("Out of range", "badge-red")

    def test_is_reporting_is_none_before_the_first_reading(self, cc_monitor_a):
        """"Not yet commissioned" and "stopped reporting" are different problems."""
        assert cc_monitor_a.is_reporting() is None
        assert cc_monitor_a.reporting_chip() == ("No readings", "badge-muted")

    def test_is_reporting_is_true_inside_three_logging_intervals(self, cc_monitor_a, cc_reading_a):
        assert cc_monitor_a.is_reporting() is True
        assert cc_monitor_a.reporting_chip() == ("Reporting", "badge-green")

    def test_is_reporting_is_false_once_the_probe_has_gone_quiet(self, cc_monitor_a):
        cc_file_reading(cc_monitor_a, 30 * 3 + 10, "5.00")
        assert cc_monitor_a.is_reporting() is False
        assert cc_monitor_a.reporting_chip() == ("Not reporting", "badge-red")

    def test_the_setpoint_gap_is_none_rather_than_zero_when_no_setpoint_is_recorded(
            self, cc_monitor_a2):
        cc_file_reading(cc_monitor_a2, 5, "5.00")
        assert cc_monitor_a2.setpoint_temperature is None
        assert cc_monitor_a2.setpoint_gap() is None

    def test_the_setpoint_gap_is_signed_and_quantized(self, cc_monitor_a):
        cc_file_reading(cc_monitor_a, 5, "3.25")
        assert cc_monitor_a.setpoint_gap() == Decimal("-1.75")

    def test_the_calibration_chip_is_muted_rather_than_green_with_no_certificate(self,
                                                                                cc_monitor_a2):
        assert cc_monitor_a2.days_to_calibration_due() is None
        assert cc_monitor_a2.is_calibration_due() is False
        assert cc_monitor_a2.calibration_chip() == ("Not recorded", "badge-muted")

    @pytest.mark.parametrize("days,label", [
        (-1, "Calibration overdue"), (0, "Due today"), (10, "10 days left"),
        (200, "In calibration date"),
    ])
    def test_the_calibration_chip_reads_the_same_notice_window_the_filter_does(self, cc_monitor_a,
                                                                              days, label):
        cc_monitor_a.calibration_due_on = cc_day(days)
        assert cc_monitor_a.calibration_chip()[0] == label
        assert cc_monitor_a.days_to_calibration_due() == days

    def test_the_open_episode_and_the_open_triage_count_answer_different_questions(
            self, cc_monitor_a, cc_excursion_a):
        """An episode can be OVER while its triage is wide open — a page that conflated the two
        would say an incident is still happening when it stopped yesterday."""
        assert cc_monitor_a.open_episode() is None
        assert cc_monitor_a.open_excursion_count() == 1
        running = cc_make_excursion(cc_monitor_a, started_minutes_ago=30, ended=False)
        assert cc_monitor_a.open_episode().pk == running.pk
        assert cc_monitor_a.open_excursion_count() == 2

    def test_a_terminal_episode_leaves_the_triage_count(self, cc_monitor_a, cc_excursion_a,
                                                        admin_user):
        cc_excursion_a.close(admin_user)
        assert cc_monitor_a.open_excursion_count() == 0

    def test_is_frozen_condition_drives_mkts_honest_none(self, cc_monitor_a, cc_monitor_frozen_a):
        assert cc_monitor_a.is_frozen_condition is False
        assert cc_monitor_frozen_a.is_frozen_condition is True

    def test_the_status_badge_comes_from_one_lookup(self, cc_monitor_a):
        from apps.scm.models import MONITOR_STATUS_CSS
        assert cc_monitor_a.status_css == MONITOR_STATUS_CSS["active"]
        cc_monitor_a.status = "lost"
        assert cc_monitor_a.status_css == "badge-red"

    def test_only_theme_css_badge_classes_are_ever_declared(self):
        """theme.css ships six classes; ``badge-success`` / ``badge-warning`` / ``badge-danger``
        render completely unstyled (L33)."""
        from apps.scm.models import (ASSESSMENT_CSS, BREACH_DIRECTION_CSS, EXCURSION_SEVERITY_CSS,
                                     EXCURSION_STATUS_CSS, MONITOR_STATUS_CSS)
        allowed = {"badge-green", "badge-red", "badge-amber", "badge-info", "badge-muted",
                   "badge-slate"}
        for vocabulary in (MONITOR_STATUS_CSS, EXCURSION_STATUS_CSS, EXCURSION_SEVERITY_CSS,
                           BREACH_DIRECTION_CSS, ASSESSMENT_CSS):
            assert set(vocabulary.values()) <= allowed


# =================================================================================================
# 4.15 · INVARIANT — the reading ledger is APPEND-ONLY and idempotent
# =================================================================================================
class TestTemperatureReadingLedger:
    def test_one_interval_summary_per_moment_per_monitor(self, cc_monitor_a, cc_reading_a):
        """``unique_together (monitor, reading_at)`` — re-uploading a logger file cannot double the
        series."""
        from apps.scm.models import TemperatureReading
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                TemperatureReading.objects.create(
                    tenant=cc_monitor_a.tenant, monitor=cc_monitor_a,
                    reading_at=cc_reading_a.reading_at, temperature=Decimal("6.00"))

    def test_the_guard_names_two_columns_and_not_three(self):
        from apps.scm.models import TemperatureReading
        assert TemperatureReading._meta.unique_together == (("monitor", "reading_at"),)

    def test_the_same_moment_on_a_different_monitor_is_fine(self, cc_monitor_a, cc_monitor_a2,
                                                            cc_reading_a):
        row = cc_file_reading(cc_monitor_a2, 0, "5.00", reading_at=cc_reading_a.reading_at)
        assert row.pk

    def test_the_log_is_newest_first(self, cc_monitor_a):
        from apps.scm.models import TemperatureReading
        cc_series(cc_monitor_a, ["1.00", "2.00", "3.00"])
        rows = list(TemperatureReading.objects.filter(tenant=cc_monitor_a.tenant))
        assert [str(row.temperature) for row in rows] == ["3.00", "2.00", "1.00"]

    def test_the_ordering_carries_a_deterministic_tie_break(self):
        from apps.scm.models import TemperatureReading
        assert TemperatureReading._meta.ordering == ["-reading_at", "-id"]

    def test_latest_reading_answers_with_the_newest_row(self, cc_monitor_a):
        rows = cc_series(cc_monitor_a, ["1.00", "2.00", "3.00"])
        assert cc_monitor_a.latest_reading().pk == rows[-1].pk

    def test_a_future_reading_is_refused(self, cc_monitor_a):
        from apps.scm.models import TemperatureReading
        row = TemperatureReading(tenant=cc_monitor_a.tenant, monitor=cc_monitor_a,
                                 reading_at=timezone.now() + datetime.timedelta(hours=1),
                                 temperature=Decimal("5"))
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "reading_at" in exc.value.message_dict

    def test_a_reading_predating_the_deployment_is_refused(self, cc_monitor_a):
        """A re-usable logger has one deployment per consignment — a row from before this one
        started belongs to a DIFFERENT monitor's history."""
        from apps.scm.models import TemperatureReading
        before = timezone.make_aware(datetime.datetime.combine(
            cc_monitor_a.deployed_on - datetime.timedelta(days=1), datetime.time(12, 0)))
        row = TemperatureReading(tenant=cc_monitor_a.tenant, monitor=cc_monitor_a,
                                 reading_at=before, temperature=Decimal("5"))
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "reading_at" in exc.value.message_dict

    def test_a_reading_on_the_deployment_day_itself_is_accepted(self, cc_monitor_a):
        from apps.scm.models import TemperatureReading
        on_the_day = timezone.make_aware(datetime.datetime.combine(
            cc_monitor_a.deployed_on, datetime.time(0, 0)))
        TemperatureReading(tenant=cc_monitor_a.tenant, monitor=cc_monitor_a,
                           reading_at=on_the_day, temperature=Decimal("5"),
                           interval_minutes=30).full_clean()

    def test_a_monitor_with_no_deployment_date_accepts_any_past_row(self, cc_monitor_a2):
        from apps.scm.models import TemperatureReading
        cc_monitor_a2.deployed_on = None
        cc_monitor_a2.save(update_fields=["deployed_on", "updated_at"])
        TemperatureReading(tenant=cc_monitor_a2.tenant, monitor=cc_monitor_a2,
                           reading_at=cc_moment(60 * 24 * 900), temperature=Decimal("5"),
                           interval_minutes=30).full_clean()

    @pytest.mark.parametrize("stats,bad_field", [
        ({"min_temperature": Decimal("9")}, "min_temperature"),
        ({"max_temperature": Decimal("1")}, "max_temperature"),
        ({"min_temperature": Decimal("4"), "max_temperature": Decimal("3")}, "max_temperature"),
    ])
    def test_the_interval_statistics_have_to_bracket_the_reading(self, cc_monitor_a, stats,
                                                                 bad_field):
        from apps.scm.models import TemperatureReading
        row = TemperatureReading(tenant=cc_monitor_a.tenant, monitor=cc_monitor_a,
                                 reading_at=cc_moment(10), temperature=Decimal("5"),
                                 interval_minutes=30, **stats)
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert bad_field in exc.value.message_dict

    def test_a_one_sided_interval_statistic_stays_legal(self, cc_monitor_a):
        """A logger that reports only a maximum is common, and refusing it would push the importer
        into inventing a minimum."""
        from apps.scm.models import TemperatureReading
        TemperatureReading(tenant=cc_monitor_a.tenant, monitor=cc_monitor_a,
                           reading_at=cc_moment(10), temperature=Decimal("5"),
                           interval_minutes=30, max_temperature=Decimal("6")).full_clean()

    @pytest.mark.parametrize("name", ["interval_minutes", "source", "recorded_by"])
    def test_the_weight_and_the_provenance_are_never_typeable(self, name):
        from apps.scm.models import TemperatureReading
        assert TemperatureReading._meta.get_field(name).editable is False, name

    def test_the_source_defaults_to_manual_and_reserves_the_iot_seam(self, cc_reading_a):
        from apps.scm.models import READING_SOURCE_CHOICES
        assert cc_reading_a.source == "manual"
        assert [value for value, _ in READING_SOURCE_CHOICES] == [
            "manual", "logger_import", "gateway", "sensor_api"]

    def test_deleting_the_monitor_takes_the_whole_reading_history(self, cc_monitor_a, cc_reading_a):
        """CASCADE — a raw interval summary is meaningless without the deployment that defines the
        limits it is judged against."""
        from apps.scm.models import TemperatureReading
        cc_monitor_a.delete()
        assert not TemperatureReading.objects.filter(pk=cc_reading_a.pk).exists()

    def test_the_ledger_declares_no_edit_or_delete_surface_anywhere(self):
        """The documented CRUD exception. There is no view, no url and no form for either."""
        from django.urls import NoReverseMatch, reverse
        from apps.scm import forms, views
        for name in ("temperaturereading_edit", "temperaturereading_delete"):
            assert not hasattr(views, name), name
            with pytest.raises(NoReverseMatch):
                reverse(f"scm:{name}", args=[1])
        assert not hasattr(forms, "TemperatureReadingEditForm")


# =================================================================================================
# 4.15 · INVARIANT — the excursion's measured half is DETECTOR-WRITTEN
# =================================================================================================
class TestTemperatureExcursionMeasuredHalf:
    MEASURED = ("started_at", "ended_at", "duration_minutes", "breach_direction",
                "extreme_temperature", "limit_min", "limit_max", "reading_count", "mkt",
                "last_detected_at", "status", "acknowledged_by", "acknowledged_at",
                "assessed_by", "assessed_on")

    @pytest.mark.parametrize("name", MEASURED)
    def test_every_measured_and_stamped_column_is_editable_false(self, name):
        from apps.scm.models import TemperatureExcursion
        assert TemperatureExcursion._meta.get_field(name).editable is False, name

    def test_assessment_stays_editable_because_the_gated_verb_writes_it(self):
        """It is kept OFF ``TemperatureExcursionForm``'s whitelist instead — that list is the only
        thing standing between a member and a product-release verdict with no signature."""
        from apps.scm.models import TemperatureExcursion
        assert TemperatureExcursion._meta.get_field("assessment").editable is True

    def test_the_snapshotted_band_has_to_be_a_band(self, cc_excursion_a):
        cc_excursion_a.limit_min = Decimal("20")
        cc_excursion_a.limit_max = Decimal("2")
        with pytest.raises(ValidationError) as exc:
            cc_excursion_a.full_clean()
        assert "limit_max" in exc.value.message_dict

    def test_an_episode_may_not_end_before_it_started(self, cc_excursion_a):
        cc_excursion_a.ended_at = cc_excursion_a.started_at - datetime.timedelta(minutes=1)
        with pytest.raises(ValidationError) as exc:
            cc_excursion_a.full_clean()
        assert "ended_at" in exc.value.message_dict

    def test_an_episode_may_not_start_in_the_future(self, cc_excursion_a):
        cc_excursion_a.started_at = timezone.now() + datetime.timedelta(hours=1)
        cc_excursion_a.ended_at = None
        with pytest.raises(ValidationError) as exc:
            cc_excursion_a.full_clean()
        assert "started_at" in exc.value.message_dict

    def test_a_second_running_episode_on_one_monitor_is_refused_at_the_form_boundary(
            self, cc_monitor_a):
        """BELT AND BRACES ONLY — the real guard is the detector's ``select_for_update()`` on the
        monitor row, and this check must never be cited as the reason a constraint is unnecessary."""
        from apps.scm.models import TemperatureExcursion
        cc_make_excursion(cc_monitor_a, started_minutes_ago=120, ended=False)
        second = TemperatureExcursion(tenant=cc_monitor_a.tenant, monitor=cc_monitor_a,
                                      started_at=cc_moment(30), limit_min=Decimal("2"),
                                      limit_max=Decimal("8"))
        with pytest.raises(ValidationError) as exc:
            second.full_clean()
        assert "monitor" in exc.value.message_dict

    def test_an_affected_product_verdict_needs_an_action_or_a_linked_ncr(self, cc_excursion_a):
        cc_excursion_a.assessment = "product_affected"
        with pytest.raises(ValidationError) as exc:
            cc_excursion_a.full_clean()
        assert "corrective_action" in exc.value.message_dict

    def test_a_linked_non_conformance_satisfies_that_rule(self, cc_excursion_a, nonconformance_a):
        cc_excursion_a.assessment = "product_affected"
        cc_excursion_a.non_conformance = nonconformance_a
        cc_excursion_a.full_clean()  # must not raise

    def test_the_monitor_is_protected_because_the_episode_is_evidence(self, cc_monitor_a,
                                                                      cc_excursion_a):
        with pytest.raises(ProtectedError):
            with transaction.atomic():
                cc_monitor_a.delete()

    def test_excess_c_is_none_rather_than_zero_with_no_limit_on_the_breached_side(self,
                                                                                 cc_excursion_a):
        """An excess of zero means "it touched the limit exactly", which is a different statement
        from "we cannot compute this"."""
        cc_excursion_a.limit_max = None
        assert cc_excursion_a.excess_c() is None

    def test_excess_c_is_none_when_no_extreme_was_recorded(self, cc_excursion_a):
        cc_excursion_a.extreme_temperature = None
        assert cc_excursion_a.excess_c() is None

    def test_excess_c_measures_against_the_snapshotted_limit(self, cc_excursion_a):
        assert cc_excursion_a.excess_c() == Decimal("4.50")

    def test_a_both_direction_episode_reports_its_worse_end(self, cc_excursion_a):
        cc_excursion_a.breach_direction = "both"
        cc_excursion_a.extreme_temperature = Decimal("-20.00")
        assert cc_excursion_a.excess_c() == Decimal("22.00")

    def test_the_stored_duration_is_used_once_the_episode_is_closed(self, cc_excursion_a):
        assert cc_excursion_a.live_duration_minutes() == 60

    def test_a_running_episode_reports_a_LIVE_duration(self, cc_excursion_running_a):
        assert cc_excursion_running_a.live_duration_minutes() >= 89

    def test_the_live_duration_is_clamped_so_a_report_cannot_overflow(self, cc_excursion_running_a):
        from apps.scm.models import MAX_EXCURSION_MINUTES
        cc_excursion_running_a.started_at = timezone.now() - datetime.timedelta(days=4000)
        assert cc_excursion_running_a.live_duration_minutes() == MAX_EXCURSION_MINUTES

    def test_is_reportable_reads_the_monitors_LIVE_grace_period(self, cc_monitor_a):
        """A stored ``reportable`` flag would freeze last month's policy onto this month's
        episodes, and nothing would ever recompute it."""
        episode = cc_make_excursion(cc_monitor_a, duration_minutes=5)
        assert episode.is_reportable is False
        cc_monitor_a.excursion_grace_minutes = 1
        episode.monitor = cc_monitor_a
        assert episode.is_reportable is True

    def test_the_episode_window_query_is_bounded_at_both_ends(self, cc_monitor_a, cc_excursion_a):
        inside = cc_file_reading(cc_monitor_a, 150, "12.00")
        cc_file_reading(cc_monitor_a, 10, "5.00")
        assert [row.pk for row in cc_excursion_a.readings()] == [inside.pk]


# =================================================================================================
# 4.15 · the triage ladder — the ONLY writers of the human columns
# =================================================================================================
class TestTemperatureExcursionWorkflow:
    def test_acknowledge_moves_open_to_investigating_and_stamps_the_first_looker(
            self, cc_excursion_a, admin_user):
        changes = cc_excursion_a.acknowledge(admin_user)
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.status == "investigating"
        assert cc_excursion_a.acknowledged_by_id == admin_user.pk
        assert changes["status"] == ["open", "investigating"]

    def test_re_acknowledging_is_a_silent_no_op(self, cc_excursion_a, admin_user, member_user):
        cc_excursion_a.acknowledge(admin_user)
        assert cc_excursion_a.acknowledge(member_user) == {}
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.acknowledged_by_id == admin_user.pk

    def test_acknowledge_survives_an_unattributed_caller(self, cc_excursion_a):
        from django.contrib.auth.models import AnonymousUser
        cc_excursion_a.acknowledge(AnonymousUser())
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.status == "investigating"
        assert cc_excursion_a.acknowledged_by_id is None

    def test_assess_records_the_verdict_and_signs_it(self, cc_excursion_a, employee_party_a):
        changes = cc_excursion_a.assess(employee_party_a, "product_ok")
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.assessment == "product_ok"
        assert cc_excursion_a.status == "assessed"
        assert cc_excursion_a.assessed_by_id == employee_party_a.pk
        assert cc_excursion_a.assessed_on is not None
        assert changes["assessment"] == ["pending", "product_ok"]

    def test_assess_refuses_a_value_outside_the_vocabulary(self, cc_excursion_a,
                                                           employee_party_a):
        with pytest.raises(ValidationError):
            cc_excursion_a.assess(employee_party_a, "released_for_sale")

    def test_assess_refuses_a_bad_cause_code(self, cc_excursion_a, employee_party_a):
        with pytest.raises(ValidationError):
            cc_excursion_a.assess(employee_party_a, "product_ok", cause="the_fridge_was_sad")

    def test_affected_product_needs_an_action_or_a_linked_ncr(self, cc_excursion_a,
                                                             employee_party_a):
        with pytest.raises(ValidationError) as exc:
            cc_excursion_a.assess(employee_party_a, "product_affected")
        assert "corrective_action" in exc.value.message_dict

    def test_affected_product_with_an_action_is_accepted(self, cc_excursion_a, employee_party_a):
        cc_excursion_a.assess(employee_party_a, "product_affected",
                              corrective_action="Quarantined the pallet.")
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.assessment == "product_affected"

    def test_assess_is_a_silent_no_op_on_a_terminal_row(self, cc_excursion_a, admin_user,
                                                        employee_party_a):
        cc_excursion_a.close(admin_user)
        assert cc_excursion_a.assess(employee_party_a, "product_ok") == {}
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.assessment == "pending"

    def test_close_refuses_while_the_episode_is_still_running(self, cc_excursion_running_a,
                                                              admin_user):
        """The one STATE refusal worth being loud about: closing an incident that is still
        happening files a compliance record saying the product was back in range."""
        with pytest.raises(ValidationError) as exc:
            cc_excursion_running_a.close(admin_user)
        assert "status" in exc.value.message_dict

    def test_close_appends_its_note_and_stamps_who_saw_it(self, cc_excursion_a, admin_user):
        cc_excursion_a.close(admin_user, note="Compressor replaced.")
        cc_excursion_a.refresh_from_db()
        assert cc_excursion_a.status == "closed"
        assert "Compressor replaced." in cc_excursion_a.notes
        assert cc_excursion_a.acknowledged_by_id == admin_user.pk

    def test_re_closing_does_not_blank_the_first_note(self, cc_excursion_a, admin_user):
        cc_excursion_a.close(admin_user, note="First.")
        assert cc_excursion_a.close(admin_user, note="Second.") == {}
        cc_excursion_a.refresh_from_db()
        assert "Second." not in cc_excursion_a.notes

    def test_dismiss_is_allowed_while_the_breach_continues(self, cc_excursion_running_a,
                                                           admin_user):
        """A door propped open during a stock take is the ordinary case — "not worth a person's
        time" can be true while the breach runs."""
        cc_excursion_running_a.dismiss(admin_user)
        cc_excursion_running_a.refresh_from_db()
        assert cc_excursion_running_a.status == "dismissed"
        assert cc_excursion_running_a.ended_at is None

    def test_dismissed_and_closed_stay_apart_on_the_report(self):
        from apps.scm.models import EXCURSION_STATUS_CHOICES, TemperatureExcursion
        assert "dismissed" in dict(EXCURSION_STATUS_CHOICES)
        assert TemperatureExcursion.CLOSED_STATUSES == ("closed", "dismissed")

    def test_the_open_set_and_the_editable_set_both_include_assessed(self):
        """REGRESSION LOCK. ``assessed`` was excluded from the editable set, which stranded the
        instruction the assess verb prints: it told the user to link the non-conformance on the
        edit form while the edit view refused that very form."""
        from apps.scm.models import EDITABLE_EXCURSION_STATUSES, OPEN_EXCURSION_STATUSES
        assert "assessed" in EDITABLE_EXCURSION_STATUSES
        assert "assessed" in OPEN_EXCURSION_STATUSES
        assert set(EDITABLE_EXCURSION_STATUSES) == {"open", "investigating", "assessed"}

    def test_an_assessed_episode_is_still_editable(self, cc_excursion_a, employee_party_a):
        cc_excursion_a.assess(employee_party_a, "product_ok")
        assert cc_excursion_a.is_editable is True

    @pytest.mark.parametrize("status", ["closed", "dismissed"])
    def test_a_terminal_episode_is_not_editable(self, cc_excursion_a, status):
        cc_excursion_a.status = status
        assert cc_excursion_a.is_editable is False
        assert cc_excursion_a.is_open is False

    def test_is_open_and_is_episode_running_are_independent(self, cc_excursion_a, admin_user):
        assert cc_excursion_a.is_open is True and cc_excursion_a.is_episode_running is False
        cc_excursion_a.close(admin_user)
        assert cc_excursion_a.is_open is False and cc_excursion_a.is_episode_running is False


# =================================================================================================
# 4.15 · NOTHING IS STORED — the sub-module's own copy of the 4.13 contract
# =================================================================================================
class TestColdChainNothingIsStored:
    """Every in-range / reporting / calibration / duration / MKT answer recomputes on read. There is
    no column to drift, and no ledger effect anywhere in the sub-module."""

    @pytest.mark.parametrize("name", ["is_in_range", "in_range", "is_reporting", "offline",
                                      "calibration_status", "open_episode",
                                      "open_excursion_count", "setpoint_gap", "latest_reading",
                                      "days_to_calibration_due", "is_calibration_due",
                                      "mkt", "pct_in_range"])
    def test_the_monitor_stores_none_of_its_derived_answers(self, name):
        from apps.scm.models import ColdChainMonitor
        assert name not in {f.name for f in ColdChainMonitor._meta.get_fields()}

    @pytest.mark.parametrize("name", ["is_excursion", "in_range", "out_of_range", "mkt", "breach",
                                      "delta", "is_current"])
    def test_a_reading_stores_no_verdict_about_itself(self, name):
        """Each would be a second copy of a fact the monitor's limits determine, and each would go
        stale the moment a limit was edited."""
        from apps.scm.models import TemperatureReading
        assert name not in {f.name for f in TemperatureReading._meta.get_fields()}

    @pytest.mark.parametrize("name", ["is_reportable", "reportable", "excess_c", "excess",
                                      "live_duration_minutes", "is_open", "is_episode_running",
                                      "is_editable"])
    def test_the_episode_stores_no_derived_flag(self, name):
        from apps.scm.models import TemperatureExcursion
        assert name not in {f.name for f in TemperatureExcursion._meta.get_fields()}

    def test_the_module_declares_no_journal_entry_pointer_anywhere(self):
        """The standing 4.9-4.15 rule (L29). 4.15 has no ledger effect at all."""
        from apps.scm.models import ColdChainMonitor, TemperatureExcursion, TemperatureReading
        for model in (ColdChainMonitor, TemperatureReading, TemperatureExcursion):
            related = {f.related_model.__name__ for f in model._meta.get_fields()
                       if getattr(f, "related_model", None) is not None}
            assert "JournalEntry" not in related, model.__name__

    def test_the_module_declares_no_stock_move_pointer_anywhere(self):
        from apps.scm.models import ColdChainMonitor, TemperatureExcursion, TemperatureReading
        for model in (ColdChainMonitor, TemperatureReading, TemperatureExcursion):
            related = {f.related_model.__name__ for f in model._meta.get_fields()
                       if getattr(f, "related_model", None) is not None}
            assert "StockMove" not in related, model.__name__

    def test_the_sub_module_declares_exactly_three_tables_and_no_maintenance_one(self):
        """"Maintenance of Reefers" is a BOARD computed over 4.13. A reefer is DERIVED as *an Asset
        with an active ColdChainMonitor*, which cannot go stale the way a hand-set type would."""
        from django.apps import apps
        declared = {model.__name__ for model in apps.get_app_config("scm").get_models()
                    if model.__module__.startswith("apps.scm.models.ColdChainManagement")}
        assert declared == {"ColdChainMonitor", "TemperatureReading", "TemperatureExcursion"}

    def test_no_reefer_value_was_added_to_the_4_13_asset_vocabulary(self):
        """A hand-set ``reefer`` type would go stale the day a unit is repurposed; "has a live probe
        pointed at it" cannot. The vocabulary is a class attribute on the 4.13 model, NOT a
        module-level export — the first version of this test imported it from ``apps.scm.models``
        and failed with ``ImportError``, which reads as "the assertion is false" but actually meant
        "the assertion never ran"."""
        from apps.scm.models import Asset
        assert "reefer" not in dict(Asset.ASSET_TYPE_CHOICES)

    def test_the_work_order_source_it_writes_is_an_EXISTING_4_13_value(self):
        from apps.scm import coldchain
        from apps.scm.models import MaintenanceWorkOrder
        assert coldchain.WORK_ORDER_SOURCE in dict(MaintenanceWorkOrder.SOURCE_CHOICES)

    def test_the_three_links_out_are_one_way_and_all_set_null(self):
        """4.9 owns disposition and the quarantine verb that flips ``LotSerial.status``; 4.13 owns
        the repair. 4.15 records the verdict and POINTS at the row somebody else acts on."""
        from apps.scm.models import TemperatureExcursion
        for name in ("non_conformance", "maintenance_work_order", "lot_serial"):
            field = TemperatureExcursion._meta.get_field(name)
            assert field.null is True
            assert field.remote_field.on_delete is models.SET_NULL, name
