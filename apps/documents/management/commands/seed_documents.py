from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Party, Tenant
from apps.documents.models import (
    DocumentDraft,
    DocumentTemplate,
    DraftCollaboration,
    TemplateSection,
)
from apps.documents.views._helpers import count_words


class Command(BaseCommand):
    help = "Seed demo data for the Document Management System (DMS) module"

    def handle(self, *args, **options):
        User = get_user_model()
        tenants = Tenant.objects.all()

        if not tenants.exists():
            self.stdout.write(self.style.WARNING("No tenants found in database. Run seed_core and seed_accounts first."))
            return

        for tenant in tenants:
            if DocumentTemplate.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"Documents already seeded for tenant '{tenant.slug}'. Skipping.")
                continue

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
                self.stdout.write(f"Seeding Document Management records for tenant '{tenant.slug}'...")

                # 1. Master Document Templates
                sop_content = (
                    "# Standard Operating Procedure: {{sop_title}}\n\n"
                    "Organization: {{company_name}}\n"
                    "Author: {{author_name}}\n\n"
                    "## 1. Purpose & Scope\n"
                    "This SOP defines the standardized operational protocol for production execution.\n\n"
                    "## 2. Responsibilities\n"
                    "All authorized departmental staff must adhere to the steps outlined herein.\n"
                )
                sop_tmpl = DocumentTemplate(
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
                sop_tmpl.save()

                nda_content = (
                    "# Mutual Non-Disclosure Agreement\n\n"
                    "Between: {{company_name}}\n"
                    "And: {{party_name}}\n\n"
                    "Effective Date: {{effective_date}}\n\n"
                    "1. Confidential Information\n"
                    "The parties agree that all proprietary documentation disclosed shall remain confidential for 5 years.\n"
                )
                nda_tmpl = DocumentTemplate(
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
                nda_tmpl.save()

                memo_tmpl = DocumentTemplate(
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
                memo_tmpl.save()

                # 2. Template Sections
                sec1 = TemplateSection(
                    tenant=tenant,
                    template=sop_tmpl,
                    title="Section 1: Purpose, Scope and Applicable Standards",
                    section_type="body_section",
                    content="All operations conducted under this procedure must conform to ISO 9001 quality management guidelines.",
                    order=10,
                    is_locked=True,
                    is_mandatory=True,
                )
                sec1.save()

                sec2 = TemplateSection(
                    tenant=tenant,
                    template=sop_tmpl,
                    title="Section 2: Execution Protocol & Steps",
                    section_type="body_section",
                    content="1. Inspect equipment baseline calibration.\n2. Verify environmental temperature and humidity.\n3. Execute processing sequence.\n4. Log parameters in batch record.",
                    order=20,
                    is_locked=False,
                    is_mandatory=True,
                )
                sec2.save()

                sec3 = TemplateSection(
                    tenant=tenant,
                    template=nda_tmpl,
                    title="Clause 3: Non-Disclosure Obligations and Remedies",
                    section_type="boilerplate",
                    content="The Receiving Party shall protect the Disclosing Party's Confidential Information with at least the degree of care it uses for its own sensitive data, but no less than reasonable care.",
                    order=10,
                    is_locked=True,
                    is_mandatory=True,
                )
                sec3.save()

                sec4 = TemplateSection(
                    tenant=tenant,
                    template=None,
                    title="Standard Corporate Legal Disclaimer",
                    section_type="disclaimer",
                    content="This communication contains confidential and privileged information intended solely for the recipient.",
                    order=100,
                    is_locked=True,
                    is_mandatory=False,
                )
                sec4.save()

                # 3. Document Drafts (Version Zero)
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
                draft1 = DocumentDraft(
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
                draft1.save()

                draft2_text = (
                    "# Mutual Non-Disclosure Agreement\n\n"
                    f"Between: {tenant.name}\n"
                    f"And: {party.name if party else 'Acme Vendor Partner'}\n\n"
                    "Effective Date: 2026-11-22\n\n"
                    "1. Confidential Information\n"
                    "The parties agree that all proprietary documentation disclosed shall remain confidential for 5 years.\n"
                    "Notice period for breach notifications shall be within 30 calendar days.\n"
                )
                draft2 = DocumentDraft(
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
                draft2.save()

                draft3_text = (
                    "MEMORANDUM\n\n"
                    "TO: Information Technology & Operations\n"
                    "FROM: Security & Compliance Committee\n"
                    "DATE: 2026-11-22\n"
                    "SUBJECT: Multi-Factor Authentication & Remote Session Protocols\n\n"
                    "Please be advised that all hybrid and remote staff members must activate hardware tokens by month end.\n"
                )
                draft3 = DocumentDraft(
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
                draft3.save()

                # 4. Draft Collaboration Feedback & Suggestions
                collab1 = DraftCollaboration(
                    tenant=tenant,
                    draft=draft1,
                    entry_type="comment",
                    status="open",
                    author=user,
                    section_anchor="Section 2: Responsibilities",
                    comment_text="Ensure inspection sampling plan references ISO 2859-1 General Inspection Level II.",
                )
                collab1.save()

                collab2 = DraftCollaboration(
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
                collab2.save()

                collab3 = DraftCollaboration(
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
                collab3.save()

                self.stdout.write(self.style.SUCCESS(f"Successfully seeded Document Management for '{tenant.slug}'."))
