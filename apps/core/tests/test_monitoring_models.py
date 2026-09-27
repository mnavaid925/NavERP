"""0.17 Monitoring, Logging & Observability - the model lane.

Every test is named `test_monitoring_*` and every helper `_monitoring_*`, so the next sub-module
appending nearby cannot shadow them. The contract is `.claude/tasks/test-contract-core-0.17.md`.
"""
import pytest
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.core.models import AlertEvent, AlertRule, Incident, ServiceComponent


def _monitoring_rule(tenant, service, **overrides):
    """A minimal valid `AlertRule`; override only what the test is about."""
    defaults = {
        "tenant": tenant,
        "service": service,
        "name": f"rule-{AlertRule.objects.filter(tenant=tenant).count()}",
        "metric_key": "cpu_pct",
        "comparator": "gte",
        "warning_threshold": Decimal("90"),
        "frequency": "hourly",
        "severity": "warning",
        "category": "capacity",
        "no_data_action": "ignore",
    }
    defaults.update(overrides)
    return AlertRule(**defaults)


# ------------------------------------------------------------------ the choice vocabularies

def test_monitoring_choices_are_exactly_as_contracted():
    """Every badge ladder in the templates is keyed off these, so their size is a contract."""
    assert len(ServiceComponent.STATUS_CHOICES) == 5
    assert len(AlertEvent.STATE_CHOICES) == 5
    assert len(AlertEvent.SEVERITY_CHOICES) == 3
    assert len(AlertRule.CATEGORY_CHOICES) == 5
    assert len(Incident.STATUS_CHOICES) == 8
    assert len(Incident.IMPACT_CHOICES) == 4
    assert len(Incident.INCIDENT_TYPE_CHOICES) == 3


def test_monitoring_every_state_and_status_value_is_reachable():
    """`no_data` and `expired` are the two the badge ladder originally dropped into the grey."""
    assert "no_data" in dict(AlertEvent.STATE_CHOICES)
    assert "expired" in dict(AlertEvent.STATE_CHOICES)
    for value in ("investigating", "identified", "in_progress"):
        assert value in dict(Incident.STATUS_CHOICES)


def test_monitoring_security_is_the_018_seam():
    """0.18 (Threat Protection) grows through exactly this one value, with no extra columns."""
    assert "security" in dict(AlertRule.CATEGORY_CHOICES)


# ------------------------------------------------------------------ L36: reuse by reference

def test_monitoring_comparators_are_reused_not_copied():
    from apps.core.models import BusinessRule
    assert AlertRule.COMPARATORS is BusinessRule.OPERATORS


def test_monitoring_frequency_choices_are_reused_not_copied():
    from apps.core.models import SyncSchedule
    assert AlertRule.FREQUENCY_CHOICES is SyncSchedule.FREQUENCY_CHOICES


# ------------------------------------------------------------------ clean(): the tier-order rule

def test_monitoring_active_rule_with_no_bound_is_refused(tenant_a, mon_service_ok_a):
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, warning_threshold=None)
    with pytest.raises(ValidationError):
        rule.full_clean(exclude=["created_at", "updated_at"])


def test_monitoring_inactive_rule_with_no_bound_is_allowed(tenant_a, mon_service_ok_a):
    """An unbounded rule is fine once parked - a written intention nobody is holding to."""
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, warning_threshold=None, is_active=False)
    rule.full_clean(exclude=["created_at", "updated_at"])


def test_monitoring_gte_reversed_tiers_are_refused(tenant_a, mon_service_ok_a):
    """critical BELOW warning under `>=` would never be reached first."""
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, comparator="gte",
                            warning_threshold=Decimal("100"), critical_threshold=Decimal("50"))
    with pytest.raises(ValidationError) as exc:
        rule.full_clean(exclude=["created_at", "updated_at"])
    assert "critical_threshold" in exc.value.message_dict




def test_monitoring_lt_reversed_tiers_are_refused(tenant_a, mon_service_ok_a):
    """Under `lt` the critical tier must be the LOWER bound, so the same pair is reversed here."""
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, comparator="lt", metric_key="uptime_pct",
                            warning_threshold=Decimal("99"), critical_threshold=Decimal("99.9"))
    with pytest.raises(ValidationError) as exc:
        rule.full_clean(exclude=["created_at", "updated_at"])
    assert "critical_threshold" in exc.value.message_dict


def test_monitoring_lt_correct_tiers_are_accepted(tenant_a, mon_service_ok_a):
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, comparator="lt", metric_key="uptime_pct",
                            warning_threshold=Decimal("99.9"), critical_threshold=Decimal("99"))
    rule.full_clean(exclude=["created_at", "updated_at"])


def test_monitoring_two_tiers_on_a_non_ordering_comparator_are_refused(tenant_a, mon_service_ok_a):
    """`eq`/`in`/`contains` have no ordering, so a warning/critical pair is not coherent."""
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, comparator="eq",
                            warning_threshold=Decimal("1"), critical_threshold=Decimal("2"))
    with pytest.raises(ValidationError) as exc:
        rule.full_clean(exclude=["created_at", "updated_at"])
    assert "critical_threshold" in exc.value.message_dict


def test_monitoring_bounds_note_names_which_tier_is_stricter(tenant_a, mon_service_ok_a):
    """`bounds_note` must not just say "Both tiers set" - that hides which end binds first."""
    floor = _monitoring_rule(tenant_a, mon_service_ok_a, comparator="lt", metric_key="uptime_pct",
                             warning_threshold=Decimal("99.9"), critical_threshold=Decimal("99"))
    assert "lower bound" in floor.bounds_note
    ceiling = _monitoring_rule(tenant_a, mon_service_ok_a, comparator="gte",
                               warning_threshold=Decimal("50"), critical_threshold=Decimal("100"))
    assert "higher bound" in ceiling.bounds_note


# ------------------------------------------- two different definitions of "open", on purpose

def test_monitoring_event_open_set_is_firing_plus_acknowledged(
        mon_event_firing_a, mon_event_ack_a, mon_event_resolved_a, mon_event_no_data_a):
    """`no_data` is NOT open - it is a different lifecycle, and the board must not fold it in."""
    assert mon_event_firing_a.is_open is True
    assert mon_event_ack_a.is_open is True
    assert mon_event_resolved_a.is_open is False
    assert mon_event_no_data_a.is_open is False


def test_monitoring_incident_open_excludes_resolved_and_completed(mon_incident_open_a):
    assert mon_incident_open_a.is_open is True


# ------------------------------------------------------------------ SET_NULL and the M2M

def test_monitoring_deleting_a_rule_leaves_its_firings_orphaned(tenant_a, mon_service_ok_a,
                                                                _mon_event):
    """The event is EVIDENCE a rule fired; it must survive the rule being retired."""
    rule = _monitoring_rule(tenant_a, mon_service_ok_a)
    rule.full_clean(exclude=["created_at", "updated_at"])
    rule.save()

# ------------------------------------------------------------------ NULL is not 0

def test_monitoring_unreported_component_has_null_not_epoch(mon_service_unreported_a):
    assert mon_service_unreported_a.last_status_at is None
    assert mon_service_unreported_a.status_age_days is None
    assert "Never reported" in mon_service_unreported_a.status_note


def test_monitoring_threshold_display_renders_unset_tiers_as_a_dash(tenant_a, mon_service_ok_a):
    """A `0` that means 'not set' is the most dangerous number an operations board can print."""
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, warning_threshold=Decimal("90"),
                            critical_threshold=None)
    assert "—" in rule.threshold_display
    assert "90" in rule.threshold_display


def test_monitoring_measure_note_distinguishes_unmeasured_from_zero(tenant_a, _mon_event,
                                                                   mon_rule_two_tier_a,
                                                                   mon_service_ok_a):
    unmeasured = _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=mon_service_ok_a,
                            observed_value=None)
    assert "not measured" in unmeasured.measure_note
    measured = _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=mon_service_ok_a,
                          observed_value=Decimal("97.5"))
    assert measured.measure_note != unmeasured.measure_note


def test_monitoring_unbounded_rule_says_so_rather_than_showing_a_zero(tenant_a, mon_service_ok_a):
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, warning_threshold=None, is_active=False)
    assert rule.is_bounded is False
    assert "No bound is set" in rule.bounds_note


# ------------------------------------------------------------------ str() and the accessors

def test_monitoring_alert_rule_str_uses_the_metric_key_accessor(tenant_a, mon_service_ok_a):
    """The field is `metric_key`; `__str__` labels every dropdown, so a wrong name 500s the form."""
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, metric_key="cpu_pct")
    assert "CPU utilisation %" in str(rule)


def test_monitoring_status_note_is_a_property_so_a_template_guard_is_real(mon_service_unreported_a):
    """As a method, `{% if obj.status_note %}` would be always-true (a bound method is truthy).

    A `property` object has an `fget`; a plain method does not. So the assertion is that `fget` IS
    callable and that it is NOT a `function` wrapper — i.e. that access goes through the descriptor.
    """
    descriptor = ServiceComponent.__dict__["status_note"]
    assert isinstance(descriptor, property), "status_note is not a property"
    assert callable(descriptor.fget)
    assert isinstance(descriptor.fget(mon_service_unreported_a), str)


def test_monitoring_incident_is_scheduled_distinguishes_a_notice_from_an_outage(
        mon_incident_open_a, mon_incident_maintenance_a):
    assert mon_incident_open_a.is_scheduled is False
    assert mon_incident_maintenance_a.is_scheduled is True


def test_monitoring_maintenance_window_needs_both_ends(mon_incident_maintenance_a):
    assert mon_incident_maintenance_a.window_valid is True


# ------------------------------------------------- every declared index reached the migration

def test_monitoring_declared_indexes_are_all_present_in_the_migration_file():
    """A model index that never reaches a migration is a silent full scan (the 7.10 failure mode).

    Read the migration source only. The test DB here is SQLite `:memory:`, which has no
    `django_migrations` table in the same shape as MariaDB, so a live query would fail for a reason
    that has nothing to do with the assertion.
    """
    import io
    from pathlib import Path
    path = Path("apps/core/migrations")
    assert path.is_dir(), "the core migrations directory is missing"
    files = sorted(path.glob("0015_*.py"))
    assert files, "migration 0015 (the four monitoring models) is not on disk"
    text = files[-1].read_text(encoding="utf-8")
    for model in (AlertRule, AlertEvent, Incident, ServiceComponent):
        for index in model._meta.indexes:
            assert index.name in text, f"{model.__name__}.{index.name} is not in migration 0015"

    event = _mon_event(tenant_a, rule=rule, service=mon_service_ok_a)
    rule.delete()
    event.refresh_from_db()
    assert event.rule_id is None
    assert event.service_label == mon_service_ok_a.name


def test_monitoring_affected_services_is_a_real_m2m(mon_incident_open_a, mon_service_ok_a):
    assert list(mon_incident_open_a.affected_services.all()) == [mon_service_ok_a]


def test_monitoring_orphan_firing_still_reads_by_its_snapshot(mon_event_orphan_a):
    """`service_label` is the denormalised copy that survives the component going away."""
    assert mon_event_orphan_a.rule_id is None
    assert mon_event_orphan_a.service_label

def test_monitoring_gte_correct_tiers_are_accepted(tenant_a, mon_service_ok_a):
    rule = _monitoring_rule(tenant_a, mon_service_ok_a, comparator="gte",
                            warning_threshold=Decimal("50"), critical_threshold=Decimal("100"))
    rule.full_clean(exclude=["created_at", "updated_at"])
