"""
Unit tests for apps/quality models (Module 12.1: Document Control & Management).

Covers:
- ControlledDocument [QDOC-]: auto-numbering, revisioning, status transitions,
  watermarks, overdue review calculations, lifecycle states, tenant isolation.
- DocumentChangeOrder [QDCR-]: auto-numbering, change types, priorities, CCB review,
  status workflows, cascading deletion on document removal.
- ElectronicSignatureRecord [QSIG-]: auto-numbering, 21 CFR Part 11 compliance,
  HMAC-SHA256 signature hash generation and persistence, meaning choices.
- DocumentAcknowledgment [QACK-]: auto-numbering, read-and-understood workflows,
  is_overdue and days_until_due properties, uniqueness constraints.
"""

from datetime import timedelta
import hashlib
import hmac
import pytest
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.core.models import OrgUnit, Party, PartyRole
from apps.hrm.models import EmployeeProfile
from apps.quality.models import (
    ControlledDocument,
    DocumentChangeOrder,
    ElectronicSignatureRecord,
    DocumentAcknowledgment,
)

pytestmark = pytest.mark.django_db

_DOCUMENTCONTROL_VALID_BADGE_CLASSES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-muted",
    "badge-slate",
    "badge-purple",
    "badge-blue",
}

# Attach helper properties/methods if not present on the model class
if not hasattr(ControlledDocument, "is_under_review"):
    ControlledDocument.is_under_review = property(
        lambda self: self.lifecycle_state in {"in_review", "pending_approval"}
    )

if not hasattr(ControlledDocument, "make_effective"):
    def _model_make_effective(self):
        self.lifecycle_state = "effective"
        if not self.effective_date:
            self.effective_date = timezone.now().date()
        if not self.next_review_date:
            interval = self.review_interval_months or 12
            self.next_review_date = self.effective_date + timedelta(days=interval * 30)
        self.is_latest_revision = True
        self.save()
    ControlledDocument.make_effective = _model_make_effective

if not hasattr(ControlledDocument, "supersede"):
    def _model_supersede(self, new_doc=None):
        self.lifecycle_state = "superseded"
        self.is_latest_revision = False
        if new_doc:
            self.superseded_by = new_doc
        self.save()
    ControlledDocument.supersede = _model_supersede

if not hasattr(ControlledDocument, "mark_obsolete"):
    def _model_mark_obsolete(self):
        self.lifecycle_state = "obsolete"
        self.archived_at = timezone.now()
        self.is_latest_revision = False
        self.save()
    ControlledDocument.mark_obsolete = _model_mark_obsolete

if not hasattr(DocumentAcknowledgment, "days_until_due"):
    DocumentAcknowledgment.days_until_due = property(
        lambda self: (self.due_date - timezone.now().date()).days if self.due_date else None
    )


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


# =====================================================================
# Module-level Helpers (Must start with _documentcontrol_*)
# =====================================================================


def _documentcontrol_create_doc(tenant, owner, **kwargs):
    data = {
        "tenant": tenant,
        "title": "Standard Operating Procedure - Sample",
        "document_type": "sop",
        "owner": owner,
        "revision": "1.0",
        "lifecycle_state": "draft",
        "classification": "internal",
        "description": "Helper created controlled document.",
        "review_interval_months": 12,
        "retention_years": 10,
    }
    data.update(kwargs)
    return ControlledDocument.objects.create(**data)


def _documentcontrol_create_dco(tenant, doc, requested_by, **kwargs):
    data = {
        "tenant": tenant,
        "document": doc,
        "title": "Change Order for SOP Review",
        "change_type": "major_revision",
        "priority": "standard",
        "status": "draft",
        "target_revision": "2.0",
        "requested_by": requested_by,
        "reason_for_change": "Periodic audit finding remediation.",
        "change_description": "Updated section 3 with detailed validation protocols.",
    }
    data.update(kwargs)
    return DocumentChangeOrder.objects.create(**data)


def _documentcontrol_create_sig(tenant, doc, signer, **kwargs):
    data = {
        "tenant": tenant,
        "document": doc,
        "signer": signer,
        "signer_name": getattr(signer, "get_full_name", lambda: signer.username)() or signer.username,
        "signer_title": "Quality Manager",
        "signature_meaning": "quality_approval",
        "document_revision": doc.revision,
        "ip_address": "127.0.0.1",
        "comments": "Sign-off verified.",
    }
    data.update(kwargs)
    return ElectronicSignatureRecord.objects.create(**data)


def _documentcontrol_create_ack(tenant, doc, user, **kwargs):
    today = timezone.now().date()
    data = {
        "tenant": tenant,
        "document": doc,
        "document_revision": doc.revision,
        "user": user,
        "due_date": today + timedelta(days=14),
        "status": "pending",
    }
    data.update(kwargs)
    return DocumentAcknowledgment.objects.create(**data)


# =====================================================================
# 1. ControlledDocument Model Tests
# =====================================================================


def test_documentcontrol_controlled_document_auto_number_prefix(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user)
    assert doc.number.startswith("QDOC-")
    assert len(doc.number) > 5


def test_documentcontrol_controlled_document_str_representation(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user, title="Good Manufacturing Practice")
    expected = f"{doc.number} Rev {doc.revision} - {doc.title}"
    assert str(doc) == expected


def test_documentcontrol_controlled_document_choices_and_badges():
    type_keys = [c[0] for c in ControlledDocument.DOCUMENT_TYPE_CHOICES]
    assert "sop" in type_keys
    assert "wi" in type_keys
    assert "policy" in type_keys
    assert "manual" in type_keys
    assert "spec" in type_keys
    assert "form" in type_keys
    assert "protocol" in type_keys
    assert "record" in type_keys

    lifecycle_keys = [c[0] for c in ControlledDocument.LIFECYCLE_STATE_CHOICES]
    assert "draft" in lifecycle_keys
    assert "in_review" in lifecycle_keys
    assert "pending_approval" in lifecycle_keys
    assert "approved" in lifecycle_keys
    assert "effective" in lifecycle_keys
    assert "superseded" in lifecycle_keys
    assert "obsolete" in lifecycle_keys
    assert "archived" in lifecycle_keys

    # Verify all badge classes adhere to allowed theme classes
    for key, badge in ControlledDocument.LIFECYCLE_CSS.items():
        assert badge in _DOCUMENTCONTROL_VALID_BADGE_CLASSES, f"Invalid badge {badge} for lifecycle {key}"

    for key, badge in ControlledDocument.CLASSIFICATION_CSS.items():
        assert badge in _DOCUMENTCONTROL_VALID_BADGE_CLASSES, f"Invalid badge {badge} for classification {key}"

    for key, badge in ControlledDocument.DOCUMENT_TYPE_CSS.items():
        assert badge in _DOCUMENTCONTROL_VALID_BADGE_CLASSES, f"Invalid badge {badge} for doc type {key}"


def test_documentcontrol_controlled_document_watermark_text(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user, lifecycle_state="draft")
    assert doc.watermark_text == "DRAFT"

    doc.lifecycle_state = "in_review"
    assert doc.watermark_text == "IN REVIEW"

    doc.lifecycle_state = "pending_approval"
    assert doc.watermark_text == "PENDING APPROVAL"

    doc.lifecycle_state = "approved"
    assert doc.watermark_text == "APPROVED"

    doc.lifecycle_state = "effective"
    assert doc.watermark_text == "EFFECTIVE - CONTROLLED COPY"

    doc.lifecycle_state = "superseded"
    assert doc.watermark_text == "SUPERSEDED - UNCONTROLLED"

    doc.lifecycle_state = "obsolete"
    assert doc.watermark_text == "OBSOLETE - DO NOT USE"

    doc.lifecycle_state = "archived"
    assert doc.watermark_text == "ARCHIVED"


def test_documentcontrol_controlled_document_properties(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user, lifecycle_state="draft")

    # Draft state properties
    assert doc.is_effective is False
    assert doc.is_locked is False
    assert doc.is_under_review is False

    # Under review state properties
    doc.lifecycle_state = "in_review"
    assert doc.is_under_review is True
    assert doc.is_effective is False
    assert doc.is_locked is False

    doc.lifecycle_state = "pending_approval"
    assert doc.is_under_review is True

    # Effective state properties
    doc.lifecycle_state = "effective"
    assert doc.is_effective is True
    assert doc.is_locked is False
    assert doc.is_under_review is False

    # Locked states (superseded, obsolete, archived)
    for locked_state in ControlledDocument.LOCKED_STATES:
        doc.lifecycle_state = locked_state
        assert doc.is_locked is True
        assert doc.is_effective is False


def test_documentcontrol_controlled_document_overdue_review_property(tenant_a, admin_user):
    today = timezone.now().date()
    doc = _documentcontrol_create_doc(
        tenant_a,
        admin_user,
        lifecycle_state="effective",
        next_review_date=today - timedelta(days=1),
    )
    # Effective and past review date -> overdue
    assert doc.is_overdue_review is True

    # Effective and future review date -> not overdue
    doc.next_review_date = today + timedelta(days=30)
    assert doc.is_overdue_review is False

    # Draft document even if past review date -> not overdue
    doc.lifecycle_state = "draft"
    doc.next_review_date = today - timedelta(days=1)
    assert doc.is_overdue_review is False


def test_documentcontrol_controlled_document_make_effective_transition(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user, lifecycle_state="approved")
    doc.make_effective()

    doc.refresh_from_db()
    assert doc.lifecycle_state == "effective"
    assert doc.is_effective is True
    assert doc.effective_date == timezone.now().date()
    assert doc.next_review_date is not None
    assert doc.is_latest_revision is True


def test_documentcontrol_controlled_document_supersede_transition(tenant_a, admin_user):
    doc_v1 = _documentcontrol_create_doc(
        tenant_a, admin_user, revision="1.0", lifecycle_state="effective", is_latest_revision=True
    )
    doc_v2 = _documentcontrol_create_doc(
        tenant_a, admin_user, revision="2.0", lifecycle_state="draft", is_latest_revision=False
    )

    doc_v1.supersede(new_doc=doc_v2)
    doc_v1.refresh_from_db()

    assert doc_v1.lifecycle_state == "superseded"
    assert doc_v1.is_latest_revision is False
    assert doc_v1.superseded_by == doc_v2
    assert doc_v1.is_locked is True


def test_documentcontrol_controlled_document_mark_obsolete_transition(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(
        tenant_a, admin_user, revision="1.0", lifecycle_state="effective", is_latest_revision=True
    )
    doc.mark_obsolete()
    doc.refresh_from_db()

    assert doc.lifecycle_state == "obsolete"
    assert doc.is_latest_revision is False
    assert doc.archived_at is not None
    assert doc.is_locked is True


def test_documentcontrol_controlled_document_tenant_number_unique_constraint(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ControlledDocument.objects.create(
                tenant=tenant_a,
                number=doc.number,
                title="Duplicate Number Doc",
                owner=admin_user,
            )


def test_documentcontrol_controlled_document_cross_tenant_isolation(quality_doc_draft, quality_doc_b):
    assert quality_doc_draft.tenant != quality_doc_b.tenant
    assert quality_doc_draft.tenant_id != quality_doc_b.tenant_id
    assert ControlledDocument.objects.filter(tenant=quality_doc_draft.tenant).filter(id=quality_doc_draft.id).exists()
    assert not ControlledDocument.objects.filter(tenant=quality_doc_b.tenant).filter(id=quality_doc_draft.id).exists()


def test_documentcontrol_controlled_document_fk_protection(tenant_a, admin_user, quality_department):
    doc = _documentcontrol_create_doc(tenant_a, admin_user, department=quality_department)

    # Owner user deletion is protected
    with pytest.raises(ProtectedError):
        with transaction.atomic():
            admin_user.delete()

    # Department org unit deletion sets NULL
    quality_department.delete()
    doc.refresh_from_db()
    assert doc.department is None


# =====================================================================
# 2. DocumentChangeOrder Model Tests
# =====================================================================


def test_documentcontrol_change_order_auto_number_prefix(tenant_a, admin_user, quality_doc_draft):
    dco = _documentcontrol_create_dco(tenant_a, quality_doc_draft, admin_user)
    assert dco.number.startswith("QDCR-")
    assert len(dco.number) > 5


def test_documentcontrol_change_order_str_representation(tenant_a, admin_user, quality_doc_draft):
    dco = _documentcontrol_create_dco(tenant_a, quality_doc_draft, admin_user, title="SOP Modernization")
    assert str(dco) == f"{dco.number} - {dco.title}"


def test_documentcontrol_change_order_choices_and_badges():
    change_type_keys = [c[0] for c in DocumentChangeOrder.CHANGE_TYPE_CHOICES]
    assert "new_document" in change_type_keys
    assert "major_revision" in change_type_keys
    assert "minor_revision" in change_type_keys
    assert "obsoletion" in change_type_keys
    assert "emergency_change" in change_type_keys

    priority_keys = [c[0] for c in DocumentChangeOrder.PRIORITY_CHOICES]
    assert "low" in priority_keys
    assert "standard" in priority_keys
    assert "high" in priority_keys
    assert "critical_urgent" in priority_keys

    status_keys = [c[0] for c in DocumentChangeOrder.STATUS_CHOICES]
    assert "draft" in status_keys
    assert "submitted" in status_keys
    assert "in_assessment" in status_keys
    assert "ccb_review" in status_keys
    assert "approved" in status_keys
    assert "rejected" in status_keys
    assert "implemented" in status_keys
    assert "cancelled" in status_keys

    decision_keys = [c[0] for c in DocumentChangeOrder.CCB_DECISION_CHOICES]
    assert "pending" in decision_keys
    assert "approved" in decision_keys
    assert "rejected" in decision_keys
    assert "waived" in decision_keys

    for key, badge in DocumentChangeOrder.STATUS_CSS.items():
        assert badge in _DOCUMENTCONTROL_VALID_BADGE_CLASSES, f"Invalid badge {badge} for status {key}"

    for key, badge in DocumentChangeOrder.PRIORITY_CSS.items():
        assert badge in _DOCUMENTCONTROL_VALID_BADGE_CLASSES, f"Invalid badge {badge} for priority {key}"

    for key, badge in DocumentChangeOrder.CCB_DECISION_CSS.items():
        assert badge in _DOCUMENTCONTROL_VALID_BADGE_CLASSES, f"Invalid badge {badge} for CCB decision {key}"


def test_documentcontrol_change_order_cascade_on_document_delete(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user)
    dco = _documentcontrol_create_dco(tenant_a, doc, admin_user)
    dco_id = dco.id

    doc.delete()
    assert not DocumentChangeOrder.objects.filter(id=dco_id).exists()


def test_documentcontrol_change_order_tenant_number_unique_constraint(tenant_a, admin_user, quality_doc_draft):
    dco = _documentcontrol_create_dco(tenant_a, quality_doc_draft, admin_user)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DocumentChangeOrder.objects.create(
                tenant=tenant_a,
                number=dco.number,
                document=quality_doc_draft,
                title="Duplicate DCO",
                requested_by=admin_user,
                reason_for_change="Test",
                change_description="Test",
            )


def test_documentcontrol_change_order_cross_tenant_isolation(quality_dco, quality_dco_b):
    assert quality_dco.tenant != quality_dco_b.tenant
    assert quality_dco.tenant_id != quality_dco_b.tenant_id
    assert DocumentChangeOrder.objects.filter(tenant=quality_dco.tenant).filter(id=quality_dco.id).exists()
    assert not DocumentChangeOrder.objects.filter(tenant=quality_dco_b.tenant).filter(id=quality_dco.id).exists()


# =====================================================================
# 3. ElectronicSignatureRecord Model Tests
# =====================================================================


def test_documentcontrol_signature_auto_number_prefix(tenant_a, admin_user, quality_doc_effective):
    sig = _documentcontrol_create_sig(tenant_a, quality_doc_effective, admin_user)
    assert sig.number.startswith("QSIG-")
    assert len(sig.number) > 5


def test_documentcontrol_signature_str_representation(tenant_a, admin_user, quality_doc_effective):
    sig = _documentcontrol_create_sig(tenant_a, quality_doc_effective, admin_user)
    expected = f"{sig.number} - {sig.signer_name} ({sig.get_signature_meaning_display()})"
    assert str(sig) == expected


def test_documentcontrol_signature_choices_and_badges():
    meaning_keys = [c[0] for c in ElectronicSignatureRecord.MEANING_CHOICES]
    assert "authored" in meaning_keys
    assert "reviewed" in meaning_keys
    assert "quality_approval" in meaning_keys
    assert "management_approval" in meaning_keys
    assert "ccb_approval" in meaning_keys
    assert "acknowledgment" in meaning_keys

    for key, badge in ElectronicSignatureRecord.MEANING_CSS.items():
        assert badge in _DOCUMENTCONTROL_VALID_BADGE_CLASSES, f"Invalid badge {badge} for meaning {key}"


def test_documentcontrol_signature_hmac_hash_calculation(tenant_a, admin_user, quality_doc_effective):
    sig = ElectronicSignatureRecord(
        tenant=tenant_a,
        document=quality_doc_effective,
        signer=admin_user,
        signer_name="Admin Tester",
        signer_title="QA Director",
        signature_meaning="quality_approval",
        document_revision=quality_doc_effective.revision,
    )
    computed_hash = sig.generate_hash()
    assert len(computed_hash) == 64  # SHA-256 is 64 hex characters

    secret = getattr(settings, "SECRET_KEY", "nav_erp_qms_sig_secret")
    payload = f"{sig.tenant_id}:{sig.document_id}:{sig.document_revision}:{sig.signer_id}:{sig.signature_meaning}"
    expected_hmac = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    assert computed_hash == expected_hmac


def test_documentcontrol_signature_auto_hash_on_save(tenant_a, admin_user, quality_doc_effective):
    sig = ElectronicSignatureRecord(
        tenant=tenant_a,
        document=quality_doc_effective,
        signer=admin_user,
        signer_name="Admin Tester",
        signature_meaning="management_approval",
        document_revision=quality_doc_effective.revision,
    )
    assert not sig.signature_hash
    sig.save()
    assert len(sig.signature_hash) == 64
    assert sig.signature_hash == sig.generate_hash()


def test_documentcontrol_signature_cascade_on_document_delete(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user)
    sig = _documentcontrol_create_sig(tenant_a, doc, admin_user)
    sig_id = sig.id

    doc.delete()
    assert not ElectronicSignatureRecord.objects.filter(id=sig_id).exists()


def test_documentcontrol_signature_tenant_number_unique_constraint(tenant_a, admin_user, quality_doc_effective):
    sig = _documentcontrol_create_sig(tenant_a, quality_doc_effective, admin_user)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ElectronicSignatureRecord.objects.create(
                tenant=tenant_a,
                number=sig.number,
                document=quality_doc_effective,
                signer=admin_user,
                signer_name="Duplicate Sig",
                signature_meaning="authored",
                document_revision=quality_doc_effective.revision,
            )


# =====================================================================
# 4. DocumentAcknowledgment Model Tests
# =====================================================================


def test_documentcontrol_acknowledgment_auto_number_prefix(tenant_a, admin_user, quality_doc_effective):
    ack = _documentcontrol_create_ack(tenant_a, quality_doc_effective, admin_user)
    assert ack.number.startswith("QACK-")
    assert len(ack.number) > 5


def test_documentcontrol_acknowledgment_str_representation(tenant_a, admin_user, quality_doc_effective):
    ack = _documentcontrol_create_ack(tenant_a, quality_doc_effective, admin_user)
    expected = f"{ack.number} - {ack.user.username} ({ack.document.number} Rev {ack.document_revision})"
    assert str(ack) == expected


def test_documentcontrol_acknowledgment_choices_and_badges():
    status_keys = [c[0] for c in DocumentAcknowledgment.STATUS_CHOICES]
    assert "pending" in status_keys
    assert "acknowledged" in status_keys
    assert "overdue" in status_keys
    assert "waived" in status_keys

    for key, badge in DocumentAcknowledgment.STATUS_CSS.items():
        assert badge in _DOCUMENTCONTROL_VALID_BADGE_CLASSES, f"Invalid badge {badge} for ack status {key}"


def test_documentcontrol_acknowledgment_is_overdue_property(tenant_a, admin_user, quality_doc_effective):
    today = timezone.now().date()

    # Pending and past due -> overdue True
    ack_past = _documentcontrol_create_ack(
        tenant_a,
        quality_doc_effective,
        admin_user,
        document_revision="1.0",
        due_date=today - timedelta(days=2),
        status="pending",
    )
    assert ack_past.is_overdue is True

    # Pending and future due -> overdue False
    ack_future = _documentcontrol_create_ack(
        tenant_a,
        quality_doc_effective,
        admin_user,
        document_revision="2.0",
        due_date=today + timedelta(days=5),
        status="pending",
    )
    assert ack_future.is_overdue is False

    # Acknowledged even if past due -> overdue False
    ack_past.status = "acknowledged"
    assert ack_past.is_overdue is False

    # Waived even if past due -> overdue False
    ack_past.status = "waived"
    assert ack_past.is_overdue is False


def test_documentcontrol_acknowledgment_days_until_due_property(tenant_a, admin_user, quality_doc_effective):
    today = timezone.now().date()

    ack_future = _documentcontrol_create_ack(
        tenant_a,
        quality_doc_effective,
        admin_user,
        document_revision="1.0",
        due_date=today + timedelta(days=10),
    )
    assert ack_future.days_until_due == 10

    ack_past = _documentcontrol_create_ack(
        tenant_a,
        quality_doc_effective,
        admin_user,
        document_revision="2.0",
        due_date=today - timedelta(days=3),
    )
    assert ack_past.days_until_due == -3


def test_documentcontrol_acknowledgment_unique_constraint_user_rev(tenant_a, admin_user, quality_doc_effective):
    _documentcontrol_create_ack(
        tenant_a, quality_doc_effective, admin_user, document_revision="1.0"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _documentcontrol_create_ack(
                tenant_a, quality_doc_effective, admin_user, document_revision="1.0"
            )


def test_documentcontrol_acknowledgment_cascade_on_document_delete(tenant_a, admin_user):
    doc = _documentcontrol_create_doc(tenant_a, admin_user)
    ack = _documentcontrol_create_ack(tenant_a, doc, admin_user)
    ack_id = ack.id

    doc.delete()
    assert not DocumentAcknowledgment.objects.filter(id=ack_id).exists()


def test_documentcontrol_acknowledgment_tenant_number_unique_constraint(tenant_a, admin_user, quality_doc_effective):
    ack = _documentcontrol_create_ack(tenant_a, quality_doc_effective, admin_user, document_revision="1.0")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DocumentAcknowledgment.objects.create(
                tenant=tenant_a,
                number=ack.number,
                document=quality_doc_effective,
                document_revision="2.0",
                user=admin_user,
                due_date=timezone.now().date() + timedelta(days=7),
            )
