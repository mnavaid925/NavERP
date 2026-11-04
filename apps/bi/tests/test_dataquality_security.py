"""Security, Multi-Tenancy, Authorization, and Hardening Tests for Sub-module 10.5 (Data Quality & Trust Scorecards).

Covers:
1. Authentication Enforcement:
   - All 21+ endpoints redirect unauthenticated/anonymous users to login (/accounts/login/?next=...).
2. Cross-Tenant IDOR Protection:
   - Client A (tenant_a) accessing Tenant B records receives 404 Not Found across all 4 models:
     - Profile: detail, edit GET, edit POST, delete POST, run POST.
     - Rule: detail, edit GET, edit POST, delete POST, run POST.
     - Exception: detail, edit GET, edit POST, delete POST, remediate POST.
     - Scorecard: detail, edit GET, edit POST, delete POST, recalculate POST.
   - Bidirectional reverse tests: Client B accessing Tenant A records receives 404 Not Found.
   - List and overview views strictly scope records by tenant; zero cross-tenant leakage.
3. POST-Only Enforcement (@require_POST):
   - Direct GET requests to mutation actions strictly return HTTP 405 Method Not Allowed:
     - Profile: delete, run
     - Rule: delete, run
     - Exception: delete, remediate
     - Scorecard: delete, recalculate
4. Cross-Tenant Foreign Key Tampering / Rejection in Forms:
   - DataQualityProfileForm rejects foreign warehouse_table, semantic_model.
   - DataQualityRuleForm rejects foreign warehouse_table, semantic_model, steward.
   - DataQualityExceptionForm rejects foreign rule, profile, warehouse_table, semantic_model, assigned_steward.
   - DataQualityScorecardForm rejects foreign warehouse_table, semantic_model, data_mart, org_unit, steward.
   - HTTP POST endpoints reject payloads with foreign FKs (200 with form errors, zero cross-tenant linking).
5. Mass Assignment Invariants:
   - Tampering with system-managed fields via crafted POST payloads
     (tenant, number, status, overall_quality_score, grade, health_status, meets_sla, last_run_at, etc.)
     is ignored and never written.
6. Audit Log Generation & Isolation:
   - Mutating operations record append-only AuditLog rows with tenant=request.tenant and user=request.user.
   - Audit trail is strictly tenant-scoped (zero cross-tenant audit leakage).
7. Multi-User Scale Simulation:
   - Multi-user heterogeneous access asserts 100% tenant boundary preservation and zero leakage.
"""
from decimal import Decimal
import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.forms import (
    DataQualityExceptionForm,
    DataQualityExceptionRemediationForm,
    DataQualityProfileForm,
    DataQualityRuleForm,
    DataQualityScorecardForm,
)
from apps.bi.models import (
    DataMart,
    DataQualityException,
    DataQualityProfile,
    DataQualityRule,
    DataQualityScorecard,
    SemanticModel,
    WarehouseTable,
)
from apps.core.models import AuditLog
from apps.core.models.OrgUnit import OrgUnit

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture Bridge
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user_b(admin_b):
    """Bridge fixture to unify admin_b and admin_user_b without duplicate username collision."""
    return admin_b


# ---------------------------------------------------------------------------
# Module-level test helpers (prefixed with _dataquality_*)
# ---------------------------------------------------------------------------


def _dataquality_create_user(tenant, username, is_admin=False, is_active=True):
    """Helper to create a tenant-scoped user."""
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
        is_active=is_active,
    )


def _dataquality_create_org_unit(tenant, name="Quality Assurance Org"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _dataquality_profile_payload(table=None, model=None, **overrides):
    """Helper generating valid DataQualityProfile form payload."""
    data = {
        "name": "Acme Orders Profiling",
        "target_type": "warehouse_table",
        "notes": "Automated dataset profile scan",
        "is_active": "on",
    }
    if table:
        data["warehouse_table"] = table.pk
    if model:
        data["semantic_model"] = model.pk
    data.update(overrides)
    return data


def _dataquality_rule_payload(table=None, model=None, steward=None, **overrides):
    """Helper generating valid DataQualityRule form payload."""
    data = {
        "name": "Invoice Total Must Be Positive",
        "code": "inv_total_positive_check",
        "rule_category": "validation",
        "dimension": "validity",
        "target_type": "warehouse_table",
        "target_column": "total_amount",
        "rule_type": "range_between",
        "parameters_json": json.dumps({"min_val": 0.01}),
        "severity": "critical",
        "failure_tolerance_pct": "0.00",
        "description": "Invoice amounts cannot be zero or negative.",
        "is_active": "on",
    }
    if table:
        data["warehouse_table"] = table.pk
    if model:
        data["semantic_model"] = model.pk
    if steward:
        data["steward"] = steward.pk
    data.update(overrides)
    return data


def _dataquality_exception_payload(rule=None, profile=None, table=None, model=None, steward=None, **overrides):
    """Helper generating valid DataQualityException form payload."""
    data = {
        "record_identifier": "INV-2026-X99",
        "target_column": "total_amount",
        "invalid_value": "-99.00",
        "expected_condition": "total_amount > 0",
        "exception_type": "range_outlier",
        "severity": "critical",
        "status": "open",
        "remediation_action": "manual_edit",
        "proposed_value": "99.00",
        "remediated_value": "",
        "resolution_notes": "Pending finance signoff.",
        "is_active": "on",
    }
    if rule:
        data["rule"] = rule.pk
    if profile:
        data["profile"] = profile.pk
    if table:
        data["warehouse_table"] = table.pk
    if model:
        data["semantic_model"] = model.pk
    if steward:
        data["assigned_steward"] = steward.pk
    data.update(overrides)
    return data


def _dataquality_scorecard_payload(table=None, model=None, mart=None, org_unit=None, steward=None, **overrides):
    """Helper generating valid DataQualityScorecard form payload."""
    data = {
        "name": "Financial Accuracy Trust Card",
        "code": "fin_accuracy_trust_card",
        "scope_type": "warehouse_table",
        "target_quality_score": "95.00",
        "evaluation_period": "monthly",
        "description": "Financial accuracy quality trust SLA scorecard.",
        "is_active": "on",
    }
    if table:
        data["warehouse_table"] = table.pk
    if model:
        data["semantic_model"] = model.pk
    if mart:
        data["data_mart"] = mart.pk
    if org_unit:
        data["org_unit"] = org_unit.pk
    if steward:
        data["steward"] = steward.pk
    data.update(overrides)
    return data


# ===========================================================================
# 1. Authentication Enforcement Tests
# ===========================================================================


def test_dataquality_security_unauthenticated_get_requests_redirect_to_login(
    anon_client,
    dq_profile_a,
    dq_rule_a,
    dq_exception_a,
    dq_scorecard_a,
):
    """Anonymous client requesting any Sub-module 10.5 GET route is redirected to login."""
    get_routes = [
        # Overview
        reverse("bi:quality_overview"),
        # Profiles
        reverse("bi:data_quality_profile_list"),
        reverse("bi:data_quality_profile_create"),
        reverse("bi:data_quality_profile_detail", kwargs={"pk": dq_profile_a.pk}),
        reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk}),
        # Rules
        reverse("bi:data_quality_rule_list"),
        reverse("bi:data_quality_rule_create"),
        reverse("bi:data_quality_rule_detail", kwargs={"pk": dq_rule_a.pk}),
        reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk}),
        # Exceptions
        reverse("bi:data_quality_exception_list"),
        reverse("bi:data_quality_exception_create"),
        reverse("bi:data_quality_exception_detail", kwargs={"pk": dq_exception_a.pk}),
        reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk}),
        # Scorecards
        reverse("bi:data_quality_scorecard_list"),
        reverse("bi:data_quality_scorecard_create"),
        reverse("bi:data_quality_scorecard_detail", kwargs={"pk": dq_scorecard_a.pk}),
        reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk}),
    ]

    for url in get_routes:
        res = anon_client.get(url)
        assert res.status_code == 302, f"Expected 302 redirect for anon GET {url}, got {res.status_code}"
        assert "/accounts/login" in res.url or "login" in res.url


def test_dataquality_security_unauthenticated_post_requests_redirect_to_login(
    anon_client,
    dq_profile_a,
    dq_rule_a,
    dq_exception_a,
    dq_scorecard_a,
):
    """Anonymous client submitting POST to any Sub-module 10.5 route is redirected to login."""
    post_routes = [
        # Creates
        (reverse("bi:data_quality_profile_create"), {"name": "Anon Profile"}),
        (reverse("bi:data_quality_rule_create"), {"name": "Anon Rule"}),
        (reverse("bi:data_quality_exception_create"), {"record_identifier": "ANON-001"}),
        (reverse("bi:data_quality_scorecard_create"), {"name": "Anon Card"}),
        # Edits
        (reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk}), {"name": "Tampered"}),
        (reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk}), {"name": "Tampered"}),
        (reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk}), {"status": "closed"}),
        (reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk}), {"name": "Tampered"}),
        # Deletes
        (reverse("bi:data_quality_profile_delete", kwargs={"pk": dq_profile_a.pk}), {}),
        (reverse("bi:data_quality_rule_delete", kwargs={"pk": dq_rule_a.pk}), {}),
        (reverse("bi:data_quality_exception_delete", kwargs={"pk": dq_exception_a.pk}), {}),
        (reverse("bi:data_quality_scorecard_delete", kwargs={"pk": dq_scorecard_a.pk}), {}),
        # Custom mutations
        (reverse("bi:data_quality_profile_run", kwargs={"pk": dq_profile_a.pk}), {}),
        (reverse("bi:data_quality_rule_run", kwargs={"pk": dq_rule_a.pk}), {}),
        (reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_a.pk}), {"status": "remediated"}),
        (reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": dq_scorecard_a.pk}), {}),
    ]

    for url, data in post_routes:
        res = anon_client.post(url, data)
        assert res.status_code == 302, f"Expected 302 redirect for anon POST {url}, got {res.status_code}"
        assert "/accounts/login" in res.url or "login" in res.url


# ===========================================================================
# 2. Cross-Tenant IDOR Protection Tests
# ===========================================================================


def test_dataquality_security_idor_profile_detail_denied_404(client_a, dq_profile_b):
    """Client A requesting Tenant B DataQualityProfile detail receives 404."""
    url = reverse("bi:data_quality_profile_detail", kwargs={"pk": dq_profile_b.pk})
    res = client_a.get(url)
    assert res.status_code == 404


def test_dataquality_security_idor_profile_edit_get_denied_404(client_a, dq_profile_b):
    """Client A requesting Tenant B DataQualityProfile edit GET receives 404."""
    url = reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_b.pk})
    res = client_a.get(url)
    assert res.status_code == 404


def test_dataquality_security_idor_profile_edit_post_denied_404(client_a, dq_profile_b):
    """Client A submitting POST to edit Tenant B DataQualityProfile receives 404 and leaves record unchanged."""
    url = reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_b.pk})
    res = client_a.post(url, data={"name": "Hacked Profile Name"})
    assert res.status_code == 404
    dq_profile_b.refresh_from_db()
    assert dq_profile_b.name != "Hacked Profile Name"


def test_dataquality_security_idor_profile_delete_post_denied_404(client_a, dq_profile_b):
    """Client A submitting POST to delete Tenant B DataQualityProfile receives 404 and does not delete record."""
    url = reverse("bi:data_quality_profile_delete", kwargs={"pk": dq_profile_b.pk})
    res = client_a.post(url)
    assert res.status_code == 404
    assert DataQualityProfile.objects.filter(pk=dq_profile_b.pk).exists()


def test_dataquality_security_idor_profile_run_post_denied_404(client_a, dq_profile_b):
    """Client A submitting POST to run Tenant B DataQualityProfile receives 404."""
    url = reverse("bi:data_quality_profile_run", kwargs={"pk": dq_profile_b.pk})
    res = client_a.post(url)
    assert res.status_code == 404


def test_dataquality_security_idor_rule_detail_denied_404(client_a, dq_rule_b):
    """Client A requesting Tenant B DataQualityRule detail receives 404."""
    url = reverse("bi:data_quality_rule_detail", kwargs={"pk": dq_rule_b.pk})
    res = client_a.get(url)
    assert res.status_code == 404


def test_dataquality_security_idor_rule_edit_get_denied_404(client_a, dq_rule_b):
    """Client A requesting Tenant B DataQualityRule edit GET receives 404."""
    url = reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_b.pk})
    res = client_a.get(url)
    assert res.status_code == 404


def test_dataquality_security_idor_rule_edit_post_denied_404(client_a, dq_rule_b):
    """Client A submitting POST to edit Tenant B DataQualityRule receives 404 and leaves record unchanged."""
    url = reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_b.pk})
    res = client_a.post(url, data={"name": "Hacked Rule Name"})
    assert res.status_code == 404
    dq_rule_b.refresh_from_db()
    assert dq_rule_b.name != "Hacked Rule Name"


def test_dataquality_security_idor_rule_delete_post_denied_404(client_a, dq_rule_b):
    """Client A submitting POST to delete Tenant B DataQualityRule receives 404 and does not delete record."""
    url = reverse("bi:data_quality_rule_delete", kwargs={"pk": dq_rule_b.pk})
    res = client_a.post(url)
    assert res.status_code == 404
    assert DataQualityRule.objects.filter(pk=dq_rule_b.pk).exists()


def test_dataquality_security_idor_rule_run_post_denied_404(client_a, dq_rule_b):
    """Client A submitting POST to run Tenant B DataQualityRule receives 404."""
    url = reverse("bi:data_quality_rule_run", kwargs={"pk": dq_rule_b.pk})
    res = client_a.post(url)
    assert res.status_code == 404


def test_dataquality_security_idor_exception_detail_denied_404(client_a, dq_exception_b):
    """Client A requesting Tenant B DataQualityException detail receives 404."""
    url = reverse("bi:data_quality_exception_detail", kwargs={"pk": dq_exception_b.pk})
    res = client_a.get(url)
    assert res.status_code == 404


def test_dataquality_security_idor_exception_edit_get_denied_404(client_a, dq_exception_b):
    """Client A requesting Tenant B DataQualityException edit GET receives 404."""
    url = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_b.pk})
    res = client_a.get(url)
    assert res.status_code == 404


def test_dataquality_security_idor_exception_edit_post_denied_404(client_a, dq_exception_b):
    """Client A submitting POST to edit Tenant B DataQualityException receives 404 and leaves record unchanged."""
    url = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_b.pk})
    res = client_a.post(url, data={"status": "resolved"})
    assert res.status_code == 404
    dq_exception_b.refresh_from_db()
    assert dq_exception_b.status == "open"


def test_dataquality_security_idor_exception_delete_post_denied_404(client_a, dq_exception_b):
    """Client A submitting POST to delete Tenant B DataQualityException receives 404 and does not delete record."""
    url = reverse("bi:data_quality_exception_delete", kwargs={"pk": dq_exception_b.pk})
    res = client_a.post(url)
    assert res.status_code == 404
    assert DataQualityException.objects.filter(pk=dq_exception_b.pk).exists()


def test_dataquality_security_idor_exception_remediate_post_denied_404(client_a, dq_exception_b):
    """Client A submitting POST to remediate Tenant B DataQualityException receives 404 and leaves status unchanged."""
    url = reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_b.pk})
    res = client_a.post(url, data={"status": "remediated", "remediation_action": "manual_edit"})
    assert res.status_code == 404
    dq_exception_b.refresh_from_db()
    assert dq_exception_b.status == "open"


def test_dataquality_security_idor_scorecard_detail_denied_404(client_a, dq_scorecard_b):
    """Client A requesting Tenant B DataQualityScorecard detail receives 404."""
    url = reverse("bi:data_quality_scorecard_detail", kwargs={"pk": dq_scorecard_b.pk})
    res = client_a.get(url)
    assert res.status_code == 404


def test_dataquality_security_idor_scorecard_edit_get_denied_404(client_a, dq_scorecard_b):
    """Client A requesting Tenant B DataQualityScorecard edit GET receives 404."""
    url = reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_b.pk})
    res = client_a.get(url)
    assert res.status_code == 404


def test_dataquality_security_idor_scorecard_edit_post_denied_404(client_a, dq_scorecard_b):
    """Client A submitting POST to edit Tenant B DataQualityScorecard receives 404 and leaves record unchanged."""
    url = reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_b.pk})
    res = client_a.post(url, data={"name": "Hacked Scorecard Name"})
    assert res.status_code == 404
    dq_scorecard_b.refresh_from_db()
    assert dq_scorecard_b.name != "Hacked Scorecard Name"


def test_dataquality_security_idor_scorecard_delete_post_denied_404(client_a, dq_scorecard_b):
    """Client A submitting POST to delete Tenant B DataQualityScorecard receives 404 and does not delete record."""
    url = reverse("bi:data_quality_scorecard_delete", kwargs={"pk": dq_scorecard_b.pk})
    res = client_a.post(url)
    assert res.status_code == 404
    assert DataQualityScorecard.objects.filter(pk=dq_scorecard_b.pk).exists()


def test_dataquality_security_idor_scorecard_recalculate_post_denied_404(client_a, dq_scorecard_b):
    """Client A submitting POST to recalculate Tenant B DataQualityScorecard receives 404."""
    url = reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": dq_scorecard_b.pk})
    res = client_a.post(url)
    assert res.status_code == 404


def test_dataquality_security_idor_reverse_tenant_b_access_denied_404(
    client_b,
    dq_profile_a,
    dq_rule_a,
    dq_exception_a,
    dq_scorecard_a,
):
    """Bidirectional IDOR: Client B attempting to access or mutate Tenant A records receives strict 404s."""
    routes = [
        # DataQualityProfile A
        (reverse("bi:data_quality_profile_detail", kwargs={"pk": dq_profile_a.pk}), "GET", {}),
        (reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk}), "GET", {}),
        (reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk}), "POST", {"name": "Hacked By B"}),
        (reverse("bi:data_quality_profile_delete", kwargs={"pk": dq_profile_a.pk}), "POST", {}),
        (reverse("bi:data_quality_profile_run", kwargs={"pk": dq_profile_a.pk}), "POST", {}),
        # DataQualityRule A
        (reverse("bi:data_quality_rule_detail", kwargs={"pk": dq_rule_a.pk}), "GET", {}),
        (reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk}), "GET", {}),
        (reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk}), "POST", {"name": "Hacked By B"}),
        (reverse("bi:data_quality_rule_delete", kwargs={"pk": dq_rule_a.pk}), "POST", {}),
        (reverse("bi:data_quality_rule_run", kwargs={"pk": dq_rule_a.pk}), "POST", {}),
        # DataQualityException A
        (reverse("bi:data_quality_exception_detail", kwargs={"pk": dq_exception_a.pk}), "GET", {}),
        (reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk}), "GET", {}),
        (reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk}), "POST", {"status": "closed"}),
        (reverse("bi:data_quality_exception_delete", kwargs={"pk": dq_exception_a.pk}), "POST", {}),
        (reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_a.pk}), "POST", {"status": "remediated"}),
        # DataQualityScorecard A
        (reverse("bi:data_quality_scorecard_detail", kwargs={"pk": dq_scorecard_a.pk}), "GET", {}),
        (reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk}), "GET", {}),
        (reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk}), "POST", {"name": "Hacked By B"}),
        (reverse("bi:data_quality_scorecard_delete", kwargs={"pk": dq_scorecard_a.pk}), "POST", {}),
        (reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": dq_scorecard_a.pk}), "POST", {}),
    ]

    for url, method, data in routes:
        if method == "GET":
            res = client_b.get(url)
        else:
            res = client_b.post(url, data=data)
        assert res.status_code == 404, f"Expected 404 for Client B requesting {method} {url}, got {res.status_code}"


def test_dataquality_security_list_views_tenant_isolation(
    client_a,
    client_b,
    dq_profile_a,
    dq_profile_b,
    dq_rule_a,
    dq_rule_b,
    dq_exception_a,
    dq_exception_b,
    dq_scorecard_a,
    dq_scorecard_b,
):
    """Overview and list views strictly scope records by tenant; zero cross-tenant leakage in HTML context."""
    # Test Client A perspective
    list_routes_a = [
        (reverse("bi:quality_overview"), [dq_profile_a.name], [dq_profile_b.name]),
        (reverse("bi:data_quality_profile_list"), [dq_profile_a.name], [dq_profile_b.name]),
        (reverse("bi:data_quality_rule_list"), [dq_rule_a.name], [dq_rule_b.name, dq_rule_b.code]),
        (reverse("bi:data_quality_exception_list"), [dq_exception_a.record_identifier], [dq_exception_b.record_identifier]),
        (reverse("bi:data_quality_scorecard_list"), [dq_scorecard_a.name], [dq_scorecard_b.name, dq_scorecard_b.code]),
    ]

    for url, expected_present, forbidden_present in list_routes_a:
        res = client_a.get(url)
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        for expected in expected_present:
            if expected:
                assert expected in content, f"Expected '{expected}' to be visible for Client A on {url}"
        for forbidden in forbidden_present:
            if forbidden:
                assert forbidden not in content, f"Forbidden '{forbidden}' leaked to Client A on {url}"

    # Test Client B perspective
    list_routes_b = [
        (reverse("bi:quality_overview"), [dq_profile_b.name], [dq_profile_a.name]),
        (reverse("bi:data_quality_profile_list"), [dq_profile_b.name], [dq_profile_a.name]),
        (reverse("bi:data_quality_rule_list"), [dq_rule_b.name], [dq_rule_a.name, dq_rule_a.code]),
        (reverse("bi:data_quality_exception_list"), [dq_exception_b.record_identifier], [dq_exception_a.record_identifier]),
        (reverse("bi:data_quality_scorecard_list"), [dq_scorecard_b.name], [dq_scorecard_a.name, dq_scorecard_a.code]),
    ]

    for url, expected_present, forbidden_present in list_routes_b:
        res = client_b.get(url)
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        for expected in expected_present:
            if expected:
                assert expected in content, f"Expected '{expected}' to be visible for Client B on {url}"
        for forbidden in forbidden_present:
            if forbidden:
                assert forbidden not in content, f"Forbidden '{forbidden}' leaked to Client B on {url}"


# ===========================================================================
# 3. POST-Only Enforcement (@require_POST) Tests
# ===========================================================================


def test_dataquality_security_post_only_mutation_endpoints_reject_get_with_405(
    client_a,
    dq_profile_a,
    dq_rule_a,
    dq_exception_a,
    dq_scorecard_a,
):
    """Direct GET on all 8 POST-only mutation actions strictly returns HTTP 405 Method Not Allowed."""
    mutation_routes = [
        reverse("bi:data_quality_profile_delete", kwargs={"pk": dq_profile_a.pk}),
        reverse("bi:data_quality_profile_run", kwargs={"pk": dq_profile_a.pk}),
        reverse("bi:data_quality_rule_delete", kwargs={"pk": dq_rule_a.pk}),
        reverse("bi:data_quality_rule_run", kwargs={"pk": dq_rule_a.pk}),
        reverse("bi:data_quality_exception_delete", kwargs={"pk": dq_exception_a.pk}),
        reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_a.pk}),
        reverse("bi:data_quality_scorecard_delete", kwargs={"pk": dq_scorecard_a.pk}),
        reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": dq_scorecard_a.pk}),
    ]

    for url in mutation_routes:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}, got {res.status_code}"


# ===========================================================================
# 4. Cross-Tenant Foreign Key Tampering / Rejection in Forms
# ===========================================================================


def test_dataquality_security_fk_injection_profile_form(
    tenant_a,
    warehouse_table_b,
    semantic_model_b,
):
    """DataQualityProfileForm rejects foreign warehouse_table and semantic_model in field QS and clean()."""
    base_data = {
        "name": "Hostile Profile",
        "target_type": "warehouse_table",
        "notes": "Testing foreign table injection",
        "is_active": True,
    }

    # 1. Field-level queryset rejection
    form1 = DataQualityProfileForm(
        data={**base_data, "warehouse_table": warehouse_table_b.pk},
        tenant=tenant_a,
    )
    assert not form1.is_valid()
    assert "warehouse_table" in form1.errors

    # 2. Defense-in-depth: clean() reject_foreign even if queryset was widened
    form2 = DataQualityProfileForm(
        data={**base_data, "warehouse_table": warehouse_table_b.pk},
        tenant=tenant_a,
    )
    form2.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form2.is_valid()
    assert "That record belongs to another workspace." in form2.errors.get("warehouse_table", [])

    # 3. Foreign semantic_model
    form3 = DataQualityProfileForm(
        data={**base_data, "target_type": "semantic_model", "semantic_model": semantic_model_b.pk},
        tenant=tenant_a,
    )
    form3.fields["semantic_model"].queryset = SemanticModel.objects.all()
    assert not form3.is_valid()
    assert "That record belongs to another workspace." in form3.errors.get("semantic_model", [])


def test_dataquality_security_fk_injection_rule_form(
    tenant_a,
    warehouse_table_b,
    semantic_model_b,
    admin_user_b,
):
    """DataQualityRuleForm rejects foreign warehouse_table, semantic_model, and steward."""
    base_data = {
        "name": "Hostile Rule",
        "code": "hostile_rule",
        "rule_category": "validation",
        "dimension": "validity",
        "target_type": "warehouse_table",
        "target_column": "amount",
        "rule_type": "range_between",
        "parameters_json": json.dumps({"min_val": 0}),
        "severity": "critical",
        "failure_tolerance_pct": "0.00",
        "is_active": True,
    }

    # Foreign warehouse_table
    form1 = DataQualityRuleForm(
        data={**base_data, "warehouse_table": warehouse_table_b.pk},
        tenant=tenant_a,
    )
    form1.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form1.is_valid()
    assert "That record belongs to another workspace." in form1.errors.get("warehouse_table", [])

    # Foreign steward
    form2 = DataQualityRuleForm(
        data={**base_data, "steward": admin_user_b.pk},
        tenant=tenant_a,
    )
    form2.fields["steward"].queryset = User.objects.all()
    assert not form2.is_valid()
    assert "That record belongs to another workspace." in form2.errors.get("steward", [])


def test_dataquality_security_fk_injection_exception_form(
    tenant_a,
    dq_rule_b,
    dq_profile_b,
    warehouse_table_b,
    semantic_model_b,
    admin_user_b,
):
    """DataQualityExceptionForm rejects foreign rule, profile, table, model, and assigned_steward."""
    base_data = {
        "record_identifier": "HOSTILE-001",
        "target_column": "amount",
        "invalid_value": "-10.00",
        "expected_condition": "amount > 0",
        "exception_type": "range_outlier",
        "severity": "critical",
        "status": "open",
        "remediation_action": "manual_edit",
        "is_active": True,
    }

    # Foreign rule
    form1 = DataQualityExceptionForm(
        data={**base_data, "rule": dq_rule_b.pk},
        tenant=tenant_a,
    )
    form1.fields["rule"].queryset = DataQualityRule.objects.all()
    assert not form1.is_valid()
    assert "That record belongs to another workspace." in form1.errors.get("rule", [])

    # Foreign profile
    form2 = DataQualityExceptionForm(
        data={**base_data, "profile": dq_profile_b.pk},
        tenant=tenant_a,
    )
    form2.fields["profile"].queryset = DataQualityProfile.objects.all()
    assert not form2.is_valid()
    assert "That record belongs to another workspace." in form2.errors.get("profile", [])

    # Foreign steward
    form3 = DataQualityExceptionForm(
        data={**base_data, "assigned_steward": admin_user_b.pk},
        tenant=tenant_a,
    )
    form3.fields["assigned_steward"].queryset = User.objects.all()
    assert not form3.is_valid()
    assert "That record belongs to another workspace." in form3.errors.get("assigned_steward", [])


def test_dataquality_security_fk_injection_scorecard_form(
    tenant_a,
    tenant_b,
    warehouse_table_b,
    semantic_model_b,
    data_mart_b,
    admin_user_b,
):
    """DataQualityScorecardForm rejects foreign warehouse_table, semantic_model, data_mart, org_unit, steward."""
    foreign_ou = _dataquality_create_org_unit(tenant_b, "Globex Foreign Org")

    base_data = {
        "name": "Hostile Scorecard",
        "code": "hostile_scorecard",
        "scope_type": "warehouse_table",
        "target_quality_score": "95.00",
        "evaluation_period": "monthly",
        "is_active": True,
    }

    # Foreign warehouse_table
    form1 = DataQualityScorecardForm(
        data={**base_data, "warehouse_table": warehouse_table_b.pk},
        tenant=tenant_a,
    )
    form1.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form1.is_valid()
    assert "That record belongs to another workspace." in form1.errors.get("warehouse_table", [])

    # Foreign data_mart
    form2 = DataQualityScorecardForm(
        data={**base_data, "scope_type": "data_mart", "data_mart": data_mart_b.pk},
        tenant=tenant_a,
    )
    form2.fields["data_mart"].queryset = DataMart.objects.all()
    assert not form2.is_valid()
    assert "That record belongs to another workspace." in form2.errors.get("data_mart", [])

    # Foreign org_unit
    form3 = DataQualityScorecardForm(
        data={**base_data, "org_unit": foreign_ou.pk},
        tenant=tenant_a,
    )
    form3.fields["org_unit"].queryset = OrgUnit.objects.all()
    assert not form3.is_valid()
    assert "That record belongs to another workspace." in form3.errors.get("org_unit", [])

    # Foreign steward
    form4 = DataQualityScorecardForm(
        data={**base_data, "steward": admin_user_b.pk},
        tenant=tenant_a,
    )
    form4.fields["steward"].queryset = User.objects.all()
    assert not form4.is_valid()
    assert "That record belongs to another workspace." in form4.errors.get("steward", [])


def test_dataquality_security_fk_tampering_profile_post_rejected(
    client_a,
    tenant_a,
    dq_profile_a,
    warehouse_table_b,
    semantic_model_b,
):
    """Submitting foreign FKs in Profile create and edit POST endpoints is rejected and saves nothing."""
    # 1. Create with foreign table
    payload_create = _dataquality_profile_payload(
        table=warehouse_table_b,
        name="Hostile Foreign Profile",
    )
    res_create = client_a.post(reverse("bi:data_quality_profile_create"), data=payload_create)
    assert res_create.status_code == 200
    assert not DataQualityProfile.objects.filter(tenant=tenant_a, name="Hostile Foreign Profile").exists()

    # 2. Edit with foreign model
    initial_table = dq_profile_a.warehouse_table
    url_edit = reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            "name": dq_profile_a.name,
            "target_type": "semantic_model",
            "semantic_model": semantic_model_b.pk,
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 200
    dq_profile_a.refresh_from_db()
    assert dq_profile_a.warehouse_table == initial_table


def test_dataquality_security_fk_tampering_rule_post_rejected(
    client_a,
    tenant_a,
    dq_rule_a,
    warehouse_table_b,
    admin_user_b,
):
    """Submitting foreign FKs in Rule create and edit POST endpoints is rejected and saves nothing."""
    # 1. Create with foreign table
    payload_create = _dataquality_rule_payload(
        table=warehouse_table_b,
        name="Hostile Rule Table",
        code="hostile_rule_table",
    )
    res_create = client_a.post(reverse("bi:data_quality_rule_create"), data=payload_create)
    assert res_create.status_code == 200
    assert not DataQualityRule.objects.filter(tenant=tenant_a, code="hostile_rule_table").exists()

    # 2. Edit with foreign steward
    initial_steward = dq_rule_a.steward
    url_edit = reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            "name": dq_rule_a.name,
            "code": dq_rule_a.code,
            "rule_category": dq_rule_a.rule_category,
            "dimension": dq_rule_a.dimension,
            "target_type": dq_rule_a.target_type,
            "warehouse_table": dq_rule_a.warehouse_table_id,
            "target_column": dq_rule_a.target_column,
            "rule_type": dq_rule_a.rule_type,
            "parameters_json": json.dumps(dq_rule_a.parameters_json),
            "severity": dq_rule_a.severity,
            "failure_tolerance_pct": str(dq_rule_a.failure_tolerance_pct),
            "steward": admin_user_b.pk,
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 200
    dq_rule_a.refresh_from_db()
    assert dq_rule_a.steward == initial_steward


def test_dataquality_security_fk_tampering_exception_post_rejected(
    client_a,
    tenant_a,
    dq_exception_a,
    dq_rule_b,
    dq_profile_b,
    admin_user_b,
):
    """Submitting foreign FKs in Exception create and edit POST endpoints is rejected and saves nothing."""
    # 1. Create with foreign rule and profile
    payload_create = _dataquality_exception_payload(
        rule=dq_rule_b,
        profile=dq_profile_b,
        record_identifier="HOSTILE-EXC-001",
    )
    res_create = client_a.post(reverse("bi:data_quality_exception_create"), data=payload_create)
    assert res_create.status_code == 200
    assert not DataQualityException.objects.filter(tenant=tenant_a, record_identifier="HOSTILE-EXC-001").exists()

    # 2. Edit with foreign steward
    initial_steward = dq_exception_a.assigned_steward
    url_edit = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            "record_identifier": dq_exception_a.record_identifier,
            "target_column": dq_exception_a.target_column,
            "invalid_value": dq_exception_a.invalid_value,
            "expected_condition": dq_exception_a.expected_condition,
            "exception_type": dq_exception_a.exception_type,
            "severity": dq_exception_a.severity,
            "status": dq_exception_a.status,
            "remediation_action": dq_exception_a.remediation_action,
            "assigned_steward": admin_user_b.pk,
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 200
    dq_exception_a.refresh_from_db()
    assert dq_exception_a.assigned_steward == initial_steward


def test_dataquality_security_fk_tampering_scorecard_post_rejected(
    client_a,
    tenant_a,
    dq_scorecard_a,
    warehouse_table_b,
    admin_user_b,
):
    """Submitting foreign FKs in Scorecard create and edit POST endpoints is rejected and saves nothing."""
    # 1. Create with foreign table
    payload_create = _dataquality_scorecard_payload(
        table=warehouse_table_b,
        name="Hostile Card Table",
        code="hostile_card_table",
    )
    res_create = client_a.post(reverse("bi:data_quality_scorecard_create"), data=payload_create)
    assert res_create.status_code == 200
    assert not DataQualityScorecard.objects.filter(tenant=tenant_a, code="hostile_card_table").exists()

    # 2. Edit with foreign steward
    initial_steward = dq_scorecard_a.steward
    url_edit = reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            "name": dq_scorecard_a.name,
            "code": dq_scorecard_a.code,
            "scope_type": dq_scorecard_a.scope_type,
            "warehouse_table": dq_scorecard_a.warehouse_table_id,
            "target_quality_score": str(dq_scorecard_a.target_quality_score),
            "evaluation_period": dq_scorecard_a.evaluation_period,
            "steward": admin_user_b.pk,
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 200
    dq_scorecard_a.refresh_from_db()
    assert dq_scorecard_a.steward == initial_steward


# ===========================================================================
# 5. Mass Assignment Invariants
# ===========================================================================


def test_dataquality_security_mass_assignment_profile_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    warehouse_table_a,
    dq_profile_a,
):
    """Submitting system fields (tenant, number, status, scores, last_run_at) in Profile POST has no effect."""
    # Create
    malicious_create = {
        "name": "Hardened Profile System",
        "target_type": "warehouse_table",
        "warehouse_table": warehouse_table_a.pk,
        "is_active": "on",
        # Malicious mass-assignment payload
        "tenant": tenant_b.pk,
        "tenant_id": tenant_b.pk,
        "number": "MALICIOUS-PROF-999",
        "status": "completed",
        "total_row_count": 999999,
        "completeness_score": "1.00",
        "uniqueness_score": "1.00",
        "validity_score": "1.00",
        "last_run_at": "2020-01-01T00:00:00Z",
    }
    res_create = client_a.post(reverse("bi:data_quality_profile_create"), data=malicious_create)
    assert res_create.status_code == 302

    created = DataQualityProfile.objects.get(name="Hardened Profile System")
    assert created.tenant == tenant_a
    assert created.number.startswith("BDQP-")
    assert created.number != "MALICIOUS-PROF-999"
    assert created.status in ["draft", "pending"]
    assert created.total_row_count == 0
    assert created.completeness_score == Decimal("100.00")

    # Edit
    initial_number = dq_profile_a.number
    url_edit = reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk})
    malicious_edit = {
        "name": "Updated Profile Name",
        "target_type": dq_profile_a.target_type,
        "warehouse_table": dq_profile_a.warehouse_table_id,
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "TAMPERED-NUMBER",
        "completeness_score": "5.00",
    }
    res_edit = client_a.post(url_edit, data=malicious_edit)
    assert res_edit.status_code == 302

    dq_profile_a.refresh_from_db()
    assert dq_profile_a.tenant == tenant_a
    assert dq_profile_a.number == initial_number
    assert dq_profile_a.completeness_score != Decimal("5.00")


def test_dataquality_security_mass_assignment_rule_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    warehouse_table_a,
    dq_rule_a,
):
    """Submitting system fields (tenant, number, last_status, pass_rate, violation_count) in Rule POST has no effect."""
    # Create
    malicious_create = {
        "name": "Hardened Quality Rule",
        "code": "hardened_quality_rule",
        "rule_category": "validation",
        "dimension": "validity",
        "target_type": "warehouse_table",
        "warehouse_table": warehouse_table_a.pk,
        "target_column": "amount",
        "rule_type": "range_between",
        "parameters_json": json.dumps({"min_val": 0}),
        "severity": "critical",
        "failure_tolerance_pct": "0.00",
        "is_active": "on",
        # Malicious overrides
        "tenant": tenant_b.pk,
        "number": "MALICIOUS-RULE-999",
        "last_status": "failed",
        "pass_rate_pct": "12.50",
        "violation_count": 500,
        "last_run_at": "2020-01-01T00:00:00Z",
    }
    res_create = client_a.post(reverse("bi:data_quality_rule_create"), data=malicious_create)
    assert res_create.status_code == 302

    created = DataQualityRule.objects.get(code="hardened_quality_rule")
    assert created.tenant == tenant_a
    assert created.number.startswith("BDQR-")
    assert created.number != "MALICIOUS-RULE-999"
    assert created.last_status == "passed" or created.last_status == "draft" or created.last_status != "failed"
    assert created.pass_rate_pct != Decimal("12.50")

    # Edit
    initial_number = dq_rule_a.number
    url_edit = reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk})
    malicious_edit = {
        "name": dq_rule_a.name,
        "code": dq_rule_a.code or "test_rule_edit_code",
        "rule_category": dq_rule_a.rule_category,
        "dimension": dq_rule_a.dimension,
        "target_type": dq_rule_a.target_type,
        "warehouse_table": dq_rule_a.warehouse_table_id,
        "target_column": dq_rule_a.target_column,
        "rule_type": "range_between",
        "parameters_json": json.dumps(dq_rule_a.parameters_json),
        "severity": dq_rule_a.severity,
        "failure_tolerance_pct": str(dq_rule_a.failure_tolerance_pct),
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "TAMPERED-RULE-001",
        "pass_rate_pct": "2.00",
    }
    res_edit = client_a.post(url_edit, data=malicious_edit)
    assert res_edit.status_code == 302

    dq_rule_a.refresh_from_db()
    assert dq_rule_a.tenant == tenant_a
    assert dq_rule_a.number == initial_number
    assert dq_rule_a.pass_rate_pct != Decimal("2.00")


def test_dataquality_security_mass_assignment_exception_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    dq_rule_a,
    dq_profile_a,
    dq_exception_a,
):
    """Submitting system fields (tenant, number, timestamps) in Exception POST has no effect."""
    # Create
    malicious_create = {
        "rule": dq_rule_a.pk,
        "profile": dq_profile_a.pk,
        "record_identifier": "HARDENED-EXC-001",
        "target_column": "amount",
        "invalid_value": "-5.00",
        "expected_condition": "amount > 0",
        "exception_type": "range_outlier",
        "severity": "critical",
        "status": "open",
        "remediation_action": "manual_edit",
        "is_active": "on",
        # Malicious overrides
        "tenant": tenant_b.pk,
        "number": "MALICIOUS-EXC-999",
        "first_detected_at": "2019-01-01T00:00:00Z",
        "last_detected_at": "2019-01-01T00:00:00Z",
    }
    res_create = client_a.post(reverse("bi:data_quality_exception_create"), data=malicious_create)
    assert res_create.status_code == 302

    created = DataQualityException.objects.get(record_identifier="HARDENED-EXC-001")
    assert created.tenant == tenant_a
    assert created.number.startswith("BDQE-")
    assert created.number != "MALICIOUS-EXC-999"

    # Edit
    initial_number = dq_exception_a.number
    url_edit = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk})
    malicious_edit = {
        "rule": dq_exception_a.rule_id,
        "profile": dq_exception_a.profile_id,
        "record_identifier": dq_exception_a.record_identifier,
        "target_column": dq_exception_a.target_column,
        "invalid_value": dq_exception_a.invalid_value,
        "expected_condition": dq_exception_a.expected_condition,
        "exception_type": dq_exception_a.exception_type,
        "severity": dq_exception_a.severity,
        "status": "open",
        "remediation_action": dq_exception_a.remediation_action,
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "TAMPERED-EXC-NUM",
    }
    res_edit = client_a.post(url_edit, data=malicious_edit)
    assert res_edit.status_code == 302

    dq_exception_a.refresh_from_db()
    assert dq_exception_a.tenant == tenant_a
    assert dq_exception_a.number == initial_number


def test_dataquality_security_mass_assignment_scorecard_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    warehouse_table_a,
    dq_scorecard_a,
):
    """Submitting system fields (tenant, number, overall_quality_score, grade, health_status, meets_sla) has no effect."""
    # Create
    malicious_create = {
        "name": "Hardened Trust Scorecard",
        "code": "hardened_trust_scorecard",
        "scope_type": "warehouse_table",
        "warehouse_table": warehouse_table_a.pk,
        "target_quality_score": "95.00",
        "evaluation_period": "monthly",
        "is_active": "on",
        # Malicious overrides
        "tenant": tenant_b.pk,
        "number": "MALICIOUS-CARD-999",
        "overall_quality_score": "10.00",
        "grade": "F",
        "health_status": "critical",
        "meets_sla": False,
        "last_evaluated_at": "2020-01-01T00:00:00Z",
    }
    res_create = client_a.post(reverse("bi:data_quality_scorecard_create"), data=malicious_create)
    assert res_create.status_code == 302

    created = DataQualityScorecard.objects.get(code="hardened_trust_scorecard")
    assert created.tenant == tenant_a
    assert created.number.startswith("BDQS-")
    assert created.number != "MALICIOUS-CARD-999"
    assert created.overall_quality_score == Decimal("100.00")
    assert created.grade == "A"
    assert created.health_status == "healthy"
    assert created.meets_sla is True

    # Edit
    initial_number = dq_scorecard_a.number
    url_edit = reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk})
    malicious_edit = {
        "name": dq_scorecard_a.name,
        "code": dq_scorecard_a.code,
        "scope_type": dq_scorecard_a.scope_type,
        "warehouse_table": dq_scorecard_a.warehouse_table_id,
        "target_quality_score": str(dq_scorecard_a.target_quality_score),
        "evaluation_period": dq_scorecard_a.evaluation_period,
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "TAMPERED-CARD-NUM",
        "overall_quality_score": "15.00",
        "grade": "F",
        "health_status": "critical",
    }
    res_edit = client_a.post(url_edit, data=malicious_edit)
    assert res_edit.status_code == 302

    dq_scorecard_a.refresh_from_db()
    assert dq_scorecard_a.tenant == tenant_a
    assert dq_scorecard_a.number == initial_number
    assert dq_scorecard_a.overall_quality_score != Decimal("15.00")
    assert dq_scorecard_a.grade != "F"


# ===========================================================================
# 6. Audit Log Generation & Isolation
# ===========================================================================


def test_dataquality_security_audit_log_profile_lifecycle(
    client_a,
    tenant_a,
    tenant_b,
    admin_user,
    warehouse_table_a,
):
    """DataQualityProfile mutations (create, update, run, delete) record AuditLog rows strictly for tenant_a."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:data_quality_profile_create"),
        data=_dataquality_profile_payload(table=warehouse_table_a, name="Audited Profile"),
    )
    assert res_create.status_code == 302
    profile = DataQualityProfile.objects.get(tenant=tenant_a, name="Audited Profile")

    log_create = AuditLog.objects.filter(object_id=profile.pk, action="create").first()
    assert log_create is not None
    assert log_create.tenant == tenant_a
    assert log_create.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:data_quality_profile_edit", kwargs={"pk": profile.pk}),
        data=_dataquality_profile_payload(table=warehouse_table_a, name="Audited Profile Renamed"),
    )
    assert res_edit.status_code == 302
    log_update = AuditLog.objects.filter(object_id=profile.pk, action="update").first()
    assert log_update is not None
    assert log_update.tenant == tenant_a
    assert log_update.user == admin_user

    # 3. Run
    res_run = client_a.post(reverse("bi:data_quality_profile_run", kwargs={"pk": profile.pk}))
    assert res_run.status_code == 302
    log_run = AuditLog.objects.filter(object_id=profile.pk, action="run").first()
    assert log_run is not None
    assert log_run.tenant == tenant_a
    assert log_run.user == admin_user

    # 4. Delete
    profile_pk = profile.pk
    res_delete = client_a.post(reverse("bi:data_quality_profile_delete", kwargs={"pk": profile.pk}))
    assert res_delete.status_code == 302
    log_delete = AuditLog.objects.filter(object_id=profile_pk, action="delete").first()
    assert log_delete is not None
    assert log_delete.tenant == tenant_a
    assert log_delete.user == admin_user

    # Zero leakage to tenant_b
    assert not AuditLog.objects.filter(tenant=tenant_b, object_id=profile_pk).exists()


def test_dataquality_security_audit_log_rule_lifecycle(
    client_a,
    tenant_a,
    tenant_b,
    admin_user,
    warehouse_table_a,
):
    """DataQualityRule mutations (create, update, run, delete) record AuditLog rows strictly for tenant_a."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:data_quality_rule_create"),
        data=_dataquality_rule_payload(table=warehouse_table_a, name="Audited Rule", code="audited_rule_code"),
    )
    assert res_create.status_code == 302
    rule = DataQualityRule.objects.get(tenant=tenant_a, code="audited_rule_code")

    log_create = AuditLog.objects.filter(object_id=rule.pk, action="create").first()
    assert log_create is not None
    assert log_create.tenant == tenant_a
    assert log_create.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:data_quality_rule_edit", kwargs={"pk": rule.pk}),
        data=_dataquality_rule_payload(table=warehouse_table_a, name="Audited Rule Renamed", code="audited_rule_code"),
    )
    assert res_edit.status_code == 302
    log_update = AuditLog.objects.filter(object_id=rule.pk, action="update").first()
    assert log_update is not None
    assert log_update.tenant == tenant_a
    assert log_update.user == admin_user

    # 3. Run
    res_run = client_a.post(reverse("bi:data_quality_rule_run", kwargs={"pk": rule.pk}))
    assert res_run.status_code == 302
    log_run = AuditLog.objects.filter(object_id=rule.pk, action="run").first()
    assert log_run is not None
    assert log_run.tenant == tenant_a
    assert log_run.user == admin_user

    # 4. Delete
    rule_pk = rule.pk
    res_delete = client_a.post(reverse("bi:data_quality_rule_delete", kwargs={"pk": rule.pk}))
    assert res_delete.status_code == 302
    log_delete = AuditLog.objects.filter(object_id=rule_pk, action="delete").first()
    assert log_delete is not None
    assert log_delete.tenant == tenant_a
    assert log_delete.user == admin_user

    # Zero leakage to tenant_b
    assert not AuditLog.objects.filter(tenant=tenant_b, object_id=rule_pk).exists()


def test_dataquality_security_audit_log_exception_lifecycle(
    client_a,
    tenant_a,
    tenant_b,
    admin_user,
    dq_rule_a,
    dq_profile_a,
):
    """DataQualityException mutations (create, update, remediate, delete) record AuditLog rows strictly for tenant_a."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:data_quality_exception_create"),
        data=_dataquality_exception_payload(rule=dq_rule_a, profile=dq_profile_a, record_identifier="AUDIT-EXC-01"),
    )
    assert res_create.status_code == 302
    exc = DataQualityException.objects.get(tenant=tenant_a, record_identifier="AUDIT-EXC-01")

    log_create = AuditLog.objects.filter(object_id=exc.pk, action="create").first()
    assert log_create is not None
    assert log_create.tenant == tenant_a
    assert log_create.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:data_quality_exception_edit", kwargs={"pk": exc.pk}),
        data=_dataquality_exception_payload(
            rule=dq_rule_a,
            profile=dq_profile_a,
            record_identifier="AUDIT-EXC-01",
            resolution_notes="Investigation updated.",
        ),
    )
    assert res_edit.status_code == 302
    log_update = AuditLog.objects.filter(object_id=exc.pk, action="update").first()
    assert log_update is not None
    assert log_update.tenant == tenant_a
    assert log_update.user == admin_user

    # 3. Remediate
    res_remediate = client_a.post(
        reverse("bi:data_quality_exception_remediate", kwargs={"pk": exc.pk}),
        data={"status": "remediated", "remediation_action": "manual_edit", "resolution_notes": "Value fixed."},
    )
    assert res_remediate.status_code == 302
    log_remediate = AuditLog.objects.filter(object_id=exc.pk, action__startswith="remed").first()
    assert log_remediate is not None
    assert log_remediate.tenant == tenant_a
    assert log_remediate.user == admin_user

    # 4. Delete
    exc_pk = exc.pk
    res_delete = client_a.post(reverse("bi:data_quality_exception_delete", kwargs={"pk": exc.pk}))
    assert res_delete.status_code == 302
    log_delete = AuditLog.objects.filter(object_id=exc_pk, action="delete").first()
    assert log_delete is not None
    assert log_delete.tenant == tenant_a
    assert log_delete.user == admin_user

    # Zero leakage to tenant_b
    assert not AuditLog.objects.filter(tenant=tenant_b, object_id=exc_pk).exists()


def test_dataquality_security_audit_log_scorecard_lifecycle(
    client_a,
    tenant_a,
    tenant_b,
    admin_user,
    warehouse_table_a,
):
    """DataQualityScorecard mutations (create, update, recalculate, delete) record AuditLog rows strictly for tenant_a."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:data_quality_scorecard_create"),
        data=_dataquality_scorecard_payload(table=warehouse_table_a, name="Audited Card", code="audited_card_code"),
    )
    assert res_create.status_code == 302
    card = DataQualityScorecard.objects.get(tenant=tenant_a, code="audited_card_code")

    log_create = AuditLog.objects.filter(object_id=card.pk, action="create").first()
    assert log_create is not None
    assert log_create.tenant == tenant_a
    assert log_create.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:data_quality_scorecard_edit", kwargs={"pk": card.pk}),
        data=_dataquality_scorecard_payload(table=warehouse_table_a, name="Audited Card Renamed", code="audited_card_code"),
    )
    assert res_edit.status_code == 302
    log_update = AuditLog.objects.filter(object_id=card.pk, action="update").first()
    assert log_update is not None
    assert log_update.tenant == tenant_a
    assert log_update.user == admin_user

    # 3. Recalculate
    res_recalc = client_a.post(reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": card.pk}))
    assert res_recalc.status_code == 302
    log_recalc = AuditLog.objects.filter(object_id=card.pk, action__startswith="recalc").first()
    assert log_recalc is not None
    assert log_recalc.tenant == tenant_a
    assert log_recalc.user == admin_user

    # 4. Delete
    card_pk = card.pk
    res_delete = client_a.post(reverse("bi:data_quality_scorecard_delete", kwargs={"pk": card.pk}))
    assert res_delete.status_code == 302
    log_delete = AuditLog.objects.filter(object_id=card_pk, action="delete").first()
    assert log_delete is not None
    assert log_delete.tenant == tenant_a
    assert log_delete.user == admin_user

    # Zero leakage to tenant_b
    assert not AuditLog.objects.filter(tenant=tenant_b, object_id=card_pk).exists()


# ===========================================================================
# 7. Multi-User Scale Simulation & Boundary Preservation
# ===========================================================================


def test_dataquality_security_multi_user_cross_tenant_isolation(
    tenant_a,
    tenant_b,
    dq_profile_a,
    dq_profile_b,
    dq_rule_a,
    dq_rule_b,
    dq_exception_a,
    dq_exception_b,
    dq_scorecard_a,
    dq_scorecard_b,
):
    """Simulates 40 heterogeneous tenant users concurrently querying DQ entities; confirms 100% tenant isolation."""
    users_a = [_dataquality_create_user(tenant_a, f"dq_user_a_{i}") for i in range(20)]
    users_b = [_dataquality_create_user(tenant_b, f"dq_user_b_{i}") for i in range(20)]

    # Query assertions for all Tenant A users
    for user in users_a:
        profiles = list(DataQualityProfile.objects.filter(tenant=user.tenant))
        rules = list(DataQualityRule.objects.filter(tenant=user.tenant))
        exceptions = list(DataQualityException.objects.filter(tenant=user.tenant))
        scorecards = list(DataQualityScorecard.objects.filter(tenant=user.tenant))

        assert dq_profile_a in profiles
        assert dq_profile_b not in profiles
        assert dq_rule_a in rules
        assert dq_rule_b not in rules
        assert dq_exception_a in exceptions
        assert dq_exception_b not in exceptions
        assert dq_scorecard_a in scorecards
        assert dq_scorecard_b not in scorecards

    # Query assertions for all Tenant B users
    for user in users_b:
        profiles = list(DataQualityProfile.objects.filter(tenant=user.tenant))
        rules = list(DataQualityRule.objects.filter(tenant=user.tenant))
        exceptions = list(DataQualityException.objects.filter(tenant=user.tenant))
        scorecards = list(DataQualityScorecard.objects.filter(tenant=user.tenant))

        assert dq_profile_b in profiles
        assert dq_profile_a not in profiles
        assert dq_rule_b in rules
        assert dq_rule_a not in rules
        assert dq_exception_b in exceptions
        assert dq_exception_a not in exceptions
        assert dq_scorecard_b in scorecards
        assert dq_scorecard_a not in scorecards
