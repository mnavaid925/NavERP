"""Security, multi-tenancy, authorization, and WORM compliance tests for Sub-module 13.9: Records Management & Compliance.

Covers:
1. Multi-Tenant Isolation & IDOR Protection:
   - Cross-tenant GET detail, edit, and list returns 404 (or doesn't leak records) across all 4 models:
     RetentionSchedule, RecordDeclaration, DocumentLegalHold, DestructionCertificate.
   - Cross-tenant mutating actions (POST delete, cutoff, release, ack, authorize, execute) return 404.
   - Cross-tenant Foreign Key submission rejected in forms (reject_foreign & ModelChoiceField queryset).
2. Role-Based Access Control (@tenant_admin_required):
   - Standard member user (non-admin) receives 403 Forbidden for administrative operations:
     retention_schedule_create, retention_schedule_edit, retention_schedule_delete,
     record_declaration_delete, record_declaration_trigger_cutoff, legal_hold_release,
     destruction_certificate_authorize, destruction_certificate_execute.
   - Tenant admin receives 200/302 for these endpoints.
   - Unauthenticated requests are redirected to login (302).
3. HTTP Method Enforcement (@require_POST):
   - GET requests to state-changing endpoints return 405 Method Not Allowed.
4. WORM Immutability, Legal Preservation & Spoliation Prevention:
   - Regulatory WORM records and locked records cannot be deleted or edited via views.
   - Active legal hold prevents record declaration deletion and editing.
   - Active legal hold prevents destruction certificate authorization and execution.
   - Parent document_delete prevents deletion if active legal hold or locked record declaration exists (Finding C5).
   - Destruction certificate execution requires status='authorized', prevents re-execution if already 'executed' (Finding C1).
   - Retention schedule deletion blocked when records are assigned.
   - Legal hold release requires mandatory justification audit trail.
"""
import datetime
import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.core.models import OrgUnit
from apps.documents.forms._common import reject_foreign
from apps.documents.forms.RecordsManagement.DestructionCertificates import DestructionCertificateForm
from apps.documents.forms.RecordsManagement.DocumentLegalHolds import DocumentLegalHoldForm
from apps.documents.forms.RecordsManagement.RecordDeclarations import RecordDeclarationForm
from apps.documents.forms.RecordsManagement.RetentionSchedules import RetentionScheduleForm
from apps.documents.models import (
    DestructionCertificate,
    Document,
    DocumentLegalHold,
    DocumentVersion,
    RecordDeclaration,
    RetentionSchedule,
)

User = get_user_model()


# ============================================================================
# Module-level helpers (prefix _records_management_*)
# ============================================================================

def _records_management_create_dept(tenant, name="Legal & Compliance", kind="department"):
    """Helper to create an OrgUnit department within the tenant."""
    return OrgUnit.objects.create(
        tenant=tenant,
        name=name,
        kind=kind,
    )


def _records_management_create_doc(
    tenant,
    owner,
    title="Corporate Records Spec",
    doc_type="policy",
    classification="confidential",
    status="published",
):
    """Helper to create a Document and an official DocumentVersion."""
    doc = Document.objects.create(
        tenant=tenant,
        owner=owner,
        title=title,
        document_type=doc_type,
        classification=classification,
        status=status,
        description=f"Specification doc for {title}",
    )
    DocumentVersion.objects.create(
        tenant=tenant,
        document=doc,
        version_label="1.0.0",
        major_number=1,
        minor_number=0,
        patch_number=0,
        version_type="major",
        status="approved",
        is_official=True,
        author=owner,
        file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    return doc


def _records_management_create_schedule(
    tenant,
    code="RET-SEC-001",
    name="Financial & Tax Records Schedule",
    compliance_framework="iso_15489",
    retention_mode="modifiable",
    retention_period_years=7,
    retention_period_months=0,
    is_permanent=False,
    trigger_type="creation_date",
    cutoff_rule="calendar_year_end",
    disposition_action="destroy",
    is_active=True,
    department=None,
    legal_citation="26 CFR 1.6001-1",
    notes="Standard tax compliance file plan.",
):
    """Helper to create a RetentionSchedule instance."""
    return RetentionSchedule.objects.create(
        tenant=tenant,
        code=code,
        name=name,
        compliance_framework=compliance_framework,
        retention_mode=retention_mode,
        retention_period_years=retention_period_years,
        retention_period_months=retention_period_months,
        is_permanent=is_permanent,
        trigger_type=trigger_type,
        cutoff_rule=cutoff_rule,
        disposition_action=disposition_action,
        is_active=is_active,
        department=department,
        legal_citation=legal_citation,
        notes=notes,
    )


def _records_management_create_declaration(
    tenant,
    document,
    schedule,
    user,
    version=None,
    declaration_mode="manual",
    record_status="active",
    is_vital_record=False,
    is_locked=True,
    vital_review_frequency_months=12,
    disposition_due_date=None,
    notes="Official declaration for compliance tracking.",
):
    """Helper to create a RecordDeclaration instance."""
    declaration = RecordDeclaration.objects.create(
        tenant=tenant,
        document=document,
        version=version,
        retention_schedule=schedule,
        declared_by=user,
        declaration_mode=declaration_mode,
        record_status=record_status,
        is_vital_record=is_vital_record,
        is_locked=is_locked,
        vital_review_frequency_months=vital_review_frequency_months,
        notes=notes,
    )
    if disposition_due_date:
        declaration.disposition_due_date = disposition_due_date
        declaration.save(update_fields=["disposition_due_date"])
    return declaration


def _records_management_create_hold(
    tenant,
    document,
    user,
    matter_name="SEC Compliance Audit Matter",
    matter_number="MAT-2026-901",
    hold_reason="litigation",
    custodian=None,
    is_active=True,
    description="Regulatory preservation hold.",
):
    """Helper to create a DocumentLegalHold instance."""
    return DocumentLegalHold.objects.create(
        tenant=tenant,
        document=document,
        placed_by=user,
        matter_name=matter_name,
        matter_number=matter_number,
        hold_reason=hold_reason,
        custodian=custodian,
        is_active=is_active,
        description=description,
    )


def _records_management_create_certificate(
    tenant,
    declaration,
    disposition_type="destruction",
    destruction_method="database_purge",
    status="pending_approval",
    legal_hold_verified_clear=True,
    certificate_notes="Drafted disposal certificate.",
):
    """Helper to create a DestructionCertificate instance."""
    return DestructionCertificate.objects.create(
        tenant=tenant,
        record_declaration=declaration,
        disposition_type=disposition_type,
        destruction_method=destruction_method,
        status=status,
        legal_hold_verified_clear=legal_hold_verified_clear,
        certificate_notes=certificate_notes,
    )


# ============================================================================
# 1. Multi-Tenant Isolation & IDOR Protection Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_cross_tenant_idor_get_detail_and_edit_blocked(
    client_b, tenant_a, admin_user
):
    """Test that Tenant B user cannot access Tenant A records objects via GET detail/edit (404)."""
    doc_a = _records_management_create_doc(tenant_a, admin_user, title="Tenant A Contract")
    schedule_a = _records_management_create_schedule(tenant_a, code="RET-A-001", name="Tenant A Schedule")
    declaration_a = _records_management_create_declaration(tenant_a, doc_a, schedule_a, admin_user)
    hold_a = _records_management_create_hold(tenant_a, doc_a, admin_user, matter_number="MAT-A-01")
    cert_a = _records_management_create_certificate(tenant_a, declaration_a)

    # 1. RetentionSchedule detail & edit
    assert client_b.get(reverse("documents:retention_schedule_detail", args=[schedule_a.pk])).status_code == 404
    assert client_b.get(reverse("documents:retention_schedule_edit", args=[schedule_a.pk])).status_code == 404

    # 2. RecordDeclaration detail & edit
    assert client_b.get(reverse("documents:record_declaration_detail", args=[declaration_a.pk])).status_code == 404
    assert client_b.get(reverse("documents:record_declaration_edit", args=[declaration_a.pk])).status_code == 404

    # 3. DocumentLegalHold detail
    assert client_b.get(reverse("documents:legal_hold_detail", args=[hold_a.pk])).status_code == 404

    # 4. DestructionCertificate detail
    assert client_b.get(reverse("documents:destruction_certificate_detail", args=[cert_a.pk])).status_code == 404


@pytest.mark.django_db
def test_records_management_cross_tenant_list_views_isolation(
    client_b, tenant_a, admin_user
):
    """Test that all list and board views strictly isolate data and never leak Tenant A records to Tenant B."""
    doc_a = _records_management_create_doc(tenant_a, admin_user, title="Acme Confidential Records")
    schedule_a = _records_management_create_schedule(tenant_a, code="RET-LEAK-A", name="Acme Secret Plan")
    declaration_a = _records_management_create_declaration(
        tenant_a,
        doc_a,
        schedule_a,
        admin_user,
        is_vital_record=True,
        disposition_due_date=timezone.now().date() - datetime.timedelta(days=1),
    )
    hold_a = _records_management_create_hold(
        tenant_a, doc_a, admin_user, matter_name="Top Secret Antitrust Probe", matter_number="SEC-LEAK-01"
    )
    cert_a = _records_management_create_certificate(tenant_a, declaration_a, certificate_notes="Acme Shred Order")

    # 1. retention_schedule_list
    res_sched = client_b.get(reverse("documents:retention_schedule_list"))
    assert res_sched.status_code == 200
    assert schedule_a not in res_sched.context["schedules"]
    assert "Acme Secret Plan" not in res_sched.content.decode("utf-8")

    # 2. record_declaration_list
    res_decl = client_b.get(reverse("documents:record_declaration_list"))
    assert res_decl.status_code == 200
    assert declaration_a not in res_decl.context["declarations"]
    assert declaration_a.number not in res_decl.content.decode("utf-8")

    # 3. legal_hold_list
    res_hold = client_b.get(reverse("documents:legal_hold_list"))
    assert res_hold.status_code == 200
    assert hold_a not in res_hold.context["holds"]
    assert "Top Secret Antitrust Probe" not in res_hold.content.decode("utf-8")

    # 4. destruction_certificate_list
    res_cert = client_b.get(reverse("documents:destruction_certificate_list"))
    assert res_cert.status_code == 200
    assert cert_a not in res_cert.context["certificates"]
    assert cert_a.number not in res_cert.content.decode("utf-8")

    # 5. disposition_review_board
    res_board = client_b.get(reverse("documents:disposition_review_board"))
    assert res_board.status_code == 200
    assert declaration_a not in res_board.context["due_records"]
    assert declaration_a not in res_board.context["held_records"]
    assert cert_a not in res_board.context["pending_certificates"]

    # 6. vital_records_list
    res_vital = client_b.get(reverse("documents:vital_records_list"))
    assert res_vital.status_code == 200
    assert declaration_a not in res_vital.context["vital_records"]


@pytest.mark.django_db
def test_records_management_cross_tenant_mutating_actions_return_404(
    client_b, tenant_a, admin_user
):
    """Test that Tenant B user cannot execute mutating POST actions against Tenant A records objects (404)."""
    doc_a = _records_management_create_doc(tenant_a, admin_user)
    schedule_a = _records_management_create_schedule(tenant_a, code="RET-MUT-A")
    declaration_a = _records_management_create_declaration(tenant_a, doc_a, schedule_a, admin_user)
    hold_a = _records_management_create_hold(tenant_a, doc_a, admin_user)
    cert_a = _records_management_create_certificate(tenant_a, declaration_a)

    # 1. retention_schedule_edit & delete
    assert client_b.post(
        reverse("documents:retention_schedule_edit", args=[schedule_a.pk]),
        {"name": "Hacked Schedule", "code": "RET-HACK"},
    ).status_code == 404
    assert client_b.post(reverse("documents:retention_schedule_delete", args=[schedule_a.pk])).status_code == 404

    # 2. record_declaration_edit, delete, trigger_cutoff
    assert client_b.post(
        reverse("documents:record_declaration_edit", args=[declaration_a.pk]),
        {"notes": "Hacked Notes"},
    ).status_code == 404
    assert client_b.post(reverse("documents:record_declaration_delete", args=[declaration_a.pk])).status_code == 404
    assert client_b.post(reverse("documents:record_declaration_trigger_cutoff", args=[declaration_a.pk])).status_code == 404

    # 3. legal_hold_release & acknowledge
    assert client_b.post(
        reverse("documents:legal_hold_release", args=[hold_a.pk]),
        {"release_justification": "Malicious release attempt"},
    ).status_code == 404
    assert client_b.post(reverse("documents:legal_hold_acknowledge", args=[hold_a.pk])).status_code == 404

    # 4. destruction_certificate_authorize & execute
    assert client_b.post(reverse("documents:destruction_certificate_authorize", args=[cert_a.pk])).status_code == 404
    assert client_b.post(reverse("documents:destruction_certificate_execute", args=[cert_a.pk])).status_code == 404

    # Verify no objects in Tenant A were altered or deleted
    assert RetentionSchedule.objects.filter(pk=schedule_a.pk).exists() is True
    assert RecordDeclaration.objects.filter(pk=declaration_a.pk).exists() is True
    hold_a.refresh_from_db()
    assert hold_a.is_active is True
    cert_a.refresh_from_db()
    assert cert_a.status == "pending_approval"


@pytest.mark.django_db
def test_records_management_cross_tenant_fk_submission_rejected_in_forms(
    tenant_a, tenant_b, admin_user, admin_b
):
    """Test that forms reject cross-tenant Foreign Key injection using reject_foreign and scoped querysets."""
    doc_a = _records_management_create_doc(tenant_a, admin_user, title="Tenant A Doc")
    doc_b = _records_management_create_doc(tenant_b, admin_b, title="Tenant B Doc")
    dept_b = _records_management_create_dept(tenant_b, name="Tenant B Dept")
    schedule_a = _records_management_create_schedule(tenant_a, code="RET-FRM-A")
    schedule_b = _records_management_create_schedule(tenant_b, code="RET-FRM-B")
    decl_a = _records_management_create_declaration(tenant_a, doc_a, schedule_a, admin_user)
    decl_b = _records_management_create_declaration(tenant_b, doc_b, schedule_b, admin_b)

    # 1. RetentionScheduleForm: foreign department
    form_sched = RetentionScheduleForm(
        data={
            "name": "Audit Schedule",
            "code": "RET-INJ-001",
            "retention_period_years": 5,
            "trigger_type": "creation_date",
            "cutoff_rule": "calendar_year_end",
            "disposition_action": "destroy",
            "compliance_framework": "iso_15489",
            "retention_mode": "modifiable",
            "department": dept_b.pk,
        },
        tenant=tenant_a,
    )
    assert form_sched.is_valid() is False
    assert "department" in form_sched.errors
    # Direct reject_foreign check
    form_sched_cleaned = {"department": dept_b}
    reject_foreign(form_sched, form_sched_cleaned, ["department"])
    assert "department" in form_sched.errors

    # 2. RecordDeclarationForm: foreign document, version, retention_schedule
    form_decl = RecordDeclarationForm(
        data={
            "document": doc_b.pk,
            "retention_schedule": schedule_b.pk,
            "declaration_mode": "manual",
        },
        tenant=tenant_a,
    )
    assert form_decl.is_valid() is False
    assert "document" in form_decl.errors or "retention_schedule" in form_decl.errors
    # Direct reject_foreign check
    form_decl_cleaned = {"document": doc_b, "retention_schedule": schedule_b}
    reject_foreign(form_decl, form_decl_cleaned, ["document", "retention_schedule"])
    assert "document" in form_decl.errors

    # 3. DocumentLegalHoldForm: foreign document, foreign custodian
    form_hold = DocumentLegalHoldForm(
        data={
            "matter_name": "Antitrust Litigation",
            "matter_number": "MAT-2026-X",
            "hold_reason": "litigation",
            "document": doc_b.pk,
            "custodian": admin_b.pk,
        },
        tenant=tenant_a,
    )
    assert form_hold.is_valid() is False
    assert "document" in form_hold.errors or "custodian" in form_hold.errors
    # Direct reject_foreign check
    form_hold_cleaned = {"document": doc_b, "custodian": admin_b}
    reject_foreign(form_hold, form_hold_cleaned, ["document", "custodian"])
    assert "document" in form_hold.errors

    # 4. DestructionCertificateForm: foreign record_declaration
    form_cert = DestructionCertificateForm(
        data={
            "record_declaration": decl_b.pk,
            "disposition_type": "destruction",
            "destruction_method": "database_purge",
        },
        tenant=tenant_a,
    )
    assert form_cert.is_valid() is False
    assert "record_declaration" in form_cert.errors
    # Direct reject_foreign check
    form_cert_cleaned = {"record_declaration": decl_b}
    reject_foreign(form_cert, form_cert_cleaned, ["record_declaration"])
    assert "record_declaration" in form_cert.errors


@pytest.mark.django_db
def test_records_management_cross_tenant_post_create_view_fk_injection_blocked(
    client_a, tenant_a, tenant_b, admin_b
):
    """Test that POST submissions with foreign PKs to create views are blocked."""
    doc_b = _records_management_create_doc(tenant_b, admin_b, title="Foreign Document")
    schedule_b = _records_management_create_schedule(tenant_b, code="RET-B-FOREIGN")
    decl_b = _records_management_create_declaration(tenant_b, doc_b, schedule_b, admin_b)

    # 1. record_declaration_create with foreign document and schedule
    res_decl = client_a.post(
        reverse("documents:record_declaration_create"),
        {
            "document": doc_b.pk,
            "retention_schedule": schedule_b.pk,
            "declaration_mode": "manual",
        },
    )
    assert res_decl.status_code == 200  # Re-renders form with errors
    assert RecordDeclaration.objects.filter(tenant=tenant_a, document_id=doc_b.pk).exists() is False

    # 2. legal_hold_create with foreign document
    res_hold = client_a.post(
        reverse("documents:legal_hold_create"),
        {
            "matter_name": "Foreign Litigation Hold",
            "matter_number": "MAT-FOR-01",
            "hold_reason": "litigation",
            "document": doc_b.pk,
        },
    )
    assert res_hold.status_code == 200
    assert DocumentLegalHold.objects.filter(tenant=tenant_a, document_id=doc_b.pk).exists() is False

    # 3. destruction_certificate_create with foreign record_declaration
    res_cert = client_a.post(
        reverse("documents:destruction_certificate_create"),
        {
            "record_declaration": decl_b.pk,
            "disposition_type": "destruction",
            "destruction_method": "database_purge",
        },
    )
    assert res_cert.status_code == 200
    assert DestructionCertificate.objects.filter(tenant=tenant_a, record_declaration_id=decl_b.pk).exists() is False


# ============================================================================
# 2. Role-Based Access Control (@tenant_admin_required) Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_rbac_standard_member_forbidden_for_admin_endpoints(
    member_client, tenant_a, admin_user
):
    """Test that standard member user (non-admin) receives 403 Forbidden for admin-only views."""
    doc_a = _records_management_create_doc(tenant_a, admin_user)
    schedule_a = _records_management_create_schedule(tenant_a, code="RET-ADM-01")
    declaration_a = _records_management_create_declaration(
        tenant_a, doc_a, schedule_a, admin_user, is_locked=False
    )
    hold_a = _records_management_create_hold(tenant_a, doc_a, admin_user)
    cert_a = _records_management_create_certificate(tenant_a, declaration_a, status="pending_approval")

    # 1. retention_schedule_create (GET and POST -> 403)
    assert member_client.get(reverse("documents:retention_schedule_create")).status_code == 403
    assert member_client.post(
        reverse("documents:retention_schedule_create"),
        {"name": "Blocked Schedule", "code": "RET-BLK-01"},
    ).status_code == 403

    # 2. retention_schedule_edit (GET and POST -> 403)
    assert member_client.get(reverse("documents:retention_schedule_edit", args=[schedule_a.pk])).status_code == 403
    assert member_client.post(
        reverse("documents:retention_schedule_edit", args=[schedule_a.pk]),
        {"name": "Altered Schedule"},
    ).status_code == 403

    # 3. retention_schedule_delete (POST -> 403)
    assert member_client.post(reverse("documents:retention_schedule_delete", args=[schedule_a.pk])).status_code == 403

    # 4. record_declaration_delete (POST -> 403)
    assert member_client.post(reverse("documents:record_declaration_delete", args=[declaration_a.pk])).status_code == 403

    # 5. record_declaration_trigger_cutoff (POST -> 403)
    assert member_client.post(reverse("documents:record_declaration_trigger_cutoff", args=[declaration_a.pk])).status_code == 403

    # 6. legal_hold_release (POST -> 403)
    assert member_client.post(
        reverse("documents:legal_hold_release", args=[hold_a.pk]),
        {"release_justification": "Non-admin release attempt"},
    ).status_code == 403

    # 7. destruction_certificate_authorize (POST -> 403)
    assert member_client.post(reverse("documents:destruction_certificate_authorize", args=[cert_a.pk])).status_code == 403

    # 8. destruction_certificate_execute (POST -> 403)
    assert member_client.post(reverse("documents:destruction_certificate_execute", args=[cert_a.pk])).status_code == 403


@pytest.mark.django_db
def test_records_management_rbac_tenant_admin_authorized_for_admin_endpoints(
    client_a, tenant_a, admin_user
):
    """Test that tenant admin is permitted (200 for GET, 302 for valid POST) across all admin endpoints."""
    doc_a = _records_management_create_doc(tenant_a, admin_user)
    schedule_a = _records_management_create_schedule(tenant_a, code="RET-AUTH-01")
    empty_sched = _records_management_create_schedule(tenant_a, code="RET-EMPTY-01")
    declaration_a = _records_management_create_declaration(
        tenant_a, doc_a, schedule_a, admin_user, is_locked=False, record_status="active"
    )
    hold_a = _records_management_create_hold(tenant_a, doc_a, admin_user, is_active=True)

    # 1. retention_schedule_create GET -> 200
    assert client_a.get(reverse("documents:retention_schedule_create")).status_code == 200

    # 2. retention_schedule_edit GET -> 200
    assert client_a.get(reverse("documents:retention_schedule_edit", args=[schedule_a.pk])).status_code == 200

    # 3. retention_schedule_delete POST on unassigned schedule -> 302
    assert client_a.post(reverse("documents:retention_schedule_delete", args=[empty_sched.pk])).status_code == 302
    assert RetentionSchedule.objects.filter(pk=empty_sched.pk).exists() is False

    # 4. legal_hold_release POST with justification -> 302
    res_rel = client_a.post(
        reverse("documents:legal_hold_release", args=[hold_a.pk]),
        {"release_justification": "Authorized legal department closure order."},
    )
    assert res_rel.status_code == 302
    hold_a.refresh_from_db()
    assert hold_a.is_active is False
    assert hold_a.released_by == admin_user

    # 5. record_declaration_trigger_cutoff POST on active record -> 302
    res_cutoff = client_a.post(reverse("documents:record_declaration_trigger_cutoff", args=[declaration_a.pk]))
    assert res_cutoff.status_code == 302
    declaration_a.refresh_from_db()
    assert declaration_a.record_status == "cutoff"
    assert declaration_a.cutoff_date is not None

    # 6. destruction_certificate_authorize & execute POST
    cert_a = _records_management_create_certificate(tenant_a, declaration_a, status="pending_approval")
    res_auth = client_a.post(reverse("documents:destruction_certificate_authorize", args=[cert_a.pk]))
    assert res_auth.status_code == 302
    cert_a.refresh_from_db()
    assert cert_a.status == "authorized"
    assert cert_a.authorized_by == admin_user

    res_exec = client_a.post(reverse("documents:destruction_certificate_execute", args=[cert_a.pk]))
    assert res_exec.status_code == 302
    cert_a.refresh_from_db()
    assert cert_a.status == "executed"
    assert cert_a.executed_by == admin_user
    declaration_a.refresh_from_db()
    assert declaration_a.record_status == "disposed"

    # 7. record_declaration_delete POST on unlocked non-WORM record without holds
    doc_unlocked = _records_management_create_doc(tenant_a, admin_user, title="Disposable Doc")
    sched_unlocked = _records_management_create_schedule(tenant_a, code="RET-UNLOCKED", retention_mode="modifiable")
    decl_unlocked = _records_management_create_declaration(
        tenant_a, doc_unlocked, sched_unlocked, admin_user, is_locked=False
    )
    res_del_decl = client_a.post(reverse("documents:record_declaration_delete", args=[decl_unlocked.pk]))
    assert res_del_decl.status_code == 302
    assert RecordDeclaration.objects.filter(pk=decl_unlocked.pk).exists() is False


@pytest.mark.django_db
def test_records_management_unauthenticated_requests_redirected_to_login(
    client, tenant_a, admin_user
):
    """Test that all 23 Sub-module 13.9 endpoints redirect unauthenticated requests to login (302)."""
    doc_a = _records_management_create_doc(tenant_a, admin_user)
    schedule_a = _records_management_create_schedule(tenant_a, code="RET-UNAUTH-01")
    declaration_a = _records_management_create_declaration(tenant_a, doc_a, schedule_a, admin_user)
    hold_a = _records_management_create_hold(tenant_a, doc_a, admin_user)
    cert_a = _records_management_create_certificate(tenant_a, declaration_a)

    endpoints = [
        reverse("documents:retention_schedule_list"),
        reverse("documents:retention_schedule_create"),
        reverse("documents:retention_schedule_detail", args=[schedule_a.pk]),
        reverse("documents:retention_schedule_edit", args=[schedule_a.pk]),
        reverse("documents:retention_schedule_delete", args=[schedule_a.pk]),
        reverse("documents:record_declaration_list"),
        reverse("documents:record_declaration_create"),
        reverse("documents:record_declaration_detail", args=[declaration_a.pk]),
        reverse("documents:record_declaration_edit", args=[declaration_a.pk]),
        reverse("documents:record_declaration_delete", args=[declaration_a.pk]),
        reverse("documents:record_declaration_trigger_cutoff", args=[declaration_a.pk]),
        reverse("documents:legal_hold_list"),
        reverse("documents:legal_hold_create"),
        reverse("documents:legal_hold_detail", args=[hold_a.pk]),
        reverse("documents:legal_hold_release", args=[hold_a.pk]),
        reverse("documents:legal_hold_acknowledge", args=[hold_a.pk]),
        reverse("documents:destruction_certificate_list"),
        reverse("documents:destruction_certificate_create"),
        reverse("documents:destruction_certificate_detail", args=[cert_a.pk]),
        reverse("documents:destruction_certificate_authorize", args=[cert_a.pk]),
        reverse("documents:destruction_certificate_execute", args=[cert_a.pk]),
        reverse("documents:disposition_review_board"),
        reverse("documents:vital_records_list"),
    ]

    for url in endpoints:
        res = client.get(url)
        assert res.status_code == 302, f"Expected 302 login redirect for {url}, got {res.status_code}"
        assert "/login/" in res.headers["Location"]


# ============================================================================
# 3. HTTP Method Enforcement (@require_POST) Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_require_post_enforced_for_mutating_endpoints(
    client_a, tenant_a, admin_user
):
    """Test that all mutating endpoints reject GET requests with 405 Method Not Allowed."""
    doc_a = _records_management_create_doc(tenant_a, admin_user)
    schedule_a = _records_management_create_schedule(tenant_a, code="RET-REQPOST-01")
    declaration_a = _records_management_create_declaration(tenant_a, doc_a, schedule_a, admin_user)
    hold_a = _records_management_create_hold(tenant_a, doc_a, admin_user)
    cert_a = _records_management_create_certificate(tenant_a, declaration_a)

    mutating_get_endpoints = [
        reverse("documents:retention_schedule_delete", args=[schedule_a.pk]),
        reverse("documents:record_declaration_delete", args=[declaration_a.pk]),
        reverse("documents:record_declaration_trigger_cutoff", args=[declaration_a.pk]),
        reverse("documents:legal_hold_release", args=[hold_a.pk]),
        reverse("documents:legal_hold_acknowledge", args=[hold_a.pk]),
        reverse("documents:destruction_certificate_authorize", args=[cert_a.pk]),
        reverse("documents:destruction_certificate_execute", args=[cert_a.pk]),
    ]

    for url in mutating_get_endpoints:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {res.status_code}"


# ============================================================================
# 4. WORM Immutability, Legal Preservation & Spoliation Prevention Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_regulatory_worm_record_cannot_be_edited(
    client_a, tenant_a, admin_user
):
    """Test that a record under regulatory WORM cannot be edited via GET or POST."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(
        tenant_a,
        code="RET-WORM-01",
        retention_mode="regulatory_worm",
        retention_period_years=7,
    )
    declaration = _records_management_create_declaration(
        tenant_a,
        doc,
        schedule,
        admin_user,
        is_locked=True,
        notes="Original regulatory notes.",
    )

    url = reverse("documents:record_declaration_edit", args=[declaration.pk])

    # 1. GET attempt redirects to detail with error
    res_get = client_a.get(url)
    assert res_get.status_code == 302
    assert res_get.url == reverse("documents:record_declaration_detail", args=[declaration.pk])
    messages = list(get_messages(res_get.wsgi_request))
    assert any("immutable record under WORM compliance lock" in str(m) for m in messages)

    # 2. POST attempt redirects to detail with error and does not mutate notes
    res_post = client_a.post(url, {"notes": "Tampered regulatory notes."})
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:record_declaration_detail", args=[declaration.pk])
    declaration.refresh_from_db()
    assert declaration.notes == "Original regulatory notes."


@pytest.mark.django_db
def test_records_management_regulatory_worm_record_cannot_be_deleted(
    client_a, tenant_a, admin_user
):
    """Test that a declared Regulatory WORM locked record cannot be deleted via view."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(
        tenant_a,
        code="RET-WORM-DEL",
        retention_mode="regulatory_worm",
        retention_period_years=10,
    )
    declaration = _records_management_create_declaration(
        tenant_a,
        doc,
        schedule,
        admin_user,
        is_locked=True,
    )

    url = reverse("documents:record_declaration_delete", args=[declaration.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:record_declaration_detail", args=[declaration.pk])
    messages = list(get_messages(res.wsgi_request))
    assert any("Cannot delete a declared Regulatory WORM record" in str(m) for m in messages)

    # Record must still exist in DB
    assert RecordDeclaration.objects.filter(pk=declaration.pk).exists() is True


@pytest.mark.django_db
def test_records_management_locked_record_cannot_be_edited(
    client_a, tenant_a, admin_user
):
    """Test that a locked record under modifiable schedule still blocks editing."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(
        tenant_a,
        code="RET-MOD-LOCK",
        retention_mode="modifiable",
    )
    declaration = _records_management_create_declaration(
        tenant_a,
        doc,
        schedule,
        admin_user,
        is_locked=True,
        notes="Unmodified locked notes.",
    )

    url = reverse("documents:record_declaration_edit", args=[declaration.pk])
    res = client_a.get(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:record_declaration_detail", args=[declaration.pk])

    res_post = client_a.post(url, {"notes": "Tampered locked notes."})
    assert res_post.status_code == 302
    declaration.refresh_from_db()
    assert declaration.notes == "Unmodified locked notes."


@pytest.mark.django_db
def test_records_management_active_legal_hold_blocks_record_declaration_edit(
    client_a, tenant_a, admin_user
):
    """Test that an active legal hold freezes the record declaration and prevents editing."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-HOLD-EDIT", retention_mode="modifiable")
    declaration = _records_management_create_declaration(
        tenant_a, doc, schedule, admin_user, is_locked=False, notes="Original notes under hold."
    )
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:record_declaration_edit", args=[declaration.pk])

    # 1. GET blocked
    res_get = client_a.get(url)
    assert res_get.status_code == 302
    assert res_get.url == reverse("documents:record_declaration_detail", args=[declaration.pk])
    messages = list(get_messages(res_get.wsgi_request))
    assert any("frozen under an active legal hold" in str(m) for m in messages)

    # 2. POST blocked
    res_post = client_a.post(url, {"notes": "Attempted edit under hold."})
    assert res_post.status_code == 302
    declaration.refresh_from_db()
    assert declaration.notes == "Original notes under hold."


@pytest.mark.django_db
def test_records_management_active_legal_hold_blocks_record_declaration_delete(
    client_a, tenant_a, admin_user
):
    """Test that an active legal hold prevents deletion of an unlocked record declaration."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-HOLD-DEL", retention_mode="modifiable")
    declaration = _records_management_create_declaration(
        tenant_a, doc, schedule, admin_user, is_locked=False
    )
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:record_declaration_delete", args=[declaration.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:record_declaration_detail", args=[declaration.pk])
    messages = list(get_messages(res.wsgi_request))
    assert any("active legal hold is placed on the document" in str(m) for m in messages)

    assert RecordDeclaration.objects.filter(pk=declaration.pk).exists() is True


@pytest.mark.django_db
def test_records_management_active_legal_hold_blocks_destruction_certificate_create_in_form(
    tenant_a, admin_user
):
    """Test that DestructionCertificateForm rejects drafting certificate when document is under active legal hold."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-CERT-HOLD")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    form = DestructionCertificateForm(
        data={
            "record_declaration": declaration.pk,
            "disposition_type": "destruction",
            "destruction_method": "database_purge",
        },
        tenant=tenant_a,
    )
    assert form.is_valid() is False
    assert "record_declaration" in form.errors
    assert "active legal hold is currently placed" in form.errors["record_declaration"][0]


@pytest.mark.django_db
def test_records_management_active_legal_hold_blocks_destruction_certificate_authorization(
    client_a, tenant_a, admin_user
):
    """Test that active legal hold stops destruction certificate authorization (spoliation prevention)."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-SPOL-01")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, declaration, status="pending_approval")

    # Place an active legal hold on the document
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:destruction_certificate_authorize", args=[cert.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:destruction_certificate_detail", args=[cert.pk])

    messages = list(get_messages(res.wsgi_request))
    assert any("active legal hold" in str(m) for m in messages)

    cert.refresh_from_db()
    assert cert.status == "pending_approval"
    assert cert.authorized_by is None


@pytest.mark.django_db
def test_records_management_active_legal_hold_blocks_destruction_certificate_execution(
    client_a, tenant_a, admin_user
):
    """Test that an active legal hold stops execution even if previously authorized."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-EXEC-HOLD")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, declaration, status="authorized")
    cert.authorized_by = admin_user
    cert.authorized_at = timezone.now()
    cert.save()

    # Place hold after authorization
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:destruction_certificate_execute", args=[cert.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:destruction_certificate_detail", args=[cert.pk])

    messages = list(get_messages(res.wsgi_request))
    assert any("active legal hold" in str(m) for m in messages)

    cert.refresh_from_db()
    assert cert.status == "authorized"
    assert cert.executed_by is None
    declaration.refresh_from_db()
    assert declaration.record_status != "disposed"


@pytest.mark.django_db
def test_records_management_parent_document_delete_blocked_by_active_legal_hold(
    client_a, tenant_a, admin_user
):
    """Test Finding C5: Parent document_delete view prevents deletion when active legal hold exists."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Preserved Litigation File")
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:document_delete", args=[doc.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:document_detail", args=[doc.pk])

    messages = list(get_messages(res.wsgi_request))
    assert any("active legal hold is in place" in str(m) for m in messages)

    # Document must remain in DB
    assert Document.objects.filter(pk=doc.pk).exists() is True


@pytest.mark.django_db
def test_records_management_parent_document_delete_blocked_by_locked_record_declaration(
    client_a, tenant_a, admin_user
):
    """Test Finding C5: Parent document_delete view prevents deletion when locked record declaration exists."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Official Corporate Record")
    schedule = _records_management_create_schedule(tenant_a, code="RET-DOC-LOCK")
    _records_management_create_declaration(tenant_a, doc, schedule, admin_user, is_locked=True)

    url = reverse("documents:document_delete", args=[doc.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:document_detail", args=[doc.pk])

    messages = list(get_messages(res.wsgi_request))
    assert any("immutable official record" in str(m) for m in messages)

    # Document must remain in DB
    assert Document.objects.filter(pk=doc.pk).exists() is True


@pytest.mark.django_db
def test_records_management_parent_document_delete_allowed_when_no_active_hold_or_locked_record(
    client_a, tenant_a, admin_user
):
    """Test that document_delete succeeds when no active holds or locked records exist."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Draft Memo")

    url = reverse("documents:document_delete", args=[doc.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:document_list")

    # Document deleted
    assert Document.objects.filter(pk=doc.pk).exists() is False


@pytest.mark.django_db
def test_records_management_destruction_certificate_requires_authorized_status(
    client_a, tenant_a, admin_user
):
    """Test Finding C1: Destruction certificate execution requires status='authorized'."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-UNAUTH-EXEC")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, declaration, status="pending_approval")

    url = reverse("documents:destruction_certificate_execute", args=[cert.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:destruction_certificate_detail", args=[cert.pk])

    messages = list(get_messages(res.wsgi_request))
    assert any("Certificate must be authorized first" in str(m) for m in messages)

    cert.refresh_from_db()
    assert cert.status == "pending_approval"
    assert cert.executed_by is None
    assert cert.executed_at is None
    declaration.refresh_from_db()
    assert declaration.record_status != "disposed"


@pytest.mark.django_db
def test_records_management_destruction_certificate_prevents_reexecution(
    client_a, tenant_a, admin_user
):
    """Test Finding C1: Destruction certificate cannot be re-executed once in 'executed' status."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-REEXEC-01")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, declaration, status="pending_approval")

    # Step 1: Authorize
    client_a.post(reverse("documents:destruction_certificate_authorize", args=[cert.pk]))

    # Step 2: First Execution -> Success
    res_exec1 = client_a.post(reverse("documents:destruction_certificate_execute", args=[cert.pk]))
    assert res_exec1.status_code == 302
    cert.refresh_from_db()
    assert cert.status == "executed"
    original_executed_at = cert.executed_at
    assert original_executed_at is not None

    # Step 3: Second Execution attempt -> Rejection with guard message
    res_exec2 = client_a.post(reverse("documents:destruction_certificate_execute", args=[cert.pk]))
    assert res_exec2.status_code == 302
    messages = list(get_messages(res_exec2.wsgi_request))
    assert any("Destruction certificate has already been executed" in str(m) for m in messages)

    cert.refresh_from_db()
    assert cert.status == "executed"
    assert cert.executed_at == original_executed_at


@pytest.mark.django_db
def test_records_management_retention_schedule_delete_blocked_when_records_assigned(
    client_a, tenant_a, admin_user
):
    """Test that retention_schedule_delete is blocked when records are currently assigned to it."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-ATTACH-01")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:retention_schedule_delete", args=[schedule.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:retention_schedule_detail", args=[schedule.pk])

    messages = list(get_messages(res.wsgi_request))
    assert any("records are currently assigned to it" in str(m) for m in messages)
    assert RetentionSchedule.objects.filter(pk=schedule.pk).exists() is True

    # Detach by deleting declaration, then delete schedule
    declaration.delete()
    res_clean = client_a.post(url)
    assert res_clean.status_code == 302
    assert res_clean.url == reverse("documents:retention_schedule_list")
    assert RetentionSchedule.objects.filter(pk=schedule.pk).exists() is False


@pytest.mark.django_db
def test_records_management_legal_hold_release_requires_justification(
    client_a, tenant_a, admin_user
):
    """Test that releasing a legal hold requires mandatory justification audit trail."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    hold = _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:legal_hold_release", args=[hold.pk])

    # 1. Empty justification rejected
    res_empty = client_a.post(url, {"release_justification": "   "})
    assert res_empty.status_code == 302
    messages = list(get_messages(res_empty.wsgi_request))
    assert any("Release justification is mandatory" in str(m) for m in messages)
    hold.refresh_from_db()
    assert hold.is_active is True

    # 2. Valid justification succeeds
    res_valid = client_a.post(
        url,
        {"release_justification": "Litigation concluded with prejudice; outside counsel confirmed."},
    )
    assert res_valid.status_code == 302
    hold.refresh_from_db()
    assert hold.is_active is False
    assert hold.released_by == admin_user
    assert "concluded with prejudice" in hold.release_justification

    # 3. Subsequent release attempt on released hold returns informational message
    res_again = client_a.post(url, {"release_justification": "Second attempt"})
    assert res_again.status_code == 302
    messages_again = list(get_messages(res_again.wsgi_request))
    assert any("already been released" in str(m) for m in messages_again)


@pytest.mark.django_db
def test_records_management_record_declaration_cutoff_requires_active_status(
    client_a, tenant_a, admin_user
):
    """Test that cutoff milestone can only be triggered for active record declarations."""
    doc = _records_management_create_doc(tenant_a, admin_user)
    schedule = _records_management_create_schedule(tenant_a, code="RET-CUT-STATUS")
    declaration = _records_management_create_declaration(
        tenant_a, doc, schedule, admin_user, record_status="disposed"
    )

    url = reverse("documents:record_declaration_trigger_cutoff", args=[declaration.pk])
    res = client_a.post(url)
    assert res.status_code == 302
    assert res.url == reverse("documents:record_declaration_detail", args=[declaration.pk])

    messages = list(get_messages(res.wsgi_request))
    assert any("Cannot trigger cutoff" in str(m) for m in messages)
    declaration.refresh_from_db()
    assert declaration.record_status == "disposed"
