"""
Security, multi-tenant IDOR, RBAC, locked/held state AuthZ, mass-assignment,
cross-tenant FK injection, XSS/CSV formula neutralization, M2 masked-key,
CSRF, HTTP method safety, and Django Admin lock tests for Module 11.18:
IT Asset Management (ITAM).

Covers review regressions C2, C3, C4, I1, I2, I3, M2, M8.
"""

from __future__ import annotations

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.assets.admin import (
    CloudAssetSubscriptionAdmin,
    CmdbRelationshipAdmin,
    ItHardwareAssetAdmin,
    SoftwareLicenseAdmin,
)
from apps.assets.forms import (
    CloudAssetSubscriptionForm,
    CmdbRelationshipForm,
    ItHardwareAssetForm,
    SoftwareLicenseForm,
)
from apps.assets.models import (
    CloudAssetSubscription,
    CmdbRelationship,
    ItHardwareAsset,
    SoftwareLicense,
)
from apps.assets.views.ItAssetManagement._helpers import csv_safe

User = get_user_model()

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (Must start with _it_asset_management_*)
# =====================================================================


def _it_asset_management_messages(response):
    """Return queued Django flash message strings for a response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _it_asset_management_parse_csv(response):
    """Parse a CSV HttpResponse into a list of rows."""
    content = response.content.decode("utf-8")
    return list(csv.reader(io.StringIO(content)))


def _it_asset_management_superuser_client():
    """Create and log in a platform superuser with tenant=None."""
    su = User.objects.create_superuser(
        email="platform_super_11_18_sec@naverp.test",
        username="platform_super_11_18_sec",
        password="TestPass123!",
        tenant=None,
    )
    client = Client()
    client.force_login(su)
    return su, client


def _it_asset_management_hw_payload(**overrides):
    data = {
        "hostname": "sec-prod-app01",
        "fqdn": "sec-prod-app01.acme.local",
        "device_class": "physical_server",
        "serial_number": "SN-SEC-001",
        "asset_tag_code": "IT-SEC-001",
        "manufacturer": "Dell",
        "model_name": "PowerEdge R760",
        "environment": "production",
        "criticality": "high",
        "disk_encryption_status": "luks_encrypted",
        "refresh_cycle_months": "48",
        "estimated_refresh_cost": "3500.00",
        "sanitization_required": "on",
        "sanitization_method": "none",
        "sanitization_status": "pending_wipe",
    }
    data.update(overrides)
    return data


def _it_asset_management_sw_payload(**overrides):
    data = {
        "software_name": "Security Vault Enterprise",
        "publisher_name": "HashiCorp",
        "product_sku": "VAULT-ENT-2026",
        "software_category": "security_edr",
        "license_type": "subscription_term",
        "license_metric": "per_user",
        "license_key_ref": "VAULT-****-9K2M",
        "entitled_quantity": "25",
        "allocated_quantity": "20",
        "active_used_quantity": "18",
        "reclaimable_inactive_count": "2",
        "unit_license_cost": "200.00",
        "total_annual_spend": "5000.00",
    }
    data.update(overrides)
    return data


def _it_asset_management_cloud_payload(**overrides):
    data = {
        "name": "Datadog Security SIEM",
        "asset_kind": "saas_application",
        "provider": "datadog",
        "external_account_id": "dd-sec-1001",
        "cloud_region": "us-east-1",
        "environment": "production",
        "resource_tags": '{"env": "prod", "cost_center": "CC-SEC", "owner": "secops"}',
        "billing_cadence": "monthly",
        "commitment_term": "annual_contract",
        "monthly_recurring_cost": "1200.00",
        "annual_contract_value": "14400.00",
        "provisioned_seats": "20",
        "active_seats_30d": "18",
        "sso_status": "sso_enforced",
        "approval_status": "sanctioned",
        "cancellation_notice_days": "30",
    }
    data.update(overrides)
    return data


def _it_asset_management_cmdb_payload(source_sw, target_hw, **overrides):
    data = {
        "source_ci_type": "software_license",
        "source_software": str(source_sw.pk),
        "relationship_type": "runs_on",
        "target_ci_type": "it_hardware",
        "target_hardware": str(target_hw.pk),
        "environment": "production",
        "criticality": "tier_2_business_important",
        "impact_severity": "degraded_performance",
        "blast_radius_notes": "Security test CMDB dependency edge.",
    }
    data.update(overrides)
    return data


def _it_asset_management_entity_pk_map(hw, sw, cloud, cmdb):
    return {
        "hw": hw.pk,
        "sw": sw.pk,
        "cloud": cloud.pk,
        "cmdb": cmdb.pk,
    }


_ITAM_DETAIL_AND_EDIT_ROUTES = [
    ("assets:it_hardware_asset_detail", "hw"),
    ("assets:it_hardware_asset_edit", "hw"),
    ("assets:software_license_detail", "sw"),
    ("assets:software_license_edit", "sw"),
    ("assets:cloud_asset_subscription_detail", "cloud"),
    ("assets:cloud_asset_subscription_edit", "cloud"),
    ("assets:cmdb_relationship_detail", "cmdb"),
    ("assets:cmdb_relationship_edit", "cmdb"),
]

# 4 deletes + 22 workflow endpoints = 26 POST-only routes
_ITAM_POST_ONLY_ROUTES = [
    # Hardware (1 delete + 7 workflow = 8)
    ("assets:it_hardware_asset_delete", "hw"),
    ("assets:it_hardware_asset_deploy", "hw"),
    ("assets:it_hardware_asset_move_to_stock", "hw"),
    ("assets:it_hardware_asset_send_to_repair", "hw"),
    ("assets:it_hardware_asset_move_to_loaner", "hw"),
    ("assets:it_hardware_asset_flag_for_refresh", "hw"),
    ("assets:it_hardware_asset_mark_sanitized", "hw"),
    ("assets:it_hardware_asset_retire", "hw"),
    # Software (1 delete + 6 workflow = 7)
    ("assets:software_license_delete", "sw"),
    ("assets:software_license_sync_compliance", "sw"),
    ("assets:software_license_reclaim_inactive", "sw"),
    ("assets:software_license_record_true_up", "sw"),
    ("assets:software_license_renew_term", "sw"),
    ("assets:software_license_place_audit_hold", "sw"),
    ("assets:software_license_retire", "sw"),
    # Cloud (1 delete + 6 workflow = 7)
    ("assets:cloud_asset_subscription_delete", "cloud"),
    ("assets:cloud_asset_subscription_sanction", "cloud"),
    ("assets:cloud_asset_subscription_flag_shadow", "cloud"),
    ("assets:cloud_asset_subscription_sync_finops", "cloud"),
    ("assets:cloud_asset_subscription_renew", "cloud"),
    ("assets:cloud_asset_subscription_suspend", "cloud"),
    ("assets:cloud_asset_subscription_decommission", "cloud"),
    # CMDB (1 delete + 3 workflow = 4)
    ("assets:cmdb_relationship_delete", "cmdb"),
    ("assets:cmdb_relationship_verify", "cmdb"),
    ("assets:cmdb_relationship_deprecate", "cmdb"),
    ("assets:cmdb_relationship_sever", "cmdb"),
]


# =====================================================================
# 1. Anonymous Authentication Redirects
# =====================================================================


@pytest.mark.parametrize(
    "url_name",
    [
        "assets:it_hardware_asset_list",
        "assets:it_hardware_asset_create",
        "assets:it_hardware_asset_export_csv",
        "assets:software_license_list",
        "assets:software_license_create",
        "assets:software_license_export_csv",
        "assets:cloud_asset_subscription_list",
        "assets:cloud_asset_subscription_create",
        "assets:cloud_asset_subscription_export_csv",
        "assets:cmdb_relationship_list",
        "assets:cmdb_relationship_create",
        "assets:cmdb_relationship_export_csv",
        "assets:it_refresh_board",
        "assets:it_refresh_board_export_csv",
        "assets:cmdb_impact_analysis",
        "assets:cmdb_impact_analysis_export_csv",
    ],
)
def test_it_asset_management_anonymous_get_static_routes_redirect_to_login(url_name):
    anon = Client()
    resp = anon.get(reverse(url_name))
    assert resp.status_code == 302
    assert "/login" in resp.url or "login" in resp.url


@pytest.mark.parametrize("url_name,entity_key", _ITAM_DETAIL_AND_EDIT_ROUTES)
def test_it_asset_management_anonymous_get_object_routes_redirect_to_login(
    url_name,
    entity_key,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    anon = Client()
    pks = _it_asset_management_entity_pk_map(
        it_hardware_a, software_license_a, cloud_subscription_a, cmdb_relationship_a
    )
    resp = anon.get(reverse(url_name, args=[pks[entity_key]]))
    assert resp.status_code == 302
    assert "login" in resp.url


@pytest.mark.parametrize(
    "url_name",
    [
        "assets:it_hardware_asset_create",
        "assets:software_license_create",
        "assets:cloud_asset_subscription_create",
        "assets:cmdb_relationship_create",
    ],
)
def test_it_asset_management_anonymous_post_create_redirects_to_login(url_name):
    anon = Client()
    resp = anon.post(reverse(url_name), data={"hostname": "rogue", "name": "rogue"})
    assert resp.status_code == 302
    assert "login" in resp.url


@pytest.mark.parametrize("url_name,entity_key", _ITAM_POST_ONLY_ROUTES)
def test_it_asset_management_anonymous_post_mutations_redirect_to_login(
    url_name,
    entity_key,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    anon = Client()
    pks = _it_asset_management_entity_pk_map(
        it_hardware_a, software_license_a, cloud_subscription_a, cmdb_relationship_a
    )
    resp = anon.post(reverse(url_name, args=[pks[entity_key]]))
    assert resp.status_code == 302
    assert "login" in resp.url

    # Also verify anonymous POST to edit URLs redirects cleanly
    for edit_name, key in (
        ("assets:it_hardware_asset_edit", "hw"),
        ("assets:software_license_edit", "sw"),
        ("assets:cloud_asset_subscription_edit", "cloud"),
        ("assets:cmdb_relationship_edit", "cmdb"),
    ):
        edit_resp = anon.post(reverse(edit_name, args=[pks[key]]), data={})
        assert edit_resp.status_code == 302
        assert "login" in edit_resp.url


# =====================================================================
# 2. Cross-Tenant IDOR Isolation (404 & Zero Data Leakage)
# =====================================================================


@pytest.mark.parametrize("url_name,entity_key", _ITAM_DETAIL_AND_EDIT_ROUTES)
def test_it_asset_management_cross_tenant_idor_detail_and_edit_return_404(
    url_name,
    entity_key,
    client_b,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    pks = _it_asset_management_entity_pk_map(
        it_hardware_a, software_license_a, cloud_subscription_a, cmdb_relationship_a
    )
    url = reverse(url_name, args=[pks[entity_key]])
    assert client_b.get(url).status_code == 404

    if url_name.endswith("_edit"):
        orig_hw = it_hardware_a.hostname
        orig_sw = software_license_a.software_name
        orig_cloud = cloud_subscription_a.name
        orig_cmdb = cmdb_relationship_a.blast_radius_notes

        assert (
            client_b.post(
                url,
                data={
                    "hostname": "idor-tampered",
                    "software_name": "idor-tampered",
                    "name": "idor-tampered",
                    "blast_radius_notes": "idor-tampered",
                },
            ).status_code
            == 404
        )
        it_hardware_a.refresh_from_db()
        software_license_a.refresh_from_db()
        cloud_subscription_a.refresh_from_db()
        cmdb_relationship_a.refresh_from_db()
        assert it_hardware_a.hostname == orig_hw
        assert software_license_a.software_name == orig_sw
        assert cloud_subscription_a.name == orig_cloud
        assert cmdb_relationship_a.blast_radius_notes == orig_cmdb


@pytest.mark.parametrize("url_name,entity_key", _ITAM_POST_ONLY_ROUTES)
def test_it_asset_management_cross_tenant_idor_all_26_post_mutations_return_404_with_zero_mutation(
    url_name,
    entity_key,
    client_b,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    # Ensure reclaimable/shortfall fields are populated so no early-return hides 404
    software_license_a.reclaimable_inactive_count = 3
    software_license_a.allocated_quantity = 120
    software_license_a.save()

    pks = _it_asset_management_entity_pk_map(
        it_hardware_a, software_license_a, cloud_subscription_a, cmdb_relationship_a
    )
    resp = client_b.post(reverse(url_name, args=[pks[entity_key]]))
    assert resp.status_code == 404

    assert ItHardwareAsset.objects.filter(
        pk=it_hardware_a.pk,
        status=it_hardware_a.status,
        sanitization_status=it_hardware_a.sanitization_status,
    ).exists()
    assert SoftwareLicense.objects.filter(
        pk=software_license_a.pk,
        status=software_license_a.status,
        entitled_quantity=software_license_a.entitled_quantity,
    ).exists()
    assert CloudAssetSubscription.objects.filter(
        pk=cloud_subscription_a.pk,
        status=cloud_subscription_a.status,
        approval_status=cloud_subscription_a.approval_status,
    ).exists()
    assert CmdbRelationship.objects.filter(
        pk=cmdb_relationship_a.pk,
        status=cmdb_relationship_a.status,
    ).exists()


def test_it_asset_management_cross_tenant_lists_csvs_and_workbenches_zero_leakage(
    client_b,
    tenant_a,
    it_hardware_a,
    it_hardware_b,
    software_license_a,
    software_license_b,
    cloud_subscription_a,
    cloud_subscription_b,
    cmdb_relationship_a,
    cmdb_relationship_b,
):
    # Make tenant_a records qualify for Refresh Board & CMDB Impact Analysis
    today = timezone.localdate()
    it_hardware_a.refresh_due_date = today - timedelta(days=5)
    it_hardware_a.sanitization_required = True
    it_hardware_a.sanitization_status = "pending_wipe"
    it_hardware_a.save()
    software_license_a.renewal_date = today + timedelta(days=10)
    software_license_a.save()
    cloud_subscription_a.renewal_date = today + timedelta(days=10)
    cloud_subscription_a.save()
    cmdb_relationship_a.is_single_point_of_failure = True
    cmdb_relationship_a.save()

    tenant_a_markers = (
        it_hardware_a.hostname,
        it_hardware_a.serial_number,
        software_license_a.software_name,
        cloud_subscription_a.name,
        cmdb_relationship_a.blast_radius_notes,
    )

    for url in [
        reverse("assets:it_hardware_asset_list"),
        reverse("assets:software_license_list"),
        reverse("assets:cloud_asset_subscription_list"),
        reverse("assets:cmdb_relationship_list"),
        reverse("assets:it_refresh_board") + "?horizon=365",
        reverse("assets:cmdb_impact_analysis"),
        reverse("assets:cmdb_impact_analysis") + f"?ci=it_hardware:{it_hardware_a.pk}",
        reverse("assets:cmdb_impact_analysis") + f"?ci=software_license:{software_license_a.pk}",
        reverse("assets:cmdb_impact_analysis") + f"?ci=cloud_asset:{cloud_subscription_a.pk}",
    ]:
        resp = client_b.get(url)
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        for marker in tenant_a_markers:
            assert marker not in body

    # Verify list contexts only contain tenant_b PKs, never tenant_a PKs
    assert it_hardware_a.pk not in [
        o.pk for o in client_b.get(reverse("assets:it_hardware_asset_list")).context["hardware_assets"]
    ]
    assert software_license_a.pk not in [
        o.pk for o in client_b.get(reverse("assets:software_license_list")).context["licenses"]
    ]
    assert cloud_subscription_a.pk not in [
        o.pk for o in client_b.get(reverse("assets:cloud_asset_subscription_list")).context["cloud_assets"]
    ]
    assert cmdb_relationship_a.pk not in [
        o.pk for o in client_b.get(reverse("assets:cmdb_relationship_list")).context["relationships"]
    ]

    # Verify direct ?ci= probing does not select tenant_a CI
    probe_resp = client_b.get(
        reverse("assets:cmdb_impact_analysis") + f"?ci=it_hardware:{it_hardware_a.pk}"
    )
    assert probe_resp.context["selected_ci_token"] != f"it_hardware:{it_hardware_a.pk}"
    assert probe_resp.context["upstream_nodes"] == [] or all(
        it_hardware_a.hostname not in n["ci_label"]
        for n in probe_resp.context["upstream_nodes"]
    )
    assert all(
        it_hardware_a.hostname not in n["ci_label"]
        for n in probe_resp.context["downstream_nodes"]
    )

    # Verify all 6 CSV exports never include tenant_a records
    for csv_url in [
        reverse("assets:it_hardware_asset_export_csv"),
        reverse("assets:software_license_export_csv"),
        reverse("assets:cloud_asset_subscription_export_csv"),
        reverse("assets:cmdb_relationship_export_csv"),
        reverse("assets:it_refresh_board_export_csv") + "?horizon=365",
        reverse("assets:cmdb_impact_analysis_export_csv")
        + f"?ci=it_hardware:{it_hardware_a.pk}",
    ]:
        csv_resp = client_b.get(csv_url)
        assert csv_resp.status_code == 200
        csv_body = csv_resp.content.decode("utf-8")
        for marker in tenant_a_markers:
            assert marker not in csv_body


def test_it_asset_management_superuser_tenant_none_empty_scopes_and_create_guard_i3(
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    """I3: Superuser with tenant=None sees empty lists/CSVs/workbenches and 302 warning on create POST."""
    _, su_client = _it_asset_management_superuser_client()

    # Lists & workbenches return 200 with zero tenant_a rows
    for url_name in (
        "assets:it_hardware_asset_list",
        "assets:software_license_list",
        "assets:cloud_asset_subscription_list",
        "assets:cmdb_relationship_list",
        "assets:it_refresh_board",
        "assets:cmdb_impact_analysis",
    ):
        resp = su_client.get(reverse(url_name))
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert it_hardware_a.number not in body
        assert software_license_a.number not in body
        assert cloud_subscription_a.number not in body
        assert cmdb_relationship_a.number not in body

    # CSV exports return header row only
    for csv_url_name in (
        "assets:it_hardware_asset_export_csv",
        "assets:software_license_export_csv",
        "assets:cloud_asset_subscription_export_csv",
        "assets:cmdb_relationship_export_csv",
        "assets:it_refresh_board_export_csv",
        "assets:cmdb_impact_analysis_export_csv",
    ):
        csv_resp = su_client.get(reverse(csv_url_name))
        assert csv_resp.status_code == 200
        rows = _it_asset_management_parse_csv(csv_resp)
        assert len(rows) == 1

    # GET create pages render 200 without crashing
    for create_name in (
        "assets:it_hardware_asset_create",
        "assets:software_license_create",
        "assets:cloud_asset_subscription_create",
        "assets:cmdb_relationship_create",
    ):
        assert su_client.get(reverse(create_name)).status_code == 200

    # POST create with tenant=None redirects safely with warning (no IntegrityError 500)
    hw_before = ItHardwareAsset.objects.count()
    sw_before = SoftwareLicense.objects.count()
    cl_before = CloudAssetSubscription.objects.count()
    cmdb_before = CmdbRelationship.objects.count()

    r_hw = su_client.post(
        reverse("assets:it_hardware_asset_create"), data=_it_asset_management_hw_payload()
    )
    assert r_hw.status_code == 302
    assert r_hw.url == reverse("assets:it_hardware_asset_list")
    assert any("Workspace context is required" in m for m in _it_asset_management_messages(r_hw))

    r_sw = su_client.post(
        reverse("assets:software_license_create"), data=_it_asset_management_sw_payload()
    )
    assert r_sw.status_code == 302
    assert r_sw.url == reverse("assets:software_license_list")
    assert any("Workspace context is required" in m for m in _it_asset_management_messages(r_sw))

    r_cl = su_client.post(
        reverse("assets:cloud_asset_subscription_create"),
        data=_it_asset_management_cloud_payload(),
    )
    assert r_cl.status_code == 302
    assert r_cl.url == reverse("assets:cloud_asset_subscription_list")
    assert any("Workspace context is required" in m for m in _it_asset_management_messages(r_cl))

    r_cmdb = su_client.post(
        reverse("assets:cmdb_relationship_create"),
        data=_it_asset_management_cmdb_payload(software_license_a, it_hardware_a),
    )
    assert r_cmdb.status_code == 302
    assert r_cmdb.url == reverse("assets:cmdb_relationship_list")
    assert any("Workspace context is required" in m for m in _it_asset_management_messages(r_cmdb))

    assert ItHardwareAsset.objects.count() == hw_before
    assert SoftwareLicense.objects.count() == sw_before
    assert CloudAssetSubscription.objects.count() == cl_before
    assert CmdbRelationship.objects.count() == cmdb_before


# =====================================================================
# 3. HTTP Method Safety (@require_POST) & CSRF Enforcement
# =====================================================================


@pytest.mark.parametrize("url_name,entity_key", _ITAM_POST_ONLY_ROUTES)
def test_it_asset_management_get_on_post_only_endpoints_returns_405(
    url_name,
    entity_key,
    client_a,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    pks = _it_asset_management_entity_pk_map(
        it_hardware_a, software_license_a, cloud_subscription_a, cmdb_relationship_a
    )
    resp = client_a.get(reverse(url_name, args=[pks[entity_key]]))
    assert resp.status_code == 405

    assert ItHardwareAsset.objects.filter(pk=it_hardware_a.pk, status=it_hardware_a.status).exists()
    assert SoftwareLicense.objects.filter(pk=software_license_a.pk, status=software_license_a.status).exists()
    assert CloudAssetSubscription.objects.filter(
        pk=cloud_subscription_a.pk, status=cloud_subscription_a.status
    ).exists()
    assert CmdbRelationship.objects.filter(
        pk=cmdb_relationship_a.pk, status=cmdb_relationship_a.status
    ).exists()


def test_it_asset_management_csrf_enforced_blocks_forged_posts(
    admin_user,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    for url in (
        reverse("assets:it_hardware_asset_delete", args=[it_hardware_a.pk]),
        reverse("assets:it_hardware_asset_mark_sanitized", args=[it_hardware_a.pk]),
        reverse("assets:software_license_delete", args=[software_license_a.pk]),
        reverse("assets:software_license_place_audit_hold", args=[software_license_a.pk]),
        reverse("assets:cloud_asset_subscription_delete", args=[cloud_subscription_a.pk]),
        reverse("assets:cloud_asset_subscription_suspend", args=[cloud_subscription_a.pk]),
        reverse("assets:cmdb_relationship_delete", args=[cmdb_relationship_a.pk]),
        reverse("assets:cmdb_relationship_sever", args=[cmdb_relationship_a.pk]),
    ):
        assert csrf_client.post(url).status_code == 403

    assert ItHardwareAsset.objects.filter(pk=it_hardware_a.pk).exists()
    assert SoftwareLicense.objects.filter(pk=software_license_a.pk).exists()
    assert CloudAssetSubscription.objects.filter(pk=cloud_subscription_a.pk).exists()
    assert CmdbRelationship.objects.filter(pk=cmdb_relationship_a.pk).exists()


# =====================================================================
# 4. Admin Role AuthZ & Locked/Held State Guards (C2, C3, C4, I1)
# =====================================================================


@pytest.mark.parametrize(
    "url_name,entity_key",
    [
        ("assets:it_hardware_asset_delete", "hw"),
        ("assets:it_hardware_asset_mark_sanitized", "hw"),
        ("assets:it_hardware_asset_retire", "hw"),
        ("assets:software_license_delete", "sw"),
        ("assets:software_license_record_true_up", "sw"),
        ("assets:software_license_place_audit_hold", "sw"),
        ("assets:software_license_retire", "sw"),
        ("assets:cloud_asset_subscription_delete", "cloud"),
        ("assets:cloud_asset_subscription_suspend", "cloud"),
        ("assets:cloud_asset_subscription_decommission", "cloud"),
        ("assets:cmdb_relationship_delete", "cmdb"),
        ("assets:cmdb_relationship_sever", "cmdb"),
    ],
)
def test_it_asset_management_member_receives_403_on_all_admin_only_actions(
    url_name,
    entity_key,
    member_client,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    software_license_a.allocated_quantity = software_license_a.entitled_quantity + 10
    software_license_a.save()

    pks = _it_asset_management_entity_pk_map(
        it_hardware_a, software_license_a, cloud_subscription_a, cmdb_relationship_a
    )
    resp = member_client.post(reverse(url_name, args=[pks[entity_key]]))
    assert resp.status_code == 403

    it_hardware_a.refresh_from_db()
    software_license_a.refresh_from_db()
    cloud_subscription_a.refresh_from_db()
    cmdb_relationship_a.refresh_from_db()
    assert it_hardware_a.status != "sanitized_retired"
    assert it_hardware_a.sanitization_verified_by is None
    assert software_license_a.status == "active_compliant"
    assert cloud_subscription_a.status == "active"
    assert cmdb_relationship_a.status == "active"


def test_it_asset_management_ui_hides_admin_actions_from_member_on_detail_and_list(
    member_client,
    client_a,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    software_license_a.allocated_quantity = software_license_a.entitled_quantity + 5
    software_license_a.save()

    # Check list templates hide delete actions from member_client
    for list_url_name, del_url_name, pk in (
        ("assets:it_hardware_asset_list", "assets:it_hardware_asset_delete", it_hardware_a.pk),
        ("assets:software_license_list", "assets:software_license_delete", software_license_a.pk),
        ("assets:cloud_asset_subscription_list", "assets:cloud_asset_subscription_delete", cloud_subscription_a.pk),
        ("assets:cmdb_relationship_list", "assets:cmdb_relationship_delete", cmdb_relationship_a.pk),
    ):
        del_path = reverse(del_url_name, args=[pk])
        member_html = member_client.get(reverse(list_url_name)).content.decode("utf-8")
        admin_html = client_a.get(reverse(list_url_name)).content.decode("utf-8")
        assert del_path not in member_html
        assert del_path in admin_html

    # Check detail templates hide admin-only workflow & delete forms from member_client
    detail_admin_actions = [
        (
            reverse("assets:it_hardware_asset_detail", args=[it_hardware_a.pk]),
            [
                reverse("assets:it_hardware_asset_mark_sanitized", args=[it_hardware_a.pk]),
                reverse("assets:it_hardware_asset_retire", args=[it_hardware_a.pk]),
                reverse("assets:it_hardware_asset_delete", args=[it_hardware_a.pk]),
            ],
        ),
        (
            reverse("assets:software_license_detail", args=[software_license_a.pk]),
            [
                reverse("assets:software_license_record_true_up", args=[software_license_a.pk]),
                reverse("assets:software_license_place_audit_hold", args=[software_license_a.pk]),
                reverse("assets:software_license_retire", args=[software_license_a.pk]),
                reverse("assets:software_license_delete", args=[software_license_a.pk]),
            ],
        ),
        (
            reverse("assets:cloud_asset_subscription_detail", args=[cloud_subscription_a.pk]),
            [
                reverse("assets:cloud_asset_subscription_suspend", args=[cloud_subscription_a.pk]),
                reverse("assets:cloud_asset_subscription_decommission", args=[cloud_subscription_a.pk]),
                reverse("assets:cloud_asset_subscription_delete", args=[cloud_subscription_a.pk]),
            ],
        ),
        (
            reverse("assets:cmdb_relationship_detail", args=[cmdb_relationship_a.pk]),
            [
                reverse("assets:cmdb_relationship_sever", args=[cmdb_relationship_a.pk]),
                reverse("assets:cmdb_relationship_delete", args=[cmdb_relationship_a.pk]),
            ],
        ),
    ]
    for detail_url, hidden_actions in detail_admin_actions:
        member_detail = member_client.get(detail_url).content.decode("utf-8")
        admin_detail = client_a.get(detail_url).content.decode("utf-8")
        for action_url in hidden_actions:
            assert action_url not in member_detail
            assert action_url in admin_detail


def test_it_asset_management_c2_software_audit_hold_blocks_member_and_hides_ui(
    member_client,
    client_a,
    software_license_a,
):
    """C2: While SoftwareLicense is on audit_hold, member receives 403 and detail UI hides mutating controls."""
    software_license_a.reclaimable_inactive_count = 4
    software_license_a.status = "audit_hold"
    software_license_a.save()

    orig_name = software_license_a.software_name
    orig_allocated = software_license_a.allocated_quantity
    orig_renewal = software_license_a.renewal_date

    # Member GET & POST edit -> 403
    edit_url = reverse("assets:software_license_edit", args=[software_license_a.pk])
    assert member_client.get(edit_url).status_code == 403
    assert (
        member_client.post(
            edit_url,
            data=_it_asset_management_sw_payload(software_name="Bypass Audit Hold"),
        ).status_code
        == 403
    )

    # Member POST to sync_compliance, reclaim_inactive, renew_term -> 403
    sync_url = reverse("assets:software_license_sync_compliance", args=[software_license_a.pk])
    reclaim_url = reverse("assets:software_license_reclaim_inactive", args=[software_license_a.pk])
    renew_url = reverse("assets:software_license_renew_term", args=[software_license_a.pk])
    assert member_client.post(sync_url).status_code == 403
    assert member_client.post(reclaim_url).status_code == 403
    assert member_client.post(renew_url).status_code == 403

    software_license_a.refresh_from_db()
    assert software_license_a.status == "audit_hold"
    assert software_license_a.software_name == orig_name
    assert software_license_a.allocated_quantity == orig_allocated
    assert software_license_a.renewal_date == orig_renewal

    # UI gate symmetry on software_license/detail.html
    detail_url = reverse("assets:software_license_detail", args=[software_license_a.pk])
    member_html = member_client.get(detail_url).content.decode("utf-8")
    for hidden_url in (sync_url, reclaim_url, renew_url, edit_url):
        assert hidden_url not in member_html

    admin_html = client_a.get(detail_url).content.decode("utf-8")
    for visible_url in (sync_url, reclaim_url, renew_url, edit_url):
        assert visible_url in admin_html


def test_it_asset_management_c3_cloud_suspended_blocks_member_and_admin_actions_preserve_suspended(
    member_client,
    client_a,
    cloud_subscription_a,
):
    """C3: Suspended CloudAssetSubscription blocks member with 403, preserves suspended on admin sanction/renew, and hides UI controls."""
    cloud_subscription_a.approval_status = "shadow_it_flagged"
    cloud_subscription_a.status = "suspended"
    cloud_subscription_a.save()

    orig_name = cloud_subscription_a.name
    orig_approval = cloud_subscription_a.approval_status
    orig_renewal = cloud_subscription_a.renewal_date

    edit_url = reverse("assets:cloud_asset_subscription_edit", args=[cloud_subscription_a.pk])
    sanction_url = reverse("assets:cloud_asset_subscription_sanction", args=[cloud_subscription_a.pk])
    shadow_url = reverse("assets:cloud_asset_subscription_flag_shadow", args=[cloud_subscription_a.pk])
    finops_url = reverse("assets:cloud_asset_subscription_sync_finops", args=[cloud_subscription_a.pk])
    renew_url = reverse("assets:cloud_asset_subscription_renew", args=[cloud_subscription_a.pk])

    # Member receives 403 on edit GET/POST and all 4 non-admin workflow actions
    assert member_client.get(edit_url).status_code == 403
    assert (
        member_client.post(
            edit_url,
            data=_it_asset_management_cloud_payload(name="Unsuspend Tamper"),
        ).status_code
        == 403
    )
    for action_url in (sanction_url, shadow_url, finops_url, renew_url):
        assert member_client.post(action_url).status_code == 403

    cloud_subscription_a.refresh_from_db()
    assert cloud_subscription_a.status == "suspended"
    assert cloud_subscription_a.name == orig_name
    assert cloud_subscription_a.approval_status == orig_approval
    assert cloud_subscription_a.renewal_date == orig_renewal

    # UI gate symmetry for member vs admin on cloud_asset_subscription/detail.html
    detail_url = reverse("assets:cloud_asset_subscription_detail", args=[cloud_subscription_a.pk])
    member_html = member_client.get(detail_url).content.decode("utf-8")
    for hidden_url in (finops_url, sanction_url, renew_url, edit_url):
        assert hidden_url not in member_html

    admin_html = client_a.get(detail_url).content.decode("utf-8")
    for visible_url in (finops_url, sanction_url, renew_url, edit_url):
        assert visible_url in admin_html

    # Even admin POST to sanction and renew does NOT lift suspended status
    assert client_a.post(sanction_url).status_code == 302
    cloud_subscription_a.refresh_from_db()
    assert cloud_subscription_a.approval_status == "sanctioned"
    assert cloud_subscription_a.status == "suspended"

    assert client_a.post(renew_url).status_code == 302
    cloud_subscription_a.refresh_from_db()
    assert cloud_subscription_a.status == "suspended"
    assert cloud_subscription_a.renewal_date > orig_renewal


def test_it_asset_management_c4_hardware_sanitization_tampering_blocked_for_member(
    member_client,
    client_a,
    admin_user,
    tenant_a,
    it_hardware_a,
):
    """C4: Member cannot forge NIST sanitization fields on create or edit, and form template hides them."""
    # Form template symmetry
    create_url = reverse("assets:it_hardware_asset_create")
    member_form_html = member_client.get(create_url).content.decode("utf-8")
    admin_form_html = client_a.get(create_url).content.decode("utf-8")
    assert 'name="sanitization_status"' not in member_form_html
    assert "managed by tenant administrators" in member_form_html
    assert 'name="sanitization_status"' in admin_form_html

    # 1. Member POST create attempting to forge sanitization fields
    tampered_create = _it_asset_management_hw_payload(
        hostname="c4-member-created-hw",
        sanitization_required="",
        sanitization_method="nist_purge",
        sanitization_status="certificate_on_file",
        sanitization_date=timezone.localdate().isoformat(),
        sanitization_certificate_ref="FORGED-CERT-999",
    )
    tampered_create.pop("sanitization_required", None)
    resp = member_client.post(create_url, data=tampered_create)
    assert resp.status_code == 302
    created_hw = ItHardwareAsset.objects.get(tenant=tenant_a, hostname="c4-member-created-hw")
    assert created_hw.sanitization_required is True
    assert created_hw.sanitization_method == "none"
    assert created_hw.sanitization_status == "pending_wipe"
    assert created_hw.sanitization_date is None
    assert created_hw.sanitization_certificate_ref == ""
    assert created_hw.sanitization_verified_by is None
    assert created_hw.sanitized_at is None

    # 2. Admin verifies it_hardware_a, then member edits it attempting to downgrade/tamper sanitization
    verified_date = timezone.localdate() - timedelta(days=3)
    verified_ts = timezone.now() - timedelta(days=3)
    it_hardware_a.sanitization_required = True
    it_hardware_a.sanitization_method = "nist_purge"
    it_hardware_a.sanitization_status = "certificate_on_file"
    it_hardware_a.sanitization_date = verified_date
    it_hardware_a.sanitization_certificate_ref = "CERT-ADMIN-2026-01"
    it_hardware_a.sanitization_verified_by = admin_user
    it_hardware_a.sanitized_at = verified_ts
    it_hardware_a.save()

    edit_url = reverse("assets:it_hardware_asset_edit", args=[it_hardware_a.pk])
    tampered_edit = _it_asset_management_hw_payload(
        hostname="c4-member-edited-hostname",
        sanitization_method="none",
        sanitization_status="wiped_verified",
        sanitization_date=timezone.localdate().isoformat(),
        sanitization_certificate_ref="TAMPERED-CERT-000",
    )
    tampered_edit.pop("sanitization_required", None)
    edit_resp = member_client.post(edit_url, data=tampered_edit)
    assert edit_resp.status_code == 302

    it_hardware_a.refresh_from_db()
    assert it_hardware_a.hostname == "c4-member-edited-hostname"
    assert it_hardware_a.sanitization_required is True
    assert it_hardware_a.sanitization_method == "nist_purge"
    assert it_hardware_a.sanitization_status == "certificate_on_file"
    assert it_hardware_a.sanitization_date == verified_date
    assert it_hardware_a.sanitization_certificate_ref == "CERT-ADMIN-2026-01"
    assert it_hardware_a.sanitization_verified_by == admin_user
    assert it_hardware_a.sanitized_at == verified_ts


def test_it_asset_management_i1_locked_hardware_cannot_be_resanitized_or_mutated(
    client_a,
    admin_user,
    it_hardware_a,
):
    """I1: sanitized_retired and disposed hardware cannot be re-sanitized, edited, or deleted by admin."""
    orig_sanitized_at = timezone.now() - timedelta(days=10)
    it_hardware_a.status = "sanitized_retired"
    it_hardware_a.sanitization_status = "wiped_verified"
    it_hardware_a.sanitization_method = "nist_clear"
    it_hardware_a.sanitization_verified_by = admin_user
    it_hardware_a.sanitized_at = orig_sanitized_at
    it_hardware_a.save()

    sanitize_url = reverse("assets:it_hardware_asset_mark_sanitized", args=[it_hardware_a.pk])
    resp = client_a.post(sanitize_url)
    assert resp.status_code == 302
    assert any("cannot be modified" in m for m in _it_asset_management_messages(resp))

    it_hardware_a.refresh_from_db()
    assert it_hardware_a.status == "sanitized_retired"
    assert it_hardware_a.sanitization_method == "nist_clear"
    assert it_hardware_a.sanitized_at == orig_sanitized_at

    # Locked edit/delete/retire also blocked
    assert (
        client_a.post(
            reverse("assets:it_hardware_asset_edit", args=[it_hardware_a.pk]),
            data=_it_asset_management_hw_payload(hostname="tampered-locked"),
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:it_hardware_asset_delete", args=[it_hardware_a.pk])
        ).status_code
        == 302
    )
    it_hardware_a.refresh_from_db()
    assert it_hardware_a.hostname != "tampered-locked"
    assert ItHardwareAsset.objects.filter(pk=it_hardware_a.pk).exists()


def test_it_asset_management_locked_software_cloud_cmdb_cannot_be_mutated(
    client_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    software_license_a.status = "retired"
    software_license_a.save()
    cloud_subscription_a.status = "cancelled"
    cloud_subscription_a.save()
    cmdb_relationship_a.status = "severed"
    cmdb_relationship_a.save()

    for url in (
        reverse("assets:software_license_edit", args=[software_license_a.pk]),
        reverse("assets:software_license_delete", args=[software_license_a.pk]),
        reverse("assets:software_license_sync_compliance", args=[software_license_a.pk]),
        reverse("assets:cloud_asset_subscription_edit", args=[cloud_subscription_a.pk]),
        reverse("assets:cloud_asset_subscription_delete", args=[cloud_subscription_a.pk]),
        reverse("assets:cloud_asset_subscription_sanction", args=[cloud_subscription_a.pk]),
        reverse("assets:cmdb_relationship_edit", args=[cmdb_relationship_a.pk]),
        reverse("assets:cmdb_relationship_delete", args=[cmdb_relationship_a.pk]),
        reverse("assets:cmdb_relationship_verify", args=[cmdb_relationship_a.pk]),
    ):
        assert client_a.post(url, data={}).status_code == 302

    assert SoftwareLicense.objects.filter(pk=software_license_a.pk, status="retired").exists()
    assert CloudAssetSubscription.objects.filter(pk=cloud_subscription_a.pk, status="cancelled").exists()
    assert CmdbRelationship.objects.filter(pk=cmdb_relationship_a.pk, status="severed").exists()


def test_it_asset_management_i2_cmdb_verify_blocks_duplicate_active_edge(
    client_a,
    tenant_a,
    software_license_a,
    it_hardware_a,
    cmdb_relationship_a,
):
    """I2: Promoting a planned/deprecated duplicate edge to active via verify runs full_clean()."""
    dup_edge = CmdbRelationship.objects.create(
        tenant=tenant_a,
        source_ci_type="software_license",
        source_software=software_license_a,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
        status="planned",
    )
    resp = client_a.post(reverse("assets:cmdb_relationship_verify", args=[dup_edge.pk]))
    assert resp.status_code == 302
    assert any("already exists" in m.lower() for m in _it_asset_management_messages(resp))
    dup_edge.refresh_from_db()
    assert dup_edge.status == "planned"


# =====================================================================
# 5. Mass-Assignment, Cross-Tenant FK Injection, XSS, CSV & M2
# =====================================================================


def test_it_asset_management_mass_assignment_protected_fields_ignored(
    client_a,
    tenant_a,
    tenant_b,
    admin_b,
    software_license_a,
    it_hardware_a,
):
    # 1. Hardware create with forged tenant, number, status, sanitization_verified_by
    hw_resp = client_a.post(
        reverse("assets:it_hardware_asset_create"),
        data=_it_asset_management_hw_payload(
            hostname="mass-assign-hw",
            tenant=str(tenant_b.pk),
            number="ITHW-FORGED-999",
            status="sanitized_retired",
            sanitization_verified_by=str(admin_b.pk),
        ),
    )
    assert hw_resp.status_code == 302
    hw = ItHardwareAsset.objects.get(hostname="mass-assign-hw")
    assert hw.tenant == tenant_a
    assert hw.number.startswith("ITHW-") and hw.number != "ITHW-FORGED-999"
    assert hw.status == "procured"
    assert hw.sanitization_verified_by is None

    # 2. Software create with forged tenant, number, status
    sw_resp = client_a.post(
        reverse("assets:software_license_create"),
        data=_it_asset_management_sw_payload(
            software_name="Mass Assign SW",
            allocated_quantity="24",
            reclaimable_inactive_count="0",
            tenant=str(tenant_b.pk),
            number="ITSW-FORGED-999",
            status="retired",
        ),
    )
    assert sw_resp.status_code == 302
    sw = SoftwareLicense.objects.get(software_name="Mass Assign SW")
    assert sw.tenant == tenant_a
    assert sw.number != "ITSW-FORGED-999"
    assert sw.status == "active_compliant"

    # 3. Cloud create with forged tenant, number, status
    cl_resp = client_a.post(
        reverse("assets:cloud_asset_subscription_create"),
        data=_it_asset_management_cloud_payload(
            name="Mass Assign Cloud",
            tenant=str(tenant_b.pk),
            number="ITCL-FORGED-999",
            status="cancelled",
        ),
    )
    assert cl_resp.status_code == 302
    cl = CloudAssetSubscription.objects.get(name="Mass Assign Cloud")
    assert cl.tenant == tenant_a
    assert cl.number != "ITCL-FORGED-999"
    assert cl.status == "active"

    # 4. CMDB create with forged tenant, number, status, verified_by
    cmdb_resp = client_a.post(
        reverse("assets:cmdb_relationship_create"),
        data=_it_asset_management_cmdb_payload(
            software_license_a,
            it_hardware_a,
            relationship_type="depends_on",
            tenant=str(tenant_b.pk),
            number="CMDB-FORGED-999",
            status="severed",
            verified_by=str(admin_b.pk),
        ),
    )
    assert cmdb_resp.status_code == 302
    rel = CmdbRelationship.objects.get(
        source_software=software_license_a,
        target_hardware=it_hardware_a,
        relationship_type="depends_on",
    )
    assert rel.tenant == tenant_a
    assert rel.number != "CMDB-FORGED-999"
    assert rel.status == "active"
    assert rel.verified_by != admin_b


def test_it_asset_management_cross_tenant_fk_injection_rejected_by_views_and_forms(
    client_a,
    tenant_a,
    org_unit_b,
    location_b,
    vendor_party_b,
    it_hardware_b,
    software_license_b,
    cloud_subscription_b,
    admin_b,
    software_license_a,
    it_hardware_a,
):
    # Hardware POST with tenant_b FKs
    hw_before = ItHardwareAsset.objects.count()
    r_hw = client_a.post(
        reverse("assets:it_hardware_asset_create"),
        data=_it_asset_management_hw_payload(
            hostname="fk-inject-hw",
            org_unit=str(org_unit_b.pk),
            location=str(location_b.pk),
            vendor_party=str(vendor_party_b.pk),
        ),
    )
    assert r_hw.status_code == 200
    assert ItHardwareAsset.objects.count() == hw_before

    # Software POST with tenant_b FKs
    sw_before = SoftwareLicense.objects.count()
    r_sw = client_a.post(
        reverse("assets:software_license_create"),
        data=_it_asset_management_sw_payload(
            software_name="FK Inject SW",
            org_unit=str(org_unit_b.pk),
            publisher_party=str(vendor_party_b.pk),
            license_owner=str(admin_b.pk),
        ),
    )
    assert r_sw.status_code == 200
    assert SoftwareLicense.objects.count() == sw_before

    # Cloud POST with tenant_b FKs
    cl_before = CloudAssetSubscription.objects.count()
    r_cl = client_a.post(
        reverse("assets:cloud_asset_subscription_create"),
        data=_it_asset_management_cloud_payload(
            name="FK Inject Cloud",
            org_unit=str(org_unit_b.pk),
            vendor_party=str(vendor_party_b.pk),
            business_owner=str(admin_b.pk),
        ),
    )
    assert r_cl.status_code == 200
    assert CloudAssetSubscription.objects.count() == cl_before

    # CMDB POST with tenant_b source/target CI FKs
    cmdb_before = CmdbRelationship.objects.count()
    r_cmdb = client_a.post(
        reverse("assets:cmdb_relationship_create"),
        data=_it_asset_management_cmdb_payload(
            software_license_b,
            it_hardware_b,
        ),
    )
    assert r_cmdb.status_code == 200
    assert CmdbRelationship.objects.count() == cmdb_before

    # Direct form-level reject_foreign check on CloudAssetSubscriptionForm & CmdbRelationshipForm
    f_cloud = CloudAssetSubscriptionForm(
        data=_it_asset_management_cloud_payload(org_unit=str(org_unit_b.pk)),
        tenant=tenant_a,
    )
    assert not f_cloud.is_valid()
    assert "org_unit" in f_cloud.errors

    f_cmdb = CmdbRelationshipForm(
        data=_it_asset_management_cmdb_payload(
            software_license_a,
            it_hardware_a,
            source_ci_type="cloud_asset",
            source_cloud=str(cloud_subscription_b.pk),
        ),
        tenant=tenant_a,
    )
    assert not f_cmdb.is_valid()
    assert "source_cloud" in f_cmdb.errors


def test_it_asset_management_xss_escaped_in_templates_and_csv_formula_neutralized(
    client_a,
    tenant_a,
):
    xss_payload = "<script>alert(1)</script>"
    formula_payload = "=CMD|'/C calc'!A0"
    plus_payload = "+SUM(1,2)"

    # Verify direct csv_safe behavior
    for bad in ("=CMD|'/C calc'!A0", "+SUM(1,2)", "-1+1", "@SUM(A1:A2)", "\t=1", "\r+1", "\n-1", " =CMD()"):
        assert csv_safe(bad).startswith("'")

    hw = ItHardwareAsset.objects.create(
        tenant=tenant_a,
        hostname=xss_payload,
        serial_number=formula_payload,
        refresh_due_date=timezone.localdate() - timedelta(days=1),
        sanitization_required=True,
        sanitization_status="pending_wipe",
        notes=xss_payload,
    )
    sw = SoftwareLicense.objects.create(
        tenant=tenant_a,
        software_name=xss_payload,
        publisher_name=formula_payload,
        renewal_date=timezone.localdate() + timedelta(days=5),
        notes=xss_payload,
    )
    cl = CloudAssetSubscription.objects.create(
        tenant=tenant_a,
        name=xss_payload,
        external_account_id=plus_payload,
        resource_tags={"<script>tag</script>": xss_payload},
        renewal_date=timezone.localdate() + timedelta(days=5),
        notes=xss_payload,
    )
    rel = CmdbRelationship.objects.create(
        tenant=tenant_a,
        source_ci_type="software_license",
        source_software=sw,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=hw,
        is_single_point_of_failure=True,
        blast_radius_notes=xss_payload,
    )

    # Templates must HTML-escape <script>alert(1)</script> across lists, details, and workbenches
    for url in (
        reverse("assets:it_hardware_asset_list"),
        reverse("assets:it_hardware_asset_detail", args=[hw.pk]),
        reverse("assets:software_license_list"),
        reverse("assets:software_license_detail", args=[sw.pk]),
        reverse("assets:cloud_asset_subscription_list"),
        reverse("assets:cloud_asset_subscription_detail", args=[cl.pk]),
        reverse("assets:cmdb_relationship_list"),
        reverse("assets:cmdb_relationship_detail", args=[rel.pk]),
        reverse("assets:it_refresh_board") + "?horizon=365",
        reverse("assets:cmdb_impact_analysis") + f"?ci=it_hardware:{hw.pk}",
    ):
        resp = client_a.get(url)
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert xss_payload not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

    # M8: Cloud resource_tags dict key/value escaped cleanly
    cl_detail = client_a.get(
        reverse("assets:cloud_asset_subscription_detail", args=[cl.pk])
    ).content.decode("utf-8")
    assert "<script>tag</script>" not in cl_detail
    assert "&lt;script&gt;tag&lt;/script&gt;" in cl_detail

    # M8: CMDB form uses |escapejs
    cmdb_form_html = client_a.get(reverse("assets:cmdb_relationship_create")).content.decode("utf-8")
    assert "syncSide('source'" in cmdb_form_html
    assert "syncSide('target'" in cmdb_form_html

    # All 6 CSV exports neutralize formula prefixes and include X-Content-Type-Options: nosniff
    expected_csv_checks = [
        (reverse("assets:it_hardware_asset_export_csv"), f"'{formula_payload}", formula_payload),
        (reverse("assets:software_license_export_csv"), f"'{formula_payload}", formula_payload),
        (reverse("assets:cloud_asset_subscription_export_csv"), f"'{plus_payload}", plus_payload),
        (reverse("assets:cmdb_relationship_export_csv"), None, None),
        (reverse("assets:it_refresh_board_export_csv") + "?horizon=365", None, None),
        (reverse("assets:cmdb_impact_analysis_export_csv") + f"?ci=it_hardware:{hw.pk}", None, None),
    ]
    for csv_url, prefixed, raw in expected_csv_checks:
        csv_resp = client_a.get(csv_url)
        assert csv_resp.status_code == 200
        assert csv_resp["X-Content-Type-Options"] == "nosniff"
        assert "text/csv" in csv_resp["Content-Type"]
        if prefixed and raw:
            rows = _it_asset_management_parse_csv(csv_resp)
            flat_cells = [cell for row in rows[1:] for cell in row]
            assert prefixed in flat_cells
            assert raw not in flat_cells


@pytest.mark.parametrize(
    "raw_secret",
    [
        "ABCD1-EFGH2-IJKL3-MNOP4",
        "AKIAIOSFODNN7EXAMPLE",
        "sk_live_1234567890abcdef1234",
        "ghp_1234567890abcdef1234567890abcdef",
        "0123456789abcdef0123456789abcdef",
        "x123-y456-z789-w012",
    ],
)
def test_it_asset_management_m2_raw_license_keys_rejected_by_form_and_model_clean(
    raw_secret,
    tenant_a,
):
    """M2: Unmasked keys & API tokens are rejected by both SoftwareLicenseForm and SoftwareLicense.clean()."""
    form = SoftwareLicenseForm(
        data=_it_asset_management_software_payload_m2(raw_secret),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "license_key_ref" in form.errors

    lic = SoftwareLicense(
        tenant=tenant_a,
        software_name="Secret Check App",
        publisher_name="Vendor",
        license_key_ref=raw_secret,
    )
    with pytest.raises(ValidationError) as exc_info:
        lic.full_clean()
    assert "license_key_ref" in exc_info.value.message_dict


def _it_asset_management_software_payload_m2(license_key_ref):
    return _it_asset_management_sw_payload(license_key_ref=license_key_ref)


def test_it_asset_management_m2_masked_license_key_refs_accepted(tenant_a):
    for masked in ("MS365-****-9X2K", "ACME-XXXX-1234", "EA-REF-01"):
        form = SoftwareLicenseForm(
            data=_it_asset_management_software_payload_m2(masked),
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

        lic = SoftwareLicense(
            tenant=tenant_a,
            software_name="Masked Check App",
            publisher_name="Vendor",
            license_key_ref=masked,
        )
        lic.full_clean()


def test_it_asset_management_adversarial_query_params_never_500(client_a):
    chaos_params = {
        "q": "\x00'\"<>%s%n",
        "status": "bogus_status",
        "device_class": "bogus",
        "environment": "bogus",
        "disk_encryption_status": "bogus",
        "eol_state": "bogus",
        "software_category": "bogus",
        "license_type": "bogus",
        "license_metric": "bogus",
        "asset_kind": "bogus",
        "provider": "bogus",
        "approval_status": "bogus",
        "sso_status": "bogus",
        "relationship_type": "bogus",
        "source_ci_type": "bogus",
        "target_ci_type": "bogus",
        "criticality": "bogus",
        "spof": "maybe",
        "org_unit": "99999999999999999999",
        "horizon": "-999",
        "priority": "bogus",
        "ci": "it_hardware:NaN;DROP TABLE",
        "page": "99999999999999999999",
    }
    for url_name in (
        "assets:it_hardware_asset_list",
        "assets:software_license_list",
        "assets:cloud_asset_subscription_list",
        "assets:cmdb_relationship_list",
        "assets:it_refresh_board",
        "assets:cmdb_impact_analysis",
        "assets:it_hardware_asset_export_csv",
        "assets:software_license_export_csv",
        "assets:cloud_asset_subscription_export_csv",
        "assets:cmdb_relationship_export_csv",
        "assets:it_refresh_board_export_csv",
        "assets:cmdb_impact_analysis_export_csv",
    ):
        assert client_a.get(reverse(url_name), data=chaos_params).status_code == 200


# =====================================================================
# 6. Django Admin 11.18 Lock Guards & Readonly Fields
# =====================================================================


def test_it_asset_management_django_admin_lock_guards_and_readonly_fields(
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    su, _ = _it_asset_management_superuser_client()
    request = RequestFactory().get("/admin/")
    request.user = su

    cases = [
        (
            ItHardwareAssetAdmin(ItHardwareAsset, django_admin.site),
            it_hardware_a,
            ("sanitized_retired", "disposed"),
            (
                "number",
                "status",
                "last_seen_checkin",
                "sanitization_verified_by",
                "sanitized_at",
                "retired_at",
                "created_at",
                "updated_at",
            ),
        ),
        (
            SoftwareLicenseAdmin(SoftwareLicense, django_admin.site),
            software_license_a,
            ("retired",),
            (
                "number",
                "status",
                "last_reconciled_at",
                "retired_at",
                "created_at",
                "updated_at",
            ),
        ),
        (
            CloudAssetSubscriptionAdmin(CloudAssetSubscription, django_admin.site),
            cloud_subscription_a,
            ("cancelled",),
            (
                "number",
                "status",
                "last_finops_sync_at",
                "decommissioned_at",
                "created_at",
                "updated_at",
            ),
        ),
        (
            CmdbRelationshipAdmin(CmdbRelationship, django_admin.site),
            cmdb_relationship_a,
            ("severed",),
            (
                "number",
                "status",
                "verified_on",
                "verified_by",
                "severed_at",
                "created_at",
                "updated_at",
            ),
        ),
    ]

    for model_admin, obj, locked_statuses, expected_readonly in cases:
        # Unlocked object allows change & delete for superuser
        assert model_admin.has_change_permission(request, obj=obj) is True
        assert model_admin.has_delete_permission(request, obj=obj) is True

        readonly = set(model_admin.get_readonly_fields(request, obj=obj))
        for field_name in expected_readonly:
            assert field_name in readonly

        # Locked statuses deny change & delete in Django Admin
        for locked_status in locked_statuses:
            obj.status = locked_status
            assert model_admin.has_change_permission(request, obj=obj) is False
            assert model_admin.has_delete_permission(request, obj=obj) is False
