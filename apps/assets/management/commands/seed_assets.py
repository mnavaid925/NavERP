from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset, GLAccount
from apps.accounting.models import FiscalPeriod
from apps.assets.models import (
    AssetCalibrationRecord,
    AssetConditionAssessment,
    AssetFailureMode,
    AssetTelemetryReading,
    AssetAcquisitionReceipt,
    AssetAudit,
    AssetCapitalization,
    AssetCategory,
    AssetCriticalityAssessment,
    AssetCustodyLog,
    AssetDepreciationSchedule,
    AssetDowntimeLog,
    AssetEnergyReading,
    AssetIncidentReport,
    AssetMaintenanceLog,
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
    AssetModel,
    AssetMovementLog,
    AssetOeeRecord,
    AssetPerformanceScorecard,
    AssetRequisition,
    AssetRevaluation,
    AssetServiceContract,
    AssetSpecificationTemplate,
    AssetTag,
    AssetTransfer,
    CapitalizationPolicy,
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
            AssetCalibrationRecord.objects.all().delete()
            AssetFailureMode.objects.all().delete()
            AssetTelemetryReading.objects.all().delete()
            AssetConditionAssessment.objects.all().delete()
            AssetPerformanceScorecard.objects.all().delete()
            AssetEnergyReading.objects.all().delete()
            AssetOeeRecord.objects.all().delete()
            AssetDowntimeLog.objects.all().delete()
            AssetMaintenanceLog.objects.all().delete()
            AssetMaintenanceRequest.objects.all().delete()
            AssetMaintenanceSchedule.objects.all().delete()
            AssetServiceContract.objects.all().delete()
            AssetDepreciationSchedule.objects.all().delete()
            AssetRevaluation.objects.all().delete()
            AssetTransfer.objects.all().delete()
            CapitalizationPolicy.objects.all().delete()
            AssetSpecificationTemplate.objects.all().delete()
            AssetCriticalityAssessment.objects.all().delete()
            AssetModel.objects.all().delete()
            AssetCategory.objects.all().delete()
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
            self._seed_tenant_11_3(tenant)
            self._seed_tenant_11_4(tenant)
            self._seed_tenant_11_5(tenant)
            self._seed_tenant_11_6(tenant)
            self._seed_tenant_11_7(tenant)

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
                audit_type="wall_to_wall",
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
                audit_type="cycle_count",
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
                reconciliation_action="incident_initiated",
                reconciled_by=user,
                reconciled_at=timezone.now() - timezone.timedelta(days=6),
                status="reconciled",
                notes="Audit closed and discrepancy handed over to plant maintenance manager.",
            )

            AssetAudit.objects.create(
                tenant=tenant,
                title="IT Server Room Equipment Periodic Spot-Audit",
                audit_type="spot_check",
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
                movement_type="inter_facility_transfer",
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
                action_type="checkout",
                borrower=party1,
                borrower_name=party1.name if party1 else "John Doe",
                crib_attendant=user,
                purpose="Precision torque measurement on turbine casing assembly.",
                work_order_reference="MWO-2026-0814",
                project_reference="PRJ-AERO-TURB",
                checkout_date=timezone.now() - timezone.timedelta(days=2),
                expected_return_date=timezone.now().date() + timezone.timedelta(days=3),
                checkout_condition="excellent",
                condition_notes="Calibrated instrument verified within 0.05% tolerance band.",
                borrower_signature_acknowledged=True,
                status="active_loan",
                notes="Checked out under standard tool crib loan liability policy.",
            )

            AssetCustodyLog.objects.create(
                tenant=tenant,
                asset=asset4,
                action_type="checkout",
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

    def _seed_tenant_11_3(self, tenant):
        # Idempotency guard for 11.3
        if AssetCategory.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.3 Classification data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.3 Asset Classification & Categorization...")

        user = User.objects.filter(tenant=tenant).order_by("pk").first()
        vendor = (
            Party.objects.filter(tenant=tenant, roles__role__in=["vendor", "supplier"]).order_by("pk").first()
            or Party.objects.filter(tenant=tenant).order_by("pk").first()
        )
        assets = list(Asset.objects.filter(tenant=tenant).order_by("pk")[:5])

        with transaction.atomic():
            # 1. Taxonomy Root Categories
            cat_fac = AssetCategory.objects.create(
                tenant=tenant,
                code="FAC-PLANT",
                name="Plant & Infrastructure",
                category_type="facility",
                default_depreciation_method="straight_line",
                default_useful_life_months=240,
                default_maintenance_strategy="preventive_calendar",
                default_criticality="high",
                description="Central plant structures, building management systems, HVAC utilities, and physical infrastructure.",
                display_order=10,
                is_active=True,
            )

            cat_mach = AssetCategory.objects.create(
                tenant=tenant,
                code="MFG-MACH",
                name="Production Machinery & Machine Tools",
                category_type="machinery",
                default_depreciation_method="double_declining",
                default_useful_life_months=120,
                default_maintenance_strategy="predictive",
                default_criticality="critical",
                description="Heavy manufacturing CNC cells, stamping presses, automated assembly conveyors, and industrial tooling.",
                display_order=20,
                is_active=True,
            )

            cat_fleet = AssetCategory.objects.create(
                tenant=tenant,
                code="FLEET-MOBILE",
                name="Mobile Equipment & Fleet",
                category_type="vehicle",
                default_depreciation_method="declining_balance",
                default_useful_life_months=84,
                default_maintenance_strategy="preventive_meter",
                default_criticality="medium",
                description="Forklifts, electric pallet jacks, yard hostlers, and earthmoving machinery.",
                display_order=30,
                is_active=True,
            )

            # 2. Child Sub-Categories
            sub_chl = AssetCategory.objects.create(
                tenant=tenant,
                code="HVAC-CHL",
                name="Central Water Chillers",
                parent=cat_fac,
                category_type="facility",
                unspsc_code="40101701",
                unspsc_title="Chillers and chiller parts",
                default_depreciation_method="straight_line",
                default_useful_life_months=240,
                default_maintenance_strategy="condition_based",
                default_criticality="critical",
                description="Centrifugal and screw liquid chillers providing facility comfort and process cooling.",
                display_order=11,
                is_active=True,
            )

            sub_cnc = AssetCategory.objects.create(
                tenant=tenant,
                code="CNC-MILL",
                name="CNC Milling Centers",
                parent=cat_mach,
                category_type="machinery",
                unspsc_code="23101504",
                unspsc_title="Milling machines",
                default_depreciation_method="double_declining",
                default_useful_life_months=120,
                default_maintenance_strategy="predictive",
                default_criticality="critical",
                description="Multi-axis high-speed vertical and horizontal CNC milling centers.",
                display_order=21,
                is_active=True,
            )

            sub_pump = AssetCategory.objects.create(
                tenant=tenant,
                code="PUMP-CENT",
                name="Centrifugal Process Pumps",
                parent=cat_mach,
                category_type="machinery",
                unspsc_code="40151503",
                unspsc_title="Centrifugal pumps",
                default_depreciation_method="straight_line",
                default_useful_life_months=96,
                default_maintenance_strategy="condition_based",
                default_criticality="high",
                description="ANSI end-suction and horizontal split-case centrifugal water/slurry pumps.",
                display_order=22,
                is_active=True,
            )

            # 3. Equipment Models
            mod_excavator = AssetModel.objects.create(
                tenant=tenant,
                model_number="CAT-320GC",
                name="320 GC Hydraulic Excavator",
                category=cat_fleet,
                manufacturer=vendor,
                manufacturer_name_fallback="Caterpillar Inc.",
                description="Medium hydraulic excavator designed for bulk earthmoving, pipe laying, and construction site utility work.",
                standard_warranty_months=24,
                warranty_coverage_type="powertrain_only",
                expected_useful_life_months=84,
                default_meter_name="Operating Hours",
                default_meter_unit="h",
                estimated_replacement_cost=Decimal("210000.00"),
                model_status="active",
                technical_specifications="Net Power: 107 kW (143 hp)\nOperating Weight: 20,500 kg (45,200 lb)\nMax Digging Depth: 6,720 mm (22.0 ft)\nBucket Capacity: 1.0 m3",
                is_active=True,
            )

            mod_haas = AssetModel.objects.create(
                tenant=tenant,
                model_number="HAAS-VF4SS",
                name="VF-4SS Super-Speed Vertical Machining Center",
                category=sub_cnc,
                manufacturer=vendor,
                manufacturer_name_fallback="Haas Automation Inc.",
                description="High-performance 50\" x 20\" x 25\" vertical machining center with inline direct-drive spindle and 30+1 tool changer.",
                standard_warranty_months=12,
                warranty_coverage_type="full_parts_labor",
                expected_useful_life_months=120,
                default_meter_name="Spindle Run Hours",
                default_meter_unit="h",
                estimated_replacement_cost=Decimal("148500.00"),
                model_status="active",
                technical_specifications="Travels: 50\" x 20\" x 25\"\nSpindle: 12,000 RPM inline direct-drive, 30 hp vector drive\nTool Changer: 30+1 side-mount high-speed\nRapid Traverse: 1,400 ipm (35.6 m/min)",
                is_active=True,
            )

            mod_trane = AssetModel.objects.create(
                tenant=tenant,
                model_number="TRANE-CVHE500",
                name="CenTraVac 500-Ton Water-Cooled Centrifugal Chiller",
                category=sub_chl,
                manufacturer=vendor,
                manufacturer_name_fallback="Trane Commercial",
                description="Direct-drive multi-stage centrifugal liquid chiller for central plant cooling with next-generation low-GWP refrigerant.",
                standard_warranty_months=36,
                warranty_coverage_type="limited",
                expected_useful_life_months=240,
                default_meter_name="Compressor Run Hours",
                default_meter_unit="h",
                estimated_replacement_cost=Decimal("295000.00"),
                model_status="active",
                technical_specifications="Cooling Capacity: 500 Tons (1,758 kW)\nRefrigerant: R-1233zd(E) (ASHRAE A1, non-toxic, non-flammable)\nFull-load Efficiency: 0.520 kW/ton\nEvaporator Flow Rate: 1,200 GPM",
                is_active=True,
            )

            # 4. Specification Templates
            AssetSpecificationTemplate.objects.create(
                tenant=tenant,
                attribute_key="cooling_capacity_tons",
                display_name="Rated Cooling Capacity",
                category=sub_chl,
                data_type="number",
                unit_of_measure="ton",
                min_numeric_value=Decimal("50.000"),
                max_numeric_value=Decimal("2500.000"),
                is_required=True,
                is_filterable=True,
                display_order=10,
                help_text="Design refrigeration cooling tonnage at ARI standard conditions",
            )

            AssetSpecificationTemplate.objects.create(
                tenant=tenant,
                attribute_key="refrigerant_chemical_code",
                display_name="Refrigerant Type",
                category=sub_chl,
                data_type="select",
                dropdown_options="R-1233zd(E), R-514A, R-134a, R-513A, R-1234ze",
                default_value="R-1233zd(E)",
                is_required=True,
                is_filterable=True,
                display_order=20,
                help_text="Chemical safety and GWP classification of working charge",
            )

            AssetSpecificationTemplate.objects.create(
                tenant=tenant,
                attribute_key="spindle_max_rpm",
                display_name="Maximum Spindle Speed",
                category=sub_cnc,
                data_type="number",
                unit_of_measure="RPM",
                min_numeric_value=Decimal("1000.000"),
                max_numeric_value=Decimal("35000.000"),
                is_required=True,
                is_filterable=True,
                display_order=10,
                help_text="Top rotational speed of main cutting spindle",
            )

            AssetSpecificationTemplate.objects.create(
                tenant=tenant,
                attribute_key="operating_voltage_vac",
                display_name="Supply Voltage Specification",
                category=cat_mach,
                data_type="select",
                dropdown_options="208V 3-Phase, 240V 3-Phase, 480V 3-Phase, 600V 3-Phase",
                default_value="480V 3-Phase",
                is_required=True,
                is_filterable=True,
                display_order=5,
                help_text="Required 3-phase AC line supply voltage",
            )

            AssetSpecificationTemplate.objects.create(
                tenant=tenant,
                attribute_key="max_dig_depth_mm",
                display_name="Maximum Digging Depth",
                model=mod_excavator,
                data_type="number",
                unit_of_measure="mm",
                min_numeric_value=Decimal("4000.000"),
                max_numeric_value=Decimal("12000.000"),
                is_required=False,
                is_filterable=True,
                display_order=15,
                help_text="Maximum vertical digging depth at standard boom reach",
            )

            # 5. Criticality Consequence Assessments
            if assets:
                asset_primary = assets[0]
                asmt1 = AssetCriticalityAssessment.objects.create(
                    tenant=tenant,
                    title=f"Annual RCM Criticality Assessment - {asset_primary.name}",
                    asset=asset_primary,
                    assessor=vendor,
                    assessment_date=timezone.now().date() - timezone.timedelta(days=15),
                    safety_impact=4,
                    environmental_impact=2,
                    operational_downtime_impact=5,
                    financial_impact=4,
                    regulatory_compliance_impact=3,
                    is_single_point_of_failure=True,
                    recommended_strategy="rcm_predictive",
                    review_cycle_months=6,
                    next_assessment_due=timezone.now().date() + timezone.timedelta(days=165),
                    findings_and_mitigation="Mission-critical production asset. Failure halts main assembly line. Single point of failure; vibration telemetry and daily acoustic thermography mandated.",
                    assessment_status="approved",
                    approved_by=user,
                    approved_at=timezone.now() - timezone.timedelta(days=12),
                )
                asset_primary.criticality = "critical"
                asset_primary.save(update_fields=["criticality"])

                if len(assets) > 1:
                    asset_secondary = assets[1]
                    AssetCriticalityAssessment.objects.create(
                        tenant=tenant,
                        title=f"Cyclical Risk Evaluation - {asset_secondary.name}",
                        asset=asset_secondary,
                        assessor=vendor,
                        assessment_date=timezone.now().date() - timezone.timedelta(days=5),
                        safety_impact=2,
                        environmental_impact=1,
                        operational_downtime_impact=2,
                        financial_impact=2,
                        regulatory_compliance_impact=1,
                        is_single_point_of_failure=False,
                        recommended_strategy="standard_pm",
                        review_cycle_months=12,
                        next_assessment_due=timezone.now().date() + timezone.timedelta(days=360),
                        findings_and_mitigation="Support equipment with hot standby available in yard staging. Routine quarterly PM sufficient.",
                        assessment_status="reviewed",
                    )

        self.stdout.write(f"[{tenant.name}] 11.3 Seeding complete (6 categories, 3 models, 5 spec templates, 2 risk assessments).")


    def _seed_tenant_11_4(self, tenant):
        """Seed demo data for Sub-module 11.4: Depreciation & Financial Management."""
        if AssetDepreciationSchedule.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.4 Depreciation & Financial data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.4 Depreciation & Financial Management...")

        user = User.objects.filter(tenant=tenant).first()
        org_units = list(OrgUnit.objects.filter(tenant=tenant))
        org_unit_src = org_units[0] if org_units else None
        org_unit_dst = org_units[1] if len(org_units) > 1 else org_unit_src
        locations = list(Location.objects.filter(tenant=tenant))
        loc_src = locations[0] if locations else None
        loc_dst = locations[1] if len(locations) > 1 else loc_src
        parties = list(Party.objects.filter(tenant=tenant))
        custodian_src = parties[0] if parties else None
        custodian_dst = parties[1] if len(parties) > 1 else custodian_src
        vendor = Party.objects.filter(tenant=tenant, roles__role__in=["vendor", "supplier"]).first() or custodian_src
        categories = list(AssetCategory.objects.filter(tenant=tenant))
        cat_machinery = next((c for c in categories if c.category_type == "machinery"), categories[0] if categories else None)

        fixed_assets = list(FixedAsset.objects.filter(tenant=tenant))
        operational_assets = list(Asset.objects.filter(tenant=tenant))
        fa_primary = fixed_assets[0] if fixed_assets else None
        oa_primary = operational_assets[0] if operational_assets else None
        fiscal_period = FiscalPeriod.objects.filter(tenant=tenant).first()

        expense_acc = GLAccount.objects.filter(tenant=tenant, account_type="expense").first() or GLAccount.objects.filter(tenant=tenant).first()
        accum_acc = GLAccount.objects.filter(tenant=tenant, account_type="asset").last() or GLAccount.objects.filter(tenant=tenant).last()
        loss_acc = GLAccount.objects.filter(tenant=tenant, account_type="expense").last() or expense_acc
        surplus_acc = GLAccount.objects.filter(tenant=tenant, account_type="equity").first() or accum_acc
        cip_acc = GLAccount.objects.filter(tenant=tenant, account_type="asset").first() or accum_acc

        with transaction.atomic():
            # 1. Capitalization Policies
            pol1 = CapitalizationPolicy.objects.create(
                tenant=tenant,
                name="Statutory IRS De Minimis Safe Harbor (CapEx Floor)",
                policy_scope="tax_book_safe_harbor",
                minimum_cost_threshold=Decimal("2500.00"),
                minimum_useful_life_months=12,
                default_classification="expense_immediately",
                de_minimis_safe_harbor=True,
                applicable_gaap_standard="US GAAP / IRS Reg. 1.263(a)-1(f)",
                default_cip_account=cip_acc,
                default_expense_account=expense_acc,
                policy_notes="All tangible property items under $2,500.00 are immediately expensed under de minimis safe harbor election.",
                effective_from=timezone.now().date() - timezone.timedelta(days=365),
                is_active=True,
            )

            pol2 = CapitalizationPolicy.objects.create(
                tenant=tenant,
                name="Heavy Machinery & Plant Infrastructure Policy",
                policy_scope="category_override",
                category=cat_machinery,
                minimum_cost_threshold=Decimal("5000.00"),
                minimum_useful_life_months=24,
                default_classification="capitalize",
                de_minimis_safe_harbor=False,
                applicable_gaap_standard="IFRS IAS 16 / US GAAP ASC 360",
                default_cip_account=cip_acc,
                default_expense_account=expense_acc,
                policy_notes="Major production plant and CNC cells capitalized over 24-month minimum economic life.",
                effective_from=timezone.now().date() - timezone.timedelta(days=180),
                is_active=True,
            )

            if fa_primary:
                # 2. Asset Depreciation Schedules
                sched1 = AssetDepreciationSchedule.objects.create(
                    tenant=tenant,
                    fixed_asset=fa_primary,
                    operational_asset=oa_primary,
                    fiscal_period=fiscal_period,
                    fiscal_year=2026,
                    period_number=1,
                    period_frequency="monthly",
                    schedule_date=timezone.now().date() - timezone.timedelta(days=30),
                    depreciation_method="straight_line",
                    starting_book_value=fa_primary.acquisition_cost or Decimal("125000.00"),
                    depreciation_amount=Decimal("2083.33"),
                    accumulated_depreciation_after=Decimal("2083.33"),
                    ending_book_value=(fa_primary.acquisition_cost or Decimal("125000.00")) - Decimal("2083.33"),
                    expense_account=expense_acc,
                    accumulated_account=accum_acc,
                    cost_center=org_unit_src,
                    status="posted",
                    posted_at=timezone.now() - timezone.timedelta(days=28),
                    posted_by=user,
                    notes="Monthly straight-line depreciation run closed and posted to general ledger.",
                )

                sched2 = AssetDepreciationSchedule.objects.create(
                    tenant=tenant,
                    fixed_asset=fa_primary,
                    operational_asset=oa_primary,
                    fiscal_period=fiscal_period,
                    fiscal_year=2026,
                    period_number=2,
                    period_frequency="monthly",
                    schedule_date=timezone.now().date(),
                    depreciation_method="straight_line",
                    starting_book_value=sched1.ending_book_value,
                    depreciation_amount=Decimal("2083.33"),
                    accumulated_depreciation_after=Decimal("4166.66"),
                    ending_book_value=sched1.ending_book_value - Decimal("2083.33"),
                    expense_account=expense_acc,
                    accumulated_account=accum_acc,
                    cost_center=org_unit_src,
                    status="calculated",
                    notes="Current period draft calculation pending month-end closing approval.",
                )

                # 3. Asset Revaluations
                rev1 = AssetRevaluation.objects.create(
                    tenant=tenant,
                    title=f"Annual Mid-Life Fair Value Revaluation - {fa_primary.name}",
                    fixed_asset=fa_primary,
                    operational_asset=oa_primary,
                    event_type="revaluation_up",
                    valuation_method="independent_appraisal",
                    valuation_date=timezone.now().date() - timezone.timedelta(days=10),
                    appraiser=vendor,
                    appraiser_name_fallback="Accredited Industrial Appraisals Inc.",
                    historical_cost=fa_primary.acquisition_cost or Decimal("125000.00"),
                    accumulated_depreciation_before=Decimal("2083.33"),
                    carrying_value_before=(fa_primary.acquisition_cost or Decimal("125000.00")) - Decimal("2083.33"),
                    new_fair_market_value=(fa_primary.acquisition_cost or Decimal("125000.00")) + Decimal("7500.00"),
                    revaluation_adjustment=Decimal("9583.33"),
                    new_salvage_value=Decimal("5000.00"),
                    remaining_useful_life_months=58,
                    revaluation_surplus_account=surplus_acc,
                    reason_and_methodology="Third-party market appraisal certified upward replacement value step-up due to tight supply chain equipment premiums.",
                    status="approved",
                    approved_by=user,
                    approved_at=timezone.now() - timezone.timedelta(days=8),
                )

                # 4. Asset Transfers
                xfr1 = AssetTransfer.objects.create(
                    tenant=tenant,
                    title=f"Inter-Facility Production Line Reallocation - {fa_primary.name}",
                    fixed_asset=fa_primary,
                    operational_asset=oa_primary,
                    transfer_type="cost_center",
                    transfer_date=timezone.now().date() - timezone.timedelta(days=5),
                    source_department=org_unit_src,
                    source_location=loc_src,
                    source_custodian=custodian_src,
                    source_expense_account=expense_acc,
                    destination_department=org_unit_dst,
                    destination_location=loc_dst,
                    destination_custodian=custodian_dst,
                    destination_expense_account=expense_acc,
                    carrying_value_at_transfer=sched1.ending_book_value,
                    transportation_cost=Decimal("1250.00"),
                    reason="Operational transfer to balance production capacity across plant work centers.",
                    status="completed",
                    transferred_by=user,
                    received_by=user,
                    completed_at=timezone.now() - timezone.timedelta(days=4),
                )

        self.stdout.write(f"[{tenant.name}] 11.4 Seeding complete (2 policies, 2 schedules, 1 revaluation, 1 transfer).")

    def _seed_tenant_11_5(self, tenant):
        # Idempotency guard for 11.5
        if AssetMaintenanceRequest.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.5 Maintenance data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.5 Maintenance & Repair Management...")

        user = User.objects.filter(tenant=tenant).first()
        currency = Currency.objects.filter(is_active=True).first()
        vendor = Party.objects.filter(tenant=tenant, roles__role__in=["vendor", "supplier"]).first() or Party.objects.filter(tenant=tenant).first()
        fa_primary = FixedAsset.objects.filter(tenant=tenant).first()
        oa_primary = Asset.objects.filter(tenant=tenant).first()
        org_unit = OrgUnit.objects.filter(tenant=tenant).first()
        expense_acc = GLAccount.objects.filter(tenant=tenant, account_type="expense").first() or GLAccount.objects.filter(tenant=tenant).first()
        category = AssetCategory.objects.filter(tenant=tenant).first()

        with transaction.atomic():
            # 1. Service Contracts
            svc1 = AssetServiceContract.objects.create(
                tenant=tenant,
                contract_number="AMC-2026-CAT-01",
                title=f"Comprehensive Hydraulic & Mechanical SLA - {fa_primary.name if fa_primary else 'Plant Equipment'}",
                vendor=vendor,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                contract_type="comprehensive_amc",
                start_date=timezone.now().date() - timezone.timedelta(days=60),
                end_date=timezone.now().date() + timezone.timedelta(days=305),
                contract_value=Decimal("18500.00"),
                currency=currency,
                billing_frequency="annual",
                sla_response_hours=4,
                sla_resolution_hours=24,
                pm_visits_included=4,
                pm_visits_completed=1,
                coverage_terms="Comprehensive parts and labor maintenance agreement including routine quarterly inspections and 24/7 emergency breakdown coverage with 4-hour on-site response guarantee.",
                auto_renew=True,
                contact_person="Marcus Vance",
                contact_phone="+1-555-882-9901",
                contact_email="service@acmevendors.com",
                status="active",
                notes="Primary plant floor equipment service agreement. Priority hotline SLA active.",
            )

            svc2 = AssetServiceContract.objects.create(
                tenant=tenant,
                contract_number="OEM-EXT-2026-09",
                title="Critical Spindle OEM Extended Warranty Agreement",
                vendor=vendor,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                contract_type="oem_warranty_extension",
                start_date=timezone.now().date() - timezone.timedelta(days=15),
                end_date=timezone.now().date() + timezone.timedelta(days=350),
                contract_value=Decimal("6200.00"),
                currency=currency,
                billing_frequency="annual",
                sla_response_hours=2,
                sla_resolution_hours=12,
                pm_visits_included=2,
                pm_visits_completed=0,
                coverage_terms="Factory-certified spindle cartridge replacement guarantee covering manufacturing defects, thermal runout, and high-frequency sensor errors.",
                auto_renew=False,
                contact_person="Helena Cross",
                contact_phone="+1-555-443-1200",
                contact_email="warranty@haasoem.com",
                status="active",
            )

            # 2. PM Schedules
            sched1 = AssetMaintenanceSchedule.objects.create(
                tenant=tenant,
                name=f"Monthly Hydraulic Filter & Fluid Check - {fa_primary.name if fa_primary else 'Equipment'}",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=category,
                schedule_type="time_based",
                frequency_interval=30,
                frequency_unit="days",
                lead_time_days=7,
                last_service_date=timezone.now().date() - timezone.timedelta(days=25),
                next_due_date=timezone.now().date() + timezone.timedelta(days=5),
                assigned_technician=user,
                preferred_vendor=vendor,
                service_contract=svc1,
                service_checklist="1. Inspect fluid reservoir levels and color.\n2. Measure operating pressure at idle and load.\n3. Replace 10-micron return line cartridge filter.\n4. Check fittings and manifold seals for weepage.",
                is_mandatory=True,
                is_active=True,
                status="active",
                notes="Critical preventive maintenance procedure. Do not bypass filter change interval.",
            )

            sched2 = AssetMaintenanceSchedule.objects.create(
                tenant=tenant,
                name="Quarterly High-Speed Spindle Bearing & Thermal Check",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=category,
                schedule_type="time_based",
                frequency_interval=90,
                frequency_unit="days",
                lead_time_days=14,
                last_service_date=timezone.now().date() - timezone.timedelta(days=100),
                next_due_date=timezone.now().date() - timezone.timedelta(days=10),
                assigned_technician=user,
                preferred_vendor=vendor,
                service_contract=svc1,
                service_checklist="1. Clean and inspect spindle taper.\n2. Perform dynamic vibration baseline check.\n3. Verify chiller coolant circulation and temperature delta.\n4. Check tool clamp pneumatic retention force.",
                is_mandatory=True,
                is_active=True,
                status="overdue",
                notes="Overdue for statutory quarterly safety compliance inspection.",
            )

            # 3. Maintenance Requests
            req1 = AssetMaintenanceRequest.objects.create(
                tenant=tenant,
                title="Main Hydraulic Pump Seal Leakage - Pressure Drop",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                requester=user,
                department=org_unit,
                request_type="breakdown_repair",
                urgency="critical",
                is_breakdown=True,
                downtime_started_at=timezone.now() - timezone.timedelta(hours=6),
                symptom_description="Hydraulic pump pressure dropped from 210 bar to 85 bar during roughing pass. Visible fluid pooling under main valve block. Production stopped.",
                triage_notes="Emergency repair authorized. Seal kit pulled from central stores. Technician dispatched immediately.",
                assigned_technician=user,
                assigned_vendor=vendor,
                service_contract=svc1,
                status="in_progress",
            )

            req2 = AssetMaintenanceRequest.objects.create(
                tenant=tenant,
                title="High-Speed Spindle Vibration Anomaly During Finishing",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                requester=user,
                department=org_unit,
                request_type="preventive_inspection",
                urgency="high",
                is_breakdown=False,
                symptom_description="Audible high-pitch hum at 10,000+ RPM. Surface finish showing minor chatter marks on aerospace titanium brackets.",
                triage_notes="Scheduled for vibration diagnostic inspection during end-of-shift window.",
                assigned_technician=user,
                status="assigned",
            )

            req3 = AssetMaintenanceRequest.objects.create(
                tenant=tenant,
                title="Coolant Tank Filtration Screen Cleaning & Pump Flush",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                requester=user,
                department=org_unit,
                request_type="facility_upkeep",
                urgency="medium",
                is_breakdown=False,
                symptom_description="Sludge accumulation in bottom chip pan. Coolant flow rate reduced by 30%.",
                status="resolved",
                resolution_summary="Reservoir drained, chip screen cleared, fresh semi-synthetic coolant filled at 8% refractometer concentration. Flow rate restored.",
                resolved_by=user,
                resolved_at=timezone.now() - timezone.timedelta(days=3),
            )

            # 4. Maintenance Logs
            log1 = AssetMaintenanceLog.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                maintenance_request=req3,
                maintenance_schedule=sched1,
                service_contract=svc1,
                service_date=timezone.now().date() - timezone.timedelta(days=3),
                completion_date=timezone.now() - timezone.timedelta(days=3, hours=-2),
                maintenance_type="preventive_service",
                failure_code="normal_wear",
                downtime_hours=Decimal("2.50"),
                meter_reading=Decimal("1420.50"),
                lead_technician=user,
                labor_hours=Decimal("2.50"),
                labor_cost=Decimal("187.50"),
                parts_consumed_summary="2x Coolant Filter Cartridge #CF-100\n1x Sump Gasket #SG-44\n20L Cutting Fluid Concentrate #CF-PRO",
                parts_cost=Decimal("345.00"),
                vendor_invoice_cost=Decimal("0.00"),
                expense_account=expense_acc,
                root_cause_analysis="Routine operational coolant bio-degradation and fine particulate loading on intake screens.",
                action_taken="Full reservoir suction cleanout, flushed return lines, calibrated coolant refractometer, ran 30-minute circulation test without pressure drop.",
                status="approved",
                approved_by=user,
                approved_at=timezone.now() - timezone.timedelta(days=2),
            )

            log2 = AssetMaintenanceLog.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                service_date=timezone.now().date() - timezone.timedelta(days=15),
                completion_date=timezone.now() - timezone.timedelta(days=15, hours=-4),
                maintenance_type="corrective_repair",
                failure_code="hydraulic_leak",
                downtime_hours=Decimal("4.00"),
                meter_reading=Decimal("1380.00"),
                lead_technician=user,
                service_vendor=vendor,
                labor_hours=Decimal("4.00"),
                labor_cost=Decimal("300.00"),
                parts_consumed_summary="1x High-Pressure Hydraulic Hose 3/8-inch #HH-38-02\n2x JIC Steel Swivel Fittings",
                parts_cost=Decimal("180.00"),
                vendor_invoice_cost=Decimal("250.00"),
                expense_account=expense_acc,
                root_cause_analysis="Hose outer jacket rubbed against cable carrier tray causing premature fatigue wear.",
                action_taken="Replaced failed hose segment, installed spiral protective wrap, rerouted clearance away from sheet metal lip, leak check verified at 250 bar.",
                status="posted",
                approved_by=user,
                approved_at=timezone.now() - timezone.timedelta(days=14),
            )



        self.stdout.write(f"[{tenant.name}] 11.5 Seeding complete (2 contracts, 2 schedules, 3 requests, 2 logs).")




    def _seed_tenant_11_6(self, tenant):
        if AssetDowntimeLog.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.6 Performance & Utilization data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.6 Asset Performance & Utilization...")
        user = User.objects.filter(tenant=tenant).first()
        fa_primary = FixedAsset.objects.filter(tenant=tenant).first()
        oa_primary = Asset.objects.filter(tenant=tenant).first()
        dept = OrgUnit.objects.filter(tenant=tenant).first()

        with transaction.atomic():
            down1 = AssetDowntimeLog.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                department=dept,
                downtime_category="unplanned_breakdown",
                impact_level="full_shutdown",
                root_cause_code="ISO-14224 MECH-VALVE-SEIZE",
                failure_description="Main hydraulic proportional valve seized during spindle traverse, causing emergency halt alarm E-404.",
                started_at=timezone.now() - timezone.timedelta(days=5, hours=4),
                ended_at=timezone.now() - timezone.timedelta(days=5, hours=1, minutes=30),
                hourly_cost_rate=Decimal("350.00"),
                is_mtbf_failure=True,
                logged_by=user,
                status="resolved",
                resolution_notes="Disassembled proportional valve, flushed contaminated spool channel, replaced seals, test run completed.",
            )

            down2 = AssetDowntimeLog.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                department=dept,
                downtime_category="setup_changeover",
                impact_level="cell_idle",
                root_cause_code="SETUP-TOOL-CALIB",
                failure_description="Scheduled fixture retooling and optical tool setter calibration for high-tolerance batch run.",
                started_at=timezone.now() - timezone.timedelta(days=2, hours=3),
                ended_at=timezone.now() - timezone.timedelta(days=2, hours=2, minutes=15),
                hourly_cost_rate=Decimal("200.00"),
                is_mtbf_failure=False,
                logged_by=user,
                status="resolved",
                resolution_notes="New collets mounted, runout checked <0.003mm, first-off sample verified on CMM.",
            )

            down3 = AssetDowntimeLog.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                department=dept,
                downtime_category="utility_outage",
                impact_level="minor_stop",
                root_cause_code="UTIL-VOLT-SAG",
                failure_description="Main factory sub-station voltage sag triggered auxiliary drive under-voltage protection.",
                started_at=timezone.now() - timezone.timedelta(hours=2),
                ended_at=None,
                hourly_cost_rate=Decimal("350.00"),
                is_mtbf_failure=False,
                logged_by=user,
                status="active",
                resolution_notes="",
            )

            oee1 = AssetOeeRecord.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                record_date=timezone.now().date() - timezone.timedelta(days=2),
                shift_name="Shift 1 (Day)",
                planned_production_time_minutes=Decimal("480.00"),
                operating_time_minutes=Decimal("420.00"),
                ideal_cycle_time_seconds=Decimal("12.00"),
                total_units_produced=1950,
                good_units_produced=1910,
                defect_units_count=25,
                rework_units_count=15,
                breakdown_loss_minutes=Decimal("30.00"),
                setup_loss_minutes=Decimal("15.00"),
                small_stops_loss_minutes=Decimal("10.00"),
                reduced_speed_loss_minutes=Decimal("5.00"),
                defect_loss_minutes=Decimal("6.00"),
                startup_loss_minutes=Decimal("4.00"),
                status="finalized",
                notes="Excellent throughput and high tool life throughout morning machining run.",
                recorded_by=user,
            )

            oee2 = AssetOeeRecord.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                record_date=timezone.now().date() - timezone.timedelta(days=1),
                shift_name="Shift 2 (Evening)",
                planned_production_time_minutes=Decimal("480.00"),
                operating_time_minutes=Decimal("360.00"),
                ideal_cycle_time_seconds=Decimal("15.00"),
                total_units_produced=1300,
                good_units_produced=1220,
                defect_units_count=55,
                rework_units_count=25,
                breakdown_loss_minutes=Decimal("60.00"),
                setup_loss_minutes=Decimal("30.00"),
                small_stops_loss_minutes=Decimal("15.00"),
                reduced_speed_loss_minutes=Decimal("10.00"),
                defect_loss_minutes=Decimal("14.00"),
                startup_loss_minutes=Decimal("8.00"),
                status="finalized",
                notes="Minor chip jamming in conveyor caused brief idling; scrap elevated during roughing pass.",
                recorded_by=user,
            )

            energy1 = AssetEnergyReading.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                reading_timestamp=timezone.now() - timezone.timedelta(days=3),
                utility_type="electricity",
                meter_serial_number="MTR-ELEC-CELL-01",
                consumption_value=Decimal("1420.5000"),
                unit_of_measure="kWh",
                peak_demand_kw=Decimal("85.50"),
                power_factor=Decimal("0.940"),
                operating_hours=Decimal("48.00"),
                units_produced=4500,
                emission_factor=Decimal("0.4500"),
                ghg_scope="scope_2",
                cost_per_unit=Decimal("0.1250"),
                status="validated",
                notes="Peak demand well within sub-station threshold. Power factor healthy at 0.94.",
                recorded_by=user,
            )

            energy2 = AssetEnergyReading.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                reading_timestamp=timezone.now() - timezone.timedelta(days=1),
                utility_type="electricity",
                meter_serial_number="MTR-ELEC-CELL-01",
                consumption_value=Decimal("1580.0000"),
                unit_of_measure="kWh",
                peak_demand_kw=Decimal("94.20"),
                power_factor=Decimal("0.915"),
                operating_hours=Decimal("48.00"),
                units_produced=4200,
                emission_factor=Decimal("0.4500"),
                ghg_scope="scope_2",
                cost_per_unit=Decimal("0.1250"),
                status="validated",
                notes="Heavy roughing cycle increased spindle motor draw; monitored power factor harmonic filter.",
                recorded_by=user,
            )

            energy3 = AssetEnergyReading.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                reading_timestamp=timezone.now() - timezone.timedelta(days=2),
                utility_type="natural_gas",
                meter_serial_number="MTR-GAS-BLDG-B",
                consumption_value=Decimal("380.0000"),
                unit_of_measure="m3",
                operating_hours=Decimal("48.00"),
                emission_factor=Decimal("1.9500"),
                ghg_scope="scope_1",
                cost_per_unit=Decimal("0.8500"),
                status="validated",
                notes="Heat treatment tempering furnace gas flow telemetry.",
                recorded_by=user,
            )

            sc1 = AssetPerformanceScorecard.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                department=dept,
                period_type="monthly",
                period_start=(timezone.now().date() - timezone.timedelta(days=35)).replace(day=1),
                period_end=timezone.now().date().replace(day=1) - timezone.timedelta(days=1),
                total_calendar_hours=Decimal("720.00"),
                planned_operating_hours=Decimal("480.00"),
                actual_operating_hours=Decimal("415.00"),
                unplanned_downtime_hours=Decimal("22.50"),
                planned_downtime_hours=Decimal("25.00"),
                failure_event_count=2,
                average_oee_percentage=Decimal("79.50"),
                total_energy_consumption_kwh=Decimal("18450.00"),
                total_carbon_emissions_kg=Decimal("8302.50"),
                total_downtime_cost=Decimal("7875.00"),
                peer_category_ranking=1,
                status="published",
                executive_summary="Solid operational performance throughout prior month. Capacity utilization exceeded 86%. Spindle availability remained above 94% despite hydraulic valve incident. Recommended continuing monthly PM filter swaps.",
                evaluated_by=user,
            )

            sc2 = AssetPerformanceScorecard.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                department=dept,
                period_type="monthly",
                period_start=timezone.now().date().replace(day=1),
                period_end=timezone.now().date(),
                total_calendar_hours=Decimal("240.00"),
                planned_operating_hours=Decimal("160.00"),
                actual_operating_hours=Decimal("142.00"),
                unplanned_downtime_hours=Decimal("6.00"),
                planned_downtime_hours=Decimal("8.00"),
                failure_event_count=1,
                average_oee_percentage=Decimal("83.20"),
                total_energy_consumption_kwh=Decimal("6120.00"),
                total_carbon_emissions_kg=Decimal("2754.00"),
                total_downtime_cost=Decimal("2100.00"),
                peer_category_ranking=1,
                status="draft",
                executive_summary="Mid-month performance tracking sound with OEE averaging 83%.",
                evaluated_by=user,
            )

        self.stdout.write(f"[{tenant.name}] 11.6 Seeding complete (3 downtimes, 2 OEE records, 3 energy readings, 2 scorecards).")


    def _seed_tenant_11_7(self, tenant):
        # Idempotency guard for 11.7
        if AssetConditionAssessment.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.7 Reliability & Condition data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.7 Asset Reliability & Condition Monitoring...")

        user = User.objects.filter(tenant=tenant).first()
        fa_primary = FixedAsset.objects.filter(tenant=tenant).first()
        fa_secondary = FixedAsset.objects.filter(tenant=tenant).last()
        oa_primary = Asset.objects.filter(tenant=tenant).first()
        cat = AssetCategory.objects.filter(tenant=tenant).first()
        vendor = Party.objects.filter(tenant=tenant, roles__role="vendor").first() or Party.objects.filter(tenant=tenant).first()
        sched = AssetMaintenanceSchedule.objects.filter(tenant=tenant).first()

        with transaction.atomic():
            # 1. Condition Assessments
            AssetConditionAssessment.objects.create(
                tenant=tenant,
                title="Baseline Ultrasonic Thickness & Shell Integrity Survey",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=cat,
                inspector=user,
                external_inspector=vendor,
                assessment_date=timezone.now().date() - timezone.timedelta(days=10),
                assessment_type="ndt_ultrasonic",
                condition_grade="grade_2_good",
                health_score=88,
                operating_status="normal_operation",
                checklist_summary="1. Ultrasonic wall thickness gauge check at 8 quadrants\n2. Paint adhesion test\n3. Anchor bolt torque audit",
                findings="Nominal wall thickness measured at 12.4mm (spec: 12.7mm). Zero deep corrosion pitting detected. Flange gasket surface smooth.",
                recommendations="Continue routine 12-month ultrasonic surveys. Next inspection scheduled for Q4.",
                followup_required=False,
                status="completed",
            )

            AssetConditionAssessment.objects.create(
                tenant=tenant,
                title="Infrared Thermography Scan on Main Transformer & Bushings",
                fixed_asset=fa_secondary,
                operational_asset=oa_primary,
                asset_category=cat,
                inspector=user,
                external_inspector=vendor,
                assessment_date=timezone.now().date() - timezone.timedelta(days=5),
                assessment_type="ndt_thermography",
                condition_grade="grade_4_poor",
                health_score=42,
                operating_status="operational_with_defects",
                checklist_summary="1. Phase A, B, C primary bushing thermal gradients\n2. Tap changer radiator fin delta-T\n3. Neutral grounding bus connection",
                findings="Hotspot detected on Phase B high-voltage termination: 84.5°C under 60% rated load (ambient 24°C). Delta-T of 38°C indicates high-resistance contact.",
                recommendations="Immediate de-energization and retorque/refacing of Phase B terminal lug. Avoid operating above 70% load until serviced.",
                followup_required=True,
                status="reviewed",
                reviewed_by=user,
                reviewed_at=timezone.now() - timezone.timedelta(days=4),
            )

            AssetConditionAssessment.objects.create(
                tenant=tenant,
                title="Monthly Vibration Screening Pen Check - Hydraulic Drive",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=cat,
                inspector=user,
                assessment_date=timezone.now().date() - timezone.timedelta(days=2),
                assessment_type="ndt_vibration_pen",
                condition_grade="grade_1_excellent",
                health_score=96,
                operating_status="normal_operation",
                checklist_summary="1. Motor drive-end horizontal RMS velocity\n2. Motor non-drive end axial velocity\n3. Pump casing vertical acceleration",
                findings="Overall velocity RMS measured at 1.1 mm/s across all bearing points. ISO 10816 Class II Zone A (As New). Zero high-frequency bearing distress.",
                recommendations="Equipment in pristine operating condition. Standard preventive maintenance schedule remains appropriate.",
                followup_required=False,
                status="completed",
            )

            # 2. Telemetry Readings
            AssetTelemetryReading.objects.create(
                tenant=tenant,
                sensor_identifier="VIB-PUMP-01-AXIAL",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                recorded_by=user,
                recorded_at=timezone.now() - timezone.timedelta(hours=6),
                source="iot_sensor",
                metric_type="vibration_velocity_rms",
                metric_unit="mm_per_s",
                reading_value=Decimal("2.4500"),
                baseline_value=Decimal("2.2000"),
                threshold_status="normal",
                is_anomaly=False,
                alert_notes="Steady state running velocity within normal baseline ISO limits.",
            )

            AssetTelemetryReading.objects.create(
                tenant=tenant,
                sensor_identifier="RTD-MOTOR-DE-02",
                fixed_asset=fa_secondary,
                operational_asset=oa_primary,
                recorded_by=user,
                recorded_at=timezone.now() - timezone.timedelta(hours=4),
                source="scada_historian",
                metric_type="bearing_temperature",
                metric_unit="celsius",
                reading_value=Decimal("78.5000"),
                baseline_value=Decimal("60.0000"),
                threshold_status="warning",
                is_anomaly=False,
                alert_notes="Bearing operating temperature 30.8% above baseline limit. Lubrication re-greasing recommended.",
            )

            AssetTelemetryReading.objects.create(
                tenant=tenant,
                sensor_identifier="USOUND-VALVE-04",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                recorded_by=user,
                recorded_at=timezone.now() - timezone.timedelta(hours=2),
                source="iot_sensor",
                metric_type="acoustic_ultrasound",
                metric_unit="decibel_uv",
                reading_value=Decimal("48.2000"),
                baseline_value=Decimal("25.0000"),
                threshold_status="anomaly_detected",
                is_anomaly=True,
                anomaly_confidence=Decimal("92.50"),
                alert_notes="High-frequency acoustic signature indicates internal seat bypass turbulence / passing valve cavitation.",
            )

            AssetTelemetryReading.objects.create(
                tenant=tenant,
                sensor_identifier="PT-LINE-DISCHARGE",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                recorded_by=user,
                recorded_at=timezone.now() - timezone.timedelta(minutes=30),
                source="handheld_tester",
                metric_type="operating_pressure",
                metric_unit="bar",
                reading_value=Decimal("120.0000"),
                baseline_value=Decimal("120.0000"),
                threshold_status="normal",
                is_anomaly=False,
                alert_notes="Direct manifold gauge verification confirms calibrated working pressure.",
            )

            # 3. Failure Mode & Effects Analysis (FMEA & RCM)
            AssetFailureMode.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=cat,
                component_subsystem="Centrifugal Pump Impeller & Volute Casing",
                function_description="Deliver 450 gpm cooling water at 6.5 bar differential head continuously during plant operations.",
                functional_failure="Total discharge flow drops below 350 gpm or erratic discharge pressure pulsing.",
                failure_mode="Cavitation Pitting & Blade Erosion",
                failure_cause="Low suction head (NPSH margin inadequate), entrained air bubbles, or suction strainer blinding.",
                failure_effect="Loss of heat exchanger cooling capacity, elevated casing vibration, and eventual impeller destruction requiring emergency line shutdown.",
                severity_score=7,
                occurrence_score=5,
                detection_score=8,
                rcm_strategy="condition_based",
                strategy_rationale="Continuous acoustic ultrasound sensor and vibration monitoring detect inception of cavitation long before structural impeller wear.",
                mitigation_task="Monthly acoustic ultrasound check on suction nozzle; automated trip if ultrasound exceeds 38 dBµV for > 5 minutes.",
                linked_maintenance_schedule=sched,
                assessed_by=user,
                status="active",
            )

            AssetFailureMode.objects.create(
                tenant=tenant,
                fixed_asset=fa_secondary,
                operational_asset=oa_primary,
                asset_category=cat,
                component_subsystem="Hydraulic Cylinder Rod Packing & Wiper Seal",
                function_description="Retain 210 bar hydraulic oil inside cylinder bore while cycling linear motion at 0.4 m/s.",
                functional_failure="External hydraulic fluid weeping along cylinder chrome rod exceeding 5 drops/min.",
                failure_mode="Elastomer Thermal Hardening & Extrusion",
                failure_cause="High hydraulic fluid operating temperature (>80°C) and particulate contamination abrading primary polyurethane lip.",
                failure_effect="Fluid loss, slipping position hold, slip hazard around machinery, and environmental cleanup required.",
                severity_score=5,
                occurrence_score=4,
                detection_score=8,
                rcm_strategy="time_based_pm",
                strategy_rationale="Seal elastomer exhibits deterministic wear out curve past 8,000 operating hours in high-heat service.",
                mitigation_task="Scheduled annual rod seal kit replacement during planned plant turnaround.",
                linked_maintenance_schedule=sched,
                assessed_by=user,
                status="active",
            )

            AssetFailureMode.objects.create(
                tenant=tenant,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=cat,
                component_subsystem="Electric Drive Motor Stator Windings",
                function_description="Convert 480V 3-phase electrical energy into 150 kW shaft mechanical power.",
                functional_failure="Phase-to-ground or phase-to-phase electrical short circuit tripping main supply breaker.",
                failure_mode="Dielectric Thermal Breakdown & Moisture Ingress",
                failure_cause="Class F insulation aging accelerated by winding temperature hotspots (>140°C) and ambient condensation.",
                failure_effect="Catastrophic motor burn-out, production line dead stoppage for 24-48 hours, high replacement capital cost.",
                severity_score=9,
                occurrence_score=7,
                detection_score=9,
                rcm_strategy="condition_based",
                strategy_rationale="Continuous stator RTD telemetry and quarterly polarization index (PI) insulation testing prevent unexpected burnout.",
                mitigation_task="Quarterly Megger insulation resistance testing (minimum 100 Megohms) and continuous RTD thermal limit trips.",
                linked_maintenance_schedule=sched,
                assessed_by=user,
                status="active",
            )

            # 4. Calibration Records
            AssetCalibrationRecord.objects.create(
                tenant=tenant,
                instrument_tag="PT-101 (Discharge Pressure Transmitter)",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                calibrated_by=user,
                service_vendor=vendor,
                calibration_date=timezone.now().date() - timezone.timedelta(days=45),
                calibration_frequency_days=365,
                next_due_date=timezone.now().date() + timezone.timedelta(days=320),
                reference_standard_used="Fluke 754 Documenting Process Calibrator S/N 892144 (NIST Traceable)",
                traceability_certificate_no="NIST-FLK-2026-9081",
                setpoint_nominal=Decimal("100.0000"),
                allowable_tolerance=Decimal("0.5000"),
                tolerance_unit="percent_span",
                as_found_reading=Decimal("100.1200"),
                as_left_reading=Decimal("100.0400"),
                calibration_result="pass",
                certificate_number="CAL-CERT-2026-PT101",
                certificate_expiry=timezone.now().date() + timezone.timedelta(days=320),
                status="valid",
                notes="Calibrated at 5 points (0%, 25%, 50%, 75%, 100% span). Zero adjustment required. Span linearity within 0.04%.",
            )

            AssetCalibrationRecord.objects.create(
                tenant=tenant,
                instrument_tag="TT-204 (Bearing Resistance Thermometer RTD)",
                fixed_asset=fa_secondary,
                operational_asset=oa_primary,
                calibrated_by=user,
                service_vendor=vendor,
                calibration_date=timezone.now().date() - timezone.timedelta(days=20),
                calibration_frequency_days=180,
                next_due_date=timezone.now().date() + timezone.timedelta(days=160),
                reference_standard_used="Beamex MC6 Multifunction Calibrator & Dry Block Bath #DB-50",
                traceability_certificate_no="ISO17025-BMX-2026-4412",
                setpoint_nominal=Decimal("50.0000"),
                allowable_tolerance=Decimal("0.2500"),
                tolerance_unit="celsius",
                as_found_reading=Decimal("50.3800"),
                as_left_reading=Decimal("50.0800"),
                calibration_result="pass_with_adjustment",
                certificate_number="CAL-CERT-2026-TT204",
                certificate_expiry=timezone.now().date() + timezone.timedelta(days=160),
                status="valid",
                notes="As-Found reading exceeded 0.25°C tolerance (+0.38°C). Trimmed zero offset via transmitter software. Final As-Left error +0.08°C.",
            )

            AssetCalibrationRecord.objects.create(
                tenant=tenant,
                instrument_tag="DG-003 (Precision Digital Toolroom Micrometer)",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                calibrated_by=user,
                calibration_date=timezone.now().date() - timezone.timedelta(days=380),
                calibration_frequency_days=365,
                next_due_date=timezone.now().date() - timezone.timedelta(days=15),
                reference_standard_used="Mitutoyo Ceramic Gauge Block Set Grade 0 ISO 3650 S/N 41029",
                traceability_certificate_no="MIT-CERT-2025-8812",
                setpoint_nominal=Decimal("25.0000"),
                allowable_tolerance=Decimal("0.0050"),
                tolerance_unit="engineering_units",
                as_found_reading=Decimal("25.0020"),
                as_left_reading=Decimal("25.0010"),
                calibration_result="pass",
                certificate_number="CAL-CERT-2025-DG003",
                certificate_expiry=timezone.now().date() - timezone.timedelta(days=15),
                status="expired",
                notes="Instrument in good physical condition but recalibration deadline is overdue by 15 days. Scheduled for recalibration this week.",
            )

        self.stdout.write(f"[{tenant.name}] 11.7 Seeding complete (3 assessments, 4 telemetry readings, 3 failure modes, 3 calibration records).")
