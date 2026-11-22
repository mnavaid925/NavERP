"""View unit tests for Sub-module 13.3: Document Approval & Review Workflow."""
import pytest
from django.urls import reverse

from apps.documents.models import (
    DocumentApprovalRequest,
    DocumentApprovalWorkflow,
    DocumentReviewComment,
    DocumentSignature,
)


@pytest.mark.django_db
def test_approval_workflow_crud_and_lifecycle_views(client, tenant_a, admin_user, document, document_version):
    """Test full CRUD lifecycle of DocumentApprovalWorkflow."""
    client.force_login(admin_user)

    # 1. List
    res = client.get(reverse("documents:workflow_list"))
    assert res.status_code == 200
    assert "Approval Workflows" in res.content.decode()

    # 2. Create
    create_url = reverse("documents:workflow_create")
    post_data = {
        "document": document.pk,
        "version": document_version.pk,
        "title": "Release Approval Cycle",
        "workflow_type": "sequential",
        "urgency": "medium",
        "total_stages": 2,
        "requires_all_comments_resolved": False,
        "allow_emergency_bypass": True,
    }
    res = client.post(create_url, post_data)
    assert res.status_code == 302
    wf = DocumentApprovalWorkflow.objects.get(title="Release Approval Cycle")
    assert wf.status == "draft"

    # 3. Detail
    detail_url = reverse("documents:workflow_detail", kwargs={"pk": wf.pk})
    res = client.get(detail_url)
    assert res.status_code == 200
    assert "Release Approval Cycle" in res.content.decode()

    # 4. Designer
    designer_url = reverse("documents:workflow_designer", kwargs={"pk": wf.pk})
    res = client.get(designer_url)
    assert res.status_code == 200

    # Save visual layout in designer
    res = client.post(designer_url, {"definition_json": '{"nodes": [], "edges": []}'})
    assert res.status_code == 302
    wf.refresh_from_db()
    assert 'nodes' in wf.definition_json

    # 5. Submit workflow (requires at least 1 request)
    req = DocumentApprovalRequest.objects.create(
        tenant=tenant_a,
        workflow=wf,
        stage_number=1,
        stage_name="Initial Gate",
        approver=admin_user,
    )
    submit_url = reverse("documents:workflow_submit", kwargs={"pk": wf.pk})
    res = client.post(submit_url)
    assert res.status_code == 302
    wf.refresh_from_db()
    assert wf.status == "pending"

    # 6. Delete draft protection: cannot delete non-draft
    del_url = reverse("documents:workflow_delete", kwargs={"pk": wf.pk})
    res = client.post(del_url)
    assert res.status_code == 302
    assert DocumentApprovalWorkflow.objects.filter(pk=wf.pk).exists()

    # 7. Cancel
    cancel_url = reverse("documents:workflow_cancel", kwargs={"pk": wf.pk})
    res = client.post(cancel_url)
    assert res.status_code == 302
    wf.refresh_from_db()
    assert wf.status == "cancelled"


@pytest.mark.django_db
def test_approval_request_decide_and_blocking_comment_gate(client, tenant_a, member_user, approval_workflow):
    """Test approval request decision and enforcement of blocking review comment gate."""
    client.force_login(member_user)

    # Create request assigned to member_user
    req = DocumentApprovalRequest.objects.create(
        tenant=tenant_a,
        workflow=approval_workflow,
        stage_number=1,
        stage_name="Security Clearance",
        stage_type="sequential",
        approver=member_user,
        status="pending",
    )
    decide_url = reverse("documents:approval_request_decide", kwargs={"pk": req.pk})

    # Case A: Blocking comment open on workflow with requires_all_comments_resolved=True
    approval_workflow.requires_all_comments_resolved = True
    approval_workflow.save()
    blocking_comm = DocumentReviewComment.objects.create(
        tenant=tenant_a,
        document=approval_workflow.document,
        version=approval_workflow.version,
        workflow=approval_workflow,
        author=member_user,
        content="Missing cryptographic cipher audit report.",
        is_blocking=True,
        status="open",
    )

    res = client.post(decide_url, {"decision": "approved", "decision_comments": "Attempting signoff."})
    assert res.status_code == 302
    req.refresh_from_db()
    assert req.status == "pending"  # Still pending because blocked!

    # Resolve comment and retry
    blocking_comm.status = "resolved"
    blocking_comm.save()

    res = client.post(decide_url, {"decision": "approved", "decision_comments": "Approved after resolution."})
    assert res.status_code == 302
    req.refresh_from_db()
    assert req.status == "approved"
    assert req.decided_at is not None


@pytest.mark.django_db
def test_document_signature_views_and_token_lookup(client, tenant_a, member_user, document_signature):
    """Test signature list, detail, manifest certificate view, and public token verify."""
    client.force_login(member_user)

    # 1. Signature List
    res = client.get(reverse("documents:signature_list"))
    assert res.status_code == 200
    assert document_signature.signer_name in res.content.decode()

    # 2. Detail
    res = client.get(reverse("documents:signature_detail", kwargs={"pk": document_signature.pk}))
    assert res.status_code == 200
    assert document_signature.number in res.content.decode()

    # 3. Certificate Manifest
    res = client.get(reverse("documents:signature_manifest", kwargs={"pk": document_signature.pk}))
    assert res.status_code == 200
    assert "21 CFR Part 11" in res.content.decode()

    # 4. Token verification
    verify_url = reverse("documents:signature_verify") + f"?token={document_signature.signature_token}"
    res = client.get(verify_url)
    assert res.status_code == 200
    assert "Valid Cryptographic Signature" in res.content.decode()


@pytest.mark.django_db
def test_review_comment_views_threads_and_resolution(client, tenant_a, member_user, admin_user, review_comment):
    """Test review comments listing, detail, thread replies, and mark resolution."""
    client.force_login(member_user)

    # 1. Detail
    detail_url = reverse("documents:review_comment_detail", kwargs={"pk": review_comment.pk})
    res = client.get(detail_url)
    assert res.status_code == 200
    assert review_comment.content in res.content.decode()

    # 2. Reply to comment
    reply_url = reverse("documents:review_comment_reply", kwargs={"pk": review_comment.pk})
    res = client.post(reply_url, {"content": "Checking calibration lab specs."})
    assert res.status_code == 302
    assert review_comment.replies.count() == 1

    # 3. Resolve comment
    client.force_login(admin_user)
    resolve_url = reverse("documents:review_comment_resolve", kwargs={"pk": review_comment.pk})
    res = client.post(resolve_url, {"status": "resolved", "resolution_notes": "Updated in rev 2."})
    assert res.status_code == 302
    review_comment.refresh_from_db()
    assert review_comment.status == "resolved"


@pytest.mark.django_db
def test_approval_dashboard_cockpit_view(client, member_user, approval_workflow, approval_request, document_signature, review_comment):
    """Test the ApprovalDashboard cockpit endpoint and metrics context."""
    client.force_login(member_user)
    res = client.get(reverse("documents:approval_dashboard"))
    assert res.status_code == 200
    content = res.content.decode()
    assert "Approval Command Center" in content
    assert "Active Approval Pipelines" in content
    assert "Average Approval Cycle Time" in content
