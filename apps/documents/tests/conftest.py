"""Shared fixtures for apps.documents test suite (Module 13: Document Management System)."""
import pytest

from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection
from apps.documents.models.VersionControl.DocumentBranches import DocumentBranch
from apps.documents.models.VersionControl.DocumentLocks import DocumentLock
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion
from apps.documents.models.ApprovalWorkflow.DocumentApprovalWorkflows import DocumentApprovalWorkflow
from apps.documents.models.ApprovalWorkflow.DocumentApprovalRequests import DocumentApprovalRequest
from apps.documents.models.ApprovalWorkflow.DocumentSignatures import DocumentSignature
from apps.documents.models.ApprovalWorkflow.DocumentReviewComments import DocumentReviewComment


@pytest.fixture
def document_template(db, tenant_a, admin_user):
    """Fixture providing a baseline active DocumentTemplate in tenant_a."""
    return DocumentTemplate.objects.create(
        tenant=tenant_a,
        name="Standard Operating Procedure Template",
        template_type="sop",
        category="quality",
        content="<h2>Document Scope</h2><p>Standard quality process procedure.</p>",
        owner=admin_user,
        is_active=True,
        is_locked=False,
    )


@pytest.fixture
def template_section(db, tenant_a, document_template):
    """Fixture providing a TemplateSection belonging to document_template."""
    return TemplateSection.objects.create(
        tenant=tenant_a,
        template=document_template,
        title="Quality Assurance Clause",
        section_type="boilerplate",
        content="All actions must strictly comply with current Good Manufacturing Practices (cGMP).",
        order=10,
        is_locked=False,
        is_mandatory=True,
    )


@pytest.fixture
def document_draft(db, tenant_a, admin_user, document_template):
    """Fixture providing an active working DocumentDraft in tenant_a."""
    return DocumentDraft.objects.create(
        tenant=tenant_a,
        template=document_template,
        title="Lab Calibration Procedure",
        document_type="sop",
        draft_version="0.1",
        content="<h2>Scope</h2><p>Equipment calibration in testing suite.</p>",
        word_count=7,
        status="draft",
        author=admin_user,
        is_collaboration_locked=False,
    )


@pytest.fixture
def draft_collaboration(db, tenant_a, member_user, document_draft):
    """Fixture providing an open DraftCollaboration feedback note on document_draft."""
    return DraftCollaboration.objects.create(
        tenant=tenant_a,
        draft=document_draft,
        author=member_user,
        entry_type="suggestion",
        comment_text="Ensure to include environmental temperature tolerances.",
        selected_text="testing suite",
        replacement_text="temperature-controlled testing suite",
        status="open",
    )


@pytest.fixture
def document(db, tenant_a, admin_user):
    """Fixture providing a baseline active Document in tenant_a."""
    return Document.objects.create(
        tenant=tenant_a,
        title="Enterprise Standard Operating Procedure",
        document_type="sop",
        classification="internal",
        status="published",
        versioning_scheme="semantic",
        current_version_label="1.0.0",
        current_version_no=1,
        owner=admin_user,
        description="Core operational procedure standard.",
    )


@pytest.fixture
def document_version(db, tenant_a, admin_user, document):
    """Fixture providing an official baseline DocumentVersion for document."""
    return DocumentVersion.objects.create(
        tenant=tenant_a,
        document=document,
        version_label="1.0.0",
        major_number=1,
        minor_number=0,
        patch_number=0,
        version_type="major",
        status="approved",
        is_official=True,
        change_summary="Initial official release",
        extracted_text="Section 1: Operating protocols and safety checks baseline.",
        author=admin_user,
    )


@pytest.fixture
def document_lock(db, tenant_a, admin_user, document, document_version):
    """Fixture providing an active DocumentLock held on document."""
    doc_lock = DocumentLock.objects.create(
        tenant=tenant_a,
        document=document,
        base_version=document_version,
        locked_by=admin_user,
        lock_type="exclusive",
        status="active",
        checkout_note="Annual procedure review and updates",
    )
    document.is_locked = True
    document.locked_by = admin_user
    document.save(update_fields=["is_locked", "locked_by"])
    return doc_lock


@pytest.fixture
def document_branch(db, tenant_a, admin_user, document, document_version):
    """Fixture providing an active DocumentBranch for what-if scenarios."""
    return DocumentBranch.objects.create(
        tenant=tenant_a,
        document=document,
        name="Branch-Safety-Spike",
        base_version=document_version,
        branch_type="what_if",
        status="active",
        created_by=admin_user,
        description="Exploring high-voltage quarantine protocols.",
    )


@pytest.fixture
def approval_workflow(db, tenant_a, admin_user, document, document_version):
    """Fixture providing a pending DocumentApprovalWorkflow in tenant_a."""
    return DocumentApprovalWorkflow.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        title="Official Procedure Sign-Off Pipeline",
        workflow_type="parallel",
        status="pending",
        urgency="medium",
        initiator=admin_user,
        total_stages=2,
        current_stage=1,
        allow_emergency_bypass=True,
    )


@pytest.fixture
def approval_request(db, tenant_a, member_user, approval_workflow):
    """Fixture providing an active pending DocumentApprovalRequest."""
    return DocumentApprovalRequest.objects.create(
        tenant=tenant_a,
        workflow=approval_workflow,
        stage_number=1,
        stage_name="Department Review",
        stage_type="parallel_all",
        approver=member_user,
        status="pending",
    )


@pytest.fixture
def document_signature(db, tenant_a, member_user, document, document_version, approval_request):
    """Fixture providing a cryptographically valid DocumentSignature."""
    return DocumentSignature.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        approval_request=approval_request,
        signer=member_user,
        signer_name="Jane Doe",
        signer_title="Lead Quality Analyst",
        signer_email="jane@acme.com",
        signature_type="biometric",
        signature_meaning="approval",
        document_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        is_valid=True,
    )


@pytest.fixture
def review_comment(db, tenant_a, member_user, document, document_version, approval_workflow):
    """Fixture providing an open blocking DocumentReviewComment."""
    return DocumentReviewComment.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        workflow=approval_workflow,
        author=member_user,
        annotation_type="critique",
        page_number=2,
        coordinate_ref="120,450,200,80",
        selected_text="Verify all calibrations",
        content="Specify calibration tolerance standard ISO 17025.",
        status="open",
        is_blocking=True,
    )

