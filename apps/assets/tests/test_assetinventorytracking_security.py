"""Asset Inventory & Tracking (11.2) — SECURITY & Multi-Tenant Authorization Test Suite.

Covers:
1. Cross-Tenant IDOR: Object access across tenants strictly returns 404.
2. Authentication Enforcement: Anonymous requests redirect to login.
3. RBAC & Privileged Actions: @tenant_admin_required enforcement returns 403 for non-admins.
4. HTTP Method Safety: Mutating action endpoints reject GET with 405 Method Not Allowed.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def non_admin_user_a(db, tenant_a):
    return User.objects.create_user(
        username="operator_a@acme.com",
        email="operator_a@acme.com",
        password="password",
        tenant=tenant_a,
        is_staff=False,
    )


# ==============================================================================
# 1. Cross-Tenant IDOR (Strict 404)
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_idor_audit_detail(client, admin_user, audit_b):
    """Tenant A admin cannot view Tenant B audit -> 404."""
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_audit_detail", kwargs={"pk": audit_b.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetinventorytracking_idor_audit_edit(client, admin_user, audit_b):
    """Tenant A admin cannot edit Tenant B audit -> 404."""
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_audit_edit", kwargs={"pk": audit_b.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetinventorytracking_idor_audit_start(client, admin_user, audit_b):
    """Tenant A admin cannot start Tenant B audit -> 404."""
    client.force_login(admin_user)
    resp = client.post(reverse("assets:asset_audit_start", kwargs={"pk": audit_b.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetinventorytracking_idor_movement_detail(client, admin_user, movement_b):
    """Tenant A admin cannot view Tenant B movement log -> 404."""
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_movement_log_detail", kwargs={"pk": movement_b.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetinventorytracking_idor_movement_dispatch(client, admin_user, movement_b):
    """Tenant A admin cannot dispatch Tenant B movement -> 404."""
    client.force_login(admin_user)
    resp = client.post(reverse("assets:asset_movement_log_dispatch", kwargs={"pk": movement_b.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetinventorytracking_idor_custody_detail(client, admin_user, custody_b):
    """Tenant A admin cannot view Tenant B custody record -> 404."""
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_custody_log_detail", kwargs={"pk": custody_b.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetinventorytracking_idor_custody_checkin(client, admin_user, custody_b):
    """Tenant A admin cannot check in Tenant B equipment -> 404."""
    client.force_login(admin_user)
    resp = client.post(reverse("assets:asset_custody_log_checkin", kwargs={"pk": custody_b.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetinventorytracking_idor_incident_detail(client, admin_user, incident_b):
    """Tenant A admin cannot view Tenant B incident report -> 404."""
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_incident_report_detail", kwargs={"pk": incident_b.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetinventorytracking_idor_incident_authorize_write_off(client, admin_user, incident_b):
    """Tenant A admin cannot authorize write-off on Tenant B incident -> 404."""
    client.force_login(admin_user)
    resp = client.post(
        reverse("assets:asset_incident_report_authorize_write_off", kwargs={"pk": incident_b.pk}),
        data={"write_off_notes": "Cross tenant exploit attempt"},
    )
    assert resp.status_code == 404


# ==============================================================================
# 2. Authentication Enforcement (Login Required)
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_anonymous_redirect_on_all_lists(client):
    """Anonymous requests to all list pages redirect to login."""
    urls = [
        reverse("assets:asset_audit_list"),
        reverse("assets:asset_movement_log_list"),
        reverse("assets:asset_custody_log_list"),
        reverse("assets:asset_incident_report_list"),
    ]
    for u in urls:
        resp = client.get(u)
        assert resp.status_code == 302
        assert "/accounts/login" in resp.url or "login" in resp.url


# ==============================================================================
# 3. RBAC & Privileged Actions (@tenant_admin_required)
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_non_admin_blocked_from_reconciliation(client, non_admin_user_a, audit_a):
    """Non-tenant-admin user receives 403 on asset_audit_reconcile."""
    client.force_login(non_admin_user_a)
    url = reverse("assets:asset_audit_reconcile", kwargs={"pk": audit_a.pk})
    resp = client.post(url, data={"reconciliation_action": "no_action_needed"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetinventorytracking_non_admin_blocked_from_write_off(client, non_admin_user_a, incident_a):
    """Non-tenant-admin user receives 403 on asset_incident_report_authorize_write_off."""
    client.force_login(non_admin_user_a)
    url = reverse("assets:asset_incident_report_authorize_write_off", kwargs={"pk": incident_a.pk})
    resp = client.post(url, data={"write_off_notes": "Unauthorized write-off attempt"})
    assert resp.status_code == 403


# ==============================================================================
# 4. HTTP Method Safety (require_POST)
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_mutating_actions_reject_get(client, admin_user, audit_a, movement_a, custody_a, incident_a):
    """All state mutating actions reject GET with 405 Method Not Allowed."""
    client.force_login(admin_user)
    post_only_urls = [
        reverse("assets:asset_audit_start", kwargs={"pk": audit_a.pk}),
        reverse("assets:asset_audit_complete", kwargs={"pk": audit_a.pk}),
        reverse("assets:asset_audit_reconcile", kwargs={"pk": audit_a.pk}),
        reverse("assets:asset_audit_cancel", kwargs={"pk": audit_a.pk}),
        reverse("assets:asset_movement_log_dispatch", kwargs={"pk": movement_a.pk}),
        reverse("assets:asset_movement_log_receive", kwargs={"pk": movement_a.pk}),
        reverse("assets:asset_movement_log_cancel", kwargs={"pk": movement_a.pk}),
        reverse("assets:asset_custody_log_checkin", kwargs={"pk": custody_a.pk}),
        reverse("assets:asset_custody_log_extend", kwargs={"pk": custody_a.pk}),
        reverse("assets:asset_custody_log_mark_lost", kwargs={"pk": custody_a.pk}),
        reverse("assets:asset_incident_report_investigate", kwargs={"pk": incident_a.pk}),
        reverse("assets:asset_incident_report_resolve_recovered", kwargs={"pk": incident_a.pk}),
        reverse("assets:asset_incident_report_authorize_write_off", kwargs={"pk": incident_a.pk}),
        reverse("assets:asset_incident_report_close", kwargs={"pk": incident_a.pk}),
    ]
    for u in post_only_urls:
        resp = client.get(u)
        assert resp.status_code == 405
