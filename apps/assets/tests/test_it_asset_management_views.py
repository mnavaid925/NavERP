"""
View, workflow, workbench, CSV export, and query-budget tests for Module 11.18:
IT Asset Management (ITAM).

Covers:
1. Navigation & URL contract (LIVE_LINKS["11.18"], context keys, auth redirect).
2. List views, filters, junk param resilience, pagination (PAGE_SIZE=15, I5),
   row actions (I6), and .empty-state CTAs (I7).
3. Detail, Create, Edit, Delete CRUD, locked-record guards, tenant-None create
   guard (I3), detail KPI icons (stat-icon orange I4), resource_tags pills (M8),
   non-admin sanitization restriction (C4), and zero template comment leaks.
4. Lifecycle / governance workflow POST actions + AuditLog (action <= 10 chars,
   changes dict M3), including I1, I2, C2, and C3 regressions.
5. Computed workbenches: ItRefreshBoards (I9 SQL KPIs, OrgUnit CapEx rollup,
   200-row slice safety) and CmdbImpactAnalyses (I10 bounded label_map, BFS
   hop<=8, cycle safety, upstream/downstream blast radius, SPOF labels).
6. All 6 CSV exports (headers, text/csv, X-Content-Type-Options: nosniff,
   csv_safe formula-injection neutralization, filtered exports).
7. O(1) query budgets (django_assert_max_num_queries & CaptureQueriesContext)
   across 4 lists, 4 details (I8 scrap_salvage__fixed_asset, M11 [:50] slice),
   ItRefreshBoards (I9), and CmdbImpactAnalyses (I10).
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    CloudAssetSubscription,
    CmdbRelationship,
    ItHardwareAsset,
    SoftwareLicense,
)
from apps.core.models import AuditLog, ServiceComponent
from apps.core.navigation import LIVE_LINKS

User = get_user_model()

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (Must start with _it_asset_management_*)
# =====================================================================


def _it_asset_management_make_hardware(tenant, hostname="srv-edge-01", **kwargs):
    data = {
        "tenant": tenant,
        "hostname": hostname,
        "device_class": "physical_server",
        "serial_number": f"SN-{hostname}",
        "environment": "production",
        "criticality": "high",
        "disk_encryption_status": "luks_encrypted",
        "status": "deployed",
        "estimated_refresh_cost": Decimal("1500.00"),
    }
    data.update(kwargs)
    return ItHardwareAsset.objects.create(**data)


def _it_asset_management_make_license(
    tenant, software_name="Grafana Enterprise", publisher_name="Grafana Labs", **kwargs
):
    data = {
        "tenant": tenant,
        "software_name": software_name,
        "publisher_name": publisher_name,
        "software_category": "devops_ide",
        "license_type": "subscription_term",
        "license_metric": "per_user",
        "entitled_quantity": 50,
        "allocated_quantity": 45,
        "active_used_quantity": 40,
        "reclaimable_inactive_count": 0,
        "unit_license_cost": Decimal("100.00"),
        "total_annual_spend": Decimal("5000.00"),
        "status": "active_compliant",
    }
    data.update(kwargs)
    return SoftwareLicense.objects.create(**data)


def _it_asset_management_make_cloud(tenant, name="Snowflake Data Cloud", **kwargs):
    data = {
        "tenant": tenant,
        "name": name,
        "asset_kind": "paas_database",
        "provider": "aws",
        "environment": "production",
        "billing_cadence": "monthly",
        "commitment_term": "annual_contract",
        "monthly_recurring_cost": Decimal("2000.00"),
        "annual_contract_value": Decimal("24000.00"),
        "provisioned_seats": 20,
        "active_seats_30d": 18,
        "sso_status": "sso_enforced",
        "approval_status": "sanctioned",
        "status": "active",
    }
    data.update(kwargs)
    return CloudAssetSubscription.objects.create(**data)


def _it_asset_management_make_service(tenant, name="Core Checkout API"):
    return ServiceComponent.objects.create(
        tenant=tenant,
        name=name,
        kind="api",
        current_status="operational",
    )


def _it_asset_management_make_cmdb(
    tenant,
    source_ci_type="software_license",
    target_ci_type="it_hardware",
    relationship_type="runs_on",
    **kwargs,
):
    data = {
        "tenant": tenant,
        "source_ci_type": source_ci_type,
        "target_ci_type": target_ci_type,
        "relationship_type": relationship_type,
        "environment": "production",
        "criticality": "tier_2_business_important",
        "impact_severity": "degraded_performance",
        "status": "active",
    }
    data.update(kwargs)
    return CmdbRelationship.objects.create(**data)


def _it_asset_management_latest_audit(tenant, obj, action=None):
    ct = ContentType.objects.get_for_model(obj.__class__)
    qs = AuditLog.objects.filter(tenant=tenant, content_type=ct, object_id=obj.pk)
    if action is not None:
        qs = qs.filter(action=action)
    return qs.order_by("-id").first()


def _it_asset_management_messages(response):
    return [m.message for m in get_messages(response.wsgi_request)]


def _it_asset_management_assert_no_template_leaks(html):
    assert "{#" not in html
    assert "{% comment" not in html


def _it_asset_management_hardware_post_data(**overrides):
    data = {
        "hostname": "nyc-k8s-node09",
        "fqdn": "nyc-k8s-node09.acme.local",
        "device_class": "physical_server",
        "serial_number": "SN-NYC-K8S-09",
        "asset_tag_code": "IT-K8S-009",
        "manufacturer": "HPE",
        "model_name": "ProLiant DL380",
        "operating_system": "Ubuntu",
        "os_version": "24.04",
        "environment": "production",
        "criticality": "critical",
        "mdm_enrolled": "on",
        "mdm_platform": "CrowdStrike",
        "disk_encryption_status": "luks_encrypted",
        "refresh_cycle_months": "48",
        "estimated_refresh_cost": "7500.00",
        "sanitization_required": "on",
        "sanitization_method": "none",
        "sanitization_status": "pending_wipe",
    }
    data.update(overrides)
    return data


def _it_asset_management_software_post_data(**overrides):
    data = {
        "software_name": "Datadog Enterprise",
        "publisher_name": "Datadog",
        "product_sku": "DD-ENT-2026",
        "software_category": "security_edr",
        "license_type": "subscription_term",
        "license_metric": "per_device",
        "license_key_ref": "DDENT-****-4A9C",
        "entitled_quantity": "40",
        "allocated_quantity": "38",
        "active_used_quantity": "35",
        "reclaimable_inactive_count": "2",
        "unit_license_cost": "150.00",
        "total_annual_spend": "6000.00",
    }
    data.update(overrides)
    return data


def _it_asset_management_cloud_post_data(**overrides):
    data = {
        "name": "PagerDuty Enterprise",
        "asset_kind": "saas_application",
        "provider": "other_saas",
        "external_account_id": "pd-acme-991",
        "cloud_region": "us-east-1",
        "environment": "corporate_saas",
        "resource_tags": '{"env": "prod", "cost_center": "CC-SRE", "owner": "oncall"}',
        "billing_cadence": "annual",
        "commitment_term": "annual_contract",
        "monthly_recurring_cost": "1200.00",
        "annual_contract_value": "14400.00",
        "provisioned_seats": "25",
        "active_seats_30d": "20",
        "sso_status": "sso_enforced",
        "approval_status": "sanctioned",
        "cancellation_notice_days": "30",
        "auto_renew": "on",
    }
    data.update(overrides)
    return data


# =====================================================================
# 1. Navigation & URL Contract
# =====================================================================


def test_it_asset_management_live_links_reverse_and_return_200(
    client_a,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    links = LIVE_LINKS.get("11.18")
    assert links == {
        "Hardware Lifecycle Management": "assets:it_hardware_asset_list",
        "Software License Management": "assets:software_license_list",
        "Cloud Asset & Subscription Tracking": "assets:cloud_asset_subscription_list",
        "Configuration Management Database (CMDB)": "assets:cmdb_relationship_list",
        "End-of-Life & Refresh Cycles": "assets:it_refresh_board",
        "CMDB Impact Analysis": "assets:cmdb_impact_analysis",
    }
    for url_name in links.values():
        resp = client_a.get(reverse(url_name))
        assert resp.status_code == 200
        _it_asset_management_assert_no_template_leaks(resp.content.decode())


def test_it_asset_management_anonymous_redirects_to_login(
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    anon = Client()
    urls = [
        reverse("assets:it_hardware_asset_list"),
        reverse("assets:it_hardware_asset_create"),
        reverse("assets:it_hardware_asset_detail", args=[it_hardware_a.pk]),
        reverse("assets:software_license_list"),
        reverse("assets:cloud_asset_subscription_list"),
        reverse("assets:cmdb_relationship_list"),
        reverse("assets:it_refresh_board"),
        reverse("assets:cmdb_impact_analysis"),
        reverse("assets:it_hardware_asset_export_csv"),
    ]
    for url in urls:
        resp = anon.get(url)
        assert resp.status_code == 302
        assert "login" in resp.url


def test_it_asset_management_list_views_context_contract(
    client_a,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    hw_resp = client_a.get(reverse("assets:it_hardware_asset_list"))
    assert hw_resp.status_code == 200
    for key in (
        "hardware_assets",
        "page_obj",
        "paginator",
        "total_count",
        "deployed_count",
        "eol_due_count",
        "pending_wipe_count",
        "status_choices",
        "device_class_choices",
        "environment_choices",
        "encryption_choices",
        "org_units",
        "search_query",
    ):
        assert key in hw_resp.context

    sw_resp = client_a.get(reverse("assets:software_license_list"))
    assert sw_resp.status_code == 200
    for key in (
        "licenses",
        "page_obj",
        "paginator",
        "total_count",
        "compliant_count",
        "true_up_count",
        "reclaimable_seats_total",
        "status_choices",
        "category_choices",
        "license_type_choices",
        "metric_choices",
        "org_units",
        "search_query",
    ):
        assert key in sw_resp.context

    cl_resp = client_a.get(reverse("assets:cloud_asset_subscription_list"))
    assert cl_resp.status_code == 200
    for key in (
        "cloud_assets",
        "page_obj",
        "paginator",
        "total_count",
        "monthly_spend_total",
        "shadow_flagged_count",
        "underutilized_count",
        "status_choices",
        "asset_kind_choices",
        "provider_choices",
        "approval_choices",
        "sso_choices",
        "org_units",
        "search_query",
    ):
        assert key in cl_resp.context

    cmdb_resp = client_a.get(reverse("assets:cmdb_relationship_list"))
    assert cmdb_resp.status_code == 200
    for key in (
        "relationships",
        "page_obj",
        "paginator",
        "total_count",
        "active_count",
        "spof_count",
        "tier1_count",
        "status_choices",
        "relationship_type_choices",
        "ci_type_choices",
        "environment_choices",
        "criticality_choices",
        "search_query",
    ):
        assert key in cmdb_resp.context


# =====================================================================
# 2. List, Filter, Pagination (I5), Actions (I6) & Empty State (I7)
# =====================================================================


def test_it_asset_management_hardware_list_filters_and_empty_state(
    client_a, tenant_a, org_unit_a
):
    today = timezone.localdate()
    hw_match = _it_asset_management_make_hardware(
        tenant_a,
        hostname="db-prod-alpha",
        device_class="physical_server",
        environment="production",
        disk_encryption_status="luks_encrypted",
        status="deployed",
        org_unit=org_unit_a,
        vendor_eol_date=today - timedelta(days=5),
        sanitization_required=True,
        sanitization_status="pending_wipe",
    )
    hw_other = _it_asset_management_make_hardware(
        tenant_a,
        hostname="mac-user-beta",
        device_class="laptop",
        environment="corporate_enduser",
        disk_encryption_status="bitlocker_filevault",
        status="staged_in_stock",
        vendor_eos_date=today + timedelta(days=20),
        vendor_eol_date=today + timedelta(days=400),
        sanitization_required=False,
        sanitization_status="not_required",
    )

    url = reverse("assets:it_hardware_asset_list")
    r_q = client_a.get(url, {"q": "db-prod-alpha"})
    assert list(r_q.context["hardware_assets"]) == [hw_match]

    r_filters = client_a.get(
        url,
        {
            "status": "deployed",
            "device_class": "physical_server",
            "environment": "production",
            "disk_encryption_status": "luks_encrypted",
            "org_unit": str(org_unit_a.pk),
            "eol_state": "eol_expired",
        },
    )
    assert list(r_filters.context["hardware_assets"]) == [hw_match]

    r_eos = client_a.get(url, {"eol_state": "eos_soon"})
    assert list(r_eos.context["hardware_assets"]) == [hw_other]

    r_wipe = client_a.get(url, {"eol_state": "pending_wipe"})
    assert list(r_wipe.context["hardware_assets"]) == [hw_match]

    r_junk = client_a.get(
        url,
        {
            "status": "INVALID",
            "device_class": "INVALID",
            "org_unit": "not-an-int",
            "eol_state": "unknown",
        },
    )
    assert r_junk.status_code == 200
    assert r_junk.context["paginator"].count == 2

    r_empty = client_a.get(url, {"q": "no-such-hostname-999"})
    assert r_empty.status_code == 200
    empty_html = r_empty.content.decode()
    assert 'class="empty-state"' in empty_html
    assert reverse("assets:it_hardware_asset_create") in empty_html


def test_it_asset_management_software_list_filters_and_empty_state(
    client_a, tenant_a, org_unit_a
):
    sw_match = _it_asset_management_make_license(
        tenant_a,
        software_name="Oracle DB Enterprise",
        publisher_name="Oracle",
        software_category="database_engine",
        license_type="enterprise_ela",
        license_metric="per_core",
        status="true_up_required",
        org_unit=org_unit_a,
    )
    _it_asset_management_make_license(
        tenant_a,
        software_name="Figma Pro",
        publisher_name="Figma",
        software_category="design_cad",
        license_type="subscription_term",
        license_metric="per_user",
        status="active_compliant",
    )

    url = reverse("assets:software_license_list")
    r_q = client_a.get(
        url,
        {
            "q": "Oracle",
            "status": "true_up_required",
            "software_category": "database_engine",
            "license_type": "enterprise_ela",
            "license_metric": "per_core",
            "org_unit": str(org_unit_a.pk),
        },
    )
    assert list(r_q.context["licenses"]) == [sw_match]

    r_junk = client_a.get(url, {"status": "bad", "org_unit": "9999999999999"})
    assert r_junk.status_code == 200
    assert r_junk.context["paginator"].count == 2

    r_empty = client_a.get(url, {"q": "nonexistent-software-xyz"})
    assert r_empty.status_code == 200
    empty_html = r_empty.content.decode()
    assert 'class="empty-state"' in empty_html
    assert reverse("assets:software_license_create") in empty_html


def test_it_asset_management_cloud_list_filters_actions_and_empty_state(
    client_a, tenant_a, org_unit_a
):
    cl_match = _it_asset_management_make_cloud(
        tenant_a,
        name="Shadow AI Tool",
        asset_kind="ai_api_platform",
        provider="other_saas",
        sso_status="shadow_it_unapproved",
        approval_status="shadow_it_flagged",
        status="shadow_flagged",
        org_unit=org_unit_a,
    )
    _it_asset_management_make_cloud(
        tenant_a,
        name="AWS Core EKS",
        asset_kind="iaas_compute",
        provider="aws",
        sso_status="sso_enforced",
        approval_status="sanctioned",
        status="active",
    )

    url = reverse("assets:cloud_asset_subscription_list")
    r_filt = client_a.get(
        url,
        {
            "q": "Shadow AI",
            "status": "shadow_flagged",
            "asset_kind": "ai_api_platform",
            "provider": "other_saas",
            "approval_status": "shadow_it_flagged",
            "sso_status": "shadow_it_unapproved",
            "org_unit": str(org_unit_a.pk),
        },
    )
    assert list(r_filt.context["cloud_assets"]) == [cl_match]
    html = r_filt.content.decode()
    # I6 action buttons & header
    assert '<th class="th-actions">Actions</th>' in html
    assert reverse("assets:cloud_asset_subscription_detail", args=[cl_match.pk]) in html
    assert reverse("assets:cloud_asset_subscription_edit", args=[cl_match.pk]) in html
    assert reverse("assets:cloud_asset_subscription_delete", args=[cl_match.pk]) in html

    r_junk = client_a.get(url, {"provider": "invalid_cloud", "org_unit": "abc"})
    assert r_junk.status_code == 200
    assert r_junk.context["paginator"].count == 2

    r_empty = client_a.get(url, {"q": "missing-cloud-sub-999"})
    assert r_empty.status_code == 200
    empty_html = r_empty.content.decode()
    assert 'class="empty-state"' in empty_html
    assert reverse("assets:cloud_asset_subscription_create") in empty_html


def test_it_asset_management_cmdb_list_filters_actions_and_empty_state(
    client_a, tenant_a, it_hardware_a, software_license_a, cloud_subscription_a
):
    svc = _it_asset_management_make_service(tenant_a, "Billing Engine")
    rel_spof = _it_asset_management_make_cmdb(
        tenant_a,
        source_ci_type="service_component",
        source_service=svc,
        relationship_type="depends_on",
        target_ci_type="cloud_asset",
        target_cloud=cloud_subscription_a,
        environment="production",
        criticality="tier_1_mission_critical",
        is_single_point_of_failure=True,
        blast_radius_notes="Billing outage risk",
    )
    _it_asset_management_make_cmdb(
        tenant_a,
        source_ci_type="software_license",
        source_software=software_license_a,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
        environment="staging",
        criticality="tier_3_operational",
        is_single_point_of_failure=False,
    )

    url = reverse("assets:cmdb_relationship_list")
    r_filt = client_a.get(
        url,
        {
            "q": "Billing Engine",
            "status": "active",
            "relationship_type": "depends_on",
            "source_ci_type": "service_component",
            "target_ci_type": "cloud_asset",
            "environment": "production",
            "criticality": "tier_1_mission_critical",
            "spof": "1",
        },
    )
    assert list(r_filt.context["relationships"]) == [rel_spof]
    html = r_filt.content.decode()
    assert '<th class="th-actions">Actions</th>' in html
    assert reverse("assets:cmdb_relationship_detail", args=[rel_spof.pk]) in html
    assert reverse("assets:cmdb_relationship_edit", args=[rel_spof.pk]) in html
    assert reverse("assets:cmdb_relationship_delete", args=[rel_spof.pk]) in html

    r_non_spof = client_a.get(url, {"spof": "0"})
    assert len(r_non_spof.context["relationships"]) == 1

    r_junk = client_a.get(url, {"status": "bad", "spof": "maybe", "criticality": "bad"})
    assert r_junk.status_code == 200
    assert r_junk.context["paginator"].count == 2

    r_empty = client_a.get(url, {"q": "nonexistent-cmdb-edge-999"})
    assert r_empty.status_code == 200
    empty_html = r_empty.content.decode()
    assert 'class="empty-state"' in empty_html
    assert reverse("assets:cmdb_relationship_create") in empty_html


def test_it_asset_management_all_lists_paginate_at_15_with_standard_footer(
    client_a, tenant_a
):
    for i in range(16):
        _it_asset_management_make_hardware(tenant_a, hostname=f"node-{i:02d}")
        _it_asset_management_make_license(tenant_a, software_name=f"App-{i:02d}")
        _it_asset_management_make_cloud(tenant_a, name=f"Cloud-{i:02d}")

    hw0 = ItHardwareAsset.objects.filter(tenant=tenant_a).first()
    for i in range(16):
        svc = _it_asset_management_make_service(tenant_a, name=f"Svc-{i:02d}")
        _it_asset_management_make_cmdb(
            tenant_a,
            source_ci_type="service_component",
            source_service=svc,
            target_ci_type="it_hardware",
            target_hardware=hw0,
        )

    for url_name in (
        "assets:it_hardware_asset_list",
        "assets:software_license_list",
        "assets:cloud_asset_subscription_list",
        "assets:cmdb_relationship_list",
    ):
        url = reverse(url_name)
        p1 = client_a.get(url)
        assert p1.status_code == 200
        assert len(p1.context["page_obj"]) == 15
        assert p1.context["paginator"].num_pages == 2
        p1_html = p1.content.decode()
        assert '<div class="pagination">' in p1_html
        assert '<span class="muted">Showing 1' in p1_html

        p2 = client_a.get(url, {"page": "2"})
        assert p2.status_code == 200
        assert len(p2.context["page_obj"]) == 1
        assert '<span class="muted">Showing 16' in p2.content.decode()

        p_hi = client_a.get(url, {"page": "999"})
        assert p_hi.status_code == 200
        assert p_hi.context["page_obj"].number == 2

        p_bad = client_a.get(url, {"page": "abc"})
        assert p_bad.status_code == 200
        assert p_bad.context["page_obj"].number == 1


# =====================================================================
# 3. Detail, Create, Edit, Delete CRUD & C4/I3/I4/M8 Regressions
# =====================================================================


def test_it_asset_management_hardware_crud_c4_and_locked_guards(
    client_a, member_client, tenant_a, admin_user
):
    # Create via member (C4: sanitization fields not exposed; defaults stay pending_wipe)
    create_url = reverse("assets:it_hardware_asset_create")
    get_resp = member_client.get(create_url)
    assert get_resp.status_code == 200
    assert "sanitization_status" not in get_resp.context["form"].fields

    post_resp = member_client.post(
        create_url,
        _it_asset_management_hardware_post_data(
            hostname="member-created-node",
            sanitization_status="wiped_verified",
            sanitization_required="",
        ),
    )
    assert post_resp.status_code == 302
    hw = ItHardwareAsset.objects.get(tenant=tenant_a, hostname="member-created-node")
    assert hw.sanitization_status == "pending_wipe"
    assert hw.sanitization_required is True
    assert _it_asset_management_latest_audit(tenant_a, hw, "create") is not None

    # Detail render
    detail_url = reverse("assets:it_hardware_asset_detail", args=[hw.pk])
    detail_resp = client_a.get(detail_url)
    assert detail_resp.status_code == 200
    _it_asset_management_assert_no_template_leaks(detail_resp.content.decode())

    # Admin edit sets sanitization_status=wiped_verified -> syncs verified_by & sanitized_at (C4)
    edit_url = reverse("assets:it_hardware_asset_edit", args=[hw.pk])
    edit_resp = client_a.post(
        edit_url,
        _it_asset_management_hardware_post_data(
            hostname="admin-updated-node",
            sanitization_method="nist_purge",
            sanitization_status="wiped_verified",
        ),
    )
    assert edit_resp.status_code == 302
    hw.refresh_from_db()
    assert hw.hostname == "admin-updated-node"
    assert hw.sanitization_verified_by == admin_user
    assert hw.sanitized_at is not None
    assert _it_asset_management_latest_audit(tenant_a, hw, "update") is not None

    # Member cannot delete (403)
    del_url = reverse("assets:it_hardware_asset_delete", args=[hw.pk])
    assert member_client.post(del_url).status_code == 403
    assert ItHardwareAsset.objects.filter(pk=hw.pk).exists()

    # Locked hardware cannot be edited or deleted
    hw.status = "sanitized_retired"
    hw.save(update_fields=["status"])
    locked_edit = client_a.get(edit_url)
    assert locked_edit.status_code == 302
    assert "cannot be edited" in " ".join(_it_asset_management_messages(locked_edit))
    locked_del = client_a.post(del_url)
    assert locked_del.status_code == 302
    assert ItHardwareAsset.objects.filter(pk=hw.pk).exists()

    # Unlocked delete by admin succeeds
    hw.status = "procured"
    hw.save(update_fields=["status"])
    ok_del = client_a.post(del_url)
    assert ok_del.status_code == 302
    assert not ItHardwareAsset.objects.filter(pk=hw.pk).exists()


def test_it_asset_management_software_crud_i4_and_locked_guards(
    client_a, member_client, tenant_a
):
    create_url = reverse("assets:software_license_create")
    assert member_client.get(create_url).status_code == 200
    # Create with compliance_delta == 0 -> I4 stat-icon orange
    resp = member_client.post(
        create_url,
        _it_asset_management_software_post_data(
            entitled_quantity="40",
            allocated_quantity="40",
            reclaimable_inactive_count="0",
        ),
    )
    assert resp.status_code == 302
    lic = SoftwareLicense.objects.get(tenant=tenant_a, software_name="Datadog Enterprise")
    assert lic.status == "active_compliant"
    assert lic.compliance_delta == 0

    detail_resp = client_a.get(reverse("assets:software_license_detail", args=[lic.pk]))
    assert detail_resp.status_code == 200
    detail_html = detail_resp.content.decode()
    assert "stat-icon orange" in detail_html
    assert "stat-icon amber" not in detail_html
    _it_asset_management_assert_no_template_leaks(detail_html)

    # Edit
    edit_url = reverse("assets:software_license_edit", args=[lic.pk])
    r_edit = client_a.post(
        edit_url,
        _it_asset_management_software_post_data(
            software_name="Datadog Pro",
            entitled_quantity="40",
            allocated_quantity="45",
            reclaimable_inactive_count="0",
        ),
    )
    assert r_edit.status_code == 302
    lic.refresh_from_db()
    assert lic.software_name == "Datadog Pro"
    assert lic.status == "true_up_required"

    # Member delete forbidden, locked edit/delete blocked
    del_url = reverse("assets:software_license_delete", args=[lic.pk])
    assert member_client.post(del_url).status_code == 403
    lic.status = "retired"
    lic.save(update_fields=["status"])
    assert client_a.get(edit_url).status_code == 302
    assert client_a.post(del_url).status_code == 302
    assert SoftwareLicense.objects.filter(pk=lic.pk).exists()

    lic.status = "draft"
    lic.save(update_fields=["status"])
    assert client_a.post(del_url).status_code == 302
    assert not SoftwareLicense.objects.filter(pk=lic.pk).exists()


def test_it_asset_management_cloud_crud_i4_m8_and_locked_guards(
    client_a, member_client, tenant_a
):
    create_url = reverse("assets:cloud_asset_subscription_create")
    assert member_client.get(create_url).status_code == 200
    resp = member_client.post(create_url, _it_asset_management_cloud_post_data())
    assert resp.status_code == 302
    cl = CloudAssetSubscription.objects.get(tenant=tenant_a, name="PagerDuty Enterprise")
    assert cl.wasted_monthly_spend > 0

    detail_resp = client_a.get(reverse("assets:cloud_asset_subscription_detail", args=[cl.pk]))
    assert detail_resp.status_code == 200
    detail_html = detail_resp.content.decode()
    # I4 stat-icon orange + M8 resource_tags pills
    assert "stat-icon orange" in detail_html
    assert "stat-icon amber" not in detail_html
    assert "badge badge-slate" in detail_html
    assert "cost_center=CC-SRE" in detail_html
    _it_asset_management_assert_no_template_leaks(detail_html)

    # Edit
    edit_url = reverse("assets:cloud_asset_subscription_edit", args=[cl.pk])
    assert (
        client_a.post(
            edit_url,
            _it_asset_management_cloud_post_data(name="PagerDuty Global"),
        ).status_code
        == 302
    )
    cl.refresh_from_db()
    assert cl.name == "PagerDuty Global"

    del_url = reverse("assets:cloud_asset_subscription_delete", args=[cl.pk])
    assert member_client.post(del_url).status_code == 403
    cl.status = "cancelled"
    cl.save(update_fields=["status"])
    assert client_a.get(edit_url).status_code == 302
    assert client_a.post(del_url).status_code == 302
    assert CloudAssetSubscription.objects.filter(pk=cl.pk).exists()

    cl.status = "active"
    cl.save(update_fields=["status"])
    assert client_a.post(del_url).status_code == 302
    assert not CloudAssetSubscription.objects.filter(pk=cl.pk).exists()


def test_it_asset_management_cmdb_crud_and_locked_guards(
    client_a, member_client, tenant_a, it_hardware_a, cloud_subscription_a
):
    svc = _it_asset_management_make_service(tenant_a, "Payments API")
    create_url = reverse("assets:cmdb_relationship_create")
    get_resp = member_client.get(create_url)
    assert get_resp.status_code == 200
    _it_asset_management_assert_no_template_leaks(get_resp.content.decode())

    resp = member_client.post(
        create_url,
        {
            "source_ci_type": "service_component",
            "source_service": str(svc.pk),
            "relationship_type": "depends_on",
            "target_ci_type": "cloud_asset",
            "target_cloud": str(cloud_subscription_a.pk),
            "environment": "production",
            "criticality": "tier_1_mission_critical",
            "impact_severity": "hard_outage",
            "is_single_point_of_failure": "on",
            "blast_radius_notes": "Critical path",
        },
    )
    assert resp.status_code == 302
    rel = CmdbRelationship.objects.get(tenant=tenant_a, source_service=svc)
    assert rel.verified_on == timezone.now().date()

    detail_resp = client_a.get(reverse("assets:cmdb_relationship_detail", args=[rel.pk]))
    assert detail_resp.status_code == 200
    _it_asset_management_assert_no_template_leaks(detail_resp.content.decode())

    edit_url = reverse("assets:cmdb_relationship_edit", args=[rel.pk])
    assert (
        client_a.post(
            edit_url,
            {
                "source_ci_type": "service_component",
                "source_service": str(svc.pk),
                "relationship_type": "hosted_in",
                "target_ci_type": "it_hardware",
                "target_hardware": str(it_hardware_a.pk),
                "environment": "production",
                "criticality": "tier_2_business_important",
                "impact_severity": "degraded_performance",
                "blast_radius_notes": "Updated target",
            },
        ).status_code
        == 302
    )
    rel.refresh_from_db()
    assert rel.relationship_type == "hosted_in"
    assert rel.target_hardware_id == it_hardware_a.pk

    del_url = reverse("assets:cmdb_relationship_delete", args=[rel.pk])
    assert member_client.post(del_url).status_code == 403
    rel.status = "severed"
    rel.save(update_fields=["status"])
    assert client_a.get(edit_url).status_code == 302
    assert client_a.post(del_url).status_code == 302
    assert CmdbRelationship.objects.filter(pk=rel.pk).exists()

    rel.status = "active"
    rel.save(update_fields=["status"])
    assert client_a.post(del_url).status_code == 302
    assert not CmdbRelationship.objects.filter(pk=rel.pk).exists()


def test_it_asset_management_create_views_guard_missing_tenant_i3(db):
    superuser = User.objects.create_superuser(
        email="super-notenant@naverp.test",
        username="super_notenant_1118",
        password="TestPass123!",
    )
    assert superuser.tenant is None
    c = Client()
    c.force_login(superuser)

    cases = [
        ("assets:it_hardware_asset_create", "assets:it_hardware_asset_list", _it_asset_management_hardware_post_data()),
        ("assets:software_license_create", "assets:software_license_list", _it_asset_management_software_post_data()),
        ("assets:cloud_asset_subscription_create", "assets:cloud_asset_subscription_list", _it_asset_management_cloud_post_data()),
        ("assets:cmdb_relationship_create", "assets:cmdb_relationship_list", {"source_ci_type": "service_component"}),
    ]
    for create_name, list_name, payload in cases:
        resp = c.post(reverse(create_name), payload)
        assert resp.status_code == 302
        assert resp.url == reverse(list_name)
        assert "Workspace context is required" in " ".join(_it_asset_management_messages(resp))


# =====================================================================
# 4. Workflow Actions + AuditLog (M3) + I1/I2/C2/C3 Regressions
# =====================================================================


def test_it_asset_management_hardware_workflow_actions_and_i1_lock(
    client_a, member_client, tenant_a, admin_user
):
    hw = _it_asset_management_make_hardware(
        tenant_a,
        hostname="wf-laptop-01",
        status="procured",
        sanitization_required=True,
        sanitization_method="none",
        sanitization_status="pending_wipe",
    )

    transitions = [
        ("assets:it_hardware_asset_deploy", "deployed", "deploy"),
        ("assets:it_hardware_asset_move_to_stock", "staged_in_stock", "stock"),
        ("assets:it_hardware_asset_send_to_repair", "in_repair", "repair"),
        ("assets:it_hardware_asset_move_to_loaner", "loaner_pool", "loaner"),
        ("assets:it_hardware_asset_flag_for_refresh", "pending_refresh", "refresh"),
    ]
    for url_name, expected_status, verb in transitions:
        prev_status = hw.status
        resp = member_client.post(reverse(url_name, args=[hw.pk]))
        assert resp.status_code == 302
        hw.refresh_from_db()
        assert hw.status == expected_status
        log = _it_asset_management_latest_audit(tenant_a, hw, verb)
        assert log is not None
        assert len(log.action) <= 10
        assert log.changes == {"status": [prev_status, expected_status]}

    assert hw.last_seen_checkin is not None
    assert hw.assigned_date is not None

    # Retire blocked while pending_wipe
    retire_url = reverse("assets:it_hardware_asset_retire", args=[hw.pk])
    assert member_client.post(retire_url).status_code == 403
    blocked_retire = client_a.post(retire_url)
    assert blocked_retire.status_code == 302
    hw.refresh_from_db()
    assert hw.status == "pending_refresh"
    assert "sanitization must be verified" in " ".join(_it_asset_management_messages(blocked_retire))

    # Sanitize is admin-only
    sanitize_url = reverse("assets:it_hardware_asset_mark_sanitized", args=[hw.pk])
    assert member_client.post(sanitize_url).status_code == 403
    san_resp = client_a.post(sanitize_url)
    assert san_resp.status_code == 302
    hw.refresh_from_db()
    assert hw.sanitization_method == "nist_purge"
    assert hw.sanitization_status == "wiped_verified"
    assert hw.sanitization_verified_by == admin_user
    assert hw.sanitized_at is not None
    san_log = _it_asset_management_latest_audit(tenant_a, hw, "sanitize")
    assert san_log is not None
    assert san_log.changes["sanitization_status"] == ["pending_wipe", "wiped_verified"]
    assert san_log.changes["sanitization_method"] == ["none", "nist_purge"]

    # Retire succeeds now
    ret_resp = client_a.post(retire_url)
    assert ret_resp.status_code == 302
    hw.refresh_from_db()
    assert hw.status == "sanitized_retired"
    assert hw.retired_at is not None
    ret_log = _it_asset_management_latest_audit(tenant_a, hw, "retire")
    assert ret_log is not None
    assert ret_log.changes == {"status": ["pending_refresh", "sanitized_retired"]}

    # I1 regression: locked sanitized_retired cannot be re-sanitized
    orig_sanitized_at = hw.sanitized_at
    hw.sanitization_certificate_ref = "CERT-TAMPER"
    hw.save(update_fields=["sanitization_certificate_ref"])
    re_san = client_a.post(sanitize_url)
    assert re_san.status_code == 302
    hw.refresh_from_db()
    assert hw.sanitization_status == "wiped_verified"
    assert hw.sanitized_at == orig_sanitized_at


def test_it_asset_management_software_workflow_actions_and_c2_audit_hold(
    client_a, member_client, tenant_a
):
    today = timezone.localdate()
    lic = _it_asset_management_make_license(
        tenant_a,
        software_name="Tableau Creator",
        entitled_quantity=20,
        allocated_quantity=25,
        active_used_quantity=15,
        reclaimable_inactive_count=5,
        renewal_date=today + timedelta(days=30),
        status="draft",
    )

    # sync_compliance -> true_up_required
    r_sync = member_client.post(reverse("assets:software_license_sync_compliance", args=[lic.pk]))
    assert r_sync.status_code == 302
    lic.refresh_from_db()
    assert lic.status == "true_up_required"
    assert lic.last_reconciled_at is not None
    log_sync = _it_asset_management_latest_audit(tenant_a, lic, "sync_elp")
    assert log_sync.changes == {"status": ["draft", "true_up_required"]}

    # reclaim_inactive -> harvests 5 seats (25 -> 20)
    r_reclaim = member_client.post(reverse("assets:software_license_reclaim_inactive", args=[lic.pk]))
    assert r_reclaim.status_code == 302
    lic.refresh_from_db()
    assert lic.allocated_quantity == 20
    assert lic.reclaimable_inactive_count == 0
    assert lic.status == "active_compliant"
    log_reclaim = _it_asset_management_latest_audit(tenant_a, lic, "reclaim")
    assert log_reclaim.changes["allocated_quantity"] == [25, 20]
    assert log_reclaim.changes["reclaimable_inactive_count"] == [5, 0]

    # record_true_up (admin-only) after creating shortfall
    lic.allocated_quantity = 28
    lic.status = "true_up_required"
    lic.save(update_fields=["allocated_quantity", "status"])
    tu_url = reverse("assets:software_license_record_true_up", args=[lic.pk])
    assert member_client.post(tu_url).status_code == 403
    assert client_a.post(tu_url).status_code == 302
    lic.refresh_from_db()
    assert lic.entitled_quantity == 28
    assert lic.status == "active_compliant"
    log_tu = _it_asset_management_latest_audit(tenant_a, lic, "true_up")
    assert log_tu.changes["entitled_quantity"] == [20, 28]

    # renew_term -> +12 months
    prev_ren = lic.renewal_date
    r_ren = member_client.post(reverse("assets:software_license_renew_term", args=[lic.pk]))
    assert r_ren.status_code == 302
    lic.refresh_from_db()
    assert lic.renewal_date > prev_ren
    log_ren = _it_asset_management_latest_audit(tenant_a, lic, "renew")
    assert log_ren.changes["renewal_date"] == [prev_ren.isoformat(), lic.renewal_date.isoformat()]

    # place_audit_hold (admin-only) + C2 regression
    hold_url = reverse("assets:software_license_place_audit_hold", args=[lic.pk])
    assert member_client.post(hold_url).status_code == 403
    assert client_a.post(hold_url).status_code == 302
    lic.refresh_from_db()
    assert lic.status == "audit_hold"
    log_hold = _it_asset_management_latest_audit(tenant_a, lic, "hold")
    assert log_hold.changes == {"status": ["active_compliant", "audit_hold"]}

    # C2: Non-admin blocked (403) from edit, sync_compliance, reclaim_inactive, renew_term while on audit_hold
    assert member_client.get(reverse("assets:software_license_edit", args=[lic.pk])).status_code == 403
    assert member_client.post(reverse("assets:software_license_sync_compliance", args=[lic.pk])).status_code == 403
    assert member_client.post(reverse("assets:software_license_reclaim_inactive", args=[lic.pk])).status_code == 403
    assert member_client.post(reverse("assets:software_license_renew_term", args=[lic.pk])).status_code == 403
    # Detail UI hides hold-clearing buttons from non-admins
    member_detail_html = member_client.get(reverse("assets:software_license_detail", args=[lic.pk])).content.decode()
    assert reverse("assets:software_license_sync_compliance", args=[lic.pk]) not in member_detail_html
    assert reverse("assets:software_license_edit", args=[lic.pk]) not in member_detail_html

    # Admin can retire
    ret_url = reverse("assets:software_license_retire", args=[lic.pk])
    assert member_client.post(ret_url).status_code == 403
    assert client_a.post(ret_url).status_code == 302
    lic.refresh_from_db()
    assert lic.status == "retired"
    assert lic.retired_at is not None


def test_it_asset_management_cloud_workflow_actions_and_c3_suspended(
    client_a, member_client, tenant_a
):
    today = timezone.localdate()
    cl = _it_asset_management_make_cloud(
        tenant_a,
        name="Miro Enterprise",
        sso_status="shadow_it_unapproved",
        approval_status="under_review",
        status="active",
        renewal_date=today + timedelta(days=45),
    )

    # flag_shadow
    r_sh = member_client.post(reverse("assets:cloud_asset_subscription_flag_shadow", args=[cl.pk]))
    assert r_sh.status_code == 302
    cl.refresh_from_db()
    assert cl.approval_status == "shadow_it_flagged"
    assert cl.status == "shadow_flagged"
    log_sh = _it_asset_management_latest_audit(tenant_a, cl, "shadow")
    assert log_sh.changes == {
        "approval_status": ["under_review", "shadow_it_flagged"],
        "status": ["active", "shadow_flagged"],
    }

    # sanction
    r_san = member_client.post(reverse("assets:cloud_asset_subscription_sanction", args=[cl.pk]))
    assert r_san.status_code == 302
    cl.refresh_from_db()
    assert cl.approval_status == "sanctioned"
    assert cl.sso_status == "sso_optional"
    assert cl.status == "active"
    log_san = _it_asset_management_latest_audit(tenant_a, cl, "sanction")
    assert log_san.changes["approval_status"] == ["shadow_it_flagged", "sanctioned"]

    # sync_finops
    r_fin = member_client.post(reverse("assets:cloud_asset_subscription_sync_finops", args=[cl.pk]))
    assert r_fin.status_code == 302
    cl.refresh_from_db()
    assert cl.last_finops_sync_at is not None
    assert _it_asset_management_latest_audit(tenant_a, cl, "finops") is not None

    # renew
    prev_ren = cl.renewal_date
    r_ren = member_client.post(reverse("assets:cloud_asset_subscription_renew", args=[cl.pk]))
    assert r_ren.status_code == 302
    cl.refresh_from_db()
    assert cl.renewal_date > prev_ren
    log_ren = _it_asset_management_latest_audit(tenant_a, cl, "renew")
    assert log_ren.changes["renewal_date"] == [prev_ren.isoformat(), cl.renewal_date.isoformat()]

    # suspend (admin-only) + C3 regression
    susp_url = reverse("assets:cloud_asset_subscription_suspend", args=[cl.pk])
    assert member_client.post(susp_url).status_code == 403
    assert client_a.post(susp_url).status_code == 302
    cl.refresh_from_db()
    assert cl.status == "suspended"

    # C3: Non-admin blocked (403) from edit, sanction, flag_shadow, sync_finops, renew while suspended
    assert member_client.get(reverse("assets:cloud_asset_subscription_edit", args=[cl.pk])).status_code == 403
    assert member_client.post(reverse("assets:cloud_asset_subscription_sanction", args=[cl.pk])).status_code == 403
    assert member_client.post(reverse("assets:cloud_asset_subscription_flag_shadow", args=[cl.pk])).status_code == 403
    assert member_client.post(reverse("assets:cloud_asset_subscription_sync_finops", args=[cl.pk])).status_code == 403
    assert member_client.post(reverse("assets:cloud_asset_subscription_renew", args=[cl.pk])).status_code == 403

    # C3: Admin sanction / renew while suspended preserves suspended status
    assert client_a.post(reverse("assets:cloud_asset_subscription_sanction", args=[cl.pk])).status_code == 302
    cl.refresh_from_db()
    assert cl.status == "suspended"
    assert client_a.post(reverse("assets:cloud_asset_subscription_renew", args=[cl.pk])).status_code == 302
    cl.refresh_from_db()
    assert cl.status == "suspended"

    # decommission (admin-only)
    dec_url = reverse("assets:cloud_asset_subscription_decommission", args=[cl.pk])
    assert member_client.post(dec_url).status_code == 403
    assert client_a.post(dec_url).status_code == 302
    cl.refresh_from_db()
    assert cl.approval_status == "decommissioned"
    assert cl.status == "cancelled"
    assert cl.decommissioned_at is not None
    log_dec = _it_asset_management_latest_audit(tenant_a, cl, "decomm")
    assert log_dec.changes == {
        "approval_status": ["sanctioned", "decommissioned"],
        "status": ["suspended", "cancelled"],
    }


def test_it_asset_management_cmdb_workflow_actions_and_i2_duplicate_verify(
    client_a, member_client, tenant_a, it_hardware_a, software_license_a
):
    # Active edge already exists
    active_edge = _it_asset_management_make_cmdb(
        tenant_a,
        source_ci_type="software_license",
        source_software=software_license_a,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
        status="active",
    )
    # Planned duplicate edge on same source/rel/target
    planned_dup = _it_asset_management_make_cmdb(
        tenant_a,
        source_ci_type="software_license",
        source_software=software_license_a,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
        status="planned",
    )

    # I2 regression: verifying planned duplicate edge fails full_clean() and flashes error
    dup_resp = member_client.post(reverse("assets:cmdb_relationship_verify", args=[planned_dup.pk]))
    assert dup_resp.status_code == 302
    planned_dup.refresh_from_db()
    assert planned_dup.status == "planned"
    assert "already exists" in " ".join(_it_asset_management_messages(dup_resp))

    # Deprecate active edge -> then verify planned_dup succeeds
    r_dep = member_client.post(reverse("assets:cmdb_relationship_deprecate", args=[active_edge.pk]))
    assert r_dep.status_code == 302
    active_edge.refresh_from_db()
    assert active_edge.status == "deprecated"
    log_dep = _it_asset_management_latest_audit(tenant_a, active_edge, "deprec")
    assert log_dep.changes == {"status": ["active", "deprecated"]}

    r_ver = member_client.post(reverse("assets:cmdb_relationship_verify", args=[planned_dup.pk]))
    assert r_ver.status_code == 302
    planned_dup.refresh_from_db()
    assert planned_dup.status == "active"
    assert planned_dup.verified_on == timezone.now().date()
    log_ver = _it_asset_management_latest_audit(tenant_a, planned_dup, "verify")
    assert log_ver.changes["status"] == ["planned", "active"]

    # Sever (admin-only)
    sev_url = reverse("assets:cmdb_relationship_sever", args=[planned_dup.pk])
    assert member_client.post(sev_url).status_code == 403
    assert client_a.post(sev_url).status_code == 302
    planned_dup.refresh_from_db()
    assert planned_dup.status == "severed"
    assert planned_dup.severed_at is not None
    log_sev = _it_asset_management_latest_audit(tenant_a, planned_dup, "sever")
    assert log_sev.changes == {"status": ["active", "severed"]}


# =====================================================================
# 5. Workbenches: ItRefreshBoards & CmdbImpactAnalyses
# =====================================================================


def test_it_asset_management_refresh_board_kpis_filters_and_200_cap(
    client_a, tenant_a, org_unit_a
):
    today = timezone.localdate()
    # Overdue HW (assigned to org_unit_a)
    _it_asset_management_make_hardware(
        tenant_a,
        hostname="hw-overdue",
        org_unit=org_unit_a,
        vendor_eol_date=today - timedelta(days=10),
        refresh_due_date=today - timedelta(days=5),
        estimated_refresh_cost=Decimal("1000.00"),
        sanitization_required=True,
        sanitization_status="pending_wipe",
    )
    # Due within 90d HW (unassigned org_unit)
    _it_asset_management_make_hardware(
        tenant_a,
        hostname="hw-due-45d",
        org_unit=None,
        refresh_due_date=today + timedelta(days=45),
        vendor_eol_date=today + timedelta(days=200),
        estimated_refresh_cost=Decimal("500.00"),
        sanitization_required=False,
        sanitization_status="not_required",
    )
    # Healthy HW (far future)
    _it_asset_management_make_hardware(
        tenant_a,
        hostname="hw-healthy",
        refresh_due_date=today + timedelta(days=600),
        vendor_eol_date=today + timedelta(days=700),
        estimated_refresh_cost=Decimal("300.00"),
        sanitization_required=False,
        sanitization_status="not_required",
    )
    # Locked HW excluded from KPIs
    _it_asset_management_make_hardware(
        tenant_a,
        hostname="hw-retired",
        status="sanitized_retired",
        vendor_eol_date=today - timedelta(days=30),
        sanitization_required=True,
        sanitization_status="pending_wipe",
    )
    # Expiring SW & Cloud inside 90d, plus SW at 45d to verify horizon=30 filtering
    _it_asset_management_make_license(
        tenant_a, software_name="SW Expiring 20d", renewal_date=today + timedelta(days=20)
    )
    _it_asset_management_make_license(
        tenant_a, software_name="SW Expiring 45d", renewal_date=today + timedelta(days=45)
    )
    _it_asset_management_make_cloud(
        tenant_a, name="Cloud Expiring", renewal_date=today + timedelta(days=25)
    )

    url = reverse("assets:it_refresh_board")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["overdue_hw_count"] == 1
    assert resp.context["due_90d_hw_count"] == 1
    assert resp.context["pending_wipe_count"] == 1
    assert resp.context["expiring_sw_cloud_count"] == 3
    assert resp.context["total_refresh_capex"] == Decimal("1500.00")
    ou_names = {row["org_unit_name"] for row in resp.context["org_unit_summary"]}
    assert org_unit_a.name in ou_names
    assert "Unassigned Org Unit" in ou_names

    # Filter by horizon=30 excludes 45d software renewal while priority=overdue_critical isolates hw-overdue
    r_h30 = client_a.get(url, {"horizon": "30"})
    assert r_h30.context["expiring_sw_cloud_count"] == 2
    r_overdue = client_a.get(url, {"priority": "overdue_critical"})
    assert [h.hostname for h in r_overdue.context["hardware_rows"]] == ["hw-overdue"]
    # Filter by priority=healthy returns hw-healthy
    r_healthy = client_a.get(url, {"priority": "healthy"})
    assert [h.hostname for h in r_healthy.context["hardware_rows"]] == ["hw-healthy"]
    # Invalid horizon/priority falls back gracefully
    r_bad = client_a.get(url, {"horizon": "999", "priority": "bad", "org_unit": "xyz"})
    assert r_bad.status_code == 200
    assert r_bad.context["horizon_days"] == 90

    # 200-row slice cap while SQL KPI counts all overdue rows
    bulk_hw = [
        ItHardwareAsset(
            tenant=tenant_a,
            hostname=f"bulk-overdue-{i:03d}",
            number=f"ITHW-BULK-{i:04d}",
            vendor_eol_date=today - timedelta(days=2),
            refresh_due_date=today - timedelta(days=2),
            estimated_refresh_cost=Decimal("10.00"),
            status="deployed",
            sanitization_required=False,
            sanitization_status="not_required",
        )
        for i in range(205)
    ]
    ItHardwareAsset.objects.bulk_create(bulk_hw)
    r_cap = client_a.get(url)
    assert r_cap.status_code == 200
    assert len(r_cap.context["hardware_rows"]) == 200
    assert r_cap.context["overdue_hw_count"] == 206


def test_it_asset_management_cmdb_impact_analysis_bfs_cycles_and_spof(
    client_a, tenant_a
):
    url = reverse("assets:cmdb_impact_analysis")

    # Empty view (no CIs / no edges)
    r_empty = client_a.get(url)
    assert r_empty.status_code == 200
    assert r_empty.context["ci_options"] == []
    assert r_empty.context["upstream_nodes"] == []
    assert r_empty.context["downstream_nodes"] == []

    # Build a 10-hop chain (svc_0 -> svc_1 -> ... -> svc_10) plus a cycle (svc_2 -> svc_0)
    svcs = [_it_asset_management_make_service(tenant_a, f"Chain-Svc-{i:02d}") for i in range(11)]
    edges = []
    for i in range(10):
        edges.append(
            _it_asset_management_make_cmdb(
                tenant_a,
                source_ci_type="service_component",
                source_service=svcs[i],
                relationship_type="depends_on",
                target_ci_type="service_component",
                target_service=svcs[i + 1],
                is_single_point_of_failure=(i == 0),
                environment="production",
            )
        )
    # Cycle edge back to svc[0]
    _it_asset_management_make_cmdb(
        tenant_a,
        source_ci_type="service_component",
        source_service=svcs[2],
        relationship_type="connects_to",
        target_ci_type="service_component",
        target_service=svcs[0],
        environment="production",
    )

    # Focus on svcs[0]: upstream hops 1..8 (capped at hop_depth <= 8)
    r_root = client_a.get(url, {"ci": f"service_component:{svcs[0].pk}"})
    assert r_root.status_code == 200
    up_hops = [n["hop"] for n in r_root.context["upstream_nodes"]]
    assert max(up_hops) == 8
    assert len(up_hops) == 8

    # Focus on svcs[1]: downstream blast radius includes svcs[0] and svcs[2] (via cycle)
    r_mid = client_a.get(url, {"ci": f"service_component:{svcs[1].pk}"})
    assert r_mid.status_code == 200
    downstream_pks = {n["ci_pk"] for n in r_mid.context["downstream_nodes"]}
    assert svcs[0].pk in downstream_pks
    assert len(r_mid.context["spof_edges"]) == 1
    spof = r_mid.context["spof_edges"][0]
    assert "Chain-Svc-00" in spof["source_label"]
    assert "Chain-Svc-01" in spof["target_label"]

    # Environment filter excludes production edges when staging selected
    r_staging = client_a.get(
        url,
        {"ci": f"service_component:{svcs[0].pk}", "environment": "staging"},
    )
    assert r_staging.status_code == 200
    assert r_staging.context["total_active_edges"] == 0
    assert r_staging.context["upstream_nodes"] == []

    # Invalid / unknown CI param handled cleanly
    for bad_ci in ("invalid-token", "it_hardware:999999", "service_component:abc"):
        r_bad = client_a.get(url, {"ci": bad_ci})
        assert r_bad.status_code == 200
        assert r_bad.context["selected_ci_token"] == ""
        assert r_bad.context["upstream_nodes"] == []


# =====================================================================
# 6. CSV Exports (All 6 Endpoints + Formula Injection Safety)
# =====================================================================


def test_it_asset_management_csv_exports_headers_nosniff_and_formula_safety(
    client_a, tenant_a
):
    today = timezone.localdate()
    hw_inj = _it_asset_management_make_hardware(
        tenant_a,
        hostname="=CMD|'/C calc'!A0",
        serial_number="+12345",
        refresh_due_date=today + timedelta(days=10),
    )
    _it_asset_management_make_hardware(
        tenant_a,
        hostname="clean-server",
        refresh_due_date=today + timedelta(days=500),
    )
    sw_inj = _it_asset_management_make_license(
        tenant_a,
        software_name="-1+1@SUM(A1:A2)",
        publisher_name="@EvilPub",
        renewal_date=today + timedelta(days=15),
    )
    cl_inj = _it_asset_management_make_cloud(
        tenant_a,
        name="@SUM(1,2)",
        external_account_id="=1+1",
        renewal_date=today + timedelta(days=15),
    )
    svc_inj = _it_asset_management_make_service(tenant_a, "=CMD|'/C calc'!A0")
    _it_asset_management_make_cmdb(
        tenant_a,
        source_ci_type="service_component",
        source_service=svc_inj,
        target_ci_type="it_hardware",
        target_hardware=hw_inj,
    )
    _it_asset_management_make_cmdb(
        tenant_a,
        source_ci_type="software_license",
        source_software=sw_inj,
        target_ci_type="cloud_asset",
        target_cloud=cl_inj,
    )

    export_cases = [
        ("assets:it_hardware_asset_export_csv", {"q": "CMD"}, "'=CMD|'/C calc'!A0", "clean-server"),
        ("assets:software_license_export_csv", {"q": "SUM"}, "'-1+1@SUM(A1:A2)", None),
        ("assets:cloud_asset_subscription_export_csv", {"q": "SUM"}, "'@SUM(1,2)", None),
        ("assets:cmdb_relationship_export_csv", {"q": "CMD"}, "'=CMD|'/C calc'!A0", None),
        ("assets:it_refresh_board_export_csv", {"horizon": "30"}, "'=CMD|'/C calc'!A0", "clean-server"),
        ("assets:cmdb_impact_analysis_export_csv", {"ci": f"service_component:{svc_inj.pk}"}, "=CMD|'/C calc'!A0", None),
    ]
    for url_name, params, expected_cell, excluded_text in export_cases:
        resp = client_a.get(reverse(url_name), params)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        assert resp["X-Content-Type-Options"] == "nosniff"
        assert "attachment; filename=" in resp["Content-Disposition"]
        body = resp.content.decode("utf-8")
        rows = list(csv.reader(io.StringIO(body)))
        assert len(rows) >= 2
        flat = [cell for row in rows for cell in row]
        assert any(expected_cell in cell for cell in flat)
        if excluded_text:
            assert excluded_text not in body


# =====================================================================
# 7. Query Budgets (O(1) Constant Queries, I8, I9, I10, M11)
# =====================================================================


def test_it_asset_management_list_views_query_budgets_constant(
    client_a, tenant_a, org_unit_a, vendor_party_a, currency_usd
):
    # Warm session/auth
    client_a.get(reverse("assets:it_hardware_asset_list"))

    def _capture(url_name):
        with CaptureQueriesContext(connection) as ctx:
            resp = client_a.get(reverse(url_name))
            assert resp.status_code == 200
        return len(ctx)

    # Seed N=1 of each
    hw1 = _it_asset_management_make_hardware(
        tenant_a, hostname="qb-hw-0", org_unit=org_unit_a, custodian_party=vendor_party_a
    )
    sw1 = _it_asset_management_make_license(
        tenant_a, software_name="qb-sw-0", currency=currency_usd
    )
    cl1 = _it_asset_management_make_cloud(
        tenant_a, name="qb-cl-0", currency=currency_usd
    )
    _it_asset_management_make_cmdb(
        tenant_a,
        source_ci_type="software_license",
        source_software=sw1,
        target_ci_type="it_hardware",
        target_hardware=hw1,
    )

    small_counts = {
        name: _capture(name)
        for name in (
            "assets:it_hardware_asset_list",
            "assets:software_license_list",
            "assets:cloud_asset_subscription_list",
            "assets:cmdb_relationship_list",
        )
    }

    # Seed 12 more rows each
    for i in range(1, 13):
        hw = _it_asset_management_make_hardware(
            tenant_a, hostname=f"qb-hw-{i:02d}", org_unit=org_unit_a, custodian_party=vendor_party_a
        )
        sw = _it_asset_management_make_license(
            tenant_a, software_name=f"qb-sw-{i:02d}", currency=currency_usd
        )
        _it_asset_management_make_cloud(
            tenant_a, name=f"qb-cl-{i:02d}", currency=currency_usd
        )
        _it_asset_management_make_cmdb(
            tenant_a,
            source_ci_type="software_license",
            source_software=sw,
            target_ci_type="it_hardware",
            target_hardware=hw,
        )

    for name, count_small in small_counts.items():
        count_many = _capture(name)
        assert count_many <= 12
        assert count_many == count_small


def test_it_asset_management_detail_views_query_budgets_and_m11_slice(
    client_a,
    tenant_a,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
    scrap_salvage_a,
    django_assert_max_num_queries,
):
    # Link I8 scrap_salvage to hardware
    it_hardware_a.scrap_salvage = scrap_salvage_a
    it_hardware_a.save(update_fields=["scrap_salvage"])

    # Create 55 outbound edges from cloud_subscription_a to test M11 [:50] slice & zero N+1
    for i in range(55):
        svc = _it_asset_management_make_service(tenant_a, f"HubTarget-{i:02d}")
        _it_asset_management_make_cmdb(
            tenant_a,
            source_ci_type="cloud_asset",
            source_cloud=cloud_subscription_a,
            target_ci_type="service_component",
            target_service=svc,
        )

    # Warm session
    client_a.get(reverse("assets:it_hardware_asset_detail", args=[it_hardware_a.pk]))

    for url_name, pk in (
        ("assets:it_hardware_asset_detail", it_hardware_a.pk),
        ("assets:software_license_detail", software_license_a.pk),
        ("assets:cloud_asset_subscription_detail", cloud_subscription_a.pk),
        ("assets:cmdb_relationship_detail", cmdb_relationship_a.pk),
    ):
        with django_assert_max_num_queries(12):
            resp = client_a.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 200

    cl_detail = client_a.get(
        reverse("assets:cloud_asset_subscription_detail", args=[cloud_subscription_a.pk])
    )
    assert len(list(cl_detail.context["outbound_edges"])) == 50


def test_it_asset_management_workbenches_query_budgets_i9_i10(
    client_a, tenant_a, org_unit_a, currency_usd, django_assert_max_num_queries
):
    today = timezone.localdate()

    def _seed_batch(start_idx, count):
        hws = []
        for i in range(start_idx, start_idx + count):
            hw = _it_asset_management_make_hardware(
                tenant_a,
                hostname=f"wb-hw-{i:02d}",
                org_unit=org_unit_a,
                currency=currency_usd,
                refresh_due_date=today + timedelta(days=15),
                sanitization_required=True,
                sanitization_status="pending_wipe",
            )
            sw = _it_asset_management_make_license(
                tenant_a,
                software_name=f"wb-sw-{i:02d}",
                org_unit=org_unit_a,
                renewal_date=today + timedelta(days=20),
            )
            cl = _it_asset_management_make_cloud(
                tenant_a,
                name=f"wb-cl-{i:02d}",
                org_unit=org_unit_a,
                renewal_date=today + timedelta(days=20),
            )
            _it_asset_management_make_cmdb(
                tenant_a,
                source_ci_type="software_license",
                source_software=sw,
                target_ci_type="it_hardware",
                target_hardware=hw,
                is_single_point_of_failure=True,
            )
            _it_asset_management_make_cmdb(
                tenant_a,
                source_ci_type="cloud_asset",
                source_cloud=cl,
                target_ci_type="it_hardware",
                target_hardware=hw,
            )
            hws.append(hw)
        return hws

    first_hw = _seed_batch(0, 1)[0]
    client_a.get(reverse("assets:it_refresh_board"))

    with CaptureQueriesContext(connection) as rb_small:
        with django_assert_max_num_queries(18):
            assert client_a.get(reverse("assets:it_refresh_board")).status_code == 200

    with CaptureQueriesContext(connection) as ia_small:
        with django_assert_max_num_queries(14):
            assert (
                client_a.get(
                    reverse("assets:cmdb_impact_analysis"),
                    {"ci": f"it_hardware:{first_hw.pk}"},
                ).status_code
                == 200
            )

    _seed_batch(1, 15)

    with CaptureQueriesContext(connection) as rb_many:
        with django_assert_max_num_queries(18):
            assert client_a.get(reverse("assets:it_refresh_board")).status_code == 200

    with CaptureQueriesContext(connection) as ia_many:
        with django_assert_max_num_queries(14):
            assert (
                client_a.get(
                    reverse("assets:cmdb_impact_analysis"),
                    {"ci": f"it_hardware:{first_hw.pk}"},
                ).status_code
                == 200
            )

    assert len(rb_many) == len(rb_small)
    assert len(ia_many) == len(ia_small)
