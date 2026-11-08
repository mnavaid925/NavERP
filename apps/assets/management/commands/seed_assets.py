from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset, GLAccount
from apps.assets.models import (
    AssetAcquisitionReceipt,
    AssetAudit,
    AssetCapitalization,
    AssetCustodyLog,
    AssetIncidentReport,
    AssetMovementLog,
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
            AssetIncidentReport.objects.all().delete()
            AssetCustodyLog.objects.all().delete()
            AssetMovementLog.objects.all().delete()
            AssetAudit.objects.all().delete()
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
            self._seed_tenant_11_1(tenant)
            self._seed_tenant_11_2(tenant)

        self.stdout.write(self.style.SUCCESS("Module 11 assets seeding complete."))
        self.stdout.write(self.style.SUCCESS("Tenant admin login credentials: admin_acme / password"))

    def _seed_tenant_11_1(self, tenant):
        # Idempotency guard for 11.1
        if AssetRequisition.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.1 Procurement data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.1 Asset Procurement...")

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
            rcv1.status = "capitalized"
            rcv1.save(update_fields=["status"])

            # 4. Asset Tags
            AssetTag.objects.create(
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

            AssetTag.objects.create(
                tenant=tenant,
                tag_code=f"AST-RFID-DELL-{tenant.pk}-002",
                tag_format="rfid_uhf",
                capitalization=cap1,
                physical_placement="Rear server rack ear",
                status="pending_print",
                notes="UHF EPC Gen2 tag allocated for IT asset tracking.",
            )

        self.stdout.write(f"[{tenant.name}] 11.1 Seeding complete.")

    def _seed_tenant_11_2(self, tenant):
        # Idempotency guard for 11.2
        if AssetAudit.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.2 Inventory & Tracking data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.2 Asset Inventory & Tracking...")

        user = User.objects.filter(tenant=tenant).first()
        org_unit = OrgUnit.objects.filter(tenant=tenant).first()
        locations = list(Location.objects.filter(tenant=tenant))
        loc1 = locations[0] if locations else None
        loc2 = locations[1] if len(locations) > 1 else loc1
        parties = list(Party.objects.filter(tenant=tenant))
        party1 = parties[0] if parties else None
        party2 = parties[1] if len(parties) > 1 else party1

        assets = list(Asset.objects.filter(tenant=tenant))
        if not assets:
            self.stdout.write(f"[{tenant.name}] Warning: No SCM assets found; skipping 11.2 asset-linked logs.")
            return

        asset1 = assets[0]
        asset2 = assets[1] if len(assets) > 1 else asset1
        asset3 = assets[2] if len(assets) > 2 else asset1
        asset4 = assets[3] if len(assets) > 3 else asset1

        with transaction.atomic():
            # 1. Asset Audits
            AssetAudit.objects.create(
                tenant=tenant,
                title="Q2 Annual Wall-to-Wall Physical Asset Audit",
                audit_type="physical_wall_to_wall",
                target_location=loc1,
                target_org_unit=org_unit,
                lead_auditor=user,
                supervisor=user,
                scheduled_date=timezone.now().date() + timezone.timedelta(days=14),
                is_blind_count=True,
                expected_asset_count=85,
                scanned_asset_count=0,
                status="scheduled",
                notes="Full floor-to-ceiling physical tag verification with blind counting enabled.",
            )

            AssetAudit.objects.create(
                tenant=tenant,
                title="Monthly High-Value Production Machinery Cycle Count",
                audit_type="cycle_count_high_value",
                target_location=loc1,
                target_org_unit=org_unit,
                lead_auditor=user,
                supervisor=user,
                scheduled_date=timezone.now().date() - timezone.timedelta(days=7),
                started_at=timezone.now() - timezone.timedelta(days=7, hours=2),
                completed_at=timezone.now() - timezone.timedelta(days=7),
                is_blind_count=False,
                expected_asset_count=24,
                scanned_asset_count=24,
                matched_asset_count=23,
                missing_asset_count=1,
                discrepancy_count=1,
                discrepancy_notes="AST-00004 missing from bay 4; investigation revealed it was sent for unlogged recalibration.",
                reconciliation_action="investigate",
                reconciled_by=user,
                reconciled_at=timezone.now() - timezone.timedelta(days=6),
                status="reconciled",
                notes="Audit closed and discrepancy handed over to plant maintenance manager.",
            )

            AssetAudit.objects.create(
                tenant=tenant,
                title="IT Server Room Equipment Periodic Spot-Audit",
                audit_type="periodic",
                target_location=loc2,
                target_org_unit=org_unit,
                lead_auditor=user,
                supervisor=user,
                scheduled_date=timezone.now().date(),
                started_at=timezone.now() - timezone.timedelta(hours=3),
                is_blind_count=False,
                expected_asset_count=16,
                scanned_asset_count=12,
                matched_asset_count=12,
                status="in_progress",
                notes="Active barcode and RFID scan sweep across server racks 1 through 4.",
            )

            # 2. Asset Movement Logs
            AssetMovementLog.objects.create(
                tenant=tenant,
                title=f"Inter-Facility Relocation of {asset1.name}",
                asset=asset1,
                movement_type="inter_facility",
                from_location=loc1,
                to_location=loc2,
                from_room_bin="Bay A-12",
                to_room_bin="Staging Bay 3",
                from_org_unit=org_unit,
                to_org_unit=org_unit,
                from_custodian=party1,
                to_custodian=party2,
                carrier_name="Swift Freight Logistics",
                tracking_number="SWF-99482104",
                gps_latitude=Decimal("37.774929"),
                gps_longitude=Decimal("-122.419416"),
                gps_address="Interstate 80 Eastbound Milepost 42, CA",
                dispatched_by=user,
                dispatch_date=timezone.now() - timezone.timedelta(days=1),
                status="in_transit",
                reason="Temporary transfer to regional depot for specialized project fabrication.",
                notes="Heavy transport tie-down straps verified. Shock recorder #SR-99 attached.",
            )

            AssetMovementLog.objects.create(
                tenant=tenant,
                title=f"Internal Workshop Relocation of {asset2.name}",
                asset=asset2,
                movement_type="department_transfer",
                from_location=loc1,
                to_location=loc1,
                from_room_bin="Assembly Room 2",
                to_room_bin="R&D Testing Lab",
                from_org_unit=org_unit,
                to_org_unit=org_unit,
                from_custodian=party1,
                to_custodian=party1,
                dispatched_by=user,
                dispatch_date=timezone.now() - timezone.timedelta(days=3),
                received_by=user,
                received_date=timezone.now() - timezone.timedelta(days=3),
                condition_on_receipt="good",
                status="received",
                reason="Relocated for quarterly vibration and thermal benchmark testing.",
                notes="Handover completed and sign-off documented.",
            )

            # 3. Asset Custody Logs (Tool Crib Lending)
            AssetCustodyLog.objects.create(
                tenant=tenant,
                asset=asset3,
                action_type="tool_crib_checkout",
                borrower=party1,
                borrower_name=party1.name if party1 else "John Doe",
                crib_attendant=user,
                purpose="Precision torque measurement on turbine casing assembly.",
                work_order_reference="MWO-2026-0814",
                project_reference="PRJ-AERO-TURB",
                checkout_date=timezone.now() - timezone.timedelta(days=2),
                expected_return_date=timezone.now().date() + timezone.timedelta(days=3),
                checkout_condition="calibrated",
                condition_notes="Calibrated instrument verified within 0.05% tolerance band.",
                borrower_signature_acknowledged=True,
                status="active_loan",
                notes="Checked out under standard tool crib loan liability policy.",
            )

            AssetCustodyLog.objects.create(
                tenant=tenant,
                asset=asset4,
                action_type="field_dispatch",
                borrower=party2,
                borrower_name=party2.name if party2 else "Jane Smith",
                crib_attendant=user,
                purpose="Emergency pipeline ultrasonic flaw testing at offshore platform.",
                work_order_reference="MWO-2026-0792",
                project_reference="PRJ-OFFSHORE-09",
                checkout_date=timezone.now() - timezone.timedelta(days=12),
                expected_return_date=timezone.now().date() - timezone.timedelta(days=3),
                checkout_condition="good",
                borrower_signature_acknowledged=True,
                status="overdue",
                condition_notes="Loan overdue by 3 days. Automated email reminder sent to borrower.",
                notes="Custodian notified to return instrument immediately upon helicopter shore landing.",
            )

            # 4. Asset Incident Reports
            AssetIncidentReport.objects.create(
                tenant=tenant,
                title=f"Suspected Loss of Handheld Diagnostic Scanner {asset1.number}",
                asset=asset1,
                incident_type="lost",
                severity="medium",
                incident_date=timezone.now().date() - timezone.timedelta(days=4),
                last_known_location=loc1,
                location_details="Tool Crib Cabinet #4, shelf B",
                reported_by=user,
                custodian_at_loss=party1,
                investigator=user,
                estimated_loss_value=Decimal("4200.00"),
                incident_description="Tool was checked back into crib system but physically absent from storage locker on morning inventory inspection.",
                investigation_findings="CCTV footage review initiated. No evidence of forced entry into tool crib room.",
                resolution_action="pending",
                status="under_investigation",
            )

            AssetIncidentReport.objects.create(
                tenant=tenant,
                title=f"Theft of Portable Generator {asset2.number} from Jobsite Yard",
                asset=asset2,
                incident_type="stolen",
                severity="critical",
                incident_date=timezone.now().date() - timezone.timedelta(days=10),
                last_known_location=loc1,
                location_details="North Perimeter Gate, Construction Laydown Yard",
                reported_by=user,
                custodian_at_loss=party2,
                investigator=user,
                police_report_filed=True,
                police_report_number="PD-2026-009841",
                police_precinct="Northern Regional Police Command",
                police_filing_date=timezone.now().date() - timezone.timedelta(days=9),
                insurance_claim_filed=True,
                insurance_carrier="Liberty Mutual Commercial Underwriters",
                insurance_claim_number="CLM-LM-2026-8819",
                estimated_loss_value=Decimal("18500.00"),
                insurance_claimed_amount=Decimal("18500.00"),
                insurance_settled_amount=Decimal("16500.00"),
                incident_description="Padlock cut on perimeter chain-link fence over weekend shutdown. Heavy generator towed off site.",
                investigation_findings="Police detective assigned. DNA and tire tracks lifted. Insurance claim processed and settlement approved.",
                resolution_action="written_off",
                write_off_authorized_by=user,
                write_off_date=timezone.now().date() - timezone.timedelta(days=2),
                write_off_notes="Authorized for write-off per Board resolution #2026-44 and net insurance recovery settlement voucher #IV-9912.",
                status="written_off",
            )

        self.stdout.write(f"[{tenant.name}] 11.2 Seeding complete (3 audits, 2 movements, 2 custody loans, 2 incident reports).")
