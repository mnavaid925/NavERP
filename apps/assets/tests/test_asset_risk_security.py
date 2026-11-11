"""
Security & Tenant-Isolation tests for Sub-module 11.12: Asset Risk Management.
Covers:
  - Unauthenticated access redirects across all 27 endpoints
  - Cross-tenant IDOR protection (detail, edit, delete, action POSTs -> 404; list isolation)
  - Non-admin RBAC enforcement (@tenant_admin_required -> 403 for member_client)
  - POST-only HTTP method enforcement (@require_POST -> 405 on GET)
  - Cross-tenant Foreign Key injection prevention in POST forms
  - Mass-assignment / forged system & disabled field resistance
"""
from datetime import date, timedelta
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetBusinessContinuityPlan,
    AssetCyberSecurityProfile,
    AssetRiskMitigationAction,
    AssetRiskRegister,
)

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (_asset_risk_*)
# =====================================================================

def _asset_risk_sec_read_endpoints(risk, bcp, cyber, action):
    return [
        reverse("assets:asset_risk_register_list"),
        reverse("assets:asset_risk_register_create"),
        reverse("assets:asset_risk_register_detail", kwargs={"pk": risk.pk}),
        reverse("assets:asset_risk_register_edit", kwargs={"pk": risk.pk}),
        reverse("assets:asset_business_continuity_plan_list"),
        reverse("assets:asset_business_continuity_plan_create"),
        reverse("assets:asset_business_continuity_plan_detail", kwargs={"pk": bcp.pk}),
        reverse("assets:asset_business_continuity_plan_edit", kwargs={"pk": bcp.pk}),
        reverse("assets:asset_cybersecurity_profile_list"),
        reverse("assets:asset_cybersecurity_profile_create"),
        reverse("assets:asset_cybersecurity_profile_detail", kwargs={"pk": cyber.pk}),
        reverse("assets:asset_cybersecurity_profile_edit", kwargs={"pk": cyber.pk}),
        reverse("assets:asset_risk_mitigation_action_list"),
        reverse("assets:asset_risk_mitigation_action_create"),
        reverse("assets:asset_risk_mitigation_action_detail", kwargs={"pk": action.pk}),
        reverse("assets:asset_risk_mitigation_action_edit", kwargs={"pk": action.pk}),
    ]


def _asset_risk_sec_post_only_endpoints(risk, bcp, cyber, action):
    return [
        reverse("assets:asset_risk_register_delete", kwargs={"pk": risk.pk}),
        reverse("assets:asset_risk_register_assess", kwargs={"pk": risk.pk}),
        reverse("assets:asset_risk_register_close", kwargs={"pk": risk.pk}),
        reverse("assets:asset_business_continuity_plan_delete", kwargs={"pk": bcp.pk}),
        reverse("assets:asset_business_continuity_plan_activate", kwargs={"pk": bcp.pk}),
        reverse("assets:asset_business_continuity_plan_drill", kwargs={"pk": bcp.pk}),
        reverse("assets:asset_cybersecurity_profile_delete", kwargs={"pk": cyber.pk}),
        reverse("assets:asset_cybersecurity_profile_scan", kwargs={"pk": cyber.pk}),
        reverse("assets:asset_risk_mitigation_action_delete", kwargs={"pk": action.pk}),
        reverse("assets:asset_risk_mitigation_action_complete", kwargs={"pk": action.pk}),
        reverse("assets:asset_risk_mitigation_action_verify", kwargs={"pk": action.pk}),
    ]


# =====================================================================
# 1. Unauthenticated Redirects Across All 27 Endpoints
# =====================================================================

class TestAssetRiskUnauthenticated:
    def test_asset_risk_anonymous_get_endpoints_redirect_to_login(
        self,
        client,
        asset_risk_register_a,
        asset_continuity_plan_a,
        asset_cyber_profile_a,
        asset_mitigation_action_a,
    ):
        for url in _asset_risk_sec_read_endpoints(
            asset_risk_register_a,
            asset_continuity_plan_a,
            asset_cyber_profile_a,
            asset_mitigation_action_a,
        ):
            resp = client.get(url)
            assert resp.status_code == 302, f"Expected 302 for anonymous GET {url}, got {resp.status_code}"
            assert "login" in resp["Location"].lower()

    def test_asset_risk_anonymous_post_endpoints_redirect_to_login(
        self,
        client,
        asset_risk_register_a,
        asset_continuity_plan_a,
        asset_cyber_profile_a,
        asset_mitigation_action_a,
    ):
        for url in _asset_risk_sec_post_only_endpoints(
            asset_risk_register_a,
            asset_continuity_plan_a,
            asset_cyber_profile_a,
            asset_mitigation_action_a,
        ):
            resp = client.post(url)
            assert resp.status_code == 302, f"Expected 302 for anonymous POST {url}, got {resp.status_code}"
            assert "login" in resp["Location"].lower()

        assert AssetRiskRegister.objects.filter(pk=asset_risk_register_a.pk).exists()
        assert AssetBusinessContinuityPlan.objects.filter(pk=asset_continuity_plan_a.pk).exists()
        assert AssetCyberSecurityProfile.objects.filter(pk=asset_cyber_profile_a.pk).exists()
        assert AssetRiskMitigationAction.objects.filter(pk=asset_mitigation_action_a.pk).exists()


# =====================================================================
# 2. Cross-Tenant IDOR & List Isolation
# =====================================================================

class TestAssetRiskTenantIsolation:
    def test_asset_risk_list_views_never_leak_foreign_tenant_rows(
        self,
        client_a,
        client_b,
        asset_risk_register_a,
        asset_risk_register_b,
        asset_continuity_plan_a,
        asset_continuity_plan_b,
        asset_cyber_profile_a,
        asset_cyber_profile_b,
        asset_mitigation_action_a,
        asset_mitigation_action_b,
    ):
        checks = [
            ("assets:asset_risk_register_list", "risks", asset_risk_register_a, asset_risk_register_b),
            ("assets:asset_business_continuity_plan_list", "plans", asset_continuity_plan_a, asset_continuity_plan_b),
            ("assets:asset_cybersecurity_profile_list", "profiles", asset_cyber_profile_a, asset_cyber_profile_b),
            ("assets:asset_risk_mitigation_action_list", "actions", asset_mitigation_action_a, asset_mitigation_action_b),
        ]
        for url_name, ctx_key, obj_a, obj_b in checks:
            url = reverse(url_name)
            label_a = getattr(obj_a, "title", None) or obj_a.asset.name
            label_b = getattr(obj_b, "title", None) or obj_b.asset.name

            resp_a = client_a.get(url)
            assert resp_a.status_code == 200
            assert list(resp_a.context[ctx_key]) == [obj_a]
            assert label_a in resp_a.content.decode()
            assert label_b not in resp_a.content.decode()

            resp_b = client_b.get(url)
            assert resp_b.status_code == 200
            assert list(resp_b.context[ctx_key]) == [obj_b]
            assert label_b in resp_b.content.decode()
            assert label_a not in resp_b.content.decode()

    def test_asset_risk_cross_tenant_idor_returns_404_across_all_objects(
        self,
        client_a,
        asset_risk_register_b,
        asset_continuity_plan_b,
        asset_cyber_profile_b,
        asset_mitigation_action_b,
    ):
        get_404_urls = [
            reverse("assets:asset_risk_register_detail", kwargs={"pk": asset_risk_register_b.pk}),
            reverse("assets:asset_risk_register_edit", kwargs={"pk": asset_risk_register_b.pk}),
            reverse("assets:asset_business_continuity_plan_detail", kwargs={"pk": asset_continuity_plan_b.pk}),
            reverse("assets:asset_business_continuity_plan_edit", kwargs={"pk": asset_continuity_plan_b.pk}),
            reverse("assets:asset_cybersecurity_profile_detail", kwargs={"pk": asset_cyber_profile_b.pk}),
            reverse("assets:asset_cybersecurity_profile_edit", kwargs={"pk": asset_cyber_profile_b.pk}),
            reverse("assets:asset_risk_mitigation_action_detail", kwargs={"pk": asset_mitigation_action_b.pk}),
            reverse("assets:asset_risk_mitigation_action_edit", kwargs={"pk": asset_mitigation_action_b.pk}),
        ]
        for url in get_404_urls:
            assert client_a.get(url).status_code == 404, f"Expected 404 for cross-tenant GET {url}"

        post_404_urls = _asset_risk_sec_post_only_endpoints(
            asset_risk_register_b,
            asset_continuity_plan_b,
            asset_cyber_profile_b,
            asset_mitigation_action_b,
        ) + [
            reverse("assets:asset_risk_register_edit", kwargs={"pk": asset_risk_register_b.pk}),
            reverse("assets:asset_business_continuity_plan_edit", kwargs={"pk": asset_continuity_plan_b.pk}),
            reverse("assets:asset_cybersecurity_profile_edit", kwargs={"pk": asset_cyber_profile_b.pk}),
            reverse("assets:asset_risk_mitigation_action_edit", kwargs={"pk": asset_mitigation_action_b.pk}),
        ]
        for url in post_404_urls:
            assert client_a.post(url, {}).status_code == 404, f"Expected 404 for cross-tenant POST {url}"

        # Tenant B records must remain completely intact in database
        assert AssetRiskRegister.objects.filter(pk=asset_risk_register_b.pk).exists()
        assert AssetBusinessContinuityPlan.objects.filter(pk=asset_continuity_plan_b.pk).exists()
        assert AssetCyberSecurityProfile.objects.filter(pk=asset_cyber_profile_b.pk).exists()
        assert AssetRiskMitigationAction.objects.filter(pk=asset_mitigation_action_b.pk).exists()


# =====================================================================
# 3. Non-Admin RBAC & HTTP Method Enforcement
# =====================================================================

class TestAssetRiskRBACAndMethods:
    def test_asset_risk_member_denied_admin_mutations_and_allowed_reads(
        self,
        member_client,
        asset_risk_register_a,
        asset_continuity_plan_a,
        asset_cyber_profile_a,
        asset_mitigation_action_a,
    ):
        # Members can view lists & details
        read_urls = [
            reverse("assets:asset_risk_register_list"),
            reverse("assets:asset_risk_register_detail", kwargs={"pk": asset_risk_register_a.pk}),
            reverse("assets:asset_business_continuity_plan_list"),
            reverse("assets:asset_business_continuity_plan_detail", kwargs={"pk": asset_continuity_plan_a.pk}),
            reverse("assets:asset_cybersecurity_profile_list"),
            reverse("assets:asset_cybersecurity_profile_detail", kwargs={"pk": asset_cyber_profile_a.pk}),
            reverse("assets:asset_risk_mitigation_action_list"),
            reverse("assets:asset_risk_mitigation_action_detail", kwargs={"pk": asset_mitigation_action_a.pk}),
        ]
        for url in read_urls:
            assert member_client.get(url).status_code == 200

        # Members denied admin-only create & edit GET/POST (403)
        admin_form_urls = [
            reverse("assets:asset_risk_register_create"),
            reverse("assets:asset_risk_register_edit", kwargs={"pk": asset_risk_register_a.pk}),
            reverse("assets:asset_business_continuity_plan_create"),
            reverse("assets:asset_business_continuity_plan_edit", kwargs={"pk": asset_continuity_plan_a.pk}),
            reverse("assets:asset_cybersecurity_profile_create"),
            reverse("assets:asset_cybersecurity_profile_edit", kwargs={"pk": asset_cyber_profile_a.pk}),
            reverse("assets:asset_risk_mitigation_action_create"),
            reverse("assets:asset_risk_mitigation_action_edit", kwargs={"pk": asset_mitigation_action_a.pk}),
        ]
        for url in admin_form_urls:
            assert member_client.get(url).status_code == 403
            assert member_client.post(url, {}).status_code == 403

        # Members denied admin-only delete & close/activate/verify POST actions (403)
        admin_post_urls = [
            reverse("assets:asset_risk_register_delete", kwargs={"pk": asset_risk_register_a.pk}),
            reverse("assets:asset_risk_register_close", kwargs={"pk": asset_risk_register_a.pk}),
            reverse("assets:asset_business_continuity_plan_delete", kwargs={"pk": asset_continuity_plan_a.pk}),
            reverse("assets:asset_business_continuity_plan_activate", kwargs={"pk": asset_continuity_plan_a.pk}),
            reverse("assets:asset_cybersecurity_profile_delete", kwargs={"pk": asset_cyber_profile_a.pk}),
            reverse("assets:asset_risk_mitigation_action_delete", kwargs={"pk": asset_mitigation_action_a.pk}),
            reverse("assets:asset_risk_mitigation_action_verify", kwargs={"pk": asset_mitigation_action_a.pk}),
        ]
        for url in admin_post_urls:
            assert member_client.post(url, {}).status_code == 403

        # Non-admin operational workflow actions are permitted for tenant members
        asset_risk_register_a.status = "identified"
        asset_risk_register_a.save(update_fields=["status"])
        assert member_client.post(
            reverse("assets:asset_risk_register_assess", kwargs={"pk": asset_risk_register_a.pk})
        ).status_code == 302
        assert member_client.post(
            reverse("assets:asset_business_continuity_plan_drill", kwargs={"pk": asset_continuity_plan_a.pk}),
            {"drill_result": "passed"},
        ).status_code == 302
        assert member_client.post(
            reverse("assets:asset_cybersecurity_profile_scan", kwargs={"pk": asset_cyber_profile_a.pk})
        ).status_code == 302
        assert member_client.post(
            reverse("assets:asset_risk_mitigation_action_complete", kwargs={"pk": asset_mitigation_action_a.pk})
        ).status_code == 302

    def test_asset_risk_post_only_endpoints_reject_get_with_405(
        self,
        client_a,
        asset_risk_register_a,
        asset_continuity_plan_a,
        asset_cyber_profile_a,
        asset_mitigation_action_a,
    ):
        for url in _asset_risk_sec_post_only_endpoints(
            asset_risk_register_a,
            asset_continuity_plan_a,
            asset_cyber_profile_a,
            asset_mitigation_action_a,
        ):
            resp = client_a.get(url)
            assert resp.status_code == 405, f"Expected 405 for GET on POST-only endpoint {url}"


# =====================================================================
# 4. Foreign-Key Injection & Mass-Assignment Protection
# =====================================================================

class TestAssetRiskInjectionAndMassAssignment:
    def test_asset_risk_rejects_foreign_tenant_fk_injection_on_create(
        self,
        client_a,
        operational_asset_a,
        operational_asset_b,
        category_a,
        category_b,
        admin_user,
        admin_b,
        asset_risk_register_b,
        vendor_party_b,
    ):
        # 1. Foreign asset on Risk Register create
        r_count = AssetRiskRegister.objects.count()
        resp_r = client_a.post(reverse("assets:asset_risk_register_create"), {
            "title": "Injected Cross-Tenant Risk",
            "asset": operational_asset_b.pk,
            "category": category_b.pk,
            "risk_category": "operational",
            "threat_source": "equipment_wear",
            "inherent_likelihood": 4,
            "inherent_impact": 4,
            "risk_owner": admin_b.pk,
            "treatment_strategy": "mitigate",
            "financial_exposure_amount": "5000.00",
            "status": "identified",
            "review_frequency": "quarterly",
        })
        assert resp_r.status_code == 200
        assert AssetRiskRegister.objects.count() == r_count

        # 2. Foreign primary asset on BCP create
        bcp_count = AssetBusinessContinuityPlan.objects.count()
        resp_bcp = client_a.post(reverse("assets:asset_business_continuity_plan_create"), {
            "title": "Injected Cross-Tenant BCP",
            "primary_asset": operational_asset_b.pk,
            "redundancy_type": "hot_standby",
            "recovery_time_objective_hours": "1.00",
            "recovery_point_objective_hours": "0.50",
            "maximum_tolerable_downtime_hours": "4.00",
            "disaster_scenario": "power_grid_outage",
            "emergency_lead": admin_user.pk,
            "drill_frequency": "annually",
            "status": "draft",
        })
        assert resp_bcp.status_code == 200
        assert AssetBusinessContinuityPlan.objects.count() == bcp_count

        # 3. Foreign asset on Cyber Profile create
        cyber_count = AssetCyberSecurityProfile.objects.count()
        resp_cyb = client_a.post(reverse("assets:asset_cybersecurity_profile_create"), {
            "asset": operational_asset_b.pk,
            "device_type": "plc_controller",
            "network_zone": "control_plc",
            "firmware_version": "V1.0",
            "firmware_update_status": "up_to_date",
            "protocol_used": "modbus_tcp",
            "exposure_level": "isolated_vlan",
            "cve_risk_score": "1.0",
            "security_posture_status": "secure",
        })
        assert resp_cyb.status_code == 200
        assert AssetCyberSecurityProfile.objects.count() == cyber_count

        # 4. Foreign risk & alternative supplier on Mitigation Action create
        act_count = AssetRiskMitigationAction.objects.count()
        resp_act = client_a.post(reverse("assets:asset_risk_mitigation_action_create"), {
            "title": "Injected Mitigation",
            "risk": asset_risk_register_b.pk,
            "action_type": "engineering_control",
            "assigned_to": admin_user.pk,
            "alternative_supplier": vendor_party_b.pk,
            "target_completion_date": (timezone.now().date() + timedelta(days=10)).isoformat(),
            "estimated_cost": "100.00",
            "actual_cost": "0.00",
            "priority": "high",
            "status": "planned",
            "effectiveness_rating": "pending_evaluation",
        })
        assert resp_act.status_code == 200
        assert AssetRiskMitigationAction.objects.count() == act_count

    def test_asset_risk_mass_assignment_and_disabled_fields_ignored(
        self,
        client_a,
        tenant_a,
        tenant_b,
        operational_asset_a,
        category_a,
        admin_user,
        asset_continuity_plan_a,
    ):
        # Attempt to forge tenant, number, inherent_risk_score, inherent_risk_level
        resp = client_a.post(reverse("assets:asset_risk_register_create"), {
            "tenant": tenant_b.pk,
            "number": "ARK-FORGED-999",
            "inherent_risk_score": 1,
            "inherent_risk_level": "low",
            "title": "Mass Assignment Resistant Risk",
            "asset": operational_asset_a.pk,
            "category": category_a.pk,
            "risk_category": "operational",
            "threat_source": "equipment_wear",
            "inherent_likelihood": 5,
            "inherent_impact": 5,
            "residual_likelihood": 2,
            "residual_impact": 2,
            "risk_owner": admin_user.pk,
            "treatment_strategy": "mitigate",
            "financial_exposure_amount": "15000.00",
            "status": "identified",
            "review_frequency": "quarterly",
        })
        assert resp.status_code == 302
        created = AssetRiskRegister.objects.get(title="Mass Assignment Resistant Risk")
        assert created.tenant_id == tenant_a.pk
        assert created.number.startswith("ARK-")
        assert created.number != "ARK-FORGED-999"
        assert created.inherent_risk_score == 25
        assert created.inherent_risk_level == "critical"

        # Attempt to tamper disabled drill history fields on BCP edit POST
        orig_date = date(2026, 2, 1)
        asset_continuity_plan_a.drill_result = "passed"
        asset_continuity_plan_a.last_drill_date = orig_date
        asset_continuity_plan_a.save(update_fields=["drill_result", "last_drill_date"])

        resp_bcp = client_a.post(
            reverse("assets:asset_business_continuity_plan_edit", kwargs={"pk": asset_continuity_plan_a.pk}),
            {
                "tenant": tenant_b.pk,
                "number": "ABC-TAMPER",
                "title": "Tamper Resistant BCP",
                "primary_asset": operational_asset_a.pk,
                "backup_redundant_asset": "",
                "redundancy_type": "hot_standby",
                "recovery_time_objective_hours": "1.00",
                "recovery_point_objective_hours": "0.50",
                "maximum_tolerable_downtime_hours": "4.00",
                "disaster_scenario": "power_grid_outage",
                "emergency_lead": admin_user.pk,
                "drill_frequency": "quarterly",
                "status": "active",
                "drill_result": "failed",
                "last_drill_date": "2020-01-01",
            },
        )
        assert resp_bcp.status_code == 302
        asset_continuity_plan_a.refresh_from_db()
        assert asset_continuity_plan_a.tenant_id == tenant_a.pk
        assert asset_continuity_plan_a.number != "ABC-TAMPER"
        assert asset_continuity_plan_a.drill_result == "passed"
        assert asset_continuity_plan_a.last_drill_date == orig_date
