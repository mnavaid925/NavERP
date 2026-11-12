from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset, FiscalPeriod, GLAccount, JournalEntry, JournalLine
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
    AssetIntegrationConnector,
    AssetTelemetryStream,
    AssetGlSyncBatch,
    AssetGisMapping,
    AssetExecutiveScorecard,
    AssetLifecycleCostAnalysis,
    AssetPortfolioScenario,
    AssetReplacementPlan,
    AssetDocument,
    AssetOperatingProcedure,
    AssetOperatorCertification,
    AssetKnowledgeArticle,
    AssetFacilitySpace,
    AssetBuildingSystem,
    AssetFurnitureFixture,
    AssetSpaceChargeback,
    CloudAssetSubscription,
    CmdbRelationship,
    ItHardwareAsset,
    SoftwareLicense,
)
from apps.core.models import OrgUnit, Party, Tenant
from apps.core.models.Monitoring import ServiceComponent
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
            CmdbRelationship.objects.all().delete()
            CloudAssetSubscription.objects.all().delete()
            SoftwareLicense.objects.all().delete()
            ItHardwareAsset.objects.all().delete()
            AssetSpaceChargeback.objects.all().delete()
            AssetFurnitureFixture.objects.all().delete()
            AssetBuildingSystem.objects.all().delete()
            AssetFacilitySpace.objects.all().update(parent=None)
            AssetFacilitySpace.objects.all().delete()
            AssetKnowledgeArticle.objects.all().delete()
            AssetOperatorCertification.objects.all().delete()
            AssetOperatingProcedure.objects.all().delete()
            AssetDocument.objects.all().delete()
            AssetGisMapping.objects.all().delete()
            AssetGlSyncBatch.objects.all().delete()
            AssetTelemetryStream.objects.all().delete()
            AssetIntegrationConnector.objects.all().delete()
            AssetGeofenceEvent.objects.all().delete()
            AssetScanLog.objects.all().delete()
            FieldWorkOrder.objects.all().delete()
            MobileAssetInspection.objects.all().delete()
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
            AssetExecutiveScorecard.objects.all().delete()
            AssetPortfolioScenario.objects.all().delete()
            AssetReplacementPlan.objects.all().delete()
            AssetLifecycleCostAnalysis.objects.all().delete()
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
            self._seed_tenant_11_14(tenant)
            self._seed_tenant_11_15(tenant)
            self._seed_tenant_11_16(tenant)
            self._seed_tenant_11_17(tenant)
            self._seed_tenant_11_18(tenant)

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
            return

        scm_asset1 = Asset.objects.filter(tenant=tenant).first()
        scm_asset2 = Asset.objects.filter(tenant=tenant).order_by("pk")[1] if Asset.objects.filter(tenant=tenant).count() > 1 else scm_asset1

        if not scm_asset1:
            self.stdout.write(f"[{tenant.name}] Warning: No SCM assets found; skipping 11.13 mobile seeding.")
            return

        with transaction.atomic():
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
        assets_pool = list(Asset.objects.filter(tenant=tenant).order_by("pk")[:3])
        if not assets_pool:
            self.stdout.write(f"[{tenant.name}] Warning: No SCM assets found; skipping 11.12 risk seeding.")
            return

        scm_asset1 = assets_pool[0]
        scm_asset2 = assets_pool[1] if len(assets_pool) > 1 else scm_asset1
        scm_asset3 = assets_pool[2] if len(assets_pool) > 2 else scm_asset1
        cat = AssetCategory.objects.filter(tenant=tenant).first()
        vendor = Party.objects.filter(tenant=tenant, roles__role="vendor").first() or Party.objects.filter(tenant=tenant).first()

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

    def _seed_tenant_11_14(self, tenant):
        if AssetLifecycleCostAnalysis.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.14 Asset Analytics & BI data already seeded, skipping.")
            return

        from apps.assets.models.AssetReliability.AssetConditionAssessments import (
            AssetConditionAssessment,
        )

        self.stdout.write(f"[{tenant.name}] Seeding 11.14 Asset Analytics & BI...")
        today = timezone.now().date()
        user = User.objects.filter(tenant=tenant).order_by("id").first()
        approver = (
            User.objects.filter(tenant=tenant).exclude(pk=user.pk).order_by("id").first()
            if user
            else None
        )
        currency = Currency.objects.filter(is_active=True).order_by("code").first()
        org_unit = OrgUnit.objects.filter(tenant=tenant).first()
        location = Location.objects.filter(tenant=tenant).first()
        categories = list(AssetCategory.objects.filter(tenant=tenant).order_by("id")[:3])
        cat1 = categories[0] if len(categories) > 0 else None
        cat2 = categories[1] if len(categories) > 1 else cat1
        cat3 = categories[2] if len(categories) > 2 else cat1
        asset_model = AssetModel.objects.filter(tenant=tenant).order_by("id").first()
        fixed_assets = list(FixedAsset.objects.filter(tenant=tenant).order_by("id")[:3])
        fa1 = fixed_assets[0] if len(fixed_assets) > 0 else None
        fa2 = fixed_assets[1] if len(fixed_assets) > 1 else fa1
        fa3 = fixed_assets[2] if len(fixed_assets) > 2 else fa1
        op_assets = list(Asset.objects.filter(tenant=tenant).order_by("code")[:3])
        op1 = op_assets[0] if len(op_assets) > 0 else None
        op2 = op_assets[1] if len(op_assets) > 1 else op1
        op3 = op_assets[2] if len(op_assets) > 2 else op1
        cond = AssetConditionAssessment.objects.filter(tenant=tenant).order_by("id").first()
        req = AssetRequisition.objects.filter(tenant=tenant).order_by("id").first()

        with transaction.atomic():
            lcca_1 = AssetLifecycleCostAnalysis(
                tenant=tenant,
                title="CNC Machining Center — 7-Yr Lifecycle TCO Study",
                fixed_asset=fa1,
                operational_asset=op1,
                asset_category=cat1,
                asset_model=asset_model,
                org_unit=org_unit,
                currency=currency,
                analyzed_by=user,
                analysis_date=today - timezone.timedelta(days=14),
                analysis_horizon_years=7,
                discount_rate_pct=Decimal("8.00"),
                lifecycle_stage="mid_life",
                status="approved",
                acquisition_capital_cost=Decimal("185000.00"),
                installation_commissioning_cost=Decimal("22500.00"),
                preventive_maintenance_cost=Decimal("24500.00"),
                corrective_maintenance_cost=Decimal("18900.00"),
                service_contract_cost=Decimal("12000.00"),
                energy_utility_cost=Decimal("16400.00"),
                downtime_opportunity_cost=Decimal("11200.00"),
                insurance_compliance_cost=Decimal("4800.00"),
                accumulated_depreciation_cost=Decimal("82000.00"),
                expected_salvage_value=Decimal("28000.00"),
                warranty_insurance_recoveries=Decimal("3500.00"),
                current_replacement_value=Decimal("235000.00"),
                notes="Baseline spindle & servo maintenance within healthy MCR threshold (<25%).",
            )
            lcca_1.save()

            lcca_2 = AssetLifecycleCostAnalysis(
                tenant=tenant,
                title="Plant Chiller & HVAC Cooling Train — Late-Life TCO Review",
                fixed_asset=fa2,
                operational_asset=op2,
                asset_category=cat2,
                asset_model=asset_model,
                org_unit=org_unit,
                currency=currency,
                analyzed_by=user,
                analysis_date=today - timezone.timedelta(days=10),
                analysis_horizon_years=10,
                discount_rate_pct=Decimal("8.50"),
                lifecycle_stage="late_life",
                status="reviewed",
                acquisition_capital_cost=Decimal("140000.00"),
                installation_commissioning_cost=Decimal("18000.00"),
                preventive_maintenance_cost=Decimal("31000.00"),
                corrective_maintenance_cost=Decimal("48500.00"),
                service_contract_cost=Decimal("14500.00"),
                energy_utility_cost=Decimal("29800.00"),
                downtime_opportunity_cost=Decimal("24000.00"),
                insurance_compliance_cost=Decimal("3900.00"),
                accumulated_depreciation_cost=Decimal("118000.00"),
                expected_salvage_value=Decimal("12000.00"),
                warranty_insurance_recoveries=Decimal("0.00"),
                current_replacement_value=Decimal("165000.00"),
                notes="Maintenance-to-RAV exceeds 55% with rising compressor failures; schedule replacement.",
            )
            lcca_2.save()

            lcca_3 = AssetLifecycleCostAnalysis(
                tenant=tenant,
                title="Warehouse Electric Forklift Fleet — Overhaul vs Replace",
                fixed_asset=fa3,
                operational_asset=op3,
                asset_category=cat3,
                org_unit=org_unit,
                currency=currency,
                analyzed_by=user,
                analysis_date=today - timezone.timedelta(days=5),
                analysis_horizon_years=5,
                discount_rate_pct=Decimal("7.50"),
                lifecycle_stage="in_service",
                status="calculated",
                acquisition_capital_cost=Decimal("96000.00"),
                installation_commissioning_cost=Decimal("4500.00"),
                preventive_maintenance_cost=Decimal("14200.00"),
                corrective_maintenance_cost=Decimal("11800.00"),
                service_contract_cost=Decimal("4200.00"),
                energy_utility_cost=Decimal("6800.00"),
                downtime_opportunity_cost=Decimal("5100.00"),
                insurance_compliance_cost=Decimal("2400.00"),
                accumulated_depreciation_cost=Decimal("38000.00"),
                expected_salvage_value=Decimal("19500.00"),
                warranty_insurance_recoveries=Decimal("2200.00"),
                current_replacement_value=Decimal("112000.00"),
                notes="Battery pack refurbishment extends useful life by 36 months.",
            )
            lcca_3.save()

            lcca_4 = AssetLifecycleCostAnalysis(
                tenant=tenant,
                title="Legacy Diesel Standby Generator — End-of-Life Retirement",
                fixed_asset=fa1,
                operational_asset=op1,
                asset_category=cat1,
                org_unit=org_unit,
                currency=currency,
                analyzed_by=user,
                analysis_date=today - timezone.timedelta(days=2),
                analysis_horizon_years=5,
                discount_rate_pct=Decimal("8.00"),
                lifecycle_stage="end_of_life",
                status="draft",
                acquisition_capital_cost=Decimal("78000.00"),
                installation_commissioning_cost=Decimal("9500.00"),
                preventive_maintenance_cost=Decimal("18000.00"),
                corrective_maintenance_cost=Decimal("41000.00"),
                service_contract_cost=Decimal("8500.00"),
                energy_utility_cost=Decimal("19400.00"),
                downtime_opportunity_cost=Decimal("27500.00"),
                insurance_compliance_cost=Decimal("3100.00"),
                accumulated_depreciation_cost=Decimal("76000.00"),
                expected_salvage_value=Decimal("6500.00"),
                warranty_insurance_recoveries=Decimal("0.00"),
                current_replacement_value=Decimal("95000.00"),
                notes="Tier-2 emissions unit exceeding economic repair threshold.",
            )
            lcca_4.save()

            rpl_1 = AssetReplacementPlan(
                tenant=tenant,
                title="Primary Plant Chiller Train Replacement (FY+1)",
                fixed_asset=fa2,
                operational_asset=op2,
                asset_category=cat2,
                asset_model=asset_model,
                org_unit=org_unit,
                location=location,
                currency=currency,
                condition_assessment=cond,
                lifecycle_analysis=lcca_2,
                linked_requisition=req,
                planner=user,
                predicted_eol_date=today + timezone.timedelta(days=210),
                remaining_useful_life_months=7,
                planned_replacement_year=today.year + 1,
                planned_quarter="q1",
                replacement_strategy="technology_upgrade",
                funding_status="budget_allocated",
                status="approved",
                condition_score=Decimal("32.00"),
                criticality_weight=9,
                failure_risk_score=Decimal("84.00"),
                current_replacement_value=Decimal("165000.00"),
                deferred_maintenance_cost=Decimal("48500.00"),
                estimated_replacement_cost=Decimal("172000.00"),
                inflation_rate_pct=Decimal("4.50"),
                estimated_salvage_recovery=Decimal("12000.00"),
                deferral_penalty_cost=Decimal("26500.00"),
                notes="Variable-speed magnetic-bearing chiller upgrade cutting HVAC kWh by 24%.",
            )
            rpl_1.save()

            rpl_2 = AssetReplacementPlan(
                tenant=tenant,
                title="Legacy Diesel Standby Generator Tier-4 Swap",
                fixed_asset=fa1,
                operational_asset=op1,
                asset_category=cat1,
                org_unit=org_unit,
                location=location,
                currency=currency,
                lifecycle_analysis=lcca_4,
                planner=user,
                predicted_eol_date=today + timezone.timedelta(days=150),
                remaining_useful_life_months=5,
                planned_replacement_year=today.year + 1,
                planned_quarter="q2",
                replacement_strategy="consolidate_retire",
                funding_status="unfunded",
                status="proposed",
                condition_score=Decimal("24.00"),
                criticality_weight=8,
                failure_risk_score=Decimal("88.00"),
                current_replacement_value=Decimal("95000.00"),
                deferred_maintenance_cost=Decimal("41000.00"),
                estimated_replacement_cost=Decimal("108000.00"),
                inflation_rate_pct=Decimal("4.00"),
                estimated_salvage_recovery=Decimal("6500.00"),
                deferral_penalty_cost=Decimal("21000.00"),
                notes="High unfunded backlog priority; environmental compliance deadline approaching.",
            )
            rpl_2.save()

            rpl_3 = AssetReplacementPlan(
                tenant=tenant,
                title="Warehouse Electric Forklift Lithium Refresh Wave 2",
                fixed_asset=fa3,
                operational_asset=op3,
                asset_category=cat3,
                org_unit=org_unit,
                location=location,
                currency=currency,
                lifecycle_analysis=lcca_3,
                planner=user,
                predicted_eol_date=today + timezone.timedelta(days=540),
                remaining_useful_life_months=18,
                planned_replacement_year=today.year + 2,
                planned_quarter="q3",
                replacement_strategy="technology_upgrade",
                funding_status="requested",
                status="forecasted",
                condition_score=Decimal("58.00"),
                criticality_weight=6,
                failure_risk_score=Decimal("45.00"),
                current_replacement_value=Decimal("112000.00"),
                deferred_maintenance_cost=Decimal("18500.00"),
                estimated_replacement_cost=Decimal("118000.00"),
                inflation_rate_pct=Decimal("3.80"),
                estimated_salvage_recovery=Decimal("19500.00"),
                deferral_penalty_cost=Decimal("8400.00"),
                notes="Phased lithium-ion battery transition eliminating lead-acid charging bay.",
            )
            rpl_3.save()

            rpl_4 = AssetReplacementPlan(
                tenant=tenant,
                title="CNC Spindle & Servo Precision Rebuild Program",
                fixed_asset=fa1,
                operational_asset=op1,
                asset_category=cat1,
                org_unit=org_unit,
                location=location,
                currency=currency,
                lifecycle_analysis=lcca_1,
                planner=user,
                predicted_eol_date=today + timezone.timedelta(days=900),
                remaining_useful_life_months=30,
                planned_replacement_year=today.year + 3,
                planned_quarter="q4",
                replacement_strategy="refurbish_extend",
                funding_status="deferred",
                status="deferred",
                condition_score=Decimal("71.00"),
                criticality_weight=7,
                failure_risk_score=Decimal("34.00"),
                current_replacement_value=Decimal("235000.00"),
                deferred_maintenance_cost=Decimal("19200.00"),
                estimated_replacement_cost=Decimal("64000.00"),
                inflation_rate_pct=Decimal("3.50"),
                estimated_salvage_recovery=Decimal("4000.00"),
                deferral_penalty_cost=Decimal("6200.00"),
                notes="Scheduled mid-life OEM spindle rebuild to defer full machine CapEx 5 years.",
            )
            rpl_4.save()

            scen_base = AssetPortfolioScenario(
                tenant=tenant,
                name="5-Year Business-As-Usual Capital Baseline",
                scenario_type="baseline_bau",
                is_baseline=True,
                base_fiscal_year=today.year,
                horizon_years=5,
                scope_org_unit=org_unit,
                currency=currency,
                owner=user,
                status="draft",
                annual_capex_budget_limit=Decimal("150000.00"),
                discount_rate_pct=Decimal("8.00"),
                inflation_rate_pct=Decimal("4.00"),
                assumptions_summary="Follows current multi-year CIP cadence without acceleration or budget freeze.",
            )
            scen_base.save()
            scen_base.run_simulation(save=False)
            scen_base.status = "adopted"
            scen_base.save()

            scen_accel = AssetPortfolioScenario(
                tenant=tenant,
                name="Accelerated Reliability & Early EOL Replacement",
                scenario_type="accelerated_replacement",
                is_baseline=False,
                baseline_scenario=scen_base,
                base_fiscal_year=today.year,
                horizon_years=5,
                scope_org_unit=org_unit,
                currency=currency,
                owner=user,
                status="draft",
                annual_capex_budget_limit=Decimal("220000.00"),
                discount_rate_pct=Decimal("8.00"),
                inflation_rate_pct=Decimal("4.00"),
                acceleration_months=12,
                maintenance_efficiency_gain_pct=Decimal("18.00"),
                assumptions_summary="Front-loads critical chiller and generator replacements by 12 months to capture 18% OpEx reduction.",
            )
            scen_accel.save()
            scen_accel.run_simulation(save=False)
            scen_accel.status = "recommended"
            scen_accel.save()

            scen_cap = AssetPortfolioScenario(
                tenant=tenant,
                name="Constrained CapEx Ceiling (-25% Capital Freeze)",
                scenario_type="budget_constrained",
                is_baseline=False,
                baseline_scenario=scen_base,
                base_fiscal_year=today.year,
                horizon_years=5,
                scope_org_unit=org_unit,
                currency=currency,
                owner=user,
                status="draft",
                annual_capex_budget_limit=Decimal("90000.00"),
                discount_rate_pct=Decimal("8.00"),
                inflation_rate_pct=Decimal("4.50"),
                assumptions_summary="Models impact of capping annual replacement CapEx at 90k/yr on deferred backlog and FCI.",
            )
            scen_cap.save()
            scen_cap.run_simulation(save=False)
            scen_cap.status = "under_review"
            scen_cap.save()

            kpi_board = AssetExecutiveScorecard(
                tenant=tenant,
                title="Quarterly Board Asset Portfolio KPI Scorecard",
                period_type="quarterly",
                period_start=today - timezone.timedelta(days=90),
                period_end=today,
                org_unit=org_unit,
                currency=currency,
                prepared_by=user,
                approved_by=approver,
                status="draft",
                annual_asset_return_amount=Decimal("95000.00"),
                target_asset_roi_pct=Decimal("12.00"),
                target_mcr_pct=Decimal("3.50"),
                target_compliance_rate_pct=Decimal("95.00"),
                executive_summary="Frozen quarterly board brief benchmarking portfolio ROI, MCR %, FCI %, and open compliance risk.",
            )
            kpi_board.save()
            kpi_board.compute_from_live_portfolio(save=False)
            kpi_board.status = "board_approved"
            kpi_board.save()

            kpi_ytd = AssetExecutiveScorecard(
                tenant=tenant,
                title="YTD Executive Asset BI & Capital Backlog Brief",
                period_type="ytd",
                period_start=today.replace(month=1, day=1),
                period_end=today,
                org_unit=org_unit,
                currency=currency,
                prepared_by=user,
                status="draft",
                annual_asset_return_amount=Decimal("112000.00"),
                target_asset_roi_pct=Decimal("12.50"),
                target_mcr_pct=Decimal("3.20"),
                target_compliance_rate_pct=Decimal("96.00"),
                executive_summary="Working YTD KPI draft ready for live portfolio refresh and CFO publication.",
            )
            kpi_ytd.save()
            kpi_ytd.compute_from_live_portfolio(save=True)

        self.stdout.write(f"[{tenant.name}] 11.14 Seeding complete (4 LCC analyses, 4 replacement plans, 3 scenarios, 2 scorecards).")

    def _seed_tenant_11_15(self, tenant):
        if AssetIntegrationConnector.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.15 Integration & API Hub data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.15 Integration & API Hub...")
        today = timezone.now().date()
        now = timezone.now()
        user = User.objects.filter(tenant=tenant).first()
        currency = Currency.objects.filter(is_active=True).order_by("code").first()
        org_unit = OrgUnit.objects.filter(tenant=tenant).first()
        location = Location.objects.filter(tenant=tenant).first()
        vendor = (
            Party.objects.filter(tenant=tenant, roles__role__in=["vendor", "supplier"]).first()
            or Party.objects.filter(tenant=tenant).first()
        )
        fixed_asset = FixedAsset.objects.filter(tenant=tenant).first()
        op_assets = list(Asset.objects.filter(tenant=tenant).order_by("code")[:3])
        op1 = op_assets[0] if len(op_assets) > 0 else None
        op2 = op_assets[1] if len(op_assets) > 1 else op1
        op3 = op_assets[2] if len(op_assets) > 2 else op1
        gl_accounts = list(GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("code")[:2])
        gl_dr = gl_accounts[0] if len(gl_accounts) >= 1 else None
        gl_cr = gl_accounts[1] if len(gl_accounts) >= 2 else None
        fiscal_period = FiscalPeriod.objects.filter(tenant=tenant, status="open").first()
        po = PurchaseOrder.objects.filter(tenant=tenant).first()
        cap = AssetCapitalization.objects.filter(tenant=tenant).first()
        dep = AssetDepreciationSchedule.objects.filter(tenant=tenant).first()
        maint = AssetMaintenanceRequest.objects.filter(tenant=tenant).first()

        with transaction.atomic():
            c_erp = AssetIntegrationConnector(
                tenant=tenant,
                name="SAP S/4HANA Asset & Procurement Sync",
                connector_category="erp_procurement",
                provider="sap_s4hana",
                protocol="odata_v4",
                sync_direction="bidirectional",
                environment="production",
                endpoint_url="https://sap-s4-api.example.com/sap/opu/odata4/sap/api_fixedasset",
                auth_method="oauth2_client",
                rate_limit_rpm=300,
                timeout_seconds=30,
                retry_policy_max=3,
                polling_interval_minutes=15,
                status="active",
                health_status="healthy",
                vendor_partner=vendor,
                default_org_unit=org_unit,
                default_currency=currency,
                owner=user,
                last_heartbeat_at=now - timezone.timedelta(minutes=5),
                webhook_verify_tls=True,
                notes="Primary ERP subledger and PO asset clearing gateway.",
            )
            c_erp.issue_new_secret()
            c_erp.save()

            c_iot = AssetIntegrationConnector(
                tenant=tenant,
                name="Kepware OPC-UA Plant SCADA Concentrator",
                connector_category="iot_scada",
                provider="kepware_opcua",
                protocol="opc_ua",
                sync_direction="inbound",
                environment="production",
                endpoint_url="opc.tcp://scada-gw.example.com:4840/naverp/plant1",
                auth_method="mtls_cert",
                rate_limit_rpm=1200,
                timeout_seconds=15,
                retry_policy_max=5,
                polling_interval_minutes=1,
                status="active",
                health_status="healthy",
                vendor_partner=vendor,
                default_org_unit=org_unit,
                default_currency=currency,
                owner=user,
                last_heartbeat_at=now - timezone.timedelta(minutes=2),
                webhook_verify_tls=True,
                notes="High-frequency rotating equipment telemetry feed.",
            )
            c_iot.issue_new_secret()
            c_iot.save()

            c_cmms = AssetIntegrationConnector(
                tenant=tenant,
                name="IBM Maximo Field Work Order Bridge",
                connector_category="cmms_eam",
                provider="maximo_eam",
                protocol="rest_json",
                sync_direction="bidirectional",
                environment="staging",
                endpoint_url="https://maximo.example.com/maximo/api/os/mxwo",
                auth_method="api_key",
                rate_limit_rpm=180,
                timeout_seconds=30,
                retry_policy_max=3,
                polling_interval_minutes=10,
                status="active",
                health_status="degraded",
                vendor_partner=vendor,
                default_org_unit=org_unit,
                default_currency=currency,
                owner=user,
                last_heartbeat_at=now - timezone.timedelta(hours=1),
                webhook_verify_tls=True,
                notes="Synchronizes dispatch status and failure codes with regional EAM crews.",
            )
            c_cmms.issue_new_secret()
            c_cmms.save()

            c_gl = AssetIntegrationConnector(
                tenant=tenant,
                name="Oracle Fusion General Ledger Posting Hub",
                connector_category="financial_gl",
                provider="oracle_fusion",
                protocol="rest_json",
                sync_direction="outbound",
                environment="production",
                endpoint_url="https://oracle-erp.example.com/fscmRestApi/resources/latest/journalBatches",
                auth_method="hmac_sha256",
                rate_limit_rpm=120,
                timeout_seconds=45,
                retry_policy_max=3,
                polling_interval_minutes=60,
                status="active",
                health_status="healthy",
                vendor_partner=vendor,
                default_org_unit=org_unit,
                default_currency=currency,
                owner=user,
                last_heartbeat_at=now - timezone.timedelta(minutes=20),
                webhook_verify_tls=True,
                notes="Month-end depreciation and capitalization GL batch settlement.",
            )
            c_gl.issue_new_secret()
            c_gl.save()

            c_gis = AssetIntegrationConnector(
                tenant=tenant,
                name="Esri ArcGIS Enterprise Feature Service",
                connector_category="gis_spatial",
                provider="esri_arcgis",
                protocol="arcgis_feature_svc",
                sync_direction="bidirectional",
                environment="production",
                endpoint_url="https://gis-portal.example.com/arcgis/rest/services/UtilitiesAssets/FeatureServer",
                auth_method="oauth2_client",
                rate_limit_rpm=240,
                timeout_seconds=30,
                retry_policy_max=2,
                polling_interval_minutes=30,
                status="active",
                health_status="healthy",
                vendor_partner=vendor,
                default_org_unit=org_unit,
                default_currency=currency,
                owner=user,
                last_heartbeat_at=now - timezone.timedelta(minutes=10),
                webhook_verify_tls=True,
                notes="Spatial polygon & LRS utility corridor layer sync.",
            )
            c_gis.issue_new_secret()
            c_gis.save()

            if op1 is not None or fixed_asset is not None:
                AssetTelemetryStream.objects.create(
                    tenant=tenant,
                    connector=c_iot,
                    operational_asset=op1,
                    fixed_asset=fixed_asset,
                    tag_address="ns=2;s=Line1.Spindle01.BearingTempC",
                    stream_name="Primary Spindle Bearing Temperature",
                    stream_protocol="opc_ua_node",
                    metric_type="bearing_temperature",
                    metric_unit="celsius",
                    ingestion_mode="polling",
                    polling_interval_seconds=30,
                    deadband_delta=Decimal("0.5000"),
                    scale_factor=Decimal("1.000000"),
                    offset_value=Decimal("0.0000"),
                    baseline_value=Decimal("52.0000"),
                    warning_threshold=Decimal("78.0000"),
                    critical_threshold=Decimal("92.0000"),
                    auto_trigger_maintenance=True,
                    stream_status="active",
                    steward=user,
                )
                AssetTelemetryStream.objects.create(
                    tenant=tenant,
                    connector=c_iot,
                    operational_asset=op2,
                    fixed_asset=fixed_asset,
                    tag_address="plant1/compressors/comp02/vibration_rms",
                    stream_name="Compressor #2 Housing Vibration RMS",
                    stream_protocol="mqtt_topic",
                    metric_type="vibration_velocity_rms",
                    metric_unit="mm_per_s",
                    ingestion_mode="streaming_pubsub",
                    polling_interval_seconds=10,
                    deadband_delta=Decimal("0.1000"),
                    scale_factor=Decimal("1.000000"),
                    offset_value=Decimal("0.0000"),
                    baseline_value=Decimal("2.1000"),
                    warning_threshold=Decimal("4.5000"),
                    critical_threshold=Decimal("7.1000"),
                    auto_trigger_maintenance=True,
                    stream_status="active",
                    steward=user,
                )
                AssetTelemetryStream.objects.create(
                    tenant=tenant,
                    connector=c_iot,
                    operational_asset=op3,
                    fixed_asset=fixed_asset,
                    tag_address="40012@PLC-GEN-04",
                    stream_name="Standby Generator Load Amperage",
                    stream_protocol="modbus_register",
                    metric_type="motor_current_amperage",
                    metric_unit="amperes",
                    ingestion_mode="polling",
                    polling_interval_seconds=60,
                    deadband_delta=Decimal("1.0000"),
                    scale_factor=Decimal("0.100000"),
                    offset_value=Decimal("0.0000"),
                    baseline_value=Decimal("110.0000"),
                    warning_threshold=Decimal("165.0000"),
                    critical_threshold=Decimal("195.0000"),
                    auto_trigger_maintenance=False,
                    stream_status="paused",
                    steward=user,
                )
                AssetTelemetryStream.objects.create(
                    tenant=tenant,
                    connector=c_iot,
                    operational_asset=op1,
                    fixed_asset=fixed_asset,
                    tag_address="PI:\\PLANT1\\TURBINE_01.RUN_HRS",
                    stream_name="CNC Turbine Operating Hours Counter",
                    stream_protocol="pi_tag",
                    metric_type="runtime_hours",
                    metric_unit="hours",
                    ingestion_mode="edge_batch_store",
                    polling_interval_seconds=300,
                    deadband_delta=Decimal("0.0000"),
                    scale_factor=Decimal("1.000000"),
                    offset_value=Decimal("0.0000"),
                    baseline_value=Decimal("1200.0000"),
                    warning_threshold=Decimal("2000.0000"),
                    critical_threshold=Decimal("2500.0000"),
                    auto_trigger_maintenance=True,
                    stream_status="active",
                    steward=user,
                )

            AssetGlSyncBatch.objects.create(
                tenant=tenant,
                connector=c_gl,
                sync_domain="depreciation_posting",
                sync_direction="outbound",
                external_batch_ref=f"ORCL-DEP-{today:%Y%m}-01",
                fiscal_period=fiscal_period,
                gl_account=gl_dr,
                offset_gl_account=gl_cr,
                fixed_asset=fixed_asset,
                depreciation_schedule=dep,
                cost_center=org_unit,
                currency=currency,
                batch_date=today,
                source_amount=Decimal("4250.00"),
                target_gl_amount=Decimal("4250.00"),
                reconciliation_status="pending",
                status="ready",
                field_mapping_json='{"asset_book": "CORP_US", "depreciation_acct": "6100"}',
                payload_summary="Monthly straight-line depreciation batch ready for GL posting.",
            )
            AssetGlSyncBatch.objects.create(
                tenant=tenant,
                connector=c_erp,
                sync_domain="capitalization_sync",
                sync_direction="bidirectional",
                external_batch_ref=f"SAP-CAP-{today:%Y%m}-02",
                fiscal_period=fiscal_period,
                gl_account=gl_dr,
                offset_gl_account=gl_cr,
                fixed_asset=fixed_asset,
                purchase_order=po,
                capitalization=cap,
                cost_center=org_unit,
                currency=currency,
                batch_date=today - timezone.timedelta(days=2),
                source_amount=Decimal("15675.00"),
                target_gl_amount=Decimal("15425.00"),
                reconciliation_status="variance_flagged",
                status="simulated",
                field_mapping_json='{"wbs_element": "CAPEX-2026-01", "asset_class": "2000"}',
                payload_summary="Capitalization settlement check detected $250 freight accrual variance.",
            )
            AssetGlSyncBatch.objects.create(
                tenant=tenant,
                connector=c_cmms,
                sync_domain="work_order_cost_rollup",
                sync_direction="inbound",
                external_batch_ref=f"MX-WO-ROLLUP-{today:%Y%m}",
                fiscal_period=fiscal_period,
                gl_account=gl_dr,
                offset_gl_account=gl_cr,
                fixed_asset=fixed_asset,
                maintenance_request=maint,
                cost_center=org_unit,
                currency=currency,
                batch_date=today - timezone.timedelta(days=5),
                source_amount=Decimal("1890.00"),
                target_gl_amount=Decimal("1890.00"),
                reconciliation_status="reconciled",
                status="reconciled",
                field_mapping_json='{"work_order": "WONUM", "cost_rollup": "ACTCOST"}',
                payload_summary="External CMMS maintenance labor & spare cost rollup.",
            )

            AssetGisMapping.objects.create(
                tenant=tenant,
                connector=c_gis,
                operational_asset=op1,
                location=location,
                org_unit=org_unit,
                external_feature_id="ARCGIS-MFG-PLANT1-001",
                layer_name="industrial_machinery_pt",
                geometry_type="point",
                coordinate_system_srid=4326,
                latitude=Decimal("37.774929"),
                longitude=Decimal("-122.419416"),
                elevation_meters=Decimal("18.50"),
                is_linear_asset=False,
                geojson_payload='{"type": "Point", "coordinates": [-122.419416, 37.774929]}',
                system_of_record="erp_authoritative",
                sync_direction="bidirectional",
                drift_status="in_sync",
                status="active",
                last_spatial_sync_at=now - timezone.timedelta(hours=3),
                gis_custodian=user,
            )
            AssetGisMapping.objects.create(
                tenant=tenant,
                connector=c_gis,
                operational_asset=op2,
                location=location,
                org_unit=org_unit,
                external_feature_id="ARCGIS-PIPE-FEEDER-044",
                layer_name="plant_utility_corridors_lrs",
                geometry_type="linestring",
                coordinate_system_srid=4326,
                latitude=Decimal("37.775400"),
                longitude=Decimal("-122.418200"),
                elevation_meters=Decimal("19.00"),
                is_linear_asset=True,
                lrs_route_id="CORRIDOR-NORTH-STEAM-01",
                lrs_from_measure=Decimal("0.000"),
                lrs_to_measure=Decimal("1.450"),
                lrs_measure_unit="km",
                geojson_payload='{"type": "LineString", "coordinates": [[-122.4194, 37.7749], [-122.4182, 37.7754]]}',
                system_of_record="gis_authoritative",
                sync_direction="bidirectional",
                drift_status="unverified",
                status="active",
                gis_custodian=user,
            )
            AssetGisMapping.objects.create(
                tenant=tenant,
                connector=c_gis,
                operational_asset=op3,
                location=location,
                org_unit=org_unit,
                external_feature_id="ARCGIS-YARD-SUBSTATION-07",
                layer_name="power_substations_poly",
                geometry_type="polygon",
                coordinate_system_srid=4326,
                is_linear_asset=False,
                system_of_record="shared_field",
                sync_direction="inbound",
                drift_status="location_drift",
                status="active",
                gis_custodian=user,
                notes="Awaiting updated survey coordinates after substation pad expansion.",
            )

        self.stdout.write(f"[{tenant.name}] 11.15 Seeding complete (5 connectors, telemetry streams, 3 GL batches, 3 GIS mappings).")

    def _seed_tenant_11_16(self, tenant):
        """Idempotent seeding for 11.16 Document & Knowledge Management."""
        if AssetDocument.objects.filter(tenant=tenant).exists():
            self.stdout.write(
                f"[{tenant.name}] 11.16 Document & Knowledge Management data already seeded, skipping."
            )
            return

        self.stdout.write(
            f"[{tenant.name}] Seeding 11.16 Document & Knowledge Management..."
        )
        today = timezone.localdate()
        now = timezone.now()

        user = User.objects.filter(tenant=tenant).order_by("pk").first()
        org_unit = OrgUnit.objects.filter(tenant=tenant).order_by("pk").first()
        party = Party.objects.filter(tenant=tenant).order_by("pk").first()
        asset_pair = list(Asset.objects.filter(tenant=tenant).order_by("pk")[:2])
        op1 = asset_pair[0] if asset_pair else None
        op2 = asset_pair[1] if len(asset_pair) > 1 else op1
        fixed_asset = FixedAsset.objects.filter(tenant=tenant).order_by("pk").first()
        category = AssetCategory.objects.filter(tenant=tenant).order_by("pk").first()
        model_obj = AssetModel.objects.filter(tenant=tenant).order_by("pk").first()
        schedule = (
            AssetMaintenanceSchedule.objects.filter(tenant=tenant)
            .order_by("pk")
            .first()
        )
        framework = (
            AssetComplianceFramework.objects.filter(tenant=tenant)
            .order_by("pk")
            .first()
        )
        failure_mode = (
            AssetFailureMode.objects.filter(tenant=tenant).order_by("pk").first()
        )

        with transaction.atomic():
            doc_rev_a = AssetDocument.objects.create(
                tenant=tenant,
                title="Centrifugal Chiller OEM Operation & Maintenance Manual",
                document_class="manual",
                access_classification="internal_tech",
                tag_code="OEM-CHW-001",
                manufacturer_ref="Trane CVHF-770",
                document_language="en",
                storage_location_ref="DMS Vault / Chiller Bay A",
                revision_label="Rev A",
                revision_sequence=1,
                is_current_revision=False,
                change_type="new_issue",
                change_request_ref="ECR-2025-004",
                effective_date=today - timezone.timedelta(days=365),
                expiry_date=today + timezone.timedelta(days=365),
                retention_years=10,
                status="superseded",
                owner=user,
                reviewer=user,
                approved_by=user,
                approved_at=now - timezone.timedelta(days=365),
                org_unit=org_unit,
                operational_asset=op1,
                fixed_asset=fixed_asset,
                asset_category=category,
                asset_model=model_obj,
                compliance_framework=framework,
                vendor_party=party,
                description="Initial OEM release for central chiller compressor train.",
            )

            doc_rev_b = AssetDocument.objects.create(
                tenant=tenant,
                title="Centrifugal Chiller OEM Operation & Maintenance Manual",
                document_class="manual",
                access_classification="internal_tech",
                tag_code="OEM-CHW-001",
                manufacturer_ref="Trane CVHF-770",
                document_language="en",
                storage_location_ref="DMS Vault / Chiller Bay A",
                revision_label="Rev B",
                revision_sequence=2,
                supersedes=doc_rev_a,
                is_current_revision=True,
                change_type="vendor_bulletin",
                change_request_ref="ECR-2026-011",
                redline_summary="Updated thrust bearing oil pressure cutoff threshold per OEM SB-442.",
                spec_delta_notes="Minimum differential oil pressure raised from 18 PSI to 22 PSI.",
                effective_date=today - timezone.timedelta(days=30),
                expiry_date=today + timezone.timedelta(days=335),
                retention_years=10,
                status="approved",
                owner=user,
                reviewer=user,
                approved_by=user,
                approved_at=now - timezone.timedelta(days=30),
                org_unit=org_unit,
                operational_asset=op1,
                fixed_asset=fixed_asset,
                asset_category=category,
                asset_model=model_obj,
                compliance_framework=framework,
                vendor_party=party,
                description="Current controlled manual incorporating OEM bearing lubrication bulletin.",
            )

            AssetDocument.objects.create(
                tenant=tenant,
                title="Plant #1 Main Switchgear P&ID & Single-Line Schematic",
                document_class="electrical_diagram",
                access_classification="restricted_eng",
                tag_code="EL-SLD-480V",
                manufacturer_ref="Schneider Masterpact MTZ",
                document_language="en",
                storage_location_ref="EHS Electrical Vault C-02",
                revision_label="Rev A",
                revision_sequence=1,
                supersedes=None,
                is_current_revision=False,
                change_type="drawing_redline",
                change_request_ref="ECR-2026-028",
                redline_summary="Added harmonic filter feeder breaker FB-14 and updated arc-flash relay curve.",
                effective_date=today,
                expiry_date=today + timezone.timedelta(days=18),
                retention_years=15,
                status="in_review",
                owner=user,
                reviewer=user,
                checked_out_by=user,
                checked_out_at=now - timezone.timedelta(hours=4),
                org_unit=org_unit,
                operational_asset=op2,
                asset_category=category,
                compliance_framework=framework,
                description="As-built redline awaiting chief electrical engineer release sign-off.",
            )

            AssetDocument.objects.create(
                tenant=tenant,
                title="Pressure Vessel Annual Statutory Inspection Certificate",
                document_class="compliance_cert",
                access_classification="public_floor",
                tag_code="PV-CERT-2026",
                manufacturer_ref="ASME Section VIII Div 1",
                document_language="en",
                storage_location_ref="Shop Floor Binder / Receiver Bay",
                revision_label="Rev A",
                revision_sequence=1,
                is_current_revision=True,
                change_type="regulatory_update",
                effective_date=today - timezone.timedelta(days=90),
                expiry_date=today + timezone.timedelta(days=275),
                retention_years=7,
                status="approved",
                owner=user,
                approved_by=user,
                approved_at=now - timezone.timedelta(days=90),
                org_unit=org_unit,
                operational_asset=op1,
                asset_category=category,
                compliance_framework=framework,
            )

            sop_loto = AssetOperatingProcedure.objects.create(
                tenant=tenant,
                title="480V Chiller Compressor LOTO & Zero-Energy Verification SOP",
                procedure_type="loto_isolation",
                safety_level="high_hazard_loto",
                revision_label="Rev 2.0",
                purpose_scope="Mandatory full electrical and mechanical isolation prior to bearing or motor servicing.",
                hazard_warnings="480V 3-phase arc-flash hazard and pressurized refrigerant receiver tank (240 PSI).",
                required_ppe="Arc-flash hood Cat-2, insulated gloves Class 0, dielectric boots, personal red padlock.",
                loto_required=True,
                loto_isolation_points=[
                    {
                        "energy_source": "Electrical 480V 3-Phase",
                        "tag_id": "MCC-CHW-01B",
                        "isolation_point": "Main Feeder Disconnect",
                        "lock_device": "Personal Red Padlock + Hasps",
                        "verification_step": "Phase-to-phase zero-voltage test (<1V)",
                    },
                    {
                        "energy_source": "Pressurized Refrigerant Loop",
                        "tag_id": "VLV-SUCT-04",
                        "isolation_point": "Suction Header Isolation Valve",
                        "lock_device": "Chain & Cable Lockout + Tag",
                        "verification_step": "Verify manifold gauge reads 0 PSIG",
                    },
                ],
                procedure_steps=[
                    {
                        "step_no": 1,
                        "title": "Controlled Shutdown & Cool-down",
                        "instruction": "Command chiller standby stop and verify compressor coast-down to 0 RPM.",
                        "expected_reading": "0 RPM",
                        "is_mandatory_signoff": True,
                    },
                    {
                        "step_no": 2,
                        "title": "Apply LOTO Locks & Bleed Residual Pressure",
                        "instruction": "Isolate MCC-CHW-01B and VLV-SUCT-04, apply personal locks and tags.",
                        "expected_reading": "0 VAC / 0 PSIG",
                        "is_mandatory_signoff": True,
                    },
                    {
                        "step_no": 3,
                        "title": "Perform Try-Start Verification",
                        "instruction": "Attempt local start pushbutton to confirm zero-energy state.",
                        "expected_reading": "No Start / De-energized",
                        "is_mandatory_signoff": True,
                    },
                ],
                required_qualification_code="QUAL-LOTO-HV",
                estimated_duration_minutes=45,
                effective_date=today - timezone.timedelta(days=60),
                review_cycle_months=12,
                next_review_date=today + timezone.timedelta(days=180),
                status="active",
                author=user,
                safety_reviewer=user,
                approved_by=user,
                approved_at=now - timezone.timedelta(days=60),
                org_unit=org_unit,
                operational_asset=op1,
                asset_category=category,
                asset_model=model_obj,
                maintenance_schedule=schedule,
                compliance_framework=framework,
                primary_document=doc_rev_b,
            )

            sop_pm = AssetOperatingProcedure.objects.create(
                tenant=tenant,
                title="Quarterly Bearing Vibration & Oil Analysis Sampling Protocol",
                procedure_type="pm_protocol",
                safety_level="caution",
                revision_label="Rev 1.0",
                purpose_scope="Standardized triaxial vibration data collection and oil port sampling under running load.",
                hazard_warnings="Rotating shaft coupling guard must remain installed; maintain safe clearance.",
                required_ppe="Safety glasses, hearing protection, close-fitting FR coveralls.",
                loto_required=False,
                procedure_steps=[
                    {
                        "step_no": 1,
                        "title": "Record Steady-State Load & Bearing Temperature",
                        "instruction": "Log RMS velocity at drive-end and non-drive-end bearing housings.",
                        "expected_reading": "< 2.8 mm/s RMS",
                        "is_mandatory_signoff": False,
                    },
                    {
                        "step_no": 2,
                        "title": "Draw Representative Oil Sample",
                        "instruction": "Flush 50 mL sample valve before filling clean ICP lab bottle.",
                        "expected_reading": "ISO 17/15/12 cleanliness",
                        "is_mandatory_signoff": True,
                    },
                ],
                required_qualification_code="QUAL-PM-VIB",
                estimated_duration_minutes=30,
                effective_date=today - timezone.timedelta(days=390),
                review_cycle_months=12,
                next_review_date=today - timezone.timedelta(days=5),
                status="active",
                author=user,
                safety_reviewer=user,
                approved_by=user,
                approved_at=now - timezone.timedelta(days=390),
                org_unit=org_unit,
                operational_asset=op1,
                asset_category=category,
                maintenance_schedule=schedule,
                primary_document=doc_rev_b,
            )

            AssetOperatingProcedure.objects.create(
                tenant=tenant,
                title="Emergency Sub-Station Blackout & E-Stop Recovery Checklist",
                procedure_type="emergency_shutdown",
                safety_level="permit_required",
                revision_label="Rev 1.0",
                purpose_scope="Emergency sequence for utility outage and controlled UPS load shedding.",
                hazard_warnings="Energized ATS transfer bus; permit-to-work required before manual bypass.",
                required_ppe="Arc-flash PPE Cat-2, insulated rescue hook nearby.",
                loto_required=True,
                required_qualification_code="QUAL-HV-SWITCH",
                estimated_duration_minutes=25,
                review_cycle_months=6,
                status="under_review",
                author=user,
                safety_reviewer=user,
                org_unit=org_unit,
                operational_asset=op2,
                asset_category=category,
                compliance_framework=framework,
            )

            if user is not None or party is not None:
                AssetOperatorCertification.objects.create(
                    tenant=tenant,
                    title="LOTO Authorized Person — High-Voltage Chiller & MCC Systems",
                    qualification_code="QUAL-LOTO-HV",
                    qualification_type="loto_authorized",
                    proficiency_level="senior_technician",
                    issuing_authority="EHS Internal Authorization Board",
                    certificate_reference="EHS-LOTO-2026-019",
                    issued_date=today - timezone.timedelta(days=120),
                    expires_on=today + timezone.timedelta(days=245),
                    renewal_lead_days=30,
                    last_assessed_date=today - timezone.timedelta(days=120),
                    training_hours=Decimal("16.00"),
                    assessment_score=Decimal("94.50"),
                    sop_acknowledged=True,
                    sop_acknowledged_at=now - timezone.timedelta(days=10),
                    status="active",
                    org_unit=org_unit,
                    operator_user=user,
                    operator_party=party,
                    issuing_party=party,
                    assessor=user,
                    operational_asset=op1,
                    asset_category=category,
                    asset_model=model_obj,
                    operating_procedure=sop_loto,
                    compliance_framework=framework,
                    notes="Verified practical LOTO demonstration on MCC-CHW-01B.",
                )

                AssetOperatorCertification.objects.create(
                    tenant=tenant,
                    title="Condition Monitoring & Vibration Specialist Level II",
                    qualification_code="QUAL-PM-VIB",
                    qualification_type="maintenance_technician",
                    proficiency_level="qualified_operator",
                    issuing_authority="ISO 18436 Vibration Institute",
                    certificate_reference="VIB-II-88412",
                    issued_date=today - timezone.timedelta(days=351),
                    expires_on=today + timezone.timedelta(days=14),
                    renewal_lead_days=30,
                    last_assessed_date=today - timezone.timedelta(days=351),
                    training_hours=Decimal("24.00"),
                    assessment_score=Decimal("91.00"),
                    sop_acknowledged=True,
                    sop_acknowledged_at=now - timezone.timedelta(days=20),
                    status="expiring_soon",
                    org_unit=org_unit,
                    operator_party=party,
                    operator_user=user,
                    assessor=user,
                    operational_asset=op1,
                    asset_category=category,
                    operating_procedure=sop_pm,
                    notes="Due for annual ISO-18436 recertification assessment.",
                )

                AssetOperatorCertification.objects.create(
                    tenant=tenant,
                    title="Crane, Hoist & Rigging Safe Lift Qualification",
                    qualification_code="QUAL-CRANE-01",
                    qualification_type="crane_rigging",
                    proficiency_level="trainee_supervised",
                    issuing_authority="NCCCO Rigging Academy",
                    certificate_reference="RIG-2026-305",
                    issued_date=today - timezone.timedelta(days=7),
                    expires_on=today + timezone.timedelta(days=358),
                    renewal_lead_days=45,
                    training_hours=Decimal("12.50"),
                    assessment_score=Decimal("88.00"),
                    sop_acknowledged=False,
                    status="pending",
                    org_unit=org_unit,
                    operator_user=user,
                    operational_asset=op2,
                    asset_category=category,
                    operating_procedure=sop_loto,
                    notes="Awaiting supervisor verification and mandatory SOP sign-off.",
                )

            AssetKnowledgeArticle.objects.create(
                tenant=tenant,
                title="Chiller Thrust Bearing Pre-Mature Spalling — 5-Why Oil Starvation RCA",
                article_type="rca_post_incident",
                rca_methodology="five_whys",
                severity="critical",
                symptom_problem="High bearing casing temperature alarm (94°C) and 8.4 mm/s axial vibration trip during peak cooling load.",
                root_cause_summary="Clogged inline 40-micron oil strainer combined with legacy 18 PSI differential trip threshold masked early oil starvation.",
                five_whys=[
                    {
                        "why_level": 1,
                        "question": "Why did the compressor thrust bearing seize?",
                        "answer": "Oil film thickness collapsed under peak axial thrust load.",
                    },
                    {
                        "why_level": 2,
                        "question": "Why did oil pressure drop below lubrication requirements?",
                        "answer": "Inline supply strainer delta-P reached 14 PSI due to varnish buildup.",
                    },
                    {
                        "why_level": 3,
                        "question": "Why was the strainer restriction not caught before failure?",
                        "answer": "PM checklist lacked differential-pressure log and OEM bulletin SB-442 was unapplied.",
                    },
                ],
                contributing_factors={
                    "machine": "Legacy 18 PSI oil trip switch",
                    "method": "OEM service bulletin SB-442 not propagated into PM protocol",
                    "material": "Oxidized synthetic refrigeration oil",
                    "measurement": "Missing differential pressure transmitter across filter housing",
                },
                remedy_corrective_action="Replaced thrust bearing assembly, flushed oil sump, raised differential cutoff to 22 PSI per OEM SB-442.",
                preventive_lessons="Adopted quarterly oil cleanliness sampling SOP and upgraded controlled manual to Rev B.",
                downtime_hours_impacted=Decimal("14.50"),
                recurrence_count=2,
                tags="chiller, bearing, starvation, 5-why, oem-sb",
                helpful_votes=7,
                view_count=42,
                incident_occurred_on=today - timezone.timedelta(days=25),
                status="published",
                author=user,
                reviewed_by=user,
                published_at=now - timezone.timedelta(days=20),
                org_unit=org_unit,
                operational_asset=op1,
                fixed_asset=fixed_asset,
                asset_category=category,
                asset_model=model_obj,
                failure_mode=failure_mode,
                related_document=doc_rev_b,
                recommended_procedure=sop_loto,
            )

            AssetKnowledgeArticle.objects.create(
                tenant=tenant,
                title="Motor-Pump Coupling Alignment Tolerance & Soft-Foot Field Troubleshooting",
                article_type="troubleshooting_guide",
                rca_methodology="fishbone_ishikawa",
                severity="high",
                symptom_problem="Recurring 2x line-frequency horizontal vibration (>6.5 mm/s) after mechanical seal overhaul.",
                root_cause_summary="Pipe strain and 0.18 mm angular soft-foot induced thermal growth misalignment at operating temperature.",
                contributing_factors={
                    "machine": "Excessive baseplate shim stack (>5 shims)",
                    "method": "Cold alignment done without pipe strain relaxation",
                    "manpower": "Pre-cut stainless shims not micrometers-verified",
                    "measurement": "Thermal growth offset neglected",
                },
                remedy_corrective_action="Re-machined base pad, limited shims to <=3 precision pieces, performed laser hot-alignment check.",
                preventive_lessons="Mandate soft-foot tolerance <0.05 mm on all rotating equipment >50 HP.",
                downtime_hours_impacted=Decimal("6.00"),
                recurrence_count=3,
                tags="alignment, vibration, soft-foot, laser",
                helpful_votes=4,
                view_count=19,
                incident_occurred_on=today - timezone.timedelta(days=12),
                status="published",
                author=user,
                reviewed_by=user,
                published_at=now - timezone.timedelta(days=10),
                org_unit=org_unit,
                operational_asset=op1,
                asset_category=category,
                recommended_procedure=sop_pm,
            )

            AssetKnowledgeArticle.objects.create(
                tenant=tenant,
                title="Harmonic Filter Feeder Breaker Curve Coordination Note",
                article_type="lessons_learned",
                rca_methodology="problem_cause_remedy",
                severity="medium",
                symptom_problem="Nuisance instantaneous trip on switchgear feeder during capacitor bank energization transient.",
                root_cause_summary="Inrush transient peak overlapped overly tight short-time pickup dial setting.",
                remedy_corrective_action="Adjusted short-time delay band per redlined P&ID ECR-2026-028.",
                preventive_lessons="Coordinate relay curve modeling whenever power factor correction banks are modified.",
                downtime_hours_impacted=Decimal("2.25"),
                recurrence_count=1,
                tags="switchgear, harmonics, relay-curve",
                incident_occurred_on=today - timezone.timedelta(days=3),
                status="peer_review",
                author=user,
                org_unit=org_unit,
                operational_asset=op2,
                asset_category=category,
            )

        self.stdout.write(
            f"[{tenant.name}] 11.16 Seeding complete (4 docs, 3 SOPs, 3 certifications, 3 KB articles)."
        )

    def _seed_tenant_11_17(self, tenant):
        """Idempotent seeding for 11.17 Space & Facility Asset Management."""
        legacy_level_map = {"zone": "wing_zone", "suite": "room"}
        legacy_category_map = {
            "office_open": "office_workspace",
            "conference_room": "conference_meeting",
            "mechanical_electrical": "mechanical_room",
            "lab_cleanroom": "cleanroom_lab",
        }
        if AssetFacilitySpace.objects.filter(tenant=tenant).exists():
            for old_val, new_val in legacy_level_map.items():
                AssetFacilitySpace.objects.filter(
                    tenant=tenant, space_level=old_val
                ).update(space_level=new_val)
            for old_val, new_val in legacy_category_map.items():
                AssetFacilitySpace.objects.filter(
                    tenant=tenant, space_category=old_val
                ).update(space_category=new_val)
            self.stdout.write(
                f"[{tenant.name}] 11.17 Space & Facility Asset Management data already seeded, skipping."
            )
            return

        def _save_clean(obj):
            obj.full_clean()
            obj.save()
            return obj

        self.stdout.write(f"[{tenant.name}] Seeding 11.17 Space & Facility Asset Management...")
        now = timezone.now()
        today = now.date()

        user = User.objects.filter(tenant=tenant).order_by("pk").first()
        org_units = list(OrgUnit.objects.filter(tenant=tenant).order_by("pk")[:3])
        org_unit_1 = org_units[0] if org_units else None
        org_unit_2 = org_units[1] if len(org_units) > 1 else org_unit_1
        parties = list(Party.objects.filter(tenant=tenant).order_by("pk")[:2])
        vendor_party = parties[0] if parties else None
        occupant_party = parties[1] if len(parties) > 1 else vendor_party
        location = Location.objects.filter(tenant=tenant).order_by("pk").first()
        op_assets = list(Asset.objects.filter(tenant=tenant).order_by("pk")[:2])
        op1 = op_assets[0] if op_assets else None
        op2 = op_assets[1] if len(op_assets) > 1 else op1
        fixed_asset = FixedAsset.objects.filter(tenant=tenant).order_by("pk").first()
        currency = Currency.objects.filter(is_active=True).order_by("code").first()
        fiscal_period = (
            FiscalPeriod.objects.filter(tenant=tenant, status="open").order_by("pk").first()
            or FiscalPeriod.objects.filter(tenant=tenant).order_by("pk").first()
        )
        gl_accounts = list(GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("pk")[:2])
        if len(gl_accounts) < 2:
            gl_accounts = list(GLAccount.objects.filter(tenant=tenant).order_by("pk")[:2])
        gl_exp = gl_accounts[0] if len(gl_accounts) >= 1 else None
        gl_rec = gl_accounts[1] if len(gl_accounts) >= 2 else None

        gis_map = AssetGisMapping.objects.filter(tenant=tenant).order_by("pk").first()
        doc_fp = AssetDocument.objects.filter(tenant=tenant).order_by("pk").first()
        permit = AssetPermitLicense.objects.filter(tenant=tenant).order_by("pk").first()
        maint_sched = AssetMaintenanceSchedule.objects.filter(tenant=tenant).order_by("pk").first()
        energy_read = AssetEnergyReading.objects.filter(tenant=tenant).order_by("pk").first()
        lease_contract = AssetLeaseContract.objects.filter(tenant=tenant).order_by("pk").first()

        with transaction.atomic():
            hq_building = _save_clean(
                AssetFacilitySpace(
                    tenant=tenant,
                    code="HQ-BLDG-A",
                    name="Headquarters Tower A",
                    space_level="building",
                    space_category="office_workspace",
                    org_unit=org_unit_1,
                    scm_location=location,
                    gis_mapping=gis_map,
                    floor_plan_document=doc_fp,
                    space_steward=user,
                    gross_area_sqft=Decimal("48000.00"),
                    rentable_area_sqft=Decimal("44500.00"),
                    usable_area_sqft=Decimal("39500.00"),
                    common_area_sqft=Decimal("5000.00"),
                    annual_rate_per_sqft=Decimal("42.00"),
                    design_seat_capacity=220,
                    current_headcount=184,
                    cad_layer_ref="A-BLDG-SITE",
                    bim_guid="1a8f3d2e-4c71-41b9-9f20-001",
                    bim_level_ref="Campus Building A",
                    drawing_revision="Rev C",
                    status="active",
                    notes="Primary corporate headquarters building tracked under BOMA 2017 Office Standard.",
                )
            )

            floor_2 = _save_clean(
                AssetFacilitySpace(
                    tenant=tenant,
                    code="HQ-F02",
                    name="Floor 02 — Operations & Engineering",
                    space_level="floor",
                    space_category="office_workspace",
                    parent=hq_building,
                    org_unit=org_unit_1,
                    scm_location=location,
                    floor_plan_document=doc_fp,
                    space_steward=user,
                    gross_area_sqft=Decimal("16000.00"),
                    rentable_area_sqft=Decimal("14800.00"),
                    usable_area_sqft=Decimal("13200.00"),
                    common_area_sqft=Decimal("1600.00"),
                    annual_rate_per_sqft=Decimal("45.00"),
                    design_seat_capacity=90,
                    current_headcount=82,
                    cad_layer_ref="A-AREA-F02",
                    bim_guid="1a8f3d2e-4c71-41b9-9f20-002",
                    bim_level_ref="Level 02",
                    drawing_revision="Rev D",
                    status="active",
                )
            )

            eng_bay = _save_clean(
                AssetFacilitySpace(
                    tenant=tenant,
                    code="HQ-F02-E204",
                    name="Engineering Collaboration Studio 204",
                    space_level="wing_zone",
                    space_category="office_workspace",
                    parent=floor_2,
                    org_unit=org_unit_1,
                    scm_location=location,
                    space_steward=user,
                    gross_area_sqft=Decimal("4200.00"),
                    rentable_area_sqft=Decimal("3900.00"),
                    usable_area_sqft=Decimal("3500.00"),
                    common_area_sqft=Decimal("400.00"),
                    annual_rate_per_sqft=Decimal("45.00"),
                    design_seat_capacity=30,
                    current_headcount=26,
                    cad_layer_ref="A-AREA-E204",
                    bim_level_ref="Level 02",
                    drawing_revision="Rev D",
                    status="active",
                )
            )

            boardroom = _save_clean(
                AssetFacilitySpace(
                    tenant=tenant,
                    code="HQ-F02-CONF",
                    name="Executive Boardroom 210",
                    space_level="room",
                    space_category="conference_meeting",
                    parent=floor_2,
                    org_unit=org_unit_2,
                    scm_location=location,
                    space_steward=user,
                    gross_area_sqft=Decimal("1100.00"),
                    rentable_area_sqft=Decimal("1020.00"),
                    usable_area_sqft=Decimal("920.00"),
                    common_area_sqft=Decimal("100.00"),
                    annual_rate_per_sqft=Decimal("48.00"),
                    design_seat_capacity=20,
                    current_headcount=6,
                    cad_layer_ref="A-AREA-R210",
                    bim_level_ref="Level 02",
                    drawing_revision="Rev B",
                    status="active",
                )
            )

            mech_core = _save_clean(
                AssetFacilitySpace(
                    tenant=tenant,
                    code="HQ-B1-MECH",
                    name="Basement B1 Central MEP Plant",
                    space_level="room",
                    space_category="mechanical_room",
                    parent=hq_building,
                    org_unit=org_unit_1,
                    scm_location=location,
                    space_steward=user,
                    gross_area_sqft=Decimal("2600.00"),
                    rentable_area_sqft=Decimal("2400.00"),
                    usable_area_sqft=Decimal("2200.00"),
                    common_area_sqft=Decimal("200.00"),
                    annual_rate_per_sqft=Decimal("22.00"),
                    design_seat_capacity=4,
                    current_headcount=0,
                    cad_layer_ref="M-MECH-B1",
                    bim_level_ref="Basement B1",
                    drawing_revision="Rev C",
                    status="active",
                )
            )

            _save_clean(
                AssetFacilitySpace(
                    tenant=tenant,
                    code="HQ-F03-LAB",
                    name="Level 03 R&D Clean Suite (Fit-Out)",
                    space_level="room",
                    space_category="cleanroom_lab",
                    parent=hq_building,
                    org_unit=org_unit_2,
                    scm_location=location,
                    space_steward=user,
                    gross_area_sqft=Decimal("3200.00"),
                    rentable_area_sqft=Decimal("2950.00"),
                    usable_area_sqft=Decimal("2700.00"),
                    common_area_sqft=Decimal("250.00"),
                    annual_rate_per_sqft=Decimal("58.00"),
                    design_seat_capacity=18,
                    current_headcount=0,
                    cad_layer_ref="A-LAB-301",
                    bim_level_ref="Level 03",
                    drawing_revision="Rev A",
                    status="under_renovation",
                    notes="Tenant improvement build-out currently in progress.",
                )
            )

            ahu_sys = _save_clean(
                AssetBuildingSystem(
                    tenant=tenant,
                    name="Primary Rooftop AHU-01 (Engineering Wing)",
                    system_domain="hvac_climate",
                    subsystem_type="ahu_air_handler",
                    facility_space=floor_2,
                    pin_x_pct=Decimal("28.50"),
                    pin_y_pct=Decimal("42.00"),
                    manufacturer="Trane",
                    model_number="CSAA-040U",
                    serial_number="TRN-AHU-2025-01",
                    load_or_voltage_rating="480V / 3-Phase / 60A",
                    ashrae_nfpa_code_ref="ASHRAE 90.1 / 62.1",
                    served_area_sqft=Decimal("13200.00"),
                    design_capacity_btu_kw=Decimal("420.00"),
                    refrigerant_type="Chilled Water",
                    setpoint_temp_c=Decimal("22.00"),
                    measured_temp_c=Decimal("22.40"),
                    target_humidity_pct=Decimal("45.00"),
                    measured_humidity_pct=Decimal("47.00"),
                    airflow_cfm=Decimal("16500.00"),
                    energy_efficiency_rating="IEER 16.4",
                    condition_grade="good",
                    criticality_tier="tier_2_mission_crit",
                    remaining_useful_life_years=14,
                    replacement_cost_estimate=Decimal("145000.00"),
                    last_statutory_inspection_date=today - timezone.timedelta(days=60),
                    next_inspection_due_date=today + timezone.timedelta(days=120),
                    status="operational",
                    operational_asset=op1,
                    fixed_asset=fixed_asset,
                    latest_energy_reading=energy_read,
                    maintenance_schedule=maint_sched,
                    operating_permit=permit,
                    schematic_document=doc_fp,
                    service_vendor=vendor_party,
                    org_unit=org_unit_1,
                )
            )

            _save_clean(
                AssetBuildingSystem(
                    tenant=tenant,
                    name="Boardroom VAV Terminal Zone 210",
                    system_domain="hvac_climate",
                    subsystem_type="vav_terminal",
                    facility_space=boardroom,
                    pin_x_pct=Decimal("64.00"),
                    pin_y_pct=Decimal("31.00"),
                    manufacturer="Carrier",
                    model_number="35E-VAV-12",
                    serial_number="CAR-VAV-210",
                    load_or_voltage_rating="24VAC Control",
                    ashrae_nfpa_code_ref="ASHRAE 55 Thermal Comfort",
                    served_area_sqft=Decimal("920.00"),
                    design_capacity_btu_kw=Decimal("28.00"),
                    setpoint_temp_c=Decimal("21.50"),
                    measured_temp_c=Decimal("24.80"),
                    target_humidity_pct=Decimal("45.00"),
                    measured_humidity_pct=Decimal("52.00"),
                    airflow_cfm=Decimal("1450.00"),
                    condition_grade="fair",
                    criticality_tier="tier_3_operational",
                    remaining_useful_life_years=7,
                    replacement_cost_estimate=Decimal("18500.00"),
                    last_statutory_inspection_date=today - timezone.timedelta(days=200),
                    next_inspection_due_date=today + timezone.timedelta(days=45),
                    status="degraded",
                    service_vendor=vendor_party,
                    org_unit=org_unit_2,
                    notes="Damper actuator calibration drift detected on west return duct.",
                )
            )

            _save_clean(
                AssetBuildingSystem(
                    tenant=tenant,
                    name="Main Low-Voltage Switchgear MDB-01",
                    system_domain="electrical_power",
                    subsystem_type="switchgear_panel",
                    facility_space=mech_core,
                    pin_x_pct=Decimal("18.00"),
                    pin_y_pct=Decimal("76.00"),
                    manufacturer="Schneider Electric",
                    model_number="QED-2-4000A",
                    serial_number="SE-MDB-8841",
                    load_or_voltage_rating="480Y/277V 4000A",
                    ashrae_nfpa_code_ref="NFPA 70E / NEC Art. 240",
                    served_area_sqft=Decimal("48000.00"),
                    design_capacity_btu_kw=Decimal("2400.00"),
                    condition_grade="excellent",
                    criticality_tier="tier_1_life_safety",
                    remaining_useful_life_years=22,
                    replacement_cost_estimate=Decimal("310000.00"),
                    last_statutory_inspection_date=today - timezone.timedelta(days=90),
                    next_inspection_due_date=today + timezone.timedelta(days=275),
                    status="operational",
                    operational_asset=op2,
                    fixed_asset=fixed_asset,
                    operating_permit=permit,
                    service_vendor=vendor_party,
                    org_unit=org_unit_1,
                )
            )

            _save_clean(
                AssetBuildingSystem(
                    tenant=tenant,
                    name="Passenger Elevator Bank ELV-A1",
                    system_domain="elevator_vertical",
                    subsystem_type="passenger_elevator",
                    facility_space=hq_building,
                    pin_x_pct=Decimal("50.00"),
                    pin_y_pct=Decimal("50.00"),
                    manufacturer="Otis",
                    model_number="Gen2-MRL-3500",
                    serial_number="OTIS-3500-A1",
                    load_or_voltage_rating="480V / 3500 lb / 500 FPM",
                    ashrae_nfpa_code_ref="ASME A17.1 Safety Code",
                    condition_grade="good",
                    criticality_tier="tier_1_life_safety",
                    remaining_useful_life_years=15,
                    replacement_cost_estimate=Decimal("265000.00"),
                    last_statutory_inspection_date=today - timezone.timedelta(days=395),
                    next_inspection_due_date=today - timezone.timedelta(days=30),
                    status="operational",
                    operating_permit=permit,
                    service_vendor=vendor_party,
                    org_unit=org_unit_1,
                    notes="Annual municipal conveyance inspection pending scheduling.",
                )
            )

            _save_clean(
                AssetBuildingSystem(
                    tenant=tenant,
                    name="Addressable Fire Alarm Panel FACP-01",
                    system_domain="fire_life_safety",
                    subsystem_type="fire_alarm_panel",
                    facility_space=hq_building,
                    pin_x_pct=Decimal("12.00"),
                    pin_y_pct=Decimal("20.00"),
                    manufacturer="Notifier by Honeywell",
                    model_number="NFS2-3030",
                    serial_number="NOT-3030-991",
                    load_or_voltage_rating="120V AC / 24V DC Battery",
                    ashrae_nfpa_code_ref="NFPA 72 National Fire Alarm Code",
                    served_area_sqft=Decimal("48000.00"),
                    condition_grade="excellent",
                    criticality_tier="tier_1_life_safety",
                    remaining_useful_life_years=16,
                    replacement_cost_estimate=Decimal("95000.00"),
                    last_statutory_inspection_date=today - timezone.timedelta(days=45),
                    next_inspection_due_date=today + timezone.timedelta(days=135),
                    status="operational",
                    operating_permit=permit,
                    service_vendor=vendor_party,
                    org_unit=org_unit_1,
                )
            )

            _save_clean(
                AssetBuildingSystem(
                    tenant=tenant,
                    name="Domestic Cold Water Triplex Booster Pump",
                    system_domain="plumbing_water",
                    subsystem_type="booster_pump",
                    facility_space=mech_core,
                    manufacturer="Grundfos",
                    model_number="Hydro-MPC-E-3CR",
                    serial_number="GF-MPC-441",
                    load_or_voltage_rating="480V / 3x15 HP VFD",
                    ashrae_nfpa_code_ref="IPC / ASHRAE 188",
                    condition_grade="poor",
                    criticality_tier="tier_2_mission_crit",
                    remaining_useful_life_years=3,
                    replacement_cost_estimate=Decimal("68000.00"),
                    last_statutory_inspection_date=today - timezone.timedelta(days=180),
                    next_inspection_due_date=today + timezone.timedelta(days=60),
                    status="under_maintenance",
                    service_vendor=vendor_party,
                    org_unit=org_unit_1,
                    notes="Seal rebuild and VFD harmonic choke replacement queued.",
                )
            )

            _save_clean(
                AssetFurnitureFixture(
                    tenant=tenant,
                    name="Height-Adjustable Bench Workstation Pod (6-Seat)",
                    ffe_category="workstation_desk",
                    asset_tag_code=f"FFE-{tenant.pk}-WS01",
                    manufacturer="Herman Miller",
                    model_sku="Renew-SitStand-6P",
                    finish_material="Natural Oak / Graphite",
                    facility_space=eng_bay,
                    custodian_party=occupant_party,
                    assigned_org_unit=org_unit_1,
                    operational_asset=op1,
                    fixed_asset=fixed_asset,
                    move_coordinator=user,
                    quantity=6,
                    unit_replacement_cost=Decimal("1850.00"),
                    pin_x_pct=Decimal("35.00"),
                    pin_y_pct=Decimal("55.00"),
                    condition_grade="new",
                    move_status="in_place",
                )
            )

            _save_clean(
                AssetFurnitureFixture(
                    tenant=tenant,
                    name="Aeron Ergonomic Task Chairs — Wave B",
                    ffe_category="ergonomic_seating",
                    asset_tag_code=f"FFE-{tenant.pk}-CHR02",
                    manufacturer="Herman Miller",
                    model_sku="AER1B23DW-G1",
                    finish_material="Carbon Pellicle Mesh",
                    facility_space=floor_2,
                    target_space=eng_bay,
                    custodian_party=occupant_party,
                    assigned_org_unit=org_unit_1,
                    operational_asset=op1,
                    move_coordinator=user,
                    quantity=14,
                    unit_replacement_cost=Decimal("1250.00"),
                    pin_x_pct=Decimal("48.00"),
                    pin_y_pct=Decimal("62.00"),
                    condition_grade="good",
                    move_status="move_requested",
                    reconfiguration_batch_ref="IMAC-2026-Q4",
                    move_scheduled_date=today + timezone.timedelta(days=7),
                    estimated_move_cost=Decimal("850.00"),
                    move_notes="Consolidate 14 engineering task chairs into Studio 204 pod expansion.",
                )
            )

            _save_clean(
                AssetFurnitureFixture(
                    tenant=tenant,
                    name="20-Seat Modular Walnut Boardroom Table & Credenza",
                    ffe_category="conference_table",
                    asset_tag_code=f"FFE-{tenant.pk}-TBL03",
                    manufacturer="Steelcase",
                    model_sku="Verge-20P-AV",
                    finish_material="American Walnut / Brushed Steel",
                    facility_space=boardroom,
                    assigned_org_unit=org_unit_2,
                    move_coordinator=user,
                    quantity=1,
                    unit_replacement_cost=Decimal("18400.00"),
                    condition_grade="good",
                    move_status="in_place",
                )
            )

            _save_clean(
                AssetFurnitureFixture(
                    tenant=tenant,
                    name="Acoustic Demountable Glass Partition Wall Modules",
                    ffe_category="modular_partition",
                    asset_tag_code=f"FFE-{tenant.pk}-PRT04",
                    manufacturer="DIRTT",
                    model_sku="STC48-GL-10FT",
                    finish_material="Tempered Acoustic Glass / Black Frame",
                    facility_space=floor_2,
                    target_space=boardroom,
                    assigned_org_unit=org_unit_2,
                    move_coordinator=user,
                    quantity=8,
                    unit_replacement_cost=Decimal("2400.00"),
                    condition_grade="good",
                    move_status="scheduled_reconfig",
                    reconfiguration_batch_ref="IMAC-2026-RECFG",
                    move_scheduled_date=today + timezone.timedelta(days=14),
                    estimated_move_cost=Decimal("2100.00"),
                )
            )

            p_start = today.replace(day=1)
            p_end = today
            je_demo = None
            if fiscal_period and gl_exp and gl_rec and gl_exp.pk != gl_rec.pk:
                je_demo = JournalEntry.objects.create(
                    tenant=tenant,
                    entry_type="recurring",
                    entry_date=p_end,
                    fiscal_period=fiscal_period,
                    description="Demo Space Chargeback GL Allocation — Engineering Floor 02",
                    reference=f"AFCB-SEED-{tenant.pk}",
                    status="posted",
                    created_by=user,
                    approved_by=user,
                    posted_at=now - timezone.timedelta(days=2),
                )
                amt_posted = Decimal("14850.00")
                l1 = JournalLine(
                    entry=je_demo,
                    gl_account=gl_exp,
                    debit=amt_posted,
                    credit=Decimal("0.00"),
                    description="Floor 02 Departmental Space & CAM Chargeback",
                    party=occupant_party,
                    org_unit=org_unit_1,
                    currency=currency,
                )
                l1.full_clean()
                l1.save()
                l2 = JournalLine(
                    entry=je_demo,
                    gl_account=gl_rec,
                    debit=Decimal("0.00"),
                    credit=amt_posted,
                    description="Facility Cost Recovery Credit — Floor 02",
                    party=occupant_party,
                    org_unit=org_unit_1,
                    currency=currency,
                )
                l2.full_clean()
                l2.save()

            _save_clean(
                AssetSpaceChargeback(
                    tenant=tenant,
                    title="Monthly Floor 02 Engineering Space & HVAC Allocation",
                    coordination_type="space_chargeback",
                    allocation_basis="usable_sqft",
                    facility_space=floor_2,
                    shared_building_system=ahu_sys,
                    lease_contract=lease_contract,
                    fixed_asset=fixed_asset,
                    charged_org_unit=org_unit_1,
                    occupant_party=occupant_party,
                    currency=currency,
                    fiscal_period=fiscal_period,
                    expense_gl_account=gl_exp,
                    recovery_gl_account=gl_rec,
                    journal_entry=je_demo,
                    period_start=p_start,
                    period_end=p_end,
                    allocated_area_sqft=Decimal("13200.00"),
                    allocation_share_pct=Decimal("72.50"),
                    base_cost_amount=Decimal("11200.00"),
                    shared_cam_amount=Decimal("2450.00"),
                    utility_recovery_amount=Decimal("1200.00"),
                    ti_improvement_cost=Decimal("0.00"),
                    ti_allowance_offset=Decimal("0.00"),
                    status="posted_to_gl" if je_demo else "approved",
                    approved_by=user,
                    approved_at=now - timezone.timedelta(days=2),
                    notes="Posted monthly proportional BOMA usable area allocation.",
                )
            )

            _save_clean(
                AssetSpaceChargeback(
                    tenant=tenant,
                    title="Executive Boardroom AV & Shared HVAC Submeter Recovery",
                    coordination_type="cam_utility_recovery",
                    allocation_basis="submeter_usage",
                    facility_space=boardroom,
                    shared_building_system=ahu_sys,
                    lease_contract=lease_contract,
                    charged_org_unit=org_unit_2,
                    occupant_party=occupant_party,
                    currency=currency,
                    fiscal_period=fiscal_period,
                    expense_gl_account=gl_exp,
                    recovery_gl_account=gl_rec,
                    period_start=p_start,
                    period_end=p_end,
                    allocated_area_sqft=Decimal("920.00"),
                    allocation_share_pct=Decimal("27.50"),
                    base_cost_amount=Decimal("3200.00"),
                    shared_cam_amount=Decimal("640.00"),
                    utility_recovery_amount=Decimal("410.00"),
                    status="approved",
                    approved_by=user,
                    approved_at=now - timezone.timedelta(days=1),
                    notes="Approved by tenant admin and queued for GL posting.",
                )
            )

            _save_clean(
                AssetSpaceChargeback(
                    tenant=tenant,
                    title="Level 03 R&D Clean Suite Leasehold Improvement (TI) Amortization",
                    coordination_type="leasehold_improvement",
                    allocation_basis="direct_ti_cost",
                    facility_space=hq_building,
                    lease_contract=lease_contract,
                    fixed_asset=fixed_asset,
                    charged_org_unit=org_unit_2,
                    currency=currency,
                    fiscal_period=fiscal_period,
                    expense_gl_account=gl_exp,
                    recovery_gl_account=gl_rec,
                    period_start=p_start,
                    period_end=p_end,
                    amortization_end_date=today + timezone.timedelta(days=1095),
                    allocated_area_sqft=Decimal("2700.00"),
                    allocation_share_pct=Decimal("100.00"),
                    base_cost_amount=Decimal("2500.00"),
                    ti_improvement_cost=Decimal("28000.00"),
                    ti_allowance_offset=Decimal("12000.00"),
                    status="pending_approval",
                    notes="36-month tenant improvement cost net of landlord TI allowance.",
                )
            )

            _save_clean(
                AssetSpaceChargeback(
                    tenant=tenant,
                    title="Studio 204 Common Corridor & Life Safety Shared Allocation",
                    coordination_type="shared_asset_allocation",
                    allocation_basis="headcount",
                    facility_space=eng_bay,
                    charged_org_unit=org_unit_1,
                    currency=currency,
                    fiscal_period=fiscal_period,
                    expense_gl_account=gl_exp,
                    recovery_gl_account=gl_rec,
                    period_start=p_start,
                    period_end=p_end,
                    allocated_area_sqft=Decimal("3500.00"),
                    allocation_share_pct=Decimal("45.00"),
                    base_cost_amount=Decimal("1950.00"),
                    shared_cam_amount=Decimal("480.00"),
                    utility_recovery_amount=Decimal("320.00"),
                    status="draft",
                )
            )

        self.stdout.write(
            f"[{tenant.name}] 11.17 Seeding complete (6 spaces, 6 building systems, 4 FF&E items, 4 space chargebacks)."
        )

    def _seed_tenant_11_18(self, tenant):
        if ItHardwareAsset.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 11.18 ITAM data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 11.18 IT Asset Management (ITAM)...")

        user = User.objects.filter(tenant=tenant).first()
        currency = Currency.objects.filter(is_active=True).first()
        org_units = list(OrgUnit.objects.filter(tenant=tenant).order_by("id"))
        org_unit_1 = org_units[0] if org_units else None
        org_unit_2 = org_units[-1] if org_units else None
        vendor = (
            Party.objects.filter(tenant=tenant, roles__role__in=["vendor", "supplier"]).first()
            or Party.objects.filter(tenant=tenant).first()
        )
        gl_exp = (
            GLAccount.objects.filter(tenant=tenant, account_type="expense").first()
            or GLAccount.objects.filter(tenant=tenant).first()
        )
        po = PurchaseOrder.objects.filter(tenant=tenant).first()
        svc_contract = AssetServiceContract.objects.filter(tenant=tenant).first()
        scm_asset = Asset.objects.filter(tenant=tenant).first()
        svc_comp = ServiceComponent.objects.filter(tenant=tenant).first()

        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            # 1. IT Hardware Assets (5 varied lifecycle states & refresh horizons)
            hw_app = ItHardwareAsset.objects.create(
                tenant=tenant,
                hostname="prod-erp-app-01",
                fqdn="prod-erp-app-01.internal.acme.local",
                device_class="physical_server",
                serial_number="DL-R750-98412",
                asset_tag_code="IT-SRV-001",
                manufacturer="Dell Technologies",
                model_name="PowerEdge R750",
                mac_address="00:1B:44:11:3A:B7",
                ip_address="10.20.14.11",
                operating_system="Ubuntu LTS",
                os_version="24.04",
                cpu_spec="2x Intel Xeon Gold 6430",
                ram_gb=256,
                storage_gb=3840,
                bios_firmware_version="v2.1.4",
                rack_unit_ref="DC1-R04-U12",
                environment="production",
                criticality="critical",
                mdm_enrolled=False,
                mdm_platform="",
                disk_encryption_status="luks_encrypted",
                commissioned_date=today - timezone.timedelta(days=540),
                assigned_date=today - timezone.timedelta(days=540),
                vendor_eos_date=today + timezone.timedelta(days=540),
                vendor_eol_date=today + timezone.timedelta(days=900),
                refresh_cycle_months=48,
                refresh_due_date=today + timezone.timedelta(days=900),
                estimated_refresh_cost=Decimal("14500.00"),
                currency=currency,
                status="deployed",
                operational_asset=scm_asset,
                org_unit=org_unit_1,
                vendor_party=vendor,
                owner=user,
                notes="Primary ERP application cluster node 1.",
            )

            hw_db = ItHardwareAsset.objects.create(
                tenant=tenant,
                hostname="prod-db-replica-01",
                fqdn="prod-db-replica-01.internal.acme.local",
                device_class="virtual_host",
                serial_number="VM-SQL-44108",
                asset_tag_code="IT-VM-002",
                manufacturer="VMware",
                model_name="vSphere 8 Virtual Appliance",
                mac_address="00:50:56:88:1C:04",
                ip_address="10.20.18.22",
                operating_system="Red Hat Enterprise Linux",
                os_version="9.3",
                cpu_spec="32 vCPU",
                ram_gb=128,
                storage_gb=8192,
                rack_unit_ref="DC1-CL02",
                environment="production",
                criticality="critical",
                mdm_enrolled=False,
                mdm_platform="",
                disk_encryption_status="luks_encrypted",
                commissioned_date=today - timezone.timedelta(days=1100),
                vendor_eos_date=today + timezone.timedelta(days=20),
                vendor_eol_date=today + timezone.timedelta(days=75),
                refresh_cycle_months=36,
                refresh_due_date=today + timezone.timedelta(days=60),
                estimated_refresh_cost=Decimal("9800.00"),
                currency=currency,
                status="deployed",
                org_unit=org_unit_1,
                owner=user,
                notes="Approaching 90-day refresh window; scheduled migration to vSphere 9 / NVMe cluster.",
            )

            hw_fw = ItHardwareAsset.objects.create(
                tenant=tenant,
                hostname="core-fw-edge-01",
                fqdn="core-fw-edge-01.net.acme.local",
                device_class="router_firewall",
                serial_number="PAN-440-77301",
                asset_tag_code="IT-NET-003",
                manufacturer="Palo Alto Networks",
                model_name="PA-1410 Next-Gen Firewall",
                ip_address="10.0.1.1",
                operating_system="PAN-OS",
                os_version="11.1.2",
                rack_unit_ref="DC1-R01-U01",
                environment="production",
                criticality="critical",
                disk_encryption_status="exempt",
                commissioned_date=today - timezone.timedelta(days=1500),
                vendor_eos_date=today - timezone.timedelta(days=90),
                vendor_eol_date=today - timezone.timedelta(days=15),
                refresh_cycle_months=48,
                refresh_due_date=today - timezone.timedelta(days=15),
                estimated_refresh_cost=Decimal("18200.00"),
                currency=currency,
                status="pending_refresh",
                org_unit=org_unit_2,
                vendor_party=vendor,
                owner=user,
                notes="Past vendor EOL — prioritized on IT Refresh & EOL Workbench.",
            )

            hw_laptop = ItHardwareAsset.objects.create(
                tenant=tenant,
                hostname="ws-eng-m3-042",
                fqdn="ws-eng-m3-042.corp.acme.local",
                device_class="laptop",
                serial_number="C02Z91K8MD6R",
                asset_tag_code="IT-LTP-042",
                manufacturer="Apple",
                model_name="MacBook Pro 16 M3 Pro",
                mac_address="A4:83:E7:42:99:1A",
                operating_system="macOS",
                os_version="14.6",
                cpu_spec="Apple M3 Pro 12-core",
                ram_gb=36,
                storage_gb=1024,
                environment="corporate_enduser",
                criticality="medium",
                mdm_enrolled=True,
                mdm_platform="jamf_pro",
                mdm_device_id="JAMF-99412",
                disk_encryption_status="bitlocker_filevault",
                last_seen_checkin=now - timezone.timedelta(hours=3),
                commissioned_date=today - timezone.timedelta(days=200),
                assigned_date=today - timezone.timedelta(days=195),
                vendor_eos_date=today + timezone.timedelta(days=1100),
                vendor_eol_date=today + timezone.timedelta(days=1460),
                refresh_cycle_months=36,
                refresh_due_date=today + timezone.timedelta(days=900),
                estimated_refresh_cost=Decimal("2850.00"),
                currency=currency,
                status="deployed",
                org_unit=org_unit_2,
                owner=user,
                notes="MDM-managed engineering workstation.",
            )

            hw_san = ItHardwareAsset.objects.create(
                tenant=tenant,
                hostname="legacy-san-02",
                fqdn="legacy-san-02.dc1.acme.local",
                device_class="storage_array",
                serial_number="NTAP-FAS-33019",
                asset_tag_code="IT-SAN-002",
                manufacturer="NetApp",
                model_name="FAS2720 Hybrid Array",
                ip_address="10.20.90.5",
                operating_system="ONTAP",
                os_version="9.12P4",
                rack_unit_ref="DC1-R08-U20",
                environment="dr_standby",
                criticality="high",
                disk_encryption_status="luks_encrypted",
                commissioned_date=today - timezone.timedelta(days=1825),
                vendor_eos_date=today - timezone.timedelta(days=120),
                vendor_eol_date=today - timezone.timedelta(days=30),
                refresh_cycle_months=60,
                refresh_due_date=today - timezone.timedelta(days=30),
                estimated_refresh_cost=Decimal("24000.00"),
                currency=currency,
                sanitization_required=True,
                sanitization_method="crypto_erase",
                sanitization_status="pending_wipe",
                status="pending_refresh",
                org_unit=org_unit_1,
                owner=user,
                notes="Queued for NIST SP 800-88 cryptographic erase prior to ITAD disposition.",
            )

            # 2. Software Licenses (4 ELP scenarios: compliant, true_up_required, surplus_reclaimable, expiring)
            sw_m365 = SoftwareLicense.objects.create(
                tenant=tenant,
                software_name="Microsoft 365 E5 Enterprise",
                publisher_name="Microsoft",
                product_sku="M365-E5-UNATT",
                version_edition="Enterprise E5",
                software_category="productivity_suite",
                license_type="subscription_term",
                license_metric="per_user",
                agreement_number="EA-MSFT-2026-01",
                license_key_ref="MS365-****-9X2K",
                entitled_quantity=120,
                allocated_quantity=114,
                active_used_quantity=110,
                reclaimable_inactive_count=0,
                unit_license_cost=Decimal("684.00"),
                total_annual_spend=Decimal("82080.00"),
                currency=currency,
                effective_date=today - timezone.timedelta(days=180),
                renewal_date=today + timezone.timedelta(days=185),
                vendor_eol_date=today + timezone.timedelta(days=730),
                auto_renew=True,
                status="active_compliant",
                last_reconciled_at=now,
                publisher_party=vendor,
                org_unit=org_unit_1,
                gl_expense_account=gl_exp,
                purchase_order=po,
                service_contract=svc_contract,
                license_owner=user,
                notes="Primary identity and office productivity entitlement.",
            )

            sw_oracle = SoftwareLicense.objects.create(
                tenant=tenant,
                software_name="Oracle Database Enterprise Edition",
                publisher_name="Oracle",
                product_sku="ORCL-DBEE-PROC",
                version_edition="23ai",
                software_category="database_engine",
                license_type="enterprise_ela",
                license_metric="per_core",
                agreement_number="OMA-ORCL-8821",
                license_key_ref="ORCL-****-4P9M",
                entitled_quantity=16,
                allocated_quantity=20,
                active_used_quantity=20,
                reclaimable_inactive_count=0,
                unit_license_cost=Decimal("4750.00"),
                total_annual_spend=Decimal("76000.00"),
                currency=currency,
                effective_date=today - timezone.timedelta(days=300),
                renewal_date=today + timezone.timedelta(days=65),
                vendor_eol_date=today + timezone.timedelta(days=1095),
                auto_renew=False,
                status="true_up_required",
                last_reconciled_at=now,
                org_unit=org_unit_1,
                license_owner=user,
                notes="4 extra cores active on failover node; true-up review scheduled.",
            )

            sw_jb = SoftwareLicense.objects.create(
                tenant=tenant,
                software_name="JetBrains All Products Pack",
                publisher_name="JetBrains",
                product_sku="JB-ALL-ORG",
                version_edition="2026.1",
                software_category="devops_ide",
                license_type="subscription_term",
                license_metric="per_user",
                agreement_number="JB-INV-55201",
                license_key_ref="JBRN-****-7T1L",
                entitled_quantity=50,
                allocated_quantity=44,
                active_used_quantity=32,
                reclaimable_inactive_count=9,
                unit_license_cost=Decimal("289.00"),
                total_annual_spend=Decimal("14450.00"),
                currency=currency,
                effective_date=today - timezone.timedelta(days=290),
                renewal_date=today + timezone.timedelta(days=45),
                vendor_eol_date=today + timezone.timedelta(days=500),
                auto_renew=True,
                status="surplus_reclaimable",
                last_reconciled_at=now,
                org_unit=org_unit_2,
                license_owner=user,
                notes="9 seats inactive >30 days eligible for license harvesting.",
            )

            SoftwareLicense.objects.create(
                tenant=tenant,
                software_name="Autodesk AutoCAD LT Commercial",
                publisher_name="Autodesk",
                product_sku="ADSK-ACDLT-26",
                version_edition="2026",
                software_category="design_cad",
                license_type="perpetual",
                license_metric="per_user",
                agreement_number="ADSK-90122",
                license_key_ref="ADSK-****-8Q3N",
                entitled_quantity=12,
                allocated_quantity=10,
                active_used_quantity=9,
                reclaimable_inactive_count=1,
                unit_license_cost=Decimal("495.00"),
                total_annual_spend=Decimal("5940.00"),
                currency=currency,
                effective_date=today - timezone.timedelta(days=340),
                renewal_date=today + timezone.timedelta(days=25),
                vendor_eol_date=today + timezone.timedelta(days=400),
                auto_renew=False,
                status="active_compliant",
                last_reconciled_at=now,
                org_unit=org_unit_2,
                license_owner=user,
                notes="Upcoming renewal cliff inside 30 days.",
            )

            # 3. Cloud Assets & SaaS Subscriptions (4 FinOps / Shadow IT scenarios)
            cl_aws = CloudAssetSubscription.objects.create(
                tenant=tenant,
                name="AWS Production EKS & RDS Reserved Cluster",
                asset_kind="reserved_instance",
                provider="aws",
                external_account_id="aws-acct-10482910",
                cloud_resource_id="arn:aws:eks:us-east-1:10482910:cluster/naverp-prod",
                cloud_region="us-east-1",
                environment="production",
                resource_tags={"env": "prod", "cost_center": "CC-INFRA", "owner": "platform-ops"},
                billing_cadence="monthly",
                commitment_term="1yr_reserved",
                monthly_recurring_cost=Decimal("6420.00"),
                annual_contract_value=Decimal("77040.00"),
                currency=currency,
                provisioned_seats=0,
                active_seats_30d=0,
                sso_status="sso_enforced",
                approval_status="sanctioned",
                renewal_date=today + timezone.timedelta(days=140),
                cancellation_notice_days=30,
                auto_renew=True,
                status="active",
                last_finops_sync_at=now,
                org_unit=org_unit_1,
                vendor_party=vendor,
                gl_expense_account=gl_exp,
                business_owner=user,
                technical_owner=user,
                notes="Core AWS Kubernetes + multi-AZ Postgres commitment.",
            )

            cl_dd = CloudAssetSubscription.objects.create(
                tenant=tenant,
                name="Datadog Enterprise APM & Log Analytics",
                asset_kind="saas_application",
                provider="datadog",
                external_account_id="dd-org-acme-01",
                cloud_resource_id="https://app.datadoghq.com/org/acme",
                cloud_region="us1",
                environment="corporate_saas",
                resource_tags={"env": "prod", "cost_center": "CC-SRE", "owner": "sre-team"},
                billing_cadence="annual",
                commitment_term="annual_contract",
                monthly_recurring_cost=Decimal("2250.00"),
                annual_contract_value=Decimal("27000.00"),
                currency=currency,
                provisioned_seats=40,
                active_seats_30d=34,
                sso_status="sso_enforced",
                approval_status="sanctioned",
                renewal_date=today + timezone.timedelta(days=20),
                cancellation_notice_days=45,
                auto_renew=True,
                status="expiring_soon",
                last_finops_sync_at=now,
                org_unit=org_unit_1,
                business_owner=user,
                technical_owner=user,
                notes="Annual renewal notice deadline within 30 days.",
            )

            CloudAssetSubscription.objects.create(
                tenant=tenant,
                name="Uncategorized Kanban Cloud Workspace",
                asset_kind="saas_application",
                provider="other_saas",
                external_account_id="card-expense-8812",
                cloud_region="global",
                environment="corporate_saas",
                resource_tags={},
                billing_cadence="monthly",
                commitment_term="monthly_flex",
                monthly_recurring_cost=Decimal("490.00"),
                annual_contract_value=Decimal("5880.00"),
                currency=currency,
                provisioned_seats=28,
                active_seats_30d=19,
                sso_status="shadow_it_unapproved",
                approval_status="shadow_it_flagged",
                renewal_date=today + timezone.timedelta(days=12),
                cancellation_notice_days=7,
                auto_renew=True,
                status="shadow_flagged",
                last_finops_sync_at=now,
                org_unit=org_unit_2,
                business_owner=user,
                notes="Detected via corporate expense ledger without SAML SSO.",
            )

            CloudAssetSubscription.objects.create(
                tenant=tenant,
                name="Snowflake Enterprise Analytics Warehouse",
                asset_kind="paas_database",
                provider="other_saas",
                external_account_id="sf-acme-us-east",
                cloud_region="us-east-1",
                environment="production",
                resource_tags={"env": "prod", "cost_center": "CC-DATA"},
                billing_cadence="monthly",
                commitment_term="monthly_flex",
                monthly_recurring_cost=Decimal("3100.00"),
                annual_contract_value=Decimal("37200.00"),
                currency=currency,
                provisioned_seats=60,
                active_seats_30d=18,
                sso_status="sso_optional",
                approval_status="consolidation_target",
                renewal_date=today + timezone.timedelta(days=110),
                cancellation_notice_days=30,
                auto_renew=False,
                status="underutilized",
                last_finops_sync_at=now,
                org_unit=org_unit_2,
                business_owner=user,
                technical_owner=user,
                notes="30% 30-day active reader ratio — candidate for seat right-sizing.",
            )

            # 4. CMDB Dependency Edges (multi-hop graph spanning HW, SW, Cloud, Service, SCM)
            if svc_comp is not None:
                CmdbRelationship.objects.create(
                    tenant=tenant,
                    source_ci_type="service_component",
                    source_service=svc_comp,
                    relationship_type="hosted_in",
                    target_ci_type="cloud_asset",
                    target_cloud=cl_aws,
                    environment="production",
                    criticality="tier_1_mission_critical",
                    impact_severity="hard_outage",
                    is_single_point_of_failure=False,
                    verified_on=today,
                    verified_by=user,
                    status="active",
                    owner=user,
                    blast_radius_notes="Core customer service hosted on AWS production EKS cluster.",
                )

            CmdbRelationship.objects.create(
                tenant=tenant,
                source_ci_type="cloud_asset",
                source_cloud=cl_dd,
                relationship_type="integrates_with",
                target_ci_type="cloud_asset",
                target_cloud=cl_aws,
                environment="production",
                criticality="tier_2_business_important",
                impact_severity="degraded_performance",
                is_single_point_of_failure=False,
                verified_on=today,
                verified_by=user,
                status="active",
                owner=user,
                blast_radius_notes="Datadog agents stream telemetry from EKS prod cluster.",
            )

            CmdbRelationship.objects.create(
                tenant=tenant,
                source_ci_type="it_hardware",
                source_hardware=hw_app,
                relationship_type="depends_on",
                target_ci_type="it_hardware",
                target_hardware=hw_db,
                environment="production",
                criticality="tier_1_mission_critical",
                impact_severity="hard_outage",
                is_single_point_of_failure=True,
                verified_on=today,
                verified_by=user,
                status="active",
                owner=user,
                blast_radius_notes="SPOF: ERP application tier relies directly on database host.",
            )

            CmdbRelationship.objects.create(
                tenant=tenant,
                source_ci_type="it_hardware",
                source_hardware=hw_db,
                relationship_type="licensed_by",
                target_ci_type="software_license",
                target_software=sw_oracle,
                environment="production",
                criticality="tier_1_mission_critical",
                impact_severity="informational",
                is_single_point_of_failure=False,
                verified_on=today,
                verified_by=user,
                status="active",
                owner=user,
                blast_radius_notes="Oracle DB core allocation bound to database host.",
            )

            CmdbRelationship.objects.create(
                tenant=tenant,
                source_ci_type="it_hardware",
                source_hardware=hw_app,
                relationship_type="connects_to",
                target_ci_type="it_hardware",
                target_hardware=hw_fw,
                environment="production",
                criticality="tier_1_mission_critical",
                impact_severity="hard_outage",
                is_single_point_of_failure=True,
                verified_on=today,
                verified_by=user,
                status="active",
                owner=user,
                blast_radius_notes="Ingress/egress traffic passes through edge firewall pending refresh.",
            )

            if scm_asset is not None:
                CmdbRelationship.objects.create(
                    tenant=tenant,
                    source_ci_type="it_hardware",
                    source_hardware=hw_san,
                    relationship_type="backed_up_by",
                    target_ci_type="operational_asset",
                    target_asset=scm_asset,
                    environment="dr_failover",
                    criticality="tier_2_business_important",
                    impact_severity="failover_available",
                    is_single_point_of_failure=False,
                    verified_on=today,
                    verified_by=user,
                    status="deprecated",
                    owner=user,
                    blast_radius_notes="Legacy storage array scheduled for NIST wipe & decommission.",
                )

            CmdbRelationship.objects.create(
                tenant=tenant,
                source_ci_type="it_hardware",
                source_hardware=hw_laptop,
                relationship_type="licensed_by",
                target_ci_type="software_license",
                target_software=sw_m365,
                environment="shared_infra",
                criticality="tier_3_operational",
                impact_severity="informational",
                is_single_point_of_failure=False,
                verified_on=today,
                verified_by=user,
                status="active",
                owner=user,
                blast_radius_notes="Managed endpoint allocated M365 E5 productivity suite.",
            )

        self.stdout.write(
            f"[{tenant.name}] 11.18 ITAM Seeding complete (5 hardware assets, 4 software licenses, 4 cloud/SaaS subscriptions, CMDB topology edges)."
        )


