"""0.18 Threat Protection - VIEWS lane.

Follows `test_monitoring_views.py`: a module-level `_security_views_body` helper and the
`client_a` fixture already in the core conftest.

The two tests worth reading first are the ones that lock in the Phase 4 fixes:
`..._contain_is_refused_on_a_false_positive` and
`..._containment_button_appears_exactly_when_the_view_would_accept`.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

PAGES = [
    # The context keys are the REAL ones, read out of `views/Security.py` - not guessed. Pinning a
    # name the view does not pass is exactly the L7/L8 blank-region failure this lane exists to
    # catch, so the pinning has to be right in the test first.
    ("core:security_overview", ["notes", "threat_count", "open_threat_count", "incident_count"]),
    ("core:threat_board", ["notes", "open_threats", "state_rows", "severity_rows"]),
    ("core:vulnerability_board", ["notes", "band_rows", "status_rows", "overdue_count"]),
    ("core:breach_clock_board", ["notes", "undecided", "undecided_count", "overdue_count"]),
    ("core:brute_force_board", ["notes", "failed_addresses", "failed_total",
                                "mfa_challenged_total"]),
    ("core:ipaccessrule_list", ["object_list", "page_obj"]),
    ("core:ipaccessrule_create", ["form"]),
    ("core:securitythreat_list", ["object_list", "page_obj"]),
    ("core:securitythreat_create", ["form"]),
    ("core:vulnerabilityfinding_list", ["object_list", "page_obj"]),
    ("core:vulnerabilityfinding_create", ["form"]),
    ("core:securityincident_list", ["object_list", "page_obj"]),
    ("core:securityincident_create", ["form"]),
]

DESTRUCTIVE = [
    "core:securitythreat_triage", "core:securitythreat_resolve", "core:securitythreat_delete",
    "core:securityincident_contain", "core:securityincident_eradicate",
    "core:securityincident_recover", "core:securityincident_close",
    "core:securityincident_notify_authority", "core:securityincident_notify_subjects",
    "core:securityincident_delete",
]


def _security_views_body(response):
    return response.content.decode("utf-8")


# ------------------------------------------------------------------ rendering

@pytest.mark.parametrize("url_name,keys", PAGES)
def test_security_views_every_page_renders_with_its_pinned_context(client_a, url_name, keys):
    """Content, not just a 200: a mismatched context key returns 200 and renders blank (L7/L8)."""
    response = client_a.get(reverse(url_name))
    assert response.status_code == 200, url_name
    for key in keys:
        assert key in response.context, "%s did not pass %r" % (url_name, key)


@pytest.mark.parametrize("url_name,keys", PAGES)
def test_security_views_every_page_carries_the_honest_limit_prose(client_a, url_name, keys):
    """The L1 honesty rule: no page may imply NavERP detects, blocks or enforces anything.

    A distinctive PHRASE is asserted, not the whole constant - the constant is long prose, and
    HTML-escaping or line-wrapping in a template would make a full-string match brittle for no
    gain. The phrase below is stable and is the sentence that carries the whole claim.
    """
    phrase = "not a security system"
    body = _security_views_body(client_a.get(reverse(url_name)))
    assert phrase in body, "%s lacks the honest-limit prose" % url_name


@pytest.mark.parametrize("url_name,_keys", PAGES)
def test_security_views_no_template_comment_leaked(client_a, url_name, _keys):
    """L3: a `{# … #}` comment is single-line only; a multi-line one renders as visible text."""
    assert "{#" not in _security_views_body(client_a.get(reverse(url_name)))


@pytest.mark.parametrize("url_name,_keys", PAGES)
def test_security_views_junk_params_and_paging_stay_200(client_a, url_name, _keys):
    for qs in ("?q=zzzz&status=nope&page=2", "?page=99999", "?severity=&direction=%%%"):
        assert client_a.get(reverse(url_name) + qs).status_code == 200, url_name + qs


# ------------------------------------------------------------------ gates

@pytest.mark.parametrize("url_name", DESTRUCTIVE)
def test_security_views_destructive_verbs_answer_405_on_get(client_a, url_name, sec_threat_new_a,
                                                            sec_incident_open_a):
    """`@require_POST` must sit ABOVE the role gate, or a GET gets 403 instead of 405."""
    obj = sec_incident_open_a if "incident" in url_name else sec_threat_new_a
    assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 405


@pytest.mark.parametrize("url_name", DESTRUCTIVE)
def test_security_views_cross_tenant_post_is_404_and_writes_nothing(client_a, url_name,
                                                                    sec_threat_b, sec_incident_b):
    obj = sec_incident_b if "incident" in url_name else sec_threat_b
    # Snapshot only what BOTH models share. Neither `SecurityThreat` nor `SecurityIncident` has
    # `updated_at`, and `SecurityThreat` has no `contained_at` either — reading either here raised
    # AttributeError instead of testing the thing this lane exists to test.
    before = (obj.status, obj.created_at)
    assert client_a.post(reverse(url_name, args=[obj.pk])).status_code == 404
    obj.refresh_from_db()
    assert (obj.status, obj.created_at) == before, "a cross-tenant POST mutated the row"


def test_security_views_cross_tenant_detail_is_404(client_a, sec_threat_b):
    assert client_a.get(
        reverse("core:securitythreat_detail", args=[sec_threat_b.pk])).status_code == 404


def test_security_views_missing_pk_is_404(client_a):
    assert client_a.get(reverse("core:securitythreat_detail", args=[999999])).status_code == 404


# ------------------------------------------------------------------ the S1 / M7 regression

def test_security_views_contain_is_refused_on_a_false_positive(client_a, tenant_a):
    """A `false_positive` is a DECISION. Stamping a containment on it would rewrite that decision,
    and the guard that missed this was found by the Phase 4 security probe, not by reading."""
    from apps.core.models import SecurityIncident
    from django.utils import timezone
    inc = SecurityIncident.objects.create(
        tenant=tenant_a, title="False positive", status="false_positive", is_notifiable=True,
        subject_exemption="none", discovered_at=timezone.now())
    client_a.post(reverse("core:securityincident_contain", args=[inc.pk]))
    inc.refresh_from_db()
    assert inc.contained_at is None


def test_security_views_close_is_refused_on_a_false_positive(client_a, tenant_a):
    from apps.core.models import SecurityIncident
    from django.utils import timezone
    inc = SecurityIncident.objects.create(
        tenant=tenant_a, title="False positive", status="false_positive", is_notifiable=True,
        subject_exemption="none", discovered_at=timezone.now())
    client_a.post(reverse("core:securityincident_close", args=[inc.pk]))
    inc.refresh_from_db()
    assert inc.status == "false_positive"


# ------------------------------------------------------------------ the lifecycle

def test_security_views_threat_resolve_stamps_once_and_a_repeat_does_not_overwrite(
        client_a, sec_threat_new_a):
    client_a.post(reverse("core:securitythreat_triage", args=[sec_threat_new_a.pk]))
    sec_threat_new_a.refresh_from_db()
    # `triaged`, not `investigating` - the threat's own STATUS_CHOICES, read rather than assumed.
    assert sec_threat_new_a.status == "triaged"

    client_a.post(reverse("core:securitythreat_resolve", args=[sec_threat_new_a.pk]))
    sec_threat_new_a.refresh_from_db()
    assert sec_threat_new_a.status == "resolved"
    assert sec_threat_new_a.resolved_at is not None
    assert sec_threat_new_a.resolved_by_id is not None
    first = sec_threat_new_a.resolved_at

    client_a.post(reverse("core:securitythreat_resolve", args=[sec_threat_new_a.pk]))
    sec_threat_new_a.refresh_from_db()
    assert sec_threat_new_a.resolved_at == first, "a second resolve overwrote the first moment"


def test_security_views_incident_lifecycle_runs_end_to_end(client_a, sec_incident_open_a):
    inc = sec_incident_open_a
    for step, url, field in (
            ("contain", "core:securityincident_contain", "contained_at"),
            ("eradicate", "core:securityincident_eradicate", "eradicated_at"),
            ("recover", "core:securityincident_recover", "recovered_at")):
        client_a.post(reverse(url, args=[inc.pk]))
        inc.refresh_from_db()
        # The field names are spelled out rather than built from the step - `contain` maps to
        # `contained_at`, so `"%s_at" % step` produced `contain_at` and raised AttributeError.
        assert getattr(inc, field) is not None, "%s wrote no stamp" % field
    inc.status = "recovered"
    inc.is_notifiable = True
    inc.notifiable_reason = "Confirmed a breach."
    inc.save()
    client_a.post(reverse("core:securityincident_close", args=[inc.pk]))
    inc.refresh_from_db()
    assert inc.closed_at is not None


def test_security_views_notify_authority_needs_a_notifiable_incident(client_a, sec_incident_open_a):
    """`is_notifiable is None` means UNDECIDED, so the authority stamp must be refused."""
    client_a.post(reverse("core:securityincident_notify_authority",
                          args=[sec_incident_open_a.pk]))
    sec_incident_open_a.refresh_from_db()
    assert sec_incident_open_a.authority_notified_at is None


# ------------------------------------------------------------------ the frontend C1

@pytest.mark.parametrize("status,expect_button", [("detected", False), ("triaged", True),
                                                  ("contained", False)])
def test_security_views_containment_button_appears_exactly_when_the_view_would_accept(
        client_a, tenant_a, status, expect_button):
    """The template condition was INVERTED until Phase 4. The button must track the VIEW guard,
    or the first response step can never be recorded through the UI."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import SecurityIncident
    inc = SecurityIncident.objects.create(
        tenant=tenant_a, title="Button probe", status=status, is_notifiable=None,
        subject_exemption="none", discovered_at=timezone.now())
    if status == "contained":
        inc.contained_at = timezone.now() - timedelta(hours=1)
        inc.save()
    body = _security_views_body(client_a.get(
        reverse("core:securityincident_detail", args=[inc.pk])))
    assert ("Record containment" in body) is expect_button, (
        "status=%s: button presence disagrees with the view guard" % status)
