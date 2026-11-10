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
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
    AssetServiceContract,
    AssetMaintenanceLog,
    AssetDowntimeLog,
    AssetOeeRecord,
    AssetEnergyReading,
    AssetPerformanceScorecard,
    AssetConditionAssessment,
    AssetTelemetryReading,
    AssetFailureMode,
    AssetCalibrationRecord,
    AssetWarranty,
    AssetWarrantyClaim,
    AssetInsurancePolicy,
    AssetInsuranceClaim,
    AssetDisposalRequest,
    AssetResaleListing,
    AssetTradeIn,
    AssetScrapSalvage,
    AssetComplianceFramework,
    AssetComplianceAudit,
    AssetPermitLicense,
    AssetComplianceIncident,
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
def location_b2(db, tenant_b):
    return Location.objects.create(
        tenant=tenant_b,
        code="WH-BAY2-B",
        name="Globex Bay 2 Yard",
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
        starting_book_value=Decimal("120000.00"),
        salvage_value=Decimal("12000.00"),
        accumulated_depreciation_prior=Decimal("0.00"),
        useful_life_months_total=60,
        depreciation_amount=Decimal("1800.00"),
        accumulated_depreciation_after=Decimal("1800.00"),
        ending_book_value=Decimal("118200.00"),
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
        starting_book_value=Decimal("45000.00"),
        salvage_value=Decimal("5000.00"),
        accumulated_depreciation_prior=Decimal("0.00"),
        useful_life_months_total=48,
        depreciation_amount=Decimal("833.33"),
        accumulated_depreciation_after=Decimal("833.33"),
        ending_book_value=Decimal("44166.67"),
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
        transportation_cost=Decimal("750.00"),
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
        transportation_cost=Decimal("250.00"),
        status="draft",
    )


# ==============================================================================
# Sub-module 11.5: Maintenance & Repair Management Fixtures
# ==============================================================================

@pytest.fixture
def service_contract_a(db, tenant_a, vendor_party_a, fixed_asset_a, operational_asset_a, currency_usd):
    today = timezone.now().date()
    return AssetServiceContract.objects.create(
        tenant=tenant_a,
        contract_number="AMC-ACME-2026-001",
        title="Comprehensive CNC Maintenance Agreement",
        contract_type="comprehensive_amc",
        vendor=vendor_party_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        start_date=today,
        end_date=today + timezone.timedelta(days=365),
        contract_value=Decimal("12000.00"),
        currency=currency_usd,
        billing_frequency="annual",
        sla_response_hours=4,
        sla_resolution_hours=24,
        pm_visits_included=4,
        pm_visits_completed=0,
        coverage_terms="Full mechanical and electrical coverage including replacement seals.",
        auto_renew=True,
        contact_person="John Service",
        contact_phone="+1-555-0199",
        contact_email="service@apexmachinery.com",
        status="active",
    )


@pytest.fixture
def service_contract_b(db, tenant_b, vendor_party_b, fixed_asset_b, operational_asset_b, currency_usd):
    today = timezone.now().date()
    return AssetServiceContract.objects.create(
        tenant=tenant_b,
        contract_number="AMC-GLOBEX-2026-001",
        title="Globex Hydraulic SLA",
        contract_type="labor_only",
        vendor=vendor_party_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        start_date=today,
        end_date=today + timezone.timedelta(days=180),
        contract_value=Decimal("6000.00"),
        currency=currency_usd,
        billing_frequency="quarterly",
        sla_response_hours=8,
        sla_resolution_hours=48,
        pm_visits_included=2,
        pm_visits_completed=0,
        status="active",
    )


@pytest.fixture
def maintenance_schedule_a(db, tenant_a, fixed_asset_a, operational_asset_a, admin_user, vendor_party_a, service_contract_a):
    today = timezone.now().date()
    return AssetMaintenanceSchedule.objects.create(
        tenant=tenant_a,
        name="Quarterly Spindle & Bearing Inspection",
        schedule_type="time_based",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        frequency_interval=3,
        frequency_unit="months",
        next_due_date=today + timezone.timedelta(days=90),
        lead_time_days=7,
        meter_trigger_threshold=500,
        is_mandatory=True,
        is_active=True,
        preferred_vendor=vendor_party_a,
        assigned_technician=admin_user,
        service_contract=service_contract_a,
        service_checklist="1. Clean air filter\n2. Inspect drive belt\n3. Lubricate bearings",
        status="active",
    )


@pytest.fixture
def maintenance_schedule_b(db, tenant_b, fixed_asset_b, operational_asset_b, admin_b, vendor_party_b, service_contract_b):
    today = timezone.now().date()
    return AssetMaintenanceSchedule.objects.create(
        tenant=tenant_b,
        name="Globex Monthly Fluid Check",
        schedule_type="time_based",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        frequency_interval=1,
        frequency_unit="months",
        next_due_date=today + timezone.timedelta(days=30),
        lead_time_days=3,
        is_mandatory=False,
        is_active=True,
        preferred_vendor=vendor_party_b,
        assigned_technician=admin_b,
        service_contract=service_contract_b,
        status="active",
    )


@pytest.fixture
def maintenance_request_a(db, tenant_a, fixed_asset_a, operational_asset_a, admin_user, org_unit_a, service_contract_a):
    return AssetMaintenanceRequest.objects.create(
        tenant=tenant_a,
        title="Spindle Vibration and Overheating Warning",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        requester=admin_user,
        department=org_unit_a,
        request_type="breakdown_repair",
        urgency="high",
        is_breakdown=True,
        downtime_started_at=timezone.now(),
        symptom_description="High-frequency vibration detected at spindle head during full RPM cutting.",
        status="submitted",
    )


@pytest.fixture
def maintenance_request_b(db, tenant_b, fixed_asset_b, operational_asset_b, admin_b, org_unit_b, service_contract_b):
    return AssetMaintenanceRequest.objects.create(
        tenant=tenant_b,
        title="Globex Hydraulic Cylinder Leak",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        requester=admin_b,
        department=org_unit_b,
        request_type="breakdown_repair",
        urgency="critical",
        is_breakdown=True,
        downtime_started_at=timezone.now(),
        symptom_description="Hydraulic pressure dropping rapidly under heavy load.",
        status="submitted",
    )


@pytest.fixture
def maintenance_log_a(db, tenant_a, fixed_asset_a, operational_asset_a, maintenance_request_a, maintenance_schedule_a, service_contract_a, admin_user, vendor_party_a, expense_account_a):
    now = timezone.now()
    return AssetMaintenanceLog.objects.create(
        tenant=tenant_a,
        maintenance_type="corrective_repair",
        service_date=now.date(),
        completion_date=now,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        maintenance_request=maintenance_request_a,
        maintenance_schedule=maintenance_schedule_a,
        service_contract=service_contract_a,
        lead_technician=admin_user,
        service_vendor=vendor_party_a,
        failure_code="mechanical_wear",
        downtime_hours=Decimal("4.50"),
        labor_hours=Decimal("6.00"),
        labor_cost=Decimal("450.00"),
        parts_cost=Decimal("350.00"),
        vendor_invoice_cost=Decimal("0.00"),
        total_cost=Decimal("800.00"),
        parts_consumed_summary="1x High-speed ceramic bearing #BRG-44\n1x Viton seal #VS-12",
        root_cause_analysis="Lubrication starvation caused inner race scoring.",
        action_taken="Flushed bearing housing, installed replacement ceramic bearing, replenished synthetic grease.",
        expense_account=expense_account_a,
        status="draft",
    )


@pytest.fixture
def maintenance_log_b(db, tenant_b, fixed_asset_b, operational_asset_b, maintenance_request_b, maintenance_schedule_b, service_contract_b, admin_b, vendor_party_b, expense_account_b):
    now = timezone.now()
    return AssetMaintenanceLog.objects.create(
        tenant=tenant_b,
        maintenance_type="emergency_breakdown",
        service_date=now.date(),
        completion_date=now,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        maintenance_request=maintenance_request_b,
        maintenance_schedule=maintenance_schedule_b,
        service_contract=service_contract_b,
        lead_technician=admin_b,
        service_vendor=vendor_party_b,
        failure_code="hydraulic_leak",
        downtime_hours=Decimal("8.00"),
        labor_hours=Decimal("8.00"),
        labor_cost=Decimal("480.00"),
        parts_cost=Decimal("220.00"),
        vendor_invoice_cost=Decimal("0.00"),
        total_cost=Decimal("700.00"),
        expense_account=expense_account_b,
        status="draft",
    )


# ---------------------------------------------------------------------------
# Module 11.6: Asset Performance & Utilization Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def downtime_log_a(db, tenant_a, fixed_asset_a, operational_asset_a, org_unit_a, admin_user):
    now = timezone.now()
    return AssetDowntimeLog.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        department=org_unit_a,
        logged_by=admin_user,
        downtime_category="unplanned_breakdown",
        impact_level="full_shutdown",
        started_at=now - timezone.timedelta(hours=3),
        ended_at=now,
        duration_minutes=Decimal("180.00"),
        hourly_cost_rate=Decimal("150.00"),
        total_downtime_cost=Decimal("450.00"),
        failure_description="Spindle bearing seizure under heavy cutting load.",
        root_cause_code="mechanical_failure",
        status="active",
    )


@pytest.fixture
def downtime_log_b(db, tenant_b, fixed_asset_b, operational_asset_b, org_unit_b, admin_b):
    now = timezone.now()
    return AssetDowntimeLog.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        department=org_unit_b,
        logged_by=admin_b,
        downtime_category="planned_maintenance",
        impact_level="minor_stop",
        started_at=now - timezone.timedelta(hours=1),
        ended_at=now,
        duration_minutes=Decimal("60.00"),
        hourly_cost_rate=Decimal("100.00"),
        total_downtime_cost=Decimal("100.00"),
        failure_description="Scheduled hydraulic fluid flush and filter replacement.",
        root_cause_code="operational_issue",
        status="active",
    )


@pytest.fixture
def oee_record_a(db, tenant_a, fixed_asset_a, operational_asset_a, admin_user):
    return AssetOeeRecord.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        recorded_by=admin_user,
        record_date=timezone.now().date(),
        shift_name="Shift 1",
        planned_production_time_minutes=Decimal("480.00"),
        operating_time_minutes=Decimal("420.00"),
        ideal_cycle_time_seconds=Decimal("30.00"),
        total_units_produced=800,
        good_units_produced=780,
        defect_units_count=20,
        rework_units_count=5,
        breakdown_loss_minutes=Decimal("30.00"),
        setup_loss_minutes=Decimal("30.00"),
        small_stops_loss_minutes=Decimal("10.00"),
        reduced_speed_loss_minutes=Decimal("10.00"),
        defect_loss_minutes=Decimal("10.00"),
        startup_loss_minutes=Decimal("5.00"),
        availability_percentage=Decimal("87.50"),
        performance_percentage=Decimal("95.24"),
        quality_percentage=Decimal("97.50"),
        oee_percentage=Decimal("81.25"),
        status="draft",
    )


@pytest.fixture
def oee_record_b(db, tenant_b, fixed_asset_b, operational_asset_b, admin_b):
    return AssetOeeRecord.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        recorded_by=admin_b,
        record_date=timezone.now().date(),
        shift_name="Shift 2",
        planned_production_time_minutes=Decimal("480.00"),
        operating_time_minutes=Decimal("360.00"),
        ideal_cycle_time_seconds=Decimal("45.00"),
        total_units_produced=450,
        good_units_produced=420,
        defect_units_count=30,
        rework_units_count=10,
        availability_percentage=Decimal("75.00"),
        performance_percentage=Decimal("93.75"),
        quality_percentage=Decimal("93.33"),
        oee_percentage=Decimal("65.62"),
        status="draft",
    )


@pytest.fixture
def energy_reading_a(db, tenant_a, fixed_asset_a, operational_asset_a, vendor_party_a, admin_user):
    return AssetEnergyReading.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        utility_provider=vendor_party_a,
        recorded_by=admin_user,
        reading_timestamp=timezone.now(),
        utility_type="electricity",
        consumption_value=Decimal("285.5000"),
        unit_of_measure="kWh",
        peak_demand_kw=Decimal("45.20"),
        power_factor=Decimal("0.950"),
        operating_hours=Decimal("8.00"),
        units_produced=100,
        cost_per_unit=Decimal("0.1450"),
        total_energy_cost=Decimal("41.40"),
        ghg_scope="scope_2",
        emission_factor=Decimal("0.3850"),
        carbon_emissions_kg_co2e=Decimal("109.92"),
        status="pending",
    )


@pytest.fixture
def energy_reading_b(db, tenant_b, fixed_asset_b, operational_asset_b, vendor_party_b, admin_b):
    return AssetEnergyReading.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        utility_provider=vendor_party_b,
        recorded_by=admin_b,
        reading_timestamp=timezone.now(),
        utility_type="diesel",
        consumption_value=Decimal("150.0000"),
        unit_of_measure="liters",
        operating_hours=Decimal("10.00"),
        units_produced=50,
        cost_per_unit=Decimal("1.2500"),
        total_energy_cost=Decimal("187.50"),
        ghg_scope="scope_1",
        emission_factor=Decimal("2.6800"),
        carbon_emissions_kg_co2e=Decimal("402.00"),
        status="pending",
    )


@pytest.fixture
def performance_scorecard_a(db, tenant_a, fixed_asset_a, operational_asset_a, org_unit_a, admin_user):
    today = timezone.now().date()
    return AssetPerformanceScorecard.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        department=org_unit_a,
        evaluated_by=admin_user,
        period_type="monthly",
        period_start=today.replace(day=1),
        period_end=today,
        total_calendar_hours=Decimal("720.00"),
        planned_operating_hours=Decimal("500.00"),
        actual_operating_hours=Decimal("460.00"),
        unplanned_downtime_hours=Decimal("25.00"),
        planned_downtime_hours=Decimal("15.00"),
        failure_event_count=2,
        capacity_utilization_rate=Decimal("92.00"),
        availability_rate=Decimal("94.85"),
        mtbf_hours=Decimal("230.00"),
        mttr_hours=Decimal("12.50"),
        average_oee_percentage=Decimal("82.50"),
        total_energy_consumption_kwh=Decimal("14250.00"),
        total_carbon_emissions_kg=Decimal("5486.25"),
        total_downtime_cost=Decimal("3750.00"),
        performance_index_score=Decimal("86.50"),
        benchmark_grade="grade_b",
        status="draft",
    )


@pytest.fixture
def performance_scorecard_b(db, tenant_b, fixed_asset_b, operational_asset_b, org_unit_b, admin_b):
    today = timezone.now().date()
    return AssetPerformanceScorecard.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        department=org_unit_b,
        evaluated_by=admin_b,
        period_type="monthly",
        period_start=today.replace(day=1),
        period_end=today,
        total_calendar_hours=Decimal("720.00"),
        planned_operating_hours=Decimal("400.00"),
        actual_operating_hours=Decimal("320.00"),
        unplanned_downtime_hours=Decimal("60.00"),
        planned_downtime_hours=Decimal("20.00"),
        failure_event_count=5,
        capacity_utilization_rate=Decimal("80.00"),
        availability_rate=Decimal("84.21"),
        mtbf_hours=Decimal("64.00"),
        mttr_hours=Decimal("12.00"),
        average_oee_percentage=Decimal("68.00"),
        total_energy_consumption_kwh=Decimal("9800.00"),
        total_carbon_emissions_kg=Decimal("3773.00"),
        total_downtime_cost=Decimal("6000.00"),
        performance_index_score=Decimal("68.20"),
        benchmark_grade="grade_c",
        status="draft",
    )


# ==============================================================================
# Sub-module 11.7: Asset Reliability & Condition Monitoring Fixtures
# ==============================================================================

@pytest.fixture
def condition_assessment_a(db, tenant_a, fixed_asset_a, operational_asset_a, category_root_a, admin_user, vendor_party_a):
    return AssetConditionAssessment.objects.create(
        tenant=tenant_a,
        title="Spindle Ultrasound & Bearing Vibration Analysis",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        assessment_type="ndt_ultrasonic",
        assessment_date=timezone.now().date(),
        condition_grade="grade_2_good",
        operating_status="normal_operation",
        health_score=82,
        inspector=admin_user,
        external_inspector=vendor_party_a,
        findings="Minor acoustic turbulence observed at drive-end bearing; well within OEM operating baseline.",
        recommendations="Continue routine lubrication cycle; re-inspect during next PM interval.",
        followup_required=False,
        status="draft",
    )


@pytest.fixture
def condition_assessment_b(db, tenant_b, fixed_asset_b, operational_asset_b, category_root_b, admin_b):
    return AssetConditionAssessment.objects.create(
        tenant=tenant_b,
        title="Globex Stacker Mast Thermography",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        asset_category=category_root_b,
        assessment_type="ndt_thermography",
        assessment_date=timezone.now().date(),
        condition_grade="grade_3_fair",
        operating_status="operational_with_defects",
        health_score=65,
        inspector=admin_b,
        findings="Elevated thermal delta of 18C on secondary hydraulic manifold.",
        recommendations="Inspect flow bypass relief valve.",
        followup_required=True,
        status="draft",
    )


@pytest.fixture
def telemetry_reading_a(db, tenant_a, fixed_asset_a, operational_asset_a, admin_user):
    return AssetTelemetryReading.objects.create(
        tenant=tenant_a,
        sensor_identifier="SENS-VIB-01",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        source="iot_sensor",
        metric_type="vibration_velocity_rms",
        metric_unit="mm_per_s",
        recorded_at=timezone.now(),
        reading_value=Decimal("4.2000"),
        baseline_value=Decimal("3.5000"),
        deviation_percentage=Decimal("20.00"),
        threshold_status="normal",
        is_anomaly=False,
        recorded_by=admin_user,
        alert_notes="Steady state production cut.",
    )


@pytest.fixture
def telemetry_reading_b(db, tenant_b, fixed_asset_b, operational_asset_b, admin_b):
    return AssetTelemetryReading.objects.create(
        tenant=tenant_b,
        sensor_identifier="SENS-TEMP-02",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        source="scada_historian",
        metric_type="bearing_temperature",
        metric_unit="celsius",
        recorded_at=timezone.now(),
        reading_value=Decimal("88.5000"),
        baseline_value=Decimal("65.0000"),
        deviation_percentage=Decimal("36.15"),
        threshold_status="warning",
        is_anomaly=False,
        recorded_by=admin_b,
        alert_notes="Temperature approaching critical boundary.",
    )


@pytest.fixture
def failure_mode_a(db, tenant_a, fixed_asset_a, operational_asset_a, category_root_a, admin_user, maintenance_schedule_a):
    return AssetFailureMode.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        component_subsystem="Spindle Assembly",
        function_description="Deliver rotary torque up to 12,000 RPM with < 0.005mm runout.",
        functional_failure="Spindle seized or excessive radial deflection.",
        failure_mode="Ceramic hybrid bearing brinelling and micro-spalling",
        failure_cause="Contamination ingress or lubricant breakdown under extreme cutting feeds.",
        failure_effect="Loss of machined part concentricity and unrecoverable workpiece scrap.",
        severity_score=7,
        occurrence_score=5,
        detection_score=4,
        rpn=140,
        risk_level="medium",
        rcm_strategy="condition_based",
        strategy_rationale="Vibration accelerometer provides 200+ hours early detection window.",
        mitigation_task="Conduct high-frequency FFT vibration sweep and inspect seal labyrinth.",
        linked_maintenance_schedule=maintenance_schedule_a,
        assessed_by=admin_user,
        status="draft",
    )


@pytest.fixture
def failure_mode_b(db, tenant_b, fixed_asset_b, operational_asset_b, category_root_b, admin_b, maintenance_schedule_b):
    return AssetFailureMode.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        asset_category=category_root_b,
        component_subsystem="Hydraulic Lift Cylinder",
        function_description="Elevate fork carriages up to 4500mm.",
        functional_failure="Mast drift under rated 2.5 ton load.",
        failure_mode="Rod gland polyurethane seal extrusion",
        failure_cause="Thermal breakdown from contaminated hydraulic oil.",
        failure_effect="Drift during overhead pallet placement posing severe hazard.",
        severity_score=8,
        occurrence_score=6,
        detection_score=5,
        rpn=240,
        risk_level="high",
        rcm_strategy="time_based_pm",
        strategy_rationale="Replace seals periodically before extrusion threshold.",
        mitigation_task="Replace hydraulic packing kit and flush cylinder bore.",
        linked_maintenance_schedule=maintenance_schedule_b,
        assessed_by=admin_b,
        status="draft",
    )


@pytest.fixture
def calibration_record_a(db, tenant_a, fixed_asset_a, operational_asset_a, admin_user, vendor_party_a):
    today = timezone.now().date()
    return AssetCalibrationRecord.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        instrument_tag="INST-PT-001",
        reference_standard_used="Fluke 754 Documenting Process Calibrator (NIST Ref: 98124)",
        calibration_date=today,
        calibration_frequency_days=365,
        next_due_date=today + timezone.timedelta(days=365),
        setpoint_nominal=Decimal("50.0000"),
        as_found_reading=Decimal("49.8500"),
        as_found_error=Decimal("-0.1500"),
        as_left_reading=Decimal("50.0100"),
        as_left_error=Decimal("0.0100"),
        allowable_tolerance=Decimal("0.2500"),
        tolerance_unit="psi",
        calibration_result="pass",
        calibrated_by=admin_user,
        service_vendor=vendor_party_a,
        certificate_number="CERT-CAL-2026-089",
        certificate_expiry=today + timezone.timedelta(days=365),
        status="valid",
        notes="Transmitter verified within OEM tolerance envelope.",
    )


@pytest.fixture
def calibration_record_b(db, tenant_b, fixed_asset_b, operational_asset_b, admin_b, vendor_party_b):
    today = timezone.now().date()
    return AssetCalibrationRecord.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        instrument_tag="INST-TC-002",
        reference_standard_used="Hart Scientific Dry Well Calibrator #9103",
        calibration_date=today,
        calibration_frequency_days=180,
        next_due_date=today + timezone.timedelta(days=180),
        setpoint_nominal=Decimal("100.0000"),
        as_found_reading=Decimal("102.8000"),
        as_found_error=Decimal("2.8000"),
        as_left_reading=Decimal("100.2000"),
        as_left_error=Decimal("0.2000"),
        allowable_tolerance=Decimal("1.0000"),
        tolerance_unit="celsius",
        calibration_result="pass_with_adjustment",
        calibrated_by=admin_b,
        service_vendor=vendor_party_b,
        certificate_number="CERT-CAL-GLOBEX-002",
        certificate_expiry=today + timezone.timedelta(days=180),
        status="valid",
        notes="Adjusted offset potentiometer by -2.6C.",
    )


# ==============================================================================
# Sub-module 11.8: Warranty & Insurance Management Fixtures
# ==============================================================================

@pytest.fixture
def underwriter_party_a(db, tenant_a):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Travelers Industrial Underwriters",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role="partner",
        status="active",
    )
    return party


@pytest.fixture
def underwriter_party_b(db, tenant_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Zurich Commercial Global",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role="partner",
        status="active",
    )
    return party


@pytest.fixture
def broker_party_a(db, tenant_a):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Marsh McLennan Risk Advisory",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role="partner",
        status="active",
    )
    return party


@pytest.fixture
def broker_party_b(db, tenant_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Aon Risk Solutions",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role="partner",
        status="active",
    )
    return party


@pytest.fixture
def adjuster_party_a(db, tenant_a):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Crawford & Company Adjusters",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role="partner",
        status="active",
    )
    return party


@pytest.fixture
def adjuster_party_b(db, tenant_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Sedgwick Claims Management",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role="partner",
        status="active",
    )
    return party


@pytest.fixture
def warranty_a(db, tenant_a, fixed_asset_a, operational_asset_a, vendor_party_a, currency_usd, admin_user):
    today = timezone.now().date()
    return AssetWarranty.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        warrantor_party=vendor_party_a,
        warranty_type="oem_standard",
        coverage_scope="comprehensive",
        title="Centrifugal Compressor OEM Factory Warranty",
        warranty_certificate_number="WARR-CERT-ACME-001",
        start_date=today - timezone.timedelta(days=30),
        end_date=today + timezone.timedelta(days=335),
        deductible_amount=Decimal("250.00"),
        contract_purchase_price=Decimal("1500.00"),
        currency=currency_usd,
        status="active",
        registered_by=admin_user,
        terms_and_conditions="Full parts and labor for manufacturing defects.",
    )


@pytest.fixture
def warranty_b(db, tenant_b, fixed_asset_b, operational_asset_b, vendor_party_b, currency_usd, admin_b):
    today = timezone.now().date()
    return AssetWarranty.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        warrantor_party=vendor_party_b,
        warranty_type="oem_extended",
        coverage_scope="powertrain_major_components",
        title="Globex Generator Extended Powertrain Warranty",
        warranty_certificate_number="WARR-CERT-GLOBEX-002",
        start_date=today - timezone.timedelta(days=60),
        end_date=today + timezone.timedelta(days=305),
        deductible_amount=Decimal("500.00"),
        contract_purchase_price=Decimal("2500.00"),
        currency=currency_usd,
        status="active",
        registered_by=admin_b,
        terms_and_conditions="Powertrain component defects and mechanical seizure.",
    )


@pytest.fixture
def warranty_claim_a(db, tenant_a, warranty_a, fixed_asset_a, operational_asset_a, currency_usd, admin_user):
    today = timezone.now().date()
    return AssetWarrantyClaim.objects.create(
        tenant=tenant_a,
        warranty=warranty_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        title="Impeller Shaft Fatigue Fracture",
        defect_description="Fatigue crack detected on high-pressure impeller shaft stage 2.",
        incident_date=today - timezone.timedelta(days=10),
        claimed_amount=Decimal("3200.00"),
        approved_amount=Decimal("0.00"),
        deductible_applied=Decimal("250.00"),
        net_recovery_amount=Decimal("0.00"),
        currency=currency_usd,
        claim_status="submitted",
        filed_by=admin_user,
    )


@pytest.fixture
def warranty_claim_b(db, tenant_b, warranty_b, fixed_asset_b, operational_asset_b, currency_usd, admin_b):
    today = timezone.now().date()
    return AssetWarrantyClaim.objects.create(
        tenant=tenant_b,
        warranty=warranty_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        title="Rotor Core Insulation Breakdown",
        defect_description="Insulation resistance dropped below 1M ohm during routine run.",
        incident_date=today - timezone.timedelta(days=12),
        claimed_amount=Decimal("5500.00"),
        approved_amount=Decimal("0.00"),
        deductible_applied=Decimal("500.00"),
        net_recovery_amount=Decimal("0.00"),
        currency=currency_usd,
        claim_status="submitted",
        filed_by=admin_b,
    )


@pytest.fixture
def insurance_policy_a(db, tenant_a, underwriter_party_a, broker_party_a, fixed_asset_a, operational_asset_a, currency_usd, admin_user):
    today = timezone.now().date()
    return AssetInsurancePolicy.objects.create(
        tenant=tenant_a,
        policy_number="POL-2026-ACME-IND-01",
        title="Industrial Machinery Breakdown & All Risk Policy",
        policy_type="machinery_breakdown",
        underwriter_party=underwriter_party_a,
        broker_party=broker_party_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        effective_date=today - timezone.timedelta(days=60),
        expiration_date=today + timezone.timedelta(days=305),
        annual_premium=Decimal("12000.00"),
        premium_frequency="annual",
        total_insured_value=Decimal("250000.00"),
        deductible_retention=Decimal("5000.00"),
        valuation_basis="replacement_cost_value",
        currency=currency_usd,
        status="active",
        risk_manager=admin_user,
        coverage_terms="Covers sudden and accidental mechanical and electrical breakdown.",
    )


@pytest.fixture
def insurance_policy_b(db, tenant_b, underwriter_party_b, broker_party_b, fixed_asset_b, operational_asset_b, currency_usd, admin_b):
    today = timezone.now().date()
    return AssetInsurancePolicy.objects.create(
        tenant=tenant_b,
        policy_number="POL-2026-GLOBEX-ENG-02",
        title="Globex Fleet & Heavy Equipment All Risk Policy",
        policy_type="comprehensive_all_risk",
        underwriter_party=underwriter_party_b,
        broker_party=broker_party_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        effective_date=today - timezone.timedelta(days=90),
        expiration_date=today + timezone.timedelta(days=275),
        annual_premium=Decimal("18500.00"),
        premium_frequency="semi_annual",
        total_insured_value=Decimal("400000.00"),
        deductible_retention=Decimal("7500.00"),
        valuation_basis="replacement_cost_value",
        currency=currency_usd,
        status="active",
        risk_manager=admin_b,
        coverage_terms="Property damage, fire, flood, and equipment collision.",
    )


@pytest.fixture
def insurance_claim_a(db, tenant_a, insurance_policy_a, fixed_asset_a, operational_asset_a, adjuster_party_a, currency_usd, admin_user):
    today = timezone.now().date()
    return AssetInsuranceClaim.objects.create(
        tenant=tenant_a,
        policy=insurance_policy_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        adjuster_party=adjuster_party_a,
        title="Stator Winding Arcing and Core Damage",
        incident_description="Grid power surge induced stator insulation flashover and thermal burn.",
        incident_location="Plant 1 - Main Compressor Bay",
        incident_date=today - timezone.timedelta(days=15),
        peril_type="electrical_arcing_surge",
        claimed_loss_amount=Decimal("28000.00"),
        deductible_applied=Decimal("5000.00"),
        settlement_payout_amount=Decimal("0.00"),
        salvage_recovery_amount=Decimal("0.00"),
        currency=currency_usd,
        claim_status="proof_of_loss_filed",
        claims_officer=admin_user,
    )


@pytest.fixture
def insurance_claim_b(db, tenant_b, insurance_policy_b, fixed_asset_b, operational_asset_b, adjuster_party_b, currency_usd, admin_b):
    today = timezone.now().date()
    return AssetInsuranceClaim.objects.create(
        tenant=tenant_b,
        policy=insurance_policy_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        adjuster_party=adjuster_party_b,
        title="Cooling Tower Basin Hydraulic Rupture",
        incident_description="Freezing rupture on heat-exchanger supply piping and flooded sump.",
        incident_location="Globex Site B - Pump House",
        incident_date=today - timezone.timedelta(days=20),
        peril_type="water_liquid_damage",
        claimed_loss_amount=Decimal("35000.00"),
        deductible_applied=Decimal("7500.00"),
        settlement_payout_amount=Decimal("0.00"),
        salvage_recovery_amount=Decimal("0.00"),
        currency=currency_usd,
        claim_status="proof_of_loss_filed",
        claims_officer=admin_b,
    )


# ==========================================
# Sub-module 11.9: Asset Disposal Fixtures
# ==========================================

@pytest.fixture
def disposal_request_a(db, tenant_a, fixed_asset_a, operational_asset_a, category_root_a, admin_user):
    return AssetDisposalRequest.objects.create(
        tenant=tenant_a,
        title="CNC Milling Center Secondary Market Resale Initiative",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        category=category_root_a,
        requested_by=admin_user,
        disposal_method="resale",
        retirement_reason="technological_obsolescence",
        justification_notes="Production upgraded to high-speed machining centers.",
        acquisition_cost=Decimal("75000.00"),
        accumulated_depreciation=Decimal("45000.00"),
        net_book_value=Decimal("30000.00"),
        estimated_residual_value=Decimal("35000.00"),
        estimated_removal_cost=Decimal("2000.00"),
        status="approved",
    )


@pytest.fixture
def disposal_request_b(db, tenant_b, fixed_asset_b, operational_asset_b, category_root_b, admin_b):
    return AssetDisposalRequest.objects.create(
        tenant=tenant_b,
        title="Globex Hydraulic Press Scrapping and Salvage Order",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        category=category_root_b,
        requested_by=admin_b,
        disposal_method="scrap_salvage",
        retirement_reason="uneconomical_repair",
        justification_notes="Catastrophic hydraulic manifold blowout beyond repair.",
        acquisition_cost=Decimal("50000.00"),
        accumulated_depreciation=Decimal("40000.00"),
        net_book_value=Decimal("10000.00"),
        estimated_residual_value=Decimal("5000.00"),
        estimated_removal_cost=Decimal("1500.00"),
        status="in_progress",
    )


@pytest.fixture
def resale_listing_a(db, tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a, admin_user):
    today = timezone.now().date()
    return AssetResaleListing.objects.create(
        tenant=tenant_a,
        disposal_request=disposal_request_a,
        fixed_asset=fixed_asset_a,
        buyer=vendor_party_a,
        broker_auctioneer=vendor_party_a,
        managed_by=admin_user,
        listing_channel="online_marketplace",
        listing_reference="LOT-CNC-9901",
        listing_date=today - timezone.timedelta(days=10),
        reserve_price=Decimal("30000.00"),
        asking_price=Decimal("38000.00"),
        highest_bid_amount=Decimal("36500.00"),
        gross_sale_proceeds=Decimal("36500.00"),
        commission_rate_percent=Decimal("5.00"),
        commission_amount=Decimal("1825.00"),
        net_sale_proceeds=Decimal("34675.00"),
        status="sold",
        payment_status="pending",
    )


@pytest.fixture
def resale_listing_b(db, tenant_b, disposal_request_b, fixed_asset_b, vendor_party_b, admin_b):
    today = timezone.now().date()
    return AssetResaleListing.objects.create(
        tenant=tenant_b,
        disposal_request=disposal_request_b,
        fixed_asset=fixed_asset_b,
        buyer=vendor_party_b,
        managed_by=admin_b,
        listing_channel="private_treaty",
        listing_reference="LOT-HYD-5502",
        listing_date=today - timezone.timedelta(days=5),
        reserve_price=Decimal("8000.00"),
        asking_price=Decimal("12000.00"),
        highest_bid_amount=Decimal("9500.00"),
        status="listed",
        payment_status="pending",
    )


@pytest.fixture
def trade_in_a(db, tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a, admin_user):
    today = timezone.now().date()
    return AssetTradeIn.objects.create(
        tenant=tenant_a,
        disposal_request=disposal_request_a,
        retired_fixed_asset=fixed_asset_a,
        vendor=vendor_party_a,
        authorized_by=admin_user,
        agreement_number="AGR-TRD-2026-001",
        agreement_date=today - timezone.timedelta(days=12),
        trade_in_allowance=Decimal("15000.00"),
        status="accepted",
    )


@pytest.fixture
def trade_in_b(db, tenant_b, disposal_request_b, fixed_asset_b, vendor_party_b, admin_b):
    today = timezone.now().date()
    return AssetTradeIn.objects.create(
        tenant=tenant_b,
        disposal_request=disposal_request_b,
        retired_fixed_asset=fixed_asset_b,
        vendor=vendor_party_b,
        authorized_by=admin_b,
        agreement_number="AGR-GLX-2026-999",
        agreement_date=today - timezone.timedelta(days=15),
        trade_in_allowance=Decimal("8000.00"),
        status="proposed",
    )


@pytest.fixture
def scrap_salvage_a(db, tenant_a, disposal_request_a, fixed_asset_a, operational_asset_a, vendor_party_a, admin_user):
    return AssetScrapSalvage.objects.create(
        tenant=tenant_a,
        disposal_request=disposal_request_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        recycler_partner=vendor_party_a,
        supervisor=admin_user,
        scrap_method="dismantling_parts_recovery",
        has_hazardous_materials=True,
        hazardous_waste_class="RCRA Class I Heavy Sludge",
        epa_manifest_number="EPA-MNF-2026-4412",
        cod_number="COD-REC-9941",
        total_scrap_weight_kg=Decimal("1250.00"),
        salvage_proceeds=Decimal("2500.00"),
        dismantling_cost=Decimal("450.00"),
        net_salvage_recovery=Decimal("2050.00"),
        status="dismantling",
    )


@pytest.fixture
def scrap_salvage_b(db, tenant_b, disposal_request_b, fixed_asset_b, operational_asset_b, vendor_party_b, admin_b):
    return AssetScrapSalvage.objects.create(
        tenant=tenant_b,
        disposal_request=disposal_request_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        recycler_partner=vendor_party_b,
        supervisor=admin_b,
        scrap_method="shredding_recycling",
        total_scrap_weight_kg=Decimal("850.00"),
        salvage_proceeds=Decimal("1200.00"),
        dismantling_cost=Decimal("200.00"),
        net_salvage_recovery=Decimal("1000.00"),
        status="scrap_transferred",
    )


# -------------------------------------------------------------------------
# Sub-module 11.11: Compliance & Regulatory Management fixtures
# -------------------------------------------------------------------------
@pytest.fixture
def category_a(category_root_a):
    return category_root_a


@pytest.fixture
def category_b(category_root_b):
    return category_root_b


@pytest.fixture

def compliance_framework_a(db, tenant_a, category_a, vendor_party_a):
    today = timezone.now().date()
    return AssetComplianceFramework.objects.create(
        tenant=tenant_a,
        name="OSHA 1910.119 Process Safety Management",
        code="OSHA-1910-PSM",
        framework_type="regulatory",
        regulatory_agency=vendor_party_a,
        applicable_category=category_a,
        effective_date=today - timezone.timedelta(days=365),
        revision="2024 Edition",
        mandatory_audit_cycle_months=12,
        readiness_score=94,
        description="Mandatory standard for highly hazardous chemicals.",
        status="active",
    )


@pytest.fixture
def compliance_framework_b(db, tenant_b, category_b, vendor_party_b):
    today = timezone.now().date()
    return AssetComplianceFramework.objects.create(
        tenant=tenant_b,
        name="ISO 55001 Asset Management Systems",
        code="ISO-55001",
        framework_type="voluntary_standard",
        regulatory_agency=vendor_party_b,
        applicable_category=category_b,
        effective_date=today - timezone.timedelta(days=180),
        revision="2024 Edition",
        mandatory_audit_cycle_months=24,
        readiness_score=85,
        description="Asset management systems requirements.",
        status="active",
    )


@pytest.fixture
def compliance_audit_a(db, tenant_a, compliance_framework_a, operational_asset_a, admin_user, vendor_party_a):
    today = timezone.now().date()
    return AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        title="Annual Plant Machine Guarding Verification",
        framework=compliance_framework_a,
        asset=operational_asset_a,
        audit_type="internal",
        lead_auditor_user=admin_user,
        auditor_party=vendor_party_a,
        audit_date=today - timezone.timedelta(days=30),
        scope_description="Verification of physical barrier interlocks and e-stops.",
        total_checkpoints=40,
        passed_checkpoints=40,
        minor_findings_count=0,
        major_findings_count=0,
        critical_findings_count=0,
        compliance_rating="fully_compliant",
        summary_findings="All machine guards secure.",
        status="completed",
        completed_at=timezone.now() - timezone.timedelta(days=29),
    )


@pytest.fixture
def compliance_audit_b(db, tenant_b, compliance_framework_b, operational_asset_b, admin_b, vendor_party_b):
    today = timezone.now().date()
    return AssetComplianceAudit.objects.create(
        tenant=tenant_b,
        title="Globex ISO Surveillance Audit",
        framework=compliance_framework_b,
        asset=operational_asset_b,
        audit_type="external_regulatory",
        lead_auditor_user=admin_b,
        auditor_party=vendor_party_b,
        audit_date=today - timezone.timedelta(days=15),
        scope_description="Life cycle surveillance.",
        total_checkpoints=30,
        passed_checkpoints=28,
        minor_findings_count=2,
        major_findings_count=0,
        critical_findings_count=0,
        compliance_rating="minor_deficiencies",
        status="scheduled",
    )


@pytest.fixture
def permit_license_a(db, tenant_a, operational_asset_a, vendor_party_a):
    today = timezone.now().date()
    return AssetPermitLicense.objects.create(
        tenant=tenant_a,
        permit_name="High-Pressure Steam Boiler Operating Certificate",
        permit_number="BOILER-CERT-1001",
        permit_type="pressure_vessel",
        asset=operational_asset_a,
        issuing_authority=vendor_party_a,
        issue_date=today - timezone.timedelta(days=90),
        effective_date=today - timezone.timedelta(days=90),
        expiration_date=today + timezone.timedelta(days=275),
        renewal_lead_days=60,
        renewal_fee=Decimal("750.00"),
        operating_conditions="Max pressure 250 PSIG.",
        status="active",
    )


@pytest.fixture
def permit_license_b(db, tenant_b, operational_asset_b, vendor_party_b):
    today = timezone.now().date()
    return AssetPermitLicense.objects.create(
        tenant=tenant_b,
        permit_name="Air Quality Emission Operating Permit",
        permit_number="EPA-AIR-2002",
        permit_type="environmental_emissions",
        asset=operational_asset_b,
        issuing_authority=vendor_party_b,
        issue_date=today - timezone.timedelta(days=300),
        effective_date=today - timezone.timedelta(days=300),
        expiration_date=today + timezone.timedelta(days=65),
        renewal_lead_days=60,
        renewal_fee=Decimal("2500.00"),
        operating_conditions="NOX capped at 25 PPM.",
        status="active",
    )


@pytest.fixture
def compliance_incident_a(db, tenant_a, operational_asset_a, permit_license_a, compliance_audit_a, vendor_party_a, admin_user):
    today = timezone.now().date()
    return AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        title="Hourly NOX Emission Exceedance Spike",
        incident_date=today - timezone.timedelta(days=10),
        discovery_date=today - timezone.timedelta(days=9),
        incident_type="emissions_exceedance",
        severity="serious",
        asset=operational_asset_a,
        permit=permit_license_a,
        audit=compliance_audit_a,
        enforcement_agency=vendor_party_a,
        citation_reference="EPA-NOV-2026-081",
        fine_assessed=Decimal("5000.00"),
        fine_paid=Decimal("5000.00"),
        fine_payment_date=today - timezone.timedelta(days=2),
        root_cause="mechanical_failure",
        root_cause_analysis="Damper stuck open.",
        corrective_action_plan="Replaced pneumatic damper actuator.",
        assigned_investigator=admin_user,
        target_resolution_date=today + timezone.timedelta(days=15),
        actual_resolution_date=today - timezone.timedelta(days=2),
        status="resolved",
    )


@pytest.fixture
def compliance_incident_b(db, tenant_b, operational_asset_b, vendor_party_b, admin_b):
    today = timezone.now().date()
    return AssetComplianceIncident.objects.create(
        tenant=tenant_b,
        title="Unpermitted Coolant Overflow",
        incident_date=today - timezone.timedelta(days=3),
        discovery_date=today - timezone.timedelta(days=3),
        incident_type="unpermitted_discharge",
        severity="other_than_serious",
        asset=operational_asset_b,
        enforcement_agency=vendor_party_b,
        fine_assessed=Decimal("0.00"),
        fine_paid=Decimal("0.00"),
        root_cause="human_error",
        root_cause_analysis="Valve left open.",
        corrective_action_plan="Installed float cutoff switch.",
        assigned_investigator=admin_b,
        target_resolution_date=today + timezone.timedelta(days=7),
        status="open",
    )






