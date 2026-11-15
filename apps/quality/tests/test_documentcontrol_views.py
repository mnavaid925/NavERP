"""
Unit and integration tests for apps/quality views (Module 12.1: Document Control & Management).

Covers all views, routes, filters, context keys, status transitions, permissions, and CSV exports:
- ControlledDocuments:
  - controlled_document_list (filters: ?q=, ?status=, ?type=, ?latest=, pagination, stats aggregate)
  - controlled_document_detail (context keys: can_approve, can_make_effective, can_obsolete, can_sign; breadcrumbs)
  - controlled_document_create (POST creates document with owner=request.user, audit log)
  - controlled_document_edit (POST updates document, audit log, locked guard)
  - controlled_document_delete (POST-only, owner or admin required per M13, locked guard)
  - controlled_document_submit, controlled_document_approve, controlled_document_make_effective,
    controlled_document_obsolete (status transitions, admin gating per I3, superseding lineage)
  - controlled_document_new_revision (branches new revision from effective document)
  - controlled_document_export (streaming CSV download)
  - document_archive_vault (vault workbench view with filters and stats aggregate)
- DocumentChangeOrders:
  - document_change_order_list (filters, stats aggregate)
  - document_change_order_detail (context keys, signatures manifest rendered per I7)
  - document_change_order_create (POST creates DCO with requested_by=request.user)
  - document_change_order_edit, document_change_order_delete, document_change_order_submit
  - document_change_order_ccb_decision (POST CCB determination, status guard per I1, admin required)
  - document_change_order_export (CSV download)
- ElectronicSignatures:
  - electronic_signature_list (stats aggregate, filters)
  - electronic_signature_detail (context keys, HMAC verification)
  - electronic_signature_verify (GET verification route)
  - controlled_document_sign (GET and POST, lifecycle guard per I5, admin gating per I16, password check, HMAC)
  - electronic_signature_export (CSV download)
- DocumentAcknowledgments:
  - document_acknowledgment_list (stats aggregate, filters)
  - document_acknowledgment_detail (context keys, signature linkage)
  - document_acknowledgment_create (creates acknowledgment requirement)
  - document_acknowledgment_edit (locked guard on acknowledged records)
  - document_acknowledgment_sign (GET and POST, authorization check per C1, password check, signs ack)
  - document_acknowledgment_delete (tenant admin required per I14, cannot delete executed ack)
  - document_acknowledgment_export (CSV download)
"""

from datetime import timedelta
import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, OrgUnit, Party, PartyRole
from apps.hrm.models import EmployeeProfile
from apps.quality.models import (
    ControlledDocument,
    DocumentChangeOrder,
    ElectronicSignatureRecord,
    DocumentAcknowledgment,
)

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixture Overrides to match actual NavERP core / hrm schemas
# =====================================================================


@pytest.fixture
def quality_department(db, tenant_a):
    return OrgUnit.objects.create(
        tenant=tenant_a,
        name="Quality Assurance",
        kind="department",
    )


@pytest.fixture
def quality_department_b(db, tenant_b):
    return OrgUnit.objects.create(
        tenant=tenant_b,
        name="Quality Assurance Globex",
        kind="department",
    )


@pytest.fixture
def quality_employee(db, tenant_a, admin_user, quality_department):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Admin QA Manager",
        kind="person",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role="employee",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_a,
        party=party,
        employee_type="full_time",
    )


@pytest.fixture
def quality_employee_b(db, tenant_b, admin_b, quality_department_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Globex QA Officer",
        kind="person",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role="employee",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_b,
        party=party,
        employee_type="full_time",
    )


# ------------------------------------------------------------------ Helpers


def _documentcontrol_get_messages(response):
    """Retrieve string messages flashed during request processing."""
    if hasattr(response, "wsgi_request") and response.wsgi_request:
        return [m.message for m in get_messages(response.wsgi_request)]
    return []


def _documentcontrol_audit_logs(obj, action=None):
    """Retrieve audit log rows written for obj."""
    ct = ContentType.objects.get_for_model(obj.__class__)
    qs = AuditLog.objects.filter(content_type=ct, object_id=obj.pk)
    if action:
        qs = qs.filter(action=action)
    return qs


def _documentcontrol_create_doc(tenant, owner, **kwargs):
    """Helper to create a ControlledDocument with sensible defaults."""
    fields = {
        "tenant": tenant,
        "owner": owner,
        "title": "Auxiliary Document Procedure",
        "document_type": "sop",
        "revision": "1.0",
        "lifecycle_state": "draft",
        "classification": "internal",
        "description": "Auxiliary document for view testing.",
        "review_interval_months": 12,
        "retention_years": 10,
    }
    fields.update(kwargs)
    return ControlledDocument.objects.create(**fields)


def _documentcontrol_create_dco(tenant, requested_by, document, **kwargs):
    """Helper to create a DocumentChangeOrder with valid choices."""
    fields = {
        "tenant": tenant,
        "requested_by": requested_by,
        "document": document,
        "title": "Auxiliary Change Request",
        "change_type": "major_revision",
        "priority": "standard",
        "status": "draft",
        "reason_for_change": "Procedure adjustment.",
        "change_description": "Updated section.",
    }
    fields.update(kwargs)
    return DocumentChangeOrder.objects.create(**fields)


def _documentcontrol_create_ack(tenant, user, document, **kwargs):
    """Helper to create a DocumentAcknowledgment."""
    fields = {
        "tenant": tenant,
        "user": user,
        "document": document,
        "status": "pending",
        "due_date": timezone.now().date() + timedelta(days=7),
    }
    fields.update(kwargs)
    return DocumentAcknowledgment.objects.create(**fields)


# ------------------------------------------------------------------ ControlledDocuments Views


def test_documentcontrol_list_renders_and_tenant_isolated(
    client_a, tenant_a, quality_doc_draft, quality_doc_effective, quality_doc_b
):
    """List view renders documents for the active tenant and enforces tenant isolation."""
    url = reverse("quality:controlled_document_list")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "documents" in response.context
    assert "page_obj" in response.context
    assert "stats" in response.context
    assert "status_choices" in response.context
    assert "type_choices" in response.context
    assert "department_choices" in response.context

    doc_ids = [d.pk for d in response.context["documents"]]
    assert quality_doc_draft.pk in doc_ids
    assert quality_doc_effective.pk in doc_ids
    assert quality_doc_b.pk not in doc_ids


def test_documentcontrol_list_filters(
    client_a, tenant_a, admin_user, quality_doc_draft, quality_doc_effective
):
    """List view supports ?q=, ?status=, ?type=, ?department=, and ?latest= filters."""
    url = reverse("quality:controlled_document_list")

    # Filter ?q=
    res_q = client_a.get(url, {"q": "Draft Standard"})
    assert res_q.status_code == 200
    pks_q = [d.pk for d in res_q.context["documents"]]
    assert quality_doc_draft.pk in pks_q
    assert quality_doc_effective.pk not in pks_q

    # Filter ?status=
    res_status = client_a.get(url, {"status": "effective"})
    assert res_status.status_code == 200
    pks_status = [d.pk for d in res_status.context["documents"]]
    assert quality_doc_effective.pk in pks_status
    assert quality_doc_draft.pk not in pks_status

    # Filter ?type=
    res_type = client_a.get(url, {"type": "sop"})
    assert res_type.status_code == 200
    pks_type = [d.pk for d in res_type.context["documents"]]
    assert quality_doc_draft.pk in pks_type

    # Filter ?latest=0 vs ?latest=1
    older_doc = _documentcontrol_create_doc(
        tenant_a, admin_user, revision="0.9", is_latest_revision=False, title="Old Archival SOP"
    )
    res_latest_1 = client_a.get(url, {"latest": "1"})
    pks_latest_1 = [d.pk for d in res_latest_1.context["documents"]]
    assert older_doc.pk not in pks_latest_1

    res_latest_0 = client_a.get(url, {"latest": "0"})
    pks_latest_0 = [d.pk for d in res_latest_0.context["documents"]]
    assert older_doc.pk in pks_latest_0


def test_documentcontrol_list_stats_aggregate(
    client_a, quality_doc_draft, quality_doc_effective
):
    """List view computes correct aggregate statistics."""
    url = reverse("quality:controlled_document_list")
    response = client_a.get(url)
    stats = response.context["stats"]

    assert stats["total"] >= 2
    assert stats["effective"] >= 1
    assert stats["draft"] >= 1
    assert "in_review" in stats
    assert "overdue_reviews" in stats


def test_documentcontrol_list_pagination(client_a, tenant_a, admin_user):
    """List view paginates at 15 items per page."""
    # Create 16 documents
    for i in range(16):
        _documentcontrol_create_doc(tenant_a, admin_user, title=f"Bulk Document {i:02d}")

    url = reverse("quality:controlled_document_list")
    res_p1 = client_a.get(url)
    assert res_p1.status_code == 200
    assert res_p1.context["is_paginated"] is True
    assert len(res_p1.context["documents"]) == 15

    res_p2 = client_a.get(url, {"page": "2"})
    assert res_p2.status_code == 200
    assert len(res_p2.context["documents"]) >= 1


def test_documentcontrol_detail_context_and_breadcrumbs(
    client_a, member_client, admin_user, tenant_a, quality_doc_draft, quality_doc_effective, quality_doc_b
):
    """Detail view returns all context flags, renders breadcrumbs, and blocks cross-tenant access."""
    # Draft document viewed by admin
    url_draft = reverse("quality:controlled_document_detail", kwargs={"pk": quality_doc_draft.pk})
    res_draft = client_a.get(url_draft)
    assert res_draft.status_code == 200
    ctx = res_draft.context
    assert ctx["can_edit"] is True
    assert ctx["can_submit"] is True
    assert ctx["can_approve"] is False
    assert ctx["can_make_effective"] is False
    assert ctx["can_obsolete"] is False
    assert ctx["can_sign"] is True
    assert ctx["is_admin"] is True

    # Breadcrumbs rendered
    content = res_draft.content.decode("utf-8")
    assert quality_doc_draft.number in content
    assert "Controlled Documents" in content

    # Effective document viewed by member
    url_eff = reverse("quality:controlled_document_detail", kwargs={"pk": quality_doc_effective.pk})
    res_eff = member_client.get(url_eff)
    assert res_eff.status_code == 200
    ctx_eff = res_eff.context
    assert ctx_eff["can_submit"] is False
    assert ctx_eff["can_approve"] is False
    assert ctx_eff["can_make_effective"] is False
    assert ctx_eff["can_obsolete"] is False
    assert ctx_eff["can_revise"] is True
    assert ctx_eff["is_admin"] is False

    # Obsolete document viewed: locked -> can_edit is False
    obs_doc = _documentcontrol_create_doc(tenant_a, admin_user, lifecycle_state="obsolete")
    url_obs = reverse("quality:controlled_document_detail", kwargs={"pk": obs_doc.pk})
    res_obs = client_a.get(url_obs)
    assert res_obs.status_code == 200
    assert res_obs.context["can_edit"] is False
    assert res_obs.context["can_sign"] is False

    # Cross-tenant IDOR returns 404
    url_b = reverse("quality:controlled_document_detail", kwargs={"pk": quality_doc_b.pk})
    res_b = client_a.get(url_b)
    assert res_b.status_code == 404


def test_documentcontrol_create_post_and_redirect(client_a, admin_user, quality_department):
    """POST creates ControlledDocument with owner=request.user and records audit log."""
    url = reverse("quality:controlled_document_create")

    # GET returns form
    get_res = client_a.get(url)
    assert get_res.status_code == 200
    assert "form" in get_res.context

    # POST valid document
    post_data = {
        "title": "Cleanroom Entry and Gowning Procedure",
        "document_type": "sop",
        "department": quality_department.pk,
        "revision": "1.0",
        "classification": "internal",
        "description": "Standard gowning sequence and disinfection protocol.",
        "change_summary": "Initial formal document creation.",
        "review_interval_months": 12,
        "retention_years": 5,
    }
    response = client_a.post(url, post_data, follow=False)
    assert response.status_code == 302

    new_doc = ControlledDocument.objects.get(title="Cleanroom Entry and Gowning Procedure")
    assert new_doc.owner == admin_user
    assert new_doc.tenant == admin_user.tenant
    assert new_doc.lifecycle_state == "draft"

    assert response.url == reverse("quality:controlled_document_detail", kwargs={"pk": new_doc.pk})

    # Verify audit log
    logs = _documentcontrol_audit_logs(new_doc, action="create")
    assert logs.exists()


def test_documentcontrol_update_post_and_locked_guard(
    client_a, admin_user, tenant_a, quality_doc_draft, quality_doc_effective
):
    """Edit view allows updating draft document with audit trail, and blocks editing locked document."""
    url_draft_edit = reverse("quality:controlled_document_edit", kwargs={"pk": quality_doc_draft.pk})

    # GET draft edit form
    res_get = client_a.get(url_draft_edit)
    assert res_get.status_code == 200

    # POST valid update to draft
    update_data = {
        "title": "Updated Draft SOP Title",
        "document_type": quality_doc_draft.document_type,
        "department": quality_doc_draft.department_id or "",
        "revision": "1.0",
        "classification": "confidential",
        "description": "Revised description for audit check.",
        "change_summary": "Revised change summary.",
        "review_interval_months": 12,
        "retention_years": 5,
    }
    res_post = client_a.post(url_draft_edit, update_data, follow=True)
    assert res_post.status_code == 200
    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.title == "Updated Draft SOP Title"
    assert quality_doc_draft.classification == "confidential"

    # Verify audit log
    assert _documentcontrol_audit_logs(quality_doc_draft, action="update").exists()

    # Attempt to edit locked (obsolete) document
    locked_doc = _documentcontrol_create_doc(
        tenant_a, admin_user, lifecycle_state="obsolete"
    )
    url_locked_edit = reverse("quality:controlled_document_edit", kwargs={"pk": locked_doc.pk})
    res_locked = client_a.get(url_locked_edit, follow=True)
    assert res_locked.status_code == 200
    messages = _documentcontrol_get_messages(res_locked)
    assert any("cannot be modified directly" in m for m in messages)


def test_documentcontrol_delete_permissions_and_locked_guard(
    client_a, member_client, admin_user, member_user, tenant_a, quality_doc_effective
):
    """Delete requires POST, owner or admin authority (M13), and rejects locked documents."""
    # Create draft owned by admin_user
    doc = _documentcontrol_create_doc(tenant_a, admin_user, title="Disposable SOP")
    url_delete = reverse("quality:controlled_document_delete", kwargs={"pk": doc.pk})

    # GET rejected with 405
    res_get = client_a.get(url_delete)
    assert res_get.status_code == 405

    # Member user (not owner, not admin) cannot delete
    res_member = member_client.post(url_delete, follow=True)
    assert res_member.status_code == 200
    messages = _documentcontrol_get_messages(res_member)
    assert any("Only the document owner or an administrator" in m for m in messages)
    assert ControlledDocument.objects.filter(pk=doc.pk).exists()

    # Locked/effective document cannot be deleted even by admin
    url_eff_delete = reverse("quality:controlled_document_delete", kwargs={"pk": quality_doc_effective.pk})
    res_eff_del = client_a.post(url_eff_delete, follow=True)
    assert res_eff_del.status_code == 200
    messages_eff = _documentcontrol_get_messages(res_eff_del)
    assert any("Cannot delete document" in m for m in messages_eff)
    assert ControlledDocument.objects.filter(pk=quality_doc_effective.pk).exists()

    # Valid delete by admin
    res_del = client_a.post(url_delete, follow=False)
    assert res_del.status_code == 302
    assert not ControlledDocument.objects.filter(pk=doc.pk).exists()
    assert _documentcontrol_audit_logs(doc, action="delete").exists()


def test_documentcontrol_lifecycle_transitions_and_admin_gating(
    client_a, member_client, tenant_a, admin_user
):
    """Workflow state transitions: submit -> approve (admin) -> make_effective (admin) -> obsolete (admin)."""
    doc = _documentcontrol_create_doc(tenant_a, admin_user, title="Lifecycle Pipeline SOP")

    # 1. Submit
    url_submit = reverse("quality:controlled_document_submit", kwargs={"pk": doc.pk})
    res_submit = client_a.post(url_submit, follow=True)
    assert res_submit.status_code == 200
    doc.refresh_from_db()
    assert doc.lifecycle_state == "in_review"
    assert _documentcontrol_audit_logs(doc, action="submit").exists()

    # Attempting to submit non-draft is rejected
    res_submit_again = client_a.post(url_submit, follow=True)
    assert any("Only draft documents" in m for m in _documentcontrol_get_messages(res_submit_again))

    # 2. Approve (I3 admin gating)
    url_approve = reverse("quality:controlled_document_approve", kwargs={"pk": doc.pk})

    # Member user gets 403 Forbidden
    res_member_app = member_client.post(url_approve)
    assert res_member_app.status_code == 403

    # Admin user approves
    res_app = client_a.post(url_approve, follow=True)
    assert res_app.status_code == 200
    doc.refresh_from_db()
    assert doc.lifecycle_state == "approved"
    assert _documentcontrol_audit_logs(doc, action="approve").exists()

    # 3. Make Effective (I3 admin gating + predecessor superseding)
    old_doc = _documentcontrol_create_doc(
        tenant_a, admin_user, revision="1.0", lifecycle_state="effective", is_latest_revision=True
    )
    doc.supersedes = old_doc
    doc.revision = "2.0"
    doc.save()

    url_eff = reverse("quality:controlled_document_make_effective", kwargs={"pk": doc.pk})

    # Member user gets 403 Forbidden
    res_member_eff = member_client.post(url_eff)
    assert res_member_eff.status_code == 403

    # Admin makes effective
    res_eff = client_a.post(url_eff, follow=True)
    assert res_eff.status_code == 200
    doc.refresh_from_db()
    old_doc.refresh_from_db()

    assert doc.lifecycle_state == "effective"
    assert doc.effective_date is not None
    assert doc.next_review_date is not None
    assert doc.is_latest_revision is True
    assert _documentcontrol_audit_logs(doc, action="effective").exists()

    # Old doc is superseded
    assert old_doc.lifecycle_state == "superseded"
    assert old_doc.is_latest_revision is False
    assert old_doc.superseded_by == doc
    assert _documentcontrol_audit_logs(old_doc, action="supersede").exists()

    # 4. Obsolete (I3 admin gating)
    url_obs = reverse("quality:controlled_document_obsolete", kwargs={"pk": doc.pk})

    # Member user gets 403 Forbidden
    res_member_obs = member_client.post(url_obs)
    assert res_member_obs.status_code == 403

    # Admin obsoletes
    res_obs = client_a.post(url_obs, follow=True)
    assert res_obs.status_code == 200
    doc.refresh_from_db()
    assert doc.lifecycle_state == "obsolete"
    assert doc.archived_at is not None
    assert doc.is_latest_revision is False
    assert _documentcontrol_audit_logs(doc, action="obsolete").exists()


def test_documentcontrol_new_revision_branching(client_a, quality_doc_draft, quality_doc_effective):
    """Branching new revision succeeds from effective document and fails on draft."""
    # Attempting to branch from draft is rejected
    url_draft_rev = reverse("quality:controlled_document_new_revision", kwargs={"pk": quality_doc_draft.pk})
    res_draft_rev = client_a.get(url_draft_rev, follow=True)
    assert any("only be branched from currently effective" in m for m in _documentcontrol_get_messages(res_draft_rev))

    # Branch from effective document
    url_eff_rev = reverse("quality:controlled_document_new_revision", kwargs={"pk": quality_doc_effective.pk})
    res_get = client_a.get(url_eff_rev)
    assert res_get.status_code == 200
    assert "form" in res_get.context

    post_data = {
        "revision": "3.0",
        "change_summary": "Periodic major revision for 2026 quality system refresh.",
        "description": "Updated standard procedure.",
    }
    res_post = client_a.post(url_eff_rev, post_data, follow=False)
    assert res_post.status_code == 302

    branched = ControlledDocument.objects.get(supersedes=quality_doc_effective, revision="3.0")
    assert branched.lifecycle_state == "draft"
    assert branched.is_latest_revision is False
    assert res_post.url == reverse("quality:controlled_document_detail", kwargs={"pk": branched.pk})


def test_documentcontrol_export_csv(client_a, quality_doc_draft, quality_doc_b):
    """CSV export returns attachment response with header and scoped document rows."""
    url = reverse("quality:controlled_document_export")
    response = client_a.get(url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert 'filename="controlled_documents.csv"' in response["Content-Disposition"]

    content = response.content.decode("utf-8")
    assert "Number,Title,Type,Revision,State,Classification,Department,Owner" in content
    assert quality_doc_draft.title in content
    assert quality_doc_b.title not in content


def test_documentcontrol_vault_workbench(
    client_a, tenant_a, admin_user, quality_doc_draft, quality_doc_effective
):
    """Vault workbench lists only superseded, obsolete, or archived documents."""
    obs_doc = _documentcontrol_create_doc(
        tenant_a,
        admin_user,
        title="Retired Quality Policy",
        lifecycle_state="obsolete",
        is_latest_revision=False,
    )
    sup_doc = _documentcontrol_create_doc(
        tenant_a,
        admin_user,
        title="Superseded Quality Policy",
        lifecycle_state="superseded",
        is_latest_revision=False,
    )

    url = reverse("quality:document_archive_vault")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "vault_documents" in response.context
    assert "stats" in response.context

    vault_pks = [d.pk for d in response.context["vault_documents"]]
    assert obs_doc.pk in vault_pks
    assert sup_doc.pk in vault_pks
    assert quality_doc_draft.pk not in vault_pks
    assert quality_doc_effective.pk not in vault_pks

    stats = response.context["stats"]
    assert stats["total_vault"] >= 2
    assert stats["obsolete"] >= 1
    assert stats["superseded"] >= 1

    # Search filter in vault
    res_search = client_a.get(url, {"q": "Retired Quality"})
    pks_search = [d.pk for d in res_search.context["vault_documents"]]
    assert obs_doc.pk in pks_search
    assert sup_doc.pk not in pks_search


# ------------------------------------------------------------------ DocumentChangeOrders Views


def test_documentcontrol_change_order_list_filters_and_stats(
    client_a, quality_dco, quality_dco_b
):
    """Change order list renders active tenant records, filters, and computes stats."""
    url = reverse("quality:document_change_order_list")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "change_orders" in response.context
    assert "stats" in response.context
    assert "status_choices" in response.context
    assert "priority_choices" in response.context

    dco_pks = [d.pk for d in response.context["change_orders"]]
    assert quality_dco.pk in dco_pks
    assert quality_dco_b.pk not in dco_pks

    # Search filter
    res_search = client_a.get(url, {"q": "Audit Requirements"})
    assert quality_dco.pk in [d.pk for d in res_search.context["change_orders"]]

    # Status and priority filters
    res_filter = client_a.get(url, {"status": "submitted", "priority": "high"})
    assert quality_dco.pk in [d.pk for d in res_filter.context["change_orders"]]

    stats = response.context["stats"]
    assert stats["total"] >= 1
    assert stats["active"] >= 1


def test_documentcontrol_change_order_detail_and_signatures_manifest(
    client_a, quality_dco, quality_dco_b, quality_sig
):
    """Detail view provides context, renders signatures manifest (I7), and prevents cross-tenant access."""
    # Link signature to change order
    quality_sig.change_order = quality_dco
    quality_sig.save()

    url = reverse("quality:document_change_order_detail", kwargs={"pk": quality_dco.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    ctx = response.context
    assert ctx["change_order"] == quality_dco
    assert ctx["document"] == quality_dco.document
    assert quality_sig in ctx["signatures"]
    assert ctx["can_ccb_approve"] is True

    # Check rendered signatures table (I7)
    content = response.content.decode("utf-8")
    assert "Electronic Signatures & CCB Approvals" in content
    assert quality_sig.signer_name in content

    # Cross-tenant IDOR
    url_b = reverse("quality:document_change_order_detail", kwargs={"pk": quality_dco_b.pk})
    assert client_a.get(url_b).status_code == 404


def test_documentcontrol_change_order_create_post(client_a, admin_user, quality_doc_draft):
    """POST creates DocumentChangeOrder with requested_by=request.user and audit log."""
    url = reverse("quality:document_change_order_create")

    # GET returns form
    assert client_a.get(url).status_code == 200

    post_data = {
        "title": "Update Temperature Logs Protocol",
        "change_type": "major_revision",
        "priority": "standard",
        "document": quality_doc_draft.pk,
        "target_revision": "1.1",
        "reason_for_change": "Incorporate automated sensor readings.",
        "change_description": "Added sensor calibration steps in section 3.",
    }
    response = client_a.post(url, post_data, follow=False)
    assert response.status_code == 302

    dco = DocumentChangeOrder.objects.get(title="Update Temperature Logs Protocol")
    assert dco.requested_by == admin_user
    assert dco.tenant == admin_user.tenant
    assert response.url == reverse("quality:document_change_order_detail", kwargs={"pk": dco.pk})
    assert _documentcontrol_audit_logs(dco, action="create").exists()


def test_documentcontrol_change_order_edit_delete_submit(client_a, tenant_a, admin_user, quality_doc_draft):
    """Editing, deleting, and submitting a change order."""
    dco = _documentcontrol_create_dco(tenant_a, admin_user, quality_doc_draft)

    # Edit draft
    url_edit = reverse("quality:document_change_order_edit", kwargs={"pk": dco.pk})
    res_edit = client_a.post(
        url_edit,
        {
            "title": "Updated DCO Title",
            "change_type": "minor_revision",
            "priority": "high",
            "document": quality_doc_draft.pk,
            "target_revision": "1.1",
            "reason_for_change": "Expanded justification.",
            "change_description": "Detailed notes.",
        },
        follow=True,
    )
    assert res_edit.status_code == 200
    dco.refresh_from_db()
    assert dco.title == "Updated DCO Title"
    assert dco.priority == "high"
    assert _documentcontrol_audit_logs(dco, action="update").exists()

    # Submit to CCB (POST-only)
    url_submit = reverse("quality:document_change_order_submit", kwargs={"pk": dco.pk})
    assert client_a.get(url_submit).status_code == 405
    res_submit = client_a.post(url_submit, follow=True)
    assert res_submit.status_code == 200
    dco.refresh_from_db()
    assert dco.status == "ccb_review"
    assert _documentcontrol_audit_logs(dco, action="submit").exists()

    # Deletion fails on submitted change order
    url_del = reverse("quality:document_change_order_delete", kwargs={"pk": dco.pk})
    res_bad_del = client_a.post(url_del, follow=True)
    assert any("Only draft change orders can be deleted" in m for m in _documentcontrol_get_messages(res_bad_del))
    assert DocumentChangeOrder.objects.filter(pk=dco.pk).exists()

    # Reset to draft and delete
    dco.status = "draft"
    dco.save()
    assert client_a.get(url_del).status_code == 405
    res_del = client_a.post(url_del, follow=False)
    assert res_del.status_code == 302
    assert not DocumentChangeOrder.objects.filter(pk=dco.pk).exists()
    assert _documentcontrol_audit_logs(dco, action="delete").exists()


def test_documentcontrol_change_order_ccb_decision_status_guard_and_admin_gating(
    client_a, member_client, admin_user, tenant_a, quality_doc_draft
):
    """CCB decision requires admin, enforces status guard I1, and records approval/rejection."""
    dco = _documentcontrol_create_dco(tenant_a, admin_user, quality_doc_draft, status="draft")
    url_ccb = reverse("quality:document_change_order_ccb_decision", kwargs={"pk": dco.pk})

    # Non-admin member gets 403 Forbidden
    res_member = member_client.post(url_ccb, {"decision": "approved"})
    assert res_member.status_code == 403

    # Status guard I1: draft change order cannot receive CCB determination
    res_draft_ccb = client_a.post(url_ccb, {"decision": "approved"}, follow=True)
    assert any("Cannot record CCB determination" in m for m in _documentcontrol_get_messages(res_draft_ccb))

    # Move to ccb_review
    dco.status = "ccb_review"
    dco.save()

    # Invalid decision is rejected
    res_bad_dec = client_a.post(url_ccb, {"decision": "invalid_choice"}, follow=True)
    assert any("Invalid CCB decision" in m for m in _documentcontrol_get_messages(res_bad_dec))

    # Approve decision
    res_approve = client_a.post(
        url_ccb,
        {"decision": "approved", "closure_notes": "Formal CCB approval granted unanimously."},
        follow=True,
    )
    assert res_approve.status_code == 200
    dco.refresh_from_db()
    assert dco.status == "approved"
    assert dco.ccb_decision == "approved"
    assert dco.ccb_decision_by == admin_user
    assert dco.ccb_decision_date is not None
    assert "Formal CCB approval" in dco.closure_notes
    assert _documentcontrol_audit_logs(dco, action="ccb_dec").exists()

    # Cannot re-decide on already approved/closed DCO
    res_redecide = client_a.post(url_ccb, {"decision": "rejected"}, follow=True)
    assert any("Cannot record CCB determination" in m for m in _documentcontrol_get_messages(res_redecide))


def test_documentcontrol_change_order_export_csv(client_a, quality_dco):
    """Change order CSV export downloads successfully."""
    url = reverse("quality:document_change_order_export")
    response = client_a.get(url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert 'filename="document_change_orders.csv"' in response["Content-Disposition"]
    assert quality_dco.title in response.content.decode("utf-8")


# ------------------------------------------------------------------ ElectronicSignatures Views


def test_documentcontrol_signature_list_filters_and_stats(client_a, quality_sig):
    """Signature list renders records, computes statistics, and filters by meaning."""
    url = reverse("quality:electronic_signature_list")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "signatures" in response.context
    assert "stats" in response.context
    assert "meaning_choices" in response.context

    pks = [s.pk for s in response.context["signatures"]]
    assert quality_sig.pk in pks

    stats = response.context["stats"]
    assert stats["total"] >= 1
    assert stats["approvals"] >= 1

    # Filter ?meaning=quality_approval
    res_meaning = client_a.get(url, {"meaning": "quality_approval"})
    assert quality_sig.pk in [s.pk for s in res_meaning.context["signatures"]]

    res_empty = client_a.get(url, {"meaning": "authored"})
    assert quality_sig.pk not in [s.pk for s in res_empty.context["signatures"]]


def test_documentcontrol_signature_detail_and_verify(client_a, quality_sig):
    """Signature detail provides context and verification route checks hash integrity."""
    url_detail = reverse("quality:electronic_signature_detail", kwargs={"pk": quality_sig.pk})
    res_detail = client_a.get(url_detail)

    assert res_detail.status_code == 200
    ctx = res_detail.context
    assert ctx["signature"] == quality_sig
    assert ctx["is_valid_hash"] is True

    # Verification route (authentic)
    url_verify = reverse("quality:electronic_signature_verify", kwargs={"pk": quality_sig.pk})
    res_verify = client_a.get(url_verify, follow=True)
    assert any("verified as authentic and tamper-free" in m for m in _documentcontrol_get_messages(res_verify))

    # Verification route (tampered)
    quality_sig.signature_hash = "0" * 64
    quality_sig.save(update_fields=["signature_hash"])
    res_tampered = client_a.get(url_verify, follow=True)
    assert any("Warning: Signature" in m for m in _documentcontrol_get_messages(res_tampered))


def test_documentcontrol_controlled_document_sign_lifecycle_guard_and_admin_gating(
    client_a, member_client, admin_user, member_user, quality_doc_draft, quality_doc_effective
):
    """Controlled document signing enforces lifecycle guard I5, password check, and admin gating I16."""
    # Obsolete document is locked against signing (I5)
    quality_doc_draft.lifecycle_state = "obsolete"
    quality_doc_draft.save()

    url_sign_obs = reverse("quality:controlled_document_sign", kwargs={"pk": quality_doc_draft.pk})
    res_locked = client_a.get(url_sign_obs, follow=True)
    assert any("locked against signature execution" in m for m in _documentcontrol_get_messages(res_locked))

    # Reset doc to draft
    quality_doc_draft.lifecycle_state = "draft"
    quality_doc_draft.save()
    url_sign = reverse("quality:controlled_document_sign", kwargs={"pk": quality_doc_draft.pk})

    # GET sign form
    assert client_a.get(url_sign).status_code == 200

    # Invalid password fails form validation
    bad_pass_data = {
        "signature_meaning": "reviewed",
        "signer_title": "Staff Engineer",
        "comments": "Reviewed thoroughly.",
        "password": "WrongPassword123!",
    }
    res_bad_pw = client_a.post(url_sign, bad_pass_data)
    assert res_bad_pw.status_code == 200
    assert "Invalid credentials" in str(res_bad_pw.content)
    assert not ElectronicSignatureRecord.objects.filter(comments="Reviewed thoroughly.").exists()

    # Admin gating for quality_approval (I16): member user rejected
    approval_data = {
        "signature_meaning": "quality_approval",
        "signer_title": "QA Specialist",
        "comments": "Quality release sign-off.",
        "password": "TestPass123!",
    }
    res_member = member_client.post(url_sign, approval_data, follow=True)
    assert any("Administrative authorization is required" in m for m in _documentcontrol_get_messages(res_member))
    assert not ElectronicSignatureRecord.objects.filter(comments="Quality release sign-off.").exists()

    # Member user can sign with non-approval role (e.g. reviewed)
    member_valid_data = {
        "signature_meaning": "reviewed",
        "signer_title": "QA Specialist",
        "comments": "Peer verification completed.",
        "password": "TestPass123!",
    }
    res_member_ok = member_client.post(url_sign, member_valid_data, follow=False)
    assert res_member_ok.status_code == 302
    assert ElectronicSignatureRecord.objects.filter(comments="Peer verification completed.").exists()

    # Admin user can sign with quality_approval
    res_admin = client_a.post(url_sign, approval_data, follow=False)
    assert res_admin.status_code == 302
    sig = ElectronicSignatureRecord.objects.get(comments="Quality release sign-off.")
    assert sig.signer == admin_user
    assert sig.signature_meaning == "quality_approval"
    assert sig.signature_hash == sig.generate_hash()
    assert _documentcontrol_audit_logs(sig, action="sign").exists()


def test_documentcontrol_signature_export_csv(client_a, quality_sig):
    """Electronic signature CSV export downloads successfully."""
    url = reverse("quality:electronic_signature_export")
    response = client_a.get(url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert 'filename="electronic_signatures.csv"' in response["Content-Disposition"]
    assert quality_sig.signer_name in response.content.decode("utf-8")


# ------------------------------------------------------------------ DocumentAcknowledgments Views


def test_documentcontrol_acknowledgment_list_filters_and_stats(
    client_a, quality_ack, quality_ack_b
):
    """Acknowledgment list renders records, enforces tenant scoping, and computes statistics."""
    url = reverse("quality:document_acknowledgment_list")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "acknowledgments" in response.context
    assert "stats" in response.context
    assert "status_choices" in response.context

    ack_pks = [a.pk for a in response.context["acknowledgments"]]
    assert quality_ack.pk in ack_pks
    assert quality_ack_b.pk not in ack_pks

    stats = response.context["stats"]
    assert stats["total"] >= 1
    assert stats["pending"] >= 1

    # Filter ?status=pending
    res_status = client_a.get(url, {"status": "pending"})
    assert quality_ack.pk in [a.pk for a in res_status.context["acknowledgments"]]


def test_documentcontrol_acknowledgment_detail_and_create(
    client_a, admin_user, member_user, quality_doc_effective, quality_ack_b
):
    """Detail view provides context, and create view assigns acknowledgment with audit trail."""
    url_create = reverse("quality:document_acknowledgment_create")

    # GET create form
    assert client_a.get(url_create).status_code == 200

    post_data = {
        "document": quality_doc_effective.pk,
        "document_revision": quality_doc_effective.revision,
        "user": member_user.pk,
        "due_date": (timezone.now() + timedelta(days=14)).date(),
        "notes": "Mandatory annual SOP review.",
    }
    response = client_a.post(url_create, post_data, follow=False)
    assert response.status_code == 302

    ack = DocumentAcknowledgment.objects.get(notes="Mandatory annual SOP review.")
    assert ack.user == member_user
    assert ack.status == "pending"
    assert response.url == reverse("quality:document_acknowledgment_detail", kwargs={"pk": ack.pk})
    assert _documentcontrol_audit_logs(ack, action="create").exists()

    # Detail context
    res_detail = client_a.get(response.url)
    assert res_detail.status_code == 200
    assert res_detail.context["acknowledgment"] == ack
    assert res_detail.context["can_sign"] is True

    # Cross-tenant IDOR returns 404
    url_b = reverse("quality:document_acknowledgment_detail", kwargs={"pk": quality_ack_b.pk})
    assert client_a.get(url_b).status_code == 404


def test_documentcontrol_acknowledgment_sign_authorization_and_lifecycle(
    client_a, member_client, admin_user, member_user, tenant_a, quality_doc_effective
):
    """Signing acknowledgment enforces user authorization C1, creates electronic signature, and locks record."""
    ack = _documentcontrol_create_ack(
        tenant_a, user=admin_user, document=quality_doc_effective
    )
    url_sign = reverse("quality:document_acknowledgment_sign", kwargs={"pk": ack.pk})

    # Authorization check C1: member user cannot sign acknowledgment assigned to admin user
    res_unauth = member_client.get(url_sign, follow=True)
    assert any("not authorized to sign this acknowledgment on behalf of another user" in m for m in _documentcontrol_get_messages(res_unauth))

    # Assigned user GET sign form
    res_get = client_a.get(url_sign)
    assert res_get.status_code == 200
    assert "form" in res_get.context

    # POST valid electronic signature
    sign_data = {
        "signature_meaning": "acknowledgment",
        "signer_title": "QA Director",
        "comments": "I have read and fully understood the SOP requirements.",
        "password": "TestPass123!",
    }
    res_sign = client_a.post(url_sign, sign_data, follow=False)
    assert res_sign.status_code == 302

    ack.refresh_from_db()
    assert ack.status == "acknowledged"
    assert ack.acknowledged_at is not None
    assert ack.signature_record is not None
    assert ack.signature_record.signature_meaning == "acknowledgment"
    assert ack.signature_record.signature_hash == ack.signature_record.generate_hash()

    # Verify audit logs
    assert _documentcontrol_audit_logs(ack, action="ack").exists()
    assert _documentcontrol_audit_logs(ack.signature_record, action="sign").exists()

    # Already acknowledged guard
    res_re_sign = client_a.get(url_sign, follow=True)
    assert any("has already been signed" in m for m in _documentcontrol_get_messages(res_re_sign))

    # Cannot edit acknowledged record
    url_edit = reverse("quality:document_acknowledgment_edit", kwargs={"pk": ack.pk})
    res_edit = client_a.get(url_edit, follow=True)
    assert any("already been signed and is locked" in m for m in _documentcontrol_get_messages(res_edit))


def test_documentcontrol_acknowledgment_delete_admin_required(
    client_a, member_client, tenant_a, member_user, quality_doc_effective
):
    """Deleting an acknowledgment requires admin authority (I14), POST-only, and rejects executed records."""
    ack = _documentcontrol_create_ack(tenant_a, user=member_user, document=quality_doc_effective)
    url_del = reverse("quality:document_acknowledgment_delete", kwargs={"pk": ack.pk})

    # Non-admin member gets 403 Forbidden (I14)
    res_member = member_client.post(url_del)
    assert res_member.status_code == 403

    # GET returns 405 Method Not Allowed
    assert client_a.get(url_del).status_code == 405

    # Cannot delete acknowledged record
    ack.status = "acknowledged"
    ack.save()
    res_del_ack = client_a.post(url_del, follow=True)
    assert any("Cannot delete an executed quality acknowledgment" in m for m in _documentcontrol_get_messages(res_del_ack))
    assert DocumentAcknowledgment.objects.filter(pk=ack.pk).exists()

    # Can delete pending record
    ack.status = "pending"
    ack.save()
    res_del = client_a.post(url_del, follow=False)
    assert res_del.status_code == 302
    assert not DocumentAcknowledgment.objects.filter(pk=ack.pk).exists()
    assert _documentcontrol_audit_logs(ack, action="delete").exists()


def test_documentcontrol_acknowledgment_export_csv(client_a, quality_ack):
    """Acknowledgment CSV export downloads successfully."""
    url = reverse("quality:document_acknowledgment_export")
    response = client_a.get(url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert 'filename="document_acknowledgments.csv"' in response["Content-Disposition"]
    assert quality_ack.document.number in response.content.decode("utf-8")
