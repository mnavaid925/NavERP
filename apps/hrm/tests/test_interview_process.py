"""Comprehensive tests for HRM 3.7 Interview Process sub-module.

Covers:
  - Models: Interview (INTV- prefix, auto-number per tenant, __str__, is_closed property,
            unique_together (tenant, number)); InterviewPanelist (unique_together (interview,
            interviewer), __str__); InterviewFeedback (IFB- prefix, unique_together (interview,
            panelist) rejects duplicate non-null panelist but allows multiple NULL panelists,
            __str__); FeedbackCriterion (clean() rejects rating 0 and 6, accepts 1..5, __str__).
  - Forms: InterviewForm (status/scheduled_by/reminder_sent_at NOT form fields; application
           queryset tenant-scoped); InterviewPanelistForm (interviewer queryset tenant-scoped;
           rsvp_status/notified_at NOT form fields); InterviewFeedbackForm (cross-interview
           panelist rejected by clean(); is_submitted/submitted_at/submitted_by NOT form fields);
           FeedbackCriterionForm (rating 1-5 validated).
  - Views / CRUD / workflow: interview CRUD 200/302; interview status machine
           (scheduled→confirmed→in_progress→completed; cancel/no_show; terminal guard; reschedule
           reopens completed); interviewfeedback_submit stamps is_submitted/submitted_at/submitted_by;
           edit after submit cannot un-submit; feedbackcriterion_add (valid + invalid rating);
           feedbackcriterion_delete; panelist add/remove/rsvp; interview list/detail context;
           feedback list/detail.
  - Email / communication: _send_interview_email with no matching template still logs a
           CandidateCommunication from the fallback body; reminder stamps reminder_sent_at;
           do_not_contact suppresses send_invite and send_reminder.
  - Multi-tenant IDOR: client_a → Globex interview/feedback pk → 404; Globex row unchanged;
           interview list / feedback list excludes other-tenant rows.
  - Authorization: non-admin member → interview_delete / interviewfeedback_delete → 403 and row
           survives; admin succeeds.
  - safe_external_url filter: javascript:/data:/empty → ""; http(s)://… pass through.
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# 3.7 Interview-specific fixtures
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
def interview_a(db, tenant_a, application_a, admin_user):
    """A scheduled Interview for tenant_a."""
    from apps.hrm.models import Interview
    return Interview.objects.create(
        tenant=tenant_a,
        application=application_a,
        title="Technical Round 1",
        round_number=1,
        mode="video",
        scheduled_at=timezone.now() + datetime.timedelta(days=3),
        duration_minutes=60,
        scheduled_by=admin_user,
    )


@pytest.fixture
def interview_b(db, tenant_b, application_b, admin_b):
    """A scheduled Interview for tenant_b (IDOR tests)."""
    from apps.hrm.models import Interview
    return Interview.objects.create(
        tenant=tenant_b,
        application=application_b,
        title="HR Screen",
        round_number=1,
        mode="phone",
        scheduled_at=timezone.now() + datetime.timedelta(days=5),
        duration_minutes=30,
        scheduled_by=admin_b,
    )


@pytest.fixture
def completed_interview_a(db, tenant_a, application_a, admin_user):
    """A completed (terminal) Interview for tenant_a."""
    from apps.hrm.models import Interview
    interview = Interview.objects.create(
        tenant=tenant_a,
        application=application_a,
        title="Completed Round",
        round_number=2,
        mode="in_person",
        scheduled_at=timezone.now() - datetime.timedelta(days=2),
        duration_minutes=90,
        scheduled_by=admin_user,
    )
    interview.status = "completed"
    interview.save(update_fields=["status", "updated_at"])
    return interview


@pytest.fixture
def panelist_a(db, tenant_a, interview_a, admin_user):
    """An InterviewPanelist for interview_a in tenant_a."""
    from apps.hrm.models import InterviewPanelist
    return InterviewPanelist.objects.create(
        tenant=tenant_a,
        interview=interview_a,
        interviewer=admin_user,
        role="lead",
    )


@pytest.fixture
def feedback_a(db, tenant_a, interview_a, panelist_a):
    """An InterviewFeedback (scorecard) for interview_a / panelist_a in tenant_a."""
    from apps.hrm.models import InterviewFeedback
    return InterviewFeedback.objects.create(
        tenant=tenant_a,
        interview=interview_a,
        panelist=panelist_a,
        overall_recommendation="yes",
        summary="Strong technical skills.",
    )


@pytest.fixture
def feedback_b(db, tenant_b, interview_b):
    """An InterviewFeedback for tenant_b (IDOR tests), panelist=None."""
    from apps.hrm.models import InterviewFeedback
    return InterviewFeedback.objects.create(
        tenant=tenant_b,
        interview=interview_b,
        panelist=None,
        overall_recommendation="maybe",
        summary="Needs more experience.",
    )


@pytest.fixture
def submitted_feedback_a(db, tenant_a, interview_a, panelist_a, admin_user):
    """A submitted InterviewFeedback for tenant_a."""
    from apps.hrm.models import InterviewFeedback
    fb = InterviewFeedback.objects.create(
        tenant=tenant_a,
        interview=interview_a,
        panelist=panelist_a,
        overall_recommendation="strong_yes",
        summary="Excellent.",
    )
    fb.is_submitted = True
    fb.submitted_at = timezone.now() - datetime.timedelta(hours=1)
    fb.submitted_by = admin_user
    fb.save(update_fields=["is_submitted", "submitted_at", "submitted_by", "updated_at"])
    return fb


# ============================================================
# Model Tests: Interview
# ============================================================

class TestInterviewModel:
    """INTV- prefix, auto-number per tenant, __str__, is_closed property."""

    def test_number_prefix(self, interview_a):
        assert interview_a.number.startswith("INTV-")

    def test_number_first_is_00001(self, interview_a):
        assert interview_a.number == "INTV-00001"

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b, application_a, application_b):
        """Each tenant's INTV counter starts at INTV-00001."""
        from apps.hrm.models import Interview
        i_a = Interview.objects.create(
            tenant=tenant_a, application=application_a, title="Round A", round_number=1,
            mode="video", scheduled_at=timezone.now() + datetime.timedelta(days=1))
        i_b = Interview.objects.create(
            tenant=tenant_b, application=application_b, title="Round B", round_number=1,
            mode="phone", scheduled_at=timezone.now() + datetime.timedelta(days=2))
        assert i_a.number == "INTV-00001"
        assert i_b.number == "INTV-00001"

    def test_str_includes_number_and_title(self, interview_a):
        s = str(interview_a)
        assert "INTV-00001" in s
        assert "Technical Round 1" in s

    def test_is_closed_false_for_scheduled(self, interview_a):
        assert interview_a.is_closed is False

    def test_is_closed_true_for_completed(self, completed_interview_a):
        assert completed_interview_a.is_closed is True

    def test_is_closed_true_for_cancelled(self, tenant_a, application_a):
        from apps.hrm.models import Interview
        interview = Interview.objects.create(
            tenant=tenant_a, application=application_a, title="Cancelled",
            round_number=1, mode="phone", scheduled_at=timezone.now())
        interview.status = "cancelled"
        interview.save(update_fields=["status", "updated_at"])
        assert interview.is_closed is True

    def test_is_closed_true_for_no_show(self, tenant_a, application_a):
        from apps.hrm.models import Interview
        interview = Interview.objects.create(
            tenant=tenant_a, application=application_a, title="No Show",
            round_number=1, mode="phone", scheduled_at=timezone.now())
        interview.status = "no_show"
        interview.save(update_fields=["status", "updated_at"])
        assert interview.is_closed is True

    def test_is_closed_false_for_rescheduled(self, tenant_a, application_a):
        """'rescheduled' is NOT a terminal status — it re-opens a closed round."""
        from apps.hrm.models import Interview
        interview = Interview.objects.create(
            tenant=tenant_a, application=application_a, title="Rescheduled",
            round_number=1, mode="phone", scheduled_at=timezone.now())
        interview.status = "rescheduled"
        interview.save(update_fields=["status", "updated_at"])
        assert interview.is_closed is False

    def test_candidate_property(self, interview_a, candidate_a):
        assert interview_a.candidate == candidate_a

    def test_requisition_property(self, interview_a, job_req_a):
        assert interview_a.requisition == job_req_a

    def test_unique_tenant_number(self, interview_a, tenant_a, application_a):
        """(tenant, number) unique constraint must reject a duplicate number."""
        from apps.hrm.models import Interview
        with pytest.raises(IntegrityError):
            Interview.objects.create(
                tenant=tenant_a,
                number=interview_a.number,  # same number for same tenant
                application=application_a,
                title="Duplicate Number",
                round_number=1,
                mode="video",
                scheduled_at=timezone.now() + datetime.timedelta(days=7),
            )


# ============================================================
# Model Tests: InterviewPanelist
# ============================================================

class TestInterviewPanelistModel:
    """unique_together (interview, interviewer), __str__."""

    def test_panelist_creation(self, panelist_a, admin_user):
        assert panelist_a.pk is not None
        assert panelist_a.interviewer == admin_user

    def test_str_includes_username(self, panelist_a, admin_user):
        s = str(panelist_a)
        # __str__ uses get_full_name() or username
        assert admin_user.username in s or "Lead Interviewer" in s

    def test_unique_interview_interviewer_raises(self, tenant_a, interview_a, panelist_a, admin_user):
        """A second panelist row with the same (interview, interviewer) must raise IntegrityError."""
        from apps.hrm.models import InterviewPanelist
        with pytest.raises(IntegrityError):
            InterviewPanelist.objects.create(
                tenant=tenant_a,
                interview=interview_a,
                interviewer=admin_user,  # same interviewer, same interview
                role="shadow",
            )

    def test_same_interviewer_different_interview_ok(self, db, tenant_a, application_a, admin_user, panelist_a):
        """Same interviewer can appear on a different interview."""
        from apps.hrm.models import Interview, InterviewPanelist
        interview2 = Interview.objects.create(
            tenant=tenant_a, application=application_a, title="Round 2",
            round_number=2, mode="video", scheduled_at=timezone.now() + datetime.timedelta(days=4))
        p2 = InterviewPanelist.objects.create(
            tenant=tenant_a, interview=interview2, interviewer=admin_user, role="interviewer")
        assert p2.pk != panelist_a.pk

    def test_rsvp_status_default_pending(self, panelist_a):
        assert panelist_a.rsvp_status == "pending"


# ============================================================
# Model Tests: InterviewFeedback
# ============================================================

class TestInterviewFeedbackModel:
    """IFB- prefix, unique (interview, panelist) for non-null panelists, multiple NULL panelists
    on one interview allowed, __str__."""

    def test_number_prefix(self, feedback_a):
        assert feedback_a.number.startswith("IFB-")

    def test_number_first_is_00001(self, feedback_a):
        assert feedback_a.number == "IFB-00001"

    def test_str_includes_number(self, feedback_a):
        s = str(feedback_a)
        assert "IFB-00001" in s

    def test_str_includes_recommendation_display(self, feedback_a):
        s = str(feedback_a)
        # overall_recommendation="yes" → "Yes"
        assert "Yes" in s

    def test_is_submitted_default_false(self, feedback_a):
        assert feedback_a.is_submitted is False

    def test_submitted_at_default_none(self, feedback_a):
        assert feedback_a.submitted_at is None

    def test_duplicate_non_null_panelist_raises(self, tenant_a, interview_a, panelist_a, feedback_a):
        """A second scorecard with the same non-null (interview, panelist) must raise IntegrityError."""
        from apps.hrm.models import InterviewFeedback
        with pytest.raises(IntegrityError):
            InterviewFeedback.objects.create(
                tenant=tenant_a,
                interview=interview_a,
                panelist=panelist_a,  # same panelist, same interview — duplicate
                overall_recommendation="no",
                summary="Different summary",
            )

    def test_multiple_null_panelists_allowed(self, tenant_a, interview_a):
        """Multiple null-panelist scorecards on the same interview must be accepted."""
        from apps.hrm.models import InterviewFeedback
        fb1 = InterviewFeedback.objects.create(
            tenant=tenant_a, interview=interview_a, panelist=None,
            overall_recommendation="yes", summary="First anon card")
        fb2 = InterviewFeedback.objects.create(
            tenant=tenant_a, interview=interview_a, panelist=None,
            overall_recommendation="maybe", summary="Second anon card")
        assert fb1.pk != fb2.pk

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b, interview_a, interview_b):
        """Each tenant's IFB counter starts at IFB-00001."""
        from apps.hrm.models import InterviewFeedback
        f_a = InterviewFeedback.objects.create(
            tenant=tenant_a, interview=interview_a, panelist=None, overall_recommendation="yes")
        f_b = InterviewFeedback.objects.create(
            tenant=tenant_b, interview=interview_b, panelist=None, overall_recommendation="no")
        assert f_a.number == "IFB-00001"
        assert f_b.number == "IFB-00001"


# ============================================================
# Model Tests: FeedbackCriterion
# ============================================================

class TestFeedbackCriterionModel:
    """clean() rejects rating 0 and 6, accepts 1..5, __str__."""

    def test_rating_zero_raises(self, tenant_a, feedback_a):
        from apps.hrm.models import FeedbackCriterion
        crit = FeedbackCriterion(
            tenant=tenant_a, feedback=feedback_a, criterion_name="Communication", rating=0)
        with pytest.raises(ValidationError) as exc_info:
            crit.clean()
        assert "rating" in exc_info.value.message_dict

    def test_rating_six_raises(self, tenant_a, feedback_a):
        from apps.hrm.models import FeedbackCriterion
        crit = FeedbackCriterion(
            tenant=tenant_a, feedback=feedback_a, criterion_name="Communication", rating=6)
        with pytest.raises(ValidationError) as exc_info:
            crit.clean()
        assert "rating" in exc_info.value.message_dict

    def test_rating_one_accepts(self, tenant_a, feedback_a):
        from apps.hrm.models import FeedbackCriterion
        crit = FeedbackCriterion(
            tenant=tenant_a, feedback=feedback_a, criterion_name="Attitude", rating=1)
        crit.clean()  # must not raise

    def test_rating_five_accepts(self, tenant_a, feedback_a):
        from apps.hrm.models import FeedbackCriterion
        crit = FeedbackCriterion(
            tenant=tenant_a, feedback=feedback_a, criterion_name="Coding", rating=5)
        crit.clean()  # must not raise

    def test_rating_three_accepts(self, tenant_a, feedback_a):
        from apps.hrm.models import FeedbackCriterion
        crit = FeedbackCriterion(
            tenant=tenant_a, feedback=feedback_a, criterion_name="Problem Solving", rating=3)
        crit.clean()  # must not raise

    def test_str_includes_name_and_rating(self, tenant_a, feedback_a):
        from apps.hrm.models import FeedbackCriterion
        crit = FeedbackCriterion.objects.create(
            tenant=tenant_a, feedback=feedback_a, criterion_name="Leadership", rating=4)
        assert "Leadership" in str(crit)
        assert "4" in str(crit)


# ============================================================
# Form Tests: InterviewForm
# ============================================================

class TestInterviewForm:
    """status/scheduled_by/reminder_sent_at not form fields; application queryset tenant-scoped."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import InterviewForm
        assert "status" not in InterviewForm.Meta.fields

    def test_scheduled_by_not_a_form_field(self):
        from apps.hrm.forms import InterviewForm
        assert "scheduled_by" not in InterviewForm.Meta.fields

    def test_reminder_sent_at_not_a_form_field(self):
        from apps.hrm.forms import InterviewForm
        assert "reminder_sent_at" not in InterviewForm.Meta.fields

    def test_feedback_reminder_sent_at_not_a_form_field(self):
        from apps.hrm.forms import InterviewForm
        assert "feedback_reminder_sent_at" not in InterviewForm.Meta.fields

    def test_application_queryset_tenant_scoped(self, tenant_a, application_a, application_b):
        """The application dropdown must only show tenant_a applications."""
        from apps.hrm.forms import InterviewForm
        form = InterviewForm(tenant=tenant_a)
        pks = list(form.fields["application"].queryset.values_list("pk", flat=True))
        assert application_a.pk in pks
        assert application_b.pk not in pks

    def test_valid_form_creates_interview(self, tenant_a, application_a):
        """A fully populated form should be valid."""
        from apps.hrm.forms import InterviewForm
        dt = timezone.now() + datetime.timedelta(days=2)
        form = InterviewForm({
            "application": application_a.pk,
            "title": "System Design Round",
            "round_number": 1,
            "mode": "video",
            "scheduled_at": dt.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": 60,
            "location": "",
            "video_provider": "",
            "meeting_url": "",
            "interviewer_instructions": "",
            "notes": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors


# ============================================================
# Form Tests: InterviewPanelistForm
# ============================================================

class TestInterviewPanelistForm:
    """interviewer queryset tenant-scoped; rsvp_status/notified_at not form fields."""

    def test_rsvp_status_not_a_form_field(self):
        from apps.hrm.forms import InterviewPanelistForm
        assert "rsvp_status" not in InterviewPanelistForm.Meta.fields

    def test_notified_at_not_a_form_field(self):
        from apps.hrm.forms import InterviewPanelistForm
        assert "notified_at" not in InterviewPanelistForm.Meta.fields

    def test_interviewer_queryset_tenant_scoped(self, tenant_a, admin_user, admin_b):
        """The interviewer dropdown must only show tenant_a users."""
        from apps.hrm.forms import InterviewPanelistForm
        form = InterviewPanelistForm(tenant=tenant_a)
        pks = list(form.fields["interviewer"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in pks
        assert admin_b.pk not in pks

    def test_cross_tenant_interviewer_rejected(self, tenant_a, admin_b):
        """Submitting a cross-tenant interviewer pk must fail validation."""
        from apps.hrm.forms import InterviewPanelistForm
        form = InterviewPanelistForm({
            "interviewer": admin_b.pk,
            "role": "interviewer",
            "briefing_notes": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "interviewer" in form.errors


# ============================================================
# Form Tests: InterviewFeedbackForm
# ============================================================

class TestInterviewFeedbackForm:
    """is_submitted/submitted_at/submitted_by not form fields; cross-interview panelist rejected."""

    def test_is_submitted_not_a_form_field(self):
        from apps.hrm.forms import InterviewFeedbackForm
        assert "is_submitted" not in InterviewFeedbackForm.Meta.fields

    def test_submitted_at_not_a_form_field(self):
        from apps.hrm.forms import InterviewFeedbackForm
        assert "submitted_at" not in InterviewFeedbackForm.Meta.fields

    def test_submitted_by_not_a_form_field(self):
        from apps.hrm.forms import InterviewFeedbackForm
        assert "submitted_by" not in InterviewFeedbackForm.Meta.fields

    def test_cross_interview_panelist_rejected(self, tenant_a, interview_a, application_a, admin_user):
        """A panelist belonging to interview_b being submitted against interview_a must fail clean()."""
        from apps.hrm.models import Interview, InterviewPanelist
        from apps.hrm.forms import InterviewFeedbackForm
        # Create a second interview with its own panelist
        interview2 = Interview.objects.create(
            tenant=tenant_a, application=application_a, title="Round 2",
            round_number=2, mode="phone", scheduled_at=timezone.now() + datetime.timedelta(days=5))
        panelist_on_interview2 = InterviewPanelist.objects.create(
            tenant=tenant_a, interview=interview2, interviewer=admin_user, role="interviewer")
        form = InterviewFeedbackForm({
            "interview": interview_a.pk,
            "panelist": panelist_on_interview2.pk,  # belongs to interview2, not interview_a
            "overall_recommendation": "yes",
            "summary": "Test",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "panelist" in form.errors

    def test_db_unique_constraint_rejects_duplicate_panelist(self, tenant_a, interview_a, panelist_a, feedback_a):
        """The DB unique_together (interview, panelist) must reject a second non-null scorecard."""
        from apps.hrm.models import InterviewFeedback
        with pytest.raises(IntegrityError):
            InterviewFeedback.objects.create(
                tenant=tenant_a,
                interview=interview_a,
                panelist=panelist_a,  # already has feedback_a
                overall_recommendation="strong_no",
                summary="Duplicate attempt",
            )

    def test_panelist_field_is_optional(self, tenant_a, interview_a):
        """A scorecard with no panelist is valid (anon/unassigned card)."""
        from apps.hrm.forms import InterviewFeedbackForm
        form = InterviewFeedbackForm({
            "interview": interview_a.pk,
            "panelist": "",
            "overall_recommendation": "maybe",
            "summary": "Anonymous review",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors


# ============================================================
# Form Tests: FeedbackCriterionForm
# ============================================================

class TestFeedbackCriterionForm:
    """rating 1-5 validated; 0 and 6 rejected."""

    def test_rating_one_valid(self, tenant_a):
        from apps.hrm.forms import FeedbackCriterionForm
        form = FeedbackCriterionForm({
            "criterion_name": "Communication", "rating": 1, "notes": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_rating_five_valid(self, tenant_a):
        from apps.hrm.forms import FeedbackCriterionForm
        form = FeedbackCriterionForm({
            "criterion_name": "Coding", "rating": 5, "notes": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_rating_zero_invalid(self, tenant_a):
        from apps.hrm.forms import FeedbackCriterionForm
        form = FeedbackCriterionForm({
            "criterion_name": "Attitude", "rating": 0, "notes": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "rating" in form.errors

    def test_rating_six_invalid(self, tenant_a):
        from apps.hrm.forms import FeedbackCriterionForm
        form = FeedbackCriterionForm({
            "criterion_name": "Attitude", "rating": 6, "notes": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "rating" in form.errors

    def test_missing_criterion_name_invalid(self, tenant_a):
        from apps.hrm.forms import FeedbackCriterionForm
        form = FeedbackCriterionForm({
            "criterion_name": "", "rating": 3, "notes": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "criterion_name" in form.errors


# ============================================================
# View Tests: Interview CRUD
# ============================================================

class TestInterviewListView:
    """List page returns 200 + tenant isolation."""

    def test_list_200(self, client_a, interview_a):
        resp = client_a.get(reverse("hrm:interview_list"))
        assert resp.status_code == 200

    def test_list_contains_tenant_a_interview(self, client_a, interview_a):
        resp = client_a.get(reverse("hrm:interview_list"))
        # Use the unique title (not the number, which both tenants start at INTV-00001)
        assert interview_a.title.encode() in resp.content

    def test_list_excludes_tenant_b_interview(self, client_a, interview_a, interview_b):
        resp = client_a.get(reverse("hrm:interview_list"))
        # Use the unique title to discriminate; "HR Screen" is interview_b's title
        assert interview_b.title.encode() not in resp.content

    def test_anon_redirects(self):
        from django.test import Client
        c = Client()
        resp = c.get(reverse("hrm:interview_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestInterviewCreateView:
    """POST creates an Interview with the request tenant and scheduled_by=request.user."""

    def test_post_creates_interview(self, client_a, tenant_a, application_a):
        from apps.hrm.models import Interview
        dt = timezone.now() + datetime.timedelta(days=3)
        resp = client_a.post(reverse("hrm:interview_create"), {
            "application": application_a.pk,
            "title": "New Interview",
            "round_number": 1,
            "mode": "video",
            "scheduled_at": dt.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": 45,
            "location": "",
            "video_provider": "",
            "meeting_url": "",
            "interviewer_instructions": "",
            "notes": "",
        })
        assert resp.status_code == 302
        assert Interview.objects.filter(tenant=tenant_a, title="New Interview").exists()

    def test_post_sets_scheduled_by(self, client_a, tenant_a, application_a, admin_user):
        from apps.hrm.models import Interview
        dt = timezone.now() + datetime.timedelta(days=3)
        client_a.post(reverse("hrm:interview_create"), {
            "application": application_a.pk,
            "title": "Scheduled By Test",
            "round_number": 1,
            "mode": "video",
            "scheduled_at": dt.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": 60,
            "location": "",
            "video_provider": "",
            "meeting_url": "",
            "interviewer_instructions": "",
            "notes": "",
        })
        interview = Interview.objects.filter(tenant=tenant_a, title="Scheduled By Test").first()
        assert interview is not None
        assert interview.scheduled_by == admin_user

    def test_post_redirects_to_detail(self, client_a, tenant_a, application_a):
        from apps.hrm.models import Interview
        dt = timezone.now() + datetime.timedelta(days=3)
        resp = client_a.post(reverse("hrm:interview_create"), {
            "application": application_a.pk,
            "title": "Redirect Test",
            "round_number": 1,
            "mode": "video",
            "scheduled_at": dt.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": 60,
            "location": "",
            "video_provider": "",
            "meeting_url": "",
            "interviewer_instructions": "",
            "notes": "",
        })
        assert resp.status_code == 302
        interview = Interview.objects.filter(tenant=tenant_a, title="Redirect Test").first()
        assert interview is not None
        assert reverse("hrm:interview_detail", args=[interview.pk]) in resp["Location"]


class TestInterviewDetailView:
    """Detail page 200; IDOR 404; expected context keys present."""

    def test_detail_200(self, client_a, interview_a):
        resp = client_a.get(reverse("hrm:interview_detail", args=[interview_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, interview_a):
        resp = client_a.get(reverse("hrm:interview_detail", args=[interview_a.pk]))
        assert resp.context["obj"] == interview_a

    def test_detail_context_has_panelists(self, client_a, interview_a):
        resp = client_a.get(reverse("hrm:interview_detail", args=[interview_a.pk]))
        assert "panelists" in resp.context

    def test_detail_context_has_feedback_entries(self, client_a, interview_a):
        resp = client_a.get(reverse("hrm:interview_detail", args=[interview_a.pk]))
        assert "feedback_entries" in resp.context

    def test_detail_idor_404(self, client_a, interview_b):
        resp = client_a.get(reverse("hrm:interview_detail", args=[interview_b.pk]))
        assert resp.status_code == 404


class TestInterviewEditView:
    """Edit view 200; POST updates and preserves status."""

    def test_edit_get_200(self, client_a, interview_a):
        resp = client_a.get(reverse("hrm:interview_edit", args=[interview_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_title(self, client_a, interview_a):
        dt = timezone.now() + datetime.timedelta(days=4)
        resp = client_a.post(reverse("hrm:interview_edit", args=[interview_a.pk]), {
            "application": interview_a.application.pk,
            "title": "Updated Title",
            "round_number": 1,
            "mode": "in_person",
            "scheduled_at": dt.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": 90,
            "location": "Conference Room A",
            "video_provider": "",
            "meeting_url": "",
            "interviewer_instructions": "",
            "notes": "",
        })
        assert resp.status_code == 302
        interview_a.refresh_from_db()
        assert interview_a.title == "Updated Title"

    def test_edit_preserves_status(self, client_a, interview_a):
        """Editing must not change the interview status (status is not a form field)."""
        original_status = interview_a.status
        dt = timezone.now() + datetime.timedelta(days=4)
        client_a.post(reverse("hrm:interview_edit", args=[interview_a.pk]), {
            "application": interview_a.application.pk,
            "title": "Edited Title",
            "round_number": 1,
            "mode": "video",
            "scheduled_at": dt.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": 60,
            "location": "",
            "video_provider": "",
            "meeting_url": "",
            "interviewer_instructions": "",
            "notes": "",
        })
        interview_a.refresh_from_db()
        assert interview_a.status == original_status


# ============================================================
# View Tests: Interview Status Machine
# ============================================================

class TestInterviewStatusMachine:
    """Status transitions: scheduled→confirmed→in_progress→completed; cancel/no_show; terminal guard."""

    def test_confirm_transitions_to_confirmed(self, client_a, interview_a):
        resp = client_a.post(reverse("hrm:interview_confirm", args=[interview_a.pk]))
        assert resp.status_code == 302
        interview_a.refresh_from_db()
        assert interview_a.status == "confirmed"

    def test_start_transitions_to_in_progress(self, client_a, interview_a):
        client_a.post(reverse("hrm:interview_confirm", args=[interview_a.pk]))
        resp = client_a.post(reverse("hrm:interview_start", args=[interview_a.pk]))
        assert resp.status_code == 302
        interview_a.refresh_from_db()
        assert interview_a.status == "in_progress"

    def test_complete_transitions_to_completed(self, client_a, interview_a):
        resp = client_a.post(reverse("hrm:interview_complete", args=[interview_a.pk]))
        assert resp.status_code == 302
        interview_a.refresh_from_db()
        assert interview_a.status == "completed"

    def test_cancel_transitions_to_cancelled(self, client_a, interview_a):
        resp = client_a.post(reverse("hrm:interview_cancel", args=[interview_a.pk]))
        assert resp.status_code == 302
        interview_a.refresh_from_db()
        assert interview_a.status == "cancelled"

    def test_no_show_transitions_to_no_show(self, client_a, interview_a):
        resp = client_a.post(reverse("hrm:interview_no_show", args=[interview_a.pk]))
        assert resp.status_code == 302
        interview_a.refresh_from_db()
        assert interview_a.status == "no_show"

    def test_terminal_guard_blocks_confirm_on_completed(self, client_a, completed_interview_a):
        """confirm must not transition a completed (terminal) interview."""
        resp = client_a.post(reverse("hrm:interview_confirm", args=[completed_interview_a.pk]))
        assert resp.status_code == 302
        completed_interview_a.refresh_from_db()
        assert completed_interview_a.status == "completed"  # unchanged

    def test_terminal_guard_blocks_complete_on_completed(self, client_a, completed_interview_a):
        """complete must not re-apply to an already completed interview."""
        resp = client_a.post(reverse("hrm:interview_complete", args=[completed_interview_a.pk]))
        assert resp.status_code == 302
        completed_interview_a.refresh_from_db()
        assert completed_interview_a.status == "completed"

    def test_terminal_guard_blocks_cancel_on_completed(self, client_a, completed_interview_a):
        """cancel on a completed interview must be rejected (stays completed)."""
        resp = client_a.post(reverse("hrm:interview_cancel", args=[completed_interview_a.pk]))
        assert resp.status_code == 302
        completed_interview_a.refresh_from_db()
        assert completed_interview_a.status == "completed"

    def test_terminal_guard_blocks_no_show_on_cancelled(self, client_a, tenant_a, application_a):
        """no_show on a cancelled interview must be rejected."""
        from apps.hrm.models import Interview
        interview = Interview.objects.create(
            tenant=tenant_a, application=application_a, title="Cancelled Interview",
            round_number=1, mode="video", scheduled_at=timezone.now())
        interview.status = "cancelled"
        interview.save(update_fields=["status", "updated_at"])

        client_a.post(reverse("hrm:interview_no_show", args=[interview.pk]))
        interview.refresh_from_db()
        assert interview.status == "cancelled"  # unchanged


class TestInterviewReschedule:
    """Reschedule reopens a terminal interview; invalid datetime returns error."""

    def test_reschedule_completed_interview_to_rescheduled(self, client_a, completed_interview_a):
        """A completed interview can be rescheduled — status becomes 'rescheduled'."""
        new_dt = timezone.now() + datetime.timedelta(days=7)
        resp = client_a.post(reverse("hrm:interview_reschedule", args=[completed_interview_a.pk]), {
            "scheduled_at": new_dt.strftime("%Y-%m-%dT%H:%M"),
        })
        assert resp.status_code == 302
        completed_interview_a.refresh_from_db()
        assert completed_interview_a.status == "rescheduled"

    def test_reschedule_updates_scheduled_at(self, client_a, completed_interview_a):
        new_dt = timezone.now() + datetime.timedelta(days=8)
        client_a.post(reverse("hrm:interview_reschedule", args=[completed_interview_a.pk]), {
            "scheduled_at": new_dt.strftime("%Y-%m-%dT%H:%M"),
        })
        completed_interview_a.refresh_from_db()
        # Check that scheduled_at was updated (it should be very close to new_dt)
        diff = abs((completed_interview_a.scheduled_at - new_dt).total_seconds())
        assert diff < 120  # within 2 minutes (timezone offset at most)

    def test_reschedule_invalid_datetime_no_change(self, client_a, completed_interview_a):
        """An empty/invalid datetime must leave the interview unchanged."""
        original_status = completed_interview_a.status
        original_scheduled_at = completed_interview_a.scheduled_at
        resp = client_a.post(reverse("hrm:interview_reschedule", args=[completed_interview_a.pk]), {
            "scheduled_at": "",
        })
        assert resp.status_code == 302
        completed_interview_a.refresh_from_db()
        assert completed_interview_a.status == original_status
        assert completed_interview_a.scheduled_at == original_scheduled_at

    def test_reschedule_non_terminal_interview_works(self, client_a, interview_a):
        """A non-terminal interview can also be rescheduled."""
        new_dt = timezone.now() + datetime.timedelta(days=10)
        resp = client_a.post(reverse("hrm:interview_reschedule", args=[interview_a.pk]), {
            "scheduled_at": new_dt.strftime("%Y-%m-%dT%H:%M"),
        })
        assert resp.status_code == 302
        interview_a.refresh_from_db()
        assert interview_a.status == "rescheduled"


# ============================================================
# View Tests: Panelist Add / Remove / RSVP
# ============================================================

class TestInterviewPanelistViews:
    """Add/remove/rsvp panelist actions."""

    def test_panelist_add_creates_row(self, client_a, tenant_a, interview_a, admin_user):
        from apps.hrm.models import InterviewPanelist
        before = InterviewPanelist.objects.filter(tenant=tenant_a, interview=interview_a).count()
        resp = client_a.post(reverse("hrm:interview_panelist_add", args=[interview_a.pk]), {
            "interviewer": admin_user.pk,
            "role": "lead",
            "briefing_notes": "",
        })
        assert resp.status_code == 302
        after = InterviewPanelist.objects.filter(tenant=tenant_a, interview=interview_a).count()
        assert after == before + 1

    def test_panelist_add_duplicate_is_idempotent(self, client_a, tenant_a, interview_a,
                                                    admin_user, panelist_a):
        """Adding the same interviewer twice must not create a second row."""
        from apps.hrm.models import InterviewPanelist
        before = InterviewPanelist.objects.filter(tenant=tenant_a, interview=interview_a).count()
        client_a.post(reverse("hrm:interview_panelist_add", args=[interview_a.pk]), {
            "interviewer": admin_user.pk,
            "role": "interviewer",  # different role — still same person
            "briefing_notes": "",
        })
        after = InterviewPanelist.objects.filter(tenant=tenant_a, interview=interview_a).count()
        assert after == before  # get_or_create prevents duplication

    def test_panelist_remove_deletes_row(self, client_a, tenant_a, interview_a, panelist_a):
        from apps.hrm.models import InterviewPanelist
        resp = client_a.post(reverse("hrm:interview_panelist_remove",
                                     args=[interview_a.pk, panelist_a.pk]))
        assert resp.status_code == 302
        assert not InterviewPanelist.objects.filter(pk=panelist_a.pk).exists()

    def test_panelist_rsvp_updates_status(self, client_a, interview_a, panelist_a):
        resp = client_a.post(reverse("hrm:interview_panelist_rsvp",
                                     args=[interview_a.pk, panelist_a.pk]), {
            "rsvp_status": "accepted",
        })
        assert resp.status_code == 302
        panelist_a.refresh_from_db()
        assert panelist_a.rsvp_status == "accepted"

    def test_panelist_rsvp_invalid_value_no_change(self, client_a, interview_a, panelist_a):
        resp = client_a.post(reverse("hrm:interview_panelist_rsvp",
                                     args=[interview_a.pk, panelist_a.pk]), {
            "rsvp_status": "not_a_real_status",
        })
        assert resp.status_code == 302
        panelist_a.refresh_from_db()
        assert panelist_a.rsvp_status == "pending"  # unchanged


# ============================================================
# View Tests: Interview Feedback CRUD + Submit
# ============================================================

class TestInterviewFeedbackListView:
    """Feedback list 200 + tenant isolation."""

    def test_list_200(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:interviewfeedback_list"))
        assert resp.status_code == 200

    def test_list_contains_tenant_a_feedback(self, client_a, feedback_a, candidate_a):
        resp = client_a.get(reverse("hrm:interviewfeedback_list"))
        # The list shows candidate.name (not the summary); use that as the discriminating field
        assert candidate_a.name.encode() in resp.content

    def test_list_excludes_tenant_b_feedback(self, client_a, feedback_a, feedback_b, candidate_b):
        resp = client_a.get(reverse("hrm:interviewfeedback_list"))
        # candidate_b.name is unique to tenant_b and must not appear in tenant_a's list
        assert candidate_b.name.encode() not in resp.content


class TestInterviewFeedbackCreateView:
    """POST creates a feedback entry."""

    def test_post_creates_feedback(self, client_a, tenant_a, interview_a, panelist_a):
        from apps.hrm.models import InterviewFeedback
        before = InterviewFeedback.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:interviewfeedback_create"), {
            "interview": interview_a.pk,
            "panelist": panelist_a.pk,
            "overall_recommendation": "maybe",
            "summary": "Decent candidate.",
        })
        assert resp.status_code == 302
        after = InterviewFeedback.objects.filter(tenant=tenant_a).count()
        assert after == before + 1

    def test_post_redirects_to_detail(self, client_a, tenant_a, interview_a):
        from apps.hrm.models import InterviewFeedback
        resp = client_a.post(reverse("hrm:interviewfeedback_create"), {
            "interview": interview_a.pk,
            "panelist": "",  # anonymous card
            "overall_recommendation": "yes",
            "summary": "Good fit.",
        })
        assert resp.status_code == 302
        fb = InterviewFeedback.objects.filter(tenant=tenant_a, interview=interview_a).first()
        assert fb is not None
        assert reverse("hrm:interviewfeedback_detail", args=[fb.pk]) in resp["Location"]

    def test_post_starts_as_not_submitted(self, client_a, tenant_a, interview_a):
        """A newly created scorecard must have is_submitted=False."""
        from apps.hrm.models import InterviewFeedback
        client_a.post(reverse("hrm:interviewfeedback_create"), {
            "interview": interview_a.pk,
            "panelist": "",
            "overall_recommendation": "no",
            "summary": "Not ready.",
        })
        fb = InterviewFeedback.objects.filter(tenant=tenant_a, interview=interview_a).first()
        assert fb is not None
        assert fb.is_submitted is False


class TestInterviewFeedbackDetailView:
    """Detail 200; IDOR 404."""

    def test_detail_200(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:interviewfeedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:interviewfeedback_detail", args=[feedback_a.pk]))
        assert resp.context["obj"] == feedback_a

    def test_detail_idor_404(self, client_a, feedback_b):
        resp = client_a.get(reverse("hrm:interviewfeedback_detail", args=[feedback_b.pk]))
        assert resp.status_code == 404


class TestInterviewFeedbackSubmit:
    """interviewfeedback_submit stamps is_submitted/submitted_at/submitted_by; idempotent."""

    def test_submit_sets_is_submitted(self, client_a, feedback_a):
        resp = client_a.post(reverse("hrm:interviewfeedback_submit", args=[feedback_a.pk]))
        assert resp.status_code == 302
        feedback_a.refresh_from_db()
        assert feedback_a.is_submitted is True

    def test_submit_stamps_submitted_at(self, client_a, feedback_a):
        client_a.post(reverse("hrm:interviewfeedback_submit", args=[feedback_a.pk]))
        feedback_a.refresh_from_db()
        assert feedback_a.submitted_at is not None

    def test_submit_stamps_submitted_by(self, client_a, feedback_a, admin_user):
        client_a.post(reverse("hrm:interviewfeedback_submit", args=[feedback_a.pk]))
        feedback_a.refresh_from_db()
        assert feedback_a.submitted_by == admin_user

    def test_submit_idempotent(self, client_a, submitted_feedback_a):
        """Submitting an already-submitted scorecard must not change submitted_at/submitted_by."""
        original_submitted_at = submitted_feedback_a.submitted_at
        original_submitted_by = submitted_feedback_a.submitted_by
        client_a.post(reverse("hrm:interviewfeedback_submit", args=[submitted_feedback_a.pk]))
        submitted_feedback_a.refresh_from_db()
        assert submitted_feedback_a.submitted_at == original_submitted_at
        assert submitted_feedback_a.submitted_by == original_submitted_by


class TestEditCannotUnsubmitScorecard:
    """Edit POST on a submitted scorecard cannot un-submit it (is_submitted not a form field).

    This is coverage gap #1 explicitly flagged in the code review.
    """

    def test_edit_keeps_is_submitted_true(self, client_a, submitted_feedback_a, interview_a, panelist_a):
        """Posting to interviewfeedback_edit with different data must keep is_submitted=True."""
        resp = client_a.post(
            reverse("hrm:interviewfeedback_edit", args=[submitted_feedback_a.pk]), {
                "interview": interview_a.pk,
                "panelist": panelist_a.pk,
                "overall_recommendation": "no",  # changed
                "summary": "Actually no after reflection.",  # changed
            })
        assert resp.status_code == 302
        submitted_feedback_a.refresh_from_db()
        assert submitted_feedback_a.is_submitted is True

    def test_edit_keeps_submitted_at_unchanged(self, client_a, submitted_feedback_a,
                                                interview_a, panelist_a):
        original_at = submitted_feedback_a.submitted_at
        client_a.post(
            reverse("hrm:interviewfeedback_edit", args=[submitted_feedback_a.pk]), {
                "interview": interview_a.pk,
                "panelist": panelist_a.pk,
                "overall_recommendation": "strong_no",
                "summary": "On reflection, strong no.",
            })
        submitted_feedback_a.refresh_from_db()
        assert submitted_feedback_a.submitted_at == original_at

    def test_edit_keeps_submitted_by_unchanged(self, client_a, submitted_feedback_a,
                                                interview_a, panelist_a, admin_user):
        client_a.post(
            reverse("hrm:interviewfeedback_edit", args=[submitted_feedback_a.pk]), {
                "interview": interview_a.pk,
                "panelist": panelist_a.pk,
                "overall_recommendation": "no",
                "summary": "Changed again.",
            })
        submitted_feedback_a.refresh_from_db()
        assert submitted_feedback_a.submitted_by == admin_user


# ============================================================
# View Tests: FeedbackCriterion Add / Delete
# ============================================================

class TestFeedbackCriterionViews:
    """feedbackcriterion_add (valid + invalid rating) and feedbackcriterion_delete."""

    def test_criterion_add_creates_row(self, client_a, tenant_a, feedback_a):
        from apps.hrm.models import FeedbackCriterion
        before = FeedbackCriterion.objects.filter(tenant=tenant_a, feedback=feedback_a).count()
        resp = client_a.post(
            reverse("hrm:feedbackcriterion_add", args=[feedback_a.pk]), {
                "criterion_name": "Communication",
                "rating": 4,
                "notes": "Clear and concise",
            })
        assert resp.status_code == 302
        after = FeedbackCriterion.objects.filter(tenant=tenant_a, feedback=feedback_a).count()
        assert after == before + 1

    def test_criterion_add_invalid_rating_no_row_created(self, client_a, tenant_a, feedback_a):
        """An invalid rating (6) must not create a FeedbackCriterion row."""
        from apps.hrm.models import FeedbackCriterion
        before = FeedbackCriterion.objects.filter(tenant=tenant_a, feedback=feedback_a).count()
        resp = client_a.post(
            reverse("hrm:feedbackcriterion_add", args=[feedback_a.pk]), {
                "criterion_name": "Out of Range",
                "rating": 6,
                "notes": "",
            })
        assert resp.status_code == 302  # view still redirects (with error message)
        after = FeedbackCriterion.objects.filter(tenant=tenant_a, feedback=feedback_a).count()
        assert after == before  # no row created

    def test_criterion_add_zero_rating_no_row_created(self, client_a, tenant_a, feedback_a):
        """An invalid rating (0) must not create a FeedbackCriterion row."""
        from apps.hrm.models import FeedbackCriterion
        before = FeedbackCriterion.objects.filter(tenant=tenant_a, feedback=feedback_a).count()
        client_a.post(
            reverse("hrm:feedbackcriterion_add", args=[feedback_a.pk]), {
                "criterion_name": "Zero",
                "rating": 0,
                "notes": "",
            })
        after = FeedbackCriterion.objects.filter(tenant=tenant_a, feedback=feedback_a).count()
        assert after == before

    def test_criterion_delete_removes_row(self, client_a, tenant_a, feedback_a):
        from apps.hrm.models import FeedbackCriterion
        crit = FeedbackCriterion.objects.create(
            tenant=tenant_a, feedback=feedback_a, criterion_name="Leadership", rating=3)
        resp = client_a.post(
            reverse("hrm:feedbackcriterion_delete", args=[feedback_a.pk, crit.pk]))
        assert resp.status_code == 302
        assert not FeedbackCriterion.objects.filter(pk=crit.pk).exists()


# ============================================================
# Email / Communication Tests
# ============================================================

class TestInterviewSendReminderNoTemplate:
    """_send_interview_email with no matching CandidateEmailTemplate still logs a
    CandidateCommunication from the fallback _interview_detail_lines body.
    This is coverage gap #4 explicitly flagged in the code review.
    """

    def test_no_template_still_logs_communication(self, client_a, tenant_a, interview_a):
        """With no 'interview_reminder' template, send_reminder must still create a CC row."""
        from apps.hrm.models import CandidateCommunication
        # Ensure NO interview_reminder template exists for tenant_a
        from apps.hrm.models import CandidateEmailTemplate
        CandidateEmailTemplate.objects.filter(tenant=tenant_a, template_type="interview_reminder").delete()

        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:interview_send_reminder", args=[interview_a.pk]))
        assert resp.status_code == 302
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1

    def test_no_template_stamps_reminder_sent_at(self, client_a, interview_a):
        """With no template, send_reminder must still stamp reminder_sent_at."""
        from apps.hrm.models import CandidateEmailTemplate
        CandidateEmailTemplate.objects.filter(
            tenant=interview_a.tenant, template_type="interview_reminder").delete()

        client_a.post(reverse("hrm:interview_send_reminder", args=[interview_a.pk]))
        interview_a.refresh_from_db()
        assert interview_a.reminder_sent_at is not None

    def test_no_template_fallback_body_contains_interview_title(self, client_a, tenant_a, interview_a):
        """The CC logged without a template must include the interview title in its body."""
        from apps.hrm.models import CandidateCommunication, CandidateEmailTemplate
        CandidateEmailTemplate.objects.filter(tenant=tenant_a, template_type="interview_reminder").delete()

        client_a.post(reverse("hrm:interview_send_reminder", args=[interview_a.pk]))
        cc = CandidateCommunication.objects.filter(tenant=tenant_a).order_by("-pk").first()
        assert cc is not None
        assert interview_a.title in cc.body

    def test_no_invite_template_still_logs_communication(self, client_a, tenant_a, interview_a):
        """With no 'interview_invite' template, send_invite must still create a CC row."""
        from apps.hrm.models import CandidateCommunication, CandidateEmailTemplate
        CandidateEmailTemplate.objects.filter(tenant=tenant_a, template_type="interview_invite").delete()

        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:interview_send_invite", args=[interview_a.pk]))
        assert resp.status_code == 302
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before + 1


class TestDoNotContactSuppression:
    """do_not_contact=True suppresses send_invite and send_reminder.
    This is coverage gap #7 — mirrors the 3.6 application_send_email suppression tests.
    """

    def test_send_invite_do_not_contact_no_communication(self, client_a, tenant_a,
                                                          interview_a, candidate_a):
        from apps.hrm.models import CandidateCommunication
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])

        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:interview_send_invite", args=[interview_a.pk]))
        assert resp.status_code == 302
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before  # do_not_contact blocks the email

    def test_send_reminder_do_not_contact_no_communication(self, client_a, tenant_a,
                                                            interview_a, candidate_a):
        from apps.hrm.models import CandidateCommunication
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])

        before = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:interview_send_reminder", args=[interview_a.pk]))
        assert resp.status_code == 302
        after = CandidateCommunication.objects.filter(tenant=tenant_a).count()
        assert after == before

    def test_send_reminder_do_not_contact_does_not_stamp_reminder_sent_at(
            self, client_a, interview_a, candidate_a):
        """do_not_contact must prevent reminder_sent_at from being stamped."""
        candidate_a.do_not_contact = True
        candidate_a.save(update_fields=["do_not_contact", "updated_at"])

        client_a.post(reverse("hrm:interview_send_reminder", args=[interview_a.pk]))
        interview_a.refresh_from_db()
        assert interview_a.reminder_sent_at is None


# ============================================================
# Multi-tenant IDOR Tests
# ============================================================

class TestInterviewIDOR:
    """Tenant-A admin requesting Tenant-B objects must receive 404."""

    def test_interview_detail_idor_404(self, client_a, interview_b):
        resp = client_a.get(reverse("hrm:interview_detail", args=[interview_b.pk]))
        assert resp.status_code == 404

    def test_interview_edit_idor_404(self, client_a, interview_b):
        resp = client_a.get(reverse("hrm:interview_edit", args=[interview_b.pk]))
        assert resp.status_code == 404

    def test_interview_confirm_idor_404(self, client_a, interview_b):
        resp = client_a.post(reverse("hrm:interview_confirm", args=[interview_b.pk]))
        assert resp.status_code == 404

    def test_interview_complete_idor_404(self, client_a, interview_b):
        resp = client_a.post(reverse("hrm:interview_complete", args=[interview_b.pk]))
        assert resp.status_code == 404

    def test_interview_reschedule_idor_404(self, client_a, interview_b):
        new_dt = timezone.now() + datetime.timedelta(days=10)
        resp = client_a.post(reverse("hrm:interview_reschedule", args=[interview_b.pk]), {
            "scheduled_at": new_dt.strftime("%Y-%m-%dT%H:%M"),
        })
        assert resp.status_code == 404

    def test_interview_send_invite_idor_404(self, client_a, interview_b):
        resp = client_a.post(reverse("hrm:interview_send_invite", args=[interview_b.pk]))
        assert resp.status_code == 404

    def test_interview_send_reminder_idor_404(self, client_a, interview_b):
        resp = client_a.post(reverse("hrm:interview_send_reminder", args=[interview_b.pk]))
        assert resp.status_code == 404

    def test_interviewfeedback_detail_idor_404(self, client_a, feedback_b):
        resp = client_a.get(reverse("hrm:interviewfeedback_detail", args=[feedback_b.pk]))
        assert resp.status_code == 404

    def test_interviewfeedback_edit_idor_404(self, client_a, feedback_b):
        resp = client_a.get(reverse("hrm:interviewfeedback_edit", args=[feedback_b.pk]))
        assert resp.status_code == 404

    def test_interviewfeedback_submit_idor_404(self, client_a, feedback_b):
        resp = client_a.post(reverse("hrm:interviewfeedback_submit", args=[feedback_b.pk]))
        assert resp.status_code == 404

    def test_interview_b_status_unchanged_after_idor_attempt(self, client_a, interview_b):
        """Attempted cross-tenant complete must not change interview_b's status."""
        resp = client_a.post(reverse("hrm:interview_complete", args=[interview_b.pk]))
        assert resp.status_code == 404
        interview_b.refresh_from_db()
        assert interview_b.status == "scheduled"  # unchanged

    def test_interview_list_excludes_tenant_b(self, client_a, interview_a, interview_b):
        resp = client_a.get(reverse("hrm:interview_list"))
        assert resp.status_code == 200
        # Use unique titles rather than auto-numbers (both tenants start at INTV-00001)
        assert interview_a.title.encode() in resp.content
        assert interview_b.title.encode() not in resp.content

    def test_feedback_list_excludes_tenant_b(self, client_a, feedback_a, feedback_b,
                                              candidate_a, candidate_b):
        resp = client_a.get(reverse("hrm:interviewfeedback_list"))
        assert resp.status_code == 200
        # The list shows candidate names; use those as discriminating fields
        assert candidate_a.name.encode() in resp.content
        assert candidate_b.name.encode() not in resp.content


# ============================================================
# Authorization Tests (@tenant_admin_required on deletes)
# ============================================================

class TestInterviewDeleteAuthorization:
    """Non-admin member → interview_delete → 403; row survives. Admin succeeds."""

    def test_nonmember_interview_delete_403(self, member_client, interview_a):
        from apps.hrm.models import Interview
        resp = member_client.post(reverse("hrm:interview_delete", args=[interview_a.pk]))
        assert resp.status_code == 403
        # Row must still exist
        assert Interview.objects.filter(pk=interview_a.pk).exists()

    def test_admin_interview_delete_succeeds(self, client_a, interview_a):
        from apps.hrm.models import Interview
        pk = interview_a.pk
        resp = client_a.post(reverse("hrm:interview_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Interview.objects.filter(pk=pk).exists()

    def test_nonmember_interviewfeedback_delete_403(self, member_client, feedback_a):
        from apps.hrm.models import InterviewFeedback
        resp = member_client.post(reverse("hrm:interviewfeedback_delete", args=[feedback_a.pk]))
        assert resp.status_code == 403
        assert InterviewFeedback.objects.filter(pk=feedback_a.pk).exists()

    def test_admin_interviewfeedback_delete_succeeds(self, client_a, feedback_a):
        from apps.hrm.models import InterviewFeedback
        pk = feedback_a.pk
        resp = client_a.post(reverse("hrm:interviewfeedback_delete", args=[pk]))
        assert resp.status_code == 302
        assert not InterviewFeedback.objects.filter(pk=pk).exists()

    def test_interview_delete_get_blocked(self, client_a, interview_a):
        """interview_delete is @require_POST — GET must return 405."""
        resp = client_a.get(reverse("hrm:interview_delete", args=[interview_a.pk]))
        assert resp.status_code == 405


# ============================================================
# safe_external_url filter unit tests (apps/core/templatetags/safe_url.py)
# ============================================================

class TestSafeExternalUrlFilter:
    """javascript:/data:/empty → ""; http(s)://… pass through."""

    def _call(self, value):
        from apps.core.templatetags.safe_url import safe_external_url
        return safe_external_url(value)

    def test_javascript_scheme_returns_empty(self):
        assert self._call("javascript:alert(1)") == ""

    def test_javascript_scheme_uppercase_returns_empty(self):
        assert self._call("JAVASCRIPT:alert(1)") == ""

    def test_data_scheme_returns_empty(self):
        assert self._call("data:text/html,<script>alert(1)</script>") == ""

    def test_empty_string_returns_empty(self):
        assert self._call("") == ""

    def test_none_returns_empty(self):
        assert self._call(None) == ""

    def test_http_url_passes_through(self):
        url = "http://example.com/meeting/123"
        assert self._call(url) == url

    def test_https_url_passes_through(self):
        url = "https://zoom.us/j/123456789"
        assert self._call(url) == url

    def test_ftp_scheme_returns_empty(self):
        """ftp:// is not http/https — must be blocked."""
        assert self._call("ftp://files.example.com/secret") == ""

    def test_vbscript_returns_empty(self):
        assert self._call("vbscript:msgbox(1)") == ""

    def test_whitespace_padded_javascript_returns_empty(self):
        """A URL with leading whitespace before 'javascript:' should still be blocked."""
        # The filter strips the value before lowercasing
        assert self._call("  javascript:alert(1)") == ""
