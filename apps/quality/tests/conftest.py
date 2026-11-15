"""Shared fixtures for apps/quality test suite (Module 12: Quality Management System)."""
from datetime import timedelta
import pytest
from django.utils import timezone

from apps.core.models import OrgUnit, Party, PartyRole
from apps.hrm.models import EmployeeProfile
from apps.quality.models import (
    ControlledDocument,
    DocumentChangeOrder,
    ElectronicSignatureRecord,
    DocumentAcknowledgment,
)


@pytest.fixture
def quality_department(db, tenant_a):
    return OrgUnit.objects.create(
        tenant=tenant_a,
        name="Quality Assurance",
        code="QA-ACME",
        unit_type="department",
    )


@pytest.fixture
def quality_department_b(db, tenant_b):
    return OrgUnit.objects.create(
        tenant=tenant_b,
        name="Quality Assurance Globex",
        code="QA-GLOBEX",
        unit_type="department",
    )


@pytest.fixture
def quality_employee(db, tenant_a, admin_user, quality_department):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Admin QA Manager",
        party_type="individual",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role_type="employee",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_a,
        party=party,
        user=admin_user,
        department=quality_department,
        number="EMP-QA-001",
        job_title="QA Director",
    )


@pytest.fixture
def quality_employee_b(db, tenant_b, admin_b, quality_department_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Globex QA Officer",
        party_type="individual",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role_type="employee",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_b,
        party=party,
        user=admin_b,
        department=quality_department_b,
        number="EMP-QA-999",
        job_title="Globex QA Lead",
    )


@pytest.fixture
def quality_doc_draft(db, tenant_a, admin_user, quality_department):
    return ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Draft Standard Operating Procedure",
        document_type="sop",
        department=quality_department,
        owner=admin_user,
        revision="1.0",
        lifecycle_state="draft",
        classification="internal",
        description="Initial draft SOP for document control testing.",
    )


@pytest.fixture
def quality_doc_effective(db, tenant_a, admin_user, quality_department):
    now = timezone.now().date()
    return ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Effective Good Manufacturing Practice Procedure",
        document_type="sop",
        department=quality_department,
        owner=admin_user,
        revision="2.0",
        lifecycle_state="effective",
        classification="confidential",
        description="Effective GxP compliance document.",
        effective_date=now,
        next_review_date=now + timedelta(days=365),
    )


@pytest.fixture
def quality_doc_b(db, tenant_b, admin_b, quality_department_b):
    return ControlledDocument.objects.create(
        tenant=tenant_b,
        title="Globex Confidential Batch Record",
        document_type="work_instruction",
        department=quality_department_b,
        owner=admin_b,
        revision="1.0",
        lifecycle_state="effective",
        classification="restricted",
        description="Globex tenant isolated document.",
    )


@pytest.fixture
def quality_dco(db, tenant_a, admin_user, quality_doc_draft):
    return DocumentChangeOrder.objects.create(
        tenant=tenant_a,
        document=quality_doc_draft,
        title="DCO: Revise SOP for 2026 Audit Requirements",
        change_type="revision",
        priority="high",
        status="submitted",
        requested_by=admin_user,
        reason_for_change="Regulatory compliance alignment.",
        change_description="Updated section 4 and revised review intervals.",
    )


@pytest.fixture
def quality_dco_b(db, tenant_b, admin_b, quality_doc_b):
    return DocumentChangeOrder.objects.create(
        tenant=tenant_b,
        document=quality_doc_b,
        title="Globex DCO: Emergency Production Alteration",
        change_type="emergency",
        priority="critical",
        status="submitted",
        requested_by=admin_b,
        reason_for_change="Globex internal change order.",
        change_description="Globex confidential update.",
    )


@pytest.fixture
def quality_sig(db, tenant_a, admin_user, quality_doc_effective):
    sig = ElectronicSignatureRecord(
        tenant=tenant_a,
        document=quality_doc_effective,
        signer=admin_user,
        signer_name="Admin Acme",
        signer_title="QA Director",
        signature_meaning="quality_approval",
        document_revision=quality_doc_effective.revision,
        ip_address="127.0.0.1",
        comments="Approved for release per SOP-001.",
    )
    sig.verification_hash = sig.generate_hash()
    sig.save()
    return sig


@pytest.fixture
def quality_ack(db, tenant_a, admin_user, quality_employee, quality_doc_effective):
    return DocumentAcknowledgment.objects.create(
        tenant=tenant_a,
        document=quality_doc_effective,
        user=admin_user,
        employee=quality_employee,
        status="pending",
        due_date=timezone.now().date() + timedelta(days=14),
    )


@pytest.fixture
def quality_ack_b(db, tenant_b, admin_b, quality_employee_b, quality_doc_b):
    return DocumentAcknowledgment.objects.create(
        tenant=tenant_b,
        document=quality_doc_b,
        user=admin_b,
        employee=quality_employee_b,
        status="pending",
        due_date=timezone.now().date() + timedelta(days=7),
    )
