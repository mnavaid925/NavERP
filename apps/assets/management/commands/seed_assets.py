from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset, GLAccount
from apps.assets.models import (
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetRequisition,
    AssetTag,
)
from apps.core.models import OrgUnit, Party, Tenant
from apps.scm.models import Asset, Location, PurchaseOrder

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo data for Module 11: Asset Management System (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing assets module data before seeding",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing assets module data...")
            AssetTag.objects.all().delete()
            AssetCapitalization.objects.all().delete()
            AssetAcquisitionReceipt.objects.all().delete()
            AssetRequisition.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Assets data flushed successfully."))

        tenants = Tenant.objects.all()
        if not tenants.exists():
            self.stdout.write(self.style.WARNING("No tenants found. Run seed_core and seed_accounts first."))
            return

        for tenant in tenants:
            self._seed_tenant(tenant)

        self.stdout.write(self.style.SUCCESS("Module 11 assets seeding complete."))
        self.stdout.write(self.style.SUCCESS("Tenant admin login credentials: admin_acme / password"))

    def _seed_tenant(self, tenant):
        # Idempotency guard: if data exists for this tenant, skip creation
        if AssetRequisition.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] Assets data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding Asset Management System...")

        user = User.objects.filter(tenant=tenant).first()
        currency = Currency.objects.filter(is_active=True).first()
        org_unit = OrgUnit.objects.filter(tenant=tenant).first()
        location = Location.objects.filter(tenant=tenant).first()
        vendor = Party.objects.filter(tenant=tenant, roles__role__in=["vendor", "supplier"]).first() or Party.objects.filter(tenant=tenant).first()
        po = PurchaseOrder.objects.filter(tenant=tenant).first()
        asset_account = GLAccount.objects.filter(tenant=tenant, account_type="asset").first() or GLAccount.objects.filter(tenant=tenant).first()
        cip_account = GLAccount.objects.filter(tenant=tenant, account_type="asset").last() or GLAccount.objects.filter(tenant=tenant).last()
        existing_operational_asset = Asset.objects.filter(tenant=tenant).first()

        with transaction.atomic():
            # 1. Asset Requisitions
            req1 = AssetRequisition.objects.create(
                tenant=tenant,
                title="CNC 5-Axis Vertical Machining Center",
                description="High-precision Haas VF-4SS with 12,000 RPM inline direct-drive spindle and 30+1 tool changer for prototype manufacturing.",
                business_justification="Required to eliminate outsourced machining bottlenecks and meet Q3 aerospace parts production targets.",
                asset_category="machinery",
                priority="urgent",
                estimated_cost=Decimal("148500.00"),
                currency=currency,
                budget_code="CAPEX-2026-MFG-01",
                proposed_vendor=vendor,
                proposed_manufacturer="Haas Automation",
                proposed_model="VF-4SS",
                required_delivery_date=timezone.now().date() + timezone.timedelta(days=45),
                target_org_unit=org_unit,
                target_location=location,
                status="approved",
                submitted_by=user,
                submitted_at=timezone.now() - timezone.timedelta(days=14),
                approved_by=user,
                approved_at=timezone.now() - timezone.timedelta(days=12),
                purchase_order=po,
            )

            req2 = AssetRequisition.objects.create(
                tenant=tenant,
                title="Heavy Duty Industrial Electric Forklift 5000lb",
                description="Toyota 8FBE20U 3-wheel electric forklift with cushion tires, side-shifter, and Lithium-ion battery pack.",
                business_justification="Replaces end-of-life leased forklift to reduce monthly operating lease costs by $1,800/mo.",
                asset_category="vehicle",
                priority="high",
                estimated_cost=Decimal("38500.00"),
                currency=currency,
                budget_code="CAPEX-2026-LOG-03",
                proposed_vendor=vendor,
                proposed_manufacturer="Toyota Material Handling",
                proposed_model="8FBE20U",
                required_delivery_date=timezone.now().date() + timezone.timedelta(days=20),
                target_org_unit=org_unit,
                target_location=location,
                status="pending_approval",
                submitted_by=user,
                submitted_at=timezone.now() - timezone.timedelta(days=2),
            )

            req3 = AssetRequisition.objects.create(
                tenant=tenant,
                title="Engineering CAD Workstation Cluster (4 Nodes)",
                description="Dell Precision 5860 Tower Workstations with Intel Xeon W-2400 and NVIDIA RTX 4500 Ada GPUs for FEA/CFD simulation.",
                business_justification="Current workstations crash during ANSYS finite element meshing runs, causing engineering delays.",
                asset_category="it_hardware",
                priority="medium",
                estimated_cost=Decimal("26000.00"),
                currency=currency,
                budget_code="CAPEX-2026-IT-09",
                proposed_vendor=vendor,
                proposed_manufacturer="Dell Technologies",
                proposed_model="Precision 5860",
                required_delivery_date=timezone.now().date() + timezone.timedelta(days=10),
                target_org_unit=org_unit,
                target_location=location,
                status="draft",
            )

            # 2. Asset Acquisition Receipts
            rcv1 = AssetAcquisitionReceipt.objects.create(
                tenant=tenant,
                title="Receipt of Haas VF-4SS CNC Machine",
                requisition=req1,
                purchase_order=po,
                vendor=vendor,
                manufacturer="Haas Automation",
                model_number="VF-4SS",
                serial_number="SN-HAAS-2026-9921",
                quantity_received=1,
                received_date=timezone.now().date() - timezone.timedelta(days=5),
                carrier_name="Expeditors Ocean Freight",
                tracking_number="EXP-99281726",
                bill_of_lading="BOL-HAAS-0029",
                receiving_location=location,
                condition_on_arrival="excellent",
                inspection_notes="Crate unsealed and inspected. Zero transit shock sensor triggers. Tooling kit and manuals verified.",
                inspected_by=user,
                inspected_at=timezone.now() - timezone.timedelta(days=4),
                status="accepted",
            )

            rcv2 = AssetAcquisitionReceipt.objects.create(
                tenant=tenant,
                title="Receipt of Dell Workstation Cluster Batch #1",
                requisition=req3,
                purchase_order=po,
                vendor=vendor,
                manufacturer="Dell Technologies",
                model_number="Precision 5860",
                serial_number="DELL-TAG-882910A",
                quantity_received=2,
                received_date=timezone.now().date() - timezone.timedelta(days=1),
                carrier_name="UPS Express Freight",
                tracking_number="1Z9999999999999999",
                bill_of_lading="BOL-UPS-8821",
                receiving_location=location,
                condition_on_arrival="good",
                inspection_notes="Unboxed 2 of 4 nodes. Initial diagnostic boot successful. Second batch arriving next week.",
                inspected_by=user,
                inspected_at=timezone.now() - timezone.timedelta(hours=6),
                status="pending_inspection",
            )

            # 3. Asset Capitalization Events
            # Create a corresponding FixedAsset in accounting
            fa1 = FixedAsset.objects.create(
                tenant=tenant,
                name="Haas VF-4SS 5-Axis CNC Mill",
                category="Production Machinery",
                acquisition_cost=Decimal("156750.00"),
                salvage_value=Decimal("15000.00"),
                useful_life_months=84,
                method="straight_line",
                in_service_date=timezone.now().date() - timezone.timedelta(days=3),
                asset_account=asset_account,
                status="active",
                notes="Capitalized via ACAP from 11.1 Seeder",
            )

            cap1 = AssetCapitalization.objects.create(
                tenant=tenant,
                title="Capitalization of Haas VF-4SS CNC Machine",
                asset_name="Haas VF-4SS 5-Axis CNC Mill",
                acquisition_receipt=rcv1,
                requisition=req1,
                purchase_cost=Decimal("148500.00"),
                freight_cost=Decimal("3800.00"),
                installation_cost=Decimal("2950.00"),
                customs_duties_cost=Decimal("1500.00"),
                other_initial_costs=Decimal("0.00"),
                is_cip_conversion=False,
                cip_gl_account=cip_account,
                asset_gl_account=asset_account,
                depreciation_method="straight_line",
                useful_life_months=84,
                salvage_value=Decimal("15000.00"),
                in_service_date=timezone.now().date() - timezone.timedelta(days=3),
                fixed_asset=fa1,
                operational_asset=existing_operational_asset,
                status="capitalized",
                capitalized_by=user,
                capitalized_at=timezone.now() - timezone.timedelta(days=3),
            )
            # Update receipt status to capitalized
            rcv1.status = "capitalized"
            rcv1.save(update_fields=["status"])

            # 4. Asset Tags
            tag1 = AssetTag.objects.create(
                tenant=tenant,
                tag_code=f"AST-QR-HAAS-{tenant.pk}-001",
                tag_format="qr_code",
                operational_asset=existing_operational_asset,
                capitalization=cap1,
                physical_placement="Front operator console bezel next to emergency stop button",
                affixed_by=user,
                affixed_at=timezone.now() - timezone.timedelta(days=2),
                is_verified=True,
                verified_by=user,
                verified_at=timezone.now() - timezone.timedelta(days=2),
                scanner_device_id="ZEBRA-TC52-SHOP-01",
                status="verified",
                notes="2D Data Matrix metal QR plate laser-etched and riveted to frame.",
            )

            tag2 = AssetTag.objects.create(
                tenant=tenant,
                tag_code=f"AST-RFID-DELL-{tenant.pk}-002",
                tag_format="rfid_uhf",
                capitalization=cap1,
                physical_placement="Rear server rack ear",
                status="pending_print",
                notes="UHF EPC Gen2 tag allocated for IT asset tracking.",
            )

        self.stdout.write(f"[{tenant.name}] Created 3 requisitions, 2 receipts, 1 capitalization, 2 asset tags.")
