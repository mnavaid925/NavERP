from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset, GLAccount
from apps.accounting.models import FiscalPeriod
from apps.assets.models import (
    AssetComplianceAudit,
    AssetComplianceFramework,
    AssetComplianceIncident,
    AssetPermitLicense,
)
from apps.assets.models import (
    AssetCalibrationRecord,
    AssetConditionAssessment,
    AssetFailureMode,
    AssetTelemetryReading,
    AssetDisposalRequest,
    AssetResaleListing,
    AssetScrapSalvage,
    AssetTradeIn,
    AssetLeaseBuyAnalysis,
    AssetLeaseContract,
    AssetLeaseModification,
    AssetLeaseSchedule,
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
    AssetWarranty,
    AssetWarrantyClaim,
    AssetInsurancePolicy,
    AssetInsuranceClaim,
    CapitalizationPolicy,
    AssetGeofenceEvent,
    AssetScanLog,
    FieldWorkOrder,
    MobileAssetInspection,
    AssetBusinessContinuityPlan,
    AssetCyberSecurityProfile,
    AssetRiskMitigationAction,
    AssetRiskRegister,
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
            AssetRiskMitigationAction.objects.all().delete()
            AssetCyberSecurityProfile.objects.all().delete()
            AssetBusinessContinuityPlan.objects.all().delete()
            AssetRiskRegister.objects.all().delete()
            AssetComplianceIncident.objects.all().delete()
            AssetPermitLicense.objects.all().delete()
            AssetComplianceAudit.objects.all().delete()
            AssetComplianceFramework.objects.all().delete()
            AssetInsuranceClaim.objects.all().delete()
            AssetInsurancePolicy.objects.all().delete()
            AssetWarrantyClaim.objects.all().delete()
            AssetWarranty.objects.all().delete()
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
            self._seed_tenant_11_8(tenant)
            self._seed_tenant_11_9(tenant)
            self._seed_tenant_11_10(tenant)
            self._seed_tenant_11_11(tenant)
            if hasattr(self, '_seed_tenant_11_12'):
                self._seed_tenant_11_12(tenant)
            self._seed_tenant_11_13(tenant)

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

    def _seed_tenant_11_8(self, tenant):
        # Idempotency guard for 11.8
        if AssetWarranty.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.8 Warranty & Insurance data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.8 Warranty & Insurance Management...")

        user = User.objects.filter(tenant=tenant).first()
        fa_primary = FixedAsset.objects.filter(tenant=tenant).first()
        fa_secondary = FixedAsset.objects.filter(tenant=tenant).last()
        oa_primary = Asset.objects.filter(tenant=tenant).first()
        cat = AssetCategory.objects.filter(tenant=tenant).first()
        vendor = Party.objects.filter(tenant=tenant, roles__role="vendor").first() or Party.objects.filter(tenant=tenant).first()
        currency = Currency.objects.filter(is_active=True).first()
        maint_req = AssetMaintenanceRequest.objects.filter(tenant=tenant).first()
        incident_rep = AssetIncidentReport.objects.filter(tenant=tenant).first()
        service_contract = AssetServiceContract.objects.filter(tenant=tenant).first()

        today = timezone.now().date()

        with transaction.atomic():
            # 1. Asset Warranties
            war1 = AssetWarranty.objects.create(
                tenant=tenant,
                title="CNC Vertical Milling Machine OEM Factory Warranty",
                warranty_certificate_number=f"OEM-WTY-{tenant.pk}-001",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=cat,
                warrantor_party=vendor,
                currency=currency,
                warranty_type="oem_standard",
                coverage_scope="comprehensive",
                start_date=today - timezone.timedelta(days=365),
                end_date=today + timezone.timedelta(days=365),
                meter_type="hours",
                meter_limit=6000,
                parts_coverage_percent=100,
                labor_coverage_percent=100,
                travel_dispatch_covered=True,
                deductible_amount=Decimal("0.00"),
                contract_purchase_price=Decimal("0.00"),
                terms_and_conditions="Comprehensive 24-month or 6,000-operating-hour manufacturer warranty covering spindle assembly, linear guideways, servomotors, and CNC controller. Requires OEM certified lubrication schedule.",
                service_contract=service_contract,
                status="active",
                registered_by=user,
            )

            war2 = AssetWarranty.objects.create(
                tenant=tenant,
                title="Industrial Backup Diesel Generator Extended Powertrain Warranty",
                warranty_certificate_number=f"EXT-POW-{tenant.pk}-002",
                fixed_asset=fa_secondary,
                operational_asset=oa_primary,
                asset_category=cat,
                warrantor_party=vendor,
                currency=currency,
                warranty_type="oem_extended",
                coverage_scope="powertrain_major_components",
                start_date=today - timezone.timedelta(days=180),
                end_date=today + timezone.timedelta(days=45),  # Expiring soon (<60d)
                meter_type="hours",
                meter_limit=2500,
                parts_coverage_percent=100,
                labor_coverage_percent=80,
                travel_dispatch_covered=False,
                deductible_amount=Decimal("250.00"),
                contract_purchase_price=Decimal("3500.00"),
                terms_and_conditions="Extended 36-month protection on engine block, crankshaft, turbocharger, and stator alternator coils. Excludes consumables, belts, and filters.",
                status="expiring_soon",
                registered_by=user,
            )

            war3 = AssetWarranty.objects.create(
                tenant=tenant,
                title="Electric Material Handling Fleet Certified Pre-Owned Warranty",
                warranty_certificate_number=f"DLR-CPO-{tenant.pk}-003",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=cat,
                warrantor_party=vendor,
                currency=currency,
                warranty_type="dealer_certified",
                coverage_scope="parts_and_labor",
                start_date=today - timezone.timedelta(days=90),
                end_date=today + timezone.timedelta(days=275),
                meter_type="hours",
                meter_limit=4000,
                parts_coverage_percent=90,
                labor_coverage_percent=90,
                travel_dispatch_covered=True,
                deductible_amount=Decimal("150.00"),
                contract_purchase_price=Decimal("1200.00"),
                terms_and_conditions="Dealer certified pre-owned coverage on drive motor, hydraulic pump, and lift mast cylinder. Regular battery electrolyte inspection required.",
                status="active",
                registered_by=user,
            )

            # 2. Asset Warranty Claims
            claim1 = AssetWarrantyClaim.objects.create(
                tenant=tenant,
                title="Spindle Drive Cooling Fan Failure & Thermal Shutdown",
                warranty=war1,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                maintenance_request=maint_req,
                incident_date=today - timezone.timedelta(days=45),
                operating_meter_at_failure=1820,
                defect_description="Spindle cooling circuit internal blower motor seized due to bearing race flaw, triggering high-temperature alarm 0x4B and emergency stop.",
                warrantor_claim_reference=f"OEM-RMA-{tenant.pk}-8812",
                currency=currency,
                claimed_amount=Decimal("2450.00"),
                approved_amount=Decimal("2450.00"),
                deductible_applied=Decimal("0.00"),
                net_recovery_amount=Decimal("2450.00"),
                resolution_type="parts_replacement",
                claim_status="settled_closed",
                part_return_status="received_inspected_by_oem",
                rma_tracking_number="1Z9999999948192837",
                submission_date=today - timezone.timedelta(days=40),
                settlement_date=today - timezone.timedelta(days=20),
                settlement_notes="OEM validated bearing cage fatigue defect under warranty. Replacement blower fan kit and harness dispatched at zero charge. Full credit issued.",
                filed_by=user,
                approved_by=user,
            )

            claim2 = AssetWarrantyClaim.objects.create(
                tenant=tenant,
                title="Generator Alternator Automatic Voltage Regulator (AVR) Breakdown",
                warranty=war2,
                fixed_asset=fa_secondary,
                operational_asset=oa_primary,
                incident_date=today - timezone.timedelta(days=12),
                operating_meter_at_failure=980,
                defect_description="AVR component diode breakdown causing AC voltage fluctuation beyond +/- 15%. Voltage hunt observed on load test.",
                warrantor_claim_reference=f"CAT-CLM-{tenant.pk}-3910",
                currency=currency,
                claimed_amount=Decimal("1850.00"),
                approved_amount=Decimal("0.00"),
                deductible_applied=Decimal("250.00"),
                net_recovery_amount=Decimal("0.00"),
                resolution_type="pending_evaluation",
                claim_status="submitted",
                part_return_status="return_required_pending",
                submission_date=today - timezone.timedelta(days=10),
                settlement_notes="Formal defect documentation and diagnostic datalogs transmitted to OEM regional technical service center. Awaiting field inspection approval.",
                filed_by=user,
            )

            # 3. Asset Insurance Policies
            pol1 = AssetInsurancePolicy.objects.create(
                tenant=tenant,
                policy_number=f"POL-PROP-{tenant.pk}-2026",
                title="Commercial Plant & Industrial Equipment All-Risk Schedule",
                policy_type="comprehensive_all_risk",
                valuation_basis="replacement_cost_value",
                underwriter_party=vendor,
                broker_party=vendor,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                asset_category=cat,
                currency=currency,
                effective_date=today - timezone.timedelta(days=120),
                expiration_date=today + timezone.timedelta(days=245),
                total_insured_value=Decimal("750000.00"),
                deductible_retention=Decimal("5000.00"),
                coinsurance_percentage=90,
                annual_premium=Decimal("8400.00"),
                premium_frequency="annual",
                coverage_terms="Broadform property, explosion, lightning, windstorm, sprinkler leakage, and accidental direct physical loss. Territorial coverage: Plant Main Facility.",
                status="active",
                risk_manager=user,
            )

            pol2 = AssetInsurancePolicy.objects.create(
                tenant=tenant,
                policy_number=f"POL-MB-{tenant.pk}-2026",
                title="Machinery Breakdown, Electrical Arcing & Boiler Pressure Vessel Policy",
                policy_type="machinery_breakdown",
                valuation_basis="replacement_cost_value",
                underwriter_party=vendor,
                broker_party=vendor,
                currency=currency,
                effective_date=today - timezone.timedelta(days=330),
                expiration_date=today + timezone.timedelta(days=35),  # Pending renewal (<45d)
                total_insured_value=Decimal("450000.00"),
                deductible_retention=Decimal("2500.00"),
                coinsurance_percentage=100,
                annual_premium=Decimal("6200.00"),
                premium_frequency="semi_annual",
                coverage_terms="Mechanical breakdown, centrifugal force rupture, electrical arcing short circuit, and boiler tube expansion failure across all plant CNC and power assets.",
                status="pending_renewal",
                risk_manager=user,
            )

            # 4. Asset Insurance Claims
            ins_claim1 = AssetInsuranceClaim.objects.create(
                tenant=tenant,
                title="Main Substation High-Voltage Surge Damage",
                policy=pol2,
                fixed_asset=fa_secondary,
                operational_asset=oa_primary,
                incident_report=incident_rep,
                incident_date=today - timezone.timedelta(days=60),
                peril_type="electrical_arcing_surge",
                incident_description="Severe atmospheric transient voltage surge propagated through utility grid, burning out substation step-down transformer insulation and switchgear relays.",
                incident_location="Building B - Electrical Substation Room 102",
                carrier_claim_number=f"CLM-SURGE-{tenant.pk}-9021",
                adjuster_party=vendor,
                adjuster_name="Marcus Vance (Crawford Forensic Loss Consulting)",
                currency=currency,
                claimed_loss_amount=Decimal("42000.00"),
                deductible_applied=Decimal("2500.00"),
                salvage_recovery_amount=Decimal("3500.00"),
                settlement_payout_amount=Decimal("36000.00"),
                claim_status="settled_paid",
                settlement_method="direct_indemnity_check",
                date_reported_to_carrier=today - timezone.timedelta(days=58),
                proof_of_loss_date=today - timezone.timedelta(days=45),
                settlement_date=today - timezone.timedelta(days=15),
                settlement_notes="Forensic engineer confirmed external grid lightning surge as primary proximate peril. Gross loss appraised at $42,000. Net indemnity $36,000 after $2,500 deductible and $3,500 transformer copper core salvage.",
                claims_officer=user,
            )

            ins_claim2 = AssetInsuranceClaim.objects.create(
                tenant=tenant,
                title="Hydraulic Press Catastrophic Cylinder Seal Blowout & Flood",
                policy=pol1,
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                incident_report=incident_rep,
                incident_date=today - timezone.timedelta(days=14),
                peril_type="mechanical_breakdown",
                incident_description="Sudden high-pressure hydraulic ram cylinder head seal blowout resulting in 300 gallons of synthetic oil release and damage to floor electronics.",
                incident_location="Main Machine Shop - Bay 4 Press Area",
                carrier_claim_number=f"CLM-HYD-{tenant.pk}-4482",
                adjuster_party=vendor,
                adjuster_name="Elena Rostova (Sedgwick Global Claims)",
                currency=currency,
                claimed_loss_amount=Decimal("18500.00"),
                deductible_applied=Decimal("5000.00"),
                salvage_recovery_amount=Decimal("0.00"),
                settlement_payout_amount=Decimal("0.00"),
                claim_status="adjuster_assigned",
                settlement_method="direct_indemnity_check",
                date_reported_to_carrier=today - timezone.timedelta(days=12),
                settlement_notes="Carrier adjuster conducted on-site physical damage assessment and hydraulic fluid oil testing. Proof of Loss statement currently being assembled.",
                claims_officer=user,
            )

        self.stdout.write(f"[{tenant.name}] 11.8 Seeding complete (3 warranties, 2 warranty claims, 2 insurance policies, 2 insurance claims).")

    def _seed_tenant_11_9(self, tenant):
        # Idempotency guard for 11.9
        if AssetDisposalRequest.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.9 Asset Disposal & Retirement data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.9 Asset Disposal & Retirement...")

        user = User.objects.filter(tenant=tenant).first()
        fa_primary = FixedAsset.objects.filter(tenant=tenant).first()
        fa_secondary = FixedAsset.objects.filter(tenant=tenant).last()
        oa_primary = Asset.objects.filter(tenant=tenant).first()
        cat = AssetCategory.objects.filter(tenant=tenant).first()
        cost_center = OrgUnit.objects.filter(tenant=tenant).first()
        vendor = Party.objects.filter(tenant=tenant, roles__role="vendor").first() or Party.objects.filter(tenant=tenant).first()

        today = timezone.now().date()

        with transaction.atomic():
            # 1. Disposal Request 1: Resale / Auction (In Progress)
            dsp_req1 = AssetDisposalRequest.objects.create(
                tenant=tenant,
                title="Secondary Market Remarketing of Surplus 5-Axis Milling Center",
                fixed_asset=fa_primary,
                operational_asset=oa_primary,
                category=cat,
                cost_center=cost_center,
                requested_by=user,
                appraised_by=user,
                approved_by=user,
                disposal_method="resale",
                retirement_reason="technological_obsolescence",
                justification_notes="Production line transitioned to high-speed dual-spindle cells. Machine is fully operational and retains substantial secondary market industrial resale value.",
                acquisition_cost=fa_primary.acquisition_cost or Decimal("85000.00"),
                accumulated_depreciation=Decimal("55000.00"),
                net_book_value=Decimal("30000.00"),
                estimated_residual_value=Decimal("38000.00"),
                estimated_removal_cost=Decimal("2500.00"),
                actual_gross_proceeds=Decimal("41500.00"),
                actual_removal_cost=Decimal("2075.00"),
                realized_gain_loss=Decimal("9425.00"),
                status="in_progress",
                submitted_at=today - timezone.timedelta(days=25),
                approved_at=today - timezone.timedelta(days=20),
            )

            # 2. Resale Listing 1: Awarded / Paid
            listing1 = AssetResaleListing.objects.create(
                tenant=tenant,
                disposal_request=dsp_req1,
                fixed_asset=fa_primary,
                buyer=vendor,
                broker_auctioneer=vendor,
                managed_by=user,
                listing_channel="public_auction",
                listing_reference=f"LOT-EAM-{tenant.pk}-9912",
                listing_date=today - timezone.timedelta(days=18),
                closing_date=today - timezone.timedelta(days=5),
                reserve_price=Decimal("35000.00"),
                asking_price=Decimal("40000.00"),
                highest_bid_amount=Decimal("41500.00"),
                buyer_contact_name="Apex Precision Engineering Ltd",
                buyer_contact_email="procurement@apexprecision.com",
                buyer_contact_phone="+1-555-839-2041",
                gross_sale_proceeds=Decimal("41500.00"),
                commission_rate_percent=Decimal("5.00"),
                commission_amount=Decimal("2075.00"),
                tax_amount=Decimal("0.00"),
                net_sale_proceeds=Decimal("39425.00"),
                status="payment_received",
                payment_status="paid",
                payment_date=today - timezone.timedelta(days=3),
                terms_and_conditions="Sold As-Is Where-Is. Rigging and heavy transport coordinated through Ritchie Bros logistics partner.",
            )

            # 3. Disposal Request 2: Vendor Trade-in (Approved / Surrendered)
            dsp_req2 = AssetDisposalRequest.objects.create(
                tenant=tenant,
                title="OEM Trade-in Exchange for High-Efficiency Press",
                fixed_asset=fa_secondary,
                operational_asset=None,
                category=cat,
                cost_center=cost_center,
                requested_by=user,
                appraised_by=user,
                approved_by=user,
                disposal_method="trade_in",
                retirement_reason="end_of_life",
                justification_notes="Equipment at end of economic 10-year service life. Dealer offered $18,000 trade allowance offset against new Tier-4 press procurement.",
                acquisition_cost=fa_secondary.acquisition_cost or Decimal("45000.00"),
                accumulated_depreciation=Decimal("38000.00"),
                net_book_value=Decimal("7000.00"),
                estimated_residual_value=Decimal("18000.00"),
                estimated_removal_cost=Decimal("1200.00"),
                actual_gross_proceeds=Decimal("19500.00"),
                actual_removal_cost=Decimal("0.00"),
                realized_gain_loss=Decimal("12500.00"),
                status="in_progress",
                submitted_at=today - timezone.timedelta(days=15),
                approved_at=today - timezone.timedelta(days=10),
            )

            # 4. Trade-in Record 1: Equipment Surrendered
            trade1 = AssetTradeIn.objects.create(
                tenant=tenant,
                disposal_request=dsp_req2,
                retired_fixed_asset=fa_secondary,
                vendor=vendor,
                replacement_fixed_asset=None,
                authorized_by=user,
                agreement_number=f"TI-AGR-{tenant.pk}-772",
                agreement_date=today - timezone.timedelta(days=8),
                handover_due_date=today + timezone.timedelta(days=14),
                dealer_appraised_value=Decimal("16500.00"),
                trade_in_allowance=Decimal("18000.00"),
                over_allowance_amount=Decimal("1500.00"),
                net_credit_applied=Decimal("19500.00"),
                replacement_asset_cost=Decimal("95000.00"),
                net_cash_outflow=Decimal("75500.00"),
                like_kind_exchange=True,
                gain_loss_deferred=Decimal("12500.00"),
                status="equipment_surrendered",
                surrendered_at=today - timezone.timedelta(days=2),
                notes="Authorized under 2026 fleet modernization contract. Dealer allowance applied directly to invoice.",
            )

            # 5. Disposal Request 3: Scrap & Salvage (Completed & Disposed)
            dsp_req3 = AssetDisposalRequest.objects.create(
                tenant=tenant,
                title="Scrap & Metal Recycling of Damaged Boiler Tank Vessel",
                fixed_asset=fa_secondary,
                operational_asset=None,
                category=cat,
                cost_center=cost_center,
                requested_by=user,
                appraised_by=user,
                approved_by=user,
                disposal_method="scrap_salvage",
                retirement_reason="uneconomical_repair",
                justification_notes="Severe wall corrosion and hydrostatic rupture. Repair deemed unsafe and uneconomical. Decommissioned for controlled metal recycling and hazardous abatement.",
                acquisition_cost=Decimal("32000.00"),
                accumulated_depreciation=Decimal("30000.00"),
                net_book_value=Decimal("2000.00"),
                estimated_residual_value=Decimal("3500.00"),
                estimated_removal_cost=Decimal("1800.00"),
                actual_gross_proceeds=Decimal("4200.00"),
                actual_removal_cost=Decimal("1650.00"),
                realized_gain_loss=Decimal("550.00"),
                status="completed",
                submitted_at=today - timezone.timedelta(days=40),
                approved_at=today - timezone.timedelta(days=35),
                completed_at=today - timezone.timedelta(days=5),
            )

            # 6. Scrap & Salvage Record 1: Settled with CoD
            scrap1 = AssetScrapSalvage.objects.create(
                tenant=tenant,
                disposal_request=dsp_req3,
                fixed_asset=fa_secondary,
                operational_asset=None,
                recycler_partner=vendor,
                supervisor=user,
                scrap_method="dismantling_parts_recovery",
                decommissioning_date=today - timezone.timedelta(days=30),
                completion_date=today - timezone.timedelta(days=5),
                total_scrap_weight_kg=Decimal("4850.00"),
                ferrous_weight_kg=Decimal("4200.00"),
                non_ferrous_weight_kg=Decimal("650.00"),
                e_waste_weight_kg=Decimal("0.00"),
                salvage_proceeds=Decimal("4200.00"),
                dismantling_cost=Decimal("1650.00"),
                net_salvage_recovery=Decimal("2550.00"),
                has_hazardous_materials=True,
                hazardous_waste_class="RCRA D008 Lead Solder",
                epa_manifest_number=f"EPA-MNF-{tenant.pk}-39912",
                abatement_certified=True,
                abatement_date=today - timezone.timedelta(days=12),
                data_sanitized=False,
                sanitization_method="none",
                cod_number=f"COD-MET-{tenant.pk}-8831",
                cod_issue_date=today - timezone.timedelta(days=5),
                cod_issuing_agency="Sims Metal & Industrial Recycling LLC",
                carrier_name="Midwest Industrial Freight Logistics",
                bill_of_lading_number=f"BOL-{tenant.pk}-5510",
                notes="Boiler shell cut and segregated. Certified hazardous abatement completed prior to metal yard smelting.",
                status="settled",
            )

        self.stdout.write(f"[{tenant.name}] 11.9 Seeding complete (3 disposal requests, 1 resale listing, 1 trade-in, 1 scrap salvage).")

    def _seed_tenant_11_11(self, tenant):
        # -------------------------------------------------------------
        # Sub-module 11.11: Compliance & Regulatory Management
        # -------------------------------------------------------------
        if AssetComplianceFramework.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.11 Compliance already seeded; skipping.")
            return

        today = timezone.now().date()
        user = User.objects.filter(tenant=tenant).first()
        cat = AssetCategory.objects.filter(tenant=tenant).first()
        oa_primary = Asset.objects.filter(tenant=tenant).first()
        if not oa_primary:
            self.stdout.write(f"[{tenant.name}] Warning: No SCM assets found; skipping 11.11 compliance seeding.")
            return
        vendor = Party.objects.filter(tenant=tenant, roles__role="vendor").first() or Party.objects.filter(tenant=tenant).first()

        with transaction.atomic():
                # 1. Compliance Framework 1: OSHA PSM
                fw_osha = AssetComplianceFramework.objects.create(
                    tenant=tenant,
                    name="OSHA 1910.119 Process Safety Management",
                    code="OSHA-1910-PSM",
                    framework_type="regulatory",
                    regulatory_agency=vendor,
                    applicable_category=cat,
                    effective_date=today - timezone.timedelta(days=365),
                    revision="2024 Edition",
                    mandatory_audit_cycle_months=12,
                    readiness_score=94,
                    description="Mandatory federal standard governing management of hazards associated with highly hazardous chemicals in process facilities.",
                    status="active",
                )

                # 2. Compliance Framework 2: ISO 55001
                fw_iso = AssetComplianceFramework.objects.create(
                    tenant=tenant,
                    name="ISO 55001:2024 Asset Management Systems",
                    code="ISO-55001",
                    framework_type="voluntary_standard",
                    regulatory_agency=vendor,
                    applicable_category=cat,
                    effective_date=today - timezone.timedelta(days=180),
                    revision="2024 Reissue",
                    mandatory_audit_cycle_months=36,
                    readiness_score=90,
                    description="International management system standard defining requirements for establishing, implementing, maintaining, and improving physical asset lifecycle governance.",
                    status="active",
                )

                # 3. Compliance Framework 3: EPA Title V
                fw_epa = AssetComplianceFramework.objects.create(
                    tenant=tenant,
                    name="EPA Clean Air Act Title V Operating Permit Standard",
                    code="EPA-TITLE-V",
                    framework_type="regulatory",
                    regulatory_agency=vendor,
                    applicable_category=cat,
                    effective_date=today - timezone.timedelta(days=500),
                    revision="Rev 4",
                    mandatory_audit_cycle_months=12,
                    readiness_score=88,
                    description="Federal and delegated state Clean Air Act requirements for stationary source emissions, continuous emission monitoring, and compliance certifications.",
                    status="active",
                )

                # 4. Compliance Audit 1: Annual OSHA Safety Audit
                audit1 = AssetComplianceAudit.objects.create(
                    tenant=tenant,
                    title="Annual Plant Machine Guarding & LOTO Verification",
                    framework=fw_osha,
                    asset=oa_primary,
                    audit_type="internal",
                    lead_auditor_user=user,
                    auditor_party=None,
                    audit_date=today - timezone.timedelta(days=45),
                    scope_description="Verification of physical barrier interlocks, emergency stop switches, and lockout/tagout procedures across production machinery.",
                    total_checkpoints=45,
                    passed_checkpoints=45,
                    minor_findings_count=0,
                    major_findings_count=0,
                    critical_findings_count=0,
                    compliance_rating="fully_compliant",
                    summary_findings="All machine guards secure. Dual interlocks tested and verified conforming. Operator sign-offs current.",
                    status="completed",
                    completed_at=timezone.now() - timezone.timedelta(days=44),
                )

                # 5. Compliance Audit 2: ISO 55001 Surveillance Audit
                audit2 = AssetComplianceAudit.objects.create(
                    tenant=tenant,
                    title="ISO 55001 Stage 2 Asset Lifecycle Surveillance Audit",
                    framework=fw_iso,
                    asset=None,
                    audit_type="third_party_certification",
                    lead_auditor_user=user,
                    auditor_party=vendor,
                    audit_date=today - timezone.timedelta(days=10),
                    scope_description="Corporate asset governance, maintenance strategy alignment, and criticality assessment completeness audit.",
                    total_checkpoints=60,
                    passed_checkpoints=57,
                    minor_findings_count=3,
                    major_findings_count=0,
                    critical_findings_count=0,
                    compliance_rating="minor_deficiencies",
                    summary_findings="3 minor observations relating to calibration interval documentation. Remedial corrective action submitted.",
                    status="in_progress",
                )

                # 6. Compliance Audit 3: EPA Emissions Audit
                audit3 = AssetComplianceAudit.objects.create(
                    tenant=tenant,
                    title="EPA Title V Stationary Source Emission Testing & Inspection",
                    framework=fw_epa,
                    asset=oa_primary,
                    audit_type="external_regulatory",
                    lead_auditor_user=user,
                    auditor_party=vendor,
                    audit_date=today - timezone.timedelta(days=5),
                    scope_description="Emissions sampling, CEMS sensor calibration checks, and continuous flare opacity verification.",
                    total_checkpoints=30,
                    passed_checkpoints=28,
                    minor_findings_count=1,
                    major_findings_count=1,
                    critical_findings_count=0,
                    compliance_rating="major_non_conformance",
                    summary_findings="One major non-conformance for hourly NOX spike during cold boiler startup. Formal NOV expected.",
                    status="under_review",
                )

                # 7. Operating Permits & Licenses
                permit1 = AssetPermitLicense.objects.create(
                    tenant=tenant,
                    permit_name="High-Pressure Steam Boiler Operating Certificate",
                    permit_number=f"BOILER-CERT-{tenant.pk}-7731",
                    permit_type="pressure_vessel",
                    asset=oa_primary,
                    issuing_authority=vendor,
                    issue_date=today - timezone.timedelta(days=120),
                    effective_date=today - timezone.timedelta(days=120),
                    expiration_date=today + timezone.timedelta(days=245),
                    renewal_lead_days=60,
                    renewal_fee=Decimal("750.00"),
                    operating_conditions="Maximum allowable working pressure 250 PSIG. Relief valve annual hydro-test certificate required.",
                    status="active",
                )

                permit2 = AssetPermitLicense.objects.create(
                    tenant=tenant,
                    permit_name="Title V Stationary Source Air Quality Operating Permit",
                    permit_number=f"EPA-AIR-{tenant.pk}-9042",
                    permit_type="environmental_emissions",
                    asset=oa_primary,
                    issuing_authority=vendor,
                    issue_date=today - timezone.timedelta(days=320),
                    effective_date=today - timezone.timedelta(days=320),
                    expiration_date=today + timezone.timedelta(days=45),
                    renewal_lead_days=60,
                    renewal_fee=Decimal("3500.00"),
                    operating_conditions="NOX emissions capped at 25 PPM. Annual flue gas testing and semi-annual electronic filing required.",
                    status="active",
                )

                permit3 = AssetPermitLicense.objects.create(
                    tenant=tenant,
                    permit_name="Industrial Wastewater Pre-Treatment Discharge Permit",
                    permit_number=f"NPDES-DISCH-{tenant.pk}-4410",
                    permit_type="water_discharge",
                    asset=oa_primary,
                    issuing_authority=vendor,
                    issue_date=today - timezone.timedelta(days=180),
                    effective_date=today - timezone.timedelta(days=180),
                    expiration_date=today + timezone.timedelta(days=185),
                    renewal_lead_days=60,
                    renewal_fee=Decimal("1200.00"),
                    operating_conditions="Effluent pH must remain between 6.0 and 9.0. Total suspended solids <= 250 mg/L.",
                    status="active",
                )

                permit4 = AssetPermitLicense.objects.create(
                    tenant=tenant,
                    permit_name="Flammable & Combustible Liquids Bulk Storage License",
                    permit_number=f"FIRE-HAZ-{tenant.pk}-019",
                    permit_type="hazardous_material",
                    asset=oa_primary,
                    issuing_authority=vendor,
                    issue_date=today - timezone.timedelta(days=380),
                    effective_date=today - timezone.timedelta(days=380),
                    expiration_date=today - timezone.timedelta(days=15),
                    renewal_lead_days=30,
                    renewal_fee=Decimal("500.00"),
                    operating_conditions="Secondary containment capacity must exceed 110% of tank volume. Fire suppression foam tested quarterly.",
                    status="expired",
                )

                # 8. Compliance Incidents & Citations
                inc1 = AssetComplianceIncident.objects.create(
                    tenant=tenant,
                    title="EPA Title V Hourly NOX Emission Spike During Cold Startup",
                    incident_date=today - timezone.timedelta(days=6),
                    discovery_date=today - timezone.timedelta(days=5),
                    incident_type="emissions_exceedance",
                    severity="serious",
                    asset=oa_primary,
                    permit=permit2,
                    audit=audit3,
                    enforcement_agency=vendor,
                    citation_reference=f"EPA-NOV-{tenant.pk}-2026-081",
                    fine_assessed=Decimal("15000.00"),
                    fine_paid=Decimal("15000.00"),
                    fine_payment_date=today - timezone.timedelta(days=1),
                    root_cause="mechanical_failure",
                    root_cause_analysis="Fuel-air actuator damper stuck at 30% position during cold burner ignition, creating incomplete combustion spike.",
                    corrective_action_plan="Replaced pneumatic damper actuator with redundant closed-loop electronic positioner. Added automated startup interlock.",
                    assigned_investigator=user,
                    target_resolution_date=today + timezone.timedelta(days=15),
                    actual_resolution_date=today - timezone.timedelta(days=1),
                    status="resolved",
                )

                inc2 = AssetComplianceIncident.objects.create(
                    tenant=tenant,
                    title="OSHA Citation 1910.212 — Missing Interlock on Stamping Feed Table",
                    incident_date=today - timezone.timedelta(days=14),
                    discovery_date=today - timezone.timedelta(days=14),
                    incident_type="safety_infraction",
                    severity="serious",
                    asset=oa_primary,
                    permit=None,
                    audit=None,
                    enforcement_agency=vendor,
                    citation_reference=f"OSHA-CIT-{tenant.pk}-99182",
                    fine_assessed=Decimal("8500.00"),
                    fine_paid=Decimal("0.00"),
                    root_cause="inadequate_procedure",
                    root_cause_analysis="Maintenance technician temporarily bypassed light curtain during tooling changeover and neglected to re-arm.",
                    corrective_action_plan="Hardwired tamper-resistant keyed interlock switches. Conducted mandatory LOTO refresher for all toolmakers.",
                    assigned_investigator=user,
                    target_resolution_date=today + timezone.timedelta(days=10),
                    status="capa_in_progress",
                )

                inc3 = AssetComplianceIncident.objects.create(
                    tenant=tenant,
                    title="Unpermitted Coolant Fluid Sump Overflow in Machining Bay 3",
                    incident_date=today - timezone.timedelta(days=2),
                    discovery_date=today - timezone.timedelta(days=2),
                    incident_type="unpermitted_discharge",
                    severity="other_than_serious",
                    asset=oa_primary,
                    permit=None,
                    audit=None,
                    enforcement_agency=None,
                    fine_assessed=Decimal("0.00"),
                    fine_paid=Decimal("0.00"),
                    root_cause="human_error",
                    root_cause_analysis="Automatic replenishment valve left open manually during shift transition.",
                    corrective_action_plan="Installed fail-safe high-level float cutoff switch with alarm buzzer.",
                    assigned_investigator=user,
                    target_resolution_date=today + timezone.timedelta(days=7),
                    status="open",
                )

        self.stdout.write(f"[{tenant.name}] 11.11 Seeding complete (3 frameworks, 3 audits, 4 permits, 3 incidents).")

    def _seed_tenant_11_10(self, tenant):
        # =====================================================================
        # 11.10 Lease & Rental Management
        # =====================================================================
        if AssetLeaseContract.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.10 Lease data already seeded; skipping.")
            return

        today = timezone.now().date()
        user = User.objects.filter(tenant=tenant).first()
        with transaction.atomic():
            lessor_party = Party.objects.filter(tenant=tenant).first()
            if not lessor_party:
                lessor_party = Party.objects.create(
                    tenant=tenant,
                    name=f"CAT Equipment Financial Services — {tenant.name}",
                    party_type="organization",
                    status="active",
                )

            cat_node = AssetCategory.objects.filter(tenant=tenant).first()
            op_asset = Asset.objects.filter(tenant=tenant).first()
            fa_node = FixedAsset.objects.filter(tenant=tenant).first()

            # Contract 1: Active Finance Lease (5-Axis CNC Machine)
            alc1 = AssetLeaseContract.objects.create(
                tenant=tenant,
                title="Finance Lease for 5-Axis CNC Machining Center",
                master_lease_agreement_ref=f"MLA-2025-IND-{tenant.pk}01",
                lessor=lessor_party,
                asset=op_asset,
                category=cat_node,
                fixed_asset=fa_node,
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
                approved_by=user,
                notes="Primary plant CNC cell lease with equipment buyout clause at month 36.",
            )
            alc1.calculate_present_value()
            alc1.save()
            alc1.generate_amortization_schedule()

            # Mark first 6 installments as paid
            for sch in alc1.payment_schedules.filter(period_number__lte=6):
                sch.status = "paid"
                sch.paid_date = sch.due_date
                sch.payment_reference = f"ACH-{tenant.pk}90{sch.period_number}"
                sch.save()
            last_paid = alc1.payment_schedules.filter(period_number=6).first()
            if last_paid:
                alc1.current_lease_liability = last_paid.ending_liability
                alc1.current_rou_asset_carrying_value = last_paid.ending_rou_asset_value
                alc1.save()

            # Contract 2: Active Operating Lease (Warehouse Forklift Fleet)
            alc2 = AssetLeaseContract.objects.create(
                tenant=tenant,
                title="Operating Lease for High-Reach Warehouse Forklift Fleet",
                master_lease_agreement_ref=f"MLA-2026-FLT-{tenant.pk}09",
                lessor=lessor_party,
                asset=op_asset,
                category=cat_node,
                fixed_asset=None,
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
                initial_direct_costs=Decimal("500.00"),
                lease_incentives=Decimal("0.00"),
                residual_value_guarantee=Decimal("0.00"),
                purchase_option_price=None,
                has_purchase_option=False,
                transfer_of_ownership=False,
                is_specialized_asset=False,
                classification="operating",
                status="active",
                approved_by=user,
                notes="Logistics material handling fleet lease under full service maintenance contract.",
            )
            alc2.calculate_present_value()
            alc2.save()
            alc2.generate_amortization_schedule()

            # Mark first 2 installments as paid
            for sch in alc2.payment_schedules.filter(period_number__lte=2):
                sch.status = "paid"
                sch.paid_date = sch.due_date
                sch.payment_reference = f"WIRE-{tenant.pk}41{sch.period_number}"
                sch.save()
            last_paid2 = alc2.payment_schedules.filter(period_number=2).first()
            if last_paid2:
                alc2.current_lease_liability = last_paid2.ending_liability
                alc2.current_rou_asset_carrying_value = last_paid2.ending_rou_asset_value
                alc2.save()

            # Contract 3: Draft Lease Contract
            alc3 = AssetLeaseContract.objects.create(
                tenant=tenant,
                title="Master Equipment Lease: Autonomous Mobile Robots (AMRs)",
                master_lease_agreement_ref=f"MLA-2026-ROB-{tenant.pk}14",
                lessor=lessor_party,
                asset=None,
                category=cat_node,
                fixed_asset=None,
                inception_date=today,
                commencement_date=today + timezone.timedelta(days=30),
                expiration_date=today + timezone.timedelta(days=1125),
                first_payment_date=today + timezone.timedelta(days=30),
                lease_term_months=36,
                economic_life_months=60,
                payment_amount=Decimal("3600.00"),
                payment_frequency="monthly",
                payment_timing="arrears",
                discount_rate_pct=Decimal("5.2500"),
                fair_market_value=Decimal("135000.00"),
                status="draft",
                notes="Pending final vendor pricing addendum and risk review.",
            )
            alc3.calculate_present_value()
            alc3.evaluate_statutory_classification()
            alc3.save()

            # Modification 1: Term Extension on Contract 1
            AssetLeaseModification.objects.create(
                tenant=tenant,
                lease_contract=alc1,
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
                requested_by=user,
                approved_by=user,
                status="executed",
                justification="Production volume increases necessitate extending lease duration by 12 months.",
                notes="Executed remeasurement approved by Controller.",
            )

            # Lease vs. Buy Analysis 1: Gantry Crane (Evaluated -> Buy recommended)
            alba1 = AssetLeaseBuyAnalysis.objects.create(
                tenant=tenant,
                title="CapEx Decision: High-Capacity 50-Ton Overhead Gantry Crane",
                description="Evaluation of outright debt purchase vs 5-year operating lease for heavy fab bay.",
                target_asset_name="Konecranes 50T Industrial Gantry Crane",
                category=cat_node,
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
                evaluated_by=user,
                status="evaluated",
                evaluation_notes="Long expected useful life (10 yrs) and favorable terminal salvage make loan purchase financially superior.",
            )
            alba1.evaluate_financial_models()
            alba1.save()

            # Lease vs. Buy Analysis 2: Palletizing Robot (Approved -> Lease recommended)
            alba2 = AssetLeaseBuyAnalysis.objects.create(
                tenant=tenant,
                title="CapEx Decision: Automated Packaging Palletizer System",
                description="Rapid technological turnover favors 3-year operating lease with vendor tech refresh.",
                target_asset_name="Fanuc M-410iC Robotic Palletizing Cell",
                category=cat_node,
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
                evaluated_by=user,
                approved_by=user,
                status="approved",
                evaluation_notes="Leasing minimizes capital lock-up and mitigates robotics obsolescence risk.",
            )
            alba2.evaluate_financial_models()
            alba2.save()

        self.stdout.write(f"[{tenant.name}] 11.10 Seeding complete (3 lease contracts, schedules, 1 modification, 2 lease vs buy analyses).")

    def _seed_tenant_11_13(self, tenant):
        # Sub-module 11.13: Mobile Asset Management
        if MobileAssetInspection.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.13 Mobile Asset Management already seeded; skipping.")
        else:
            scm_asset1 = Asset.objects.filter(tenant=tenant).first()
            scm_asset2 = Asset.objects.filter(tenant=tenant).order_by("pk")[1] if Asset.objects.filter(tenant=tenant).count() > 1 else scm_asset1

            if not scm_asset1:
                self.stdout.write(f"[{tenant.name}] Warning: No SCM assets found; skipping 11.13 mobile seeding.")
            else:
                user = User.objects.filter(tenant=tenant).first()
                fixed_asset1 = FixedAsset.objects.filter(tenant=tenant).first()

                # Inspections
                mins1 = MobileAssetInspection.objects.create(
                    tenant=tenant,
                    title="Daily CNC Milling Machine Walkaround Inspection",
                    inspection_type="routine_pm",
                    asset=scm_asset1,
                    fixed_asset=fixed_asset1,
                    inspector=user,
                    inspection_date=timezone.now() - timezone.timedelta(days=2),
                    scheduled_date=(timezone.now() - timezone.timedelta(days=2)).date(),
                    overall_result="pass",
                    condition_rating=5,
                    meter_reading=Decimal("1420.50"),
                    checklist_summary="Spindle Lubrication: OK\nEmergency Interlocks: PASS\nCoolant Sump Level: 85%\nTelescopic Way Covers: Undamaged",
                    findings_summary="Machine in excellent operating condition. Zero fluid leaks observed.",
                    photo_url="https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=800",
                    photo_caption="Clean spindle head and way cover inspection",
                    voice_notes_transcription="Spindle runout checked with dial indicator, well within 2 micron tolerance.",
                    corrective_action_required=False,
                    gps_latitude=Decimal("37.774929"),
                    gps_longitude=Decimal("-122.419416"),
                    location_accuracy_m=4.2,
                    client_sync_id="c1a2b3c4-mins-001",
                    is_offline_captured=False,
                    status="approved",
                )

                mins2 = MobileAssetInspection.objects.create(
                    tenant=tenant,
                    title="Forklift Pre-Shift Safety & Hydraulic Audit",
                    inspection_type="pre_trip",
                    asset=scm_asset2,
                    fixed_asset=None,
                    inspector=user,
                    inspection_date=timezone.now() - timezone.timedelta(days=1),
                    scheduled_date=(timezone.now() - timezone.timedelta(days=1)).date(),
                    overall_result="conditional_pass",
                    condition_rating=3,
                    meter_reading=Decimal("3820.00"),
                    checklist_summary="Mast Chains: Good\nForks: Undamaged\nTilt Cylinder: Minor seepage\nBrake Response: Normal",
                    findings_summary="Minor hydraulic weeping noticed around tilt cylinder gland nut. Servicing due.",
                    photo_url="https://images.unsplash.com/photo-1581092335397-9583fe92d232?w=800",
                    photo_caption="Trace oil seepage around mast tilt cylinder gland",
                    voice_notes_transcription="Operator reports tilt cylinder gland nut has slight weeping under maximum rated load.",
                    corrective_action_required=True,
                    gps_latitude=Decimal("37.775112"),
                    gps_longitude=Decimal("-122.419985"),
                    location_accuracy_m=6.8,
                    client_sync_id="c1a2b3c4-mins-002",
                    is_offline_captured=True,
                    synced_at=timezone.now() - timezone.timedelta(hours=18),
                    status="submitted",
                )

                mins3 = MobileAssetInspection.objects.create(
                    tenant=tenant,
                    title="Overhead Crane Safety & Hoist Brake Audit",
                    inspection_type="safety_audit",
                    asset=scm_asset1,
                    fixed_asset=fixed_asset1,
                    inspector=user,
                    inspection_date=timezone.now() - timezone.timedelta(hours=6),
                    scheduled_date=timezone.now().date(),
                    overall_result="fail",
                    condition_rating=2,
                    meter_reading=Decimal("9450.25"),
                    checklist_summary="Wire Rope: Fraying detected\nLimit Switch: PASS\nHook Latch: Broken\nMain Brake: Slip under test load",
                    findings_summary="CRITICAL: Wire rope exhibits 4 broken strands near equalizer sheave. Hoist tagged out.",
                    photo_url="https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?w=800",
                    photo_caption="Broken safety hook latch and rope strand fatigue",
                    voice_notes_transcription="Urgent lock-out required immediately. Do not lift loads above 500kg until rope replacement.",
                    corrective_action_required=True,
                    gps_latitude=Decimal("37.774850"),
                    gps_longitude=Decimal("-122.419200"),
                    location_accuracy_m=3.5,
                    client_sync_id="c1a2b3c4-mins-003",
                    is_offline_captured=False,
                    status="under_review",
                )

                # Field Work Orders
                fwo1 = FieldWorkOrder.objects.create(
                    tenant=tenant,
                    title="Preventive Spindle Bearing Lube & Filter Kit Service",
                    work_order_type="scheduled_pm",
                    priority="medium",
                    status="in_progress",
                    asset=scm_asset1,
                    fixed_asset=fixed_asset1,
                    assigned_technician=user,
                    scheduled_start=timezone.now() - timezone.timedelta(hours=4),
                    scheduled_end=timezone.now() + timezone.timedelta(hours=2),
                    actual_arrival=timezone.now() - timezone.timedelta(hours=3, minutes=45),
                    labor_wrench_minutes=150,
                    safety_lockout_confirmed=True,
                    parts_requisition_notes="1x Mobil Vactra #2 Way Oil (5L)\n1x Donaldson Hydraulic Return Filter #P550388\n2x O-Ring Nitrile 70",
                    estimated_parts_cost=Decimal("245.00"),
                    work_performed_notes="Flushed reservoir, replaced return filter element, bled hydraulic manifold. Verifying flow rate.",
                    dispatch_latitude=Decimal("37.774900"),
                    dispatch_longitude=Decimal("-122.419400"),
                    is_offline_captured=False,
                )

                fwo2 = FieldWorkOrder.objects.create(
                    tenant=tenant,
                    title="Emergency Hydraulic Cylinder Seal Replacement",
                    work_order_type="emergency_repair",
                    priority="urgent",
                    status="completed",
                    asset=scm_asset2,
                    fixed_asset=None,
                    assigned_technician=user,
                    scheduled_start=timezone.now() - timezone.timedelta(days=1, hours=8),
                    scheduled_end=timezone.now() - timezone.timedelta(days=1, hours=4),
                    actual_arrival=timezone.now() - timezone.timedelta(days=1, hours=7, minutes=50),
                    completed_at=timezone.now() - timezone.timedelta(days=1, hours=4, minutes=15),
                    labor_wrench_minutes=210,
                    safety_lockout_confirmed=True,
                    parts_requisition_notes="1x Cylinder Gland Packing Kit #CYL-449\n10L Tellus S2 MX 46 Hydraulic Fluid",
                    estimated_parts_cost=Decimal("410.00"),
                    work_performed_notes="Replaced worn rod seal and wiper ring. Torqued gland nut to 180 Nm. Pressure tested to 250 bar with zero leakage.",
                    signature_name="Marcus Vance",
                    signature_designation="Production Floor Supervisor",
                    signed_at=timezone.now() - timezone.timedelta(days=1, hours=4, minutes=10),
                    dispatch_latitude=Decimal("37.775100"),
                    dispatch_longitude=Decimal("-122.419900"),
                    completion_latitude=Decimal("37.775120"),
                    completion_longitude=Decimal("-122.419910"),
                    is_offline_captured=True,
                    synced_at=timezone.now() - timezone.timedelta(days=1, hours=3),
                )

                fwo3 = FieldWorkOrder.objects.create(
                    tenant=tenant,
                    title="Precision Laser Alignment & Calibration",
                    work_order_type="calibration",
                    priority="high",
                    status="dispatched",
                    asset=scm_asset1,
                    fixed_asset=fixed_asset1,
                    assigned_technician=user,
                    scheduled_start=timezone.now() + timezone.timedelta(days=1),
                    scheduled_end=timezone.now() + timezone.timedelta(days=1, hours=4),
                    labor_wrench_minutes=0,
                    safety_lockout_confirmed=False,
                    parts_requisition_notes="1x Fluke Laser Alignment Target Kit\nCalibration Verification Certificate Pack",
                    estimated_parts_cost=Decimal("120.00"),
                    work_performed_notes="Scheduled dispatch for quarterly laser alignment verification.",
                    dispatch_latitude=Decimal("37.774900"),
                    dispatch_longitude=Decimal("-122.419400"),
                    is_offline_captured=False,
                )

                # Scan Logs
                ascn1 = AssetScanLog.objects.create(
                    tenant=tenant,
                    scanned_by=user,
                    scanned_at=timezone.now() - timezone.timedelta(hours=5),
                    scan_context="field_audit",
                    scan_method="camera_qr",
                    raw_payload=f"AST-QR-{scm_asset1.code}",
                    asset=scm_asset1,
                    match_status="matched",
                    gps_latitude=Decimal("37.774929"),
                    gps_longitude=Decimal("-122.419416"),
                    gps_accuracy_m=4.5,
                    device_info="Zebra TC57 Rugged Touch Computer / Android 11",
                    notes="Verified in Bay 3 machining center.",
                )

                ascn2 = AssetScanLog.objects.create(
                    tenant=tenant,
                    scanned_by=user,
                    scanned_at=timezone.now() - timezone.timedelta(hours=3),
                    scan_context="checkout_verification",
                    scan_method="camera_barcode",
                    raw_payload=f"BARC-{scm_asset2.code}-001",
                    asset=scm_asset2,
                    match_status="matched",
                    gps_latitude=Decimal("37.775112"),
                    gps_longitude=Decimal("-122.419985"),
                    gps_accuracy_m=5.1,
                    device_info="Samsung Galaxy Tab Active 4 Pro / Chrome 124",
                    notes="Forklift signed out for warehouse transfer shift.",
                )

                ascn3 = AssetScanLog.objects.create(
                    tenant=tenant,
                    scanned_by=user,
                    scanned_at=timezone.now() - timezone.timedelta(hours=2),
                    scan_context="work_order_init",
                    scan_method="bluetooth_rfid",
                    raw_payload="E2801160600002049A32DF81",
                    asset=scm_asset1,
                    match_status="matched",
                    gps_latitude=Decimal("37.774900"),
                    gps_longitude=Decimal("-122.419400"),
                    gps_accuracy_m=3.0,
                    device_info="Nordic ID EXA51e UHF RFID Reader (Bluetooth)",
                    notes="UHF EPC tag instant interrogation before maintenance.",
                )

                ascn4 = AssetScanLog.objects.create(
                    tenant=tenant,
                    scanned_by=user,
                    scanned_at=timezone.now() - timezone.timedelta(minutes=45),
                    scan_context="receiving",
                    scan_method="camera_barcode",
                    raw_payload="UNREG-TAG-9948271",
                    asset=None,
                    match_status="not_found",
                    gps_latitude=Decimal("37.774700"),
                    gps_longitude=Decimal("-122.419100"),
                    gps_accuracy_m=8.0,
                    device_info="iPhone 14 Pro / Safari Mobile",
                    notes="Unknown vendor crate tag; barcode not registered in NavERP asset database.",
                )

                # Geofence Events
                ageo1 = AssetGeofenceEvent.objects.create(
                    tenant=tenant,
                    asset=scm_asset1,
                    fence_name="Plant 1 Machining Hall Boundary",
                    center_latitude=Decimal("37.774900"),
                    center_longitude=Decimal("-122.419400"),
                    radius_meters=60,
                    recorded_latitude=Decimal("37.774925"),
                    recorded_longitude=Decimal("-122.419410"),
                    recorded_accuracy_m=3.2,
                    distance_from_center_m=3.4,
                    event_type="inside_perimeter",
                    severity="info",
                    status="resolved",
                    detected_at=timezone.now() - timezone.timedelta(hours=8),
                    acknowledged_by=user,
                    acknowledged_at=timezone.now() - timezone.timedelta(hours=7, minutes=50),
                    resolution_notes="Routine daily position ping: asset within authorized CNC cell zone.",
                )

                ageo2 = AssetGeofenceEvent.objects.create(
                    tenant=tenant,
                    asset=scm_asset2,
                    fence_name="Logistics Yard Perimeter",
                    center_latitude=Decimal("37.775100"),
                    center_longitude=Decimal("-122.419900"),
                    radius_meters=120,
                    recorded_latitude=Decimal("37.775950"),
                    recorded_longitude=Decimal("-122.420800"),
                    recorded_accuracy_m=5.0,
                    distance_from_center_m=118.2,
                    event_type="boundary_warning",
                    severity="medium",
                    status="open_alert",
                    detected_at=timezone.now() - timezone.timedelta(hours=2),
                    resolution_notes="Forklift approaching North gate boundary. Driver notified via dashboard.",
                )

                ageo3 = AssetGeofenceEvent.objects.create(
                    tenant=tenant,
                    asset=scm_asset1,
                    fence_name="Equipment Secure Staging Yard",
                    center_latitude=Decimal("37.774800"),
                    center_longitude=Decimal("-122.419200"),
                    radius_meters=100,
                    recorded_latitude=Decimal("37.777200"),
                    recorded_longitude=Decimal("-122.422500"),
                    recorded_accuracy_m=4.1,
                    distance_from_center_m=385.6,
                    event_type="perimeter_exit",
                    severity="critical",
                    status="under_investigation",
                    detected_at=timezone.now() - timezone.timedelta(minutes=30),
                    resolution_notes="ALARM: Asset GPS transponder detected outside secure perimeter without dispatch authorization. Security dispatched to investigate.",
                )

            self.stdout.write(f"[{tenant.name}] 11.13 Seeding complete (3 inspections, 3 work orders, 4 scans, 3 geofence events).")

    def _seed_tenant_11_12(self, tenant):
        # =====================================================================
        # 11.12 Asset Risk Management
        # =====================================================================
        if AssetRiskRegister.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.12 Asset Risk Management already seeded; skipping.")
            return

        today = timezone.now().date()
        user = User.objects.filter(tenant=tenant).first()
        scm_asset1 = Asset.objects.filter(tenant=tenant).first()
        scm_asset2 = Asset.objects.filter(tenant=tenant).order_by("pk")[1] if Asset.objects.filter(tenant=tenant).count() > 1 else scm_asset1
        scm_asset3 = Asset.objects.filter(tenant=tenant).order_by("pk")[2] if Asset.objects.filter(tenant=tenant).count() > 2 else scm_asset1
        cat = AssetCategory.objects.filter(tenant=tenant).first()
        vendor = Party.objects.filter(tenant=tenant, roles__role="vendor").first() or Party.objects.filter(tenant=tenant).first()

        if not scm_asset1:
            self.stdout.write(f"[{tenant.name}] Warning: No SCM assets found; skipping 11.12 risk seeding.")
            return

        with transaction.atomic():
            # 1. Asset Risk Registers
            ark1 = AssetRiskRegister.objects.create(
                tenant=tenant,
                title="Catastrophic Spindle Bearing Seizure on 5-Axis CNC Mill",
                asset=scm_asset1,
                category=cat,
                risk_category="operational",
                threat_source="equipment_wear",
                failure_mode="Bearing cage fatigue leading to thermal seizure and spindle stall",
                description="High spindle thermal runout during continuous titanium milling operations poses catastrophic crash risk.",
                inherent_likelihood=4,
                inherent_impact=4,
                residual_likelihood=2,
                residual_impact=3,
                risk_owner=user,
                treatment_strategy="mitigate",
                financial_exposure_amount=Decimal("85000.00"),
                status="treating",
                review_frequency="monthly",
                next_review_date=today + timezone.timedelta(days=30),
            )
            ark1.calculate_scores()
            ark1.save()

            ark2 = AssetRiskRegister.objects.create(
                tenant=tenant,
                title="OT Network Ransomware Infection via Remote Maintenance Gateway",
                asset=scm_asset2,
                category=cat,
                risk_category="cybersecurity",
                threat_source="cyber_attack",
                failure_mode="Ransomware deployment on supervisory SCADA compromising PLC automation",
                description="Vendor remote diagnostics VPN vulnerable to credential stuffing and OT lateral traversal.",
                inherent_likelihood=3,
                inherent_impact=5,
                residual_likelihood=1,
                residual_impact=4,
                risk_owner=user,
                treatment_strategy="mitigate",
                financial_exposure_amount=Decimal("250000.00"),
                status="assessed",
                review_frequency="quarterly",
                next_review_date=today + timezone.timedelta(days=60),
            )
            ark2.calculate_scores()
            ark2.save()

            ark3 = AssetRiskRegister.objects.create(
                tenant=tenant,
                title="Sole-Source Heavy Forgings Supply Chain Bottleneck",
                asset=scm_asset3,
                category=cat,
                risk_category="geopolitical_supply_chain",
                threat_source="supply_chain_disruption",
                failure_mode="Single tier-1 supplier shutdown halting assembly line for 8 weeks",
                description="Turbine shaft casting supplier experiencing backlog and lead times exceeding 26 weeks.",
                inherent_likelihood=4,
                inherent_impact=3,
                residual_likelihood=2,
                residual_impact=2,
                risk_owner=user,
                treatment_strategy="transfer",
                financial_exposure_amount=Decimal("120000.00"),
                status="identified",
                review_frequency="quarterly",
                next_review_date=today + timezone.timedelta(days=45),
            )
            ark3.calculate_scores()
            ark3.save()

            ark4 = AssetRiskRegister.objects.create(
                tenant=tenant,
                title="High-Pressure Hydraulic Fluid Line Rupture & Environmental Release",
                asset=scm_asset1,
                category=cat,
                risk_category="environmental",
                threat_source="equipment_wear",
                failure_mode="Flexible hose fatigue burst spilling 400L ISO 46 oil into storm drain sump",
                description="Hydraulic power unit operating at 3000 PSI adjacent to exterior storm runoff perimeter.",
                inherent_likelihood=3,
                inherent_impact=3,
                residual_likelihood=1,
                residual_impact=2,
                risk_owner=user,
                treatment_strategy="mitigate",
                financial_exposure_amount=Decimal("45000.00"),
                status="monitored",
                review_frequency="semi_annually",
                next_review_date=today + timezone.timedelta(days=90),
            )
            ark4.calculate_scores()
            ark4.save()

            # 2. Asset Business Continuity Plans
            abc1 = AssetBusinessContinuityPlan.objects.create(
                tenant=tenant,
                title="Emergency Power Substation Diesel Generator Hot Standby BCP",
                primary_asset=scm_asset1,
                backup_redundant_asset=scm_asset2,
                redundancy_type="hot_standby",
                recovery_time_objective_hours=Decimal("0.50"),
                recovery_point_objective_hours=Decimal("0.10"),
                maximum_tolerable_downtime_hours=Decimal("4.00"),
                disaster_scenario="power_grid_outage",
                failover_procedure="1. Automatic transfer switch (ATS) detects utility undervoltage (<90%).\n2. Dual diesel gensets auto-crank within 10 seconds.\n3. Essential bus synchronized and energized within 30 seconds.",
                failback_procedure="1. Utility voltage stable for 15 minutes continuous.\n2. In-phase transfer closed.\n3. Gensets run 5-minute cool-down cycle.",
                alternate_facility_site="Building B Auxiliary Substation Yard",
                critical_spares_required="Fuel filter elements (P/N FF-582), 24V starter battery bank, auto-synchronizer PLC module.",
                emergency_lead=user,
                drill_frequency="quarterly",
                last_drill_date=today - timezone.timedelta(days=45),
                next_drill_date=today + timezone.timedelta(days=45),
                drill_result="passed",
                status="active",
            )

            abc2 = AssetBusinessContinuityPlan.objects.create(
                tenant=tenant,
                title="CNC Milling Cell Warm Standby Failover & Production Reroute",
                primary_asset=scm_asset2,
                backup_redundant_asset=scm_asset1,
                redundancy_type="warm_standby",
                recovery_time_objective_hours=Decimal("2.00"),
                recovery_point_objective_hours=Decimal("0.50"),
                maximum_tolerable_downtime_hours=Decimal("12.00"),
                disaster_scenario="critical_hardware_loss",
                failover_procedure="1. Tooling packages loaded onto secondary 5-axis mill.\n2. CAM post-processor config switched to Machine B kinematics.\n3. First-article CMM inspection performed.",
                failback_procedure="1. Mechanical overhaul completed and 4-hour test cut validated.\n2. Work orders released back to primary spindle.",
                alternate_facility_site="Machine Shop Bay 2",
                critical_spares_required="HSK-A63 spindle cartridges, Renishaw probe stylus, Siemens 840D drive module.",
                emergency_lead=user,
                drill_frequency="semi_annually",
                last_drill_date=today - timezone.timedelta(days=120),
                next_drill_date=today + timezone.timedelta(days=60),
                drill_result="passed_with_deficiencies",
                status="active",
            )

            abc3 = AssetBusinessContinuityPlan.objects.create(
                tenant=tenant,
                title="Industrial Steam Boiler Disaster Recovery Plan (Single Point of Failure)",
                primary_asset=scm_asset3,
                backup_redundant_asset=None,
                redundancy_type="none_single_point_of_failure",
                recovery_time_objective_hours=Decimal("72.00"),
                recovery_point_objective_hours=Decimal("4.00"),
                maximum_tolerable_downtime_hours=Decimal("96.00"),
                disaster_scenario="fire_explosion",
                failover_procedure="1. Emergency manual trip and fuel isolation.\n2. Call Nationwide Boiler emergency mobile steam dispatch (SLA contract #NB-942).\n3. Hook up temporary steam header and potable feedwater line.",
                failback_procedure="1. ASME boiler inspector clearance certificate.\n2. Hydrostatic pressure re-certification.\n3. Transition valve manifold back to plant boiler.",
                alternate_facility_site="Exterior Boiler Pad Mobile Hookup",
                critical_spares_required="Flexible 4-inch steam hoses, pressure relief safety valves, feedwater pumps.",
                emergency_lead=user,
                drill_frequency="annually",
                drill_result="not_tested",
                status="draft",
            )

            # 3. Asset Cyber Security Profiles
            acs1 = AssetCyberSecurityProfile.objects.create(
                tenant=tenant,
                asset=scm_asset1,
                device_type="plc_controller",
                ip_address="192.168.10.45",
                mac_address="00:1B:1B:3A:42:01",
                network_zone="control_plc",
                firmware_version="V4.2.1",
                latest_available_firmware="V4.3.0",
                firmware_update_status="update_available",
                protocol_used="modbus_tcp",
                exposure_level="isolated_vlan",
                known_vulnerabilities_cve="CVE-2024-21887: Modbus stack buffer overflow under crafted TCP packet payload",
                cve_risk_score=Decimal("6.8"),
                compensating_controls="Strict firewall rule blocking external ingress; OT DPI filter drop on non-whitelisted function codes.",
                last_vulnerability_scan_date=today - timezone.timedelta(days=15),
                security_posture_status="attention_required",
                patch_freeze_until=today + timezone.timedelta(days=30),
            )

            acs2 = AssetCyberSecurityProfile.objects.create(
                tenant=tenant,
                asset=scm_asset2,
                device_type="scada_server",
                ip_address="10.20.1.15",
                mac_address="00:50:56:A2:3F:89",
                network_zone="supervisory_scada",
                firmware_version="2024.1.2",
                latest_available_firmware="2024.1.2",
                firmware_update_status="up_to_date",
                protocol_used="opc_ua",
                exposure_level="monitored_dmz",
                known_vulnerabilities_cve="None. Baseline patched to latest certified release.",
                cve_risk_score=Decimal("0.0"),
                compensating_controls="EDR sensor active, MFA for all RDP sessions, SIEM syslog forwarder.",
                last_vulnerability_scan_date=today - timezone.timedelta(days=5),
                security_posture_status="secure",
            )

            acs3 = AssetCyberSecurityProfile.objects.create(
                tenant=tenant,
                asset=scm_asset3,
                device_type="iot_sensor",
                ip_address="192.168.30.102",
                mac_address="B8:27:EB:14:8A:23",
                network_zone="process_io",
                firmware_version="1.0.4",
                latest_available_firmware="1.2.0",
                firmware_update_status="critical_patch_pending",
                protocol_used="mqtt",
                exposure_level="isolated_vlan",
                known_vulnerabilities_cve="CVE-2023-4863: Heap buffer overflow in WebP and embedded MQTT parser.",
                cve_risk_score=Decimal("8.8"),
                compensating_controls="Isolated micro-segment with zero internet egress; TLS mutual authentication enforced.",
                last_vulnerability_scan_date=today - timezone.timedelta(days=20),
                security_posture_status="vulnerable",
            )

            # 4. Asset Risk Mitigation Actions
            arma1 = AssetRiskMitigationAction.objects.create(
                tenant=tenant,
                title="Install Wireless Vibration & Temperature Telemetry Sensors on Spindle",
                risk=ark1,
                action_type="preventive_inspection",
                priority="critical",
                description="Mount tri-axial high-frequency piezoelectric accelerometers on spindle front and rear bearings with automated threshold alerting.",
                assigned_to=user,
                alternative_supplier=None,
                target_completion_date=today + timezone.timedelta(days=14),
                estimated_cost=Decimal("6500.00"),
                actual_cost=Decimal("6200.00"),
                status="verified_effective",
                actual_completion_date=today - timezone.timedelta(days=2),
                effectiveness_rating="highly_effective",
                verification_notes="Sensors transmitting 10-minute FFT spectra to asset health dashboard. Bearing baseline established.",
            )

            arma2 = AssetRiskMitigationAction.objects.create(
                tenant=tenant,
                title="Implement Zero-Trust OT Gateway with Hardware Key MFA for Vendor Access",
                risk=ark2,
                action_type="firmware_security_patch",
                priority="high",
                description="Replace legacy PPTP/IPsec vendor tunnel with Claroty SRA zero-trust proxy requiring hardware FIDO2 tokens.",
                assigned_to=user,
                alternative_supplier=None,
                target_completion_date=today + timezone.timedelta(days=30),
                estimated_cost=Decimal("14500.00"),
                actual_cost=Decimal("0.00"),
                status="in_progress",
                effectiveness_rating="pending_evaluation",
            )

            arma3 = AssetRiskMitigationAction.objects.create(
                tenant=tenant,
                title="Qualify Secondary Tier-1 Forgings Supplier with Approved First-Article",
                risk=ark3,
                action_type="supplier_diversification",
                priority="high",
                description="Audit and certify secondary forging vendor for turbine shaft casting. Negotiate 30-day emergency stocking reserve.",
                assigned_to=user,
                alternative_supplier=vendor,
                target_completion_date=today + timezone.timedelta(days=60),
                estimated_cost=Decimal("22000.00"),
                actual_cost=Decimal("0.00"),
                status="planned",
                effectiveness_rating="pending_evaluation",
            )

            arma4 = AssetRiskMitigationAction.objects.create(
                tenant=tenant,
                title="Install Heavy-Duty Double-Braided Hydraulic Hoses with Containment Shrouds",
                risk=ark4,
                action_type="engineering_control",
                priority="medium",
                description="Retrofit all high-pressure flexible lines with MSHA-certified bursting sleeves and auto-shutoff check valves.",
                assigned_to=user,
                alternative_supplier=None,
                target_completion_date=today + timezone.timedelta(days=21),
                estimated_cost=Decimal("4800.00"),
                actual_cost=Decimal("4650.00"),
                status="completed",
                actual_completion_date=today - timezone.timedelta(days=1),
                effectiveness_rating="partially_effective",
                verification_notes="Burst sleeve containment installed; awaiting secondary sump float switch installation next week.",
            )

        self.stdout.write(f"[{tenant.name}] 11.12 Seeding complete (4 risk registers, 3 continuity plans, 3 cyber profiles, 4 mitigation actions).")

