import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Party, Tenant
from apps.documents.models import (
    CoauthorSession,
    DlpIncident,
    DlpPolicy,
    Document,
    DocumentAccessPermission,
    DocumentActivity,
    DocumentApprovalRequest,
    DocumentApprovalWorkflow,
    DocumentBatchImport,
    DocumentBranch,
    DocumentDraft,
    DocumentDrmPolicy,
    DocumentFolder,
    DocumentLock,
    DocumentMetadataValue,
    DocumentOcrJob,
    DocumentRelationship,
    DocumentReviewComment,
    DocumentSavedSearch,
    DocumentSearchAlert,
    DocumentSearchQueryLog,
    DocumentSearchSynonym,
    DocumentShare,
    DocumentSignature,
    DocumentTask,
    DocumentTemplate,
    DocumentVersion,
    DraftCollaboration,
    MetadataSchema,
    StorageVolume,
    TaxonomyTerm,
    TemplateSection,
    WatermarkPolicy,
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
            DocumentActivity.objects.all().delete()
            DocumentTask.objects.all().delete()
            CoauthorSession.objects.all().delete()
            DocumentShare.objects.all().delete()
            DlpIncident.objects.all().delete()
            DlpPolicy.objects.all().delete()
            DocumentDrmPolicy.objects.all().delete()
            WatermarkPolicy.objects.all().delete()
            DocumentAccessPermission.objects.all().delete()
            DocumentSearchAlert.objects.all().delete()
            DocumentSavedSearch.objects.all().delete()
            DocumentSearchSynonym.objects.all().delete()
            DocumentSearchQueryLog.objects.all().delete()
            DocumentOcrJob.objects.all().delete()
            DocumentMetadataValue.objects.all().delete()
            TaxonomyTerm.objects.all().delete()
            MetadataSchema.objects.all().delete()
            DocumentRelationship.objects.all().delete()
            DocumentBatchImport.objects.all().delete()
            DocumentFolder.objects.all().delete()
            StorageVolume.objects.all().delete()
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

                # ---------------------------------------------------------
                # 13.4 Document Storage & Repository Demo Data
                # ---------------------------------------------------------
                if not StorageVolume.objects.filter(tenant=tenant).exists():
                    self.stdout.write(f"Seeding Document Storage & Repository records for tenant '{tenant.slug}'...")

                    # 1. Storage Volumes
                    vol1 = StorageVolume.objects.create(
                        tenant=tenant,
                        name="Primary NVMe High-Performance Store",
                        code="VOL-HOT-01",
                        backend_type="local_filesystem",
                        tier="hot",
                        base_path="/var/nav_erp/storage/hot_tier",
                        region="us-east-1",
                        max_capacity_bytes=107374182400,  # 100 GB
                        utilized_bytes=21474836480,       # 20 GB
                        warning_threshold_pct=85,
                        is_default=True,
                        is_active=True,
                        compression_type="none",
                        deduplication_enabled=True,
                        encryption_type="aes_256",
                        description="Primary low-latency local SSD volume for active document authoring, revisions, and approval workflows.",
                    )

                    vol2 = StorageVolume.objects.create(
                        tenant=tenant,
                        name="AWS S3 Standard Object Repository",
                        code="VOL-S3-01",
                        backend_type="s3_compatible",
                        tier="warm",
                        base_path="nav-erp-dms-standard",
                        region="us-east-1",
                        endpoint_url="https://s3.us-east-1.amazonaws.com",
                        max_capacity_bytes=536870912000,  # 500 GB
                        utilized_bytes=53687091200,       # 50 GB
                        warning_threshold_pct=85,
                        is_default=False,
                        is_active=True,
                        compression_type="zstandard",
                        deduplication_enabled=True,
                        encryption_type="kms_managed",
                        rollover_volume=vol1,
                        description="Warm cloud object repository for published documents, operational reports, and multi-year records.",
                    )

                    StorageVolume.objects.create(
                        tenant=tenant,
                        name="Deep Compliance Glacier Archive",
                        code="VOL-GLAC-01",
                        backend_type="air_gapped",
                        tier="glacier_archive",
                        base_path="/mnt/secure_vault/cold_archive",
                        region="us-east-1",
                        max_capacity_bytes=2147483648000,  # 2 TB
                        utilized_bytes=107374182400,       # 100 GB
                        warning_threshold_pct=90,
                        is_default=False,
                        is_active=True,
                        compression_type="gzip",
                        deduplication_enabled=True,
                        encryption_type="aes_256",
                        description="Air-gapped long-term compliance storage for superseded contracts, tax records, and regulatory archives.",
                    )

                    # 2. Folder Taxonomy & Hierarchy
                    fld_root = DocumentFolder.objects.create(
                        tenant=tenant,
                        name="Corporate Repository",
                        slug="corporate",
                        department=org_unit,
                        owner=user,
                        color_code="#2563EB",
                        icon_name="briefcase",
                        default_classification="internal",
                        default_document_type="general",
                        is_system=True,
                        is_active=True,
                        description="Master root directory for corporate organization, governance, and operating documentation.",
                    )

                    fld_legal = DocumentFolder.objects.create(
                        tenant=tenant,
                        parent=fld_root,
                        name="Legal & Corporate Agreements",
                        slug="legal-agreements",
                        department=org_unit,
                        owner=user,
                        color_code="#4F46E5",
                        icon_name="shield",
                        default_classification="confidential",
                        default_document_type="contract",
                        is_active=True,
                        description="Repository folder holding Master Services Agreements, NDAs, and corporate governance contracts.",
                    )

                    fld_sop = DocumentFolder.objects.create(
                        tenant=tenant,
                        parent=fld_root,
                        name="Standard Operating Procedures (SOP)",
                        slug="sop-library",
                        department=org_unit,
                        owner=user,
                        color_code="#059669",
                        icon_name="file-text",
                        default_classification="internal",
                        default_document_type="sop",
                        is_active=True,
                        description="Authorized procedures, work instructions, and quality management manuals.",
                    )

                    DocumentFolder.objects.create(
                        tenant=tenant,
                        parent=fld_root,
                        name="Engineering & Technical Specifications",
                        slug="engineering-specs",
                        department=org_unit,
                        owner=user,
                        color_code="#D97706",
                        icon_name="cpu",
                        default_classification="restricted",
                        default_document_type="technical",
                        is_active=True,
                        description="Product blueprints, technical specifications, and system architecture manuals.",
                    )

                    # Smart Virtual Folder
                    DocumentFolder.objects.create(
                        tenant=tenant,
                        name="Confidential Contracts Vault",
                        slug="confidential-contracts-vault",
                        department=org_unit,
                        owner=user,
                        color_code="#7C3AED",
                        icon_name="sparkles",
                        default_classification="confidential",
                        default_document_type="contract",
                        is_virtual=True,
                        virtual_criteria_json='{"classification": "confidential", "document_type": "contract"}',
                        is_active=True,
                        description="Smart Virtual Folder dynamically aggregating all confidential commercial contracts across departments.",
                    )

                    # 3. Document Relationships
                    tenant_docs = Document.objects.filter(tenant=tenant).order_by("created_at")
                    if tenant_docs.count() >= 2:
                        doc_a = tenant_docs[0]
                        doc_b = tenant_docs[1]

                        DocumentRelationship.objects.create(
                            tenant=tenant,
                            source_document=doc_a,
                            target_document=doc_b,
                            relationship_type="references",
                            dependency_level="contractual",
                            is_bidirectional=True,
                            description=f"{doc_a.title} cross-references terms and specifications in {doc_b.title}.",
                            created_by=user,
                        )

                        if tenant_docs.count() >= 3:
                            doc_c = tenant_docs[2]
                            DocumentRelationship.objects.create(
                                tenant=tenant,
                                source_document=doc_a,
                                target_document=doc_c,
                                relationship_type="contract_exhibit",
                                dependency_level="strict_blocking",
                                is_bidirectional=True,
                                description=f"{doc_c.title} serves as Exhibit Schedule A to {doc_a.title}.",
                                created_by=user,
                            )

                    # 4. Document Batch Imports
                    DocumentBatchImport.objects.create(
                        tenant=tenant,
                        batch_name="2026 Q1 Corporate Agreements Migration",
                        source_type="zip_archive",
                        target_folder=fld_legal,
                        storage_volume=vol1,
                        status="completed",
                        total_files_detected=12,
                        processed_files_count=12,
                        success_files_count=12,
                        failed_files_count=0,
                        total_bytes_processed=14680064,  # ~14 MB
                        log_summary=(
                            f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Ingestion job initialized.\n"
                            "Archive inspection: 12 valid documents identified in ZIP container.\n"
                            "Extraction completed into target folder '/corporate/legal-agreements/'.\n"
                            "Integrity check: 100% SHA-256 checksums verified."
                        ),
                        created_by=user,
                        started_at=timezone.now(),
                        completed_at=timezone.now(),
                    )

                    DocumentBatchImport.objects.create(
                        tenant=tenant,
                        batch_name="Legacy Standard Operating Procedures Archive",
                        source_type="legacy_migration",
                        target_folder=fld_sop,
                        storage_volume=vol2,
                        status="queued",
                        total_files_detected=8,
                        processed_files_count=0,
                        success_files_count=0,
                        failed_files_count=0,
                        total_bytes_processed=0,
                        log_summary="Ingestion job registered in queue. Waiting for extraction trigger.",
                        created_by=user,
                    )

                # ---------------------------------------------------------
                # 13.5 Metadata & Indexing Demo Data
                # ---------------------------------------------------------
                if not MetadataSchema.objects.filter(tenant=tenant).exists():
                    self.stdout.write(f"Seeding Metadata & Indexing records for tenant '{tenant.slug}'...")

                    nda_fields = [
                        {"key": "counterparty", "label": "Counterparty Name", "data_type": "text", "required": True},
                        {"key": "effective_date", "label": "Effective Date", "data_type": "date", "required": True},
                        {"key": "expiration_date", "label": "Expiration Date", "data_type": "date", "required": False},
                        {"key": "contract_value", "label": "Contract Value", "data_type": "decimal", "required": False},
                        {"key": "governing_law", "label": "Governing Jurisdiction", "data_type": "dropdown", "choices": ["Delaware", "California", "New York", "England & Wales"]},
                        {"key": "confidentiality_years", "label": "Confidentiality Term (Years)", "data_type": "integer", "default": 5},
                    ]
                    schema_nda = MetadataSchema.objects.create(
                        tenant=tenant,
                        name="Corporate NDA & Confidentiality Schema",
                        code="NDA_SCHEMA",
                        description="Standardized legal metadata properties for non-disclosure agreements and confidentiality riders.",
                        target_type="contract",
                        inheritance_mode="folder_default",
                        fields_definition_json=json.dumps(nda_fields, indent=2),
                        is_required=True,
                        allow_custom_fields=True,
                        created_by=user,
                    )

                    sop_fields = [
                        {"key": "sop_code", "label": "SOP Identifier", "data_type": "text", "required": True},
                        {"key": "iso_clause", "label": "ISO Standard Clause", "data_type": "text", "required": False},
                        {"key": "review_cycle_months", "label": "Review Cycle (Months)", "data_type": "integer", "default": 12},
                        {"key": "safety_critical", "label": "Safety Critical Procedure", "data_type": "boolean", "default": False},
                    ]
                    schema_sop = MetadataSchema.objects.create(
                        tenant=tenant,
                        name="Standard Operating Procedure (SOP) Metadata",
                        code="SOP_SCHEMA",
                        description="Operational and quality compliance metadata for SOPs and work instructions.",
                        target_type="sop",
                        inheritance_mode="folder_strict",
                        fields_definition_json=json.dumps(sop_fields, indent=2),
                        is_required=False,
                        allow_custom_fields=True,
                        created_by=user,
                    )

                    # 2. Controlled Vocabularies & Thesauri
                    tax_legal = TaxonomyTerm.objects.create(
                        tenant=tenant,
                        name="Legal & Corporate Governance Thesaurus",
                        term_code="TAX_LEGAL",
                        category="legal",
                        description="Controlled vocabulary covering contract types, covenants, and legal jurisdiction.",
                        synonyms_json=json.dumps(["Legal", "Law", "Corporate Counsel", "Jurisprudence"]),
                        external_code="LEGAL-THES-2026",
                        is_governed=True,
                        created_by=user,
                    )

                    tax_nda = TaxonomyTerm.objects.create(
                        tenant=tenant,
                        name="Non-Disclosure & Confidentiality",
                        term_code="TAX_NDA",
                        category="legal",
                        parent=tax_legal,
                        description="Bilateral and unilateral secrecy and non-disclosure instruments.",
                        synonyms_json=json.dumps(["NDA", "Confidentiality Agreement", "Proprietary Info Agreement", "MNDA"]),
                        external_code="ISO 27001:A.13.2.4",
                        is_governed=True,
                        created_by=user,
                    )

                    tax_msa = TaxonomyTerm.objects.create(
                        tenant=tenant,
                        name="Master Services Agreements",
                        term_code="TAX_MSA",
                        category="legal",
                        parent=tax_legal,
                        description="Umbrella commercial contracts governing client and vendor service engagements.",
                        synonyms_json=json.dumps(["MSA", "Framework Agreement", "Service Contract"]),
                        is_governed=True,
                        created_by=user,
                    )

                    tax_compliance = TaxonomyTerm.objects.create(
                        tenant=tenant,
                        name="Quality & Regulatory Compliance",
                        term_code="TAX_COMPLIANCE",
                        category="compliance",
                        description="Standard terms relating to ISO, OSHA, FDA, and enterprise audits.",
                        synonyms_json=json.dumps(["Compliance", "Audit", "Regulatory", "Quality Assurance"]),
                        external_code="ISO 9001:2015",
                        is_governed=True,
                        created_by=user,
                    )

                    tax_sop = TaxonomyTerm.objects.create(
                        tenant=tenant,
                        name="Standard Operating Procedures",
                        term_code="TAX_SOP",
                        category="compliance",
                        parent=tax_compliance,
                        description="Formal documentation of operational methods and work instructions.",
                        synonyms_json=json.dumps(["SOP", "Work Instruction", "Operating Procedure"]),
                        is_governed=True,
                        created_by=user,
                    )

                    # 3. Document Metadata Values
                    docs = Document.objects.filter(tenant=tenant).order_by("pk")
                    doc1 = docs.first()
                    doc2 = docs.last()

                    if doc1:
                        DocumentMetadataValue.objects.create(
                            tenant=tenant,
                            document=doc1,
                            schema=schema_nda,
                            field_name="counterparty",
                            field_label="Counterparty Name",
                            data_type="text",
                            value_text="Acme International Holdings LLC",
                            source="manual_entry",
                            validation_status="valid",
                            last_validated_at=timezone.now(),
                            updated_by=user,
                        )
                        DocumentMetadataValue.objects.create(
                            tenant=tenant,
                            document=doc1,
                            schema=schema_nda,
                            field_name="contract_value",
                            field_label="Contract Value",
                            data_type="decimal",
                            value_number=250000.0000,
                            source="manual_entry",
                            validation_status="valid",
                            last_validated_at=timezone.now(),
                            updated_by=user,
                        )
                        DocumentMetadataValue.objects.create(
                            tenant=tenant,
                            document=doc1,
                            schema=schema_nda,
                            field_name="effective_date",
                            field_label="Effective Date",
                            data_type="date",
                            value_date=timezone.now().date(),
                            source="folder_inherited",
                            validation_status="valid",
                            last_validated_at=timezone.now(),
                            updated_by=user,
                        )

                    if doc2 and doc2 != doc1:
                        DocumentMetadataValue.objects.create(
                            tenant=tenant,
                            document=doc2,
                            schema=schema_sop,
                            field_name="sop_code",
                            field_label="SOP Identifier",
                            data_type="text",
                            value_text="SOP-PROD-2026-001",
                            source="template_inherited",
                            validation_status="valid",
                            last_validated_at=timezone.now(),
                            updated_by=user,
                        )
                        DocumentMetadataValue.objects.create(
                            tenant=tenant,
                            document=doc2,
                            schema=schema_sop,
                            field_name="safety_critical",
                            field_label="Safety Critical Procedure",
                            data_type="boolean",
                            value_boolean=True,
                            source="manual_entry",
                            validation_status="valid",
                            last_validated_at=timezone.now(),
                            updated_by=user,
                        )

                    # 4. Document OCR Jobs
                    if doc1:
                        ocr_text_doc1 = (
                            f"CONFIDENTIAL NON-DISCLOSURE AGREEMENT\n"
                            f"DOCUMENT IDENTIFIER: {doc1.number}\n"
                            f"BETWEEN: {tenant.name} AND Acme International Holdings LLC\n"
                            f"EFFECTIVE DATE: {timezone.now().strftime('%Y-%m-%d')}\n\n"
                            "1. DEFINITION OF CONFIDENTIAL INFORMATION.\n"
                            "All trade secrets, algorithms, customer lists, and financial forecasts.\n"
                            "2. TERM AND TERMINATION.\n"
                            "The confidentiality obligations shall endure for a duration of five (5) years.\n"
                        )
                        DocumentOcrJob.objects.create(
                            tenant=tenant,
                            document=doc1,
                            version=doc1.versions.first() if hasattr(doc1, "versions") else None,
                            status="completed",
                            ocr_engine="azure_document_intelligence",
                            extracted_full_text=ocr_text_doc1,
                            confidence_score=98.20,
                            page_count=3,
                            suggested_category="Legal Contracts & Agreements",
                            suggested_tags_json=json.dumps(["NDA", "Confidential", "Legal", "Acme"]),
                            extracted_entities_json=json.dumps({
                                "counterparty": "Acme International Holdings LLC",
                                "term_duration": "5 years",
                                "effective_date": timezone.now().strftime("%Y-%m-%d"),
                                "jurisdiction": "Delaware"
                            }, indent=2),
                            has_handwriting=False,
                            has_barcode=True,
                            processing_duration_ms=1450,
                            applied_to_document=True,
                            created_by=user,
                        )

                    if doc2 and doc2 != doc1:
                        DocumentOcrJob.objects.create(
                            tenant=tenant,
                            document=doc2,
                            version=doc2.versions.first() if hasattr(doc2, "versions") else None,
                            status="queued",
                            ocr_engine="tesseract_ocr",
                            page_count=2,
                            confidence_score=0.00,
                            created_by=user,
                        )

                # --- 13.6 Search & Discovery Seeding ---
                if not DocumentSavedSearch.objects.filter(tenant=tenant).exists():
                    self.stdout.write(f"Seeding Search & Discovery for '{tenant.slug}'...")
                    svd1 = DocumentSavedSearch.objects.create(
                        tenant=tenant,
                        name="Active Confidential Contracts",
                        description="Monitors all active confidential contracts in legal and procurement",
                        owner=user,
                        visibility="public",
                        query_text="agreement contract liability",
                        filters_json=json.dumps({"document_type": "contract", "classification": "confidential", "status": "approved"}),
                        facet_filters_json=json.dumps({"status": ["approved"]}),
                        sort_by="relevance",
                        sort_order="desc",
                        is_pinned=True,
                        is_favorite=True,
                        is_active=True,
                        run_count=18,
                        total_results_last_run=4,
                        last_run_at=timezone.now(),
                    )
                    svd2 = DocumentSavedSearch.objects.create(
                        tenant=tenant,
                        name="Technical SOPs & Engineering Guides",
                        description="Standard operating procedures for IT, security, and quality",
                        owner=user,
                        visibility="shared_department",
                        query_text="sop procedure specification",
                        filters_json=json.dumps({"document_type": "sop", "status": "approved"}),
                        facet_filters_json=json.dumps({}),
                        sort_by="updated_at_desc",
                        sort_order="desc",
                        is_pinned=True,
                        is_favorite=False,
                        is_active=True,
                        run_count=9,
                        total_results_last_run=6,
                        last_run_at=timezone.now(),
                    )
                    svd3 = DocumentSavedSearch.objects.create(
                        tenant=tenant,
                        name="Draft Policies Pending Approval",
                        description="Corporate policies currently in draft review state",
                        owner=user,
                        visibility="private",
                        query_text="",
                        filters_json=json.dumps({"document_type": "policy", "status": "draft"}),
                        facet_filters_json=json.dumps({"status": ["draft"]}),
                        sort_by="created_at_desc",
                        sort_order="desc",
                        is_pinned=False,
                        is_favorite=False,
                        is_active=True,
                        run_count=3,
                        total_results_last_run=2,
                        last_run_at=timezone.now(),
                    )

                    DocumentSearchAlert.objects.create(
                        tenant=tenant,
                        saved_search=svd1,
                        subscriber=user,
                        frequency="daily",
                        delivery_channel="in_app",
                        is_active=True,
                        status="active",
                        notes="Daily digest of newly uploaded or revised confidential agreements",
                        new_matches_count=1,
                        last_notified_at=timezone.now(),
                        last_checked_at=timezone.now(),
                    )
                    DocumentSearchAlert.objects.create(
                        tenant=tenant,
                        saved_search=svd2,
                        subscriber=user,
                        frequency="weekly",
                        delivery_channel="email",
                        is_active=True,
                        status="active",
                        notes="Weekly summary of newly ratified engineering SOPs",
                        new_matches_count=0,
                        last_checked_at=timezone.now(),
                    )

                    synonyms_data = [
                        ("SOP", "standard operating procedure, procedure, work instruction, guidelines", "acronym", True),
                        ("NDA", "non-disclosure agreement, confidentiality agreement, secrecy agreement", "acronym", True),
                        ("PO", "purchase order, procurement order, vendor requisition", "acronym", True),
                        ("MSA", "master services agreement, master contract, framework agreement", "acronym", True),
                        ("Policy", "governance, regulation, standard, compliance rule", "domain", True),
                        ("Specs", "specifications, technical requirements, blueprint", "general", True),
                    ]
                    for term, syns, cat, bidir in synonyms_data:
                        DocumentSearchSynonym.objects.create(
                            tenant=tenant,
                            term=term,
                            synonyms=syns,
                            category=cat,
                            is_bidirectional=bidir,
                            language="en",
                            is_active=True,
                            created_by=user,
                            hit_count=5,
                        )

                    log_data = [
                        ("confidential vendor agreement", 4, 12, False, "search_hub"),
                        ("engineering sop calibration", 3, 18, False, "search_hub"),
                        ("q3 financial statements", 0, 8, True, "search_hub"),
                        ("cloud security posture policy", 2, 14, False, "quick_search"),
                        ("unknown supplier certificate xyz", 0, 6, True, "search_hub"),
                        ("iso 9001 quality audit procedure", 5, 22, False, "saved_search"),
                    ]
                    for qtext, count, ms, is_zero, source in log_data:
                        DocumentSearchQueryLog.objects.create(
                            tenant=tenant,
                            query_text=qtext,
                            user=user,
                            results_count=count,
                            is_zero_result=is_zero,
                            execution_time_ms=ms,
                            search_source=source,
                            filters_applied_json="{}",
                            session_key=f"demo_sess_{tenant.slug}",
                        )

                # --- 13.7 Document Security & Access Control Seeding ---
                if not DocumentAccessPermission.objects.filter(tenant=tenant).exists():
                    self.stdout.write(f"Seeding Document Security & Access Control for '{tenant.slug}'...")

                    doc_target = Document.objects.filter(tenant=tenant).first()
                    fld_target = DocumentFolder.objects.filter(tenant=tenant).first()
                    org_target = OrgUnit.objects.filter(tenant=tenant).first()

                    # 1. Access Permissions
                    if doc_target:
                        DocumentAccessPermission.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            grantee_type="user",
                            user=user,
                            permission_level="owner",
                            can_read=True,
                            can_write=True,
                            can_delete=True,
                            can_download=True,
                            can_print=True,
                            can_share=True,
                            is_active=True,
                            access_count=12,
                            last_accessed_at=timezone.now(),
                            notes="Primary document owner administrative grant",
                            created_by=user,
                        )
                        DocumentAccessPermission.objects.create(
                            tenant=tenant,
                            document=doc_target,
                            grantee_type="tenant_wide",
                            permission_level="viewer",
                            can_read=True,
                            can_write=False,
                            can_delete=False,
                            can_download=True,
                            can_print=True,
                            can_share=False,
                            is_active=True,
                            access_count=45,
                            last_accessed_at=timezone.now(),
                            notes="All-staff read access",
                            created_by=user,
                        )

                    if fld_target:
                        DocumentAccessPermission.objects.create(
                            tenant=tenant,
                            folder=fld_target,
                            grantee_type="org_unit" if org_target else "tenant_wide",
                            org_unit=org_target,
                            permission_level="editor",
                            can_read=True,
                            can_write=True,
                            can_delete=False,
                            can_download=True,
                            can_print=True,
                            can_share=False,
                            is_active=True,
                            access_count=8,
                            last_accessed_at=timezone.now(),
                            notes="Departmental collaboration folder grant",
                            created_by=user,
                        )

                    # 2. Watermark Policies
                    wtr1 = WatermarkPolicy.objects.create(
                        tenant=tenant,
                        name="Confidential Records Watermark",
                        description="Enforces diagonal user and timestamp watermark across all confidential documents",
                        classification="confidential",
                        document_type="all",
                        apply_to_all=False,
                        watermark_text="{{classification}} | {{user_name}} | {{timestamp}}",
                        secondary_text="Unauthorized Copying Prohibited — Trade Secret",
                        position="diagonal_center",
                        opacity_percent=25,
                        font_size=32,
                        font_color="#94a3b8",
                        rotation_angle=-45,
                        show_classification_banner=True,
                        banner_position="top",
                        enforce_on_view=True,
                        enforce_on_download=True,
                        enforce_on_print=True,
                        priority=10,
                        is_active=True,
                        created_by=user,
                    )
                    wtr2 = WatermarkPolicy.objects.create(
                        tenant=tenant,
                        name="Strictly Restricted Executive Watermark",
                        description="High-contrast forensic watermark for strictly restricted board documents",
                        classification="restricted",
                        document_type="all",
                        apply_to_all=False,
                        watermark_text="RESTRICTED | {{user_email}} | IP: {{ip_address}}",
                        secondary_text="Strictly Confidential — Personal Copy",
                        position="diagonal_center",
                        opacity_percent=40,
                        font_size=36,
                        font_color="#dc2626",
                        rotation_angle=-45,
                        show_classification_banner=True,
                        banner_position="both",
                        enforce_on_view=True,
                        enforce_on_download=True,
                        enforce_on_print=True,
                        priority=5,
                        is_active=True,
                        created_by=user,
                    )

                    # 3. DRM Policies
                    drm1 = DocumentDrmPolicy.objects.create(
                        tenant=tenant,
                        name="Confidential Contracts Anti-Exfiltration DRM",
                        description="Prohibits raw binary download and clipboard copy for confidential contracts",
                        classification="confidential",
                        document_type="contract",
                        target_document=doc_target,
                        allow_download=False,
                        allow_print=False,
                        allow_copy_paste=False,
                        screen_shield_enabled=True,
                        secure_viewer_required=True,
                        require_watermark=True,
                        max_offline_hours=0,
                        expiry_days=30,
                        ip_allowlist="10.0.0.0/8, 192.168.1.0/24",
                        geo_fencing_countries="US, CA, GB",
                        encryption_standard="AES_256_GCM",
                        is_active=True,
                        created_by=user,
                    )

                    # 4. DLP Policies
                    dlp1 = DlpPolicy.objects.create(
                        tenant=tenant,
                        name="Payment Card (PCI-DSS) Exfiltration Guard",
                        description="Detects credit card numbers in document uploads and blocks saving",
                        rule_type="built_in_pattern",
                        built_in_pattern="credit_card_pci",
                        match_threshold=1,
                        action="block_save",
                        severity="critical",
                        notify_security_officer=True,
                        notification_email="security@company.com",
                        apply_to_all_types=True,
                        incident_count=3,
                        last_triggered_at=timezone.now(),
                        is_active=True,
                        created_by=user,
                    )
                    dlp2 = DlpPolicy.objects.create(
                        tenant=tenant,
                        name="Confidential M&A Keywords Monitor",
                        description="Warns authors when saving documents containing sensitive M&A trade secret terms",
                        rule_type="sensitive_keywords",
                        sensitive_keywords=["Acquisition", "Project Titan", "Merger Agreement", "Target Valuation"],
                        match_threshold=1,
                        action="warn_author",
                        severity="high",
                        notify_security_officer=True,
                        notification_email="compliance@company.com",
                        apply_to_all_types=True,
                        incident_count=1,
                        last_triggered_at=timezone.now(),
                        is_active=True,
                        created_by=user,
                    )
                    dlp3 = DlpPolicy.objects.create(
                        tenant=tenant,
                        name="US SSN & Identity Protection Rule",
                        description="Quarantines documents containing unmasked social security numbers",
                        rule_type="built_in_pattern",
                        built_in_pattern="us_ssn",
                        match_threshold=1,
                        action="quarantine",
                        severity="high",
                        notify_security_officer=True,
                        apply_to_all_types=True,
                        incident_count=1,
                        last_triggered_at=timezone.now(),
                        is_active=True,
                        created_by=user,
                    )

                    # 5. DLP Incidents
                    if doc_target:
                        DlpIncident.objects.create(
                            tenant=tenant,
                            policy=dlp1,
                            document=doc_target,
                            triggered_by=user,
                            severity="critical",
                            action_taken="blocked",
                            matches_detected_count=2,
                            snippet_redacted="Payment card sequence detected: 4111-****-****-1111",
                            resolution_status="open",
                        )
                        DlpIncident.objects.create(
                            tenant=tenant,
                            policy=dlp2,
                            document=doc_target,
                            triggered_by=user,
                            severity="high",
                            action_taken="warned",
                            matches_detected_count=1,
                            snippet_redacted="Detected keyword 'Project Titan' in clause 3.2",
                            resolution_status="resolved_justified",
                            resolved_by=user,
                            resolution_notes="Authorized M&A corporate development team review.",
                        )

                # 6. Sub-module 13.8: Collaboration & Sharing Demo Seeding
                if not DocumentShare.objects.filter(tenant=tenant).exists():
                    doc_collab = Document.objects.filter(tenant=tenant).order_by("created_at").first()
                    version_collab = DocumentVersion.objects.filter(tenant=tenant, document=doc_collab).first() if doc_collab else None
                    review_comment_target = DocumentReviewComment.objects.filter(tenant=tenant, document=doc_collab).first() if doc_collab else None
                    org_unit_target = OrgUnit.objects.filter(tenant=tenant, is_active=True).first()

                    if doc_collab and user:
                        # 1. Document Shares
                        share1 = DocumentShare(
                            tenant=tenant,
                            document=doc_collab,
                            version=version_collab,
                            share_type="public_link",
                            access_level="view_only",
                            allow_download=True,
                            allow_print=True,
                            include_annotations=True,
                            expires_at=timezone.now() + timezone.timedelta(days=30),
                            max_uses=100,
                            access_count=14,
                            last_accessed_at=timezone.now() - timezone.timedelta(hours=2),
                            shared_by=user,
                            share_message="Please review the published terms for Q4 operations.",
                            is_active=True,
                        )
                        share1.save()

                        share2 = DocumentShare(
                            tenant=tenant,
                            document=doc_collab,
                            version=version_collab,
                            share_type="external_email",
                            access_level="comment",
                            shared_with_email="counsel@externaladvisors.com",
                            allow_download=False,
                            allow_print=True,
                            include_annotations=True,
                            expires_at=timezone.now() + timezone.timedelta(days=14),
                            max_uses=20,
                            access_count=3,
                            last_accessed_at=timezone.now() - timezone.timedelta(days=1),
                            shared_by=user,
                            share_message="External counsel review copy with comment permissions enabled.",
                            is_active=True,
                        )
                        share2.set_password("AcmeLegal2026!")
                        share2.save()

                        share3 = DocumentShare(
                            tenant=tenant,
                            document=doc_collab,
                            share_type="internal_dept",
                            access_level="edit",
                            shared_with_org_unit=org_unit_target,
                            allow_download=True,
                            allow_print=True,
                            shared_by=user,
                            is_active=True,
                        )
                        share3.save()

                        # 2. Co-Authoring Sessions
                        CoauthorSession.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            version=version_collab,
                            user=user,
                            color_code="#3B82F6",
                            status="active",
                            is_editing=True,
                            current_section="Section 3: Deliverables & Specifications",
                            client_ip="127.0.0.1",
                            cursor_position='{"page": 2, "paragraph": 4, "offset": 120}',
                        )
                        CoauthorSession.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            version=version_collab,
                            guest_name="Sarah Miller (External Auditor)",
                            color_code="#10B981",
                            status="active",
                            is_editing=False,
                            current_section="Section 1: Executive Summary",
                            client_ip="192.168.1.45",
                            cursor_position='{"page": 1, "paragraph": 2, "offset": 45}',
                        )
                        CoauthorSession.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            user=user,
                            color_code="#F59E0B",
                            status="idle",
                            is_editing=False,
                            current_section="Section 5: Pricing",
                            client_ip="10.0.0.21",
                        )

                        # 3. Document Tasks
                        task1 = DocumentTask.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            version=version_collab,
                            review_comment=review_comment_target,
                            title="Verify compliance with regulatory guidelines",
                            description="Cross-check statutory clauses against the revised ISO 27001 Annex A controls.",
                            task_type="review",
                            priority="high",
                            status="in_progress",
                            assigned_to=user,
                            assigned_by=user,
                            due_date=timezone.now().date() + timezone.timedelta(days=7),
                            reminder_date=timezone.now().date() + timezone.timedelta(days=5),
                        )
                        task2 = DocumentTask.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            version=version_collab,
                            title="Sign-off on technical architecture exhibits",
                            description="Formal technical review of API payload specifications and schemas.",
                            task_type="approval_signoff",
                            priority="urgent",
                            status="pending",
                            assigned_to=user,
                            assigned_by=user,
                            due_date=timezone.now().date() + timezone.timedelta(days=3),
                            reminder_date=timezone.now().date() + timezone.timedelta(days=2),
                        )
                        task3 = DocumentTask.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            title="Update SLA schedule penalty clauses",
                            description="Historical revision task resolved following committee consensus.",
                            task_type="revision_requested",
                            priority="medium",
                            status="completed",
                            assigned_to=user,
                            assigned_by=user,
                            due_date=timezone.now().date() - timezone.timedelta(days=2),
                            completed_at=timezone.now() - timezone.timedelta(days=1),
                            completed_by=user,
                            completion_notes="Revised wording aligned with procurement legal templates.",
                        )
                        task4 = DocumentTask.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            title="Overdue statutory data retention review",
                            description="Mandatory 30-day compliance milestone check.",
                            task_type="fact_check",
                            priority="urgent",
                            status="pending",
                            assigned_to=user,
                            assigned_by=user,
                            due_date=timezone.now().date() - timezone.timedelta(days=1),
                        )

                        # 4. Document Activities
                        DocumentActivity.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            actor=user,
                            target_user=user,
                            action_type="document_shared",
                            summary=f"Created public share link {share1.number} for '{doc_collab.title}'",
                            notification_channel="in_app",
                            is_read=True,
                            read_at=timezone.now(),
                        )
                        DocumentActivity.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            actor=user,
                            target_user=user,
                            action_type="task_assigned",
                            summary=f"Assigned task '{task1.title}' to {user.get_full_name() or user.username}",
                            notification_channel="in_app",
                            is_read=False,
                        )
                        DocumentActivity.objects.create(
                            tenant=tenant,
                            document=doc_collab,
                            guest_name="Sarah Miller (External Auditor)",
                            action_type="coauthor_joined",
                            summary=f"External collaborator joined coauthoring session on '{doc_collab.title}'",
                            notification_channel="in_app",
                            is_read=False,
                        )

                self.stdout.write(self.style.SUCCESS(f"Successfully processed Document Management seeding for '{tenant.slug}'."))

        self.stdout.write(
            self.style.SUCCESS(
                "Document Management System seeding complete.\n"
                "Tenant credentials notice: Log in as a tenant user/admin (e.g. admin_acme / password) to access records."
            )
        )
