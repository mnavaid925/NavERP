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
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.StorageRepository.DocumentBatchImports import DocumentBatchImport
from apps.documents.models.MetadataIndexing.MetadataSchemas import MetadataSchema
from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue
from apps.documents.models.MetadataIndexing.TaxonomyTerms import TaxonomyTerm
from apps.documents.models.MetadataIndexing.DocumentOcrJobs import DocumentOcrJob
from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlert
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog
from apps.documents.models.CollaborationSharing.DocumentShares import DocumentShare
from apps.documents.models.CollaborationSharing.CoauthorSessions import CoauthorSession
from apps.documents.models.CollaborationSharing.DocumentTasks import DocumentTask
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.core.models import OrgUnit



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


@pytest.fixture
def document_folder(db, tenant_a, admin_user):
    """Fixture providing a root DocumentFolder in tenant_a."""
    return DocumentFolder.objects.create(
        tenant=tenant_a,
        name="Corporate Policies",
        slug="corporate-policies",
        default_classification="internal",
        description="Official enterprise governance policies.",
        color_code="#2563eb",
        icon_name="folder",
        owner=admin_user,
        is_active=True,
    )


@pytest.fixture
def child_document_folder(db, tenant_a, admin_user, document_folder):
    """Fixture providing a child DocumentFolder nested under document_folder."""
    return DocumentFolder.objects.create(
        tenant=tenant_a,
        name="HR Policies",
        slug="hr-policies",
        parent=document_folder,
        default_classification="internal",
        description="Human resource rules and operating guidelines.",
        color_code="#059669",
        icon_name="users",
        owner=admin_user,
        is_active=True,
    )


@pytest.fixture
def storage_volume(db, tenant_a):
    """Fixture providing a primary StorageVolume in tenant_a."""
    return StorageVolume.objects.create(
        tenant=tenant_a,
        name="Primary NVMe SSD Store",
        code="VOL-SSD-01",
        backend_type="local_filesystem",
        base_path="/var/storage/nav_docs",
        tier="hot",
        max_capacity_bytes=100 * 1024 * 1024 * 1024,  # 100 GB
        utilized_bytes=10 * 1024 * 1024 * 1024,      # 10 GB
        is_default=True,
        is_active=True,
    )


@pytest.fixture
def target_document(db, tenant_a, admin_user):
    """Fixture providing a second Document in tenant_a for relationship linking."""
    return Document.objects.create(
        tenant=tenant_a,
        title="Quality Manual Baseline",
        document_type="policy",
        classification="internal",
        status="published",
        versioning_scheme="semantic",
        current_version_label="1.0.0",
        current_version_no=1,
        owner=admin_user,
        description="Quality manual companion reference.",
    )


@pytest.fixture
def document_relationship(db, tenant_a, admin_user, document, target_document):
    """Fixture providing a DocumentRelationship between document and target_document."""
    return DocumentRelationship.objects.create(
        tenant=tenant_a,
        source_document=document,
        target_document=target_document,
        relationship_type="references",
        description="Procedure directly references the quality manual clause.",
        is_bidirectional=False,
        created_by=admin_user,
    )


@pytest.fixture
def document_batch_import(db, tenant_a, admin_user, storage_volume):
    """Fixture providing a DocumentBatchImport record in tenant_a."""
    return DocumentBatchImport.objects.create(
        tenant=tenant_a,
        batch_name="Q4 Historical Document Ingestion",
        source_type="zip_archive",
        storage_volume=storage_volume,
        status="queued",
        total_files_detected=5,
        processed_files_count=0,
        failed_files_count=0,
        total_bytes_processed=1024 * 1024,
        created_by=admin_user,
    )


@pytest.fixture
def metadata_schema(db, tenant_a, admin_user):
    """Fixture providing an active MetadataSchema in tenant_a."""
    return MetadataSchema.objects.create(
        tenant=tenant_a,
        name="Contract Metadata Schema",
        code="CONTRACT_V1",
        target_type="contract",
        fields_definition_json='[{"key": "effective_date", "label": "Effective Date", "data_type": "date", "required": true}, {"key": "contract_value", "label": "Contract Value", "data_type": "decimal", "required": false}]',
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def taxonomy_term(db, tenant_a, admin_user):
    """Fixture providing a baseline TaxonomyTerm in tenant_a."""
    return TaxonomyTerm.objects.create(
        tenant=tenant_a,
        name="Financial Services",
        term_code="FIN-SERV",
        category="industry",
        description="Banking, securities, insurance, and asset management institutions.",
        synonyms_json='["banking", "wealth management", "fintech"]',
        is_governed=True,
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def child_taxonomy_term(db, tenant_a, admin_user, taxonomy_term):
    """Fixture providing a child TaxonomyTerm in tenant_a."""
    return TaxonomyTerm.objects.create(
        tenant=tenant_a,
        name="Investment Banking",
        term_code="FIN-INV",
        category="industry",
        parent=taxonomy_term,
        description="Underwriting, mergers, acquisitions, and advisory services.",
        synonyms_json='["m&a", "capital markets"]',
        is_governed=False,
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def document_metadata_value(db, tenant_a, document, document_version, metadata_schema):
    """Fixture providing an active DocumentMetadataValue in tenant_a."""
    return DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        schema=metadata_schema,
        field_name="contract_value",
        field_label="Contract Total Value",
        data_type="decimal",
        value_number=150000.00,
        source="manual_entry",
        validation_status="valid",
    )


@pytest.fixture
def document_ocr_job(db, tenant_a, admin_user, document, document_version):
    """Fixture providing an OCR job in tenant_a."""
    return DocumentOcrJob.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        ocr_engine="tesseract_ocr",
        status="completed",
        confidence_score=94.50,
        page_count=3,
        extracted_full_text="Agreement made between party A and party B for delivery of consulting services.",
        suggested_tags_json='["consulting", "agreement", "q4"]',
        created_by=admin_user,
    )


@pytest.fixture
def document_saved_search(db, tenant_a, admin_user):
    """Fixture providing a baseline DocumentSavedSearch in tenant_a."""
    return DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        name="All Active Policies",
        description="Filter for published policy documents",
        query_text="policy",
        filters_json={"document_type": "policy", "status": "published"},
        facet_filters_json={"classification": ["internal"]},
        sort_by="-updated_at",
        visibility="public",
        owner=admin_user,
        is_pinned=True,
        is_active=True,
    )


@pytest.fixture
def document_search_alert(db, tenant_a, admin_user, document_saved_search):
    """Fixture providing a baseline DocumentSearchAlert in tenant_a."""
    return DocumentSearchAlert.objects.create(
        tenant=tenant_a,
        saved_search=document_saved_search,
        subscriber=admin_user,
        delivery_channel="in_app",
        frequency="daily",
        is_active=True,
    )


@pytest.fixture
def document_search_synonym(db, tenant_a, admin_user):
    """Fixture providing a baseline DocumentSearchSynonym in tenant_a."""
    return DocumentSearchSynonym.objects.create(
        tenant=tenant_a,
        term="agreement",
        synonyms="contract, accord, deal",
        category="domain",
        language="en",
        is_bidirectional=True,
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def document_search_query_log(db, tenant_a, admin_user):
    """Fixture providing a baseline DocumentSearchQueryLog in tenant_a."""
    return DocumentSearchQueryLog.objects.create(
        tenant=tenant_a,
        query_text="safety procedures",
        search_source="search_hub",
        filters_applied_json={"status": "published"},
        results_count=5,
        execution_time_ms=45.2,
        user=admin_user,
    )


@pytest.fixture
def org_unit_a(db, tenant_a):
    """Fixture providing an OrgUnit in tenant_a."""
    return OrgUnit.objects.create(
        tenant=tenant_a,
        name="Engineering Dept",
        code="ENG-DEPT",
    )


@pytest.fixture
def document_share(db, tenant_a, admin_user, member_user, document, document_version):
    """Fixture providing an active internal DocumentShare in tenant_a."""
    return DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        share_type="internal_user",
        access_level="view",
        shared_by=admin_user,
        shared_with_user=member_user,
        is_active=True,
    )


@pytest.fixture
def public_document_share(db, tenant_a, admin_user, document, document_version):
    """Fixture providing a public link DocumentShare in tenant_a."""
    share = DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        share_type="public_link",
        access_level="download",
        shared_by=admin_user,
        is_active=True,
        require_password=True,
        allow_download=True,
    )
    share.set_password("Secret123!")
    share.save()
    return share


@pytest.fixture
def coauthor_session(db, tenant_a, admin_user, document, document_version):
    """Fixture providing an active CoauthorSession in tenant_a."""
    return CoauthorSession.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        user=admin_user,
        client_id="client-test-session-123",
        status="active",
        color_code="#3B82F6",
        cursor_position_json={"line": 1, "column": 5},
    )


@pytest.fixture
def document_task(db, tenant_a, admin_user, member_user, document, document_version):
    """Fixture providing an assigned DocumentTask in tenant_a."""
    return DocumentTask.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        title="Review Section 3 Technical Specs",
        description="Verify compliance with ISO standard.",
        task_type="review",
        priority="high",
        status="pending",
        assigned_by=admin_user,
        assigned_to=member_user,
    )


@pytest.fixture
def document_activity(db, tenant_a, admin_user, member_user, document):
    """Fixture providing a DocumentActivity notification in tenant_a."""
    return DocumentActivity.objects.create(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        target_user=member_user,
        action_type="task_assigned",
        title="New Task Assigned",
        description="Admin assigned task Review Section 3 to you.",
        is_read=False,
    )





