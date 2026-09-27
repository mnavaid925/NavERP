"""0.18 Threat Protection - SECURITY lane.

Distinct from the pre-existing 0.9-era `apps/core/tests/test_security.py`, which is a generic
CSRF/IDOR file. This one is 0.18's posture: the seeder zero rule, the honesty vocabulary, the
authorisation gates, and the L36 seams 0.18 must not have re-declared.
"""
import pytest
from django.urls import reverse

from apps.core.models import (AlertRule, IpAccessRule, RateLimitPolicy, SecurityIncident,
                               SecurityThreat, SyncSchedule, VulnerabilityFinding)

pytestmark = pytest.mark.django_db

PAGES = ["core:security_overview", "core:threat_board", "core:vulnerability_board",
         "core:breach_clock_board", "core:brute_force_board", "core:ipaccessrule_list",
         "core:securitythreat_list", "core:vulnerabilityfinding_list",
         "core:securityincident_list"]

# The one `advisory_id` the seeder is permitted to write. It is an EXAMPLE on purpose, so the
# advisory is unmistakably a sample rather than a real CVE someone must remediate.
_SEEDED_ADVISORY_ID = "EXAMPLE-2026-0001"


# ------------------------------------------------------------------ the L52 zero rule

def test_security_seeder_creates_no_threat_incident_or_rule(db, tenant_a):
    """THE L52 RULING. A fabricated breach is worse than an empty board, and a seeded incident
    would start a live 72-hour GDPR Art. 33 clock against a breach that never happened. The
    seeder's ONLY 0.18 row is one explicitly-labelled example advisory."""
    assert SecurityThreat.objects.filter(tenant=tenant_a).count() == 0
    assert SecurityIncident.objects.filter(tenant=tenant_a).count() == 0
    assert IpAccessRule.objects.filter(tenant=tenant_a).count() == 0


def test_security_the_only_seeded_row_is_the_labelled_example_advisory(db, tenant_a):
    """The seeder guards on the WHOLE table (`if not VulnerabilityFinding...exists()`), so in a
    bare test DB it writes nothing at all. That is correct L52 behaviour - the assertion here is
    that the row the real seeder DOES write is unmistakably an example, read from its own source."""
    import inspect

    from apps.core.management.commands.seed_core import Command
    src = inspect.getsource(Command._seed_security)
    assert "EXAMPLE-2026-0001" in src, "the seeded advisory id must say EXAMPLE"
    assert "Example: a known weakness" in src, "the seeded advisory must be titled as an example"
    # And it is guarded per-entity, never tenant-wide.
    assert "if not VulnerabilityFinding.objects.filter(tenant=tenant).exists()" in src
    # Nothing else is created anywhere in the seeder. Matched with a word boundary rather than a
    # bare substring - `VulnerabilityFinding.objects.create` CONTAINS "objects.create", so a
    # substring test would flag the one row L52 explicitly permits.
    import re
    for model in ("SecurityThreat", "SecurityIncident", "IpAccessRule"):
        assert not re.search(r"\b%s\s*\.\s*objects\s*\.\s*create" % model, src), (
            "%s is created by the seeder - L52 forbids it" % model)


# ------------------------------------------------------------------ L36 seams

def test_security_no_017_model_gained_a_column():
    """0.18 extended the 0.17 seams and added four tables. It did not touch 0.17's tables."""
    forbidden = {"threat_level", "ip_address", "cvss_score", "mitre_technique", "is_notifiable"}
    for model in (AlertRule, RateLimitPolicy, SyncSchedule):
        assert not (forbidden & {f.name for f in model._meta.fields}), model.__name__


def test_security_no_second_alert_table_was_created():
    """One alert table, one incident lifecycle, one board set - that is the L36 ruling. 0.18
    points at 0.17's rule and event through FKs rather than subclassing or shadowing them."""
    fields = {f.name for f in SecurityThreat._meta.fields}
    assert "rate_limit_policy" in fields, "the rate-limit spine was not reused"
    assert "alert_event" in fields, "the alert seam was not reused"
    assert "incident" in {f.name for f in SecurityIncident._meta.fields}


def test_security_the_rate_limit_spine_is_extended_not_replaced(db, tenant_a):
    """`RateLimitPolicy` (0.13) still owns rate-limit configuration; 0.18 only points at it.

    The field names are 0.13's own, read off the model rather than guessed: `max_requests` and
    `window`. There is no `scope`, `max_events`, `window_seconds` or `action`."""
    policy = RateLimitPolicy.objects.create(
        tenant=tenant_a, name="API limit", max_requests=100, window="hour", is_active=True)
    threat = SecurityThreat.objects.create(
        tenant=tenant_a, title="Rate limit exceeded", threat_type="rate_limit_exceeded",
        status="new", rate_limit_policy=policy)
    assert threat.rate_limit_policy_id == policy.pk
    assert RateLimitPolicy.objects.filter(pk=policy.pk).count() == 1


# ------------------------------------------------------------------ honesty (L1)

def test_security_no_page_claims_to_block_or_detect(client_a):
    """NavERP enforces nothing. A page asserting otherwise is a correctness bug, not a style one."""
    forbidden = ["traffic is blocked", "attack blocked", "threat blocked", "automatically blocked",
                 "is monitoring", "actively scanning", "protection is active"]
    for url_name in PAGES:
        body = client_a.get(reverse(url_name)).content.decode("utf-8").lower()
        for phrase in forbidden:
            assert phrase not in body, "%s claims %r" % (url_name, phrase)


def test_security_badge_green_never_appears_on_a_security_surface():
    """The zero rule as a test: `badge-green` would read as all-clear on a security board."""
    import os
    root = os.path.join("templates", "core")
    for folder in ("securitythreat", "ipaccessrule", "vulnerabilityfinding", "securityincident"):
        d = os.path.join(root, folder)
        for name in os.listdir(d):
            body = open(os.path.join(d, name), encoding="utf-8").read()
            assert "badge-green" not in body, "%s/%s uses badge-green" % (folder, name)
    for name in ("securityoverview.html", "threatboard.html", "vulnerabilityboard.html",
                 "breachclock.html", "bruteforceboard.html"):
        body = open(os.path.join(root, name), encoding="utf-8").read()
        assert "badge-green" not in body, name


# ------------------------------------------------------------------ authorisation

def test_security_every_018_view_requires_a_tenant_admin():
    """Read the decorators off the source rather than trusting that a probe covered them all."""
    import inspect

    from apps.core.views import Security as views
    public = [n for n, f in vars(views).items()
              if inspect.isfunction(f) and not n.startswith("_")
              and getattr(f, "__module__", "") == views.__name__]
    assert len(public) == 33, "the view count drifted: %d" % len(public)
    for name in public:
        assert "@tenant_admin_required" in inspect.getsource(getattr(views, name)), \
            "%s is not tenant-gated" % name


def test_security_destructive_verbs_put_require_post_above_the_role_gate():
    """Order matters: `@require_POST` below `@tenant_admin_required` turns a GET into 403, not 405."""
    import inspect

    from apps.core.views import Security as views
    for name in ("securitythreat_triage", "securitythreat_resolve", "securitythreat_delete",
                 "securityincident_contain", "securityincident_eradicate",
                 "securityincident_recover", "securityincident_close",
                 "securityincident_notify_authority", "securityincident_notify_subjects",
                 "securityincident_delete"):
        lines = [ln.strip() for ln in inspect.getsource(getattr(views, name)).splitlines()
                 if ln.strip().startswith("@")]
        assert lines.index("@require_POST") < lines.index("@tenant_admin_required"), \
            "%s has the decorators in the wrong order" % name


def test_security_anonymous_is_redirected_never_served(db):
    from django.test import Client
    c = Client()
    for url_name in PAGES:
        assert c.get(reverse(url_name)).status_code in (302, 403), \
            "%s served an anonymous visitor" % url_name


# ------------------------------------------------------------------ the 72h clock

def test_security_the_72_hour_clock_is_art33_not_an_invented_window():
    """A deadline that is not GDPR's own 72 hours is not a GDPR deadline."""
    from apps.core.views.Security import NOTIFICATION_WINDOW_HOURS
    assert NOTIFICATION_WINDOW_HOURS == 72
