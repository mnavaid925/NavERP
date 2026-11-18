import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Tenant
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
from apps.quality.models.NonConformance.MrbDispositions import MrbDisposition
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.ProcessDeviations import ProcessDeviation
from apps.quality.models.NonConformance.QuarantineContainments import QuarantineContainment
from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment
from apps.quality.models.RiskManagement.RiskControlMeasures import RiskControlMeasure
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan
from apps.quality.models.RiskManagement.RiskReviewRecords import RiskReviewRecord


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


