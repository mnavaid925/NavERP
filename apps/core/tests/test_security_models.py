"""0.18 Threat Protection - MODELS lane.

Every test is named `test_security_models_*` and every module-level helper `_security_models_*`,
so the next sub-module appending nearby cannot shadow them. The `sec_*` conftest prefix avoids
colliding with the pre-existing 0.9-era `test_security.py`.

This lane is the regression net for the two defects Phase 4 found, so those tests are named for
what they prove rather than for the method.
"""
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import (AlertRule, IpAccessRule, SecurityIncident, SecurityThreat,
                               SyncSchedule, VulnerabilityFinding)

pytestmark = pytest.mark.django_db

_NOT_A_FORM_FIELD = ("resolved_at", "resolved_by", "service_label", "tenant", "created_at")


# ------------------------------------------------------------------ L36: reuse by reference

def test_security_models_severity_is_reused_by_identity_not_copied():
    """`is`, not `==`. A pasted copy that is equal today forks the first time 0.17 adds a value."""
    assert SecurityThreat.SEVERITY_CHOICES is AlertRule.SEVERITY_CHOICES
    assert SecurityIncident.SEVERITY_CHOICES is AlertRule.SEVERITY_CHOICES
    assert VulnerabilityFinding.SCAN_FREQUENCY_CHOICES is SyncSchedule.FREQUENCY_CHOICES


def test_security_models_cvss_band_is_deliberately_not_the_alert_severity():
    """A CVSS band and a firing severity are DIFFERENT facts. This is the one place a second
    severity list is correct, called out so nobody "fixes" it by pointing the finding at the
    alert vocabulary."""
    assert VulnerabilityFinding.SEVERITY_BAND_CHOICES is not AlertRule.SEVERITY_CHOICES
    assert "critical" in dict(VulnerabilityFinding.SEVERITY_BAND_CHOICES)


def test_security_models_the_017_seam_is_untouched():
    """0.18 grew THROUGH the 0.17 enum value, not beside it: no new column on any 0.17 model.

    The list is 0.17's four models ONLY. `SecurityThreat` is an 0.18 model and legitimately owns
    `source_ip` and `mitre_technique` — including it here was my first draft's bug, and it is
    exactly the confusion the seam exists to prevent.
    """
    from apps.core.models import AlertEvent, Incident as MonitorIncident, ServiceComponent

    assert "security" in dict(AlertRule.CATEGORY_CHOICES)
    forbidden = {"threat_level", "ip_address", "cvss_score", "mitre_technique"}
    for model in (AlertRule, AlertEvent, MonitorIncident, ServiceComponent):
        assert not (forbidden & {f.name for f in model._meta.fields}), model.__name__


# ------------------------------------------------------------------ the C1 regression

def test_security_models_resolved_status_is_refused_not_crashed():
    """THE C1 REGRESSION. `resolved_at`/`resolved_by` are L22 system-set, so they are not on the
    form; Django's `add_error` RAISES `ValueError` for a key that is not a field, which turned
    choosing "Resolved" into a 500. The rule must therefore be keyed on `status`."""
    threat = SecurityThreat(title="x", threat_type="brute_force", status="resolved")
    with pytest.raises(ValidationError) as exc:
        threat.full_clean(exclude=["tenant"])
    assert "status" in exc.value.message_dict
    for name in _NOT_A_FORM_FIELD:
        assert name not in exc.value.message_dict, "keyed on a field the form does not have"


# ------------------------------------------------------------------ IpAccessRule

def test_security_models_iprule_requires_a_reason():
    rule = IpAccessRule(cidr="203.0.113.7", direction="deny", reason="   ", scope="workspace")
    with pytest.raises(ValidationError) as exc:
        rule.full_clean(exclude=["tenant"])
    assert "reason" in exc.value.message_dict


def test_security_models_iprule_scope_service_requires_a_service():
    rule = IpAccessRule(cidr="203.0.113.0/24", direction="allow", reason="office",
                        scope="service", service=None)
    with pytest.raises(ValidationError) as exc:
        rule.full_clean(exclude=["tenant"])
    assert "service" in exc.value.message_dict


def test_security_models_iprule_action_display_says_would_not_does():
    """A rule that claims to block when nothing blocks reads as a control that works. The default
    is `log` for the same reason `AlertEvent` has no payload column."""
    rule = IpAccessRule(cidr="203.0.113.7", direction="deny", action="block", reason="x")
    assert rule.action_display == "Would block"
    assert IpAccessRule._meta.get_field("action").default == "log"


def test_security_models_iprule_cidr_validator_rejects_nonsense():
    bad = IpAccessRule(cidr="not-an-address", direction="deny", reason="x")
    with pytest.raises(ValidationError):
        bad.full_clean(exclude=["tenant"])


# ------------------------------------------------------------------ SecurityThreat

def test_security_models_rate_limit_exceeded_must_name_the_policy():
    """A rate-limit finding that does not say WHICH limit was crossed is not evidence."""
    threat = SecurityThreat(title="x", threat_type="rate_limit_exceeded", status="new")
    with pytest.raises(ValidationError) as exc:
        threat.full_clean(exclude=["tenant"])
    assert "rate_limit_policy" in exc.value.message_dict


def test_security_models_threat_is_open_only_while_unsettled():
    """`false_positive` and `ignored` are DECISIONS, not open items."""
    assert SecurityThreat(title="x", status="new").is_open is True
    for settled in ("resolved", "false_positive", "ignored"):
        assert SecurityThreat(title="x", status=settled).is_open is False


# ------------------------------------------------------------------ VulnerabilityFinding

def test_security_models_risk_accepted_needs_a_reason_and_an_owner():
    finding = VulnerabilityFinding(title="x", advisory_id="A-1", finding_source="dependency",
                                   status="risk_accepted", accepted_reason="  ",
                                   first_seen_at=timezone.now())
    with pytest.raises(ValidationError) as exc:
        finding.full_clean(exclude=["tenant"])
    assert "accepted_reason" in exc.value.message_dict


def test_security_models_fixed_is_refused_when_no_fix_exists():
    """A finding with no fix is not a finding that is fixed."""
    finding = VulnerabilityFinding(title="x", advisory_id="A-1", finding_source="application",
                                   status="fixed", fix_available="no",
                                   first_seen_at=timezone.now())
    with pytest.raises(ValidationError) as exc:
        finding.full_clean(exclude=["tenant"])
    assert "fix_available" in exc.value.message_dict


def test_security_models_finding_due_on_is_never_defaulted_to_today():
    """NULL means "no remediation deadline has been set" - different from "due today"."""
    from datetime import timedelta
    blank = VulnerabilityFinding(title="x", advisory_id="A-1", finding_source="application",
                                 due_on=None)
    assert blank.days_overdue is None
    late = VulnerabilityFinding(title="x", advisory_id="A-1", finding_source="application",
                                status="open",
                                due_on=timezone.localdate() - timedelta(days=5))
    assert late.days_overdue == 5


# ------------------------------------------------------------------ SecurityIncident

def test_security_models_regulatory_deadline_is_derived_not_stored():
    """Art. 33(1)'s 72 hours from `discovered_at`. A @property, so the anchor and the deadline
    cannot drift; a stored column could."""
    from datetime import timedelta
    now = timezone.now()
    incident = SecurityIncident(title="x", status="detected", is_notifiable=None,
                                 subject_exemption="none", discovered_at=now)
    assert incident.regulatory_deadline == now + timedelta(hours=72)
    assert "regulatory_deadline" not in {f.name for f in incident._meta.fields}
    assert incident.deadline_display != "—"


def test_security_models_deadline_display_is_an_em_dash_without_an_anchor():
    incident = SecurityIncident(title="x", status="detected", is_notifiable=None,
                                 subject_exemption="none", discovered_at=None)
    assert incident.deadline_display == "—"
    assert incident.hours_remaining is None
    assert incident.is_overdue is False


def test_security_models_close_is_refused_while_notifiability_is_undecided():
    """You may not close a breach without having decided whether it is notifiable."""
    incident = SecurityIncident(title="x", status="closed", is_notifiable=None,
                                 subject_exemption="none", discovered_at=timezone.now())
    with pytest.raises(ValidationError) as exc:
        incident.full_clean(exclude=["tenant"])
    assert "is_notifiable" in exc.value.message_dict


def test_security_models_a_recorded_no_notification_needs_a_stated_exemption():
    incident = SecurityIncident(title="x", status="detected", is_notifiable=True,
                                 subjects_notified=False, subject_exemption="none",
                                 discovered_at=timezone.now())
    with pytest.raises(ValidationError) as exc:
        incident.full_clean(exclude=["tenant"])
    assert "subject_exemption" in exc.value.message_dict


# ------------------------------------------------------------------ tenancy

def test_security_models_every_model_is_tenant_scoped():
    for model in (IpAccessRule, SecurityThreat, VulnerabilityFinding, SecurityIncident):
        assert "tenant" in {f.name for f in model._meta.fields}


def test_security_models_both_tenants_are_isolated(tenant_a, tenant_b, sec_threat_new_a,
                                                 sec_threat_b):
    assert SecurityThreat.objects.filter(tenant=tenant_a).count() == 1
    assert SecurityThreat.objects.filter(tenant=tenant_b).count() == 1
    assert not SecurityThreat.objects.filter(tenant=tenant_a, title="Globex-only finding").exists()
