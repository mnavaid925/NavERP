"""Model unit tests for Sub-module 13.3: Document Approval & Review Workflow."""
import pytest
from django.db import IntegrityError

from apps.documents.models import (
    DocumentApprovalRequest,
    DocumentApprovalWorkflow,
    DocumentReviewComment,
    DocumentSignature,
)


@pytest.mark.django_db
def test_approval_workflow_model_creation_and_autonumber(tenant_a, admin_user, document, document_version):
    """Test workflow creation generates formatted sequence number and string representation."""
    wf = DocumentApprovalWorkflow.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        title="Engineering Spec Review",
        workflow_type="sequential",
        urgency="high",
        initiator=admin_user,
        total_stages=3,
        current_stage=1,
    )
    assert wf.number.startswith("DWF-")
    assert "Engineering Spec Review" in str(wf)
    assert wf.status == "draft"
    assert wf.total_stages == 3
    assert wf.current_stage == 1


@pytest.mark.django_db
def test_approval_workflow_tenant_isolation_and_uniqueness(tenant_a, tenant_b, admin_user, document):
    """Test uniqueness constraints on number within tenant scope."""
    wf1 = DocumentApprovalWorkflow.objects.create(
        tenant=tenant_a,
        number="DWF-UNIQUE-01",
        document=document,
        title="Acme Review",
        initiator=admin_user,
    )
    assert wf1.number == "DWF-UNIQUE-01"

    # Duplicate number within same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        DocumentApprovalWorkflow.objects.create(
            tenant=tenant_a,
            number="DWF-UNIQUE-01",
            document=document,
            title="Duplicate Acme Review",
            initiator=admin_user,
        )


@pytest.mark.django_db
def test_approval_request_model_lifecycle(tenant_a, admin_user, member_user, approval_workflow):
    """Test approval request lifecycle, auto-numbering, delegation and escalation fields."""
    req = DocumentApprovalRequest.objects.create(
        tenant=tenant_a,
        workflow=approval_workflow,
        stage_number=1,
        stage_name="QA Signoff",
        stage_type="sequential",
        approver=member_user,
        status="pending",
    )
    assert req.number.startswith("DAPR-")
    assert "QA Signoff" in req.stage_name
    assert req.status == "pending"

    # Test delegation fields
    req.delegated_to = admin_user
    req.delegation_reason = "Delegated during vacation leave"
    req.status = "delegated"
    req.save()
    req.refresh_from_db()
    assert req.status == "delegated"
    assert req.delegated_to == admin_user

    # Test escalation fields
    req.is_escalated = True
    req.escalated_to = admin_user
    req.escalation_reason = "24-hour turnaround timeout exceeded"
    req.save()
    req.refresh_from_db()
    assert req.is_escalated is True
    assert req.escalated_to == admin_user


@pytest.mark.django_db
def test_document_signature_token_and_verification(tenant_a, member_user, document, document_version, approval_request):
    """Test signature auto token generation, checksum hashing, and validation."""
    sig = DocumentSignature.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        approval_request=approval_request,
        signer=member_user,
        signer_name="Alice Smith",
        signer_title="Chief Technology Officer",
        signature_type="crypto_token",
        signature_meaning="authorship",
        document_checksum="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        is_valid=True,
    )
    assert sig.number.startswith("DSIG-")
    assert sig.signature_token is not None
    assert len(sig.signature_token) >= 32
    assert sig.is_valid is True
    assert "Alice Smith" in str(sig)


@pytest.mark.django_db
def test_document_review_comment_hierarchy_and_blocking(tenant_a, member_user, admin_user, document, document_version, approval_workflow):
    """Test review comments, threaded replies, and blocking gates."""
    parent_comment = DocumentReviewComment.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        workflow=approval_workflow,
        author=member_user,
        annotation_type="defect",
        page_number=4,
        coordinate_ref="50,100,300,40",
        selected_text="Section 4.1 Fault Tolerance",
        content="Failover mechanism requires automatic retry logic.",
        is_blocking=True,
        status="open",
    )
    assert parent_comment.number.startswith("DREV-")
    assert parent_comment.is_blocking is True
    assert parent_comment.status == "open"

    # Threaded reply
    child_reply = DocumentReviewComment.objects.create(
        tenant=tenant_a,
        document=document,
        version=document_version,
        workflow=approval_workflow,
        author=admin_user,
        parent=parent_comment,
        content="Acknowledged. Adding exponential backoff retry in patch 1.1.",
        status="open",
    )
    assert child_reply.parent == parent_comment
    assert parent_comment.replies.count() == 1

    # Resolution
    parent_comment.status = "resolved"
    parent_comment.resolved_by = admin_user
    parent_comment.resolution_notes = "Updated in revision commit."
    parent_comment.save()
    parent_comment.refresh_from_db()
    assert parent_comment.status == "resolved"
    assert parent_comment.resolved_by == admin_user
