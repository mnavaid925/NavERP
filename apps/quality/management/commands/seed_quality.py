import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Party, Tenant
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.quality.models.CapaManagement.CapaActions import CapaAction
from apps.quality.models.CapaManagement.CapaEffectivenessReviews import CapaEffectivenessReview
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.CapaManagement.RootCauseAnalyses import RootCauseAnalysis
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgment
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord
from apps.quality.models.IncomingQuality.CertificatesOfAnalysis import (
    CertificateOfAnalysis,
)
from apps.quality.models.IncomingQuality.IncomingInspectionLots import (
    IncomingInspectionLot,
)
from apps.quality.models.IncomingQuality.IncomingInspectionPlans import (
    IncomingInspectionPlan,
)
from apps.quality.models.IncomingQuality.QualityReturnAuthorizations import (
    QualityReturnAuthorization,
)
from apps.quality.models.NonConformance.MrbDispositions import MrbDisposition
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.ProcessDeviations import ProcessDeviation
from apps.quality.models.NonConformance.QuarantineContainments import QuarantineContainment
from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment
from apps.quality.models.RiskManagement.RiskControlMeasures import RiskControlMeasure
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan
from apps.quality.models.RiskManagement.RiskReviewRecords import RiskReviewRecord
from apps.quality.models.SupplierQuality.SupplierChangeNotifications import (
    SupplierChangeNotification,
)
from apps.quality.models.SupplierQuality.SupplierCorrectiveActions import (
    SupplierCorrectiveAction,
)
from apps.quality.models.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAudit,
)
from apps.quality.models.SupplierQuality.SupplierQualityScorecards import (
    SupplierQualityScorecard,
)
from apps.quality.models.InProcessQuality.FirstArticleInspections import (
    FirstArticleInspection,
)
from apps.quality.models.InProcessQuality.InProcessInspections import (
    InProcessInspection,
)
from apps.quality.models.InProcessQuality.LayeredProcessAudits import (
    LayeredProcessAudit,
)
from apps.quality.models.InProcessQuality.ProcessParameterLogs import (
    ProcessParameterLog,
)
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import CalibrationRecord
from apps.quality.models.CalibrationAnalysis.OutOfToleranceInvestigations import OutOfToleranceInvestigation
from apps.quality.models.CalibrationAnalysis.MeasurementSystemAnalyses import MeasurementSystemAnalysis
from apps.quality.models.FinalQuality.CertificatesOfConformance import (
    CertificateOfConformance,
)
from apps.quality.models.FinalQuality.FinalInspectionLots import (
    FinalInspectionLot,
)
from apps.quality.models.FinalQuality.PackagingLabelVerifications import (
    PackagingLabelVerification,
)
from apps.quality.models.FinalQuality.QualityReleaseAuthorizations import (
    QualityReleaseAuthorization,
)
from apps.quality.models.AuditManagement.AuditPrograms import AuditProgram
from apps.quality.models.AuditManagement.QualityAudits import QualityAudit
from apps.quality.models.AuditManagement.AuditFindings import AuditFinding
from apps.quality.models.AuditManagement.RegulatoryInspectionHosts import RegulatoryInspectionHost
from apps.quality.models.TrainingCompetency.CompetencyCertifications import CompetencyCertification
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse
from apps.quality.models.TrainingCompetency.TrainingEnrollments import TrainingEnrollment
from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.models.CustomerComplaints.ComplaintInvestigations import ComplaintInvestigation
from apps.quality.models.CustomerComplaints.RegulatoryReports import RegulatoryReport
from apps.quality.models.CustomerComplaints.FieldActions import FieldAction
from apps.quality.models.ManagementReview.ManagementReviewActions import (
    ManagementReviewAction,
)
from apps.quality.models.ManagementReview.ManagementReviewInputs import (
    ManagementReviewInput,
)
from apps.quality.models.ManagementReview.ManagementReviews import (
    ManagementReview,
)
from apps.quality.models.ManagementReview.QualityObjectives import (
    QualityObjective,
)
from apps.quality.models.ProcessValidation.ValidationProtocols import (
    ValidationProtocol,
)
from apps.quality.models.ProcessValidation.ProcessCapabilityStudies import (
    ProcessCapabilityStudy,
)
from apps.quality.models.ProcessValidation.ComputerSystemValidations import (
    ComputerSystemValidation,
)
from apps.quality.models.ProcessValidation.CleaningValidations import (
    CleaningValidation,
)
from apps.quality.models.EhsManagement.HazardousMaterials import (
    HazardousMaterial,
)
from apps.quality.models.EhsManagement.SafetyIncidents import (
    SafetyIncident,
)
from apps.quality.models.EhsManagement.EnvironmentalMonitoringLogs import (
    EnvironmentalMonitoringLog,
)
from apps.quality.models.EhsManagement.WasteDisposalManifests import (
    WasteDisposalManifest,
)


User = get_user_model()


class Command(BaseCommand):
    help = "Seeds demo data for Module 12: Quality Management System (QMS)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing quality module data before seeding",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing quality module data...")
            WasteDisposalManifest.objects.all().delete()
            EnvironmentalMonitoringLog.objects.all().delete()
            SafetyIncident.objects.all().delete()
            HazardousMaterial.objects.all().delete()
            CleaningValidation.objects.all().delete()
            ComputerSystemValidation.objects.all().delete()
            ProcessCapabilityStudy.objects.all().delete()
            ValidationProtocol.objects.all().delete()
            ManagementReviewAction.objects.all().delete()
            ManagementReviewInput.objects.all().delete()
            ManagementReview.objects.all().delete()
            QualityObjective.objects.all().delete()
            FieldAction.objects.all().delete()
            RegulatoryReport.objects.all().delete()
            ComplaintInvestigation.objects.all().delete()
            CustomerComplaint.objects.all().delete()
            CompetencyCertification.objects.all().delete()
            TrainingEnrollment.objects.all().delete()
            QualityTrainingCourse.objects.all().delete()
            CompetencyMatrix.objects.all().delete()
            RegulatoryInspectionHost.objects.all().delete()
            AuditFinding.objects.all().delete()
            QualityAudit.objects.all().delete()
            AuditProgram.objects.all().delete()
            MeasurementSystemAnalysis.objects.all().delete()
            OutOfToleranceInvestigation.objects.all().delete()
            CalibrationRecord.objects.all().delete()
            CalibrationGage.objects.all().update(reference_standard_parent=None)
            CalibrationGage.objects.all().delete()
            QualityReleaseAuthorization.objects.all().delete()
            PackagingLabelVerification.objects.all().delete()
            CertificateOfConformance.objects.all().delete()
            FinalInspectionLot.objects.all().delete()
            LayeredProcessAudit.objects.all().delete()
            ProcessParameterLog.objects.all().delete()
            FirstArticleInspection.objects.all().delete()
            InProcessInspection.objects.all().delete()
            QualityReturnAuthorization.objects.all().delete()
            CertificateOfAnalysis.objects.all().delete()
            IncomingInspectionLot.objects.all().delete()
            IncomingInspectionPlan.objects.all().delete()
            SupplierChangeNotification.objects.all().delete()
            SupplierCorrectiveAction.objects.all().delete()
            SupplierQualityScorecard.objects.all().delete()
            SupplierQualificationAudit.objects.all().delete()
            ProcessDeviation.objects.all().delete()
            MrbDisposition.objects.all().delete()
            QuarantineContainment.objects.all().delete()
            NonConformanceReport.objects.all().delete()
            CapaEffectivenessReview.objects.all().delete()
            CapaAction.objects.all().delete()
            RootCauseAnalysis.objects.all().delete()
            CapaInvestigation.objects.all().delete()
            RiskReviewRecord.objects.all().delete()
            RiskControlMeasure.objects.all().delete()
            RiskAssessment.objects.all().delete()
            RiskManagementPlan.objects.all().delete()
            DesignVerification.objects.all().delete()
            DesignReview.objects.all().delete()
            DesignInput.objects.all().delete()
            DesignProject.objects.all().delete()
            DocumentAcknowledgment.objects.all().delete()
            ElectronicSignatureRecord.objects.all().delete()
            DocumentChangeOrder.objects.all().delete()
            ControlledDocument.objects.all().update(supersedes=None, superseded_by=None)
            ControlledDocument.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Quality data flushed successfully."))

        tenants = Tenant.objects.all()
        if not tenants.exists():
            self.stdout.write(self.style.ERROR("No tenants found. Run seed_accounts / seed_core first."))
            return

        for tenant in tenants:
            self._seed_submodule_12_1(tenant)
            self._seed_submodule_12_2(tenant)
            self._seed_submodule_12_3(tenant)
            self._seed_submodule_12_4(tenant)
            self._seed_submodule_12_5(tenant)
            self._seed_submodule_12_6(tenant)
            self._seed_submodule_12_7(tenant)
            self._seed_submodule_12_8(tenant)
            self._seed_submodule_12_9(tenant)
            self._seed_submodule_12_10(tenant)
            self._seed_submodule_12_11(tenant)
            self._seed_submodule_12_12(tenant)
            self._seed_submodule_12_13(tenant)
            self._seed_submodule_12_14(tenant)
            self._seed_submodule_12_15(tenant)
            self._seed_submodule_12_16(tenant)


        self.stdout.write(self.style.SUCCESS("Module 12 quality seeding complete."))
        self.stdout.write(
            "NOTE: The global 'admin' superuser has tenant=None by design and cannot view tenant-scoped records."
        )
        self.stdout.write(
            "Log in as a tenant user (e.g. admin_acme / password) to inspect seeded quality data."
        )

    def _seed_submodule_12_1(self, tenant):
        if ControlledDocument.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.1 Document Control data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.1 Document Control & Management...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        if not admin_user:
            self.stdout.write(f"[{tenant.name}] Warning: No user found for tenant.")
            return

        users = list(User.objects.filter(tenant=tenant).order_by("pk"))
        reviewer_user = users[1] if len(users) > 1 else admin_user

        qa_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="quality").order_by("pk").first()
        if not qa_dept:
            qa_dept = OrgUnit.objects.filter(tenant=tenant).order_by("pk").first()

        ops_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="operation").order_by("pk").first()
        if not ops_dept:
            ops_dept = OrgUnit.objects.filter(tenant=tenant).order_by("pk").last()

        employee = EmployeeProfile.objects.filter(tenant=tenant).order_by("pk").first()

        today = timezone.now().date()
        now = timezone.now()

        with transaction.atomic():
            # 1. Superseded Predecessor SOP (0.9)
            doc_legacy = ControlledDocument.objects.create(
                tenant=tenant,
                title="Good Documentation Practices (GDP) & Quality Records",
                document_type="sop",
                department=qa_dept,
                owner=admin_user,
                revision="0.9",
                is_latest_revision=False,
                lifecycle_state="superseded",
                classification="internal",
                description="Early draft guideline on Good Documentation Practices.",
                change_summary="Initial operational draft before formal 21 CFR Part 11 validation.",
                effective_date=today - datetime.timedelta(days=365),
                review_interval_months=12,
                next_review_date=today - datetime.timedelta(days=1),
                retention_years=10,
            )

            # 2. Currently Effective Master SOP (Rev 1.0)
            doc_effective = ControlledDocument.objects.create(
                tenant=tenant,
                title="Good Documentation Practices (GDP) & Quality Records",
                document_type="sop",
                department=qa_dept,
                owner=admin_user,
                revision="1.0",
                is_latest_revision=True,
                lifecycle_state="effective",
                classification="internal",
                description="Governing Standard Operating Procedure defining data integrity standards, contemporaneous ALCOA+ record entries, corrections, and electronic signature protocols per FDA 21 CFR Part 11 and ISO 13485:2016.",
                change_summary="Formal release incorporating 21 CFR Part 11 signature manifests and automated read-and-acknowledge distribution.",
                effective_date=today - datetime.timedelta(days=90),
                review_interval_months=12,
                next_review_date=today + datetime.timedelta(days=275),
                retention_years=10,
                supersedes=doc_legacy,
            )
            doc_legacy.superseded_by = doc_effective
            doc_legacy.save(update_fields=["superseded_by"])

            # 3. Policy (Effective)
            doc_policy = ControlledDocument.objects.create(
                tenant=tenant,
                title="Corporate Quality Policy & Management Responsibility",
                document_type="policy",
                department=qa_dept,
                owner=admin_user,
                revision="1.0",
                is_latest_revision=True,
                lifecycle_state="effective",
                classification="public",
                description="Foundational quality policy establishing executive commitment to customer satisfaction, regulatory compliance, and continual quality management improvement.",
                change_summary="Executive charter approval for global manufacturing and distribution facilities.",
                effective_date=today - datetime.timedelta(days=180),
                review_interval_months=12,
                next_review_date=today + datetime.timedelta(days=185),
                retention_years=15,
            )

            # 4. Work Instruction (In Review)
            doc_wi = ControlledDocument.objects.create(
                tenant=tenant,
                title="Document Change Order Execution and CCB Review Protocol",
                document_type="wi",
                department=qa_dept,
                owner=reviewer_user,
                revision="1.0",
                is_latest_revision=True,
                lifecycle_state="in_review",
                classification="internal",
                description="Step-by-step procedural instruction detailing the lifecycle routing of formal Document Change Orders, Change Control Board agendas, and impact evaluations.",
                change_summary="New procedural instruction written to standardize routing workflows.",
                effective_date=None,
                review_interval_months=12,
                retention_years=7,
            )

            # 5. Quality Template / Form (Effective)
            doc_form = ControlledDocument.objects.create(
                tenant=tenant,
                title="Standard Operating Procedure Authoring Template",
                document_type="form",
                department=qa_dept,
                owner=admin_user,
                revision="2.0",
                is_latest_revision=True,
                lifecycle_state="effective",
                classification="internal",
                description="Controlled template format for drafting Standard Operating Procedures and Work Instructions.",
                change_summary="Standardized typography, mandatory 21 CFR Part 11 signature block, and version control header.",
                effective_date=today - datetime.timedelta(days=60),
                review_interval_months=24,
                next_review_date=today + datetime.timedelta(days=670),
                retention_years=5,
                is_template=True,
            )

            # 6. Obsolete Procedure
            doc_obsolete = ControlledDocument.objects.create(
                tenant=tenant,
                title="Legacy Physical Paper Vault Archive & Binder Indexing Protocol",
                document_type="sop",
                department=ops_dept or qa_dept,
                owner=admin_user,
                revision="3.2",
                is_latest_revision=False,
                lifecycle_state="obsolete",
                classification="internal",
                description="Historical protocol governing manual three-ring binder distribution and paper stamping.",
                change_summary="Retired and replaced by NavERP cloud electronic document management.",
                effective_date=today - datetime.timedelta(days=730),
                review_interval_months=12,
                retention_years=20,
                archived_at=timezone.now() - datetime.timedelta(days=90),
            )

            # 7. Document Change Orders
            dco1 = DocumentChangeOrder.objects.create(
                tenant=tenant,
                title="Annual GDP Procedure Revision & Digital Signature Enactment",
                change_type="major_revision",
                priority="high",
                document=doc_effective,
                target_revision="1.0",
                reason_for_change="Periodic regulatory audit finding required electronic signature non-repudiation.",
                change_description="Upgraded from pre-release Rev 0.9 to formal validated Rev 1.0 with 21 CFR Part 11 hash binding.",
                regulatory_impact=True,
                training_required=True,
                impact_assessment="All manufacturing floor leads and QA auditors must complete read-and-acknowledge sign-off.",
                status="implemented",
                requested_by=admin_user,
                target_effective_date=today - datetime.timedelta(days=90),
                ccb_decision="approved",
                ccb_decision_date=today - datetime.timedelta(days=95),
                ccb_decision_by=admin_user,
                closure_notes="Formally reviewed and authorized by Change Control Board.",
                closed_at=timezone.now() - datetime.timedelta(days=90),
            )

            dco2 = DocumentChangeOrder.objects.create(
                tenant=tenant,
                title="Update Work Instruction for CCB Emergency Change Thresholds",
                change_type="minor_revision",
                priority="standard",
                document=doc_wi,
                target_revision="1.1",
                reason_for_change="Harmonize emergency change request approvals with ISO 13485:2016 Clause 4.2.4.",
                change_description="Added clause 4.3 clarifying expedited QA emergency approvals with post-release verification.",
                regulatory_impact=False,
                training_required=True,
                impact_assessment="Affects QA administrators and department managers.",
                status="ccb_review",
                requested_by=reviewer_user,
                target_effective_date=today + datetime.timedelta(days=14),
                ccb_decision="pending",
            )

            # 8. 21 CFR Part 11 Electronic Signatures
            sig_author = ElectronicSignatureRecord.objects.create(
                tenant=tenant,
                document=doc_effective,
                change_order=dco1,
                signer=admin_user,
                signer_name=admin_user.get_full_name() or admin_user.username,
                signer_title="Principal Quality Assurance Engineer",
                signature_meaning="authored",
                document_revision="1.0",
                comments="Authored and validated per GxP requirements.",
                ip_address="127.0.0.1",
            )

            sig_qa = ElectronicSignatureRecord.objects.create(
                tenant=tenant,
                document=doc_effective,
                change_order=dco1,
                signer=reviewer_user,
                signer_name=reviewer_user.get_full_name() or reviewer_user.username,
                signer_title="Director of Regulatory Affairs & Quality",
                signature_meaning="quality_approval",
                document_revision="1.0",
                comments="Official quality assurance release authorization.",
                ip_address="127.0.0.1",
            )

            # 9. Document Acknowledgments (Read & Acknowledge)
            ack_done = DocumentAcknowledgment.objects.create(
                tenant=tenant,
                document=doc_effective,
                document_revision="1.0",
                user=admin_user,
                employee=employee,
                due_date=today + datetime.timedelta(days=30),
                status="acknowledged",
                acknowledged_at=timezone.now() - datetime.timedelta(days=80),
                notes="Completed initial training review upon document release.",
            )

            # Create acknowledgment signature
            sig_ack = ElectronicSignatureRecord.objects.create(
                tenant=tenant,
                document=doc_effective,
                signer=admin_user,
                signer_name=admin_user.get_full_name() or admin_user.username,
                signer_title="System Administrator / QA Specialist",
                signature_meaning="acknowledgment",
                document_revision="1.0",
                comments="I have read, understood, and agree to adhere to Good Documentation Practices.",
                ip_address="127.0.0.1",
            )
            ack_done.signature_record = sig_ack
            ack_done.save(update_fields=["signature_record"])

            if reviewer_user != admin_user:
                DocumentAcknowledgment.objects.create(
                    tenant=tenant,
                    document=doc_effective,
                    document_revision="1.0",
                    user=reviewer_user,
                    due_date=today + datetime.timedelta(days=14),
                    status="pending",
                    notes="Mandatory read-and-acknowledge sign-off required.",
                )

            # Overdue demo acknowledgment
            DocumentAcknowledgment.objects.create(
                tenant=tenant,
                document=doc_policy,
                document_revision="1.0",
                user=admin_user,
                due_date=today - datetime.timedelta(days=5),
                status="pending",
                notes="Annual quality policy reaffirmation sign-off (Overdue).",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.1 Document Control seeded successfully."))

    def _seed_submodule_12_2(self, tenant):
        if DesignProject.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.2 Design Controls data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.2 Design Controls & Development...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        if not admin_user:
            return

        users = list(User.objects.filter(tenant=tenant).order_by("pk"))
        reviewer_user = users[1] if len(users) > 1 else admin_user

        qa_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="quality").order_by("pk").first()
        if not qa_dept:
            qa_dept = OrgUnit.objects.filter(tenant=tenant).order_by("pk").first()

        doc_sop = ControlledDocument.objects.filter(tenant=tenant, document_type="sop").order_by("pk").first()

        today = timezone.now().date()
        now = timezone.now()

        with transaction.atomic():
            # 1. Active Design Project: Smart Infusion Pump System
            project_active = DesignProject.objects.create(
                tenant=tenant,
                title="NextGen Smart Infusion Pump System",
                device_name="InfuseFlow Pro 3000",
                device_class="class_ii",
                regulatory_pathway="510k",
                intended_use="Controlled volumetric administration of intravenous fluids and medications to adult and pediatric patients.",
                current_phase="output_verification",
                status="active",
                project_lead=admin_user,
                quality_lead=reviewer_user,
                department=qa_dept,
                target_completion_date=today + datetime.timedelta(days=120),
                dhf_location="DHF-VOL-01 / Central QMS Cloud Vault",
                dhf_locked=False,
                description="Electromechanical large volume pump with dedicated drug library, wireless telemetry, and closed-loop occlusion pressure monitoring.",
            )

            # 2. Completed / Locked Design Project: Sterile Disposable Syringe Set
            project_locked = DesignProject.objects.create(
                tenant=tenant,
                title="Sterile Disposable Syringe Set Development",
                device_name="AccuInject 5mL Safety Syringe",
                device_class="class_ii",
                regulatory_pathway="510k",
                intended_use="General purpose sterile piston syringe with integrated needle retract mechanism for aspiration and injection.",
                current_phase="closed",
                status="completed",
                project_lead=admin_user,
                quality_lead=reviewer_user,
                department=qa_dept,
                target_completion_date=today - datetime.timedelta(days=60),
                actual_completion_date=today - datetime.timedelta(days=45),
                dhf_location="DHF-ARCHIVE-ACCUINJECT-01",
                dhf_locked=True,
                description="Commercialized safety needle syringe. DHF frozen post manufacturing transfer.",
            )

            # 3. Design Inputs for Active Project
            un_01 = DesignInput.objects.create(
                tenant=tenant,
                project=project_active,
                identifier="UN-001",
                title="Clinician Flow Rate Accuracy",
                input_type="user_need",
                priority="critical",
                status="approved",
                description="The clinician must be able to administer liquid medications at programmed flow rates without dangerous under- or over-infusion.",
                acceptance_criteria="Flow delivery rate deviation within +/- 2.0% across all programmed flow rates from 0.1 mL/hr to 1200 mL/hr.",
                rationale="Prevent patient medication dosage error and hemodynamic instability.",
                owner=admin_user,
                version="1.0",
            )

            di_flow_01 = DesignInput.objects.create(
                tenant=tenant,
                project=project_active,
                identifier="DI-FLOW-01",
                title="Volumetric Motor Step Precision",
                input_type="functional",
                priority="critical",
                status="verified",
                description="The stepper motor lead-screw mechanism shall deliver precise bolus volumes conforming to target flow rate.",
                acceptance_criteria="Volumetric displacement variance shall not exceed 1.5% at nominal back-pressure.",
                rationale="Directly derives from User Need UN-001 clinician accuracy requirement.",
                user_need_parent=un_01,
                controlled_document=doc_sop,
                owner=admin_user,
                version="1.0",
            )

            di_flow_02 = DesignInput.objects.create(
                tenant=tenant,
                project=project_active,
                identifier="DI-FLOW-02",
                title="Battery Runtime Under High Flow",
                input_type="performance",
                priority="major",
                status="verified",
                description="The internal rechargeable lithium-ion battery shall power continuous delivery at maximum rated flow for at least 8 hours.",
                acceptance_criteria="Battery duration >= 8.0 hours continuous at 125 mL/hr flow rate without AC mains connection.",
                rationale="Supports safe patient intra-hospital transport per IEC 60601-2-24.",
                user_need_parent=un_01,
                owner=admin_user,
                version="1.0",
            )

            di_safe_01 = DesignInput.objects.create(
                tenant=tenant,
                project=project_active,
                identifier="DI-SAFE-01",
                title="Air-in-Line Ultrasonic Detection & Alarm",
                input_type="safety",
                priority="critical",
                status="in_review",
                description="The system shall detect micro air bubbles in the administration line and halt pumping with audible and visual alarms.",
                acceptance_criteria="Single bubble >= 50 microliters or cumulative 100 microliters/15min triggers immediate pump stop within 200ms.",
                rationale="Mitigates life-threatening air embolism hazard per ISO 14971 risk analysis.",
                user_need_parent=un_01,
                owner=reviewer_user,
                version="1.0",
            )

            # 4. Stage-Gate Design Reviews for Active Project
            sig_review = ElectronicSignatureRecord.objects.filter(tenant=tenant).order_by("pk").first()

            rev_gate_1 = DesignReview.objects.create(
                tenant=tenant,
                project=project_active,
                title="Design Input Freeze Stage Gate",
                review_stage="input_freeze",
                review_date=today - datetime.timedelta(days=30),
                status="approved",
                lead_reviewer=admin_user,
                independent_reviewer=reviewer_user,
                agenda="Multidisciplinary review of User Needs (UN-001), engineering functional inputs, and IEC 60601 compliance standards.",
                discussion_summary="All clinical user needs verified against human factors data. Flow rate accuracy thresholds approved by biomedical engineering.",
                conclusions="Design inputs are complete, unambiguous, and testable. Input Freeze Gate approved.",
                action_items="All preliminary inputs approved with consensus.",
                action_items_resolved=True,
                electronic_signature=sig_review,
            )

            rev_gate_2 = DesignReview.objects.create(
                tenant=tenant,
                project=project_active,
                title="Verification & Architecture Gate Review",
                review_stage="verification_gate",
                review_date=today - datetime.timedelta(days=5),
                status="conditional",
                lead_reviewer=admin_user,
                independent_reviewer=reviewer_user,
                agenda="Review of verification test protocols for flow rate and ultrasonic air detection.",
                discussion_summary="Flow rate bench test passed. Air-in-line sensor testing shows sensitivity near tolerance threshold.",
                conclusions="Conditional approval granted pending completion of extended bubble test matrix.",
                action_items="Execute remaining 12 bubble calibration tests with blood analog solution.",
                action_items_resolved=False,
            )

            # 5. Design Verifications for Active Project
            ver_01 = DesignVerification.objects.create(
                tenant=tenant,
                project=project_active,
                primary_input=di_flow_01,
                title="Volumetric Infusion Rate Bench Testing",
                activity_type="verification",
                status="passed",
                test_method="lab_test",
                acceptance_criteria="Calculated flow rate error <= +/- 2% across 15 trial runs using calibrated analytical balance.",
                sample_size=15,
                results_summary="Mean flow deviation observed was +0.68% (sigma = 0.22%). Criteria satisfied.",
                pass_fail_result="pass",
                deviation_notes="",
                executed_by=admin_user,
                execution_date=today - datetime.timedelta(days=10),
                protocol_document=doc_sop,
            )

            ver_02 = DesignVerification.objects.create(
                tenant=tenant,
                project=project_active,
                primary_input=di_flow_02,
                title="Battery Endurance Test Under 125 mL/hr Load",
                activity_type="verification",
                status="passed",
                test_method="lab_test",
                acceptance_criteria="Continuous pump operation >= 8 hours without low battery alarm shutdown.",
                sample_size=10,
                results_summary="All 10 test units sustained minimum 9 hours 14 minutes continuous delivery before low-battery trigger.",
                pass_fail_result="pass",
                deviation_notes="",
                executed_by=admin_user,
                execution_date=today - datetime.timedelta(days=8),
            )

            ver_03 = DesignVerification.objects.create(
                tenant=tenant,
                project=project_active,
                primary_input=di_safe_01,
                title="Air-in-Line Ultrasonic Sensor Calibration Protocol",
                activity_type="verification",
                status="testing",
                test_method="lab_test",
                acceptance_criteria="Detection of 50 uL air bubble within 200 ms with audible alarm >= 65 dBA.",
                sample_size=12,
                results_summary="First 6 units detected bubbles successfully; remaining 6 in progress.",
                pass_fail_result="pending",
                deviation_notes="Bench temperature held at 22C +/- 1C.",
                executed_by=reviewer_user,
                execution_date=today - datetime.timedelta(days=2),
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.2 Design Controls & Development seeded successfully."))

    def _seed_submodule_12_3(self, tenant):
        if RiskManagementPlan.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.3 Risk Management data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.3 Risk Management (ISO 14971 / FMEA)...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        if not admin_user:
            self.stdout.write(f"[{tenant.name}] Warning: No user found for tenant.")
            return

        users = list(User.objects.filter(tenant=tenant).order_by("pk"))
        reviewer_user = users[1] if len(users) > 1 else admin_user

        qa_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="quality").order_by("pk").first()
        if not qa_dept:
            qa_dept = OrgUnit.objects.filter(tenant=tenant).order_by("pk").first()

        today = timezone.now().date()
        now = timezone.now()
        project_active = DesignProject.objects.filter(tenant=tenant, status="active").first()
        di_safe = DesignInput.objects.filter(tenant=tenant, input_type="safety").first()
        doc_sop = ControlledDocument.objects.filter(tenant=tenant, lifecycle_state="effective").first()
        ver_01 = DesignVerification.objects.filter(tenant=tenant, status="passed").first()

        with transaction.atomic():
            # 1. Master Risk Management Plan (Active Infusion System)
            rmp_active = RiskManagementPlan.objects.create(
                tenant=tenant,
                title="InfuseFlow Pro 3000 Device Risk Management Plan",
                plan_version="2.0",
                status="active",
                design_project=project_active,
                lead_risk_manager=admin_user,
                department=qa_dept,
                device_classification="class_ii_b",
                scope_description=(
                    "Comprehensive ISO 14971:2019 lifecycle risk management covering InfuseFlow Pro 3000 infusion pump system. "
                    "Encompasses fluid delivery mechanism, lithium battery sub-assembly, clinical user interface, and bedside IV administration."
                ),
                matrix_dimension="5x5",
                risk_acceptability_policy=(
                    "Pre-defined ISO 14971 risk acceptance criteria: S*P >= 15 is Unacceptable (mandatory reduction); "
                    "S*P 6 to 14 is ALARP (Conditionally Acceptable - requires formal clinical Benefit-Risk Analysis); "
                    "S*P <= 5 is Broadly Acceptable. Single-fault failure modes leading to catastrophic harm are prohibited."
                ),
                overall_residual_risk_acceptable=True,
                overall_benefit_risk_summary=(
                    "Clinical evaluation confirms that precise life-sustaining continuous drug infusion delivered by InfuseFlow Pro 3000 "
                    "substantially outweighs all mitigated collective residual risks when used per validated IFU instructions."
                ),
                periodic_review_frequency_months=12,
                next_review_due_date=today + datetime.timedelta(days=180),
            )

            # 2. Draft Secondary Risk Management Plan (Connected Health Telemetry)
            rmp_draft = RiskManagementPlan.objects.create(
                tenant=tenant,
                title="SmartInfuse Cloud Gateway Software Risk Plan",
                plan_version="1.0",
                status="draft",
                design_project=None,
                lead_risk_manager=reviewer_user,
                department=qa_dept,
                device_classification="samd",
                scope_description=(
                    "Software as a Medical Device (SaMD) risk management file addressing cloud gateway telemetry, "
                    "HL7/FHIR EHR communication, and cybersecurity anomaly detection."
                ),
                matrix_dimension="5x5",
                risk_acceptability_policy="SaMD risk acceptability per IEC 62304 and FDA Cybersecurity Guidance.",
                overall_residual_risk_acceptable=False,
                overall_benefit_risk_summary="",
                periodic_review_frequency_months=6,
                next_review_due_date=today + datetime.timedelta(days=90),
            )

            # 3. Risk Assessment 1: Air-in-line ultrasonic detection failure
            risk_01 = RiskAssessment.objects.create(
                tenant=tenant,
                plan=rmp_active,
                analysis_type="hazard_analysis",
                hazard_category="energy_mechanical",
                hazard_description="Air-in-line ultrasonic bubble detection failure",
                hazardous_situation="Air bubble (> 100 uL) passes undetected through infusion cassette into IV line",
                foreseeable_sequence_of_events=(
                    "1. Tubing cassette micro-crack introduces air; "
                    "2. Transducer acoustic coupling is compromised; "
                    "3. Sensor fails to trip occlusion alarm; "
                    "4. Air is pumped directly into patient vasculature."
                ),
                potential_harm="Venous/arterial air embolism causing neurological stroke or cardiac arrest",
                item_function="Bubble Detection Sensor Subsystem",
                failure_mode="Loss of acoustic echo detection",
                failure_cause="Piezoelectric ceramic crystal cracking or adhesive delamination",
                failure_effect="False negative detection of air bolus during rapid delivery",
                initial_severity=5,
                initial_probability=3,
                initial_detectability=2,
                residual_severity=5,
                residual_probability=1,
                residual_detectability=1,
                residual_risk_acceptable=True,
                bra_required=True,
                benefit_risk_justification=(
                    "Residual probability reduced to < 1 in 100,000 via dual redundant sensors and automatic mechanical line clamp. "
                    "Critical IV therapy cannot be discontinued; benefit of life-saving infusion outweighs residual risk."
                ),
                disclosed_in_ifu=True,
                design_input=di_safe,
                lifecycle_status="closed",
            )

            # 4. Risk Assessment 2: Battery depletion during active medication delivery
            risk_02 = RiskAssessment.objects.create(
                tenant=tenant,
                plan=rmp_active,
                analysis_type="dfmea",
                hazard_category="energy_electrical",
                hazard_description="Sudden battery depletion during active drug infusion",
                hazardous_situation="Pump shuts down unexpectedly mid-infusion while operating on internal battery during hospital transport",
                foreseeable_sequence_of_events="1. AC power disconnected for transport; 2. State-of-charge calculation drifts; 3. Low-battery alarm fails to sound before cut-off.",
                potential_harm="Abrupt hemodynamic decompensation due to cessation of vasoactive inotropic infusion",
                item_function="Battery Management Unit (BMU)",
                failure_mode="Premature cell voltage collapse below operating threshold",
                failure_cause="Electrolyte degradation or high internal cell impedance",
                failure_effect="Sudden loss of motor torque and immediate delivery shutdown",
                initial_severity=4,
                initial_probability=3,
                initial_detectability=2,
                residual_severity=4,
                residual_probability=1,
                residual_detectability=1,
                residual_risk_acceptable=True,
                bra_required=False,
                benefit_risk_justification="",
                disclosed_in_ifu=True,
                design_input=None,
                lifecycle_status="closed",
            )

            # 5. Risk Assessment 3: Fluid ingress causing electrical short circuit
            risk_03 = RiskAssessment.objects.create(
                tenant=tenant,
                plan=rmp_active,
                analysis_type="hazard_analysis",
                hazard_category="energy_electrical",
                hazard_description="Saline / cleaning solution fluid ingress into pump enclosure",
                hazardous_situation="Conductive IV fluid bridges high-voltage power converter trace to exposed patient ground",
                foreseeable_sequence_of_events="1. Accidental IV bag leak spills 500 mL saline over top housing; 2. Enclosure seam seal leaks; 3. Short circuit occurs.",
                potential_harm="Electrical shock to clinical operator or patient touch current exceedance",
                item_function="Chassis Enclosure & Gasket Assembly",
                failure_mode="Moisture penetration through mating housing seams",
                failure_cause="Inadequate gasket compression or degradation from harsh hospital disinfectants",
                failure_effect="Internal corrosion and dielectric insulation breakdown",
                initial_severity=4,
                initial_probability=4,
                initial_detectability=1,
                residual_severity=4,
                residual_probability=1,
                residual_detectability=1,
                residual_risk_acceptable=True,
                bra_required=False,
                benefit_risk_justification="",
                disclosed_in_ifu=False,
                design_input=None,
                lifecycle_status="closed",
            )

            # 6. Risk Assessment 4: Syringe misloading by nursing staff (Use Error)
            risk_04 = RiskAssessment.objects.create(
                tenant=tenant,
                plan=rmp_active,
                analysis_type="use_error_urra",
                hazard_category="operational_use_error",
                hazard_description="Syringe flange misplacement in drive carriage clamp",
                hazardous_situation="User clamps syringe plunger without engaging flange sensor, causing uncontrolled siphon flow",
                foreseeable_sequence_of_events="1. Nurse rushes during emergency room setup; 2. Syringe barrel is placed askew; 3. Siphon flow occurs under gravity.",
                potential_harm="Rapid unmetered drug bolus administration causing overdose toxicity",
                item_function="Syringe Drive Mechanism Clamp",
                failure_mode="Mechanical flange engagement not locked before start",
                failure_cause="Poor visual feedback and ambiguous mechanical detent feel",
                failure_effect="Free-flow delivery under atmospheric head pressure",
                initial_severity=4,
                initial_probability=3,
                initial_detectability=3,
                residual_severity=4,
                residual_probability=1,
                residual_detectability=1,
                residual_risk_acceptable=True,
                bra_required=True,
                benefit_risk_justification="Safety interlock switch prevents pump start unless barrel flange is seated.",
                disclosed_in_ifu=True,
                design_input=None,
                lifecycle_status="mitigated",
            )

            # 7. Risk Control Measures
            rcm_01 = RiskControlMeasure.objects.create(
                tenant=tenant,
                risk_assessment=risk_01,
                control_hierarchy="inherent_safety",
                title="Dual-Channel Ultrasonic Bubble Transducers with Solenoid Anti-Free-Flow Clamp",
                description=(
                    "Hardware design implements two independent ultrasonic sensors operating at 2.5 MHz with cross-channel voting. "
                    "An automatic spring-loaded line clamp mechanically pinches the IV line closed within 50 ms if air is detected."
                ),
                assigned_to=admin_user,
                due_date=today - datetime.timedelta(days=20),
                status="verified",
                design_input=di_safe,
                controlled_document=None,
                design_verification=ver_01,
                implementation_verified=True,
                effectiveness_verified=True,
                verification_notes="Verification test protocol demonstrated 100% occlusion clamp closure on 15 test trials with zero bubble escape.",
                introduces_new_hazard=False,
                new_hazard_details="",
            )

            rcm_02 = RiskControlMeasure.objects.create(
                tenant=tenant,
                risk_assessment=risk_02,
                control_hierarchy="protective_measure",
                title="Coulomb-Counting Smart Fuel Gauge with Forced Transport Lockout at 20% Reserve",
                description=(
                    "Integrated Texas Instruments bq40z50 battery fuel-gauge IC with impedance tracking. "
                    "Firmware enforces a continuous acoustic warning at 30 minutes runtime remaining and prohibits patient transport if reserve < 20%."
                ),
                assigned_to=admin_user,
                due_date=today - datetime.timedelta(days=15),
                status="verified",
                design_input=None,
                controlled_document=None,
                design_verification=None,
                implementation_verified=True,
                effectiveness_verified=True,
                verification_notes="Battery discharge run-down test protocol demonstrated reliable 45-minute minimum warning across all 10 test packs.",
                introduces_new_hazard=False,
                new_hazard_details="",
            )

            rcm_03 = RiskControlMeasure.objects.create(
                tenant=tenant,
                risk_assessment=risk_03,
                control_hierarchy="protective_measure",
                title="IPX4 Liquid Ingress Gasket Seals with Internal Drain Channeling",
                description=(
                    "Overmolded silicone perimeter gasket with labyrinth joint seal tested to IEC 60529 IPX4 splash testing. "
                    "Internal physical bulkhead diverts any incidental fluid away from high-voltage DC/DC power components."
                ),
                assigned_to=reviewer_user,
                due_date=today - datetime.timedelta(days=10),
                status="verified",
                design_input=None,
                controlled_document=None,
                design_verification=None,
                implementation_verified=True,
                effectiveness_verified=True,
                verification_notes="IPX4 oscillating spray test passed with zero dielectric breakdown under 4,000V dielectric withstand test.",
                introduces_new_hazard=False,
                new_hazard_details="",
            )

            rcm_04 = RiskControlMeasure.objects.create(
                tenant=tenant,
                risk_assessment=risk_04,
                control_hierarchy="information_for_safety",
                title="Color-Coded Mechanical Detent Clamp & On-Screen Visual Syringe Seating Guide",
                description=(
                    "Mechanical syringe clamp features high-contrast green indicator flag visible only when barrel flange is fully seated. "
                    "LCD prompts step-by-step confirmation wizard and IFU warning label highlights syringe seating check."
                ),
                assigned_to=reviewer_user,
                due_date=today + datetime.timedelta(days=30),
                status="in_progress",
                design_input=None,
                controlled_document=doc_sop,
                design_verification=None,
                implementation_verified=True,
                effectiveness_verified=False,
                verification_notes="Formative human factors study completed with 12 nurses; summative validation test scheduled.",
                introduces_new_hazard=False,
                new_hazard_details="",
            )

            # 8. Risk Review Records
            rmr_01 = RiskReviewRecord.objects.create(
                tenant=tenant,
                plan=rmp_active,
                review_title="Initial Risk Management Report (RMR) - Design Freeze & V&V Completion",
                review_type="initial_rmr",
                review_date=today - datetime.timedelta(days=30),
                review_period_start=today - datetime.timedelta(days=365),
                review_period_end=today - datetime.timedelta(days=30),
                pms_sources_reviewed="Design verification protocols, safety engineering hazard log, FMEA worksheets, and clinical usability assessments.",
                new_hazards_identified=False,
                risk_profile_changed=False,
                overall_residual_risk_reconfirmed=True,
                findings_summary=(
                    "Comprehensive review of all 4 identified hazard categories and associated FMEA lines confirms: "
                    "100% of risk control measures are implemented; dual redundant bubble detection eliminates catastrophic air embolism; "
                    "all residual risks are in acceptable or justified ALARP zones per ISO 14971 Clause 8."
                ),
                action_items_required="Submit RMR to Regulatory Affairs for 510(k) Premarket Notification dossier compilation.",
                status="approved",
                lead_reviewer=admin_user,
            )

            rmr_02 = RiskReviewRecord.objects.create(
                tenant=tenant,
                plan=rmp_active,
                review_title="Annual Post-Market Surveillance (PMS) Risk Evaluation - Year 1 Commercial",
                review_type="post_market_surveillance",
                review_date=today - datetime.timedelta(days=5),
                review_period_start=today - datetime.timedelta(days=180),
                review_period_end=today - datetime.timedelta(days=5),
                pms_sources_reviewed="32 customer complaints, 2 service maintenance records, FDA MAUDE adverse event database, and cleanroom non-conformances.",
                new_hazards_identified=False,
                risk_profile_changed=False,
                overall_residual_risk_reconfirmed=True,
                findings_summary=(
                    "Post-market feedback across 2,400 deployed clinical units shows zero air embolism incidents and zero electric shock events. "
                    "Observed syringe misloading complaints were 0.08 per 1,000 infusions (well below 0.5 per 1,000 threshold). "
                    "Overall residual risk profile remains completely acceptable."
                ),
                action_items_required="Continue standard 12-month post-market vigilance cadence.",
                status="approved",
                lead_reviewer=admin_user,
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.3 Risk Management (ISO 14971 / FMEA) seeded successfully."))

    def _seed_submodule_12_4(self, tenant):
        if CapaInvestigation.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.4 CAPA data already seeded, skipping.")
            return

        admin_user = (
            User.objects.filter(tenant=tenant, is_staff=True).first()
            or User.objects.filter(tenant=tenant).first()
        )
        if not admin_user:
            self.stdout.write(self.style.WARNING(f"[{tenant.name}] No user found to assign CAPAs, skipping."))
            return

        today = timezone.now().date()
        now = timezone.now()
        dept = OrgUnit.objects.filter(tenant=tenant).first()
        design_prj = DesignProject.objects.filter(tenant=tenant).first()
        risk_asmt = RiskAssessment.objects.filter(tenant=tenant).first()
        controlled_doc = ControlledDocument.objects.filter(tenant=tenant).first()
        change_ord = DocumentChangeOrder.objects.filter(tenant=tenant).first()

        with transaction.atomic():
            # 1. Critical CAPA: Infusion Pump Occlusion Pressure Sensor Calibration Drift
            capa_01 = CapaInvestigation.objects.create(
                tenant=tenant,
                title="Infusion Pump Occlusion Pressure Sensor Calibration Drift",
                issue_summary=(
                    "In-line functional pressure testing observed a 15% positive calibration drift across multiple "
                    "InfuseFlow Pro 3000 units, resulting in delayed downstream occlusion alarm triggers under simulated patient backpressure."
                ),
                action_type="corrective",
                source_type="ncr",
                source_reference="NCR-2026-0042",
                risk_priority="critical",
                containment_actions="Immediate quarantine hold on assembly Lot LOT-2026-A1; stopped line 2 calibration cell.",
                containment_implemented=True,
                containment_verified_by=admin_user,
                containment_date=today - datetime.timedelta(days=45),
                affected_item_code="PRD-MED-3000",
                affected_item_name="InfuseFlow Pro 3000 Smart Infusion Pump",
                affected_lot_numbers="LOT-2026-A1",
                lead_investigator=admin_user,
                quality_owner=admin_user,
                department=dept,
                design_project=design_prj,
                risk_assessment=risk_asmt,
                status="effectiveness_review",
                target_investigation_date=today - datetime.timedelta(days=30),
                target_closure_date=today + datetime.timedelta(days=15),
                is_escalated=True,
                escalation_reason="Critical patient safety threshold: delayed occlusion detection could induce venous bolus.",
                escalated_at=timezone.now() - datetime.timedelta(days=40),
            )

            # RCA for CAPA 1: 5 Whys
            rca_01 = RootCauseAnalysis.objects.create(
                tenant=tenant,
                capa=capa_01,
                rca_method="5_whys",
                problem_statement="Sensor output voltage drifted above upper acceptance tolerance by +0.18V after curing cycle.",
                why_1="Pressure transducer diaphragm adhesive curing temperature fluctuated by +/- 8°C.",
                why_2="Infrared oven thermal controller thermocouple had uncalibrated thermal offset.",
                why_3="Preventative maintenance calibration cycle was missed due to ambiguous maintenance schedule.",
                why_4="Calibration tracking relied on decentralized physical logbook rather than automated CMMS.",
                why_5="Root cause: Inadequate tooling calibration management and missing thermal interlock on cure oven.",
                root_cause_category="equipment",
                root_cause_summary=(
                    "Physical verification proved uncalibrated thermal sensor allowed cure temperature to exceed 65°C, "
                    "causing polymeric pre-stress on piezo-resistive diaphragm silicon element."
                ),
                escape_point_gap="Pre-assembly incoming batch electrical test checked resistance at ambient 20°C but not post-cure thermal delta.",
                status="verified",
                lead_investigator=admin_user,
                verified_by=admin_user,
                verified_date=today - datetime.timedelta(days=25),
                verification_notes="Thermal gradient study confirmed repeatability of +0.18V drift at >65°C oven temperature.",
            )

            # Actions for CAPA 1
            act_01_containment = CapaAction.objects.create(
                tenant=tenant,
                capa=capa_01,
                root_cause=rca_01,
                action_type="containment",
                title="Quarantine and segregate assembly Lot LOT-2026-A1",
                description="Physically tag and move all 140 assembled pump subassemblies to Quality Quarantine Cage B.",
                assigned_to=admin_user,
                department=dept,
                due_date=today - datetime.timedelta(days=44),
                completion_date=today - datetime.timedelta(days=44),
                status="verified",
                implementation_notes="All 140 units locked in Cage B with yellow NCR quarantine tags.",
                verified_by=admin_user,
                verified_on=today - datetime.timedelta(days=43),
                verification_evidence="Physical count verified 140/140 serialized units accounted for.",
            )

            act_01_corrective_1 = CapaAction.objects.create(
                tenant=tenant,
                capa=capa_01,
                root_cause=rca_01,
                action_type="corrective",
                title="Install automated digital thermal interlock and replace thermocouple",
                description="Fit dual-redundant Class A RTD temperature sensors with automatic oven power cutoff if temperature exceeds 62°C.",
                assigned_to=admin_user,
                department=dept,
                due_date=today - datetime.timedelta(days=20),
                completion_date=today - datetime.timedelta(days=20),
                status="verified",
                change_order=change_ord,
                design_project=design_prj,
                implementation_notes="New Eurotherm 3216 controller installed with NIST-traceable thermocouple.",
                verified_by=admin_user,
                verified_on=today - datetime.timedelta(days=18),
                verification_evidence="Calibration certificate #CAL-2026-0889 attached and verified.",
            )

            act_01_corrective_2 = CapaAction.objects.create(
                tenant=tenant,
                capa=capa_01,
                root_cause=rca_01,
                action_type="corrective",
                title="Revise Curing & Sensor Calibration Procedure SOP",
                description="Update SOP-MFG-004 to mandate temperature profile logging and 100% post-cure pressure offset verification.",
                assigned_to=admin_user,
                department=dept,
                due_date=today - datetime.timedelta(days=15),
                completion_date=today - datetime.timedelta(days=14),
                status="verified",
                controlled_document=controlled_doc,
                implementation_notes="SOP-MFG-004 Rev 3.0 approved and effective.",
                verified_by=admin_user,
                verified_on=today - datetime.timedelta(days=12),
                verification_evidence="Training records confirmed 8/8 assembly operators completed revised SOP training.",
            )

            # Effectiveness Review for CAPA 1
            eff_01 = CapaEffectivenessReview.objects.create(
                tenant=tenant,
                capa=capa_01,
                review_criteria="Zero pressure sensor calibration drift across 5 consecutive production batches (sample N=150, Cpk >= 1.33).",
                verification_method="process_capability",
                planned_review_date=today - datetime.timedelta(days=5),
                actual_review_date=today - datetime.timedelta(days=2),
                evaluator=admin_user,
                metrics_evaluated="Evaluated 180 units across Lots A2, A3, and A4. Mean offset: +0.01V, StdDev: 0.021V, Cpk = 1.62.",
                recurrence_observed=False,
                outcome="effective",
                status="completed",
                review_notes="Capability analysis proves curing process is fully robust with zero recurrence in production.",
            )

            # 2. Medium Priority CAPA: Cleanroom Particulate Count Excursion in Packaging Cell B
            capa_02 = CapaInvestigation.objects.create(
                tenant=tenant,
                title="Cleanroom Particulate Count Excursion in Packaging Cell B",
                issue_summary=(
                    "Routine environmental monitoring detected ISO Class 7 particulate count excursion (0.5µm particles > 352,000/m³) "
                    "near sterile packaging sealing station #2."
                ),
                action_type="corrective",
                source_type="internal_audit",
                source_reference="AUD-2026-Q1",
                risk_priority="medium",
                containment_actions="Halted packaging line B; switched primary sterile packaging to line A.",
                containment_implemented=True,
                containment_verified_by=admin_user,
                containment_date=today - datetime.timedelta(days=20),
                affected_item_code="PRD-SYR-005",
                affected_item_name="AccuInject 5mL Safety Syringe",
                affected_lot_numbers="LOT-2026-SYR-11",
                lead_investigator=admin_user,
                quality_owner=admin_user,
                department=dept,
                status="action_implementation",
                target_investigation_date=today - datetime.timedelta(days=10),
                target_closure_date=today + datetime.timedelta(days=30),
                is_escalated=False,
            )

            # RCA for CAPA 2: Ishikawa 6M
            rca_02 = RootCauseAnalysis.objects.create(
                tenant=tenant,
                capa=capa_02,
                rca_method="fishbone_ishikawa",
                problem_statement="ISO Class 7 particle count elevated during secondary shift packaging operation.",
                fishbone_manpower="Personnel movement rate exceeded SOP limits during shift handover.",
                fishbone_machine="HEPA filter fan unit #4 terminal seal degradation.",
                fishbone_material="Cardboard carton storage within 3 meters of packaging barrier.",
                fishbone_method="Missing wipe-down protocol for supply cart entry.",
                fishbone_measurement="Particle counter optical sensor calibrated and verified accurate.",
                fishbone_environment="Differential pressure dropped from 15 Pa to 8 Pa during main exhaust damper transition.",
                root_cause_category="environmental",
                root_cause_summary="Damper seal degradation on exhaust line caused intermittent low-pressure vacuum backdraft through pass-through door.",
                escape_point_gap="Continuous facility monitoring alarm threshold was set to 15-minute averaging rather than instantaneous excursion trigger.",
                status="completed",
                lead_investigator=admin_user,
            )

            act_02_1 = CapaAction.objects.create(
                tenant=tenant,
                capa=capa_02,
                root_cause=rca_02,
                action_type="corrective",
                title="Replace HEPA terminal seal and overhaul exhaust damper gasket",
                description="Install silicone gasket and re-balance HVAC differential pressure to maintain >=15 Pa at all times.",
                assigned_to=admin_user,
                department=dept,
                due_date=today + datetime.timedelta(days=5),
                status="in_progress",
                implementation_notes="Damper gasket received from supplier; HVAC maintenance scheduled for weekend maintenance shutdown.",
            )

            act_02_2 = CapaAction.objects.create(
                tenant=tenant,
                capa=capa_02,
                root_cause=rca_02,
                action_type="preventive",
                title="Implement instantaneous particle counter alarm interlock",
                description="Reconfigure SCADA environmental monitoring to alert instantly upon any 60-second particle count surge.",
                assigned_to=admin_user,
                department=dept,
                due_date=today + datetime.timedelta(days=15),
                status="pending",
            )

            eff_02 = CapaEffectivenessReview.objects.create(
                tenant=tenant,
                capa=capa_02,
                review_criteria="30 consecutive days of continuous environmental monitoring confirming particle counts <= 100,000/m³ in ISO Class 7 zone.",
                verification_method="trend_analysis",
                planned_review_date=today + datetime.timedelta(days=45),
                evaluator=admin_user,
                outcome="pending",
                status="scheduled",
            )

            # 3. Preventive Action: Proactive Upstream Supplier Resin Moisture Tolerance Tightening
            capa_03 = CapaInvestigation.objects.create(
                tenant=tenant,
                title="Proactive Upstream Supplier Resin Moisture Tolerance Tightening",
                issue_summary=(
                    "Statistical analysis of raw polycarbonate polymer incoming moisture logs identified a seasonal upward trend "
                    "approaching the upper specification limit during high-humidity summer months."
                ),
                action_type="preventive",
                source_type="risk_assessment",
                source_reference="QRMP-00001",
                risk_priority="low",
                containment_actions="Desiccant dryer dwell time temporarily increased from 4 to 6 hours.",
                containment_implemented=True,
                containment_verified_by=admin_user,
                containment_date=today - datetime.timedelta(days=10),
                affected_item_code="RESIN-PC-01",
                affected_item_name="Medical Grade Polycarbonate Resin",
                lead_investigator=admin_user,
                quality_owner=admin_user,
                department=dept,
                status="under_investigation",
                target_investigation_date=today + datetime.timedelta(days=20),
                target_closure_date=today + datetime.timedelta(days=60),
                is_escalated=False,
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.4 Corrective & Preventive Action (CAPA) seeded successfully."))

    def _seed_submodule_12_5(self, tenant):
        """Seed demo data for Sub-module 12.5: Non-Conformance & Deviation Management."""
        if NonConformanceReport.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.5 Non-Conformance & Deviation records already seeded. Skipping.")
            return

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=False).first()
            or User.objects.filter(tenant=tenant).first()
        )
        if not admin_user:
            return

        dept = OrgUnit.objects.filter(tenant=tenant).first()
        capa_ref = CapaInvestigation.objects.filter(tenant=tenant).first()
        doc_ref = ControlledDocument.objects.filter(tenant=tenant).first()
        today = timezone.now().date()
        now = timezone.now()

        with transaction.atomic():
            # 1. Critical NCR: Solder Bridging in Automated PCBA Wave Soldering
            ncr_01 = NonConformanceReport.objects.create(
                tenant=tenant,
                title="Solder Bridging & Short Circuit Defect in Main Controller PCB Sub-Assembly",
                description=(
                    "In-process automated optical inspection (AOI) flagged intermittent electrical short circuits across "
                    "microcontroller pins QFP-64 on board revision D2 due to excess solder paste deposition."
                ),
                source_type="in_process",
                category="process",
                severity="critical",
                status="containment_active",
                defect_code="SMT-BRDG-04",
                department=dept,
                initiator=admin_user,
                owner=admin_user,
                affected_item_code="PCBA-CTRL-002",
                affected_item_name="Main Embedded System Logic Controller Board",
                lot_serial_numbers="LOT-2026-PCBA-091",
                quantity_inspected=Decimal("250.00"),
                quantity_nonconforming=Decimal("38.00"),
                unit_of_measure="EA",
                estimated_financial_loss=Decimal("7600.00"),
                immediate_containment_required=True,
                capa_required=True,
                capa_investigation=capa_ref,
                target_resolution_date=today + datetime.timedelta(days=7),
            )

            # Quarantine hold for NCR 1
            QuarantineContainment.objects.create(
                tenant=tenant,
                ncr=ncr_01,
                title="Immediate Physical Quarantine of PCBA Lot 091",
                hold_type="physical_quarantine",
                quarantine_location="SMT Production Floor - Quarantine Bin Q-02",
                red_tag_number="TAG-RED-2026-041",
                quantity_on_hold=Decimal("38.00"),
                unit_of_measure="EA",
                hold_date=today - datetime.timedelta(days=2),
                hold_applied_by=admin_user,
                status="active",
                release_criteria="Re-inspection via AOI and flying probe test post precision desoldering rework.",
            )

            # Digital stop-shipment hold
            QuarantineContainment.objects.create(
                tenant=tenant,
                ncr=ncr_01,
                title="Digital ERP Stop-Shipment Hold on Finished Assemblies Containing Lot 091",
                hold_type="stop_shipment",
                quarantine_location="Warehouse Main Staging - Digital Lockout",
                red_tag_number="HOLD-SYS-901",
                quantity_on_hold=Decimal("120.00"),
                unit_of_measure="EA",
                hold_date=today - datetime.timedelta(days=2),
                hold_applied_by=admin_user,
                status="active",
                release_criteria="Full serialization trace confirming removal of affected controller sub-assemblies.",
            )

            # MRB Disposition for NCR 1
            MrbDisposition.objects.create(
                tenant=tenant,
                ncr=ncr_01,
                title="MRB Convening: Hot-Air Rework & Stencil Aperture Recalibration",
                disposition_decision="rework",
                technical_justification=(
                    "Engineering analysis confirms PCB substrate and integrated circuit silicon are undamaged. "
                    "Defect is strictly solder volume excess; manual hot-air touch-up and flux cleaning will restore full spec."
                ),
                rework_instructions=(
                    "1. Apply No-Clean tacky flux to bridged QFP pins.\n"
                    "2. Use Hakko hot-air nozzle at 320°C with copper solder wick to draw excess tin.\n"
                    "3. Inspect under 20x stereo microscope for micro-solder balls.\n"
                    "4. Run automated test fixture diagnostic sequence."
                ),
                rework_assignee=admin_user,
                rework_completed_date=today - datetime.timedelta(days=1),
                reinspection_required=True,
                reinspection_criteria="Zero bridges under 20x magnification; 100% test fixture continuity pass.",
                reinspection_passed=True,
                reinspection_by=admin_user,
                scrap_cost=Decimal("0.00"),
                rework_labor_cost=Decimal("950.00"),
                vendor_chargeback_cost=Decimal("0.00"),
                total_cost_impact=Decimal("950.00"),
                mrb_chair=admin_user,
                quality_approved_by=admin_user,
                engineering_approved_by=admin_user,
                operations_approved_by=admin_user,
                status="approved",
            )

            # 2. Major NCR: Incoming Stainless Steel Tubing Wall Thickness Out-of-Spec
            ncr_02 = NonConformanceReport.objects.create(
                tenant=tenant,
                title="Incoming Stainless Steel 316L Hydraulic Tubing Wall Thickness Dimension Out-of-Spec",
                description=(
                    "Receiving quality inspection utilizing ultrasonic wall thickness gauge recorded average thickness of "
                    "0.82mm vs drawing specification of 1.00mm +/- 0.05mm across two supply coils."
                ),
                source_type="incoming",
                category="material",
                severity="major",
                status="mrb_review",
                defect_code="DIM-WALL-OOS",
                department=dept,
                initiator=admin_user,
                owner=admin_user,
                affected_item_code="RAW-TUBE-SS316",
                affected_item_name="Hydraulic Fluid Transfer Line 316L 10mm OD",
                lot_serial_numbers="COIL-SS-2026-88A, COIL-SS-2026-88B",
                quantity_inspected=Decimal("1000.00"),
                quantity_nonconforming=Decimal("500.00"),
                unit_of_measure="M",
                estimated_financial_loss=Decimal("12500.00"),
                immediate_containment_required=True,
                capa_required=False,
                target_resolution_date=today + datetime.timedelta(days=14),
            )

            # Quarantine for NCR 2
            QuarantineContainment.objects.create(
                tenant=tenant,
                ncr=ncr_02,
                title="Receiving Dock Quarantine - SS316L Coils 88A & 88B",
                hold_type="physical_quarantine",
                quarantine_location="Receiving Inspection Quarantine Area Bay 4",
                red_tag_number="TAG-RED-2026-042",
                quantity_on_hold=Decimal("500.00"),
                unit_of_measure="M",
                hold_date=today - datetime.timedelta(days=4),
                hold_applied_by=admin_user,
                status="active",
                release_criteria="Vendor Return to Vendor RMA paperwork or concession disposition sign-off.",
            )

            # MRB Disposition for NCR 2
            MrbDisposition.objects.create(
                tenant=tenant,
                ncr=ncr_02,
                title="MRB Decision: Return to Vendor (RTV) with Supplier Debit Memo",
                disposition_decision="return_to_vendor",
                technical_justification=(
                    "Reduced wall thickness compromises hydrostatic burst pressure rating below 4x safety factor. "
                    "Unusable in production hydraulic sub-assemblies. Supplier must replace entire mill batch."
                ),
                scrap_cost=Decimal("0.00"),
                rework_labor_cost=Decimal("150.00"),
                vendor_chargeback_cost=Decimal("12500.00"),
                total_cost_impact=Decimal("12650.00"),
                mrb_chair=admin_user,
                quality_approved_by=admin_user,
                engineering_approved_by=admin_user,
                status="under_review",
            )

            # 3. Process Deviation: Temporary Reflow Temperature Profile Adjustment
            dev_01 = ProcessDeviation.objects.create(
                tenant=tenant,
                title="Temporary 5°C Reflow Peak Temperature Adjustment for Lead-Free SAC305 Solder Alloy",
                deviation_type="planned",
                category="process_parameter",
                controlled_document=doc_ref,
                department=dept,
                requested_by=admin_user,
                approved_by=admin_user,
                risk_impact_level="minor",
                quality_impact_assessment=(
                    "Thermal profile modeling and thermocouple data loggers confirm component peak temperatures "
                    "remain safely under 260°C maximum rating while achieving complete intermetallic compound formation."
                ),
                affected_lots_summary="PCBA Batches LOT-2026-092 through LOT-2026-096",
                customer_notification_required=False,
                customer_concession_obtained=False,
                regulatory_reporting_required=False,
                valid_from=today - datetime.timedelta(days=3),
                valid_until=today + datetime.timedelta(days=14),
                max_batches_permitted=5,
                batches_produced_count=3,
                status="active",
            )

            # 4. Unplanned Deviation linked to Packaging Seal Temperature Fluctuation
            dev_02 = ProcessDeviation.objects.create(
                tenant=tenant,
                ncr=ncr_01,
                title="Unplanned Heating Element Thermocouple Drift on Pouch Sealer Line 1",
                deviation_type="unplanned",
                category="equipment_substitution",
                department=dept,
                requested_by=admin_user,
                approved_by=admin_user,
                risk_impact_level="moderate",
                quality_impact_assessment=(
                    "Sealing temperature dipped 8°C below nominal for 15 minutes before backup controller engaged. "
                    "Dye penetration seal integrity testing conducted on 100% of pouches yielded zero channel leaks."
                ),
                affected_lots_summary="Packaging Run LOT-PKG-2026-301 (40 units)",
                customer_notification_required=True,
                customer_concession_obtained=True,
                regulatory_reporting_required=False,
                valid_from=today - datetime.timedelta(days=5),
                valid_until=today + datetime.timedelta(days=2),
                max_batches_permitted=1,
                batches_produced_count=1,
                status="closed",
            )

            # 5. Closed NCR: Barcode Label DPI Print Blur on Secondary Packaging
            NonConformanceReport.objects.create(
                tenant=tenant,
                title="Secondary Carton Barcode Label Readability Failure at 200 DPI",
                description=(
                    "Thermal transfer printhead abrasion caused vertical bar voids, resulting in Grade D scanner verification "
                    "scores at warehouse packaging verification station."
                ),
                source_type="final_inspection",
                category="documentation",
                severity="minor",
                status="closed",
                defect_code="LBL-BAR-VOID",
                department=dept,
                initiator=admin_user,
                owner=admin_user,
                affected_item_code="PKG-BOX-MED",
                affected_item_name="Master Shipping Carton Outer Shipper",
                lot_serial_numbers="SHP-2026-0188",
                quantity_inspected=Decimal("100.00"),
                quantity_nonconforming=Decimal("15.00"),
                unit_of_measure="EA",
                estimated_financial_loss=Decimal("45.00"),
                immediate_containment_required=False,
                capa_required=False,
                closed_at=timezone.now(),
                closed_by=admin_user,
                closure_notes="Replaced worn thermal transfer printhead; verified Grade A barcode scan across 100 consecutive labels.",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.5 Non-Conformance & Deviation Management seeded successfully."))

    def _seed_submodule_12_6(self, tenant):
        if SupplierQualificationAudit.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.6 Supplier Quality data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.6 Supplier & Vendor Quality Management...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        lead_auditor = User.objects.filter(tenant=tenant).order_by("pk").last() or admin_user

        # Fetch supplier parties
        cascade = Party.objects.filter(tenant=tenant, name="Cascade Components Ltd").first()
        northwind = Party.objects.filter(tenant=tenant, name="Northwind Industrial Supply").first()
        umbrella = Party.objects.filter(tenant=tenant, name="Umbrella Supplies").first()
        initech = Party.objects.filter(tenant=tenant, name="Initech LLC").first()

        # Fallback to any suppliers/parties if specific demo parties don't exist
        suppliers = list(Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor")).distinct())
        if not suppliers:
            suppliers = list(Party.objects.filter(tenant=tenant).order_by("name"))

        if not cascade and suppliers:
            cascade = suppliers[0]
        if not northwind and len(suppliers) > 1:
            northwind = suppliers[1]
        elif not northwind:
            northwind = cascade
        if not umbrella and len(suppliers) > 2:
            umbrella = suppliers[2]
        elif not umbrella:
            umbrella = northwind
        if not initech and len(suppliers) > 3:
            initech = suppliers[3]
        elif not initech:
            initech = umbrella

        if not cascade:
            self.stdout.write(f"[{tenant.name}] No supplier parties available to seed 12.6, skipping.")
            return

        today = timezone.now().date()
        now = timezone.now()
        quality_agreement = ControlledDocument.objects.filter(tenant=tenant).first()
        design_project = DesignProject.objects.filter(tenant=tenant).first()
        capa = CapaInvestigation.objects.filter(tenant=tenant).first()

        with transaction.atomic():
            # 1. Supplier Qualification Audits (AVL)
            # Record 1: Cascade Components Ltd (Approved, Critical Tier, Dock-to-Stock)
            audit_cas = SupplierQualificationAudit.objects.create(
                tenant=tenant,
                supplier=cascade,
                assessment_type="initial_qualification",
                criticality_tier="critical",
                audit_method="on_site",
                qualification_status="approved",
                scope_commodities="Precision machined stainless steel shafts, titanium surgical implant blanks",
                score=Decimal("94.50"),
                audit_result="passed",
                critical_findings=0,
                major_findings=1,
                minor_findings=2,
                lead_auditor=lead_auditor,
                audit_date=today - datetime.timedelta(days=90),
                qualified_date=today - datetime.timedelta(days=80),
                next_audit_due_date=today + datetime.timedelta(days=275),
                certificate_expiry_date=today + datetime.timedelta(days=640),
                dock_to_stock_eligible=True,
                skip_lot_approved=True,
                requires_coa=True,
                quality_agreement=quality_agreement,
                notes="Facility audited under ISO 13485:2016 scope. Cleanroom particle counts well within Class 7 limits.",
            )

            # Record 2: Northwind Industrial Supply (Approved, Major Tier, Standard Receiving)
            audit_nw = SupplierQualificationAudit.objects.create(
                tenant=tenant,
                supplier=northwind,
                assessment_type="periodic_reaudit",
                criticality_tier="major",
                audit_method="desktop_survey",
                qualification_status="approved",
                scope_commodities="Industrial fasteners, silicone gaskets, O-rings, and molded seals",
                score=Decimal("88.00"),
                audit_result="passed",
                critical_findings=0,
                major_findings=2,
                minor_findings=3,
                lead_auditor=admin_user,
                audit_date=today - datetime.timedelta(days=120),
                qualified_date=today - datetime.timedelta(days=110),
                next_audit_due_date=today + datetime.timedelta(days=245),
                certificate_expiry_date=today + datetime.timedelta(days=400),
                dock_to_stock_eligible=False,
                skip_lot_approved=False,
                requires_coa=True,
                quality_agreement=quality_agreement,
                notes="Desktop questionnaire audit complete. Verified ISO 9001:2015 third-party certificate validity.",
            )

            # Record 3: Umbrella Supplies (Conditional, Major Tier, Passed with CAPA)
            audit_umb = SupplierQualificationAudit.objects.create(
                tenant=tenant,
                supplier=umbrella,
                assessment_type="for_cause",
                criticality_tier="major",
                audit_method="on_site",
                qualification_status="conditional",
                scope_commodities="Medical grade polymers, polycarbonate housings",
                score=Decimal("72.00"),
                audit_result="passed_with_capa",
                critical_findings=1,
                major_findings=4,
                minor_findings=5,
                lead_auditor=lead_auditor,
                audit_date=today - datetime.timedelta(days=45),
                qualified_date=today - datetime.timedelta(days=30),
                next_audit_due_date=today + datetime.timedelta(days=45),
                certificate_expiry_date=today + datetime.timedelta(days=180),
                dock_to_stock_eligible=False,
                skip_lot_approved=False,
                requires_coa=True,
                notes="For-cause audit triggered by wall thickness non-conformances. Status conditioned on SCAR closure.",
            )

            # Record 4: Initech LLC (Under Evaluation, Minor Tier)
            SupplierQualificationAudit.objects.create(
                tenant=tenant,
                supplier=initech,
                assessment_type="certification_review",
                criticality_tier="minor",
                audit_method="third_party_iso",
                qualification_status="under_evaluation",
                scope_commodities="Calibration standards and secondary metrology laboratory services",
                score=None,
                audit_result="pending",
                critical_findings=0,
                major_findings=0,
                minor_findings=0,
                lead_auditor=admin_user,
                audit_date=today - datetime.timedelta(days=10),
                qualified_date=None,
                next_audit_due_date=today + datetime.timedelta(days=20),
                certificate_expiry_date=today + datetime.timedelta(days=365),
                dock_to_stock_eligible=False,
                skip_lot_approved=False,
                requires_coa=False,
                notes="Initial onboarding qualification underway. Awaiting accreditation certificate ISO/IEC 17025.",
            )

            # 2. Supplier Quality Scorecards
            # Scorecard 1: Cascade Components Ltd (Q3 2026, Grade A)
            SupplierQualityScorecard.objects.create(
                tenant=tenant,
                supplier=cascade,
                cadence="quarterly",
                period_start=today - datetime.timedelta(days=90),
                period_end=today,
                status="published",
                lot_acceptance_rate_score=Decimal("98.00"),
                defect_ppm_score=Decimal("95.00"),
                scar_responsiveness_score=Decimal("92.00"),
                audit_compliance_score=Decimal("94.50"),
                documentation_coa_score=Decimal("96.00"),
                total_lots_received=45,
                lots_rejected=1,
                total_scars_issued=0,
                evaluated_by=admin_user,
                evaluation_notes="Exemplary performance across all titanium machining lots. 98% lot acceptance rate.",
            )

            # Scorecard 2: Northwind Industrial Supply (Q3 2026, Grade B)
            SupplierQualityScorecard.objects.create(
                tenant=tenant,
                supplier=northwind,
                cadence="quarterly",
                period_start=today - datetime.timedelta(days=90),
                period_end=today,
                status="published",
                lot_acceptance_rate_score=Decimal("89.00"),
                defect_ppm_score=Decimal("86.00"),
                scar_responsiveness_score=Decimal("85.00"),
                audit_compliance_score=Decimal("88.00"),
                documentation_coa_score=Decimal("90.00"),
                total_lots_received=38,
                lots_rejected=4,
                total_scars_issued=1,
                evaluated_by=admin_user,
                evaluation_notes="Solid delivery reliability; minor defect PPM bump caused by silicone heat cure issue.",
            )

            # Scorecard 3: Umbrella Supplies (Q3 2026, Grade C)
            SupplierQualityScorecard.objects.create(
                tenant=tenant,
                supplier=umbrella,
                cadence="quarterly",
                period_start=today - datetime.timedelta(days=90),
                period_end=today,
                status="published",
                lot_acceptance_rate_score=Decimal("74.00"),
                defect_ppm_score=Decimal("70.00"),
                scar_responsiveness_score=Decimal("75.00"),
                audit_compliance_score=Decimal("72.00"),
                documentation_coa_score=Decimal("80.00"),
                total_lots_received=25,
                lots_rejected=6,
                total_scars_issued=2,
                evaluated_by=admin_user,
                evaluation_notes="At risk performance due to mold sink mark issues. Conditional AVL hold active.",
            )

            # 3. Supplier Corrective Actions (SCAR)
            # SCAR 1: Umbrella Supplies (Critical, Action Plan Approved)
            SupplierCorrectiveAction.objects.create(
                tenant=tenant,
                supplier=umbrella,
                title="Polycarbonate Housing Wall Thickness Non-Conformance below 2.0mm Specification",
                severity="critical",
                status="action_plan_approved",
                defect_summary="Wall thickness measured 1.65mm - 1.82mm across 15 sample parts, failing the 2.00mm +/- 0.10mm drawing specification.",
                affected_item_code="POL-HOU-01",
                affected_item_name="Diagnostic Device Base Enclosure",
                affected_lots="LOT-UMB-2026-088",
                qualification_audit=audit_umb,
                internal_capa=capa,
                issued_date=today - datetime.timedelta(days=35),
                response_due_date=today + datetime.timedelta(days=10),
                issued_by=admin_user,
                containment_action="Quarantined 450 units at incoming dock; supplier placed shipping hold on remaining warehouse inventory and audited mold tooling temperature calibration.",
                containment_due_date=today - datetime.timedelta(days=33),
                containment_verified_at=today - datetime.timedelta(days=32),
                root_cause_category="tooling_equipment",
                root_cause_summary="Core pin thermal cooling channel calcification caused localized mold core overheating, inducing polymer thermal shrink sink marks.",
                vendor_investigation_details="5 Whys: 1. Thin wall? Polymer sink mark. 2. Sink mark? Core temp >140C. 3. High temp? Cooling water restricted. 4. Restricted? Calcium scale. 5. Scale? Demineralized water filter bypassed during maintenance.",
                corrective_action_plan="Acid-descaled all tool cooling channels; installed automated flow rate telemetry sensors with hard interlocks.",
                preventive_action_plan="Updated preventative maintenance SOP-MOLD-04 to mandate bi-weekly demineralizer conductivity checks.",
                implementation_due_date=today + datetime.timedelta(days=20),
                implemented_at=today - datetime.timedelta(days=5),
                effectiveness_due_date=today + datetime.timedelta(days=60),
                effectiveness_method="Cpk evaluation and dimensional measurement on next 3 consecutive production shipments of 500 units.",
            )

            # SCAR 2: Northwind Industrial Supply (Major, Implemented)
            SupplierCorrectiveAction.objects.create(
                tenant=tenant,
                supplier=northwind,
                title="Silicone O-Ring Tensile Strength Degradation Under Heat Aging",
                severity="major",
                status="implemented",
                defect_summary="Batch LOT-NW-442 exhibited 35% tensile strength loss after 72-hour thermal stress screening.",
                affected_item_code="SL-RING-08",
                affected_item_name="High-Purity Fluorosilicone O-Ring Seal",
                affected_lots="LOT-NW-442",
                qualification_audit=audit_nw,
                issued_date=today - datetime.timedelta(days=50),
                response_due_date=today - datetime.timedelta(days=20),
                issued_by=lead_auditor,
                containment_action="Segregated suspect batch in quarantine area; audited cure cycle timer records.",
                containment_due_date=today - datetime.timedelta(days=48),
                containment_verified_at=today - datetime.timedelta(days=47),
                root_cause_category="process_parameter",
                root_cause_summary="Post-curing oven heat distribution baffle dislodged, resulting in a 15C cold zone in oven rack tier 3.",
                vendor_investigation_details="Oven thermal profiling confirmed temperature variance between top and bottom racks.",
                corrective_action_plan="Re-welded air circulation plenum and re-profiled oven 9-point thermal mapping.",
                preventive_action_plan="Implemented daily thermocouple data logger review before releasing cured elastomer lots.",
                implementation_due_date=today - datetime.timedelta(days=10),
                implemented_at=today - datetime.timedelta(days=8),
                effectiveness_due_date=today + datetime.timedelta(days=30),
                effectiveness_method="Destructive tensile elongation pull testing on 10 samples per lot for 5 consecutive lots.",
            )

            # SCAR 3: Cascade Components Ltd (Minor, Closed / Verified)
            SupplierCorrectiveAction.objects.create(
                tenant=tenant,
                supplier=cascade,
                title="Titanium Mandrel Micro-Burrs on Distal Bevel Edge",
                severity="minor",
                status="closed",
                defect_summary="Micro-burrs exceeding 0.05mm observed under 20x optical inspection on batch LOT-CAS-102.",
                affected_item_code="TI-MND-40",
                affected_item_name="Titanium Endoscopic Mandrel Shaft",
                affected_lots="LOT-CAS-102",
                qualification_audit=audit_cas,
                issued_date=today - datetime.timedelta(days=80),
                response_due_date=today - datetime.timedelta(days=60),
                issued_by=admin_user,
                containment_action="100% optical deburring and re-inspection performed on all in-house inventory.",
                containment_due_date=today - datetime.timedelta(days=78),
                containment_verified_at=today - datetime.timedelta(days=77),
                root_cause_category="tooling_equipment",
                root_cause_summary="Diamond grinding wheel reached 500-cycle end-of-life wear threshold prematurely due to harder alloy lot.",
                vendor_investigation_details="Wheel wear log confirmed diamond grit glazing after 380 cycles.",
                corrective_action_plan="Adjusted grinding wheel redress interval from 500 to 350 cycles.",
                preventive_action_plan="Added automated optical in-line edge inspection station at CNC grinding cell.",
                implementation_due_date=today - datetime.timedelta(days=50),
                implemented_at=today - datetime.timedelta(days=52),
                effectiveness_due_date=today - datetime.timedelta(days=20),
                effectiveness_method="Zero burrs detected across 1,200 consecutive components manufactured under revised dress frequency.",
                effectiveness_results="Verified 100% pass rate with zero optical burrs across 3 subsequent delivery lots.",
                is_effective=True,
                verified_by=lead_auditor,
                closed_at=today - datetime.timedelta(days=15),
            )

            # 4. Supplier Change Notifications (SCN)
            # SCN 1: Cascade Components Ltd (Relocation, Level 2 Moderate)
            SupplierChangeNotification.objects.create(
                tenant=tenant,
                supplier=cascade,
                title="Relocation of Titanium Passivation and Ultrasonic Cleaning Line to Plant 3",
                supplier_scn_number="SCN-CAS-2026-004",
                change_category="facility_location",
                risk_level="level_2_moderate",
                status="under_assessment",
                description="Moving automated ultrasonic nitric acid passivation line 200 meters to new cleanroom facility Plant 3 to double processing capacity.",
                proposed_effective_date=today + datetime.timedelta(days=60),
                first_affected_lot="CAS-TI-2026-P3-01",
                affected_item_code="TI-MND-40",
                affected_item_name="Titanium Endoscopic Mandrel Shaft",
                affects_form_fit_function=False,
                requires_requalification=True,
                requires_design_change=False,
                requires_regulatory_filing=False,
                requires_customer_notification=False,
                samples_required=True,
                impact_assessment_notes="ASTM A967 chemical passivation testing and residual bioburden validation protocol required before approval.",
                requalification_audit=audit_cas,
                disposition="pending",
                evaluated_by=admin_user,
            )

            # SCN 2: Umbrella Supplies (Raw Material Alt Source, Level 3 Major)
            SupplierChangeNotification.objects.create(
                tenant=tenant,
                supplier=umbrella,
                title="Polycarbonate Resin Raw Material Supplier Alternative Sourcing (Covestro Makrolon 2808)",
                supplier_scn_number="PCN-UMB-2026-11",
                change_category="raw_material",
                risk_level="level_3_major",
                status="technical_evaluation",
                description="Primary polycarbonate resin supplier experiencing force majeure supply interruption. Proposing secondary qualified source Covestro Makrolon 2808 with identical ISO 10993 biocompatibility certification.",
                proposed_effective_date=today + datetime.timedelta(days=45),
                first_affected_lot="UMB-POL-2026-R2",
                affected_item_code="POL-HOU-01",
                affected_item_name="Diagnostic Device Base Enclosure",
                affects_form_fit_function=True,
                requires_requalification=True,
                requires_design_change=True,
                requires_regulatory_filing=True,
                requires_customer_notification=True,
                samples_required=True,
                impact_assessment_notes="Critical raw material change. Requires drop-impact testing, biocompatibility review, and technical file update.",
                design_project=design_project,
                requalification_audit=audit_umb,
                disposition="pending",
                evaluated_by=lead_auditor,
            )

            # SCN 3: Northwind Industrial Supply (Packaging Upgrade, Level 1 Minor, Approved)
            SupplierChangeNotification.objects.create(
                tenant=tenant,
                supplier=northwind,
                title="Secondary Packaging Blister Pack Heat Seal Adhesive Upgrade to Tyvek 1073B",
                supplier_scn_number="SCN-NW-2026-08",
                change_category="packaging_labeling",
                risk_level="level_1_minor",
                status="approved",
                description="Upgrading outer moisture barrier adhesive on non-sterile bulk packaging to improve peel durability during export transit.",
                proposed_effective_date=today - datetime.timedelta(days=15),
                first_affected_lot="NW-PKG-882",
                affected_item_code="SL-RING-08",
                affected_item_name="High-Purity Fluorosilicone O-Ring Seal",
                affects_form_fit_function=False,
                requires_requalification=False,
                requires_design_change=False,
                requires_regulatory_filing=False,
                requires_customer_notification=False,
                samples_required=False,
                impact_assessment_notes="Low risk outer carton packaging improvement. Tested peel seal strength exceeds 1.5 N/15mm.",
                disposition="approved",
                disposition_notes="Approved for immediate implementation. Low risk packaging specification improvement.",
                disposition_date=today - datetime.timedelta(days=10),
                approved_by=admin_user,
                evaluated_by=admin_user,
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.6 Supplier & Vendor Quality Management seeded successfully."))

    def _seed_submodule_12_7(self, tenant):
        """Seed demo data for Sub-module 12.7: Incoming Quality Control (IQC)."""
        if IncomingInspectionPlan.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.7 Incoming Quality Control data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.7 Incoming Quality Control (IQC)...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).first()
            or User.objects.filter(is_superuser=True).first()
        )

        suppliers = list(
            Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor")).order_by("pk")
        )

        cascade = next((s for s in suppliers if "Cascade" in s.name or "Component" in s.name), None)
        northwind = next((s for s in suppliers if "Northwind" in s.name or "Supply" in s.name), None)
        umbrella = next((s for s in suppliers if "Umbrella" in s.name or "Chemical" in s.name), None)

        if not cascade and suppliers:
            cascade = suppliers[0]
        if not northwind and len(suppliers) > 1:
            northwind = suppliers[1]
        elif not northwind:
            northwind = cascade
        if not umbrella and len(suppliers) > 2:
            umbrella = suppliers[2]
        elif not umbrella:
            umbrella = northwind

        if not cascade:
            self.stdout.write(f"[{tenant.name}] No supplier parties available to seed 12.7, skipping.")
            return

        today = timezone.now().date()
        now = timezone.now()
        sop_doc = ControlledDocument.objects.filter(tenant=tenant).first()
        ncr = NonConformanceReport.objects.filter(tenant=tenant).first()
        scar = SupplierCorrectiveAction.objects.filter(tenant=tenant).first()

        with transaction.atomic():
            # 1. Incoming Inspection Plans (QIIP)
            plan_shaft = IncomingInspectionPlan.objects.create(
                tenant=tenant,
                title="Precision CNC Machined Shaft IQC Protocol",
                item_code="PRT-10024",
                item_name="Drive Shaft 25mm Stainless",
                revision="B",
                supplier=cascade,
                sampling_standard="ansi_asq_z14",
                inspection_level="level_2",
                inspection_severity="normal",
                inspection_frequency="every_lot",
                skip_lot_interval=5,
                aql_critical=Decimal("0.00"),
                aql_major=Decimal("1.00"),
                aql_minor=Decimal("4.00"),
                requires_coa=True,
                requires_coc=False,
                status="active",
                characteristics_matrix=[
                    {
                        "name": "Shaft Outer Diameter",
                        "type": "variable",
                        "lsl": 24.98,
                        "usl": 25.02,
                        "target": 25.00,
                        "unit": "mm",
                        "test_method": "Digital Micrometer",
                    },
                    {
                        "name": "Total Length",
                        "type": "variable",
                        "lsl": 199.5,
                        "usl": 200.5,
                        "target": 200.0,
                        "unit": "mm",
                        "test_method": "Vernier Caliper",
                    },
                    {
                        "name": "Surface Roughness",
                        "type": "attribute",
                        "expected": "Ra <= 0.8um",
                        "test_method": "Profilometer",
                    },
                ],
                sop_document=sop_doc,
                notes="Critical rotating shaft. High precision bearing fit required.",
            )

            plan_pcb = IncomingInspectionPlan.objects.create(
                tenant=tenant,
                title="Telemetry Core PCB Controller IQC",
                item_code="PCB-A440",
                item_name="Telemetry Core PCB Controller Assembly",
                revision="C",
                supplier=northwind,
                sampling_standard="iso_2859_1",
                inspection_level="level_2",
                inspection_severity="normal",
                inspection_frequency="skip_lot",
                skip_lot_interval=5,
                aql_critical=Decimal("0.00"),
                aql_major=Decimal("0.65"),
                aql_minor=Decimal("2.50"),
                requires_coa=True,
                requires_coc=True,
                status="active",
                characteristics_matrix=[
                    {
                        "name": "Supply Voltage Regulation",
                        "type": "variable",
                        "lsl": 3.25,
                        "usl": 3.35,
                        "target": 3.30,
                        "unit": "V",
                        "test_method": "Digital Multimeter",
                    },
                    {
                        "name": "Idle Operating Current",
                        "type": "variable",
                        "lsl": 15.0,
                        "usl": 25.0,
                        "target": 20.0,
                        "unit": "mA",
                        "test_method": "Current Shunt Meter",
                    },
                ],
                sop_document=sop_doc,
                notes="Approved mature supplier under skip-lot testing protocol (1:5 lots).",
            )

            plan_enclosure = IncomingInspectionPlan.objects.create(
                tenant=tenant,
                title="Diagnostic Device Base Housing Enclosure IQC",
                item_code="POL-HOU-01",
                item_name="Diagnostic Device Base Enclosure Shell",
                revision="A",
                supplier=umbrella,
                sampling_standard="c_zero_squeglia",
                inspection_level="level_1",
                inspection_severity="normal",
                inspection_frequency="every_lot",
                aql_critical=Decimal("0.00"),
                aql_major=Decimal("0.65"),
                aql_minor=Decimal("1.50"),
                requires_coa=True,
                requires_coc=True,
                status="active",
                characteristics_matrix=[
                    {
                        "name": "Wall Thickness",
                        "type": "variable",
                        "lsl": 2.4,
                        "usl": 2.8,
                        "target": 2.6,
                        "unit": "mm",
                        "test_method": "Ultrasonic Gauge",
                    }
                ],
                notes="Medical device external shell. Zero critical defects tolerated.",
            )

            plan_fastener = IncomingInspectionPlan.objects.create(
                tenant=tenant,
                title="Fluorosilicone O-Ring Seal Dock-to-Stock Protocol",
                item_code="SL-RING-08",
                item_name="High-Purity Fluorosilicone O-Ring Seal",
                revision="A",
                supplier=northwind,
                sampling_standard="fixed_percentage",
                inspection_frequency="dock_to_stock",
                aql_critical=Decimal("0.00"),
                aql_major=Decimal("2.50"),
                aql_minor=Decimal("6.50"),
                requires_coa=False,
                status="active",
                notes="Authorized dock-to-stock direct inventory release.",
            )

            # 2. Incoming Inspection Lots (QIIL)
            # Lot 1: Conforming Lot for Shaft (Accepted, high capability)
            lot_shaft_good = IncomingInspectionLot.objects.create(
                tenant=tenant,
                inspection_plan=plan_shaft,
                item_code="PRT-10024",
                item_name="Drive Shaft 25mm Stainless",
                supplier=cascade,
                lot_number="LOT-2026-A101",
                heat_or_batch="HEAT-SS316-901",
                receipt_date=today - datetime.timedelta(days=7),
                inspection_date=today - datetime.timedelta(days=6),
                lot_quantity=Decimal("500.000"),
                sample_size=50,
                inspected_quantity=50,
                accepted_quantity=Decimal("500.000"),
                rejected_quantity=Decimal("0.000"),
                quarantine_quantity=Decimal("0.000"),
                critical_defects=0,
                major_defects=0,
                minor_defects=0,
                stage="completed",
                usage_decision="accepted",
                usage_decision_notes="Lot conforming to all dimensional and metallurgical criteria. Released to inventory.",
                decided_by=admin_user,
                decided_at=timezone.now() - datetime.timedelta(days=6),
                inspector=admin_user,
                measurements_data=[
                    {"sample_no": 1, "characteristic": "Shaft Outer Diameter", "value": 25.002, "is_pass": True},
                    {"sample_no": 2, "characteristic": "Shaft Outer Diameter", "value": 25.004, "is_pass": True},
                    {"sample_no": 3, "characteristic": "Shaft Outer Diameter", "value": 24.998, "is_pass": True},
                    {"sample_no": 4, "characteristic": "Shaft Outer Diameter", "value": 25.001, "is_pass": True},
                    {"sample_no": 5, "characteristic": "Shaft Outer Diameter", "value": 25.003, "is_pass": True},
                ],
                spc_mean=Decimal("25.0016"),
                spc_std_dev=Decimal("0.0023"),
                spc_cp=Decimal("2.90"),
                spc_cpk=Decimal("2.67"),
                spc_out_of_control=False,
                notes="High precision lot from Cascade Components.",
            )

            # Lot 2: Non-Conforming Rejected Lot for Shaft (Out-of-Control SPC, NCR & SCAR linked)
            lot_shaft_bad = IncomingInspectionLot.objects.create(
                tenant=tenant,
                inspection_plan=plan_shaft,
                item_code="PRT-10024",
                item_name="Drive Shaft 25mm Stainless",
                supplier=cascade,
                lot_number="LOT-2026-A102",
                heat_or_batch="HEAT-SS316-902",
                receipt_date=today - datetime.timedelta(days=3),
                inspection_date=today - datetime.timedelta(days=2),
                lot_quantity=Decimal("1000.000"),
                sample_size=80,
                inspected_quantity=80,
                accepted_quantity=Decimal("0.000"),
                rejected_quantity=Decimal("1000.000"),
                quarantine_quantity=Decimal("0.000"),
                critical_defects=2,
                major_defects=5,
                minor_defects=1,
                stage="completed",
                usage_decision="rejected",
                usage_decision_notes="Lot rejected: Critical outer diameter excursions beyond 25.02mm USL. Return for credit requested.",
                decided_by=admin_user,
                decided_at=timezone.now() - datetime.timedelta(days=2),
                inspector=admin_user,
                measurements_data=[
                    {"sample_no": 1, "characteristic": "Shaft Outer Diameter", "value": 24.960, "is_pass": False},
                    {"sample_no": 2, "characteristic": "Shaft Outer Diameter", "value": 24.970, "is_pass": False},
                    {"sample_no": 3, "characteristic": "Shaft Outer Diameter", "value": 25.035, "is_pass": False},
                    {"sample_no": 4, "characteristic": "Shaft Outer Diameter", "value": 25.010, "is_pass": True},
                ],
                spc_mean=Decimal("24.9938"),
                spc_std_dev=Decimal("0.0335"),
                spc_cp=Decimal("0.79"),
                spc_cpk=Decimal("0.73"),
                spc_out_of_control=True,
                linked_ncr=ncr,
                linked_scar=scar,
                notes="Tool wear during supplier lathe machining run identified as root cause.",
            )

            # Lot 3: Quarantined Lot for Medical Housing
            lot_enclosure = IncomingInspectionLot.objects.create(
                tenant=tenant,
                inspection_plan=plan_enclosure,
                item_code="POL-HOU-01",
                item_name="Diagnostic Device Base Enclosure Shell",
                supplier=umbrella,
                lot_number="LOT-2026-M404",
                heat_or_batch="BATCH-UB-77",
                receipt_date=today - datetime.timedelta(days=1),
                inspection_date=today,
                lot_quantity=Decimal("200.000"),
                sample_size=32,
                inspected_quantity=32,
                accepted_quantity=Decimal("0.000"),
                rejected_quantity=Decimal("0.000"),
                quarantine_quantity=Decimal("200.000"),
                critical_defects=0,
                major_defects=3,
                minor_defects=2,
                stage="under_mrb",
                usage_decision="quarantined",
                usage_decision_notes="Quarantined in QA Holding Bay A3 pending secondary biocompatibility testing.",
                decided_by=admin_user,
                decided_at=timezone.now(),
                inspector=admin_user,
                notes="Wall thickness variation observed in injection port area.",
            )

            # Lot 4: Skip-Lot Passed for PCB Controller
            lot_pcb = IncomingInspectionLot.objects.create(
                tenant=tenant,
                inspection_plan=plan_pcb,
                item_code="PCB-A440",
                item_name="Telemetry Core PCB Controller Assembly",
                supplier=northwind,
                lot_number="LOT-2026-E505",
                heat_or_batch="LOT-NW-PC-01",
                receipt_date=today - datetime.timedelta(days=4),
                inspection_date=today - datetime.timedelta(days=4),
                lot_quantity=Decimal("2500.000"),
                sample_size=0,
                inspected_quantity=0,
                accepted_quantity=Decimal("2500.000"),
                rejected_quantity=Decimal("0.000"),
                quarantine_quantity=Decimal("0.000"),
                critical_defects=0,
                major_defects=0,
                minor_defects=0,
                stage="completed",
                usage_decision="skip_lot_passed",
                usage_decision_notes="Auto-released under approved skip-lot 1:5 inspection policy.",
                decided_by=admin_user,
                decided_at=timezone.now() - datetime.timedelta(days=4),
                inspector=admin_user,
                notes="Skip-lot authorization verified against active AVL record.",
            )

            # 3. Certificates of Analysis (QCOA)
            # CoA 1: Compliant CoA for Shaft Lot A101
            coa_good = CertificateOfAnalysis.objects.create(
                tenant=tenant,
                certificate_number="COA-CAS-2026-081",
                supplier=cascade,
                item_code="PRT-10024",
                item_name="Drive Shaft 25mm Stainless",
                lot_number="LOT-2026-A101",
                inspection_lot=lot_shaft_good,
                inspection_plan=plan_shaft,
                manufacturer_name="Cascade Metallurgical Works",
                date_of_manufacture=today - datetime.timedelta(days=20),
                expiry_or_retest_date=today + datetime.timedelta(days=710),
                lab_accreditation="ISO/IEC 17025 Accredited Metrology Lab #441",
                parameters_payload=[
                    {
                        "parameter": "Tensile Strength",
                        "method": "ASTM E8",
                        "lsl": 550,
                        "usl": 750,
                        "actual_value": 625,
                        "unit": "MPa",
                        "is_pass": True,
                    },
                    {
                        "parameter": "Yield Strength",
                        "method": "ASTM E8",
                        "lsl": 240,
                        "usl": 400,
                        "actual_value": 315,
                        "unit": "MPa",
                        "is_pass": True,
                    },
                    {
                        "parameter": "Hardness HRC",
                        "method": "ASTM E18",
                        "lsl": 25,
                        "usl": 32,
                        "actual_value": 29,
                        "unit": "HRC",
                        "is_pass": True,
                    },
                ],
                variance_count=0,
                is_within_spec=True,
                status="verified_compliant",
                verified_by=admin_user,
                verified_at=timezone.now() - datetime.timedelta(days=6),
                supporting_document=sop_doc,
                notes="Certified test report verified against drawing rev B metallurgical requirements.",
            )

            # CoA 2: Exception CoA for Shaft Lot A102
            coa_bad = CertificateOfAnalysis.objects.create(
                tenant=tenant,
                certificate_number="COA-CAS-2026-082",
                supplier=cascade,
                item_code="PRT-10024",
                item_name="Drive Shaft 25mm Stainless",
                lot_number="LOT-2026-A102",
                inspection_lot=lot_shaft_bad,
                inspection_plan=plan_shaft,
                manufacturer_name="Cascade Metallurgical Works",
                date_of_manufacture=today - datetime.timedelta(days=15),
                expiry_or_retest_date=today + datetime.timedelta(days=715),
                lab_accreditation="Supplier Factory Lab",
                parameters_payload=[
                    {
                        "parameter": "Tensile Strength",
                        "method": "ASTM E8",
                        "lsl": 550,
                        "usl": 750,
                        "actual_value": 520,
                        "unit": "MPa",
                        "is_pass": False,
                    },
                    {
                        "parameter": "Hardness HRC",
                        "method": "ASTM E18",
                        "lsl": 25,
                        "usl": 32,
                        "actual_value": 28,
                        "unit": "HRC",
                        "is_pass": True,
                    },
                ],
                variance_count=1,
                is_within_spec=False,
                status="exception_detected",
                verified_by=admin_user,
                verified_at=timezone.now() - datetime.timedelta(days=2),
                notes="Tensile strength 520 MPa is below 550 MPa minimum specification limit.",
            )

            # CoA 3: Received CoA for PCB Controller
            CertificateOfAnalysis.objects.create(
                tenant=tenant,
                certificate_number="COA-NW-2026-191",
                supplier=northwind,
                item_code="PCB-A440",
                item_name="Telemetry Core PCB Controller Assembly",
                lot_number="LOT-2026-E505",
                inspection_lot=lot_pcb,
                inspection_plan=plan_pcb,
                manufacturer_name="Northwind Advanced Circuit Solutions",
                date_of_manufacture=today - datetime.timedelta(days=10),
                expiry_or_retest_date=today + datetime.timedelta(days=355),
                lab_accreditation="TUV Rheinland Certified QA Lab",
                parameters_payload=[
                    {
                        "parameter": "Firmware CRC Checksum",
                        "method": "Automated Test Bench",
                        "expected": "0xFA9941",
                        "actual_value": "0xFA9941",
                        "unit": "HEX",
                        "is_pass": True,
                    }
                ],
                variance_count=0,
                is_within_spec=True,
                status="received",
                notes="Awaiting formal QC engineer sign-off.",
            )

            # 4. Quality Return Authorizations (QRMA)
            # RMA 1: Rejected lot return to Cascade Components
            QualityReturnAuthorization.objects.create(
                tenant=tenant,
                inspection_lot=lot_shaft_bad,
                supplier=cascade,
                vendor_rma_number="VRMA-CAS-2026-881",
                return_reason="dimensional_oos",
                disposition_type="return_for_credit",
                return_quantity=Decimal("1000.000"),
                unit_of_measure="EA",
                estimated_credit_value=Decimal("4500.00"),
                status="shipped_to_vendor",
                carrier="FedEx Freight",
                tracking_number="7849 2011 8841",
                bill_of_lading="BOL-CAS-9941",
                shipped_date=today - datetime.timedelta(days=1),
                debit_memo_number="DM-2026-092",
                settled_amount=Decimal("0.00"),
                assigned_coordinator=admin_user,
                linked_ncr=ncr,
                linked_scar=scar,
                notes="All 1,000 shafts securely packed on 2 pallets and dispatched to Cascade Components machine shop.",
            )

            # RMA 2: Replacement RMA for Umbrella Chemical Enclosure
            QualityReturnAuthorization.objects.create(
                tenant=tenant,
                inspection_lot=lot_enclosure,
                supplier=umbrella,
                vendor_rma_number="VRMA-UMB-2026-404",
                return_reason="contamination",
                disposition_type="return_for_replacement",
                return_quantity=Decimal("200.000"),
                unit_of_measure="EA",
                estimated_credit_value=Decimal("1200.00"),
                status="rma_approved",
                assigned_coordinator=admin_user,
                notes="Supplier accepted return; replacement production run scheduled for next week.",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.7 Incoming Quality Control (IQC) seeded successfully."))

    def _seed_submodule_12_8(self, tenant):
        if InProcessInspection.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.8 In-Process Quality Control (IPQC) data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.8 In-Process Quality Control (IPQC)...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        if not admin_user:
            self.stdout.write(f"[{tenant.name}] Warning: No user found for tenant.")
            return

        users = list(User.objects.filter(tenant=tenant).order_by("pk"))
        inspector_user = users[1] if len(users) > 1 else admin_user
        verifier_user = users[2] if len(users) > 2 else admin_user

        now = timezone.now()

        with transaction.atomic():
            # 1. In-Process Inspections (QIPQ)
            InProcessInspection.objects.create(
                tenant=tenant,
                title="CNC Mill Line 2 - Routine In-Line Inspection",
                inspection_type="dimensional_gauging",
                stage_gate="Op 020 - Turning",
                status="completed",
                disposition="pass",
                production_order_number="PO-2026-8801",
                work_center_code="WC-CNC-02",
                operation_step="Op 020 - Turning",
                item_code="ST-SHAFT-22",
                item_name="Precision Turbine Stainless Drive Shaft",
                lot_number="LOT-2026-IP-001",
                serial_number="SN-IP-9901",
                batch_quantity=500,
                sample_size_inspected=5,
                quantity_passed=5,
                quantity_rejected=0,
                quantity_reworked=0,
                defect_category="",
                defect_description="",
                inspector=inspector_user,
                inspection_date=now.date(),
                notes="Tool offset calibrated. Spindle runout within allowable tolerance. Approved to run batch.",
            )

            InProcessInspection.objects.create(
                tenant=tenant,
                title="SMT Assembly Line 1 - Hourly Solder Paste Check",
                inspection_type="visual_surface",
                stage_gate="SMT Screen Printing",
                status="completed",
                disposition="conditional_pass",
                production_order_number="PO-2026-8802",
                work_center_code="WC-SMT-01",
                operation_step="Op 010 - Screen Print",
                item_code="PCB-A440",
                item_name="Telemetry Core PCB Controller Assembly",
                lot_number="LOT-2026-IP-002",
                batch_quantity=1200,
                sample_size_inspected=32,
                quantity_passed=31,
                quantity_rejected=0,
                quantity_reworked=1,
                defect_category="assembly_error",
                defect_description="Minor solder bridging reworked on bench. Stencil wiper frequency increased.",
                inspector=inspector_user,
                inspection_date=now.date(),
                notes="Minor solder bridging reworked on bench.",
            )

            InProcessInspection.objects.create(
                tenant=tenant,
                title="Line 3 Clearance & Changeover Verification",
                inspection_type="in_line_stage_gate",
                stage_gate="Assembly Final Changeover",
                status="in_progress",
                disposition="pending",
                production_order_number="PO-2026-8805",
                work_center_code="WC-ASM-03",
                operation_step="Op 050 - Assembly",
                item_code="ASM-VALVE-X1",
                item_name="Hydraulic Proportional Flow Valve Assembly",
                lot_number="LOT-2026-IP-003",
                batch_quantity=250,
                sample_size_inspected=10,
                quantity_passed=10,
                quantity_rejected=0,
                quantity_reworked=0,
                inspector=inspector_user,
                inspection_date=now.date(),
                notes="Changeover line clearance verification in progress.",
            )

            # 2. First Article Inspections (QFAI - AS9102 / PPAP)
            FirstArticleInspection.objects.create(
                tenant=tenant,
                title="AS9102 Rev C Full FAI - Titanium Strut",
                fai_type="full_fai",
                setup_reason="new_product_intro",
                status="approved_run_released",
                release_verdict="released",
                production_order_number="PO-2026-FAI-01",
                work_center_code="WC-CNC-01",
                machine_tooling_id="CNC-5AX-01",
                item_code="AERO-BRKT-901",
                item_name="Titanium Support Bracket Strut",
                drawing_number="DWG-AERO-901-REV-C",
                drawing_revision="Rev C",
                first_piece_lot_number="LOT-2026-FAI-001",
                serial_number="FAI-SN-001",
                total_characteristics_inspected=18,
                characteristics_conforming=18,
                characteristics_out_of_spec=0,
                max_deviation_found="+0.003 mm on Bore Dia",
                as9102_form1_complete=True,
                as9102_form2_complete=True,
                as9102_form3_complete=True,
                gage_serial_numbers="CMM-ZEISS-01, MIC-MIT-22",
                inspector=inspector_user,
                approved_by=admin_user,
                approved_at=now,
                notes="AS9102 Rev C complete package approved.",
            )

            FirstArticleInspection.objects.create(
                tenant=tenant,
                title="Tooling Die Replacement Delta FAI - Die-Cast Module Housing",
                fai_type="delta_partial_fai",
                setup_reason="tooling_die_change",
                status="conditional_approval",
                release_verdict="conditional_pilot_release",
                production_order_number="PO-2026-FAI-02",
                work_center_code="WC-CAST-02",
                machine_tooling_id="DIE-CAST-T4",
                item_code="HSG-ALUM-402",
                item_name="Die-Cast Electronic Module Housing",
                drawing_number="DWG-HSG-402-REV-B",
                drawing_revision="Rev B",
                first_piece_lot_number="LOT-2026-FAI-002",
                serial_number="FAI-SN-002",
                total_characteristics_inspected=12,
                characteristics_conforming=11,
                characteristics_out_of_spec=1,
                max_deviation_found="+0.025 mm Cavity Depth",
                as9102_form1_complete=True,
                as9102_form2_complete=True,
                as9102_form3_complete=False,
                gage_serial_numbers="HG-VERNIER-05, CMM-02",
                conditional_release_notes="Pilot run of 50 units authorized under 100% manual dimensional check.",
                inspector=inspector_user,
                approved_by=admin_user,
                approved_at=now,
                notes="Tool insert T4 qualified for pilot release.",
            )

            # 3. Process Parameter Logs (QPAR)
            ProcessParameterLog.objects.create(
                tenant=tenant,
                parameter_name="Peak Reflow Temperature",
                parameter_category="temperature",
                unit_of_measure="°C",
                work_center_code="WC-SMT-01",
                production_order_number="PO-2026-8802",
                operation_step="Op 030 - Reflow",
                item_code="PCB-A440",
                lot_number="LOT-2026-IP-002",
                target_nominal_value=Decimal("245.0000"),
                upper_spec_limit=Decimal("255.0000"),
                lower_spec_limit=Decimal("235.0000"),
                upper_control_limit=Decimal("250.0000"),
                lower_control_limit=Decimal("240.0000"),
                recorded_value=Decimal("246.2000"),
                recorded_at=now - datetime.timedelta(hours=2),
                excursion_status="normal",
                logged_by=inspector_user,
                containment_action="none",
                containment_notes="Peak temperature stable across all 10 thermocouple channels.",
            )

            ProcessParameterLog.objects.create(
                tenant=tenant,
                parameter_name="Pack Pressure",
                parameter_category="pressure",
                unit_of_measure="bar",
                work_center_code="WC-MOLD-01",
                production_order_number="PO-2026-8808",
                operation_step="Op 010 - Molding",
                item_code="HSG-ALUM-402",
                lot_number="LOT-2026-IP-008",
                target_nominal_value=Decimal("85.0000"),
                upper_spec_limit=Decimal("95.0000"),
                lower_spec_limit=Decimal("75.0000"),
                upper_control_limit=Decimal("90.0000"),
                lower_control_limit=Decimal("80.0000"),
                recorded_value=Decimal("96.5000"),
                recorded_at=now - datetime.timedelta(hours=1),
                excursion_status="out_of_spec",
                logged_by=inspector_user,
                containment_action="machine_parameter_adjusted",
                containment_notes="Overpressure exceeded USL. Hydraulic relief valve calibrated and returned to 84.8 bar.",
            )

            ProcessParameterLog.objects.create(
                tenant=tenant,
                parameter_name="Finish Turn Spindle Speed",
                parameter_category="speed_feed",
                unit_of_measure="RPM",
                work_center_code="WC-CNC-02",
                production_order_number="PO-2026-8801",
                operation_step="Op 020 - Turning",
                item_code="ST-SHAFT-22",
                lot_number="LOT-2026-IP-001",
                target_nominal_value=Decimal("3200.0000"),
                upper_spec_limit=Decimal("3300.0000"),
                lower_spec_limit=Decimal("3100.0000"),
                upper_control_limit=Decimal("3250.0000"),
                lower_control_limit=Decimal("3150.0000"),
                recorded_value=Decimal("3195.0000"),
                recorded_at=now - datetime.timedelta(minutes=30),
                excursion_status="normal",
                logged_by=admin_user,
                containment_action="none",
                containment_notes="Spindle drive tachometer feedback within 0.2% of setpoint.",
            )

            # 4. Layered Process Audits (QLPA)
            LayeredProcessAudit.objects.create(
                tenant=tenant,
                title="Tier 2 Supervisor LPA - Machining Line 2 Standard Work",
                audit_layer="tier_2_supervisor",
                focus_area="standard_work_wi",
                status="completed",
                work_center_code="WC-CNC-02",
                shift="Shift 1 (Morning)",
                scheduled_date=now.date(),
                conducted_at=now,
                total_questions_audited=10,
                questions_conforming=10,
                questions_non_conforming=0,
                compliance_percentage=Decimal("100.00"),
                findings_summary="Excellent compliance observed on CNC Mill Line 2. Clean workstation, standard work displayed, gauges valid.",
                on_the_spot_mitigation=False,
                auditor=inspector_user,
                notes="Clean pass on daily supervisor tier 2 LPA.",
            )

            LayeredProcessAudit.objects.create(
                tenant=tenant,
                title="Tier 3 Quality Manager LPA - Electronics Assembly & ESD Controls",
                audit_layer="tier_3_quality_manager",
                focus_area="gauging_calibration",
                status="completed",
                work_center_code="WC-SMT-01",
                shift="Shift 2 (Evening)",
                scheduled_date=now.date(),
                conducted_at=now,
                total_questions_audited=10,
                questions_conforming=9,
                questions_non_conforming=1,
                compliance_percentage=Decimal("90.00"),
                findings_summary="One torque driver at bench 4 had calibration sticker expiring today. Immediately replaced with newly calibrated tool.",
                on_the_spot_mitigation=True,
                mitigation_details="Tool swapped from calibration crib immediately. Serial #TQ-881 checked in for recalibration.",
                auditor=verifier_user,
                notes="On-the-spot mitigation verified.",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.8 In-Process Quality Control (IPQC) seeded successfully."))

    def _seed_submodule_12_10(self, tenant):
        if CalibrationGage.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.10 Calibration & Measurement System Analysis data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.10 Calibration & Measurement System Analysis (MSA)...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        inspector_user = (
            User.objects.filter(tenant=tenant, username__icontains="inspector").order_by("pk").first()
            or admin_user
        )
        verifier_user = (
            User.objects.filter(tenant=tenant, username__icontains="quality").order_by("pk").first()
            or admin_user
        )
        vendor_party = (
            Party.objects.filter(tenant=tenant, roles__role="vendor").first()
            or Party.objects.filter(tenant=tenant).first()
        )
        dept = OrgUnit.objects.filter(tenant=tenant).first()
        sop_doc = ControlledDocument.objects.filter(tenant=tenant).first()
        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            # 1. Master Reference Standard
            std_gage = CalibrationGage.objects.create(
                tenant=tenant,
                gage_id="GAG-STD-001",
                name="Grade 0 Ceramic Master Gauge Block Set (81 Pcs)",
                gage_type="gauge_block_pin",
                criticality="critical",
                status="active_in_service",
                manufacturer="Mitutoyo",
                model_number="516-902-26",
                serial_number="MIT-STD-8841",
                measurement_range="0.5 to 100 mm",
                resolution="0.0001 mm",
                accuracy_spec="±0.0002 mm (ISO 3650 Grade 0)",
                max_permissible_error=Decimal("0.0002"),
                engineering_unit="mm",
                is_reference_standard=True,
                nist_traceability_number="NIST-TEST-2026-8841-B",
                storage_location="Metrology Cleanroom Vault STD-1",
                custodian=verifier_user,
                department=dept,
                calibration_interval_days=730,
                last_calibration_date=today - datetime.timedelta(days=120),
                next_calibration_due=today + datetime.timedelta(days=610),
                last_calibration_result="Pass (Fully Conforming)",
                sop_document=sop_doc,
                notes="Primary lab reference standard. Must be handled with cotton gloves at 20.0 °C.",
            )

            # 2. Digital Caliper (Working Gage)
            caliper_gage = CalibrationGage.objects.create(
                tenant=tenant,
                gage_id="GAG-DIG-002",
                name="0-150mm IP67 Digital Caliper",
                gage_type="caliper_micrometer",
                criticality="critical",
                status="active_in_service",
                manufacturer="Mitutoyo",
                model_number="500-196-30",
                serial_number="MIT-500-8819",
                measurement_range="0 to 150 mm",
                resolution="0.01 mm",
                accuracy_spec="±0.02 mm",
                max_permissible_error=Decimal("0.0200"),
                engineering_unit="mm",
                is_reference_standard=False,
                reference_standard_parent=std_gage,
                storage_location="Quality Inspection Bench 1",
                custodian=inspector_user,
                department=dept,
                calibration_interval_days=365,
                last_calibration_date=today - datetime.timedelta(days=60),
                next_calibration_due=today + datetime.timedelta(days=305),
                last_calibration_result="Pass (Fully Conforming)",
                sop_document=sop_doc,
                notes="In-line inspection caliper for outer diameters.",
            )

            # 3. Precision External Micrometer
            mic_gage = CalibrationGage.objects.create(
                tenant=tenant,
                gage_id="GAG-MIC-003",
                name="0-25mm Precision Digital External Micrometer",
                gage_type="caliper_micrometer",
                criticality="critical",
                status="active_in_service",
                manufacturer="Starrett",
                model_number="733XFL-1",
                serial_number="STR-2026-0912",
                measurement_range="0 to 25 mm",
                resolution="0.001 mm",
                accuracy_spec="±0.002 mm",
                max_permissible_error=Decimal("0.0020"),
                engineering_unit="mm",
                is_reference_standard=False,
                reference_standard_parent=std_gage,
                storage_location="Machining Cell 2 Cabinet",
                custodian=inspector_user,
                department=dept,
                calibration_interval_days=180,
                last_calibration_date=today - datetime.timedelta(days=30),
                next_calibration_due=today + datetime.timedelta(days=150),
                last_calibration_result="Pass (Fully Conforming)",
                sop_document=sop_doc,
                notes="Used for ground pin and shaft OD verifications.",
            )

            # 4. Hydraulic Pressure Gauge (Past Due)
            prs_gage = CalibrationGage.objects.create(
                tenant=tenant,
                gage_id="GAG-PRS-004",
                name="0-100 PSI Test Pressure Gauge",
                gage_type="pressure_vacuum",
                criticality="major",
                status="past_due",
                manufacturer="WIKA",
                model_number="232.50",
                serial_number="WIK-99214-P",
                measurement_range="0 to 100 psi",
                resolution="0.5 psi",
                accuracy_spec="±1.0% FS",
                max_permissible_error=Decimal("1.0000"),
                engineering_unit="psi",
                is_reference_standard=False,
                storage_location="Hydraulics Test Stand 3",
                custodian=admin_user,
                department=dept,
                calibration_interval_days=365,
                last_calibration_date=today - datetime.timedelta(days=400),
                next_calibration_due=today - datetime.timedelta(days=35),
                last_calibration_result="Pass (Fully Conforming)",
                sop_document=sop_doc,
                notes="Scheduled for calibration crib pickup.",
            )

            # 5. Benchtop Multimeter (In Calibration)
            mm_gage = CalibrationGage.objects.create(
                tenant=tenant,
                gage_id="GAG-ELC-005",
                name="6.5 Digit Precision Benchtop Multimeter",
                gage_type="electrical_multimeter",
                criticality="major",
                status="in_calibration",
                manufacturer="Fluke",
                model_number="8846A",
                serial_number="FLK-8846A-882",
                measurement_range="0 to 1000 V / 0 to 10 A",
                resolution="6.5 Digits",
                accuracy_spec="0.0024% DC",
                max_permissible_error=Decimal("0.0050"),
                engineering_unit="v",
                is_reference_standard=False,
                storage_location="Calibration Service Lab",
                custodian=admin_user,
                department=dept,
                calibration_interval_days=365,
                last_calibration_date=today - datetime.timedelta(days=360),
                next_calibration_due=today + datetime.timedelta(days=5),
                last_calibration_result="In Progress",
                sop_document=sop_doc,
                notes="Shipped to Fluke certified calibration center.",
            )

            # 6. Torque Wrench (Quarantined Out-of-Tolerance)
            trq_gage = CalibrationGage.objects.create(
                tenant=tenant,
                gage_id="GAG-TRQ-006",
                name="10-100 Nm Electronic Torque Wrench",
                gage_type="torque_force",
                criticality="critical",
                status="quarantined_oot",
                manufacturer="Snap-on",
                model_number="ATECH2FR100",
                serial_number="SNAP-2026-TRQ",
                measurement_range="10 to 100 Nm",
                resolution="0.1 Nm",
                accuracy_spec="±2% CW",
                max_permissible_error=Decimal("2.0000"),
                engineering_unit="nm",
                is_reference_standard=False,
                storage_location="Quarantine Locker Q-01",
                custodian=verifier_user,
                department=dept,
                calibration_interval_days=180,
                last_calibration_date=today - datetime.timedelta(days=10),
                next_calibration_due=today + datetime.timedelta(days=170),
                last_calibration_result="Fail (Out-of-Tolerance)",
                sop_document=sop_doc,
                notes="Failed As-Found calibration test on 100 Nm setting. Quarantined immediately.",
            )

            # Calibration Records
            # Event 1: Std Gage Passed
            cal_rec_1 = CalibrationRecord.objects.create(
                tenant=tenant,
                gage=std_gage,
                calibration_date=today - datetime.timedelta(days=120),
                calibration_type="external_accredited",
                status="completed",
                service_vendor=vendor_party,
                certificate_number="CERT-ISO17025-2026-001",
                as_found_condition="in_tolerance",
                as_left_condition="in_tolerance",
                overall_result="pass",
                ambient_temperature_c=Decimal("20.00"),
                ambient_relative_humidity=Decimal("45.00"),
                expanded_uncertainty=Decimal("0.0001"),
                test_uncertainty_ratio=Decimal("4.00"),
                max_observed_error=Decimal("0.0001"),
                guardband_applied=True,
                technician_name="Dr. Marcus Vance, Metrologist",
                calibrated_by_user=verifier_user,
                approved_by=admin_user,
                approved_at=now,
                notes="ISO/IEC 17025 accredited calibration performed under controlled environmental conditions.",
            )

            # Event 2: Caliper Passed Internal
            cal_rec_2 = CalibrationRecord.objects.create(
                tenant=tenant,
                gage=caliper_gage,
                calibration_date=today - datetime.timedelta(days=60),
                calibration_type="internal_metrology",
                status="completed",
                certificate_number="INT-CAL-2026-042",
                as_found_condition="in_tolerance",
                as_left_condition="in_tolerance",
                overall_result="pass",
                ambient_temperature_c=Decimal("20.20"),
                ambient_relative_humidity=Decimal("46.50"),
                expanded_uncertainty=Decimal("0.0050"),
                test_uncertainty_ratio=Decimal("4.00"),
                max_observed_error=Decimal("0.0080"),
                guardband_applied=True,
                standard_traceability_notes="Verified against Master Gauge Block Set GAG-STD-001.",
                technician_name="Sarah Jenkins",
                calibrated_by_user=inspector_user,
                approved_by=verifier_user,
                approved_at=now,
                notes="Internal verification complete. All test points conforming.",
            )
            cal_rec_2.standards_used.add(std_gage)

            # Event 3: Micrometer Passed External
            cal_rec_3 = CalibrationRecord.objects.create(
                tenant=tenant,
                gage=mic_gage,
                calibration_date=today - datetime.timedelta(days=30),
                calibration_type="external_accredited",
                status="completed",
                service_vendor=vendor_party,
                certificate_number="CERT-ISO17025-2026-109",
                as_found_condition="in_tolerance",
                as_left_condition="in_tolerance",
                overall_result="pass",
                ambient_temperature_c=Decimal("20.00"),
                ambient_relative_humidity=Decimal("44.00"),
                expanded_uncertainty=Decimal("0.0005"),
                test_uncertainty_ratio=Decimal("4.00"),
                max_observed_error=Decimal("0.0008"),
                guardband_applied=True,
                technician_name="Robert Lang, CCT",
                calibrated_by_user=verifier_user,
                approved_by=admin_user,
                approved_at=now,
                notes="Anvil and spindle flatness and parallelism verified within 0.001mm.",
            )

            # Event 4: Torque Wrench Failed OOT
            cal_rec_4 = CalibrationRecord.objects.create(
                tenant=tenant,
                gage=trq_gage,
                calibration_date=today - datetime.timedelta(days=10),
                calibration_type="internal_metrology",
                status="completed",
                certificate_number="INT-CAL-2026-OOT-01",
                as_found_condition="out_of_tolerance",
                as_left_condition="out_of_tolerance",
                overall_result="fail_out_of_tolerance",
                ambient_temperature_c=Decimal("20.50"),
                ambient_relative_humidity=Decimal("48.00"),
                expanded_uncertainty=Decimal("0.5000"),
                test_uncertainty_ratio=Decimal("3.50"),
                max_observed_error=Decimal("4.8000"),
                guardband_applied=True,
                technician_name="Sarah Jenkins",
                calibrated_by_user=inspector_user,
                approved_by=verifier_user,
                approved_at=now,
                notes="100 Nm test point drifted to 104.8 Nm (error +4.8 Nm exceeds ±2.0 Nm tolerance).",
            )

            # 3. Out-of-Tolerance Investigation
            OutOfToleranceInvestigation.objects.create(
                tenant=tenant,
                calibration_record=cal_rec_4,
                gage=trq_gage,
                discovery_date=today - datetime.timedelta(days=10),
                status="investigating",
                risk_level="critical",
                title="Electronic Torque Wrench High-End Drift at 100 Nm Setting",
                as_found_error_description=(
                    "During routine recalibration, GAG-TRQ-006 exhibited excessive positive error at the 100 Nm point: "
                    "Recorded 104.8 Nm (+4.8 Nm error vs max permissible tolerance of ±2.0 Nm). "
                    "Lower test points (20 Nm and 50 Nm) were within tolerance."
                ),
                suspect_window_start=today - datetime.timedelta(days=180),
                suspect_window_end=today - datetime.timedelta(days=10),
                suspect_production_orders="WO-2026-ASM-041, WO-2026-ASM-048, Batch #8812-B",
                suspect_lots_count=8,
                products_affected="Gearbox Assembly P/N GBX-900, Flange Bolts",
                consumer_risk_rating=4,
                producer_risk_rating=3,
                containment_actions_taken=(
                    "1. Physical quarantine of GAG-TRQ-006 in metrology locker Q-01 with red lockout tag. "
                    "2. Hold placed on 42 finished gearboxes in warehouse pending breakaway torque audit."
                ),
                product_disposition="re_inspect_inventory",
                customer_notification_required=False,
                product_recall_required=False,
                investigator=verifier_user,
                quality_approver=admin_user,
                conclusion_summary=(
                    "Preliminary audit of warehouse units shows actual fastener torque maintained adequate clamp load. "
                    "100% verification continuing on remaining lots."
                ),
            )

            # 4. Measurement System Analysis (MSA / Gage R&R) Studies
            # Study 1: Caliper Crossed ANOVA (Acceptable)
            MeasurementSystemAnalysis.objects.create(
                tenant=tenant,
                study_title="0-150mm Digital Caliper Gage R&R for Pin Outer Diameter",
                gage=caliper_gage,
                study_type="gage_rr_crossed",
                analysis_method="anova",
                status="approved",
                characteristic_name="Pin Outer Diameter (OD)",
                study_date=today - datetime.timedelta(days=45),
                number_of_operators=3,
                number_of_parts=10,
                number_of_trials=3,
                specification_tolerance=Decimal("0.1000"),
                reference_master_value=Decimal("12.5000"),
                repeatability_ev=Decimal("0.0018"),
                reproducibility_av=Decimal("0.0011"),
                gage_rr_grr=Decimal("0.0021"),
                part_variation_pv=Decimal("0.0280"),
                total_variation_tv=Decimal("0.0281"),
                percent_gage_rr_study_variation=Decimal("7.42"),
                percent_tolerance_pt_ratio=Decimal("12.60"),
                number_of_distinct_categories_ndc=Decimal("18.80"),
                study_result="acceptable",
                study_protocol_doc=sop_doc,
                study_lead=inspector_user,
                approved_by=verifier_user,
                approved_at=now,
                conclusion="Measurement system is fully acceptable for production quality verification per AIAG standards (%GRR < 10%).",
                notes="ANOVA method confirms negligible operator-by-part interaction.",
            )

            # Study 2: Micrometer Crossed (Marginal)
            MeasurementSystemAnalysis.objects.create(
                tenant=tenant,
                study_title="Micrometer Gage R&R for Tight-Tolerance Hydraulic Spool Diameter",
                gage=mic_gage,
                study_type="gage_rr_crossed",
                analysis_method="average_and_range_xbar_r",
                status="approved",
                characteristic_name="Spool Valve OD",
                study_date=today - datetime.timedelta(days=20),
                number_of_operators=3,
                number_of_parts=10,
                number_of_trials=3,
                specification_tolerance=Decimal("0.0150"),
                reference_master_value=Decimal("8.0000"),
                repeatability_ev=Decimal("0.0008"),
                reproducibility_av=Decimal("0.0006"),
                gage_rr_grr=Decimal("0.0010"),
                part_variation_pv=Decimal("0.0065"),
                total_variation_tv=Decimal("0.0066"),
                percent_gage_rr_study_variation=Decimal("15.15"),
                percent_tolerance_pt_ratio=Decimal("20.00"),
                number_of_distinct_categories_ndc=Decimal("9.20"),
                study_result="marginal_conditional",
                study_protocol_doc=sop_doc,
                study_lead=inspector_user,
                approved_by=verifier_user,
                approved_at=now,
                conclusion="Measurement system is conditionally acceptable (10-30% range). Operator training on ratchet thimble stop recommended.",
                notes="X-bar and R chart shows operator B has slight upward bias.",
            )

            # Study 3: Standard Gauge Block Linearity & Bias
            MeasurementSystemAnalysis.objects.create(
                tenant=tenant,
                study_title="Master Gauge Block Set Linearity and Bias Calibration Evaluation",
                gage=std_gage,
                study_type="linearity_and_bias",
                analysis_method="anova",
                status="approved",
                characteristic_name="Block Length Deviation",
                study_date=today - datetime.timedelta(days=100),
                number_of_operators=1,
                number_of_parts=5,
                number_of_trials=12,
                specification_tolerance=Decimal("0.0010"),
                reference_master_value=Decimal("50.0000"),
                repeatability_ev=Decimal("0.0001"),
                reproducibility_av=Decimal("0.0000"),
                gage_rr_grr=Decimal("0.0001"),
                part_variation_pv=Decimal("0.0009"),
                total_variation_tv=Decimal("0.0009"),
                percent_gage_rr_study_variation=Decimal("1.10"),
                percent_tolerance_pt_ratio=Decimal("2.40"),
                number_of_distinct_categories_ndc=Decimal("45.00"),
                bias_value=Decimal("0.0000"),
                bias_percentage=Decimal("0.05"),
                linearity_slope=Decimal("0.0001"),
                linearity_r_squared=Decimal("0.9998"),
                study_result="acceptable",
                study_protocol_doc=sop_doc,
                study_lead=verifier_user,
                approved_by=admin_user,
                approved_at=now,
                conclusion="Exceptional linearity and zero detectable bias across entire 100mm span.",
                notes="Evaluated with Tesa laser micrometer in cleanroom.",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.10 Calibration & Measurement System Analysis (MSA) seeded successfully."))

    def _seed_submodule_12_9(self, tenant):
        if FinalInspectionLot.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.9 Final Quality Control (FQC / OQC) data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.9 Final Quality Control (FQC / OQC)...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        if not admin_user:
            self.stdout.write(f"[{tenant.name}] Warning: No user found for tenant.")
            return

        users = list(User.objects.filter(tenant=tenant).order_by("pk"))
        inspector_user = users[1] if len(users) > 1 else admin_user
        verifier_user = users[2] if len(users) > 2 else admin_user

        customer = (
            Party.objects.filter(tenant=tenant, roles__role__in=("customer", "client")).first()
            or Party.objects.filter(tenant=tenant).order_by("pk").first()
        )
        if not customer:
            customer = Party.objects.create(
                tenant=tenant,
                name=f"{tenant.name} Premier Aero Client",
            )

        sop_doc = ControlledDocument.objects.filter(tenant=tenant).first()

        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            # 1. Final Inspection Lots (QFQC)
            lot_1 = FinalInspectionLot.objects.create(
                tenant=tenant,
                title="Post-Packaging OQC - Medical Titanium Bone Screws Batch 44",
                inspection_stage="post_packaging_oqc",
                sampling_standard="ansi_asq_z1_4_normal",
                aql_critical=Decimal("0.00"),
                aql_major=Decimal("0.65"),
                aql_minor=Decimal("4.00"),
                status="completed",
                usage_decision="accepted",
                decision_rationale="AQL inspection conforming to ISO 2859-1 Level II. Zero critical defects found.",
                item_code="MED-TBS-40",
                item_name="Titanium Polyaxial Bone Screw 4.0mm x 40mm",
                lot_number="LOT-2026-FQC-001",
                batch_number="BATCH-M44",
                serial_number_range="TBS-44001 through TBS-44500",
                lot_quantity=5000,
                sample_size_inspected=200,
                critical_defects_count=0,
                major_defects_count=0,
                minor_defects_count=1,
                units_passed=199,
                units_rejected=1,
                visual_inspection_passed=True,
                dimensional_inspection_passed=True,
                functional_test_passed=True,
                packaging_inspection_passed=True,
                is_on_hold=False,
                customer=customer,
                sales_order_number="SO-2026-9041",
                inspection_plan=sop_doc,
                inspector=inspector_user,
                decision_by=verifier_user,
                inspection_date=today - datetime.timedelta(days=2),
                decision_date=today - datetime.timedelta(days=2),
                inspection_notes="Cleanroom double sterile blister pack inspected under laminar flow hood.",
            )

            lot_2 = FinalInspectionLot.objects.create(
                tenant=tenant,
                title="Pre-Packaging FQC - Aerospace Precision Actuator Housing",
                inspection_stage="pre_packaging_fqc",
                sampling_standard="c_zero_sampling",
                aql_critical=Decimal("0.00"),
                aql_major=Decimal("0.25"),
                aql_minor=Decimal("1.50"),
                status="completed",
                usage_decision="accepted_with_concession",
                decision_rationale="Minor surface anodizing cosmetic variation accepted per customer engineering deviation DEV-2026-08.",
                item_code="AERO-ACT-770",
                item_name="Electro-Hydraulic Flight Actuator Housing",
                lot_number="LOT-2026-FQC-002",
                batch_number="BATCH-ACT-77",
                serial_number_range="ACT-7701 through ACT-7780",
                lot_quantity=80,
                sample_size_inspected=80,
                critical_defects_count=0,
                major_defects_count=0,
                minor_defects_count=2,
                units_passed=78,
                units_rejected=0,
                visual_inspection_passed=True,
                dimensional_inspection_passed=True,
                functional_test_passed=True,
                packaging_inspection_passed=True,
                is_on_hold=False,
                customer=customer,
                sales_order_number="SO-2026-9115",
                inspection_plan=sop_doc,
                inspector=inspector_user,
                decision_by=admin_user,
                inspection_date=today - datetime.timedelta(days=1),
                decision_date=today - datetime.timedelta(days=1),
                inspection_notes="100% C=0 inspection protocol applied for flight-critical component.",
            )

            lot_3 = FinalInspectionLot.objects.create(
                tenant=tenant,
                title="Finished Goods Dock Hold - Automotive Sensor Harness Assembly",
                inspection_stage="finished_goods_dock",
                sampling_standard="ansi_asq_z1_4_tightened",
                aql_critical=Decimal("0.00"),
                aql_major=Decimal("1.00"),
                aql_minor=Decimal("2.50"),
                status="in_progress",
                usage_decision="quarantined_hold",
                decision_rationale="Outer shipping carton moisture indicator turned pink. Batch quarantined on hold pending repack audit.",
                item_code="AUTO-HARN-09",
                item_name="Powertrain CAN Bus Shielded Sensor Wiring Harness",
                lot_number="LOT-2026-FQC-003",
                batch_number="BATCH-HARN-09B",
                lot_quantity=1500,
                sample_size_inspected=125,
                critical_defects_count=0,
                major_defects_count=3,
                minor_defects_count=4,
                units_passed=118,
                units_rejected=7,
                visual_inspection_passed=False,
                dimensional_inspection_passed=True,
                functional_test_passed=True,
                packaging_inspection_passed=False,
                is_on_hold=True,
                hold_reason="Shipping pallet barrier bag unsealed during dock staging. Quarantine hold placed.",
                customer=customer,
                sales_order_number="SO-2026-9280",
                inspector=inspector_user,
                decision_by=None,
                inspection_date=today,
                decision_date=None,
                inspection_notes="Sample pulled from dock bay 4. Awaiting packaging integrity verification.",
            )

            # 2. Certificates of Conformance (QCOC)
            coc_1 = CertificateOfConformance.objects.create(
                tenant=tenant,
                title="Certificate of Conformance - Titanium Bone Screws Batch 44",
                certificate_type="medical_device_iso13485",
                status="approved_signed",
                customer=customer,
                customer_po_number="PO-CUST-88392",
                sales_order_number="SO-2026-9041",
                item_code="MED-TBS-40",
                item_name="Titanium Polyaxial Bone Screw 4.0mm x 40mm",
                revision="Rev C",
                lot_number="LOT-2026-FQC-001",
                batch_number="BATCH-M44",
                serial_numbers_text="TBS-44001 through TBS-44500",
                certified_quantity=5000,
                inspection_lot=lot_1,
                applicable_specifications="ISO 13485:2016, ASTM F136 Ti-6Al-4V ELI, FDA 21 CFR Part 820",
                test_results_summary="Tensile yield: 860 MPa (spec >= 795 MPa). Dimensional: Cpk 1.84. Sterility: EtO SAL 10^-6 validated.",
                conformance_statement="We hereby certify that the items identified above were manufactured, inspected, and tested in accordance with the contract requirements, applicable drawings, and validated manufacturing processes.",
                authorized_signatory=admin_user,
                signatory_title="Director of Quality Assurance",
                signed_date=today - datetime.timedelta(days=2),
                digital_signature_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                notes="Original digital certificate transmitted electronically to customer regulatory portal.",
            )

            coc_2 = CertificateOfConformance.objects.create(
                tenant=tenant,
                title="Certificate of Conformance - Flight Actuator Housing",
                certificate_type="aerospace_as9100_as9102",
                status="under_review",
                customer=customer,
                customer_po_number="PO-AERO-77104",
                sales_order_number="SO-2026-9115",
                item_code="AERO-ACT-770",
                item_name="Electro-Hydraulic Flight Actuator Housing",
                revision="Rev F",
                lot_number="LOT-2026-FQC-002",
                batch_number="BATCH-ACT-77",
                serial_numbers_text="ACT-7701 through ACT-7780",
                certified_quantity=80,
                inspection_lot=lot_2,
                applicable_specifications="AS9100D, AMS 4928 Titanium Bar, MIL-STD-130N",
                test_results_summary="Hydrostatic pressure tested to 4500 PSI with zero leakage. Anodize thickness 0.0018 in.",
                conformance_statement="Goods conform in all material respects to engineering drawings and purchase order specifications, subject to approved customer concession DEV-2026-08.",
                authorized_signatory=verifier_user,
                signatory_title="Quality Engineering Manager",
                signed_date=None,
                notes="Pending customer MRB co-signature on concession deviation.",
            )

            # 3. Packaging & Label Verifications (QPKG)
            pkg_1 = PackagingLabelVerification.objects.create(
                tenant=tenant,
                title="UDI Barcode & Packaging Audit - Titanium Screws M44",
                status="verified",
                disposition="pass_released",
                item_code="MED-TBS-40",
                item_name="Titanium Polyaxial Bone Screw 4.0mm x 40mm",
                lot_number="LOT-2026-FQC-001",
                carton_count_inspected=25,
                label_part_number="LBL-MED-TBS40",
                label_artwork_revision="Rev 3",
                artwork_master=sop_doc,
                barcode_symbology="datamatrix_gs1_2d",
                scanned_barcode_data="(01)00850012345678(17)311231(10)LOT-2026-FQC-001(21)TBS-44001",
                iso_iec_print_grade="grade_a_4_0",
                label_content_accurate=True,
                regulatory_symbols_present=True,
                serialization_verified=True,
                carton_integrity_intact=True,
                tamper_evident_seal_intact=True,
                cushioning_dunnage_adequate=True,
                pallet_stacking_compliant=True,
                inspection_lot=lot_1,
                verifier=inspector_user,
                verified_date=today - datetime.timedelta(days=2),
                discrepancy_details="",
                notes="ISO/IEC 15415 grading performed using Cognex DataMan 8600 verifier. Grade 4.0 (A) across all 25 cartons.",
            )

            pkg_2 = PackagingLabelVerification.objects.create(
                tenant=tenant,
                title="Pallet Label & Integrity Inspection - Harness Batch 09B",
                status="failed",
                disposition="relabel_required",
                item_code="AUTO-HARN-09",
                item_name="Powertrain CAN Bus Shielded Sensor Wiring Harness",
                lot_number="LOT-2026-FQC-003",
                carton_count_inspected=12,
                label_part_number="LBL-AUTO-HARN09",
                label_artwork_revision="Rev 1",
                barcode_symbology="code_128_1d",
                scanned_barcode_data="AI-HARN-09B-1250",
                iso_iec_print_grade="grade_d_1_0",
                label_content_accurate=True,
                regulatory_symbols_present=False,
                serialization_verified=False,
                carton_integrity_intact=False,
                tamper_evident_seal_intact=False,
                cushioning_dunnage_adequate=True,
                pallet_stacking_compliant=False,
                inspection_lot=lot_3,
                verifier=inspector_user,
                verified_date=today,
                discrepancy_details="Thermal print ribbon low density causing Code 128 modulation failure (Grade D). Moisture indicator triggered on pallet wrap.",
                notes="Reprint all 12 carton labels on Zebra ZT411 with fresh 5095 resin ribbon. Pallet repack required.",
            )

            # 4. Quality Release Authorizations (QREL)
            rel_1 = QualityReleaseAuthorization.objects.create(
                tenant=tenant,
                title="Final Outgoing Release - Bone Screws Batch 44 to Central Hospital",
                status="authorized",
                release_disposition="released_full",
                customer=customer,
                destination_country="United States",
                destination_facility="Metro Health Regional Distribution Center, Dock 2",
                sales_order_number="SO-2026-9041",
                lot_number="LOT-2026-FQC-001",
                quantity_authorized=5000,
                inspection_lot=lot_1,
                certificate_of_conformance=coc_1,
                packaging_verification=pkg_1,
                is_on_hold=False,
                hold_reason="",
                final_inspection_passed=True,
                no_open_ncrs_or_capas=True,
                packaging_label_approved=True,
                coc_issued_and_signed=True,
                export_compliance_verified=True,
                certificate_of_origin_attached=True,
                shipping_container_security_seal="SEAL-US-991204",
                carrier_name="FedEx HealthCare Priority",
                tracking_reference="FX-774910284711",
                releasing_officer=admin_user,
                release_date=today - datetime.timedelta(days=2),
                concession_rationale="",
                notes="All QMS release gates cleared. Gate pass printed and affixed to lead shipping carton.",
            )

            rel_2 = QualityReleaseAuthorization.objects.create(
                tenant=tenant,
                title="Shipping Quality Hold - CAN Bus Harness Batch 09B",
                status="active_hold",
                release_disposition="quarantined_hold",
                customer=customer,
                destination_country="Germany",
                destination_facility="Munich Assembly Plant 4",
                sales_order_number="SO-2026-9280",
                lot_number="LOT-2026-FQC-003",
                quantity_authorized=1500,
                inspection_lot=lot_3,
                certificate_of_conformance=None,
                packaging_verification=pkg_2,
                is_on_hold=True,
                hold_reason="Pallet packaging failed moisture integrity audit and barcode grading D. Shipping blocked.",
                final_inspection_passed=False,
                no_open_ncrs_or_capas=False,
                packaging_label_approved=False,
                coc_issued_and_signed=False,
                export_compliance_verified=True,
                certificate_of_origin_attached=False,
                shipping_container_security_seal="",
                carrier_name="DHL Global Forwarding",
                tracking_reference="",
                releasing_officer=inspector_user,
                release_date=today,
                concession_rationale="Release blocked until relabeling and repack verification completed.",
                notes="Active quality hold placed in ERP. Warehouse dock staging notified.",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.9 Final Quality Control (FQC / OQC) seeded successfully."))

    def _seed_submodule_12_11(self, tenant):
        if AuditProgram.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.11 Audit Management data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.11 Audit Management...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        quality_lead = (
            User.objects.filter(tenant=tenant, username__icontains="quality").order_by("pk").first()
            or User.objects.filter(tenant=tenant, username__icontains="inspector").order_by("pk").first()
            or admin_user
        )
        external_party = (
            Party.objects.filter(tenant=tenant, roles__role="supplier").first()
            or Party.objects.filter(tenant=tenant).first()
        )
        org_unit = OrgUnit.objects.filter(tenant=tenant).first()
        sop_doc = ControlledDocument.objects.filter(tenant=tenant).first()
        linked_capa = CapaInvestigation.objects.filter(tenant=tenant).first()
        linked_ncr = NonConformanceReport.objects.filter(tenant=tenant).first()

        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            # 1. Audit Programs
            prog_enterprise = AuditProgram.objects.create(
                tenant=tenant,
                title="FY2026 Enterprise Quality & Regulatory Audit Program",
                program_year=today.year,
                program_type="integrated_enterprise",
                risk_basis="high_risk_semi_annual",
                scope_description="Global quality oversight covering ISO 13485:2016 design controls, FDA 21 CFR 820 / QMSR compliance, and critical supplier qualifications.",
                start_date=today.replace(month=1, day=1),
                end_date=today.replace(month=12, day=31),
                allocated_budget_hours=480,
                status="active",
                program_manager=admin_user,
                notes="Board-approved enterprise quality compliance program for fiscal year.",
            )

            prog_supplier = AuditProgram.objects.create(
                tenant=tenant,
                title="FY2026 Supplier & External Vendor Quality Program",
                program_year=today.year,
                program_type="supplier_external",
                risk_basis="medium_risk_biennial",
                scope_description="Tier 1 medical components, microelectronics, raw titanium blanks, and contract packaging vendor audit universe.",
                start_date=today.replace(month=1, day=1),
                end_date=today.replace(month=12, day=31),
                allocated_budget_hours=240,
                status="active",
                program_manager=quality_lead,
                notes="Risk-based audit frequency derived from supplier criticality score matrix.",
            )

            # 2. Quality Audits
            audit_internal = QualityAudit.objects.create(
                tenant=tenant,
                program=prog_enterprise,
                title="ISO 13485:2016 Design Controls & Risk Management Audit",
                audit_type="internal_system",
                audit_method="on_site",
                standard_framework="iso_13485_2016",
                target_org_unit=org_unit,
                external_entity=None,
                lead_auditor=quality_lead,
                auditee_lead=admin_user,
                audit_checklist_sop=sop_doc,
                planned_start_date=today - datetime.timedelta(days=45),
                planned_end_date=today - datetime.timedelta(days=42),
                actual_start_date=today - datetime.timedelta(days=45),
                actual_end_date=today - datetime.timedelta(days=42),
                scope_objectives="Verification of DHF traceability, ISO 14971 risk mitigations, and design transfer sign-offs across product engineering.",
                product_scope="CardioSense Pro Series IV",
                lot_number_sampled="LOT-2026-ENG-088",
                status="closed",
                outcome="minor_findings",
                executive_summary="Design control files were comprehensive and compliant with ISO 13485 §7.3. Isolated document revision date gaps identified in risk analysis tables.",
                report_published_date=today - datetime.timedelta(days=35),
                total_findings_count=2,
                critical_findings_count=0,
                major_findings_count=0,
                minor_findings_count=1,
                ofi_findings_count=1,
                notes="Audit closed following successful verification of corrective action evidence.",
            )

            audit_process = QualityAudit.objects.create(
                tenant=tenant,
                program=prog_enterprise,
                title="FDA 21 CFR 820 QMSR Cleanroom & Production Controls Audit",
                audit_type="internal_process",
                audit_method="hybrid",
                standard_framework="fda_21cfr820_qmsr",
                target_org_unit=org_unit,
                external_entity=None,
                lead_auditor=quality_lead,
                auditee_lead=admin_user,
                audit_checklist_sop=sop_doc,
                planned_start_date=today - datetime.timedelta(days=5),
                planned_end_date=today + datetime.timedelta(days=2),
                actual_start_date=today - datetime.timedelta(days=5),
                actual_end_date=None,
                scope_objectives="Process validation (IQ/OQ/PQ), environmental particulate monitoring logs, and DHR line clearance adherence.",
                product_scope="NeuroVascular Guidewire Assembly",
                lot_number_sampled="LOT-2026-FQC-001",
                status="in_progress",
                outcome="pending",
                executive_summary="Fieldwork ongoing across cleanroom production suites and packaging lines.",
                report_published_date=None,
                total_findings_count=1,
                critical_findings_count=0,
                major_findings_count=1,
                minor_findings_count=0,
                ofi_findings_count=0,
                notes="Cleanroom environmental particulate monitoring records sampled and evaluated.",
            )

            audit_regulatory = QualityAudit.objects.create(
                tenant=tenant,
                program=None,
                title="US FDA Routine cGMP & QSIT Bi-Annual Facility Inspection",
                audit_type="regulatory_fda",
                audit_method="on_site",
                standard_framework="fda_21cfr820_qmsr",
                target_org_unit=org_unit,
                external_entity=external_party,
                lead_auditor=quality_lead,
                auditee_lead=admin_user,
                audit_checklist_sop=sop_doc,
                planned_start_date=today - datetime.timedelta(days=2),
                planned_end_date=today + datetime.timedelta(days=3),
                actual_start_date=today - datetime.timedelta(days=2),
                actual_end_date=None,
                scope_objectives="FDA QSIT comprehensive inspection covering Management Controls, Design Controls, CAPA, and Production & Process Controls (P&PC).",
                product_scope="Implantable Titanium Spinal Cage",
                lot_number_sampled="LOT-2026-SP-901",
                status="in_progress",
                outcome="pending",
                executive_summary="Lead investigator Dr. A. Vance on site conducting daily interviews and sampling CAPA records.",
                report_published_date=None,
                total_findings_count=0,
                critical_findings_count=0,
                major_findings_count=0,
                minor_findings_count=0,
                ofi_findings_count=0,
                notes="War room activated; primary spokesperson escorting investigator through cleanroom facility.",
            )

            # 3. Audit Findings
            AuditFinding.objects.create(
                tenant=tenant,
                audit=audit_internal,
                finding_number_in_audit=1,
                title="Risk analysis document revision date disparity in DHF Table 4",
                severity="minor",
                standard_clause="ISO 13485:2016 §7.3.3 / ISO 14971:2019 §5.4",
                requirement_statement="Design risk management files shall maintain contemporaneous revision history aligned with engineering change orders.",
                condition_evidence="DHF-774 Rev C referenced Risk File RA-102 Rev B instead of active Rev C dated 2025-11-14.",
                audited_org_unit=org_unit,
                assignee=admin_user,
                response_due_date=today - datetime.timedelta(days=15),
                response_received_date=today - datetime.timedelta(days=18),
                containment_action="Administrative cross-reference matrix corrected immediately.",
                root_cause_summary="Document control link in electronic change notice template was manually typed instead of auto-populated.",
                corrective_action_plan="Updated PLM change workflow script to enforce automated document parent-child revision matching.",
                linked_capa=linked_capa,
                linked_ncr=linked_ncr,
                status="closed",
                closure_verified_by=quality_lead,
                closed_date=today - datetime.timedelta(days=10),
                closure_notes="Verified updated PLM workflow and revised DHF cross-reference index. Finding verified and closed.",
            )

            AuditFinding.objects.create(
                tenant=tenant,
                audit=audit_internal,
                finding_number_in_audit=2,
                title="Software automated testing traceability to risk index",
                severity="observation_ofi",
                standard_clause="IEC 62304:2006/AMD 1:2015 §5.2",
                requirement_statement="Software system tests should provide bi-directional traceability to hazard mitigations.",
                condition_evidence="Automated test suite reports pass/fail in CI/CD pipeline but does not directly map test case IDs to hazard control IDs in the hazard traceability matrix.",
                audited_org_unit=org_unit,
                assignee=admin_user,
                response_due_date=today + datetime.timedelta(days=30),
                response_received_date=None,
                containment_action="N/A - observation for improvement.",
                root_cause_summary="",
                corrective_action_plan="Integrate Pytest hazard tag decorators into continuous integration dashboard.",
                linked_capa=None,
                linked_ncr=None,
                status="response_submitted",
                closure_verified_by=None,
                closed_date=None,
                closure_notes="",
            )

            AuditFinding.objects.create(
                tenant=tenant,
                audit=audit_process,
                finding_number_in_audit=1,
                title="Differential pressure gauge out of calibration in Cleanroom Suite B",
                severity="major",
                standard_clause="21 CFR 820.72 / ISO 13485:2016 §6.4",
                requirement_statement="Environmental control and monitoring equipment shall be calibrated at specified intervals.",
                condition_evidence="Magnehelic gauge DP-04 calibration expired on 2026-01-15 while cleanroom suite continued active packaging operations.",
                audited_org_unit=org_unit,
                assignee=admin_user,
                response_due_date=today + datetime.timedelta(days=14),
                response_received_date=None,
                containment_action="Gage immediately replaced with calibrated spare DP-12 and secondary calibration verified.",
                root_cause_summary="Work order assignment dropped during CMMS database maintenance migration.",
                corrective_action_plan="Initiating CAPA for calibration scheduling redundancy and monthly physical sticker sweeps.",
                linked_capa=linked_capa,
                linked_ncr=linked_ncr,
                status="capa_in_progress",
                closure_verified_by=None,
                closed_date=None,
                closure_notes="",
            )

            # 4. Regulatory Inspection Host Records (War Room)
            RegulatoryInspectionHost.objects.create(
                tenant=tenant,
                audit=audit_regulatory,
                inspection_title="US FDA cGMP / QSIT Medical Device Surveillance Inspection",
                agency_or_body="fda_cdrh",
                agency_name="US Food & Drug Administration - CDRH / ORA",
                lead_inspector_name="Consumer Safety Officer Arthur Vance, Ph.D.",
                inspector_credentials="FDA Investigator Badge #60144 / Minneapolis District Office",
                inspection_purpose="routine_surveillance",
                announcement_status="announced",
                scheduled_start_date=today - datetime.timedelta(days=2),
                scheduled_end_date=today + datetime.timedelta(days=3),
                actual_start_date=today - datetime.timedelta(days=2),
                actual_end_date=None,
                front_room_lead=admin_user,
                back_room_lead=quality_lead,
                scribe_user=quality_lead,
                war_room_location="Executive Conference Room Alpha (Front Room) & Quality Training Lab B (Back Room)",
                status="active_inspection",
                requests_logged_count=18,
                requests_fulfilled_count=16,
                form_483_issued=False,
                observations_count=0,
                formal_outcome="pending",
                daily_summary_notes="Day 1: Management Review minutes and Org chart reviewed with zero questions. Day 2: Sampled 5 CAPA records from 2025. Back room staging responded within average 12 minutes.",
                closeout_memo="",
            )

            RegulatoryInspectionHost.objects.create(
                tenant=tenant,
                audit=None,
                inspection_title="TÜV SÜD ISO 13485:2016 & EU MDR Annex IX Recertification",
                agency_or_body="iso_notified_body",
                agency_name="TÜV SÜD Product Service GmbH (Notified Body 0123)",
                lead_inspector_name="Lead Auditor Klaus Becker, Dipl.-Ing.",
                inspector_credentials="TÜV SÜD Auditor Registration #TS-99214",
                inspection_purpose="recertification_audit",
                announcement_status="announced",
                scheduled_start_date=today - datetime.timedelta(days=60),
                scheduled_end_date=today - datetime.timedelta(days=57),
                actual_start_date=today - datetime.timedelta(days=60),
                actual_end_date=today - datetime.timedelta(days=57),
                front_room_lead=admin_user,
                back_room_lead=quality_lead,
                scribe_user=quality_lead,
                war_room_location="Main Boardroom & Secure Virtual Room",
                status="inspection_closed",
                requests_logged_count=35,
                requests_fulfilled_count=35,
                form_483_issued=False,
                observations_count=1,
                formal_outcome="certified_unconditional",
                daily_summary_notes="All technical documentation and PMS data reviewed. Unconditional certificate renewal recommended.",
                closeout_memo="Closing meeting held 2026-01-20. Formal certificate reissue received.",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.11 Audit Management seeded successfully."))

    def _seed_submodule_12_12(self, tenant):
        """Seed demo data for Sub-module 12.12: Training & Competency Management."""
        if CompetencyMatrix.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.12 Training & Competency Management data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.12 Training & Competency Management...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
            or User.objects.filter(tenant=tenant).first()
        )
        quality_lead = (
            User.objects.filter(tenant=tenant, username__icontains="quality").first()
            or User.objects.filter(tenant=tenant, is_staff=True).first()
            or admin_user
        )
        operator_user = (
            User.objects.filter(tenant=tenant, username__icontains="operator").first()
            or User.objects.filter(tenant=tenant).exclude(pk=admin_user.pk).first()
            or admin_user
        )

        qa_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="Quality").first()
        mfg_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="Manufacturing").first()

        doc1 = ControlledDocument.objects.filter(tenant=tenant).first()
        doc2 = ControlledDocument.objects.filter(tenant=tenant).last()
        dco = DocumentChangeOrder.objects.filter(tenant=tenant).first()
        capa = CapaAction.objects.filter(tenant=tenant).first()

        today = timezone.now().date()
        now = timezone.now()

        with transaction.atomic():
            # 1. Competency Matrices
            m1 = CompetencyMatrix.objects.create(
                tenant=tenant,
                title="Aseptic Fill Suite Senior Operator Qualification Matrix",
                role_title="Aseptic Cleanroom Fill Line Senior Operator",
                qualification_tier="specialist",
                department=mfg_dept,
                criticality="critical_gxp",
                revision="1.0",
                status="approved",
                minimum_passing_score=85,
                validity_period_months=12,
                prerequisite_experience_months=24,
                description="Comprehensive qualification curriculum covering cleanroom gowning, environmental monitoring, sterility assurance, and automated vial filler operation.",
                approved_by=quality_lead,
                approval_date=today - datetime.timedelta(days=90),
                notes="Mandatory for all Class A/B cleanroom operators under EU GMP Annex 1.",
            )

            m2 = CompetencyMatrix.objects.create(
                tenant=tenant,
                title="Quality Assurance Documentation Specialist Matrix",
                role_title="QA Document Control Specialist",
                qualification_tier="independent",
                department=qa_dept,
                criticality="high",
                revision="2.0",
                status="active",
                minimum_passing_score=80,
                validity_period_months=12,
                prerequisite_experience_months=6,
                description="Covers Good Documentation Practices (GDP), 21 CFR Part 11 electronic records, change order workflows, and batch record archiving.",
                approved_by=admin_user,
                approval_date=today - datetime.timedelta(days=120),
                notes="Required for all document coordinators and release scribes.",
            )

            m3 = CompetencyMatrix.objects.create(
                tenant=tenant,
                title="Manufacturing Equipment Maintenance & Calibration Matrix",
                role_title="Senior Calibration Technician",
                qualification_tier="trainer",
                department=mfg_dept,
                criticality="medium",
                revision="1.1",
                status="active",
                minimum_passing_score=80,
                validity_period_months=24,
                prerequisite_experience_months=18,
                description="Covers preventive maintenance, autoclave sterilization cycles, gage calibration protocols, and lockout-tagout (LOTO) procedures.",
                approved_by=quality_lead,
                approval_date=today - datetime.timedelta(days=60),
                notes="Technicians certified under this matrix can evaluate and sign off junior apprentices.",
            )

            # 2. Quality Training Courses
            c1 = QualityTrainingCourse.objects.create(
                tenant=tenant,
                title="SOP-0042 Aseptic Gowning and Cleanroom Entry Protocol",
                competency_matrix=m1,
                course_code="TRN-SOP-042",
                category="gxp_compliance",
                delivery_method="on_the_job",
                assessment_method="both_exam_and_ojt",
                status="active",
                controlled_document=doc1,
                document_revision="Rev C",
                retrain_on_revision=True,
                duration_hours=Decimal("3.50"),
                passing_score=85,
                ojt_checklist_criteria="1. Hand hygiene and sterile gowning under 10 minutes without touching outer surfaces.\n2. Contact plate fingertip touch-test yielding 0 CFU.\n3. Demonstration of unidirectional laminar airflow discipline.",
                syllabus_summary="Principles of aseptic processing, microbiological contamination vectors, cleanroom classification standards (ISO 14644-1), gowning procedures, and exit protocols.",
                instructor=quality_lead,
                notes="Classroom review followed by 3 supervised gowning mock sessions.",
            )

            c2 = QualityTrainingCourse.objects.create(
                tenant=tenant,
                title="SOP-0015 Good Documentation Practices (GDP) & 21 CFR Part 11",
                competency_matrix=m2,
                course_code="TRN-GDP-015",
                category="gxp_compliance",
                delivery_method="elearning",
                assessment_method="written_exam",
                status="active",
                controlled_document=doc2,
                document_revision="Rev B",
                retrain_on_revision=True,
                duration_hours=Decimal("2.00"),
                passing_score=80,
                syllabus_summary="ALCOA+ data integrity principles, concurrent recording rules, correction of error protocols, electronic signature non-repudiation, and audit trail review responsibilities.",
                instructor=admin_user,
                notes="Annual mandatory refresher for all site employees with QMS access.",
            )

            c3 = QualityTrainingCourse.objects.create(
                tenant=tenant,
                title="SOP-0088 Root Cause Analysis & 5-Why Investigation Methodology",
                competency_matrix=m2,
                course_code="TRN-RCA-088",
                category="quality_tools",
                delivery_method="classroom_lecture",
                assessment_method="written_exam",
                status="active",
                duration_hours=Decimal("4.00"),
                passing_score=80,
                syllabus_summary="Problem statement formulation, Fishbone (Ishikawa) diagramming, 5-Why iterative drilldown, barrier analysis, and CAPA action plan effectiveness verification.",
                instructor=quality_lead,
                notes="Case study driven workshop with cross-functional deviation scenarios.",
            )

            c4 = QualityTrainingCourse.objects.create(
                tenant=tenant,
                title="SOP-0104 Autoclave Sterilizer Operation & Safety Procedures",
                competency_matrix=m3,
                course_code="TRN-EQP-104",
                category="equipment_operation",
                delivery_method="on_the_job",
                assessment_method="practical_ojt",
                status="active",
                duration_hours=Decimal("3.00"),
                passing_score=80,
                ojt_checklist_criteria="1. Verify steam pressure and temperature chamber sensors prior to run.\n2. Load configuration inspection per validated loading pattern.\n3. Cycle biological indicator placement and retrieval protocol.",
                syllabus_summary="Steam sterilization physics, cycle parameters (121°C / 15 psi), Bowie-Dick testing, emergency shutdown procedures, and chamber maintenance.",
                instructor=quality_lead,
                notes="Practical hands-on qualification in central sterile supply wing.",
            )

            # 3. Training Enrollments
            e1 = TrainingEnrollment.objects.create(
                tenant=tenant,
                course=c1,
                trainee=operator_user,
                assignment_reason="annual_refresher",
                assigned_date=today - datetime.timedelta(days=45),
                due_date=today - datetime.timedelta(days=15),
                status="verified",
                completion_date=today - datetime.timedelta(days=20),
                score=Decimal("94.00"),
                is_passed=True,
                self_certified=True,
                self_certified_at=timezone.now() - datetime.timedelta(days=20),
                practical_rating="meets_standard",
                practical_verified_by=quality_lead,
                practical_verified_at=timezone.now() - datetime.timedelta(days=18),
                practical_evaluation_notes="Operator demonstrated flawless gowning technique and cleanroom laminar air behavior. All fingertip agar plates negative.",
                notes="Annual recertification completed on schedule.",
            )

            e2 = TrainingEnrollment.objects.create(
                tenant=tenant,
                course=c1,
                trainee=admin_user,
                assignment_reason="role_transfer",
                assigned_date=today - datetime.timedelta(days=10),
                due_date=today + datetime.timedelta(days=20),
                status="completed",
                completion_date=today - datetime.timedelta(days=2),
                score=Decimal("90.00"),
                is_passed=True,
                self_certified=True,
                self_certified_at=timezone.now() - datetime.timedelta(days=2),
                notes="Written exam passed. Practical demonstration scheduled with Lead Auditor.",
            )

            e3 = TrainingEnrollment.objects.create(
                tenant=tenant,
                course=c2,
                trainee=operator_user,
                assignment_reason="onboarding_new_hire",
                assigned_date=today - datetime.timedelta(days=60),
                due_date=today - datetime.timedelta(days=30),
                status="verified",
                completion_date=today - datetime.timedelta(days=35),
                score=Decimal("98.00"),
                is_passed=True,
                self_certified=True,
                self_certified_at=timezone.now() - datetime.timedelta(days=35),
                notes="GDP foundational module completed with exemplary score.",
            )

            e4 = TrainingEnrollment.objects.create(
                tenant=tenant,
                course=c2,
                trainee=quality_lead,
                assignment_reason="annual_refresher",
                assigned_date=today - datetime.timedelta(days=5),
                due_date=today + datetime.timedelta(days=25),
                status="assigned",
                notes="Annual corporate data integrity recertification cycle.",
            )

            e5 = TrainingEnrollment.objects.create(
                tenant=tenant,
                course=c3,
                trainee=operator_user,
                assignment_reason="capa_corrective_action",
                capa_action=capa,
                assigned_date=today - datetime.timedelta(days=25),
                due_date=today - datetime.timedelta(days=5),
                status="assigned",
                notes="Assigned per CAPA root cause investigation action item. Currently past due.",
            )

            e6 = TrainingEnrollment.objects.create(
                tenant=tenant,
                course=c4,
                trainee=admin_user,
                assignment_reason="manager_assignment",
                assigned_date=today - datetime.timedelta(days=30),
                due_date=today - datetime.timedelta(days=10),
                status="waived",
                waiver_reason="Grandfathered certified master mechanical engineer with documented ASME autoclave calibration history exceeding 10 years.",
                waived_by=quality_lead,
                waived_at=timezone.now() - datetime.timedelta(days=15),
                notes="Formal waiver approved by Quality Assurance Director.",
            )

            # 4. Competency Certifications
            CompetencyCertification.objects.create(
                tenant=tenant,
                enrollment=e1,
                trainee=operator_user,
                course=c1,
                competency_matrix=m1,
                qualification_title="Certified Aseptic Fill Suite Level 2 Independent Operator",
                qualification_level="level_2_qualified",
                issue_date=today - datetime.timedelta(days=18),
                valid_until=today + datetime.timedelta(days=347),
                renewal_interval_months=12,
                status="active",
                authorized_work_centers="Cleanroom Suite B (Fill-Finish Vial Line #1 and Isolator Cabinet Alpha)",
                certified_by=quality_lead,
                notes="Authorized for unattended aseptic production fills and environmental monitoring touch-sampling.",
            )

            CompetencyCertification.objects.create(
                tenant=tenant,
                enrollment=e3,
                trainee=operator_user,
                course=c2,
                competency_matrix=m2,
                qualification_title="Certified GDP & Electronic Records Operator",
                qualification_level="level_2_qualified",
                issue_date=today - datetime.timedelta(days=345),
                valid_until=today + datetime.timedelta(days=20),
                renewal_interval_months=12,
                status="active",
                authorized_work_centers="All Manufacturing and Packaging Lines",
                certified_by=admin_user,
                notes="Expiring soon within 20 days. Trainee queued for annual refresher course.",
            )

            CompetencyCertification.objects.create(
                tenant=tenant,
                trainee=quality_lead,
                course=c4,
                competency_matrix=m3,
                qualification_title="Certified Sterilization Master Trainer & Assessor",
                qualification_level="level_4_trainer_assessor",
                issue_date=today - datetime.timedelta(days=100),
                valid_until=today + datetime.timedelta(days=630),
                renewal_interval_months=24,
                status="active",
                authorized_work_centers="Central Sterilization Wing & Autoclaves #1 through #4",
                certified_by=admin_user,
                notes="Qualified to conduct and certify junior technicians on practical OJT checklists.",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.12 Training & Competency Management seeded successfully."))

    def _seed_submodule_12_13(self, tenant):
        """Seed demo data for Sub-module 12.13: Customer Complaint Handling."""
        if CustomerComplaint.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.13 Customer Complaint Handling data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.13 Customer Complaint Handling...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
            or User.objects.filter(tenant=tenant).first()
        )
        quality_lead = (
            User.objects.filter(tenant=tenant, username__icontains="quality").first()
            or User.objects.filter(tenant=tenant, is_staff=True).first()
            or admin_user
        )
        operator_user = (
            User.objects.filter(tenant=tenant, username__icontains="operator").first()
            or User.objects.filter(tenant=tenant).exclude(pk=admin_user.pk).first()
            or admin_user
        )

        customer_party = Party.objects.filter(tenant=tenant).first()
        now = timezone.now()
        today = now.date()

        with transaction.atomic():

            cmp1 = CustomerComplaint.objects.create(
                tenant=tenant,
                title="Infusion Pump Display Freeze During Chemotherapy Delivery",
                intake_channel="phone",
                customer=customer_party,
                complainant_name="Dr. Eleanor Vance",
                complainant_organization="St. Jude Oncology Center",
                complainant_email="e.vance@stjude-oncology.org",
                complainant_phone="+1-555-839-2041",
                item_code="MED-PUMP-4000",
                item_name="Infusion Pro Plus 4000",
                lot_number="LOT-2026-X1",
                serial_number="SN-40991",
                udi_di_number="(01)00849204018291(11)260115(21)40991",
                date_received=today - datetime.timedelta(days=12),
                date_of_occurrence=today - datetime.timedelta(days=13),
                problem_description="Infusion pump LCD display became completely blank and unresponsive during active cytarabine infusion administration at bedside. Clinician was required to manually clamp the line and transition patient to secondary pump.",
                patient_involved=True,
                adverse_event_alleged=True,
                severity="critical_safety",
                status="under_investigation",
                validity="valid_complaint",
                reportability="reportable_event",
                complaint_category="Display / UI Hardware Malfunction",
                sample_return_status="sample_received",
                sample_tracking_number="FEDEX-774920194821",
                sample_received_date=today - datetime.timedelta(days=9),
                triage_notes="Direct patient impact during hazardous oncology drug infusion. Elevated immediately to Critical severity. Statutory FDA 30-day MDR clock started on date received. Full physical diagnostic requested.",
                triaged_by=quality_lead,
                triaged_at=now - datetime.timedelta(days=11),
                investigation_required=True,
                assigned_to=quality_lead,
            )

            cmp2 = CustomerComplaint.objects.create(
                tenant=tenant,
                title="Blood Glucose Monitor Inconsistent Strip Calibration Codes",
                intake_channel="email",
                customer=customer_party,
                complainant_name="Marcus Aurelius",
                complainant_organization="Metro Health Outpatient Clinic",
                complainant_email="m.aurelius@metrohealth.net",
                complainant_phone="+1-555-392-1940",
                item_code="GLUCO-STRIP-100",
                item_name="AccuCheck Reagent Test Strips (100pk)",
                lot_number="LOT-2026-B8",
                udi_di_number="(01)00849204019402(11)260201",
                date_received=today - datetime.timedelta(days=25),
                date_of_occurrence=today - datetime.timedelta(days=26),
                problem_description="Clinic reported error code 'E-03' on multiple test strip vials when attempting patient morning fasting blood sugar screenings.",
                patient_involved=False,
                adverse_event_alleged=False,
                severity="major_malfunction",
                status="resolved",
                validity="valid_complaint",
                reportability="non_reportable",
                non_reportable_justification="Technical investigation confirmed vial packaging desiccant was unsealed at clinic storage room with 85% relative humidity. Product retained samples passed all lot release specs. No patient misdiagnosis or adverse consequence.",
                complaint_category="Calibration & Reagent Drift",
                sample_return_status="not_requested",
                triage_notes="No patient adverse outcome. QA review confirms non-reportable per 21 CFR 820.198.",
                triaged_by=admin_user,
                triaged_at=now - datetime.timedelta(days=24),
                investigation_required=True,
                resolution_summary="Customer contacted with educational memo regarding clinical storage guidelines (storage under 30C and <50% humidity). Replacement vials dispatched under customer goodwill policy.",
                customer_letter_sent=True,
                customer_letter_date=today - datetime.timedelta(days=5),
                assigned_to=admin_user,
            )

            cmp3 = CustomerComplaint.objects.create(
                tenant=tenant,
                title="Crushed Outer Shipper Cartons During Transit",
                intake_channel="web_portal",
                customer=customer_party,
                complainant_name="Jennifer Lopez",
                complainant_organization="Central Regional Medical Supply",
                complainant_email="jlopez@crmedical.com",
                item_code="KIT-DIAG-01",
                item_name="Rapid Antigen Diagnostic Test 25pk",
                lot_number="LOT-2026-T4",
                date_received=today - datetime.timedelta(days=45),
                date_of_occurrence=today - datetime.timedelta(days=46),
                problem_description="Consignee reported 4 of 20 corrugated outer master shippers arrived with crushed corner cartons. Inner foil pouches were inspected and intact.",
                patient_involved=False,
                adverse_event_alleged=False,
                severity="minor_cosmetic",
                status="closed",
                validity="valid_complaint",
                reportability="exempt",
                complaint_category="Packaging & Transit Damage",
                sample_return_status="not_requested",
                investigation_required=False,
                no_investigation_rationale="Outer cosmetic transit damage only. Inner sterile barrier integrity 100% verified by receiving clinic inspection. Carrier freight claim initiated.",
                resolution_summary="Credit memo issued for damaged outer cartons. Carrier feedback logged.",
                customer_letter_sent=True,
                customer_letter_date=today - datetime.timedelta(days=40),
                closed_by=admin_user,
                closed_at=now - datetime.timedelta(days=40),
                assigned_to=admin_user,
            )

            cmp4 = CustomerComplaint.objects.create(
                tenant=tenant,
                title="Customer Pricing Tier and Invoice Credit Dispute",
                intake_channel="sales_rep",
                customer=customer_party,
                complainant_name="Robert Smith",
                complainant_organization="Apex Diagnostics",
                item_code="MED-PUMP-4000",
                item_name="Infusion Pro Plus 4000",
                date_received=today - datetime.timedelta(days=5),
                problem_description="Customer contacted QA hotline alleging product overcharge relative to regional group purchasing contract.",
                patient_involved=False,
                adverse_event_alleged=False,
                severity="service_inconvenience",
                status="closed",
                validity="commercial_inquiry",
                reportability="exempt",
                investigation_required=False,
                no_investigation_rationale="Inquiry is strictly commercial / contract pricing dispute. Transferred to Commercial Operations and Sales Finance.",
                resolution_summary="Transferred to regional sales director. Closed in QMS.",
                closed_by=admin_user,
                closed_at=now - datetime.timedelta(days=4),
                assigned_to=admin_user,
            )

            # Investigations
            inv1 = ComplaintInvestigation.objects.create(
                tenant=tenant,
                complaint=cmp1,
                lead_investigator=quality_lead,
                target_completion_date=today + datetime.timedelta(days=10),
                status="in_progress",
                dhr_reviewed=True,
                dhr_lot_number="LOT-2026-X1",
                dhr_quantity_produced=500,
                dhr_anomalies_identified=False,
                dhr_review_summary="DHR for LOT-2026-X1 reviewed: All in-process assembly records, torque verifications, and burn-in tests met specification with zero non-conformances logged during manufacturing.",
                physical_sample_examined=True,
                analytical_method="electrical_functional",
                sample_testing_findings="Sample SN-40991 received in lab. High-resolution microscope and thermal imaging revealed an intermittent cold solder joint at pin 14 of display ribbon connector J4. Display freeze was replicated when subjected to 1.2G vibration.",
                failure_reproduced=True,
                hhe_required=True,
                health_hazard_evaluation="Medical assessment: Undetected infusion display freeze creates potential for infusion over-delivery or delay in therapy for critical oncology medications. Clinical risk determined as moderate-to-severe.",
                risk_exceeds_threshold=True,
                root_cause_category="component_defect",
                root_cause_narrative="5 Whys: Display froze because ribbon cable pin 14 disconnected intermittently -> cold solder joint formed during surface mount assembly -> PCB reflow profile thermal soak was 4C below supplier recommendation on manufacturing line #2.",
                capa_required=True,
                investigation_conclusion="Investigation confirmed hardware defect in surface-mount display connector. SMT reflow profile requires revision. Escalated to CAPA and potential field action.",
            )

            # Regulatory Reports
            rpt1 = RegulatoryReport.objects.create(
                tenant=tenant,
                complaint=cmp1,
                agency="fda_cdrh",
                report_type="initial_report",
                adverse_event_class="serious_injury",
                timeline_category="30_day_standard_mdr",
                statutory_due_date=today + datetime.timedelta(days=18),
                submission_status="submitted",
                submission_format="fda_emdr_xml",
                submission_date=today - datetime.timedelta(days=2),
                agency_report_identifier="MDR-2026-00812",
                agency_acknowledgement_number="FDA-ESG-ACK-8839201",
                agency_acknowledgement_date=today - datetime.timedelta(days=1),
                event_summary="Infusion pump display froze during oncology chemotherapy delivery. Device stopped responding to keypad input. Patient treatment delayed by 35 minutes while backup pump was deployed. No permanent injury sustained.",
                device_operator="Healthcare Professional (Oncology RN)",
                patient_remedial_action="Patient vitals monitored continuously; therapy resumed on secondary pump with no adverse clinical outcome.",
                prepared_by=quality_lead,
                reviewed_by=admin_user,
                notes="Initial 30-day MDR submitted via FDA eSubmitter AS2 gateway.",
            )

            rpt2 = RegulatoryReport.objects.create(
                tenant=tenant,
                complaint=cmp1,
                agency="eu_competent_auth",
                report_type="initial_report",
                adverse_event_class="malfunction_recurrent",
                timeline_category="15_day_serious_incident",
                statutory_due_date=today + datetime.timedelta(days=3),
                submission_status="under_internal_review",
                submission_format="eu_mir_xml",
                event_summary="Manufacturer Incident Report (MIR) drafted for EU Competent Authority notification under EU MDR 2017/745 Article 87.",
                device_operator="Healthcare Professional",
                prepared_by=quality_lead,
                notes="Statutory clock: 15-day EU MIR deadline expires in 3 days. High priority.",
            )

            # Field Action / Recall
            fa1 = FieldAction.objects.create(
                tenant=tenant,
                title="Class II Recall: Infusion Pro Plus 4000 Display PCB Solder Conformance",
                action_type="recall_removal",
                recall_class="class_ii_moderate",
                initiating_complaint=cmp1,
                coordinator=quality_lead,
                initiation_date=today - datetime.timedelta(days=8),
                status="quarantine_in_progress",
                affected_product_code="MED-PUMP-4000",
                affected_product_name="Infusion Pro Plus 4000",
                affected_lot_numbers="LOT-2026-X1, LOT-2026-X2",
                distribution_start_date=today - datetime.timedelta(days=180),
                distribution_end_date=today - datetime.timedelta(days=30),
                reason_for_action="Potential for display ribbon connector cold solder joint leading to display blanking during active clinical infusion.",
                hhe_summary="Clinical Health Hazard Evaluation concluded risk of temporary, reversible delay in therapy. No permanent health consequences expected when clinical staff follows alarm protocol.",
                total_units_distributed=500,
                consignees_targeted=45,
                consignees_notified=45,
                consignees_responded=38,
                units_quarantined_field=120,
                units_recovered_destroyed=185,
                regulatory_agency_notified="FDA CDRH Recall Operations",
                regulatory_recall_number="Z-1049-2026",
                agency_notification_date=today - datetime.timedelta(days=7),
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.13 Customer Complaint Handling seeded successfully."))

    def _seed_submodule_12_14(self, tenant):
        """Seed demo data for Sub-module 12.14: Management Review & Quality Planning."""
        if QualityObjective.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.14 Management Review data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.14 Management Review & Quality Planning...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
            or User.objects.filter(tenant=tenant).first()
        )
        quality_lead = (
            User.objects.filter(tenant=tenant, username__icontains="quality").first()
            or User.objects.filter(tenant=tenant, is_staff=True).first()
            or admin_user
        )
        executive_sponsor = admin_user

        org_unit = OrgUnit.objects.filter(tenant=tenant).first()
        today = timezone.now().date()
        year = today.year

        with transaction.atomic():
            # 1. Quality Objectives
            obj1 = QualityObjective.objects.create(
                tenant=tenant,
                title="Maintain First Pass Inspection Yield >= 98.5%",
                description="Target overall finished goods operational yield across all cleanroom assembly lines to prevent costly rework and batch deviations per ISO 9001:2015 Clause 6.2.",
                category="product_quality",
                period_year=year,
                cadence="annual",
                metric_unit="%",
                baseline_value=Decimal("96.200"),
                target_value=Decimal("98.500"),
                current_value=Decimal("98.700"),
                target_direction="higher_better",
                status="achieved",
                rag_status="green",
                owner=quality_lead,
                org_unit=org_unit,
                target_date=datetime.date(year, 12, 31),
                last_evaluated_date=today,
                action_plan_summary="Standardized IPC-A-610 Class 3 soldering criteria, continuous operator retraining, and automated optical inspection calibration.",
            )

            obj2 = QualityObjective.objects.create(
                tenant=tenant,
                title="Reduce Manufacturing Scrap & Rework Rate <= 1.20%",
                description="Lower scrap generated from defective injection molding tool wear and dimensional drift in production cells per ISO 13485:2016 Clause 5.4.1.",
                category="process_performance",
                period_year=year,
                cadence="quarterly",
                metric_unit="%",
                baseline_value=Decimal("2.400"),
                target_value=Decimal("1.200"),
                current_value=Decimal("1.350"),
                target_direction="lower_better",
                status="at_risk",
                rag_status="amber",
                owner=admin_user,
                org_unit=org_unit,
                target_date=datetime.date(year, 9, 30),
                last_evaluated_date=today - datetime.timedelta(days=15),
                action_plan_summary="Implemented real-time cavity pressure transducer telemetry on Molding Press 4 and enhanced preventive tool maintenance cycles.",
            )

            obj3 = QualityObjective.objects.create(
                tenant=tenant,
                title="Timely Resolution of Audit Findings <= 30 Days >= 95%",
                description="Ensure all internal and supplier audit non-conformances have root cause analysis and action plans completed within the statutory 30-day window.",
                category="compliance_regulatory",
                period_year=year,
                cadence="quarterly",
                metric_unit="%",
                baseline_value=Decimal("88.000"),
                target_value=Decimal("95.000"),
                current_value=Decimal("96.500"),
                target_direction="higher_better",
                status="achieved",
                rag_status="green",
                owner=quality_lead,
                org_unit=org_unit,
                target_date=datetime.date(year, 12, 31),
                last_evaluated_date=today - datetime.timedelta(days=5),
                action_plan_summary="Automated SLA notification workflow dispatching reminder alerts at day 15 and day 25.",
            )

            obj4 = QualityObjective.objects.create(
                tenant=tenant,
                title="Customer Allegation & Complaint Rate <= 0.15 PPM",
                description="Reduce post-market field complaint frequency related to packaging seal integrity and labeling clarity per FDA 21 CFR 820.198 and QMSR.",
                category="customer_satisfaction",
                period_year=year,
                cadence="monthly",
                metric_unit="PPM",
                baseline_value=Decimal("0.350"),
                target_value=Decimal("0.150"),
                current_value=Decimal("0.220"),
                target_direction="lower_better",
                status="behind",
                rag_status="red",
                owner=quality_lead,
                org_unit=org_unit,
                target_date=datetime.date(year, 12, 31),
                last_evaluated_date=today - datetime.timedelta(days=2),
                action_plan_summary="Tyvek heat sealer continuous thermal validation and 100% burst test sampling per ASTM F1140.",
            )

            # 2. Management Reviews
            rev_approved = ManagementReview.objects.create(
                tenant=tenant,
                title="Q3 2026 Executive Management Review",
                cadence="quarterly",
                period_start=today - datetime.timedelta(days=180),
                period_end=today - datetime.timedelta(days=90),
                scheduled_date=today - datetime.timedelta(days=85),
                actual_meeting_date=today - datetime.timedelta(days=85),
                location="Executive Conference Room & Virtual Teams Bridge",
                executive_sponsor=executive_sponsor,
                lead_facilitator=quality_lead,
                org_unit=org_unit,
                attendees_roster="Executive Management Sponsor: John Davis (VP Operations)\nLead Quality Facilitator: Sarah Jenkins (Quality Director)\nManufacturing Manager: Robert Chen\nRegulatory Affairs Director: Elena Rostova\nDesign Engineering Lead: Marcus Vance",
                quorum_met=True,
                status="approved",
                qms_suitability_conclusion="suitable_effective",
                executive_summary="The Quality Management System has been thoroughly evaluated against ISO 13485:2016, ISO 9001:2015, and FDA QMSR. Operational yields have exceeded target thresholds (98.7% FPY). Internal audit program is fully on schedule with zero critical findings. Corrective actions show sustained effectiveness.",
                minutes_discussion="1. Internal Audit Results: Reviewed 8 audits; 12 minor findings, all closed on schedule.\n2. Customer Complaints: Volume down 18% YoY. No statutory adverse events reported in Q3.\n3. CAPA Status: 4 open investigations progressing within SLA.\n4. Process Performance: Line 2 packaging seal drift detected and contained under NCR-2026-004.\n5. Supplier Performance: Top 10 critical component suppliers average 98.2 score.",
                resource_decisions="Authorized $45,000 capital expenditure for automated vision inspection system on SMT Line 2. Approved headcount for one additional validation specialist in Q4.",
                approved_by=executive_sponsor,
                approved_at=timezone.now() - datetime.timedelta(days=85),
            )

            rev_scheduled = ManagementReview.objects.create(
                tenant=tenant,
                title="Q4 2026 Executive Management Review",
                cadence="quarterly",
                period_start=today - datetime.timedelta(days=90),
                period_end=today,
                scheduled_date=today + datetime.timedelta(days=14),
                location="Boardroom Alpha",
                executive_sponsor=executive_sponsor,
                lead_facilitator=quality_lead,
                org_unit=org_unit,
                attendees_roster="Executive Sponsor, Quality Director, Operations VP, Regulatory Manager, R&D Director",
                quorum_met=True,
                status="scheduled",
                qms_suitability_conclusion="pending",
                executive_summary="",
                minutes_discussion="",
                resource_decisions="",
            )

            # Sibling quality records to link (if available)
            linked_audit = QualityAudit.objects.filter(tenant=tenant).first()
            linked_capa = CapaInvestigation.objects.filter(tenant=tenant).first()
            linked_complaint = CustomerComplaint.objects.filter(tenant=tenant).first()
            linked_ncr = NonConformanceReport.objects.filter(tenant=tenant).first()

            # 3. Review Inputs for rev_approved
            inp1 = ManagementReviewInput.objects.create(
                tenant=tenant,
                management_review=rev_approved,
                agenda_order=1,
                title="Q3 Internal & Supplier Quality Audit Findings Rollup",
                category="audit_results",
                presenter=quality_lead,
                summary_findings="Conducted 6 internal QMS system audits and 2 critical tier-1 supplier on-site audits. 14 minor findings logged, zero major non-conformances. Supplier AVL compliance stands at 97.4%.",
                metrics_data="Total Audits: 8 | Minor Findings: 14 | Major Findings: 0 | Closed on Time: 100%",
                status="accepted",
                linked_audit=linked_audit,
                attachments_summary="Presentation Deck Slides 4-9 & Audit Summary Pack",
            )

            inp2 = ManagementReviewInput.objects.create(
                tenant=tenant,
                management_review=rev_approved,
                agenda_order=2,
                title="Q3 Post-Market Customer Complaint Trending & Reportability",
                category="customer_feedback",
                presenter=quality_lead,
                summary_findings="Total customer complaints logged: 12. Average investigation closure cycle time reduced from 28 to 19 days. Zero complaints met FDA 21 CFR 803 / EU MDR Article 87 reportability criteria.",
                metrics_data="Complaints: 12 | Valid: 8 | Invalid: 4 | Reportable: 0 | Avg Days to Close: 19.2",
                status="accepted",
                linked_complaint=linked_complaint,
                attachments_summary="Post-Market Surveillance Quarterly Trends Report",
            )

            inp3 = ManagementReviewInput.objects.create(
                tenant=tenant,
                management_review=rev_approved,
                agenda_order=3,
                title="Process Performance, Yield Analysis & Scrap Reduction",
                category="process_conformity",
                presenter=admin_user,
                summary_findings="Finished good First Pass Yield reached 98.7% against 98.5% goal. In-process scrap dropped from 2.4% baseline to 1.35%, driven by molding telemetry and tooling refurbishments.",
                metrics_data="FPY: 98.7% | In-Process Scrap: 1.35% | MRB Dispositions: 6 lots released with rework",
                status="accepted",
                linked_ncr=linked_ncr,
                attachments_summary="Manufacturing KPI Dashboard Q3 Data Package",
            )

            inp4 = ManagementReviewInput.objects.create(
                tenant=tenant,
                management_review=rev_approved,
                agenda_order=4,
                title="CAPA System Health, Aging & Effectiveness Verification",
                category="capa_status",
                presenter=quality_lead,
                summary_findings="Reviewed 5 active CAPAs. Two completed 90-day post-implementation effectiveness verifications with zero recurrence. Average CAPA aging is 38 days, well within the 60-day policy ceiling.",
                metrics_data="Active CAPAs: 5 | Verified & Closed: 2 | Overdue: 0 | Recurrence Rate: 0.0%",
                status="accepted",
                linked_capa=linked_capa,
                attachments_summary="CAPA Log Sheet & Verification Files",
            )

            # 4. Review Actions for rev_approved
            act1 = ManagementReviewAction.objects.create(
                tenant=tenant,
                management_review=rev_approved,
                title="Procure automated optical inspection (AOI) vision system for SMT Line 2",
                action_type="resource_allocation",
                priority="high",
                description="Acquire and qualify an in-line 3D AOI inspection system for high-density surface mount PCBs to eliminate micro-bridging escapes prior to conformal coating.",
                assignee=admin_user,
                due_date=today + datetime.timedelta(days=30),
                budget_allocated=Decimal("45000.00"),
                status="in_progress",
            )

            act2 = ManagementReviewAction.objects.create(
                tenant=tenant,
                management_review=rev_approved,
                title="Revise raw material incoming acceptance criteria for medical-grade resin",
                action_type="procedure_revision",
                priority="medium",
                description="Update SOP-QC-204 to include melt-flow index testing and spectrophotometric color tolerance verification upon lot receiving.",
                assignee=quality_lead,
                due_date=today - datetime.timedelta(days=15),
                completion_date=today - datetime.timedelta(days=14),
                resolution_summary="SOP-QC-204 Rev 3 was updated and routed through Document Change Order vault. Quality control receiving inspectors trained and certified on the updated test method.",
                verified_by=admin_user,
                verification_notes="Reviewed training logs and verified first article inspection on Resin Lot #R-8820. Test method executed per revised SOP.",
                status="completed",
            )

            act3 = ManagementReviewAction.objects.create(
                tenant=tenant,
                management_review=rev_approved,
                title="Establish supplier corrective action for sub-assembly solder bridging",
                action_type="capa_initiation",
                priority="critical",
                description="Formal supplier corrective action requested from Board Assembly Partner for repetitive defect pattern identified in incoming lot IQC-2026-012.",
                assignee=quality_lead,
                due_date=today + datetime.timedelta(days=15),
                status="open",
                spawned_capa=linked_capa,
            )

            act4 = ManagementReviewAction.objects.create(
                tenant=tenant,
                management_review=rev_approved,
                title="Conduct cleanroom gowning and particulate control retraining for operators",
                action_type="training_competency",
                priority="medium",
                description="Schedule mandatory refresher training for Cleanroom Suite B manufacturing operators following periodic particulate count trend variance.",
                assignee=admin_user,
                due_date=today + datetime.timedelta(days=45),
                status="open",
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.14 Management Review & Quality Planning seeded successfully."))

    def _seed_submodule_12_15(self, tenant):
        """Seed demo data for Sub-module 12.15: Process Validation & Verification."""
        if ValidationProtocol.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.15 Process Validation data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.15 Process Validation & Verification...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
            or User.objects.filter(tenant=tenant).first()
        )
        quality_lead = (
            User.objects.filter(tenant=tenant, username__icontains="quality").first()
            or User.objects.filter(tenant=tenant, is_staff=True).first()
            or admin_user
        )
        change_control = DocumentChangeOrder.objects.filter(tenant=tenant).first()
        org_unit = OrgUnit.objects.filter(tenant=tenant).first()

        today = timezone.now().date()

        with transaction.atomic():
            # 1. Validation Protocols
            proto1 = ValidationProtocol.objects.create(
                tenant=tenant,
                title="High-Speed Vial Filling & Stoppering Line 3 Qualification",
                description="Comprehensive Installation, Operational, and Performance Qualification (IQ/OQ/PQ) of sterile filling line 3 per FDA Guidance for Industry (2011).",
                protocol_stage="pq",
                target_type="equipment",
                status="final_approved",
                revalidation_trigger="initial",
                equipment_tag="EQ-FILL-03",
                process_name="Aseptic Vial Filling & Stoppering",
                facility_area="Building 4, Cleanroom Suite A",
                item_code="VIAL-STERILE-10ML",
                target_completion_date=today - datetime.timedelta(days=30),
                actual_completion_date=today - datetime.timedelta(days=25),
                revalidation_due_date=today + datetime.timedelta(days=340),
                test_runs_planned=3,
                test_runs_completed=3,
                acceptance_criteria="100% compliance with critical utility specs, particulate counts <= ISO Class 5, filling speed 300 vials/min with fill volume accuracy within +/- 1.0%.",
                summary_conclusions="All 48 IQ, OQ, and PQ acceptance tests successfully executed without critical deviations. Environmental monitoring and particulate counts satisfied ISO 14644-1 requirements.",
                deviations_encountered=0,
                critical_parameters_verified=True,
                department=org_unit,
                lead_author=quality_lead,
                qa_reviewer=admin_user,
                final_approver=quality_lead,
                triggering_change=change_control,
            )

            proto2 = ValidationProtocol.objects.create(
                tenant=tenant,
                title="Clean-In-Place (CIP) Skid 04 & Bioreactor 500L Cleaning Validation Protocol",
                description="Establish scientific evidence that multi-product CIP wash sequence consistently removes biological and chemical residues below toxicological and 10 ppm limits.",
                protocol_stage="ppq",
                target_type="cleaning_procedure",
                status="in_execution",
                revalidation_trigger="periodic_review",
                equipment_tag="CIP-SKID-04",
                process_name="Bioreactor Clean-In-Place Alkaline & Acid Wash",
                facility_area="Building 2, Bioprocess Hall",
                target_completion_date=today + datetime.timedelta(days=20),
                revalidation_due_date=today + datetime.timedelta(days=345),
                test_runs_planned=3,
                test_runs_completed=2,
                acceptance_criteria="Three consecutive full-scale runs with swab TOC <= 1.23 ug/100cm2, rinse conductivity <= 1.3 uS/cm, bioburden < 10 CFU/100mL.",
                summary_conclusions="Runs 1 and 2 successfully passed all chemical and microbiological criteria. Minor non-critical flow rate sensor glitch logged as deviation DEV-01 and addressed.",
                deviations_encountered=1,
                critical_parameters_verified=True,
                department=org_unit,
                lead_author=quality_lead,
                qa_reviewer=admin_user,
            )

            proto3 = ValidationProtocol.objects.create(
                tenant=tenant,
                title="Laboratory Information Management System (LIMS) GAMP 5 CSV Protocol",
                description="Computer System Validation of GAMP 5 Category 4 configured software including 21 CFR Part 11 electronic records, audit trails, and data backup/recovery.",
                protocol_stage="iq",
                target_type="computerized_system",
                status="approved_for_execution",
                revalidation_trigger="initial",
                equipment_tag="SW-LIMS-01",
                process_name="QC Analytical Results Workflow",
                facility_area="Central QC Analytical Laboratory",
                target_completion_date=today + datetime.timedelta(days=45),
                revalidation_due_date=today + datetime.timedelta(days=730),
                test_runs_planned=55,
                test_runs_completed=0,
                acceptance_criteria="All functional requirements tested with 100% pass rate. Unalterable timestamped audit trails and two-factor electronic signature enforcement verified.",
                summary_conclusions="Protocol approved by Quality Assurance and IT Steering Committee. Ready for dry-run execution in staging environment.",
                deviations_encountered=0,
                critical_parameters_verified=False,
                department=org_unit,
                lead_author=quality_lead,
                qa_reviewer=admin_user,
            )

            # 2. Process Capability Studies
            study1 = ProcessCapabilityStudy.objects.create(
                tenant=tenant,
                title="Sterile Vial Fill Volume 10.0 mL Operational Qualification SPC",
                parameter_name="Filling Volume (mL)",
                parameter_category="fill_volume_weight",
                unit_of_measure="mL",
                upper_spec_limit=Decimal("10.2000"),
                lower_spec_limit=Decimal("9.8000"),
                target_nominal=Decimal("10.0000"),
                subgroup_size=5,
                number_of_subgroups=30,
                total_samples=150,
                mean_value=Decimal("10.0120"),
                within_subgroup_stdev=Decimal("0.0380"),
                overall_stdev=Decimal("0.0410"),
                cp_index=Decimal("1.750"),
                cpk_index=Decimal("1.640"),
                pp_index=Decimal("1.630"),
                ppk_index=Decimal("1.530"),
                expected_ppm=Decimal("0.45"),
                is_normally_distributed=True,
                capability_determination="capable_excellent",
                status="completed",
                process_name="Vial Filling Line 3",
                equipment_tag="EQ-FILL-03",
                item_code="VIAL-STERILE-10ML",
                lot_number="LOT-2026-094",
                analysis_summary="Process is in statistical control and exhibits high capability (Cpk = 1.64 > 1.33 threshold). Recommend maintaining standard inline weight check frequency.",
                study_date=today - datetime.timedelta(days=28),
                validation_protocol=proto1,
                investigator=admin_user,
                approved_by=quality_lead,
            )

            study2 = ProcessCapabilityStudy.objects.create(
                tenant=tenant,
                title="Tyvek Pouch Packaging Heat Seal Strength Peel Force Study",
                parameter_name="Seal Peel Strength (N/15mm)",
                parameter_category="seal_strength_force",
                unit_of_measure="N/15mm",
                upper_spec_limit=Decimal("6.5000"),
                lower_spec_limit=Decimal("3.5000"),
                target_nominal=Decimal("5.0000"),
                subgroup_size=5,
                number_of_subgroups=20,
                total_samples=100,
                mean_value=Decimal("4.8500"),
                within_subgroup_stdev=Decimal("0.2800"),
                overall_stdev=Decimal("0.3100"),
                cp_index=Decimal("1.790"),
                cpk_index=Decimal("1.610"),
                pp_index=Decimal("1.610"),
                ppk_index=Decimal("1.450"),
                expected_ppm=Decimal("0.82"),
                is_normally_distributed=True,
                capability_determination="capable_excellent",
                status="completed",
                process_name="Pouch Sealing Line 1",
                equipment_tag="SEAL-01",
                item_code="POUCH-TYVEK-150",
                lot_number="LOT-2026-088",
                analysis_summary="Pouch seal peel force meets ISO 11607-1 integrity requirements. Cpk of 1.61 demonstrates excellent process capability.",
                study_date=today - datetime.timedelta(days=5),
                investigator=quality_lead,
                approved_by=admin_user,
            )

            # 3. Computer System Validations
            csv1 = ComputerSystemValidation.objects.create(
                tenant=tenant,
                system_name="LabVantage LIMS Enterprise",
                version_release="v8.8.2",
                vendor_name="LabVantage Solutions Inc.",
                gamp_category="cat_4_configured",
                gxp_impact="direct_gxp",
                validation_approach="csa_risk_based",
                hosting_model="cloud_saas",
                is_part_11_compliant=True,
                requires_audit_trail=True,
                has_disaster_recovery_plan=True,
                traceability_status="verified_100_percent",
                urs_requirements_count=85,
                test_scripts_count=55,
                deviations_found_count=0,
                status="in_qualification",
                validated_date=None,
                periodic_review_frequency_months=24,
                next_review_due=today + datetime.timedelta(days=365),
                description="Quality Control analytical data management, sample lifecycle tracking, automated certificate of analysis generation, and stability study scheduling.",
                system_owner=admin_user,
                quality_lead=quality_lead,
                validation_protocol=proto3,
            )

            csv2 = ComputerSystemValidation.objects.create(
                tenant=tenant,
                system_name="Siemens Desigo CC Building & Environmental Monitoring System",
                version_release="v5.1",
                vendor_name="Siemens AG",
                gamp_category="cat_4_configured",
                gxp_impact="direct_gxp",
                validation_approach="traditional_v_model",
                hosting_model="on_premise",
                is_part_11_compliant=True,
                requires_audit_trail=True,
                has_disaster_recovery_plan=True,
                traceability_status="verified_100_percent",
                urs_requirements_count=42,
                test_scripts_count=38,
                deviations_found_count=0,
                status="validated_live",
                validated_date=today - datetime.timedelta(days=120),
                periodic_review_frequency_months=24,
                last_review_date=today - datetime.timedelta(days=120),
                next_review_due=today + datetime.timedelta(days=245),
                description="Cleanroom differential pressure, HVAC temperature, and relative humidity continuous recording and deviation alerting.",
                system_owner=admin_user,
                quality_lead=quality_lead,
                validation_protocol=proto1,
            )

            # 4. Cleaning Validations
            clean1 = CleaningValidation.objects.create(
                tenant=tenant,
                title="Bioreactor 500L & CIP Skid Multi-Product Cleaning Protocol",
                equipment_train_tag="CIP-SKID-04 / BIO-500L",
                target_residue="Monoclonal Antibody mAb-201",
                cleaning_agent_used="CIP-100 Alkaline Detergent & WFI",
                worst_case_rationale="highest_potency",
                calculation_basis="toxicological_pde",
                min_daily_dose_active_mg=Decimal("50.0000"),
                max_daily_dose_subsequent_mg=Decimal("100.0000"),
                smallest_batch_size_kg=Decimal("250.000"),
                safety_factor=Decimal("1000.0"),
                toxicological_pde_mg_day=Decimal("0.5000"),
                calculated_maco_mg=Decimal("5.5556"),
                total_surface_area_sqcm=Decimal("45000.00"),
                swab_sampling_area_sqcm=Decimal("25.00"),
                calculated_swab_limit_ug=Decimal("1.235"),
                rinse_volume_liters=Decimal("150.00"),
                calculated_rinse_limit_ppm=Decimal("2.500"),
                analytical_method="toc",
                method_recovery_percentage=Decimal("84.50"),
                dirty_hold_time_hours=Decimal("72.0"),
                clean_hold_time_hours=Decimal("48.0"),
                consecutive_successful_runs=2,
                is_visually_clean=True,
                worst_swab_result_ug=Decimal("0.420"),
                worst_rinse_result_ppm=Decimal("0.850"),
                cleaning_status="in_cleaning_runs",
                next_revalidation_date=today + datetime.timedelta(days=360),
                notes="Runs 1 and 2 completed with swab TOC results at 0.42 ug/100cm2 and 0.38 ug/100cm2 against 1.23 limit. Run 3 scheduled for execution.",
                validation_protocol=proto2,
                analytical_lead=quality_lead,
                qa_approver=admin_user,
            )

            clean2 = CleaningValidation.objects.create(
                tenant=tenant,
                title="High-Shear Fluid Bed Granulator 250L Solvent Wash Protocol",
                equipment_train_tag="GRAN-250L",
                target_residue="Active Compound X-99 (Insoluble)",
                cleaning_agent_used="Ethanol USP / Decon 90",
                worst_case_rationale="lowest_solubility",
                calculation_basis="ten_ppm_limit",
                min_daily_dose_active_mg=Decimal("10.0000"),
                max_daily_dose_subsequent_mg=Decimal("20.0000"),
                smallest_batch_size_kg=Decimal("120.000"),
                safety_factor=Decimal("1000.0"),
                toxicological_pde_mg_day=Decimal("0.1000"),
                calculated_maco_mg=Decimal("1.2000"),
                total_surface_area_sqcm=Decimal("32000.00"),
                swab_sampling_area_sqcm=Decimal("25.00"),
                calculated_swab_limit_ug=Decimal("0.375"),
                rinse_volume_liters=Decimal("80.00"),
                calculated_rinse_limit_ppm=Decimal("1.000"),
                analytical_method="hplc",
                method_recovery_percentage=Decimal("88.20"),
                dirty_hold_time_hours=Decimal("48.0"),
                clean_hold_time_hours=Decimal("72.0"),
                consecutive_successful_runs=3,
                is_visually_clean=True,
                worst_swab_result_ug=Decimal("0.110"),
                worst_rinse_result_ppm=Decimal("0.240"),
                cleaning_status="validated_pass",
                next_revalidation_date=today + datetime.timedelta(days=305),
                notes="3 consecutive validation runs met all acceptance criteria with analytical non-detects across 12 critical sampling points.",
                validation_protocol=proto1,
                analytical_lead=quality_lead,
                qa_approver=admin_user,
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.15 Process Validation & Verification seeded successfully."))

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.15 Process Validation & Verification seeded successfully."))

    def _seed_submodule_12_16(self, tenant):
        if HazardousMaterial.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.16 Environmental, Health & Safety (EHS) data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.16 Environmental, Health & Safety (EHS)...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).order_by("pk").first()
            or User.objects.filter(tenant=tenant).order_by("pk").first()
        )
        if not admin_user:
            self.stdout.write(f"[{tenant.name}] Warning: No user found for tenant.")
            return

        users = list(User.objects.filter(tenant=tenant).order_by("pk"))
        ehs_officer = users[1] if len(users) > 1 else admin_user

        qa_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="quality").order_by("pk").first()
        if not qa_dept:
            qa_dept = OrgUnit.objects.filter(tenant=tenant).order_by("pk").first()

        vendor = Party.objects.filter(tenant=tenant, is_vendor=True).order_by("pk").first()
        if not vendor:
            vendor = Party.objects.filter(tenant=tenant).order_by("pk").first()

        today = timezone.now().date()
        now = timezone.now()

        with transaction.atomic():
            # 1. Hazardous Materials
            haz1 = HazardousMaterial.objects.create(
                tenant=tenant,
                material_name="Isopropyl Alcohol 99.8% (IPA USP Grade)",
                trade_name="Propan-2-ol Electronic Cleaning Solvent",
                cas_number="67-63-0",
                un_number="UN1219",
                chemical_formula="C3H8O",
                physical_state="liquid",
                ghs_signal_word="danger",
                ghs_pictograms="GHS02,GHS07",
                hazard_statements="H225: Highly flammable liquid and vapour. H319: Causes serious eye irritation.",
                precautionary_statements="P210: Keep away from heat, sparks, open flames. P305+P351+P338: If in eyes rinse cautiously with water.",
                nfpa_health=1,
                nfpa_flammability=3,
                nfpa_instability=0,
                nfpa_special_hazard="none",
                sds_revision="Rev 3.0",
                sds_issue_date=today - datetime.timedelta(days=180),
                sds_expiry_date=today + datetime.timedelta(days=915),
                osha_pel="400 ppm (980 mg/m3) TWA",
                acgih_tlv="200 ppm TWA, 400 ppm STEL",
                exposure_uom="ppm",
                ppe_requirements="Nitrile gloves (min 4 mil), splash goggles, chemical apron.",
                incompatible_materials="Strong oxidizing agents, acetaldehyde, chlorine, ethylene oxide, isocyanates.",
                spill_cleanup_procedure="Eliminate ignition sources. Absorb with non-combustible absorbent and transfer to sealed container.",
                storage_location_code="Flammables Storage Bunker B-101 / Flammable Safety Cabinet 3",
                maximum_storage_quantity=Decimal("1000.00"),
                quantity_uom="L",
                status="active",
                org_unit=qa_dept,
                supplier=vendor,
                managed_by=ehs_officer,
            )

            haz2 = HazardousMaterial.objects.create(
                tenant=tenant,
                material_name="Sulfuric Acid 96% AR Grade",
                trade_name="Hydrogen Sulfate Concentrated Acid",
                cas_number="7664-93-9",
                un_number="UN1830",
                chemical_formula="H2SO4",
                physical_state="liquid",
                ghs_signal_word="danger",
                ghs_pictograms="GHS05",
                hazard_statements="H314: Causes severe skin burns and eye damage. H290: May be corrosive to metals.",
                precautionary_statements="P260: Do not breathe mists. P280: Wear protective gloves/clothing/eye protection. P301+P330+P331: IF SWALLOWED: Rinse mouth. Do NOT induce vomiting.",
                nfpa_health=3,
                nfpa_flammability=0,
                nfpa_instability=2,
                nfpa_special_hazard="w_slash",
                sds_revision="Rev 4.1",
                sds_issue_date=today - datetime.timedelta(days=90),
                sds_expiry_date=today + datetime.timedelta(days=1005),
                osha_pel="1 mg/m3 TWA",
                acgih_tlv="0.2 mg/m3 TWA (thoracic particulate)",
                exposure_uom="mg/m3",
                ppe_requirements="Acid-resistant butyl rubber gloves, face shield with safety glasses, rubber apron, rubber boots.",
                incompatible_materials="Water, combustible materials, organic materials, strong reducing agents, bases.",
                spill_cleanup_procedure="Neutralize carefully with basic material such as lime or soda ash. Absorb with inert material.",
                storage_location_code="Acid Corrosives Vault A-04 / Spill Containment Sump 2",
                maximum_storage_quantity=Decimal("200.00"),
                quantity_uom="L",
                status="active",
                org_unit=qa_dept,
                supplier=vendor,
                managed_by=ehs_officer,
            )

            haz3 = HazardousMaterial.objects.create(
                tenant=tenant,
                material_name="Formaldehyde 37% Solution (Formalin)",
                trade_name="Methanal Preservative Solution",
                cas_number="50-00-0",
                un_number="UN2209",
                chemical_formula="CH2O",
                physical_state="liquid",
                ghs_signal_word="danger",
                ghs_pictograms="GHS05,GHS06,GHS08",
                hazard_statements="H301: Toxic if swallowed. H311: Toxic in contact with skin. H314: Causes severe skin burns. H350: May cause cancer.",
                precautionary_statements="P201: Obtain special instructions before use. P280: Wear protective gloves/protective clothing/eye protection/face protection.",
                nfpa_health=3,
                nfpa_flammability=2,
                nfpa_instability=0,
                nfpa_special_hazard="none",
                sds_revision="Rev 2.0",
                sds_issue_date=today - datetime.timedelta(days=45),
                sds_expiry_date=today + datetime.timedelta(days=1050),
                osha_pel="0.75 ppm TWA, 2 ppm STEL",
                acgih_tlv="0.1 ppm TWA, 0.3 ppm STEL",
                exposure_uom="ppm",
                ppe_requirements="Nitrile gloves, vapor respirator with formaldehyde cartridges, splash goggles, lab coat.",
                incompatible_materials="Strong oxidizing agents, strong bases, acids, phenols, urea.",
                spill_cleanup_procedure="Evacuate personnel. Ventilate area. Absorb with inert binder and deactivate with dilute ammonia solution.",
                storage_location_code="Toxic Chemicals Cabinet T-02",
                maximum_storage_quantity=Decimal("50.00"),
                quantity_uom="L",
                status="active",
                org_unit=qa_dept,
                supplier=vendor,
                managed_by=admin_user,
            )

            # 2. Safety Incidents
            inc1 = SafetyIncident.objects.create(
                tenant=tenant,
                title="Chemical Splash to Forearm During QC Acid Transfer",
                incident_date=now - datetime.timedelta(days=14),
                report_date=today - datetime.timedelta(days=14),
                incident_type="chemical_spill",
                severity="minor",
                status="closed",
                org_unit=qa_dept,
                location_details="Quality Control Analytical Laboratory 2, Fume Hood 4",
                reported_by=ehs_officer,
                affected_person=admin_user,
                affected_party_type="employee",
                nature_of_injury="burn_heat_chemical",
                body_part_affected="hands_fingers",
                medical_treatment_level="first_aid_only",
                is_osha_recordable=False,
                osha_classification="first_aid",
                lost_workdays_count=0,
                restricted_workdays_count=0,
                ppe_compliance_status="inadequate_ppe",
                ppe_notes="Standard nitrile gloves did not provide extended forearm cuff protection when handling acid carboys.",
                immediate_actions_taken="Emergency eyewash and safety shower station used immediately for 15 minutes continuous irrigation. First aid burn dressing applied by occupational health nurse.",
                lead_investigator=ehs_officer,
                root_cause_category="procedure_gap",
                investigation_findings="Analyst sustained a minor skin exposure of dilute acid to the wrist area due to improper glove cuff overlap under lab coat. Procure extended-cuff chemical resistant gloves.",
            )

            inc2 = SafetyIncident.objects.create(
                tenant=tenant,
                title="Forklift Near Miss in Raw Material Quarantine Aisle B",
                incident_date=now - datetime.timedelta(days=5),
                report_date=today - datetime.timedelta(days=5),
                incident_type="near_miss",
                severity="minor",
                status="investigating",
                org_unit=qa_dept,
                location_details="Warehouse Zone 1, Main Quarantine Aisle Intersection B-3",
                reported_by=admin_user,
                affected_person=None,
                affected_party_name="Pallet Truck Operator Team",
                affected_party_type="employee",
                nature_of_injury="none",
                body_part_affected="none",
                medical_treatment_level="none",
                is_osha_recordable=False,
                osha_classification="non_recordable",
                lost_workdays_count=0,
                restricted_workdays_count=0,
                ppe_compliance_status="compliant",
                ppe_notes="High-visibility safety vests and steel-toe boots were worn by both operators.",
                immediate_actions_taken="Both operators debriefed immediately by warehouse safety lead. Corner stop mirror adjusted.",
                lead_investigator=ehs_officer,
                root_cause_category="environmental_hazard",
                investigation_findings="Blind aisle intersection lacked convex wide-angle safety dome mirror and floor stop line markings.",
            )

            # 3. Environmental Monitoring Logs
            log1 = EnvironmentalMonitoringLog.objects.create(
                tenant=tenant,
                sampling_point_id="CR1-LFH-01-AIR",
                sampling_timestamp=now - datetime.timedelta(days=1, hours=2),
                org_unit=qa_dept,
                cleanroom_class="iso_class_5",
                operational_state="in_operation",
                monitoring_category="viable_air_microbial",
                parameter_name="Active Air Sampler Viable Colony Count",
                measured_value=Decimal("0.000"),
                unit_of_measure="cfu_m3",
                target_nominal_value=Decimal("0.000"),
                lower_alert_limit=None,
                upper_alert_limit=Decimal("1.000"),
                lower_action_limit=None,
                upper_action_limit=Decimal("1.000"),
                evaluation_status="normal",
                excursion_details="",
                immediate_containment_action="",
                sampled_by=admin_user,
                verified_by=ehs_officer,
            )

            log2 = EnvironmentalMonitoringLog.objects.create(
                tenant=tenant,
                sampling_point_id="CR1-AL-03-SURF",
                sampling_timestamp=now - datetime.timedelta(days=2, hours=4),
                org_unit=qa_dept,
                cleanroom_class="iso_class_7",
                operational_state="in_operation",
                monitoring_category="viable_surface_contact",
                parameter_name="Gowning Airlock Step-Over Bench Surface Swab",
                measured_value=Decimal("6.500"),
                unit_of_measure="cfu_plate",
                target_nominal_value=Decimal("0.000"),
                lower_alert_limit=None,
                upper_alert_limit=Decimal("5.000"),
                lower_action_limit=None,
                upper_action_limit=Decimal("10.000"),
                evaluation_status="alert_exceeded",
                excursion_details="Slightly elevated contact plate count (6.5 CFU/plate) observed on gowning step-over bench following shift change.",
                immediate_containment_action="Immediate sanitization using sterile 70% IPA spray and wipe. Resampling scheduled post-cleaning.",
                sampled_by=ehs_officer,
                verified_by=admin_user,
            )

            log3 = EnvironmentalMonitoringLog.objects.create(
                tenant=tenant,
                sampling_point_id="PKG-DP-02",
                sampling_timestamp=now - datetime.timedelta(hours=6),
                org_unit=qa_dept,
                cleanroom_class="iso_class_8",
                operational_state="in_operation",
                monitoring_category="differential_pressure",
                parameter_name="Packaging Area Differential Room Pressure",
                measured_value=Decimal("18.400"),
                unit_of_measure="pascals",
                target_nominal_value=Decimal("15.000"),
                lower_alert_limit=Decimal("12.000"),
                upper_alert_limit=Decimal("25.000"),
                lower_action_limit=Decimal("10.000"),
                upper_action_limit=Decimal("30.000"),
                evaluation_status="normal",
                excursion_details="",
                immediate_containment_action="",
                sampled_by=admin_user,
                verified_by=ehs_officer,
            )

            # 4. Waste Disposal Manifests
            man1 = WasteDisposalManifest.objects.create(
                tenant=tenant,
                manifest_title="Q4 Spent Flammable Solvent Drums Shipment",
                regulatory_manifest_id="018492043JJK",
                manifest_type="hazardous_chemical",
                status="certified_disposed",
                generator_org_unit=qa_dept,
                generator_epa_id="TXD980831201",
                accumulation_start_date=today - datetime.timedelta(days=90),
                waste_description="Waste Flammable Liquids, N.O.S. (Contains Acetone, Isopropanol), 3, UN1993, PG II",
                epa_waste_codes="D001, F003, F005",
                associated_hazardous_material=haz1,
                physical_state="liquid",
                is_ignitable=True,
                is_corrosive=False,
                is_reactive=False,
                is_toxic=False,
                container_count=10,
                container_type="drum_55gal",
                quantity_value=Decimal("1850.00"),
                quantity_uom="kilograms",
                transporter=vendor,
                transporter_epa_id="TXD980831201",
                tsdf_facility=vendor,
                tsdf_epa_id="TXD000838896",
                shipment_date=today - datetime.timedelta(days=20),
                tsdf_receipt_date=today - datetime.timedelta(days=17),
                destruction_certificate_date=today - datetime.timedelta(days=5),
                discrepancy_details="",
                prepared_by=ehs_officer,
            )

            man2 = WasteDisposalManifest.objects.create(
                tenant=tenant,
                manifest_title="Neutralized Acid Rinse Solution IBC Tote Transfer",
                regulatory_manifest_id="019284756XYZ",
                manifest_type="hazardous_chemical",
                status="in_transit",
                generator_org_unit=qa_dept,
                generator_epa_id="TXD980831201",
                accumulation_start_date=today - datetime.timedelta(days=45),
                waste_description="Corrosive Liquid, Acidic, Inorganic, N.O.S. (Contains Sulfuric Acid Residue), 8, UN3264, PG II",
                epa_waste_codes="D002",
                associated_hazardous_material=haz2,
                physical_state="liquid",
                is_ignitable=False,
                is_corrosive=True,
                is_reactive=False,
                is_toxic=False,
                container_count=2,
                container_type="tote_ibc",
                quantity_value=Decimal("750.00"),
                quantity_uom="kilograms",
                transporter=vendor,
                transporter_epa_id="TXD980831201",
                tsdf_facility=vendor,
                tsdf_epa_id="TXD000838896",
                shipment_date=today - datetime.timedelta(days=3),
                tsdf_receipt_date=None,
                destruction_certificate_date=None,
                discrepancy_details="",
                prepared_by=admin_user,
            )

        self.stdout.write(self.style.SUCCESS(f"[{tenant.name}] 12.16 Environmental, Health & Safety (EHS) seeded successfully."))







