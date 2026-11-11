"""
Integration tests for Sub-module 11.12: Asset Risk Management Views.
Covers all 27 endpoints across AssetRiskRegister, AssetBusinessContinuityPlan,
AssetCyberSecurityProfile, and AssetRiskMitigationAction (list filters, search
including asset__code, junk params, KPIs, pagination, N+1 bounds, detail,
create, edit, delete, and state-transition actions).
"""
from datetime import date, timedelta
from decimal import Decimal
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

def _asset_risk_register_post_payload(asset, category, owner, **overrides):
    data = {
        "title": "High-Pressure Steam Valve Seal Degradation",
        "asset": asset.pk,
        "category": category.pk,
        "risk_category": "operational",
        "threat_source": "equipment_wear",
        "failure_mode": "Gasket blowout under thermal ramp",
        "description": "Measured micro-leaks during hydrostatic inspection.",
        "inherent_likelihood": 4,
        "inherent_impact": 5,
        "residual_likelihood": 2,
        "residual_impact": 3,
        "risk_owner": owner.pk,
        "treatment_strategy": "mitigate",
        "financial_exposure_amount": "85000.00",
        "status": "identified",
        "review_frequency": "quarterly",
        "next_review_date": (timezone.now().date() + timedelta(days=90)).isoformat(),
    }
    data.update(overrides)
    return data


def _asset_risk_bcp_post_payload(primary_asset, lead, backup_asset=None, **overrides):
    data = {
        "title": "Switchgear Bus-B Hot Failover Continuity Plan",
        "primary_asset": primary_asset.pk,
        "backup_redundant_asset": backup_asset.pk if backup_asset else "",
        "redundancy_type": "hot_standby",
        "recovery_time_objective_hours": "1.50",
        "recovery_point_objective_hours": "0.25",
        "maximum_tolerable_downtime_hours": "6.00",
        "disaster_scenario": "power_grid_outage",
        "failover_procedure": "Trip breaker A1 and lock bus-tie B2.",
        "failback_procedure": "Verify sync-check relay before main re-close.",
        "alternate_facility_site": "East Backup Substation",
        "critical_spares_required": "ATS contactor kit RK-55",
        "emergency_lead": lead.pk,
        "drill_frequency": "quarterly",
        "next_drill_date": (timezone.now().date() + timedelta(days=60)).isoformat(),
        "status": "draft",
    }
    data.update(overrides)
    return data


def _asset_risk_cyber_post_payload(asset, **overrides):
    data = {
        "asset": asset.pk,
        "device_type": "plc_controller",
        "ip_address": "10.42.8.15",
        "mac_address": "AA:BB:CC:DD:EE:11",
        "network_zone": "control_plc",
        "firmware_version": "V4.2.1",
        "latest_available_firmware": "V4.5.0",
        "firmware_update_status": "critical_patch_pending",
        "protocol_used": "modbus_tcp",
        "exposure_level": "isolated_vlan",
        "known_vulnerabilities_cve": "CVE-2025-9901",
        "cve_risk_score": "8.2",
        "compensating_controls": "Allowlisted unidirectional OT firewall rules.",
        "last_vulnerability_scan_date": timezone.now().date().isoformat(),
        "security_posture_status": "vulnerable",
        "patch_freeze_until": (timezone.now().date() + timedelta(days=14)).isoformat(),
    }
    data.update(overrides)
    return data


def _asset_risk_mitigation_post_payload(risk, assignee, supplier=None, **overrides):
    data = {
        "title": "Install Ultrasonic Flow & Vibration Telemetry Probe",
        "risk": risk.pk,
        "action_type": "engineering_control",
        "description": "Mount redundant telemetry sensor with PLC interlock.",
        "assigned_to": assignee.pk,
        "alternative_supplier": supplier.pk if supplier else "",
        "target_completion_date": (timezone.now().date() + timedelta(days=30)).isoformat(),
        "estimated_cost": "14500.00",
        "actual_cost": "0.00",
        "priority": "critical",
        "status": "planned",
        "verification_notes": "Awaiting procurement PO release.",
        "effectiveness_rating": "pending_evaluation",
    }
    data.update(overrides)
    return data


# =====================================================================
# 1. AssetRiskRegister Views
# =====================================================================

class TestAssetRiskRegisterViews:
    def test_asset_risk_register_list_renders_and_kpis(
        self, client_a, tenant_a, asset_risk_register_a, operational_asset_a, category_a, admin_user
    ):
        AssetRiskRegister.objects.create(
            tenant=tenant_a,
            title="Critical Hydraulic Seal Blowout",
            asset=operational_asset_a,
            category=category_a,
            risk_category="safety_health",
            threat_source="equipment_wear",
            inherent_likelihood=5,
            inherent_impact=5,
            risk_owner=admin_user,
            treatment_strategy="mitigate",
            financial_exposure_amount=Decimal("250000.00"),
            status="treating",
        )
        url = reverse("assets:asset_risk_register_list")
        resp = client_a.get(url)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert asset_risk_register_a.number in html
        assert asset_risk_register_a.title in html
        assert operational_asset_a.code in html

        assert resp.context["total_risks"] == 2
        assert resp.context["critical_risks_count"] >= 1
        assert resp.context["active_treatment_count"] == 1
        assert resp.context["total_financial_exposure"] >= Decimal("250000.00")
        for key in ["risks", "page_obj", "paginator", "is_paginated",
                    "category_choices", "level_choices", "status_choices", "strategy_choices"]:
            assert key in resp.context

    def test_asset_risk_register_list_filters_search_and_junk_params(
        self, client_a, tenant_a, asset_risk_register_a, operational_asset_a, category_a, admin_user
    ):
        second = AssetRiskRegister.objects.create(
            tenant=tenant_a,
            title="Supplier Sole-Source Delay",
            asset=operational_asset_a,
            category=category_a,
            risk_category="geopolitical_supply_chain",
            threat_source="supply_chain_disruption",
            inherent_likelihood=2,
            inherent_impact=2,
            risk_owner=admin_user,
            treatment_strategy="transfer",
            status="closed",
        )
        url = reverse("assets:asset_risk_register_list")

        # Search by number
        resp_num = client_a.get(url, {"q": asset_risk_register_a.number})
        assert resp_num.status_code == 200
        assert asset_risk_register_a in resp_num.context["risks"]
        assert second not in resp_num.context["risks"]

        # Search by asset__name
        resp_name = client_a.get(url, {"q": operational_asset_a.name})
        assert resp_name.status_code == 200
        assert asset_risk_register_a in resp_name.context["risks"]

        # Filter by status, risk_category, inherent_risk_level, treatment_strategy
        resp_filt = client_a.get(url, {
            "status": "closed",
            "risk_category": "geopolitical_supply_chain",
            "inherent_risk_level": "low",
            "treatment_strategy": "transfer",
        })
        assert resp_filt.status_code == 200
        assert list(resp_filt.context["risks"]) == [second]

        # Junk query params handled gracefully
        resp_junk = client_a.get(url, {"status": "nonexistent", "page": "abc", "foo": "bar"})
        assert resp_junk.status_code == 200

    def test_asset_risk_register_list_pagination_and_query_budget(
        self, client_a, tenant_a, operational_asset_a, category_a, admin_user, django_assert_max_num_queries
    ):
        for i in range(26):
            AssetRiskRegister.objects.create(
                tenant=tenant_a,
                title=f"Bulk Risk Item {i}",
                asset=operational_asset_a,
                category=category_a,
                risk_owner=admin_user,
                inherent_likelihood=3,
                inherent_impact=3,
            )
        url = reverse("assets:asset_risk_register_list")
        with django_assert_max_num_queries(15):
            resp_p1 = client_a.get(url)
        assert resp_p1.status_code == 200
        assert resp_p1.context["is_paginated"] is True
        assert len(resp_p1.context["risks"]) == 25

        resp_p2 = client_a.get(url, {"page": 2})
        assert resp_p2.status_code == 200
        assert len(resp_p2.context["risks"]) == 1

    def test_asset_risk_register_detail_create_edit_delete(
        self, client_a, asset_risk_register_a, operational_asset_a, category_a, admin_user, asset_mitigation_action_a
    ):
        # Detail
        detail_url = reverse("assets:asset_risk_register_detail", kwargs={"pk": asset_risk_register_a.pk})
        resp_detail = client_a.get(detail_url)
        assert resp_detail.status_code == 200
        html = resp_detail.content.decode()
        assert asset_risk_register_a.number in html
        assert operational_asset_a.code in html
        assert "Back to List" in html
        assert asset_mitigation_action_a in resp_detail.context["mitigation_actions"]

        # Create GET & POST
        create_url = reverse("assets:asset_risk_register_create")
        assert client_a.get(create_url).status_code == 200
        payload = _asset_risk_register_post_payload(operational_asset_a, category_a, admin_user)
        resp_create = client_a.post(create_url, payload)
        assert resp_create.status_code == 302
        created = AssetRiskRegister.objects.get(title=payload["title"])
        assert created.inherent_risk_score == 20
        assert created.inherent_risk_level == "critical"

        # Edit GET & POST
        edit_url = reverse("assets:asset_risk_register_edit", kwargs={"pk": created.pk})
        resp_edit_get = client_a.get(edit_url)
        assert resp_edit_get.status_code == 200
        assert resp_edit_get.context["is_edit"] is True
        payload["title"] = "Updated Valve Risk Title"
        payload["inherent_likelihood"] = 2
        payload["inherent_impact"] = 2
        resp_edit_post = client_a.post(edit_url, payload)
        assert resp_edit_post.status_code == 302
        created.refresh_from_db()
        assert created.title == "Updated Valve Risk Title"
        assert created.inherent_risk_score == 4

        # Delete POST (and 405 on GET)
        delete_url = reverse("assets:asset_risk_register_delete", kwargs={"pk": created.pk})
        assert client_a.get(delete_url).status_code == 405
        resp_del = client_a.post(delete_url)
        assert resp_del.status_code == 302
        assert not AssetRiskRegister.objects.filter(pk=created.pk).exists()

    def test_asset_risk_register_assess_and_close_actions_and_guards(
        self, client_a, asset_risk_register_a
    ):
        asset_risk_register_a.status = "identified"
        asset_risk_register_a.save(update_fields=["status"])

        assess_url = reverse("assets:asset_risk_register_assess", kwargs={"pk": asset_risk_register_a.pk})
        close_url = reverse("assets:asset_risk_register_close", kwargs={"pk": asset_risk_register_a.pk})

        # Valid assess transition: identified -> assessed
        resp_assess = client_a.post(assess_url)
        assert resp_assess.status_code == 302
        asset_risk_register_a.refresh_from_db()
        assert asset_risk_register_a.status == "assessed"
        assert asset_risk_register_a.last_reviewed_at is not None

        # Invalid assess guard: assessed -> cannot re-assess
        prev_review = asset_risk_register_a.last_reviewed_at
        resp_assess_invalid = client_a.post(assess_url)
        assert resp_assess_invalid.status_code == 302
        asset_risk_register_a.refresh_from_db()
        assert asset_risk_register_a.status == "assessed"
        assert asset_risk_register_a.last_reviewed_at == prev_review

        # Valid close transition: assessed -> closed
        resp_close = client_a.post(close_url)
        assert resp_close.status_code == 302
        asset_risk_register_a.refresh_from_db()
        assert asset_risk_register_a.status == "closed"

        # Invalid close guard: already closed
        resp_close_again = client_a.post(close_url)
        assert resp_close_again.status_code == 302
        asset_risk_register_a.refresh_from_db()
        assert asset_risk_register_a.status == "closed"


# =====================================================================
# 2. AssetBusinessContinuityPlan Views
# =====================================================================

class TestAssetBusinessContinuityPlanViews:
    def test_asset_risk_bcp_list_filters_kpis_and_pagination(
        self, client_a, tenant_a, operational_asset_a, admin_user, django_assert_max_num_queries
    ):
        spof_plan = AssetBusinessContinuityPlan.objects.create(
            tenant=tenant_a,
            title="Spindle Bearing SPOF Plan",
            primary_asset=operational_asset_a,
            redundancy_type="none_single_point_of_failure",
            recovery_time_objective_hours=Decimal("12.00"),
            disaster_scenario="critical_hardware_loss",
            emergency_lead=admin_user,
            status="active",
        )
        for i in range(25):
            AssetBusinessContinuityPlan.objects.create(
                tenant=tenant_a,
                title=f"Hot Standby Cell Plan {i}",
                primary_asset=operational_asset_a,
                redundancy_type="hot_standby",
                recovery_time_objective_hours=Decimal("2.00"),
                disaster_scenario="power_grid_outage",
                emergency_lead=admin_user,
                status="draft",
            )

        url = reverse("assets:asset_business_continuity_plan_list")
        with django_assert_max_num_queries(15):
            resp = client_a.get(url)
        assert resp.status_code == 200
        assert resp.context["total_plans"] == 26
        assert resp.context["active_plans_count"] == 1
        assert resp.context["spof_count"] == 1
        assert resp.context["is_paginated"] is True
        assert len(resp.context["plans"]) == 25

        resp_p2 = client_a.get(url, {"page": 2})
        assert resp_p2.status_code == 200
        assert len(resp_p2.context["plans"]) == 1

        # Search by primary asset name + filter
        resp_filt = client_a.get(url, {
            "q": operational_asset_a.name,
            "redundancy_type": "none_single_point_of_failure",
            "disaster_scenario": "critical_hardware_loss",
            "status": "active",
        })
        assert resp_filt.status_code == 200
        assert list(resp_filt.context["plans"]) == [spof_plan]

        # Junk params
        assert client_a.get(url, {"status": "invalid", "page": "xyz"}).status_code == 200

    def test_asset_risk_bcp_detail_create_edit_delete(
        self, client_a, asset_continuity_plan_a, operational_asset_a, admin_user
    ):
        detail_url = reverse(
            "assets:asset_business_continuity_plan_detail",
            kwargs={"pk": asset_continuity_plan_a.pk},
        )
        resp_detail = client_a.get(detail_url)
        assert resp_detail.status_code == 200
        html = resp_detail.content.decode()
        assert asset_continuity_plan_a.number in html
        assert operational_asset_a.code in html
        assert "Back to List" in html

        # Create
        create_url = reverse("assets:asset_business_continuity_plan_create")
        assert client_a.get(create_url).status_code == 200
        payload = _asset_risk_bcp_post_payload(operational_asset_a, admin_user)
        resp_create = client_a.post(create_url, payload)
        assert resp_create.status_code == 302
        created = AssetBusinessContinuityPlan.objects.get(title=payload["title"])

        # Edit (drill history fields are disabled on form so DB values remain intact)
        created.drill_result = "passed"
        created.save(update_fields=["drill_result"])
        edit_url = reverse("assets:asset_business_continuity_plan_edit", kwargs={"pk": created.pk})
        assert client_a.get(edit_url).status_code == 200
        payload["title"] = "Updated Switchgear Failover Plan"
        payload["drill_result"] = "failed"
        resp_edit = client_a.post(edit_url, payload)
        assert resp_edit.status_code == 302
        created.refresh_from_db()
        assert created.title == "Updated Switchgear Failover Plan"
        assert created.drill_result == "passed"

        # Delete
        delete_url = reverse("assets:asset_business_continuity_plan_delete", kwargs={"pk": created.pk})
        assert client_a.get(delete_url).status_code == 405
        assert client_a.post(delete_url).status_code == 302
        assert not AssetBusinessContinuityPlan.objects.filter(pk=created.pk).exists()

    def test_asset_risk_bcp_activate_and_drill_actions(
        self, client_a, asset_continuity_plan_a
    ):
        asset_continuity_plan_a.status = "draft"
        asset_continuity_plan_a.save(update_fields=["status"])

        activate_url = reverse(
            "assets:asset_business_continuity_plan_activate",
            kwargs={"pk": asset_continuity_plan_a.pk},
        )
        drill_url = reverse(
            "assets:asset_business_continuity_plan_drill",
            kwargs={"pk": asset_continuity_plan_a.pk},
        )

        # Valid activate: draft -> active
        assert client_a.post(activate_url).status_code == 302
        asset_continuity_plan_a.refresh_from_db()
        assert asset_continuity_plan_a.status == "active"

        # Invalid activate guard when already active -> remains active
        asset_continuity_plan_a.status = "deprecated"
        asset_continuity_plan_a.save(update_fields=["status"])
        assert client_a.post(activate_url).status_code == 302
        asset_continuity_plan_a.refresh_from_db()
        assert asset_continuity_plan_a.status == "deprecated"

        # Drill with valid choice
        assert client_a.post(drill_url, {"drill_result": "passed_with_deficiencies"}).status_code == 302
        asset_continuity_plan_a.refresh_from_db()
        assert asset_continuity_plan_a.drill_result == "passed_with_deficiencies"
        assert asset_continuity_plan_a.last_drill_date == timezone.now().date()

        # Drill with invalid choice falls back to "passed"
        assert client_a.post(drill_url, {"drill_result": "forged_result"}).status_code == 302
        asset_continuity_plan_a.refresh_from_db()
        assert asset_continuity_plan_a.drill_result == "passed"


# =====================================================================
# 3. AssetCyberSecurityProfile Views
# =====================================================================

class TestAssetCyberSecurityProfileViews:
    def test_asset_risk_cyber_list_filters_search_and_pagination(
        self, client_a, tenant_a, operational_asset_a, django_assert_max_num_queries
    ):
        from apps.scm.models import Asset

        scada_asset = Asset.objects.create(
            tenant=tenant_a,
            code="AST-SCADA-99",
            name="Supervisory SCADA Rack 99",
            asset_type="equipment",
        )
        vuln = AssetCyberSecurityProfile.objects.create(
            tenant=tenant_a,
            asset=scada_asset,
            device_type="scada_server",
            ip_address="10.99.1.50",
            mac_address="11:22:33:44:55:66",
            network_zone="supervisory_scada",
            firmware_version="V9.9.1",
            firmware_update_status="critical_patch_pending",
            security_posture_status="vulnerable",
            cve_risk_score=Decimal("9.1"),
        )
        for i in range(25):
            AssetCyberSecurityProfile.objects.create(
                tenant=tenant_a,
                asset=operational_asset_a,
                device_type="iot_sensor",
                network_zone="process_io",
                firmware_version=f"V1.0.{i}",
                firmware_update_status="up_to_date",
                security_posture_status="secure",
            )

        url = reverse("assets:asset_cybersecurity_profile_list")
        with django_assert_max_num_queries(15):
            resp = client_a.get(url)
        assert resp.status_code == 200
        assert resp.context["total_profiles"] == 26
        assert resp.context["secure_count"] == 25
        assert resp.context["vulnerable_count"] == 1
        assert resp.context["critical_patches_count"] == 1
        assert resp.context["is_paginated"] is True
        assert len(resp.context["profiles"]) == 25

        resp_p2 = client_a.get(url, {"page": 2})
        assert resp_p2.status_code == 200
        assert len(resp_p2.context["profiles"]) == 1

        # Search by asset__code and IP address + filters
        resp_code = client_a.get(url, {"q": scada_asset.code})
        assert resp_code.status_code == 200
        assert list(resp_code.context["profiles"]) == [vuln]

        resp_filt = client_a.get(url, {
            "q": "10.99.1.50",
            "device_type": "scada_server",
            "network_zone": "supervisory_scada",
            "security_posture_status": "vulnerable",
            "firmware_update_status": "critical_patch_pending",
        })
        assert resp_filt.status_code == 200
        assert list(resp_filt.context["profiles"]) == [vuln]

        # Junk params
        assert client_a.get(url, {"device_type": "bogus", "page": "-1"}).status_code == 200

    def test_asset_risk_cyber_detail_create_edit_delete_and_scan(
        self, client_a, asset_cyber_profile_a, operational_asset_a
    ):
        detail_url = reverse(
            "assets:asset_cybersecurity_profile_detail",
            kwargs={"pk": asset_cyber_profile_a.pk},
        )
        resp_detail = client_a.get(detail_url)
        assert resp_detail.status_code == 200
        html = resp_detail.content.decode()
        assert asset_cyber_profile_a.number in html
        assert operational_asset_a.code in html
        assert "Back to List" in html

        # Create
        create_url = reverse("assets:asset_cybersecurity_profile_create")
        assert client_a.get(create_url).status_code == 200
        payload = _asset_risk_cyber_post_payload(operational_asset_a)
        resp_create = client_a.post(create_url, payload)
        assert resp_create.status_code == 302
        created = AssetCyberSecurityProfile.objects.get(ip_address="10.42.8.15")

        # Edit
        edit_url = reverse("assets:asset_cybersecurity_profile_edit", kwargs={"pk": created.pk})
        assert client_a.get(edit_url).status_code == 200
        payload["firmware_version"] = "V4.5.0"
        payload["firmware_update_status"] = "up_to_date"
        assert client_a.post(edit_url, payload).status_code == 302
        created.refresh_from_db()
        assert created.firmware_version == "V4.5.0"

        # Scan action
        created.last_vulnerability_scan_date = None
        created.save(update_fields=["last_vulnerability_scan_date"])
        scan_url = reverse("assets:asset_cybersecurity_profile_scan", kwargs={"pk": created.pk})
        assert client_a.get(scan_url).status_code == 405
        assert client_a.post(scan_url).status_code == 302
        created.refresh_from_db()
        assert created.last_vulnerability_scan_date == timezone.now().date()

        # Delete
        delete_url = reverse("assets:asset_cybersecurity_profile_delete", kwargs={"pk": created.pk})
        assert client_a.get(delete_url).status_code == 405
        assert client_a.post(delete_url).status_code == 302
        assert not AssetCyberSecurityProfile.objects.filter(pk=created.pk).exists()


# =====================================================================
# 4. AssetRiskMitigationAction Views
# =====================================================================

class TestAssetRiskMitigationActionViews:
    def test_asset_risk_mitigation_list_filters_kpis_and_pagination(
        self, client_a, tenant_a, asset_risk_register_a, admin_user, django_assert_max_num_queries
    ):
        action_vip = AssetRiskMitigationAction.objects.create(
            tenant=tenant_a,
            title="Dual-Source Critical Spare Valves",
            risk=asset_risk_register_a,
            action_type="supplier_diversification",
            priority="critical",
            status="in_progress",
            effectiveness_rating="partially_effective",
            assigned_to=admin_user,
            target_completion_date=date(2027, 1, 15),
            estimated_cost=Decimal("20000.00"),
            actual_cost=Decimal("5000.00"),
        )
        for i in range(25):
            AssetRiskMitigationAction.objects.create(
                tenant=tenant_a,
                title=f"Routine Inspection Task {i}",
                risk=asset_risk_register_a,
                action_type="preventive_inspection",
                priority="low",
                status="verified_effective",
                effectiveness_rating="highly_effective",
                assigned_to=admin_user,
                target_completion_date=date(2027, 2, 1),
                estimated_cost=Decimal("100.00"),
                actual_cost=Decimal("100.00"),
            )

        url = reverse("assets:asset_risk_mitigation_action_list")
        with django_assert_max_num_queries(15):
            resp = client_a.get(url)
        assert resp.status_code == 200
        assert resp.context["total_actions"] == 26
        assert resp.context["in_progress_count"] == 1
        assert resp.context["verified_count"] == 25
        assert resp.context["total_estimated_cost"] == Decimal("22500.00")
        assert resp.context["total_actual_cost"] == Decimal("7500.00")
        assert resp.context["is_paginated"] is True
        assert len(resp.context["actions"]) == 25

        resp_p2 = client_a.get(url, {"page": 2})
        assert resp_p2.status_code == 200
        assert len(resp_p2.context["actions"]) == 1

        # Filter + search across parent risk number/title
        resp_filt = client_a.get(url, {
            "q": asset_risk_register_a.number,
            "action_type": "supplier_diversification",
            "priority": "critical",
            "status": "in_progress",
            "effectiveness_rating": "partially_effective",
        })
        assert resp_filt.status_code == 200
        assert list(resp_filt.context["actions"]) == [action_vip]

        assert client_a.get(url, {"status": "bad", "page": "notanint"}).status_code == 200

    def test_asset_risk_mitigation_detail_create_prefill_edit_delete(
        self, client_a, asset_mitigation_action_a, asset_risk_register_a, admin_user, vendor_party_a
    ):
        detail_url = reverse(
            "assets:asset_risk_mitigation_action_detail",
            kwargs={"pk": asset_mitigation_action_a.pk},
        )
        resp_detail = client_a.get(detail_url)
        assert resp_detail.status_code == 200
        html = resp_detail.content.decode()
        assert asset_mitigation_action_a.number in html
        assert asset_risk_register_a.number in html
        assert "Back to List" in html

        # Create GET with ?risk=<pk> prefill
        create_url = reverse("assets:asset_risk_mitigation_action_create")
        resp_prefill = client_a.get(create_url, {"risk": asset_risk_register_a.pk})
        assert resp_prefill.status_code == 200
        assert resp_prefill.context["form"].initial.get("risk") == asset_risk_register_a

        # Create POST
        payload = _asset_risk_mitigation_post_payload(asset_risk_register_a, admin_user, vendor_party_a)
        resp_create = client_a.post(create_url, payload)
        assert resp_create.status_code == 302
        created = AssetRiskMitigationAction.objects.get(title=payload["title"])

        # Edit GET & POST
        edit_url = reverse("assets:asset_risk_mitigation_action_edit", kwargs={"pk": created.pk})
        assert client_a.get(edit_url).status_code == 200
        payload["title"] = "Updated Telemetry Probe Action"
        payload["actual_cost"] = "13200.00"
        assert client_a.post(edit_url, payload).status_code == 302
        created.refresh_from_db()
        assert created.title == "Updated Telemetry Probe Action"
        assert created.actual_cost == Decimal("13200.00")

        # Delete
        delete_url = reverse("assets:asset_risk_mitigation_action_delete", kwargs={"pk": created.pk})
        assert client_a.get(delete_url).status_code == 405
        assert client_a.post(delete_url).status_code == 302
        assert not AssetRiskMitigationAction.objects.filter(pk=created.pk).exists()

    def test_asset_risk_mitigation_complete_and_verify_actions_and_guards(
        self, client_a, asset_mitigation_action_a
    ):
        asset_mitigation_action_a.status = "planned"
        asset_mitigation_action_a.save(update_fields=["status"])

        complete_url = reverse(
            "assets:asset_risk_mitigation_action_complete",
            kwargs={"pk": asset_mitigation_action_a.pk},
        )
        verify_url = reverse(
            "assets:asset_risk_mitigation_action_verify",
            kwargs={"pk": asset_mitigation_action_a.pk},
        )

        # Guard: cannot verify while status == "planned"
        assert client_a.post(verify_url, {"effectiveness_rating": "highly_effective"}).status_code == 302
        asset_mitigation_action_a.refresh_from_db()
        assert asset_mitigation_action_a.status == "planned"

        # Valid complete: planned -> completed
        assert client_a.post(complete_url).status_code == 302
        asset_mitigation_action_a.refresh_from_db()
        assert asset_mitigation_action_a.status == "completed"
        assert asset_mitigation_action_a.actual_completion_date == timezone.now().date()

        # Guard: cannot re-complete once completed
        assert client_a.post(complete_url).status_code == 302
        asset_mitigation_action_a.refresh_from_db()
        assert asset_mitigation_action_a.status == "completed"

        # Valid verify: completed -> verified_effective (invalid rating defaults to highly_effective)
        assert client_a.post(verify_url, {"effectiveness_rating": "bogus_rating"}).status_code == 302
        asset_mitigation_action_a.refresh_from_db()
        assert asset_mitigation_action_a.status == "verified_effective"
        assert asset_mitigation_action_a.effectiveness_rating == "highly_effective"
