"""Comprehensive tests for HRM 3.8 Offer Management sub-module.

Covers:
  - Models: Offer (OFR- prefix, auto-number per tenant, __str__, is_overdue, is_closed,
            total_compensation, clean() rejects negative amounts); OfferApproval
            (unique_together (offer, step_order), clean() step_order >= 1, __str__);
            BackgroundVerification (BGV- prefix, auto-number per tenant, is_completed, __str__);
            PreboardingItem (__str__); OfferLetterTemplate (OLTMPL- prefix, auto-number per tenant,
            unique_together (tenant, name), __str__).
  - Services: generate_offer_approval_chain (2 steps low-comp / 3 steps with executive step when
            total comp > OFFER_APPROVAL_EXEC_THRESHOLD=150000; idempotent); generate_preboarding_checklist
            (7 default lines; idempotent).
  - Forms: OfferForm (status/workflow-stamp fields NOT form fields; rejects negative base_salary;
            signed_document upload validation); BackgroundVerificationForm (result NOT a form field;
            report_file upload validation); PreboardingItemForm (uploaded_file upload validation).
  - Views / CRUD / status machine: offer create/edit/delete guarded by draft-only status;
            submit->approve(each step)->extend->accept happy path (chain built, email logged,
            application hired, pre-boarding raised); extend blocked until fully approved; decline
            requires valid decline_reason; expire only when extended AND overdue.
  - REGRESSION: reject/resubmit chain reset — a previously-rejected step must not stay stuck,
            letting the offer approve early after resubmission.
  - BGV lifecycle: initiate blocked without consent; mark_status guarded to
            BGV_MANUAL_TRANSITION_STATUSES; complete requires valid result; edit blocked once completed.
  - Pre-boarding: mark_submitted only from pending/rejected + clears stale verified_by/at; verify/reject
            stamp verified_by/at; send_invite stamps reminder_sent_at + respects do_not_contact.
  - Multi-tenant IDOR: tenant_a admin requesting tenant_b Offer/BackgroundVerification/
            OfferLetterTemplate/OfferApproval/PreboardingItem pk -> 404 (sweep of child-pk actions too).
  - Authorization: @tenant_admin_required actions -> 403 for non-admin, succeed for admin;
            @login_required-only actions work for a regular tenant user.
  - Email / do_not_contact: offer_send_email + offer_extend suppress send and don't 500.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# 3.8-specific fixtures
# ============================================================

@pytest.fixture
def job_req_a(db, tenant_a, dept_a, designation_a):
    """A draft JobRequisition for tenant_a."""
    from apps.hrm.models import JobRequisition
    return JobRequisition.objects.create(
        tenant=tenant_a,
        title="Senior Engineer",
        designation=designation_a,
        department=dept_a,
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="new_headcount",
        posting_type="external",
        priority="high",
        salary_currency="USD",
    )


@pytest.fixture
def job_req_b(db, tenant_b):
    """A draft JobRequisition for tenant_b (IDOR tests)."""
    from apps.hrm.models import JobRequisition
    return JobRequisition.objects.create(
        tenant=tenant_b,
        title="Analyst B",
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="new_headcount",
        posting_type="external",
        priority="low",
        salary_currency="USD",
    )


@pytest.fixture
def candidate_a(db, tenant_a):
    """A CandidateProfile for tenant_a."""
    from apps.core.models import Party, PartyRole
    from apps.hrm.models import CandidateProfile
    party = Party.objects.create(tenant=tenant_a, kind="person", name="Alice Candidate")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="candidate")
    return CandidateProfile.objects.create(
        tenant=tenant_a,
        party=party,
        first_name="Alice",
        last_name="Candidate",
        email="alice.candidate@acme.com",
        source="careers_page",
    )


@pytest.fixture
def candidate_b(db, tenant_b):
    """A CandidateProfile for tenant_b (IDOR tests)."""
    from apps.core.models import Party, PartyRole
    from apps.hrm.models import CandidateProfile
    party = Party.objects.create(tenant=tenant_b, kind="person", name="Bob Candidate")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="candidate")
    return CandidateProfile.objects.create(
        tenant=tenant_b,
        party=party,
        first_name="Bob",
        last_name="Candidate",
        email="bob.candidate@globex.com",
        source="careers_page",
    )


@pytest.fixture
def application_a(db, tenant_a, candidate_a, job_req_a):
    """A JobApplication for candidate_a / job_req_a in tenant_a."""
    from apps.hrm.models import JobApplication
    return JobApplication.objects.create(
        tenant=tenant_a,
        candidate=candidate_a,
        requisition=job_req_a,
        source="careers_page",
    )


@pytest.fixture
def application_b(db, tenant_b, candidate_b, job_req_b):
    """A JobApplication for tenant_b (IDOR tests)."""
    from apps.hrm.models import JobApplication
    return JobApplication.objects.create(
        tenant=tenant_b,
        candidate=candidate_b,
        requisition=job_req_b,
        source="careers_page",
    )


@pytest.fixture
def offer_email_template_a(db, tenant_a):
    """An active 'offer' CandidateEmailTemplate for tenant_a — required for _send_candidate_email
    to actually log a CandidateCommunication on offer_extend/offer_send_email (no template ->
    body is None -> nothing is sent, by design)."""
    from apps.hrm.models import CandidateEmailTemplate
    return CandidateEmailTemplate.objects.create(
        tenant=tenant_a,
        name="Offer Extended",
        template_type="offer",
        subject="Your offer from {{company_name}}",
        body_html="Dear {{candidate_name}}, congratulations on your offer for {{job_title}}.",
        is_active=True,
    )


@pytest.fixture
def offer_letter_template_a(db, tenant_a):
    """A reusable OfferLetterTemplate for tenant_a."""
    from apps.hrm.models import OfferLetterTemplate
    return OfferLetterTemplate.objects.create(
        tenant=tenant_a,
        name="Standard Offer Letter",
        is_active=True,
        body_html=("Dear {{candidate_name}}, we are pleased to offer you {{job_title}} at "
                    "{{company_name}} for {{currency}} {{base_salary}}, starting {{start_date}}."),
    )


@pytest.fixture
def offer_letter_template_b(db, tenant_b):
    """An OfferLetterTemplate for tenant_b (IDOR tests)."""
    from apps.hrm.models import OfferLetterTemplate
    return OfferLetterTemplate.objects.create(
        tenant=tenant_b,
        name="Globex Offer Letter",
        is_active=True,
        body_html="Dear {{candidate_name}}, offer for {{job_title}}.",
    )


@pytest.fixture
def draft_offer_a(db, tenant_a, application_a, offer_letter_template_a, admin_user):
    """A draft Offer for tenant_a, low comp (below the executive threshold)."""
    from apps.hrm.models import Offer
    return Offer.objects.create(
        tenant=tenant_a,
        application=application_a,
        offer_letter_template=offer_letter_template_a,
        base_salary=Decimal("90000.00"),
        currency="USD",
        bonus_amount=Decimal("5000.00"),
        signing_bonus=Decimal("2000.00"),
        start_date=datetime.date.today() + datetime.timedelta(days=30),
        expires_on=datetime.date.today() + datetime.timedelta(days=14),
        created_by=admin_user,
    )


@pytest.fixture
def offer_b(db, tenant_b, application_b, admin_b):
    """A draft Offer for tenant_b (IDOR tests)."""
    from apps.hrm.models import Offer
    return Offer.objects.create(
        tenant=tenant_b,
        application=application_b,
        base_salary=Decimal("80000.00"),
        currency="USD",
        start_date=datetime.date.today() + datetime.timedelta(days=30),
        expires_on=datetime.date.today() + datetime.timedelta(days=14),
        created_by=admin_b,
    )


@pytest.fixture
def high_comp_offer_a(db, tenant_a, application_a, admin_user):
    """A draft Offer for tenant_a with total comp > OFFER_APPROVAL_EXEC_THRESHOLD (150000)."""
    from apps.hrm.models import Offer
    return Offer.objects.create(
        tenant=tenant_a,
        application=application_a,
        base_salary=Decimal("140000.00"),
        currency="USD",
        bonus_amount=Decimal("15000.00"),
        signing_bonus=Decimal("10000.00"),
        start_date=datetime.date.today() + datetime.timedelta(days=30),
        expires_on=datetime.date.today() + datetime.timedelta(days=14),
        created_by=admin_user,
    )


@pytest.fixture
def pending_approval_offer_a(db, draft_offer_a):
    """draft_offer_a submitted into pending_approval with its default 2-step chain built."""
    from apps.hrm.services import generate_offer_approval_chain
    generate_offer_approval_chain(draft_offer_a)
    draft_offer_a.status = "pending_approval"
    draft_offer_a.save(update_fields=["status", "updated_at"])
    return draft_offer_a


@pytest.fixture
def approved_offer_a(db, pending_approval_offer_a, admin_user):
    """pending_approval_offer_a with every approval step approved -> status approved."""
    now = timezone.now()
    for step in pending_approval_offer_a.approvals.all():
        step.status = "approved"
        step.approver = admin_user
        step.decided_by = admin_user
        step.decided_at = now
        step.save()
    pending_approval_offer_a.status = "approved"
    pending_approval_offer_a.save(update_fields=["status", "updated_at"])
    return pending_approval_offer_a


@pytest.fixture
def extended_offer_a(db, approved_offer_a, admin_user):
    """approved_offer_a extended to the candidate."""
    approved_offer_a.status = "extended"
    approved_offer_a.extended_by = admin_user
    approved_offer_a.extended_at = timezone.now()
    approved_offer_a.signature_status = "sent"
    approved_offer_a.save(update_fields=["status", "extended_by", "extended_at",
                                          "signature_status", "updated_at"])
    return approved_offer_a


@pytest.fixture
def bgv_a(db, tenant_a, draft_offer_a):
    """A BackgroundVerification for draft_offer_a in tenant_a."""
    from apps.hrm.models import BackgroundVerification
    return BackgroundVerification.objects.create(
        tenant=tenant_a,
        offer=draft_offer_a,
        vendor="checkr",
        check_type="employment",
    )


@pytest.fixture
def bgv_b(db, tenant_b, offer_b):
    """A BackgroundVerification for offer_b in tenant_b (IDOR tests)."""
    from apps.hrm.models import BackgroundVerification
    return BackgroundVerification.objects.create(
        tenant=tenant_b,
        offer=offer_b,
        vendor="hireright",
        check_type="employment",
    )


@pytest.fixture
def preboarding_item_a(db, tenant_a, draft_offer_a):
    """A PreboardingItem on draft_offer_a in tenant_a."""
    from apps.hrm.models import PreboardingItem
    return PreboardingItem.objects.create(
        tenant=tenant_a,
        offer=draft_offer_a,
        document_type="id_proof",
        is_required=True,
    )


@pytest.fixture
def preboarding_item_b(db, tenant_b, offer_b):
    """A PreboardingItem on offer_b in tenant_b (IDOR tests)."""
    from apps.hrm.models import PreboardingItem
    return PreboardingItem.objects.create(
        tenant=tenant_b,
        offer=offer_b,
        document_type="id_proof",
        is_required=True,
    )


@pytest.fixture
def offer_approval_a(db, pending_approval_offer_a):
    """The first (lowest step_order) OfferApproval on pending_approval_offer_a."""
    return pending_approval_offer_a.approvals.order_by("step_order").first()


@pytest.fixture
def offer_approval_b(db, tenant_b, offer_b):
    """An OfferApproval on offer_b in tenant_b (IDOR tests)."""
    from apps.hrm.models import OfferApproval
    return OfferApproval.objects.create(
        tenant=tenant_b, offer=offer_b, step_order=1, approver_role="hiring_manager")


def _small_pdf(name="doc.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 test content", content_type="application/pdf")


def _small_exe(name="malware.exe"):
    return SimpleUploadedFile(name, b"MZ fake binary", content_type="application/octet-stream")


def _oversized_pdf(name="huge.pdf"):
    return SimpleUploadedFile(name, b"0" * (10 * 1024 * 1024 + 1), content_type="application/pdf")


# ============================================================
# Model Tests: Offer
# ============================================================

class TestOfferModel:
    """OFR- prefix, per-tenant auto-number, __str__, is_overdue, is_closed, total_compensation, clean()."""

    def test_number_prefix(self, draft_offer_a):
        assert draft_offer_a.number.startswith("OFR-")

    def test_number_first_is_00001(self, draft_offer_a):
        assert draft_offer_a.number == "OFR-00001"

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b, application_a, application_b):
        from apps.hrm.models import Offer
        o_a = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("50000"),
            start_date=datetime.date.today() + datetime.timedelta(days=10))
        o_b = Offer.objects.create(
            tenant=tenant_b, application=application_b, base_salary=Decimal("50000"),
            start_date=datetime.date.today() + datetime.timedelta(days=10))
        assert o_a.number == "OFR-00001"
        assert o_b.number == "OFR-00001"

    def test_str_includes_number_and_candidate_name(self, draft_offer_a, candidate_a):
        s = str(draft_offer_a)
        assert "OFR-00001" in s
        assert candidate_a.name in s

    def test_candidate_property(self, draft_offer_a, candidate_a):
        assert draft_offer_a.candidate == candidate_a

    def test_requisition_property(self, draft_offer_a, job_req_a):
        assert draft_offer_a.requisition == job_req_a

    def test_total_compensation_sums_base_bonus_signing(self, draft_offer_a):
        # base=90000, bonus=5000, signing=2000
        assert draft_offer_a.total_compensation == Decimal("97000.00")

    def test_total_compensation_excludes_relocation(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            relocation_assistance=Decimal("9000"),
            start_date=datetime.date.today() + datetime.timedelta(days=10))
        assert offer.total_compensation == Decimal("60000.00")

    def test_total_compensation_handles_null_bonus_and_signing(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today() + datetime.timedelta(days=10))
        assert offer.total_compensation == Decimal("60000.00")

    def test_is_closed_false_for_draft(self, draft_offer_a):
        assert draft_offer_a.is_closed is False

    def test_is_closed_true_for_accepted(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today(), status="accepted")
        assert offer.is_closed is True

    def test_is_closed_true_for_declined(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today(), status="declined")
        assert offer.is_closed is True

    def test_is_closed_true_for_rescinded(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today(), status="rescinded")
        assert offer.is_closed is True

    def test_is_closed_true_for_expired(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today(), status="expired")
        assert offer.is_closed is True

    def test_is_closed_false_for_extended(self, extended_offer_a):
        assert extended_offer_a.is_closed is False

    def test_is_overdue_false_when_no_expiry(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today())
        assert offer.is_overdue is False

    def test_is_overdue_false_when_future_expiry(self, draft_offer_a):
        # expires_on is 14 days out
        assert draft_offer_a.is_overdue is False

    def test_is_overdue_true_when_past_expiry_and_non_terminal(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today(),
            expires_on=datetime.date.today() - datetime.timedelta(days=1),
            status="extended")
        assert offer.is_overdue is True

    def test_is_overdue_false_when_past_expiry_but_terminal(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today(),
            expires_on=datetime.date.today() - datetime.timedelta(days=1),
            status="accepted")
        assert offer.is_overdue is False

    def test_unique_tenant_number(self, draft_offer_a, tenant_a, application_a):
        from apps.hrm.models import Offer
        with pytest.raises(IntegrityError):
            Offer.objects.create(
                tenant=tenant_a, number=draft_offer_a.number, application=application_a,
                base_salary=Decimal("60000"), start_date=datetime.date.today())

    def test_clean_rejects_negative_base_salary(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer(tenant=tenant_a, application=application_a, base_salary=Decimal("-1000"),
                      start_date=datetime.date.today())
        with pytest.raises(ValidationError) as exc_info:
            offer.clean()
        assert "base_salary" in exc_info.value.message_dict

    def test_clean_rejects_negative_bonus_amount(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer(tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
                      bonus_amount=Decimal("-500"), start_date=datetime.date.today())
        with pytest.raises(ValidationError) as exc_info:
            offer.clean()
        assert "bonus_amount" in exc_info.value.message_dict

    def test_clean_rejects_negative_signing_bonus(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer(tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
                      signing_bonus=Decimal("-1"), start_date=datetime.date.today())
        with pytest.raises(ValidationError) as exc_info:
            offer.clean()
        assert "signing_bonus" in exc_info.value.message_dict

    def test_clean_rejects_negative_relocation_assistance(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer(tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
                      relocation_assistance=Decimal("-1"), start_date=datetime.date.today())
        with pytest.raises(ValidationError) as exc_info:
            offer.clean()
        assert "relocation_assistance" in exc_info.value.message_dict

    def test_clean_accepts_zero_amounts(self, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer(tenant=tenant_a, application=application_a, base_salary=Decimal("0"),
                      bonus_amount=Decimal("0"), start_date=datetime.date.today())
        offer.clean()  # must not raise

    def test_approval_progress_no_steps(self, draft_offer_a):
        assert draft_offer_a.approval_progress == (0, 0)

    def test_approval_progress_partial(self, pending_approval_offer_a, admin_user):
        step = pending_approval_offer_a.approvals.order_by("step_order").first()
        step.status = "approved"
        step.decided_by = admin_user
        step.decided_at = timezone.now()
        step.save()
        assert pending_approval_offer_a.approval_progress == (1, 2)

    def test_current_approval_step_returns_lowest_pending(self, pending_approval_offer_a):
        step = pending_approval_offer_a.current_approval_step
        assert step is not None
        assert step.step_order == 1

    def test_current_approval_step_none_when_fully_decided(self, approved_offer_a):
        assert approved_offer_a.current_approval_step is None


# ============================================================
# Model Tests: OfferApproval
# ============================================================

class TestOfferApprovalModel:
    """unique_together (offer, step_order); clean() rejects step_order < 1; __str__."""

    def test_str_includes_step_and_status(self, offer_approval_a):
        s = str(offer_approval_a)
        assert "Step 1" in s
        assert "Pending" in s

    def test_unique_offer_step_order_raises(self, tenant_a, pending_approval_offer_a):
        from apps.hrm.models import OfferApproval
        with pytest.raises(IntegrityError):
            OfferApproval.objects.create(
                tenant=tenant_a, offer=pending_approval_offer_a, step_order=1,
                approver_role="hr")

    def test_same_step_order_different_offer_ok(self, tenant_a, draft_offer_a, application_a):
        from apps.hrm.models import Offer, OfferApproval
        offer2 = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("70000"),
            start_date=datetime.date.today())
        step = OfferApproval.objects.create(
            tenant=tenant_a, offer=offer2, step_order=1, approver_role="hr")
        assert step.pk is not None

    def test_clean_rejects_step_order_zero(self, tenant_a, draft_offer_a):
        from apps.hrm.models import OfferApproval
        step = OfferApproval(tenant=tenant_a, offer=draft_offer_a, step_order=0, approver_role="hr")
        with pytest.raises(ValidationError) as exc_info:
            step.clean()
        assert "step_order" in exc_info.value.message_dict

    def test_clean_accepts_step_order_one(self, tenant_a, draft_offer_a):
        from apps.hrm.models import OfferApproval
        step = OfferApproval(tenant=tenant_a, offer=draft_offer_a, step_order=1, approver_role="hr")
        step.clean()  # must not raise


# ============================================================
# Model Tests: BackgroundVerification
# ============================================================

class TestBackgroundVerificationModel:
    """BGV- prefix, per-tenant auto-number, is_completed, __str__."""

    def test_number_prefix(self, bgv_a):
        assert bgv_a.number.startswith("BGV-")

    def test_number_first_is_00001(self, bgv_a):
        assert bgv_a.number == "BGV-00001"

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b, draft_offer_a, offer_b):
        from apps.hrm.models import BackgroundVerification
        b_a = BackgroundVerification.objects.create(tenant=tenant_a, offer=draft_offer_a)
        b_b = BackgroundVerification.objects.create(tenant=tenant_b, offer=offer_b)
        assert b_a.number == "BGV-00001"
        assert b_b.number == "BGV-00001"

    def test_str_includes_number(self, bgv_a):
        assert "BGV-00001" in str(bgv_a)

    def test_is_completed_false_by_default(self, bgv_a):
        assert bgv_a.is_completed is False

    def test_is_completed_true_when_completed(self, bgv_a):
        bgv_a.status = "completed"
        bgv_a.save(update_fields=["status", "updated_at"])
        assert bgv_a.is_completed is True

    def test_default_status_not_started(self, bgv_a):
        assert bgv_a.status == "not_started"

    def test_default_consent_given_false(self, bgv_a):
        assert bgv_a.consent_given is False


# ============================================================
# Model Tests: PreboardingItem
# ============================================================

class TestPreboardingItemModel:
    """__str__, default status pending."""

    def test_str_includes_document_type_and_status(self, preboarding_item_a):
        s = str(preboarding_item_a)
        assert "Pending" in s

    def test_default_status_pending(self, preboarding_item_a):
        assert preboarding_item_a.status == "pending"

    def test_default_is_required_true(self, preboarding_item_a):
        assert preboarding_item_a.is_required is True


# ============================================================
# Model Tests: OfferLetterTemplate
# ============================================================

class TestOfferLetterTemplateModel:
    """OLTMPL- prefix, per-tenant auto-number, unique_together (tenant, name), __str__."""

    def test_number_prefix(self, offer_letter_template_a):
        assert offer_letter_template_a.number.startswith("OLTMPL-")

    def test_number_first_is_00001(self, offer_letter_template_a):
        assert offer_letter_template_a.number == "OLTMPL-00001"

    def test_str_includes_number_and_name(self, offer_letter_template_a):
        s = str(offer_letter_template_a)
        assert "OLTMPL-00001" in s
        assert "Standard Offer Letter" in s

    def test_unique_tenant_name_raises(self, tenant_a, offer_letter_template_a):
        from apps.hrm.models import OfferLetterTemplate
        with pytest.raises(IntegrityError):
            OfferLetterTemplate.objects.create(
                tenant=tenant_a, name="Standard Offer Letter", body_html="Duplicate name")

    def test_same_name_different_tenant_ok(self, tenant_b, offer_letter_template_a):
        from apps.hrm.models import OfferLetterTemplate
        tmpl = OfferLetterTemplate.objects.create(
            tenant=tenant_b, name="Standard Offer Letter", body_html="Different tenant, same name")
        assert tmpl.pk is not None

    def test_default_is_active_true(self, offer_letter_template_a):
        assert offer_letter_template_a.is_active is True


# ============================================================
# Service Tests: generate_offer_approval_chain
# ============================================================

class TestGenerateOfferApprovalChain:
    """2 steps for low comp; 3 (with executive) when comp > 150000; idempotent."""

    def test_low_comp_builds_two_steps(self, draft_offer_a):
        from apps.hrm.services import generate_offer_approval_chain
        steps = generate_offer_approval_chain(draft_offer_a)
        assert len(steps) == 2
        roles = [s.approver_role for s in steps]
        assert roles == ["hiring_manager", "hr"]

    def test_high_comp_builds_three_steps_with_executive(self, high_comp_offer_a):
        from apps.hrm.services import generate_offer_approval_chain
        assert high_comp_offer_a.total_compensation == Decimal("165000.00")
        steps = generate_offer_approval_chain(high_comp_offer_a)
        assert len(steps) == 3
        roles = [s.approver_role for s in steps]
        assert roles == ["hiring_manager", "hr", "executive"]

    def test_executive_step_is_last_and_step_order_3(self, high_comp_offer_a):
        from apps.hrm.services import generate_offer_approval_chain
        steps = generate_offer_approval_chain(high_comp_offer_a)
        exec_step = steps[-1]
        assert exec_step.approver_role == "executive"
        assert exec_step.step_order == 3

    def test_comp_exactly_at_threshold_does_not_add_executive(self, tenant_a, application_a):
        """total_compensation == threshold (not strictly greater) must NOT add the executive step."""
        from apps.hrm.models import Offer
        from apps.hrm.services import OFFER_APPROVAL_EXEC_THRESHOLD, generate_offer_approval_chain
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=OFFER_APPROVAL_EXEC_THRESHOLD,
            start_date=datetime.date.today())
        steps = generate_offer_approval_chain(offer)
        assert len(steps) == 2

    def test_idempotent_second_call_adds_nothing(self, draft_offer_a):
        from apps.hrm.models import OfferApproval
        from apps.hrm.services import generate_offer_approval_chain
        generate_offer_approval_chain(draft_offer_a)
        count_after_first = OfferApproval.objects.filter(offer=draft_offer_a).count()
        generate_offer_approval_chain(draft_offer_a)
        count_after_second = OfferApproval.objects.filter(offer=draft_offer_a).count()
        assert count_after_first == count_after_second == 2

    def test_idempotent_preserves_existing_custom_chain(self, tenant_a, draft_offer_a):
        """If a tenant added a custom step before calling the service, it's returned untouched."""
        from apps.hrm.models import OfferApproval
        from apps.hrm.services import generate_offer_approval_chain
        OfferApproval.objects.create(
            tenant=tenant_a, offer=draft_offer_a, step_order=1, approver_role="hr")
        steps = generate_offer_approval_chain(draft_offer_a)
        assert len(steps) == 1
        assert steps[0].approver_role == "hr"

    def test_all_steps_default_pending(self, draft_offer_a):
        from apps.hrm.services import generate_offer_approval_chain
        steps = generate_offer_approval_chain(draft_offer_a)
        assert all(s.status == "pending" for s in steps)

    def test_all_steps_tenant_scoped(self, draft_offer_a, tenant_a):
        from apps.hrm.services import generate_offer_approval_chain
        steps = generate_offer_approval_chain(draft_offer_a)
        assert all(s.tenant_id == tenant_a.id for s in steps)


# ============================================================
# Service Tests: generate_preboarding_checklist
# ============================================================

class TestGeneratePreboardingChecklist:
    """7 default lines; idempotent (keyed on document_type)."""

    def test_builds_seven_lines(self, draft_offer_a):
        from apps.hrm.services import generate_preboarding_checklist
        created = generate_preboarding_checklist(draft_offer_a)
        assert created == 7
        assert draft_offer_a.preboarding_items.count() == 7

    def test_expected_document_types(self, draft_offer_a):
        from apps.hrm.services import generate_preboarding_checklist
        generate_preboarding_checklist(draft_offer_a)
        doc_types = set(draft_offer_a.preboarding_items.values_list("document_type", flat=True))
        assert doc_types == {"id_proof", "address_proof", "tax_form", "bank_details",
                              "nda", "background_check_consent", "education_certificate"}

    def test_education_certificate_not_required(self, draft_offer_a):
        from apps.hrm.services import generate_preboarding_checklist
        generate_preboarding_checklist(draft_offer_a)
        item = draft_offer_a.preboarding_items.get(document_type="education_certificate")
        assert item.is_required is False

    def test_id_proof_is_required(self, draft_offer_a):
        from apps.hrm.services import generate_preboarding_checklist
        generate_preboarding_checklist(draft_offer_a)
        item = draft_offer_a.preboarding_items.get(document_type="id_proof")
        assert item.is_required is True

    def test_idempotent_second_call_adds_nothing(self, draft_offer_a):
        from apps.hrm.services import generate_preboarding_checklist
        generate_preboarding_checklist(draft_offer_a)
        second_created = generate_preboarding_checklist(draft_offer_a)
        assert second_created == 0
        assert draft_offer_a.preboarding_items.count() == 7

    def test_idempotent_preserves_existing_line_status(self, draft_offer_a):
        """A pre-existing document_type line (e.g. already verified) must not be duplicated/reset."""
        from apps.hrm.models import PreboardingItem
        from apps.hrm.services import generate_preboarding_checklist
        existing = PreboardingItem.objects.create(
            tenant=draft_offer_a.tenant, offer=draft_offer_a, document_type="id_proof",
            is_required=True, status="verified")
        generate_preboarding_checklist(draft_offer_a)
        existing.refresh_from_db()
        assert existing.status == "verified"
        assert PreboardingItem.objects.filter(offer=draft_offer_a, document_type="id_proof").count() == 1


# ============================================================
# Form Tests: OfferForm
# ============================================================

class TestOfferForm:
    """status/workflow-stamp fields NOT form fields; rejects negative base_salary; upload validation."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import OfferForm
        assert "status" not in OfferForm.Meta.fields

    def test_extended_by_not_a_form_field(self):
        from apps.hrm.forms import OfferForm
        assert "extended_by" not in OfferForm.Meta.fields

    def test_extended_at_not_a_form_field(self):
        from apps.hrm.forms import OfferForm
        assert "extended_at" not in OfferForm.Meta.fields

    def test_accepted_at_not_a_form_field(self):
        from apps.hrm.forms import OfferForm
        assert "accepted_at" not in OfferForm.Meta.fields

    def test_declined_at_not_a_form_field(self):
        from apps.hrm.forms import OfferForm
        assert "declined_at" not in OfferForm.Meta.fields

    def test_rescinded_at_not_a_form_field(self):
        from apps.hrm.forms import OfferForm
        assert "rescinded_at" not in OfferForm.Meta.fields

    def test_created_by_not_a_form_field(self):
        from apps.hrm.forms import OfferForm
        assert "created_by" not in OfferForm.Meta.fields

    def test_number_not_a_form_field(self):
        from apps.hrm.forms import OfferForm
        assert "number" not in OfferForm.Meta.fields

    def test_application_queryset_tenant_scoped(self, tenant_a, application_a, application_b):
        from apps.hrm.forms import OfferForm
        form = OfferForm(tenant=tenant_a)
        pks = list(form.fields["application"].queryset.values_list("pk", flat=True))
        assert application_a.pk in pks
        assert application_b.pk not in pks

    def test_currency_optional_on_form(self, tenant_a):
        from apps.hrm.forms import OfferForm
        form = OfferForm(tenant=tenant_a)
        assert form.fields["currency"].required is False

    def test_valid_form(self, tenant_a, application_a):
        from apps.hrm.forms import OfferForm
        form = OfferForm({
            "application": application_a.pk,
            "offer_letter_template": "",
            "base_salary": "90000.00",
            "currency": "USD",
            "bonus_amount": "",
            "bonus_terms": "",
            "signing_bonus": "",
            "equity_terms": "",
            "relocation_assistance": "",
            "benefits_summary": "",
            "start_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
            "expires_on": "",
            "decline_reason": "",
            "decline_notes": "",
            "signature_status": "not_sent",
            "notes": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_negative_base_salary_rejected(self, tenant_a, application_a):
        from apps.hrm.forms import OfferForm
        form = OfferForm({
            "application": application_a.pk,
            "base_salary": "-1000",
            "currency": "USD",
            "start_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
            "signature_status": "not_sent",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "base_salary" in form.errors

    def test_negative_bonus_amount_rejected(self, tenant_a, application_a):
        from apps.hrm.forms import OfferForm
        form = OfferForm({
            "application": application_a.pk,
            "base_salary": "90000",
            "bonus_amount": "-500",
            "currency": "USD",
            "start_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
            "signature_status": "not_sent",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "bonus_amount" in form.errors

    def test_signed_document_rejects_disallowed_extension(self, tenant_a, application_a):
        from apps.hrm.forms import OfferForm
        form = OfferForm({
            "application": application_a.pk,
            "base_salary": "90000",
            "currency": "USD",
            "start_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
            "signature_status": "not_sent",
        }, {"signed_document": _small_exe()}, tenant=tenant_a)
        assert not form.is_valid()
        assert "signed_document" in form.errors

    def test_signed_document_rejects_oversized_file(self, tenant_a, application_a):
        from apps.hrm.forms import OfferForm
        form = OfferForm({
            "application": application_a.pk,
            "base_salary": "90000",
            "currency": "USD",
            "start_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
            "signature_status": "not_sent",
        }, {"signed_document": _oversized_pdf()}, tenant=tenant_a)
        assert not form.is_valid()
        assert "signed_document" in form.errors

    def test_signed_document_accepts_valid_pdf(self, tenant_a, application_a):
        from apps.hrm.forms import OfferForm
        form = OfferForm({
            "application": application_a.pk,
            "base_salary": "90000",
            "currency": "USD",
            "start_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
            "signature_status": "not_sent",
        }, {"signed_document": _small_pdf()}, tenant=tenant_a)
        assert form.is_valid(), form.errors


# ============================================================
# Form Tests: BackgroundVerificationForm
# ============================================================

class TestBackgroundVerificationForm:
    """result NOT a form field; report_file upload validation."""

    def test_result_not_a_form_field(self):
        from apps.hrm.forms import BackgroundVerificationForm
        assert "result" not in BackgroundVerificationForm.Meta.fields

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import BackgroundVerificationForm
        assert "status" not in BackgroundVerificationForm.Meta.fields

    def test_initiated_at_not_a_form_field(self):
        from apps.hrm.forms import BackgroundVerificationForm
        assert "initiated_at" not in BackgroundVerificationForm.Meta.fields

    def test_completed_at_not_a_form_field(self):
        from apps.hrm.forms import BackgroundVerificationForm
        assert "completed_at" not in BackgroundVerificationForm.Meta.fields

    def test_offer_queryset_tenant_scoped(self, tenant_a, draft_offer_a, offer_b):
        from apps.hrm.forms import BackgroundVerificationForm
        form = BackgroundVerificationForm(tenant=tenant_a)
        pks = list(form.fields["offer"].queryset.values_list("pk", flat=True))
        assert draft_offer_a.pk in pks
        assert offer_b.pk not in pks

    def test_valid_form(self, tenant_a, draft_offer_a):
        from apps.hrm.forms import BackgroundVerificationForm
        form = BackgroundVerificationForm({
            "offer": draft_offer_a.pk,
            "vendor": "checkr",
            "check_type": "employment",
            "consent_given": False,
            "notes": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_report_file_rejects_disallowed_extension(self, tenant_a, draft_offer_a):
        from apps.hrm.forms import BackgroundVerificationForm
        form = BackgroundVerificationForm({
            "offer": draft_offer_a.pk,
            "vendor": "checkr",
            "check_type": "employment",
            "consent_given": False,
        }, {"report_file": _small_exe()}, tenant=tenant_a)
        assert not form.is_valid()
        assert "report_file" in form.errors

    def test_report_file_rejects_oversized_file(self, tenant_a, draft_offer_a):
        from apps.hrm.forms import BackgroundVerificationForm
        form = BackgroundVerificationForm({
            "offer": draft_offer_a.pk,
            "vendor": "checkr",
            "check_type": "employment",
            "consent_given": False,
        }, {"report_file": _oversized_pdf()}, tenant=tenant_a)
        assert not form.is_valid()
        assert "report_file" in form.errors

    def test_report_file_accepts_valid_pdf(self, tenant_a, draft_offer_a):
        from apps.hrm.forms import BackgroundVerificationForm
        form = BackgroundVerificationForm({
            "offer": draft_offer_a.pk,
            "vendor": "checkr",
            "check_type": "employment",
            "consent_given": False,
        }, {"report_file": _small_pdf()}, tenant=tenant_a)
        assert form.is_valid(), form.errors


# ============================================================
# Form Tests: PreboardingItemForm
# ============================================================

class TestPreboardingItemForm:
    """uploaded_file upload validation; status/timestamps NOT form fields."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import PreboardingItemForm
        assert "status" not in PreboardingItemForm.Meta.fields

    def test_submitted_at_not_a_form_field(self):
        from apps.hrm.forms import PreboardingItemForm
        assert "submitted_at" not in PreboardingItemForm.Meta.fields

    def test_verified_by_not_a_form_field(self):
        from apps.hrm.forms import PreboardingItemForm
        assert "verified_by" not in PreboardingItemForm.Meta.fields

    def test_reminder_sent_at_not_a_form_field(self):
        from apps.hrm.forms import PreboardingItemForm
        assert "reminder_sent_at" not in PreboardingItemForm.Meta.fields

    def test_offer_not_a_form_field(self):
        """`offer` is set in the view, not exposed on the inline-add form."""
        from apps.hrm.forms import PreboardingItemForm
        assert "offer" not in PreboardingItemForm.Meta.fields

    def test_valid_form(self, tenant_a):
        from apps.hrm.forms import PreboardingItemForm
        form = PreboardingItemForm({
            "document_type": "id_proof", "is_required": True, "notes": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_uploaded_file_rejects_disallowed_extension(self, tenant_a):
        from apps.hrm.forms import PreboardingItemForm
        form = PreboardingItemForm({
            "document_type": "id_proof", "is_required": True, "notes": "",
        }, {"uploaded_file": _small_exe()}, tenant=tenant_a)
        assert not form.is_valid()
        assert "uploaded_file" in form.errors

    def test_uploaded_file_rejects_oversized_file(self, tenant_a):
        from apps.hrm.forms import PreboardingItemForm
        form = PreboardingItemForm({
            "document_type": "id_proof", "is_required": True, "notes": "",
        }, {"uploaded_file": _oversized_pdf()}, tenant=tenant_a)
        assert not form.is_valid()
        assert "uploaded_file" in form.errors

    def test_uploaded_file_accepts_valid_pdf(self, tenant_a):
        from apps.hrm.forms import PreboardingItemForm
        form = PreboardingItemForm({
            "document_type": "id_proof", "is_required": True, "notes": "",
        }, {"uploaded_file": _small_pdf()}, tenant=tenant_a)
        assert form.is_valid(), form.errors


# ============================================================
# View Tests: Offer CRUD
# ============================================================

class TestOfferListView:
    def test_list_200(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_list"))
        assert resp.status_code == 200

    def test_list_contains_tenant_a_offer(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_list"))
        assert draft_offer_a.number.encode() in resp.content

    def test_list_excludes_tenant_b_offer(self, client_a, draft_offer_a, offer_b):
        resp = client_a.get(reverse("hrm:offer_list"))
        assert offer_b.candidate.name.encode() not in resp.content

    def test_anon_redirects(self):
        from django.test import Client
        c = Client()
        resp = c.get(reverse("hrm:offer_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_list_query_count(self, client_a, draft_offer_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:offer_list"))


class TestOfferCreateView:
    def test_post_creates_offer(self, client_a, tenant_a, application_a):
        from apps.hrm.models import Offer
        resp = client_a.post(reverse("hrm:offer_create"), {
            "application": application_a.pk,
            "base_salary": "85000.00",
            "currency": "USD",
            "start_date": (datetime.date.today() + datetime.timedelta(days=20)).isoformat(),
            "signature_status": "not_sent",
        })
        assert resp.status_code == 302
        assert Offer.objects.filter(tenant=tenant_a, base_salary=Decimal("85000.00")).exists()

    def test_post_sets_created_by(self, client_a, tenant_a, application_a, admin_user):
        from apps.hrm.models import Offer
        client_a.post(reverse("hrm:offer_create"), {
            "application": application_a.pk,
            "base_salary": "77000.00",
            "currency": "USD",
            "start_date": (datetime.date.today() + datetime.timedelta(days=20)).isoformat(),
            "signature_status": "not_sent",
        })
        offer = Offer.objects.filter(tenant=tenant_a, base_salary=Decimal("77000.00")).first()
        assert offer.created_by == admin_user

    def test_post_defaults_currency_from_requisition_when_blank(self, client_a, tenant_a, application_a):
        """Leaving currency blank must default from the requisition's salary_currency (view-level)."""
        from apps.hrm.models import Offer
        application_a.requisition.salary_currency = "EUR"
        application_a.requisition.save(update_fields=["salary_currency", "updated_at"])
        client_a.post(reverse("hrm:offer_create"), {
            "application": application_a.pk,
            "base_salary": "66000.00",
            "currency": "",
            "start_date": (datetime.date.today() + datetime.timedelta(days=20)).isoformat(),
            "signature_status": "not_sent",
        })
        offer = Offer.objects.filter(tenant=tenant_a, base_salary=Decimal("66000.00")).first()
        assert offer is not None
        assert offer.currency == "EUR"

    def test_post_redirects_to_detail(self, client_a, tenant_a, application_a):
        from apps.hrm.models import Offer
        resp = client_a.post(reverse("hrm:offer_create"), {
            "application": application_a.pk,
            "base_salary": "72000.00",
            "currency": "USD",
            "start_date": (datetime.date.today() + datetime.timedelta(days=20)).isoformat(),
            "signature_status": "not_sent",
        })
        offer = Offer.objects.filter(tenant=tenant_a, base_salary=Decimal("72000.00")).first()
        assert reverse("hrm:offer_detail", args=[offer.pk]) in resp["Location"]


class TestOfferDetailView:
    def test_detail_200(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_detail", args=[draft_offer_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_detail", args=[draft_offer_a.pk]))
        assert resp.context["obj"] == draft_offer_a

    def test_detail_context_has_approvals(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_detail", args=[draft_offer_a.pk]))
        assert "approvals" in resp.context

    def test_detail_context_has_background_checks(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_detail", args=[draft_offer_a.pk]))
        assert "background_checks" in resp.context

    def test_detail_context_has_preboarding_items(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_detail", args=[draft_offer_a.pk]))
        assert "preboarding_items" in resp.context

    def test_detail_context_has_all_approved_flag(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_detail", args=[draft_offer_a.pk]))
        assert "all_approved" in resp.context

    def test_detail_idor_404(self, client_a, offer_b):
        resp = client_a.get(reverse("hrm:offer_detail", args=[offer_b.pk]))
        assert resp.status_code == 404


class TestOfferEditView:
    """Editable only while draft."""

    def test_edit_get_200_for_draft(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_edit", args=[draft_offer_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_base_salary_for_draft(self, client_a, draft_offer_a, application_a):
        resp = client_a.post(reverse("hrm:offer_edit", args=[draft_offer_a.pk]), {
            "application": application_a.pk,
            "base_salary": "99000.00",
            "currency": "USD",
            "start_date": draft_offer_a.start_date.isoformat(),
            "signature_status": "not_sent",
        })
        assert resp.status_code == 302
        draft_offer_a.refresh_from_db()
        assert draft_offer_a.base_salary == Decimal("99000.00")

    def test_edit_blocked_for_pending_approval(self, client_a, pending_approval_offer_a, application_a):
        resp = client_a.post(reverse("hrm:offer_edit", args=[pending_approval_offer_a.pk]), {
            "application": application_a.pk,
            "base_salary": "1000.00",
            "currency": "USD",
            "start_date": pending_approval_offer_a.start_date.isoformat(),
            "signature_status": "not_sent",
        })
        assert resp.status_code == 302
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.base_salary != Decimal("1000.00")

    def test_edit_blocked_for_approved(self, client_a, approved_offer_a, application_a):
        original_salary = approved_offer_a.base_salary
        resp = client_a.post(reverse("hrm:offer_edit", args=[approved_offer_a.pk]), {
            "application": application_a.pk,
            "base_salary": "1000.00",
            "currency": "USD",
            "start_date": approved_offer_a.start_date.isoformat(),
            "signature_status": "not_sent",
        })
        assert resp.status_code == 302
        approved_offer_a.refresh_from_db()
        assert approved_offer_a.base_salary == original_salary

    def test_edit_get_blocked_for_approved_redirects(self, client_a, approved_offer_a):
        resp = client_a.get(reverse("hrm:offer_edit", args=[approved_offer_a.pk]))
        assert resp.status_code == 302
        assert reverse("hrm:offer_detail", args=[approved_offer_a.pk]) in resp["Location"]


class TestOfferDeleteView:
    """Admin-only + draft-only."""

    def test_admin_delete_draft_succeeds(self, client_a, draft_offer_a):
        from apps.hrm.models import Offer
        pk = draft_offer_a.pk
        resp = client_a.post(reverse("hrm:offer_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Offer.objects.filter(pk=pk).exists()

    def test_nonadmin_delete_403(self, member_client, draft_offer_a):
        from apps.hrm.models import Offer
        resp = member_client.post(reverse("hrm:offer_delete", args=[draft_offer_a.pk]))
        assert resp.status_code == 403
        assert Offer.objects.filter(pk=draft_offer_a.pk).exists()

    def test_delete_blocked_for_pending_approval(self, client_a, pending_approval_offer_a):
        from apps.hrm.models import Offer
        resp = client_a.post(reverse("hrm:offer_delete", args=[pending_approval_offer_a.pk]))
        assert resp.status_code == 302
        assert Offer.objects.filter(pk=pending_approval_offer_a.pk).exists()

    def test_delete_get_blocked(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_delete", args=[draft_offer_a.pk]))
        assert resp.status_code == 405


# ============================================================
# View Tests: Offer status machine happy path
# ============================================================

class TestOfferStatusMachineHappyPath:
    """create -> submit (chain built) -> approve each step -> extend (email logged) -> accept
    (application hired, pre-boarding raised)."""

    def test_submit_builds_approval_chain(self, client_a, draft_offer_a):
        resp = client_a.post(reverse("hrm:offer_submit", args=[draft_offer_a.pk]))
        assert resp.status_code == 302
        draft_offer_a.refresh_from_db()
        assert draft_offer_a.status == "pending_approval"
        assert draft_offer_a.approvals.count() == 2

    def test_submit_only_allowed_from_draft(self, client_a, pending_approval_offer_a):
        resp = client_a.post(reverse("hrm:offer_submit", args=[pending_approval_offer_a.pk]))
        assert resp.status_code == 302
        # still pending_approval, not re-submitted / errored into another state
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "pending_approval"

    def test_approve_each_step_then_offer_approved(self, client_a, pending_approval_offer_a):
        client_a.post(reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "pending_approval"  # 1 of 2 approved
        client_a.post(reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "approved"  # both approved

    def test_extend_blocked_until_all_steps_approved(self, client_a, pending_approval_offer_a):
        # Approve only the first of 2 steps.
        client_a.post(reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        resp = client_a.post(reverse("hrm:offer_extend", args=[pending_approval_offer_a.pk]))
        assert resp.status_code == 302
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "pending_approval"  # not extended

    def test_extend_succeeds_when_approved(self, client_a, approved_offer_a):
        resp = client_a.post(reverse("hrm:offer_extend", args=[approved_offer_a.pk]))
        assert resp.status_code == 302
        approved_offer_a.refresh_from_db()
        assert approved_offer_a.status == "extended"
        assert approved_offer_a.extended_at is not None
        assert approved_offer_a.extended_by is not None

    def test_extend_logs_offer_email(self, client_a, tenant_a, approved_offer_a, offer_email_template_a):
        from apps.hrm.models import CandidateCommunication
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        client_a.post(reverse("hrm:offer_extend", args=[approved_offer_a.pk]))
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1

    def test_accept_marks_application_hired(self, client_a, extended_offer_a):
        resp = client_a.post(reverse("hrm:offer_accept", args=[extended_offer_a.pk]))
        assert resp.status_code == 302
        extended_offer_a.refresh_from_db()
        assert extended_offer_a.status == "accepted"
        extended_offer_a.application.refresh_from_db()
        assert extended_offer_a.application.stage == "hired"
        assert extended_offer_a.application.hired_on is not None

    def test_accept_raises_preboarding_checklist(self, client_a, extended_offer_a):
        client_a.post(reverse("hrm:offer_accept", args=[extended_offer_a.pk]))
        assert extended_offer_a.preboarding_items.count() == 7

    def test_accept_only_allowed_from_extended(self, client_a, approved_offer_a):
        resp = client_a.post(reverse("hrm:offer_accept", args=[approved_offer_a.pk]))
        assert resp.status_code == 302
        approved_offer_a.refresh_from_db()
        assert approved_offer_a.status == "approved"  # unchanged


class TestOfferDecline:
    def test_decline_requires_valid_reason(self, client_a, extended_offer_a):
        resp = client_a.post(reverse("hrm:offer_decline", args=[extended_offer_a.pk]), {
            "decline_reason": "not_a_real_choice",
        })
        assert resp.status_code == 302
        extended_offer_a.refresh_from_db()
        assert extended_offer_a.status == "extended"  # unchanged, invalid reason rejected

    def test_decline_with_valid_reason_succeeds(self, client_a, extended_offer_a):
        resp = client_a.post(reverse("hrm:offer_decline", args=[extended_offer_a.pk]), {
            "decline_reason": "competing_offer",
            "decline_notes": "Took another role.",
        })
        assert resp.status_code == 302
        extended_offer_a.refresh_from_db()
        assert extended_offer_a.status == "declined"
        assert extended_offer_a.decline_reason == "competing_offer"
        assert extended_offer_a.declined_at is not None

    def test_decline_only_allowed_from_extended(self, client_a, approved_offer_a):
        resp = client_a.post(reverse("hrm:offer_decline", args=[approved_offer_a.pk]), {
            "decline_reason": "salary",
        })
        assert resp.status_code == 302
        approved_offer_a.refresh_from_db()
        assert approved_offer_a.status == "approved"  # unchanged


class TestOfferRescind:
    def test_rescind_from_extended_succeeds(self, client_a, extended_offer_a):
        resp = client_a.post(reverse("hrm:offer_rescind", args=[extended_offer_a.pk]))
        assert resp.status_code == 302
        extended_offer_a.refresh_from_db()
        assert extended_offer_a.status == "rescinded"
        assert extended_offer_a.rescinded_at is not None

    def test_rescind_from_draft_blocked(self, client_a, draft_offer_a):
        resp = client_a.post(reverse("hrm:offer_rescind", args=[draft_offer_a.pk]))
        assert resp.status_code == 302
        draft_offer_a.refresh_from_db()
        assert draft_offer_a.status == "draft"  # unchanged

    def test_rescind_nonadmin_403(self, member_client, extended_offer_a):
        resp = member_client.post(reverse("hrm:offer_rescind", args=[extended_offer_a.pk]))
        assert resp.status_code == 403


class TestOfferExpire:
    """Only when extended AND overdue."""

    def test_expire_blocked_when_not_overdue(self, client_a, extended_offer_a):
        resp = client_a.post(reverse("hrm:offer_expire", args=[extended_offer_a.pk]))
        assert resp.status_code == 302
        extended_offer_a.refresh_from_db()
        assert extended_offer_a.status == "extended"  # not overdue yet, unchanged

    def test_expire_succeeds_when_overdue(self, client_a, extended_offer_a):
        extended_offer_a.expires_on = datetime.date.today() - datetime.timedelta(days=1)
        extended_offer_a.save(update_fields=["expires_on", "updated_at"])
        resp = client_a.post(reverse("hrm:offer_expire", args=[extended_offer_a.pk]))
        assert resp.status_code == 302
        extended_offer_a.refresh_from_db()
        assert extended_offer_a.status == "expired"

    def test_expire_blocked_when_not_extended(self, client_a, approved_offer_a):
        approved_offer_a.expires_on = datetime.date.today() - datetime.timedelta(days=1)
        approved_offer_a.save(update_fields=["expires_on", "updated_at"])
        resp = client_a.post(reverse("hrm:offer_expire", args=[approved_offer_a.pk]))
        assert resp.status_code == 302
        approved_offer_a.refresh_from_db()
        assert approved_offer_a.status == "approved"  # unchanged


# ============================================================
# REGRESSION: reject/resubmit chain reset
# ============================================================

class TestOfferRejectResubmitChainReset:
    """submit -> reject_step -> resubmit -> approve: the offer must only become 'approved' after
    EVERY step is RE-approved. A previously-rejected step must not stay stuck letting the offer
    approve early (explorer finding — mirrors jobrequisition_submit's chain-reset regression)."""

    def test_reject_step_reopens_to_draft(self, client_a, pending_approval_offer_a):
        resp = client_a.post(reverse("hrm:offer_reject_step", args=[pending_approval_offer_a.pk]), {
            "comments": "Comp too high, revise.",
        })
        assert resp.status_code == 302
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "draft"

    def test_reject_step_resets_other_steps_to_pending(self, client_a, pending_approval_offer_a):
        client_a.post(reverse("hrm:offer_reject_step", args=[pending_approval_offer_a.pk]))
        statuses = set(pending_approval_offer_a.approvals.values_list("status", flat=True))
        assert statuses == {"pending"} or statuses == {"pending", "rejected"}
        # None of the steps should remain "approved" after a reject.
        assert "approved" not in statuses

    def test_full_reject_resubmit_reapprove_cycle(self, client_a, pending_approval_offer_a):
        """The core regression: reject step 1, resubmit, then only ONE approve must NOT flip the
        offer straight to approved — both steps must be re-approved from scratch."""
        # Reject the first pending step (step 1, hiring_manager).
        client_a.post(reverse("hrm:offer_reject_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "draft"

        # Resubmit — this must reset ALL steps (including any that might have been left "approved")
        # back to pending, and rebuild/reuse the same 2-step chain.
        client_a.post(reverse("hrm:offer_submit", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "pending_approval"
        assert pending_approval_offer_a.approvals.count() == 2
        assert all(s.status == "pending" for s in pending_approval_offer_a.approvals.all())

        # Approve only the first step — the offer must NOT be approved yet.
        client_a.post(reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "pending_approval"

        # Approve the second (final) step — NOW the offer is fully approved.
        client_a.post(reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "approved"

    def test_reject_after_first_step_approved_resets_that_approval_too(
            self, client_a, pending_approval_offer_a):
        """If step 1 was already approved and step 2 gets rejected, resubmitting must reset BOTH
        steps to pending — a stale 'approved' step 1 must not let the offer approve after only
        re-approving step 2."""
        # Approve step 1.
        client_a.post(reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "pending_approval"
        approved_step = pending_approval_offer_a.approvals.filter(status="approved").first()
        assert approved_step is not None

        # Reject step 2 (the now-current pending step).
        client_a.post(reverse("hrm:offer_reject_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "draft"
        # The reject-step view must reset ALL steps, including the previously-approved step 1.
        assert not pending_approval_offer_a.approvals.filter(status="approved").exists()

        # Resubmit and approve only once — must NOT be enough to approve the offer (2 steps required).
        client_a.post(reverse("hrm:offer_submit", args=[pending_approval_offer_a.pk]))
        client_a.post(reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "pending_approval"  # still needs step 2

        client_a.post(reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        pending_approval_offer_a.refresh_from_db()
        assert pending_approval_offer_a.status == "approved"


# ============================================================
# View Tests: OfferApproval add/delete
# ============================================================

class TestOfferApprovalViews:
    def test_add_step_creates_row(self, client_a, tenant_a, draft_offer_a):
        from apps.hrm.models import OfferApproval
        resp = client_a.post(reverse("hrm:offerapproval_add", args=[draft_offer_a.pk]), {
            "step_order": 1, "approver": "", "approver_role": "hr", "comments": "",
        })
        assert resp.status_code == 302
        assert OfferApproval.objects.filter(tenant=tenant_a, offer=draft_offer_a, step_order=1).exists()

    def test_add_step_blocked_when_not_draft(self, client_a, pending_approval_offer_a):
        from apps.hrm.models import OfferApproval
        before = OfferApproval.objects.filter(offer=pending_approval_offer_a).count()
        client_a.post(reverse("hrm:offerapproval_add", args=[pending_approval_offer_a.pk]), {
            "step_order": 5, "approver": "", "approver_role": "hr", "comments": "",
        })
        after = OfferApproval.objects.filter(offer=pending_approval_offer_a).count()
        assert after == before

    def test_add_step_nonadmin_403(self, member_client, draft_offer_a):
        resp = member_client.post(reverse("hrm:offerapproval_add", args=[draft_offer_a.pk]), {
            "step_order": 1, "approver": "", "approver_role": "hr", "comments": "",
        })
        assert resp.status_code == 403

    def test_delete_step_removes_row(self, client_a, offer_approval_a):
        from apps.hrm.models import OfferApproval
        # Reset the offer back to draft since steps are only removable pre-submit.
        offer = offer_approval_a.offer
        offer.status = "draft"
        offer.save(update_fields=["status", "updated_at"])
        pk = offer_approval_a.pk
        resp = client_a.post(reverse("hrm:offerapproval_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OfferApproval.objects.filter(pk=pk).exists()

    def test_delete_step_blocked_when_not_draft(self, client_a, offer_approval_a):
        from apps.hrm.models import OfferApproval
        # offer_approval_a's offer is pending_approval by default (fixture chain).
        resp = client_a.post(reverse("hrm:offerapproval_delete", args=[offer_approval_a.pk]))
        assert resp.status_code == 302
        assert OfferApproval.objects.filter(pk=offer_approval_a.pk).exists()

    def test_delete_step_nonadmin_403(self, member_client, offer_approval_a):
        resp = member_client.post(reverse("hrm:offerapproval_delete", args=[offer_approval_a.pk]))
        assert resp.status_code == 403


# ============================================================
# View Tests: BackgroundVerification lifecycle
# ============================================================

class TestBackgroundVerificationLifecycle:
    """initiate blocked without consent; mark_status guarded; complete requires valid result;
    edit blocked once completed."""

    def test_initiate_without_consent_goes_consent_pending(self, client_a, bgv_a):
        resp = client_a.post(reverse("hrm:backgroundverification_initiate", args=[bgv_a.pk]))
        assert resp.status_code == 302
        bgv_a.refresh_from_db()
        assert bgv_a.status == "consent_pending"
        assert bgv_a.initiated_at is None

    def test_initiate_with_consent_stamps_initiated(self, client_a, bgv_a, admin_user):
        bgv_a.consent_given = True
        bgv_a.save(update_fields=["consent_given", "updated_at"])
        resp = client_a.post(reverse("hrm:backgroundverification_initiate", args=[bgv_a.pk]))
        assert resp.status_code == 302
        bgv_a.refresh_from_db()
        assert bgv_a.status == "initiated"
        assert bgv_a.initiated_at is not None
        assert bgv_a.initiated_by == admin_user

    def test_initiate_nonadmin_403(self, member_client, bgv_a):
        resp = member_client.post(reverse("hrm:backgroundverification_initiate", args=[bgv_a.pk]))
        assert resp.status_code == 403

    def test_mark_status_rejects_invalid_status(self, client_a, bgv_a):
        bgv_a.consent_given = True
        bgv_a.status = "initiated"
        bgv_a.save(update_fields=["consent_given", "status", "updated_at"])
        resp = client_a.post(reverse("hrm:backgroundverification_mark_status", args=[bgv_a.pk]), {
            "status": "completed",  # not in BGV_MANUAL_TRANSITION_STATUSES
        })
        assert resp.status_code == 302
        bgv_a.refresh_from_db()
        assert bgv_a.status == "initiated"  # unchanged

    def test_mark_status_accepts_in_progress(self, client_a, bgv_a):
        bgv_a.consent_given = True
        bgv_a.status = "initiated"
        bgv_a.save(update_fields=["consent_given", "status", "updated_at"])
        resp = client_a.post(reverse("hrm:backgroundverification_mark_status", args=[bgv_a.pk]), {
            "status": "in_progress",
        })
        assert resp.status_code == 302
        bgv_a.refresh_from_db()
        assert bgv_a.status == "in_progress"

    def test_mark_status_blocked_before_initiate(self, client_a, bgv_a):
        resp = client_a.post(reverse("hrm:backgroundverification_mark_status", args=[bgv_a.pk]), {
            "status": "in_progress",
        })
        assert resp.status_code == 302
        bgv_a.refresh_from_db()
        assert bgv_a.status == "not_started"

    def test_mark_status_nonadmin_403(self, member_client, bgv_a):
        resp = member_client.post(reverse("hrm:backgroundverification_mark_status", args=[bgv_a.pk]), {
            "status": "in_progress",
        })
        assert resp.status_code == 403

    def test_complete_requires_valid_result(self, client_a, bgv_a):
        resp = client_a.post(reverse("hrm:backgroundverification_complete", args=[bgv_a.pk]), {
            "result": "not_a_real_result",
        })
        assert resp.status_code == 302
        bgv_a.refresh_from_db()
        assert bgv_a.status != "completed"

    def test_complete_with_valid_result_succeeds(self, client_a, bgv_a):
        resp = client_a.post(reverse("hrm:backgroundverification_complete", args=[bgv_a.pk]), {
            "result": "clear",
        })
        assert resp.status_code == 302
        bgv_a.refresh_from_db()
        assert bgv_a.status == "completed"
        assert bgv_a.result == "clear"
        assert bgv_a.completed_at is not None

    def test_complete_nonadmin_403(self, member_client, bgv_a):
        resp = member_client.post(reverse("hrm:backgroundverification_complete", args=[bgv_a.pk]), {
            "result": "clear",
        })
        assert resp.status_code == 403

    def test_edit_blocked_once_completed(self, client_a, bgv_a):
        bgv_a.status = "completed"
        bgv_a.result = "clear"
        bgv_a.save(update_fields=["status", "result", "updated_at"])
        resp = client_a.get(reverse("hrm:backgroundverification_edit", args=[bgv_a.pk]))
        assert resp.status_code == 302
        assert reverse("hrm:backgroundverification_detail", args=[bgv_a.pk]) in resp["Location"]

    def test_delete_nonadmin_403(self, member_client, bgv_a):
        from apps.hrm.models import BackgroundVerification
        resp = member_client.post(reverse("hrm:backgroundverification_delete", args=[bgv_a.pk]))
        assert resp.status_code == 403
        assert BackgroundVerification.objects.filter(pk=bgv_a.pk).exists()

    def test_delete_admin_succeeds(self, client_a, bgv_a):
        from apps.hrm.models import BackgroundVerification
        pk = bgv_a.pk
        resp = client_a.post(reverse("hrm:backgroundverification_delete", args=[pk]))
        assert resp.status_code == 302
        assert not BackgroundVerification.objects.filter(pk=pk).exists()


# ============================================================
# View Tests: Pre-boarding items
# ============================================================

class TestPreboardingItemViews:
    """mark_submitted only from pending/rejected + clears stale verified_by/at; verify/reject stamp
    verified_by/at; send_invite stamps reminder_sent_at + respects do_not_contact; add works for a
    regular tenant user; verify/reject/delete are admin-only."""

    def test_add_creates_item(self, client_a, tenant_a, draft_offer_a):
        from apps.hrm.models import PreboardingItem
        resp = client_a.post(reverse("hrm:preboardingitem_add", args=[draft_offer_a.pk]), {
            "document_type": "nda", "is_required": True, "notes": "",
        })
        assert resp.status_code == 302
        assert PreboardingItem.objects.filter(tenant=tenant_a, offer=draft_offer_a,
                                              document_type="nda").exists()

    def test_add_works_for_regular_tenant_user(self, member_client, tenant_a, draft_offer_a):
        """@login_required-only — a regular (non-admin) tenant user can add a pre-boarding item."""
        from apps.hrm.models import PreboardingItem
        resp = member_client.post(reverse("hrm:preboardingitem_add", args=[draft_offer_a.pk]), {
            "document_type": "tax_form", "is_required": True, "notes": "",
        })
        assert resp.status_code == 302
        assert PreboardingItem.objects.filter(tenant=tenant_a, offer=draft_offer_a,
                                              document_type="tax_form").exists()

    def test_mark_submitted_from_pending_succeeds(self, client_a, preboarding_item_a):
        resp = client_a.post(
            reverse("hrm:preboardingitem_mark_submitted", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.status == "submitted"
        assert preboarding_item_a.submitted_at is not None

    def test_mark_submitted_works_for_regular_tenant_user(self, member_client, preboarding_item_a):
        resp = member_client.post(
            reverse("hrm:preboardingitem_mark_submitted", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.status == "submitted"

    def test_mark_submitted_blocked_from_verified(self, client_a, preboarding_item_a, admin_user):
        preboarding_item_a.status = "verified"
        preboarding_item_a.verified_by = admin_user
        preboarding_item_a.verified_at = timezone.now()
        preboarding_item_a.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
        resp = client_a.post(
            reverse("hrm:preboardingitem_mark_submitted", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.status == "verified"  # unchanged

    def test_mark_submitted_from_rejected_clears_stale_verification(
            self, client_a, preboarding_item_a, admin_user):
        """A resubmit from 'rejected' must clear the stale verified_by/verified_at from the prior
        reject so history stays consistent."""
        preboarding_item_a.status = "rejected"
        preboarding_item_a.verified_by = admin_user
        preboarding_item_a.verified_at = timezone.now()
        preboarding_item_a.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
        resp = client_a.post(
            reverse("hrm:preboardingitem_mark_submitted", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.status == "submitted"
        assert preboarding_item_a.verified_by is None
        assert preboarding_item_a.verified_at is None

    def test_verify_stamps_verified_by_and_at(self, client_a, preboarding_item_a, admin_user):
        preboarding_item_a.status = "submitted"
        preboarding_item_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(reverse("hrm:preboardingitem_verify", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.status == "verified"
        assert preboarding_item_a.verified_by == admin_user
        assert preboarding_item_a.verified_at is not None

    def test_verify_nonadmin_403(self, member_client, preboarding_item_a):
        resp = member_client.post(
            reverse("hrm:preboardingitem_verify", args=[preboarding_item_a.pk]))
        assert resp.status_code == 403

    def test_reject_stamps_verified_by_and_at(self, client_a, preboarding_item_a, admin_user):
        preboarding_item_a.status = "submitted"
        preboarding_item_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(reverse("hrm:preboardingitem_reject", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.status == "rejected"
        assert preboarding_item_a.verified_by == admin_user
        assert preboarding_item_a.verified_at is not None

    def test_reject_nonadmin_403(self, member_client, preboarding_item_a):
        resp = member_client.post(
            reverse("hrm:preboardingitem_reject", args=[preboarding_item_a.pk]))
        assert resp.status_code == 403

    def test_delete_nonadmin_403(self, member_client, preboarding_item_a):
        from apps.hrm.models import PreboardingItem
        resp = member_client.post(
            reverse("hrm:preboardingitem_delete", args=[preboarding_item_a.pk]))
        assert resp.status_code == 403
        assert PreboardingItem.objects.filter(pk=preboarding_item_a.pk).exists()

    def test_delete_admin_succeeds(self, client_a, preboarding_item_a):
        from apps.hrm.models import PreboardingItem
        pk = preboarding_item_a.pk
        resp = client_a.post(reverse("hrm:preboardingitem_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PreboardingItem.objects.filter(pk=pk).exists()

    def test_send_invite_stamps_reminder_sent_at(self, client_a, tenant_a, preboarding_item_a):
        resp = client_a.post(
            reverse("hrm:preboardingitem_send_invite", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.reminder_sent_at is not None

    def test_send_invite_works_for_regular_tenant_user(self, member_client, preboarding_item_a):
        resp = member_client.post(
            reverse("hrm:preboardingitem_send_invite", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.reminder_sent_at is not None

    def test_send_invite_respects_do_not_contact(self, client_a, preboarding_item_a, candidate_a):
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])
        resp = client_a.post(
            reverse("hrm:preboardingitem_send_invite", args=[preboarding_item_a.pk]))
        assert resp.status_code == 302
        preboarding_item_a.refresh_from_db()
        assert preboarding_item_a.reminder_sent_at is None

    def test_send_invite_logs_communication(self, client_a, tenant_a, preboarding_item_a):
        from apps.hrm.models import CandidateCommunication
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        client_a.post(reverse("hrm:preboardingitem_send_invite", args=[preboarding_item_a.pk]))
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1


# ============================================================
# Email / do_not_contact suppression tests
# ============================================================

class TestOfferEmailDoNotContact:
    """offer_send_email + offer_extend suppress the send and don't 500 when do_not_contact."""

    def test_send_email_do_not_contact_no_communication(self, client_a, tenant_a,
                                                        approved_offer_a, candidate_a):
        from apps.hrm.models import CandidateCommunication
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:offer_send_email", args=[approved_offer_a.pk]))
        assert resp.status_code == 302  # no 500
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before

    def test_send_email_normal_candidate_logs_communication(
            self, client_a, tenant_a, approved_offer_a, offer_email_template_a):
        from apps.hrm.models import CandidateCommunication
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:offer_send_email", args=[approved_offer_a.pk]))
        assert resp.status_code == 302
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1

    def test_send_email_blocked_when_closed(self, client_a, tenant_a, application_a, admin_user):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today(), status="declined", created_by=admin_user)
        from apps.hrm.models import CandidateCommunication
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:offer_send_email", args=[offer.pk]))
        assert resp.status_code == 302
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before

    def test_send_email_works_for_regular_tenant_user(
            self, member_client, tenant_a, approved_offer_a, offer_email_template_a):
        """@login_required-only action."""
        from apps.hrm.models import CandidateCommunication
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = member_client.post(reverse("hrm:offer_send_email", args=[approved_offer_a.pk]))
        assert resp.status_code == 302
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1

    def test_extend_do_not_contact_does_not_500_and_extends_anyway(
            self, client_a, approved_offer_a, candidate_a):
        """offer_extend must still transition the offer even when the email is suppressed."""
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])
        resp = client_a.post(reverse("hrm:offer_extend", args=[approved_offer_a.pk]))
        assert resp.status_code == 302  # no 500
        approved_offer_a.refresh_from_db()
        assert approved_offer_a.status == "extended"

    def test_extend_do_not_contact_suppresses_communication(
            self, client_a, tenant_a, approved_offer_a, candidate_a):
        from apps.hrm.models import CandidateCommunication
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        client_a.post(reverse("hrm:offer_extend", args=[approved_offer_a.pk]))
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before

    def test_accept_works_for_regular_tenant_user(self, member_client, extended_offer_a):
        """@login_required-only action."""
        resp = member_client.post(reverse("hrm:offer_accept", args=[extended_offer_a.pk]))
        assert resp.status_code == 302
        extended_offer_a.refresh_from_db()
        assert extended_offer_a.status == "accepted"

    def test_decline_works_for_regular_tenant_user(self, member_client, extended_offer_a):
        """@login_required-only action."""
        resp = member_client.post(reverse("hrm:offer_decline", args=[extended_offer_a.pk]), {
            "decline_reason": "timing",
        })
        assert resp.status_code == 302
        extended_offer_a.refresh_from_db()
        assert extended_offer_a.status == "declined"


# ============================================================
# OfferLetterTemplate CRUD + print
# ============================================================

class TestOfferLetterTemplateViews:
    def test_list_200(self, client_a, offer_letter_template_a):
        resp = client_a.get(reverse("hrm:offerlettertemplate_list"))
        assert resp.status_code == 200

    def test_create_post(self, client_a, tenant_a):
        from apps.hrm.models import OfferLetterTemplate
        resp = client_a.post(reverse("hrm:offerlettertemplate_create"), {
            "name": "Executive Offer Letter", "is_active": True,
            "body_html": "Dear {{candidate_name}}, executive offer.",
        })
        assert resp.status_code == 302
        assert OfferLetterTemplate.objects.filter(tenant=tenant_a, name="Executive Offer Letter").exists()

    def test_delete_nonadmin_403(self, member_client, offer_letter_template_a):
        from apps.hrm.models import OfferLetterTemplate
        resp = member_client.post(
            reverse("hrm:offerlettertemplate_delete", args=[offer_letter_template_a.pk]))
        assert resp.status_code == 403
        assert OfferLetterTemplate.objects.filter(pk=offer_letter_template_a.pk).exists()

    def test_delete_admin_succeeds(self, client_a, offer_letter_template_a):
        from apps.hrm.models import OfferLetterTemplate
        pk = offer_letter_template_a.pk
        resp = client_a.post(reverse("hrm:offerlettertemplate_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OfferLetterTemplate.objects.filter(pk=pk).exists()

    def test_offer_letter_print_200(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_letter_print", args=[draft_offer_a.pk]))
        assert resp.status_code == 200

    def test_offer_letter_print_merges_candidate_name(self, client_a, draft_offer_a, candidate_a):
        resp = client_a.get(reverse("hrm:offer_letter_print", args=[draft_offer_a.pk]))
        assert candidate_a.name.encode() in resp.content

    def test_offer_letter_print_falls_back_without_template(self, client_a, tenant_a, application_a):
        from apps.hrm.models import Offer
        offer = Offer.objects.create(
            tenant=tenant_a, application=application_a, base_salary=Decimal("60000"),
            start_date=datetime.date.today() + datetime.timedelta(days=10))
        resp = client_a.get(reverse("hrm:offer_letter_print", args=[offer.pk]))
        assert resp.status_code == 200


# ============================================================
# Multi-tenant IDOR Tests
# ============================================================

class TestOfferIDOR:
    """Tenant-A admin requesting Tenant-B objects must receive 404 — sweep of every action."""

    def test_offer_detail_idor_404(self, client_a, offer_b):
        resp = client_a.get(reverse("hrm:offer_detail", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_edit_idor_404(self, client_a, offer_b):
        resp = client_a.get(reverse("hrm:offer_edit", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_delete_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_delete", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_submit_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_submit", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_approve_step_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_approve_step", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_reject_step_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_reject_step", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_extend_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_extend", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_accept_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_accept", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_decline_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_decline", args=[offer_b.pk]), {"decline_reason": "salary"})
        assert resp.status_code == 404

    def test_offer_rescind_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_rescind", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_expire_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_expire", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_send_email_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_send_email", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offer_letter_print_idor_404(self, client_a, offer_b):
        resp = client_a.get(reverse("hrm:offer_letter_print", args=[offer_b.pk]))
        assert resp.status_code == 404

    def test_offerapproval_add_idor_404(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offerapproval_add", args=[offer_b.pk]), {
            "step_order": 1, "approver": "", "approver_role": "hr", "comments": "",
        })
        assert resp.status_code == 404

    def test_offerapproval_delete_idor_404(self, client_a, offer_approval_b):
        resp = client_a.post(reverse("hrm:offerapproval_delete", args=[offer_approval_b.pk]))
        assert resp.status_code == 404

    def test_backgroundverification_detail_idor_404(self, client_a, bgv_b):
        resp = client_a.get(reverse("hrm:backgroundverification_detail", args=[bgv_b.pk]))
        assert resp.status_code == 404

    def test_backgroundverification_edit_idor_404(self, client_a, bgv_b):
        resp = client_a.get(reverse("hrm:backgroundverification_edit", args=[bgv_b.pk]))
        assert resp.status_code == 404

    def test_backgroundverification_delete_idor_404(self, client_a, bgv_b):
        resp = client_a.post(reverse("hrm:backgroundverification_delete", args=[bgv_b.pk]))
        assert resp.status_code == 404

    def test_backgroundverification_initiate_idor_404(self, client_a, bgv_b):
        resp = client_a.post(reverse("hrm:backgroundverification_initiate", args=[bgv_b.pk]))
        assert resp.status_code == 404

    def test_backgroundverification_mark_status_idor_404(self, client_a, bgv_b):
        resp = client_a.post(reverse("hrm:backgroundverification_mark_status", args=[bgv_b.pk]),
                             {"status": "in_progress"})
        assert resp.status_code == 404

    def test_backgroundverification_complete_idor_404(self, client_a, bgv_b):
        resp = client_a.post(reverse("hrm:backgroundverification_complete", args=[bgv_b.pk]),
                             {"result": "clear"})
        assert resp.status_code == 404

    def test_preboardingitem_delete_idor_404(self, client_a, preboarding_item_b):
        resp = client_a.post(reverse("hrm:preboardingitem_delete", args=[preboarding_item_b.pk]))
        assert resp.status_code == 404

    def test_preboardingitem_mark_submitted_idor_404(self, client_a, preboarding_item_b):
        resp = client_a.post(reverse("hrm:preboardingitem_mark_submitted", args=[preboarding_item_b.pk]))
        assert resp.status_code == 404

    def test_preboardingitem_verify_idor_404(self, client_a, preboarding_item_b):
        resp = client_a.post(reverse("hrm:preboardingitem_verify", args=[preboarding_item_b.pk]))
        assert resp.status_code == 404

    def test_preboardingitem_reject_idor_404(self, client_a, preboarding_item_b):
        resp = client_a.post(reverse("hrm:preboardingitem_reject", args=[preboarding_item_b.pk]))
        assert resp.status_code == 404

    def test_preboardingitem_send_invite_idor_404(self, client_a, preboarding_item_b):
        resp = client_a.post(reverse("hrm:preboardingitem_send_invite", args=[preboarding_item_b.pk]))
        assert resp.status_code == 404

    def test_preboardingitem_add_idor_404(self, client_a, offer_b):
        """Adding a pre-boarding item against a cross-tenant offer pk must 404."""
        resp = client_a.post(reverse("hrm:preboardingitem_add", args=[offer_b.pk]), {
            "document_type": "nda", "is_required": True, "notes": "",
        })
        assert resp.status_code == 404

    def test_offerlettertemplate_detail_idor_404(self, client_a, offer_letter_template_b):
        resp = client_a.get(reverse("hrm:offerlettertemplate_detail", args=[offer_letter_template_b.pk]))
        assert resp.status_code == 404

    def test_offerlettertemplate_edit_idor_404(self, client_a, offer_letter_template_b):
        resp = client_a.get(reverse("hrm:offerlettertemplate_edit", args=[offer_letter_template_b.pk]))
        assert resp.status_code == 404

    def test_offerlettertemplate_delete_idor_404(self, client_a, offer_letter_template_b):
        resp = client_a.post(reverse("hrm:offerlettertemplate_delete", args=[offer_letter_template_b.pk]))
        assert resp.status_code == 404

    def test_offer_list_excludes_tenant_b(self, client_a, draft_offer_a, offer_b):
        resp = client_a.get(reverse("hrm:offer_list"))
        assert resp.status_code == 200
        assert draft_offer_a.number.encode() in resp.content
        assert offer_b.candidate.name.encode() not in resp.content

    def test_backgroundverification_list_excludes_tenant_b(self, client_a, bgv_a, bgv_b, candidate_a, candidate_b):
        resp = client_a.get(reverse("hrm:backgroundverification_list"))
        assert resp.status_code == 200
        # Both tenants' BGV counters start at BGV-00001, so discriminate on the candidate name instead.
        assert candidate_a.name.encode() in resp.content
        assert candidate_b.name.encode() not in resp.content

    def test_offerlettertemplate_list_excludes_tenant_b(
            self, client_a, offer_letter_template_a, offer_letter_template_b):
        resp = client_a.get(reverse("hrm:offerlettertemplate_list"))
        assert resp.status_code == 200
        assert offer_letter_template_a.name.encode() in resp.content
        assert offer_letter_template_b.name.encode() not in resp.content

    def test_offer_b_status_unchanged_after_idor_attempt(self, client_a, offer_b):
        resp = client_a.post(reverse("hrm:offer_submit", args=[offer_b.pk]))
        assert resp.status_code == 404
        offer_b.refresh_from_db()
        assert offer_b.status == "draft"  # unchanged


# ============================================================
# Authorization Tests (@tenant_admin_required vs @login_required)
# ============================================================

class TestOfferAuthorization:
    """@tenant_admin_required actions -> 403 for non-admin, succeed for admin.
    @login_required-only actions work for a regular tenant user (covered inline above too)."""

    def test_offer_submit_nonadmin_403(self, member_client, draft_offer_a):
        resp = member_client.post(reverse("hrm:offer_submit", args=[draft_offer_a.pk]))
        assert resp.status_code == 403
        draft_offer_a.refresh_from_db()
        assert draft_offer_a.status == "draft"

    def test_offer_submit_admin_succeeds(self, client_a, draft_offer_a):
        resp = client_a.post(reverse("hrm:offer_submit", args=[draft_offer_a.pk]))
        assert resp.status_code == 302
        draft_offer_a.refresh_from_db()
        assert draft_offer_a.status == "pending_approval"

    def test_offer_approve_step_nonadmin_403(self, member_client, pending_approval_offer_a):
        resp = member_client.post(
            reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        assert resp.status_code == 403

    def test_offer_approve_step_admin_succeeds(self, client_a, pending_approval_offer_a):
        resp = client_a.post(
            reverse("hrm:offer_approve_step", args=[pending_approval_offer_a.pk]))
        assert resp.status_code == 302

    def test_offer_reject_step_nonadmin_403(self, member_client, pending_approval_offer_a):
        resp = member_client.post(
            reverse("hrm:offer_reject_step", args=[pending_approval_offer_a.pk]))
        assert resp.status_code == 403

    def test_offer_reject_step_admin_succeeds(self, client_a, pending_approval_offer_a):
        resp = client_a.post(
            reverse("hrm:offer_reject_step", args=[pending_approval_offer_a.pk]))
        assert resp.status_code == 302

    def test_offer_extend_nonadmin_403(self, member_client, approved_offer_a):
        resp = member_client.post(reverse("hrm:offer_extend", args=[approved_offer_a.pk]))
        assert resp.status_code == 403

    def test_offer_extend_admin_succeeds(self, client_a, approved_offer_a):
        resp = client_a.post(reverse("hrm:offer_extend", args=[approved_offer_a.pk]))
        assert resp.status_code == 302

    def test_offer_expire_nonadmin_403(self, member_client, extended_offer_a):
        resp = member_client.post(reverse("hrm:offer_expire", args=[extended_offer_a.pk]))
        assert resp.status_code == 403

    def test_offer_delete_admin_only(self, member_client, client_a, draft_offer_a):
        resp = member_client.post(reverse("hrm:offer_delete", args=[draft_offer_a.pk]))
        assert resp.status_code == 403

    def test_offerapproval_delete_admin_only(self, member_client, offer_approval_a):
        resp = member_client.post(reverse("hrm:offerapproval_delete", args=[offer_approval_a.pk]))
        assert resp.status_code == 403

    def test_preboardingitem_verify_admin_only(self, member_client, preboarding_item_a):
        resp = member_client.post(reverse("hrm:preboardingitem_verify", args=[preboarding_item_a.pk]))
        assert resp.status_code == 403

    def test_preboardingitem_reject_admin_only(self, member_client, preboarding_item_a):
        resp = member_client.post(reverse("hrm:preboardingitem_reject", args=[preboarding_item_a.pk]))
        assert resp.status_code == 403

    def test_preboardingitem_delete_admin_only(self, member_client, preboarding_item_a):
        resp = member_client.post(reverse("hrm:preboardingitem_delete", args=[preboarding_item_a.pk]))
        assert resp.status_code == 403

    def test_backgroundverification_initiate_admin_only(self, member_client, bgv_a):
        resp = member_client.post(reverse("hrm:backgroundverification_initiate", args=[bgv_a.pk]))
        assert resp.status_code == 403

    def test_backgroundverification_mark_status_admin_only(self, member_client, bgv_a):
        resp = member_client.post(
            reverse("hrm:backgroundverification_mark_status", args=[bgv_a.pk]), {"status": "in_progress"})
        assert resp.status_code == 403

    def test_backgroundverification_complete_admin_only(self, member_client, bgv_a):
        resp = member_client.post(
            reverse("hrm:backgroundverification_complete", args=[bgv_a.pk]), {"result": "clear"})
        assert resp.status_code == 403

    def test_offerlettertemplate_delete_admin_only(self, member_client, offer_letter_template_a):
        resp = member_client.post(
            reverse("hrm:offerlettertemplate_delete", args=[offer_letter_template_a.pk]))
        assert resp.status_code == 403

    def test_offer_submit_get_blocked(self, client_a, draft_offer_a):
        """@require_POST — GET must return 405."""
        resp = client_a.get(reverse("hrm:offer_submit", args=[draft_offer_a.pk]))
        assert resp.status_code == 405

    def test_offer_delete_get_blocked(self, client_a, draft_offer_a):
        resp = client_a.get(reverse("hrm:offer_delete", args=[draft_offer_a.pk]))
        assert resp.status_code == 405

    def test_anon_offer_detail_redirects_to_login(self, draft_offer_a):
        from django.test import Client
        c = Client()
        resp = c.get(reverse("hrm:offer_detail", args=[draft_offer_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
