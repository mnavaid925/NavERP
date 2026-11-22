"""Form unit tests for Sub-module 13.3: Document Approval & Review Workflow."""
import pytest

from apps.documents.forms.ApprovalWorkflow.DocumentApprovalRequests import (
    ApprovalDecisionForm,
    ApprovalDelegationForm,
    ApprovalEscalationForm,
    DocumentApprovalRequestForm,
)
from apps.documents.forms.ApprovalWorkflow.DocumentApprovalWorkflows import (
    DocumentApprovalWorkflowForm,
    WorkflowBypassForm,
)
from apps.documents.forms.ApprovalWorkflow.DocumentReviewComments import (
    CommentReplyForm,
    CommentResolveForm,
    DocumentReviewCommentForm,
)
from apps.documents.forms.ApprovalWorkflow.DocumentSignatures import (
    DocumentSignatureForm,
    SignatureVerificationForm,
)
from apps.documents.models import Document, DocumentVersion


@pytest.mark.django_db
def test_approval_workflow_form_valid_and_version_consistency(tenant_a, document, document_version):
    """Test DocumentApprovalWorkflowForm validation and document-version alignment check."""
    form_data = {
        "document": document.pk,
        "version": document_version.pk,
        "title": "ISO Quality Manual Approval",
        "workflow_type": "sequential",
        "urgency": "high",
        "total_stages": 2,
        "requires_all_comments_resolved": True,
        "allow_emergency_bypass": True,
    }
    form = DocumentApprovalWorkflowForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    # Version belonging to another document must raise validation error
    other_doc = Document.objects.create(
        tenant=tenant_a,
        title="Secondary Operating Procedure",
        document_type="sop",
        status="published",
        owner=document.owner,
    )
    other_version = DocumentVersion.objects.create(
        tenant=tenant_a,
        document=other_doc,
        version_label="0.9.0",
        version_type="minor",
        author=document.owner,
    )
    mismatched_data = dict(form_data, version=other_version.pk)
    mismatched_form = DocumentApprovalWorkflowForm(data=mismatched_data, tenant=tenant_a)
    assert not mismatched_form.is_valid()
    assert "version" in mismatched_form.errors


@pytest.mark.django_db
def test_workflow_bypass_form_validation():
    """Test WorkflowBypassForm requires justification."""
    invalid_form = WorkflowBypassForm(data={"bypass_reason": "   "})
    assert not invalid_form.is_valid()
    assert "bypass_reason" in invalid_form.errors

    valid_form = WorkflowBypassForm(data={"bypass_reason": "Production hotfix critical release under incident INC-4921."})
    assert valid_form.is_valid()


@pytest.mark.django_db
def test_approval_request_form_and_decision_forms(tenant_a, member_user, approval_workflow):
    """Test DocumentApprovalRequestForm and its specialized decision forms."""
    req_form = DocumentApprovalRequestForm(
        data={
            "workflow": approval_workflow.pk,
            "stage_number": 2,
            "stage_name": "VP Review",
            "stage_type": "parallel_first",
            "approver": member_user.pk,
            "order": 10,
        },
        tenant=tenant_a,
    )
    assert req_form.is_valid(), req_form.errors

    # Decision Form
    decision_form = ApprovalDecisionForm(data={"decision": "approved", "decision_comments": "Looks good for production."})
    assert decision_form.is_valid(), decision_form.errors

    invalid_decision = ApprovalDecisionForm(data={"decision": "invalid_choice"})
    assert not invalid_decision.is_valid()

    # Delegation Form
    delegation_form = ApprovalDelegationForm(
        data={"delegated_to": member_user.pk, "delegation_reason": "Covering team lead shift."},
        tenant=tenant_a,
    )
    assert delegation_form.is_valid(), delegation_form.errors

    # Escalation Form
    escalation_form = ApprovalEscalationForm(
        data={"escalated_to": member_user.pk, "escalation_reason": "Exceeded review SLA."},
        tenant=tenant_a,
    )
    assert escalation_form.is_valid(), escalation_form.errors


@pytest.mark.django_db
def test_document_signature_form_immutable_on_edit(tenant_a, member_user, document, document_version, approval_request, document_signature):
    """Test DocumentSignatureForm locks immutable fields on edit instance."""
    edit_form = DocumentSignatureForm(instance=document_signature, tenant=tenant_a)
    assert edit_form.fields["document"].disabled is True
    assert edit_form.fields["version"].disabled is True
    assert edit_form.fields["approval_request"].disabled is True
    assert edit_form.fields["signer_name"].disabled is True
    assert edit_form.fields["signature_type"].disabled is True

    # Token lookup form
    verify_form = SignatureVerificationForm(data={"token": document_signature.signature_token})
    assert verify_form.is_valid(), verify_form.errors


@pytest.mark.django_db
def test_document_review_comment_form_and_action_forms(tenant_a, document, document_version, approval_workflow):
    """Test DocumentReviewCommentForm, reply and resolve sub-forms."""
    comment_form = DocumentReviewCommentForm(
        data={
            "document": document.pk,
            "version": document_version.pk,
            "workflow": approval_workflow.pk,
            "annotation_type": "inline_comment",
            "page_number": 3,
            "content": "Consider clarifying paragraph 2 step b.",
            "is_blocking": False,
        },
        tenant=tenant_a,
    )
    assert comment_form.is_valid(), comment_form.errors

    # Reply form
    reply_form = CommentReplyForm(data={"content": "Agree, clarified in draft revision."})
    assert reply_form.is_valid(), reply_form.errors

    # Resolve form
    resolve_form = CommentResolveForm(data={"status": "resolved", "resolution_notes": "Implemented and verified."})
    assert resolve_form.is_valid(), resolve_form.errors
