import datetime
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Tenant
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgment
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord

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
