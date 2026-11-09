"""Asset Classification & Categorization (11.3) — MODEL Invariants Test Suite.

Covers the 4 core models:
- AssetCategory [ACAT-]
- AssetModel [AMOD-]
- AssetCriticalityAssessment [ACRT-]
- AssetSpecificationTemplate [ASPC-]

Invariants pinned:
1. String representations (__str__) for all 4 models.
2. Auto-number generation and collision-free prefixing (ACAT, AMOD, ACRT, ASPC).
3. AssetCategory taxonomy tree, parent-child relationships, get_ancestors/get_descendants, full_path, cycle prevention and cross-tenant clean() validation.
4. AssetModel properties, display_manufacturer fallback, MinValueValidator on estimated_replacement_cost, and reverse FK access.
5. AssetCriticalityAssessment composite score calculation, SPOF consequence bonus, ABC rating derivation (A/B/C), and workflow status progression.
6. AssetSpecificationTemplate validation (category or model target, snake_case attribute_key, min <= max bounds, regex pattern checking), and data_type_css badge mappings.
7. Tenant isolation and compound unique constraints across multi-tenant boundaries.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.models import (
    AssetCategory,
    AssetCriticalityAssessment,
    AssetModel,
    AssetSpecificationTemplate,
)


def _assetclassification_allowed_badge_classes():
    """Return the set of valid colour-named theme.css badge classes."""
    return {
        "badge-green",
        "badge-red",
        "badge-amber",
        "badge-info",
        "badge-muted",
        "badge-slate",
        "badge-purple",
    }


# ==============================================================================
# 1. String Representations (__str__)
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_models_category_str(category_root_a, category_child_a):
    """AssetCategory __str__ format is '{code} — {name}' with em-dash."""
    assert str(category_root_a) == f"{category_root_a.code} — {category_root_a.name}"
    assert str(category_child_a) == f"{category_child_a.code} — {category_child_a.name}"
    assert category_root_a.code in str(category_root_a)
    assert category_root_a.name in str(category_root_a)


@pytest.mark.django_db
def test_assetclassification_models_model_str(asset_model_a):
    """AssetModel __str__ format is '{model_number} — {name}' with em-dash."""
    assert str(asset_model_a) == f"{asset_model_a.model_number} — {asset_model_a.name}"
    assert asset_model_a.model_number in str(asset_model_a)
    assert asset_model_a.name in str(asset_model_a)


@pytest.mark.django_db
def test_assetclassification_models_criticality_str(criticality_assessment_a):
    """AssetCriticalityAssessment __str__ format is '{number} — {title} ({abc_display})'."""
    expected = f"{criticality_assessment_a.number} — {criticality_assessment_a.title} ({criticality_assessment_a.get_abc_rating_display()})"
    assert str(criticality_assessment_a) == expected


@pytest.mark.django_db
def test_assetclassification_models_spec_template_str(spec_template_a):
    """AssetSpecificationTemplate __str__ format is '{attribute_key} ({display_name})'."""
    assert str(spec_template_a) == f"{spec_template_a.attribute_key} ({spec_template_a.display_name})"


# ==============================================================================
# 2. Number Sequence & Prefix Integrity
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_models_category_number_prefix(tenant_a):
    """AssetCategory auto-generates unique sequential numbers prefixed with ACAT-."""
    c1 = AssetCategory.objects.create(
        tenant=tenant_a,
        code="PUMP-CENT",
        name="Centrifugal Pumps",
    )
    c2 = AssetCategory.objects.create(
        tenant=tenant_a,
        code="PUMP-POS",
        name="Positive Displacement Pumps",
    )
    assert c1.number.startswith("ACAT-")
    assert c2.number.startswith("ACAT-")
    assert c1.number != c2.number


@pytest.mark.django_db
def test_assetclassification_models_model_number_prefix(tenant_a, category_root_a):
    """AssetModel auto-generates unique sequential numbers prefixed with AMOD-."""
    m1 = AssetModel.objects.create(
        tenant=tenant_a,
        model_number="MOD-ALPHA-01",
        name="Alpha Series Model 1",
        category=category_root_a,
    )
    m2 = AssetModel.objects.create(
        tenant=tenant_a,
        model_number="MOD-BETA-02",
        name="Beta Series Model 2",
        category=category_root_a,
    )
    assert m1.number.startswith("AMOD-")
    assert m2.number.startswith("AMOD-")
    assert m1.number != m2.number


@pytest.mark.django_db
def test_assetclassification_models_criticality_number_prefix(tenant_a, operational_asset_a, vendor_party_a):
    """AssetCriticalityAssessment auto-generates numbers prefixed with ACRT-."""
    cr1 = AssetCriticalityAssessment.objects.create(
        tenant=tenant_a,
        title="Audit 1",
        asset=operational_asset_a,
        assessor=vendor_party_a,
    )
    cr2 = AssetCriticalityAssessment.objects.create(
        tenant=tenant_a,
        title="Audit 2",
        asset=operational_asset_a,
        assessor=vendor_party_a,
    )
    assert cr1.number.startswith("ACRT-")
    assert cr2.number.startswith("ACRT-")
    assert cr1.number != cr2.number


@pytest.mark.django_db
def test_assetclassification_models_spec_template_number_prefix(tenant_a, category_root_a):
    """AssetSpecificationTemplate auto-generates numbers prefixed with ASPC-."""
    st1 = AssetSpecificationTemplate.objects.create(
        tenant=tenant_a,
        category=category_root_a,
        attribute_key="spec_test_attr_one",
        display_name="Test Attribute One",
    )
    st2 = AssetSpecificationTemplate.objects.create(
        tenant=tenant_a,
        category=category_root_a,
        attribute_key="spec_test_attr_two",
        display_name="Test Attribute Two",
    )
    assert st1.number.startswith("ASPC-")
    assert st2.number.startswith("ASPC-")
    assert st1.number != st2.number


# ==============================================================================
# 3. AssetCategory Hierarchy, Path & Cycle Validation
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_models_category_hierarchy_parent_children(category_root_a, category_child_a, tenant_a):
    """AssetCategory hierarchy correctly models parent and children relationships."""
    assert category_child_a.parent == category_root_a
    assert category_root_a.children.filter(pk=category_child_a.pk).exists()

    grandchild = AssetCategory.objects.create(
        tenant=tenant_a,
        code="CHL-SCROLL",
        name="Scroll Compressors",
        parent=category_child_a,
    )
    assert grandchild.parent == category_child_a
    assert category_child_a.children.filter(pk=grandchild.pk).exists()


@pytest.mark.django_db
def test_assetclassification_models_category_get_ancestors_and_descendants(category_root_a, category_child_a, tenant_a):
    """AssetCategory get_ancestors and get_descendants recursively traverse taxonomy nodes."""
    grandchild = AssetCategory.objects.create(
        tenant=tenant_a,
        code="CHL-MOTOR",
        name="Compressor Drive Motor",
        parent=category_child_a,
    )

    ancestors = grandchild.get_ancestors()
    assert ancestors == [category_child_a, category_root_a]
    assert category_root_a.get_ancestors() == []

    descendants = category_root_a.get_descendants()
    assert category_child_a in descendants
    assert grandchild in descendants
    assert grandchild.get_descendants() == []


@pytest.mark.django_db
def test_assetclassification_models_category_full_path(category_root_a, category_child_a, tenant_a):
    """AssetCategory full_path returns slash-delimited breadcrumb codes from root."""
    assert category_root_a.full_path == "FAC-PLANT"
    assert category_child_a.full_path == "FAC-PLANT / HVAC-CHL"

    grandchild = AssetCategory.objects.create(
        tenant=tenant_a,
        code="ROOF-TOP",
        name="Rooftop Package",
        parent=category_child_a,
    )
    assert grandchild.full_path == "FAC-PLANT / HVAC-CHL / ROOF-TOP"


@pytest.mark.django_db
def test_assetclassification_models_category_clean_self_parent(category_root_a):
    """AssetCategory.clean prevents a category from being its own parent."""
    category_root_a.parent = category_root_a
    with pytest.raises(ValidationError) as exc_info:
        category_root_a.clean()
    assert "parent" in exc_info.value.message_dict
    assert "cannot be its own parent" in exc_info.value.message_dict["parent"][0]


@pytest.mark.django_db
def test_assetclassification_models_category_clean_circular_loop(category_root_a, category_child_a):
    """AssetCategory.clean detects and rejects circular parent references."""
    category_root_a.parent = category_child_a
    with pytest.raises(ValidationError) as exc_info:
        category_root_a.clean()
    assert "parent" in exc_info.value.message_dict
    assert "Circular category hierarchy detected" in exc_info.value.message_dict["parent"][0]


@pytest.mark.django_db
def test_assetclassification_models_category_clean_tenant_isolation(category_root_a, category_root_b):
    """AssetCategory.clean rejects parenting to a category belonging to another tenant."""
    category_root_b.parent = category_root_a
    with pytest.raises(ValidationError) as exc_info:
        category_root_b.clean()
    assert "parent" in exc_info.value.message_dict
    assert "belongs to another workspace" in exc_info.value.message_dict["parent"][0]


@pytest.mark.django_db
def test_assetclassification_models_category_code_uppercase(tenant_a):
    """AssetCategory.clean strips whitespace and converts code to uppercase."""
    cat = AssetCategory(
        tenant=tenant_a,
        code="  elec-gen  ",
        name="Diesel Generators",
    )
    cat.clean()
    assert cat.code == "ELEC-GEN"


@pytest.mark.django_db
def test_assetclassification_models_category_defaults_and_choices(category_root_a):
    """AssetCategory has standard defaults and valid CSS badge classes."""
    allowed = _assetclassification_allowed_badge_classes()
    assert category_root_a.default_depreciation_method == "straight_line"
    assert category_root_a.category_type == "machinery"
    assert category_root_a.default_maintenance_strategy == "preventive_calendar"
    assert category_root_a.status_css in allowed
    assert category_root_a.criticality_css in allowed


# ==============================================================================
# 4. AssetModel Invariants, Relationships & Fallbacks
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_models_model_properties_and_fallback(tenant_a, category_root_a, vendor_party_a):
    """AssetModel display_manufacturer uses Party name, fallback text, or em-dash."""
    model_with_party = AssetModel.objects.create(
        tenant=tenant_a,
        model_number="TRANE-CVHE",
        name="Centrifugal Water Chiller",
        category=category_root_a,
        manufacturer=vendor_party_a,
    )
    assert model_with_party.display_manufacturer == vendor_party_a.name

    model_with_fallback = AssetModel.objects.create(
        tenant=tenant_a,
        model_number="YORK-YK-01",
        name="Centrifugal Liquid Chiller",
        category=category_root_a,
        manufacturer_name_fallback="York International",
    )
    assert model_with_fallback.display_manufacturer == "York International"

    model_bare = AssetModel.objects.create(
        tenant=tenant_a,
        model_number="GEN-CUSTOM-01",
        name="Custom Fabricated Skid",
        category=category_root_a,
    )
    assert model_bare.display_manufacturer == "—"


@pytest.mark.django_db
def test_assetclassification_models_model_estimated_replacement_cost_non_negative(tenant_a, category_root_a):
    """AssetModel estimated_replacement_cost MinValueValidator prevents negative values."""
    model = AssetModel(
        tenant=tenant_a,
        model_number="NEG-COST-MOD",
        name="Negative Cost Model",
        category=category_root_a,
        estimated_replacement_cost=Decimal("-500.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        model.full_clean()
    assert "estimated_replacement_cost" in exc_info.value.message_dict

    # Zero and positive should pass
    model.estimated_replacement_cost = Decimal("0.00")
    model.full_clean()


@pytest.mark.django_db
def test_assetclassification_models_model_model_number_cleaned(tenant_a, category_root_a):
    """AssetModel.clean strips and capitalizes model_number."""
    mod = AssetModel(
        tenant=tenant_a,
        model_number="  hfe-m2-200t  ",
        name="Hydraulic Press Brake 200T",
        category=category_root_a,
    )
    mod.clean()
    assert mod.model_number == "HFE-M2-200T"


@pytest.mark.django_db
def test_assetclassification_models_model_relationships(asset_model_a, category_root_a, vendor_party_a):
    """AssetModel foreign keys and reverse querysets operate correctly."""
    assert asset_model_a.category == category_root_a
    assert category_root_a.models.filter(pk=asset_model_a.pk).exists()

    assert asset_model_a.manufacturer == vendor_party_a
    assert vendor_party_a.asset_models.filter(pk=asset_model_a.pk).exists()


@pytest.mark.django_db
def test_assetclassification_models_model_status_css(asset_model_a):
    """AssetModel status_css resolves to a valid CSS badge class across all choices."""
    allowed = _assetclassification_allowed_badge_classes()
    for status_code, _ in AssetModel.MODEL_STATUS_CHOICES:
        asset_model_a.model_status = status_code
        assert asset_model_a.status_css in allowed


# ==============================================================================
# 5. AssetCriticalityAssessment Composite Score & ABC Rating
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_models_criticality_calculate_composite_score_standard(operational_asset_a, vendor_party_a, tenant_a):
    """Composite score is sum of 5 impact factors (1..5) plus 0 when not single point of failure."""
    assessment = AssetCriticalityAssessment(
        tenant=tenant_a,
        title="Standard Pump Criticality",
        asset=operational_asset_a,
        assessor=vendor_party_a,
        safety_impact=3,
        environmental_impact=3,
        operational_downtime_impact=3,
        financial_impact=3,
        regulatory_compliance_impact=3,
        is_single_point_of_failure=False,
    )
    assessment.calculate_composite_score()
    # 3 + 3 + 3 + 3 + 3 = 15
    assert assessment.composite_score == 15
    assert assessment.abc_rating == "B"
    assert assessment.recommended_strategy == "rigorous_pm"


@pytest.mark.django_db
def test_assetclassification_models_criticality_calculate_composite_score_class_a(operational_asset_a, vendor_party_a, tenant_a):
    """Composite score >= 20 produces Class A (Mission-Critical) with predictive maintenance recommendation."""
    assessment = AssetCriticalityAssessment(
        tenant=tenant_a,
        title="Primary Substation Review",
        asset=operational_asset_a,
        assessor=vendor_party_a,
        safety_impact=4,
        environmental_impact=4,
        operational_downtime_impact=4,
        financial_impact=4,
        regulatory_compliance_impact=4,
        is_single_point_of_failure=False,
    )
    assessment.calculate_composite_score()
    # 4*5 = 20
    assert assessment.composite_score == 20
    assert assessment.abc_rating == "A"
    assert assessment.recommended_strategy == "rcm_predictive"


@pytest.mark.django_db
def test_assetclassification_models_criticality_calculate_composite_score_spof_bonus(operational_asset_a, vendor_party_a, tenant_a):
    """Single point of failure adds +5 bonus, and escalates to Class A if safety or downtime impact >= 4."""
    assessment = AssetCriticalityAssessment(
        tenant=tenant_a,
        title="Sole Feedwater Pump",
        asset=operational_asset_a,
        assessor=vendor_party_a,
        safety_impact=4,
        environmental_impact=1,
        operational_downtime_impact=2,
        financial_impact=1,
        regulatory_compliance_impact=1,
        is_single_point_of_failure=True,
    )
    assessment.calculate_composite_score()
    # 4+1+2+1+1 + 5 = 14
    assert assessment.composite_score == 14
    # Because SPOF=True and safety_impact >= 4, auto-escalates to Class A
    assert assessment.abc_rating == "A"


@pytest.mark.django_db
def test_assetclassification_models_criticality_calculate_composite_score_class_c(operational_asset_a, vendor_party_a, tenant_a):
    """Composite score < 12 yields Class C (Standard / Low Impact)."""
    assessment = AssetCriticalityAssessment(
        tenant=tenant_a,
        title="Utility Sink Exhaust Fan",
        asset=operational_asset_a,
        assessor=vendor_party_a,
        safety_impact=1,
        environmental_impact=1,
        operational_downtime_impact=1,
        financial_impact=1,
        regulatory_compliance_impact=1,
        is_single_point_of_failure=False,
    )
    assessment.calculate_composite_score()
    # 1+1+1+1+1 = 5
    assert assessment.composite_score == 5
    assert assessment.abc_rating == "C"


@pytest.mark.django_db
def test_assetclassification_models_criticality_save_auto_calculates(operational_asset_a, vendor_party_a, tenant_a):
    """AssetCriticalityAssessment.save automatically executes calculate_composite_score()."""
    assessment = AssetCriticalityAssessment(
        tenant=tenant_a,
        title="Auto-Calc Test",
        asset=operational_asset_a,
        assessor=vendor_party_a,
        safety_impact=5,
        environmental_impact=5,
        operational_downtime_impact=5,
        financial_impact=5,
        regulatory_compliance_impact=5,
        is_single_point_of_failure=True,
    )
    assessment.save()
    # 25 + 5 = 30
    assert assessment.composite_score == 30
    assert assessment.abc_rating == "A"


@pytest.mark.django_db
def test_assetclassification_models_criticality_status_workflow(criticality_assessment_a, admin_user):
    """AssetCriticalityAssessment tracks audit statuses and validates CSS badge classes."""
    allowed = _assetclassification_allowed_badge_classes()
    assert criticality_assessment_a.status_css in allowed
    assert criticality_assessment_a.abc_css in allowed

    # Move to approved
    criticality_assessment_a.assessment_status = "approved"
    criticality_assessment_a.approved_by = admin_user
    criticality_assessment_a.approved_at = timezone.now()
    criticality_assessment_a.save()
    assert criticality_assessment_a.status_css == "badge-green"

    # Move to superseded
    criticality_assessment_a.assessment_status = "superseded"
    criticality_assessment_a.save()
    assert criticality_assessment_a.status_css == "badge-muted"


# ==============================================================================
# 6. AssetSpecificationTemplate Validation & Schemas
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_models_spec_template_clean_category_or_model_required(tenant_a):
    """AssetSpecificationTemplate requires either a Category or Model parent."""
    template = AssetSpecificationTemplate(
        tenant=tenant_a,
        attribute_key="unattached_attr",
        display_name="Unattached Attribute",
        category=None,
        model=None,
    )
    with pytest.raises(ValidationError) as exc_info:
        template.clean()
    assert "must be assigned to either an Asset Category or an Asset Model" in str(exc_info.value)


@pytest.mark.django_db
def test_assetclassification_models_spec_template_attribute_key_slug(tenant_a, category_root_a):
    """AssetSpecificationTemplate.clean validates and normalizes attribute_key as snake_case."""
    # Invalid characters
    invalid_template = AssetSpecificationTemplate(
        tenant=tenant_a,
        category=category_root_a,
        attribute_key="Voltage (VAC)!",
        display_name="Operating Voltage",
    )
    with pytest.raises(ValidationError) as exc_info:
        invalid_template.clean()
    assert "attribute_key" in exc_info.value.message_dict

    # Valid key with mixed case gets lowercased
    valid_template = AssetSpecificationTemplate(
        tenant=tenant_a,
        category=category_root_a,
        attribute_key="  OPERATING_VOLTAGE_VAC  ",
        display_name="Operating Voltage",
    )
    valid_template.clean()
    assert valid_template.attribute_key == "operating_voltage_vac"


@pytest.mark.django_db
def test_assetclassification_models_spec_template_min_max_numeric_validation(tenant_a, category_root_a):
    """AssetSpecificationTemplate.clean enforces min_numeric_value <= max_numeric_value."""
    template = AssetSpecificationTemplate(
        tenant=tenant_a,
        category=category_root_a,
        attribute_key="flow_rate_gpm",
        display_name="Flow Rate (GPM)",
        min_numeric_value=Decimal("500.00"),
        max_numeric_value=Decimal("100.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        template.clean()
    assert "min_numeric_value" in exc_info.value.message_dict
    assert "Minimum bound cannot exceed maximum bound" in exc_info.value.message_dict["min_numeric_value"][0]

    # Valid range passes
    template.min_numeric_value = Decimal("100.00")
    template.max_numeric_value = Decimal("500.00")
    template.clean()


@pytest.mark.django_db
def test_assetclassification_models_spec_template_validation_regex(tenant_a, category_root_a):
    """AssetSpecificationTemplate.clean verifies that validation_regex compiles without error."""
    template = AssetSpecificationTemplate(
        tenant=tenant_a,
        category=category_root_a,
        attribute_key="serial_format",
        display_name="Serial Number Format",
        validation_regex="^[0-9]{3}-([A-Z]{2",  # Unclosed group
    )
    with pytest.raises(ValidationError) as exc_info:
        template.clean()
    assert "validation_regex" in exc_info.value.message_dict
    assert "Invalid regular expression pattern" in exc_info.value.message_dict["validation_regex"][0]

    # Valid regex passes
    template.validation_regex = r"^[0-9]{3}-[A-Z]{2}$"
    template.clean()


@pytest.mark.django_db
def test_assetclassification_models_spec_template_data_type_css(spec_template_a):
    """AssetSpecificationTemplate data_type_css returns a valid badge class for each choice."""
    allowed = _assetclassification_allowed_badge_classes()
    for dt_code, _ in AssetSpecificationTemplate.DATA_TYPE_CHOICES:
        spec_template_a.data_type = dt_code
        assert spec_template_a.data_type_css in allowed


@pytest.mark.django_db
def test_assetclassification_models_spec_template_target_scope(category_root_a, asset_model_a, tenant_a):
    """AssetSpecificationTemplate target_scope returns human-readable scope label."""
    cat_tmpl = AssetSpecificationTemplate(
        tenant=tenant_a,
        category=category_root_a,
        attribute_key="pressure_psi",
        display_name="Pressure (PSI)",
    )
    assert cat_tmpl.target_scope == f"Category: {category_root_a.code}"

    mod_tmpl = AssetSpecificationTemplate(
        tenant=tenant_a,
        model=asset_model_a,
        attribute_key="hydraulic_oil_type",
        display_name="Hydraulic Oil Type",
    )
    assert mod_tmpl.target_scope == f"Model: {asset_model_a.model_number}"


# ==============================================================================
# 7. Tenant Isolation & Compound Unique Constraints
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_models_tenant_isolation_category(category_root_a, category_root_b, tenant_a, tenant_b):
    """AssetCategory enforces (tenant, code) compound uniqueness across multi-tenant boundaries."""
    # Cross-tenant same code is permitted
    dup_b = AssetCategory.objects.create(
        tenant=tenant_b,
        code=category_root_a.code,
        name="Acme Duplicate in Globex",
    )
    assert dup_b.pk is not None

    # Intra-tenant duplicate code raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetCategory.objects.create(
                tenant=tenant_a,
                code=category_root_a.code,
                name="Duplicate Code Within Acme",
            )


@pytest.mark.django_db
def test_assetclassification_models_tenant_isolation_model(asset_model_a, asset_model_b, tenant_a, tenant_b, category_root_b):
    """AssetModel enforces (tenant, model_number) compound uniqueness across tenants."""
    # Cross-tenant same model_number is allowed
    dup_b = AssetModel.objects.create(
        tenant=tenant_b,
        model_number=asset_model_a.model_number,
        name="Cross-Tenant Duplicate Model",
        category=category_root_b,
    )
    assert dup_b.pk is not None

    # Intra-tenant duplicate raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetModel.objects.create(
                tenant=tenant_a,
                model_number=asset_model_a.model_number,
                name="Duplicate Model In Same Tenant",
                category=asset_model_a.category,
            )


@pytest.mark.django_db
def test_assetclassification_models_tenant_isolation_criticality(criticality_assessment_a, criticality_assessment_b):
    """AssetCriticalityAssessment records are completely isolated per tenant."""
    assert criticality_assessment_a.tenant != criticality_assessment_b.tenant
    assert criticality_assessment_a.number.startswith("ACRT-")
    assert criticality_assessment_b.number.startswith("ACRT-")
    assert criticality_assessment_a.asset.tenant == criticality_assessment_a.tenant


@pytest.mark.django_db
def test_assetclassification_models_tenant_isolation_spec_template(spec_template_a, spec_template_b):
    """AssetSpecificationTemplate records are partitioned by tenant."""
    assert spec_template_a.tenant != spec_template_b.tenant
    assert spec_template_a.category.tenant == spec_template_a.tenant
    assert spec_template_b.category.tenant == spec_template_b.tenant
