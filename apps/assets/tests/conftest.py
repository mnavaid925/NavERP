"""Shared test contract fixtures for apps/assets (Module 11)."""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.accounting.models import Currency, GLAccount, FixedAsset
from apps.core.models import OrgUnit, Party, PartyRole
from apps.scm.models import Asset, Location, PurchaseOrder
from apps.assets.models import (
    AssetRequisition,
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetTag,
    AssetAudit,
    AssetMovementLog,
    AssetCustodyLog,
    AssetIncidentReport,
    AssetCategory,
    AssetModel,
    AssetCriticalityAssessment,
    AssetSpecificationTemplate,
    AssetDepreciationSchedule,
    AssetRevaluation,
    AssetTransfer,
    CapitalizationPolicy,
)


@pytest.fixture
def currency_usd(db):
    curr, _ = Currency.objects.get_or_create(
        code="USD",
        defaults={"name": "US Dollar", "symbol": "$", "is_active": True},
    )
    return curr


@pytest.fixture
def vendor_party_a(db, tenant_a):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Apex Industrial Machinery",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role="vendor",
        status="active",
    )
    return party


@pytest.fixture
def vendor_party_b(db, tenant_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Globex Heavy Supply",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role="vendor",
        status="active",
    )
    return party


@pytest.fixture
def org_unit_a(db, tenant_a):
    return OrgUnit.objects.create(
        tenant=tenant_a,
        name="Manufacturing Plant 1",
        kind="department",
    )


@pytest.fixture
def org_unit_b(db, tenant_b):
    return OrgUnit.objects.create(
        tenant=tenant_b,
        name="Globex Logistics Hub",
        kind="department",
    )


@pytest.fixture
def location_a(db, tenant_a):
    return Location.objects.create(
        tenant=tenant_a,
        code="WH-MAIN-A",
        name="Acme Central Staging Dock",
        location_type="staging",
        is_active=True,
    )


@pytest.fixture
def location_a2(db, tenant_a):
    return Location.objects.create(
        tenant=tenant_a,
        code="WH-BAY2-A",
        name="Acme Bay 2 Assembly",
        location_type="staging",
        is_active=True,
    )


@pytest.fixture
def location_b(db, tenant_b):
    return Location.objects.create(
        tenant=tenant_b,
        code="WH-MAIN-B",
        name="Globex Receiving Depot",
        location_type="staging",
        is_active=True,
    )


@pytest.fixture
def po_a(db, tenant_a, vendor_party_a):
    return PurchaseOrder.objects.create(
        tenant=tenant_a,
        number="PO-2026-9001",
        vendor=vendor_party_a,
        status="approved",
    )


@pytest.fixture
def po_b(db, tenant_b, vendor_party_b):
    return PurchaseOrder.objects.create(
        tenant=tenant_b,
        number="PO-2026-9002",
        vendor=vendor_party_b,
        status="approved",
    )


@pytest.fixture
def asset_account_a(db, tenant_a):
    return GLAccount.objects.create(
        tenant=tenant_a,
        code="1500-A",
        name="Machinery & Equipment",
        account_type="asset",
        normal_balance="debit",
        is_active=True,
    )


@pytest.fixture
def cip_account_a(db, tenant_a):
    return GLAccount.objects.create(
        tenant=tenant_a,
        code="1599-A",
        name="Construction in Progress - Clearing",
        account_type="asset",
        normal_balance="debit",
        is_active=True,
    )


@pytest.fixture
def operational_asset_a(db, tenant_a, location_a):
    return Asset.objects.create(
        tenant=tenant_a,
        code="AST-ACME-01",
        name="Haas 5-Axis CNC Mill",
        asset_type="machinery",
        location=location_a,
    )


@pytest.fixture
def operational_asset_b(db, tenant_b, location_b):
    return Asset.objects.create(
        tenant=tenant_b,
        code="AST-GLOBEX-01",
        name="Caterpillar Forklift 5000",
        asset_type="vehicle",
        location=location_b,
    )


@pytest.fixture
def requisition_a(db, tenant_a, currency_usd, vendor_party_a, org_unit_a, location_a, admin_user):
    return AssetRequisition.objects.create(
        tenant=tenant_a,
        title="Automated Laser Cutting System",
        description="Fiber laser cutting workstation 4kW for sheet metal fabrication.",
        asset_category="machinery",
        priority="high",
        estimated_cost=Decimal("125000.00"),
        currency=currency_usd,
        budget_code="CAPEX-2026-01",
        proposed_vendor=vendor_party_a,
        target_org_unit=org_unit_a,
        target_location=location_a,
        status="draft",
        submitted_by=admin_user,
    )


@pytest.fixture
def requisition_b(db, tenant_b, currency_usd, vendor_party_b, location_b, admin_b):
    return AssetRequisition.objects.create(
        tenant=tenant_b,
        title="Globex Hydraulic Press Brake",
        description="Heavy 200-ton press brake machine.",
        asset_category="machinery",
        priority="medium",
        estimated_cost=Decimal("85000.00"),
        currency=currency_usd,
        budget_code="CAPEX-GLOBEX-01",
        proposed_vendor=vendor_party_b,
        target_location=location_b,
        status="draft",
        submitted_by=admin_b,
    )


@pytest.fixture
def receipt_a(db, tenant_a, requisition_a, po_a, vendor_party_a, location_a):
    return AssetAcquisitionReceipt.objects.create(
        tenant=tenant_a,
        title="Dock Receipt for Laser Cutter",
        requisition=requisition_a,
        purchase_order=po_a,
        vendor=vendor_party_a,
        manufacturer="Trumpf Laser",
        model_number="TruLaser 3030",
        serial_number="TL3030-998811",
        quantity_received=1,
        received_date=timezone.now().date(),
        receiving_location=location_a,
        condition_on_arrival="intact",
        status="pending_inspection",
    )


@pytest.fixture
def receipt_b(db, tenant_b, requisition_b, po_b, vendor_party_b, location_b):
    return AssetAcquisitionReceipt.objects.create(
        tenant=tenant_b,
        title="Dock Receipt for Press Brake",
        requisition=requisition_b,
        purchase_order=po_b,
        vendor=vendor_party_b,
        manufacturer="Amada",
        model_number="HFE-M2",
        serial_number="AMD-882233",
        quantity_received=1,
        received_date=timezone.now().date(),
        receiving_location=location_b,
        condition_on_arrival="intact",
        status="pending_inspection",
    )


@pytest.fixture
def capitalization_a(db, tenant_a, receipt_a, cip_account_a, asset_account_a):
    return AssetCapitalization.objects.create(
        tenant=tenant_a,
        asset_name="Capitalized Trumpf Laser Cutter",
        title="Capitalization Trumpf Laser Cutter",
        acquisition_receipt=receipt_a,
        purchase_cost=Decimal("120000.00"),
        freight_cost=Decimal("3500.00"),
        installation_cost=Decimal("1500.00"),
        salvage_value=Decimal("10000.00"),
        useful_life_months=84,
        depreciation_method="straight_line",
        in_service_date=timezone.now().date(),
        cip_gl_account=cip_account_a,
        asset_gl_account=asset_account_a,
        status="draft",
    )


@pytest.fixture
def capitalization_b(db, tenant_b, receipt_b):
    return AssetCapitalization.objects.create(
        tenant=tenant_b,
        asset_name="Capitalized Globex Press Brake",
        title="Capitalization Globex Press Brake",
        acquisition_receipt=receipt_b,
        purchase_cost=Decimal("80000.00"),
        salvage_value=Decimal("5000.00"),
        useful_life_months=60,
        depreciation_method="straight_line",
        in_service_date=timezone.now().date(),
        status="draft",
    )


@pytest.fixture
def asset_tag_a(db, tenant_a, operational_asset_a, capitalization_a):
    return AssetTag.objects.create(
        tenant=tenant_a,
        tag_code="ATAG-ACME-00001",
        tag_format="qr_code",
        operational_asset=operational_asset_a,
        capitalization=capitalization_a,
        physical_placement="Main chassis nameplate",
        status="pending_print",
        is_verified=False,
    )


@pytest.fixture
def asset_tag_b(db, tenant_b, operational_asset_b, capitalization_b):
    return AssetTag.objects.create(
        tenant=tenant_b,
        tag_code="ATAG-GLOBEX-00001",
        tag_format="barcode_128",
        operational_asset=operational_asset_b,
        capitalization=capitalization_b,
        physical_placement="Dashboard label",
        status="pending_print",
        is_verified=False,
    )


# ==============================================================================
# Sub-module 11.2 Asset Inventory & Tracking Fixtures
# ==============================================================================

@pytest.fixture
def audit_a(db, tenant_a, location_a, org_unit_a, admin_user):
    return AssetAudit.objects.create(
        tenant=tenant_a,
        title="Q2 Annual Physical Audit",
        audit_type="wall_to_wall",
        target_location=location_a,
        target_org_unit=org_unit_a,
        lead_auditor=admin_user,
        supervisor=admin_user,
        scheduled_date=timezone.now().date() + timezone.timedelta(days=7),
        is_blind_count=True,
        expected_asset_count=25,
        scanned_asset_count=0,
        status="scheduled",
    )


@pytest.fixture
def audit_b(db, tenant_b, location_b, admin_b):
    return AssetAudit.objects.create(
        tenant=tenant_b,
        title="Globex Depot Spot Check",
        audit_type="spot_check",
        target_location=location_b,
        lead_auditor=admin_b,
        scheduled_date=timezone.now().date(),
        is_blind_count=False,
        expected_asset_count=10,
        scanned_asset_count=0,
        status="scheduled",
    )


@pytest.fixture
def movement_a(db, tenant_a, operational_asset_a, location_a, location_a2, org_unit_a, vendor_party_a, admin_user):
    return AssetMovementLog.objects.create(
        tenant=tenant_a,
        title="Transfer CNC to Bay 2",
        asset=operational_asset_a,
        movement_type="inter_facility_transfer",
        from_location=location_a,
        to_location=location_a2,
        from_org_unit=org_unit_a,
        to_org_unit=org_unit_a,
        from_custodian=vendor_party_a,
        carrier_name="Internal Transport",
        status="requested",
        reason="Scheduled maintenance overhaul in Bay 2.",
    )


@pytest.fixture
def movement_b(db, tenant_b, operational_asset_b, location_b, vendor_party_b):
    return AssetMovementLog.objects.create(
        tenant=tenant_b,
        title="Globex Forklift Transfer",
        asset=operational_asset_b,
        movement_type="department_transfer",
        from_location=location_b,
        to_location=location_b,
        from_custodian=vendor_party_b,
        status="requested",
        reason="Relocation to packing station.",
    )


@pytest.fixture
def custody_a(db, tenant_a, operational_asset_a, vendor_party_a, admin_user):
    return AssetCustodyLog.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        action_type="checkout",
        borrower=vendor_party_a,
        borrower_name=vendor_party_a.name,
        crib_attendant=admin_user,
        purpose="Precision CNC prototyping",
        checkout_date=timezone.now() - timezone.timedelta(days=1),
        expected_return_date=timezone.now().date() + timezone.timedelta(days=7),
        checkout_condition="excellent",
        borrower_signature_acknowledged=True,
        status="active_loan",
    )


@pytest.fixture
def custody_b(db, tenant_b, operational_asset_b, vendor_party_b, admin_b):
    return AssetCustodyLog.objects.create(
        tenant=tenant_b,
        asset=operational_asset_b,
        action_type="checkout",
        borrower=vendor_party_b,
        borrower_name=vendor_party_b.name,
        crib_attendant=admin_b,
        purpose="Globex warehouse operations",
        checkout_date=timezone.now() - timezone.timedelta(days=2),
        expected_return_date=timezone.now().date() + timezone.timedelta(days=5),
        checkout_condition="good",
        borrower_signature_acknowledged=True,
        status="active_loan",
    )


@pytest.fixture
def incident_a(db, tenant_a, operational_asset_a, location_a, admin_user, vendor_party_a):
    return AssetIncidentReport.objects.create(
        tenant=tenant_a,
        title="Spindle Motor Damage Report",
        asset=operational_asset_a,
        incident_type="damaged_beyond_repair",
        severity="high",
        incident_date=timezone.now().date() - timezone.timedelta(days=2),
        last_known_location=location_a,
        reported_by=admin_user,
        custodian_at_loss=vendor_party_a,
        estimated_loss_value=Decimal("8500.00"),
        incident_description="Overvoltage surge caused terminal stator burnout during roughing pass.",
        status="reported",
    )


@pytest.fixture
def incident_b(db, tenant_b, operational_asset_b, location_b, admin_b):
    return AssetIncidentReport.objects.create(
        tenant=tenant_b,
        title="Missing Forklift Attachment",
        asset=operational_asset_b,
        incident_type="lost",
        severity="medium",
        incident_date=timezone.now().date() - timezone.timedelta(days=5),
        last_known_location=location_b,
        reported_by=admin_b,
        estimated_loss_value=Decimal("1200.00"),
        incident_description="Clamp attachment missing from staging rack.",
        status="reported",
    )


# ---------------------------------------------------------------------------
# Module 11.3 Asset Classification & Categorization Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def category_root_a(db, tenant_a):
    return AssetCategory.objects.create(
        tenant=tenant_a,
        code="FAC-PLANT",
        name="Plant Equipment",
        category_type="machinery",
        default_depreciation_method="straight_line",
        default_useful_life_months=120,
        is_active=True,
    )


@pytest.fixture
def category_child_a(db, tenant_a, category_root_a):
    return AssetCategory.objects.create(
        tenant=tenant_a,
        code="HVAC-CHL",
        name="Centrifugal Chillers",
        parent=category_root_a,
        category_type="facility",
        default_depreciation_method="straight_line",
        default_useful_life_months=84,
        is_active=True,
    )


@pytest.fixture
def category_root_b(db, tenant_b):
    return AssetCategory.objects.create(
        tenant=tenant_b,
        code="LOG-FLEET",
        name="Fleet Vehicles",
        category_type="fleet",
        default_depreciation_method="straight_line",
        default_useful_life_months=60,
        is_active=True,
    )


@pytest.fixture
def asset_model_a(db, tenant_a, category_root_a, vendor_party_a):
    return AssetModel.objects.create(
        tenant=tenant_a,
        model_number="CAT-320GC",
        name="Hydraulic Excavator",
        category=category_root_a,
        manufacturer=vendor_party_a,
        estimated_replacement_cost=Decimal("175000.00"),
        expected_useful_life_months=120,
        standard_warranty_months=24,
        default_meter_name="Operating Hours",
        default_meter_unit="h",
        model_status="active",
    )


@pytest.fixture
def asset_model_b(db, tenant_b, category_root_b, vendor_party_b):
    return AssetModel.objects.create(
        tenant=tenant_b,
        model_number="YALE-ERP040",
        name="Electric Forklift",
        category=category_root_b,
        manufacturer=vendor_party_b,
        estimated_replacement_cost=Decimal("38000.00"),
        expected_useful_life_months=84,
        standard_warranty_months=12,
        default_meter_name="Operating Hours",
        default_meter_unit="h",
        model_status="active",
    )


@pytest.fixture
def criticality_assessment_a(db, tenant_a, operational_asset_a, vendor_party_a):
    assessment = AssetCriticalityAssessment(
        tenant=tenant_a,
        title="Acme CNC Criticality Review",
        asset=operational_asset_a,
        assessor=vendor_party_a,
        operational_downtime_impact=5,
        safety_impact=4,
        environmental_impact=3,
        regulatory_compliance_impact=3,
        financial_impact=4,
        is_single_point_of_failure=True,
        assessment_status="draft",
        findings_and_mitigation="Primary critical bottleneck asset.",
    )
    assessment.calculate_composite_score()
    assessment.save()
    return assessment


@pytest.fixture
def criticality_assessment_b(db, tenant_b, operational_asset_b, vendor_party_b):
    assessment = AssetCriticalityAssessment(
        tenant=tenant_b,
        title="Globex Forklift Criticality Review",
        asset=operational_asset_b,
        assessor=vendor_party_b,
        operational_downtime_impact=2,
        safety_impact=1,
        environmental_impact=1,
        regulatory_compliance_impact=1,
        financial_impact=2,
        is_single_point_of_failure=False,
        assessment_status="draft",
    )
    assessment.calculate_composite_score()
    assessment.save()
    return assessment


@pytest.fixture
def spec_template_a(db, tenant_a, category_root_a):
    return AssetSpecificationTemplate.objects.create(
        tenant=tenant_a,
        category=category_root_a,
        display_name="Operating Voltage",
        attribute_key="operating_voltage",
        data_type="number",
        unit_of_measure="V",
        min_numeric_value=Decimal("380.00"),
        max_numeric_value=Decimal("480.00"),
        is_required=True,
        is_filterable=True,
    )


@pytest.fixture
def spec_template_b(db, tenant_b, category_root_b):
    return AssetSpecificationTemplate.objects.create(
        tenant=tenant_b,
        category=category_root_b,
        display_name="Battery Capacity",
        attribute_key="battery_capacity",
        data_type="number",
        unit_of_measure="Ah",
        is_required=False,
    )


# ==============================================================================
# Sub-module 11.4 Asset Depreciation & Financial Management Fixtures
# ==============================================================================

@pytest.fixture
def expense_account_a(db, tenant_a):
    return GLAccount.objects.create(
        tenant=tenant_a,
        code="6100-A",
        name="Depreciation Expense - Machinery",
        account_type="expense",
        normal_balance="debit",
        is_active=True,
    )


@pytest.fixture
def accum_account_a(db, tenant_a):
    return GLAccount.objects.create(
        tenant=tenant_a,
        code="1510-A",
        name="Accumulated Depreciation - Machinery",
        account_type="asset",
        normal_balance="credit",
        is_active=True,
    )


@pytest.fixture
def surplus_account_a(db, tenant_a):
    return GLAccount.objects.create(
        tenant=tenant_a,
        code="3200-A",
        name="Asset Revaluation Surplus",
        account_type="equity",
        normal_balance="credit",
        is_active=True,
    )


@pytest.fixture
def expense_account_b(db, tenant_b):
    return GLAccount.objects.create(
        tenant=tenant_b,
        code="6100-B",
        name="Globex Depreciation Expense",
        account_type="expense",
        normal_balance="debit",
        is_active=True,
    )


@pytest.fixture
def accum_account_b(db, tenant_b):
    return GLAccount.objects.create(
        tenant=tenant_b,
        code="1510-B",
        name="Globex Accumulated Depreciation",
        account_type="asset",
        normal_balance="credit",
        is_active=True,
    )


@pytest.fixture
def fixed_asset_a(db, tenant_a, asset_account_a, accum_account_a, expense_account_a):
    return FixedAsset.objects.create(
        tenant=tenant_a,
        name="Haas 5-Axis Machining Center VF-4",
        category="Machinery",
        acquisition_cost=Decimal("120000.00"),
        salvage_value=Decimal("12000.00"),
        useful_life_months=60,
        method="straight_line",
        status="active",
        asset_account=asset_account_a,
        accumulated_account=accum_account_a,
        expense_account=expense_account_a,
        in_service_date=timezone.now().date() - timezone.timedelta(days=365),
    )


@pytest.fixture
def fixed_asset_b(db, tenant_b, accum_account_b, expense_account_b):
    return FixedAsset.objects.create(
        tenant=tenant_b,
        name="Globex Warehouse Stacker 2000",
        category="Vehicle",
        acquisition_cost=Decimal("45000.00"),
        salvage_value=Decimal("5000.00"),
        useful_life_months=48,
        method="straight_line",
        status="active",
        accumulated_account=accum_account_b,
        expense_account=expense_account_b,
        in_service_date=timezone.now().date() - timezone.timedelta(days=180),
    )


@pytest.fixture
def capitalization_policy_a(db, tenant_a, category_root_a, cip_account_a, expense_account_a):
    return CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="Acme Machinery CapEx Policy",
        policy_scope="category_override",
        category=category_root_a,
        minimum_cost_threshold=Decimal("5000.00"),
        minimum_useful_life_months=12,
        default_classification="capitalize",
        de_minimis_safe_harbor=False,
        default_cip_account=cip_account_a,
        default_expense_account=expense_account_a,
        is_active=True,
    )


@pytest.fixture
def capitalization_policy_b(db, tenant_b, category_root_b, expense_account_b):
    return CapitalizationPolicy.objects.create(
        tenant=tenant_b,
        name="Globex De Minimis Policy",
        policy_scope="tax_book_safe_harbor",
        category=category_root_b,
        minimum_cost_threshold=Decimal("2500.00"),
        minimum_useful_life_months=12,
        default_classification="expense_immediately",
        de_minimis_safe_harbor=True,
        default_expense_account=expense_account_b,
        is_active=True,
    )


@pytest.fixture
def depreciation_schedule_a(db, tenant_a, fixed_asset_a, operational_asset_a, expense_account_a, accum_account_a):
    sched = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        schedule_date=timezone.now().date(),
        depreciation_method="straight_line",
        asset_cost_basis=Decimal("120000.00"),
        salvage_value=Decimal("12000.00"),
        accumulated_depreciation_prior=Decimal("0.00"),
        useful_life_months_total=60,
        depreciation_amount=Decimal("1800.00"),
        accumulated_depreciation_after=Decimal("1800.00"),
        net_book_value_after=Decimal("118200.00"),
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        status="draft",
    )
    return sched


@pytest.fixture
def depreciation_schedule_b(db, tenant_b, fixed_asset_b, operational_asset_b, expense_account_b, accum_account_b):
    return AssetDepreciationSchedule.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        schedule_date=timezone.now().date(),
        depreciation_method="straight_line",
        asset_cost_basis=Decimal("45000.00"),
        salvage_value=Decimal("5000.00"),
        accumulated_depreciation_prior=Decimal("0.00"),
        useful_life_months_total=48,
        depreciation_amount=Decimal("833.33"),
        accumulated_depreciation_after=Decimal("833.33"),
        net_book_value_after=Decimal("44166.67"),
        expense_account=expense_account_b,
        accumulated_account=accum_account_b,
        status="draft",
    )


@pytest.fixture
def revaluation_a(db, tenant_a, fixed_asset_a, operational_asset_a, vendor_party_a, expense_account_a, surplus_account_a):
    return AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="Acme CNC Annual Appraisal",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        event_type="revaluation_up",
        valuation_method="independent_appraisal",
        valuation_date=timezone.now().date(),
        appraiser=vendor_party_a,
        historical_cost=Decimal("120000.00"),
        accumulated_depreciation_before=Decimal("20000.00"),
        carrying_value_before=Decimal("100000.00"),
        new_fair_market_value=Decimal("115000.00"),
        revaluation_adjustment=Decimal("15000.00"),
        impairment_loss_account=expense_account_a,
        revaluation_surplus_account=surplus_account_a,
        status="draft",
    )


@pytest.fixture
def revaluation_b(db, tenant_b, fixed_asset_b, operational_asset_b, vendor_party_b, expense_account_b):
    return AssetRevaluation.objects.create(
        tenant=tenant_b,
        title="Globex Stacker Impairment Assessment",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        event_type="impairment",
        valuation_method="market_approach",
        valuation_date=timezone.now().date(),
        appraiser=vendor_party_b,
        historical_cost=Decimal("45000.00"),
        accumulated_depreciation_before=Decimal("10000.00"),
        carrying_value_before=Decimal("35000.00"),
        new_fair_market_value=Decimal("28000.00"),
        revaluation_adjustment=Decimal("-7000.00"),
        impairment_loss_account=expense_account_b,
        status="draft",
    )


@pytest.fixture
def transfer_a(db, tenant_a, fixed_asset_a, operational_asset_a, location_a, location_a2, org_unit_a, vendor_party_a, admin_user):
    return AssetTransfer.objects.create(
        tenant=tenant_a,
        title="Inter-Facility Transfer CNC Mill",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        transfer_type="inter_facility",
        transfer_date=timezone.now().date(),
        source_location=location_a,
        destination_location=location_a2,
        source_department=org_unit_a,
        source_custodian=vendor_party_a,
        transferred_by=admin_user,
        freight_cost=Decimal("750.00"),
        status="draft",
    )


@pytest.fixture
def transfer_b(db, tenant_b, fixed_asset_b, operational_asset_b, location_b, location_b2, org_unit_b, vendor_party_b, admin_b):
    return AssetTransfer.objects.create(
        tenant=tenant_b,
        title="Relocation Stacker to Yard",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        transfer_type="cost_center",
        transfer_date=timezone.now().date(),
        source_location=location_b,
        destination_location=location_b2,
        source_department=org_unit_b,
        source_custodian=vendor_party_b,
        transferred_by=admin_b,
        freight_cost=Decimal("250.00"),
        status="draft",
    )


