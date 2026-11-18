"""Unit and validation tests for Module 12.7 Incoming Quality Control forms.

Target forms:
- IncomingInspectionPlanForm
- IncomingInspectionLotForm
- CertificateOfAnalysisForm
- QualityReturnAuthorizationForm

All test functions follow the prefix rule: test_incomingquality_forms_*
All helper functions follow the prefix rule: _incomingquality_forms_*
"""

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import OrgUnit, Party, PartyRole
from apps.quality.forms import (
    CertificateOfAnalysisForm,
    IncomingInspectionLotForm,
    IncomingInspectionPlanForm,
    QualityReturnAuthorizationForm,
)
from apps.quality.forms._common import reject_foreign
from apps.quality.models import (
    CertificateOfAnalysis,
    ControlledDocument,
    IncomingInspectionLot,
    IncomingInspectionPlan,
    NonConformanceReport,
    ProcessDeviation,
    QualityReturnAuthorization,
    QuarantineContainment,
    SupplierCorrectiveAction,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _incomingquality_forms_*)
# =============================================================================

def _incomingquality_forms_pk(val):
    """Return pk if val is a model instance, or val itself if scalar / None."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _incomingquality_forms_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _incomingquality_forms_plan_base_data(supplier=None, doc=None, team=None, **extra):
    """Build valid baseline POST dictionary for IncomingInspectionPlanForm."""
    data = {
        "title": "Titanium Rods IQC Plan",
        "item_code": "TI-ROD-01",
        "item_name": "Medical Grade Titanium Rod 10mm",
        "revision": "A",
        "supplier": _incomingquality_forms_pk(supplier) if supplier else "",
        "sampling_standard": "ansi_asq_z14",
        "inspection_level": "level_2",
        "inspection_severity": "normal",
        "inspection_frequency": "every_lot",
        "skip_lot_interval": 5,
        "aql_critical": "0.00",
        "aql_major": "1.00",
        "aql_minor": "4.00",
        "requires_coa": True,
        "requires_coc": False,
        "status": "active",
        "sop_document": _incomingquality_forms_pk(doc) if doc else "",
        "assigned_team": _incomingquality_forms_pk(team) if team else "",
        "characteristics_json": json.dumps([
            {"name": "Diameter", "type": "variable", "target": 10.0, "lsl": 9.95, "usl": 10.05, "unit": "mm"}
        ]),
        "notes": "Incoming inspection requirements per ISO 13485.",
    }
    data.update(extra)
    return data


def _incomingquality_forms_lot_base_data(plan, supplier, inspector=None, decided_by=None, **extra):
    """Build valid baseline POST dictionary for IncomingInspectionLotForm."""
    data = {
        "inspection_plan": _incomingquality_forms_pk(plan),
        "item_code": "TI-ROD-01",
        "item_name": "Medical Grade Titanium Rod 10mm",
        "supplier": _incomingquality_forms_pk(supplier),
        "purchase_order": "",
        "goods_receipt_note": "",
        "lot_number": "LOT-2026-IQC-0881",
        "heat_or_batch": "HEAT-9941",
        "receipt_date": _incomingquality_forms_date(-2),
        "inspection_date": _incomingquality_forms_date(0),
        "lot_quantity": "500.000",
        "sample_size": 32,
        "inspected_quantity": 32,
        "accepted_quantity": "500.000",
        "rejected_quantity": "0.000",
        "quarantine_quantity": "0.000",
        "critical_defects": 0,
        "major_defects": 0,
        "minor_defects": 0,
        "stage": "completed",
        "usage_decision": "accepted",
        "usage_decision_notes": "Conforms fully to critical dimensions.",
        "decided_by": _incomingquality_forms_pk(decided_by) if decided_by else "",
        "inspector": _incomingquality_forms_pk(inspector) if inspector else "",
        "linked_ncr": "",
        "linked_deviation": "",
        "linked_containment": "",
        "linked_scar": "",
        "measurements_json": json.dumps([
            {"sample_no": 1, "characteristic": "Diameter", "value": 10.001, "is_pass": True},
            {"sample_no": 2, "characteristic": "Diameter", "value": 9.998, "is_pass": True},
        ]),
        "notes": "ANSI Z1.4 Level II normal inspection executed.",
    }
    data.update(extra)
    return data


def _incomingquality_forms_coa_base_data(supplier, plan=None, lot=None, doc=None, **extra):
    """Build valid baseline POST dictionary for CertificateOfAnalysisForm."""
    data = {
        "certificate_number": "COA-VND-2026-9921",
        "supplier": _incomingquality_forms_pk(supplier),
        "item_code": "TI-ROD-01",
        "item_name": "Medical Grade Titanium Rod 10mm",
        "lot_number": "LOT-2026-IQC-0881",
        "inspection_lot": _incomingquality_forms_pk(lot) if lot else "",
        "inspection_plan": _incomingquality_forms_pk(plan) if plan else "",
        "manufacturer_name": "Precision Alloys Corp",
        "date_of_manufacture": _incomingquality_forms_date(-30),
        "expiry_or_retest_date": _incomingquality_forms_date(365),
        "lab_accreditation": "ISO/IEC 17025 Accredited Lab #441",
        "status": "received",
        "supporting_document": _incomingquality_forms_pk(doc) if doc else "",
        "parameters_json": json.dumps([
            {"parameter": "Tensile Strength", "lsl": 860.0, "usl": 950.0, "actual_value": 895.0, "unit": "MPa"}
        ]),
        "notes": "Verified against mill test report.",
    }
    data.update(extra)
    return data


def _incomingquality_forms_rma_base_data(lot, supplier, coordinator=None, **extra):
    """Build valid baseline POST dictionary for QualityReturnAuthorizationForm."""
    data = {
        "inspection_lot": _incomingquality_forms_pk(lot),
        "supplier": _incomingquality_forms_pk(supplier),
        "vendor_rma_number": "VRMA-2026-1188",
        "return_reason": "dimensional_oos",
        "disposition_type": "return_for_credit",
        "return_quantity": "50.000",
        "unit_of_measure": "EA",
        "estimated_credit_value": "1250.00",
        "status": "rma_requested",
        "carrier": "FedEx Freight",
        "tracking_number": "7849 2011 8841",
        "bill_of_lading": "BOL-99410",
        "shipped_date": _incomingquality_forms_date(2),
        "vendor_receipt_date": _incomingquality_forms_date(6),
        "debit_memo_number": "DM-2026-041",
        "settled_amount": "1250.00",
        "settlement_date": _incomingquality_forms_date(10),
        "assigned_coordinator": _incomingquality_forms_pk(coordinator) if coordinator else "",
        "linked_ncr": "",
        "linked_scar": "",
        "notes": "Parts rejected during incoming dimensional verification.",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. IncomingInspectionPlanForm Tests
# =============================================================================

def test_incomingquality_forms_plan_init_without_tenant():
    """Verify form initializes safely when tenant is None."""
    form = IncomingInspectionPlanForm()
    assert form.tenant is None
    assert "title" in form.fields
    assert "characteristics_json" in form.fields


def test_incomingquality_forms_plan_init_with_tenant(tenant_a, supplier_party_a, doc_a, quality_department):
    """Verify form initializes with tenant and populates scoped querysets."""
    form = IncomingInspectionPlanForm(tenant=tenant_a)
    assert form.tenant == tenant_a
    assert supplier_party_a in form.fields["supplier"].queryset
    assert doc_a in form.fields["sop_document"].queryset
    assert quality_department in form.fields["assigned_team"].queryset


def test_incomingquality_forms_plan_system_field_exclusions(tenant_a, supplier_party_a):
    """Verify tenant, number, timestamps, and characteristics_matrix are excluded."""
    form = IncomingInspectionPlanForm(tenant=tenant_a)
    for field in ["tenant", "number", "created_at", "updated_at", "characteristics_matrix"]:
        assert field not in form.fields

    # Attempting to inject system fields via POST data must be ignored
    data = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        tenant=tenant_a.pk,
        number="QIIP-MALICIOUS-999",
        created_at=_incomingquality_forms_date(-50),
    )
    bound_form = IncomingInspectionPlanForm(data=data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert instance.number != "QIIP-MALICIOUS-999"


def test_incomingquality_forms_plan_tenant_scoping_supplier_roles_and_distinct(
    tenant_a, tenant_b, supplier_party_a, supplier_party_b
):
    """Verify supplier queryset includes only tenant suppliers with supplier/vendor role and distinct."""
    # Party with customer role only in Tenant A
    customer = Party.objects.create(tenant=tenant_a, name="Acme Customer Corp", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=customer, role="customer")

    # Party with both vendor and supplier roles in Tenant A
    multi_role_supplier = Party.objects.create(tenant=tenant_a, name="Dual Role Vendor", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=multi_role_supplier, role="supplier")
    PartyRole.objects.create(tenant=tenant_a, party=multi_role_supplier, role="vendor")

    form = IncomingInspectionPlanForm(tenant=tenant_a)
    qs = form.fields["supplier"].queryset

    assert supplier_party_a in qs
    assert multi_role_supplier in qs
    assert customer not in qs
    assert supplier_party_b not in qs
    # Check that multi_role_supplier is not duplicated
    supplier_ids = list(qs.values_list("id", flat=True))
    assert supplier_ids.count(multi_role_supplier.id) == 1


def test_incomingquality_forms_plan_tenant_scoping_sop_doc_and_orgunit(
    tenant_a, doc_a, doc_b, quality_department, quality_department_b
):
    """Verify sop_document and assigned_team are strictly scoped to tenant."""
    form = IncomingInspectionPlanForm(tenant=tenant_a)
    sop_qs = form.fields["sop_document"].queryset
    team_qs = form.fields["assigned_team"].queryset

    assert doc_a in sop_qs
    assert doc_b not in sop_qs
    assert quality_department in team_qs
    assert quality_department_b not in team_qs


def test_incomingquality_forms_plan_reject_foreign_cross_tenant(
    tenant_a, supplier_party_b, doc_b, quality_department_b
):
    """Submitting foreign keys from Tenant B to Tenant A form must trigger validation errors and reject_foreign."""
    data = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_b,
        doc=doc_b,
        team=quality_department_b,
    )
    form = IncomingInspectionPlanForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "supplier" in form.errors
    assert "sop_document" in form.errors
    assert "assigned_team" in form.errors

    # Verify reject_foreign directly adds the specific workspace isolation message
    direct_form = IncomingInspectionPlanForm(tenant=tenant_a)
    direct_form.cleaned_data = {
        "supplier": supplier_party_b,
        "sop_document": doc_b,
        "assigned_team": quality_department_b,
    }
    reject_foreign(direct_form, direct_form.cleaned_data, ["supplier", "sop_document", "assigned_team"])
    assert "That record belongs to another workspace." in direct_form.errors["supplier"][0]
    assert "That record belongs to another workspace." in direct_form.errors["sop_document"][0]
    assert "That record belongs to another workspace." in direct_form.errors["assigned_team"][0]


def test_incomingquality_forms_plan_characteristics_json_valid_list(tenant_a, supplier_party_a):
    """Verify valid JSON array is parsed into cleaned_data and saved to characteristics_matrix."""
    payload = [
        {"name": "Outside Diameter", "type": "variable", "lsl": 9.9, "usl": 10.1, "unit": "mm"},
        {"name": "Surface Flaws", "type": "attribute", "acceptance_criteria": "Zero cracks"},
    ]
    data = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        characteristics_json=json.dumps(payload),
    )
    form = IncomingInspectionPlanForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["characteristics_json"] == payload

    instance = form.save(commit=True)
    assert instance.characteristics_matrix == payload


def test_incomingquality_forms_plan_characteristics_json_empty(tenant_a, supplier_party_a):
    """Verify empty or whitespace characteristics_json parses to empty list."""
    data = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        characteristics_json="   ",
    )
    form = IncomingInspectionPlanForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["characteristics_json"] == []

    instance = form.save(commit=True)
    assert instance.characteristics_matrix == []


def test_incomingquality_forms_plan_characteristics_json_invalid_syntax(tenant_a, supplier_party_a):
    """Verify malformed JSON raises validation error."""
    data = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        characteristics_json='{"invalid_json": [missing_bracket}',
    )
    form = IncomingInspectionPlanForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "characteristics_json" in form.errors
    assert "Invalid JSON:" in form.errors["characteristics_json"][0]


def test_incomingquality_forms_plan_characteristics_json_non_list(tenant_a, supplier_party_a):
    """Verify JSON object or primitive (not list) raises validation error."""
    invalid_payloads = [
        json.dumps({"name": "Single Characteristic"}),
        json.dumps("Just a string"),
        json.dumps(12345),
    ]
    for raw in invalid_payloads:
        data = _incomingquality_forms_plan_base_data(
            supplier=supplier_party_a,
            characteristics_json=raw,
        )
        form = IncomingInspectionPlanForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "characteristics_json" in form.errors
        assert "Characteristics must be a JSON array of characteristic objects." in form.errors["characteristics_json"][0]


def test_incomingquality_forms_plan_initial_characteristics_json_from_instance(tenant_a, incoming_plan_a):
    """Verify initial value of characteristics_json is formatted from instance matrix."""
    form = IncomingInspectionPlanForm(instance=incoming_plan_a, tenant=tenant_a)
    initial_val = form.fields["characteristics_json"].initial
    assert initial_val is not None
    parsed = json.loads(initial_val)
    assert parsed == incoming_plan_a.characteristics_matrix


def test_incomingquality_forms_plan_aql_negative_validation(tenant_a, supplier_party_a):
    """Negative AQL values must trigger field errors."""
    # Negative critical
    data1 = _incomingquality_forms_plan_base_data(supplier=supplier_party_a, aql_critical="-0.50")
    f1 = IncomingInspectionPlanForm(data=data1, tenant=tenant_a)
    assert not f1.is_valid()
    assert "Critical AQL cannot be negative." in f1.errors["aql_critical"][0]

    # Negative major
    data2 = _incomingquality_forms_plan_base_data(supplier=supplier_party_a, aql_major="-1.00")
    f2 = IncomingInspectionPlanForm(data=data2, tenant=tenant_a)
    assert not f2.is_valid()
    assert "Major AQL cannot be negative." in f2.errors["aql_major"][0]

    # Negative minor
    data3 = _incomingquality_forms_plan_base_data(supplier=supplier_party_a, aql_minor="-2.00")
    f3 = IncomingInspectionPlanForm(data=data3, tenant=tenant_a)
    assert not f3.is_valid()
    assert "Minor AQL cannot be negative." in f3.errors["aql_minor"][0]


def test_incomingquality_forms_plan_aql_hierarchy_validation(tenant_a, supplier_party_a):
    """AQL hierarchy invariant: Critical <= Major <= Minor."""
    # Critical exceeds Major
    data1 = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        aql_critical="2.50",
        aql_major="1.00",
        aql_minor="4.00",
    )
    f1 = IncomingInspectionPlanForm(data=data1, tenant=tenant_a)
    assert not f1.is_valid()
    assert "Critical AQL must not exceed Major AQL." in f1.errors["aql_critical"][0]

    # Major exceeds Minor
    data2 = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        aql_critical="0.65",
        aql_major="6.50",
        aql_minor="4.00",
    )
    f2 = IncomingInspectionPlanForm(data=data2, tenant=tenant_a)
    assert not f2.is_valid()
    assert "Major AQL must not exceed Minor AQL." in f2.errors["aql_major"][0]

    # Equal AQL is valid
    data3 = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        aql_critical="1.00",
        aql_major="1.00",
        aql_minor="1.00",
    )
    f3 = IncomingInspectionPlanForm(data=data3, tenant=tenant_a)
    assert f3.is_valid(), f3.errors


def test_incomingquality_forms_plan_missing_required_fields(tenant_a):
    """Submitting empty dictionary must trigger required field validations."""
    form = IncomingInspectionPlanForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "item_code" in form.errors
    assert "item_name" in form.errors


def test_incomingquality_forms_plan_valid_submission_creates_and_updates(
    tenant_a, supplier_party_a, doc_a, quality_department, incoming_plan_a
):
    """Verify valid submission creates new record and updates existing record."""
    # Create new
    create_data = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        doc=doc_a,
        team=quality_department,
        title="Custom Bar Stock IQC Plan",
        item_code="BAR-STL-099",
    )
    create_form = IncomingInspectionPlanForm(data=create_data, tenant=tenant_a)
    assert create_form.is_valid(), create_form.errors
    plan = create_form.save()
    assert plan.pk is not None
    assert plan.tenant == tenant_a
    assert plan.number.startswith("QIIP-")
    assert plan.title == "Custom Bar Stock IQC Plan"

    # Update existing
    update_data = _incomingquality_forms_plan_base_data(
        supplier=supplier_party_a,
        doc=doc_a,
        team=quality_department,
        title="Updated Titanium Plan Title",
        item_code="TI-ROD-01",
        revision="B",
    )
    update_form = IncomingInspectionPlanForm(data=update_data, instance=incoming_plan_a, tenant=tenant_a)
    assert update_form.is_valid(), update_form.errors
    updated_plan = update_form.save()
    assert updated_plan.pk == incoming_plan_a.pk
    assert updated_plan.title == "Updated Titanium Plan Title"
    assert updated_plan.revision == "B"


# =============================================================================
# 2. IncomingInspectionLotForm Tests
# =============================================================================

def test_incomingquality_forms_lot_init_without_tenant():
    """Verify lot form initializes cleanly when tenant is None."""
    form = IncomingInspectionLotForm()
    assert form.tenant is None
    assert "inspection_plan" in form.fields
    assert "measurements_json" in form.fields


def test_incomingquality_forms_lot_init_with_tenant(
    tenant_a, incoming_plan_a, supplier_party_a, admin_user
):
    """Verify lot form initializes with tenant and populates scoped querysets."""
    form = IncomingInspectionLotForm(tenant=tenant_a)
    assert form.tenant == tenant_a
    assert incoming_plan_a in form.fields["inspection_plan"].queryset
    assert supplier_party_a in form.fields["supplier"].queryset
    assert admin_user in form.fields["decided_by"].queryset
    assert admin_user in form.fields["inspector"].queryset


def test_incomingquality_forms_lot_system_field_exclusions(tenant_a, incoming_plan_a, supplier_party_a):
    """Verify tenant, number, timestamps, and spc fields are strictly excluded."""
    form = IncomingInspectionLotForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "measurements_data",
        "spc_mean",
        "spc_std_dev",
        "spc_cp",
        "spc_cpk",
        "spc_out_of_control",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from lot form"

    # Malicious injection in POST data
    data = _incomingquality_forms_lot_base_data(
        incoming_plan_a,
        supplier_party_a,
        spc_mean="99.999",
        spc_cpk="3.50",
        number="QIIL-HACK-000",
    )
    bound_form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert instance.number != "QIIL-HACK-000"


def test_incomingquality_forms_lot_tenant_scoping_users_active_only(tenant_a, tenant_b, admin_user, admin_b):
    """Verify decided_by and inspector only include active users from tenant."""
    inactive_inspector = User.objects.create_user(
        username="inactive_inspector_a",
        email="inactive_insp@acme.com",
        password="TestPass123!",
        tenant=tenant_a,
        is_active=False,
    )

    form = IncomingInspectionLotForm(tenant=tenant_a)
    decided_qs = form.fields["decided_by"].queryset
    inspector_qs = form.fields["inspector"].queryset

    assert admin_user in decided_qs
    assert admin_user in inspector_qs
    assert inactive_inspector not in decided_qs
    assert inactive_inspector not in inspector_qs
    assert admin_b not in decided_qs
    assert admin_b not in inspector_qs


def test_incomingquality_forms_lot_tenant_scoping_inspection_plan(tenant_a, incoming_plan_a, incoming_plan_b):
    """Verify inspection_plan queryset is strictly scoped to tenant."""
    form = IncomingInspectionLotForm(tenant=tenant_a)
    qs = form.fields["inspection_plan"].queryset
    assert incoming_plan_a in qs
    assert incoming_plan_b not in qs


def test_incomingquality_forms_lot_tenant_scoping_supplier_and_links(
    tenant_a,
    supplier_party_a,
    supplier_party_b,
    ncr_a,
    ncr_b,
    process_deviation_a,
    process_deviation_b,
    quarantine_a,
    quarantine_b,
    scar_a,
    scar_b,
):
    """Verify supplier and linked quality records are strictly scoped to tenant."""
    form = IncomingInspectionLotForm(tenant=tenant_a)
    assert supplier_party_a in form.fields["supplier"].queryset
    assert supplier_party_b not in form.fields["supplier"].queryset
    assert ncr_a in form.fields["linked_ncr"].queryset
    assert ncr_b not in form.fields["linked_ncr"].queryset
    assert process_deviation_a in form.fields["linked_deviation"].queryset
    assert process_deviation_b not in form.fields["linked_deviation"].queryset
    assert quarantine_a in form.fields["linked_containment"].queryset
    assert quarantine_b not in form.fields["linked_containment"].queryset
    assert scar_a in form.fields["linked_scar"].queryset
    assert scar_b not in form.fields["linked_scar"].queryset


def test_incomingquality_forms_lot_reject_foreign_cross_tenant(
    tenant_a,
    incoming_plan_b,
    supplier_party_b,
    admin_b,
    ncr_b,
    process_deviation_b,
    quarantine_b,
    scar_b,
):
    """Submitting Tenant B foreign keys to Tenant A lot form must trigger validation and reject_foreign."""
    data = _incomingquality_forms_lot_base_data(
        plan=incoming_plan_b,
        supplier=supplier_party_b,
        inspector=admin_b,
        decided_by=admin_b,
        linked_ncr=_incomingquality_forms_pk(ncr_b),
        linked_deviation=_incomingquality_forms_pk(process_deviation_b),
        linked_containment=_incomingquality_forms_pk(quarantine_b),
        linked_scar=_incomingquality_forms_pk(scar_b),
    )
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    fields_to_check = [
        "inspection_plan",
        "supplier",
        "inspector",
        "decided_by",
        "linked_ncr",
        "linked_deviation",
        "linked_containment",
        "linked_scar",
    ]
    for field in fields_to_check:
        assert field in form.errors

    # Verify reject_foreign directly adds the specific workspace isolation message
    direct_form = IncomingInspectionLotForm(tenant=tenant_a)
    direct_form.cleaned_data = {
        "inspection_plan": incoming_plan_b,
        "supplier": supplier_party_b,
        "inspector": admin_b,
        "decided_by": admin_b,
        "linked_ncr": ncr_b,
        "linked_deviation": process_deviation_b,
        "linked_containment": quarantine_b,
        "linked_scar": scar_b,
    }
    reject_foreign(direct_form, direct_form.cleaned_data, fields_to_check)
    for field in fields_to_check:
        assert "That record belongs to another workspace." in direct_form.errors[field][0]


def test_incomingquality_forms_lot_measurements_json_valid_and_spc_recalculated(
    tenant_a, incoming_plan_a, supplier_party_a, admin_user
):
    """Submitting valid measurements JSON parses and triggers recalculate_spc() on save."""
    # Set characteristic spec on plan to enable Cpk computation
    incoming_plan_a.characteristics_matrix = [
        {"name": "Diameter", "type": "variable", "target": 10.0, "lsl": 9.90, "usl": 10.10, "unit": "mm"}
    ]
    incoming_plan_a.save()

    measurements = [
        {"sample_no": 1, "characteristic": "Diameter", "value": 10.01, "is_pass": True},
        {"sample_no": 2, "characteristic": "Diameter", "value": 10.02, "is_pass": True},
        {"sample_no": 3, "characteristic": "Diameter", "value": 9.99, "is_pass": True},
        {"sample_no": 4, "characteristic": "Diameter", "value": 10.00, "is_pass": True},
    ]
    data = _incomingquality_forms_lot_base_data(
        incoming_plan_a,
        supplier_party_a,
        inspector=admin_user,
        decided_by=admin_user,
        measurements_json=json.dumps(measurements),
    )
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["measurements_json"] == measurements

    lot = form.save(commit=True)
    assert lot.measurements_data == measurements
    assert lot.spc_mean is not None
    assert lot.spc_std_dev is not None


def test_incomingquality_forms_lot_measurements_json_empty(tenant_a, incoming_plan_a, supplier_party_a):
    """Empty measurements_json parses to empty list."""
    data = _incomingquality_forms_lot_base_data(
        incoming_plan_a,
        supplier_party_a,
        measurements_json="   ",
    )
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["measurements_json"] == []


def test_incomingquality_forms_lot_measurements_json_invalid_syntax(tenant_a, incoming_plan_a, supplier_party_a):
    """Malformed measurements JSON raises validation error."""
    data = _incomingquality_forms_lot_base_data(
        incoming_plan_a,
        supplier_party_a,
        measurements_json="[unclosed: array",
    )
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "measurements_json" in form.errors
    assert "Invalid JSON:" in form.errors["measurements_json"][0]


def test_incomingquality_forms_lot_measurements_json_non_list(tenant_a, incoming_plan_a, supplier_party_a):
    """Non-list measurements JSON raises array validation error."""
    data = _incomingquality_forms_lot_base_data(
        incoming_plan_a,
        supplier_party_a,
        measurements_json=json.dumps({"sample_no": 1, "value": 10.0}),
    )
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "measurements_json" in form.errors
    assert "Measurements must be a JSON array of reading objects." in form.errors["measurements_json"][0]


def test_incomingquality_forms_lot_initial_measurements_json_populated(tenant_a, incoming_lot_a):
    """Verify measurements_json initial value is populated when editing instance."""
    form = IncomingInspectionLotForm(instance=incoming_lot_a, tenant=tenant_a)
    initial_val = form.fields["measurements_json"].initial
    assert initial_val is not None
    assert json.loads(initial_val) == incoming_lot_a.measurements_data


def test_incomingquality_forms_lot_date_ordering_validation(tenant_a, incoming_plan_a, supplier_party_a):
    """Inspection date cannot precede receipt date."""
    data = _incomingquality_forms_lot_base_data(
        incoming_plan_a,
        supplier_party_a,
        receipt_date=_incomingquality_forms_date(5),
        inspection_date=_incomingquality_forms_date(2),
    )
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_date" in form.errors
    assert "Inspection date cannot precede receipt date." in form.errors["inspection_date"][0]


def test_incomingquality_forms_lot_negative_quantities_validation(tenant_a, incoming_plan_a, supplier_party_a):
    """Negative lot, accepted, rejected, or quarantine quantities must be rejected."""
    # Negative lot quantity
    d1 = _incomingquality_forms_lot_base_data(incoming_plan_a, supplier_party_a, lot_quantity="-50.000")
    f1 = IncomingInspectionLotForm(data=d1, tenant=tenant_a)
    assert not f1.is_valid()
    assert "Lot quantity cannot be negative." in f1.errors["lot_quantity"][0]

    # Negative accepted quantity
    d2 = _incomingquality_forms_lot_base_data(incoming_plan_a, supplier_party_a, accepted_quantity="-10.000")
    f2 = IncomingInspectionLotForm(data=d2, tenant=tenant_a)
    assert not f2.is_valid()
    assert "Accepted quantity cannot be negative." in f2.errors["accepted_quantity"][0]

    # Negative rejected quantity
    d3 = _incomingquality_forms_lot_base_data(incoming_plan_a, supplier_party_a, rejected_quantity="-5.000")
    f3 = IncomingInspectionLotForm(data=d3, tenant=tenant_a)
    assert not f3.is_valid()
    assert "Rejected quantity cannot be negative." in f3.errors["rejected_quantity"][0]

    # Negative quarantine quantity
    d4 = _incomingquality_forms_lot_base_data(incoming_plan_a, supplier_party_a, quarantine_quantity="-2.000")
    f4 = IncomingInspectionLotForm(data=d4, tenant=tenant_a)
    assert not f4.is_valid()
    assert "Quarantined quantity cannot be negative." in f4.errors["quarantine_quantity"][0]


def test_incomingquality_forms_lot_quantity_sum_exceeds_lot_quantity(tenant_a, incoming_plan_a, supplier_party_a):
    """Sum of accepted, rejected, and quarantined quantities cannot exceed total lot quantity."""
    data = _incomingquality_forms_lot_base_data(
        incoming_plan_a,
        supplier_party_a,
        lot_quantity="100.000",
        accepted_quantity="60.000",
        rejected_quantity="30.000",
        quarantine_quantity="20.000",  # 60 + 30 + 20 = 110 > 100
    )
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "accepted_quantity" in form.errors
    assert "Sum of accepted, rejected, and quarantined quantities cannot exceed total lot quantity." in form.errors["accepted_quantity"][0]


def test_incomingquality_forms_lot_missing_required_fields(tenant_a):
    """Submitting empty dictionary must trigger required field validations."""
    form = IncomingInspectionLotForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "supplier" in form.errors
    assert "item_code" in form.errors
    assert "item_name" in form.errors
    assert "lot_number" in form.errors


def test_incomingquality_forms_lot_valid_submission_creates_and_saves(
    tenant_a, incoming_plan_a, supplier_party_a, admin_user
):
    """Verify valid lot form submission saves properly with auto-numbered QIIL- prefix."""
    data = _incomingquality_forms_lot_base_data(
        incoming_plan_a,
        supplier_party_a,
        inspector=admin_user,
        decided_by=admin_user,
        lot_number="LOT-2026-VAL-101",
    )
    form = IncomingInspectionLotForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    lot = form.save()
    assert lot.pk is not None
    assert lot.tenant == tenant_a
    assert lot.number.startswith("QIIL-")
    assert lot.lot_number == "LOT-2026-VAL-101"
    assert lot.inspector == admin_user


# =============================================================================
# 3. CertificateOfAnalysisForm Tests
# =============================================================================

def test_incomingquality_forms_coa_init_without_tenant():
    """Verify CoA form initializes safely when tenant is None."""
    form = CertificateOfAnalysisForm()
    assert form.tenant is None
    assert "certificate_number" in form.fields
    assert "parameters_json" in form.fields


def test_incomingquality_forms_coa_init_with_tenant(
    tenant_a, supplier_party_a, incoming_lot_a, incoming_plan_a, doc_a
):
    """Verify CoA form initializes with tenant and populates scoped querysets."""
    form = CertificateOfAnalysisForm(tenant=tenant_a)
    assert form.tenant == tenant_a
    assert supplier_party_a in form.fields["supplier"].queryset
    assert incoming_lot_a in form.fields["inspection_lot"].queryset
    assert incoming_plan_a in form.fields["inspection_plan"].queryset
    assert doc_a in form.fields["supporting_document"].queryset


def test_incomingquality_forms_coa_system_field_exclusions(tenant_a, supplier_party_a):
    """Verify tenant, number, timestamps, and automated result fields are excluded."""
    form = CertificateOfAnalysisForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "parameters_payload",
        "variance_count",
        "is_within_spec",
        "verified_by",
        "verified_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from CoA form"

    # Malicious injection in POST data
    data = _incomingquality_forms_coa_base_data(
        supplier_party_a,
        variance_count=999,
        is_within_spec=False,
        number="QCOA-MALICIOUS-888",
    )
    bound_form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert instance.number != "QCOA-MALICIOUS-888"


def test_incomingquality_forms_coa_tenant_scoping_foreign_keys(
    tenant_a,
    supplier_party_a,
    supplier_party_b,
    incoming_lot_a,
    incoming_lot_b,
    incoming_plan_a,
    incoming_plan_b,
    doc_a,
    doc_b,
):
    """Verify supplier, inspection_lot, inspection_plan, and supporting_document are scoped."""
    form = CertificateOfAnalysisForm(tenant=tenant_a)
    assert supplier_party_a in form.fields["supplier"].queryset
    assert supplier_party_b not in form.fields["supplier"].queryset
    assert incoming_lot_a in form.fields["inspection_lot"].queryset
    assert incoming_lot_b not in form.fields["inspection_lot"].queryset
    assert incoming_plan_a in form.fields["inspection_plan"].queryset
    assert incoming_plan_b not in form.fields["inspection_plan"].queryset
    assert doc_a in form.fields["supporting_document"].queryset
    assert doc_b not in form.fields["supporting_document"].queryset


def test_incomingquality_forms_coa_reject_foreign_cross_tenant(
    tenant_a, supplier_party_b, incoming_lot_b, incoming_plan_b, doc_b
):
    """Submitting Tenant B foreign keys to Tenant A CoA form must trigger reject_foreign validation."""
    data = _incomingquality_forms_coa_base_data(
        supplier=supplier_party_b,
        lot=incoming_lot_b,
        plan=incoming_plan_b,
        doc=doc_b,
    )
    form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    fields_to_check = ["supplier", "inspection_lot", "inspection_plan", "supporting_document"]
    for field in fields_to_check:
        assert field in form.errors

    # Verify reject_foreign directly adds the specific workspace isolation message
    direct_form = CertificateOfAnalysisForm(tenant=tenant_a)
    direct_form.cleaned_data = {
        "supplier": supplier_party_b,
        "inspection_lot": incoming_lot_b,
        "inspection_plan": incoming_plan_b,
        "supporting_document": doc_b,
    }
    reject_foreign(direct_form, direct_form.cleaned_data, fields_to_check)
    for field in fields_to_check:
        assert "That record belongs to another workspace." in direct_form.errors[field][0]


def test_incomingquality_forms_coa_parameters_json_valid_and_verify_specs(tenant_a, supplier_party_a):
    """Valid parameters JSON parses and triggers verify_specifications() on save."""
    # Spec: 98.0 to 102.0. Actual: 99.4 -> within spec
    params = [
        {"parameter": "Assay Purity", "method": "HPLC", "lsl": 98.0, "usl": 102.0, "actual_value": 99.4, "unit": "%"}
    ]
    data = _incomingquality_forms_coa_base_data(
        supplier=supplier_party_a,
        parameters_json=json.dumps(params),
    )
    form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["parameters_json"] == params

    coa = form.save(commit=True)
    assert coa.parameters_payload is not None
    assert coa.is_within_spec is True
    assert coa.variance_count == 0


def test_incomingquality_forms_coa_parameters_json_failing_tolerance(tenant_a, supplier_party_a):
    """Parameters failing tolerances trigger variance_count > 0 and is_within_spec=False."""
    # Spec: 98.0 to 102.0. Actual: 95.0 -> out of spec
    params = [
        {"parameter": "Assay Purity", "method": "HPLC", "lsl": 98.0, "usl": 102.0, "actual_value": 95.0, "unit": "%"}
    ]
    data = _incomingquality_forms_coa_base_data(
        supplier=supplier_party_a,
        parameters_json=json.dumps(params),
    )
    form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    coa = form.save(commit=True)
    assert coa.variance_count == 1
    assert coa.is_within_spec is False


def test_incomingquality_forms_coa_parameters_json_empty(tenant_a, supplier_party_a):
    """Empty parameters_json parses to empty list."""
    data = _incomingquality_forms_coa_base_data(
        supplier=supplier_party_a,
        parameters_json="   ",
    )
    form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["parameters_json"] == []


def test_incomingquality_forms_coa_parameters_json_invalid_syntax(tenant_a, supplier_party_a):
    """Malformed parameters JSON raises validation error."""
    data = _incomingquality_forms_coa_base_data(
        supplier=supplier_party_a,
        parameters_json="[bad_json_token",
    )
    form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "parameters_json" in form.errors
    assert "Invalid JSON:" in form.errors["parameters_json"][0]


def test_incomingquality_forms_coa_parameters_json_non_list(tenant_a, supplier_party_a):
    """Non-list parameters JSON raises array validation error."""
    data = _incomingquality_forms_coa_base_data(
        supplier=supplier_party_a,
        parameters_json=json.dumps({"param": "Density", "val": 1.2}),
    )
    form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "parameters_json" in form.errors
    assert "Parameters must be a JSON array of parameter dictionaries." in form.errors["parameters_json"][0]


def test_incomingquality_forms_coa_initial_parameters_json_populated(tenant_a, coa_a):
    """Verify initial value of parameters_json is formatted from instance."""
    form = CertificateOfAnalysisForm(instance=coa_a, tenant=tenant_a)
    initial_val = form.fields["parameters_json"].initial
    assert initial_val is not None
    assert json.loads(initial_val) == coa_a.parameters_payload


def test_incomingquality_forms_coa_date_ordering_validation(tenant_a, supplier_party_a):
    """Expiry or retest date cannot precede date of manufacture."""
    data = _incomingquality_forms_coa_base_data(
        supplier_party_a,
        date_of_manufacture=_incomingquality_forms_date(10),
        expiry_or_retest_date=_incomingquality_forms_date(5),
    )
    form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "expiry_or_retest_date" in form.errors
    assert "Expiry or retest date cannot precede date of manufacture." in form.errors["expiry_or_retest_date"][0]


def test_incomingquality_forms_coa_missing_required_fields(tenant_a):
    """Submitting empty dictionary must trigger required field validations."""
    form = CertificateOfAnalysisForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "certificate_number" in form.errors
    assert "supplier" in form.errors
    assert "item_code" in form.errors
    assert "item_name" in form.errors
    assert "lot_number" in form.errors


def test_incomingquality_forms_coa_valid_submission_creates_and_saves(
    tenant_a, supplier_party_a, incoming_lot_a, incoming_plan_a
):
    """Verify valid CoA submission saves properly with auto-numbered QCOA- prefix."""
    data = _incomingquality_forms_coa_base_data(
        supplier_party_a,
        plan=incoming_plan_a,
        lot=incoming_lot_a,
        certificate_number="COA-TEST-SUBMIT-001",
    )
    form = CertificateOfAnalysisForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    coa = form.save()
    assert coa.pk is not None
    assert coa.tenant == tenant_a
    assert coa.number.startswith("QCOA-")
    assert coa.certificate_number == "COA-TEST-SUBMIT-001"


# =============================================================================
# 4. QualityReturnAuthorizationForm Tests
# =============================================================================

def test_incomingquality_forms_rma_init_without_tenant():
    """Verify RMA form initializes cleanly when tenant is None."""
    form = QualityReturnAuthorizationForm()
    assert form.tenant is None
    assert "inspection_lot" in form.fields
    assert "vendor_rma_number" in form.fields


def test_incomingquality_forms_rma_init_with_tenant(
    tenant_a, incoming_lot_a, supplier_party_a, admin_user
):
    """Verify RMA form initializes with tenant and populates scoped querysets."""
    form = QualityReturnAuthorizationForm(tenant=tenant_a)
    assert form.tenant == tenant_a
    assert incoming_lot_a in form.fields["inspection_lot"].queryset
    assert supplier_party_a in form.fields["supplier"].queryset
    assert admin_user in form.fields["assigned_coordinator"].queryset


def test_incomingquality_forms_rma_system_field_exclusions(tenant_a, incoming_lot_a, supplier_party_a):
    """Verify tenant, number, and timestamps are excluded from editable fields."""
    form = QualityReturnAuthorizationForm(tenant=tenant_a)
    for field in ["tenant", "number", "created_at", "updated_at"]:
        assert field not in form.fields

    data = _incomingquality_forms_rma_base_data(
        incoming_lot_a,
        supplier_party_a,
        number="QRMA-MALICIOUS-777",
    )
    bound_form = QualityReturnAuthorizationForm(data=data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert instance.number != "QRMA-MALICIOUS-777"


def test_incomingquality_forms_rma_tenant_scoping_coordinator_active_only(tenant_a, tenant_b, admin_user, admin_b):
    """Verify assigned_coordinator includes only active users belonging to the tenant."""
    inactive_coordinator = User.objects.create_user(
        username="inactive_coord_a",
        email="inactive_coord@acme.com",
        password="TestPass123!",
        tenant=tenant_a,
        is_active=False,
    )

    form = QualityReturnAuthorizationForm(tenant=tenant_a)
    coord_qs = form.fields["assigned_coordinator"].queryset

    assert admin_user in coord_qs
    assert inactive_coordinator not in coord_qs
    assert admin_b not in coord_qs


def test_incomingquality_forms_rma_tenant_scoping_foreign_keys(
    tenant_a,
    incoming_lot_a,
    incoming_lot_b,
    supplier_party_a,
    supplier_party_b,
    ncr_a,
    ncr_b,
    scar_a,
    scar_b,
):
    """Verify inspection_lot, supplier, linked_ncr, and linked_scar are tenant-scoped."""
    form = QualityReturnAuthorizationForm(tenant=tenant_a)
    assert incoming_lot_a in form.fields["inspection_lot"].queryset
    assert incoming_lot_b not in form.fields["inspection_lot"].queryset
    assert supplier_party_a in form.fields["supplier"].queryset
    assert supplier_party_b not in form.fields["supplier"].queryset
    assert ncr_a in form.fields["linked_ncr"].queryset
    assert ncr_b not in form.fields["linked_ncr"].queryset
    assert scar_a in form.fields["linked_scar"].queryset
    assert scar_b not in form.fields["linked_scar"].queryset


def test_incomingquality_forms_rma_reject_foreign_cross_tenant(
    tenant_a, incoming_lot_b, supplier_party_b, admin_b, ncr_b, scar_b
):
    """Submitting Tenant B foreign keys to Tenant A RMA form must trigger reject_foreign validation."""
    data = _incomingquality_forms_rma_base_data(
        lot=incoming_lot_b,
        supplier=supplier_party_b,
        coordinator=admin_b,
        linked_ncr=_incomingquality_forms_pk(ncr_b),
        linked_scar=_incomingquality_forms_pk(scar_b),
    )
    form = QualityReturnAuthorizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    fields_to_check = ["inspection_lot", "supplier", "assigned_coordinator", "linked_ncr", "linked_scar"]
    for field in fields_to_check:
        assert field in form.errors

    # Verify reject_foreign directly adds the specific workspace isolation message
    direct_form = QualityReturnAuthorizationForm(tenant=tenant_a)
    direct_form.cleaned_data = {
        "inspection_lot": incoming_lot_b,
        "supplier": supplier_party_b,
        "assigned_coordinator": admin_b,
        "linked_ncr": ncr_b,
        "linked_scar": scar_b,
    }
    reject_foreign(direct_form, direct_form.cleaned_data, fields_to_check)
    for field in fields_to_check:
        assert "That record belongs to another workspace." in direct_form.errors[field][0]


def test_incomingquality_forms_rma_negative_values_validation(tenant_a, incoming_lot_a, supplier_party_a):
    """Negative values for return_quantity, estimated_credit_value, and settled_amount must be rejected."""
    # Negative return_quantity
    d1 = _incomingquality_forms_rma_base_data(incoming_lot_a, supplier_party_a, return_quantity="-10.000")
    f1 = QualityReturnAuthorizationForm(data=d1, tenant=tenant_a)
    assert not f1.is_valid()
    assert "Return quantity cannot be negative." in f1.errors["return_quantity"][0]

    # Negative estimated_credit_value
    d2 = _incomingquality_forms_rma_base_data(incoming_lot_a, supplier_party_a, estimated_credit_value="-50.00")
    f2 = QualityReturnAuthorizationForm(data=d2, tenant=tenant_a)
    assert not f2.is_valid()
    assert "Estimated credit value cannot be negative." in f2.errors["estimated_credit_value"][0]

    # Negative settled_amount
    d3 = _incomingquality_forms_rma_base_data(incoming_lot_a, supplier_party_a, settled_amount="-100.00")
    f3 = QualityReturnAuthorizationForm(data=d3, tenant=tenant_a)
    assert not f3.is_valid()
    assert "Settled amount cannot be negative." in f3.errors["settled_amount"][0]


def test_incomingquality_forms_rma_date_ordering_validation(tenant_a, incoming_lot_a, supplier_party_a):
    """Vendor receipt date and settlement date cannot precede shipped date."""
    # vendor_receipt_date precedes shipped_date
    d1 = _incomingquality_forms_rma_base_data(
        incoming_lot_a,
        supplier_party_a,
        shipped_date=_incomingquality_forms_date(5),
        vendor_receipt_date=_incomingquality_forms_date(2),
    )
    f1 = QualityReturnAuthorizationForm(data=d1, tenant=tenant_a)
    assert not f1.is_valid()
    assert "vendor_receipt_date" in f1.errors
    assert "Vendor receipt date cannot precede shipped date." in f1.errors["vendor_receipt_date"][0]

    # settlement_date precedes shipped_date
    d2 = _incomingquality_forms_rma_base_data(
        incoming_lot_a,
        supplier_party_a,
        shipped_date=_incomingquality_forms_date(5),
        vendor_receipt_date=_incomingquality_forms_date(6),
        settlement_date=_incomingquality_forms_date(3),
    )
    f2 = QualityReturnAuthorizationForm(data=d2, tenant=tenant_a)
    assert not f2.is_valid()
    assert "settlement_date" in f2.errors
    assert "Settlement date cannot precede shipped date." in f2.errors["settlement_date"][0]


def test_incomingquality_forms_rma_missing_required_fields(tenant_a):
    """Submitting empty dictionary must trigger required field validations."""
    form = QualityReturnAuthorizationForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_lot" in form.errors
    assert "supplier" in form.errors


def test_incomingquality_forms_rma_valid_submission_creates_and_saves(
    tenant_a, incoming_lot_a, supplier_party_a, admin_user
):
    """Verify valid RMA submission saves properly with auto-numbered QRMA- prefix."""
    data = _incomingquality_forms_rma_base_data(
        incoming_lot_a,
        supplier_party_a,
        coordinator=admin_user,
        vendor_rma_number="VRMA-SUCCESS-001",
    )
    form = QualityReturnAuthorizationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    rma = form.save()
    assert rma.pk is not None
    assert rma.tenant == tenant_a
    assert rma.number.startswith("QRMA-")
    assert rma.vendor_rma_number == "VRMA-SUCCESS-001"
    assert rma.assigned_coordinator == admin_user


# =============================================================================
# 5. Widget and UI Invariant Tests
# =============================================================================

def test_incomingquality_forms_widgets_and_styling(tenant_a):
    """Verify standard form widgets and CSS class mappings across all 4 forms."""
    forms_to_check = [
        IncomingInspectionPlanForm(tenant=tenant_a),
        IncomingInspectionLotForm(tenant=tenant_a),
        CertificateOfAnalysisForm(tenant=tenant_a),
        QualityReturnAuthorizationForm(tenant=tenant_a),
    ]

    for form in forms_to_check:
        for name, field in form.fields.items():
            widget = field.widget
            css_class = widget.attrs.get("class", "")
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                assert "form-select" in css_class, f"{form.__class__.__name__}.{name} should have form-select"
            elif isinstance(widget, forms.Textarea):
                assert "form-textarea" in css_class, f"{form.__class__.__name__}.{name} should have form-textarea"
            elif isinstance(widget, forms.CheckboxInput):
                assert "form-checkbox" in css_class or "form-check" in css_class, (
                    f"{form.__class__.__name__}.{name} should have form-checkbox or form-check"
                )
            elif isinstance(widget, (forms.TextInput, forms.NumberInput, forms.DateInput)):
                assert "form-input" in css_class, f"{form.__class__.__name__}.{name} should have form-input"
