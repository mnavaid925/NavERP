"""Unit tests for Sub-module 10.6 Master Data Management (MDM) forms.

Forms covered:
- MdmGoldenRecordForm
- MdmGoldenRecordMergeForm
- MdmSurvivorshipRuleForm
- MdmHierarchyNodeForm
- MdmReferenceCodeForm
"""
from decimal import Decimal
import json

import pytest
from django.contrib.auth import get_user_model

from apps.bi.forms import (
    MdmGoldenRecordForm,
    MdmGoldenRecordMergeForm,
    MdmHierarchyNodeForm,
    MdmReferenceCodeForm,
    MdmSurvivorshipRuleForm,
)
from apps.bi.models import (
    MdmGoldenRecord,
    MdmHierarchyNode,
    MdmReferenceCode,
    MdmSurvivorshipRule,
    WarehouseTable,
)
from apps.core.models import OrgUnit, Party, PartyRole
from apps.scm.models.AssetManagement.Assets import Asset
from apps.scm.models.InventoryManagement.Items import Item, ItemCategory


User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (must be prefixed with _masterdata_*)
# ---------------------------------------------------------------------------


def _masterdata_create_party(tenant, name="Test Party", kind="organization"):
    """Helper to create a tenant-scoped Party."""
    return Party.objects.create(tenant=tenant, name=name, kind=kind)


def _masterdata_create_party_role(tenant, party, role="customer"):
    """Helper to create a tenant-scoped PartyRole."""
    return PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")


def _masterdata_create_item(tenant, sku="TEST-SKU-001", name="Test Item"):
    """Helper to create a tenant-scoped SCM Item."""
    return Item.objects.create(tenant=tenant, sku=sku, name=name)


def _masterdata_create_asset(tenant, code="AST-TEST-001", name="Test Plant Asset"):
    """Helper to create a tenant-scoped SCM Asset."""
    return Asset.objects.create(tenant=tenant, code=code, name=name)


def _masterdata_create_org_unit(tenant, name="Business Intelligence Ops"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _masterdata_create_item_category(tenant, name="Enterprise Components"):
    """Helper to create a tenant-scoped ItemCategory."""
    return ItemCategory.objects.create(tenant=tenant, name=name)


def _masterdata_create_user(tenant, username, is_active=True):
    """Helper to create a tenant-scoped User."""
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_active=is_active,
    )


def _masterdata_base_golden_record_data(**overrides):
    """Helper returning a valid payload dictionary for MdmGoldenRecordForm."""
    data = {
        "name": "Acme Global Solutions Inc",
        "code": "acme_global_solutions",
        "domain": "customer",
        "status": "approved",
        "trust_tier": "gold",
        "confidence_score": "98.50",
        "tax_id": "US-987654321",
        "primary_email": "masterdata@acme.example.com",
        "primary_phone": "+1-555-0199",
        "primary_address": "100 Enterprise Blvd, Suite 500, Austin, TX",
        "stewardship_notes": "Cleaned and verified through automated Dun & Bradstreet feed.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _masterdata_base_survivorship_rule_data(**overrides):
    """Helper returning a valid payload dictionary for MdmSurvivorshipRuleForm."""
    data = {
        "name": "Customer Legal Name Source Trust Precedence",
        "code": "cust_legal_name_trust",
        "domain": "customer",
        "target_field": "name",
        "survivorship_strategy": "source_priority",
        "match_algorithm": "exact",
        "match_threshold_pct": "80.00",
        "auto_merge_threshold_pct": "95.00",
        "source_priority_list_text": '["SAP_ERP", "SALESFORCE_CRM", "BILLING_CORE"]',
        "priority_order": 10,
        "description": "Rules determining field precedence for legal entity names.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _masterdata_base_hierarchy_node_data(**overrides):
    """Helper returning a valid payload dictionary for MdmHierarchyNodeForm."""
    data = {
        "name": "North American Commercial Group",
        "code": "na_commercial_group",
        "hierarchy_type": "corporate_legal",
        "relationship_kind": "subsidiary",
        "sort_order": 10,
        "description": "Commercial operating entities across North America.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _masterdata_base_reference_code_data(**overrides):
    """Helper returning a valid payload dictionary for MdmReferenceCodeForm."""
    data = {
        "code_set": "ISO-3166-COUNTRY",
        "canonical_code": "CAN",
        "canonical_name": "Canada",
        "source_system": "legacy_sap",
        "source_code": "CA",
        "category": "North America",
        "status": "active",
        "attributes_text": '{"iso_numeric": "124", "alpha_2": "CA", "currency": "CAD"}',
        "description": "Official ISO-3166-1 3-letter country code for Canada.",
        "is_active": True,
    }
    data.update(overrides)
    return data


# ===========================================================================
# 1. System Field Exclusions Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_golden_record_form_system_field_exclusions():
    """Verify system fields (tenant, number, merged_at, reviewed_at, etc.) are excluded from MdmGoldenRecordForm."""
    excluded_fields = [
        "tenant",
        "number",
        "merged_at",
        "reviewed_at",
        "reviewed_by",
        "merged_into_record",
        "source_record_count",
        "source_crosswalks_json",
        "golden_attributes_json",
    ]
    for field in excluded_fields:
        assert field not in MdmGoldenRecordForm.base_fields, f"System field '{field}' must be excluded from form."


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_system_field_exclusions():
    """Verify system fields (tenant, number, source_priority_list_json) are excluded from MdmSurvivorshipRuleForm."""
    excluded_fields = [
        "tenant",
        "number",
        "source_priority_list_json",  # handled via custom source_priority_list_text field
    ]
    for field in excluded_fields:
        assert field not in MdmSurvivorshipRuleForm.base_fields, f"System field '{field}' must be excluded from form."


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_system_field_exclusions():
    """Verify system fields (tenant, number, level, path) are excluded from MdmHierarchyNodeForm."""
    excluded_fields = [
        "tenant",
        "number",
        "level",
        "path",
    ]
    for field in excluded_fields:
        assert field not in MdmHierarchyNodeForm.base_fields, f"System field '{field}' must be excluded from form."


@pytest.mark.django_db
def test_masterdata_reference_code_form_system_field_exclusions():
    """Verify system fields (tenant, number, attributes_json) are excluded from MdmReferenceCodeForm."""
    excluded_fields = [
        "tenant",
        "number",
        "attributes_json",  # handled via custom attributes_text field
    ]
    for field in excluded_fields:
        assert field not in MdmReferenceCodeForm.base_fields, f"System field '{field}' must be excluded from form."


# ===========================================================================
# 2. MdmGoldenRecordForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_golden_record_form_valid_basic(tenant_a):
    """Test valid MdmGoldenRecordForm creation with basic attributes and tenant binding."""
    data = _masterdata_base_golden_record_data()
    form = MdmGoldenRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.name == "Acme Global Solutions Inc"
    assert instance.code == "acme_global_solutions"
    assert instance.domain == "customer"
    assert instance.status == "approved"
    assert instance.trust_tier == "gold"
    assert instance.confidence_score == Decimal("98.50")
    assert instance.number.startswith("BMGR-")


@pytest.mark.django_db
def test_masterdata_golden_record_form_valid_with_all_fks(tenant_a, admin_user, warehouse_table_a):
    """Test valid MdmGoldenRecordForm submission with all related master FKs populated."""
    party = _masterdata_create_party(tenant_a, name="Acme Aerospace Division")
    party_role = _masterdata_create_party_role(tenant_a, party=party, role="customer")
    item = _masterdata_create_item(tenant_a, sku="AERO-001", name="Turbine Component")
    asset = _masterdata_create_asset(tenant_a, code="AST-TURB-01", name="Turbine Test Stand")

    data = _masterdata_base_golden_record_data(
        name="Acme Aerospace Master Record",
        code="acme_aerospace_master",
        party=party.pk,
        party_role=party_role.pk,
        item=item.pk,
        asset=asset.pk,
        warehouse_table=warehouse_table_a.pk,
        assigned_steward=admin_user.pk,
    )
    form = MdmGoldenRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    record = form.save()
    assert record.party == party
    assert record.party_role == party_role
    assert record.item == item
    assert record.asset == asset
    assert record.warehouse_table == warehouse_table_a
    assert record.assigned_steward == admin_user


@pytest.mark.django_db
def test_masterdata_golden_record_form_status_merged_excluded_from_choices(tenant_a):
    """Verify status='merged' is strictly excluded from available form status choices."""
    form = MdmGoldenRecordForm(tenant=tenant_a)
    available_choice_keys = [c[0] for c in form.fields["status"].choices]
    assert "merged" not in available_choice_keys
    # Verify standard active choices remain present
    assert "approved" in available_choice_keys
    assert "pending_review" in available_choice_keys
    assert "draft" in available_choice_keys


@pytest.mark.django_db
def test_masterdata_golden_record_form_status_merged_rejected_on_submission(tenant_a):
    """Verify submitting status='merged' fails validation to prevent manual unassisted merge assignment."""
    data = _masterdata_base_golden_record_data(status="merged")
    form = MdmGoldenRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "status" in form.errors
    assert any("valid choice" in err.lower() for err in form.errors["status"])


@pytest.mark.django_db
def test_masterdata_golden_record_form_tenant_queryset_isolation(
    tenant_a,
    tenant_b,
    admin_user,
    admin_user_b,
    warehouse_table_a,
    warehouse_table_b,
):
    """Verify party, item, asset, warehouse_table, and steward querysets strictly filter by tenant."""
    party_a = _masterdata_create_party(tenant_a, name="Acme Entity")
    party_b = _masterdata_create_party(tenant_b, name="Globex Entity")

    item_a = _masterdata_create_item(tenant_a, sku="SKU-A", name="Acme Item")
    item_b = _masterdata_create_item(tenant_b, sku="SKU-B", name="Globex Item")

    asset_a = _masterdata_create_asset(tenant_a, code="AST-A", name="Acme Asset")
    asset_b = _masterdata_create_asset(tenant_b, code="AST-B", name="Globex Asset")

    role_a = _masterdata_create_party_role(tenant_a, party=party_a, role="customer")
    role_b = _masterdata_create_party_role(tenant_b, party=party_b, role="customer")

    form = MdmGoldenRecordForm(tenant=tenant_a)

    # Party queryset
    party_qs = form.fields["party"].queryset
    assert party_a in party_qs
    assert party_b not in party_qs

    # PartyRole queryset
    role_qs = form.fields["party_role"].queryset
    assert role_a in role_qs
    assert role_b not in role_qs

    # Item queryset
    item_qs = form.fields["item"].queryset
    assert item_a in item_qs
    assert item_b not in item_qs

    # Asset queryset
    asset_qs = form.fields["asset"].queryset
    assert asset_a in asset_qs
    assert asset_b not in asset_qs

    # WarehouseTable queryset
    table_qs = form.fields["warehouse_table"].queryset
    assert warehouse_table_a in table_qs
    assert warehouse_table_b not in table_qs

    # Assigned Steward queryset
    steward_qs = form.fields["assigned_steward"].queryset
    assert admin_user in steward_qs
    assert admin_user_b not in steward_qs


@pytest.mark.django_db
def test_masterdata_golden_record_form_steward_inactive_user_handling(tenant_a):
    """Verify inactive users are excluded from steward queryset unless editing a record already assigned to them."""
    active_user = _masterdata_create_user(tenant_a, username="active_steward", is_active=True)
    inactive_user = _masterdata_create_user(tenant_a, username="inactive_steward", is_active=False)

    # New record form: inactive user excluded
    new_form = MdmGoldenRecordForm(tenant=tenant_a)
    assert active_user in new_form.fields["assigned_steward"].queryset
    assert inactive_user not in new_form.fields["assigned_steward"].queryset

    # Editing record assigned to inactive user: inactive user included
    existing_record = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        name="Legacy Custody Record",
        code="legacy_custody_rec",
        domain="customer",
        assigned_steward=inactive_user,
    )
    edit_form = MdmGoldenRecordForm(instance=existing_record, tenant=tenant_a)
    assert inactive_user in edit_form.fields["assigned_steward"].queryset


@pytest.mark.django_db
def test_masterdata_golden_record_form_cross_tenant_fk_rejection(
    tenant_a,
    tenant_b,
    admin_user_b,
    warehouse_table_b,
):
    """Verify reject_foreign prevents cross-tenant FK injection if queryset was bypassed."""
    foreign_party = _masterdata_create_party(tenant_b, name="Foreign Party")
    foreign_item = _masterdata_create_item(tenant_b, sku="FOR-01", name="Foreign Item")
    foreign_asset = _masterdata_create_asset(tenant_b, code="AST-FOR-01", name="Foreign Asset")
    foreign_role = _masterdata_create_party_role(tenant_b, party=foreign_party, role="vendor")

    data = _masterdata_base_golden_record_data(
        party=foreign_party.pk,
        party_role=foreign_role.pk,
        item=foreign_item.pk,
        asset=foreign_asset.pk,
        warehouse_table=warehouse_table_b.pk,
        assigned_steward=admin_user_b.pk,
    )
    form = MdmGoldenRecordForm(data=data, tenant=tenant_a)

    # Broaden querysets to test reject_foreign defense-in-depth
    form.fields["party"].queryset = Party.objects.all()
    form.fields["party_role"].queryset = PartyRole.objects.all()
    form.fields["item"].queryset = Item.objects.all()
    form.fields["asset"].queryset = Asset.objects.all()
    form.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    form.fields["assigned_steward"].queryset = User.objects.all()

    assert form.is_valid() is False
    assert "That record belongs to another workspace." in form.errors["party"]
    assert "That record belongs to another workspace." in form.errors["party_role"]
    assert "That record belongs to another workspace." in form.errors["item"]
    assert "That record belongs to another workspace." in form.errors["asset"]
    assert "That record belongs to another workspace." in form.errors["warehouse_table"]
    assert "That record belongs to another workspace." in form.errors["assigned_steward"]


@pytest.mark.django_db
def test_masterdata_golden_record_form_duplicate_code_same_domain_rejected(
    tenant_a,
    mdm_golden_record_a,
):
    """Verify unique constraint (tenant, domain, code) is validated by TenantUniqueMixin."""
    data = _masterdata_base_golden_record_data(
        name="Duplicate Acme Code",
        code=mdm_golden_record_a.code,
        domain=mdm_golden_record_a.domain,
    )
    form = MdmGoldenRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    # Check that error is registered on code or non_field_errors
    all_errors = str(form.errors)
    assert "code" in form.errors or "already exists" in all_errors.lower()


@pytest.mark.django_db
def test_masterdata_golden_record_form_duplicate_code_different_domain_allowed(
    tenant_a,
    mdm_golden_record_a,
):
    """Verify same code under a different domain (e.g. vendor vs customer) is accepted."""
    data = _masterdata_base_golden_record_data(
        name="Vendor with same slug",
        code=mdm_golden_record_a.code,
        domain="vendor",  # primary is 'customer'
    )
    form = MdmGoldenRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    record = form.save()
    assert record.domain == "vendor"
    assert record.code == mdm_golden_record_a.code


@pytest.mark.django_db
def test_masterdata_golden_record_form_confidence_score_bounds(tenant_a):
    """Verify confidence_score is bounded between 0.00 and 100.00."""
    # Score > 100
    form_high = MdmGoldenRecordForm(
        data=_masterdata_base_golden_record_data(confidence_score="105.00"),
        tenant=tenant_a,
    )
    assert form_high.is_valid() is False
    assert "confidence_score" in form_high.errors

    # Score < 0
    form_low = MdmGoldenRecordForm(
        data=_masterdata_base_golden_record_data(confidence_score="-5.00"),
        tenant=tenant_a,
    )
    assert form_low.is_valid() is False
    assert "confidence_score" in form_low.errors

    # Edge cases 0.00 and 100.00
    form_zero = MdmGoldenRecordForm(
        data=_masterdata_base_golden_record_data(code="edge_score_zero", confidence_score="0.00"),
        tenant=tenant_a,
    )
    assert form_zero.is_valid()

    form_hundred = MdmGoldenRecordForm(
        data=_masterdata_base_golden_record_data(code="edge_score_hundred", confidence_score="100.00"),
        tenant=tenant_a,
    )
    assert form_hundred.is_valid()


@pytest.mark.django_db
def test_masterdata_golden_record_form_edit_existing_instance(tenant_a, mdm_golden_record_a):
    """Verify updating an existing golden record instance preserves tenant and number while applying changes."""
    data = _masterdata_base_golden_record_data(
        name="Acme Prime Corp Updated Name",
        code=mdm_golden_record_a.code,
        confidence_score="99.99",
        tax_id="US-NEWTAXID",
    )
    form = MdmGoldenRecordForm(instance=mdm_golden_record_a, data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    updated = form.save()
    assert updated.pk == mdm_golden_record_a.pk
    assert updated.number == mdm_golden_record_a.number
    assert updated.tenant == tenant_a
    assert updated.name == "Acme Prime Corp Updated Name"
    assert updated.confidence_score == Decimal("99.99")
    assert updated.tax_id == "US-NEWTAXID"


@pytest.mark.django_db
def test_masterdata_golden_record_form_missing_required_fields(tenant_a):
    """Verify missing required fields (name) raise validation errors."""
    data = _masterdata_base_golden_record_data(name="")
    form = MdmGoldenRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "name" in form.errors


# ===========================================================================
# 3. MdmGoldenRecordMergeForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_merge_form_clean_signature(tenant_a, mdm_golden_record_a):
    """Verify MdmGoldenRecordMergeForm accepts clean keyword arguments (tenant, primary_record)."""
    form = MdmGoldenRecordMergeForm(tenant=tenant_a, primary_record=mdm_golden_record_a)
    assert form.fields["secondary_record"].queryset is not None


@pytest.mark.django_db
def test_masterdata_merge_form_candidate_queryset_filtering(
    tenant_a,
    tenant_b,
    mdm_golden_record_a,
    mdm_golden_record_secondary_a,
    mdm_golden_record_b,
):
    """Verify merge candidate queryset excludes primary record, already merged records, different domains, and foreign tenants."""
    # 1. Same tenant, same domain, not merged -> should be IN candidate queryset
    valid_candidate = mdm_golden_record_secondary_a

    # 2. Same tenant, same domain, but ALREADY merged -> should be EXCLUDED
    merged_candidate = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        name="Already Merged Corp",
        code="already_merged_corp",
        domain=mdm_golden_record_a.domain,
        status="merged",
    )

    # 3. Same tenant, DIFFERENT domain -> should be EXCLUDED
    different_domain_candidate = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        name="Acme Parts Supply",
        code="acme_parts_supply",
        domain="product",
        status="approved",
    )

    form = MdmGoldenRecordMergeForm(tenant=tenant_a, primary_record=mdm_golden_record_a)
    candidate_qs = form.fields["secondary_record"].queryset

    # Assertions
    assert valid_candidate in candidate_qs
    assert mdm_golden_record_a not in candidate_qs, "Primary record must be excluded from its own merge candidates."
    assert merged_candidate not in candidate_qs, "Already merged records must be excluded from merge candidates."
    assert different_domain_candidate not in candidate_qs, "Records from different domains must be excluded."
    assert mdm_golden_record_b not in candidate_qs, "Cross-tenant records must be excluded."


@pytest.mark.django_db
def test_masterdata_merge_form_valid_submission(tenant_a, mdm_golden_record_a, mdm_golden_record_secondary_a):
    """Verify successful validation of MdmGoldenRecordMergeForm with valid secondary record and stewardship notes."""
    data = {
        "secondary_record": mdm_golden_record_secondary_a.pk,
        "stewardship_notes": "Duplicate verified via matching EIN and address taxonomy.",
    }
    form = MdmGoldenRecordMergeForm(data=data, tenant=tenant_a, primary_record=mdm_golden_record_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    assert form.cleaned_data["secondary_record"] == mdm_golden_record_secondary_a
    assert form.cleaned_data["stewardship_notes"] == "Duplicate verified via matching EIN and address taxonomy."


@pytest.mark.django_db
def test_masterdata_merge_form_missing_candidate_rejected(tenant_a, mdm_golden_record_a):
    """Verify MdmGoldenRecordMergeForm requires secondary_record."""
    form = MdmGoldenRecordMergeForm(data={"stewardship_notes": "Note"}, tenant=tenant_a, primary_record=mdm_golden_record_a)
    assert form.is_valid() is False
    assert "secondary_record" in form.errors


@pytest.mark.django_db
def test_masterdata_merge_form_cross_tenant_candidate_rejected(
    tenant_a,
    mdm_golden_record_a,
    mdm_golden_record_b,
):
    """Verify submitting a cross-tenant golden record as merge candidate is rejected."""
    data = {"secondary_record": mdm_golden_record_b.pk}
    form = MdmGoldenRecordMergeForm(data=data, tenant=tenant_a, primary_record=mdm_golden_record_a)
    assert form.is_valid() is False
    assert "secondary_record" in form.errors


@pytest.mark.django_db
def test_masterdata_merge_form_self_candidate_rejected(tenant_a, mdm_golden_record_a):
    """Verify submitting the primary record as its own merge candidate is rejected."""
    data = {"secondary_record": mdm_golden_record_a.pk}
    form = MdmGoldenRecordMergeForm(data=data, tenant=tenant_a, primary_record=mdm_golden_record_a)
    assert form.is_valid() is False
    assert "secondary_record" in form.errors


# ===========================================================================
# 4. MdmSurvivorshipRuleForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_valid_basic(tenant_a, admin_user):
    """Test valid MdmSurvivorshipRuleForm creation with standard attributes."""
    data = _masterdata_base_survivorship_rule_data(steward=admin_user.pk)
    form = MdmSurvivorshipRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save()
    assert rule.pk is not None
    assert rule.tenant == tenant_a
    assert rule.number.startswith("BMSR-")
    assert rule.name == "Customer Legal Name Source Trust Precedence"
    assert rule.domain == "customer"
    assert rule.survivorship_strategy == "source_priority"
    assert rule.match_algorithm == "exact"
    assert rule.match_threshold_pct == Decimal("80.00")
    assert rule.auto_merge_threshold_pct == Decimal("95.00")
    assert rule.steward == admin_user


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_priority_list_json_array_parsing(tenant_a):
    """Verify source_priority_list_text parses JSON array strings and saves to source_priority_list_json."""
    data = _masterdata_base_survivorship_rule_data(
        code="json_priority_rule",
        source_priority_list_text='["ERP_ORACLE", "SALESFORCE_CRM", "BILLING_STRIPE"]',
    )
    form = MdmSurvivorshipRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save()
    assert rule.source_priority_list_json == ["ERP_ORACLE", "SALESFORCE_CRM", "BILLING_STRIPE"]


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_priority_list_comma_separated_parsing(tenant_a):
    """Verify source_priority_list_text parses comma-separated strings as fallback."""
    data = _masterdata_base_survivorship_rule_data(
        code="csv_priority_rule",
        source_priority_list_text="ERP_CORE, CRM_APP, PORTAL_WEB, BILLING",
    )
    form = MdmSurvivorshipRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save()
    assert rule.source_priority_list_json == ["ERP_CORE", "CRM_APP", "PORTAL_WEB", "BILLING"]


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_priority_list_empty_parsing(tenant_a):
    """Verify empty source_priority_list_text gracefully parses to empty list []."""
    data = _masterdata_base_survivorship_rule_data(
        code="empty_priority_rule",
        source_priority_list_text="",
    )
    form = MdmSurvivorshipRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save()
    assert rule.source_priority_list_json == []


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_priority_list_initial_population(tenant_a, mdm_survivorship_rule_a):
    """Verify initializing MdmSurvivorshipRuleForm with instance populates source_priority_list_text initial."""
    form = MdmSurvivorshipRuleForm(instance=mdm_survivorship_rule_a, tenant=tenant_a)
    initial_text = form.fields["source_priority_list_text"].initial
    assert initial_text is not None
    parsed = json.loads(initial_text)
    assert parsed == mdm_survivorship_rule_a.source_priority_list_json


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_threshold_relationship_valid(tenant_a):
    """Verify auto_merge_threshold_pct >= match_threshold_pct passes validation."""
    # Case 1: auto_merge > match
    data1 = _masterdata_base_survivorship_rule_data(
        code="thresh_valid_gt",
        match_threshold_pct="80.00",
        auto_merge_threshold_pct="95.00",
    )
    form1 = MdmSurvivorshipRuleForm(data=data1, tenant=tenant_a)
    assert form1.is_valid()

    # Case 2: auto_merge == match
    data2 = _masterdata_base_survivorship_rule_data(
        code="thresh_valid_eq",
        match_threshold_pct="85.00",
        auto_merge_threshold_pct="85.00",
    )
    form2 = MdmSurvivorshipRuleForm(data=data2, tenant=tenant_a)
    assert form2.is_valid()


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_threshold_relationship_invalid(tenant_a):
    """Verify auto_merge_threshold_pct < match_threshold_pct raises validation error."""
    data = _masterdata_base_survivorship_rule_data(
        code="thresh_invalid",
        match_threshold_pct="90.00",
        auto_merge_threshold_pct="80.00",  # lower than match!
    )
    form = MdmSurvivorshipRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "auto_merge_threshold_pct" in form.errors
    assert "Auto-merge threshold must be greater than or equal to candidate match threshold." in form.errors["auto_merge_threshold_pct"]


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_threshold_bounds_validation(tenant_a):
    """Verify match and auto-merge thresholds enforce 0.00 to 100.00 limits."""
    # Out of range high
    form_high = MdmSurvivorshipRuleForm(
        data=_masterdata_base_survivorship_rule_data(
            match_threshold_pct="101.00",
            auto_merge_threshold_pct="105.00",
        ),
        tenant=tenant_a,
    )
    assert form_high.is_valid() is False
    assert "match_threshold_pct" in form_high.errors
    assert "auto_merge_threshold_pct" in form_high.errors

    # Out of range low
    form_low = MdmSurvivorshipRuleForm(
        data=_masterdata_base_survivorship_rule_data(
            match_threshold_pct="-5.00",
            auto_merge_threshold_pct="-1.00",
        ),
        tenant=tenant_a,
    )
    assert form_low.is_valid() is False
    assert "match_threshold_pct" in form_low.errors


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_steward_tenant_isolation(
    tenant_a,
    tenant_b,
    admin_user,
    admin_user_b,
):
    """Verify steward queryset in MdmSurvivorshipRuleForm only includes users from tenant_a."""
    form = MdmSurvivorshipRuleForm(tenant=tenant_a)
    steward_qs = form.fields["steward"].queryset
    assert admin_user in steward_qs
    assert admin_user_b not in steward_qs


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_cross_tenant_steward_rejection(tenant_a, admin_user_b):
    """Verify reject_foreign rejects a cross-tenant steward if queryset was broadened."""
    data = _masterdata_base_survivorship_rule_data(steward=admin_user_b.pk)
    form = MdmSurvivorshipRuleForm(data=data, tenant=tenant_a)
    form.fields["steward"].queryset = User.objects.all()

    assert form.is_valid() is False
    assert "That record belongs to another workspace." in form.errors["steward"]


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_duplicate_code_rejected(tenant_a, mdm_survivorship_rule_a):
    """Verify unique constraint on (tenant, code) is validated."""
    data = _masterdata_base_survivorship_rule_data(
        name="Rule with duplicate code",
        code=mdm_survivorship_rule_a.code,
    )
    form = MdmSurvivorshipRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    all_errors = str(form.errors)
    assert "code" in form.errors or "already exists" in all_errors.lower()


@pytest.mark.django_db
def test_masterdata_survivorship_rule_form_missing_required_fields(tenant_a):
    """Verify missing required name field raises validation error."""
    data = _masterdata_base_survivorship_rule_data(name="")
    form = MdmSurvivorshipRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "name" in form.errors


# ===========================================================================
# 5. MdmHierarchyNodeForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_valid_root_node(tenant_a):
    """Verify creating a valid root hierarchy node with parent=None."""
    data = _masterdata_base_hierarchy_node_data(
        name="Global Holding Corp",
        code="global_holding_corp",
        parent="",
    )
    form = MdmHierarchyNodeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    node = form.save()
    assert node.pk is not None
    assert node.tenant == tenant_a
    assert node.parent is None
    assert node.level == 0
    assert node.path == f"/{node.pk}/"
    assert node.number.startswith("BMHR-")


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_valid_child_node(tenant_a, mdm_hierarchy_node_root_a):
    """Verify creating a valid child hierarchy node referencing a parent with matching hierarchy_type."""
    data = _masterdata_base_hierarchy_node_data(
        name="Western Regional Division",
        code="western_regional_div",
        hierarchy_type=mdm_hierarchy_node_root_a.hierarchy_type,
        parent=mdm_hierarchy_node_root_a.pk,
    )
    form = MdmHierarchyNodeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    child = form.save()
    assert child.parent == mdm_hierarchy_node_root_a
    assert child.level == 1
    assert child.path == f"/{mdm_hierarchy_node_root_a.pk}/{child.pk}/"


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_valid_with_related_fks(
    tenant_a,
    mdm_golden_record_a,
):
    """Verify submitting MdmHierarchyNodeForm with golden_record, party, org_unit, and item_category FKs."""
    party = _masterdata_create_party(tenant_a, name="Operating Entity Party")
    org_unit = _masterdata_create_org_unit(tenant_a, name="Operations Directorate")
    item_cat = _masterdata_create_item_category(tenant_a, name="Industrial Assets Category")

    data = _masterdata_base_hierarchy_node_data(
        name="Integrated Facility Node",
        code="integrated_facility_node",
        golden_record=mdm_golden_record_a.pk,
        party=party.pk,
        org_unit=org_unit.pk,
        item_category=item_cat.pk,
    )
    form = MdmHierarchyNodeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    node = form.save()
    assert node.golden_record == mdm_golden_record_a
    assert node.party == party
    assert node.org_unit == org_unit
    assert node.item_category == item_cat


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_parent_queryset_tenant_isolation(
    tenant_a,
    tenant_b,
    mdm_hierarchy_node_root_a,
    mdm_hierarchy_node_b,
):
    """Verify parent queryset in MdmHierarchyNodeForm excludes nodes from foreign tenants."""
    form = MdmHierarchyNodeForm(tenant=tenant_a)
    parent_qs = form.fields["parent"].queryset
    assert mdm_hierarchy_node_root_a in parent_qs
    assert mdm_hierarchy_node_b not in parent_qs


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_parent_queryset_excludes_self_on_edit(
    tenant_a,
    mdm_hierarchy_node_root_a,
):
    """Verify parent queryset excludes self when editing an existing hierarchy node."""
    form = MdmHierarchyNodeForm(instance=mdm_hierarchy_node_root_a, tenant=tenant_a)
    assert mdm_hierarchy_node_root_a not in form.fields["parent"].queryset


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_self_parenting_prevention(
    tenant_a,
    mdm_hierarchy_node_root_a,
):
    """Verify clean() prevents setting self as parent."""
    data = _masterdata_base_hierarchy_node_data(
        name=mdm_hierarchy_node_root_a.name,
        code=mdm_hierarchy_node_root_a.code,
        hierarchy_type=mdm_hierarchy_node_root_a.hierarchy_type,
        parent=mdm_hierarchy_node_root_a.pk,
    )
    form = MdmHierarchyNodeForm(instance=mdm_hierarchy_node_root_a, data=data, tenant=tenant_a)
    # Broaden queryset to let self pass initial ModelChoiceField validation and hit clean()
    form.fields["parent"].queryset = MdmHierarchyNode.objects.filter(tenant=tenant_a)

    assert form.is_valid() is False
    assert "parent" in form.errors
    assert "A hierarchy node cannot be its own parent." in form.errors["parent"]


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_circular_reference_prevention(
    tenant_a,
    mdm_hierarchy_node_root_a,
    mdm_hierarchy_node_child_a,
):
    """Verify clean() detects circular parent assignment (cannot set descendant as parent)."""
    # mdm_hierarchy_node_root_a is parent of mdm_hierarchy_node_child_a.
    # Attempt to edit root_a and set child_a as its parent.
    data = _masterdata_base_hierarchy_node_data(
        name=mdm_hierarchy_node_root_a.name,
        code=mdm_hierarchy_node_root_a.code,
        hierarchy_type=mdm_hierarchy_node_root_a.hierarchy_type,
        parent=mdm_hierarchy_node_child_a.pk,
    )
    form = MdmHierarchyNodeForm(instance=mdm_hierarchy_node_root_a, data=data, tenant=tenant_a)
    # Child is not excluded by parent_qs.exclude(pk=self.pk), so child passes to clean()
    assert form.is_valid() is False
    assert "parent" in form.errors
    assert "Cannot set a child node as parent (circular hierarchy)." in form.errors["parent"]


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_hierarchy_type_homogeneity_validation(
    tenant_a,
    mdm_hierarchy_node_root_a,
):
    """Verify clean() rejects parent whose hierarchy_type does not match node hierarchy_type."""
    # root_a has hierarchy_type="corporate_legal"
    data = _masterdata_base_hierarchy_node_data(
        name="Mismatched Taxonomy Node",
        code="mismatched_tax_node",
        hierarchy_type="account_group",  # differs from root's corporate_legal
        parent=mdm_hierarchy_node_root_a.pk,
    )
    form = MdmHierarchyNodeForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "parent" in form.errors
    assert "Parent node hierarchy type must match node hierarchy type." in form.errors["parent"]


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_cross_tenant_fk_rejection(
    tenant_a,
    tenant_b,
    mdm_hierarchy_node_b,
    mdm_golden_record_b,
):
    """Verify reject_foreign rejects cross-tenant FK assignments on hierarchy nodes."""
    foreign_party = _masterdata_create_party(tenant_b, name="Foreign Corp")
    foreign_org = _masterdata_create_org_unit(tenant_b, name="Foreign Division")
    foreign_item_cat = _masterdata_create_item_category(tenant_b, name="Foreign Cat")

    data = _masterdata_base_hierarchy_node_data(
        parent=mdm_hierarchy_node_b.pk,
        golden_record=mdm_golden_record_b.pk,
        party=foreign_party.pk,
        org_unit=foreign_org.pk,
        item_category=foreign_item_cat.pk,
    )
    form = MdmHierarchyNodeForm(data=data, tenant=tenant_a)

    # Broaden querysets to test reject_foreign
    form.fields["parent"].queryset = MdmHierarchyNode.objects.all()
    form.fields["golden_record"].queryset = MdmGoldenRecord.objects.all()
    form.fields["party"].queryset = Party.objects.all()
    form.fields["org_unit"].queryset = OrgUnit.objects.all()
    form.fields["item_category"].queryset = ItemCategory.objects.all()

    assert form.is_valid() is False
    assert "That record belongs to another workspace." in form.errors["parent"]
    assert "That record belongs to another workspace." in form.errors["golden_record"]
    assert "That record belongs to another workspace." in form.errors["party"]
    assert "That record belongs to another workspace." in form.errors["org_unit"]
    assert "That record belongs to another workspace." in form.errors["item_category"]


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_duplicate_code_same_type_rejected(
    tenant_a,
    mdm_hierarchy_node_root_a,
):
    """Verify unique constraint (tenant, hierarchy_type, code) is validated."""
    data = _masterdata_base_hierarchy_node_data(
        name="Duplicate Node Name",
        code=mdm_hierarchy_node_root_a.code,
        hierarchy_type=mdm_hierarchy_node_root_a.hierarchy_type,
    )
    form = MdmHierarchyNodeForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    all_errors = str(form.errors)
    assert "code" in form.errors or "already exists" in all_errors.lower()


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_duplicate_code_different_type_allowed(
    tenant_a,
    mdm_hierarchy_node_root_a,
):
    """Verify same code under a different hierarchy_type is accepted."""
    data = _masterdata_base_hierarchy_node_data(
        name="Product Taxonomy Node",
        code=mdm_hierarchy_node_root_a.code,
        hierarchy_type="product_taxonomy",  # root_a is 'corporate_legal'
    )
    form = MdmHierarchyNodeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    node = form.save()
    assert node.hierarchy_type == "product_taxonomy"
    assert node.code == mdm_hierarchy_node_root_a.code


@pytest.mark.django_db
def test_masterdata_hierarchy_node_form_missing_required_fields(tenant_a):
    """Verify missing required name field raises validation error."""
    data = _masterdata_base_hierarchy_node_data(name="")
    form = MdmHierarchyNodeForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "name" in form.errors


# ===========================================================================
# 6. MdmReferenceCodeForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_reference_code_form_valid_basic(tenant_a):
    """Test valid MdmReferenceCodeForm creation with standard attributes."""
    data = _masterdata_base_reference_code_data()
    form = MdmReferenceCodeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    ref_code = form.save()
    assert ref_code.pk is not None
    assert ref_code.tenant == tenant_a
    assert ref_code.number.startswith("BMRD-")
    assert ref_code.code_set == "ISO-3166-COUNTRY"
    assert ref_code.canonical_code == "CAN"
    assert ref_code.canonical_name == "Canada"
    assert ref_code.source_system == "legacy_sap"
    assert ref_code.source_code == "CA"
    assert ref_code.attributes_json == {"iso_numeric": "124", "alpha_2": "CA", "currency": "CAD"}


@pytest.mark.django_db
def test_masterdata_reference_code_form_attributes_valid_json_dict(tenant_a):
    """Verify clean_attributes_text parses valid JSON dictionary and saves to attributes_json."""
    data = _masterdata_base_reference_code_data(
        canonical_code="MEX",
        canonical_name="Mexico",
        attributes_text='{"dial_code": "+52", "capital": "Mexico City", "official_lang": "es"}',
    )
    form = MdmReferenceCodeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    ref_code = form.save()
    assert ref_code.attributes_json == {
        "dial_code": "+52",
        "capital": "Mexico City",
        "official_lang": "es",
    }


@pytest.mark.django_db
def test_masterdata_reference_code_form_attributes_empty_defaults_to_dict(tenant_a):
    """Verify empty attributes_text defaults to empty dict {}."""
    data = _masterdata_base_reference_code_data(
        canonical_code="GBR",
        canonical_name="United Kingdom",
        attributes_text="",
    )
    form = MdmReferenceCodeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    ref_code = form.save()
    assert ref_code.attributes_json == {}


@pytest.mark.django_db
def test_masterdata_reference_code_form_attributes_malformed_json_rejected(tenant_a):
    """Verify invalid JSON syntax in attributes_text raises ValidationError."""
    data = _masterdata_base_reference_code_data(
        attributes_text='{"unclosed_string: 1234',
    )
    form = MdmReferenceCodeForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "attributes_text" in form.errors
    assert any("invalid json" in err.lower() for err in form.errors["attributes_text"])


@pytest.mark.django_db
def test_masterdata_reference_code_form_attributes_non_dict_json_rejected(tenant_a):
    """Verify non-dictionary JSON (e.g. array, integer, string) raises ValidationError."""
    # JSON list
    form_list = MdmReferenceCodeForm(
        data=_masterdata_base_reference_code_data(attributes_text='["item1", "item2"]'),
        tenant=tenant_a,
    )
    assert form_list.is_valid() is False
    assert "attributes_text" in form_list.errors
    assert "Attributes must be a valid JSON dictionary." in form_list.errors["attributes_text"]

    # JSON scalar string
    form_str = MdmReferenceCodeForm(
        data=_masterdata_base_reference_code_data(attributes_text='"scalar_string"'),
        tenant=tenant_a,
    )
    assert form_str.is_valid() is False
    assert "attributes_text" in form_str.errors
    assert "Attributes must be a valid JSON dictionary." in form_str.errors["attributes_text"]


@pytest.mark.django_db
def test_masterdata_reference_code_form_attributes_initial_population(tenant_a):
    """Verify initializing MdmReferenceCodeForm with instance populates attributes_text initial."""
    instance = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="PAYMENT-TERMS",
        canonical_code="NET60",
        canonical_name="Net 60 Days",
        attributes_json={"days_due": 60, "discount_pct": 0.0},
    )
    form = MdmReferenceCodeForm(instance=instance, tenant=tenant_a)
    initial_text = form.fields["attributes_text"].initial
    assert initial_text is not None
    parsed = json.loads(initial_text)
    assert parsed == {"days_due": 60, "discount_pct": 0.0}


@pytest.mark.django_db
def test_masterdata_reference_code_form_superseded_by_queryset_isolation(
    tenant_a,
    tenant_b,
    mdm_reference_code_a,
    mdm_reference_code_b,
):
    """Verify superseded_by queryset in MdmReferenceCodeForm only includes codes for tenant_a."""
    form = MdmReferenceCodeForm(tenant=tenant_a)
    superseded_qs = form.fields["superseded_by"].queryset
    assert mdm_reference_code_a in superseded_qs
    assert mdm_reference_code_b not in superseded_qs


@pytest.mark.django_db
def test_masterdata_reference_code_form_superseded_by_queryset_excludes_self(
    tenant_a,
    mdm_reference_code_a,
):
    """Verify superseded_by queryset excludes self when editing an existing reference code."""
    form = MdmReferenceCodeForm(instance=mdm_reference_code_a, tenant=tenant_a)
    assert mdm_reference_code_a not in form.fields["superseded_by"].queryset


@pytest.mark.django_db
def test_masterdata_reference_code_form_cross_tenant_superseded_by_rejected(
    tenant_a,
    mdm_reference_code_b,
):
    """Verify reject_foreign rejects a cross-tenant superseded_by code."""
    data = _masterdata_base_reference_code_data(superseded_by=mdm_reference_code_b.pk)
    form = MdmReferenceCodeForm(data=data, tenant=tenant_a)
    form.fields["superseded_by"].queryset = MdmReferenceCode.objects.all()

    assert form.is_valid() is False
    assert "That record belongs to another workspace." in form.errors["superseded_by"]


@pytest.mark.django_db
def test_masterdata_reference_code_form_duplicate_code_rejected(tenant_a, mdm_reference_code_a):
    """Verify unique constraint on (tenant, code_set, canonical_code, source_system, source_code)."""
    data = _masterdata_base_reference_code_data(
        code_set=mdm_reference_code_a.code_set,
        canonical_code=mdm_reference_code_a.canonical_code,
        source_system=mdm_reference_code_a.source_system,
        source_code=mdm_reference_code_a.source_code,
        canonical_name="Duplicate Code Definition",
    )
    form = MdmReferenceCodeForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    all_errors = str(form.errors)
    assert (
        "canonical_code" in form.errors
        or "code_set" in form.errors
        or "already exists" in all_errors.lower()
    )


@pytest.mark.django_db
def test_masterdata_reference_code_form_missing_required_fields(tenant_a):
    """Verify missing required fields (code_set, canonical_code, canonical_name) raise validation errors."""
    data = _masterdata_base_reference_code_data(
        code_set="",
        canonical_code="",
        canonical_name="",
    )
    form = MdmReferenceCodeForm(data=data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "code_set" in form.errors
    assert "canonical_code" in form.errors
    assert "canonical_name" in form.errors
