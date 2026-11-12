"""
Unit tests for Module 11.18: IT Asset Management (ITAM) Models & Validators.
Covers ItHardwareAsset [ITHW-], SoftwareLicense [ITSW-],
CloudAssetSubscription [ITCL-], CmdbRelationship [CMDB-],
shared validators, auto-numbering, constraints, badge classes,
derived properties, compliance/operational status computation,
and cross-tenant FK multi-error accumulation.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError, transaction
from django.utils import timezone

import apps.assets.models as assets_models
import apps.assets.models.ItAssetManagement as itam_models
from apps.assets.models import (
    CloudAssetSubscription,
    CmdbRelationship,
    ItHardwareAsset,
    SoftwareLicense,
)
from apps.assets.models.ItAssetManagement import (
    CloudAssetSubscription as DirectCloudAssetSubscription,
    CmdbRelationship as DirectCmdbRelationship,
    ItHardwareAsset as DirectItHardwareAsset,
    SoftwareLicense as DirectSoftwareLicense,
)
from apps.assets.models.ItAssetManagement._validators import (
    add_field_error,
    add_months,
    validate_masked_key_ref,
    validate_tenant_fks,
)
from apps.core.models import ServiceComponent

pytestmark = pytest.mark.django_db

_IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-muted",
    "badge-slate",
}


# =====================================================================
# Module-level Helpers (Must start with _it_asset_management_*)
# =====================================================================


def _it_asset_management_create_hardware(tenant, hostname="edge-fw-01", **kwargs):
    data = {
        "tenant": tenant,
        "hostname": hostname,
        "device_class": "laptop",
        "environment": "corporate_enduser",
        "criticality": "medium",
        "disk_encryption_status": "bitlocker_filevault",
        "status": "procured",
    }
    data.update(kwargs)
    return ItHardwareAsset.objects.create(**data)


def _it_asset_management_create_license(
    tenant, software_name="Atlassian Jira", publisher_name="Atlassian", **kwargs
):
    data = {
        "tenant": tenant,
        "software_name": software_name,
        "publisher_name": publisher_name,
        "software_category": "devops_ide",
        "license_type": "subscription_term",
        "license_metric": "per_user",
        "entitled_quantity": 20,
        "allocated_quantity": 18,
        "active_used_quantity": 15,
        "unit_license_cost": Decimal("100.00"),
        "status": "draft",
    }
    data.update(kwargs)
    return SoftwareLicense.objects.create(**data)


def _it_asset_management_create_cloud(tenant, name="GCP BigQuery", **kwargs):
    data = {
        "tenant": tenant,
        "name": name,
        "asset_kind": "paas_database",
        "provider": "gcp",
        "environment": "production",
        "monthly_recurring_cost": Decimal("1200.00"),
        "annual_contract_value": Decimal("14400.00"),
        "provisioned_seats": 20,
        "active_seats_30d": 15,
        "status": "active",
    }
    data.update(kwargs)
    return CloudAssetSubscription.objects.create(**data)


def _it_asset_management_create_service_component(tenant, name="Checkout API"):
    return ServiceComponent.objects.create(
        tenant=tenant,
        name=name,
        kind="api",
        current_status="operational",
    )


def _it_asset_management_create_cmdb(
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


# =====================================================================
# 1. Package Re-exports & Contract Registration
# =====================================================================


def test_it_asset_management_package_reexports():
    expected_itam = [
        "ItHardwareAsset",
        "SoftwareLicense",
        "CloudAssetSubscription",
        "CmdbRelationship",
    ]
    assert itam_models.__all__ == expected_itam
    assert ItHardwareAsset is DirectItHardwareAsset
    assert SoftwareLicense is DirectSoftwareLicense
    assert CloudAssetSubscription is DirectCloudAssetSubscription
    assert CmdbRelationship is DirectCmdbRelationship

    for symbol in expected_itam:
        assert symbol in assets_models.__all__
        assert getattr(assets_models, symbol) is getattr(itam_models, symbol)


# =====================================================================
# 2. Auto-Numbering, Monotonicity, Tenant Sequence Isolation & Uniqueness
# =====================================================================


def test_it_asset_management_auto_numbering_and_tenant_isolation(
    tenant_a, tenant_b, it_hardware_a, software_license_a, cloud_subscription_a
):
    hw_a1 = _it_asset_management_create_hardware(tenant_a, hostname="hw-a1")
    hw_a2 = _it_asset_management_create_hardware(tenant_a, hostname="hw-a2")
    hw_b1 = _it_asset_management_create_hardware(tenant_b, hostname="hw-b1")

    assert it_hardware_a.number == "ITHW-00001"
    assert hw_a1.number == "ITHW-00002"
    assert hw_a2.number == "ITHW-00003"
    assert hw_b1.number == "ITHW-00001"
    assert str(hw_a1) == "ITHW-00002 — hw-a1"

    sw_a1 = _it_asset_management_create_license(tenant_a, software_name="GitHub Copilot")
    sw_b1 = _it_asset_management_create_license(tenant_b, software_name="Slack Enterprise")
    assert software_license_a.number == "ITSW-00001"
    assert sw_a1.number == "ITSW-00002"
    assert sw_b1.number == "ITSW-00001"
    assert str(sw_a1) == "ITSW-00002 — GitHub Copilot"

    cl_a1 = _it_asset_management_create_cloud(tenant_a, name="Datadog APM")
    cl_b1 = _it_asset_management_create_cloud(tenant_b, name="Snowflake DW")
    assert cloud_subscription_a.number == "ITCL-00001"
    assert cl_a1.number == "ITCL-00002"
    assert cl_b1.number == "ITCL-00001"
    assert str(cl_a1) == "ITCL-00002 — Datadog APM"

    cmdb_a1 = _it_asset_management_create_cmdb(
        tenant_a,
        source_software=sw_a1,
        target_hardware=hw_a1,
    )
    cmdb_a2 = _it_asset_management_create_cmdb(
        tenant_a,
        source_software=sw_a1,
        target_hardware=hw_a2,
    )
    cmdb_b1 = _it_asset_management_create_cmdb(
        tenant_b,
        source_software=sw_b1,
        target_hardware=hw_b1,
    )
    assert cmdb_a1.number == "CMDB-00001"
    assert cmdb_a2.number == "CMDB-00002"
    assert cmdb_b1.number == "CMDB-00001"
    assert "CMDB-00001:" in str(cmdb_a1)
    assert "-> runs_on ->" in str(cmdb_a1)


def test_it_asset_management_tenant_number_uniqueness_constraints(
    tenant_a, it_hardware_a, software_license_a, cloud_subscription_a, cmdb_relationship_a
):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ItHardwareAsset.objects.create(
                tenant=tenant_a,
                number=it_hardware_a.number,
                hostname="dup-hw",
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SoftwareLicense.objects.create(
                tenant=tenant_a,
                number=software_license_a.number,
                software_name="Dup SW",
                publisher_name="Pub",
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CloudAssetSubscription.objects.create(
                tenant=tenant_a,
                number=cloud_subscription_a.number,
                name="Dup Cloud",
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CmdbRelationship.objects.create(
                tenant=tenant_a,
                number=cmdb_relationship_a.number,
                source_ci_type="software_license",
                source_software=software_license_a,
                target_ci_type="it_hardware",
                target_hardware=it_hardware_a,
            )


# =====================================================================
# 3. Badge CSS Class Allowlist Enforcement
# =====================================================================


def test_it_asset_management_all_badge_classes_are_valid_theme_classes(
    tenant_a, it_hardware_a, software_license_a, cloud_subscription_a, cmdb_relationship_a
):
    for status_key, _ in ItHardwareAsset.STATUS_CHOICES:
        it_hardware_a.status = status_key
        assert it_hardware_a.status_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES
    for crit_key, _ in ItHardwareAsset.CRITICALITY_CHOICES:
        it_hardware_a.criticality = crit_key
        assert it_hardware_a.criticality_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES
    for san_key, _ in ItHardwareAsset.SANITIZATION_STATUS_CHOICES:
        it_hardware_a.sanitization_status = san_key
        assert it_hardware_a.sanitization_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES
    for prio_key, css_cls in ItHardwareAsset.REFRESH_PRIORITY_CSS.items():
        assert css_cls in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES

    for status_key, _ in SoftwareLicense.STATUS_CHOICES:
        software_license_a.status = status_key
        assert software_license_a.status_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES

    for status_key, _ in CloudAssetSubscription.STATUS_CHOICES:
        cloud_subscription_a.status = status_key
        assert cloud_subscription_a.status_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES
    for aprv_key, _ in CloudAssetSubscription.APPROVAL_STATUS_CHOICES:
        cloud_subscription_a.approval_status = aprv_key
        assert cloud_subscription_a.approval_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES
    for sso_key, _ in CloudAssetSubscription.SSO_STATUS_CHOICES:
        cloud_subscription_a.sso_status = sso_key
        assert cloud_subscription_a.sso_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES

    for status_key, _ in CmdbRelationship.STATUS_CHOICES:
        cmdb_relationship_a.status = status_key
        assert cmdb_relationship_a.status_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES
    for crit_key, _ in CmdbRelationship.CRITICALITY_CHOICES:
        cmdb_relationship_a.criticality = crit_key
        assert cmdb_relationship_a.criticality_badge_class in _IT_ASSET_MANAGEMENT_VALID_BADGE_CLASSES

    # Unknown fallback always resolves to valid badge-slate
    it_hardware_a.status = "nonexistent"
    software_license_a.status = "nonexistent"
    cloud_subscription_a.status = "nonexistent"
    cmdb_relationship_a.status = "nonexistent"
    assert it_hardware_a.status_badge_class == "badge-slate"
    assert software_license_a.status_badge_class == "badge-slate"
    assert cloud_subscription_a.status_badge_class == "badge-slate"
    assert cmdb_relationship_a.status_badge_class == "badge-slate"


# =====================================================================
# 4. Shared Validators (_validators.py)
# =====================================================================


def test_it_asset_management_validators_add_months_and_field_errors():
    assert add_months(None, 12) is None
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert add_months(date(2026, 3, 15), 48) == date(2030, 3, 15)

    errors = {}
    add_field_error(errors, "hostname", "First error")
    add_field_error(errors, "hostname", "Second error")
    assert errors == {"hostname": ["First error", "Second error"]}

    unsaved = ItHardwareAsset(hostname="no-tenant")
    assert validate_tenant_fks(unsaved, ("org_unit",)) == {}


def test_it_asset_management_validate_masked_key_ref_rules():
    assert validate_masked_key_ref("") == ""
    assert validate_masked_key_ref("   ") == ""
    assert validate_masked_key_ref(None) == ""
    assert validate_masked_key_ref("  MS365-****-9X2K  ") == "MS365-****-9X2K"
    assert validate_masked_key_ref("XXXX-XXXX-1234") == "XXXX-XXXX-1234"
    assert validate_masked_key_ref("xxxx-abcd-9999") == "xxxx-abcd-9999"
    assert validate_masked_key_ref("VOLUME-MAK") == "VOLUME-MAK"

    rejected_samples = [
        # Raw Microsoft-style multi-segment keys (even with an 'X' character)
        "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
        "X2345-67890-ABCDE-FGHIJ-KLMNO",
        "1234-5678-9012",
        # Long unbroken 16+ char hex / API keys
        "0123456789abcdef0123456789abcdef",
        "abcdef1234567890",
        "token_1234567890abcdef",
        # Token prefixes even if short
        "AKIAIOSFODNN7EXAMPLE",
        "AKIA1234",
        "sk_live_abc123",
        "pk_test_xyz",
        "ghp_123456",
        "gho_abc",
        "glpat-12345",
        "xoxb-123",
        "xoxp-999",
    ]
    for raw_secret in rejected_samples:
        with pytest.raises(ValidationError):
            validate_masked_key_ref(raw_secret)


# =====================================================================
# 5. ItHardwareAsset Model Tests
# =====================================================================


def test_it_asset_management_hardware_refresh_due_date_derivation(tenant_a):
    # Derived from commissioned_date + refresh_cycle_months
    hw1 = _it_asset_management_create_hardware(
        tenant_a,
        hostname="calc-from-commissioned",
        commissioned_date=date(2024, 1, 31),
        refresh_cycle_months=1,
        vendor_eol_date=date(2029, 12, 31),
    )
    assert hw1.refresh_due_date == date(2024, 2, 29)

    # Fallback to vendor_eol_date when commissioned_date is absent
    hw2 = _it_asset_management_create_hardware(
        tenant_a,
        hostname="fallback-to-eol",
        commissioned_date=None,
        vendor_eol_date=date(2028, 6, 30),
    )
    assert hw2.refresh_due_date == date(2028, 6, 30)

    # Explicit refresh_due_date is preserved
    explicit_date = date(2027, 11, 15)
    hw3 = _it_asset_management_create_hardware(
        tenant_a,
        hostname="explicit-refresh",
        commissioned_date=date(2024, 1, 1),
        refresh_cycle_months=48,
        refresh_due_date=explicit_date,
    )
    assert hw3.refresh_due_date == explicit_date


def test_it_asset_management_hardware_lifecycle_properties_and_refresh_tiers(tenant_a):
    today = timezone.now().date()

    # Overdue via refresh_due_date < today
    hw = _it_asset_management_create_hardware(
        tenant_a,
        hostname="tier-test",
        refresh_due_date=today - timedelta(days=1),
        vendor_eol_date=today + timedelta(days=400),
    )
    assert hw.refresh_priority == "overdue_critical"
    assert hw.refresh_priority_badge_class == "badge-red"
    assert hw.refresh_priority_display == "Overdue / EOL Expired"
    assert hw.is_eol_expired is False

    # Overdue via vendor_eol_date < today even when refresh_due_date is future
    hw.refresh_due_date = today + timedelta(days=500)
    hw.vendor_eol_date = today - timedelta(days=1)
    assert hw.is_eol_expired is True
    assert hw.refresh_priority == "overdue_critical"

    # Due within 90 days
    hw.vendor_eol_date = today + timedelta(days=400)
    hw.refresh_due_date = today + timedelta(days=90)
    assert hw.refresh_priority == "due_within_90d"
    assert hw.refresh_priority_badge_class == "badge-amber"

    # Planned within 12 months (91..365 days)
    hw.refresh_due_date = today + timedelta(days=91)
    assert hw.refresh_priority == "planned_fy"
    assert hw.refresh_priority_badge_class == "badge-info"

    # Healthy (> 365 days)
    hw.refresh_due_date = today + timedelta(days=366)
    assert hw.refresh_priority == "healthy"
    assert hw.refresh_priority_badge_class == "badge-green"

    # Healthy when no dates set
    hw.refresh_due_date = None
    hw.vendor_eol_date = None
    assert hw.refresh_priority == "healthy"

    # Locked statuses always report healthy even if EOL expired
    hw.vendor_eol_date = today - timedelta(days=30)
    for locked_status in ("sanitized_retired", "disposed"):
        hw.status = locked_status
        assert hw.is_locked is True
        assert hw.refresh_priority == "healthy"

    hw.status = "deployed"
    assert hw.is_locked is False

    # EOS approaching window: [today, today + 90d]
    hw.vendor_eos_date = None
    assert hw.is_eos_approaching is False
    hw.vendor_eos_date = today - timedelta(days=1)
    assert hw.is_eos_approaching is False
    hw.vendor_eos_date = today
    assert hw.is_eos_approaching is True
    hw.vendor_eos_date = today + timedelta(days=90)
    assert hw.is_eos_approaching is True
    hw.vendor_eos_date = today + timedelta(days=91)
    assert hw.is_eos_approaching is False


def test_it_asset_management_hardware_bounds_and_sanitization_validation(tenant_a):
    today = timezone.now().date()
    cycle_field = ItHardwareAsset._meta.get_field("refresh_cycle_months")
    cost_field = ItHardwareAsset._meta.get_field("estimated_refresh_cost")
    assert any(
        isinstance(v, MinValueValidator) and v.limit_value == 1 for v in cycle_field.validators
    )
    assert any(
        isinstance(v, MinValueValidator) and v.limit_value == Decimal("0.00")
        for v in cost_field.validators
    )

    hw = ItHardwareAsset(
        tenant=tenant_a,
        hostname="bad-hw",
        refresh_cycle_months=0,
        estimated_refresh_cost=Decimal("-1.00"),
        vendor_eos_date=today + timedelta(days=30),
        vendor_eol_date=today + timedelta(days=10),
        sanitization_required=True,
        sanitization_status="wiped_verified",
        sanitization_method="none",
    )
    with pytest.raises(ValidationError) as exc:
        hw.full_clean()
    assert "refresh_cycle_months" in exc.value.message_dict
    assert "estimated_refresh_cost" in exc.value.message_dict
    assert "vendor_eol_date" in exc.value.message_dict
    assert "sanitization_method" in exc.value.message_dict

    # certificate_on_file with method="none" when required also fails
    hw.refresh_cycle_months = 36
    hw.estimated_refresh_cost = Decimal("0.00")
    hw.vendor_eol_date = today + timedelta(days=60)
    hw.sanitization_status = "certificate_on_file"
    with pytest.raises(ValidationError) as exc_cert:
        hw.full_clean()
    assert "sanitization_method" in exc_cert.value.message_dict

    # Selecting a NIST SP 800-88 method passes
    hw.sanitization_method = "nist_purge"
    hw.full_clean()

    # When sanitization_required=False, method="none" is permitted
    hw.sanitization_required = False
    hw.sanitization_method = "none"
    hw.full_clean()


# =====================================================================
# 6. SoftwareLicense Model Tests
# =====================================================================


def test_it_asset_management_software_elp_properties_and_compliance_status(tenant_a):
    today = timezone.now().date()
    lic = _it_asset_management_create_license(
        tenant_a,
        entitled_quantity=100,
        allocated_quantity=95,
        active_used_quantity=80,
        reclaimable_inactive_count=0,
        unit_license_cost=Decimal("50.00"),
        renewal_date=today + timedelta(days=90),
        vendor_eol_date=today + timedelta(days=180),
        status="draft",
    )
    assert lic.compliance_delta == 5
    assert lic.is_under_licensed is False
    assert lic.utilization_pct == 80.0
    assert lic.estimated_true_up_cost == Decimal("0.00")
    assert lic.reclaim_savings_potential == Decimal("0.00")
    assert lic.is_eol_expired is False
    assert lic.is_locked is False
    assert lic.compute_compliance_status(today=today) == "active_compliant"

    # Surplus >= 15% (100 - 85 = 15) -> surplus_reclaimable
    lic.allocated_quantity = 85
    assert lic.compute_compliance_status(today=today) == "surplus_reclaimable"

    # Reclaimable inactive count > 0 -> surplus_reclaimable + savings calculation
    lic.allocated_quantity = 98
    lic.reclaimable_inactive_count = 6
    assert lic.reclaim_savings_potential == Decimal("300.00")
    assert lic.compute_compliance_status(today=today) == "surplus_reclaimable"

    # Over-allocated -> true_up_required + true-up cost
    lic.reclaimable_inactive_count = 0
    lic.allocated_quantity = 107
    assert lic.compliance_delta == -7
    assert lic.is_under_licensed is True
    assert lic.estimated_true_up_cost == Decimal("350.00")
    assert lic.compute_compliance_status(today=today) == "true_up_required"

    # Expired takes precedence over true_up_required when renewal_date < today
    lic.renewal_date = today - timedelta(days=1)
    lic.vendor_eol_date = today - timedelta(days=1)
    assert lic.is_eol_expired is True
    assert lic.compute_compliance_status(today=today) == "expired"

    # audit_hold & retired preserve status regardless of expiry/over-allocation
    lic.status = "audit_hold"
    assert lic.is_locked is False
    assert lic.compute_compliance_status(today=today) == "audit_hold"

    lic.status = "retired"
    assert lic.is_locked is True
    assert lic.compute_compliance_status(today=today) == "retired"

    # Zero-entitlement guard on utilization_pct
    lic.entitled_quantity = 0
    assert lic.utilization_pct == 0.0


def test_it_asset_management_software_key_ref_and_bounds_enforced_in_clean(tenant_a):
    today = timezone.now().date()
    lic = SoftwareLicense(
        tenant=tenant_a,
        software_name="Adobe Creative Cloud",
        publisher_name="Adobe",
        license_key_ref="  MS365-****-9X2K  ",
        entitled_quantity=10,
        allocated_quantity=8,
        reclaimable_inactive_count=2,
        unit_license_cost=Decimal("500.00"),
        total_annual_spend=Decimal("5000.00"),
        effective_date=today,
        renewal_date=today + timedelta(days=365),
    )
    lic.full_clean()
    assert lic.license_key_ref == "MS365-****-9X2K"

    lic.license_key_ref = "XXXX-XXXX-1234"
    lic.full_clean()

    for bad_key in (
        "X2345-67890-ABCDE-FGHIJ-KLMNO",
        "0123456789abcdef01234567",
        "AKIA1234567890ABCDEF",
        "sk_live_secret123",
        "ghp_token123",
    ):
        lic.license_key_ref = bad_key
        with pytest.raises(ValidationError) as exc_key:
            lic.clean()
        assert "license_key_ref" in exc_key.value.message_dict

    lic_bad = SoftwareLicense(
        tenant=tenant_a,
        software_name="Bad Bounds",
        publisher_name="Vendor",
        license_key_ref="ghp_invalid",
        entitled_quantity=0,
        allocated_quantity=2,
        reclaimable_inactive_count=5,
        unit_license_cost=Decimal("-10.00"),
        total_annual_spend=Decimal("-50.00"),
        effective_date=today,
        renewal_date=today - timedelta(days=5),
    )
    with pytest.raises(ValidationError) as exc_bounds:
        lic_bad.full_clean()
    for field_name in (
        "license_key_ref",
        "entitled_quantity",
        "reclaimable_inactive_count",
        "unit_license_cost",
        "total_annual_spend",
        "renewal_date",
    ):
        assert field_name in exc_bounds.value.message_dict


# =====================================================================
# 7. CloudAssetSubscription Model Tests
# =====================================================================


def test_it_asset_management_cloud_validators_tags_and_seat_bounds(tenant_a):
    mrc_field = CloudAssetSubscription._meta.get_field("monthly_recurring_cost")
    acv_field = CloudAssetSubscription._meta.get_field("annual_contract_value")
    assert any(
        isinstance(v, MinValueValidator) and v.limit_value == Decimal("0.00")
        for v in mrc_field.validators
    )
    assert any(
        isinstance(v, MinValueValidator) and v.limit_value == Decimal("0.00")
        for v in acv_field.validators
    )

    for invalid_tags in (["env", "prod"], "not-a-dict", 42):
        sub = CloudAssetSubscription(
            tenant=tenant_a,
            name="Invalid Tags Cloud",
            resource_tags=invalid_tags,
            monthly_recurring_cost=Decimal("-1.00"),
            annual_contract_value=Decimal("-10.00"),
            provisioned_seats=10,
            active_seats_30d=15,
        )
        with pytest.raises(ValidationError) as exc:
            sub.full_clean()
        assert "resource_tags" in exc.value.message_dict
        assert "monthly_recurring_cost" in exc.value.message_dict
        assert "annual_contract_value" in exc.value.message_dict
        assert "active_seats_30d" in exc.value.message_dict

    valid_sub = CloudAssetSubscription(
        tenant=tenant_a,
        name="Valid SaaS",
        resource_tags={"env": "prod", "cost_center": "CC-1", "owner": "sre"},
        monthly_recurring_cost=Decimal("0.00"),
        annual_contract_value=Decimal("0.00"),
        provisioned_seats=10,
        active_seats_30d=10,
    )
    valid_sub.full_clean()


def test_it_asset_management_cloud_operational_status_and_finops_properties(tenant_a):
    today = timezone.now().date()
    sub = _it_asset_management_create_cloud(
        tenant_a,
        monthly_recurring_cost=Decimal("1000.00"),
        provisioned_seats=40,
        active_seats_30d=30,
        resource_tags={"env": "prod", "cost_center": "CC-ENG", "owner": "devops"},
        renewal_date=today + timedelta(days=90),
        vendor_eol_date=today + timedelta(days=180),
        approval_status="sanctioned",
        sso_status="sso_enforced",
        status="active",
    )
    assert sub.seat_utilization_pct == 75.0
    assert sub.wasted_monthly_spend == Decimal("250.00")
    assert sub.has_required_tags is True
    assert sub.is_eol_expired is False
    assert sub.is_locked is False
    assert sub.compute_operational_status(today=today) == "active"

    # Underutilized (< 50% seat utilization)
    sub.active_seats_30d = 19
    assert sub.compute_operational_status(today=today) == "underutilized"

    # Expiring soon (renewal_date <= today + 30d) takes precedence over underutilized
    sub.renewal_date = today + timedelta(days=30)
    assert sub.compute_operational_status(today=today) == "expiring_soon"

    # Shadow IT flagged via approval_status or sso_status takes precedence over expiring_soon
    sub.approval_status = "shadow_it_flagged"
    assert sub.compute_operational_status(today=today) == "shadow_flagged"
    sub.approval_status = "under_review"
    sub.sso_status = "shadow_it_unapproved"
    assert sub.compute_operational_status(today=today) == "shadow_flagged"

    # Suspended and cancelled are preserved
    sub.status = "suspended"
    assert sub.is_locked is False
    assert sub.compute_operational_status(today=today) == "suspended"
    sub.status = "cancelled"
    assert sub.is_locked is True
    assert sub.compute_operational_status(today=today) == "cancelled"

    # Zero seats & missing required tags & EOL expired
    sub.provisioned_seats = 0
    sub.active_seats_30d = 0
    sub.resource_tags = {"env": "prod", "cost_center": "   ", "owner": "sre"}
    sub.vendor_eol_date = today - timedelta(days=1)
    assert sub.seat_utilization_pct is None
    assert sub.wasted_monthly_spend == Decimal("0.00")
    assert sub.has_required_tags is False
    assert sub.is_eol_expired is True


# =====================================================================
# 8. CmdbRelationship Model Tests
# =====================================================================


def test_it_asset_management_cmdb_ci_type_fk_alignment_all_five_types(
    tenant_a, it_hardware_a, software_license_a, cloud_subscription_a, operational_asset_a
):
    svc_a = _it_asset_management_create_service_component(tenant_a, name="Payments API")

    # Missing selected source and target FK fails
    empty_edge = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="service_component",
        target_ci_type="cloud_asset",
    )
    with pytest.raises(ValidationError) as exc_missing:
        empty_edge.clean()
    assert "source_service" in exc_missing.value.message_dict
    assert "target_cloud" in exc_missing.value.message_dict

    # Mismatched FK slot fails
    mismatched_edge = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="service_component",
        source_service=svc_a,
        source_hardware=it_hardware_a,
        target_ci_type="cloud_asset",
        target_cloud=cloud_subscription_a,
        target_software=software_license_a,
    )
    with pytest.raises(ValidationError) as exc_mismatch:
        mismatched_edge.clean()
    assert "source_hardware" in exc_mismatch.value.message_dict
    assert "target_software" in exc_mismatch.value.message_dict

    # Unsupported ci_type fails cleanly
    bad_type_edge = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="unknown_ci",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
    )
    with pytest.raises(ValidationError) as exc_type:
        bad_type_edge.clean()
    assert "source_ci_type" in exc_type.value.message_dict

    # All 5 CI types resolve source_ci / target_ci / keys / labels cleanly
    pairs = [
        ("service_component", {"source_service": svc_a}, "cloud_asset", {"target_cloud": cloud_subscription_a}),
        ("cloud_asset", {"source_cloud": cloud_subscription_a}, "it_hardware", {"target_hardware": it_hardware_a}),
        ("it_hardware", {"source_hardware": it_hardware_a}, "operational_asset", {"target_asset": operational_asset_a}),
        ("operational_asset", {"source_asset": operational_asset_a}, "software_license", {"target_software": software_license_a}),
    ]
    for src_type, src_kw, tgt_type, tgt_kw in pairs:
        edge = CmdbRelationship(
            tenant=tenant_a,
            source_ci_type=src_type,
            target_ci_type=tgt_type,
            relationship_type="depends_on",
            **src_kw,
            **tgt_kw,
        )
        edge.full_clean()
        assert edge.source_ci is not None
        assert edge.target_ci is not None
        assert edge.source_ci_key == (src_type, edge.source_ci.pk)
        assert edge.target_ci_key == (tgt_type, edge.target_ci.pk)
        assert edge.source_label == str(edge.source_ci)
        assert edge.target_label == str(edge.target_ci)

    unlinked = CmdbRelationship(tenant=tenant_a)
    assert unlinked.source_label == "Unlinked Source CI"
    assert unlinked.target_label == "Unlinked Target CI"


def test_it_asset_management_cmdb_self_edge_and_duplicate_active_guards(
    tenant_a, it_hardware_a, software_license_a, cmdb_relationship_a
):
    # Self-edge on same CI instance is forbidden
    self_edge = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="it_hardware",
        source_hardware=it_hardware_a,
        relationship_type="connects_to",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
    )
    with pytest.raises(ValidationError) as exc_self:
        self_edge.clean()
    assert "target_hardware" in exc_self.value.message_dict

    # Editing the existing active edge is allowed (excluded by pk)
    cmdb_relationship_a.blast_radius_notes = "Updated notes"
    cmdb_relationship_a.full_clean()

    # Second active edge with identical (tenant, source, relationship_type, target) is blocked
    dup_active = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="software_license",
        source_software=software_license_a,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
        status="active",
    )
    with pytest.raises(ValidationError) as exc_dup:
        dup_active.clean()
    assert "relationship_type" in exc_dup.value.message_dict

    # Distinct relationship_type on the exact same CI pair is allowed
    distinct_rel = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="software_license",
        source_software=software_license_a,
        relationship_type="licensed_by",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
        status="active",
    )
    distinct_rel.full_clean()

    # Historical deprecated duplicate is allowed while active exists
    deprecated_dup = _it_asset_management_create_cmdb(
        tenant_a,
        source_ci_type="software_license",
        source_software=software_license_a,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
        status="deprecated",
    )
    deprecated_dup.full_clean()

    # Locked status property check
    assert deprecated_dup.is_locked is False
    deprecated_dup.status = "severed"
    assert deprecated_dup.is_locked is True


# =====================================================================
# 9. Cross-Tenant FK Rejection & Multi-Error Accumulation (All 4 Models)
# =====================================================================


def test_it_asset_management_cross_tenant_fk_multi_error_accumulation(
    tenant_a,
    tenant_b,
    currency_usd,
    org_unit_b,
    location_b,
    vendor_party_b,
    operational_asset_b,
    expense_account_b,
    po_b,
    admin_b,
    it_hardware_b,
    software_license_b,
    cloud_subscription_b,
):
    # Global accounting.Currency must NEVER trigger cross-tenant errors on either tenant
    hw_global_curr = ItHardwareAsset(
        tenant=tenant_a,
        hostname="global-curr-hw",
        currency=currency_usd,
    )
    hw_global_curr.full_clean()

    # 1. ItHardwareAsset: accumulates multiple cross-tenant FK errors + field error in one clean()
    bad_hw = ItHardwareAsset(
        tenant=tenant_a,
        hostname="cross-hw",
        currency=currency_usd,
        org_unit=org_unit_b,
        location=location_b,
        vendor_party=vendor_party_b,
        custodian_party=vendor_party_b,
        operational_asset=operational_asset_b,
        owner=admin_b,
        sanitization_verified_by=admin_b,
        sanitization_required=True,
        sanitization_status="wiped_verified",
        sanitization_method="none",
    )
    with pytest.raises(ValidationError) as exc_hw:
        bad_hw.clean()
    for field_name in (
        "org_unit",
        "location",
        "vendor_party",
        "custodian_party",
        "operational_asset",
        "owner",
        "sanitization_verified_by",
        "sanitization_method",
    ):
        assert field_name in exc_hw.value.message_dict
    assert "currency" not in exc_hw.value.message_dict

    # 2. SoftwareLicense: accumulates multiple cross-tenant FK errors + license_key_ref error
    bad_sw = SoftwareLicense(
        tenant=tenant_a,
        software_name="Cross SW",
        publisher_name="Pub",
        currency=currency_usd,
        publisher_party=vendor_party_b,
        reseller_party=vendor_party_b,
        org_unit=org_unit_b,
        gl_expense_account=expense_account_b,
        purchase_order=po_b,
        license_owner=admin_b,
        license_key_ref="ghp_leakedsecret",
    )
    with pytest.raises(ValidationError) as exc_sw:
        bad_sw.clean()
    for field_name in (
        "publisher_party",
        "reseller_party",
        "org_unit",
        "gl_expense_account",
        "purchase_order",
        "license_owner",
        "license_key_ref",
    ):
        assert field_name in exc_sw.value.message_dict
    assert "currency" not in exc_sw.value.message_dict

    # 3. CloudAssetSubscription: accumulates multiple cross-tenant FK errors + resource_tags error
    bad_cl = CloudAssetSubscription(
        tenant=tenant_a,
        name="Cross Cloud",
        currency=currency_usd,
        org_unit=org_unit_b,
        vendor_party=vendor_party_b,
        gl_expense_account=expense_account_b,
        business_owner=admin_b,
        technical_owner=admin_b,
        resource_tags=["not-a-dict"],
    )
    with pytest.raises(ValidationError) as exc_cl:
        bad_cl.clean()
    for field_name in (
        "org_unit",
        "vendor_party",
        "gl_expense_account",
        "business_owner",
        "technical_owner",
        "resource_tags",
    ):
        assert field_name in exc_cl.value.message_dict
    assert "currency" not in exc_cl.value.message_dict

    # 4. CmdbRelationship: accumulates cross-tenant source/target/owner/verified_by FKs
    bad_cmdb = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="software_license",
        source_software=software_license_b,
        target_ci_type="it_hardware",
        target_hardware=it_hardware_b,
        owner=admin_b,
        verified_by=admin_b,
    )
    with pytest.raises(ValidationError) as exc_cmdb:
        bad_cmdb.clean()
    for field_name in ("source_software", "target_hardware", "owner", "verified_by"):
        assert field_name in exc_cmdb.value.message_dict

    # Also verify cross-tenant cloud & operational asset FKs in CmdbRelationship
    bad_cmdb2 = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="cloud_asset",
        source_cloud=cloud_subscription_b,
        target_ci_type="operational_asset",
        target_asset=operational_asset_b,
    )
    with pytest.raises(ValidationError) as exc_cmdb2:
        bad_cmdb2.clean()
    assert "source_cloud" in exc_cmdb2.value.message_dict
    assert "target_asset" in exc_cmdb2.value.message_dict
