"""Shared test contract fixtures for apps/assets (Module 11)."""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.accounting.models import Currency, GLAccount
from apps.core.models import OrgUnit, Party, PartyRole
from apps.scm.models import Asset, Location, PurchaseOrder
from apps.assets.models import (
    AssetRequisition,
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetTag,
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
def location_a(db, tenant_a):
    return Location.objects.create(
        tenant=tenant_a,
        code="WH-MAIN-A",
        name="Acme Central Staging Dock",
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
