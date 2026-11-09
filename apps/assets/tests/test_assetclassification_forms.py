"""Asset Classification & Categorization (11.3) — FORMS Invariants Test Suite.

Covers the 4 model forms:
- AssetCategoryForm
- AssetModelForm
- AssetCriticalityAssessmentForm
- AssetSpecificationTemplateForm

Invariants pinned:
1. Valid data creation and updates.
2. System & view-owned field exclusions (tenant, number, timestamps, calculated/privileged fields).
3. Tenant-scoped dropdown querysets for parent, category, manufacturer, asset, assessor, and model.
4. Cross-tenant FK rejection via reject_foreign and clean() validation.
5. Cycle prevention validation on category hierarchy.
6. Code and model number whitespace stripping & uppercase cleaning.
7. Criticality consequence score validation (1 to 5 range, rejection of negative/malformed inputs without 500).
8. Strict mass-assignment protection on AssetCriticalityAssessment (composite_score, abc_rating, status, approval).
9. Specification template target validation (category or model required), slug attribute_key, numeric bounds, and regex pattern syntax compilation.
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.forms import (
    AssetCategoryForm,
    AssetCriticalityAssessmentForm,
    AssetModelForm,
    AssetSpecificationTemplateForm,
)
from apps.assets.models import (
    AssetCategory,
    AssetCriticalityAssessment,
    AssetModel,
    AssetSpecificationTemplate,
)


def _assetclassification_category_payload(code="HVAC-AIR", name="Air Handling Units", **kwargs):
    """Generate valid base form payload for AssetCategoryForm."""
    payload = {
        "code": code,
        "name": name,
        "parent": "",
        "category_type": "facility",
        "unspsc_code": "40101701",
        "unspsc_title": "Air handlers",
        "default_depreciation_method": "straight_line",
        "default_useful_life_months": 96,
        "default_maintenance_strategy": "preventive_calendar",
        "default_criticality": "medium",
        "description": "Standard facility air handling units and ventilation systems.",
        "display_order": 20,
        "is_active": True,
    }
    payload.update(kwargs)
    return payload


def _assetclassification_model_payload(category, model_number="TRANE-CVHE-500", name="Trane CenTraVac Chiller", **kwargs):
    """Generate valid base form payload for AssetModelForm."""
    payload = {
        "model_number": model_number,
        "name": name,
        "category": category.pk if hasattr(category, "pk") else category,
        "manufacturer": "",
        "manufacturer_name_fallback": "Trane Commercial",
        "description": "Direct-drive centrifugal liquid chiller with adaptive controls.",
        "standard_warranty_months": 24,
        "warranty_coverage_type": "full_parts_labor",
        "expected_useful_life_months": 180,
        "default_meter_name": "Operating Hours",
        "default_meter_unit": "h",
        "estimated_replacement_cost": "250000.00",
        "model_status": "active",
        "technical_specifications": "Capacity: 500 Tons; Refrigerant: R-1233zd(E); Voltage: 480V 3Ph 60Hz",
        "is_active": True,
    }
    payload.update(kwargs)
    return payload


def _assetclassification_criticality_payload(asset, assessor, title="Annual Criticality Review", **kwargs):
    """Generate valid base form payload for AssetCriticalityAssessmentForm."""
    payload = {
        "title": title,
        "asset": asset.pk if hasattr(asset, "pk") else asset,
        "assessor": assessor.pk if hasattr(assessor, "pk") else assessor,
        "assessment_date": str(timezone.now().date()),
        "safety_impact": 4,
        "environmental_impact": 3,
        "operational_downtime_impact": 5,
        "financial_impact": 4,
        "regulatory_compliance_impact": 3,
        "is_single_point_of_failure": True,
        "recommended_strategy": "rcm_predictive",
        "review_cycle_months": 12,
        "next_assessment_due": str(timezone.now().date() + timezone.timedelta(days=365)),
        "findings_and_mitigation": "Primary line bottleneck asset. Vibration analysis recommended.",
    }
    payload.update(kwargs)
    return payload


def _assetclassification_spec_template_payload(**kwargs):
    """Generate valid base form payload for AssetSpecificationTemplateForm."""
    payload = {
        "attribute_key": "rated_operating_voltage",
        "display_name": "Rated Operating Voltage",
        "category": "",
        "model": "",
        "data_type": "number",
        "unit_of_measure": "V",
        "default_value": "480",
        "dropdown_options": "",
        "min_numeric_value": "380.000",
        "max_numeric_value": "480.000",
        "validation_regex": r"^[0-9]{3}$",
        "is_required": True,
        "is_filterable": True,
        "display_order": 10,
        "help_text": "Rated line-to-line operating AC voltage in Volts.",
    }
    payload.update(kwargs)
    return payload


# ==============================================================================
# 1. AssetCategoryForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_forms_category_create_valid(tenant_a, category_root_a):
    """AssetCategoryForm successfully creates a valid category with parent linkage."""
    data = _assetclassification_category_payload(
        code="hvac-vav",
        name="Variable Air Volume Boxes",
        parent=category_root_a.pk,
    )
    form = AssetCategoryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    category = form.save()
    assert category.pk is not None
    assert category.tenant == tenant_a
    assert category.parent == category_root_a
    assert category.code == "HVAC-VAV"
    assert category.name == "Variable Air Volume Boxes"
    assert category.default_useful_life_months == 96


@pytest.mark.django_db
def test_assetclassification_forms_category_update_valid(tenant_a, category_child_a):
    """AssetCategoryForm successfully updates an existing category instance."""
    data = _assetclassification_category_payload(
        code=category_child_a.code,
        name="Updated Centrifugal Chillers",
        parent=category_child_a.parent.pk,
        default_criticality="critical",
        display_order=99,
    )
    form = AssetCategoryForm(data=data, instance=category_child_a, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == category_child_a.pk
    assert updated.name == "Updated Centrifugal Chillers"
    assert updated.default_criticality == "critical"
    assert updated.display_order == 99


@pytest.mark.django_db
def test_assetclassification_forms_category_excludes_system_fields():
    """AssetCategoryForm strictly excludes tenant, number, created_at, and updated_at."""
    form = AssetCategoryForm()
    excluded_fields = ["tenant", "number", "created_at", "updated_at"]
    for field_name in excluded_fields:
        assert field_name not in form.fields
    assert excluded_fields == AssetCategoryForm.Meta.exclude


@pytest.mark.django_db
def test_assetclassification_forms_category_tenant_scoping_parent_queryset(tenant_a, tenant_b, category_root_a, category_root_b):
    """AssetCategoryForm scopes parent dropdown strictly to active categories of the tenant."""
    form = AssetCategoryForm(tenant=tenant_a)
    parent_qs = form.fields["parent"].queryset
    assert category_root_a in parent_qs
    assert category_root_b not in parent_qs

    # Inactive category should also be excluded
    inactive_cat = AssetCategory.objects.create(
        tenant=tenant_a,
        code="OBS-INACT",
        name="Obsolete Machinery",
        is_active=False,
    )
    form_refreshed = AssetCategoryForm(tenant=tenant_a)
    assert inactive_cat not in form_refreshed.fields["parent"].queryset


@pytest.mark.django_db
def test_assetclassification_forms_category_cycle_prevention_self_exclusion(tenant_a, category_root_a):
    """AssetCategoryForm excludes the edited instance itself from its parent queryset and rejects self as parent."""
    # When editing category_root_a, it cannot be its own parent
    form = AssetCategoryForm(instance=category_root_a, tenant=tenant_a)
    assert category_root_a not in form.fields["parent"].queryset

    # If submitted with self as parent, form fails validation
    data = _assetclassification_category_payload(
        code=category_root_a.code,
        name=category_root_a.name,
        parent=category_root_a.pk,
    )
    invalid_form = AssetCategoryForm(data=data, instance=category_root_a, tenant=tenant_a)
    assert not invalid_form.is_valid()
    assert "parent" in invalid_form.errors


@pytest.mark.django_db
def test_assetclassification_forms_category_rejects_cross_tenant_parent(tenant_a, tenant_b, category_root_b):
    """AssetCategoryForm rejects parent category belonging to another tenant."""
    data = _assetclassification_category_payload(
        code="ILLEGAL-CHILD",
        name="Illegal Child Category",
        parent=category_root_b.pk,
    )
    form = AssetCategoryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "parent" in form.errors


@pytest.mark.django_db
def test_assetclassification_forms_category_code_uppercase_cleaning(tenant_a):
    """AssetCategoryForm normalizes code to uppercase and strips surrounding whitespace."""
    data = _assetclassification_category_payload(
        code="  elec-xform-sub  ",
        name="Substation Transformers",
    )
    form = AssetCategoryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["code"] == "ELEC-XFORM-SUB"

    saved = form.save()
    assert saved.code == "ELEC-XFORM-SUB"


# ==============================================================================
# 2. AssetModelForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_forms_model_create_valid(tenant_a, category_root_a, vendor_party_a):
    """AssetModelForm successfully creates a valid equipment model."""
    data = _assetclassification_model_payload(
        category=category_root_a,
        model_number="  cummins-qsk60  ",
        name="Cummins QSK60 Diesel Generator",
        manufacturer=vendor_party_a.pk,
        estimated_replacement_cost="185000.00",
        standard_warranty_months=36,
    )
    form = AssetModelForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    model = form.save()
    assert model.pk is not None
    assert model.tenant == tenant_a
    assert model.category == category_root_a
    assert model.manufacturer == vendor_party_a
    assert model.model_number == "CUMMINS-QSK60"
    assert model.estimated_replacement_cost == Decimal("185000.00")


@pytest.mark.django_db
def test_assetclassification_forms_model_update_valid(tenant_a, asset_model_a, category_root_a):
    """AssetModelForm successfully updates an existing equipment model."""
    data = _assetclassification_model_payload(
        category=category_root_a,
        model_number=asset_model_a.model_number,
        name="Updated Excavator Blueprint",
        manufacturer=asset_model_a.manufacturer.pk if asset_model_a.manufacturer else "",
        model_status="phased_out",
        estimated_replacement_cost="195000.50",
    )
    form = AssetModelForm(data=data, instance=asset_model_a, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == asset_model_a.pk
    assert updated.name == "Updated Excavator Blueprint"
    assert updated.model_status == "phased_out"
    assert updated.estimated_replacement_cost == Decimal("195000.50")


@pytest.mark.django_db
def test_assetclassification_forms_model_excludes_system_fields():
    """AssetModelForm strictly excludes tenant, number, created_at, and updated_at."""
    form = AssetModelForm()
    excluded_fields = ["tenant", "number", "created_at", "updated_at"]
    for field_name in excluded_fields:
        assert field_name not in form.fields
    assert excluded_fields == AssetModelForm.Meta.exclude


@pytest.mark.django_db
def test_assetclassification_forms_model_tenant_scoping_querysets(tenant_a, tenant_b, category_root_a, category_root_b, vendor_party_a, vendor_party_b):
    """AssetModelForm scopes category and manufacturer dropdown querysets strictly to tenant."""
    form = AssetModelForm(tenant=tenant_a)

    cat_qs = form.fields["category"].queryset
    assert category_root_a in cat_qs
    assert category_root_b not in cat_qs

    mfr_qs = form.fields["manufacturer"].queryset
    assert vendor_party_a in mfr_qs
    assert vendor_party_b not in mfr_qs


@pytest.mark.django_db
def test_assetclassification_forms_model_rejects_cross_tenant_category(tenant_a, category_root_b):
    """AssetModelForm rejects category belonging to another tenant."""
    data = _assetclassification_model_payload(
        category=category_root_b,
        model_number="CROSS-CAT-01",
        name="Cross-Tenant Category Model",
    )
    form = AssetModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "category" in form.errors


@pytest.mark.django_db
def test_assetclassification_forms_model_rejects_cross_tenant_manufacturer(tenant_a, category_root_a, vendor_party_b):
    """AssetModelForm rejects manufacturer party belonging to another tenant."""
    data = _assetclassification_model_payload(
        category=category_root_a,
        model_number="CROSS-MFR-01",
        name="Cross-Tenant Manufacturer Model",
        manufacturer=vendor_party_b.pk,
    )
    form = AssetModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "manufacturer" in form.errors


@pytest.mark.django_db
def test_assetclassification_forms_model_validates_non_negative_replacement_cost(tenant_a, category_root_a):
    """AssetModelForm rejects negative estimated replacement cost."""
    data = _assetclassification_model_payload(
        category=category_root_a,
        model_number="NEG-COST-01",
        name="Negative Cost Model",
        estimated_replacement_cost="-500.00",
    )
    form = AssetModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "estimated_replacement_cost" in form.errors


@pytest.mark.django_db
def test_assetclassification_forms_model_model_number_cleaning(tenant_a, category_root_a):
    """AssetModelForm strips whitespace and uppercases model_number."""
    data = _assetclassification_model_payload(
        category=category_root_a,
        model_number="  honda-gx390-gen  ",
        name="Honda GX390 Engine",
    )
    form = AssetModelForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["model_number"] == "HONDA-GX390-GEN"


# ==============================================================================
# 3. AssetCriticalityAssessmentForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_forms_criticality_create_valid(tenant_a, operational_asset_a, vendor_party_a):
    """AssetCriticalityAssessmentForm validates clean assessment data and persists record."""
    data = _assetclassification_criticality_payload(
        asset=operational_asset_a,
        assessor=vendor_party_a,
        title="Plant Chiller Unit 1 Assessment",
        safety_impact=5,
        environmental_impact=4,
        operational_downtime_impact=5,
        financial_impact=4,
        regulatory_compliance_impact=3,
        is_single_point_of_failure=True,
    )
    form = AssetCriticalityAssessmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    assessment = form.save()
    assert assessment.pk is not None
    assert assessment.tenant == tenant_a
    assert assessment.asset == operational_asset_a
    assert assessment.assessor == vendor_party_a
    assert assessment.safety_impact == 5
    assert assessment.is_single_point_of_failure is True
    # Assessment status remains initial model default 'draft'
    assert assessment.assessment_status == "draft"


@pytest.mark.django_db
def test_assetclassification_forms_criticality_update_valid(tenant_a, criticality_assessment_a):
    """AssetCriticalityAssessmentForm successfully updates an existing assessment."""
    data = _assetclassification_criticality_payload(
        asset=criticality_assessment_a.asset,
        assessor=criticality_assessment_a.assessor,
        title="Updated Annual CNC Review",
        safety_impact=2,
        environmental_impact=2,
        operational_downtime_impact=3,
        financial_impact=2,
        regulatory_compliance_impact=1,
        is_single_point_of_failure=False,
    )
    form = AssetCriticalityAssessmentForm(data=data, instance=criticality_assessment_a, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == criticality_assessment_a.pk
    assert updated.title == "Updated Annual CNC Review"
    assert updated.safety_impact == 2
    assert updated.is_single_point_of_failure is False


@pytest.mark.django_db
def test_assetclassification_forms_criticality_strict_mass_assignment_exclusion():
    """AssetCriticalityAssessmentForm strictly excludes calculated & workflow fields from Meta.fields."""
    form = AssetCriticalityAssessmentForm()
    strictly_excluded = [
        "composite_score",
        "abc_rating",
        "assessment_status",
        "approved_by",
        "approved_at",
        "tenant",
        "number",
        "created_at",
        "updated_at",
    ]
    for field_name in strictly_excluded:
        assert field_name not in form.fields
        assert field_name not in AssetCriticalityAssessmentForm.Meta.fields
        assert field_name in AssetCriticalityAssessmentForm.Meta.exclude


@pytest.mark.django_db
def test_assetclassification_forms_criticality_tenant_scoping_querysets(tenant_a, tenant_b, operational_asset_a, operational_asset_b, vendor_party_a, vendor_party_b):
    """AssetCriticalityAssessmentForm scopes asset and assessor dropdown querysets to tenant."""
    form = AssetCriticalityAssessmentForm(tenant=tenant_a)

    asset_qs = form.fields["asset"].queryset
    assert operational_asset_a in asset_qs
    assert operational_asset_b not in asset_qs

    assessor_qs = form.fields["assessor"].queryset
    assert vendor_party_a in assessor_qs
    assert vendor_party_b not in assessor_qs


@pytest.mark.django_db
def test_assetclassification_forms_criticality_rejects_cross_tenant_asset(tenant_a, operational_asset_b, vendor_party_a):
    """AssetCriticalityAssessmentForm rejects asset belonging to another tenant."""
    data = _assetclassification_criticality_payload(
        asset=operational_asset_b,
        assessor=vendor_party_a,
        title="Illegal Cross-Tenant Asset Review",
    )
    form = AssetCriticalityAssessmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors


@pytest.mark.django_db
def test_assetclassification_forms_criticality_rejects_cross_tenant_assessor(tenant_a, operational_asset_a, vendor_party_b):
    """AssetCriticalityAssessmentForm rejects assessor belonging to another tenant."""
    data = _assetclassification_criticality_payload(
        asset=operational_asset_a,
        assessor=vendor_party_b,
        title="Illegal Cross-Tenant Assessor Review",
    )
    form = AssetCriticalityAssessmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "assessor" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("fld", [
    "safety_impact",
    "environmental_impact",
    "operational_downtime_impact",
    "financial_impact",
    "regulatory_compliance_impact",
])
def test_assetclassification_forms_criticality_score_range_validation(tenant_a, operational_asset_a, vendor_party_a, fld):
    """AssetCriticalityAssessmentForm rejects consequence scores below 1 or above 5."""
    # Score 0 (below 1)
    data_low = _assetclassification_criticality_payload(
        asset=operational_asset_a,
        assessor=vendor_party_a,
        **{fld: 0},
    )
    form_low = AssetCriticalityAssessmentForm(data=data_low, tenant=tenant_a)
    assert not form_low.is_valid()
    assert fld in form_low.errors

    # Score 6 (above 5)
    data_high = _assetclassification_criticality_payload(
        asset=operational_asset_a,
        assessor=vendor_party_a,
        **{fld: 6},
    )
    form_high = AssetCriticalityAssessmentForm(data=data_high, tenant=tenant_a)
    assert not form_high.is_valid()
    assert fld in form_high.errors


@pytest.mark.django_db
@pytest.mark.parametrize("fld", [
    "safety_impact",
    "environmental_impact",
    "operational_downtime_impact",
    "financial_impact",
    "regulatory_compliance_impact",
])
def test_assetclassification_forms_criticality_malformed_scores_no_500(tenant_a, operational_asset_a, vendor_party_a, fld):
    """AssetCriticalityAssessmentForm cleanly handles negative and non-numeric inputs without ValueError 500."""
    # Negative number
    data_neg = _assetclassification_criticality_payload(
        asset=operational_asset_a,
        assessor=vendor_party_a,
        **{fld: -3},
    )
    form_neg = AssetCriticalityAssessmentForm(data=data_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert fld in form_neg.errors

    # Malformed non-numeric string
    data_str = _assetclassification_criticality_payload(
        asset=operational_asset_a,
        assessor=vendor_party_a,
        **{fld: "not_a_valid_number"},
    )
    form_str = AssetCriticalityAssessmentForm(data=data_str, tenant=tenant_a)
    assert not form_str.is_valid()
    assert fld in form_str.errors


# ==============================================================================
# 4. AssetSpecificationTemplateForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_create_with_category_valid(tenant_a, category_root_a):
    """AssetSpecificationTemplateForm successfully creates a template attached to an AssetCategory."""
    data = _assetclassification_spec_template_payload(
        attribute_key="max_ambient_temp_c",
        display_name="Maximum Ambient Operating Temperature",
        category=category_root_a.pk,
        model="",
        data_type="number",
        unit_of_measure="degC",
        min_numeric_value="-20.000",
        max_numeric_value="55.000",
        validation_regex="",
    )
    form = AssetSpecificationTemplateForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    tpl = form.save()
    assert tpl.pk is not None
    assert tpl.tenant == tenant_a
    assert tpl.category == category_root_a
    assert tpl.model is None
    assert tpl.attribute_key == "max_ambient_temp_c"
    assert tpl.min_numeric_value == Decimal("-20.000")
    assert tpl.max_numeric_value == Decimal("55.000")


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_create_with_model_valid(tenant_a, asset_model_a):
    """AssetSpecificationTemplateForm successfully creates a template attached to an AssetModel."""
    data = _assetclassification_spec_template_payload(
        attribute_key="hydraulic_oil_type",
        display_name="Hydraulic Fluid Grade",
        category="",
        model=asset_model_a.pk,
        data_type="select",
        unit_of_measure="",
        dropdown_options="ISO VG 46, ISO VG 68, ISO VG 100",
        min_numeric_value="",
        max_numeric_value="",
        validation_regex="",
    )
    form = AssetSpecificationTemplateForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    tpl = form.save()
    assert tpl.pk is not None
    assert tpl.tenant == tenant_a
    assert tpl.category is None
    assert tpl.model == asset_model_a
    assert tpl.attribute_key == "hydraulic_oil_type"
    assert tpl.data_type == "select"
    assert "ISO VG 46" in tpl.dropdown_options


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_update_valid(tenant_a, spec_template_a):
    """AssetSpecificationTemplateForm successfully updates an existing specification template."""
    data = _assetclassification_spec_template_payload(
        attribute_key=spec_template_a.attribute_key,
        display_name="Updated Operating Voltage AC",
        category=spec_template_a.category.pk if spec_template_a.category else "",
        model=spec_template_a.model.pk if spec_template_a.model else "",
        min_numeric_value="360.000",
        max_numeric_value="500.000",
        validation_regex="",
    )
    form = AssetSpecificationTemplateForm(data=data, instance=spec_template_a, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == spec_template_a.pk
    assert updated.display_name == "Updated Operating Voltage AC"
    assert updated.min_numeric_value == Decimal("360.000")
    assert updated.max_numeric_value == Decimal("500.000")


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_excludes_system_fields():
    """AssetSpecificationTemplateForm strictly excludes tenant, number, created_at, and updated_at."""
    form = AssetSpecificationTemplateForm()
    excluded_fields = ["tenant", "number", "created_at", "updated_at"]
    for field_name in excluded_fields:
        assert field_name not in form.fields
    assert excluded_fields == AssetSpecificationTemplateForm.Meta.exclude


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_tenant_scoping_querysets(tenant_a, tenant_b, category_root_a, category_root_b, asset_model_a, asset_model_b):
    """AssetSpecificationTemplateForm scopes category and model dropdown querysets to tenant."""
    form = AssetSpecificationTemplateForm(tenant=tenant_a)

    cat_qs = form.fields["category"].queryset
    assert category_root_a in cat_qs
    assert category_root_b not in cat_qs

    mod_qs = form.fields["model"].queryset
    assert asset_model_a in mod_qs
    assert asset_model_b not in mod_qs


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_requires_category_or_model(tenant_a):
    """AssetSpecificationTemplateForm rejects submission when neither category nor model is selected."""
    data = _assetclassification_spec_template_payload(
        category="",
        model="",
        attribute_key="floating_attribute",
        display_name="Floating Attribute",
        validation_regex="",
    )
    form = AssetSpecificationTemplateForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "category" in form.errors


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_slug_attribute_key_validation(tenant_a, category_root_a):
    """AssetSpecificationTemplateForm validates snake_case slug attribute_key format and normalizes case."""
    # Invalid characters (spaces, hyphens, symbols, punctuation)
    invalid_keys = [
        "Rated Operating Voltage",
        "rated-voltage-ac",
        "power@rating",
        "voltage (vac)!",
        "flow.rate",
    ]
    for key in invalid_keys:
        data = _assetclassification_spec_template_payload(
            category=category_root_a.pk,
            attribute_key=key,
            validation_regex="",
        )
        form = AssetSpecificationTemplateForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Expected {key} to be rejected"
        assert "attribute_key" in form.errors

    # Valid snake_case key with uppercase / whitespace gets normalized to lowercase snake_case
    valid_data = _assetclassification_spec_template_payload(
        category=category_root_a.pk,
        attribute_key="  OPERATING_VOLTAGE_VAC  ",
        validation_regex="",
    )
    valid_form = AssetSpecificationTemplateForm(data=valid_data, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors
    saved = valid_form.save()
    assert saved.attribute_key == "operating_voltage_vac"


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_numeric_bounds_validation(tenant_a, category_root_a):
    """AssetSpecificationTemplateForm rejects cases where min_numeric_value exceeds max_numeric_value."""
    data = _assetclassification_spec_template_payload(
        category=category_root_a.pk,
        attribute_key="reversed_bounds_attr",
        min_numeric_value="500.000",
        max_numeric_value="100.000",
        validation_regex="",
    )
    form = AssetSpecificationTemplateForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "min_numeric_value" in form.errors


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_regex_syntax_compilation(tenant_a, category_root_a):
    """AssetSpecificationTemplateForm compiles regex pattern and rejects invalid regex syntax."""
    # Invalid regex syntax
    data_invalid = _assetclassification_spec_template_payload(
        category=category_root_a.pk,
        attribute_key="regex_test_attr",
        validation_regex=r"^[0-9]+([a-z",  # unclosed parenthesis
    )
    form_invalid = AssetSpecificationTemplateForm(data=data_invalid, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "validation_regex" in form_invalid.errors

    # Valid regex syntax
    data_valid = _assetclassification_spec_template_payload(
        category=category_root_a.pk,
        attribute_key="regex_valid_attr",
        validation_regex=r"^[A-Z]{3}-[0-9]{4}$",
    )
    form_valid = AssetSpecificationTemplateForm(data=data_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_rejects_cross_tenant_category(tenant_a, category_root_b):
    """AssetSpecificationTemplateForm rejects category belonging to another tenant."""
    data = _assetclassification_spec_template_payload(
        category=category_root_b.pk,
        attribute_key="cross_ten_cat_attr",
        validation_regex="",
    )
    form = AssetSpecificationTemplateForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "category" in form.errors


@pytest.mark.django_db
def test_assetclassification_forms_spec_template_rejects_cross_tenant_model(tenant_a, asset_model_b):
    """AssetSpecificationTemplateForm rejects model belonging to another tenant."""
    data = _assetclassification_spec_template_payload(
        model=asset_model_b.pk,
        attribute_key="cross_ten_mod_attr",
        validation_regex="",
    )
    form = AssetSpecificationTemplateForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "model" in form.errors
