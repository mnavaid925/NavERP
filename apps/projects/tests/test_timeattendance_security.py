"""Projects 7.11 — Time & Attendance Tracking security tests.

Covers:
- Anonymous user access redirection to login
- Cross-tenant IDOR defense (404 on foreign PK access across all GET and POST routes)
- Role-based authorization (@tenant_admin_required on approval and rejection verbs)
- HTTP method enforcement (@require_POST on mutating verbs yields 405 on GET)

Naming: every test ``test_timeattendance_*``, every helper ``_timeattendance_*``.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

_ANON_GET_ROUTES = [
    "tac_list", "tac_create",
    "otr_list", "otr_create",
    "pot_list", "pot_create",
    "utilization_dashboard",
    "time_calendar",
]

_POST_ONLY_ROUTES = [
    "pot_submit", "pot_approve", "pot_reject", "pot_delete",
    "tac_delete", "otr_delete",
]


# ==================================================================================================
# Anonymous Redirection
# ==================================================================================================

@pytest.mark.parametrize("route_name", _ANON_GET_ROUTES)
def test_timeattendance_anon_get_redirects_to_login(client, route_name):
    url = reverse(f"projects:{route_name}")
    resp = client.get(url)
    assert resp.status_code in (301, 302)
    assert "/login/" in resp.url or "/accounts/login/" in resp.url


# ==================================================================================================
# Cross-Tenant IDOR Isolation (Tenant A client accessing Tenant B objects returns 404)
# ==================================================================================================

def test_timeattendance_cross_tenant_tac_detail_returns_404(client_a, timeattendance_code_b):
    url = reverse("projects:tac_detail", kwargs={"pk": timeattendance_code_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_timeattendance_cross_tenant_otr_detail_returns_404(client_a, timeattendance_rule_b):
    url = reverse("projects:otr_detail", kwargs={"pk": timeattendance_rule_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_timeattendance_cross_tenant_pot_detail_returns_404(client_a, timeattendance_record_draft_b):
    url = reverse("projects:pot_detail", kwargs={"pk": timeattendance_record_draft_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_timeattendance_cross_tenant_pot_verbs_return_404(client_a, timeattendance_record_draft_b):
    submit_url = reverse("projects:pot_submit", kwargs={"pk": timeattendance_record_draft_b.pk})
    assert client_a.post(submit_url).status_code == 404

    approve_url = reverse("projects:pot_approve", kwargs={"pk": timeattendance_record_draft_b.pk})
    assert client_a.post(approve_url).status_code == 404

    reject_url = reverse("projects:pot_reject", kwargs={"pk": timeattendance_record_draft_b.pk})
    assert client_a.post(reject_url, {"reason": "IDOR attempt"}).status_code == 404


# ==================================================================================================
# Role-Based Permissions (@tenant_admin_required on approval and rejection verbs)
# ==================================================================================================

def test_timeattendance_non_admin_cannot_approve_overtime(
    member_client, timeattendance_record_submitted_a
):
    url = reverse("projects:pot_approve", kwargs={"pk": timeattendance_record_submitted_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_timeattendance_non_admin_cannot_reject_overtime(
    member_client, timeattendance_record_submitted_a
):
    url = reverse("projects:pot_reject", kwargs={"pk": timeattendance_record_submitted_a.pk})
    resp = member_client.post(url, {"reason": "Unauthorized reject"})
    assert resp.status_code == 403


# ==================================================================================================
# Method Not Allowed (405 on GET to POST-only verbs)
# ==================================================================================================

@pytest.mark.parametrize("route_name", _POST_ONLY_ROUTES)
def test_timeattendance_post_only_verbs_refuse_get(client_a, route_name):
    # Dummy pk 99999; @require_POST check runs before DB query
    url = reverse(f"projects:{route_name}", kwargs={"pk": 99999})
    resp = client_a.get(url)
    assert resp.status_code == 405
