"""Model unit tests for Sub-module 13.9: Records Management & Compliance.

Tests the four core models:
- RetentionSchedule: file plan retention blueprint, regulatory frameworks, WORM modes, cutoff rules.
- RecordDeclaration: formal record declaration, hash snapshotting, legal hold status, cutoff state machine.
- DocumentLegalHold: litigation and regulatory preservation holds, custodian tracking, hold release.
- DestructionCertificate: immutable proof of disposition, legal hold verification gates, execution workflow.
"""
import calendar
import datetime
import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.documents.models import (
    DestructionCertificate,
    Document,
    DocumentLegalHold,
    DocumentVersion,
    RecordDeclaration,
    RetentionSchedule,
)


# ---------------------------------------------------------------------------
# Module-level test helpers (prefix _records_management_*)
# ---------------------------------------------------------------------------

def _records_management_create_schedule(
    tenant,
    code="RET-TEST-001",
    name="Standard Corporate Records",
    retention_period_years=7,
    retention_period_months=0,
    is_permanent=False,
    trigger_type="creation_date",
    cutoff_rule="calendar_year_end",
    disposition_action="destroy",
    compliance_framework="iso_15489",
    retention_mode="modifiable",
    is_active=True,
    department=None,
    legal_citation="ISO 15489-1:2016",
):
    """Helper to create a valid RetentionSchedule."""
    return RetentionSchedule.objects.create(
        tenant=tenant,
        code=code,
        name=name,
        retention_period_years=retention_period_years,
        retention_period_months=retention_period_months,
        is_permanent=is_permanent,
        trigger_type=trigger_type,
        cutoff_rule=cutoff_rule,
        disposition_action=disposition_action,
        compliance_framework=compliance_framework,
        retention_mode=retention_mode,
        is_active=is_active,
        department=department,
        legal_citation=legal_citation,
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
    version_hash_snapshot="",
    notes="",
):
    """Helper to create a valid RecordDeclaration."""
    return RecordDeclaration.objects.create(
        tenant=tenant,
        document=document,
        version=version,
        retention_schedule=schedule,
        declared_by=user,
        declaration_mode=declaration_mode,
        record_status=record_status,
        is_vital_record=is_vital_record,
        is_locked=is_locked,
        version_hash_snapshot=version_hash_snapshot,
        notes=notes,
    )


def _records_management_create_legal_hold(
    tenant,
    document,
    user,
    matter_name="In re Acme Litigation",
    matter_number="MAT-2026-001",
    hold_reason="litigation",
    custodian=None,
    is_active=True,
    description="Preserve all financial and compliance records",
):
    """Helper to create a valid DocumentLegalHold."""
    return DocumentLegalHold.objects.create(
        tenant=tenant,
        document=document,
        matter_name=matter_name,
        matter_number=matter_number,
        hold_reason=hold_reason,
        placed_by=user,
        custodian=custodian,
        is_active=is_active,
        description=description,
    )


def _records_management_create_destruction_cert(
    tenant,
    declaration=None,
    disposition_type="destruction",
    destruction_method="database_purge",
    status="pending_approval",
    certificate_notes="",
):
    """Helper to create a valid DestructionCertificate."""
    return DestructionCertificate.objects.create(
        tenant=tenant,
        record_declaration=declaration,
        disposition_type=disposition_type,
        destruction_method=destruction_method,
        status=status,
        certificate_notes=certificate_notes,
    )


# ---------------------------------------------------------------------------
# 1. RetentionSchedule Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_records_management_retention_schedule_defaults_and_autonumber(tenant_a):
    """Test RetentionSchedule creation, default values, auto-number generation (DRTN-), and __str__."""
    schedule = RetentionSchedule.objects.create(
        tenant=tenant_a,
        code="RET-CORP-DEF",
        name="Corporate General Governance",
    )
    assert schedule.number.startswith("DRTN-")
    assert schedule.code == "RET-CORP-DEF"
    assert schedule.name == "Corporate General Governance"
    assert schedule.retention_period_years == 7
    assert schedule.retention_period_months == 0
    assert schedule.is_permanent is False
    assert schedule.trigger_type == "creation_date"
    assert schedule.cutoff_rule == "calendar_year_end"
    assert schedule.disposition_action == "destroy"
    assert schedule.compliance_framework == "iso_15489"
    assert schedule.retention_mode == "modifiable"
    assert schedule.is_active is True
    assert schedule.legal_citation == ""
    assert schedule.description == ""
    assert str(schedule) == "RET-CORP-DEF - Corporate General Governance"


@pytest.mark.django_db
def test_records_management_retention_schedule_choices_and_badges(tenant_a):
    """Test RetentionSchedule choice fields and associated CSS badge mappings."""
    # Test all frameworks
    frameworks = ["iso_15489", "dod_5015_2", "sec_17a_4", "gdpr", "hipaa", "irs_tax", "general"]
    for fmwk in frameworks:
        sched = _records_management_create_schedule(
            tenant=tenant_a,
            code=f"RET-FMWK-{fmwk}",
            name=f"Schedule for {fmwk}",
            compliance_framework=fmwk,
        )
        assert sched.compliance_framework == fmwk
        assert isinstance(sched.framework_badge_class, str)
        assert len(sched.framework_badge_class) > 0

    # Test retention modes
    sched_mod = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-MODE-MOD",
        name="Modifiable Mode",
        retention_mode="modifiable",
    )
    assert sched_mod.retention_mode_badge_class == "badge-info"

    sched_worm = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-MODE-WORM",
        name="WORM Mode",
        retention_mode="regulatory_worm",
    )
    assert sched_worm.retention_mode_badge_class == "badge-red"

    # Test disposition actions
    actions = {
        "destroy": "badge-red",
        "archive": "badge-green",
        "review": "badge-amber",
        "transfer": "badge-info",
    }
    for action, expected_badge in actions.items():
        s = _records_management_create_schedule(
            tenant=tenant_a,
            code=f"RET-ACT-{action}",
            name=f"Action {action}",
            disposition_action=action,
        )
        assert s.disposition_badge_class == expected_badge

    # Test trigger types and cutoff rules
    trigger_types = ["creation_date", "last_modified", "declaration_date", "event_based"]
    cutoff_rules = ["immediate", "calendar_year_end", "fiscal_year_end", "event_completion"]
    for trig, rule in zip(trigger_types, cutoff_rules):
        s = _records_management_create_schedule(
            tenant=tenant_a,
            code=f"RET-TC-{trig}",
            name=f"Trigger {trig}",
            trigger_type=trig,
            cutoff_rule=rule,
        )
        assert s.trigger_type == trig
        assert s.cutoff_rule == rule

    # Test status badge
    active_sched = _records_management_create_schedule(tenant=tenant_a, code="RET-ACT-ON", is_active=True)
    inactive_sched = _records_management_create_schedule(tenant=tenant_a, code="RET-ACT-OFF", is_active=False)
    assert active_sched.status_badge_class == "badge-green"
    assert inactive_sched.status_badge_class == "badge-muted"


@pytest.mark.django_db
def test_records_management_retention_schedule_retention_summary(tenant_a):
    """Test retention_summary property across various year/month configurations."""
    # Permanent
    perm_sched = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-PERM",
        name="Permanent Legal Schedule",
        is_permanent=True,
    )
    assert perm_sched.retention_summary == "Permanent (Do Not Destroy)"

    # Years only
    yr_sched = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-5Y",
        retention_period_years=5,
        retention_period_months=0,
    )
    assert yr_sched.retention_summary == "5y"

    # Months only
    mo_sched = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-6M",
        retention_period_years=0,
        retention_period_months=6,
    )
    assert mo_sched.retention_summary == "6m"

    # Both years and months
    combo_sched = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-3Y4M",
        retention_period_years=3,
        retention_period_months=4,
    )
    assert combo_sched.retention_summary == "3y 4m"

    # Zero years and zero months
    zero_sched = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-0",
        retention_period_years=0,
        retention_period_months=0,
    )
    assert zero_sched.retention_summary == "0m"


@pytest.mark.django_db
def test_records_management_retention_schedule_uniqueness_and_tenant_isolation(tenant_a, tenant_b):
    """Test unique constraint on (tenant, code) and multi-tenant isolation."""
    _records_management_create_schedule(tenant=tenant_a, code="RET-UNIQUE-01", name="Acme Tax Schedule")

    # Duplicate code in same tenant raises IntegrityError
    with pytest.raises(IntegrityError):
        _records_management_create_schedule(tenant=tenant_a, code="RET-UNIQUE-01", name="Duplicate Acme Tax Schedule")

    # Same code in different tenant succeeds
    sched_b = _records_management_create_schedule(tenant=tenant_b, code="RET-UNIQUE-01", name="Beta Tax Schedule")
    assert sched_b.tenant == tenant_b
    assert sched_b.code == "RET-UNIQUE-01"


# ---------------------------------------------------------------------------
# 2. RecordDeclaration Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_records_management_record_declaration_defaults_and_autonumber(tenant_a, admin_user, document):
    """Test RecordDeclaration creation, auto-numbering (DRCD-), defaults, and string representation."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-SOP-01")
    decl = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
    )
    assert decl.number.startswith("DRCD-")
    assert decl.declaration_mode == "manual"
    assert decl.record_status == "active"
    assert decl.is_vital_record is False
    assert decl.vital_review_frequency_months == 12
    assert decl.is_locked is True
    assert decl.cutoff_date is None
    assert decl.cutoff_triggered_at is None
    assert decl.disposition_due_date is not None
    assert str(decl) == f"{decl.number} - {document.title}"


@pytest.mark.django_db
def test_records_management_record_declaration_version_hash_snapshot(tenant_a, admin_user, document, document_version):
    """Test version hash snapshotting behavior during record declaration save."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-HASH-01")

    # 1. Version has file_hash: snapshot copied automatically
    document_version.file_hash = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    document_version.save(update_fields=["file_hash"])

    decl_with_ver = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        version=document_version,
    )
    assert decl_with_ver.version_hash_snapshot == document_version.file_hash

    # 2. Explicit version_hash_snapshot passed: preserved without overwrite
    custom_hash = "custom-hash-0123456789abcdef"
    decl_explicit = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        version=document_version,
        version_hash_snapshot=custom_hash,
    )
    assert decl_explicit.version_hash_snapshot == custom_hash

    # 3. Version is None, but document has current_version with file_hash
    document.current_version = document_version
    decl_from_doc = RecordDeclaration.objects.create(
        tenant=tenant_a,
        document=document,
        version=None,
        retention_schedule=schedule,
        declared_by=admin_user,
    )
    assert decl_from_doc.version_hash_snapshot == document_version.file_hash


@pytest.mark.django_db
def test_records_management_record_declaration_is_under_legal_hold_property(tenant_a, admin_user, document):
    """Test is_under_legal_hold property both with queryset annotation and through ORM traversal."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-HOLD-01")
    decl = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
    )

    # Initially, no hold exists
    assert decl.is_under_legal_hold is False

    # Create an active legal hold on the document
    hold = _records_management_create_legal_hold(tenant=tenant_a, document=document, user=admin_user)
    assert decl.is_under_legal_hold is True

    # Release the legal hold
    hold.release_hold(admin_user, justification="Investigation concluded without findings")
    assert decl.is_under_legal_hold is False

    # Test annotation fast-path when has_active_hold attribute exists on model instance
    decl.has_active_hold = True
    assert decl.is_under_legal_hold is True
    decl.has_active_hold = False
    assert decl.is_under_legal_hold is False


@pytest.mark.django_db
def test_records_management_record_declaration_calculate_disposition_due_date(tenant_a, admin_user, document):
    """Test calculate_disposition_due_date across years, months, leap year boundaries, and permanent schedules."""
    # 7 years schedule
    schedule_7y = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-CALC-7Y",
        retention_period_years=7,
        retention_period_months=0,
    )
    decl_7y = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=schedule_7y, user=admin_user)

    ref_date = datetime.date(2024, 6, 15)
    calculated_7y = decl_7y.calculate_disposition_due_date(from_date=ref_date)
    assert calculated_7y == datetime.date(2031, 6, 15)

    # 18 months schedule (1 year, 6 months)
    schedule_18m = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-CALC-18M",
        retention_period_years=1,
        retention_period_months=6,
    )
    decl_18m = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=schedule_18m, user=admin_user)
    calculated_18m = decl_18m.calculate_disposition_due_date(from_date=datetime.date(2025, 3, 10))
    assert calculated_18m == datetime.date(2026, 9, 10)

    # Month-end boundary: Jan 31 + 1 month in leap year (2024 -> Feb 29)
    schedule_1m = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-CALC-1M",
        retention_period_years=0,
        retention_period_months=1,
    )
    decl_1m = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=schedule_1m, user=admin_user)
    leap_date = decl_1m.calculate_disposition_due_date(from_date=datetime.date(2024, 1, 31))
    assert leap_date == datetime.date(2024, 2, 29)

    # Month-end boundary: Jan 31 + 1 month in non-leap year (2023 -> Feb 28)
    non_leap_date = decl_1m.calculate_disposition_due_date(from_date=datetime.date(2023, 1, 31))
    assert non_leap_date == datetime.date(2023, 2, 28)

    # Permanent schedule returns None
    perm_schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-CALC-PERM", is_permanent=True)
    decl_perm = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=perm_schedule, user=admin_user)
    assert decl_perm.calculate_disposition_due_date() is None
    assert decl_perm.disposition_due_date is None


@pytest.mark.django_db
def test_records_management_record_declaration_trigger_cutoff(tenant_a, admin_user, document):
    """Test trigger_cutoff state transition to cutoff, timestamping, and recalculation of disposition due date."""
    schedule = _records_management_create_schedule(
        tenant=tenant_a,
        code="RET-CUTOFF-01",
        retention_period_years=3,
        retention_period_months=0,
    )
    decl = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        record_status="active",
    )
    assert decl.record_status == "active"
    assert decl.cutoff_date is None
    assert decl.cutoff_triggered_at is None

    decl.trigger_cutoff()
    decl.refresh_from_db()

    today = timezone.now().date()
    assert decl.record_status == "cutoff"
    assert decl.cutoff_date == today
    assert decl.cutoff_triggered_at is not None
    assert decl.disposition_due_date == datetime.date(today.year + 3, today.month, today.day)

    # Trigger cutoff on already frozen/held record preserves non-active status
    decl.record_status = "under_legal_hold"
    decl.save(update_fields=["record_status"])
    decl.trigger_cutoff()
    decl.refresh_from_db()
    assert decl.record_status == "under_legal_hold"


@pytest.mark.django_db
def test_records_management_record_declaration_badges_and_modes(tenant_a, admin_user, document):
    """Test declaration mode and status badge classes on RecordDeclaration."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-BDG-01")

    # Declaration mode badge classes
    modes = {
        "manual": "badge-info",
        "automatic_rule": "badge-slate",
        "workflow_trigger": "badge-green",
    }
    for mode, badge in modes.items():
        decl = _records_management_create_declaration(
            tenant=tenant_a,
            document=document,
            schedule=schedule,
            user=admin_user,
            declaration_mode=mode,
        )
        assert decl.declaration_mode_badge_class == badge

    # Status badge classes
    statuses = {
        "active": "badge-green",
        "cutoff": "badge-info",
        "pending_disposition": "badge-amber",
        "under_legal_hold": "badge-red",
        "disposed": "badge-muted",
    }
    for status_val, badge in statuses.items():
        decl = _records_management_create_declaration(
            tenant=tenant_a,
            document=document,
            schedule=schedule,
            user=admin_user,
            record_status=status_val,
        )
        assert decl.status_badge_class == badge

    # Legal hold overrides status badge to badge-red even if status is active
    decl_held = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        record_status="active",
    )
    _records_management_create_legal_hold(tenant=tenant_a, document=document, user=admin_user)
    assert decl_held.status_badge_class == "badge-red"


# ---------------------------------------------------------------------------
# 3. DocumentLegalHold Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_records_management_legal_hold_defaults_and_autonumber(tenant_a, admin_user, document):
    """Test DocumentLegalHold creation, auto-numbering (DHLD-), defaults, and string representation."""
    hold = DocumentLegalHold.objects.create(
        tenant=tenant_a,
        document=document,
        matter_name="DOJ Antitrust Compliance Audit",
        matter_number="MAT-DOJ-2026",
        placed_by=admin_user,
    )
    assert hold.number.startswith("DHLD-")
    assert hold.matter_name == "DOJ Antitrust Compliance Audit"
    assert hold.matter_number == "MAT-DOJ-2026"
    assert hold.hold_reason == "litigation"
    assert hold.is_active is True
    assert hold.custodian is None
    assert hold.custodian_notified is False
    assert hold.custodian_acknowledged_at is None
    assert hold.released_by is None
    assert hold.released_at is None
    assert hold.release_justification == ""
    assert str(hold) == f"{hold.number} (MAT-DOJ-2026) - {document.title}"


@pytest.mark.django_db
def test_records_management_legal_hold_custodian_tracking_and_acknowledgement(tenant_a, admin_user, member_user, document):
    """Test custodian assignment and custodian acknowledgement workflow."""
    hold = _records_management_create_legal_hold(
        tenant=tenant_a,
        document=document,
        user=admin_user,
        custodian=member_user,
    )
    assert hold.custodian == member_user
    assert hold.custodian_notified is False
    assert hold.custodian_acknowledged_at is None

    # Acknowledge hold by custodian
    hold.acknowledge_hold(member_user)
    hold.refresh_from_db()

    assert hold.custodian_notified is True
    assert hold.custodian_acknowledged_at is not None


@pytest.mark.django_db
def test_records_management_legal_hold_release(tenant_a, admin_user, member_user, document):
    """Test release_hold method releasing active preservation status."""
    hold = _records_management_create_legal_hold(
        tenant=tenant_a,
        document=document,
        user=admin_user,
        custodian=member_user,
    )
    assert hold.is_active is True
    assert hold.status_badge_class == "badge-red"

    justification = "Case dismissed with prejudice by court order."
    hold.release_hold(admin_user, justification=justification)
    hold.refresh_from_db()

    assert hold.is_active is False
    assert hold.released_by == admin_user
    assert hold.released_at is not None
    assert hold.release_justification == justification
    assert hold.status_badge_class == "badge-muted"


@pytest.mark.django_db
def test_records_management_legal_hold_reasons_and_badges(tenant_a, admin_user, document):
    """Test hold_reason choices and reason_badge_class mapping."""
    reason_badges = {
        "litigation": "badge-red",
        "regulatory_audit": "badge-amber",
        "tax_investigation": "badge-slate",
        "internal_inquiry": "badge-info",
        "ediscovery_matter": "badge-red",
    }
    for reason, expected_badge in reason_badges.items():
        hold = _records_management_create_legal_hold(
            tenant=tenant_a,
            document=document,
            user=admin_user,
            matter_number=f"MAT-{reason}",
            hold_reason=reason,
        )
        assert hold.hold_reason == reason
        assert hold.reason_badge_class == expected_badge


# ---------------------------------------------------------------------------
# 4. DestructionCertificate Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_records_management_destruction_certificate_defaults_and_autonumber(tenant_a, admin_user, document, document_version):
    """Test DestructionCertificate creation, auto-number (DDST-), default fields, snapshots, and __str__."""
    document_version.file_hash = "sha256:fedcba9876543210"
    document_version.save(update_fields=["file_hash"])

    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-FIN-DISP", name="Financial Records")
    decl = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        version=document_version,
    )

    cert = _records_management_create_destruction_cert(
        tenant=tenant_a,
        declaration=decl,
        disposition_type="destruction",
        destruction_method="database_purge",
    )
    assert cert.number.startswith("DDST-")
    assert cert.disposition_type == "destruction"
    assert cert.destruction_method == "database_purge"
    assert cert.status == "pending_approval"
    assert cert.legal_hold_verified_clear is True
    assert cert.authorized_by is None
    assert cert.authorized_at is None
    assert cert.executed_by is None
    assert cert.executed_at is None

    # Test snapshots populated on save
    assert cert.document_title_snapshot == document.title
    assert cert.document_number_snapshot == document.number
    assert cert.schedule_name_snapshot == f"{schedule.code} - {schedule.name}"
    assert cert.content_verification_hash == decl.version_hash_snapshot
    assert cert.document == document
    assert str(cert) == f"{cert.number} - {cert.document_title_snapshot}"


@pytest.mark.django_db
def test_records_management_destruction_certificate_verify_legal_holds(tenant_a, admin_user, document):
    """Test verify_legal_holds method verifying clear status or active hold obstruction."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-VERIFY-01")
    decl = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=schedule, user=admin_user)
    cert = _records_management_create_destruction_cert(tenant=tenant_a, declaration=decl)

    # 1. Clear status when no legal holds exist
    assert cert.verify_legal_holds() is True
    assert cert.legal_hold_verified_clear is True
    assert cert.hold_verification_date is not None

    # 2. Obstructed when an active legal hold is placed on document
    hold = _records_management_create_legal_hold(tenant=tenant_a, document=document, user=admin_user)
    assert cert.verify_legal_holds() is False
    assert cert.legal_hold_verified_clear is False

    # 3. Clear again after legal hold is released
    hold.release_hold(admin_user, justification="Audit completed")
    assert cert.verify_legal_holds() is True
    assert cert.legal_hold_verified_clear is True

    # 4. Certificate with no record_declaration defaults to True
    cert_no_decl = _records_management_create_destruction_cert(tenant=tenant_a, declaration=None)
    assert cert_no_decl.verify_legal_holds() is True
    assert cert_no_decl.legal_hold_verified_clear is True


@pytest.mark.django_db
def test_records_management_destruction_certificate_authorization(tenant_a, admin_user, document):
    """Test authorize method setting status, authorized_by, authorized_at, and blocking on legal hold."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-AUTH-01")
    decl = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=schedule, user=admin_user)
    cert = _records_management_create_destruction_cert(tenant=tenant_a, declaration=decl)

    # Placing an active hold prevents authorization
    hold = _records_management_create_legal_hold(tenant=tenant_a, document=document, user=admin_user)
    with pytest.raises(ValueError, match="Cannot authorize destruction: Document is currently subject to an active legal hold."):
        cert.authorize(admin_user)

    assert cert.status == "pending_approval"
    assert cert.authorized_by is None

    # Releasing hold allows authorization
    hold.release_hold(admin_user, justification="Litigation settled")
    cert.authorize(admin_user)
    cert.refresh_from_db()

    assert cert.status == "authorized"
    assert cert.authorized_by == admin_user
    assert cert.authorized_at is not None


@pytest.mark.django_db
def test_records_management_destruction_certificate_execution_success(tenant_a, admin_user, document):
    """Test execute_destruction workflow transitioning certificate, record declaration, and document status."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-EXEC-01")
    decl = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        record_status="cutoff",
    )
    document.status = "published"
    document.save(update_fields=["status"])

    cert = _records_management_create_destruction_cert(tenant=tenant_a, declaration=decl)
    cert.authorize(admin_user)

    # Execute destruction
    cert.execute_destruction(admin_user)
    cert.refresh_from_db()
    decl.refresh_from_db()
    document.refresh_from_db()

    assert cert.status == "executed"
    assert cert.executed_by == admin_user
    assert cert.executed_at is not None

    # RecordDeclaration status set to disposed
    assert decl.record_status == "disposed"

    # Document status set to archived
    assert document.status == "archived"


@pytest.mark.django_db
def test_records_management_destruction_certificate_execution_guards(tenant_a, admin_user, document):
    """Test validation guards on execute_destruction: unauthorized, already executed, and active holds."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-GUARDS-01")
    decl = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=schedule, user=admin_user)
    cert = _records_management_create_destruction_cert(tenant=tenant_a, declaration=decl)

    # 1. Cannot execute if not yet authorized
    with pytest.raises(ValueError, match="Cannot execute destruction: Certificate must be authorized first."):
        cert.execute_destruction(admin_user)

    # Authorize certificate
    cert.authorize(admin_user)

    # 2. Cannot execute if active legal hold was placed after authorization
    hold = _records_management_create_legal_hold(tenant=tenant_a, document=document, user=admin_user)
    with pytest.raises(ValueError, match="Cannot execute destruction: Document has an active legal hold."):
        cert.execute_destruction(admin_user)

    # Release hold and execute
    hold.release_hold(admin_user, justification="Dismissed")
    cert.execute_destruction(admin_user)
    assert cert.status == "executed"

    # 3. Re-execution guard raises ValueError
    with pytest.raises(ValueError, match="Destruction certificate has already been executed."):
        cert.execute_destruction(admin_user)


@pytest.mark.django_db
def test_records_management_destruction_certificate_choices_and_badges(tenant_a, admin_user, document):
    """Test status, disposition_type, and destruction_method badge classes."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-BDG-CERT")
    decl = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=schedule, user=admin_user)

    # Status badges
    statuses = {
        "pending_approval": "badge-amber",
        "authorized": "badge-info",
        "executed": "badge-green",
        "rejected": "badge-muted",
    }
    for stat, badge in statuses.items():
        cert = _records_management_create_destruction_cert(tenant=tenant_a, declaration=decl, status=stat)
        assert cert.status_badge_class == badge

    # Disposition type badges
    types = {
        "destruction": "badge-red",
        "archival_transfer": "badge-green",
        "deaccession": "badge-amber",
    }
    for dtype, badge in types.items():
        cert = _records_management_create_destruction_cert(tenant=tenant_a, declaration=decl, disposition_type=dtype)
        assert cert.disposition_badge_class == badge

    # Destruction method badges
    methods = {
        "database_purge": "badge-slate",
        "dod_5220_22m": "badge-red",
        "nist_800_88": "badge-red",
        "cryptographic_erase": "badge-info",
        "physical_crosscut": "badge-amber",
        "nara_transfer": "badge-green",
    }
    for meth, badge in methods.items():
        cert = _records_management_create_destruction_cert(tenant=tenant_a, declaration=decl, destruction_method=meth)
        assert cert.method_badge_class == badge
