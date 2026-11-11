"""
Unit tests for Sub-module 11.12: Asset Risk Management Models.
Covers AssetRiskRegister, AssetBusinessContinuityPlan, AssetCyberSecurityProfile,
and AssetRiskMitigationAction.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.models import (
    AssetRiskRegister,
    AssetBusinessContinuityPlan,
    AssetCyberSecurityProfile,
    AssetRiskMitigationAction,
)
from apps.scm.models import Asset
from apps.core.models import Party

pytestmark = pytest.mark.django_db

VALID_BADGE_CLASSES = {
    "badge-slate",
    "badge-info",
    "badge-amber",
    "badge-green",
    "badge-red",
    "badge-purple",
    "badge-muted",
}


# =====================================================================
# Module-level Helpers (Must start with _asset_risk_*)
# =====================================================================

def _asset_risk_create_register(tenant, title="CNC Bearing Wear Risk", **kwargs):
    """Helper to instantiate AssetRiskRegister with defaults."""
    data = {
        "tenant": tenant,
        "title": title,
        "risk_category": "operational",
        "threat_source": "equipment_wear",
        "inherent_likelihood": 3,
        "inherent_impact": 3,
        "residual_likelihood": 2,
        "residual_impact": 2,
        "treatment_strategy": "mitigate",
        "financial_exposure_amount": Decimal("15000.00"),
        "status": "identified",
        "review_frequency": "quarterly",
    }
    data.update(kwargs)
    return AssetRiskRegister.objects.create(**data)


def _asset_risk_create_bcp(tenant, title="Generator Backup Plan", **kwargs):
    """Helper to instantiate AssetBusinessContinuityPlan with defaults."""
    data = {
        "tenant": tenant,
        "title": title,
        "redundancy_type": "warm_standby",
        "recovery_time_objective_hours": Decimal("4.00"),
        "recovery_point_objective_hours": Decimal("1.00"),
        "maximum_tolerable_downtime_hours": Decimal("24.00"),
        "disaster_scenario": "critical_hardware_loss",
        "drill_frequency": "annually",
        "drill_result": "not_tested",
        "status": "draft",
    }
    data.update(kwargs)
    return AssetBusinessContinuityPlan.objects.create(**data)


def _asset_risk_create_cyber_profile(tenant, asset, **kwargs):
    """Helper to instantiate AssetCyberSecurityProfile with defaults."""
    data = {
        "tenant": tenant,
        "asset": asset,
        "device_type": "plc_controller",
        "ip_address": "192.168.10.15",
        "mac_address": "AA:BB:CC:DD:EE:01",
        "network_zone": "control_plc",
        "firmware_version": "1.0.0",
        "firmware_update_status": "up_to_date",
        "protocol_used": "modbus_tcp",
        "exposure_level": "isolated_vlan",
        "cve_risk_score": Decimal("0.0"),
        "security_posture_status": "secure",
    }
    data.update(kwargs)
    return AssetCyberSecurityProfile.objects.create(**data)


def _asset_risk_create_mitigation(tenant, risk, title="Install Sensor", **kwargs):
    """Helper to instantiate AssetRiskMitigationAction with defaults."""
    data = {
        "tenant": tenant,
        "risk": risk,
        "title": title,
        "action_type": "preventive_inspection",
        "priority": "medium",
        "status": "planned",
        "target_completion_date": timezone.now().date() + timezone.timedelta(days=30),
        "estimated_cost": Decimal("2000.00"),
        "actual_cost": Decimal("0.00"),
        "effectiveness_rating": "pending_evaluation",
    }
    data.update(kwargs)
    return AssetRiskMitigationAction.objects.create(**data)


# =====================================================================
# 1. AssetRiskRegister Tests
# =====================================================================

class TestAssetRiskRegisterModel:
    """Model test suite for AssetRiskRegister [ARK-]."""

    def test_asset_risk_register_autonumber_and_prefix(self, tenant_a, operational_asset_a):
        """Verifies auto-numbering generates ARK- prefix and increments sequentially."""
        r1 = _asset_risk_create_register(tenant_a, title="Risk Alpha", asset=operational_asset_a)
        r2 = _asset_risk_create_register(tenant_a, title="Risk Beta", asset=operational_asset_a)

        assert r1.number.startswith("ARK-")
        assert r2.number.startswith("ARK-")
        assert r1.number != r2.number

        # Parse numeric suffixes and verify increment
        num1 = int(r1.number.split("-")[1])
        num2 = int(r2.number.split("-")[1])
        assert num2 == num1 + 1

    def test_asset_risk_register_str_representation(self, asset_risk_register_a):
        """Verifies __str__ representation format f'{number} — {title} ({inherent_risk_level_display})'."""
        expected = f"{asset_risk_register_a.number} — {asset_risk_register_a.title} ({asset_risk_register_a.get_inherent_risk_level_display()})"
        assert str(asset_risk_register_a) == expected

    def test_asset_risk_register_calculate_scores_matrix_bounds(self, tenant_a):
        """Verifies 5x5 matrix scoring (1-25) and level mappings for all 4 severity bands."""
        # Low risk: 1-4 (e.g. 1x1=1, 2x2=4)
        r_low = _asset_risk_create_register(
            tenant_a,
            title="Low Risk Item",
            inherent_likelihood=1,
            inherent_impact=1,
            residual_likelihood=2,
            residual_impact=2,
        )
        assert r_low.inherent_risk_score == 1
        assert r_low.inherent_risk_level == "low"
        assert r_low.residual_risk_score == 4
        assert r_low.residual_risk_level == "low"

        # Medium risk: 5-9 (e.g. 1x5=5, 3x3=9)
        r_med = _asset_risk_create_register(
            tenant_a,
            title="Medium Risk Item",
            inherent_likelihood=1,
            inherent_impact=5,
            residual_likelihood=3,
            residual_impact=3,
        )
        assert r_med.inherent_risk_score == 5
        assert r_med.inherent_risk_level == "medium"
        assert r_med.residual_risk_score == 9
        assert r_med.residual_risk_level == "medium"

        # High risk: 10-14 (e.g. 2x5=10, 3x4=12, 2x6->bound to 2x5=10)
        r_high = _asset_risk_create_register(
            tenant_a,
            title="High Risk Item",
            inherent_likelihood=2,
            inherent_impact=5,
            residual_likelihood=3,
            residual_impact=4,
        )
        assert r_high.inherent_risk_score == 10
        assert r_high.inherent_risk_level == "high"
        assert r_high.residual_risk_score == 12
        assert r_high.residual_risk_level == "high"

        # Critical risk: 15-25 (e.g. 3x5=15, 5x5=25)
        r_crit = _asset_risk_create_register(
            tenant_a,
            title="Critical Risk Item",
            inherent_likelihood=3,
            inherent_impact=5,
            residual_likelihood=5,
            residual_impact=5,
        )
        assert r_crit.inherent_risk_score == 15
        assert r_crit.inherent_risk_level == "critical"
        assert r_crit.residual_risk_score == 25
        assert r_crit.residual_risk_level == "critical"

    def test_asset_risk_register_calculate_scores_clamping(self, tenant_a):
        """Verifies calculate_scores() clamps likelihood and impact within bounds [1, 5]."""
        # Values below 1 or None should clamp to 1
        r_clamp_min = AssetRiskRegister(
            tenant=tenant_a,
            title="Clamp Min Test",
            inherent_likelihood=0,
            inherent_impact=None,
            residual_likelihood=-5,
            residual_impact=0,
        )
        r_clamp_min.calculate_scores()
        assert r_clamp_min.inherent_likelihood == 1
        assert r_clamp_min.inherent_impact == 1
        assert r_clamp_min.inherent_risk_score == 1
        assert r_clamp_min.inherent_risk_level == "low"
        assert r_clamp_min.residual_likelihood == 1
        assert r_clamp_min.residual_impact == 1
        assert r_clamp_min.residual_risk_score == 1
        assert r_clamp_min.residual_risk_level == "low"

        # Values above 5 should clamp to 5
        r_clamp_max = AssetRiskRegister(
            tenant=tenant_a,
            title="Clamp Max Test",
            inherent_likelihood=10,
            inherent_impact=99,
            residual_likelihood=6,
            residual_impact=7,
        )
        r_clamp_max.calculate_scores()
        assert r_clamp_max.inherent_likelihood == 5
        assert r_clamp_max.inherent_impact == 5
        assert r_clamp_max.inherent_risk_score == 25
        assert r_clamp_max.inherent_risk_level == "critical"
        assert r_clamp_max.residual_likelihood == 5
        assert r_clamp_max.residual_impact == 5
        assert r_clamp_max.residual_risk_score == 25
        assert r_clamp_max.residual_risk_level == "critical"

    def test_asset_risk_register_save_triggers_calculate_scores(self, tenant_a):
        """Verifies save() automatically recalculates scores and levels before saving."""
        r = AssetRiskRegister(
            tenant=tenant_a,
            title="Dynamic Save Scoring",
            inherent_likelihood=4,
            inherent_impact=4,
            residual_likelihood=2,
            residual_impact=1,
        )
        # Prior to save, defaults may not reflect the customized inputs
        r.save()
        r.refresh_from_db()
        assert r.inherent_risk_score == 16
        assert r.inherent_risk_level == "critical"
        assert r.residual_risk_score == 2
        assert r.residual_risk_level == "low"

    def test_asset_risk_register_defaults_and_choices(self, tenant_a):
        """Verifies default values and valid choices on AssetRiskRegister."""
        r = AssetRiskRegister.objects.create(
            tenant=tenant_a,
            title="Defaults Verification",
        )
        assert r.risk_category == "operational"
        assert r.threat_source == "equipment_wear"
        assert r.failure_mode == ""
        assert r.description == ""
        assert r.inherent_likelihood == 3
        assert r.inherent_impact == 3
        assert r.inherent_risk_score == 9
        assert r.inherent_risk_level == "medium"
        assert r.residual_likelihood == 2
        assert r.residual_impact == 2
        assert r.residual_risk_score == 4
        assert r.residual_risk_level == "low"
        assert r.treatment_strategy == "mitigate"
        assert r.financial_exposure_amount == Decimal("0.00")
        assert r.status == "identified"
        assert r.review_frequency == "quarterly"
        assert r.next_review_date is None
        assert r.last_reviewed_at is None

        # Validate choice sets
        cat_choices = [c[0] for c in AssetRiskRegister.RISK_CATEGORY_CHOICES]
        assert "operational" in cat_choices
        assert "financial" in cat_choices
        assert "safety_health" in cat_choices
        assert "environmental" in cat_choices
        assert "cybersecurity" in cat_choices
        assert "regulatory" in cat_choices
        assert "geopolitical_supply_chain" in cat_choices
        assert "reputational" in cat_choices

        threat_choices = [c[0] for c in AssetRiskRegister.THREAT_SOURCE_CHOICES]
        assert "equipment_wear" in threat_choices
        assert "cyber_attack" in threat_choices
        assert "extreme_weather" in threat_choices

        strat_choices = [c[0] for c in AssetRiskRegister.TREATMENT_STRATEGY_CHOICES]
        assert "mitigate" in strat_choices
        assert "transfer" in strat_choices
        assert "avoid" in strat_choices
        assert "accept" in strat_choices

        stat_choices = [c[0] for c in AssetRiskRegister.STATUS_CHOICES]
        assert "identified" in stat_choices
        assert "assessed" in stat_choices
        assert "treating" in stat_choices
        assert "monitored" in stat_choices
        assert "closed" in stat_choices

    def test_asset_risk_register_badge_properties(self, asset_risk_register_a):
        """Verifies badge color properties strictly map to valid theme.css badges."""
        # Status badges
        for status_val, expected_css in AssetRiskRegister.STATUS_CSS.items():
            asset_risk_register_a.status = status_val
            assert asset_risk_register_a.status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_risk_register_a.status = "unknown_status"
        assert asset_risk_register_a.status_badge_class == "badge-slate"

        # Inherent Risk Level badges
        for lvl_val, expected_css in AssetRiskRegister.RISK_LEVEL_CSS.items():
            asset_risk_register_a.inherent_risk_level = lvl_val
            assert asset_risk_register_a.inherent_risk_level_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_risk_register_a.inherent_risk_level = "unknown_level"
        assert asset_risk_register_a.inherent_risk_level_badge_class == "badge-slate"

        # Residual Risk Level badges
        for lvl_val, expected_css in AssetRiskRegister.RISK_LEVEL_CSS.items():
            asset_risk_register_a.residual_risk_level = lvl_val
            assert asset_risk_register_a.residual_risk_level_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_risk_register_a.residual_risk_level = "unknown_level"
        assert asset_risk_register_a.residual_risk_level_badge_class == "badge-slate"

        # Risk Category badges
        for cat_val, expected_css in AssetRiskRegister.RISK_CATEGORY_CSS.items():
            asset_risk_register_a.risk_category = cat_val
            assert asset_risk_register_a.risk_category_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_risk_register_a.risk_category = "unknown_category"
        assert asset_risk_register_a.risk_category_badge_class == "badge-slate"

        # Treatment Strategy badges
        for strat_val, expected_css in AssetRiskRegister.TREATMENT_STRATEGY_CSS.items():
            asset_risk_register_a.treatment_strategy = strat_val
            assert asset_risk_register_a.treatment_strategy_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_risk_register_a.treatment_strategy = "unknown_strategy"
        assert asset_risk_register_a.treatment_strategy_badge_class == "badge-slate"

    def test_asset_risk_register_tenant_unique_constraint(self, tenant_a, tenant_b):
        """Verifies UniqueConstraint(tenant, number) rejects duplicate numbers within tenant but allows across tenants."""
        r_a1 = _asset_risk_create_register(tenant_a, title="Acme Risk 1")

        # Duplicate number under tenant_a must raise IntegrityError
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                r_duplicate = AssetRiskRegister(
                    tenant=tenant_a,
                    title="Acme Duplicate",
                    number=r_a1.number,
                )
                r_duplicate.save()

        # Same number under tenant_b must succeed
        r_b1 = AssetRiskRegister(
            tenant=tenant_b,
            title="Globex Risk Same Number",
            number=r_a1.number,
        )
        r_b1.save()
        assert r_b1.pk is not None
        assert r_b1.number == r_a1.number
        assert r_b1.tenant != r_a1.tenant


# =====================================================================
# 2. AssetBusinessContinuityPlan Tests
# =====================================================================

class TestAssetBusinessContinuityPlanModel:
    """Model test suite for AssetBusinessContinuityPlan [ABC-]."""

    def test_asset_risk_bcp_autonumber_and_prefix(self, tenant_a, operational_asset_a):
        """Verifies auto-numbering generates ABC- prefix and increments sequentially."""
        p1 = _asset_risk_create_bcp(tenant_a, title="BCP Prime", primary_asset=operational_asset_a)
        p2 = _asset_risk_create_bcp(tenant_a, title="BCP Aux", primary_asset=operational_asset_a)

        assert p1.number.startswith("ABC-")
        assert p2.number.startswith("ABC-")
        assert p1.number != p2.number

        num1 = int(p1.number.split("-")[1])
        num2 = int(p2.number.split("-")[1])
        assert num2 == num1 + 1

    def test_asset_risk_bcp_str_representation(self, asset_continuity_plan_a):
        """Verifies __str__ representation format f'{number} — {title} ({redundancy_type_display})'."""
        expected = f"{asset_continuity_plan_a.number} — {asset_continuity_plan_a.title} ({asset_continuity_plan_a.get_redundancy_type_display()})"
        assert str(asset_continuity_plan_a) == expected

    def test_asset_risk_bcp_defaults_and_choices(self, tenant_a):
        """Verifies default values and valid choices on AssetBusinessContinuityPlan."""
        plan = AssetBusinessContinuityPlan.objects.create(
            tenant=tenant_a,
            title="Default BCP Validation",
        )
        assert plan.redundancy_type == "none_single_point_of_failure"
        assert plan.recovery_time_objective_hours == Decimal("4.00")
        assert plan.recovery_point_objective_hours == Decimal("1.00")
        assert plan.maximum_tolerable_downtime_hours == Decimal("24.00")
        assert plan.disaster_scenario == "critical_hardware_loss"
        assert plan.failover_procedure == ""
        assert plan.failback_procedure == ""
        assert plan.alternate_facility_site == ""
        assert plan.critical_spares_required == ""
        assert plan.drill_frequency == "annually"
        assert plan.last_drill_date is None
        assert plan.next_drill_date is None
        assert plan.drill_result == "not_tested"
        assert plan.status == "draft"

        # Validate choice sets
        red_choices = [c[0] for c in AssetBusinessContinuityPlan.REDUNDANCY_TYPE_CHOICES]
        assert "hot_standby" in red_choices
        assert "warm_standby" in red_choices
        assert "cold_standby" in red_choices
        assert "n_plus_one_cluster" in red_choices
        assert "reciprocal_agreement" in red_choices
        assert "mobile_replacement" in red_choices
        assert "none_single_point_of_failure" in red_choices

        scen_choices = [c[0] for c in AssetBusinessContinuityPlan.DISASTER_SCENARIO_CHOICES]
        assert "power_grid_outage" in scen_choices
        assert "fire_explosion" in scen_choices
        assert "flood_natural_disaster" in scen_choices
        assert "cyber_attack_ransomware" in scen_choices
        assert "critical_hardware_loss" in scen_choices
        assert "hazmat_contamination" in scen_choices

        res_choices = [c[0] for c in AssetBusinessContinuityPlan.DRILL_RESULT_CHOICES]
        assert "not_tested" in res_choices
        assert "passed" in res_choices
        assert "passed_with_deficiencies" in res_choices
        assert "failed" in res_choices

        status_choices = [c[0] for c in AssetBusinessContinuityPlan.STATUS_CHOICES]
        assert "draft" in status_choices
        assert "active" in status_choices
        assert "under_review" in status_choices
        assert "deprecated" in status_choices

    def test_asset_risk_bcp_badge_properties(self, asset_continuity_plan_a):
        """Verifies badge color properties strictly map to valid theme.css badges."""
        # Status badges
        for status_val, expected_css in AssetBusinessContinuityPlan.STATUS_CSS.items():
            asset_continuity_plan_a.status = status_val
            assert asset_continuity_plan_a.status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_continuity_plan_a.status = "unknown_status"
        assert asset_continuity_plan_a.status_badge_class == "badge-slate"

        # Redundancy type badges
        for red_val, expected_css in AssetBusinessContinuityPlan.REDUNDANCY_TYPE_CSS.items():
            asset_continuity_plan_a.redundancy_type = red_val
            assert asset_continuity_plan_a.redundancy_type_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_continuity_plan_a.redundancy_type = "unknown_redundancy"
        assert asset_continuity_plan_a.redundancy_type_badge_class == "badge-slate"

        # Drill result badges
        for res_val, expected_css in AssetBusinessContinuityPlan.DRILL_RESULT_CSS.items():
            asset_continuity_plan_a.drill_result = res_val
            assert asset_continuity_plan_a.drill_result_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_continuity_plan_a.drill_result = "unknown_result"
        assert asset_continuity_plan_a.drill_result_badge_class == "badge-slate"

        # Disaster scenario badges
        for scen_val, expected_css in AssetBusinessContinuityPlan.DISASTER_SCENARIO_CSS.items():
            asset_continuity_plan_a.disaster_scenario = scen_val
            assert asset_continuity_plan_a.disaster_scenario_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_continuity_plan_a.disaster_scenario = "unknown_scenario"
        assert asset_continuity_plan_a.disaster_scenario_badge_class == "badge-slate"

    def test_asset_risk_bcp_is_spof_property(self, asset_continuity_plan_a):
        """Verifies is_spof property correctly identifies Single Point of Failure."""
        asset_continuity_plan_a.redundancy_type = "none_single_point_of_failure"
        assert asset_continuity_plan_a.is_spof is True

        asset_continuity_plan_a.redundancy_type = "hot_standby"
        assert asset_continuity_plan_a.is_spof is False

        asset_continuity_plan_a.redundancy_type = "warm_standby"
        assert asset_continuity_plan_a.is_spof is False

        asset_continuity_plan_a.redundancy_type = "n_plus_one_cluster"
        assert asset_continuity_plan_a.is_spof is False

    def test_asset_risk_bcp_tenant_unique_constraint(self, tenant_a, tenant_b):
        """Verifies UniqueConstraint(tenant, number) rejects duplicate numbers within tenant but allows across tenants."""
        p_a1 = _asset_risk_create_bcp(tenant_a, title="Plan Acme 1")

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                p_dup = AssetBusinessContinuityPlan(
                    tenant=tenant_a,
                    title="Plan Acme Dup",
                    number=p_a1.number,
                )
                p_dup.save()

        p_b1 = AssetBusinessContinuityPlan(
            tenant=tenant_b,
            title="Plan Globex Same Number",
            number=p_a1.number,
        )
        p_b1.save()
        assert p_b1.pk is not None
        assert p_b1.number == p_a1.number
        assert p_b1.tenant != p_a1.tenant


# =====================================================================
# 3. AssetCyberSecurityProfile Tests
# =====================================================================

class TestAssetCyberSecurityProfileModel:
    """Model test suite for AssetCyberSecurityProfile [ACS-]."""

    def test_asset_risk_cyber_profile_autonumber_and_prefix(self, tenant_a, operational_asset_a):
        """Verifies auto-numbering generates ACS- prefix and increments sequentially."""
        p1 = _asset_risk_create_cyber_profile(tenant_a, asset=operational_asset_a)
        p2 = _asset_risk_create_cyber_profile(tenant_a, asset=operational_asset_a)

        assert p1.number.startswith("ACS-")
        assert p2.number.startswith("ACS-")
        assert p1.number != p2.number

        num1 = int(p1.number.split("-")[1])
        num2 = int(p2.number.split("-")[1])
        assert num2 == num1 + 1

    def test_asset_risk_cyber_profile_str_representation(self, asset_cyber_profile_a):
        """Verifies __str__ representation with linked asset f'{number} — {asset.name} ({device_type_display})'."""
        expected = f"{asset_cyber_profile_a.number} — {asset_cyber_profile_a.asset.name} ({asset_cyber_profile_a.get_device_type_display()})"
        assert str(asset_cyber_profile_a) == expected

    def test_asset_risk_cyber_profile_str_unlinked_defensive_check(self, tenant_a):
        """Verifies __str__ defensive handling when asset is None/unlinked."""
        profile = AssetCyberSecurityProfile(
            tenant=tenant_a,
            number="ACS-99999",
            device_type="plc_controller",
        )
        # asset is unset / unlinked
        expected = "ACS-99999 — Unlinked (Programmable Logic Controller (PLC))"
        assert str(profile) == expected

    def test_asset_risk_cyber_profile_defaults_and_choices(self, tenant_a, operational_asset_a):
        """Verifies default values and valid choices on AssetCyberSecurityProfile."""
        prof = AssetCyberSecurityProfile.objects.create(
            tenant=tenant_a,
            asset=operational_asset_a,
        )
        assert prof.device_type == "plc_controller"
        assert prof.ip_address is None
        assert prof.mac_address == ""
        assert prof.network_zone == "control_plc"
        assert prof.firmware_version == "1.0.0"
        assert prof.latest_available_firmware == ""
        assert prof.firmware_update_status == "up_to_date"
        assert prof.protocol_used == "modbus_tcp"
        assert prof.exposure_level == "isolated_vlan"
        assert prof.known_vulnerabilities_cve == ""
        assert prof.cve_risk_score == Decimal("0.0")
        assert prof.compensating_controls == ""
        assert prof.last_vulnerability_scan_date is None
        assert prof.security_posture_status == "secure"
        assert prof.patch_freeze_until is None

        # Validate choice sets
        dev_choices = [c[0] for c in AssetCyberSecurityProfile.DEVICE_TYPE_CHOICES]
        assert "plc_controller" in dev_choices
        assert "scada_server" in dev_choices
        assert "rtu_remote_terminal" in dev_choices
        assert "iot_sensor" in dev_choices
        assert "hmi_touchscreen" in dev_choices
        assert "network_switch_gateway" in dev_choices
        assert "vfd_drive" in dev_choices
        assert "smart_meter" in dev_choices
        assert "robotic_cell" in dev_choices

        zone_choices = [c[0] for c in AssetCyberSecurityProfile.NETWORK_ZONE_CHOICES]
        assert "enterprise_it" in zone_choices
        assert "dmz" in zone_choices
        assert "supervisory_scada" in zone_choices
        assert "control_plc" in zone_choices
        assert "process_io" in zone_choices
        assert "isolated_airgap" in zone_choices

        proto_choices = [c[0] for c in AssetCyberSecurityProfile.PROTOCOL_CHOICES]
        assert "modbus_tcp" in proto_choices
        assert "opc_ua" in proto_choices
        assert "ethernet_ip" in proto_choices
        assert "profinet" in proto_choices
        assert "mqtt" in proto_choices
        assert "https_rest" in proto_choices

        fw_choices = [c[0] for c in AssetCyberSecurityProfile.FIRMWARE_STATUS_CHOICES]
        assert "up_to_date" in fw_choices
        assert "update_available" in fw_choices
        assert "critical_patch_pending" in fw_choices
        assert "end_of_life_unsupported" in fw_choices

        exp_choices = [c[0] for c in AssetCyberSecurityProfile.EXPOSURE_LEVEL_CHOICES]
        assert "air_gapped" in exp_choices
        assert "isolated_vlan" in exp_choices
        assert "monitored_dmz" in exp_choices
        assert "internet_facing" in exp_choices

        post_choices = [c[0] for c in AssetCyberSecurityProfile.POSTURE_STATUS_CHOICES]
        assert "secure" in post_choices
        assert "attention_required" in post_choices
        assert "vulnerable" in post_choices
        assert "compromised" in post_choices

    def test_asset_risk_cyber_profile_badge_properties(self, asset_cyber_profile_a):
        """Verifies badge color properties strictly map to valid theme.css badges."""
        # Posture status badges
        for post_val, expected_css in AssetCyberSecurityProfile.POSTURE_STATUS_CSS.items():
            asset_cyber_profile_a.security_posture_status = post_val
            assert asset_cyber_profile_a.posture_status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_cyber_profile_a.security_posture_status = "unknown_status"
        assert asset_cyber_profile_a.posture_status_badge_class == "badge-slate"

        # Firmware status badges
        for fw_val, expected_css in AssetCyberSecurityProfile.FIRMWARE_STATUS_CSS.items():
            asset_cyber_profile_a.firmware_update_status = fw_val
            assert asset_cyber_profile_a.firmware_status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_cyber_profile_a.firmware_update_status = "unknown_status"
        assert asset_cyber_profile_a.firmware_status_badge_class == "badge-slate"

        # Network zone badges
        for zone_val, expected_css in AssetCyberSecurityProfile.NETWORK_ZONE_CSS.items():
            asset_cyber_profile_a.network_zone = zone_val
            assert asset_cyber_profile_a.network_zone_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_cyber_profile_a.network_zone = "unknown_zone"
        assert asset_cyber_profile_a.network_zone_badge_class == "badge-slate"

        # Exposure level badges
        for exp_val, expected_css in AssetCyberSecurityProfile.EXPOSURE_LEVEL_CSS.items():
            asset_cyber_profile_a.exposure_level = exp_val
            assert asset_cyber_profile_a.exposure_level_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_cyber_profile_a.exposure_level = "unknown_exposure"
        assert asset_cyber_profile_a.exposure_level_badge_class == "badge-slate"

    def test_asset_risk_cyber_profile_cvss_score_validation(self, tenant_a, operational_asset_a):
        """Verifies CVSS cve_risk_score validator bounds [0.0, 10.0]."""
        # Valid boundary scores
        for valid_score in [Decimal("0.0"), Decimal("5.5"), Decimal("9.8"), Decimal("10.0")]:
            profile = AssetCyberSecurityProfile(
                tenant=tenant_a,
                asset=operational_asset_a,
                cve_risk_score=valid_score,
            )
            profile.full_clean()  # Must not raise

        # Invalid: Negative score (< 0.0)
        invalid_neg = AssetCyberSecurityProfile(
            tenant=tenant_a,
            asset=operational_asset_a,
            cve_risk_score=Decimal("-0.1"),
        )
        with pytest.raises(ValidationError) as exc_info:
            invalid_neg.full_clean()
        assert "cve_risk_score" in exc_info.value.message_dict

        # Invalid: Out of upper bound (> 10.0)
        invalid_high = AssetCyberSecurityProfile(
            tenant=tenant_a,
            asset=operational_asset_a,
            cve_risk_score=Decimal("10.1"),
        )
        with pytest.raises(ValidationError) as exc_info:
            invalid_high.full_clean()
        assert "cve_risk_score" in exc_info.value.message_dict

    def test_asset_risk_cyber_profile_tenant_unique_constraint(self, tenant_a, tenant_b, operational_asset_a, operational_asset_b):
        """Verifies UniqueConstraint(tenant, number) rejects duplicate numbers within tenant but allows across tenants."""
        p_a1 = _asset_risk_create_cyber_profile(tenant_a, asset=operational_asset_a)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                p_dup = AssetCyberSecurityProfile(
                    tenant=tenant_a,
                    asset=operational_asset_a,
                    number=p_a1.number,
                )
                p_dup.save()

        p_b1 = AssetCyberSecurityProfile(
            tenant=tenant_b,
            asset=operational_asset_b,
            number=p_a1.number,
        )
        p_b1.save()
        assert p_b1.pk is not None
        assert p_b1.number == p_a1.number
        assert p_b1.tenant != p_a1.tenant


# =====================================================================
# 4. AssetRiskMitigationAction Tests
# =====================================================================

class TestAssetRiskMitigationActionModel:
    """Model test suite for AssetRiskMitigationAction [ARMA-]."""

    def test_asset_risk_mitigation_action_autonumber_and_prefix(self, tenant_a, asset_risk_register_a):
        """Verifies auto-numbering generates ARMA- prefix and increments sequentially."""
        a1 = _asset_risk_create_mitigation(tenant_a, risk=asset_risk_register_a, title="Action Alpha")
        a2 = _asset_risk_create_mitigation(tenant_a, risk=asset_risk_register_a, title="Action Beta")

        assert a1.number.startswith("ARMA-")
        assert a2.number.startswith("ARMA-")
        assert a1.number != a2.number

        num1 = int(a1.number.split("-")[1])
        num2 = int(a2.number.split("-")[1])
        assert num2 == num1 + 1

    def test_asset_risk_mitigation_action_str_representation(self, asset_mitigation_action_a):
        """Verifies __str__ representation format f'{number} — {title} ({status_display})'."""
        expected = f"{asset_mitigation_action_a.number} — {asset_mitigation_action_a.title} ({asset_mitigation_action_a.get_status_display()})"
        assert str(asset_mitigation_action_a) == expected

    def test_asset_risk_mitigation_action_defaults_and_choices(self, tenant_a, asset_risk_register_a):
        """Verifies default values and valid choices on AssetRiskMitigationAction."""
        deadline = timezone.now().date() + timezone.timedelta(days=15)
        action = AssetRiskMitigationAction.objects.create(
            tenant=tenant_a,
            risk=asset_risk_register_a,
            title="Defaults Verification Action",
            target_completion_date=deadline,
        )
        assert action.action_type == "engineering_control"
        assert action.description == ""
        assert action.assigned_to is None
        assert action.alternative_supplier is None
        assert action.target_completion_date == deadline
        assert action.actual_completion_date is None
        assert action.estimated_cost == Decimal("0.00")
        assert action.actual_cost == Decimal("0.00")
        assert action.priority == "medium"
        assert action.status == "planned"
        assert action.verification_notes == ""
        assert action.effectiveness_rating == "pending_evaluation"

        # Validate choice sets
        type_choices = [c[0] for c in AssetRiskMitigationAction.ACTION_TYPE_CHOICES]
        assert "engineering_control" in type_choices
        assert "redundancy_addition" in type_choices
        assert "firmware_security_patch" in type_choices
        assert "insurance_transfer" in type_choices
        assert "supplier_diversification" in type_choices
        assert "spare_parts_buffer" in type_choices
        assert "procedure_training" in type_choices
        assert "preventive_inspection" in type_choices

        prio_choices = [c[0] for c in AssetRiskMitigationAction.PRIORITY_CHOICES]
        assert "critical" in prio_choices
        assert "high" in prio_choices
        assert "medium" in prio_choices
        assert "low" in prio_choices

        stat_choices = [c[0] for c in AssetRiskMitigationAction.STATUS_CHOICES]
        assert "planned" in stat_choices
        assert "in_progress" in stat_choices
        assert "completed" in stat_choices
        assert "verified_effective" in stat_choices
        assert "deferred" in stat_choices
        assert "cancelled" in stat_choices

        eff_choices = [c[0] for c in AssetRiskMitigationAction.EFFECTIVENESS_CHOICES]
        assert "pending_evaluation" in eff_choices
        assert "highly_effective" in eff_choices
        assert "partially_effective" in eff_choices
        assert "ineffective" in eff_choices

    def test_asset_risk_mitigation_action_badge_properties(self, asset_mitigation_action_a):
        """Verifies badge color properties strictly map to valid theme.css badges."""
        # Status badges
        for status_val, expected_css in AssetRiskMitigationAction.STATUS_CSS.items():
            asset_mitigation_action_a.status = status_val
            assert asset_mitigation_action_a.status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_mitigation_action_a.status = "unknown_status"
        assert asset_mitigation_action_a.status_badge_class == "badge-slate"

        # Priority badges
        for prio_val, expected_css in AssetRiskMitigationAction.PRIORITY_CSS.items():
            asset_mitigation_action_a.priority = prio_val
            assert asset_mitigation_action_a.priority_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_mitigation_action_a.priority = "unknown_priority"
        assert asset_mitigation_action_a.priority_badge_class == "badge-slate"

        # Action type badges
        for type_val, expected_css in AssetRiskMitigationAction.ACTION_TYPE_CSS.items():
            asset_mitigation_action_a.action_type = type_val
            assert asset_mitigation_action_a.action_type_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_mitigation_action_a.action_type = "unknown_type"
        assert asset_mitigation_action_a.action_type_badge_class == "badge-slate"

        # Effectiveness badges
        for eff_val, expected_css in AssetRiskMitigationAction.EFFECTIVENESS_CSS.items():
            asset_mitigation_action_a.effectiveness_rating = eff_val
            assert asset_mitigation_action_a.effectiveness_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_mitigation_action_a.effectiveness_rating = "unknown_effectiveness"
        assert asset_mitigation_action_a.effectiveness_badge_class == "badge-slate"

    def test_asset_risk_mitigation_action_tenant_unique_constraint(self, tenant_a, tenant_b, asset_risk_register_a, asset_risk_register_b):
        """Verifies UniqueConstraint(tenant, number) rejects duplicate numbers within tenant but allows across tenants."""
        a_a1 = _asset_risk_create_mitigation(tenant_a, risk=asset_risk_register_a, title="Acme Action 1")

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                a_dup = AssetRiskMitigationAction(
                    tenant=tenant_a,
                    risk=asset_risk_register_a,
                    title="Acme Duplicate Action",
                    number=a_a1.number,
                    target_completion_date=timezone.now().date(),
                )
                a_dup.save()

        a_b1 = AssetRiskMitigationAction(
            tenant=tenant_b,
            risk=asset_risk_register_b,
            title="Globex Action Same Number",
            number=a_a1.number,
            target_completion_date=timezone.now().date(),
        )
        a_b1.save()
        assert a_b1.pk is not None
        assert a_b1.number == a_a1.number
        assert a_b1.tenant != a_a1.tenant


# =====================================================================
# 5. Cross-Model Relational Integrity & Cascades
# =====================================================================

class TestAssetRiskCrossModelIntegrity:
    """Relational integrity tests across Sub-module 11.12 models and core entities."""

    def test_asset_risk_cascade_on_risk_deletion(self, tenant_a, asset_risk_register_a):
        """Verifies deleting an AssetRiskRegister cascades to its mitigation actions."""
        action = _asset_risk_create_mitigation(tenant_a, risk=asset_risk_register_a, title="Child Action")
        action_pk = action.pk

        assert AssetRiskMitigationAction.objects.filter(pk=action_pk).exists()
        asset_risk_register_a.delete()
        assert not AssetRiskMitigationAction.objects.filter(pk=action_pk).exists()

    def test_asset_risk_null_on_asset_deletion(self, tenant_a):
        """Verifies deleting an Asset sets ForeignKeys to NULL on AssetRiskRegister and BCP."""
        asset = Asset.objects.create(
            tenant=tenant_a,
            name="Temporary Asset For Delete Test",
            asset_type="equipment",
        )
        risk = _asset_risk_create_register(tenant_a, asset=asset, title="Asset Delete Test")
        bcp = _asset_risk_create_bcp(tenant_a, primary_asset=asset, title="BCP Asset Delete Test")

        assert risk.asset_id == asset.pk
        assert bcp.primary_asset_id == asset.pk

        asset.delete()
        risk.refresh_from_db()
        bcp.refresh_from_db()

        assert risk.asset is None
        assert bcp.primary_asset is None

    def test_asset_risk_cyber_profile_cascades_on_asset_deletion(self, tenant_a):
        """Verifies AssetCyberSecurityProfile cascades upon parent Asset deletion."""
        asset = Asset.objects.create(
            tenant=tenant_a,
            name="PLC Hardware Node For Deletion",
            asset_type="equipment",
        )
        profile = _asset_risk_create_cyber_profile(tenant_a, asset=asset)
        profile_pk = profile.pk

        assert AssetCyberSecurityProfile.objects.filter(pk=profile_pk).exists()
        asset.delete()
        assert not AssetCyberSecurityProfile.objects.filter(pk=profile_pk).exists()

    def test_asset_risk_supplier_party_null_on_delete(self, tenant_a, asset_risk_register_a):
        """Verifies deleting alternative_supplier Party sets FK to NULL on AssetRiskMitigationAction."""
        supplier_party = Party.objects.create(
            tenant=tenant_a,
            name="Backup Component Foundry",
            kind="organization",
        )
        action = _asset_risk_create_mitigation(
            tenant_a,
            risk=asset_risk_register_a,
            alternative_supplier=supplier_party,
        )
        assert action.alternative_supplier_id == supplier_party.pk

        supplier_party.delete()
        action.refresh_from_db()
        assert action.alternative_supplier is None
