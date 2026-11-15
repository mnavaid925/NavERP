import datetime
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Tenant
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
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

        self.stdout.write(self.style.SUCCESS("Module 12 quality seeding complete."))

    def _seed_submodule_12_1(self, tenant):
        if ControlledDocument.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"[{tenant.name}] 12.1 Document Control data already seeded, skipping.")
            return

        self.stdout.write(f"[{tenant.name}] Seeding 12.1 Document Control & Management...")

        admin_user = (
            User.objects.filter(tenant=tenant, is_superuser=True).first()
            or User.objects.filter(tenant=tenant).first()
        )
        if not admin_user:
            self.stdout.write(f"[{tenant.name}] Warning: No user found for tenant.")
            return

        users = list(User.objects.filter(tenant=tenant))
        reviewer_user = users[1] if len(users) > 1 else admin_user

        qa_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="quality").first()
        if not qa_dept:
            qa_dept = OrgUnit.objects.filter(tenant=tenant).first()

        ops_dept = OrgUnit.objects.filter(tenant=tenant, name__icontains="operation").first()
        if not ops_dept:
            ops_dept = OrgUnit.objects.filter(tenant=tenant).last()

        employee = EmployeeProfile.objects.filter(tenant=tenant).first()

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
