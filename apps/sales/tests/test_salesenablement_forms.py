"""Sub-module 8.9 Sales Enablement -- form test suite.

Covers:
1. EnablementContentForm:
   - Valid submission saves cleanly (create & edit).
   - Required fields and form validation.
   - Foreign key dropdowns are tenant-scoped in __init__ (competitor, document, pipeline_stage, author).
   - _reject_foreign rejects foreign tenant PKs on all FK fields.
   - Meta.fields excludes view-owned fields: tenant, number, view_count, share_count.
   - Form-level clean validates G1 requirement (document, external_url, or description).
2. SalesPlaybookForm:
   - Valid submission saves cleanly (create & edit).
   - Dropdown querysets tenant-scoped (pipeline, owner).
   - _reject_foreign rejects cross-tenant injection.
   - Meta.fields excludes view-owned fields: tenant, number.
3. SalesCertificationForm:
   - Valid submission saves cleanly (create & edit).
   - Dropdown querysets tenant-scoped (rep, certified_by, hrm_course).
   - _reject_foreign rejects cross-tenant injection.
   - Meta.fields excludes view-owned fields: tenant, number.
   - Validates passing score, certified_at, expires_at consistency.
4. CoachingScorecardForm:
   - Valid submission saves cleanly (create & edit).
   - Dropdown querysets tenant-scoped (coach, coachee, communication_log, activity_log).
   - _reject_foreign rejects cross-tenant injection.
   - Meta.fields excludes view-owned fields: tenant, number, overall_score, and review_status (per I3).
   - Form initial defaults: call_sentiment="neutral", evaluated_on today.
   - activity_log queryset has .select_related("communication_log") (per C4).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import Document, Party
from apps.crm.models import CommunicationLog
from apps.hrm.models import TrainingCourse
from apps.sales.forms import (
    CoachingScorecardForm,
    EnablementContentForm,
    SalesCertificationForm,
    SalesPlaybookForm,
)
from apps.sales.models import (
    ActivityLog,
    ActivityType,
    CoachingScorecard,
    CompetitorProfile,
    EnablementContent,
    Pipeline,
    PipelineStage,
    SalesCertification,
    SalesPlaybook,
)
from apps.sales.tests.conftest import (
    _salesenablement_certification,
    _salesenablement_content,
    _salesenablement_document,
    _salesenablement_playbook,
    _salesenablement_scorecard,
)

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers (_salesenablement_*)
# ============================================================================

def _salesenablement_widen(form, field_name, queryset):
    """Widens a form field queryset to allow cross-tenant test values past field validation."""
    form.fields[field_name].queryset = queryset


def _salesenablement_competitor(tenant, name="Alpha Corp", is_active=True, **overrides):
    """Helper creating a valid CompetitorProfile for testing."""
    party = Party.objects.create(
        tenant=tenant,
        name=f"{name}_{int(timezone.now().timestamp() * 1000) % 100000}",
        kind="organization",
    )
    defaults = {
        "tenant": tenant,
        "party": party,
        "market_positioning": "Tier 1 Enterprise Competitor",
        "strengths": "Brand legacy, large salesforce",
        "weaknesses": "Outdated UI, high implementation cost",
        "differentiators": "Highlight modern API and total cost of ownership",
        "is_active": is_active,
    }
    defaults.update(overrides)
    return CompetitorProfile.objects.create(**defaults)


def _salesenablement_pipeline_stage(tenant, pipeline=None, name="Stage 1", code="STG1", sequence=1):
    """Helper creating a valid PipelineStage for testing."""
    if pipeline is None:
        pipeline = Pipeline.objects.create(tenant=tenant, name=f"Pipeline {sequence}", is_active=True)
    return PipelineStage.objects.create(
        tenant=tenant,
        pipeline=pipeline,
        name=name,
        code=f"{code.lower()}_{int(timezone.now().timestamp() * 1000) % 100000}",
        sequence=sequence,
        stage_kind="open",
        crm_stage_key="qualification",
        probability=20,
        forecast_category="pipeline",
    )


def _salesenablement_hrm_course(tenant, title="MEDDPICC Mastery 101", is_active=True):
    """Helper creating a valid HRM TrainingCourse for testing."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    return TrainingCourse.objects.create(
        tenant=tenant,
        title=f"{title} {label}",
        is_active=is_active,
    )


def _salesenablement_activity_log(tenant, owner=None, communication_log=None):
    """Helper creating a valid ActivityLog for testing."""
    if communication_log is None:
        communication_log = CommunicationLog.objects.create(
            tenant=tenant,
            channel="call",
            subject="Coaching Call",
            owner=owner,
        )
    activity_type, _ = ActivityType.objects.get_or_create(
        tenant=tenant,
        name="Sales Call",
        defaults={"kind": "call"},
    )
    return ActivityLog.objects.create(
        tenant=tenant,
        communication_log=communication_log,
        activity_type=activity_type,
        owner=owner,
    )


def _salesenablement_inactive_user(tenant, email="inactive@example.com"):
    """Helper creating an inactive User for testing queryset filtering."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    return User.objects.create_user(
        username=f"inactive_{label}",
        email=f"inactive_{label}@example.com",
        tenant=tenant,
        is_active=False,
    )


def _salesenablement_content_payload(**overrides):
    """Default valid payload for EnablementContentForm."""
    payload = {
        "title": "Enterprise Battlecard vs Competitor X",
        "description": "Key competitive differentiators and handling objections.",
        "content_type": "battle_card",
        "external_url": "",
        "target_stage": "demo_eval",
        "target_persona": "technical_buyer",
        "tags": "security,enterprise,battlecard",
        "version": "1.0",
        "is_client_facing": False,
        "is_active": True,
        "expires_on": (timezone.now().date() + timedelta(days=90)).isoformat(),
    }
    payload.update(overrides)
    return payload


def _salesenablement_playbook_payload(**overrides):
    """Default valid payload for SalesPlaybookForm."""
    payload = {
        "name": "Mid-Market Outbound Playbook",
        "summary": "Outbound execution cadence and messaging framework.",
        "motion_type": "new_business",
        "status": "published",
        "target_audience": "VP of Engineering and CTOs",
        "discovery_questions": "1. What is your current ERP stack?\n2. What is your release velocity?",
        "talk_tracks": "Focus on developer agility and unified ERP/CRM workflows.",
        "objection_scripts": "Budget: Highlight 6-month payback period.",
        "dos_and_donts": "DO: demo live. DON'T: disparage legacy vendors.",
        "exit_criteria": "Agreed POC scope and signed NDA.",
        "version": "1.0",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _salesenablement_certification_payload(rep, **overrides):
    """Default valid payload for SalesCertificationForm."""
    payload = {
        "curriculum_name": "MEDDPICC Enterprise Accreditation",
        "category": "methodology",
        "rep": str(rep.pk) if rep else "",
        "status": "enrolled",
        "score_percent": "",
        "passing_score_percent": "80.00",
        "certified_by": "",
        "certified_at": "",
        "expires_at": "",
        "accreditation_notes": "Completed initial assessment webinar.",
        "hrm_course": "",
    }
    payload.update(overrides)
    return payload


def _salesenablement_scorecard_payload(communication_log, coachee, **overrides):
    """Default valid payload for CoachingScorecardForm."""
    payload = {
        "communication_log": str(communication_log.pk) if communication_log else "",
        "activity_log": "",
        "coach": "",
        "coachee": str(coachee.pk) if coachee else "",
        "recording_url": "https://zoom.us/rec/123456789",
        "discovery_score": 4,
        "value_prop_score": 4,
        "objection_handling_score": 3,
        "next_steps_score": 4,
        "talk_listen_ratio_percent": 48,
        "call_sentiment": "positive",
        "transcript_summary": "Prospect confirmed pain around manual reconciliations.",
        "key_strengths": "Crisp qualification of economic buyer decision criteria.",
        "areas_for_improvement": "Pushed next steps slightly too early.",
        "action_items": "Review competitor one-pager before next call.",
        "evaluated_on": timezone.now().date().isoformat(),
    }
    payload.update(overrides)
    return payload


# ============================================================================
# 1. EnablementContentForm Tests
# ============================================================================

def test_salesenablement_content_form_meta_fields():
    """EnablementContentForm Meta.fields includes all authorable fields and excludes view-owned."""
    expected_fields = {
        "title",
        "description",
        "content_type",
        "document",
        "external_url",
        "competitor",
        "target_stage",
        "target_persona",
        "pipeline_stage",
        "author",
        "tags",
        "version",
        "is_client_facing",
        "is_active",
        "expires_on",
    }
    assert set(EnablementContentForm.Meta.fields) == expected_fields

    excluded_view_owned = {"tenant", "number", "view_count", "share_count", "id", "created_at", "updated_at"}
    for field in excluded_view_owned:
        assert field not in EnablementContentForm.Meta.fields
        assert field not in EnablementContentForm().fields


def test_salesenablement_content_form_valid_submission_saves_cleanly(tenant_a, admin_user):
    """Valid form submission saves cleanly, assigning tenant and auto-numbering ECN."""
    doc = _salesenablement_document(tenant_a)
    comp = _salesenablement_competitor(tenant_a)
    stage = _salesenablement_pipeline_stage(tenant_a)

    payload = _salesenablement_content_payload(
        document=str(doc.pk),
        competitor=str(comp.pk),
        pipeline_stage=str(stage.pk),
        author=str(admin_user.pk),
        title="Acme Battlecard Q1",
        version="1.2",
    )
    form = EnablementContentForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    content = form.save()

    assert content.pk is not None
    assert content.tenant == tenant_a
    assert content.number.startswith("ECN-")
    assert content.title == "Acme Battlecard Q1"
    assert content.document == doc
    assert content.competitor == comp
    assert content.pipeline_stage == stage
    assert content.author == admin_user
    assert content.version == "1.2"
    assert content.view_count == 0
    assert content.share_count == 0

    # Instance edit saves cleanly
    edit_payload = _salesenablement_content_payload(
        document=str(doc.pk),
        title="Acme Battlecard Q1 Updated",
        version="1.3",
    )
    edit_form = EnablementContentForm(edit_payload, instance=content, tenant=tenant_a)
    assert edit_form.is_valid(), f"Edit form errors: {edit_form.errors}"
    updated = edit_form.save()
    assert updated.pk == content.pk
    assert updated.title == "Acme Battlecard Q1 Updated"
    assert updated.version == "1.3"


def test_salesenablement_content_form_required_fields(tenant_a):
    """Title is a mandatory field on EnablementContentForm."""
    payload = _salesenablement_content_payload(title="")
    form = EnablementContentForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "This field is required." in form.errors["title"]


def test_salesenablement_content_form_g1_validation(tenant_a):
    """Form-level clean validates G1: at least one of document, external_url, or description."""
    # Case A: None provided -> invalid
    payload_none = _salesenablement_content_payload(
        document="",
        external_url="",
        description="",
    )
    form_none = EnablementContentForm(payload_none, tenant=tenant_a)
    assert not form_none.is_valid()
    assert "__all__" in form_none.errors
    expected_msg = "Provide a document file attachment, an external cloud URL, or a text description/script."
    assert any(expected_msg in err for err in form_none.errors["__all__"])

    # Case B: Only document provided -> valid
    doc = _salesenablement_document(tenant_a)
    payload_doc = _salesenablement_content_payload(
        document=str(doc.pk),
        external_url="",
        description="",
    )
    form_doc = EnablementContentForm(payload_doc, tenant=tenant_a)
    assert form_doc.is_valid(), f"Errors with document: {form_doc.errors}"

    # Case C: Only external_url provided -> valid
    payload_url = _salesenablement_content_payload(
        document="",
        external_url="https://docs.google.com/presentation/d/example123",
        description="",
    )
    form_url = EnablementContentForm(payload_url, tenant=tenant_a)
    assert form_url.is_valid(), f"Errors with url: {form_url.errors}"

    # Case D: Only description provided -> valid
    payload_desc = _salesenablement_content_payload(
        document="",
        external_url="",
        description="Text-only elevator pitch summary.",
    )
    form_desc = EnablementContentForm(payload_desc, tenant=tenant_a)
    assert form_desc.is_valid(), f"Errors with desc: {form_desc.errors}"


def test_salesenablement_content_form_dropdown_querysets_tenant_scoped(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
):
    """Dropdown querysets in EnablementContentForm are strictly tenant-scoped."""
    doc_a = _salesenablement_document(tenant_a)
    doc_b = _salesenablement_document(tenant_b)

    comp_a_active = _salesenablement_competitor(tenant_a, is_active=True)
    comp_a_inactive = _salesenablement_competitor(tenant_a, is_active=False)
    comp_b = _salesenablement_competitor(tenant_b, is_active=True)

    stage_a = _salesenablement_pipeline_stage(tenant_a)
    stage_b = _salesenablement_pipeline_stage(tenant_b)

    user_a_inactive = _salesenablement_inactive_user(tenant_a)

    form_a = EnablementContentForm(tenant=tenant_a)

    # Document scoping
    doc_qs = form_a.fields["document"].queryset
    assert doc_a in doc_qs
    assert doc_b not in doc_qs

    # Competitor scoping (tenant + is_active=True)
    comp_qs = form_a.fields["competitor"].queryset
    assert comp_a_active in comp_qs
    assert comp_a_inactive not in comp_qs
    assert comp_b not in comp_qs

    # PipelineStage scoping
    stage_qs = form_a.fields["pipeline_stage"].queryset
    assert stage_a in stage_qs
    assert stage_b not in stage_qs

    # Author scoping (tenant + is_active=True)
    author_qs = form_a.fields["author"].queryset
    assert admin_user in author_qs
    assert user_a_inactive not in author_qs
    assert admin_b not in author_qs

    # Tenant=None defaults to empty querysets
    form_none = EnablementContentForm(tenant=None)
    assert form_none.fields["document"].queryset.count() == 0
    assert form_none.fields["competitor"].queryset.count() == 0
    assert form_none.fields["pipeline_stage"].queryset.count() == 0
    assert form_none.fields["author"].queryset.count() == 0


def test_salesenablement_content_form_reject_foreign_fks(tenant_a, tenant_b, admin_b):
    """_reject_foreign rejects foreign tenant PKs across all FK fields."""
    doc_b = _salesenablement_document(tenant_b)
    comp_b = _salesenablement_competitor(tenant_b)
    stage_b = _salesenablement_pipeline_stage(tenant_b)

    fk_cases = [
        ("document", doc_b, Document.objects.all()),
        ("competitor", comp_b, CompetitorProfile.objects.all()),
        ("pipeline_stage", stage_b, PipelineStage.objects.all()),
        ("author", admin_b, User.objects.all()),
    ]

    for field_name, foreign_obj, widened_qs in fk_cases:
        # Default scoped queryset rejects foreign PK at choice validation
        payload = _salesenablement_content_payload(**{field_name: str(foreign_obj.pk)})
        form_default = EnablementContentForm(payload, tenant=tenant_a)
        assert not form_default.is_valid()
        assert field_name in form_default.errors
        assert any("Select a valid choice" in err for err in form_default.errors[field_name])

        # Widened queryset reaches clean() and triggers _reject_foreign
        form_widened = EnablementContentForm(payload, tenant=tenant_a)
        _salesenablement_widen(form_widened, field_name, widened_qs)
        assert not form_widened.is_valid()
        assert field_name in form_widened.errors
        assert "That record belongs to another workspace." in form_widened.errors[field_name]


# ============================================================================
# 2. SalesPlaybookForm Tests
# ============================================================================

def test_salesenablement_playbook_form_meta_fields():
    """SalesPlaybookForm Meta.fields includes all playbook fields and excludes view-owned."""
    expected_fields = {
        "name",
        "summary",
        "motion_type",
        "pipeline",
        "status",
        "target_audience",
        "discovery_questions",
        "talk_tracks",
        "objection_scripts",
        "dos_and_donts",
        "exit_criteria",
        "owner",
        "version",
        "is_active",
    }
    assert set(SalesPlaybookForm.Meta.fields) == expected_fields

    excluded_view_owned = {"tenant", "number", "id", "created_at", "updated_at"}
    for field in excluded_view_owned:
        assert field not in SalesPlaybookForm.Meta.fields
        assert field not in SalesPlaybookForm().fields


def test_salesenablement_playbook_form_valid_submission_saves_cleanly(tenant_a, admin_user):
    """Valid SalesPlaybookForm submission saves cleanly with tenant and SPB auto-numbering."""
    pipeline = Pipeline.objects.create(tenant=tenant_a, name="Enterprise Mid-Market", is_active=True)

    payload = _salesenablement_playbook_payload(
        pipeline=str(pipeline.pk),
        owner=str(admin_user.pk),
        name="Enterprise Sales Playbook 2027",
        version="2.1",
    )
    form = SalesPlaybookForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    playbook = form.save()

    assert playbook.pk is not None
    assert playbook.tenant == tenant_a
    assert playbook.number.startswith("SPB-")
    assert playbook.name == "Enterprise Sales Playbook 2027"
    assert playbook.pipeline == pipeline
    assert playbook.owner == admin_user
    assert playbook.version == "2.1"

    # Edit existing playbook
    edit_payload = _salesenablement_playbook_payload(
        pipeline=str(pipeline.pk),
        owner=str(admin_user.pk),
        name="Enterprise Sales Playbook 2027 Revised",
        status="archived",
    )
    edit_form = SalesPlaybookForm(edit_payload, instance=playbook, tenant=tenant_a)
    assert edit_form.is_valid(), f"Edit form errors: {edit_form.errors}"
    updated = edit_form.save()
    assert updated.pk == playbook.pk
    assert updated.name == "Enterprise Sales Playbook 2027 Revised"
    assert updated.status == "archived"


def test_salesenablement_playbook_form_required_fields(tenant_a):
    """Playbook name is required."""
    payload = _salesenablement_playbook_payload(name="")
    form = SalesPlaybookForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "This field is required." in form.errors["name"]


def test_salesenablement_playbook_form_dropdown_querysets_tenant_scoped(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
):
    """Dropdown querysets in SalesPlaybookForm are strictly tenant-scoped."""
    pipe_a_active = Pipeline.objects.create(tenant=tenant_a, name="Pipe A Active", is_active=True)
    pipe_a_inactive = Pipeline.objects.create(tenant=tenant_a, name="Pipe A Inactive", is_active=False)
    pipe_b = Pipeline.objects.create(tenant=tenant_b, name="Pipe B Active", is_active=True)

    user_a_inactive = _salesenablement_inactive_user(tenant_a)

    form_a = SalesPlaybookForm(tenant=tenant_a)

    # Pipeline queryset scoping
    pipe_qs = form_a.fields["pipeline"].queryset
    assert pipe_a_active in pipe_qs
    assert pipe_a_inactive not in pipe_qs
    assert pipe_b not in pipe_qs

    # Owner queryset scoping
    owner_qs = form_a.fields["owner"].queryset
    assert admin_user in owner_qs
    assert user_a_inactive not in owner_qs
    assert admin_b not in owner_qs

    # Tenant=None defaults to empty querysets
    form_none = SalesPlaybookForm(tenant=None)
    assert form_none.fields["pipeline"].queryset.count() == 0
    assert form_none.fields["owner"].queryset.count() == 0


def test_salesenablement_playbook_form_reject_foreign_fks(tenant_a, tenant_b, admin_b):
    """_reject_foreign rejects foreign tenant PKs for pipeline and owner."""
    pipe_b = Pipeline.objects.create(tenant=tenant_b, name="Foreign Pipe", is_active=True)

    fk_cases = [
        ("pipeline", pipe_b, Pipeline.objects.all()),
        ("owner", admin_b, User.objects.all()),
    ]

    for field_name, foreign_obj, widened_qs in fk_cases:
        payload = _salesenablement_playbook_payload(**{field_name: str(foreign_obj.pk)})
        form_default = SalesPlaybookForm(payload, tenant=tenant_a)
        assert not form_default.is_valid()
        assert field_name in form_default.errors
        assert any("Select a valid choice" in err for err in form_default.errors[field_name])

        form_widened = SalesPlaybookForm(payload, tenant=tenant_a)
        _salesenablement_widen(form_widened, field_name, widened_qs)
        assert not form_widened.is_valid()
        assert field_name in form_widened.errors
        assert "That record belongs to another workspace." in form_widened.errors[field_name]


# ============================================================================
# 3. SalesCertificationForm Tests
# ============================================================================

def test_salesenablement_certification_form_meta_fields():
    """SalesCertificationForm Meta.fields includes all 11 certification fields and excludes view-owned."""
    expected_fields = {
        "curriculum_name",
        "category",
        "rep",
        "status",
        "score_percent",
        "passing_score_percent",
        "certified_by",
        "certified_at",
        "expires_at",
        "accreditation_notes",
        "hrm_course",
    }
    assert set(SalesCertificationForm.Meta.fields) == expected_fields

    excluded_view_owned = {"tenant", "number", "id", "created_at", "updated_at"}
    for field in excluded_view_owned:
        assert field not in SalesCertificationForm.Meta.fields
        assert field not in SalesCertificationForm().fields


def test_salesenablement_certification_form_valid_submission_saves_cleanly(
    tenant_a,
    member_user,
    admin_user,
):
    """Valid SalesCertificationForm saves cleanly, assigning tenant and SCTF auto-numbering."""
    hrm_course = _salesenablement_hrm_course(tenant_a, is_active=True)

    payload = _salesenablement_certification_payload(
        rep=member_user,
        curriculum_name="Product Specialist Certification v3",
        category="product_certification",
        status="enrolled",
        passing_score_percent="85.00",
        certified_by=str(admin_user.pk),
        hrm_course=str(hrm_course.pk),
    )
    form = SalesCertificationForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    cert = form.save()

    assert cert.pk is not None
    assert cert.tenant == tenant_a
    assert cert.number.startswith("SCTF-")
    assert cert.curriculum_name == "Product Specialist Certification v3"
    assert cert.rep == member_user
    assert cert.certified_by == admin_user
    assert cert.hrm_course == hrm_course
    assert cert.passing_score_percent == Decimal("85.00")

    # Edit certification to completed with passing score and dates
    cert_date = timezone.now().date()
    exp_date = cert_date + timedelta(days=365)
    edit_payload = _salesenablement_certification_payload(
        rep=member_user,
        curriculum_name="Product Specialist Certification v3",
        category="product_certification",
        status="completed",
        score_percent="92.50",
        passing_score_percent="85.00",
        certified_by=str(admin_user.pk),
        certified_at=cert_date.isoformat(),
        expires_at=exp_date.isoformat(),
        hrm_course=str(hrm_course.pk),
    )
    edit_form = SalesCertificationForm(edit_payload, instance=cert, tenant=tenant_a)
    assert edit_form.is_valid(), f"Edit form errors: {edit_form.errors}"
    updated = edit_form.save()
    assert updated.pk == cert.pk
    assert updated.status == "completed"
    assert updated.score_percent == Decimal("92.50")
    assert updated.certified_at == cert_date
    assert updated.expires_at == exp_date


def test_salesenablement_certification_form_required_fields(tenant_a):
    """Curriculum name and rep are required fields on SalesCertificationForm."""
    payload = _salesenablement_certification_payload(rep=None, curriculum_name="")
    form = SalesCertificationForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "curriculum_name" in form.errors
    assert "This field is required." in form.errors["curriculum_name"]
    assert "rep" in form.errors
    assert "This field is required." in form.errors["rep"]


def test_salesenablement_certification_form_dropdown_querysets_tenant_scoped(
    tenant_a,
    tenant_b,
    admin_user,
    member_user,
    admin_b,
):
    """Dropdown querysets in SalesCertificationForm are strictly tenant-scoped."""
    user_a_inactive = _salesenablement_inactive_user(tenant_a)

    course_a_active = _salesenablement_hrm_course(tenant_a, title="Course A Active", is_active=True)
    course_a_inactive = _salesenablement_hrm_course(tenant_a, title="Course A Inactive", is_active=False)
    course_b = _salesenablement_hrm_course(tenant_b, title="Course B Active", is_active=True)

    form_a = SalesCertificationForm(tenant=tenant_a)

    # Rep queryset scoping
    rep_qs = form_a.fields["rep"].queryset
    assert admin_user in rep_qs
    assert member_user in rep_qs
    assert user_a_inactive not in rep_qs
    assert admin_b not in rep_qs

    # Certified_by queryset scoping
    cert_by_qs = form_a.fields["certified_by"].queryset
    assert admin_user in cert_by_qs
    assert user_a_inactive not in cert_by_qs
    assert admin_b not in cert_by_qs

    # HRM course queryset scoping (tenant + is_active=True)
    course_qs = form_a.fields["hrm_course"].queryset
    assert course_a_active in course_qs
    assert course_a_inactive not in course_qs
    assert course_b not in course_qs

    # Tenant=None defaults to empty querysets
    form_none = SalesCertificationForm(tenant=None)
    assert form_none.fields["rep"].queryset.count() == 0
    assert form_none.fields["certified_by"].queryset.count() == 0
    assert form_none.fields["hrm_course"].queryset.count() == 0


def test_salesenablement_certification_form_reject_foreign_fks(tenant_a, tenant_b, admin_b):
    """_reject_foreign rejects foreign tenant PKs for rep, certified_by, and hrm_course."""
    course_b = _salesenablement_hrm_course(tenant_b, is_active=True)

    fk_cases = [
        ("rep", admin_b, User.objects.all()),
        ("certified_by", admin_b, User.objects.all()),
        ("hrm_course", course_b, TrainingCourse.objects.all()),
    ]

    for field_name, foreign_obj, widened_qs in fk_cases:
        payload = _salesenablement_certification_payload(rep=foreign_obj if field_name == "rep" else admin_b)
        if field_name != "rep":
            payload[field_name] = str(foreign_obj.pk)

        form_default = SalesCertificationForm(payload, tenant=tenant_a)
        assert not form_default.is_valid()
        assert field_name in form_default.errors
        assert any("Select a valid choice" in err for err in form_default.errors[field_name])

        form_widened = SalesCertificationForm(payload, tenant=tenant_a)
        _salesenablement_widen(form_widened, field_name, widened_qs)
        # Ensure rep is also widened if testing certified_by or hrm_course with admin_b as rep
        if field_name != "rep":
            _salesenablement_widen(form_widened, "rep", User.objects.all())
        assert not form_widened.is_valid()
        assert field_name in form_widened.errors
        assert "That record belongs to another workspace." in form_widened.errors[field_name]


def test_salesenablement_certification_form_validates_score_bounds(tenant_a, member_user):
    """Score percent and passing score percent must be bounded between 0.00% and 100.00%."""
    # Negative score_percent
    p_neg_score = _salesenablement_certification_payload(rep=member_user, score_percent="-5.00")
    f_neg_score = SalesCertificationForm(p_neg_score, tenant=tenant_a)
    assert not f_neg_score.is_valid()
    assert "score_percent" in f_neg_score.errors

    # Score > 100
    p_high_score = _salesenablement_certification_payload(rep=member_user, score_percent="105.00")
    f_high_score = SalesCertificationForm(p_high_score, tenant=tenant_a)
    assert not f_high_score.is_valid()
    assert "score_percent" in f_high_score.errors

    # Negative passing_score_percent
    p_neg_pass = _salesenablement_certification_payload(rep=member_user, passing_score_percent="-1.00")
    f_neg_pass = SalesCertificationForm(p_neg_pass, tenant=tenant_a)
    assert not f_neg_pass.is_valid()
    assert "passing_score_percent" in f_neg_pass.errors

    # Passing score > 100
    p_high_pass = _salesenablement_certification_payload(rep=member_user, passing_score_percent="120.00")
    f_high_pass = SalesCertificationForm(p_high_pass, tenant=tenant_a)
    assert not f_high_pass.is_valid()
    assert "passing_score_percent" in f_high_pass.errors


def test_salesenablement_certification_form_validates_passing_score_and_completion(
    tenant_a,
    member_user,
):
    """Completed status requires score_percent >= passing_score_percent."""
    # Score 75% < passing 80% -> invalid for completed status
    payload_fail = _salesenablement_certification_payload(
        rep=member_user,
        status="completed",
        score_percent="75.00",
        passing_score_percent="80.00",
    )
    form_fail = SalesCertificationForm(payload_fail, tenant=tenant_a)
    assert not form_fail.is_valid()
    assert "status" in form_fail.errors
    assert any("below passing threshold" in err for err in form_fail.errors["status"])

    # Score 80% >= passing 80% -> valid
    payload_pass = _salesenablement_certification_payload(
        rep=member_user,
        status="completed",
        score_percent="80.00",
        passing_score_percent="80.00",
    )
    form_pass = SalesCertificationForm(payload_pass, tenant=tenant_a)
    assert form_pass.is_valid(), f"Errors: {form_pass.errors}"


def test_salesenablement_certification_form_completion_auto_sets_certified_at(
    tenant_a,
    member_user,
):
    """Marking completed without certified_at automatically populates certified_at on save."""
    payload = _salesenablement_certification_payload(
        rep=member_user,
        status="completed",
        score_percent="88.00",
        passing_score_percent="80.00",
        certified_at="",
    )
    form = SalesCertificationForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    cert = form.save()
    assert cert.certified_at == timezone.now().date()


def test_salesenablement_certification_form_validates_expires_at_after_certified_at(
    tenant_a,
    member_user,
):
    """expires_at cannot precede certified_at."""
    cert_date = date(2026, 6, 1)
    exp_before = date(2026, 5, 20)

    # Inconsistent dates
    payload_inconsistent = _salesenablement_certification_payload(
        rep=member_user,
        status="completed",
        score_percent="90.00",
        certified_at=cert_date.isoformat(),
        expires_at=exp_before.isoformat(),
    )
    form_inconsistent = SalesCertificationForm(payload_inconsistent, tenant=tenant_a)
    assert not form_inconsistent.is_valid()
    assert "expires_at" in form_inconsistent.errors
    assert "Expiration date cannot precede certification date." in form_inconsistent.errors["expires_at"]

    # Consistent dates
    exp_after = date(2027, 6, 1)
    payload_consistent = _salesenablement_certification_payload(
        rep=member_user,
        status="completed",
        score_percent="90.00",
        certified_at=cert_date.isoformat(),
        expires_at=exp_after.isoformat(),
    )
    form_consistent = SalesCertificationForm(payload_consistent, tenant=tenant_a)
    assert form_consistent.is_valid(), f"Errors: {form_consistent.errors}"


# ============================================================================
# 4. CoachingScorecardForm Tests
# ============================================================================

def test_salesenablement_scorecard_form_meta_fields():
    """CoachingScorecardForm Meta.fields excludes view-owned: tenant, number, overall_score, review_status (I3)."""
    expected_fields = {
        "communication_log",
        "activity_log",
        "coach",
        "coachee",
        "recording_url",
        "discovery_score",
        "value_prop_score",
        "objection_handling_score",
        "next_steps_score",
        "talk_listen_ratio_percent",
        "call_sentiment",
        "transcript_summary",
        "key_strengths",
        "areas_for_improvement",
        "action_items",
        "evaluated_on",
    }
    assert set(CoachingScorecardForm.Meta.fields) == expected_fields

    excluded_view_owned = {
        "tenant",
        "number",
        "overall_score",
        "review_status",
        "id",
        "created_at",
        "updated_at",
    }
    for field in excluded_view_owned:
        assert field not in CoachingScorecardForm.Meta.fields
        assert field not in CoachingScorecardForm().fields


def test_salesenablement_scorecard_form_valid_submission_saves_cleanly(
    tenant_a,
    admin_user,
    member_user,
):
    """Valid CoachingScorecardForm submission saves cleanly, auto-calculates overall_score, and assigns CSC-."""
    comm_log = CommunicationLog.objects.create(
        tenant=tenant_a,
        channel="call",
        subject="Mid-Market Discovery Call",
        owner=member_user,
    )
    act_log = _salesenablement_activity_log(tenant_a, owner=member_user, communication_log=comm_log)

    payload = _salesenablement_scorecard_payload(
        communication_log=comm_log,
        coachee=member_user,
        activity_log=str(act_log.pk),
        coach=str(admin_user.pk),
        discovery_score=5,
        value_prop_score=4,
        objection_handling_score=4,
        next_steps_score=3,
        talk_listen_ratio_percent=44,
        call_sentiment="positive",
    )
    form = CoachingScorecardForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    scorecard = form.save()

    assert scorecard.pk is not None
    assert scorecard.tenant == tenant_a
    assert scorecard.number.startswith("CSC-")
    assert scorecard.communication_log == comm_log
    assert scorecard.activity_log == act_log
    assert scorecard.coach == admin_user
    assert scorecard.coachee == member_user
    # Overall score: (5 + 4 + 4 + 3) / 20 * 100 = 80%
    assert scorecard.overall_score == 80
    assert scorecard.review_status == "draft"  # default from model

    # Edit existing scorecard
    edit_payload = _salesenablement_scorecard_payload(
        communication_log=comm_log,
        coachee=member_user,
        discovery_score=5,
        value_prop_score=5,
        objection_handling_score=5,
        next_steps_score=5,
    )
    edit_form = CoachingScorecardForm(edit_payload, instance=scorecard, tenant=tenant_a)
    assert edit_form.is_valid(), f"Edit form errors: {edit_form.errors}"
    updated = edit_form.save()
    assert updated.pk == scorecard.pk
    # Overall score updated: 20 / 20 * 100 = 100%
    assert updated.overall_score == 100


def test_salesenablement_scorecard_form_required_fields(tenant_a):
    """communication_log and coachee are required on CoachingScorecardForm."""
    payload = _salesenablement_scorecard_payload(
        communication_log=None,
        coachee=None,
    )
    form = CoachingScorecardForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "communication_log" in form.errors
    assert "This field is required." in form.errors["communication_log"]
    assert "coachee" in form.errors
    assert "This field is required." in form.errors["coachee"]


def test_salesenablement_scorecard_form_initial_defaults(tenant_a, admin_user, member_user):
    """Form defaults: call_sentiment='neutral', evaluated_on=today for new instances."""
    # Unbound new form gets defaults assigned to field.initial
    form_new = CoachingScorecardForm(tenant=tenant_a)
    assert form_new.fields["call_sentiment"].initial == "neutral"
    assert form_new.fields["evaluated_on"].initial == timezone.now().date()

    # Form with explicit initial overrides preserves passed initial
    custom_date = date(2026, 1, 15)
    form_custom = CoachingScorecardForm(
        tenant=tenant_a,
        initial={"call_sentiment": "skeptical", "evaluated_on": custom_date},
    )
    assert form_custom.initial.get("call_sentiment") == "skeptical"
    assert form_custom.initial.get("evaluated_on") == custom_date
    assert form_custom.get_initial_for_field(form_custom.fields["call_sentiment"], "call_sentiment") == "skeptical"
    assert form_custom.get_initial_for_field(form_custom.fields["evaluated_on"], "evaluated_on") == custom_date

    # Bound to existing instance does not force new-instance initials
    past_date = date(2026, 2, 10)
    scorecard = _salesenablement_scorecard(
        tenant_a,
        coach=admin_user,
        coachee=member_user,
        call_sentiment="negative",
        evaluated_on=past_date,
    )
    form_existing = CoachingScorecardForm(instance=scorecard, tenant=tenant_a)
    assert form_existing.initial.get("call_sentiment") == "negative"
    assert form_existing.initial.get("evaluated_on") == past_date


def test_salesenablement_scorecard_form_activity_log_select_related(tenant_a):
    """activity_log queryset must have .select_related('communication_log') per C4."""
    form = CoachingScorecardForm(tenant=tenant_a)
    qs = form.fields["activity_log"].queryset
    assert "communication_log" in qs.query.select_related, (
        f"Expected select_related('communication_log') in activity_log queryset, got: {qs.query.select_related}"
    )


def test_salesenablement_scorecard_form_dropdown_querysets_tenant_scoped(
    tenant_a,
    tenant_b,
    admin_user,
    member_user,
    admin_b,
):
    """Dropdown querysets in CoachingScorecardForm are strictly tenant-scoped."""
    comm_a = CommunicationLog.objects.create(tenant=tenant_a, channel="call", subject="Comm A")
    comm_b = CommunicationLog.objects.create(tenant=tenant_b, channel="call", subject="Comm B")

    act_a = _salesenablement_activity_log(tenant_a, communication_log=comm_a)
    act_b = _salesenablement_activity_log(tenant_b, communication_log=comm_b)

    user_a_inactive = _salesenablement_inactive_user(tenant_a)

    form_a = CoachingScorecardForm(tenant=tenant_a)

    # Communication log scoping
    comm_qs = form_a.fields["communication_log"].queryset
    assert comm_a in comm_qs
    assert comm_b not in comm_qs

    # Activity log scoping
    act_qs = form_a.fields["activity_log"].queryset
    assert act_a in act_qs
    assert act_b not in act_qs

    # Coach scoping
    coach_qs = form_a.fields["coach"].queryset
    assert admin_user in coach_qs
    assert user_a_inactive not in coach_qs
    assert admin_b not in coach_qs

    # Coachee scoping
    coachee_qs = form_a.fields["coachee"].queryset
    assert member_user in coachee_qs
    assert user_a_inactive not in coachee_qs
    assert admin_b not in coachee_qs

    # Tenant=None defaults to empty querysets
    form_none = CoachingScorecardForm(tenant=None)
    assert form_none.fields["communication_log"].queryset.count() == 0
    assert form_none.fields["activity_log"].queryset.count() == 0
    assert form_none.fields["coach"].queryset.count() == 0
    assert form_none.fields["coachee"].queryset.count() == 0


def test_salesenablement_scorecard_form_reject_foreign_fks(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
):
    """_reject_foreign rejects foreign tenant PKs for coach, coachee, communication_log, activity_log."""
    comm_b = CommunicationLog.objects.create(tenant=tenant_b, channel="call", subject="Foreign Comm")
    act_b = _salesenablement_activity_log(tenant_b, communication_log=comm_b)
    comm_a = CommunicationLog.objects.create(tenant=tenant_a, channel="call", subject="Valid Comm")

    fk_cases = [
        ("communication_log", comm_b, CommunicationLog.objects.all()),
        ("activity_log", act_b, ActivityLog.objects.all()),
        ("coach", admin_b, User.objects.all()),
        ("coachee", admin_b, User.objects.all()),
    ]

    for field_name, foreign_obj, widened_qs in fk_cases:
        payload = _salesenablement_scorecard_payload(
            communication_log=foreign_obj if field_name == "communication_log" else comm_a,
            coachee=foreign_obj if field_name == "coachee" else admin_user,
        )
        if field_name not in ("communication_log", "coachee"):
            payload[field_name] = str(foreign_obj.pk)

        # Default scoped queryset rejects foreign PK
        form_default = CoachingScorecardForm(payload, tenant=tenant_a)
        assert not form_default.is_valid()
        assert field_name in form_default.errors
        assert any("Select a valid choice" in err for err in form_default.errors[field_name])

        # Widened queryset reaches clean() and triggers _reject_foreign
        form_widened = CoachingScorecardForm(payload, tenant=tenant_a)
        _salesenablement_widen(form_widened, field_name, widened_qs)
        # Ensure communication_log and coachee valid if testing other fields
        if field_name == "activity_log" or field_name == "coach":
            _salesenablement_widen(form_widened, "communication_log", CommunicationLog.objects.all())
            _salesenablement_widen(form_widened, "coachee", User.objects.all())
        assert not form_widened.is_valid()
        assert field_name in form_widened.errors
        assert "That record belongs to another workspace." in form_widened.errors[field_name]


def test_salesenablement_scorecard_form_validates_rubric_and_ratio_bounds(
    tenant_a,
    member_user,
):
    """Scorecard validates rubric scores (1-5) and talk_listen_ratio_percent (0-100%)."""
    comm_log = CommunicationLog.objects.create(
        tenant=tenant_a,
        channel="call",
        subject="Evaluation Call",
        owner=member_user,
    )

    # Invalid rubric score (e.g. 0 or 6)
    payload_bad_rubric = _salesenablement_scorecard_payload(
        communication_log=comm_log,
        coachee=member_user,
        discovery_score=0,
    )
    form_bad_rubric = CoachingScorecardForm(payload_bad_rubric, tenant=tenant_a)
    assert not form_bad_rubric.is_valid()
    assert "discovery_score" in form_bad_rubric.errors

    # Invalid talk/listen ratio > 100
    payload_bad_ratio = _salesenablement_scorecard_payload(
        communication_log=comm_log,
        coachee=member_user,
        talk_listen_ratio_percent=120,
    )
    form_bad_ratio = CoachingScorecardForm(payload_bad_ratio, tenant=tenant_a)
    assert not form_bad_ratio.is_valid()
    assert "talk_listen_ratio_percent" in form_bad_ratio.errors

    # Negative talk/listen ratio
    payload_neg_ratio = _salesenablement_scorecard_payload(
        communication_log=comm_log,
        coachee=member_user,
        talk_listen_ratio_percent=-5,
    )
    form_neg_ratio = CoachingScorecardForm(payload_neg_ratio, tenant=tenant_a)
    assert not form_neg_ratio.is_valid()
    assert "talk_listen_ratio_percent" in form_neg_ratio.errors
