"""
Unit tests for Module 11.18: IT Asset Management (ITAM) Forms & Helpers.
Covers ItHardwareAssetForm, SoftwareLicenseForm, CloudAssetSubscriptionForm,
CmdbRelationshipForm, _helpers.py (scope_tenant_querysets, normalize_json_dict_value,
validate_masked_key_ref), system/audit field exclusion, C4 NIST sanitization
admin-gating, I8 select_related / M11 queryset reuse query budgets, cross-tenant
reject_foreign rejection, negative/malformed input validation, and theme widgets.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

import apps.assets.forms as assets_forms
import apps.assets.forms.ItAssetManagement as itam_forms
from apps.accounting.models import Currency
from apps.assets.forms import (
    CloudAssetSubscriptionForm,
    CmdbRelationshipForm,
    ItHardwareAssetForm,
    SoftwareLicenseForm,
    reject_foreign,
)
from apps.assets.forms.ItAssetManagement import (
    CloudAssetSubscriptionForm as DirectCloudAssetSubscriptionForm,
    CmdbRelationshipForm as DirectCmdbRelationshipForm,
    ItHardwareAssetForm as DirectItHardwareAssetForm,
    SoftwareLicenseForm as DirectSoftwareLicenseForm,
)
from apps.assets.forms.ItAssetManagement._helpers import (
    normalize_json_dict_value,
    scope_tenant_querysets,
    validate_masked_key_ref,
)
from apps.assets.models import (
    AssetScrapSalvage,
    CloudAssetSubscription,
    CmdbRelationship,
    ItHardwareAsset,
    SoftwareLicense,
)
from apps.core.models import Party, ServiceComponent
from apps.hrm.models import EmployeeProfile
from apps.scm.models import PurchaseOrder

User = get_user_model()

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (Must start with _it_asset_management_*)
# =====================================================================


def _it_asset_management_base_hardware_payload(**overrides):
    data = {
        "hostname": "lon-prod-db01",
        "fqdn": "lon-prod-db01.acme.local",
        "device_class": "physical_server",
        "serial_number": "SN-9X420-DL380",
        "asset_tag_code": "IT-SRV-0142",
        "manufacturer": "Dell",
        "model_name": "PowerEdge R760",
        "environment": "production",
        "criticality": "high",
        "mdm_enrolled": True,
        "mdm_platform": "Microsoft Intune",
        "disk_encryption_status": "luks_encrypted",
        "refresh_cycle_months": "48",
        "estimated_refresh_cost": "4500.00",
        "sanitization_required": True,
        "sanitization_method": "none",
        "sanitization_status": "pending_wipe",
    }
    data.update(overrides)
    return data


def _it_asset_management_base_software_payload(**overrides):
    data = {
        "software_name": "Atlassian Jira Cloud",
        "publisher_name": "Atlassian",
        "product_sku": "JIRA-ENT-2026",
        "software_category": "devops_ide",
        "license_type": "subscription_term",
        "license_metric": "per_user",
        "license_key_ref": "JIRA-****-8M2P",
        "entitled_quantity": "50",
        "allocated_quantity": "40",
        "active_used_quantity": "35",
        "reclaimable_inactive_count": "5",
        "unit_license_cost": "120.00",
        "total_annual_spend": "6000.00",
    }
    data.update(overrides)
    return data


def _it_asset_management_base_cloud_payload(**overrides):
    data = {
        "name": "Datadog APM Enterprise",
        "asset_kind": "saas_application",
        "provider": "datadog",
        "external_account_id": "dd-org-acme-01",
        "cloud_region": "us-east-1",
        "environment": "production",
        "resource_tags": '{"env": "prod", "cost_center": "CC-ENG", "owner": "sre"}',
        "billing_cadence": "monthly",
        "commitment_term": "annual_contract",
        "monthly_recurring_cost": "1800.00",
        "annual_contract_value": "21600.00",
        "provisioned_seats": "30",
        "active_seats_30d": "25",
        "sso_status": "sso_enforced",
        "approval_status": "sanctioned",
        "cancellation_notice_days": "30",
        "auto_renew": True,
    }
    data.update(overrides)
    return data


def _it_asset_management_base_cmdb_payload(
    source_ci_type="service_component",
    target_ci_type="cloud_asset",
    relationship_type="depends_on",
    **overrides,
):
    data = {
        "source_ci_type": source_ci_type,
        "relationship_type": relationship_type,
        "target_ci_type": target_ci_type,
        "environment": "production",
        "criticality": "tier_2_business_important",
        "impact_severity": "degraded_performance",
        "is_single_point_of_failure": False,
        "blast_radius_notes": "Checkout service dependency edge.",
    }
    data.update(overrides)
    return data


def _it_asset_management_create_employee(tenant, name):
    party = Party.objects.create(tenant=tenant, name=name, kind="person")
    return EmployeeProfile.objects.create(tenant=tenant, party=party)


def _it_asset_management_create_service(tenant, name):
    return ServiceComponent.objects.create(
        tenant=tenant,
        name=name,
        kind="api",
        current_status="operational",
    )


# =====================================================================
# 1. Package Re-exports & Contract Registration
# =====================================================================


def test_it_asset_management_forms_package_reexports():
    expected = [
        "ItHardwareAssetForm",
        "SoftwareLicenseForm",
        "CloudAssetSubscriptionForm",
        "CmdbRelationshipForm",
    ]
    assert itam_forms.__all__ == expected
    assert ItHardwareAssetForm is DirectItHardwareAssetForm
    assert SoftwareLicenseForm is DirectSoftwareLicenseForm
    assert CloudAssetSubscriptionForm is DirectCloudAssetSubscriptionForm
    assert CmdbRelationshipForm is DirectCmdbRelationshipForm

    for symbol in expected:
        assert symbol in assets_forms.__all__
        assert getattr(assets_forms, symbol) is getattr(itam_forms, symbol)


# =====================================================================
# 2. System & Audit Field Exclusion Security Invariant
# =====================================================================


def test_it_asset_management_system_and_audit_fields_excluded(
    tenant_a, admin_user, member_user
):
    hw_admin_form = ItHardwareAssetForm(tenant=tenant_a, user=admin_user)
    hw_member_form = ItHardwareAssetForm(tenant=tenant_a, user=member_user)
    sw_form = SoftwareLicenseForm(tenant=tenant_a)
    cl_form = CloudAssetSubscriptionForm(tenant=tenant_a)
    cmdb_form = CmdbRelationshipForm(tenant=tenant_a)

    hw_forbidden = {
        "tenant",
        "number",
        "status",
        "last_seen_checkin",
        "sanitization_verified_by",
        "sanitized_at",
        "retired_at",
        "created_at",
        "updated_at",
    }
    assert hw_forbidden.isdisjoint(hw_admin_form.fields.keys())
    assert hw_forbidden.isdisjoint(hw_member_form.fields.keys())
    assert set(hw_admin_form.fields.keys()) == set(ItHardwareAssetForm.Meta.fields)
    assert set(hw_member_form.fields.keys()) == (
        set(ItHardwareAssetForm.Meta.fields)
        - set(ItHardwareAssetForm._SANITIZATION_ADMIN_FIELDS)
    )

    sw_forbidden = {
        "tenant",
        "number",
        "status",
        "last_reconciled_at",
        "retired_at",
        "created_at",
        "updated_at",
    }
    assert sw_forbidden.isdisjoint(sw_form.fields.keys())
    assert set(sw_form.fields.keys()) == set(SoftwareLicenseForm.Meta.fields)

    cl_forbidden = {
        "tenant",
        "number",
        "status",
        "last_finops_sync_at",
        "decommissioned_at",
        "created_at",
        "updated_at",
    }
    assert cl_forbidden.isdisjoint(cl_form.fields.keys())
    assert set(cl_form.fields.keys()) == set(CloudAssetSubscriptionForm.Meta.fields)

    cmdb_forbidden = {
        "tenant",
        "number",
        "status",
        "verified_on",
        "verified_by",
        "severed_at",
        "created_at",
        "updated_at",
    }
    assert cmdb_forbidden.isdisjoint(cmdb_form.fields.keys())
    assert set(cmdb_form.fields.keys()) == set(CmdbRelationshipForm.Meta.fields)


# =====================================================================
# 3. Tenant-Scoped FK Querysets & Global Currency Handling
# =====================================================================


def test_it_asset_management_scope_tenant_querysets_none_returns_empty(
    it_hardware_a, software_license_a, cloud_subscription_a
):
    for form_cls, extra_kwargs in (
        (ItHardwareAssetForm, {"user": None}),
        (SoftwareLicenseForm, {}),
        (CloudAssetSubscriptionForm, {}),
        (CmdbRelationshipForm, {}),
    ):
        form = form_cls(tenant=None, **extra_kwargs)
        for field_name in form_cls._TENANT_FIELDS:
            assert form.fields[field_name].queryset.count() == 0

    # Nonexistent field names in mapping are ignored safely
    hw_form = ItHardwareAssetForm(tenant=None, user=None)
    scope_tenant_querysets(hw_form, {"nonexistent_field": ItHardwareAsset})


def test_it_asset_management_hardware_form_fk_querysets_and_currency(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    currency_usd,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    asset_model_a,
    asset_model_b,
    category_root_a,
    category_root_b,
    warranty_a,
    warranty_b,
    requisition_a,
    requisition_b,
    analytics_rpl_a,
    analytics_rpl_b,
    disposal_request_a,
    disposal_request_b,
    scrap_salvage_a,
    scrap_salvage_b,
    org_unit_a,
    org_unit_b,
    location_a,
    location_b,
    vendor_party_a,
    vendor_party_b,
):
    emp_a = _it_asset_management_create_employee(tenant_a, "Alice Acme")
    emp_b = _it_asset_management_create_employee(tenant_b, "Bob Globex")
    inactive_curr, _ = Currency.objects.get_or_create(
        code="ZZZ",
        defaults={"name": "Inactive Currency", "symbol": "Z", "is_active": False},
    )
    if inactive_curr.is_active:
        inactive_curr.is_active = False
        inactive_curr.save(update_fields=["is_active"])

    form = ItHardwareAssetForm(tenant=tenant_a, user=admin_user)
    expected_pairs = {
        "operational_asset": (operational_asset_a, operational_asset_b),
        "fixed_asset": (fixed_asset_a, fixed_asset_b),
        "asset_model": (asset_model_a, asset_model_b),
        "asset_category": (category_root_a, category_root_b),
        "warranty": (warranty_a, warranty_b),
        "requisition": (requisition_a, requisition_b),
        "replacement_plan": (analytics_rpl_a, analytics_rpl_b),
        "disposal_request": (disposal_request_a, disposal_request_b),
        "scrap_salvage": (scrap_salvage_a, scrap_salvage_b),
        "org_unit": (org_unit_a, org_unit_b),
        "location": (location_a, location_b),
        "custodian_party": (vendor_party_a, vendor_party_b),
        "vendor_party": (vendor_party_a, vendor_party_b),
        "employee_profile": (emp_a, emp_b),
        "owner": (admin_user, admin_b),
    }
    for field_name, (obj_a, obj_b) in expected_pairs.items():
        pks = set(form.fields[field_name].queryset.values_list("pk", flat=True))
        assert obj_a.pk in pks
        assert obj_b.pk not in pks

    currency_pks = set(form.fields["currency"].queryset.values_list("pk", flat=True))
    assert currency_usd.pk in currency_pks
    assert inactive_curr.pk not in currency_pks


def test_it_asset_management_software_and_cloud_form_fk_querysets(
    tenant_a,
    admin_user,
    admin_b,
    currency_usd,
    vendor_party_a,
    vendor_party_b,
    org_unit_a,
    org_unit_b,
    expense_account_a,
    expense_account_b,
    po_a,
    po_b,
    service_contract_a,
    service_contract_b,
):
    inactive_curr, _ = Currency.objects.get_or_create(
        code="XIN",
        defaults={"name": "Inactive Test Currency", "symbol": "X", "is_active": False},
    )
    if inactive_curr.is_active:
        inactive_curr.is_active = False
        inactive_curr.save(update_fields=["is_active"])

    sw_form = SoftwareLicenseForm(tenant=tenant_a)
    sw_pairs = {
        "publisher_party": (vendor_party_a, vendor_party_b),
        "reseller_party": (vendor_party_a, vendor_party_b),
        "org_unit": (org_unit_a, org_unit_b),
        "gl_expense_account": (expense_account_a, expense_account_b),
        "purchase_order": (po_a, po_b),
        "service_contract": (service_contract_a, service_contract_b),
        "license_owner": (admin_user, admin_b),
    }
    for field_name, (obj_a, obj_b) in sw_pairs.items():
        pks = set(sw_form.fields[field_name].queryset.values_list("pk", flat=True))
        assert obj_a.pk in pks
        assert obj_b.pk not in pks

    sw_curr_pks = set(sw_form.fields["currency"].queryset.values_list("pk", flat=True))
    assert currency_usd.pk in sw_curr_pks
    assert inactive_curr.pk not in sw_curr_pks

    cl_form = CloudAssetSubscriptionForm(tenant=tenant_a)
    cl_pairs = {
        "org_unit": (org_unit_a, org_unit_b),
        "vendor_party": (vendor_party_a, vendor_party_b),
        "gl_expense_account": (expense_account_a, expense_account_b),
        "business_owner": (admin_user, admin_b),
        "technical_owner": (admin_user, admin_b),
    }
    for field_name, (obj_a, obj_b) in cl_pairs.items():
        pks = set(cl_form.fields[field_name].queryset.values_list("pk", flat=True))
        assert obj_a.pk in pks
        assert obj_b.pk not in pks

    cl_curr_pks = set(cl_form.fields["currency"].queryset.values_list("pk", flat=True))
    assert currency_usd.pk in cl_curr_pks
    assert inactive_curr.pk not in cl_curr_pks


def test_it_asset_management_cmdb_form_fk_querysets_and_shared_choices(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    it_hardware_a,
    it_hardware_b,
    software_license_a,
    software_license_b,
    cloud_subscription_a,
    cloud_subscription_b,
    operational_asset_a,
    operational_asset_b,
):
    svc_a = _it_asset_management_create_service(tenant_a, "Acme Auth API")
    svc_b = _it_asset_management_create_service(tenant_b, "Globex Auth API")

    form = CmdbRelationshipForm(tenant=tenant_a)
    ci_pairs = {
        "hardware": (it_hardware_a, it_hardware_b),
        "software": (software_license_a, software_license_b),
        "cloud": (cloud_subscription_a, cloud_subscription_b),
        "service": (svc_a, svc_b),
        "asset": (operational_asset_a, operational_asset_b),
    }
    for suffix, (obj_a, obj_b) in ci_pairs.items():
        for prefix in ("source", "target"):
            field = form.fields[f"{prefix}_{suffix}"]
            pks = set(field.queryset.values_list("pk", flat=True))
            assert obj_a.pk in pks
            assert obj_b.pk not in pks
            choice_values = {val for val, _ in field.widget.choices if val != ""}
            assert obj_a.pk in choice_values
            assert obj_b.pk not in choice_values

    owner_pks = set(form.fields["owner"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in owner_pks
    assert admin_b.pk not in owner_pks


# =====================================================================
# 4. Performance Regressions (I8 select_related & M11 queryset reuse)
# =====================================================================


def test_it_asset_management_i8_select_related_on_fk_dropdowns(
    django_assert_num_queries,
    tenant_a,
    admin_user,
    disposal_request_a,
    fixed_asset_a,
    operational_asset_a,
    vendor_party_a,
    scrap_salvage_a,
    po_a,
):
    # Add multiple rows to prove evaluation stays O(1) SQL query (no N+1)
    for idx in range(3):
        AssetScrapSalvage.objects.create(
            tenant=tenant_a,
            disposal_request=disposal_request_a,
            fixed_asset=fixed_asset_a,
            operational_asset=operational_asset_a,
            recycler_partner=vendor_party_a,
            supervisor=admin_user,
            scrap_method="shredding_recycling",
            status="scrap_transferred",
        )
        _it_asset_management_create_employee(tenant_a, f"Employee {idx}")
        PurchaseOrder.objects.create(
            tenant=tenant_a,
            number=f"PO-ITAM-{idx}",
            vendor=vendor_party_a,
            status="approved",
        )

    hw_form = ItHardwareAssetForm(tenant=tenant_a, user=admin_user)
    with django_assert_num_queries(1):
        salvage_labels = [str(obj) for obj in hw_form.fields["scrap_salvage"].queryset]
    assert len(salvage_labels) >= 4

    with django_assert_num_queries(1):
        emp_labels = [str(obj) for obj in hw_form.fields["employee_profile"].queryset]
    assert len(emp_labels) >= 3

    sw_form = SoftwareLicenseForm(tenant=tenant_a)
    with django_assert_num_queries(1):
        po_labels = [str(obj) for obj in sw_form.fields["purchase_order"].queryset]
    assert len(po_labels) >= 4


def test_it_asset_management_m11_cmdb_form_reuses_ci_querysets_without_duplicate_queries(
    django_assert_num_queries,
    django_assert_max_num_queries,
    tenant_a,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    operational_asset_a,
):
    _it_asset_management_create_service(tenant_a, "Billing API")

    # __init__ evaluates each of the 5 CI querysets once (5 queries total, not 10)
    with django_assert_max_num_queries(5):
        form = CmdbRelationshipForm(tenant=tenant_a)

    # Rendering all 10 source_* / target_* bound CI fields triggers zero extra DB queries
    with django_assert_num_queries(0):
        for suffix in ("hardware", "software", "cloud", "service", "asset"):
            src_field = form.fields[f"source_{suffix}"]
            tgt_field = form.fields[f"target_{suffix}"]
            assert src_field.widget.choices == tgt_field.widget.choices
            src_html = str(form[f"source_{suffix}"])
            tgt_html = str(form[f"target_{suffix}"])
            assert f"source_{suffix}" in src_html
            assert f"target_{suffix}" in tgt_html


# =====================================================================
# 5. C4 NIST Sanitization Admin-Gating Regression
# =====================================================================


def test_it_asset_management_c4_sanitization_fields_gated_by_admin_role(
    tenant_a, admin_user, member_user, it_hardware_a
):
    admin_fields = ItHardwareAssetForm._SANITIZATION_ADMIN_FIELDS

    # Non-admin (member_user) and unauthenticated/missing user (None) have fields popped
    for non_admin in (member_user, None):
        form = ItHardwareAssetForm(tenant=tenant_a, user=non_admin)
        for fname in admin_fields:
            assert fname not in form.fields

    # POST tampering by member_user on CREATE is ignored and defaults remain enforced
    tamper_create_data = _it_asset_management_base_hardware_payload(
        hostname="tamper-create-host",
        sanitization_required=False,
        sanitization_method="nist_purge",
        sanitization_status="certificate_on_file",
        sanitization_date="2026-06-01",
        sanitization_certificate_ref="FAKE-CERT-999",
    )
    member_create_form = ItHardwareAssetForm(
        data=tamper_create_data, tenant=tenant_a, user=member_user
    )
    assert member_create_form.is_valid(), member_create_form.errors
    created_hw = member_create_form.save()
    assert created_hw.sanitization_required is True
    assert created_hw.sanitization_method == "none"
    assert created_hw.sanitization_status == "pending_wipe"
    assert created_hw.sanitization_date is None
    assert created_hw.sanitization_certificate_ref == ""

    # POST tampering by member_user on EDIT preserves existing sanitization state
    tamper_edit_data = _it_asset_management_base_hardware_payload(
        hostname=it_hardware_a.hostname,
        sanitization_required=False,
        sanitization_method="crypto_erase",
        sanitization_status="wiped_verified",
        sanitization_date="2026-06-15",
        sanitization_certificate_ref="TAMPER-CERT",
    )
    member_edit_form = ItHardwareAssetForm(
        data=tamper_edit_data,
        instance=it_hardware_a,
        tenant=tenant_a,
        user=member_user,
    )
    assert member_edit_form.is_valid(), member_edit_form.errors
    edited_hw = member_edit_form.save()
    edited_hw.refresh_from_db()
    assert edited_hw.sanitization_required is True
    assert edited_hw.sanitization_method == "none"
    assert edited_hw.sanitization_status == "pending_wipe"
    assert edited_hw.sanitization_certificate_ref == ""

    # Tenant admin retains all sanitization fields and validates NIST rules
    admin_form = ItHardwareAssetForm(tenant=tenant_a, user=admin_user)
    for fname in admin_fields:
        assert fname in admin_form.fields

    # Superuser (even if is_tenant_admin=False) also retains sanitization fields
    superuser = User.objects.create_user(
        username="itam_super_check",
        email="super@acme.test",
        password="pw",
        tenant=tenant_a,
        is_superuser=True,
        is_tenant_admin=False,
    )
    super_form = ItHardwareAssetForm(tenant=tenant_a, user=superuser)
    for fname in admin_fields:
        assert fname in super_form.fields

    # Admin with wiped_verified + method="none" while required=True fails Model.clean()
    bad_admin_form = ItHardwareAssetForm(
        data=_it_asset_management_base_hardware_payload(
            hostname="bad-san-admin",
            sanitization_required=True,
            sanitization_status="wiped_verified",
            sanitization_method="none",
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_admin_form.is_valid()
    assert "sanitization_method" in bad_admin_form.errors

    # Admin with valid NIST SP 800-88 method + certificate saves cleanly
    good_admin_form = ItHardwareAssetForm(
        data=_it_asset_management_base_hardware_payload(
            hostname="good-san-admin",
            sanitization_required=True,
            sanitization_status="certificate_on_file",
            sanitization_method="nist_purge",
            sanitization_date="2026-06-20",
            sanitization_certificate_ref="CERT-NIST-2026-088",
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert good_admin_form.is_valid(), good_admin_form.errors
    saved_admin_hw = good_admin_form.save()
    assert saved_admin_hw.sanitization_status == "certificate_on_file"
    assert saved_admin_hw.sanitization_method == "nist_purge"
    assert saved_admin_hw.sanitization_certificate_ref == "CERT-NIST-2026-088"


# =====================================================================
# 6. Cross-Tenant FK Rejection (reject_foreign)
# =====================================================================


def test_it_asset_management_cross_tenant_fk_rejection_all_forms(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    currency_usd,
    vendor_party_b,
    org_unit_b,
    location_b,
    operational_asset_b,
    fixed_asset_b,
    asset_model_b,
    category_root_b,
    warranty_b,
    requisition_b,
    analytics_rpl_b,
    disposal_request_b,
    scrap_salvage_b,
    expense_account_b,
    po_b,
    service_contract_b,
    it_hardware_a,
    it_hardware_b,
    software_license_b,
    cloud_subscription_b,
):
    emp_b = _it_asset_management_create_employee(tenant_b, "Foreign Employee")
    svc_b = _it_asset_management_create_service(tenant_b, "Foreign Service")

    # 1. ItHardwareAssetForm rejects every tenant_b FK
    hw_foreign_fields = {
        "operational_asset": operational_asset_b.pk,
        "fixed_asset": fixed_asset_b.pk,
        "asset_model": asset_model_b.pk,
        "asset_category": category_root_b.pk,
        "warranty": warranty_b.pk,
        "requisition": requisition_b.pk,
        "replacement_plan": analytics_rpl_b.pk,
        "disposal_request": disposal_request_b.pk,
        "scrap_salvage": scrap_salvage_b.pk,
        "org_unit": org_unit_b.pk,
        "location": location_b.pk,
        "custodian_party": vendor_party_b.pk,
        "vendor_party": vendor_party_b.pk,
        "employee_profile": emp_b.pk,
        "owner": admin_b.pk,
    }
    for fk_name, foreign_pk in hw_foreign_fields.items():
        form = ItHardwareAssetForm(
            data=_it_asset_management_base_hardware_payload(**{fk_name: foreign_pk}),
            tenant=tenant_a,
            user=admin_user,
        )
        assert not form.is_valid()
        assert fk_name in form.errors

    # 2. SoftwareLicenseForm rejects every tenant_b FK
    sw_foreign_fields = {
        "publisher_party": vendor_party_b.pk,
        "reseller_party": vendor_party_b.pk,
        "org_unit": org_unit_b.pk,
        "gl_expense_account": expense_account_b.pk,
        "purchase_order": po_b.pk,
        "service_contract": service_contract_b.pk,
        "license_owner": admin_b.pk,
    }
    for fk_name, foreign_pk in sw_foreign_fields.items():
        form = SoftwareLicenseForm(
            data=_it_asset_management_base_software_payload(**{fk_name: foreign_pk}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert fk_name in form.errors

    # 3. CloudAssetSubscriptionForm rejects every tenant_b FK
    cl_foreign_fields = {
        "org_unit": org_unit_b.pk,
        "vendor_party": vendor_party_b.pk,
        "gl_expense_account": expense_account_b.pk,
        "business_owner": admin_b.pk,
        "technical_owner": admin_b.pk,
    }
    for fk_name, foreign_pk in cl_foreign_fields.items():
        form = CloudAssetSubscriptionForm(
            data=_it_asset_management_base_cloud_payload(**{fk_name: foreign_pk}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert fk_name in form.errors

    # 4. CmdbRelationshipForm rejects foreign source/target/owner FKs
    cmdb_cases = [
        ("it_hardware", "source_hardware", it_hardware_b.pk, "it_hardware", "target_hardware", it_hardware_a.pk),
        ("software_license", "source_software", software_license_b.pk, "it_hardware", "target_hardware", it_hardware_a.pk),
        ("cloud_asset", "source_cloud", cloud_subscription_b.pk, "it_hardware", "target_hardware", it_hardware_a.pk),
        ("service_component", "source_service", svc_b.pk, "it_hardware", "target_hardware", it_hardware_a.pk),
        ("operational_asset", "source_asset", operational_asset_b.pk, "it_hardware", "target_hardware", it_hardware_a.pk),
    ]
    for src_t, src_f, src_pk, tgt_t, tgt_f, tgt_pk in cmdb_cases:
        form = CmdbRelationshipForm(
            data=_it_asset_management_base_cmdb_payload(
                source_ci_type=src_t,
                target_ci_type=tgt_t,
                **{src_f: src_pk, tgt_f: tgt_pk},
            ),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert src_f in form.errors

    # Direct reject_foreign helper check verifies exact message & global currency immunity
    direct_form = ItHardwareAssetForm(
        data=_it_asset_management_base_hardware_payload(),
        tenant=tenant_a,
        user=admin_user,
    )
    assert direct_form.is_valid(), direct_form.errors
    cleaned = {"org_unit": org_unit_b, "currency": currency_usd}
    reject_foreign(direct_form, cleaned, ("org_unit",))
    assert "org_unit" in direct_form.errors
    assert "That record belongs to another workspace." in direct_form.errors["org_unit"]
    assert "currency" not in direct_form.errors


# =====================================================================
# 7. Domain Validations & Negative / Malformed Inputs
# =====================================================================


def test_it_asset_management_hardware_form_valid_and_negative_validations(
    tenant_a, admin_user, currency_usd, org_unit_a
):
    valid_form = ItHardwareAssetForm(
        data=_it_asset_management_base_hardware_payload(
            currency=currency_usd.pk,
            org_unit=org_unit_a.pk,
            vendor_eos_date="2028-01-01",
            vendor_eol_date="2029-01-01",
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert valid_form.is_valid(), valid_form.errors
    hw = valid_form.save()
    assert hw.tenant == tenant_a
    assert hw.number.startswith("ITHW-")
    assert hw.currency == currency_usd

    # Missing hostname, cycle < 1, negative cost, EOL < EOS all rejected cleanly
    invalid_form = ItHardwareAssetForm(
        data=_it_asset_management_base_hardware_payload(
            hostname="",
            refresh_cycle_months="0",
            estimated_refresh_cost="-10.50",
            vendor_eos_date="2028-06-01",
            vendor_eol_date="2028-05-01",
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not invalid_form.is_valid()
    for field_name in (
        "hostname",
        "refresh_cycle_months",
        "estimated_refresh_cost",
        "vendor_eol_date",
    ):
        assert field_name in invalid_form.errors


def test_it_asset_management_software_form_masked_keys_and_negative_validations(
    tenant_a, currency_usd, vendor_party_a
):
    today = date.today()
    # Valid masked key (with whitespace trimmed) & over-allocation permitted for true-up tracking
    valid_form = SoftwareLicenseForm(
        data=_it_asset_management_base_software_payload(
            license_key_ref="  MS365-****-9X2K  ",
            entitled_quantity="10",
            allocated_quantity="14",
            reclaimable_inactive_count="2",
            currency=currency_usd.pk,
            publisher_party=vendor_party_a.pk,
            effective_date=today.isoformat(),
            renewal_date=(today + timedelta(days=365)).isoformat(),
        ),
        tenant=tenant_a,
    )
    assert valid_form.is_valid(), valid_form.errors
    lic = valid_form.save()
    assert lic.tenant == tenant_a
    assert lic.license_key_ref == "MS365-****-9X2K"
    assert lic.is_under_licensed is True

    # M2 regression: unmasked raw keys/tokens rejected on license_key_ref
    for raw_key in (
        "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
        "X2345-67890-ABCDE-FGHIJ-KLMNO",
        "0123456789abcdef0123456789abcdef",
        "AKIAIOSFODNN7EXAMPLE",
        "sk_live_secret123",
        "ghp_token12345",
    ):
        bad_key_form = SoftwareLicenseForm(
            data=_it_asset_management_base_software_payload(license_key_ref=raw_key),
            tenant=tenant_a,
        )
        assert not bad_key_form.is_valid()
        assert "license_key_ref" in bad_key_form.errors

    # Negative cost, entitled < 1, reclaimable > allocated, renewal < effective, missing required
    bad_bounds_form = SoftwareLicenseForm(
        data=_it_asset_management_base_software_payload(
            software_name="",
            publisher_name="",
            entitled_quantity="0",
            allocated_quantity="5",
            reclaimable_inactive_count="6",
            unit_license_cost="-1.00",
            total_annual_spend="-5.00",
            effective_date="2026-06-01",
            renewal_date="2026-05-01",
        ),
        tenant=tenant_a,
    )
    assert not bad_bounds_form.is_valid()
    for field_name in (
        "software_name",
        "publisher_name",
        "entitled_quantity",
        "reclaimable_inactive_count",
        "unit_license_cost",
        "total_annual_spend",
        "renewal_date",
    ):
        assert field_name in bad_bounds_form.errors


def test_it_asset_management_cloud_form_json_tags_and_negative_validations(
    tenant_a, currency_usd, vendor_party_a
):
    # Direct helper checks
    assert normalize_json_dict_value(None) == {}
    assert normalize_json_dict_value("") == {}
    assert normalize_json_dict_value({"env": "prod"}) == {"env": "prod"}
    for non_dict in (["env"], "prod", 42, True):
        with pytest.raises(ValidationError):
            normalize_json_dict_value(non_dict)

    # Blank resource_tags normalizes to {}
    blank_tags_form = CloudAssetSubscriptionForm(
        data=_it_asset_management_base_cloud_payload(
            name="Blank Tags SaaS",
            resource_tags="",
            currency=currency_usd.pk,
            vendor_party=vendor_party_a.pk,
        ),
        tenant=tenant_a,
    )
    assert blank_tags_form.is_valid(), blank_tags_form.errors
    saved_blank = blank_tags_form.save()
    assert saved_blank.resource_tags == {}

    # Valid JSON object parses cleanly
    valid_tags_form = CloudAssetSubscriptionForm(
        data=_it_asset_management_base_cloud_payload(
            name="Tagged SaaS",
            resource_tags='{"env": "prod", "cost_center": "CC-ENG", "owner": "sre"}',
        ),
        tenant=tenant_a,
    )
    assert valid_tags_form.is_valid(), valid_tags_form.errors
    saved_tagged = valid_tags_form.save()
    assert saved_tagged.resource_tags == {
        "env": "prod",
        "cost_center": "CC-ENG",
        "owner": "sre",
    }
    assert saved_tagged.has_required_tags is True

    # JSON array, scalar, string, and malformed JSON rejected cleanly
    for bad_tags in ('["a", "b"]', "42", '"just-a-string"', "{not valid json"):
        bad_json_form = CloudAssetSubscriptionForm(
            data=_it_asset_management_base_cloud_payload(resource_tags=bad_tags),
            tenant=tenant_a,
        )
        assert not bad_json_form.is_valid()
        assert "resource_tags" in bad_json_form.errors

    # Negative costs, negative seats/notice days, and active_seats_30d > provisioned_seats
    bad_bounds_form = CloudAssetSubscriptionForm(
        data=_it_asset_management_base_cloud_payload(
            name="",
            monthly_recurring_cost="-10.00",
            annual_contract_value="-120.00",
            provisioned_seats="10",
            active_seats_30d="15",
            cancellation_notice_days="-5",
        ),
        tenant=tenant_a,
    )
    assert not bad_bounds_form.is_valid()
    for field_name in (
        "name",
        "monthly_recurring_cost",
        "annual_contract_value",
        "active_seats_30d",
        "cancellation_notice_days",
    ):
        assert field_name in bad_bounds_form.errors


def test_it_asset_management_cmdb_form_slot_normalization_self_loop_and_duplicate_edge(
    tenant_a,
    it_hardware_a,
    software_license_a,
    cloud_subscription_a,
    cmdb_relationship_a,
):
    svc_a = _it_asset_management_create_service(tenant_a, "Orders API")

    # Missing selected source & target CI slot fails
    missing_form = CmdbRelationshipForm(
        data=_it_asset_management_base_cmdb_payload(
            source_ci_type="service_component",
            target_ci_type="cloud_asset",
        ),
        tenant=tenant_a,
    )
    assert not missing_form.is_valid()
    assert "source_service" in missing_form.errors
    assert "target_cloud" in missing_form.errors

    # Inactive CI slots are cleared automatically by _normalize_side()
    normalized_form = CmdbRelationshipForm(
        data=_it_asset_management_base_cmdb_payload(
            source_ci_type="service_component",
            source_service=svc_a.pk,
            source_hardware=it_hardware_a.pk,
            target_ci_type="cloud_asset",
            target_cloud=cloud_subscription_a.pk,
            target_software=software_license_a.pk,
        ),
        tenant=tenant_a,
    )
    assert normalized_form.is_valid(), normalized_form.errors
    edge = normalized_form.save()
    assert edge.source_service == svc_a
    assert edge.source_hardware is None
    assert edge.target_cloud == cloud_subscription_a
    assert edge.target_software is None

    # Self-loop rejected cleanly
    self_loop_form = CmdbRelationshipForm(
        data=_it_asset_management_base_cmdb_payload(
            source_ci_type="it_hardware",
            source_hardware=it_hardware_a.pk,
            target_ci_type="it_hardware",
            target_hardware=it_hardware_a.pk,
            relationship_type="connects_to",
        ),
        tenant=tenant_a,
    )
    assert not self_loop_form.is_valid()
    assert "target_hardware" in self_loop_form.errors

    # Duplicate active edge rejected cleanly (matches cmdb_relationship_a)
    dup_form = CmdbRelationshipForm(
        data=_it_asset_management_base_cmdb_payload(
            source_ci_type="software_license",
            source_software=software_license_a.pk,
            relationship_type="runs_on",
            target_ci_type="it_hardware",
            target_hardware=it_hardware_a.pk,
        ),
        tenant=tenant_a,
    )
    assert not dup_form.is_valid()
    assert "relationship_type" in dup_form.errors

    # Editing existing active edge does NOT falsely collide with itself
    edit_form = CmdbRelationshipForm(
        data=_it_asset_management_base_cmdb_payload(
            source_ci_type="software_license",
            source_software=software_license_a.pk,
            relationship_type="runs_on",
            target_ci_type="it_hardware",
            target_hardware=it_hardware_a.pk,
            blast_radius_notes="Updated blast radius note.",
        ),
        instance=cmdb_relationship_a,
        tenant=tenant_a,
    )
    assert edit_form.is_valid(), edit_form.errors
    updated_edge = edit_form.save()
    assert updated_edge.blast_radius_notes == "Updated blast radius note."


# =====================================================================
# 8. Tailwind / Theme Widget Styling & Rendering
# =====================================================================


def test_it_asset_management_form_widget_classes_and_clean_rendering(
    tenant_a, admin_user
):
    hw_form = ItHardwareAssetForm(tenant=tenant_a, user=admin_user)
    assert "form-input" in hw_form.fields["hostname"].widget.attrs.get("class", "")
    assert "form-select" in hw_form.fields["device_class"].widget.attrs.get("class", "")
    assert "form-textarea" in hw_form.fields["notes"].widget.attrs.get("class", "")
    assert "form-check" in hw_form.fields["mdm_enrolled"].widget.attrs.get("class", "")
    assert hw_form.fields["commissioned_date"].widget.input_type == "date"
    assert hw_form.fields["sanitization_date"].widget.input_type == "date"

    sw_form = SoftwareLicenseForm(tenant=tenant_a)
    assert "form-input" in sw_form.fields["software_name"].widget.attrs.get("class", "")
    assert "form-select" in sw_form.fields["software_category"].widget.attrs.get("class", "")
    assert "form-check" in sw_form.fields["auto_renew"].widget.attrs.get("class", "")
    assert sw_form.fields["renewal_date"].widget.input_type == "date"

    cl_form = CloudAssetSubscriptionForm(tenant=tenant_a)
    assert "form-input" in cl_form.fields["name"].widget.attrs.get("class", "")
    assert "form-textarea" in cl_form.fields["resource_tags"].widget.attrs.get("class", "")
    assert cl_form.fields["renewal_date"].widget.input_type == "date"

    cmdb_form = CmdbRelationshipForm(tenant=tenant_a)
    assert "form-select" in cmdb_form.fields["source_ci_type"].widget.attrs.get("class", "")
    assert "form-textarea" in cmdb_form.fields["blast_radius_notes"].widget.attrs.get("class", "")
    assert "form-check" in cmdb_form.fields["is_single_point_of_failure"].widget.attrs.get("class", "")

    for form in (hw_form, sw_form, cl_form, cmdb_form):
        rendered = form.as_p()
        assert "<input" in rendered or "<select" in rendered
