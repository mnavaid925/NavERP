"""
Unit & Integration tests for Sub-module 11.12: Asset Risk Management Forms.
Covers AssetRiskRegisterForm, AssetBusinessContinuityPlanForm,
AssetCyberSecurityProfileForm, and AssetRiskMitigationActionForm.
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.forms import (
    AssetRiskRegisterForm,
    AssetBusinessContinuityPlanForm,
    AssetCyberSecurityProfileForm,
    AssetRiskMitigationActionForm,
)
from apps.core.models import Party

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (_asset_risk_*)
# =====================================================================

def _asset_risk_valid_register_payload(asset, category, owner):
    return {
        "title": "Main Turbine Shaft Fatigue Crack",
        "asset": asset.pk,
        "category": category.pk,
        "risk_category": "operational",
        "threat_source": "equipment_wear",
        "failure_mode": "Micro-crack propagation at blade root",
        "description": "Thermal cycling stress over 10,000 operating hours.",
        "inherent_likelihood": 4,
        "inherent_impact": 5,
        "residual_likelihood": 2,
        "residual_impact": 3,
        "risk_owner": owner.pk,
        "treatment_strategy": "mitigate",
        "financial_exposure_amount": "125000.00",
        "status": "assessed",
        "review_frequency": "quarterly",
        "next_review_date": (timezone.now().date() + timezone.timedelta(days=90)).isoformat(),
    }


def _asset_risk_valid_bcp_payload(primary_asset, backup_asset, lead):
    return {
        "title": "Primary Substation Emergency Switchgear Failover Plan",
        "primary_asset": primary_asset.pk,
        "backup_redundant_asset": backup_asset.pk if backup_asset else "",
        "redundancy_type": "hot_standby",
        "recovery_time_objective_hours": "0.50",
        "recovery_point_objective_hours": "0.10",
        "maximum_tolerable_downtime_hours": "4.00",
        "disaster_scenario": "power_grid_outage",
        "failover_procedure": "Engage automatic transfer switch bus B.",
        "failback_procedure": "Synchronize phase angle before utility re-close.",
        "alternate_facility_site": "North Auxiliary Substation",
        "critical_spares_required": "Relay module RK-102",
        "emergency_lead": lead.pk,
        "drill_frequency": "quarterly",
        "next_drill_date": (timezone.now().date() + timezone.timedelta(days=45)).isoformat(),
        "status": "draft",
    }


def _asset_risk_valid_cyber_payload(asset):
    return {
        "asset": asset.pk,
        "device_type": "plc_controller",
        "ip_address": "192.168.50.10",
        "mac_address": "00:1A:2B:3C:4D:99",
        "network_zone": "control_plc",
        "firmware_version": "V5.1.0",
        "latest_available_firmware": "V5.2.0",
        "firmware_update_status": "update_available",
        "protocol_used": "modbus_tcp",
        "exposure_level": "isolated_vlan",
        "known_vulnerabilities_cve": "CVE-2025-1102",
        "cve_risk_score": "6.5",
        "compensating_controls": "OT deep packet inspection firewall enabled.",
        "last_vulnerability_scan_date": timezone.now().date().isoformat(),
        "security_posture_status": "attention_required",
        "patch_freeze_until": (timezone.now().date() + timezone.timedelta(days=30)).isoformat(),
    }


def _asset_risk_valid_mitigation_payload(risk, assignee, supplier=None):
    return {
        "title": "Retrofit Laser Alignment Vibration Monitoring Sensors",
        "risk": risk.pk,
        "action_type": "preventive_inspection",
        "description": "Install online vibration probes with threshold alarms.",
        "assigned_to": assignee.pk,
        "alternative_supplier": supplier.pk if supplier else "",
        "target_completion_date": (timezone.now().date() + timezone.timedelta(days=21)).isoformat(),
        "estimated_cost": "8500.00",
        "actual_cost": "0.00",
        "priority": "high",
        "status": "planned",
        "verification_notes": "Pending installation.",
        "effectiveness_rating": "pending_evaluation",
    }


# =====================================================================
# 1. AssetRiskRegisterForm Tests
# =====================================================================

class TestAssetRiskRegisterForm:
    def test_asset_risk_register_form_valid(
        self, tenant_a, operational_asset_a, category_a, admin_user
    ):
        payload = _asset_risk_valid_register_payload(operational_asset_a, category_a, admin_user)
        form = AssetRiskRegisterForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save(commit=False)
        obj.tenant = tenant_a
        obj.save()
        assert obj.inherent_risk_score == 20
        assert obj.inherent_risk_level == "critical"

    def test_asset_risk_register_form_excludes_system_fields(self, tenant_a):
        form = AssetRiskRegisterForm(tenant=tenant_a)
        for excluded in [
            "tenant",
            "number",
            "inherent_risk_score",
            "inherent_risk_level",
            "residual_risk_score",
            "residual_risk_level",
            "last_reviewed_at",
            "created_at",
            "updated_at",
        ]:
            assert excluded not in form.fields

    def test_asset_risk_register_form_missing_required_title(
        self, tenant_a, operational_asset_a, category_a, admin_user
    ):
        payload = _asset_risk_valid_register_payload(operational_asset_a, category_a, admin_user)
        payload["title"] = ""
        form = AssetRiskRegisterForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "title" in form.errors

    def test_asset_risk_register_form_tenant_scopes_dropdowns(
        self, tenant_a, operational_asset_a, operational_asset_b, category_a, category_b, admin_user, admin_b
    ):
        form = AssetRiskRegisterForm(tenant=tenant_a)
        asset_qs = form.fields["asset"].queryset
        cat_qs = form.fields["category"].queryset
        owner_qs = form.fields["risk_owner"].queryset

        assert operational_asset_a in asset_qs
        assert operational_asset_b not in asset_qs
        assert category_a in cat_qs
        assert category_b not in cat_qs
        assert admin_user in owner_qs
        assert admin_b not in owner_qs

    def test_asset_risk_register_form_rejects_foreign_asset_in_post(
        self, tenant_a, operational_asset_b, category_a, admin_user
    ):
        payload = _asset_risk_valid_register_payload(operational_asset_b, category_a, admin_user)
        form = AssetRiskRegisterForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "asset" in form.errors

    def test_asset_risk_register_form_rejects_foreign_category_in_post(
        self, tenant_a, operational_asset_a, category_b, admin_user
    ):
        payload = _asset_risk_valid_register_payload(operational_asset_a, category_b, admin_user)
        form = AssetRiskRegisterForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "category" in form.errors

    def test_asset_risk_register_form_rejects_foreign_owner_in_post(
        self, tenant_a, operational_asset_a, category_a, admin_b
    ):
        payload = _asset_risk_valid_register_payload(operational_asset_a, category_a, admin_b)
        form = AssetRiskRegisterForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "risk_owner" in form.errors


# =====================================================================
# 2. AssetBusinessContinuityPlanForm Tests
# =====================================================================

class TestAssetBusinessContinuityPlanForm:
    def test_asset_risk_bcp_form_valid(self, tenant_a, operational_asset_a, admin_user):
        from apps.scm.models import Asset

        backup = Asset.objects.create(
            tenant=tenant_a,
            code="AST-BAK-99",
            name="Backup Generator 99",
            asset_type="equipment",
        )
        payload = _asset_risk_valid_bcp_payload(operational_asset_a, backup, admin_user)
        form = AssetBusinessContinuityPlanForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_asset_risk_bcp_form_excludes_system_fields(self, tenant_a):
        form = AssetBusinessContinuityPlanForm(tenant=tenant_a)
        for excluded in ["tenant", "number", "created_at", "updated_at"]:
            assert excluded not in form.fields

    def test_asset_risk_bcp_form_disables_drill_history_fields(self, tenant_a):
        form = AssetBusinessContinuityPlanForm(tenant=tenant_a)
        assert form.fields["last_drill_date"].disabled is True
        assert form.fields["drill_result"].disabled is True

    def test_asset_risk_bcp_form_ignores_forged_drill_result_on_post(
        self, tenant_a, asset_continuity_plan_a, operational_asset_a, admin_user
    ):
        payload = _asset_risk_valid_bcp_payload(operational_asset_a, None, admin_user)
        payload["drill_result"] = "passed"
        form = AssetBusinessContinuityPlanForm(
            data=payload, instance=asset_continuity_plan_a, tenant=tenant_a
        )
        assert form.is_valid(), form.errors
        updated = form.save()
        # Disabled fields preserve existing instance value instead of forged POST data
        assert updated.drill_result == "not_tested"

    def test_asset_risk_bcp_form_rejects_identical_primary_and_backup_asset(
        self, tenant_a, operational_asset_a, admin_user
    ):
        payload = _asset_risk_valid_bcp_payload(operational_asset_a, operational_asset_a, admin_user)
        form = AssetBusinessContinuityPlanForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "identical machine" in str(form.non_field_errors()).lower()

    def test_asset_risk_bcp_form_tenant_scopes_dropdowns(
        self, tenant_a, operational_asset_a, operational_asset_b, admin_user, admin_b
    ):
        form = AssetBusinessContinuityPlanForm(tenant=tenant_a)
        assert operational_asset_a in form.fields["primary_asset"].queryset
        assert operational_asset_b not in form.fields["primary_asset"].queryset
        assert operational_asset_a in form.fields["backup_redundant_asset"].queryset
        assert operational_asset_b not in form.fields["backup_redundant_asset"].queryset
        assert admin_user in form.fields["emergency_lead"].queryset
        assert admin_b not in form.fields["emergency_lead"].queryset

    def test_asset_risk_bcp_form_rejects_foreign_assets_in_post(
        self, tenant_a, operational_asset_b, admin_user
    ):
        payload = _asset_risk_valid_bcp_payload(operational_asset_b, None, admin_user)
        form = AssetBusinessContinuityPlanForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "primary_asset" in form.errors


# =====================================================================
# 3. AssetCyberSecurityProfileForm Tests
# =====================================================================

class TestAssetCyberSecurityProfileForm:
    def test_asset_risk_cyber_form_valid(self, tenant_a, operational_asset_a):
        payload = _asset_risk_valid_cyber_payload(operational_asset_a)
        form = AssetCyberSecurityProfileForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_asset_risk_cyber_form_excludes_system_fields(self, tenant_a):
        form = AssetCyberSecurityProfileForm(tenant=tenant_a)
        for excluded in ["tenant", "number", "created_at", "updated_at"]:
            assert excluded not in form.fields

    def test_asset_risk_cyber_form_cvss_score_bounds(self, tenant_a, operational_asset_a):
        # Negative CVSS score invalid
        payload = _asset_risk_valid_cyber_payload(operational_asset_a)
        payload["cve_risk_score"] = "-0.1"
        form = AssetCyberSecurityProfileForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "cve_risk_score" in form.errors

        # CVSS score > 10.0 invalid
        payload["cve_risk_score"] = "10.1"
        form_high = AssetCyberSecurityProfileForm(data=payload, tenant=tenant_a)
        assert not form_high.is_valid()
        assert "cve_risk_score" in form_high.errors

        # Boundaries 0.0 and 10.0 valid
        payload["cve_risk_score"] = "0.0"
        assert AssetCyberSecurityProfileForm(data=payload, tenant=tenant_a).is_valid()
        payload["cve_risk_score"] = "10.0"
        assert AssetCyberSecurityProfileForm(data=payload, tenant=tenant_a).is_valid()

    def test_asset_risk_cyber_form_rejects_invalid_ip_address(self, tenant_a, operational_asset_a):
        payload = _asset_risk_valid_cyber_payload(operational_asset_a)
        payload["ip_address"] = "999.999.1.1"
        form = AssetCyberSecurityProfileForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "ip_address" in form.errors

    def test_asset_risk_cyber_form_tenant_scopes_asset(
        self, tenant_a, operational_asset_a, operational_asset_b
    ):
        form = AssetCyberSecurityProfileForm(tenant=tenant_a)
        assert operational_asset_a in form.fields["asset"].queryset
        assert operational_asset_b not in form.fields["asset"].queryset

    def test_asset_risk_cyber_form_rejects_foreign_asset_in_post(
        self, tenant_a, operational_asset_b
    ):
        payload = _asset_risk_valid_cyber_payload(operational_asset_b)
        form = AssetCyberSecurityProfileForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "asset" in form.errors


# =====================================================================
# 4. AssetRiskMitigationActionForm Tests
# =====================================================================

class TestAssetRiskMitigationActionForm:
    def test_asset_risk_mitigation_form_valid(
        self, tenant_a, asset_risk_register_a, admin_user, vendor_party_a
    ):
        payload = _asset_risk_valid_mitigation_payload(
            asset_risk_register_a, admin_user, vendor_party_a
        )
        form = AssetRiskMitigationActionForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_asset_risk_mitigation_form_excludes_system_fields(self, tenant_a):
        form = AssetRiskMitigationActionForm(tenant=tenant_a)
        for excluded in ["tenant", "number", "actual_completion_date", "created_at", "updated_at"]:
            assert excluded not in form.fields

    def test_asset_risk_mitigation_form_tenant_scopes_dropdowns(
        self,
        tenant_a,
        asset_risk_register_a,
        asset_risk_register_b,
        admin_user,
        admin_b,
        vendor_party_a,
        vendor_party_b,
    ):
        form = AssetRiskMitigationActionForm(tenant=tenant_a)
        assert asset_risk_register_a in form.fields["risk"].queryset
        assert asset_risk_register_b not in form.fields["risk"].queryset
        assert admin_user in form.fields["assigned_to"].queryset
        assert admin_b not in form.fields["assigned_to"].queryset
        assert vendor_party_a in form.fields["alternative_supplier"].queryset
        assert vendor_party_b not in form.fields["alternative_supplier"].queryset

    def test_asset_risk_mitigation_form_rejects_foreign_risk_in_post(
        self, tenant_a, asset_risk_register_b, admin_user
    ):
        payload = _asset_risk_valid_mitigation_payload(asset_risk_register_b, admin_user)
        form = AssetRiskMitigationActionForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "risk" in form.errors

    def test_asset_risk_mitigation_form_rejects_foreign_supplier_in_post(
        self, tenant_a, asset_risk_register_a, admin_user, vendor_party_b
    ):
        payload = _asset_risk_valid_mitigation_payload(
            asset_risk_register_a, admin_user, vendor_party_b
        )
        form = AssetRiskMitigationActionForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "alternative_supplier" in form.errors

    def test_asset_risk_mitigation_form_missing_required_target_date(
        self, tenant_a, asset_risk_register_a, admin_user
    ):
        payload = _asset_risk_valid_mitigation_payload(asset_risk_register_a, admin_user)
        payload["target_completion_date"] = ""
        form = AssetRiskMitigationActionForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "target_completion_date" in form.errors
