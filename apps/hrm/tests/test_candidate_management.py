"""Comprehensive tests for HRM 3.6 Candidate Management sub-module.

Covers:
  - Models: CandidateProfile (CAND- prefix, name property, __str__, unique tenant+email,
            status choices), CandidateSkill (unique candidate+skill_name),
            JobApplication (APP- prefix, unique candidate+requisition, clean() rating 1-5,
            stage/stage_changed_at/hired_on workflow), CandidateEmailTemplate (CETMPL- prefix),
            CandidateCommunication (CC- prefix), CandidateTag (unique tenant+name),
            JobRequisition.public_token (unique, NULL-able).
  - Forms: CandidateProfileForm.clean_email (friendly duplicate error),
           CandidateTagForm.clean_color (rejects CSS-injection, accepts valid hex),
           JobApplicationForm FK querysets tenant-scoped,
           PublicApplicationForm (gdpr_consent required, resume required, rejects .exe).
  - Views / CRUD / workflow: candidate_create (Party+PartyRole+CandidateProfile, redirect to
           detail), consent stamping, candidate_edit Party name sync, application_create
           redirect to detail, stage machine (applied→screening→interview→hired sets hired_on
           + candidate.status="hired"), terminal-stage guard, application_reject logs
           CandidateCommunication, application_send_email (do_not_contact suppresses send),
           application_reject / application_withdraw / application_hold / application_advance_stage
           do NOT advance past terminal stage.
  - Multi-tenant isolation (IDOR): tenant-A admin → tenant-B object → 404 for candidate_detail,
           application_detail, emailtemplate_detail, communication_detail, candidatetag_edit.
  - Authorization: non-admin user gets 403 on candidate_delete, candidate_blacklist,
           emailtemplate_create, emailtemplate_edit, emailtemplate_delete; admin succeeds.
  - Public career portal: careers_apply only resolves for posted reqs with a public_token;
           POST creates CandidateProfile + JobApplication(source="careers_page") + fires
           CandidateCommunication; duplicate POST does NOT create a 2nd application;
           gdpr_consent + gdpr_consent_date are stamped when box is ticked.
"""
import io
import secrets
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# Candidate-specific fixtures
# ============================================================

@pytest.fixture
def req_posted_token(db, tenant_a, dept_a, designation_a):
    """A posted JobRequisition with a public_token for tenant_a."""
    from apps.hrm.models import JobRequisition
    req = JobRequisition.objects.create(
        tenant=tenant_a,
        title="QA Engineer",
        designation=designation_a,
        department=dept_a,
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="backfill",
        posting_type="external",
        priority="medium",
    )
    req.status = "posted"
    req.submitted_at = timezone.now()
    req.approved_at = timezone.now()
    req.posted_at = timezone.now()
    req.public_token = secrets.token_urlsafe(32)
    req.save(update_fields=["status", "submitted_at", "approved_at", "posted_at",
                            "public_token", "updated_at"])
    return req


@pytest.fixture
def req_posted_no_token(db, tenant_a, dept_a, designation_a):
    """A posted JobRequisition WITHOUT a public_token for tenant_a."""
    from apps.hrm.models import JobRequisition
    req = JobRequisition.objects.create(
        tenant=tenant_a,
        title="Internal Analyst",
        designation=designation_a,
        department=dept_a,
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="backfill",
        posting_type="internal",
        priority="low",
    )
    req.status = "posted"
    req.submitted_at = timezone.now()
    req.approved_at = timezone.now()
    req.posted_at = timezone.now()
    req.public_token = None
    req.save(update_fields=["status", "submitted_at", "approved_at", "posted_at",
                            "public_token", "updated_at"])
    return req


@pytest.fixture
def req_draft_a(db, tenant_a, dept_a, designation_a):
    """A draft JobRequisition for tenant_a."""
    from apps.hrm.models import JobRequisition
    from decimal import Decimal
    return JobRequisition.objects.create(
        tenant=tenant_a,
        title="Backend Developer",
        designation=designation_a,
        department=dept_a,
        headcount=2,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="new_headcount",
        posting_type="external",
        priority="medium",
        salary_min=Decimal("60000"),
        salary_max=Decimal("90000"),
        salary_currency="USD",
    )


@pytest.fixture
def req_b(db, tenant_b):
    """A draft JobRequisition for tenant_b (IDOR tests)."""
    from apps.hrm.models import JobRequisition
    return JobRequisition.objects.create(
        tenant=tenant_b,
        title="Analyst",
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="new_headcount",
        posting_type="external",
        priority="low",
    )


@pytest.fixture
def tag_a(db, tenant_a):
    """A CandidateTag for tenant_a."""
    from apps.hrm.models import CandidateTag
    return CandidateTag.objects.create(tenant=tenant_a, name="Python Expert", color="#3B82F6")


@pytest.fixture
def tag_b(db, tenant_b):
    """A CandidateTag for tenant_b (IDOR tests)."""
    from apps.hrm.models import CandidateTag
    return CandidateTag.objects.create(tenant=tenant_b, name="Java Expert", color="#EF4444")


@pytest.fixture
def candidate_a(db, tenant_a):
    """A CandidateProfile for tenant_a (via Party + PartyRole)."""
    from apps.core.models import Party, PartyRole
    from apps.hrm.models import CandidateProfile
    party = Party.objects.create(tenant=tenant_a, kind="person", name="Jane Doe")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="candidate")
    return CandidateProfile.objects.create(
        tenant=tenant_a,
        party=party,
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        source="careers_page",
    )


@pytest.fixture
def candidate_b(db, tenant_b):
    """A CandidateProfile for tenant_b (IDOR tests)."""
    from apps.core.models import Party, PartyRole
    from apps.hrm.models import CandidateProfile
    party = Party.objects.create(tenant=tenant_b, kind="person", name="Bob B")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="candidate")
    return CandidateProfile.objects.create(
        tenant=tenant_b,
        party=party,
        first_name="Bob",
        last_name="B",
        email="bob@globex.com",
        source="careers_page",
    )


@pytest.fixture
def application_a(db, tenant_a, candidate_a, req_draft_a):
    """A JobApplication for candidate_a / req_draft_a in tenant_a."""
    from apps.hrm.models import JobApplication
    return JobApplication.objects.create(
        tenant=tenant_a,
        candidate=candidate_a,
        requisition=req_draft_a,
        source="careers_page",
    )


@pytest.fixture
def application_b(db, tenant_b, candidate_b, req_b):
    """A JobApplication for tenant_b (IDOR tests)."""
    from apps.hrm.models import JobApplication
    return JobApplication.objects.create(
        tenant=tenant_b,
        candidate=candidate_b,
        requisition=req_b,
        source="careers_page",
    )


@pytest.fixture
def email_template_a(db, tenant_a):
    """A CandidateEmailTemplate for tenant_a."""
    from apps.hrm.models import CandidateEmailTemplate
    return CandidateEmailTemplate.objects.create(
        tenant=tenant_a,
        name="Welcome Email",
        template_type="application_received",
        subject="Thanks for applying to {{job_title}}",
        body_html="Hi {{candidate_name}}, thanks for applying!",
        is_active=True,
        is_auto_send=False,
    )


@pytest.fixture
def email_template_auto_reject(db, tenant_a):
    """An auto-send rejection CandidateEmailTemplate for tenant_a."""
    from apps.hrm.models import CandidateEmailTemplate
    return CandidateEmailTemplate.objects.create(
        tenant=tenant_a,
        name="Rejection Auto",
        template_type="rejection",
        subject="Your application has been reviewed",
        body_html="Hi {{candidate_name}}, unfortunately we cannot move forward.",
        is_active=True,
        is_auto_send=True,
    )


@pytest.fixture
def email_template_b(db, tenant_b):
    """A CandidateEmailTemplate for tenant_b (IDOR tests)."""
    from apps.hrm.models import CandidateEmailTemplate
    return CandidateEmailTemplate.objects.create(
        tenant=tenant_b,
        name="Welcome B",
        template_type="application_received",
        subject="Thanks",
        body_html="Hi there!",
        is_active=True,
        is_auto_send=False,
    )


@pytest.fixture
def communication_a(db, tenant_a, candidate_a, application_a, email_template_a, admin_user):
    """A CandidateCommunication for tenant_a."""
    from apps.hrm.models import CandidateCommunication
    return CandidateCommunication.objects.create(
        tenant=tenant_a,
        candidate=candidate_a,
        application=application_a,
        template=email_template_a,
        subject="Hi Jane",
        body="Thanks for applying!",
        sent_by=admin_user,
        delivery_status="sent",
    )


@pytest.fixture
def communication_b(db, tenant_b, candidate_b, application_b):
    """A CandidateCommunication for tenant_b (IDOR tests)."""
    from apps.hrm.models import CandidateCommunication
    return CandidateCommunication.objects.create(
        tenant=tenant_b,
        candidate=candidate_b,
        application=application_b,
        subject="Hi Bob",
        body="Thanks for applying!",
        delivery_status="sent",
    )


# helper to build a valid in-memory resume file
def _make_resume(name="resume.pdf", content=b"%PDF-1.4 test"):
    f = io.BytesIO(content)
    f.name = name
    f.size = len(content)
    return f


# ============================================================
# Model Tests: CandidateProfile
# ============================================================

class TestCandidateProfileModel:
    """CAND- prefix, name property, __str__, status default, unique (tenant, email)."""

    def test_number_prefix(self, candidate_a):
        assert candidate_a.number.startswith("CAND-")

    def test_number_format_first(self, candidate_a):
        assert candidate_a.number == "CAND-00001"

    def test_name_property(self, candidate_a):
        assert candidate_a.name == "Jane Doe"

    def test_str_includes_number(self, candidate_a):
        s = str(candidate_a)
        assert "CAND-00001" in s

    def test_str_includes_name(self, candidate_a):
        s = str(candidate_a)
        assert "Jane Doe" in s

    def test_status_default_active(self, candidate_a):
        assert candidate_a.status == "active"

    def test_unique_tenant_email_same_tenant_raises(self, tenant_a, candidate_a):
        """Creating a second CandidateProfile with the same (tenant, email) must raise IntegrityError."""
        from apps.core.models import Party, PartyRole
        from apps.hrm.models import CandidateProfile
        party2 = Party.objects.create(tenant=tenant_a, kind="person", name="Jane Dup")
        PartyRole.objects.create(tenant=tenant_a, party=party2, role="candidate")
        with pytest.raises(IntegrityError):
            CandidateProfile.objects.create(
                tenant=tenant_a, party=party2,
                first_name="Jane", last_name="Dup",
                email="jane.doe@example.com",  # same email as candidate_a
                source="careers_page",
            )

    def test_same_email_different_tenant_ok(self, tenant_b, candidate_a):
        """Same email in a different tenant is allowed."""
        from apps.core.models import Party, PartyRole
        from apps.hrm.models import CandidateProfile
        party_b = Party.objects.create(tenant=tenant_b, kind="person", name="Jane Other")
        PartyRole.objects.create(tenant=tenant_b, party=party_b, role="candidate")
        cp_b = CandidateProfile.objects.create(
            tenant=tenant_b, party=party_b,
            first_name="Jane", last_name="Other",
            email="jane.doe@example.com",  # same as candidate_a but different tenant
            source="careers_page",
        )
        assert cp_b.pk is not None

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b):
        """Each tenant's counter starts at CAND-00001."""
        from apps.core.models import Party, PartyRole
        from apps.hrm.models import CandidateProfile
        p_a = Party.objects.create(tenant=tenant_a, kind="person", name="A1")
        PartyRole.objects.create(tenant=tenant_a, party=p_a, role="candidate")
        cp_a = CandidateProfile.objects.create(
            tenant=tenant_a, party=p_a, first_name="A", last_name="One",
            email="a1@a.com", source="careers_page")
        p_b = Party.objects.create(tenant=tenant_b, kind="person", name="B1")
        PartyRole.objects.create(tenant=tenant_b, party=p_b, role="candidate")
        cp_b = CandidateProfile.objects.create(
            tenant=tenant_b, party=p_b, first_name="B", last_name="One",
            email="b1@b.com", source="careers_page")
        assert cp_a.number == "CAND-00001"
        assert cp_b.number == "CAND-00001"


# ============================================================
# Model Tests: CandidateSkill
# ============================================================

class TestCandidateSkillModel:
    """unique_together (candidate, skill_name)."""

    def test_skill_creation(self, tenant_a, candidate_a):
        from apps.hrm.models import CandidateSkill
        skill = CandidateSkill.objects.create(
            tenant=tenant_a, candidate=candidate_a, skill_name="Python", proficiency="expert")
        assert skill.pk is not None

    def test_unique_candidate_skill_name_raises(self, tenant_a, candidate_a):
        """A second CandidateSkill with the same (candidate, skill_name) must raise IntegrityError."""
        from apps.hrm.models import CandidateSkill
        CandidateSkill.objects.create(tenant=tenant_a, candidate=candidate_a, skill_name="Python")
        with pytest.raises(IntegrityError):
            CandidateSkill.objects.create(tenant=tenant_a, candidate=candidate_a, skill_name="Python")

    def test_different_skill_names_ok(self, tenant_a, candidate_a):
        from apps.hrm.models import CandidateSkill
        s1 = CandidateSkill.objects.create(tenant=tenant_a, candidate=candidate_a, skill_name="Python")
        s2 = CandidateSkill.objects.create(tenant=tenant_a, candidate=candidate_a, skill_name="Django")
        assert s1.pk != s2.pk

    def test_str_includes_skill_name(self, tenant_a, candidate_a):
        from apps.hrm.models import CandidateSkill
        skill = CandidateSkill.objects.create(
            tenant=tenant_a, candidate=candidate_a, skill_name="Python", proficiency="expert")
        assert "Python" in str(skill)


# ============================================================
# Model Tests: JobApplication
# ============================================================

class TestJobApplicationModel:
    """APP- prefix, unique (candidate, requisition), clean() rejects rating outside 1-5,
    stage machine fields, __str__."""

    def test_number_prefix(self, application_a):
        assert application_a.number.startswith("APP-")

    def test_number_format_first(self, application_a):
        assert application_a.number == "APP-00001"

    def test_stage_default_applied(self, application_a):
        assert application_a.stage == "applied"

    def test_str_includes_number(self, application_a):
        s = str(application_a)
        assert "APP-00001" in s

    def test_str_includes_candidate_name(self, application_a):
        s = str(application_a)
        assert "Jane Doe" in s

    def test_unique_candidate_requisition_raises(self, tenant_a, candidate_a, req_draft_a, application_a):
        """A second application for the same (candidate, requisition) must raise IntegrityError."""
        from apps.hrm.models import JobApplication
        with pytest.raises(IntegrityError):
            JobApplication.objects.create(
                tenant=tenant_a,
                candidate=candidate_a,
                requisition=req_draft_a,
                source="referral",
            )

    def test_clean_rejects_rating_zero(self, tenant_a, candidate_a, req_draft_a):
        from apps.hrm.models import JobApplication
        app = JobApplication(
            tenant=tenant_a, candidate=candidate_a, requisition=req_draft_a,
            source="careers_page", rating=0,
        )
        with pytest.raises(ValidationError) as exc_info:
            app.clean()
        assert "rating" in exc_info.value.message_dict

    def test_clean_rejects_rating_six(self, tenant_a, candidate_a, req_draft_a):
        from apps.hrm.models import JobApplication
        app = JobApplication(
            tenant=tenant_a, candidate=candidate_a, requisition=req_draft_a,
            source="careers_page", rating=6,
        )
        with pytest.raises(ValidationError) as exc_info:
            app.clean()
        assert "rating" in exc_info.value.message_dict

    def test_clean_accepts_rating_one(self, tenant_a, candidate_a, req_draft_a):
        from apps.hrm.models import JobApplication
        app = JobApplication(
            tenant=tenant_a, candidate=candidate_a, requisition=req_draft_a,
            source="careers_page", rating=1,
        )
        app.clean()  # should not raise

    def test_clean_accepts_rating_five(self, tenant_a, candidate_a, req_draft_a):
        from apps.hrm.models import JobApplication
        app = JobApplication(
            tenant=tenant_a, candidate=candidate_a, requisition=req_draft_a,
            source="careers_page", rating=5,
        )
        app.clean()  # should not raise

    def test_clean_accepts_no_rating(self, tenant_a, candidate_a, req_draft_a):
        from apps.hrm.models import JobApplication
        app = JobApplication(
            tenant=tenant_a, candidate=candidate_a, requisition=req_draft_a,
            source="careers_page", rating=None,
        )
        app.clean()  # should not raise


# ============================================================
# Model Tests: CandidateTag
# ============================================================

class TestCandidateTagModel:
    """unique_together (tenant, name), __str__."""

    def test_str_is_name(self, tag_a):
        assert str(tag_a) == "Python Expert"

    def test_unique_tag_name_same_tenant_raises(self, tenant_a, tag_a):
        from apps.hrm.models import CandidateTag
        with pytest.raises(IntegrityError):
            CandidateTag.objects.create(tenant=tenant_a, name="Python Expert", color="#EF4444")

    def test_same_name_different_tenant_ok(self, tenant_b, tag_a):
        from apps.hrm.models import CandidateTag
        tag2 = CandidateTag.objects.create(tenant=tenant_b, name="Python Expert", color="#EF4444")
        assert tag2.pk != tag_a.pk


# ============================================================
# Model Tests: JobRequisition.public_token
# ============================================================

class TestJobRequisitionPublicToken:
    """public_token is unique and NULL-able — two unposted reqs with NULL token coexist."""

    def test_two_null_tokens_coexist(self, tenant_a, dept_a, designation_a):
        """Two unposted reqs with NULL public_token must NOT trigger a unique constraint error."""
        from apps.hrm.models import JobRequisition
        r1 = JobRequisition.objects.create(
            tenant=tenant_a, title="Role A", headcount=1, req_type="standard",
            employment_type="full_time", reason_for_hire="new_headcount",
            posting_type="external", priority="low",
        )
        r2 = JobRequisition.objects.create(
            tenant=tenant_a, title="Role B", headcount=1, req_type="standard",
            employment_type="full_time", reason_for_hire="new_headcount",
            posting_type="external", priority="low",
        )
        # Both have null tokens by default (not yet posted)
        assert r1.public_token is None
        assert r2.public_token is None

    def test_unique_non_null_token(self, req_posted_token, tenant_b):
        """Setting the same non-null token on a second requisition must raise IntegrityError."""
        from apps.hrm.models import JobRequisition
        with pytest.raises(IntegrityError):
            JobRequisition.objects.create(
                tenant=tenant_b, title="Clash Role", headcount=1, req_type="standard",
                employment_type="full_time", reason_for_hire="new_headcount",
                posting_type="external", priority="low",
                public_token=req_posted_token.public_token,  # duplicate
            )


# ============================================================
# Form Tests: CandidateTagForm
# ============================================================

class TestCandidateTagForm:
    """clean_color rejects CSS-injection values; accepts valid hex."""

    def test_valid_hex_color_accepted(self, tenant_a):
        from apps.hrm.forms import CandidateTagForm
        form = CandidateTagForm({"name": "Taggy", "color": "#3B82F6", "description": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_css_injection_rejected(self, tenant_a):
        """A color value that embeds CSS injection must fail clean_color."""
        from apps.hrm.forms import CandidateTagForm
        form = CandidateTagForm(
            {"name": "Bad", "color": "red;background:url(x)", "description": ""},
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "color" in form.errors

    def test_plain_word_rejected(self, tenant_a):
        from apps.hrm.forms import CandidateTagForm
        form = CandidateTagForm({"name": "Bad2", "color": "red", "description": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "color" in form.errors

    def test_short_hex_rejected(self, tenant_a):
        """Three-digit shorthand hex (#abc) must be rejected — we require exactly 6 digits."""
        from apps.hrm.forms import CandidateTagForm
        form = CandidateTagForm({"name": "Short", "color": "#abc", "description": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "color" in form.errors

    def test_missing_hash_rejected(self, tenant_a):
        from apps.hrm.forms import CandidateTagForm
        form = CandidateTagForm({"name": "NoHash", "color": "3B82F6", "description": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "color" in form.errors


# ============================================================
# Form Tests: CandidateProfileForm
# ============================================================

class TestCandidateProfileForm:
    """clean_email surfaces a friendly duplicate error (not IntegrityError) for existing tenant email."""

    def test_duplicate_email_friendly_error(self, tenant_a, candidate_a):
        """Submitting the same email as an existing candidate in the tenant produces a form error."""
        from apps.hrm.forms import CandidateProfileForm
        form = CandidateProfileForm({
            "first_name": "Jane",
            "last_name": "Clone",
            "email": "jane.doe@example.com",  # already exists for tenant_a
            "source": "careers_page",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "email" in form.errors
        # The error must be the friendly message, not a DB constraint trace
        assert "already exists" in form.errors["email"][0].lower()

    def test_same_email_on_edit_is_ok(self, tenant_a, candidate_a):
        """Editing a candidate with their own email must not trigger a self-duplicate error."""
        from apps.hrm.forms import CandidateProfileForm
        form = CandidateProfileForm({
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "source": "careers_page",
        }, instance=candidate_a, tenant=tenant_a)
        # Should be valid (email is allowed for the same instance)
        assert "email" not in form.errors or form.is_valid()

    def test_status_not_a_form_field(self):
        """status is workflow-owned and must not appear in form fields."""
        from apps.hrm.forms import CandidateProfileForm
        assert "status" not in CandidateProfileForm.Meta.fields

    def test_gdpr_consent_date_not_a_form_field(self):
        """gdpr_consent_date is system-set and must not appear in form fields."""
        from apps.hrm.forms import CandidateProfileForm
        assert "gdpr_consent_date" not in CandidateProfileForm.Meta.fields

    def test_party_not_a_form_field(self):
        """party is set by the view; must not be in the form."""
        from apps.hrm.forms import CandidateProfileForm
        assert "party" not in CandidateProfileForm.Meta.fields


# ============================================================
# Form Tests: JobApplicationForm — FK querysets tenant-scoped
# ============================================================

class TestJobApplicationForm:
    """candidate and requisition querysets must be scoped to the form's tenant."""

    def test_candidate_queryset_tenant_scoped(self, tenant_a, candidate_a, candidate_b):
        from apps.hrm.forms import JobApplicationForm
        form = JobApplicationForm(tenant=tenant_a)
        pks = list(form.fields["candidate"].queryset.values_list("pk", flat=True))
        assert candidate_a.pk in pks
        assert candidate_b.pk not in pks

    def test_requisition_queryset_tenant_scoped(self, tenant_a, tenant_b, req_draft_a, req_b):
        from apps.hrm.forms import JobApplicationForm
        form = JobApplicationForm(tenant=tenant_a)
        pks = list(form.fields["requisition"].queryset.values_list("pk", flat=True))
        assert req_draft_a.pk in pks
        assert req_b.pk not in pks

    def test_cross_tenant_candidate_rejected(self, tenant_a, req_draft_a, candidate_b):
        """Submitting a cross-tenant candidate pk must fail validation."""
        from apps.hrm.forms import JobApplicationForm
        form = JobApplicationForm({
            "candidate": candidate_b.pk,
            "requisition": req_draft_a.pk,
            "source": "careers_page",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "candidate" in form.errors

    def test_cross_tenant_requisition_rejected(self, tenant_a, req_b, candidate_a):
        """Submitting a cross-tenant requisition pk must fail validation."""
        from apps.hrm.forms import JobApplicationForm
        form = JobApplicationForm({
            "candidate": candidate_a.pk,
            "requisition": req_b.pk,
            "source": "careers_page",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "requisition" in form.errors

    def test_stage_not_a_form_field(self):
        from apps.hrm.forms import JobApplicationForm
        assert "stage" not in JobApplicationForm.Meta.fields

    def test_hired_on_not_a_form_field(self):
        from apps.hrm.forms import JobApplicationForm
        assert "hired_on" not in JobApplicationForm.Meta.fields


# ============================================================
# Form Tests: PublicApplicationForm
# ============================================================

class TestPublicApplicationForm:
    """gdpr_consent required; resume_file required and rejects .exe."""

    def _valid_data(self):
        return {
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "phone": "",
            "linkedin_url": "",
            "city": "",
            "cover_letter_text": "",
            "source": "careers_page",
            "gdpr_consent": True,
        }

    def test_valid_form_with_pdf_resume(self):
        from apps.hrm.forms import PublicApplicationForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        resume = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        form = PublicApplicationForm(self._valid_data(), {"resume_file": resume})
        assert form.is_valid(), form.errors

    def test_gdpr_consent_required(self):
        from apps.hrm.forms import PublicApplicationForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = self._valid_data()
        data.pop("gdpr_consent")  # omit consent
        resume = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        form = PublicApplicationForm(data, {"resume_file": resume})
        assert not form.is_valid()
        assert "gdpr_consent" in form.errors

    def test_resume_required(self):
        from apps.hrm.forms import PublicApplicationForm
        form = PublicApplicationForm(self._valid_data(), {})
        assert not form.is_valid()
        assert "resume_file" in form.errors

    def test_exe_resume_rejected(self):
        from apps.hrm.forms import PublicApplicationForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        resume = SimpleUploadedFile("malware.exe", b"MZ\x90\x00", content_type="application/octet-stream")
        form = PublicApplicationForm(self._valid_data(), {"resume_file": resume})
        assert not form.is_valid()
        assert "resume_file" in form.errors

    def test_doc_resume_accepted(self):
        from apps.hrm.forms import PublicApplicationForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        resume = SimpleUploadedFile("cv.docx", b"PK\x03\x04", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        form = PublicApplicationForm(self._valid_data(), {"resume_file": resume})
        assert form.is_valid(), form.errors


# ============================================================
# View Tests: Candidate CRUD
# ============================================================

class TestCandidateCreateView:
    """POST candidate_create creates exactly one Party + PartyRole + CandidateProfile."""

    def test_post_creates_candidate_profile(self, client_a, tenant_a):
        from apps.hrm.models import CandidateProfile
        resp = client_a.post(reverse("hrm:candidate_create"), {
            "first_name": "Alice",
            "last_name": "New",
            "email": "alice.new@example.com",
            "source": "linkedin",
            "gdpr_consent": "",  # not ticked
        })
        assert resp.status_code == 302
        assert CandidateProfile.objects.filter(tenant=tenant_a, email="alice.new@example.com").exists()

    def test_post_creates_exactly_one_party(self, client_a, tenant_a):
        from apps.core.models import Party
        before = Party.objects.filter(tenant=tenant_a, kind="person").count()
        client_a.post(reverse("hrm:candidate_create"), {
            "first_name": "Alice",
            "last_name": "New",
            "email": "alice.new2@example.com",
            "source": "linkedin",
        })
        after = Party.objects.filter(tenant=tenant_a, kind="person").count()
        assert after == before + 1

    def test_post_creates_party_role_candidate(self, client_a, tenant_a):
        from apps.core.models import Party, PartyRole
        client_a.post(reverse("hrm:candidate_create"), {
            "first_name": "Alice",
            "last_name": "New",
            "email": "alice.new3@example.com",
            "source": "linkedin",
        })
        party = Party.objects.filter(tenant=tenant_a, name="Alice New").first()
        assert party is not None
        assert PartyRole.objects.filter(tenant=tenant_a, party=party, role="candidate").exists()

    def test_post_redirects_to_detail(self, client_a, tenant_a):
        from apps.hrm.models import CandidateProfile
        resp = client_a.post(reverse("hrm:candidate_create"), {
            "first_name": "Bob",
            "last_name": "Created",
            "email": "bob.created@example.com",
            "source": "linkedin",
        })
        assert resp.status_code == 302
        cp = CandidateProfile.objects.filter(tenant=tenant_a, email="bob.created@example.com").first()
        assert cp is not None
        assert reverse("hrm:candidate_detail", args=[cp.pk]) in resp["Location"]

    def test_consent_stamping_when_ticked(self, client_a, tenant_a):
        """POSTing with gdpr_consent=True must stamp gdpr_consent_date."""
        from apps.hrm.models import CandidateProfile
        client_a.post(reverse("hrm:candidate_create"), {
            "first_name": "Consent",
            "last_name": "User",
            "email": "consent.user@example.com",
            "source": "careers_page",
            "gdpr_consent": "on",
        })
        cp = CandidateProfile.objects.filter(tenant=tenant_a, email="consent.user@example.com").first()
        assert cp is not None
        assert cp.gdpr_consent is True
        assert cp.gdpr_consent_date is not None

    def test_no_consent_stamp_when_not_ticked(self, client_a, tenant_a):
        """POSTing without gdpr_consent must leave gdpr_consent_date as None."""
        from apps.hrm.models import CandidateProfile
        client_a.post(reverse("hrm:candidate_create"), {
            "first_name": "NoConsent",
            "last_name": "User",
            "email": "noconsent.user@example.com",
            "source": "careers_page",
        })
        cp = CandidateProfile.objects.filter(tenant=tenant_a, email="noconsent.user@example.com").first()
        assert cp is not None
        assert cp.gdpr_consent_date is None

    def test_anon_redirect(self):
        from django.test import Client
        c = Client()
        resp = c.post(reverse("hrm:candidate_create"), {
            "first_name": "Anon", "last_name": "Try", "email": "anon@x.com", "source": "linkedin"})
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestCandidateEditView:
    """Editing a candidate syncs Party.name when the name changes."""

    def test_edit_post_syncs_party_name(self, client_a, candidate_a):
        resp = client_a.post(reverse("hrm:candidate_edit", args=[candidate_a.pk]), {
            "first_name": "Janet",
            "last_name": "Smith",
            "email": "jane.doe@example.com",  # keep same email
            "source": "linkedin",
        })
        assert resp.status_code == 302
        candidate_a.refresh_from_db()
        candidate_a.party.refresh_from_db()
        assert candidate_a.first_name == "Janet"
        assert candidate_a.party.name == "Janet Smith"

    def test_edit_idor_404(self, client_a, candidate_b):
        resp = client_a.get(reverse("hrm:candidate_edit", args=[candidate_b.pk]))
        assert resp.status_code == 404


class TestCandidateDetailView:
    """Detail page 200; IDOR 404."""

    def test_detail_200(self, client_a, candidate_a):
        resp = client_a.get(reverse("hrm:candidate_detail", args=[candidate_a.pk]))
        assert resp.status_code == 200

    def test_detail_idor_404(self, client_a, candidate_b):
        resp = client_a.get(reverse("hrm:candidate_detail", args=[candidate_b.pk]))
        assert resp.status_code == 404


# ============================================================
# View Tests: Application CRUD + workflow
# ============================================================

class TestApplicationCreateView:
    """POST application_create redirects to the new application's detail."""

    def test_post_redirects_to_application_detail(self, client_a, tenant_a, candidate_a, req_draft_a):
        from apps.hrm.models import JobApplication
        resp = client_a.post(reverse("hrm:application_create"), {
            "candidate": candidate_a.pk,
            "requisition": req_draft_a.pk,
            "source": "linkedin",
        })
        assert resp.status_code == 302
        app = JobApplication.objects.filter(tenant=tenant_a, candidate=candidate_a,
                                            requisition=req_draft_a).first()
        assert app is not None
        assert reverse("hrm:application_detail", args=[app.pk]) in resp["Location"]

    def test_post_sets_correct_tenant(self, client_a, tenant_a, candidate_a, req_draft_a):
        from apps.hrm.models import JobApplication
        client_a.post(reverse("hrm:application_create"), {
            "candidate": candidate_a.pk,
            "requisition": req_draft_a.pk,
            "source": "careers_page",
        })
        app = JobApplication.objects.filter(tenant=tenant_a, candidate=candidate_a).first()
        assert app is not None
        assert app.tenant == tenant_a


class TestApplicationStageMachine:
    """Stage machine: applied→screening→interview; 'hired' sets hired_on + candidate.status."""

    def test_advance_applied_to_screening(self, client_a, application_a):
        resp = client_a.post(
            reverse("hrm:application_advance_stage", args=[application_a.pk]),
            {"new_stage": "screening"})
        assert resp.status_code == 302
        application_a.refresh_from_db()
        assert application_a.stage == "screening"

    def test_advance_sets_stage_changed_at(self, client_a, application_a):
        client_a.post(
            reverse("hrm:application_advance_stage", args=[application_a.pk]),
            {"new_stage": "screening"})
        application_a.refresh_from_db()
        assert application_a.stage_changed_at is not None

    def test_advance_screening_to_interview(self, client_a, application_a):
        application_a.stage = "screening"
        application_a.save(update_fields=["stage", "updated_at"])
        resp = client_a.post(
            reverse("hrm:application_advance_stage", args=[application_a.pk]),
            {"new_stage": "interview"})
        assert resp.status_code == 302
        application_a.refresh_from_db()
        assert application_a.stage == "interview"

    def test_advance_to_hired_sets_hired_on(self, client_a, application_a):
        client_a.post(
            reverse("hrm:application_advance_stage", args=[application_a.pk]),
            {"new_stage": "hired"})
        application_a.refresh_from_db()
        assert application_a.hired_on is not None

    def test_advance_to_hired_sets_candidate_status(self, client_a, application_a, candidate_a):
        client_a.post(
            reverse("hrm:application_advance_stage", args=[application_a.pk]),
            {"new_stage": "hired"})
        candidate_a.refresh_from_db()
        assert candidate_a.status == "hired"

    def test_terminal_stage_guard_reject(self, client_a, application_a):
        """After reject, application_reject must not change the stage again."""
        # First reject
        client_a.post(reverse("hrm:application_reject", args=[application_a.pk]),
                      {"rejection_reason": "other", "rejection_notes": "First rejection"})
        application_a.refresh_from_db()
        assert application_a.stage == "rejected"

        # Second reject must be a no-op
        client_a.post(reverse("hrm:application_reject", args=[application_a.pk]),
                      {"rejection_reason": "overqualified", "rejection_notes": "Second"})
        application_a.refresh_from_db()
        assert application_a.stage == "rejected"
        assert application_a.rejection_reason in ("other", "")  # not overqualified — first wins

    def test_terminal_stage_guard_withdraw(self, client_a, application_a):
        """After reject, application_withdraw must not change the stage."""
        application_a.stage = "rejected"
        application_a.stage_changed_at = timezone.now()
        application_a.save(update_fields=["stage", "stage_changed_at", "updated_at"])

        client_a.post(reverse("hrm:application_withdraw", args=[application_a.pk]))
        application_a.refresh_from_db()
        assert application_a.stage == "rejected"

    def test_terminal_stage_guard_hold(self, client_a, application_a):
        """After reject, application_hold must not change the stage."""
        application_a.stage = "rejected"
        application_a.stage_changed_at = timezone.now()
        application_a.save(update_fields=["stage", "stage_changed_at", "updated_at"])

        client_a.post(reverse("hrm:application_hold", args=[application_a.pk]))
        application_a.refresh_from_db()
        assert application_a.stage == "rejected"

    def test_terminal_stage_guard_advance(self, client_a, application_a):
        """After reject, application_advance_stage must not change the stage."""
        application_a.stage = "rejected"
        application_a.stage_changed_at = timezone.now()
        application_a.save(update_fields=["stage", "stage_changed_at", "updated_at"])

        client_a.post(
            reverse("hrm:application_advance_stage", args=[application_a.pk]),
            {"new_stage": "screening"})
        application_a.refresh_from_db()
        assert application_a.stage == "rejected"


class TestApplicationRejectLogging:
    """application_reject with is_auto_send rejection template logs a CandidateCommunication."""

    def test_reject_with_auto_send_template_logs_communication(
            self, client_a, tenant_a, application_a, email_template_auto_reject):
        from apps.hrm.models import CandidateCommunication
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        client_a.post(reverse("hrm:application_reject", args=[application_a.pk]),
                      {"rejection_reason": "other", "rejection_notes": ""})
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1

    def test_reject_no_auto_send_template_no_communication(
            self, client_a, tenant_a, application_a):
        """Without an is_auto_send rejection template, no CandidateCommunication is created."""
        from apps.hrm.models import CandidateCommunication
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        client_a.post(reverse("hrm:application_reject", args=[application_a.pk]),
                      {"rejection_reason": "other"})
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before  # no auto-send template → nothing logged

    def test_reject_do_not_contact_suppresses_communication(
            self, client_a, tenant_a, application_a, candidate_a, email_template_auto_reject):
        """When candidate.do_not_contact=True, rejection auto-send must be suppressed (no new CC)."""
        from apps.hrm.models import CandidateCommunication
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])

        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        client_a.post(reverse("hrm:application_reject", args=[application_a.pk]),
                      {"rejection_reason": "other"})
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before  # do_not_contact suppresses the auto-send


class TestApplicationSendEmail:
    """application_send_email logs a CandidateCommunication; do_not_contact suppresses it."""

    def test_send_email_logs_communication(
            self, client_a, tenant_a, application_a, email_template_a):
        from apps.hrm.models import CandidateCommunication
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        client_a.post(reverse("hrm:application_send_email", args=[application_a.pk]), {
            "template_id": email_template_a.pk,
        })
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1

    def test_send_email_do_not_contact_suppressed(
            self, client_a, tenant_a, application_a, candidate_a, email_template_a):
        """If candidate.do_not_contact=True, send_email must send nothing and log nothing."""
        from apps.hrm.models import CandidateCommunication
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])

        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:application_send_email", args=[application_a.pk]), {
            "template_id": email_template_a.pk,
        })
        assert resp.status_code == 302
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before  # nothing logged


# ============================================================
# Multi-tenant isolation (IDOR) tests
# ============================================================

class TestCandidateManagementIDOR:
    """Tenant-A admin requesting Tenant-B objects must receive 404."""

    def test_candidate_detail_idor_404(self, client_a, candidate_b):
        resp = client_a.get(reverse("hrm:candidate_detail", args=[candidate_b.pk]))
        assert resp.status_code == 404

    def test_application_detail_idor_404(self, client_a, application_b):
        resp = client_a.get(reverse("hrm:application_detail", args=[application_b.pk]))
        assert resp.status_code == 404

    def test_emailtemplate_detail_idor_404(self, client_a, email_template_b):
        resp = client_a.get(reverse("hrm:emailtemplate_detail", args=[email_template_b.pk]))
        assert resp.status_code == 404

    def test_communication_detail_idor_404(self, client_a, communication_b):
        resp = client_a.get(reverse("hrm:communication_detail", args=[communication_b.pk]))
        assert resp.status_code == 404

    def test_candidatetag_edit_idor_404(self, client_a, tag_b):
        resp = client_a.get(reverse("hrm:candidatetag_edit", args=[tag_b.pk]))
        assert resp.status_code == 404

    def test_candidate_list_excludes_other_tenant(self, client_a, candidate_a, candidate_b):
        resp = client_a.get(reverse("hrm:candidate_list"))
        assert resp.status_code == 200
        assert candidate_a.email.encode() in resp.content
        assert candidate_b.email.encode() not in resp.content

    def test_application_list_excludes_other_tenant(self, client_a, application_a, application_b):
        """The application list must contain tenant-A's candidate email but not tenant-B's."""
        resp = client_a.get(reverse("hrm:application_list"))
        assert resp.status_code == 200
        # Use candidate email (unique, cross-tenant distinct) as the discriminating anchor —
        # both tenants produce APP-00001 so the number alone is not a useful IDOR signal.
        assert application_a.candidate.email.encode() in resp.content
        assert application_b.candidate.email.encode() not in resp.content


# ============================================================
# Authorization tests (@tenant_admin_required)
# ============================================================

class TestCandidateManagementAuthorization:
    """Non-admin members get 403 on privileged actions; admin succeeds."""

    def test_nonmember_candidate_delete_403(self, member_client, candidate_a):
        from django.core.exceptions import PermissionDenied
        resp = member_client.post(reverse("hrm:candidate_delete", args=[candidate_a.pk]))
        assert resp.status_code == 403

    def test_admin_candidate_delete_succeeds(self, client_a, candidate_a):
        resp = client_a.post(reverse("hrm:candidate_delete", args=[candidate_a.pk]))
        assert resp.status_code == 302  # redirect after delete

    def test_nonmember_candidate_blacklist_403(self, member_client, candidate_a):
        resp = member_client.post(reverse("hrm:candidate_blacklist", args=[candidate_a.pk]))
        assert resp.status_code == 403

    def test_admin_candidate_blacklist_succeeds(self, client_a, candidate_a):
        resp = client_a.post(reverse("hrm:candidate_blacklist", args=[candidate_a.pk]))
        assert resp.status_code == 302
        candidate_a.refresh_from_db()
        assert candidate_a.status == "blacklisted"

    def test_nonmember_emailtemplate_create_403(self, member_client, tenant_a):
        resp = member_client.get(reverse("hrm:emailtemplate_create"))
        assert resp.status_code == 403

    def test_admin_emailtemplate_create_200(self, client_a):
        resp = client_a.get(reverse("hrm:emailtemplate_create"))
        assert resp.status_code == 200

    def test_nonmember_emailtemplate_edit_403(self, member_client, email_template_a):
        resp = member_client.get(reverse("hrm:emailtemplate_edit", args=[email_template_a.pk]))
        assert resp.status_code == 403

    def test_admin_emailtemplate_edit_200(self, client_a, email_template_a):
        resp = client_a.get(reverse("hrm:emailtemplate_edit", args=[email_template_a.pk]))
        assert resp.status_code == 200

    def test_nonmember_emailtemplate_delete_403(self, member_client, email_template_a):
        resp = member_client.post(reverse("hrm:emailtemplate_delete", args=[email_template_a.pk]))
        assert resp.status_code == 403

    def test_admin_emailtemplate_delete_succeeds(self, client_a, email_template_a):
        from apps.hrm.models import CandidateEmailTemplate
        pk = email_template_a.pk
        resp = client_a.post(reverse("hrm:emailtemplate_delete", args=[pk]))
        assert resp.status_code == 302
        assert not CandidateEmailTemplate.objects.filter(pk=pk).exists()

    def test_anon_candidate_list_redirects(self):
        from django.test import Client
        c = Client()
        resp = c.get(reverse("hrm:candidate_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_application_list_redirects(self):
        from django.test import Client
        c = Client()
        resp = c.get(reverse("hrm:application_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================
# Public career portal tests (anonymous client)
# ============================================================

class TestCareersApplyView:
    """careers_apply resolves only for posted reqs with a public_token;
    POST creates CandidateProfile + JobApplication(source='careers_page');
    duplicate POST does not create a 2nd application;
    gdpr_consent + gdpr_consent_date are stamped."""

    def _post_form(self, client, token, extra=None):
        """Post the minimum valid career-apply form."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        resume = SimpleUploadedFile("cv.pdf", b"%PDF-1.4", content_type="application/pdf")
        data = {
            "first_name": "Public",
            "last_name": "Applicant",
            "email": "public.applicant@example.com",
            "phone": "",
            "linkedin_url": "",
            "city": "",
            "cover_letter_text": "",
            "source": "careers_page",
            "gdpr_consent": "on",
            "resume_file": resume,
        }
        if extra:
            data.update(extra)
        return client.post(
            reverse("hrm:careers_apply", args=[token]),
            data,
            format="multipart",
        )

    def test_posted_req_with_token_resolves_200(self, client, req_posted_token):
        resp = client.get(reverse("hrm:careers_apply", args=[req_posted_token.public_token]))
        assert resp.status_code == 200

    def test_nonexistent_token_404(self, client):
        resp = client.get(reverse("hrm:careers_apply", args=["nonexistenttoken123"]))
        assert resp.status_code == 404

    def test_draft_req_without_token_404(self, client, req_draft_a):
        """A draft req has no public_token — a fabricated token must 404."""
        resp = client.get(reverse("hrm:careers_apply", args=["drafttokendoesnotexist"]))
        assert resp.status_code == 404

    def test_posted_req_without_token_not_accessible(self, client, req_posted_no_token):
        """A posted req with public_token=None cannot be resolved via URL (no valid token exists)."""
        resp = client.get(reverse("hrm:careers_apply", args=["sometoken"]))
        assert resp.status_code == 404

    def test_post_creates_candidate_profile(self, client, tenant_a, req_posted_token):
        from apps.hrm.models import CandidateProfile
        self._post_form(client, req_posted_token.public_token)
        assert CandidateProfile.objects.filter(
            tenant=tenant_a, email="public.applicant@example.com").exists()

    def test_post_creates_job_application_source_careers_page(self, client, tenant_a, req_posted_token):
        from apps.hrm.models import JobApplication
        self._post_form(client, req_posted_token.public_token)
        app = JobApplication.objects.filter(tenant=tenant_a, requisition=req_posted_token).first()
        assert app is not None
        assert app.source == "careers_page"

    def test_post_application_under_req_tenant(self, client, tenant_a, req_posted_token):
        """The created application must belong to the requisition's tenant."""
        from apps.hrm.models import JobApplication
        self._post_form(client, req_posted_token.public_token)
        app = JobApplication.objects.filter(tenant=tenant_a, requisition=req_posted_token).first()
        assert app is not None
        assert app.tenant == tenant_a

    def test_post_fires_application_received_communication(self, client, tenant_a, req_posted_token):
        """If an is_auto_send application_received template exists, a CC must be logged."""
        from apps.hrm.models import CandidateEmailTemplate, CandidateCommunication
        CandidateEmailTemplate.objects.create(
            tenant=tenant_a,
            name="App Received Auto",
            template_type="application_received",
            subject="Thanks for applying to {{job_title}}",
            body_html="Hi {{candidate_name}}, we got your application!",
            is_active=True,
            is_auto_send=True,
        )
        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        self._post_form(client, req_posted_token.public_token)
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1

    def test_duplicate_post_does_not_create_second_application(self, client, tenant_a, req_posted_token):
        """Submitting the same email + req twice must NOT create a 2nd JobApplication."""
        from apps.hrm.models import JobApplication
        self._post_form(client, req_posted_token.public_token)
        self._post_form(client, req_posted_token.public_token)
        count = JobApplication.objects.filter(tenant=tenant_a, requisition=req_posted_token).count()
        assert count == 1

    def test_gdpr_consent_stamped(self, client, tenant_a, req_posted_token):
        """Ticking gdpr_consent must set gdpr_consent=True and gdpr_consent_date on the candidate."""
        from apps.hrm.models import CandidateProfile
        self._post_form(client, req_posted_token.public_token)
        cp = CandidateProfile.objects.filter(
            tenant=tenant_a, email="public.applicant@example.com").first()
        assert cp is not None
        assert cp.gdpr_consent is True
        assert cp.gdpr_consent_date is not None

    def test_post_without_consent_fails_form(self, client, req_posted_token):
        """Posting without gdpr_consent must keep the form and not create any records."""
        from apps.hrm.models import CandidateProfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        resume = SimpleUploadedFile("cv.pdf", b"%PDF-1.4", content_type="application/pdf")
        resp = client.post(
            reverse("hrm:careers_apply", args=[req_posted_token.public_token]),
            {
                "first_name": "No",
                "last_name": "Consent",
                "email": "no.consent@example.com",
                "source": "careers_page",
                # gdpr_consent deliberately omitted
                "resume_file": resume,
            },
            format="multipart",
        )
        # Form must be re-rendered (200) — not redirect
        assert resp.status_code == 200
        assert not CandidateProfile.objects.filter(
            email="no.consent@example.com").exists()

    def test_post_redirects_with_submitted_1(self, client, req_posted_token):
        """After successful submit, the view must redirect to ?submitted=1."""
        resp = self._post_form(client, req_posted_token.public_token)
        assert resp.status_code == 302
        assert "submitted=1" in resp["Location"]
