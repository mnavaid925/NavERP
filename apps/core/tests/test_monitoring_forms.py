"""0.17 Monitoring, Logging & Observability - the form lane.

The three things this lane exists to protect, each of which is a real bug that shipped once:
  * **L22** - no system stamp is ever an editable field.
  * **Tenant scoping** - a foreign tenant's pk must not bind, on ANY FK and on the M2M.
  * **The two `save()` overrides** - the status stamp and the service-label snapshot.
"""
import pytest

from apps.core.forms import AlertEventForm, AlertRuleForm, IncidentForm, ServiceComponentForm
from apps.core.models import AlertRule, ServiceComponent

#: Every system-set stamp on the four models. L22: none of these may be a form field.
_MONITORING_SYSTEM_STAMPS = [
    "last_status_at", "created_at", "updated_at",                 # ServiceComponent
    "fired_at", "first_seen_at", "last_seen_at",                  # AlertEvent
    "acknowledged_at", "acknowledged_by",
    "resolved_at", "resolved_by",                                 # AlertEvent
    "notified_at",                                                # Incident
]

_MONITORING_FORMS = [ServiceComponentForm, AlertRuleForm, AlertEventForm, IncidentForm]


# ------------------------------------------------------------------ L22: zero editable datetimes

@pytest.mark.parametrize("form_class", _MONITORING_FORMS)
def test_monitoring_no_system_stamp_is_an_editable_field(form_class):
    """A `DateInput` on a nullable datetime truncates the time, and a typed stamp is a fiction."""
    fields = set(form_class.base_fields)
    offenders = [name for name in _MONITORING_SYSTEM_STAMPS if name in fields]
    assert not offenders, f"{form_class.__name__} exposes system stamps: {offenders}"


def test_monitoring_tenant_is_never_a_form_field():
    """A form must never be able to set its own tenant - that is the whole isolation guarantee."""
    for form_class in _MONITORING_FORMS:
        assert "tenant" not in form_class.base_fields
        assert "tenant_id" not in form_class.base_fields


# ------------------------------------------------------------------ tenant scoping of every FK

def _monitoring_rule_data(**overrides):
    data = {"name": "Boundary", "module_slug": "core", "metric_key": "cpu_pct",
            "comparator": "gte", "warning_threshold": "90", "critical_threshold": "",
            "must_persist_seconds": "0", "frequency": "hourly", "severity": "warning",
            "category": "capacity", "no_data_action": "ignore", "service": "",
            "notification_rule": "", "notes": "", "is_active": "on"}
    data.update(overrides)
    return data


def _monitoring_event_data(**overrides):
    data = {"message": "Checkout latency", "state": "firing", "severity_at_fire": "warning",
            "rule": "", "service": "", "fired_at": "2026-09-26 10:00",
            "occurrence_count": "1", "evidence": "",
            "first_seen_at": "2026-09-26 10:00", "last_seen_at": "2026-09-26 10:00",
            "muted_until": "", "created_at": ""}
    data.update(overrides)
    return data


def test_monitoring_alert_rule_service_rejects_another_tenants_pk(tenant_a, tenant_b, _mon_svc):
    """The highest-value check in the suite: a foreign pk must not bind, and the own pk must."""
    mine = _mon_svc()
    theirs = ServiceComponent.objects.create(
        tenant=tenant_b, name="Globex service", code="g", kind="api")

    hostile = AlertRuleForm(data=_monitoring_rule_data(service=theirs.pk), tenant=tenant_a)
    assert not hostile.is_valid()
    assert "service" in hostile.errors

    control = AlertRuleForm(data=_monitoring_rule_data(service=mine.pk), tenant=tenant_a)
    assert control.is_valid(), control.errors


def test_monitoring_alert_rule_service_is_required(tenant_a):
    """A rule with no component cannot be shown on a board, so this FK is not nullable."""
    form = AlertRuleForm(data=_monitoring_rule_data(service=""), tenant=tenant_a)
    assert not form.is_valid()
    assert "service" in form.errors


def test_monitoring_alert_event_rule_rejects_another_tenants_pk(tenant_a, tenant_b):
    from decimal import Decimal
    def _rule(tenant, name):
        return AlertRule.objects.create(
            tenant=tenant, name=name, service=None, metric_key="cpu_pct", comparator="gte",
            warning_threshold=Decimal("90"), frequency="hourly", severity="warning",
            category="capacity", no_data_action="ignore")
    theirs, mine = _rule(tenant_b, "Globex rule"), _rule(tenant_a, "Acme rule")

    hostile = AlertEventForm(data=_monitoring_event_data(rule=theirs.pk), tenant=tenant_a)
    assert not hostile.is_valid()
    assert "rule" in hostile.errors

    control = AlertEventForm(data=_monitoring_event_data(rule=mine.pk), tenant=tenant_a)
    assert control.is_valid(), control.errors


def test_monitoring_incident_m2m_rejects_another_tenants_pk(tenant_a, tenant_b, _mon_svc):
    """`ModelMultipleChoiceField` must be narrowed too - a different class from the FK one."""
    mine = _mon_svc()
    theirs = ServiceComponent.objects.create(
        tenant=tenant_b, name="Globex service", code="g2", kind="api")
    base = {"title": "Cross-tenant probe", "service": "", "affected_services": [],
            "primary_alert": "", "incident_type": "incident", "status": "investigating",
            "impact": "minor", "public_note": "", "internal_note": "", "progress_pct": "",
            "started_at": "2026-09-26 10:00", "scheduled_for": "", "scheduled_until": "",
            "is_active": "on", "notes": ""}

    hostile = IncidentForm(data={**base, "affected_services": [theirs.pk]}, tenant=tenant_a)
    assert not hostile.is_valid()
    assert "affected_services" in hostile.errors

    control = IncidentForm(data={**base, "affected_services": [mine.pk]}, tenant=tenant_a)
    assert control.is_valid(), control.errors



# ------------------------------------------------------------------ the two save() overrides

def test_monitoring_service_form_stamps_last_status_at_when_the_status_changes(tenant_a,
                                                                              mon_component_payload):
    """Nobody probes this component, so the honest reading of 'last status change' is the last edit."""
    svc = ServiceComponentForm(data=mon_component_payload, tenant=tenant_a)
    assert svc.is_valid(), svc.errors
    created = svc.save()
    assert created.last_status_at is not None

    unchanged = ServiceComponentForm(data=mon_component_payload, instance=created, tenant=tenant_a)
    assert unchanged.is_valid(), unchanged.errors
    kept = unchanged.save()
    kept.refresh_from_db()
    assert kept.last_status_at == created.last_status_at, "an unrelated edit re-stamped the status"

    changed = ServiceComponentForm(
        data={**mon_component_payload, "current_status": "degraded"}, instance=created,
        tenant=tenant_a)
    assert changed.is_valid(), changed.errors
    moved = changed.save()
    moved.refresh_from_db()
    assert moved.last_status_at > kept.last_status_at


def test_monitoring_alert_event_form_snapshots_the_service_name(tenant_a, _mon_svc, _mon_event,
                                                               mon_rule_two_tier_a):
    """`service_label` is written by the FORM, not the view, so the admin path gets it too."""
    svc = _mon_svc()
    form = AlertEventForm(data=_monitoring_event_data(rule=mon_rule_two_tier_a.pk, service=svc.pk),
                          tenant=tenant_a)
    assert form.is_valid(), form.errors
    event = form.save()
    assert event.service_label == svc.name


def test_monitoring_clearing_the_service_preserves_the_label_snapshot(tenant_a, _mon_svc,
                                                                     _mon_event,
                                                                     mon_rule_two_tier_a):
    """THE I1 REGRESSION.

    `service_label` exists so the row still reads after the component is deleted. Overwriting it
    unconditionally meant that clearing the service - a legitimate correction, because the firing was
    logged against the wrong component - set it to "" and destroyed the very evidence the snapshot
    exists to preserve.
    """
    svc = _mon_svc()
    event = _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=svc)
    assert event.service_label == svc.name

    form = AlertEventForm(data=_monitoring_event_data(rule=mon_rule_two_tier_a.pk, service=""),
                          instance=event, tenant=tenant_a)
    assert form.is_valid(), form.errors
    cleared = form.save()
    cleared.refresh_from_db()
    assert cleared.service_id is None
    assert cleared.service_label == svc.name, "the snapshot was erased by detaching the service"


def test_monitoring_first_seen_at_is_backfilled_only_once(tenant_a, _mon_svc, _mon_event,
                                                          mon_rule_two_tier_a):
    """Back-filled from `fired_at` when empty, but a later edit must not rewrite the first sighting."""
    event = _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=_mon_svc(), first_seen_at=None)
    assert event.first_seen_at is None
    form = AlertEventForm(data=_monitoring_event_data(rule=mon_rule_two_tier_a.pk),
                          instance=event, tenant=tenant_a)
    assert form.is_valid(), form.errors
    first = form.save().first_seen_at
    assert first == event.fired_at

    form2 = AlertEventForm(data=_monitoring_event_data(rule=mon_rule_two_tier_a.pk,
                                                       message="Edited later"),
                           instance=event, tenant=tenant_a)
    assert form2.is_valid(), form2.errors
    assert form2.save().first_seen_at == first


# ------------------------------------------------------------------ the honest-claim help text

def test_monitoring_mute_help_text_says_nothing_enforces_it(tenant_a):
    """A user must not read a recorded mute as a suppression that is actually in force."""
    text = AlertEventForm.base_fields["muted_until"].help_text or ""
    assert "nothing enforces" in text.lower() or "recorded" in text.lower()


def test_monitoring_frequency_help_text_says_nothing_runs_it(tenant_a):
    text = AlertRuleForm.base_fields["frequency"].help_text or ""
    assert "nothing in naverp runs it" in text.lower()

# ------------------------------------------------------------------ the tier-order rule, as a form error

def test_monitoring_reversed_gte_tiers_are_a_form_error(tenant_a, _mon_svc):
    form = AlertRuleForm(data=_monitoring_rule_data(
        service=_mon_svc().pk, warning_threshold="100", critical_threshold="50"), tenant=tenant_a)
    assert not form.is_valid()
    assert "critical_threshold" in form.errors


def test_monitoring_two_tiers_on_an_unordered_comparator_are_a_form_error(tenant_a, _mon_svc):
    form = AlertRuleForm(data=_monitoring_rule_data(
        service=_mon_svc().pk, comparator="in",
        warning_threshold="1", critical_threshold="2"), tenant=tenant_a)
    assert not form.is_valid()
    assert "critical_threshold" in form.errors


def test_monitoring_a_valid_one_tier_rule_saves(tenant_a, _mon_svc, mon_rule_payload):
    form = AlertRuleForm(data={**mon_rule_payload, "service": _mon_svc().pk}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.tenant_id == tenant_a.id
