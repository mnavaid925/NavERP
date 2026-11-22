"""Security and multi-tenant isolation unit tests for Sub-module 13.3: Document Approval & Review Workflow."""
import pytest
from django.urls import reverse

from apps.documents.models import (
    DocumentApprovalRequest,
    DocumentApprovalWorkflow,
    DocumentReviewComment,
    DocumentSignature,
)


@pytest.fixture
def other_user(db, tenant_a):
    """Fixture providing a second distinct user belonging to tenant_a."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="other@acme.com",
        username="other_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


@pytest.mark.django_db
def test_approval_workflow_unauthenticated_redirect(client, approval_workflow, approval_request, document_signature, review_comment):
    """Test that all protected 13.3 endpoints redirect unauthenticated users to login."""
    protected_urls = [
        reverse("documents:workflow_list"),
        reverse("documents:workflow_create"),
        reverse("documents:workflow_detail", kwargs={"pk": approval_workflow.pk}),
        reverse("documents:workflow_designer", kwargs={"pk": approval_workflow.pk}),
        reverse("documents:approval_request_list"),
        reverse("documents:approval_request_detail", kwargs={"pk": approval_request.pk}),
        reverse("documents:signature_list"),
        reverse("documents:signature_detail", kwargs={"pk": document_signature.pk}),
        reverse("documents:signature_manifest", kwargs={"pk": document_signature.pk}),
        reverse("documents:review_comment_list"),
        reverse("documents:review_comment_detail", kwargs={"pk": review_comment.pk}),
        reverse("documents:approval_dashboard"),
    ]
    for url in protected_urls:
        res = client.get(url)
        assert res.status_code == 302
        assert "/login/" in res.headers["Location"]


@pytest.mark.django_db
def test_approval_workflow_cross_tenant_idor_protection(client, admin_b, approval_workflow, approval_request, document_signature, review_comment):
    """Test that tenant_b user cannot access or mutate tenant_a workflow objects (must 404)."""
    client.force_login(admin_b)

    # 1. Workflow Detail & Mutations
    assert client.get(reverse("documents:workflow_detail", kwargs={"pk": approval_workflow.pk})).status_code == 404
    assert client.get(reverse("documents:workflow_designer", kwargs={"pk": approval_workflow.pk})).status_code == 404
    assert client.post(reverse("documents:workflow_submit", kwargs={"pk": approval_workflow.pk})).status_code == 404
    assert client.post(reverse("documents:workflow_bypass", kwargs={"pk": approval_workflow.pk}), {"bypass_reason": "Hack"}).status_code == 404
    assert client.post(reverse("documents:workflow_delete", kwargs={"pk": approval_workflow.pk})).status_code == 404

    # 2. Approval Request Detail & Decisions
    assert client.get(reverse("documents:approval_request_detail", kwargs={"pk": approval_request.pk})).status_code == 404
    assert client.post(reverse("documents:approval_request_decide", kwargs={"pk": approval_request.pk}), {"decision": "approved"}).status_code == 404
    assert client.post(reverse("documents:approval_request_delete", kwargs={"pk": approval_request.pk})).status_code == 404

    # 3. Document Signature Detail & Manifest
    assert client.get(reverse("documents:signature_detail", kwargs={"pk": document_signature.pk})).status_code == 404
    assert client.get(reverse("documents:signature_manifest", kwargs={"pk": document_signature.pk})).status_code == 404
    assert client.post(reverse("documents:signature_delete", kwargs={"pk": document_signature.pk})).status_code == 404

    # 4. Review Comment Detail & Mutations
    assert client.get(reverse("documents:review_comment_detail", kwargs={"pk": review_comment.pk})).status_code == 404
    assert client.post(reverse("documents:review_comment_delete", kwargs={"pk": review_comment.pk})).status_code == 404
    assert client.post(reverse("documents:review_comment_resolve", kwargs={"pk": review_comment.pk}), {"status": "resolved"}).status_code == 404


@pytest.mark.django_db
def test_approval_workflow_authorization_guards(client, tenant_a, member_user, other_user, admin_user, approval_workflow):
    """Test authorization checks: only assigned approver or admin can decide or bypass."""
    # 1. Non-approver decision rejection (CR-C2)
    req = DocumentApprovalRequest.objects.create(
        tenant=tenant_a,
        workflow=approval_workflow,
        stage_number=1,
        stage_name="Signoff",
        approver=member_user,
        status="pending",
    )
    client.force_login(other_user)  # different user in same tenant
    decide_url = reverse("documents:approval_request_decide", kwargs={"pk": req.pk})
    res = client.post(decide_url, {"decision": "approved", "decision_comments": "Illegitimate signoff."})
    assert res.status_code == 302
    req.refresh_from_db()
    assert req.status == "pending"  # Decision was rejected!

    # 2. Emergency Bypass authorization guard (CR-C3)
    client.force_login(other_user)
    bypass_url = reverse("documents:workflow_bypass", kwargs={"pk": approval_workflow.pk})
    res = client.post(bypass_url, {"bypass_reason": "Low privilege bypass."})
    assert res.status_code == 302
    approval_workflow.refresh_from_db()
    assert approval_workflow.status == "pending"  # Not bypassed!

    # But tenant admin CAN bypass
    client.force_login(admin_user)
    res = client.post(bypass_url, {"bypass_reason": "Authorized incident emergency bypass."})
    assert res.status_code == 302
    approval_workflow.refresh_from_db()
    assert approval_workflow.status == "bypassed"


@pytest.mark.django_db
def test_review_comment_author_authorization(client, other_user, member_user, review_comment):
    """Test that users cannot edit or delete review comments authored by others (CR-I11)."""
    client.force_login(other_user)
    del_url = reverse("documents:review_comment_delete", kwargs={"pk": review_comment.pk})
    res = client.post(del_url)
    assert res.status_code == 302
    assert DocumentReviewComment.objects.filter(pk=review_comment.pk).exists()

    edit_url = reverse("documents:review_comment_edit", kwargs={"pk": review_comment.pk})
    res = client.post(edit_url, {"content": "Tampered content"})
    assert res.status_code == 302
    review_comment.refresh_from_db()
    assert review_comment.content != "Tampered content"


@pytest.mark.django_db
def test_signature_glyph_xss_protection(client, admin_user, document_signature):
    """Test that malicious script in signature_glyph is escaped safely (CR-C1)."""
    document_signature.signature_glyph = '<script>alert("XSS")</script><svg onload="alert(1)"></svg>'
    document_signature.save()

    client.force_login(admin_user)
    detail_url = reverse("documents:signature_detail", kwargs={"pk": document_signature.pk})
    res = client.get(detail_url)
    assert res.status_code == 200
    html = res.content.decode()
    # Must NOT render raw unescaped script tag
    assert '<script>alert("XSS")</script>' not in html
    assert '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;' in html or '&lt;script&gt;' in html
