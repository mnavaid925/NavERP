"""View integration tests for Sub-module 13.9: Records Management & Compliance.

Tests the full lifecycle and views across the records management domain:
1. Retention Schedule views:
   - retention_schedule_list (filtering by framework, retention mode, status, department, search, pagination)
   - retention_schedule_create (GET, POST success, invalid form, tenant admin required)
   - retention_schedule_detail (context keys: schedule, declared_records, declared_records_count)
   - retention_schedule_edit (GET, POST success, tenant admin required)
   - retention_schedule_delete (blocked with attached records, success without records, POST required, admin required)
2. Record Declaration views:
   - record_declaration_list (filtering by status, schedule, vital_only, pagination, search, annotated has_active_hold)
   - record_declaration_create (GET, prefill params, POST success, duplicate active declaration rejection)
   - record_declaration_detail (context keys: declaration, active_holds, certificates)
   - record_declaration_edit (GET/POST success for unlocked modifiable, rejection on locked/WORM/active hold)
   - record_declaration_delete (rejection on locked WORM, rejection on active hold, success, admin required)
   - record_declaration_trigger_cutoff (status transition to cutoff, rejection when not active, admin required)
3. Document Legal Hold views:
   - legal_hold_list (filters by reason, status, search, pagination)
   - legal_hold_create (GET, prefill param, POST success, validation)
   - legal_hold_detail (context keys: hold, release_form)
   - legal_hold_release (POST with justification sets is_active=False, rejection on empty justification, admin required)
   - legal_hold_acknowledge (POST records custodian acknowledgment)
4. Destruction Certificate views:
   - destruction_certificate_list (filters by status, disposition_type, destruction_method, pagination, search)
   - destruction_certificate_create (GET, prefill param, POST success, rejection under legal hold)
   - destruction_certificate_detail (context key: certificate)
   - destruction_certificate_authorize (POST sets status=authorized, rejection when active hold present, admin required)
   - destruction_certificate_execute (rejection when not authorized, execution updates record and doc status, admin required)
5. Specialized views:
   - disposition_review_board (context keys: due_records, held_records, pending_certificates, counts, partitioning)
   - vital_records_list (filter by department, search query, pagination, context keys, vital records only)
6. Tenant isolation:
   - Strict 404 enforcement across tenants for schedules, declarations, holds, and certificates.
"""
import datetime
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import OrgUnit
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
    code="RET-VIEW-001",
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
# 1. Retention Schedule Views Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_retention_schedule_list_rendering(client_a, tenant_a):
    """Test retention_schedule_list renders 200 OK with expected context keys."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-LST-001", name="Accounting Ledgers")
    url = reverse("documents:retention_schedule_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "schedules" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "framework_choices" in resp.context
    assert "retention_mode_choices" in resp.context
    assert "departments" in resp.context
    assert schedule in resp.context["schedules"]


@pytest.mark.django_db
def test_records_management_retention_schedule_list_filters(client_a, tenant_a):
    """Test retention_schedule_list filtering by framework, retention mode, status, department, and query."""
    dept = _records_management_create_dept(tenant_a, name="Tax Department")
    sch1 = _records_management_create_schedule(
        tenant_a,
        code="RET-IRS-001",
        name="IRS Audit Files",
        compliance_framework="irs_tax",
        retention_mode="regulatory_worm",
        is_active=True,
        department=dept,
        legal_citation="IRS Sec 6001",
    )
    sch2 = _records_management_create_schedule(
        tenant_a,
        code="RET-GDPR-002",
        name="Customer Consent Logs",
        compliance_framework="gdpr",
        retention_mode="modifiable",
        is_active=False,
        department=None,
        legal_citation="GDPR Art 17",
    )

    url = reverse("documents:retention_schedule_list")

    # Filter compliance_framework
    res_fw = client_a.get(url, {"compliance_framework": "irs_tax"})
    assert res_fw.status_code == 200
    assert sch1 in res_fw.context["schedules"]
    assert sch2 not in res_fw.context["schedules"]

    # Filter retention_mode
    res_mode = client_a.get(url, {"retention_mode": "regulatory_worm"})
    assert res_mode.status_code == 200
    assert sch1 in res_mode.context["schedules"]
    assert sch2 not in res_mode.context["schedules"]

    # Filter status: active vs inactive
    res_act = client_a.get(url, {"status": "active"})
    assert sch1 in res_act.context["schedules"]
    assert sch2 not in res_act.context["schedules"]

    res_inact = client_a.get(url, {"status": "inactive"})
    assert sch2 in res_inact.context["schedules"]
    assert sch1 not in res_inact.context["schedules"]

    # Filter department
    res_dept = client_a.get(url, {"department": str(dept.pk)})
    assert sch1 in res_dept.context["schedules"]
    assert sch2 not in res_dept.context["schedules"]

    # Search query
    res_q = client_a.get(url, {"q": "Consent"})
    assert sch2 in res_q.context["schedules"]
    assert sch1 not in res_q.context["schedules"]


@pytest.mark.django_db
def test_records_management_retention_schedule_list_pagination(client_a, tenant_a):
    """Test retention_schedule_list pagination handles page splits cleanly."""
    for i in range(18):
        _records_management_create_schedule(tenant_a, code=f"RET-PAGE-{i:03d}", name=f"Schedule Page Item {i}")

    url = reverse("documents:retention_schedule_list")
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["schedules"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["schedules"]) == 3


@pytest.mark.django_db
def test_records_management_retention_schedule_create_get(client_a, tenant_a):
    """Test retention_schedule_create GET renders empty form with correct context."""
    url = reverse("documents:retention_schedule_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["schedule"] is None


@pytest.mark.django_db
def test_records_management_retention_schedule_create_post_success(client_a, tenant_a):
    """Test retention_schedule_create POST creates schedule and redirects to detail."""
    dept = _records_management_create_dept(tenant_a, name="Operations")
    url = reverse("documents:retention_schedule_create")
    data = {
        "name": "Operational Health & Safety Log",
        "code": "RET-OHS-001",
        "description": "OSHA incident records and annual audits.",
        "retention_period_years": 5,
        "retention_period_months": 0,
        "is_permanent": False,
        "trigger_type": "creation_date",
        "cutoff_rule": "calendar_year_end",
        "disposition_action": "destroy",
        "compliance_framework": "general",
        "retention_mode": "modifiable",
        "legal_citation": "29 CFR 1904.33",
        "department": dept.pk,
        "is_active": True,
        "notes": "Verified against state OSHA standards.",
    }
    resp = client_a.post(url, data)
    schedule = RetentionSchedule.objects.filter(tenant=tenant_a, code="RET-OHS-001").first()
    assert schedule is not None
    assert resp.status_code == 302
    assert resp.url == reverse("documents:retention_schedule_detail", kwargs={"pk": schedule.pk})
    assert schedule.name == "Operational Health & Safety Log"
    assert schedule.department == dept


@pytest.mark.django_db
def test_records_management_retention_schedule_create_post_invalid(client_a, tenant_a):
    """Test retention_schedule_create POST with invalid data returns form errors."""
    url = reverse("documents:retention_schedule_create")
    # Regulatory WORM schedule cannot have 0 years and 0 months if not permanent
    data = {
        "name": "Invalid WORM",
        "code": "RET-INV-001",
        "retention_period_years": 0,
        "retention_period_months": 0,
        "is_permanent": False,
        "retention_mode": "regulatory_worm",
        "compliance_framework": "sec_17a_4",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_records_management_retention_schedule_create_permission_denied(member_client, tenant_a):
    """Test non-admin member cannot create retention schedule (403 Forbidden)."""
    url = reverse("documents:retention_schedule_create")
    resp = member_client.get(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_records_management_retention_schedule_detail(client_a, tenant_a, admin_user):
    """Test retention_schedule_detail renders schedule and attached declared records."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DET-001")
    doc1 = _records_management_create_doc(tenant_a, admin_user, title="Doc Attached 1")
    doc2 = _records_management_create_doc(tenant_a, admin_user, title="Doc Attached 2")
    decl1 = _records_management_create_declaration(tenant_a, doc1, schedule, admin_user)
    decl2 = _records_management_create_declaration(tenant_a, doc2, schedule, admin_user)

    url = reverse("documents:retention_schedule_detail", kwargs={"pk": schedule.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["schedule"] == schedule
    assert resp.context["declared_records_count"] == 2
    assert decl1 in resp.context["declared_records"]
    assert decl2 in resp.context["declared_records"]


@pytest.mark.django_db
def test_records_management_retention_schedule_edit_get(client_a, tenant_a):
    """Test retention_schedule_edit GET renders edit form with instance populated."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-EDT-001")
    url = reverse("documents:retention_schedule_edit", kwargs={"pk": schedule.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["schedule"] == schedule


@pytest.mark.django_db
def test_records_management_retention_schedule_edit_post_success(client_a, tenant_a):
    """Test retention_schedule_edit POST updates schedule and redirects to detail."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-EDT-002", name="Pre-Edit Name")
    url = reverse("documents:retention_schedule_edit", kwargs={"pk": schedule.pk})
    data = {
        "name": "Updated Schedule Name",
        "code": "RET-EDT-002",
        "retention_period_years": 10,
        "retention_period_months": 6,
        "is_permanent": False,
        "trigger_type": "declaration_date",
        "cutoff_rule": "fiscal_year_end",
        "disposition_action": "archive",
        "compliance_framework": "iso_15489",
        "retention_mode": "modifiable",
        "is_active": True,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("documents:retention_schedule_detail", kwargs={"pk": schedule.pk})

    schedule.refresh_from_db()
    assert schedule.name == "Updated Schedule Name"
    assert schedule.retention_period_years == 10
    assert schedule.disposition_action == "archive"


@pytest.mark.django_db
def test_records_management_retention_schedule_edit_permission_denied(member_client, tenant_a):
    """Test non-admin member cannot edit retention schedule (403 Forbidden)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-PERM-EDT")
    url = reverse("documents:retention_schedule_edit", kwargs={"pk": schedule.pk})
    resp = member_client.get(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_records_management_retention_schedule_delete_blocked_with_declared_records(client_a, tenant_a, admin_user):
    """Test retention_schedule_delete is blocked when declared records are linked."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-BLK")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Attached Document")
    _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:retention_schedule_delete", kwargs={"pk": schedule.pk})
    resp = client_a.post(url)

    # Redirected back to detail with an error message, schedule preserved
    assert resp.status_code == 302
    assert resp.url == reverse("documents:retention_schedule_detail", kwargs={"pk": schedule.pk})
    assert RetentionSchedule.objects.filter(pk=schedule.pk).exists()


@pytest.mark.django_db
def test_records_management_retention_schedule_delete_success(client_a, tenant_a):
    """Test retention_schedule_delete succeeds when no declared records are attached."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-OK")
    url = reverse("documents:retention_schedule_delete", kwargs={"pk": schedule.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("documents:retention_schedule_list")
    assert not RetentionSchedule.objects.filter(pk=schedule.pk).exists()


@pytest.mark.django_db
def test_records_management_retention_schedule_delete_get_blocked(client_a, tenant_a):
    """Test retention_schedule_delete returns 405 on GET (require_POST)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-GET")
    url = reverse("documents:retention_schedule_delete", kwargs={"pk": schedule.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_records_management_retention_schedule_delete_permission_denied(member_client, tenant_a):
    """Test non-admin member cannot delete retention schedule (403 Forbidden)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-MBR")
    url = reverse("documents:retention_schedule_delete", kwargs={"pk": schedule.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


# ============================================================================
# 2. Record Declaration Views Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_record_declaration_list_rendering(client_a, tenant_a, admin_user):
    """Test record_declaration_list renders 200 OK with expected context keys."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DECLST-01")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Declaration List Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:record_declaration_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "declarations" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "status_choices" in resp.context
    assert "schedules" in resp.context
    assert decl in resp.context["declarations"]


@pytest.mark.django_db
def test_records_management_record_declaration_list_filters(client_a, tenant_a, admin_user):
    """Test record_declaration_list filtering by status, schedule, vital_only, and search."""
    sch1 = _records_management_create_schedule(tenant_a, code="RET-SCH-A")
    sch2 = _records_management_create_schedule(tenant_a, code="RET-SCH-B")

    doc1 = _records_management_create_doc(tenant_a, admin_user, title="Safety Policy Alpha")
    doc2 = _records_management_create_doc(tenant_a, admin_user, title="Financial Report Beta")

    decl1 = _records_management_create_declaration(
        tenant_a, doc1, sch1, admin_user, record_status="active", is_vital_record=True
    )
    decl2 = _records_management_create_declaration(
        tenant_a, doc2, sch2, admin_user, record_status="cutoff", is_vital_record=False
    )

    url = reverse("documents:record_declaration_list")

    # Filter status
    res_st = client_a.get(url, {"status": "cutoff"})
    assert decl2 in res_st.context["declarations"]
    assert decl1 not in res_st.context["declarations"]

    # Filter schedule
    res_sch = client_a.get(url, {"schedule": str(sch1.pk)})
    assert decl1 in res_sch.context["declarations"]
    assert decl2 not in res_sch.context["declarations"]

    # Filter vital
    res_vit_y = client_a.get(url, {"vital": "yes"})
    assert decl1 in res_vit_y.context["declarations"]
    assert decl2 not in res_vit_y.context["declarations"]

    res_vit_n = client_a.get(url, {"vital": "no"})
    assert decl2 in res_vit_n.context["declarations"]
    assert decl1 not in res_vit_n.context["declarations"]

    # Search query
    res_q = client_a.get(url, {"q": "Safety"})
    assert decl1 in res_q.context["declarations"]
    assert decl2 not in res_q.context["declarations"]


@pytest.mark.django_db
def test_records_management_record_declaration_list_pagination(client_a, tenant_a, admin_user):
    """Test record_declaration_list pagination handles 15+ items across pages."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-PAG-DCL")
    for i in range(18):
        doc = _records_management_create_doc(tenant_a, admin_user, title=f"Bulk Declaration Doc {i:02d}")
        _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:record_declaration_list")
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["declarations"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["declarations"]) == 3


@pytest.mark.django_db
def test_records_management_record_declaration_list_annotated_has_active_hold(client_a, tenant_a, admin_user):
    """Test record_declaration_list correctly annotates has_active_hold."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-HLD-ANN")
    doc_held = _records_management_create_doc(tenant_a, admin_user, title="Held Document Spec")
    doc_free = _records_management_create_doc(tenant_a, admin_user, title="Free Document Spec")
    doc_rel = _records_management_create_doc(tenant_a, admin_user, title="Released Hold Doc Spec")

    decl_held = _records_management_create_declaration(tenant_a, doc_held, schedule, admin_user)
    decl_free = _records_management_create_declaration(tenant_a, doc_free, schedule, admin_user)
    decl_rel = _records_management_create_declaration(tenant_a, doc_rel, schedule, admin_user)

    _records_management_create_hold(tenant_a, doc_held, admin_user, is_active=True)
    _records_management_create_hold(tenant_a, doc_rel, admin_user, is_active=False)

    url = reverse("documents:record_declaration_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    items_by_pk = {item.pk: item for item in resp.context["declarations"]}
    assert items_by_pk[decl_held.pk].has_active_hold is True
    assert items_by_pk[decl_free.pk].has_active_hold is False
    assert items_by_pk[decl_rel.pk].has_active_hold is False


@pytest.mark.django_db
def test_records_management_record_declaration_create_get(client_a, tenant_a, admin_user):
    """Test record_declaration_create GET renders form and handles prefill params."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-PRE-001")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Prefill Candidate Doc")

    url = reverse("documents:record_declaration_create")
    resp = client_a.get(url, {"schedule": str(schedule.pk), "document": str(doc.pk)})

    assert resp.status_code == 200
    assert resp.context["is_edit"] is False
    assert resp.context["declaration"] is None
    assert resp.context["form"].initial.get("retention_schedule") == schedule
    assert resp.context["form"].initial.get("document") == doc


@pytest.mark.django_db
def test_records_management_record_declaration_create_post_success(client_a, tenant_a, admin_user):
    """Test record_declaration_create POST saves declaration and redirects to detail."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CR-DCL")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Legal Agreement 2026")

    url = reverse("documents:record_declaration_create")
    data = {
        "document": doc.pk,
        "retention_schedule": schedule.pk,
        "declaration_mode": "manual",
        "is_vital_record": True,
        "vital_review_frequency_months": 6,
        "notes": "Officially declared for ISO records management.",
    }
    resp = client_a.post(url, data)
    declaration = RecordDeclaration.objects.filter(tenant=tenant_a, document=doc).first()

    assert declaration is not None
    assert resp.status_code == 302
    assert resp.url == reverse("documents:record_declaration_detail", kwargs={"pk": declaration.pk})
    assert declaration.declared_by == admin_user
    assert declaration.is_vital_record is True
    assert declaration.record_status == "active"


@pytest.mark.django_db
def test_records_management_record_declaration_create_duplicate_active_rejected(client_a, tenant_a, admin_user):
    """Test record_declaration_create rejects duplicate active declaration on the same document."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DUP-001")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Already Declared Doc")
    _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:record_declaration_create")
    data = {
        "document": doc.pk,
        "retention_schedule": schedule.pk,
        "declaration_mode": "manual",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    assert "document" in resp.context["form"].errors


@pytest.mark.django_db
def test_records_management_record_declaration_detail(client_a, tenant_a, admin_user):
    """Test record_declaration_detail renders declaration, active holds, and certificates."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DET-DCL")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Comprehensive Declaration Doc")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    hold = _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)
    cert = _records_management_create_certificate(tenant_a, declaration)

    url = reverse("documents:record_declaration_detail", kwargs={"pk": declaration.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["declaration"] == declaration
    assert hold in resp.context["active_holds"]
    assert cert in resp.context["certificates"]


@pytest.mark.django_db
def test_records_management_record_declaration_edit_get_and_post_success(client_a, tenant_a, admin_user):
    """Test record_declaration_edit allows updating an unlocked modifiable record."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-MOD-001", retention_mode="modifiable")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Modifiable Doc")
    declaration = _records_management_create_declaration(
        tenant_a, doc, schedule, admin_user, is_locked=False, vital_review_frequency_months=12
    )

    url = reverse("documents:record_declaration_edit", kwargs={"pk": declaration.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    data = {
        "document": doc.pk,
        "retention_schedule": schedule.pk,
        "declaration_mode": "manual",
        "is_vital_record": True,
        "vital_review_frequency_months": 24,
        "notes": "Updated vital review frequency to 24 months.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("documents:record_declaration_detail", kwargs={"pk": declaration.pk})

    declaration.refresh_from_db()
    assert declaration.vital_review_frequency_months == 24
    assert declaration.is_vital_record is True


@pytest.mark.django_db
def test_records_management_record_declaration_edit_rejection_locked_or_worm(client_a, tenant_a, admin_user):
    """Test record_declaration_edit rejects editing locked or regulatory WORM records."""
    # Case A: Record is locked
    sch_mod = _records_management_create_schedule(tenant_a, code="RET-MOD-LOCK", retention_mode="modifiable")
    doc_a = _records_management_create_doc(tenant_a, admin_user, title="Locked Record Doc")
    decl_locked = _records_management_create_declaration(tenant_a, doc_a, sch_mod, admin_user, is_locked=True)

    url_a = reverse("documents:record_declaration_edit", kwargs={"pk": decl_locked.pk})
    resp_a = client_a.get(url_a)
    assert resp_a.status_code == 302
    assert resp_a.url == reverse("documents:record_declaration_detail", kwargs={"pk": decl_locked.pk})

    # Case B: Schedule is regulatory WORM
    sch_worm = _records_management_create_schedule(tenant_a, code="RET-WORM-01", retention_mode="regulatory_worm")
    doc_b = _records_management_create_doc(tenant_a, admin_user, title="WORM Record Doc")
    decl_worm = _records_management_create_declaration(tenant_a, doc_b, sch_worm, admin_user, is_locked=False)

    url_b = reverse("documents:record_declaration_edit", kwargs={"pk": decl_worm.pk})
    resp_b = client_a.get(url_b)
    assert resp_b.status_code == 302
    assert resp_b.url == reverse("documents:record_declaration_detail", kwargs={"pk": decl_worm.pk})


@pytest.mark.django_db
def test_records_management_record_declaration_edit_rejection_active_hold(client_a, tenant_a, admin_user):
    """Test record_declaration_edit rejects editing records under active legal hold."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-HLD-EDT", retention_mode="modifiable")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Frozen Record Doc")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user, is_locked=False)
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:record_declaration_edit", kwargs={"pk": declaration.pk})
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("documents:record_declaration_detail", kwargs={"pk": declaration.pk})


@pytest.mark.django_db
def test_records_management_record_declaration_delete_rejection_locked_worm(client_a, tenant_a, admin_user):
    """Test record_declaration_delete rejects deleting locked regulatory WORM records."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-WRM", retention_mode="regulatory_worm")
    doc = _records_management_create_doc(tenant_a, admin_user, title="WORM Inviolable Record")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user, is_locked=True)

    url = reverse("documents:record_declaration_delete", kwargs={"pk": declaration.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("documents:record_declaration_detail", kwargs={"pk": declaration.pk})
    assert RecordDeclaration.objects.filter(pk=declaration.pk).exists()


@pytest.mark.django_db
def test_records_management_record_declaration_delete_rejection_active_hold(client_a, tenant_a, admin_user):
    """Test record_declaration_delete rejects deleting records under active legal hold."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-HLD", retention_mode="modifiable")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Hold Frozen Record")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user, is_locked=False)
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:record_declaration_delete", kwargs={"pk": declaration.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("documents:record_declaration_detail", kwargs={"pk": declaration.pk})
    assert RecordDeclaration.objects.filter(pk=declaration.pk).exists()


@pytest.mark.django_db
def test_records_management_record_declaration_delete_success(client_a, tenant_a, admin_user):
    """Test record_declaration_delete deletes eligible unlocked modifiable records without legal holds."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-OKD", retention_mode="modifiable")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Erasable Record Doc")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user, is_locked=False)

    url = reverse("documents:record_declaration_delete", kwargs={"pk": declaration.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("documents:record_declaration_list")
    assert not RecordDeclaration.objects.filter(pk=declaration.pk).exists()


@pytest.mark.django_db
def test_records_management_record_declaration_delete_get_blocked(client_a, tenant_a, admin_user):
    """Test record_declaration_delete returns 405 on GET (require_POST)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-GET2")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Delete GET Doc")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:record_declaration_delete", kwargs={"pk": declaration.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_records_management_record_declaration_delete_permission_denied(member_client, tenant_a, admin_user):
    """Test non-admin member cannot delete record declaration (403 Forbidden)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DEL-MBRD")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Member Delete Doc")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:record_declaration_delete", kwargs={"pk": declaration.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_records_management_record_declaration_trigger_cutoff_success(client_a, tenant_a, admin_user):
    """Test record_declaration_trigger_cutoff triggers retention clock and transitions to cutoff."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CUT-001", retention_period_years=3)
    doc = _records_management_create_doc(tenant_a, admin_user, title="Active Record for Cutoff")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user, record_status="active")

    url = reverse("documents:record_declaration_trigger_cutoff", kwargs={"pk": declaration.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("documents:record_declaration_detail", kwargs={"pk": declaration.pk})

    declaration.refresh_from_db()
    assert declaration.record_status == "cutoff"
    assert declaration.cutoff_date == timezone.now().date()
    assert declaration.disposition_due_date is not None


@pytest.mark.django_db
def test_records_management_record_declaration_trigger_cutoff_rejection(client_a, tenant_a, admin_user):
    """Test record_declaration_trigger_cutoff rejects non-active records (already cutoff or disposed)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CUT-REJ")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Already Cutoff Doc")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user, record_status="cutoff")

    url = reverse("documents:record_declaration_trigger_cutoff", kwargs={"pk": declaration.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("documents:record_declaration_detail", kwargs={"pk": declaration.pk})
    declaration.refresh_from_db()
    assert declaration.record_status == "cutoff"


@pytest.mark.django_db
def test_records_management_record_declaration_trigger_cutoff_get_blocked(client_a, tenant_a, admin_user):
    """Test record_declaration_trigger_cutoff returns 405 on GET (require_POST)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CUT-GET")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Cutoff GET Doc")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:record_declaration_trigger_cutoff", kwargs={"pk": declaration.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_records_management_record_declaration_trigger_cutoff_permission_denied(member_client, tenant_a, admin_user):
    """Test non-admin member cannot trigger cutoff (403 Forbidden)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CUT-MBR")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Cutoff Member Doc")
    declaration = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:record_declaration_trigger_cutoff", kwargs={"pk": declaration.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


# ============================================================================
# 3. Document Legal Hold Views Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_legal_hold_list_rendering(client_a, tenant_a, admin_user):
    """Test legal_hold_list renders 200 OK with expected context keys."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Legal Hold List Spec")
    hold = _records_management_create_hold(tenant_a, doc, admin_user)

    url = reverse("documents:legal_hold_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "holds" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "reason_choices" in resp.context
    assert hold in resp.context["holds"]


@pytest.mark.django_db
def test_records_management_legal_hold_list_filters(client_a, tenant_a, admin_user):
    """Test legal_hold_list filtering by hold reason, active/released status, and search query."""
    doc1 = _records_management_create_doc(tenant_a, admin_user, title="Antitrust Litigation Contract")
    doc2 = _records_management_create_doc(tenant_a, admin_user, title="Tax Audit Financials")

    h1 = _records_management_create_hold(
        tenant_a, doc1, admin_user, matter_name="Antitrust FTC", matter_number="MAT-FTC-01",
        hold_reason="litigation", is_active=True
    )
    h2 = _records_management_create_hold(
        tenant_a, doc2, admin_user, matter_name="IRS Tax Examination", matter_number="MAT-IRS-02",
        hold_reason="tax_investigation", is_active=False
    )

    url = reverse("documents:legal_hold_list")

    # Filter hold_reason
    res_rsn = client_a.get(url, {"hold_reason": "litigation"})
    assert h1 in res_rsn.context["holds"]
    assert h2 not in res_rsn.context["holds"]

    # Filter status: active vs released
    res_act = client_a.get(url, {"status": "active"})
    assert h1 in res_act.context["holds"]
    assert h2 not in res_act.context["holds"]

    res_rel = client_a.get(url, {"status": "released"})
    assert h2 in res_rel.context["holds"]
    assert h1 not in res_rel.context["holds"]

    # Filter search query
    res_q = client_a.get(url, {"q": "Examination"})
    assert h2 in res_q.context["holds"]
    assert h1 not in res_q.context["holds"]


@pytest.mark.django_db
def test_records_management_legal_hold_list_pagination(client_a, tenant_a, admin_user):
    """Test legal_hold_list pagination handles page splits."""
    for i in range(18):
        doc = _records_management_create_doc(tenant_a, admin_user, title=f"Hold Pagination Doc {i:02d}")
        _records_management_create_hold(tenant_a, doc, admin_user, matter_number=f"MAT-PAG-{i:03d}")

    url = reverse("documents:legal_hold_list")
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["holds"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["holds"]) == 3


@pytest.mark.django_db
def test_records_management_legal_hold_create_get(client_a, tenant_a, admin_user):
    """Test legal_hold_create GET renders form with document prefill support."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Target Document Hold")
    url = reverse("documents:legal_hold_create")
    resp = client_a.get(url, {"document": str(doc.pk)})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].initial.get("document") == doc


@pytest.mark.django_db
def test_records_management_legal_hold_create_post_success(client_a, tenant_a, admin_user, member_user):
    """Test legal_hold_create POST creates active legal hold and redirects to detail."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Patent Dispute Document")
    url = reverse("documents:legal_hold_create")
    data = {
        "matter_name": "In re ACME Patent Claims",
        "matter_number": "PAT-2026-880",
        "hold_reason": "litigation",
        "description": "Preserve all engineering and test notes.",
        "document": doc.pk,
        "custodian": member_user.pk,
    }
    resp = client_a.post(url, data)
    hold = DocumentLegalHold.objects.filter(tenant=tenant_a, matter_number="PAT-2026-880").first()

    assert hold is not None
    assert resp.status_code == 302
    assert resp.url == reverse("documents:legal_hold_detail", kwargs={"pk": hold.pk})
    assert hold.placed_by == admin_user
    assert hold.is_active is True
    assert hold.custodian == member_user


@pytest.mark.django_db
def test_records_management_legal_hold_create_post_invalid(client_a, tenant_a):
    """Test legal_hold_create POST with missing required fields returns errors."""
    url = reverse("documents:legal_hold_create")
    resp = client_a.post(url, {})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_records_management_legal_hold_detail(client_a, tenant_a, admin_user):
    """Test legal_hold_detail renders hold and includes release_form in context."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Detail Hold Doc")
    hold = _records_management_create_hold(tenant_a, doc, admin_user)

    url = reverse("documents:legal_hold_detail", kwargs={"pk": hold.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["hold"] == hold
    assert "release_form" in resp.context


@pytest.mark.django_db
def test_records_management_legal_hold_release_post_success(client_a, tenant_a, admin_user):
    """Test legal_hold_release releases hold with justification and records audit trail."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Hold to Release Doc")
    hold = _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:legal_hold_release", kwargs={"pk": hold.pk})
    data = {
        "release_justification": "Matter closed per court settlement order dated November 2026.",
    }
    resp = client_a.post(url, data)

    assert resp.status_code == 302
    assert resp.url == reverse("documents:legal_hold_detail", kwargs={"pk": hold.pk})

    hold.refresh_from_db()
    assert hold.is_active is False
    assert hold.released_by == admin_user
    assert hold.released_at is not None
    assert "court settlement order" in hold.release_justification


@pytest.mark.django_db
def test_records_management_legal_hold_release_empty_justification_rejected(client_a, tenant_a, admin_user):
    """Test legal_hold_release rejects empty justification and keeps hold active."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Reject Empty Release Doc")
    hold = _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:legal_hold_release", kwargs={"pk": hold.pk})
    resp = client_a.post(url, {"release_justification": ""})

    assert resp.status_code == 302
    assert resp.url == reverse("documents:legal_hold_detail", kwargs={"pk": hold.pk})

    hold.refresh_from_db()
    assert hold.is_active is True


@pytest.mark.django_db
def test_records_management_legal_hold_release_already_released(client_a, tenant_a, admin_user):
    """Test legal_hold_release on an already released hold redirects with info."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Already Released Doc")
    hold = _records_management_create_hold(tenant_a, doc, admin_user, is_active=False)

    url = reverse("documents:legal_hold_release", kwargs={"pk": hold.pk})
    resp = client_a.post(url, {"release_justification": "Re-releasing hold."})

    assert resp.status_code == 302
    assert resp.url == reverse("documents:legal_hold_detail", kwargs={"pk": hold.pk})


@pytest.mark.django_db
def test_records_management_legal_hold_release_get_blocked(client_a, tenant_a, admin_user):
    """Test legal_hold_release returns 405 on GET (require_POST)."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Hold Release GET Doc")
    hold = _records_management_create_hold(tenant_a, doc, admin_user)

    url = reverse("documents:legal_hold_release", kwargs={"pk": hold.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_records_management_legal_hold_release_permission_denied(member_client, tenant_a, admin_user):
    """Test non-admin member cannot release legal hold (403 Forbidden)."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Hold Release MBR Doc")
    hold = _records_management_create_hold(tenant_a, doc, admin_user)

    url = reverse("documents:legal_hold_release", kwargs={"pk": hold.pk})
    resp = member_client.post(url, {"release_justification": "Member release attempt."})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_records_management_legal_hold_acknowledge_post(client_a, tenant_a, admin_user):
    """Test legal_hold_acknowledge records custodian acknowledgment."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Acknowledge Hold Doc")
    hold = _records_management_create_hold(tenant_a, doc, admin_user, custodian=admin_user)

    url = reverse("documents:legal_hold_acknowledge", kwargs={"pk": hold.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("documents:legal_hold_detail", kwargs={"pk": hold.pk})

    hold.refresh_from_db()
    assert hold.custodian_acknowledged_at is not None
    assert hold.custodian_notified is True


@pytest.mark.django_db
def test_records_management_legal_hold_acknowledge_get_blocked(client_a, tenant_a, admin_user):
    """Test legal_hold_acknowledge returns 405 on GET (require_POST)."""
    doc = _records_management_create_doc(tenant_a, admin_user, title="Acknowledge GET Doc")
    hold = _records_management_create_hold(tenant_a, doc, admin_user)

    url = reverse("documents:legal_hold_acknowledge", kwargs={"pk": hold.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


# ============================================================================
# 4. Destruction Certificate Views Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_destruction_certificate_list_rendering(client_a, tenant_a, admin_user):
    """Test destruction_certificate_list renders 200 OK with expected context keys."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CRT-LST")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Certificate List Spec")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl)

    url = reverse("documents:destruction_certificate_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "certificates" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "status_choices" in resp.context
    assert "type_choices" in resp.context
    assert "method_choices" in resp.context
    assert cert in resp.context["certificates"]


@pytest.mark.django_db
def test_records_management_destruction_certificate_list_filters(client_a, tenant_a, admin_user):
    """Test destruction_certificate_list filtering by status, disposition type, method, and search."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CRT-FLT")
    doc1 = _records_management_create_doc(tenant_a, admin_user, title="Secure Destruction Blueprint")
    doc2 = _records_management_create_doc(tenant_a, admin_user, title="Archive Preservation Blueprint")

    decl1 = _records_management_create_declaration(tenant_a, doc1, schedule, admin_user)
    decl2 = _records_management_create_declaration(tenant_a, doc2, schedule, admin_user)

    c1 = _records_management_create_certificate(
        tenant_a, decl1, disposition_type="destruction", destruction_method="database_purge",
        status="pending_approval"
    )
    c2 = _records_management_create_certificate(
        tenant_a, decl2, disposition_type="archival_transfer", destruction_method="nara_transfer",
        status="authorized"
    )

    url = reverse("documents:destruction_certificate_list")

    # Filter status
    res_st = client_a.get(url, {"status": "authorized"})
    assert c2 in res_st.context["certificates"]
    assert c1 not in res_st.context["certificates"]

    # Filter disposition_type
    res_tp = client_a.get(url, {"disposition_type": "destruction"})
    assert c1 in res_tp.context["certificates"]
    assert c2 not in res_tp.context["certificates"]

    # Filter destruction_method
    res_mt = client_a.get(url, {"destruction_method": "nara_transfer"})
    assert c2 in res_mt.context["certificates"]
    assert c1 not in res_mt.context["certificates"]

    # Search query
    res_q = client_a.get(url, {"q": "Preservation"})
    assert c2 in res_q.context["certificates"]
    assert c1 not in res_q.context["certificates"]


@pytest.mark.django_db
def test_records_management_destruction_certificate_list_pagination(client_a, tenant_a, admin_user):
    """Test destruction_certificate_list pagination handles 15+ items across pages."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CRT-PAG")
    for i in range(18):
        doc = _records_management_create_doc(tenant_a, admin_user, title=f"Disposal Doc {i:02d}")
        decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
        _records_management_create_certificate(tenant_a, decl)

    url = reverse("documents:destruction_certificate_list")
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["certificates"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["certificates"]) == 3


@pytest.mark.django_db
def test_records_management_destruction_certificate_create_get(client_a, tenant_a, admin_user):
    """Test destruction_certificate_create GET renders form with prefill param support."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CRT-CR1")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Disposal Target Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:destruction_certificate_create")
    resp = client_a.get(url, {"declaration": str(decl.pk)})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].initial.get("record_declaration") == decl


@pytest.mark.django_db
def test_records_management_destruction_certificate_create_post_success(client_a, tenant_a, admin_user):
    """Test destruction_certificate_create POST drafts certificate and snapshots document data."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CR-SUC")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Target for Legal Purge")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)

    url = reverse("documents:destruction_certificate_create")
    data = {
        "record_declaration": decl.pk,
        "disposition_type": "destruction",
        "destruction_method": "database_purge",
        "certificate_notes": "All compliance pre-checks completed.",
    }
    resp = client_a.post(url, data)
    cert = DestructionCertificate.objects.filter(tenant=tenant_a, record_declaration=decl).first()

    assert cert is not None
    assert resp.status_code == 302
    assert resp.url == reverse("documents:destruction_certificate_detail", kwargs={"pk": cert.pk})
    assert cert.document_title_snapshot == "Target for Legal Purge"
    assert cert.document_number_snapshot == doc.number
    assert schedule.code in cert.schedule_name_snapshot
    assert cert.status == "pending_approval"


@pytest.mark.django_db
def test_records_management_destruction_certificate_create_rejection_under_hold(client_a, tenant_a, admin_user):
    """Test destruction_certificate_create rejects creation when document is under active legal hold."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-CRT-HLD")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Litigation Shielded Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:destruction_certificate_create")
    data = {
        "record_declaration": decl.pk,
        "disposition_type": "destruction",
        "destruction_method": "database_purge",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    assert "record_declaration" in resp.context["form"].errors


@pytest.mark.django_db
def test_records_management_destruction_certificate_detail(client_a, tenant_a, admin_user):
    """Test destruction_certificate_detail renders certificate context."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-DET-CERT")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Detail Cert Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl)

    url = reverse("documents:destruction_certificate_detail", kwargs={"pk": cert.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["certificate"] == cert


@pytest.mark.django_db
def test_records_management_destruction_certificate_authorize_success(client_a, tenant_a, admin_user):
    """Test destruction_certificate_authorize transitions status to authorized."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-AUTH-SUC")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Auth Clearance Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl, status="pending_approval")

    url = reverse("documents:destruction_certificate_authorize", kwargs={"pk": cert.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("documents:destruction_certificate_detail", kwargs={"pk": cert.pk})

    cert.refresh_from_db()
    assert cert.status == "authorized"
    assert cert.authorized_by == admin_user
    assert cert.authorized_at is not None


@pytest.mark.django_db
def test_records_management_destruction_certificate_authorize_rejection_under_hold(client_a, tenant_a, admin_user):
    """Test destruction_certificate_authorize rejects authorization when hold is active."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-AUTH-REJ")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Auth Blocked Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl, status="pending_approval")
    _records_management_create_hold(tenant_a, doc, admin_user, is_active=True)

    url = reverse("documents:destruction_certificate_authorize", kwargs={"pk": cert.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("documents:destruction_certificate_detail", kwargs={"pk": cert.pk})

    cert.refresh_from_db()
    assert cert.status == "pending_approval"


@pytest.mark.django_db
def test_records_management_destruction_certificate_authorize_get_blocked(client_a, tenant_a, admin_user):
    """Test destruction_certificate_authorize returns 405 on GET (require_POST)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-AUTH-GET")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Auth GET Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl)

    url = reverse("documents:destruction_certificate_authorize", kwargs={"pk": cert.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_records_management_destruction_certificate_authorize_permission_denied(member_client, tenant_a, admin_user):
    """Test non-admin member cannot authorize destruction certificate (403 Forbidden)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-AUTH-MBR")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Auth MBR Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl)

    url = reverse("documents:destruction_certificate_authorize", kwargs={"pk": cert.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_records_management_destruction_certificate_execute_rejection_not_authorized(client_a, tenant_a, admin_user):
    """Test destruction_certificate_execute rejects certificates not yet authorized."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-EXE-REJ")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Premature Exec Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl, status="pending_approval")

    url = reverse("documents:destruction_certificate_execute", kwargs={"pk": cert.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("documents:destruction_certificate_detail", kwargs={"pk": cert.pk})

    cert.refresh_from_db()
    assert cert.status == "pending_approval"


@pytest.mark.django_db
def test_records_management_destruction_certificate_execute_success(client_a, tenant_a, admin_user):
    """Test destruction_certificate_execute archives document and marks record disposed."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-EXE-SUC")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Doc Bound for Archival")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user, record_status="active")
    cert = _records_management_create_certificate(tenant_a, decl, status="authorized")

    url = reverse("documents:destruction_certificate_execute", kwargs={"pk": cert.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("documents:destruction_certificate_detail", kwargs={"pk": cert.pk})

    cert.refresh_from_db()
    decl.refresh_from_db()
    doc.refresh_from_db()

    assert cert.status == "executed"
    assert cert.executed_by == admin_user
    assert cert.executed_at is not None
    assert decl.record_status == "disposed"
    assert doc.status == "archived"


@pytest.mark.django_db
def test_records_management_destruction_certificate_execute_rejection_already_executed(client_a, tenant_a, admin_user):
    """Test destruction_certificate_execute rejects already executed certificates."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-EXE-ALR")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Already Executed Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl, status="executed")

    url = reverse("documents:destruction_certificate_execute", kwargs={"pk": cert.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("documents:destruction_certificate_detail", kwargs={"pk": cert.pk})


@pytest.mark.django_db
def test_records_management_destruction_certificate_execute_get_blocked(client_a, tenant_a, admin_user):
    """Test destruction_certificate_execute returns 405 on GET (require_POST)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-EXE-GET")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Exec GET Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl)

    url = reverse("documents:destruction_certificate_execute", kwargs={"pk": cert.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_records_management_destruction_certificate_execute_permission_denied(member_client, tenant_a, admin_user):
    """Test non-admin member cannot execute destruction certificate (403 Forbidden)."""
    schedule = _records_management_create_schedule(tenant_a, code="RET-EXE-MBR")
    doc = _records_management_create_doc(tenant_a, admin_user, title="Exec MBR Doc")
    decl = _records_management_create_declaration(tenant_a, doc, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl, status="authorized")

    url = reverse("documents:destruction_certificate_execute", kwargs={"pk": cert.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


# ============================================================================
# 5. Specialized Views Tests
# ============================================================================

@pytest.mark.django_db
def test_records_management_disposition_review_board(client_a, tenant_a, admin_user):
    """Test disposition_review_board partitions due, held, and pending certificate records."""
    today = timezone.now().date()
    past_due_date = today - datetime.timedelta(days=10)

    schedule = _records_management_create_schedule(tenant_a, code="RET-DSP-BRD")

    # Due record: past due date, not held, not disposed
    doc_due = _records_management_create_doc(tenant_a, admin_user, title="Due Record Doc")
    decl_due = _records_management_create_declaration(
        tenant_a, doc_due, schedule, admin_user, record_status="cutoff", disposition_due_date=past_due_date
    )

    # Held record: active legal hold present
    doc_held = _records_management_create_doc(tenant_a, admin_user, title="Held Record Doc")
    decl_held = _records_management_create_declaration(
        tenant_a, doc_held, schedule, admin_user, record_status="active", disposition_due_date=past_due_date
    )
    _records_management_create_hold(tenant_a, doc_held, admin_user, is_active=True)

    # Pending certificate
    doc_cert = _records_management_create_doc(tenant_a, admin_user, title="Pending Cert Doc")
    decl_cert = _records_management_create_declaration(tenant_a, doc_cert, schedule, admin_user)
    cert = _records_management_create_certificate(tenant_a, decl_cert, status="pending_approval")

    # Disposed record: should NOT appear in due or held
    doc_disp = _records_management_create_doc(tenant_a, admin_user, title="Disposed Record Doc")
    _records_management_create_declaration(
        tenant_a, doc_disp, schedule, admin_user, record_status="disposed", disposition_due_date=past_due_date
    )

    url = reverse("documents:disposition_review_board")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "due_records" in resp.context
    assert "held_records" in resp.context
    assert "pending_certificates" in resp.context
    assert "due_count" in resp.context
    assert "held_count" in resp.context
    assert "pending_count" in resp.context

    due_records = list(resp.context["due_records"])
    held_records = list(resp.context["held_records"])
    pending_certificates = list(resp.context["pending_certificates"])

    assert decl_due in due_records
    assert decl_held not in due_records
    assert decl_held in held_records
    assert cert in pending_certificates


@pytest.mark.django_db
def test_records_management_vital_records_list(client_a, tenant_a, admin_user):
    """Test vital_records_list renders vital records only and supports department/query filtering."""
    dept1 = _records_management_create_dept(tenant_a, name="Treasury Department")
    dept2 = _records_management_create_dept(tenant_a, name="R&D Department")

    sch1 = _records_management_create_schedule(tenant_a, code="RET-VTL-1", department=dept1)
    sch2 = _records_management_create_schedule(tenant_a, code="RET-VTL-2", department=dept2)

    doc_vital1 = _records_management_create_doc(tenant_a, admin_user, title="Mission Critical Treasury Formula")
    doc_vital2 = _records_management_create_doc(tenant_a, admin_user, title="Proprietary R&D Algorithm")
    doc_non_vital = _records_management_create_doc(tenant_a, admin_user, title="General Office Supplies Receipt")

    decl_v1 = _records_management_create_declaration(tenant_a, doc_vital1, sch1, admin_user, is_vital_record=True)
    decl_v2 = _records_management_create_declaration(tenant_a, doc_vital2, sch2, admin_user, is_vital_record=True)
    decl_nv = _records_management_create_declaration(tenant_a, doc_non_vital, sch1, admin_user, is_vital_record=False)

    url = reverse("documents:vital_records_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "vital_records" in resp.context
    assert "departments" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context

    vital_items = list(resp.context["vital_records"])
    assert decl_v1 in vital_items
    assert decl_v2 in vital_items
    assert decl_nv not in vital_items

    # Filter department
    resp_dept = client_a.get(url, {"department": str(dept1.pk)})
    assert decl_v1 in resp_dept.context["vital_records"]
    assert decl_v2 not in resp_dept.context["vital_records"]

    # Filter search query
    resp_q = client_a.get(url, {"q": "Algorithm"})
    assert decl_v2 in resp_q.context["vital_records"]
    assert decl_v1 not in resp_q.context["vital_records"]


# ============================================================================
# 6. Tenant Isolation & Security Edge Cases
# ============================================================================

@pytest.mark.django_db
def test_records_management_tenant_isolation_schedule(client_a, tenant_b, admin_b):
    """Test cross-tenant access to retention schedule returns 404."""
    sch_b = _records_management_create_schedule(tenant_b, code="RET-TB-001")

    # Detail
    assert client_a.get(reverse("documents:retention_schedule_detail", kwargs={"pk": sch_b.pk})).status_code == 404
    # Edit
    assert client_a.get(reverse("documents:retention_schedule_edit", kwargs={"pk": sch_b.pk})).status_code == 404
    # Delete
    assert client_a.post(reverse("documents:retention_schedule_delete", kwargs={"pk": sch_b.pk})).status_code == 404


@pytest.mark.django_db
def test_records_management_tenant_isolation_declaration(client_a, tenant_b, admin_b):
    """Test cross-tenant access to record declaration returns 404."""
    sch_b = _records_management_create_schedule(tenant_b, code="RET-TB-DCL")
    doc_b = _records_management_create_doc(tenant_b, admin_b, title="Tenant B Confidential Doc")
    decl_b = _records_management_create_declaration(tenant_b, doc_b, sch_b, admin_b, is_locked=False)

    # Detail
    assert client_a.get(reverse("documents:record_declaration_detail", kwargs={"pk": decl_b.pk})).status_code == 404
    # Edit
    assert client_a.get(reverse("documents:record_declaration_edit", kwargs={"pk": decl_b.pk})).status_code == 404
    # Delete
    assert client_a.post(reverse("documents:record_declaration_delete", kwargs={"pk": decl_b.pk})).status_code == 404
    # Cutoff
    assert client_a.post(reverse("documents:record_declaration_trigger_cutoff", kwargs={"pk": decl_b.pk})).status_code == 404


@pytest.mark.django_db
def test_records_management_tenant_isolation_legal_hold(client_a, tenant_b, admin_b):
    """Test cross-tenant access to legal hold returns 404."""
    doc_b = _records_management_create_doc(tenant_b, admin_b, title="Tenant B Hold Doc")
    hold_b = _records_management_create_hold(tenant_b, doc_b, admin_b)

    # Detail
    assert client_a.get(reverse("documents:legal_hold_detail", kwargs={"pk": hold_b.pk})).status_code == 404
    # Release
    assert client_a.post(
        reverse("documents:legal_hold_release", kwargs={"pk": hold_b.pk}),
        {"release_justification": "Cross tenant release attempt."}
    ).status_code == 404
    # Acknowledge
    assert client_a.post(reverse("documents:legal_hold_acknowledge", kwargs={"pk": hold_b.pk})).status_code == 404


@pytest.mark.django_db
def test_records_management_tenant_isolation_destruction_certificate(client_a, tenant_b, admin_b):
    """Test cross-tenant access to destruction certificate returns 404."""
    sch_b = _records_management_create_schedule(tenant_b, code="RET-TB-CRT")
    doc_b = _records_management_create_doc(tenant_b, admin_b, title="Tenant B Cert Doc")
    decl_b = _records_management_create_declaration(tenant_b, doc_b, sch_b, admin_b)
    cert_b = _records_management_create_certificate(tenant_b, decl_b)

    # Detail
    assert client_a.get(reverse("documents:destruction_certificate_detail", kwargs={"pk": cert_b.pk})).status_code == 404
    # Authorize
    assert client_a.post(reverse("documents:destruction_certificate_authorize", kwargs={"pk": cert_b.pk})).status_code == 404
    # Execute
    assert client_a.post(reverse("documents:destruction_certificate_execute", kwargs={"pk": cert_b.pk})).status_code == 404
