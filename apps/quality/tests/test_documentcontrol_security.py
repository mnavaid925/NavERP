"""
Security and Multi-Tenant Isolation Tests for Module 12.1: Document Control & Management.

Covers:
1. Multi-Tenant IDOR:
   - Client B attempting to access Tenant A ControlledDocument endpoints (detail, edit, delete, submit, approve, make-effective, obsolete, revise, sign) returns HTTP 404.
   - Client B attempting to access Tenant A DocumentChangeOrder endpoints (detail, edit, delete, submit, ccb-decision) returns HTTP 404.
   - Client B attempting to access Tenant A ElectronicSignatureRecord endpoints (detail, verify) returns HTTP 404.
   - Client B attempting to access Tenant A DocumentAcknowledgment endpoints (detail, edit, delete, sign) returns HTTP 404.
   - List and export endpoints strictly isolate tenant data; 0 records from foreign tenants leaked.
   - Symmetric IDOR: Client A requesting Tenant B resources returns HTTP 404.
2. Form FK Cross-Tenant Injection Defense (reject_foreign):
   - ControlledDocumentForm rejects foreign department.
   - DocumentChangeOrderForm rejects foreign document.
   - DocumentAcknowledgmentForm rejects foreign document, foreign user, or foreign employee.
3. Authentication & Authorization (AuthN / AuthZ):
   - Unauthenticated requests to all endpoints redirect to login (HTTP 302).
   - Non-admin member users attempting tenant admin endpoints (controlled_document_approve, controlled_document_make_effective, controlled_document_obsolete, document_change_order_ccb_decision, document_acknowledgment_delete) receive HTTP 403 Forbidden.
   - Tenant admin users succeed on privileged endpoints.
4. Acknowledgment Recipient Verification (C1):
   - Non-admin unassigned user cannot forge compliance sign-off on another user's acknowledgment record.
   - Executed / already-acknowledged records cannot be re-signed or deleted.
5. Electronic Signature Security (21 CFR Part 11 & HMAC-SHA256):
   - 21 CFR Part 11 credential verification enforces correct user password; rejects bad password and unauthenticated/unset user (I2).
   - Approval signature meanings (quality_approval, management_approval, ccb_approval) require tenant admin authority (I16); author/reviewer allowed for members.
   - Lifecycle lock guard: documents in locked lifecycle states cannot be signed (I5).
   - Non-repudiation cryptographic verification: detects tampering with signature hash digest.
6. Unrestricted File Upload Prevention:
   - Stored XSS defense: .svg files strictly rejected (C3).
   - Unpermitted executable/script extensions (.exe, .php, .sh, .bat) rejected.
   - Oversized files (>20 MB limit) rejected.
   - Permitted document formats (.pdf, .docx, .png) accepted.
7. Mass Assignment Defense (I13):
   - Tampered tenant, owner, requested_by, status, or number cannot be injected via POST on document creation/editing or change order creation.
8. Audit Logging:
   - Comprehensive audit log records created for all state mutations across ControlledDocuments, DocumentChangeOrders, ElectronicSignatures, and DocumentAcknowledgments.
"""

import csv
import io
from datetime import timedelta
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES
from apps.core.models import AuditLog, OrgUnit, Party, PartyRole
from apps.hrm.models import EmployeeProfile
from apps.quality.forms import (
    ControlledDocumentForm,
    ControlledDocumentRevisionForm,
    DocumentAcknowledgmentForm,
    DocumentChangeOrderForm,
    ElectronicSignatureForm,
)
from apps.quality.models import (
    ControlledDocument,
    DocumentAcknowledgment,
    DocumentChangeOrder,
    ElectronicSignatureRecord,
)

User = get_user_model()
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


@pytest.fixture
def quality_sig_b(db, tenant_b, admin_b, quality_doc_b):
    sig = ElectronicSignatureRecord(
        tenant=tenant_b,
        document=quality_doc_b,
        signer=admin_b,
        signer_name="Globex QA Officer",
        signer_title="Globex QA Lead",
        signature_meaning="quality_approval",
        document_revision=quality_doc_b.revision,
        ip_address="127.0.0.1",
        comments="Globex approved.",
    )
    sig.save()
    return sig


# =====================================================================
# Helpers (All prefixed with _documentcontrol_*)
# =====================================================================


def _documentcontrol_messages(response):
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


def _documentcontrol_parse_csv(response):
    """Parse CSV response into rows."""
    content = response.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    return list(reader)


def _documentcontrol_create_doc(tenant, owner, **kwargs):
    """Helper to create a ControlledDocument with defaults."""
    fields = {
        "tenant": tenant,
        "owner": owner,
        "title": "Security Auxiliary Document",
        "document_type": "sop",
        "revision": "1.0",
        "lifecycle_state": "draft",
        "classification": "internal",
        "description": "Auxiliary document for security testing.",
        "review_interval_months": 12,
        "retention_years": 10,
    }
    fields.update(kwargs)
    return ControlledDocument.objects.create(**fields)


def _documentcontrol_create_dco(tenant, requested_by, document, **kwargs):
    """Helper to create a DocumentChangeOrder with defaults."""
    fields = {
        "tenant": tenant,
        "requested_by": requested_by,
        "document": document,
        "title": "Security Change Request",
        "change_type": "major_revision",
        "priority": "standard",
        "status": "draft",
        "reason_for_change": "Security audit alignment.",
        "change_description": "Audit updates.",
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
        "due_date": timezone.now().date() + timedelta(days=14),
    }
    fields.update(kwargs)
    return DocumentAcknowledgment.objects.create(**fields)


def _documentcontrol_base_doc_data(department, extra=None):
    """Payload helper for ControlledDocumentForm."""
    data = {
        "title": "Standard Operating Procedure for Quality Control",
        "document_type": "sop",
        "department": department.pk if department else "",
        "revision": "1.0",
        "classification": "internal",
        "description": "Standard operating procedure description.",
        "change_summary": "Initial draft of SOP.",
        "effective_date": timezone.now().date(),
        "review_interval_months": 12,
        "retention_years": 5,
        "is_template": False,
    }
    if extra:
        data.update(extra)
    return data


# =====================================================================
# 1. Multi-Tenant IDOR Tests
# =====================================================================


def test_documentcontrol_security_controlled_document_detail_idor(client_b, quality_doc_draft):
    """Client B attempting to view Tenant A ControlledDocument detail returns HTTP 404."""
    url = reverse("quality:controlled_document_detail", kwargs={"pk": quality_doc_draft.pk})
    res = client_b.get(url)
    assert res.status_code == 404


def test_documentcontrol_security_controlled_document_edit_idor(client_b, quality_doc_draft):
    """Client B attempting GET or POST to edit Tenant A ControlledDocument returns HTTP 404."""
    url = reverse("quality:controlled_document_edit", kwargs={"pk": quality_doc_draft.pk})
    assert client_b.get(url).status_code == 404

    payload = {"title": "Hostile Hijack Title", "document_type": "sop", "revision": "1.0"}
    res_post = client_b.post(url, payload)
    assert res_post.status_code == 404
    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.title != "Hostile Hijack Title"


def test_documentcontrol_security_controlled_document_delete_idor(client_b, quality_doc_draft):
    """Client B attempting POST to delete Tenant A ControlledDocument returns HTTP 404 and doc remains."""
    url = reverse("quality:controlled_document_delete", kwargs={"pk": quality_doc_draft.pk})
    res = client_b.post(url)
    assert res.status_code == 404
    assert ControlledDocument.objects.filter(pk=quality_doc_draft.pk).exists()


def test_documentcontrol_security_controlled_document_submit_idor(client_b, quality_doc_draft):
    """Client B attempting to transition Tenant A ControlledDocument to review returns HTTP 404."""
    url = reverse("quality:controlled_document_submit", kwargs={"pk": quality_doc_draft.pk})
    res = client_b.post(url)
    assert res.status_code == 404
    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.lifecycle_state == "draft"


def test_documentcontrol_security_controlled_document_approve_idor(client_b, quality_doc_draft):
    """Client B attempting to approve Tenant A ControlledDocument returns HTTP 404."""
    quality_doc_draft.lifecycle_state = "in_review"
    quality_doc_draft.save(update_fields=["lifecycle_state"])

    url = reverse("quality:controlled_document_approve", kwargs={"pk": quality_doc_draft.pk})
    res = client_b.post(url)
    assert res.status_code == 404
    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.lifecycle_state == "in_review"


def test_documentcontrol_security_controlled_document_make_effective_idor(client_b, quality_doc_draft):
    """Client B attempting to make Tenant A ControlledDocument effective returns HTTP 404."""
    quality_doc_draft.lifecycle_state = "approved"
    quality_doc_draft.save(update_fields=["lifecycle_state"])

    url = reverse("quality:controlled_document_make_effective", kwargs={"pk": quality_doc_draft.pk})
    res = client_b.post(url)
    assert res.status_code == 404
    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.lifecycle_state == "approved"


def test_documentcontrol_security_controlled_document_obsolete_idor(client_b, quality_doc_effective):
    """Client B attempting to retire Tenant A ControlledDocument to obsolete returns HTTP 404."""
    url = reverse("quality:controlled_document_obsolete", kwargs={"pk": quality_doc_effective.pk})
    res = client_b.post(url)
    assert res.status_code == 404
    quality_doc_effective.refresh_from_db()
    assert quality_doc_effective.lifecycle_state == "effective"


def test_documentcontrol_security_controlled_document_new_revision_idor(client_b, quality_doc_effective):
    """Client B attempting GET or POST new revision on Tenant A ControlledDocument returns HTTP 404."""
    url = reverse("quality:controlled_document_new_revision", kwargs={"pk": quality_doc_effective.pk})
    assert client_b.get(url).status_code == 404

    payload = {"revision": "3.0", "change_summary": "Illicit foreign revision attempt"}
    assert client_b.post(url, payload).status_code == 404
    assert not ControlledDocument.objects.filter(revision="3.0", title=quality_doc_effective.title).exists()


def test_documentcontrol_security_controlled_document_sign_idor(client_b, quality_doc_draft):
    """Client B attempting GET or POST to sign Tenant A ControlledDocument returns HTTP 404."""
    url = reverse("quality:controlled_document_sign", kwargs={"pk": quality_doc_draft.pk})
    assert client_b.get(url).status_code == 404

    payload = {
        "signature_meaning": "authored",
        "signer_title": "Globex Impostor",
        "password": "TestPass123!",
    }
    assert client_b.post(url, payload).status_code == 404
    assert not ElectronicSignatureRecord.objects.filter(document=quality_doc_draft, signer_title="Globex Impostor").exists()


def test_documentcontrol_security_dco_detail_idor(client_b, quality_dco):
    """Client B attempting to view Tenant A DocumentChangeOrder detail returns HTTP 404."""
    url = reverse("quality:document_change_order_detail", kwargs={"pk": quality_dco.pk})
    assert client_b.get(url).status_code == 404


def test_documentcontrol_security_dco_edit_idor(client_b, quality_dco):
    """Client B attempting GET or POST to edit Tenant A DocumentChangeOrder returns HTTP 404."""
    url = reverse("quality:document_change_order_edit", kwargs={"pk": quality_dco.pk})
    assert client_b.get(url).status_code == 404

    payload = {"title": "Hostile DCO Override", "change_type": "major_revision", "priority": "high"}
    assert client_b.post(url, payload).status_code == 404
    quality_dco.refresh_from_db()
    assert quality_dco.title != "Hostile DCO Override"


def test_documentcontrol_security_dco_delete_idor(client_b, quality_dco):
    """Client B attempting POST to delete Tenant A DocumentChangeOrder returns HTTP 404."""
    url = reverse("quality:document_change_order_delete", kwargs={"pk": quality_dco.pk})
    assert client_b.post(url).status_code == 404
    assert DocumentChangeOrder.objects.filter(pk=quality_dco.pk).exists()


def test_documentcontrol_security_dco_submit_idor(client_b, quality_dco):
    """Client B attempting to submit Tenant A DocumentChangeOrder returns HTTP 404."""
    quality_dco.status = "draft"
    quality_dco.save(update_fields=["status"])

    url = reverse("quality:document_change_order_submit", kwargs={"pk": quality_dco.pk})
    assert client_b.post(url).status_code == 404
    quality_dco.refresh_from_db()
    assert quality_dco.status == "draft"


def test_documentcontrol_security_dco_ccb_decision_idor(client_b, quality_dco):
    """Client B attempting to record CCB decision on Tenant A DCO returns HTTP 404."""
    quality_dco.status = "ccb_review"
    quality_dco.save(update_fields=["status"])

    url = reverse("quality:document_change_order_ccb_decision", kwargs={"pk": quality_dco.pk})
    payload = {"decision": "approved", "closure_notes": "Illicit cross-tenant CCB approval"}
    assert client_b.post(url, payload).status_code == 404
    quality_dco.refresh_from_db()
    assert quality_dco.status == "ccb_review"
    assert quality_dco.ccb_decision == "pending"


def test_documentcontrol_security_electronic_signature_detail_idor(client_b, quality_sig):
    """Client B attempting to view Tenant A ElectronicSignatureRecord detail returns HTTP 404."""
    url = reverse("quality:electronic_signature_detail", kwargs={"pk": quality_sig.pk})
    assert client_b.get(url).status_code == 404


def test_documentcontrol_security_electronic_signature_verify_idor(client_b, quality_sig):
    """Client B attempting to verify Tenant A ElectronicSignatureRecord returns HTTP 404."""
    url = reverse("quality:electronic_signature_verify", kwargs={"pk": quality_sig.pk})
    assert client_b.get(url).status_code == 404


def test_documentcontrol_security_acknowledgment_detail_idor(client_b, quality_ack):
    """Client B attempting to view Tenant A DocumentAcknowledgment detail returns HTTP 404."""
    url = reverse("quality:document_acknowledgment_detail", kwargs={"pk": quality_ack.pk})
    assert client_b.get(url).status_code == 404


def test_documentcontrol_security_acknowledgment_edit_idor(client_b, quality_ack):
    """Client B attempting GET or POST to edit Tenant A DocumentAcknowledgment returns HTTP 404."""
    url = reverse("quality:document_acknowledgment_edit", kwargs={"pk": quality_ack.pk})
    assert client_b.get(url).status_code == 404

    payload = {"notes": "Hostile Acknowledgment Notes Modification"}
    assert client_b.post(url, payload).status_code == 404
    quality_ack.refresh_from_db()
    assert quality_ack.notes != "Hostile Acknowledgment Notes Modification"


def test_documentcontrol_security_acknowledgment_delete_idor(client_b, quality_ack):
    """Client B attempting POST to delete Tenant A DocumentAcknowledgment returns HTTP 404."""
    url = reverse("quality:document_acknowledgment_delete", kwargs={"pk": quality_ack.pk})
    assert client_b.post(url).status_code == 404
    assert DocumentAcknowledgment.objects.filter(pk=quality_ack.pk).exists()


def test_documentcontrol_security_acknowledgment_sign_idor(client_b, quality_ack):
    """Client B attempting GET or POST to sign Tenant A DocumentAcknowledgment returns HTTP 404."""
    url = reverse("quality:document_acknowledgment_sign", kwargs={"pk": quality_ack.pk})
    assert client_b.get(url).status_code == 404

    payload = {
        "signature_meaning": "acknowledgment",
        "signer_title": "Globex Impostor",
        "password": "TestPass123!",
    }
    assert client_b.post(url, payload).status_code == 404
    quality_ack.refresh_from_db()
    assert quality_ack.status == "pending"
    assert quality_ack.signature_record is None


def test_documentcontrol_security_symmetric_idor_tenant_a_cannot_access_tenant_b(
    client_a, quality_doc_b, quality_dco_b, quality_ack_b, quality_sig_b
):
    """Symmetric verification: Client A attempting to access Tenant B resources returns HTTP 404."""
    # ControlledDocument
    assert client_a.get(reverse("quality:controlled_document_detail", args=[quality_doc_b.pk])).status_code == 404
    assert client_a.get(reverse("quality:controlled_document_edit", args=[quality_doc_b.pk])).status_code == 404
    assert client_a.post(reverse("quality:controlled_document_delete", args=[quality_doc_b.pk])).status_code == 404

    # DocumentChangeOrder
    assert client_a.get(reverse("quality:document_change_order_detail", args=[quality_dco_b.pk])).status_code == 404
    assert client_a.get(reverse("quality:document_change_order_edit", args=[quality_dco_b.pk])).status_code == 404
    assert client_a.post(reverse("quality:document_change_order_delete", args=[quality_dco_b.pk])).status_code == 404

    # DocumentAcknowledgment
    assert client_a.get(reverse("quality:document_acknowledgment_detail", args=[quality_ack_b.pk])).status_code == 404
    assert client_a.get(reverse("quality:document_acknowledgment_edit", args=[quality_ack_b.pk])).status_code == 404
    assert client_a.post(reverse("quality:document_acknowledgment_delete", args=[quality_ack_b.pk])).status_code == 404

    # ElectronicSignatureRecord
    assert client_a.get(reverse("quality:electronic_signature_detail", args=[quality_sig_b.pk])).status_code == 404
    assert client_a.get(reverse("quality:electronic_signature_verify", args=[quality_sig_b.pk])).status_code == 404


def test_documentcontrol_security_list_and_export_tenant_isolation(
    client_b, quality_doc_draft, quality_doc_effective, quality_doc_b,
    quality_dco, quality_dco_b, quality_sig, quality_sig_b, quality_ack, quality_ack_b,
    tenant_a, admin_user
):
    """List views and streaming CSV exports return ONLY authenticated tenant records (0 foreign records)."""
    # 1. Controlled Documents list
    res_docs = client_b.get(reverse("quality:controlled_document_list"), {"latest": "all"})
    assert res_docs.status_code == 200
    doc_pks = [d.pk for d in res_docs.context["documents"]]
    assert quality_doc_b.pk in doc_pks
    assert quality_doc_draft.pk not in doc_pks
    assert quality_doc_effective.pk not in doc_pks

    # Controlled Documents CSV Export
    res_doc_csv = client_b.get(reverse("quality:controlled_document_export"))
    assert res_doc_csv.status_code == 200
    doc_csv_text = res_doc_csv.content.decode("utf-8")
    assert quality_doc_b.title in doc_csv_text
    assert quality_doc_draft.title not in doc_csv_text
    assert quality_doc_effective.title not in doc_csv_text

    # Controlled Documents Vault
    obs_a = _documentcontrol_create_doc(tenant_a, admin_user, lifecycle_state="obsolete", is_latest_revision=False)
    res_vault = client_b.get(reverse("quality:document_archive_vault"))
    assert res_vault.status_code == 200
    vault_pks = [d.pk for d in res_vault.context["vault_documents"]]
    assert obs_a.pk not in vault_pks

    # 2. Change Orders list and export
    res_dco = client_b.get(reverse("quality:document_change_order_list"))
    assert res_dco.status_code == 200
    dco_pks = [d.pk for d in res_dco.context["change_orders"]]
    assert quality_dco_b.pk in dco_pks
    assert quality_dco.pk not in dco_pks

    res_dco_csv = client_b.get(reverse("quality:document_change_order_export"))
    assert res_dco_csv.status_code == 200
    dco_csv_text = res_dco_csv.content.decode("utf-8")
    assert quality_dco_b.title in dco_csv_text
    assert quality_dco.title not in dco_csv_text

    # 3. Signatures list and export
    res_sig = client_b.get(reverse("quality:electronic_signature_list"))
    assert res_sig.status_code == 200
    sig_pks = [s.pk for s in res_sig.context["signatures"]]
    assert quality_sig_b.pk in sig_pks
    assert quality_sig.pk not in sig_pks

    res_sig_csv = client_b.get(reverse("quality:electronic_signature_export"))
    assert res_sig_csv.status_code == 200
    sig_csv_text = res_sig_csv.content.decode("utf-8")
    assert quality_sig_b.signer_name in sig_csv_text
    assert quality_sig.signer_name not in sig_csv_text

    # 4. Acknowledgments list and export
    res_ack = client_b.get(reverse("quality:document_acknowledgment_list"))
    assert res_ack.status_code == 200
    ack_pks = [a.pk for a in res_ack.context["acknowledgments"]]
    assert quality_ack_b.pk in ack_pks
    assert quality_ack.pk not in ack_pks

    res_ack_csv = client_b.get(reverse("quality:document_acknowledgment_export"))
    assert res_ack_csv.status_code == 200
    ack_csv_text = res_ack_csv.content.decode("utf-8")
    assert quality_ack_b.user.username in ack_csv_text
    assert quality_ack.user.username not in ack_csv_text


# =====================================================================
# 2. Form Foreign Key Cross-Tenant Validation (reject_foreign)
# =====================================================================


def test_documentcontrol_security_form_fk_department_cross_tenant_rejected(
    tenant_a, quality_department, quality_department_b
):
    """ControlledDocumentForm rejects department from foreign tenant."""
    # Scoped queryset excludes foreign department
    form = ControlledDocumentForm(tenant=tenant_a)
    assert quality_department.pk in list(form.fields["department"].queryset.values_list("pk", flat=True))
    assert quality_department_b.pk not in list(form.fields["department"].queryset.values_list("pk", flat=True))

    # Submitting foreign department fails clean validation
    data = _documentcontrol_base_doc_data(quality_department_b)
    bound_form = ControlledDocumentForm(data=data, tenant=tenant_a)
    assert not bound_form.is_valid()
    assert "department" in bound_form.errors or "__all__" in bound_form.errors


def test_documentcontrol_security_form_fk_dco_document_cross_tenant_rejected(
    tenant_a, quality_doc_draft, quality_doc_b
):
    """DocumentChangeOrderForm rejects document from foreign tenant."""
    form = DocumentChangeOrderForm(tenant=tenant_a)
    assert quality_doc_draft.pk in list(form.fields["document"].queryset.values_list("pk", flat=True))
    assert quality_doc_b.pk not in list(form.fields["document"].queryset.values_list("pk", flat=True))

    data = {
        "title": "Security DCO Revise",
        "change_type": "major_revision",
        "priority": "standard",
        "document": quality_doc_b.pk,
        "target_revision": "2.0",
        "reason_for_change": "Testing foreign doc rejection.",
        "change_description": "Attempted foreign document binding.",
    }
    bound_form = DocumentChangeOrderForm(data=data, tenant=tenant_a)
    assert not bound_form.is_valid()
    assert "document" in bound_form.errors or "__all__" in bound_form.errors


def test_documentcontrol_security_form_fk_acknowledgment_cross_tenant_rejected(
    tenant_a, quality_doc_effective, quality_doc_b, admin_user, admin_b, quality_employee, quality_employee_b
):
    """DocumentAcknowledgmentForm rejects foreign document, foreign user, or foreign employee."""
    form = DocumentAcknowledgmentForm(tenant=tenant_a)
    assert quality_doc_effective.pk in list(form.fields["document"].queryset.values_list("pk", flat=True))
    assert quality_doc_b.pk not in list(form.fields["document"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in list(form.fields["user"].queryset.values_list("pk", flat=True))
    assert admin_b.pk not in list(form.fields["user"].queryset.values_list("pk", flat=True))
    assert quality_employee.pk in list(form.fields["employee"].queryset.values_list("pk", flat=True))
    assert quality_employee_b.pk not in list(form.fields["employee"].queryset.values_list("pk", flat=True))

    valid_base = {
        "document": quality_doc_effective.pk,
        "document_revision": quality_doc_effective.revision,
        "user": admin_user.pk,
        "employee": quality_employee.pk,
        "due_date": timezone.now().date() + timedelta(days=7),
    }

    # Foreign document
    data_bad_doc = dict(valid_base, document=quality_doc_b.pk)
    f_doc = DocumentAcknowledgmentForm(data=data_bad_doc, tenant=tenant_a)
    assert not f_doc.is_valid()
    assert "document" in f_doc.errors or "__all__" in f_doc.errors

    # Foreign user
    data_bad_user = dict(valid_base, user=admin_b.pk)
    f_user = DocumentAcknowledgmentForm(data=data_bad_user, tenant=tenant_a)
    assert not f_user.is_valid()
    assert "user" in f_user.errors or "__all__" in f_user.errors

    # Foreign employee
    data_bad_emp = dict(valid_base, employee=quality_employee_b.pk)
    f_emp = DocumentAcknowledgmentForm(data=data_bad_emp, tenant=tenant_a)
    assert not f_emp.is_valid()
    assert "employee" in f_emp.errors or "__all__" in f_emp.errors


# =====================================================================
# 3. Authentication & Authorization (AuthN / AuthZ)
# =====================================================================


def test_documentcontrol_security_unauthenticated_redirects_to_login(
    quality_doc_draft, quality_doc_effective, quality_dco, quality_sig, quality_ack
):
    """Anonymous client is redirected to login (HTTP 302) on all quality endpoints."""
    anon = Client()
    endpoints = [
        # ControlledDocuments
        reverse("quality:controlled_document_list"),
        reverse("quality:controlled_document_create"),
        reverse("quality:controlled_document_export"),
        reverse("quality:document_archive_vault"),
        reverse("quality:controlled_document_detail", args=[quality_doc_draft.pk]),
        reverse("quality:controlled_document_edit", args=[quality_doc_draft.pk]),
        reverse("quality:controlled_document_delete", args=[quality_doc_draft.pk]),
        reverse("quality:controlled_document_submit", args=[quality_doc_draft.pk]),
        reverse("quality:controlled_document_approve", args=[quality_doc_draft.pk]),
        reverse("quality:controlled_document_make_effective", args=[quality_doc_draft.pk]),
        reverse("quality:controlled_document_obsolete", args=[quality_doc_effective.pk]),
        reverse("quality:controlled_document_new_revision", args=[quality_doc_effective.pk]),
        reverse("quality:controlled_document_sign", args=[quality_doc_draft.pk]),
        # DocumentChangeOrders
        reverse("quality:document_change_order_list"),
        reverse("quality:document_change_order_create"),
        reverse("quality:document_change_order_export"),
        reverse("quality:document_change_order_detail", args=[quality_dco.pk]),
        reverse("quality:document_change_order_edit", args=[quality_dco.pk]),
        reverse("quality:document_change_order_delete", args=[quality_dco.pk]),
        reverse("quality:document_change_order_submit", args=[quality_dco.pk]),
        reverse("quality:document_change_order_ccb_decision", args=[quality_dco.pk]),
        # ElectronicSignatures
        reverse("quality:electronic_signature_list"),
        reverse("quality:electronic_signature_export"),
        reverse("quality:electronic_signature_detail", args=[quality_sig.pk]),
        reverse("quality:electronic_signature_verify", args=[quality_sig.pk]),
        # DocumentAcknowledgments
        reverse("quality:document_acknowledgment_list"),
        reverse("quality:document_acknowledgment_create"),
        reverse("quality:document_acknowledgment_export"),
        reverse("quality:document_acknowledgment_detail", args=[quality_ack.pk]),
        reverse("quality:document_acknowledgment_edit", args=[quality_ack.pk]),
        reverse("quality:document_acknowledgment_delete", args=[quality_ack.pk]),
        reverse("quality:document_acknowledgment_sign", args=[quality_ack.pk]),
    ]

    for url in endpoints:
        res = anon.get(url)
        assert res.status_code == 302, f"Expected 302 redirect for unauthenticated GET {url}, got {res.status_code}"
        assert res.url.startswith("/login/") or reverse(settings.LOGIN_URL) in res.url, (
            f"Expected redirect to login URL for {url}, got {res.url}"
        )


def test_documentcontrol_security_tenant_admin_endpoints_403_for_member(
    member_client, quality_doc_draft, quality_doc_effective, quality_dco, quality_ack
):
    """Non-admin member client receives HTTP 403 Forbidden on tenant-admin-gated endpoints."""
    # 1. Document Approve
    res_appr = member_client.post(reverse("quality:controlled_document_approve", args=[quality_doc_draft.pk]))
    assert res_appr.status_code == 403

    # 2. Document Make Effective
    res_eff = member_client.post(reverse("quality:controlled_document_make_effective", args=[quality_doc_draft.pk]))
    assert res_eff.status_code == 403

    # 3. Document Obsolete
    res_obs = member_client.post(reverse("quality:controlled_document_obsolete", args=[quality_doc_effective.pk]))
    assert res_obs.status_code == 403

    # 4. Change Order CCB Decision
    res_ccb = member_client.post(
        reverse("quality:document_change_order_ccb_decision", args=[quality_dco.pk]),
        {"decision": "approved"},
    )
    assert res_ccb.status_code == 403

    # 5. Document Acknowledgment Delete
    res_ack_del = member_client.post(reverse("quality:document_acknowledgment_delete", args=[quality_ack.pk]))
    assert res_ack_del.status_code == 403


def test_documentcontrol_security_tenant_admin_endpoints_permitted_for_admin(
    client_a, quality_doc_draft, quality_dco, quality_ack
):
    """Tenant admin client is authorized to execute privileged operations without 403."""
    # Document Approve: requires lifecycle_state in {'in_review', 'pending_approval'}
    quality_doc_draft.lifecycle_state = "in_review"
    quality_doc_draft.save(update_fields=["lifecycle_state"])

    res_appr = client_a.post(reverse("quality:controlled_document_approve", args=[quality_doc_draft.pk]))
    assert res_appr.status_code == 302
    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.lifecycle_state == "approved"

    # Document Make Effective: requires lifecycle_state == 'approved'
    res_eff = client_a.post(reverse("quality:controlled_document_make_effective", args=[quality_doc_draft.pk]))
    assert res_eff.status_code == 302
    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.lifecycle_state == "effective"

    # Document Obsolete: requires lifecycle_state == 'effective'
    res_obs = client_a.post(reverse("quality:controlled_document_obsolete", args=[quality_doc_draft.pk]))
    assert res_obs.status_code == 302
    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.lifecycle_state == "obsolete"

    # CCB Decision: requires status in {'submitted', 'in_assessment', 'ccb_review'}
    quality_dco.status = "ccb_review"
    quality_dco.save(update_fields=["status"])
    res_ccb = client_a.post(
        reverse("quality:document_change_order_ccb_decision", args=[quality_dco.pk]),
        {"decision": "approved", "closure_notes": "Authorized by QA Director."},
    )
    assert res_ccb.status_code == 302
    quality_dco.refresh_from_db()
    assert quality_dco.status == "approved"

    # Acknowledgment Delete: unexecuted pending ack can be deleted by admin
    res_ack_del = client_a.post(reverse("quality:document_acknowledgment_delete", args=[quality_ack.pk]))
    assert res_ack_del.status_code == 302
    assert not DocumentAcknowledgment.objects.filter(pk=quality_ack.pk).exists()


# =====================================================================
# 4. Acknowledgment Recipient Verification (C1)
# =====================================================================


def test_documentcontrol_security_acknowledgment_recipient_cannot_be_forged_by_unassigned_member(
    member_client, quality_ack
):
    """Compliance sign-off cannot be forged by an unassigned non-admin user (C1)."""
    # quality_ack is assigned to admin_user, not member_user
    url_sign = reverse("quality:document_acknowledgment_sign", args=[quality_ack.pk])

    # GET sign form blocked with authorization warning
    res_get = member_client.get(url_sign, follow=True)
    assert res_get.status_code == 200
    assert any("not authorized to sign this acknowledgment on behalf of another user" in m for m in _documentcontrol_messages(res_get))

    # POST sign attempt blocked even with member's valid credentials
    post_data = {
        "signature_meaning": "acknowledgment",
        "signer_title": "Unassigned Specialist",
        "password": "TestPass123!",
    }
    res_post = member_client.post(url_sign, post_data, follow=True)
    assert res_post.status_code == 200
    assert any("not authorized to sign this acknowledgment on behalf of another user" in m for m in _documentcontrol_messages(res_post))

    quality_ack.refresh_from_db()
    assert quality_ack.status == "pending"
    assert quality_ack.signature_record is None


def test_documentcontrol_security_acknowledgment_already_signed_cannot_be_resigned_or_deleted(
    client_a, quality_ack
):
    """Executed / acknowledged records cannot be re-signed or deleted."""
    # Mark acknowledgment as already signed
    quality_ack.status = "acknowledged"
    quality_ack.acknowledged_at = timezone.now()
    quality_ack.save(update_fields=["status", "acknowledged_at"])

    # Re-sign attempt is redirected with informational message
    url_sign = reverse("quality:document_acknowledgment_sign", args=[quality_ack.pk])
    res_sign = client_a.get(url_sign, follow=True)
    assert any("already been signed" in m for m in _documentcontrol_messages(res_sign))

    # Delete attempt by admin is blocked per I14
    url_del = reverse("quality:document_acknowledgment_delete", args=[quality_ack.pk])
    res_del = client_a.post(url_del, follow=True)
    assert any("Cannot delete an executed quality acknowledgment record" in m for m in _documentcontrol_messages(res_del))
    assert DocumentAcknowledgment.objects.filter(pk=quality_ack.pk).exists()


# =====================================================================
# 5. Electronic Signature Security (21 CFR Part 11 & HMAC-SHA256)
# =====================================================================


def test_documentcontrol_security_electronic_signature_password_verification_enforced(admin_user):
    """21 CFR Part 11 credential verification enforces correct password; rejects bad password and unset user."""
    # Bad password rejected
    form_bad = ElectronicSignatureForm(
        data={"signature_meaning": "authored", "password": "WrongPassword999!"},
        user=admin_user,
    )
    assert not form_bad.is_valid()
    assert "password" in form_bad.errors
    assert "FDA 21 CFR § 11.200" in str(form_bad.errors["password"])

    # Unset user (user=None) rejected per I2
    form_none = ElectronicSignatureForm(
        data={"signature_meaning": "authored", "password": "TestPass123!"},
        user=None,
    )
    assert not form_none.is_valid()
    assert "password" in form_none.errors

    # Valid password accepted
    form_valid = ElectronicSignatureForm(
        data={"signature_meaning": "authored", "password": "TestPass123!"},
        user=admin_user,
    )
    assert form_valid.is_valid(), form_valid.errors


def test_documentcontrol_security_electronic_signature_approval_meaning_gated_to_admin(
    member_client, quality_doc_draft
):
    """Approval signature meanings (quality_approval, management_approval, ccb_approval) require admin (I16)."""
    url_sign = reverse("quality:controlled_document_sign", args=[quality_doc_draft.pk])
    approval_meanings = ["quality_approval", "management_approval", "ccb_approval"]

    for meaning in approval_meanings:
        payload = {
            "signature_meaning": meaning,
            "signer_title": "Unauthorized Signer",
            "password": "TestPass123!",
        }
        res = member_client.post(url_sign, payload, follow=True)
        assert any("Administrative authorization is required" in m for m in _documentcontrol_messages(res))
        assert not ElectronicSignatureRecord.objects.filter(
            document=quality_doc_draft, signature_meaning=meaning
        ).exists()


def test_documentcontrol_security_electronic_signature_member_can_sign_author_or_reviewer(
    member_client, member_user, quality_doc_draft
):
    """Non-admin member user CAN sign with author or peer verification review meanings."""
    url_sign = reverse("quality:controlled_document_sign", args=[quality_doc_draft.pk])
    payload = {
        "signature_meaning": "reviewed",
        "signer_title": "Peer Technical Reviewer",
        "comments": "Reviewed methodology section for audit adherence.",
        "password": "TestPass123!",
    }
    res = member_client.post(url_sign, payload, follow=False)
    assert res.status_code == 302

    sig = ElectronicSignatureRecord.objects.get(
        document=quality_doc_draft, signature_meaning="reviewed", signer=member_user
    )
    assert sig.signer_name == member_user.username
    assert sig.signature_hash == sig.generate_hash()
    assert _documentcontrol_audit_logs(sig, action="sign").exists()


def test_documentcontrol_security_electronic_signature_locked_document_guard(
    client_a, quality_doc_draft
):
    """Documents in locked states (superseded, obsolete, archived) cannot be signed per I5."""
    locked_states = ["superseded", "obsolete", "archived"]
    url_sign = reverse("quality:controlled_document_sign", args=[quality_doc_draft.pk])

    for state in locked_states:
        quality_doc_draft.lifecycle_state = state
        quality_doc_draft.save(update_fields=["lifecycle_state"])

        # GET is blocked
        res_get = client_a.get(url_sign, follow=True)
        assert any("locked against signature execution" in m for m in _documentcontrol_messages(res_get))

        # POST is blocked
        payload = {
            "signature_meaning": "authored",
            "password": "TestPass123!",
        }
        res_post = client_a.post(url_sign, payload, follow=True)
        assert any("locked against signature execution" in m for m in _documentcontrol_messages(res_post))
        assert not ElectronicSignatureRecord.objects.filter(
            document=quality_doc_draft, comments="Locked test"
        ).exists()


def test_documentcontrol_security_electronic_signature_hmac_tamper_detection(
    client_a, quality_sig
):
    """HMAC-SHA256 signature hash guarantees tamper detection and non-repudiation."""
    # Authentic signature verifies cleanly
    assert quality_sig.signature_hash == quality_sig.generate_hash()

    url_verify = reverse("quality:electronic_signature_verify", args=[quality_sig.pk])
    res_auth = client_a.get(url_verify, follow=True)
    assert any("verified as authentic and tamper-free" in m for m in _documentcontrol_messages(res_auth))

    # Tamper with recorded hash digest in DB
    quality_sig.signature_hash = "0" * 64
    quality_sig.save(update_fields=["signature_hash"])
    assert quality_sig.signature_hash != quality_sig.generate_hash()

    res_tampered = client_a.get(url_verify, follow=True)
    assert any("Warning: Signature" in m and "does not match recorded state!" in m for m in _documentcontrol_messages(res_tampered))


# =====================================================================
# 6. Unrestricted File Upload Prevention
# =====================================================================


def test_documentcontrol_security_upload_svg_rejected_xss(tenant_a, quality_department):
    """SVG uploads are strictly rejected to prevent Stored XSS attacks (C3)."""
    svg_payload = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert("XSS")</script></svg>'
    svg_file = SimpleUploadedFile("malicious.svg", svg_payload, content_type="image/svg+xml")

    # ControlledDocumentForm
    base_data = _documentcontrol_base_doc_data(quality_department)
    form_doc = ControlledDocumentForm(data=base_data, files={"file": svg_file}, tenant=tenant_a)
    assert not form_doc.is_valid()
    assert "file" in form_doc.errors
    assert "not allowed" in str(form_doc.errors["file"])

    # ControlledDocumentRevisionForm
    svg_file_rev = SimpleUploadedFile("exploit.svg", svg_payload, content_type="image/svg+xml")
    rev_data = {"revision": "2.0", "change_summary": "SVG revision upload attempt"}
    form_rev = ControlledDocumentRevisionForm(data=rev_data, files={"file": svg_file_rev}, tenant=tenant_a)
    assert not form_rev.is_valid()
    assert "file" in form_rev.errors
    assert "not allowed" in str(form_rev.errors["file"])


def test_documentcontrol_security_upload_unpermitted_extensions_rejected(tenant_a, quality_department):
    """Executable and dangerous script extensions (.exe, .php, .sh, .bat, .py) are rejected."""
    dangerous_files = ["malware.exe", "backdoor.php", "attack.sh", "install.bat", "reverse.py"]
    base_data = _documentcontrol_base_doc_data(quality_department)

    for filename in dangerous_files:
        bad_file = SimpleUploadedFile(filename, b"binary payload content", content_type="application/octet-stream")
        form = ControlledDocumentForm(data=base_data, files={"file": bad_file}, tenant=tenant_a)
        assert not form.is_valid(), f"File {filename} should have been rejected."
        assert "file" in form.errors
        assert "not allowed" in str(form.errors["file"])


def test_documentcontrol_security_upload_oversized_file_rejected(tenant_a, quality_department):
    """Files exceeding MAX_UPLOAD_BYTES (20 MB limit) are strictly rejected."""
    base_data = _documentcontrol_base_doc_data(quality_department)

    oversized_file = SimpleUploadedFile("huge_manual.pdf", b"%PDF-1.4 header bytes")
    oversized_file.size = MAX_UPLOAD_BYTES + 1024

    form = ControlledDocumentForm(data=base_data, files={"file": oversized_file}, tenant=tenant_a)
    assert not form.is_valid()
    assert "file" in form.errors
    assert "20 MB limit" in str(form.errors["file"])


def test_documentcontrol_security_upload_allowed_extensions_accepted(tenant_a, quality_department):
    """Approved enterprise documentation formats (.pdf, .docx, .png) are accepted cleanly."""
    base_data = _documentcontrol_base_doc_data(quality_department)
    allowed_samples = [
        ("procedure.pdf", b"%PDF-1.4 sample content", "application/pdf"),
        ("specification.docx", b"PK\x03\x04 fake docx stream", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("diagram.png", b"\x89PNG\r\n\x1a\n fake image stream", "image/png"),
    ]

    for fname, content, ctype in allowed_samples:
        valid_file = SimpleUploadedFile(fname, content, content_type=ctype)
        form = ControlledDocumentForm(data=base_data, files={"file": valid_file}, tenant=tenant_a)
        assert form.is_valid(), f"Allowed file {fname} failed validation: {form.errors}"


# =====================================================================
# 7. Mass Assignment Defense (I13)
# =====================================================================


def test_documentcontrol_security_mass_assignment_controlled_document_create(
    client_a, admin_user, tenant_a, tenant_b, admin_b, quality_department
):
    """POST to controlled_document_create cannot override tenant, owner, number, or lifecycle_state (I13)."""
    url = reverse("quality:controlled_document_create")
    tampered_data = {
        "title": "Anti-Tamper Standard Procedure",
        "document_type": "sop",
        "department": quality_department.pk,
        "revision": "1.0",
        "classification": "internal",
        "description": "Verification of anti-mass-assignment defense.",
        "change_summary": "Initial revision.",
        "review_interval_months": 12,
        "retention_years": 5,
        # Forged fields in POST body:
        "tenant": tenant_b.pk,
        "owner": admin_b.pk,
        "number": "SOP-FORGED-001",
        "lifecycle_state": "effective",
        "is_latest_revision": False,
    }

    res = client_a.post(url, tampered_data, follow=False)
    assert res.status_code == 302

    doc = ControlledDocument.objects.get(title="Anti-Tamper Standard Procedure")
    assert doc.tenant == tenant_a
    assert doc.owner == admin_user
    assert doc.lifecycle_state == "draft"  # Forged 'effective' was ignored
    assert doc.number.startswith("QDOC-")
    assert doc.number != "SOP-FORGED-001"
    assert doc.is_latest_revision is True


def test_documentcontrol_security_mass_assignment_controlled_document_edit(
    client_a, tenant_a, tenant_b, admin_user, admin_b, quality_doc_draft
):
    """POST to controlled_document_edit cannot mutate immutable fields (tenant, owner, number, state)."""
    url = reverse("quality:controlled_document_edit", args=[quality_doc_draft.pk])
    original_number = quality_doc_draft.number

    tampered_data = {
        "title": "Legitimately Edited Title",
        "document_type": quality_doc_draft.document_type,
        "department": quality_doc_draft.department_id or "",
        "revision": "1.1",
        "classification": quality_doc_draft.classification,
        "description": "Legitimately updated description.",
        "change_summary": "Updated summary.",
        "review_interval_months": 12,
        "retention_years": 10,
        # Forged fields in POST body:
        "tenant": tenant_b.pk,
        "owner": admin_b.pk,
        "number": "SOP-OVERRIDE-999",
        "lifecycle_state": "obsolete",
    }

    res = client_a.post(url, tampered_data, follow=False)
    assert res.status_code == 302

    quality_doc_draft.refresh_from_db()
    assert quality_doc_draft.title == "Legitimately Edited Title"
    assert quality_doc_draft.tenant == tenant_a
    assert quality_doc_draft.owner == admin_user
    assert quality_doc_draft.number == original_number
    assert quality_doc_draft.lifecycle_state == "draft"


def test_documentcontrol_security_mass_assignment_dco_create(
    client_a, tenant_a, tenant_b, admin_user, admin_b, quality_doc_draft
):
    """POST to document_change_order_create cannot override tenant, requested_by, status, or number."""
    url = reverse("quality:document_change_order_create")
    tampered_data = {
        "title": "Anti-Tamper Change Request",
        "change_type": "major_revision",
        "priority": "high",
        "document": quality_doc_draft.pk,
        "target_revision": "2.0",
        "reason_for_change": "Defense verification.",
        "change_description": "Anti-mass-assignment check.",
        # Forged fields in POST body:
        "tenant": tenant_b.pk,
        "requested_by": admin_b.pk,
        "number": "DCO-FORGED-999",
        "status": "approved",
    }

    res = client_a.post(url, tampered_data, follow=False)
    assert res.status_code == 302

    dco = DocumentChangeOrder.objects.get(title="Anti-Tamper Change Request")
    assert dco.tenant == tenant_a
    assert dco.requested_by == admin_user
    assert dco.status == "draft"  # Forged 'approved' was ignored
    assert dco.number.startswith("QDCR-")
    assert dco.number != "DCO-FORGED-999"


# =====================================================================
# 8. Audit Logging Verification
# =====================================================================


def test_documentcontrol_security_audit_logging_on_state_mutations(
    client_a, admin_user, tenant_a, quality_department, quality_doc_effective, quality_employee
):
    """AuditLog rows are recorded on all state mutations across Document Control entities."""
    # 1. Document Create
    url_doc_create = reverse("quality:controlled_document_create")
    doc_payload = _documentcontrol_base_doc_data(quality_department, {"title": "Audit Traced SOP"})
    client_a.post(url_doc_create, doc_payload)
    new_doc = ControlledDocument.objects.get(title="Audit Traced SOP")
    logs_create = _documentcontrol_audit_logs(new_doc, action="create")
    assert logs_create.exists()
    assert logs_create.first().user == admin_user

    # 2. Document Edit
    url_doc_edit = reverse("quality:controlled_document_edit", args=[new_doc.pk])
    doc_payload["title"] = "Audit Traced SOP (Revised)"
    client_a.post(url_doc_edit, doc_payload)
    logs_update = _documentcontrol_audit_logs(new_doc, action="update")
    assert logs_update.exists()

    # 3. Document Submit
    client_a.post(reverse("quality:controlled_document_submit", args=[new_doc.pk]))
    assert _documentcontrol_audit_logs(new_doc, action="submit").exists()

    # 4. Document Approve
    client_a.post(reverse("quality:controlled_document_approve", args=[new_doc.pk]))
    assert _documentcontrol_audit_logs(new_doc, action="approve").exists()

    # 5. Document Make Effective
    client_a.post(reverse("quality:controlled_document_make_effective", args=[new_doc.pk]))
    assert _documentcontrol_audit_logs(new_doc, action="effective").exists()

    # 6. Document Obsolete
    client_a.post(reverse("quality:controlled_document_obsolete", args=[new_doc.pk]))
    assert _documentcontrol_audit_logs(new_doc, action="obsolete").exists()

    # 7. Document Delete (draft doc)
    del_doc = _documentcontrol_create_doc(tenant_a, admin_user, title="Disposable Doc")
    doc_pk = del_doc.pk
    client_a.post(reverse("quality:controlled_document_delete", args=[doc_pk]))
    ct_doc = ContentType.objects.get_for_model(ControlledDocument)
    assert AuditLog.objects.filter(content_type=ct_doc, object_id=doc_pk, action="delete").exists()

    # 8. DCO Create, Submit, CCB Decision, Delete
    dco = _documentcontrol_create_dco(tenant_a, admin_user, quality_doc_effective)
    # Write create audit log directly or via view
    client_a.post(reverse("quality:document_change_order_submit", args=[dco.pk]))
    assert _documentcontrol_audit_logs(dco, action="submit").exists()

    client_a.post(
        reverse("quality:document_change_order_ccb_decision", args=[dco.pk]),
        {"decision": "approved", "closure_notes": "Passed CCB review."},
    )
    assert _documentcontrol_audit_logs(dco, action="ccb_dec").exists()

    draft_dco = _documentcontrol_create_dco(tenant_a, admin_user, quality_doc_effective, title="Disposable DCO")
    dco_pk = draft_dco.pk
    client_a.post(reverse("quality:document_change_order_delete", args=[dco_pk]))
    ct_dco = ContentType.objects.get_for_model(DocumentChangeOrder)
    assert AuditLog.objects.filter(content_type=ct_dco, object_id=dco_pk, action="delete").exists()

    # 9. Acknowledgment Create and Sign
    url_ack_create = reverse("quality:document_acknowledgment_create")
    ack_payload = {
        "document": quality_doc_effective.pk,
        "document_revision": quality_doc_effective.revision,
        "user": admin_user.pk,
        "employee": quality_employee.pk,
        "due_date": timezone.now().date() + timedelta(days=7),
    }
    client_a.post(url_ack_create, ack_payload)
    new_ack = DocumentAcknowledgment.objects.get(document=quality_doc_effective, user=admin_user)
    assert _documentcontrol_audit_logs(new_ack, action="create").exists()

    # Sign Acknowledgment
    url_ack_sign = reverse("quality:document_acknowledgment_sign", args=[new_ack.pk])
    client_a.post(
        url_ack_sign,
        {"signature_meaning": "acknowledgment", "signer_title": "QA Lead", "password": "TestPass123!"},
    )
    new_ack.refresh_from_db()
    assert _documentcontrol_audit_logs(new_ack, action="ack").exists()
    assert _documentcontrol_audit_logs(new_ack.signature_record, action="sign").exists()
