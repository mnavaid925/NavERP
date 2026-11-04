"""Unit tests for Sub-module 10.6 Master Data Management (MDM) models.

Models covered:
- MdmGoldenRecord (BMGR)
- MdmSurvivorshipRule (BMSR)
- MdmHierarchyNode (BMHR)
- MdmReferenceCode (BMRD)
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.bi.models import (
    MdmGoldenRecord,
    MdmHierarchyNode,
    MdmReferenceCode,
    MdmSurvivorshipRule,
)


# ---------------------------------------------------------------------------
# Module Helpers
# ---------------------------------------------------------------------------


def _masterdata_extract_choice_keys(choices_list):
    """Helper to extract keys from Django choices tuple/list."""
    return [c[0] for c in choices_list]


# ---------------------------------------------------------------------------
# 1. MdmGoldenRecord Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_masterdata_golden_record_creation_and_autonumber(tenant_a, admin_user):
    """Test MdmGoldenRecord creation, BMGR- auto-number prefix, and core fields."""
    record = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        name="Global Logistics Partners",
        code="global_logistics_partners",
        domain="vendor",
        trust_tier="gold",
        confidence_score=Decimal("99.20"),
        assigned_steward=admin_user,
    )
    assert record.NUMBER_PREFIX == "BMGR"
    assert record.number.startswith("BMGR-")
    assert record.name == "Global Logistics Partners"
    assert record.code == "global_logistics_partners"
    assert record.domain == "vendor"
    assert record.trust_tier == "gold"
    assert record.confidence_score == Decimal("99.20")
    assert record.tenant == tenant_a
    assert record.assigned_steward == admin_user


@pytest.mark.django_db
def test_masterdata_golden_record_str_representation(mdm_golden_record_a):
    """Test MdmGoldenRecord string format '{number} - {name} ({domain_display})'."""
    expected_str = f"{mdm_golden_record_a.number} - {mdm_golden_record_a.name} ({mdm_golden_record_a.get_domain_display()})"
    assert str(mdm_golden_record_a) == expected_str


@pytest.mark.django_db
def test_masterdata_golden_record_absolute_url(mdm_golden_record_a):
    """Verify get_absolute_url resolves to canonical detail route '/bi/mdm/golden-records/{pk}/'."""
    expected_url = f"/bi/mdm/golden-records/{mdm_golden_record_a.pk}/"
    assert mdm_golden_record_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_masterdata_golden_record_defaults(tenant_a):
    """Verify default field values for MdmGoldenRecord."""
    record = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        name="Default Candidate Record",
        code="default_cand_record",
    )
    assert record.domain == "customer"
    assert record.status == "approved"
    assert record.trust_tier == "silver"
    assert record.confidence_score == Decimal("100.00")
    assert record.source_record_count == 1
    assert record.golden_attributes_json == {}
    assert record.source_crosswalks_json == []
    assert record.merged_into_record is None
    assert record.merged_at is None
    assert record.assigned_steward is None
    assert record.reviewed_by is None
    assert record.reviewed_at is None
    assert record.stewardship_notes == ""
    assert record.is_active is True


@pytest.mark.django_db
def test_masterdata_golden_record_choices():
    """Verify choice keys for MdmGoldenRecord domain, status, and trust tier."""
    domain_keys = _masterdata_extract_choice_keys(MdmGoldenRecord.DOMAIN_CHOICES)
    assert domain_keys == [
        "customer",
        "vendor",
        "product",
        "asset",
        "employee",
        "account",
        "custom",
    ]

    status_keys = _masterdata_extract_choice_keys(MdmGoldenRecord.STATUS_CHOICES)
    assert status_keys == [
        "draft",
        "pending_review",
        "approved",
        "in_dispute",
        "merged",
        "superseded",
        "archived",
    ]

    tier_keys = _masterdata_extract_choice_keys(MdmGoldenRecord.TRUST_TIER_CHOICES)
    assert tier_keys == ["gold", "silver", "bronze"]


@pytest.mark.django_db
def test_masterdata_golden_record_confidence_score_validation(tenant_a):
    """Verify confidence_score enforces MinValueValidator(0.00) and MaxValueValidator(100.00)."""
    # Valid boundary scores
    rec_zero = MdmGoldenRecord(
        tenant=tenant_a,
        name="Zero Score",
        code="zero_score",
        confidence_score=Decimal("0.00"),
        golden_attributes_json={"tier": "bronze"},
        source_crosswalks_json=[{"system": "CRM", "id": "1"}],
    )
    rec_zero.full_clean()

    rec_hundred = MdmGoldenRecord(
        tenant=tenant_a,
        name="Hundred Score",
        code="hundred_score",
        confidence_score=Decimal("100.00"),
        golden_attributes_json={"tier": "gold"},
        source_crosswalks_json=[{"system": "CRM", "id": "2"}],
    )
    rec_hundred.full_clean()

    # Out-of-bounds negative score
    rec_neg = MdmGoldenRecord(
        tenant=tenant_a,
        name="Negative Score",
        code="neg_score",
        confidence_score=Decimal("-0.01"),
        golden_attributes_json={"tier": "bronze"},
        source_crosswalks_json=[{"system": "CRM", "id": "3"}],
    )
    with pytest.raises(ValidationError) as exc_info:
        rec_neg.full_clean()
    assert "confidence_score" in exc_info.value.message_dict

    # Out-of-bounds excessive score
    rec_high = MdmGoldenRecord(
        tenant=tenant_a,
        name="Excessive Score",
        code="excessive_score",
        confidence_score=Decimal("100.01"),
        golden_attributes_json={"tier": "gold"},
        source_crosswalks_json=[{"system": "CRM", "id": "4"}],
    )
    with pytest.raises(ValidationError) as exc_info:
        rec_high.full_clean()
    assert "confidence_score" in exc_info.value.message_dict


@pytest.mark.django_db
def test_masterdata_golden_record_json_fields_handling(tenant_a):
    """Verify storing, modifying, and persisting golden_attributes_json and source_crosswalks_json."""
    crosswalks = [
        {"system": "salesforce", "source_id": "SF-0091", "extracted_at": "2026-11-01"},
        {"system": "sap_erp", "source_id": "CUST_99182", "extracted_at": "2026-11-02"},
    ]
    attributes = {
        "annual_revenue": 5000000,
        "employee_count": 250,
        "segment": "Enterprise",
        "compliance": {"gdpr_ready": True, "iso27001": True},
    }
    record = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        name="Nexus Enterprise Corp",
        code="nexus_enterprise_corp",
        source_record_count=2,
        source_crosswalks_json=crosswalks,
        golden_attributes_json=attributes,
    )
    record.refresh_from_db()
    assert len(record.source_crosswalks_json) == 2
    assert record.source_crosswalks_json[0]["system"] == "salesforce"
    assert record.golden_attributes_json["compliance"]["gdpr_ready"] is True

    # Mutate and persist JSON payload
    record.golden_attributes_json["segment"] = "Strategic Enterprise"
    record.source_crosswalks_json.append({"system": "billing", "source_id": "INV-500"})
    record.source_record_count = 3
    record.save(update_fields=["golden_attributes_json", "source_crosswalks_json", "source_record_count"])

    record.refresh_from_db()
    assert record.golden_attributes_json["segment"] == "Strategic Enterprise"
    assert len(record.source_crosswalks_json) == 3
    assert record.source_record_count == 3


@pytest.mark.django_db
def test_masterdata_golden_record_unique_tenant_domain_code(tenant_a, tenant_b):
    """Verify unique constraint on ('tenant', 'domain', 'code')."""
    MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        name="Target Corp Master",
        code="target_corp",
        domain="customer",
    )
    # Duplicate (tenant, domain, code) in tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        MdmGoldenRecord.objects.create(
            tenant=tenant_a,
            name="Target Corp Duplicate",
            code="target_corp",
            domain="customer",
        )

    # Same code but different domain in tenant_a is permitted
    vendor_rec = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        name="Target Corp Supplier",
        code="target_corp",
        domain="vendor",
    )
    assert vendor_rec.domain == "vendor"

    # Same domain and code in tenant_b is permitted (multi-tenant isolation)
    globex_rec = MdmGoldenRecord.objects.create(
        tenant=tenant_b,
        name="Target Corp Globex Branch",
        code="target_corp",
        domain="customer",
    )
    assert globex_rec.tenant == tenant_b


@pytest.mark.django_db
def test_masterdata_golden_record_unique_tenant_number(tenant_a, mdm_golden_record_a):
    """Verify unique constraint on ('tenant', 'number')."""
    with pytest.raises(IntegrityError):
        MdmGoldenRecord.objects.create(
            tenant=tenant_a,
            number=mdm_golden_record_a.number,
            name="Conflicting Number Record",
            code="conflicting_num_record",
            domain="customer",
        )


@pytest.mark.django_db
def test_masterdata_golden_record_merge_relationship(tenant_a, mdm_golden_record_a, mdm_golden_record_secondary_a):
    """Verify self-referential merge relationship and absorbed_records reverse manager."""
    merge_time = timezone.now()
    mdm_golden_record_secondary_a.status = "merged"
    mdm_golden_record_secondary_a.merged_into_record = mdm_golden_record_a
    mdm_golden_record_secondary_a.merged_at = merge_time
    mdm_golden_record_secondary_a.save(update_fields=["status", "merged_into_record", "merged_at"])

    # Absorbed records reverse relation
    absorbed = list(mdm_golden_record_a.absorbed_records.all())
    assert mdm_golden_record_secondary_a in absorbed
    assert absorbed[0].merged_at == merge_time


@pytest.mark.django_db
def test_masterdata_golden_record_tenant_isolation(tenant_a, tenant_b, mdm_golden_record_a, mdm_golden_record_b):
    """Verify strict tenant isolation between Acme (tenant_a) and Globex (tenant_b)."""
    acme_records = list(MdmGoldenRecord.objects.filter(tenant=tenant_a))
    assert mdm_golden_record_a in acme_records
    assert mdm_golden_record_b not in acme_records

    globex_records = list(MdmGoldenRecord.objects.filter(tenant=tenant_b))
    assert mdm_golden_record_b in globex_records
    assert mdm_golden_record_a not in globex_records


# ---------------------------------------------------------------------------
# 2. MdmSurvivorshipRule Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_masterdata_survivorship_rule_creation_and_autonumber(tenant_a, admin_user):
    """Test MdmSurvivorshipRule creation, BMSR- prefix, and initial attributes."""
    rule = MdmSurvivorshipRule.objects.create(
        tenant=tenant_a,
        name="Customer Primary Phone Precedence",
        code="cust_phone_precedence",
        domain="customer",
        target_field="primary_phone",
        survivorship_strategy="source_priority",
        source_priority_list_json=["CRM", "PORTAL", "BILLING"],
        match_algorithm="exact",
        match_threshold_pct=Decimal("85.00"),
        auto_merge_threshold_pct=Decimal("98.00"),
        steward=admin_user,
        priority_order=5,
    )
    assert rule.NUMBER_PREFIX == "BMSR"
    assert rule.number.startswith("BMSR-")
    assert rule.name == "Customer Primary Phone Precedence"
    assert rule.code == "cust_phone_precedence"
    assert rule.target_field == "primary_phone"
    assert rule.source_priority_list_json == ["CRM", "PORTAL", "BILLING"]
    assert rule.priority_order == 5
    assert rule.steward == admin_user


@pytest.mark.django_db
def test_masterdata_survivorship_rule_str_representation(mdm_survivorship_rule_a):
    """Test MdmSurvivorshipRule string format '{number} - {name} ({strategy_display})'."""
    expected_str = f"{mdm_survivorship_rule_a.number} - {mdm_survivorship_rule_a.name} ({mdm_survivorship_rule_a.get_survivorship_strategy_display()})"
    assert str(mdm_survivorship_rule_a) == expected_str


@pytest.mark.django_db
def test_masterdata_survivorship_rule_absolute_url(mdm_survivorship_rule_a):
    """Verify get_absolute_url resolves to canonical detail route '/bi/mdm/survivorship-rules/{pk}/'."""
    expected_url = f"/bi/mdm/survivorship-rules/{mdm_survivorship_rule_a.pk}/"
    assert mdm_survivorship_rule_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_masterdata_survivorship_rule_defaults(tenant_a):
    """Verify default field values for MdmSurvivorshipRule."""
    rule = MdmSurvivorshipRule.objects.create(
        tenant=tenant_a,
        name="Default Survivorship Rule",
        code="default_surv_rule",
    )
    assert rule.domain == "all"
    assert rule.target_field == "*"
    assert rule.survivorship_strategy == "source_priority"
    assert rule.match_algorithm == "exact"
    assert rule.match_threshold_pct == Decimal("80.00")
    assert rule.auto_merge_threshold_pct == Decimal("95.00")
    assert rule.source_priority_list_json == []
    assert rule.priority_order == 10
    assert rule.steward is None
    assert rule.description == ""
    assert rule.is_active is True


@pytest.mark.django_db
def test_masterdata_survivorship_rule_choices():
    """Verify choice keys and aliases for domain, survivorship strategy, and match algorithm."""
    domain_keys = _masterdata_extract_choice_keys(MdmSurvivorshipRule.DOMAIN_CHOICES)
    assert domain_keys == ["all", "customer", "vendor", "product", "asset", "employee"]

    # Verify strategy choices and STRATEGY_CHOICES alias
    strategy_keys = _masterdata_extract_choice_keys(MdmSurvivorshipRule.SURVIVORSHIP_STRATEGY_CHOICES)
    assert strategy_keys == [
        "source_priority",
        "most_recent",
        "highest_completeness",
        "most_frequent",
        "manual_pick",
        "oldest_original",
    ]
    assert MdmSurvivorshipRule.STRATEGY_CHOICES == MdmSurvivorshipRule.SURVIVORSHIP_STRATEGY_CHOICES

    # Verify match algorithm choices and MATCH_ALGO_CHOICES alias
    algo_keys = _masterdata_extract_choice_keys(MdmSurvivorshipRule.MATCH_ALGORITHM_CHOICES)
    assert algo_keys == [
        "exact",
        "fuzzy_levenshtein",
        "fuzzy_jaro_winkler",
        "phonetic_soundex",
        "token_set_ratio",
        "rule_expression",
    ]
    assert MdmSurvivorshipRule.MATCH_ALGO_CHOICES == MdmSurvivorshipRule.MATCH_ALGORITHM_CHOICES


@pytest.mark.django_db
def test_masterdata_survivorship_rule_threshold_validations(tenant_a):
    """Verify match_threshold_pct and auto_merge_threshold_pct 0.00-100.00 validation."""
    rule_valid = MdmSurvivorshipRule(
        tenant=tenant_a,
        name="Boundary Rule",
        code="boundary_rule",
        match_threshold_pct=Decimal("0.00"),
        auto_merge_threshold_pct=Decimal("100.00"),
        source_priority_list_json=["CRM"],
    )
    rule_valid.full_clean()

    # match_threshold_pct < 0
    rule_neg = MdmSurvivorshipRule(
        tenant=tenant_a,
        name="Negative Match",
        code="neg_match",
        match_threshold_pct=Decimal("-5.00"),
        source_priority_list_json=["CRM"],
    )
    with pytest.raises(ValidationError) as exc:
        rule_neg.full_clean()
    assert "match_threshold_pct" in exc.value.message_dict

    # auto_merge_threshold_pct > 100
    rule_over = MdmSurvivorshipRule(
        tenant=tenant_a,
        name="Over 100 Auto Merge",
        code="over_100_auto",
        auto_merge_threshold_pct=Decimal("105.00"),
        source_priority_list_json=["CRM"],
    )
    with pytest.raises(ValidationError) as exc:
        rule_over.full_clean()
    assert "auto_merge_threshold_pct" in exc.value.message_dict


@pytest.mark.django_db
def test_masterdata_survivorship_rule_source_precedence_list_handling(tenant_a):
    """Verify source precedence list getter, setter, init kwarg, and JSON persistence."""
    # Init with source_precedence_list
    rule = MdmSurvivorshipRule.objects.create(
        tenant=tenant_a,
        name="Vendor Master Precedence",
        code="vendor_master_prec",
        source_precedence_list=["SAP", "ORACLE", "COUPA"],
    )
    assert rule.source_priority_list_json == ["SAP", "ORACLE", "COUPA"]
    assert rule.source_precedence_list == ["SAP", "ORACLE", "COUPA"]

    # Mutate through property setter
    rule.source_precedence_list = ["COUPA", "SAP"]
    rule.save(update_fields=["source_priority_list_json"])

    rule.refresh_from_db()
    assert rule.source_priority_list_json == ["COUPA", "SAP"]
    assert rule.source_precedence_list == ["COUPA", "SAP"]


@pytest.mark.django_db
def test_masterdata_survivorship_rule_unique_tenant_code(tenant_a, tenant_b):
    """Verify unique constraint on ('tenant', 'code')."""
    MdmSurvivorshipRule.objects.create(
        tenant=tenant_a,
        name="Customer Tax ID Survivorship",
        code="cust_tax_id_surv",
    )
    with pytest.raises(IntegrityError):
        MdmSurvivorshipRule.objects.create(
            tenant=tenant_a,
            name="Duplicate Code Rule",
            code="cust_tax_id_surv",
        )

    # Same code in tenant_b is allowed
    globex_rule = MdmSurvivorshipRule.objects.create(
        tenant=tenant_b,
        name="Globex Tax ID Survivorship",
        code="cust_tax_id_surv",
    )
    assert globex_rule.tenant == tenant_b


@pytest.mark.django_db
def test_masterdata_survivorship_rule_unique_tenant_number(tenant_a, mdm_survivorship_rule_a):
    """Verify unique constraint on ('tenant', 'number')."""
    with pytest.raises(IntegrityError):
        MdmSurvivorshipRule.objects.create(
            tenant=tenant_a,
            number=mdm_survivorship_rule_a.number,
            name="Conflicting Number Rule",
            code="conflicting_num_rule",
        )


@pytest.mark.django_db
def test_masterdata_survivorship_rule_tenant_isolation(tenant_a, tenant_b, mdm_survivorship_rule_a, mdm_survivorship_rule_b):
    """Verify tenant isolation for survivorship rules."""
    acme_rules = list(MdmSurvivorshipRule.objects.filter(tenant=tenant_a))
    assert mdm_survivorship_rule_a in acme_rules
    assert mdm_survivorship_rule_b not in acme_rules

    globex_rules = list(MdmSurvivorshipRule.objects.filter(tenant=tenant_b))
    assert mdm_survivorship_rule_b in globex_rules
    assert mdm_survivorship_rule_a not in globex_rules


# ---------------------------------------------------------------------------
# 3. MdmHierarchyNode Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_masterdata_hierarchy_node_root_creation_level_and_path(tenant_a):
    """Verify root node creation computes level=0 and path=/{pk}/."""
    root = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Acme Holdings Inc",
        code="acme_holdings",
        hierarchy_type="corporate_legal",
        relationship_kind="holding_company",
        parent=None,
    )
    assert root.NUMBER_PREFIX == "BMHR"
    assert root.number.startswith("BMHR-")
    assert root.level == 0
    assert root.path == f"/{root.pk}/"
    assert root.parent is None


@pytest.mark.django_db
def test_masterdata_hierarchy_node_child_creation_level_and_path(tenant_a):
    """Verify child node creation inherits parent path and sets level=parent.level + 1."""
    root = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Apex Parent Group",
        code="apex_parent_grp",
        hierarchy_type="account_group",
    )
    child = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Apex Enterprise Accounts",
        code="apex_ent_accts",
        hierarchy_type="account_group",
        parent=root,
    )
    assert child.level == 1
    assert child.path == f"/{root.pk}/{child.pk}/"
    assert child.parent == root


@pytest.mark.django_db
def test_masterdata_hierarchy_node_grandchild_creation_level_and_path(tenant_a):
    """Verify multi-level hierarchy creates grandchild with level=2 and compound path."""
    root = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Product Taxonomy Root",
        code="prod_tax_root",
        hierarchy_type="product_taxonomy",
    )
    category = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Industrial Equipment",
        code="industrial_equip",
        hierarchy_type="product_taxonomy",
        parent=root,
    )
    subcategory = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="High-Pressure Pumps",
        code="hp_pumps",
        hierarchy_type="product_taxonomy",
        parent=category,
    )
    assert subcategory.level == 2
    assert subcategory.path == f"/{root.pk}/{category.pk}/{subcategory.pk}/"


@pytest.mark.django_db
def test_masterdata_hierarchy_node_descendant_path_cascading_on_reparent(tenant_a):
    """Verify moving an intermediate node cascades updated level and path to all descendants."""
    root_1 = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Root Americas",
        code="root_americas",
        hierarchy_type="org_reporting",
    )
    root_2 = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Root Global Operations",
        code="root_global_ops",
        hierarchy_type="org_reporting",
    )

    division = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Logistics Division",
        code="logistics_div",
        hierarchy_type="org_reporting",
        parent=root_1,
    )
    team = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Fleet Dispatch Team",
        code="fleet_dispatch_team",
        hierarchy_type="org_reporting",
        parent=division,
    )

    # Initial paths
    assert division.level == 1
    assert division.path == f"/{root_1.pk}/{division.pk}/"
    assert team.level == 2
    assert team.path == f"/{root_1.pk}/{division.pk}/{team.pk}/"

    # Re-parent division from root_1 to root_2
    division.parent = root_2
    division.save()

    division.refresh_from_db()
    team.refresh_from_db()

    # Division and Team must reflect root_2 path and updated levels
    assert division.path == f"/{root_2.pk}/{division.pk}/"
    assert division.level == 1
    assert team.path == f"/{root_2.pk}/{division.pk}/{team.pk}/"
    assert team.level == 2


@pytest.mark.django_db
def test_masterdata_hierarchy_node_str_representation(mdm_hierarchy_node_root_a):
    """Test MdmHierarchyNode string format '{number} - {name} ({hierarchy_type_display})'."""
    expected_str = f"{mdm_hierarchy_node_root_a.number} - {mdm_hierarchy_node_root_a.name} ({mdm_hierarchy_node_root_a.get_hierarchy_type_display()})"
    assert str(mdm_hierarchy_node_root_a) == expected_str


@pytest.mark.django_db
def test_masterdata_hierarchy_node_absolute_url(mdm_hierarchy_node_root_a):
    """Verify get_absolute_url resolves to canonical detail route '/bi/mdm/hierarchy-nodes/{pk}/'."""
    expected_url = f"/bi/mdm/hierarchy-nodes/{mdm_hierarchy_node_root_a.pk}/"
    assert mdm_hierarchy_node_root_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_masterdata_hierarchy_node_defaults(tenant_a):
    """Verify default field values for MdmHierarchyNode."""
    node = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Default Hierarchy Node",
        code="default_hier_node",
    )
    assert node.hierarchy_type == "corporate_legal"
    assert node.parent is None
    assert node.level == 0
    assert node.path == f"/{node.pk}/"
    assert node.golden_record is None
    assert node.party is None
    assert node.org_unit is None
    assert node.item_category is None
    assert node.relationship_kind == "parent_child"
    assert node.sort_order == 10
    assert node.valid_from is None
    assert node.valid_to is None
    assert node.description == ""
    assert node.is_active is True


@pytest.mark.django_db
def test_masterdata_hierarchy_node_choices():
    """Verify choice keys for HIERARCHY_TYPE_CHOICES."""
    type_keys = _masterdata_extract_choice_keys(MdmHierarchyNode.HIERARCHY_TYPE_CHOICES)
    assert type_keys == [
        "corporate_legal",
        "account_group",
        "product_taxonomy",
        "org_reporting",
        "cost_center_rollup",
        "asset_location",
    ]


@pytest.mark.django_db
def test_masterdata_hierarchy_node_unique_tenant_type_code(tenant_a, tenant_b):
    """Verify unique constraint on ('tenant', 'hierarchy_type', 'code')."""
    MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Corporate Tree Node",
        code="corp_node_a",
        hierarchy_type="corporate_legal",
    )
    with pytest.raises(IntegrityError):
        MdmHierarchyNode.objects.create(
            tenant=tenant_a,
            name="Conflicting Corporate Tree Node",
            code="corp_node_a",
            hierarchy_type="corporate_legal",
        )

    # Same code with different hierarchy_type in tenant_a is permitted
    org_node = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Org Tree Node",
        code="corp_node_a",
        hierarchy_type="org_reporting",
    )
    assert org_node.hierarchy_type == "org_reporting"

    # Same hierarchy_type and code in tenant_b is permitted
    globex_node = MdmHierarchyNode.objects.create(
        tenant=tenant_b,
        name="Globex Corporate Tree Node",
        code="corp_node_a",
        hierarchy_type="corporate_legal",
    )
    assert globex_node.tenant == tenant_b


@pytest.mark.django_db
def test_masterdata_hierarchy_node_unique_tenant_number(tenant_a, mdm_hierarchy_node_root_a):
    """Verify unique constraint on ('tenant', 'number')."""
    with pytest.raises(IntegrityError):
        MdmHierarchyNode.objects.create(
            tenant=tenant_a,
            number=mdm_hierarchy_node_root_a.number,
            name="Conflicting Number Node",
            code="conflicting_num_node",
        )


@pytest.mark.django_db
def test_masterdata_hierarchy_node_golden_record_relationship(tenant_a, mdm_golden_record_a):
    """Verify linking MdmHierarchyNode to MdmGoldenRecord and reverse manager."""
    node = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Acme Prime Corp Legal Entity",
        code="acme_prime_legal_entity",
        hierarchy_type="corporate_legal",
        golden_record=mdm_golden_record_a,
    )
    assert node.golden_record == mdm_golden_record_a
    assert node in mdm_golden_record_a.hierarchy_nodes.all()


@pytest.mark.django_db
def test_masterdata_hierarchy_node_node_type_alias_property(tenant_a):
    """Verify node_type init kwarg, property getter, and setter map to relationship_kind."""
    node = MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        name="Holding Entity Node",
        code="holding_entity_node",
        node_type="holding_company",
    )
    assert node.relationship_kind == "holding_company"
    assert node.node_type == "holding_company"

    node.node_type = "operating_subsidiary"
    assert node.relationship_kind == "operating_subsidiary"


@pytest.mark.django_db
def test_masterdata_hierarchy_node_tenant_isolation(tenant_a, tenant_b, mdm_hierarchy_node_root_a, mdm_hierarchy_node_b):
    """Verify tenant isolation for hierarchy nodes."""
    acme_nodes = list(MdmHierarchyNode.objects.filter(tenant=tenant_a))
    assert mdm_hierarchy_node_root_a in acme_nodes
    assert mdm_hierarchy_node_b not in acme_nodes

    globex_nodes = list(MdmHierarchyNode.objects.filter(tenant=tenant_b))
    assert mdm_hierarchy_node_b in globex_nodes
    assert mdm_hierarchy_node_root_a not in globex_nodes


# ---------------------------------------------------------------------------
# 4. MdmReferenceCode Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_masterdata_reference_code_creation_and_autonumber(tenant_a):
    """Test MdmReferenceCode creation, BMRD- prefix, and code mapping fields."""
    ref = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="ISO-3166-COUNTRY",
        canonical_code="USA",
        canonical_name="United States of America",
        source_system="CRM_SALES",
        source_code="US",
        category="North America",
        status="active",
    )
    assert ref.NUMBER_PREFIX == "BMRD"
    assert ref.number.startswith("BMRD-")
    assert ref.code_set == "ISO-3166-COUNTRY"
    assert ref.canonical_code == "USA"
    assert ref.canonical_name == "United States of America"
    assert ref.source_system == "CRM_SALES"
    assert ref.source_code == "US"
    assert ref.category == "North America"
    assert ref.status == "active"


@pytest.mark.django_db
def test_masterdata_reference_code_str_representation_with_and_without_source(tenant_a, mdm_reference_code_a):
    """Test string format with source info and without source info."""
    # With source info
    expected_with_src = f"{mdm_reference_code_a.code_set} / {mdm_reference_code_a.canonical_code} - {mdm_reference_code_a.canonical_name} [{mdm_reference_code_a.source_system}:{mdm_reference_code_a.source_code}]"
    assert str(mdm_reference_code_a) == expected_with_src

    # Without source info (pure canonical standard)
    canonical_pure = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="ISO-3166-COUNTRY",
        canonical_code="CAN",
        canonical_name="Canada",
        source_system="",
        source_code="",
    )
    expected_without_src = f"{canonical_pure.code_set} / {canonical_pure.canonical_code} - {canonical_pure.canonical_name}"
    assert str(canonical_pure) == expected_without_src


@pytest.mark.django_db
def test_masterdata_reference_code_absolute_url(mdm_reference_code_a):
    """Verify get_absolute_url resolves to canonical detail route '/bi/mdm/reference-codes/{pk}/'."""
    expected_url = f"/bi/mdm/reference-codes/{mdm_reference_code_a.pk}/"
    assert mdm_reference_code_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_masterdata_reference_code_defaults(tenant_a):
    """Verify default field values for MdmReferenceCode."""
    ref = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="UN-ECE-UOM",
        canonical_code="KGM",
        canonical_name="Kilogram",
    )
    assert ref.source_system == ""
    assert ref.source_code == ""
    assert ref.category == ""
    assert ref.status == "active"
    assert ref.superseded_by is None
    assert ref.effective_from is None
    assert ref.effective_to is None
    assert ref.attributes_json == {}
    assert ref.description == ""
    assert ref.is_active is True


@pytest.mark.django_db
def test_masterdata_reference_code_choices():
    """Verify choice keys for STATUS_CHOICES and CODE_SET_CHOICES."""
    status_keys = _masterdata_extract_choice_keys(MdmReferenceCode.STATUS_CHOICES)
    assert status_keys == ["draft", "active", "deprecated", "superseded", "inactive"]

    code_set_keys = _masterdata_extract_choice_keys(MdmReferenceCode.CODE_SET_CHOICES)
    assert code_set_keys == [
        "ISO-4217-CURRENCY",
        "ISO-3166-COUNTRY",
        "UN-ECE-UOM",
        "INC-TERMS",
        "PAYMENT-TERMS",
        "CUSTOM",
    ]


@pytest.mark.django_db
def test_masterdata_reference_code_unique_together_constraint(tenant_a):
    """Verify unique constraint on ('tenant', 'code_set', 'canonical_code', 'source_system', 'source_code')."""
    MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="ISO-4217-CURRENCY",
        canonical_code="JPY",
        canonical_name="Japanese Yen",
        source_system="SAP",
        source_code="JPY",
    )
    with pytest.raises(IntegrityError):
        MdmReferenceCode.objects.create(
            tenant=tenant_a,
            code_set="ISO-4217-CURRENCY",
            canonical_code="JPY",
            canonical_name="Duplicate Yen Mapping",
            source_system="SAP",
            source_code="JPY",
        )

    # Different source_system or source_code within the same code_set is allowed
    oracle_mapping = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="ISO-4217-CURRENCY",
        canonical_code="JPY",
        canonical_name="Japanese Yen Oracle",
        source_system="ORACLE",
        source_code="392",
    )
    assert oracle_mapping.source_system == "ORACLE"


@pytest.mark.django_db
def test_masterdata_reference_code_cross_tenant_allowed(tenant_a, tenant_b):
    """Verify identical reference code mapping is permitted across separate tenants."""
    ref_a = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="INC-TERMS",
        canonical_code="FOB",
        canonical_name="Free On Board",
        source_system="LEGACY",
        source_code="FOB",
    )
    ref_b = MdmReferenceCode.objects.create(
        tenant=tenant_b,
        code_set="INC-TERMS",
        canonical_code="FOB",
        canonical_name="Free On Board Globex",
        source_system="LEGACY",
        source_code="FOB",
    )
    assert ref_a.tenant == tenant_a
    assert ref_b.tenant == tenant_b


@pytest.mark.django_db
def test_masterdata_reference_code_unique_tenant_number(tenant_a, mdm_reference_code_a):
    """Verify unique constraint on ('tenant', 'number')."""
    with pytest.raises(IntegrityError):
        MdmReferenceCode.objects.create(
            tenant=tenant_a,
            number=mdm_reference_code_a.number,
            code_set="ISO-4217-CURRENCY",
            canonical_code="GBP",
            canonical_name="British Pound",
        )


@pytest.mark.django_db
def test_masterdata_reference_code_superseded_by_relationship(tenant_a):
    """Verify self-referential superseded_by foreign key and superseded_codes manager."""
    old_code = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="PAYMENT-TERMS",
        canonical_code="NET15",
        canonical_name="Net 15 Days",
        status="superseded",
    )
    new_code = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="PAYMENT-TERMS",
        canonical_code="NET30",
        canonical_name="Standard Net 30 Days",
        status="active",
    )
    old_code.superseded_by = new_code
    old_code.save(update_fields=["superseded_by"])

    assert old_code in new_code.superseded_codes.all()


@pytest.mark.django_db
def test_masterdata_reference_code_attributes_json_handling(tenant_a):
    """Verify supplementary attributes JSON dictionary persistence."""
    attrs = {
        "iso_numeric": "840",
        "alpha_2": "US",
        "dial_code": "+1",
        "currency_symbol": "$",
    }
    ref = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="ISO-3166-COUNTRY",
        canonical_code="USA",
        canonical_name="United States",
        attributes_json=attrs,
    )
    ref.refresh_from_db()
    assert ref.attributes_json["iso_numeric"] == "840"
    assert ref.attributes_json["currency_symbol"] == "$"


@pytest.mark.django_db
def test_masterdata_reference_code_is_standard_property(tenant_a):
    """Verify is_standard property and kwarg initialization."""
    # When initialized with is_standard=True
    ref_standard = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="ISO-4217-CURRENCY",
        canonical_code="CHF",
        canonical_name="Swiss Franc",
        is_standard=True,
    )
    assert ref_standard.is_standard is True

    # Standard without source_system defaults to is_standard=True
    ref_canonical = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="ISO-4217-CURRENCY",
        canonical_code="CAD",
        canonical_name="Canadian Dollar",
        source_system="",
    )
    assert ref_canonical.is_standard is True

    # Feeder system mapping defaults to is_standard=False
    ref_feeder = MdmReferenceCode.objects.create(
        tenant=tenant_a,
        code_set="ISO-4217-CURRENCY",
        canonical_code="CAD",
        canonical_name="Canadian Dollar Feeder",
        source_system="QUICKBOOKS",
        source_code="C$",
    )
    assert ref_feeder.is_standard is False


@pytest.mark.django_db
def test_masterdata_reference_code_tenant_isolation(tenant_a, tenant_b, mdm_reference_code_a, mdm_reference_code_b):
    """Verify tenant isolation for reference codes."""
    acme_codes = list(MdmReferenceCode.objects.filter(tenant=tenant_a))
    assert mdm_reference_code_a in acme_codes
    assert mdm_reference_code_b not in acme_codes

    globex_codes = list(MdmReferenceCode.objects.filter(tenant=tenant_b))
    assert mdm_reference_code_b in globex_codes
    assert mdm_reference_code_a not in globex_codes


# ---------------------------------------------------------------------------
# 5. Cross-Cutting & Fixture Verification Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_masterdata_conftest_fixtures_integrity(
    mdm_golden_record_a,
    mdm_golden_record_secondary_a,
    mdm_golden_record_b,
    mdm_survivorship_rule_a,
    mdm_survivorship_rule_b,
    mdm_hierarchy_node_root_a,
    mdm_hierarchy_node_child_a,
    mdm_hierarchy_node_b,
    mdm_reference_code_a,
    mdm_reference_code_b,
):
    """Verify all shared fixtures in conftest.py instantiate cleanly with valid attributes."""
    # Golden Records
    assert mdm_golden_record_a.number == "BMGR-00001"
    assert mdm_golden_record_secondary_a.number == "BMGR-00002"
    assert mdm_golden_record_b.number == "BMGR-00003"
    assert mdm_golden_record_a.domain == "customer"
    assert mdm_golden_record_a.trust_tier == "gold"

    # Survivorship Rules
    assert mdm_survivorship_rule_a.number == "BMSR-00001"
    assert mdm_survivorship_rule_b.number == "BMSR-00002"
    assert mdm_survivorship_rule_a.survivorship_strategy == "source_priority"

    # Hierarchy Nodes
    assert mdm_hierarchy_node_root_a.number == "BMHR-00001"
    assert mdm_hierarchy_node_child_a.number == "BMHR-00002"
    assert mdm_hierarchy_node_child_a.parent == mdm_hierarchy_node_root_a
    assert mdm_hierarchy_node_child_a.golden_record == mdm_golden_record_a

    # Reference Codes
    assert mdm_reference_code_a.number == "BMRD-00001"
    assert mdm_reference_code_b.number == "BMRD-00002"
    assert mdm_reference_code_a.canonical_code == "USD"
    assert mdm_reference_code_b.canonical_code == "EUR"


@pytest.mark.django_db
def test_masterdata_autonumber_sequential_generation(tenant_a):
    """Verify sequential numbering across successive records within the same tenant."""
    g1 = MdmGoldenRecord.objects.create(tenant=tenant_a, name="Seq Golden 1", code="seq_g_1")
    g2 = MdmGoldenRecord.objects.create(tenant=tenant_a, name="Seq Golden 2", code="seq_g_2")
    num1 = int(g1.number.split("-")[1])
    num2 = int(g2.number.split("-")[1])
    assert num2 == num1 + 1

    r1 = MdmSurvivorshipRule.objects.create(tenant=tenant_a, name="Seq Rule 1", code="seq_r_1")
    r2 = MdmSurvivorshipRule.objects.create(tenant=tenant_a, name="Seq Rule 2", code="seq_r_2")
    r_num1 = int(r1.number.split("-")[1])
    r_num2 = int(r2.number.split("-")[1])
    assert r_num2 == r_num1 + 1
