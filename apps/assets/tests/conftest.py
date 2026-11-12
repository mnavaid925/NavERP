"""Shared test contract fixtures for apps/assets (Module 11)."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.accounting.models import Currency, FiscalPeriod, GLAccount, FixedAsset
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
    AssetLeaseBuyAnalysis,
    AssetLeaseContract,
    AssetLeaseModification,
    AssetLeaseSchedule,
    MobileAssetInspection,
    FieldWorkOrder,
    AssetScanLog,
    AssetGeofenceEvent,
    AssetRiskRegister,
    AssetBusinessContinuityPlan,
    AssetCyberSecurityProfile,
    AssetRiskMitigationAction,
    AssetIntegrationConnector,
    AssetTelemetryStream,
    AssetGlSyncBatch,
    AssetGisMapping,
    AssetDocument,
    AssetOperatingProcedure,
    AssetOperatorCertification,
    AssetKnowledgeArticle,
    AssetLifecycleCostAnalysis,
    AssetReplacementPlan,
    AssetPortfolioScenario,
    AssetExecutiveScorecard,
    ItHardwareAsset,
    SoftwareLicense,
    CloudAssetSubscription,
    CmdbRelationship,
    AssetFacilitySpace,
    AssetBuildingSystem,
    AssetFurnitureFixture,
    AssetSpaceChargeback,
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
        incident_date=timezone.now() - timezone.timedelta(days=10),
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
        incident_date=timezone.now() - timezone.timedelta(days=3),
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


# ---------------------------------------------------------------------------
# Sub-module 11.10: Lease & Rental Management Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def lease_contract_a(db, tenant_a, vendor_party_a, operational_asset_a, category_root_a, fixed_asset_a, admin_user):
    today = timezone.now().date()
    alc = AssetLeaseContract.objects.create(
        tenant=tenant_a,
        title="Finance Lease for 5-Axis CNC Machining Center",
        master_lease_agreement_ref="MLA-2025-IND-A01",
        lessor=vendor_party_a,
        asset=operational_asset_a,
        category=category_root_a,
        fixed_asset=fixed_asset_a,
        inception_date=today - timezone.timedelta(days=180),
        commencement_date=today - timezone.timedelta(days=180),
        expiration_date=today + timezone.timedelta(days=900),
        first_payment_date=today - timezone.timedelta(days=180),
        lease_term_months=36,
        economic_life_months=48,
        payment_amount=Decimal("4500.00"),
        payment_frequency="monthly",
        payment_timing="arrears",
        discount_rate_pct=Decimal("5.5000"),
        fair_market_value=Decimal("160000.00"),
        initial_direct_costs=Decimal("1200.00"),
        lease_incentives=Decimal("500.00"),
        residual_value_guarantee=Decimal("10000.00"),
        purchase_option_price=Decimal("15000.00"),
        has_purchase_option=True,
        transfer_of_ownership=False,
        is_specialized_asset=False,
        classification="finance",
        status="active",
        approved_by=admin_user,
        notes="Primary CNC cell finance lease fixture.",
    )
    alc.calculate_present_value()
    alc.save()
    return alc


@pytest.fixture
def lease_contract_b(db, tenant_b, vendor_party_b, operational_asset_b, category_root_b, admin_b):
    today = timezone.now().date()
    alc = AssetLeaseContract.objects.create(
        tenant=tenant_b,
        title="Operating Lease for Forklift Fleet",
        master_lease_agreement_ref="MLA-2026-FLT-B09",
        lessor=vendor_party_b,
        asset=operational_asset_b,
        category=category_root_b,
        inception_date=today - timezone.timedelta(days=60),
        commencement_date=today - timezone.timedelta(days=60),
        expiration_date=today + timezone.timedelta(days=660),
        first_payment_date=today - timezone.timedelta(days=60),
        lease_term_months=24,
        economic_life_months=84,
        payment_amount=Decimal("2800.00"),
        payment_frequency="monthly",
        payment_timing="advance",
        discount_rate_pct=Decimal("4.7500"),
        fair_market_value=Decimal("110000.00"),
        classification="operating",
        status="active",
        approved_by=admin_b,
        notes="Tenant B operating lease fixture.",
    )
    alc.calculate_present_value()
    alc.save()
    return alc


@pytest.fixture
def lease_schedule_a(db, tenant_a, lease_contract_a):
    today = timezone.now().date()
    return AssetLeaseSchedule.objects.create(
        tenant=tenant_a,
        lease_contract=lease_contract_a,
        period_number=1,
        due_date=today - timezone.timedelta(days=150),
        payment_amount=Decimal("4500.00"),
        beginning_liability=Decimal("130000.00"),
        interest_expense=Decimal("595.83"),
        principal_reduction=Decimal("3904.17"),
        ending_liability=Decimal("126095.83"),
        rou_depreciation=Decimal("3625.00"),
        ending_rou_asset_value=Decimal("126875.00"),
        status="paid",
        paid_date=today - timezone.timedelta(days=150),
        payment_reference="ACH-2026-001",
    )


@pytest.fixture
def lease_schedule_b(db, tenant_b, lease_contract_b):
    today = timezone.now().date()
    return AssetLeaseSchedule.objects.create(
        tenant=tenant_b,
        lease_contract=lease_contract_b,
        period_number=1,
        due_date=today - timezone.timedelta(days=30),
        payment_amount=Decimal("2800.00"),
        beginning_liability=Decimal("63000.00"),
        interest_expense=Decimal("249.38"),
        principal_reduction=Decimal("2550.62"),
        ending_liability=Decimal("60449.38"),
        rou_depreciation=Decimal("2625.00"),
        ending_rou_asset_value=Decimal("60375.00"),
        status="scheduled",
    )


@pytest.fixture
def lease_modification_a(db, tenant_a, lease_contract_a, admin_user):
    today = timezone.now().date()
    return AssetLeaseModification.objects.create(
        tenant=tenant_a,
        lease_contract=lease_contract_a,
        modification_type="term_extension",
        request_date=today - timezone.timedelta(days=30),
        effective_date=today - timezone.timedelta(days=15),
        prior_lease_liability=Decimal("125000.00"),
        revised_lease_liability=Decimal("142000.00"),
        liability_adjustment=Decimal("17000.00"),
        prior_rou_asset_value=Decimal("120000.00"),
        revised_rou_asset_value=Decimal("137000.00"),
        rou_asset_adjustment=Decimal("17000.00"),
        revised_term_months=48,
        requested_by=admin_user,
        approved_by=admin_user,
        status="executed",
        justification="Production volume increases necessitate term extension.",
        notes="Controller approved modification fixture.",
    )


@pytest.fixture
def lease_modification_b(db, tenant_b, lease_contract_b, admin_b):
    today = timezone.now().date()
    return AssetLeaseModification.objects.create(
        tenant=tenant_b,
        lease_contract=lease_contract_b,
        modification_type="payment_adjustment",
        request_date=today - timezone.timedelta(days=10),
        effective_date=today - timezone.timedelta(days=5),
        prior_lease_liability=Decimal("60000.00"),
        revised_lease_liability=Decimal("55000.00"),
        liability_adjustment=Decimal("-5000.00"),
        prior_rou_asset_value=Decimal("60000.00"),
        revised_rou_asset_value=Decimal("55000.00"),
        rou_asset_adjustment=Decimal("-5000.00"),
        revised_payment_amount=Decimal("2500.00"),
        requested_by=admin_b,
        status="submitted",
        justification="Vendor concession rate reduction.",
        notes="Pending tenant B approval.",
    )


@pytest.fixture
def lease_buy_analysis_a(db, tenant_a, category_root_a, admin_user):
    alba = AssetLeaseBuyAnalysis.objects.create(
        tenant=tenant_a,
        title="CapEx Decision: High-Capacity 50-Ton Overhead Gantry Crane",
        description="Outright debt purchase vs 5-year operating lease evaluation.",
        target_asset_name="Konecranes 50T Industrial Gantry Crane",
        category=category_root_a,
        expected_useful_life_years=Decimal("10.0"),
        purchase_price=Decimal("240000.00"),
        down_payment_pct=Decimal("15.00"),
        loan_interest_rate_pct=Decimal("5.75"),
        loan_term_years=Decimal("5.0"),
        estimated_salvage_value=Decimal("35000.00"),
        annual_maintenance_cost_buy=Decimal("6500.00"),
        annual_insurance_tax_buy=Decimal("3200.00"),
        lease_term_months=60,
        monthly_lease_payment=Decimal("4200.00"),
        upfront_lease_fees=Decimal("5000.00"),
        end_of_lease_purchase_option=Decimal("25000.00"),
        lessor_covers_maintenance=True,
        annual_maintenance_cost_lease=Decimal("0.00"),
        discount_rate_wacc_pct=Decimal("8.00"),
        corporate_tax_rate_pct=Decimal("21.00"),
        evaluated_by=admin_user,
        status="evaluated",
        evaluation_notes="Long life favors buy scenario.",
    )
    alba.evaluate_financial_models()
    alba.save()
    return alba


@pytest.fixture
def lease_buy_analysis_b(db, tenant_b, category_root_b, admin_b):
    alba = AssetLeaseBuyAnalysis.objects.create(
        tenant=tenant_b,
        title="CapEx Decision: Automated Packaging Palletizer System",
        description="Rapid tech turnover favors 3-year operating lease.",
        target_asset_name="Fanuc M-410iC Robotic Palletizing Cell",
        category=category_root_b,
        expected_useful_life_years=Decimal("4.0"),
        purchase_price=Decimal("185000.00"),
        down_payment_pct=Decimal("20.00"),
        loan_interest_rate_pct=Decimal("6.50"),
        loan_term_years=Decimal("4.0"),
        estimated_salvage_value=Decimal("15000.00"),
        annual_maintenance_cost_buy=Decimal("8500.00"),
        annual_insurance_tax_buy=Decimal("2400.00"),
        lease_term_months=36,
        monthly_lease_payment=Decimal("2900.00"),
        upfront_lease_fees=Decimal("2500.00"),
        end_of_lease_purchase_option=Decimal("10000.00"),
        lessor_covers_maintenance=True,
        annual_maintenance_cost_lease=Decimal("0.00"),
        discount_rate_wacc_pct=Decimal("8.50"),
        corporate_tax_rate_pct=Decimal("21.00"),
        evaluated_by=admin_b,
        approved_by=admin_b,
        status="approved",
        evaluation_notes="Leasing recommended.",
    )
    alba.evaluate_financial_models()
    alba.save()
    return alba


# ============================================================================
# Sub-module 11.13: Mobile Asset Management Fixtures
# ============================================================================

@pytest.fixture
def mobile_inspection_a(db, tenant_a, operational_asset_a, fixed_asset_a, admin_user):
    return MobileAssetInspection.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        fixed_asset=fixed_asset_a,
        inspector=admin_user,
        title="Pre-Trip Walkaround Inspection",
        inspection_type="pre_trip",
        inspection_date=timezone.now(),
        status="submitted",
        overall_result="pass",
        condition_rating=4,
        checklist_summary="Completed all check items successfully.",
        findings_summary="Yard Bay 14",
    )


@pytest.fixture
def mobile_inspection_b(db, tenant_b, operational_asset_b, fixed_asset_b, admin_b):
    return MobileAssetInspection.objects.create(
        tenant=tenant_b,
        asset=operational_asset_b,
        fixed_asset=fixed_asset_b,
        inspector=admin_b,
        title="Routine PM Walkaround Inspection",
        inspection_type="routine_pm",
        inspection_date=timezone.now(),
        status="draft",
        overall_result="conditional_pass",
        condition_rating=3,
        checklist_summary="Pending secondary hydraulic fluid test.",
        findings_summary="Globex Depot B",
    )


@pytest.fixture
def field_work_order_a(db, tenant_a, operational_asset_a, fixed_asset_a, admin_user):
    now = timezone.now()
    return FieldWorkOrder.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        fixed_asset=fixed_asset_a,
        assigned_technician=admin_user,
        title="Field Inspection & Sensor Calibration",
        work_order_type="scheduled_pm",
        priority="high",
        status="in_progress",
        scheduled_start=now,
        scheduled_end=now + timezone.timedelta(hours=4),
        work_performed_notes="Field diagnosis verified proper sensor output.",
    )


@pytest.fixture
def field_work_order_b(db, tenant_b, operational_asset_b, fixed_asset_b, admin_b):
    now = timezone.now()
    return FieldWorkOrder.objects.create(
        tenant=tenant_b,
        asset=operational_asset_b,
        fixed_asset=fixed_asset_b,
        assigned_technician=admin_b,
        title="Globex Generator Valve Replacement",
        work_order_type="emergency_repair",
        priority="urgent",
        status="dispatched",
        scheduled_start=now,
        scheduled_end=now + timezone.timedelta(hours=8),
        work_performed_notes="Emergency replacement of high-pressure relief valve.",
    )


@pytest.fixture
def asset_scan_log_a(db, tenant_a, operational_asset_a, admin_user):
    return AssetScanLog.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        scanned_by=admin_user,
        raw_payload="ACME-BARCODE-998811",
        scan_method="camera_qr",
        scan_context="field_audit",
        match_status="matched",
        gps_latitude=Decimal("37.774900"),
        gps_longitude=Decimal("-122.419400"),
        device_info="ZEBRA-TC57-FIELD-01",
    )


@pytest.fixture
def asset_scan_log_b(db, tenant_b, operational_asset_b, admin_b):
    return AssetScanLog.objects.create(
        tenant=tenant_b,
        asset=operational_asset_b,
        scanned_by=admin_b,
        raw_payload="GLOBEX-RFID-554433",
        scan_method="bluetooth_rfid",
        scan_context="location_reconciliation",
        match_status="matched",
        gps_latitude=Decimal("40.712800"),
        gps_longitude=Decimal("-74.006000"),
        device_info="HONEYWELL-EDA52-02",
    )


@pytest.fixture
def asset_geofence_event_a(db, tenant_a, operational_asset_a):
    return AssetGeofenceEvent.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        fence_name="Acme Northern Storage Yard",
        center_latitude=Decimal("37.774000"),
        center_longitude=Decimal("-122.419000"),
        radius_meters=150,
        recorded_latitude=Decimal("37.774900"),
        recorded_longitude=Decimal("-122.419400"),
        distance_from_center_m=120.0,
        event_type="perimeter_exit",
        severity="high",
        status="open_alert",
        resolution_notes="Asset telemetry triggered unexpected departure event.",
    )


@pytest.fixture
def asset_geofence_event_b(db, tenant_b, operational_asset_b):
    return AssetGeofenceEvent.objects.create(
        tenant=tenant_b,
        asset=operational_asset_b,
        fence_name="Globex Secure Hangar B",
        center_latitude=Decimal("40.712000"),
        center_longitude=Decimal("-74.005000"),
        radius_meters=100,
        recorded_latitude=Decimal("40.712800"),
        recorded_longitude=Decimal("-74.006000"),
        distance_from_center_m=110.0,
        event_type="unauthorized_movement",
        severity="critical",
        status="open_alert",
        resolution_notes="Movement detected outside authorized operational hours.",
    )


# =====================================================================
# Sub-module 11.12: Asset Risk Management Fixtures
# =====================================================================

@pytest.fixture
def asset_risk_register_a(db, tenant_a, operational_asset_a, category_a, admin_user):
    return AssetRiskRegister.objects.create(
        tenant=tenant_a,
        title="CNC Spindle Bearing Seizure Risk",
        asset=operational_asset_a,
        category=category_a,
        risk_category="operational",
        threat_source="equipment_wear",
        failure_mode="Fatigue failure of ceramic ball bearing",
        description="High spindle speeds causing overheating.",
        inherent_likelihood=4,
        inherent_impact=4,
        residual_likelihood=2,
        residual_impact=2,
        risk_owner=admin_user,
        treatment_strategy="mitigate",
        financial_exposure_amount=Decimal("50000.00"),
        status="identified",
        review_frequency="quarterly",
    )


@pytest.fixture
def asset_risk_register_b(db, tenant_b, operational_asset_b, category_b, admin_b):
    return AssetRiskRegister.objects.create(
        tenant=tenant_b,
        title="Compressor Motor Insulation Breakdown Risk",
        asset=operational_asset_b,
        category=category_b,
        risk_category="operational",
        threat_source="equipment_wear",
        failure_mode="Stator winding thermal breakdown",
        description="Voltage surges causing insulation degrade.",
        inherent_likelihood=3,
        inherent_impact=3,
        residual_likelihood=1,
        residual_impact=2,
        risk_owner=admin_b,
        treatment_strategy="transfer",
        financial_exposure_amount=Decimal("30000.00"),
        status="identified",
        review_frequency="semi_annually",
    )


@pytest.fixture
def asset_continuity_plan_a(db, tenant_a, operational_asset_a, admin_user):
    return AssetBusinessContinuityPlan.objects.create(
        tenant=tenant_a,
        title="Primary CNC Cell Disaster Recovery Plan",
        primary_asset=operational_asset_a,
        redundancy_type="warm_standby",
        recovery_time_objective_hours=Decimal("4.00"),
        recovery_point_objective_hours=Decimal("1.00"),
        maximum_tolerable_downtime_hours=Decimal("12.00"),
        disaster_scenario="critical_hardware_loss",
        failover_procedure="Reroute production batches to secondary machine.",
        failback_procedure="Recalibrate axes and verify first-article cut.",
        alternate_facility_site="Bay 3 South",
        critical_spares_required="Spare spindle cartridge P/N 884-A",
        emergency_lead=admin_user,
        drill_frequency="semi_annually",
        drill_result="not_tested",
        status="draft",
    )


@pytest.fixture
def asset_continuity_plan_b(db, tenant_b, operational_asset_b, admin_b):
    return AssetBusinessContinuityPlan.objects.create(
        tenant=tenant_b,
        title="Globex Power Generator Continuity Plan",
        primary_asset=operational_asset_b,
        redundancy_type="hot_standby",
        recovery_time_objective_hours=Decimal("0.50"),
        recovery_point_objective_hours=Decimal("0.10"),
        maximum_tolerable_downtime_hours=Decimal("2.00"),
        disaster_scenario="power_grid_outage",
        failover_procedure="ATS automatically starts auxiliary diesel generator.",
        failback_procedure="Switch back to utility grid after 30 min stable voltage.",
        alternate_facility_site="Power Yard 2",
        critical_spares_required="Diesel fuel filter, 24V starter battery",
        emergency_lead=admin_b,
        drill_frequency="quarterly",
        drill_result="passed",
        status="active",
    )


@pytest.fixture
def asset_cyber_profile_a(db, tenant_a, operational_asset_a):
    return AssetCyberSecurityProfile.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        device_type="plc_controller",
        ip_address="192.168.1.10",
        mac_address="00:1A:2B:3C:4D:5E",
        network_zone="control_plc",
        firmware_version="2.1.0",
        latest_available_firmware="2.2.0",
        firmware_update_status="update_available",
        protocol_used="modbus_tcp",
        exposure_level="isolated_vlan",
        known_vulnerabilities_cve="CVE-2024-0001",
        cve_risk_score=Decimal("4.5"),
        compensating_controls="Firewall port restriction",
        security_posture_status="secure",
    )


@pytest.fixture
def asset_cyber_profile_b(db, tenant_b, operational_asset_b):
    return AssetCyberSecurityProfile.objects.create(
        tenant=tenant_b,
        asset=operational_asset_b,
        device_type="scada_server",
        ip_address="10.0.0.50",
        mac_address="00:11:22:33:44:55",
        network_zone="supervisory_scada",
        firmware_version="1.0.0",
        latest_available_firmware="1.0.0",
        firmware_update_status="up_to_date",
        protocol_used="opc_ua",
        exposure_level="monitored_dmz",
        known_vulnerabilities_cve="None",
        cve_risk_score=Decimal("0.0"),
        compensating_controls="MFA enabled",
        security_posture_status="secure",
    )


@pytest.fixture
def asset_mitigation_action_a(db, tenant_a, asset_risk_register_a, admin_user):
    return AssetRiskMitigationAction.objects.create(
        tenant=tenant_a,
        title="Install Spindle Vibration Sensor",
        risk=asset_risk_register_a,
        action_type="preventive_inspection",
        description="Install high-frequency vibration sensor to monitor early bearing wear.",
        assigned_to=admin_user,
        target_completion_date=timezone.now().date() + timezone.timedelta(days=14),
        estimated_cost=Decimal("2500.00"),
        priority="high",
        status="planned",
        effectiveness_rating="pending_evaluation",
    )


@pytest.fixture
def asset_mitigation_action_b(db, tenant_b, asset_risk_register_b, admin_b):
    return AssetRiskMitigationAction.objects.create(
        tenant=tenant_b,
        title="Install Motor Surge Protector",
        risk=asset_risk_register_b,
        action_type="engineering_control",
        description="Install industrial grade transient voltage surge suppressor.",
        assigned_to=admin_b,
        target_completion_date=timezone.now().date() + timezone.timedelta(days=30),
        estimated_cost=Decimal("1500.00"),
        priority="medium",
        status="planned",
        effectiveness_rating="pending_evaluation",
    )


# ===== 11.15 Integration & API Hub =====


@pytest.fixture
def integration_open_fiscal_period_a(db, tenant_a):
    today = timezone.localdate()
    start_date = today.replace(day=1)
    end_date = (today.replace(day=28) + timezone.timedelta(days=4)).replace(
        day=1
    ) - timezone.timedelta(days=1)
    period = FiscalPeriod(
        tenant=tenant_a,
        name=f"{start_date:%b %Y} (Open)",
        period_type="month",
        start_date=start_date,
        end_date=end_date,
        status="open",
    )
    period.full_clean()
    period.save()
    return period


@pytest.fixture
def integration_closed_fiscal_period_a(db, tenant_a):
    today = timezone.localdate()
    prev_end = today.replace(day=1) - timezone.timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    period = FiscalPeriod(
        tenant=tenant_a,
        name=f"{prev_start:%b %Y} (Closed)",
        period_type="month",
        start_date=prev_start,
        end_date=prev_end,
        status="closed",
    )
    period.full_clean()
    period.save()
    return period


@pytest.fixture
def integration_open_fiscal_period_b(db, tenant_b):
    today = timezone.localdate()
    start_date = today.replace(day=1)
    end_date = (today.replace(day=28) + timezone.timedelta(days=4)).replace(
        day=1
    ) - timezone.timedelta(days=1)
    period = FiscalPeriod(
        tenant=tenant_b,
        name=f"{start_date:%b %Y} Globex (Open)",
        period_type="month",
        start_date=start_date,
        end_date=end_date,
        status="open",
    )
    period.full_clean()
    period.save()
    return period


@pytest.fixture
def integration_connector_a(
    db, tenant_a, vendor_party_a, org_unit_a, currency_usd, admin_user
):
    connector = AssetIntegrationConnector(
        tenant=tenant_a,
        name="Acme SAP S/4HANA Integration Hub",
        connector_category="erp_procurement",
        provider="sap_s4hana",
        protocol="odata_v4",
        sync_direction="bidirectional",
        environment="production",
        endpoint_url="https://api-acme.example.com/sap/opu/odata4/assets",
        auth_method="api_key",
        rate_limit_rpm=240,
        timeout_seconds=30,
        retry_policy_max=3,
        polling_interval_minutes=15,
        status="active",
        vendor_partner=vendor_party_a,
        default_org_unit=org_unit_a,
        default_currency=currency_usd,
        owner=admin_user,
        webhook_verify_tls=True,
        notes="Primary Acme ERP asset integration connector.",
    )
    connector.issue_new_secret()
    connector.full_clean()
    connector.save()
    return connector


@pytest.fixture
def integration_connector_b(
    db, tenant_b, vendor_party_b, org_unit_b, currency_usd, admin_b
):
    connector = AssetIntegrationConnector(
        tenant=tenant_b,
        name="Globex Oracle Fusion GL Bridge",
        connector_category="financial_gl",
        provider="oracle_fusion",
        protocol="rest_json",
        sync_direction="outbound",
        environment="staging",
        endpoint_url="https://api-globex.example.com/fscmRestApi/assets",
        auth_method="oauth2_client",
        rate_limit_rpm=120,
        timeout_seconds=30,
        retry_policy_max=3,
        polling_interval_minutes=15,
        status="active",
        vendor_partner=vendor_party_b,
        default_org_unit=org_unit_b,
        default_currency=currency_usd,
        owner=admin_b,
        webhook_verify_tls=True,
        notes="Primary Globex GL integration connector.",
    )
    connector.issue_new_secret()
    connector.full_clean()
    connector.save()
    return connector


@pytest.fixture
def integration_stream_a(
    db,
    tenant_a,
    integration_connector_a,
    operational_asset_a,
    fixed_asset_a,
    admin_user,
):
    stream = AssetTelemetryStream(
        tenant=tenant_a,
        connector=integration_connector_a,
        operational_asset=operational_asset_a,
        fixed_asset=fixed_asset_a,
        tag_address="ns=2;s=Line1.CNC01.BearingTempC",
        stream_name="CNC Mill Spindle Bearing Temperature",
        stream_protocol="opc_ua_node",
        metric_type="bearing_temperature",
        metric_unit="celsius",
        ingestion_mode="polling",
        polling_interval_seconds=60,
        deadband_delta=Decimal("0.5000"),
        scale_factor=Decimal("1.000000"),
        offset_value=Decimal("0.0000"),
        baseline_value=Decimal("50.0000"),
        warning_threshold=Decimal("75.0000"),
        critical_threshold=Decimal("90.0000"),
        auto_trigger_maintenance=True,
        stream_status="active",
        steward=admin_user,
        notes="Acme CNC spindle bearing telemetry feed.",
    )
    stream.full_clean()
    stream.save()
    return stream


@pytest.fixture
def integration_stream_b(
    db,
    tenant_b,
    integration_connector_b,
    operational_asset_b,
    fixed_asset_b,
    admin_b,
):
    stream = AssetTelemetryStream(
        tenant=tenant_b,
        connector=integration_connector_b,
        operational_asset=operational_asset_b,
        fixed_asset=fixed_asset_b,
        tag_address="globex/yard1/forklift01/vibration_rms",
        stream_name="Globex Forklift Vibration RMS",
        stream_protocol="mqtt_topic",
        metric_type="vibration_velocity_rms",
        metric_unit="mm_per_s",
        ingestion_mode="streaming_pubsub",
        polling_interval_seconds=30,
        deadband_delta=Decimal("0.1000"),
        scale_factor=Decimal("1.000000"),
        offset_value=Decimal("0.0000"),
        baseline_value=Decimal("2.0000"),
        warning_threshold=Decimal("5.0000"),
        critical_threshold=Decimal("8.0000"),
        auto_trigger_maintenance=True,
        stream_status="active",
        steward=admin_b,
        notes="Globex yard fleet vibration telemetry feed.",
    )
    stream.full_clean()
    stream.save()
    return stream


@pytest.fixture
def integration_gl_batch_a(
    db,
    tenant_a,
    integration_connector_a,
    integration_open_fiscal_period_a,
    asset_account_a,
    expense_account_a,
    fixed_asset_a,
    org_unit_a,
    currency_usd,
):
    batch = AssetGlSyncBatch(
        tenant=tenant_a,
        connector=integration_connector_a,
        sync_domain="depreciation_posting",
        sync_direction="outbound",
        external_batch_ref="SAP-BELNR-2026-A01",
        fiscal_period=integration_open_fiscal_period_a,
        gl_account=expense_account_a,
        offset_gl_account=asset_account_a,
        fixed_asset=fixed_asset_a,
        cost_center=org_unit_a,
        currency=currency_usd,
        batch_date=timezone.localdate(),
        source_amount=Decimal("1800.00"),
        target_gl_amount=Decimal("1800.00"),
        reconciliation_status="pending",
        status="ready",
        field_mapping_json='{"asset_book": "CORP_US", "depreciation_acct": "6100-A"}',
        payload_summary="Acme monthly depreciation batch ready for GL posting.",
    )
    batch.full_clean()
    batch.save()
    return batch


@pytest.fixture
def integration_gl_batch_b(
    db,
    tenant_b,
    integration_connector_b,
    integration_open_fiscal_period_b,
    expense_account_b,
    accum_account_b,
    fixed_asset_b,
    org_unit_b,
    currency_usd,
):
    batch = AssetGlSyncBatch(
        tenant=tenant_b,
        connector=integration_connector_b,
        sync_domain="depreciation_posting",
        sync_direction="outbound",
        external_batch_ref="ORCL-DEP-2026-B01",
        fiscal_period=integration_open_fiscal_period_b,
        gl_account=expense_account_b,
        offset_gl_account=accum_account_b,
        fixed_asset=fixed_asset_b,
        cost_center=org_unit_b,
        currency=currency_usd,
        batch_date=timezone.localdate(),
        source_amount=Decimal("833.33"),
        target_gl_amount=Decimal("833.33"),
        reconciliation_status="pending",
        status="ready",
        field_mapping_json='{"asset_book": "GLOBEX_US", "depreciation_acct": "6100-B"}',
        payload_summary="Globex monthly depreciation batch ready for GL posting.",
    )
    batch.full_clean()
    batch.save()
    return batch


@pytest.fixture
def integration_gis_mapping_a(
    db,
    tenant_a,
    integration_connector_a,
    operational_asset_a,
    location_a,
    org_unit_a,
    admin_user,
):
    mapping = AssetGisMapping(
        tenant=tenant_a,
        connector=integration_connector_a,
        operational_asset=operational_asset_a,
        location=location_a,
        org_unit=org_unit_a,
        external_feature_id="ARCGIS-CNC-001",
        layer_name="plant_machinery_pt",
        geometry_type="point",
        coordinate_system_srid=4326,
        latitude=Decimal("40.748400"),
        longitude=Decimal("-73.985700"),
        elevation_meters=Decimal("12.50"),
        is_linear_asset=False,
        geojson_payload='{"type": "Point", "coordinates": [-73.9857, 40.7484]}',
        system_of_record="erp_authoritative",
        sync_direction="bidirectional",
        drift_status="unverified",
        status="active",
        gis_custodian=admin_user,
        notes="Acme CNC machine shop GIS point mapping.",
    )
    mapping.full_clean()
    mapping.save()
    return mapping


@pytest.fixture
def integration_gis_mapping_b(
    db,
    tenant_b,
    integration_connector_b,
    operational_asset_b,
    location_b,
    org_unit_b,
    admin_b,
):
    mapping = AssetGisMapping(
        tenant=tenant_b,
        connector=integration_connector_b,
        operational_asset=operational_asset_b,
        location=location_b,
        org_unit=org_unit_b,
        external_feature_id="QGIS-FORKLIFT-002",
        layer_name="yard_fleet_corridor",
        geometry_type="linestring",
        coordinate_system_srid=4326,
        latitude=Decimal("34.052235"),
        longitude=Decimal("-118.243683"),
        is_linear_asset=True,
        lrs_route_id="YARD-ROUTE-01",
        lrs_from_measure=Decimal("0.000"),
        lrs_to_measure=Decimal("1.250"),
        lrs_measure_unit="km",
        geojson_payload='{"type": "LineString", "coordinates": [[-118.243683, 34.052235], [-118.240000, 34.055000]]}',
        system_of_record="gis_authoritative",
        sync_direction="inbound",
        drift_status="unverified",
        status="active",
        gis_custodian=admin_b,
        notes="Globex yard LRS corridor mapping.",
    )
    mapping.full_clean()
    mapping.save()
    return mapping



# ===== 11.16 Document & Knowledge Management =====


@pytest.fixture
def adk_document_a(
    db,
    tenant_a,
    operational_asset_a,
    category_root_a,
    org_unit_a,
    admin_user,
):
    doc = AssetDocument(
        tenant=tenant_a,
        title="CNC Lathe OEM Service Manual",
        document_class="manual",
        access_classification="public_floor",
        revision_label="Rev A",
        revision_sequence=1,
        is_current_revision=True,
        change_type="new_issue",
        status="approved",
        owner=admin_user,
        approved_by=admin_user,
        approved_at=timezone.now(),
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        org_unit=org_unit_a,
        effective_date=timezone.localdate(),
    )
    doc.full_clean()
    doc.save()
    return doc


@pytest.fixture
def adk_document_draft_a(db, tenant_a, operational_asset_a, admin_user):
    doc = AssetDocument(
        tenant=tenant_a,
        title="CNC Hydraulic Schematic Draft",
        document_class="schematic_pid",
        access_classification="internal_tech",
        revision_label="Rev A",
        revision_sequence=1,
        is_current_revision=True,
        change_type="drawing_redline",
        status="draft",
        owner=admin_user,
        operational_asset=operational_asset_a,
    )
    doc.full_clean()
    doc.save()
    return doc


@pytest.fixture
def adk_document_restricted_a(db, tenant_a, operational_asset_a, admin_user):
    doc = AssetDocument(
        tenant=tenant_a,
        title="Restricted Firmware & Calibration Dossier",
        document_class="inspection_dossier",
        access_classification="restricted_eng",
        revision_label="Rev A",
        revision_sequence=1,
        is_current_revision=True,
        change_type="spec_update",
        status="approved",
        owner=admin_user,
        approved_by=admin_user,
        approved_at=timezone.now(),
        operational_asset=operational_asset_a,
    )
    doc.full_clean()
    doc.save()
    return doc


@pytest.fixture
def adk_document_b(
    db,
    tenant_b,
    operational_asset_b,
    category_root_b,
    org_unit_b,
    admin_b,
):
    doc = AssetDocument(
        tenant=tenant_b,
        title="Globex Forklift Manual",
        document_class="manual",
        access_classification="public_floor",
        revision_label="Rev A",
        revision_sequence=1,
        is_current_revision=True,
        change_type="new_issue",
        status="approved",
        owner=admin_b,
        approved_by=admin_b,
        approved_at=timezone.now(),
        operational_asset=operational_asset_b,
        asset_category=category_root_b,
        org_unit=org_unit_b,
        effective_date=timezone.localdate(),
    )
    doc.full_clean()
    doc.save()
    return doc


@pytest.fixture
def adk_procedure_a(
    db,
    tenant_a,
    operational_asset_a,
    category_root_a,
    maintenance_schedule_a,
    adk_document_a,
    admin_user,
):
    proc = AssetOperatingProcedure(
        tenant=tenant_a,
        title="CNC Main Breaker LOTO Procedure",
        procedure_type="loto_isolation",
        safety_level="high_hazard_loto",
        revision_label="Rev 1.0",
        loto_required=True,
        required_qualification_code="LOTO-01",
        estimated_duration_minutes=45,
        review_cycle_months=12,
        effective_date=timezone.localdate(),
        next_review_date=timezone.localdate() + timedelta(days=180),
        status="active",
        author=admin_user,
        approved_by=admin_user,
        approved_at=timezone.now(),
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        maintenance_schedule=maintenance_schedule_a,
        primary_document=adk_document_a,
    )
    proc.full_clean()
    proc.save()
    return proc


@pytest.fixture
def adk_procedure_draft_a(db, tenant_a, operational_asset_a, admin_user):
    proc = AssetOperatingProcedure(
        tenant=tenant_a,
        title="Spindle Alignment PM SOP Draft",
        procedure_type="pm_protocol",
        safety_level="standard",
        revision_label="Rev 1.0",
        loto_required=False,
        status="draft",
        author=admin_user,
        operational_asset=operational_asset_a,
    )
    proc.full_clean()
    proc.save()
    return proc


@pytest.fixture
def adk_procedure_b(
    db,
    tenant_b,
    operational_asset_b,
    category_root_b,
    maintenance_schedule_b,
    adk_document_b,
    admin_b,
):
    proc = AssetOperatingProcedure(
        tenant=tenant_b,
        title="Globex Yard LOTO Protocol",
        procedure_type="loto_isolation",
        safety_level="high_hazard_loto",
        revision_label="Rev 1.0",
        loto_required=True,
        status="active",
        author=admin_b,
        approved_by=admin_b,
        approved_at=timezone.now(),
        operational_asset=operational_asset_b,
        asset_category=category_root_b,
        maintenance_schedule=maintenance_schedule_b,
        primary_document=adk_document_b,
    )
    proc.full_clean()
    proc.save()
    return proc


@pytest.fixture
def adk_certification_a(
    db,
    tenant_a,
    vendor_party_a,
    admin_user,
    operational_asset_a,
    adk_procedure_a,
):
    cert = AssetOperatorCertification(
        tenant=tenant_a,
        title="LOTO Authorized CNC Technician",
        qualification_code="LOTO-01",
        qualification_type="loto_authorized",
        proficiency_level="qualified_operator",
        issued_date=timezone.localdate() - timedelta(days=30),
        expires_on=timezone.localdate() + timedelta(days=180),
        renewal_lead_days=30,
        status="active",
        operator_party=vendor_party_a,
        operator_user=admin_user,
        operational_asset=operational_asset_a,
        operating_procedure=adk_procedure_a,
    )
    cert.full_clean()
    cert.save()
    return cert


@pytest.fixture
def adk_certification_pending_a(
    db,
    tenant_a,
    vendor_party_a,
    member_user,
    operational_asset_a,
):
    cert = AssetOperatorCertification(
        tenant=tenant_a,
        title="CNC Trainee Qualification Pending",
        qualification_code="OP-TRAINEE",
        qualification_type="equipment_operator",
        proficiency_level="trainee_supervised",
        issued_date=timezone.localdate(),
        expires_on=timezone.localdate() + timedelta(days=365),
        renewal_lead_days=30,
        status="pending",
        operator_party=vendor_party_a,
        operator_user=member_user,
        operational_asset=operational_asset_a,
    )
    cert.full_clean()
    cert.save()
    return cert


@pytest.fixture
def adk_certification_b(
    db,
    tenant_b,
    vendor_party_b,
    admin_b,
    operational_asset_b,
    adk_procedure_b,
):
    cert = AssetOperatorCertification(
        tenant=tenant_b,
        title="Globex LOTO Authorization",
        qualification_code="LOTO-B1",
        qualification_type="loto_authorized",
        proficiency_level="qualified_operator",
        issued_date=timezone.localdate() - timedelta(days=15),
        expires_on=timezone.localdate() + timedelta(days=180),
        renewal_lead_days=30,
        status="active",
        operator_party=vendor_party_b,
        operator_user=admin_b,
        operational_asset=operational_asset_b,
        operating_procedure=adk_procedure_b,
    )
    cert.full_clean()
    cert.save()
    return cert


@pytest.fixture
def adk_article_a(
    db,
    tenant_a,
    operational_asset_a,
    failure_mode_a,
    incident_a,
    adk_document_a,
    adk_procedure_a,
    admin_user,
):
    article = AssetKnowledgeArticle(
        tenant=tenant_a,
        title="Spindle Bearing Overheating RCA",
        article_type="rca_post_incident",
        rca_methodology="five_whys",
        severity="high",
        symptom_problem="Spindle temperature exceeded 85C under sustained load.",
        root_cause_summary="Clogged coolant return strainer starved bearing cooling.",
        remedy_corrective_action="Flush coolant circuit and install 100-mesh strainer.",
        preventive_lessons="Add weekly differential-pressure inspection to PM checklist.",
        downtime_hours_impacted=Decimal("4.50"),
        recurrence_count=1,
        tags="spindle,coolant,bearing",
        status="published",
        author=admin_user,
        reviewed_by=admin_user,
        published_at=timezone.now(),
        operational_asset=operational_asset_a,
        failure_mode=failure_mode_a,
        incident_report=incident_a,
        related_document=adk_document_a,
        recommended_procedure=adk_procedure_a,
    )
    article.full_clean()
    article.save()
    return article


@pytest.fixture
def adk_article_draft_a(db, tenant_a, operational_asset_a, admin_user):
    article = AssetKnowledgeArticle(
        tenant=tenant_a,
        title="Coolant Pump Cavitation Note Draft",
        article_type="lessons_learned",
        rca_methodology="problem_cause_remedy",
        severity="medium",
        symptom_problem="Intermittent pump pressure ripple during shift startup.",
        status="draft",
        author=admin_user,
        operational_asset=operational_asset_a,
    )
    article.full_clean()
    article.save()
    return article


@pytest.fixture
def adk_article_b(
    db,
    tenant_b,
    operational_asset_b,
    failure_mode_b,
    incident_b,
    adk_document_b,
    adk_procedure_b,
    admin_b,
):
    article = AssetKnowledgeArticle(
        tenant=tenant_b,
        title="Globex Forklift Mast Seal RCA",
        article_type="rca_post_incident",
        rca_methodology="five_whys",
        severity="medium",
        symptom_problem="Hydraulic mast weep observed after heavy lift cycle.",
        status="published",
        author=admin_b,
        reviewed_by=admin_b,
        published_at=timezone.now(),
        operational_asset=operational_asset_b,
        failure_mode=failure_mode_b,
        incident_report=incident_b,
        related_document=adk_document_b,
        recommended_procedure=adk_procedure_b,
    )
    article.full_clean()
    article.save()
    return article


# ── Sub-module 11.14: Asset Analytics & Business Intelligence ───────────────


@pytest.fixture
def analytics_lcc_a(
    db,
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    asset_model_a,
    org_unit_a,
    currency_usd,
    admin_user,
):
    lcc = AssetLifecycleCostAnalysis(
        tenant=tenant_a,
        title="CNC Lathe 5-Year Lifecycle Cost Study",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        asset_model=asset_model_a,
        org_unit=org_unit_a,
        currency=currency_usd,
        analyzed_by=admin_user,
        analysis_date=timezone.localdate(),
        analysis_horizon_years=5,
        discount_rate_pct=Decimal("8.00"),
        lifecycle_stage="in_service",
        status="draft",
        acquisition_capital_cost=Decimal("120000.00"),
        installation_commissioning_cost=Decimal("10000.00"),
        preventive_maintenance_cost=Decimal("12000.00"),
        corrective_maintenance_cost=Decimal("8000.00"),
        service_contract_cost=Decimal("6000.00"),
        energy_utility_cost=Decimal("9000.00"),
        downtime_opportunity_cost=Decimal("4000.00"),
        insurance_compliance_cost=Decimal("3000.00"),
        accumulated_depreciation_cost=Decimal("25000.00"),
        expected_salvage_value=Decimal("15000.00"),
        warranty_insurance_recoveries=Decimal("2000.00"),
        current_replacement_value=Decimal("140000.00"),
        notes="Baseline lifecycle cost study for CNC lathe.",
    )
    lcc.full_clean()
    lcc.save()
    return lcc


@pytest.fixture
def analytics_lcc_locked_a(
    db,
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    org_unit_a,
    currency_usd,
    admin_user,
):
    lcc = AssetLifecycleCostAnalysis(
        tenant=tenant_a,
        title="Approved Chiller Lifecycle Study",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        org_unit=org_unit_a,
        currency=currency_usd,
        analyzed_by=admin_user,
        analysis_date=timezone.localdate(),
        analysis_horizon_years=7,
        discount_rate_pct=Decimal("7.50"),
        lifecycle_stage="late_life",
        status="approved",
        acquisition_capital_cost=Decimal("85000.00"),
        preventive_maintenance_cost=Decimal("22000.00"),
        corrective_maintenance_cost=Decimal("28000.00"),
        current_replacement_value=Decimal("90000.00"),
    )
    lcc.full_clean()
    lcc.save()
    return lcc


@pytest.fixture
def analytics_lcc_b(
    db,
    tenant_b,
    fixed_asset_b,
    operational_asset_b,
    category_root_b,
    org_unit_b,
    currency_usd,
    admin_b,
):
    lcc = AssetLifecycleCostAnalysis(
        tenant=tenant_b,
        title="Globex Compressor Lifecycle Cost Study",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        asset_category=category_root_b,
        org_unit=org_unit_b,
        currency=currency_usd,
        analyzed_by=admin_b,
        analysis_date=timezone.localdate(),
        analysis_horizon_years=5,
        discount_rate_pct=Decimal("8.00"),
        lifecycle_stage="in_service",
        status="draft",
        acquisition_capital_cost=Decimal("60000.00"),
        preventive_maintenance_cost=Decimal("5000.00"),
        current_replacement_value=Decimal("70000.00"),
    )
    lcc.full_clean()
    lcc.save()
    return lcc


@pytest.fixture
def analytics_rpl_a(
    db,
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    asset_model_a,
    org_unit_a,
    location_a,
    currency_usd,
    condition_assessment_a,
    analytics_lcc_a,
    admin_user,
):
    rpl = AssetReplacementPlan(
        tenant=tenant_a,
        title="CNC Lathe FY2027 Capital Replacement",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        asset_model=asset_model_a,
        org_unit=org_unit_a,
        location=location_a,
        currency=currency_usd,
        condition_assessment=condition_assessment_a,
        lifecycle_analysis=analytics_lcc_a,
        planner=admin_user,
        predicted_eol_date=timezone.localdate() + timedelta(days=365),
        remaining_useful_life_months=12,
        planned_replacement_year=timezone.localdate().year + 1,
        planned_quarter="q2",
        replacement_strategy="technology_upgrade",
        funding_status="unfunded",
        status="forecasted",
        condition_score=Decimal("42.00"),
        criticality_weight=8,
        failure_risk_score=Decimal("70.00"),
        current_replacement_value=Decimal("150000.00"),
        deferred_maintenance_cost=Decimal("45000.00"),
        estimated_replacement_cost=Decimal("155000.00"),
        inflation_rate_pct=Decimal("4.00"),
        estimated_salvage_recovery=Decimal("12000.00"),
        deferral_penalty_cost=Decimal("9000.00"),
    )
    rpl.full_clean()
    rpl.save()
    return rpl


@pytest.fixture
def analytics_rpl_locked_a(
    db,
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    org_unit_a,
    location_a,
    currency_usd,
    admin_user,
):
    rpl = AssetReplacementPlan(
        tenant=tenant_a,
        title="Approved Substation Switchgear Replacement",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        org_unit=org_unit_a,
        location=location_a,
        currency=currency_usd,
        planner=admin_user,
        remaining_useful_life_months=6,
        planned_replacement_year=timezone.localdate().year + 1,
        planned_quarter="q1",
        replacement_strategy="like_for_like",
        funding_status="budget_allocated",
        status="approved",
        condition_score=Decimal("30.00"),
        criticality_weight=9,
        failure_risk_score=Decimal("82.00"),
        current_replacement_value=Decimal("200000.00"),
        deferred_maintenance_cost=Decimal("60000.00"),
        estimated_replacement_cost=Decimal("210000.00"),
        inflation_rate_pct=Decimal("3.50"),
    )
    rpl.full_clean()
    rpl.save()
    return rpl


@pytest.fixture
def analytics_rpl_b(
    db,
    tenant_b,
    fixed_asset_b,
    operational_asset_b,
    category_root_b,
    org_unit_b,
    location_b,
    currency_usd,
    admin_b,
):
    rpl = AssetReplacementPlan(
        tenant=tenant_b,
        title="Globex Forklift Replacement Plan",
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        asset_category=category_root_b,
        org_unit=org_unit_b,
        location=location_b,
        currency=currency_usd,
        planner=admin_b,
        remaining_useful_life_months=18,
        planned_replacement_year=timezone.localdate().year + 2,
        planned_quarter="q3",
        replacement_strategy="like_for_like",
        funding_status="unfunded",
        status="forecasted",
        condition_score=Decimal("55.00"),
        criticality_weight=6,
        failure_risk_score=Decimal("50.00"),
        current_replacement_value=Decimal("75000.00"),
        deferred_maintenance_cost=Decimal("10000.00"),
        estimated_replacement_cost=Decimal("78000.00"),
        inflation_rate_pct=Decimal("4.00"),
    )
    rpl.full_clean()
    rpl.save()
    return rpl


@pytest.fixture
def analytics_scenario_base_a(
    db,
    tenant_a,
    org_unit_a,
    category_root_a,
    currency_usd,
    admin_user,
    analytics_rpl_a,
):
    scenario = AssetPortfolioScenario(
        tenant=tenant_a,
        name="FY2026 Baseline BAU Scenario",
        scenario_type="baseline_bau",
        is_baseline=True,
        base_fiscal_year=timezone.localdate().year,
        horizon_years=5,
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        currency=currency_usd,
        owner=admin_user,
        status="draft",
        annual_capex_budget_limit=Decimal("300000.00"),
        discount_rate_pct=Decimal("8.00"),
        inflation_rate_pct=Decimal("4.00"),
    )
    scenario.full_clean()
    scenario.save()
    scenario.run_simulation()
    return scenario


@pytest.fixture
def analytics_scenario_a(
    db,
    tenant_a,
    org_unit_a,
    category_root_a,
    currency_usd,
    admin_user,
    analytics_scenario_base_a,
):
    scenario = AssetPortfolioScenario(
        tenant=tenant_a,
        name="Accelerated Replacement & Efficiency Scenario",
        scenario_type="accelerated_replacement",
        is_baseline=False,
        base_fiscal_year=timezone.localdate().year,
        horizon_years=5,
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        currency=currency_usd,
        baseline_scenario=analytics_scenario_base_a,
        owner=admin_user,
        status="draft",
        annual_capex_budget_limit=Decimal("450000.00"),
        discount_rate_pct=Decimal("8.00"),
        inflation_rate_pct=Decimal("4.00"),
        acceleration_months=12,
        fleet_growth_pct=Decimal("5.00"),
        consolidation_reduction_pct=Decimal("0.00"),
        maintenance_efficiency_gain_pct=Decimal("12.00"),
    )
    scenario.full_clean()
    scenario.save()
    return scenario


@pytest.fixture
def analytics_scenario_locked_a(
    db,
    tenant_a,
    org_unit_a,
    currency_usd,
    admin_user,
):
    scenario = AssetPortfolioScenario(
        tenant=tenant_a,
        name="Adopted FY2026 Fleet Consolidation",
        scenario_type="site_consolidation",
        is_baseline=False,
        base_fiscal_year=timezone.localdate().year,
        horizon_years=5,
        scope_org_unit=org_unit_a,
        currency=currency_usd,
        owner=admin_user,
        status="adopted",
        annual_capex_budget_limit=Decimal("250000.00"),
        consolidation_reduction_pct=Decimal("10.00"),
    )
    scenario.full_clean()
    scenario.save()
    return scenario


@pytest.fixture
def analytics_scenario_b(
    db,
    tenant_b,
    org_unit_b,
    category_root_b,
    currency_usd,
    admin_b,
):
    scenario = AssetPortfolioScenario(
        tenant=tenant_b,
        name="Globex Baseline BAU Scenario",
        scenario_type="baseline_bau",
        is_baseline=True,
        base_fiscal_year=timezone.localdate().year,
        horizon_years=5,
        scope_org_unit=org_unit_b,
        scope_category=category_root_b,
        currency=currency_usd,
        owner=admin_b,
        status="draft",
        annual_capex_budget_limit=Decimal("150000.00"),
    )
    scenario.full_clean()
    scenario.save()
    return scenario


@pytest.fixture
def analytics_scorecard_a(
    db,
    tenant_a,
    org_unit_a,
    category_root_a,
    currency_usd,
    admin_user,
):
    today = timezone.localdate()
    scorecard = AssetExecutiveScorecard(
        tenant=tenant_a,
        title="Q1 Portfolio Executive Scorecard",
        period_type="quarterly",
        period_start=today - timedelta(days=90),
        period_end=today,
        org_unit=org_unit_a,
        asset_category=category_root_a,
        currency=currency_usd,
        prepared_by=admin_user,
        status="draft",
        target_asset_roi_pct=Decimal("12.00"),
        target_mcr_pct=Decimal("3.50"),
        target_compliance_rate_pct=Decimal("95.00"),
        annual_asset_return_amount=Decimal("40000.00"),
        executive_summary="Quarterly asset performance & risk brief.",
    )
    scorecard.full_clean()
    scorecard.save()
    return scorecard


@pytest.fixture
def analytics_scorecard_published_a(
    db,
    tenant_a,
    org_unit_a,
    currency_usd,
    member_user,
):
    today = timezone.localdate()
    scorecard = AssetExecutiveScorecard(
        tenant=tenant_a,
        title="Published Executive Scorecard",
        period_type="quarterly",
        period_start=today - timedelta(days=90),
        period_end=today,
        org_unit=org_unit_a,
        currency=currency_usd,
        prepared_by=member_user,
        status="published",
        rag_status="green",
        target_asset_roi_pct=Decimal("12.00"),
        target_mcr_pct=Decimal("3.50"),
        target_compliance_rate_pct=Decimal("95.00"),
        annual_asset_return_amount=Decimal("55000.00"),
    )
    scorecard.full_clean()
    scorecard.save()
    return scorecard


@pytest.fixture
def analytics_scorecard_b(
    db,
    tenant_b,
    org_unit_b,
    currency_usd,
    admin_b,
):
    today = timezone.localdate()
    scorecard = AssetExecutiveScorecard(
        tenant=tenant_b,
        title="Globex Q1 Executive Scorecard",
        period_type="quarterly",
        period_start=today - timedelta(days=90),
        period_end=today,
        org_unit=org_unit_b,
        currency=currency_usd,
        prepared_by=admin_b,
        status="draft",
        annual_asset_return_amount=Decimal("25000.00"),
    )
    scorecard.full_clean()
    scorecard.save()
    return scorecard


# ---------------------------------------------------------------------------
# Module 11.18 — IT Asset Management (ITAM)
# ---------------------------------------------------------------------------


@pytest.fixture
def it_hardware_a(
    db,
    tenant_a,
    org_unit_a,
    location_a,
    vendor_party_a,
    currency_usd,
    admin_user,
):
    today = timezone.localdate()
    hw = ItHardwareAsset(
        tenant=tenant_a,
        hostname="acme-app-srv01",
        fqdn="acme-app-srv01.acme.local",
        device_class="physical_server",
        serial_number="SN-ACME-ITHW-001",
        asset_tag_code="IT-SRV-001",
        manufacturer="Dell",
        model_name="PowerEdge R760",
        operating_system="Ubuntu",
        os_version="24.04 LTS",
        environment="production",
        criticality="high",
        mdm_enrolled=True,
        mdm_platform="Microsoft Intune",
        disk_encryption_status="luks_encrypted",
        status="deployed",
        commissioned_date=today - timedelta(days=365),
        assigned_date=today - timedelta(days=360),
        vendor_eos_date=today + timedelta(days=365),
        vendor_eol_date=today + timedelta(days=730),
        refresh_cycle_months=48,
        estimated_refresh_cost=Decimal("8500.00"),
        currency=currency_usd,
        sanitization_required=True,
        sanitization_method="none",
        sanitization_status="pending_wipe",
        org_unit=org_unit_a,
        location=location_a,
        custodian_party=vendor_party_a,
        vendor_party=vendor_party_a,
        owner=admin_user,
    )
    hw.full_clean()
    hw.save()
    return hw


@pytest.fixture
def it_hardware_b(
    db,
    tenant_b,
    org_unit_b,
    location_b,
    vendor_party_b,
    currency_usd,
    admin_b,
):
    today = timezone.localdate()
    hw = ItHardwareAsset(
        tenant=tenant_b,
        hostname="globex-lap-001",
        fqdn="globex-lap-001.globex.local",
        device_class="laptop",
        serial_number="SN-GLOBEX-ITHW-001",
        asset_tag_code="IT-LAP-001",
        manufacturer="Apple",
        model_name="MacBook Pro 14",
        operating_system="macOS",
        os_version="15.3",
        environment="corporate_enduser",
        criticality="medium",
        mdm_enrolled=True,
        mdm_platform="Jamf Pro",
        disk_encryption_status="bitlocker_filevault",
        status="staged_in_stock",
        commissioned_date=today - timedelta(days=180),
        vendor_eos_date=today + timedelta(days=540),
        vendor_eol_date=today + timedelta(days=900),
        refresh_cycle_months=36,
        estimated_refresh_cost=Decimal("2400.00"),
        currency=currency_usd,
        sanitization_required=True,
        sanitization_method="none",
        sanitization_status="pending_wipe",
        org_unit=org_unit_b,
        location=location_b,
        custodian_party=vendor_party_b,
        vendor_party=vendor_party_b,
        owner=admin_b,
    )
    hw.full_clean()
    hw.save()
    return hw


@pytest.fixture
def software_license_a(
    db,
    tenant_a,
    org_unit_a,
    vendor_party_a,
    currency_usd,
    admin_user,
):
    today = timezone.localdate()
    lic = SoftwareLicense(
        tenant=tenant_a,
        software_name="Microsoft 365 E5",
        publisher_name="Microsoft",
        product_sku="M365-E5-ENT",
        version_edition="Enterprise 2026",
        software_category="productivity_suite",
        license_type="subscription_term",
        license_metric="per_user",
        agreement_number="EA-ACME-2026-01",
        license_key_ref="MS365-****-9X2K",
        entitled_quantity=100,
        allocated_quantity=95,
        active_used_quantity=90,
        reclaimable_inactive_count=0,
        unit_license_cost=Decimal("420.00"),
        total_annual_spend=Decimal("42000.00"),
        currency=currency_usd,
        effective_date=today - timedelta(days=180),
        renewal_date=today + timedelta(days=185),
        vendor_eol_date=today + timedelta(days=730),
        auto_renew=True,
        status="active_compliant",
        publisher_party=vendor_party_a,
        org_unit=org_unit_a,
        license_owner=admin_user,
    )
    lic.full_clean()
    lic.save()
    return lic


@pytest.fixture
def software_license_b(
    db,
    tenant_b,
    org_unit_b,
    vendor_party_b,
    currency_usd,
    admin_b,
):
    today = timezone.localdate()
    lic = SoftwareLicense(
        tenant=tenant_b,
        software_name="JetBrains All Products Pack",
        publisher_name="JetBrains",
        product_sku="JB-ALL-ENT",
        version_edition="2026.1",
        software_category="devops_ide",
        license_type="subscription_term",
        license_metric="per_user",
        agreement_number="JB-GLOBEX-2026-01",
        license_key_ref="JBALL-****-4P7M",
        entitled_quantity=50,
        allocated_quantity=45,
        active_used_quantity=42,
        reclaimable_inactive_count=0,
        unit_license_cost=Decimal("289.00"),
        total_annual_spend=Decimal("14450.00"),
        currency=currency_usd,
        effective_date=today - timedelta(days=90),
        renewal_date=today + timedelta(days=275),
        vendor_eol_date=today + timedelta(days=730),
        auto_renew=False,
        status="active_compliant",
        publisher_party=vendor_party_b,
        org_unit=org_unit_b,
        license_owner=admin_b,
    )
    lic.full_clean()
    lic.save()
    return lic


@pytest.fixture
def cloud_subscription_a(
    db,
    tenant_a,
    org_unit_a,
    vendor_party_a,
    currency_usd,
    admin_user,
):
    today = timezone.localdate()
    sub = CloudAssetSubscription(
        tenant=tenant_a,
        name="AWS Production EKS Cluster",
        asset_kind="iaas_compute",
        provider="aws",
        external_account_id="aws-acct-acme-1001",
        cloud_resource_id="arn:aws:eks:us-east-1:1001:cluster/prod",
        cloud_region="us-east-1",
        environment="production",
        resource_tags={"env": "prod", "cost_center": "CC-ENG", "owner": "devops"},
        billing_cadence="monthly",
        commitment_term="1yr_reserved",
        monthly_recurring_cost=Decimal("4500.00"),
        annual_contract_value=Decimal("54000.00"),
        currency=currency_usd,
        provisioned_seats=40,
        active_seats_30d=36,
        sso_status="sso_enforced",
        approval_status="sanctioned",
        renewal_date=today + timedelta(days=180),
        cancellation_notice_days=30,
        auto_renew=True,
        vendor_eol_date=today + timedelta(days=730),
        status="active",
        org_unit=org_unit_a,
        vendor_party=vendor_party_a,
        business_owner=admin_user,
        technical_owner=admin_user,
    )
    sub.full_clean()
    sub.save()
    return sub


@pytest.fixture
def cloud_subscription_b(
    db,
    tenant_b,
    org_unit_b,
    vendor_party_b,
    currency_usd,
    admin_b,
):
    today = timezone.localdate()
    sub = CloudAssetSubscription(
        tenant=tenant_b,
        name="Azure Core App Service",
        asset_kind="paas_database",
        provider="azure",
        external_account_id="az-sub-globex-2001",
        cloud_resource_id="/subscriptions/2001/resourceGroups/prod/providers/Microsoft.Web/sites/core",
        cloud_region="eastus",
        environment="production",
        resource_tags={"env": "prod", "cost_center": "CC-OPS", "owner": "platform"},
        billing_cadence="annual",
        commitment_term="annual_contract",
        monthly_recurring_cost=Decimal("2200.00"),
        annual_contract_value=Decimal("26400.00"),
        currency=currency_usd,
        provisioned_seats=25,
        active_seats_30d=22,
        sso_status="sso_enforced",
        approval_status="sanctioned",
        renewal_date=today + timedelta(days=200),
        cancellation_notice_days=30,
        auto_renew=True,
        vendor_eol_date=today + timedelta(days=730),
        status="active",
        org_unit=org_unit_b,
        vendor_party=vendor_party_b,
        business_owner=admin_b,
        technical_owner=admin_b,
    )
    sub.full_clean()
    sub.save()
    return sub


@pytest.fixture
def cmdb_relationship_a(
    db,
    tenant_a,
    software_license_a,
    it_hardware_a,
    admin_user,
):
    rel = CmdbRelationship(
        tenant=tenant_a,
        source_ci_type="software_license",
        source_software=software_license_a,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_a,
        environment="production",
        criticality="tier_2_business_important",
        impact_severity="degraded_performance",
        is_single_point_of_failure=False,
        verified_on=timezone.localdate(),
        verified_by=admin_user,
        status="active",
        owner=admin_user,
        blast_radius_notes="Primary productivity license suite running on Acme app server.",
    )
    rel.full_clean()
    rel.save()
    return rel


@pytest.fixture
def cmdb_relationship_b(
    db,
    tenant_b,
    software_license_b,
    it_hardware_b,
    admin_b,
):
    rel = CmdbRelationship(
        tenant=tenant_b,
        source_ci_type="software_license",
        source_software=software_license_b,
        relationship_type="runs_on",
        target_ci_type="it_hardware",
        target_hardware=it_hardware_b,
        environment="production",
        criticality="tier_3_operational",
        impact_severity="informational",
        is_single_point_of_failure=False,
        verified_on=timezone.localdate(),
        verified_by=admin_b,
        status="active",
        owner=admin_b,
        blast_radius_notes="Globex developer IDE license deployed on corporate endpoint.",
    )
    rel.full_clean()
    rel.save()
    return rel


# ===== 11.17 SpaceFacilityAsset =====


@pytest.fixture
def sfa_member_client_a(db, member_user):
    from django.test import Client
    c = Client()
    c.force_login(member_user)
    return c


@pytest.fixture
def sfa_space_building_a(
    db,
    tenant_a,
    org_unit_a,
    location_a,
    integration_gis_mapping_a,
    adk_document_a,
    admin_user,
):
    space = AssetFacilitySpace(
        tenant=tenant_a,
        code="SFA-BLDG-A",
        name="Acme North Tower A",
        space_level="building",
        space_category="office_workspace",
        org_unit=org_unit_a,
        scm_location=location_a,
        gis_mapping=integration_gis_mapping_a,
        floor_plan_document=adk_document_a,
        space_steward=admin_user,
        gross_area_sqft=Decimal("20000.00"),
        rentable_area_sqft=Decimal("18000.00"),
        usable_area_sqft=Decimal("16000.00"),
        common_area_sqft=Decimal("2000.00"),
        annual_rate_per_sqft=Decimal("40.00"),
        design_seat_capacity=120,
        current_headcount=96,
        cad_layer_ref="A-BLDG-N",
        bim_guid="1117-bldg-a-001",
        bim_level_ref="Campus Tower A",
        drawing_revision="Rev A",
        status="active",
        notes="Primary corporate office building for 11.17 tests.",
    )
    space.full_clean()
    space.save()
    return space


@pytest.fixture
def sfa_space_floor_a(
    db,
    tenant_a,
    sfa_space_building_a,
    org_unit_a,
    location_a,
    adk_document_a,
    admin_user,
):
    space = AssetFacilitySpace(
        tenant=tenant_a,
        code="SFA-F02-A",
        name="Acme Floor 02 Engineering Suite",
        space_level="floor",
        space_category="office_workspace",
        parent=sfa_space_building_a,
        org_unit=org_unit_a,
        scm_location=location_a,
        floor_plan_document=adk_document_a,
        space_steward=admin_user,
        gross_area_sqft=Decimal("8000.00"),
        rentable_area_sqft=Decimal("7200.00"),
        usable_area_sqft=Decimal("6400.00"),
        common_area_sqft=Decimal("800.00"),
        annual_rate_per_sqft=Decimal("42.00"),
        design_seat_capacity=60,
        current_headcount=45,
        cad_layer_ref="A-F02-ENG",
        bim_level_ref="Level 02",
        drawing_revision="Rev B",
        status="active",
    )
    space.full_clean()
    space.save()
    return space


@pytest.fixture
def sfa_space_b(
    db,
    tenant_b,
    org_unit_b,
    location_b,
    adk_document_b,
    admin_b,
):
    space = AssetFacilitySpace(
        tenant=tenant_b,
        code="SFA-GLX-01",
        name="Globex East Hub",
        space_level="building",
        space_category="office_workspace",
        org_unit=org_unit_b,
        scm_location=location_b,
        floor_plan_document=adk_document_b,
        space_steward=admin_b,
        gross_area_sqft=Decimal("10000.00"),
        rentable_area_sqft=Decimal("9000.00"),
        usable_area_sqft=Decimal("8000.00"),
        common_area_sqft=Decimal("1000.00"),
        annual_rate_per_sqft=Decimal("35.00"),
        design_seat_capacity=50,
        current_headcount=40,
        status="active",
    )
    space.full_clean()
    space.save()
    return space


@pytest.fixture
def sfa_building_system_hvac_a(
    db,
    tenant_a,
    sfa_space_floor_a,
    operational_asset_a,
    fixed_asset_a,
    energy_reading_a,
    maintenance_schedule_a,
    permit_license_a,
    adk_document_a,
    vendor_party_a,
    org_unit_a,
):
    today = timezone.localdate()
    sys_obj = AssetBuildingSystem(
        tenant=tenant_a,
        name="Rooftop AHU-11.17",
        system_domain="hvac_climate",
        subsystem_type="ahu_air_handler",
        facility_space=sfa_space_floor_a,
        pin_x_pct=Decimal("25.00"),
        pin_y_pct=Decimal("40.00"),
        manufacturer="Trane",
        model_number="CSAA-100",
        serial_number="TRN-SFA-01",
        load_or_voltage_rating="480V / 3-Phase",
        ashrae_nfpa_code_ref="ASHRAE 90.1",
        served_area_sqft=Decimal("6400.00"),
        design_capacity_btu_kw=Decimal("320.00"),
        setpoint_temp_c=Decimal("22.00"),
        measured_temp_c=Decimal("22.30"),
        target_humidity_pct=Decimal("45.00"),
        measured_humidity_pct=Decimal("46.00"),
        airflow_cfm=Decimal("12000.00"),
        condition_grade="good",
        criticality_tier="tier_2_mission_crit",
        remaining_useful_life_years=12,
        replacement_cost_estimate=Decimal("95000.00"),
        last_statutory_inspection_date=today - timedelta(days=30),
        next_inspection_due_date=today + timedelta(days=150),
        status="operational",
        operational_asset=operational_asset_a,
        fixed_asset=fixed_asset_a,
        latest_energy_reading=energy_reading_a,
        maintenance_schedule=maintenance_schedule_a,
        operating_permit=permit_license_a,
        schematic_document=adk_document_a,
        service_vendor=vendor_party_a,
        org_unit=org_unit_a,
    )
    sys_obj.full_clean()
    sys_obj.save()
    return sys_obj


@pytest.fixture
def sfa_building_system_infra_a(
    db,
    tenant_a,
    sfa_space_building_a,
    org_unit_a,
    vendor_party_a,
    permit_license_a,
):
    today = timezone.localdate()
    sys_obj = AssetBuildingSystem(
        tenant=tenant_a,
        name="Main Switchgear MDB-11.17",
        system_domain="electrical_power",
        subsystem_type="switchgear_panel",
        facility_space=sfa_space_building_a,
        pin_x_pct=Decimal("15.00"),
        pin_y_pct=Decimal("70.00"),
        manufacturer="Schneider",
        model_number="QED-4000",
        serial_number="SCH-SFA-99",
        load_or_voltage_rating="480Y/277V 4000A",
        ashrae_nfpa_code_ref="NFPA 70E",
        served_area_sqft=Decimal("20000.00"),
        design_capacity_btu_kw=Decimal("1800.00"),
        condition_grade="excellent",
        criticality_tier="tier_1_life_safety",
        remaining_useful_life_years=20,
        replacement_cost_estimate=Decimal("220000.00"),
        last_statutory_inspection_date=today - timedelta(days=60),
        next_inspection_due_date=today + timedelta(days=300),
        status="operational",
        operating_permit=permit_license_a,
        service_vendor=vendor_party_a,
        org_unit=org_unit_a,
    )
    sys_obj.full_clean()
    sys_obj.save()
    return sys_obj


@pytest.fixture
def sfa_building_system_b(
    db,
    tenant_b,
    sfa_space_b,
    org_unit_b,
    vendor_party_b,
):
    today = timezone.localdate()
    sys_obj = AssetBuildingSystem(
        tenant=tenant_b,
        name="Globex Switchgear B",
        system_domain="electrical_power",
        subsystem_type="switchgear_panel",
        facility_space=sfa_space_b,
        manufacturer="Eaton",
        model_number="PRL-200",
        serial_number="ETN-GLX-01",
        condition_grade="good",
        criticality_tier="tier_1_life_safety",
        status="operational",
        last_statutory_inspection_date=today - timedelta(days=15),
        next_inspection_due_date=today + timedelta(days=180),
        service_vendor=vendor_party_b,
        org_unit=org_unit_b,
    )
    sys_obj.full_clean()
    sys_obj.save()
    return sys_obj


@pytest.fixture
def sfa_furniture_a(
    db,
    tenant_a,
    sfa_space_floor_a,
    vendor_party_a,
    org_unit_a,
    operational_asset_a,
    admin_user,
):
    ffe = AssetFurnitureFixture(
        tenant=tenant_a,
        name="Sit-Stand Workstation Pod A",
        ffe_category="workstation_desk",
        asset_tag_code="SFA-FFE-A01",
        manufacturer="Herman Miller",
        model_sku="HM-RENEW-6P",
        finish_material="Natural Oak",
        facility_space=sfa_space_floor_a,
        custodian_party=vendor_party_a,
        assigned_org_unit=org_unit_a,
        operational_asset=operational_asset_a,
        move_coordinator=admin_user,
        quantity=6,
        unit_replacement_cost=Decimal("1500.00"),
        pin_x_pct=Decimal("30.00"),
        pin_y_pct=Decimal("50.00"),
        condition_grade="good",
        move_status="in_place",
    )
    ffe.full_clean()
    ffe.save()
    return ffe


@pytest.fixture
def sfa_furniture_b(
    db,
    tenant_b,
    sfa_space_b,
    vendor_party_b,
    org_unit_b,
    admin_b,
):
    ffe = AssetFurnitureFixture(
        tenant=tenant_b,
        name="Globex Boardroom Table B",
        ffe_category="conference_table",
        asset_tag_code="SFA-FFE-B01",
        manufacturer="Steelcase",
        facility_space=sfa_space_b,
        custodian_party=vendor_party_b,
        assigned_org_unit=org_unit_b,
        move_coordinator=admin_b,
        quantity=1,
        unit_replacement_cost=Decimal("9000.00"),
        condition_grade="good",
        move_status="in_place",
    )
    ffe.full_clean()
    ffe.save()
    return ffe


@pytest.fixture
def sfa_chargeback_draft_a(
    db,
    tenant_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    lease_contract_a,
    fixed_asset_a,
    org_unit_a,
    vendor_party_a,
    currency_usd,
    integration_open_fiscal_period_a,
    expense_account_a,
    accum_account_a,
):
    today = timezone.localdate()
    cb = AssetSpaceChargeback(
        tenant=tenant_a,
        title="Monthly Engineering Floor Chargeback",
        coordination_type="space_chargeback",
        allocation_basis="usable_sqft",
        facility_space=sfa_space_floor_a,
        shared_building_system=sfa_building_system_hvac_a,
        lease_contract=lease_contract_a,
        fixed_asset=fixed_asset_a,
        charged_org_unit=org_unit_a,
        occupant_party=vendor_party_a,
        currency=currency_usd,
        fiscal_period=integration_open_fiscal_period_a,
        expense_gl_account=expense_account_a,
        recovery_gl_account=accum_account_a,
        period_start=today.replace(day=1),
        period_end=today,
        allocated_area_sqft=Decimal("6400.00"),
        allocation_share_pct=Decimal("40.00"),
        base_cost_amount=Decimal("5000.00"),
        shared_cam_amount=Decimal("1000.00"),
        utility_recovery_amount=Decimal("500.00"),
        ti_improvement_cost=Decimal("400.00"),
        ti_allowance_offset=Decimal("150.00"),
        status="draft",
    )
    cb.full_clean()
    cb.save()
    return cb


@pytest.fixture
def sfa_chargeback_approved_a(
    db,
    tenant_a,
    sfa_space_floor_a,
    sfa_building_system_infra_a,
    org_unit_a,
    vendor_party_a,
    currency_usd,
    integration_open_fiscal_period_a,
    expense_account_a,
    accum_account_a,
    admin_user,
):
    today = timezone.localdate()
    cb = AssetSpaceChargeback(
        tenant=tenant_a,
        title="Approved Switchgear Recovery Chargeback",
        coordination_type="cam_utility_recovery",
        allocation_basis="usable_sqft",
        facility_space=sfa_space_floor_a,
        shared_building_system=sfa_building_system_infra_a,
        charged_org_unit=org_unit_a,
        occupant_party=vendor_party_a,
        currency=currency_usd,
        fiscal_period=integration_open_fiscal_period_a,
        expense_gl_account=expense_account_a,
        recovery_gl_account=accum_account_a,
        period_start=today.replace(day=1),
        period_end=today,
        allocated_area_sqft=Decimal("6400.00"),
        allocation_share_pct=Decimal("25.00"),
        base_cost_amount=Decimal("2000.00"),
        shared_cam_amount=Decimal("500.00"),
        utility_recovery_amount=Decimal("250.00"),
        ti_improvement_cost=Decimal("0.00"),
        ti_allowance_offset=Decimal("0.00"),
        status="approved",
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    cb.full_clean()
    cb.save()
    return cb


@pytest.fixture
def sfa_chargeback_b(
    db,
    tenant_b,
    sfa_space_b,
    sfa_building_system_b,
    org_unit_b,
    vendor_party_b,
    currency_usd,
    integration_open_fiscal_period_b,
    expense_account_b,
    accum_account_b,
):
    today = timezone.localdate()
    cb = AssetSpaceChargeback(
        tenant=tenant_b,
        title="Globex Hub Chargeback",
        coordination_type="space_chargeback",
        allocation_basis="usable_sqft",
        facility_space=sfa_space_b,
        shared_building_system=sfa_building_system_b,
        charged_org_unit=org_unit_b,
        occupant_party=vendor_party_b,
        currency=currency_usd,
        fiscal_period=integration_open_fiscal_period_b,
        expense_gl_account=expense_account_b,
        recovery_gl_account=accum_account_b,
        period_start=today.replace(day=1),
        period_end=today,
        base_cost_amount=Decimal("3000.00"),
        status="draft",
    )
    cb.full_clean()
    cb.save()
    return cb
