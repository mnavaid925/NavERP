from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Party, Tenant
from apps.documents.models import (
    Document,
    DocumentApprovalRequest,
    DocumentApprovalWorkflow,
    DocumentBranch,
    DocumentDraft,
    DocumentLock,
    DocumentReviewComment,
    DocumentSignature,
    DocumentTemplate,
    DocumentVersion,
    DraftCollaboration,
    TemplateSection,
)
from apps.documents.views._helpers import count_words


class Command(BaseCommand):
    help = "Seed demo data for the Document Management System (DMS) module"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing documents module data before seeding",
        )

    def handle(self, *args, **options):
        if options.get("flush"):
            self.stdout.write("Flushing documents module data...")
            DocumentReviewComment.objects.all().delete()
            DocumentSignature.objects.all().delete()
            DocumentApprovalRequest.objects.all().delete()
            DocumentApprovalWorkflow.objects.all().delete()
            DraftCollaboration.objects.all().delete()
            DocumentDraft.objects.all().delete()
            TemplateSection.objects.all().delete()
            DocumentTemplate.objects.all().delete()
            DocumentLock.objects.all().delete()
            DocumentBranch.objects.all().delete()
            DocumentVersion.objects.all().delete()
            Document.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Documents module data flushed successfully."))

        User = get_user_model()
        tenants = Tenant.objects.all()

        if not tenants.exists():
            self.stdout.write(self.style.WARNING("No tenants found in database. Run seed_core and seed_accounts first."))
            return

        for tenant in tenants:
            user = (
                User.objects.filter(tenant=tenant, username__icontains="admin").first()
                or User.objects.filter(tenant=tenant).first()
            )
            org_unit = OrgUnit.objects.filter(tenant=tenant).first()
            party = Party.objects.filter(tenant=tenant).first()

            if not user:
                self.stdout.write(self.style.WARNING(f"No user found for tenant '{tenant.slug}'. Skipping."))
                continue

            with transaction.atomic():
                # ---------------------------------------------------------
                # 13.1 Authoring Demo Data
                # ---------------------------------------------------------
                if not DocumentTemplate.objects.filter(tenant=tenant).exists():
                    self.stdout.write(f"Seeding Document Authoring records for tenant '{tenant.slug}'...")

                    sop_content = (
                        "# Standard Operating Procedure: {{sop_title}}\n\n"
                        "Organization: {{company_name}}\n"
                        "Author: {{author_name}}\n\n"
                        "## 1. Purpose & Scope\n"
                        "This SOP defines the standardized operational protocol for production execution.\n\n"
                        "## 2. Responsibilities\n"
                        "All authorized departmental staff must adhere to the steps outlined herein.\n"
                    )
                    sop_tmpl = DocumentTemplate.objects.create(
                        tenant=tenant,
                        name="Standard Operating Procedure (SOP) Master",
                        template_type="sop",
                        category="operations",
                        description="Standardized corporate procedure template with locked typography and mandatory sections.",
                        content=sop_content,
                        version="1.0",
                        is_active=True,
                        is_locked=True,
                        target_org_unit=org_unit,
                        owner=user,
                        available_tokens={
                            "company_name": "Official Legal Entity Name",
                            "sop_title": "Procedure Title Heading",
                            "author_name": "Primary Document Author",
                        },
                    )

                    nda_content = (
                        "# Mutual Non-Disclosure Agreement\n\n"
                        "Between: {{company_name}}\n"
                        "And: {{party_name}}\n\n"
                        "Effective Date: {{effective_date}}\n\n"
                        "1. Confidential Information\n"
                        "The parties agree that all proprietary documentation disclosed shall remain confidential for 5 years.\n"
                    )
                    nda_tmpl = DocumentTemplate.objects.create(
                        tenant=tenant,
                        name="Mutual Non-Disclosure Agreement (NDA)",
                        template_type="contract",
                        category="legal",
                        description="Standard legal confidentiality agreement with locked boilerplate clauses.",
                        content=nda_content,
                        version="2.0",
                        is_active=True,
                        is_locked=True,
                        target_org_unit=org_unit,
                        owner=user,
                        available_tokens={
                            "company_name": "Company Legal Name",
                            "party_name": "Counterparty Legal Name",
                            "effective_date": "Contract Effective Date",
                        },
                    )

                    memo_tmpl = DocumentTemplate.objects.create(
                        tenant=tenant,
                        name="Corporate Policy & Governance Memo",
                        template_type="memo",
                        category="hr",
                        description="Internal policy memo template for executive communications and HR circulars.",
                        content="MEMORANDUM\n\nTO: {{recipient_dept}}\nFROM: Executive Management\nDATE: {{memo_date}}\nSUBJECT: {{policy_subject}}\n\nPlease review the attached corporate guidelines.",
                        version="1.0",
                        is_active=True,
                        is_locked=False,
                        target_org_unit=org_unit,
                        owner=user,
                        available_tokens={
                            "recipient_dept": "Target Recipient Department",
                            "memo_date": "Date of Memorandum Issuance",
                            "policy_subject": "Policy Topic Title",
                        },
                    )

                    # Template Sections
                    TemplateSection.objects.create(
                        tenant=tenant,
                        template=sop_tmpl,
                        title="Section 1: Purpose, Scope and Applicable Standards",
                        section_type="body_section",
                        content="All operations conducted under this procedure must conform to ISO 9001 quality management guidelines.",
                        order=10,
                        is_locked=True,
                        is_mandatory=True,
                    )

                    TemplateSection.objects.create(
                        tenant=tenant,
                        template=sop_tmpl,
                        title="Section 2: Execution Protocol & Steps",
                        section_type="body_section",
                        content="1. Inspect equipment baseline calibration.\n2. Verify environmental temperature and humidity.\n3. Execute processing sequence.\n4. Log parameters in batch record.",
                        order=20,
                        is_locked=False,
                        is_mandatory=True,
                    )

                    TemplateSection.objects.create(
                        tenant=tenant,
                        template=nda_tmpl,
                        title="Clause 3: Non-Disclosure Obligations and Remedies",
                        section_type="boilerplate",
                        content="The Receiving Party shall protect the Disclosing Party's Confidential Information with at least the degree of care it uses for its own sensitive data, but no less than reasonable care.",
                        order=10,
                        is_locked=True,
                        is_mandatory=True,
                    )

                    TemplateSection.objects.create(
                        tenant=tenant,
                        template=None,
                        title="Standard Corporate Legal Disclaimer",
                        section_type="disclaimer",
                        content="This communication contains confidential and privileged information intended solely for the recipient.",
                        order=100,
                        is_locked=True,
                        is_mandatory=False,
                    )

                    # Document Drafts
                    draft1_text = (
                        "# Standard Operating Procedure: Incoming Raw Material Sampling\n\n"
                        f"Organization: {tenant.name}\n"
                        f"Author: {user.get_full_name() or user.username}\n\n"
                        "## 1. Purpose & Scope\n"
                        "This SOP governs incoming lot sampling across chemical, electronic, and packaging inventory streams.\n\n"
                        "## 2. Responsibilities\n"
                        "QC Technicians must verify Certificates of Analysis prior to unloading.\n"
                        "Samples must be drawn within 24 hours of warehouse arrival.\n"
                    )
                    draft1 = DocumentDraft.objects.create(
                        tenant=tenant,
                        template=sop_tmpl,
                        title="SOP: Incoming Raw Material Quality Sampling",
                        document_type="sop",
                        status="draft",
                        draft_version="0.1",
                        content=draft1_text,
                        content_format="markdown",
                        author=user,
                        department=org_unit,
                        word_count=count_words(draft1_text),
                        sync_status="synced",
                    )

                    draft2_text = (
                        "# Mutual Non-Disclosure Agreement\n\n"
                        f"Between: {tenant.name}\n"
                        f"And: {party.name if party else 'Acme Vendor Partner'}\n\n"
                        "Effective Date: 2026-11-22\n\n"
                        "1. Confidential Information\n"
                        "The parties agree that all proprietary documentation disclosed shall remain confidential for 5 years.\n"
                        "Notice period for breach notifications shall be within 30 calendar days.\n"
                    )
                    draft2 = DocumentDraft.objects.create(
                        tenant=tenant,
                        template=nda_tmpl,
                        title=f"NDA: {tenant.name} & Partner Alliance",
                        document_type="contract",
                        status="in_review",
                        draft_version="0.2",
                        content=draft2_text,
                        content_format="markdown",
                        author=user,
                        department=org_unit,
                        related_party=party,
                        word_count=count_words(draft2_text),
                        sync_status="synced",
                    )

                    draft3_text = (
                        "MEMORANDUM\n\n"
                        "TO: Information Technology & Operations\n"
                        "FROM: Security & Compliance Committee\n"
                        "DATE: 2026-11-22\n"
                        "SUBJECT: Multi-Factor Authentication & Remote Session Protocols\n\n"
                        "Please be advised that all hybrid and remote staff members must activate hardware tokens by month end.\n"
                    )
                    draft3 = DocumentDraft.objects.create(
                        tenant=tenant,
                        template=memo_tmpl,
                        title="Policy Memo: Information Security & Remote Access Standards",
                        document_type="memo",
                        status="ready_for_promotion",
                        draft_version="0.9",
                        content=draft3_text,
                        content_format="plain",
                        author=user,
                        department=org_unit,
                        word_count=count_words(draft3_text),
                        sync_status="synced",
                    )

                    # Draft Collaboration
                    DraftCollaboration.objects.create(
                        tenant=tenant,
                        draft=draft1,
                        entry_type="comment",
                        status="open",
                        author=user,
                        section_anchor="Section 2: Responsibilities",
                        comment_text="Ensure inspection sampling plan references ISO 2859-1 General Inspection Level II.",
                    )

                    DraftCollaboration.objects.create(
                        tenant=tenant,
                        draft=draft2,
                        entry_type="suggestion",
                        status="open",
                        author=user,
                        section_anchor="Clause 1: Confidential Information",
                        selected_text="within 30 calendar days",
                        replacement_text="within 10 business days",
                        comment_text="Align breach notification window with corporate legal SLA.",
                    )

                    DraftCollaboration.objects.create(
                        tenant=tenant,
                        draft=draft3,
                        entry_type="track_change",
                        status="accepted",
                        author=user,
                        section_anchor="Subject Paragraph",
                        selected_text="all remote employees",
                        replacement_text="all hybrid and remote staff members",
                        comment_text="Broaden scope to explicitly include hybrid workers.",
                        resolved_by=user,
                        resolved_at=timezone.now(),
                    )

                # ---------------------------------------------------------
                # 13.2 Version Control & Revision Management Demo Data
                # ---------------------------------------------------------
                if not Document.objects.filter(tenant=tenant).exists():
                    self.stdout.write(f"Seeding Version Control records for tenant '{tenant.slug}'...")

                    # Document 1: Enterprise SOP Master (Published, Semantic Scheme)
                    doc1 = Document.objects.create(
                        tenant=tenant,
                        title="Enterprise Standard Operating Procedure Master",
                        document_type="sop",
                        classification="internal",
                        status="published",
                        versioning_scheme="semantic",
                        current_version_label="1.2.0",
                        current_version_no=3,
                        owner=user,
                        department=org_unit,
                        description="Core quality assurance and standard operating protocol for manufacturing line calibration.",
                    )

                    v1_text = (
                        "Section 1: Operating Protocols & Safety Baseline\n"
                        "1.1 Technicians must calibrate pressure gauges daily.\n"
                        "1.2 Wear Level 2 PPE in high-voltage cleanrooms.\n\n"
                        "Section 2: Maintenance Schedules\n"
                        "2.1 Monthly filter change-outs."
                    )
                    ver1 = DocumentVersion.objects.create(
                        tenant=tenant,
                        document=doc1,
                        version_label="1.0.0",
                        major_number=1,
                        minor_number=0,
                        patch_number=0,
                        version_type="major",
                        status="superseded",
                        is_official=False,
                        change_summary="Initial publication of enterprise SOP",
                        extracted_text=v1_text,
                        file_name="Enterprise_SOP_v1.0.0.pdf",
                        file_size=1048576,
                        mime_type="application/pdf",
                        author=user,
                    )

                    v2_text = (
                        "Section 1: Operating Protocols & Safety Baseline\n"
                        "1.1 Technicians must calibrate pressure gauges twice daily.\n"
                        "1.2 Wear Level 2 PPE in high-voltage cleanrooms.\n"
                        "1.3 Log temperature recordings hourly.\n\n"
                        "Section 2: Maintenance Schedules\n"
                        "2.1 Bi-weekly filter change-outs and sanitation."
                    )
                    ver2 = DocumentVersion.objects.create(
                        tenant=tenant,
                        document=doc1,
                        version_label="1.1.0",
                        major_number=1,
                        minor_number=1,
                        patch_number=0,
                        version_type="minor",
                        status="superseded",
                        is_official=False,
                        change_summary="Added hourly temperature recordings and increased filter cycle",
                        extracted_text=v2_text,
                        file_name="Enterprise_SOP_v1.1.0.pdf",
                        file_size=1153433,
                        mime_type="application/pdf",
                        author=user,
                    )

                    v3_text = (
                        "Section 1: Operating Protocols & Safety Baseline\n"
                        "1.1 Technicians must calibrate pressure gauges twice daily using digital telemetry.\n"
                        "1.2 Wear Level 3 PPE in high-voltage cleanrooms.\n"
                        "1.3 Log temperature recordings hourly via SCADA.\n\n"
                        "Section 2: Maintenance Schedules\n"
                        "2.1 Weekly filter change-outs and certified HEPA sanitation."
                    )
                    ver3 = DocumentVersion.objects.create(
                        tenant=tenant,
                        document=doc1,
                        version_label="1.2.0",
                        major_number=1,
                        minor_number=2,
                        patch_number=0,
                        version_type="minor",
                        status="approved",
                        is_official=True,
                        change_summary="Updated calibration telemetry and HEPA sanitation compliance",
                        extracted_text=v3_text,
                        file_name="Enterprise_SOP_v1.2.0.pdf",
                        file_size=1258291,
                        mime_type="application/pdf",
                        author=user,
                    )

                    # Resolved lock on Document 1
                    DocumentLock.objects.create(
                        tenant=tenant,
                        document=doc1,
                        base_version=ver2,
                        locked_by=user,
                        lock_type="exclusive",
                        status="checked_in",
                        checkout_note="Routine revision to include SCADA and telemetry guidelines",
                        unlocked_at=timezone.now(),
                        unlocked_by=user,
                    )

                    # Active Branch on Document 1
                    DocumentBranch.objects.create(
                        tenant=tenant,
                        document=doc1,
                        name="Quarantine-Spike-2027",
                        base_version=ver3,
                        branch_type="what_if",
                        status="active",
                        created_by=user,
                        description="Simulation branch evaluating automated robotic quarantine bypass protocol.",
                    )

                    # Document 2: Mutual NDA Master (Published, Major.Minor Scheme, Currently Checked Out)
                    doc2 = Document.objects.create(
                        tenant=tenant,
                        title="Mutual Non-Disclosure Agreement (NDA) Master",
                        document_type="contract",
                        classification="confidential",
                        status="published",
                        versioning_scheme="major_minor",
                        current_version_label="2.0",
                        current_version_no=2,
                        owner=user,
                        department=org_unit,
                        is_locked=True,
                        locked_by=user,
                        locked_at=timezone.now(),
                        description="Standard corporate reciprocal confidentiality and proprietary trade secret agreement.",
                    )

                    nda_v1_text = (
                        "Article 1: Confidentiality Obligations\n"
                        "Both parties agree to hold confidential information in strict confidence for three (3) years.\n\n"
                        "Article 2: Jurisdiction\n"
                        "Disputes shall be settled under the laws of the State of Delaware."
                    )
                    nda_ver1 = DocumentVersion.objects.create(
                        tenant=tenant,
                        document=doc2,
                        version_label="1.0",
                        major_number=1,
                        minor_number=0,
                        patch_number=0,
                        version_type="major",
                        status="superseded",
                        is_official=False,
                        change_summary="Original 3-year mutual NDA template",
                        extracted_text=nda_v1_text,
                        file_name="Mutual_NDA_v1.0.pdf",
                        file_size=524288,
                        mime_type="application/pdf",
                        author=user,
                    )

                    nda_v2_text = (
                        "Article 1: Confidentiality Obligations\n"
                        "Both parties agree to hold confidential information in strict confidence for five (5) years.\n"
                        "Article 1.1: GDPR & Data Privacy Safeguards apply to all shared personally identifiable data.\n\n"
                        "Article 2: Jurisdiction\n"
                        "Disputes shall be settled by binding arbitration under AAA rules."
                    )
                    nda_ver2 = DocumentVersion.objects.create(
                        tenant=tenant,
                        document=doc2,
                        version_label="2.0",
                        major_number=2,
                        minor_number=0,
                        patch_number=0,
                        version_type="major",
                        status="approved",
                        is_official=True,
                        change_summary="Extended term to 5 years, AAA arbitration, and GDPR clauses",
                        extracted_text=nda_v2_text,
                        file_name="Mutual_NDA_v2.0.pdf",
                        file_size=629145,
                        mime_type="application/pdf",
                        author=user,
                    )

                    # Active Lock on Document 2
                    DocumentLock.objects.create(
                        tenant=tenant,
                        document=doc2,
                        base_version=nda_ver2,
                        locked_by=user,
                        lock_type="exclusive",
                        status="active",
                        checkout_note="Drafting cross-border EU-US data privacy framework addendum",
                    )

                    # Document 3: Technical Architecture Specification (In Review, Semantic Scheme)
                    doc3 = Document.objects.create(
                        tenant=tenant,
                        title="Technical Architecture & Cloud Topology Specification",
                        document_type="specification",
                        classification="restricted",
                        status="in_review",
                        versioning_scheme="semantic",
                        current_version_label="0.9.1",
                        current_version_no=2,
                        owner=user,
                        department=org_unit,
                        description="Comprehensive microservice topology, queueing infrastructure, and network segmentation plan.",
                    )

                    spec_v1_text = (
                        "Architecture Overview:\n"
                        "- Primary Database: MariaDB Cluster\n"
                        "- In-memory Cache: Standalone Redis\n"
                        "- Asynchronous Worker: Single Celery worker instance"
                    )
                    spec_ver1 = DocumentVersion.objects.create(
                        tenant=tenant,
                        document=doc3,
                        version_label="0.9.0",
                        major_number=0,
                        minor_number=9,
                        patch_number=0,
                        version_type="minor",
                        status="superseded",
                        is_official=False,
                        change_summary="Initial infrastructure topology draft",
                        extracted_text=spec_v1_text,
                        file_name="Cloud_Architecture_v0.9.0.docx",
                        file_size=2097152,
                        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        author=user,
                    )

                    spec_v2_text = (
                        "Architecture Overview:\n"
                        "- Primary Database: MariaDB High-Availability Galera Cluster\n"
                        "- In-memory Cache: Redis Sentinel HA Trio\n"
                        "- Asynchronous Worker: Autoscaling Celery worker pools with Flower monitoring"
                    )
                    spec_ver2 = DocumentVersion.objects.create(
                        tenant=tenant,
                        document=doc3,
                        version_label="0.9.1",
                        major_number=0,
                        minor_number=9,
                        patch_number=1,
                        version_type="patch",
                        status="pending_review",
                        is_official=False,
                        change_summary="Upgraded cache and worker architecture to HA cluster specifications",
                        extracted_text=spec_v2_text,
                        file_name="Cloud_Architecture_v0.9.1.docx",
                        file_size=2306867,
                        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        author=user,
                    )

                    # Merged Branch on Document 3
                    DocumentBranch.objects.create(
                        tenant=tenant,
                        document=doc3,
                        name="Feature-Kubernetes-Orchestration",
                        base_version=spec_ver1,
                        branch_type="variant",
                        status="merged",
                        created_by=user,
                        merged_at=timezone.now(),
                        description="Evaluation of Helm charts and container orchestration topologies (merged into 0.9.1).",
                    )

                # ---------------------------------------------------------
                # 13.3 Approval & Review Workflow Demo Data
                # ---------------------------------------------------------
                if not DocumentApprovalWorkflow.objects.filter(tenant=tenant).exists():
                    self.stdout.write(f"Seeding Document Approval Workflow records for tenant '{tenant.slug}'...")

                    doc_target = Document.objects.filter(tenant=tenant).first()
                    doc_ver_target = DocumentVersion.objects.filter(tenant=tenant, document=doc_target).first() if doc_target else None

                    if doc_target:
                        # 1. In-Progress Sequential Approval Workflow
                        wf1 = DocumentApprovalWorkflow.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            version=doc_ver_target,
                            title="Standard Operating Procedure (SOP) Regulatory Sign-Off",
                            workflow_type="sequential",
                            status="pending",
                            urgency="high",
                            current_stage=1,
                            total_stages=2,
                            target_turnaround_hours=48,
                            initiator=user,
                            department=org_unit,
                            due_date=timezone.now() + timezone.timedelta(days=2),
                            requires_all_comments_resolved=True,
                            allow_emergency_bypass=True,
                            definition_json='{"nodes":[{"id":"start","label":"Draft"},{"id":"stage1","label":"QA Review"},{"id":"stage2","label":"Executive Signoff"}]}',
                        )

                        req1 = DocumentApprovalRequest.objects.create(
                            tenant=tenant,
                            workflow=wf1,
                            stage_number=1,
                            stage_name="QA & Regulatory Compliance Audit",
                            stage_type="sequential",
                            order=1,
                            approver=user,
                            status="approved",
                            decided_at=timezone.now(),
                            decision_comments="Verified all procedural steps comply with ISO 9001:2015 and current GMP standards.",
                        )

                        req2 = DocumentApprovalRequest.objects.create(
                            tenant=tenant,
                            workflow=wf1,
                            stage_number=2,
                            stage_name="Executive Management Sign-Off",
                            stage_type="final_signoff",
                            order=1,
                            approver=user,
                            status="pending",
                            due_date=timezone.now() + timezone.timedelta(days=2),
                        )

                        # 2. Approved Parallel Workflow
                        wf2 = DocumentApprovalWorkflow.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            version=doc_ver_target,
                            title="Vendor Master Services Agreement Executive Approval",
                            workflow_type="parallel",
                            status="approved",
                            urgency="medium",
                            current_stage=1,
                            total_stages=1,
                            target_turnaround_hours=72,
                            initiator=user,
                            department=org_unit,
                            completed_at=timezone.now(),
                            requires_all_comments_resolved=False,
                            allow_emergency_bypass=False,
                        )

                        req3 = DocumentApprovalRequest.objects.create(
                            tenant=tenant,
                            workflow=wf2,
                            stage_number=1,
                            stage_name="Legal & Corporate Risk Sign-Off",
                            stage_type="parallel_all",
                            order=1,
                            approver=user,
                            status="approved",
                            decided_at=timezone.now(),
                            decision_comments="Commercial terms and indemnity provisions accepted.",
                        )

                        # 3. Electronic Signatures
                        sig1 = DocumentSignature.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            version=doc_ver_target,
                            approval_request=req1,
                            signer=user,
                            signer_name="Dr. Eleanor Vance",
                            signer_title="VP of Quality & Regulatory Affairs",
                            signer_email="eleanor.vance@example.com",
                            signature_type="digital_cert",
                            signature_meaning="approval",
                            document_checksum="d2c3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3",
                            certificate_serial="US-FDA-PKI-2026-994821",
                            is_valid=True,
                        )

                        sig2 = DocumentSignature.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            version=doc_ver_target,
                            signer=user,
                            signer_name="Marcus Sterling",
                            signer_title="Chief Technology Officer",
                            signer_email="marcus.sterling@example.com",
                            signature_type="click_to_sign",
                            signature_meaning="authorship",
                            document_checksum="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
                            is_valid=True,
                        )

                        # 4. Review Comments & Markup Annotations
                        comm1 = DocumentReviewComment.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            version=doc_ver_target,
                            workflow=wf1,
                            author=user,
                            annotation_type="redline",
                            page_number=2,
                            coordinate_ref="150,220,400,60",
                            selected_text="Production batch release cycle turnaround target of 4 hours",
                            content="Please clarify whether emergency expedited protocols are covered by this release threshold.",
                            status="open",
                            is_blocking=True,
                        )

                        comm2 = DocumentReviewComment.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            version=doc_ver_target,
                            workflow=wf1,
                            author=user,
                            annotation_type="highlight",
                            page_number=4,
                            coordinate_ref="100,500,300,40",
                            selected_text="Audit log and revision history retention floor: 7 years minimum",
                            content="Verified against corporate archival standard.",
                            status="resolved",
                            is_blocking=False,
                            resolved_by=user,
                            resolved_at=timezone.now(),
                            resolution_notes="Confirmed compliant with regulatory retention baseline.",
                        )

                        DocumentReviewComment.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            version=doc_ver_target,
                            workflow=wf1,
                            author=user,
                            annotation_type="inline_comment",
                            page_number=2,
                            parent=comm1,
                            content="Agreed, we will explicitly detail the expedited batch protocol in Section 2.3.",
                            status="open",
                            is_blocking=False,
                        )

                self.stdout.write(self.style.SUCCESS(f"Successfully processed Document Management seeding for '{tenant.slug}'."))

        self.stdout.write(
            self.style.SUCCESS(
                "Document Management System seeding complete.\n"
                "Tenant credentials notice: Log in as a tenant user/admin (e.g. admin_acme / password) to access records."
            )
        )
