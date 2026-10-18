"""Sub-module 8.9 Sales Enablement -- model test suite.

Covers:
1. Model field contracts and choices:
   - Field presence and order against SALESENABLEMENT_MODEL_FIELDS
   - Choices validation against SALESENABLEMENT_CHOICES
   - Constraints and indexes pinning
2. String representations (__str__):
   - All 4 models: EnablementContent, SalesPlaybook, SalesCertification, CoachingScorecard
3. Auto-numbering:
   - ECN-, SPB-, SCTF-, CSC- prefix generation, formatting, and tenant sequence isolation
4. Business logic & custom methods:
   - EnablementContent: tag_list property, record_view(), record_share()
   - CoachingScorecard: automated overall_score calculation in save()
5. Model validation guards in clean():
   - G1: EnablementContent requires at least one of document, external_url, or description
   - G2-G5 & User FK checks: cross-tenant FK assignment raises ValidationError
   - G6: SalesCertification completed status requires score_percent >= passing_score_percent
   - G7: status="completed" auto-sets certified_at if missing
   - G8: expires_at < certified_at raises ValidationError
   - G9-G12 & User FK checks: cross-tenant FKs on certification and scorecard raise ValidationError
   - Numeric range guards on scores and percentages
6. Integrity & cascade rules:
   - Unique constraints per tenant, cascade deletion, and SET_NULL behaviors
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import Document, Party, Tenant
from apps.crm.models import CommunicationLog
from apps.hrm.models import TrainingCourse
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
    SALESENABLEMENT_CHOICES,
    SALESENABLEMENT_MODEL_FIELDS,
    _salesenablement_certification,
    _salesenablement_content,
    _salesenablement_document,
    _salesenablement_playbook,
    _salesenablement_scorecard,
)

pytestmark = pytest.mark.django_db

ALL_ENABLEMENT_MODELS = (
    EnablementContent,
    SalesPlaybook,
    SalesCertification,
    CoachingScorecard,
)


# ============================================================================
# Helpers (_salesenablement_*)
# ============================================================================

def _salesenablement_competitor(tenant, name="Alpha Corp", **overrides):
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
        "is_active": True,
    }
    defaults.update(overrides)
    return CompetitorProfile.objects.create(**defaults)


def _salesenablement_pipeline_stage(tenant, pipeline=None, name="Solution Validation", code="SOLVAL", sequence=1):
    """Helper creating a valid PipelineStage for testing."""
    if pipeline is None:
        pipeline = Pipeline.objects.create(tenant=tenant, name="Standard Pipeline")
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


def _salesenablement_activity_log(tenant, owner=None, communication_log=None):
    """Helper creating a valid ActivityLog for testing."""
    if communication_log is None:
        communication_log = _salesenablement_communication_log(tenant, owner=owner)
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


def _salesenablement_hrm_course(tenant, title="MEDDPICC Mastery 101"):
    """Helper creating a valid HRM TrainingCourse for testing."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    return TrainingCourse.objects.create(
        tenant=tenant,
        title=f"{title} {label}",
    )


def _salesenablement_communication_log(tenant, owner=None, subject="Executive Call"):
    """Helper creating a CRM CommunicationLog."""
    return CommunicationLog.objects.create(
        tenant=tenant,
        channel="call",
        subject=subject,
        owner=owner,
    )


# ============================================================================
# 1. Model field contracts, choices, constraints, and indexes
# ============================================================================

def test_salesenablement_model_fields_match_contract():
    """Verify that concrete fields on each model match SALESENABLEMENT_MODEL_FIELDS."""
    classes = {
        "EnablementContent": EnablementContent,
        "SalesPlaybook": SalesPlaybook,
        "SalesCertification": SalesCertification,
        "CoachingScorecard": CoachingScorecard,
    }
    for name, model_cls in classes.items():
        actual_fields = tuple(field.name for field in model_cls._meta.fields)
        expected_fields = SALESENABLEMENT_MODEL_FIELDS[name]
        assert actual_fields == expected_fields, f"Field mismatch on {name}"


def test_salesenablement_model_choices_match_contract():
    """Verify that choice definitions match SALESENABLEMENT_CHOICES verbatim."""
    classes = {
        "EnablementContent": EnablementContent,
        "SalesPlaybook": SalesPlaybook,
        "SalesCertification": SalesCertification,
        "CoachingScorecard": CoachingScorecard,
    }
    for model_name, choice_dict in SALESENABLEMENT_CHOICES.items():
        model_cls = classes[model_name]
        for field_name, expected_choices in choice_dict.items():
            field = model_cls._meta.get_field(field_name)
            actual_choices = tuple(tuple(pair) for pair in field.choices)
            assert actual_choices == expected_choices, (
                f"Choice mismatch for {model_name}.{field_name}"
            )


def test_salesenablement_constraints_and_indexes_pinned():
    """Ensure the unique constraints and performance indexes are pinned per contract."""
    expected = {
        EnablementContent: (
            ["sales_ecn_tenant_number_uniq"],
            ["sales_ecn_type_active_idx", "sales_ecn_act_upd_idx", "sales_ecn_stage_idx"],
        ),
        SalesPlaybook: (
            ["sales_spb_tenant_number_uniq"],
            ["sales_spb_motion_stat_idx"],
        ),
        SalesCertification: (
            ["sales_sctf_tenant_number_uniq"],
            ["sales_sctf_cat_stat_idx", "sales_crt_tenant_rep_stat_idx", "sales_crt_tenant_cert_idx"],
        ),
        CoachingScorecard: (
            ["sales_csc_tenant_number_uniq"],
            ["sales_csc_coachee_stat_idx", "sales_csc_tenant_eval_idx", "sales_csc_tenant_coach_idx"],
        ),
    }
    for model_cls, (constraint_names, index_names) in expected.items():
        actual_constraints = [c.name for c in model_cls._meta.constraints]
        actual_indexes = [idx.name for idx in model_cls._meta.indexes]
        assert actual_constraints == constraint_names, (
            f"Constraint mismatch on {model_cls.__name__}: {actual_constraints} vs {constraint_names}"
        )
        assert actual_indexes == index_names, (
            f"Index mismatch on {model_cls.__name__}: {actual_indexes} vs {index_names}"
        )


# ============================================================================
# 2. String representations (__str__)
# ============================================================================

def test_salesenablement_str_representations(
    tenant_a,
    admin_user,
    member_user,
    enablement_content_a,
    sales_playbook_a,
    sales_certification_a,
    coaching_scorecard_a,
):
    """Verify that __str__ on all 4 models returns the documented readable representation."""
    # EnablementContent: f"{number} - {title} ({get_content_type_display()})"
    content_str = str(enablement_content_a)
    assert content_str.startswith(enablement_content_a.number)
    assert enablement_content_a.title in content_str
    assert enablement_content_a.get_content_type_display() in content_str

    # SalesPlaybook: f"{number} - {name} ({get_motion_type_display()})"
    playbook_str = str(sales_playbook_a)
    assert playbook_str.startswith(sales_playbook_a.number)
    assert sales_playbook_a.name in playbook_str
    assert sales_playbook_a.get_motion_type_display() in playbook_str

    # SalesCertification: f"{number} - {curriculum_name} ({rep}) [{get_status_display()}]"
    cert_str = str(sales_certification_a)
    assert cert_str.startswith(sales_certification_a.number)
    assert sales_certification_a.curriculum_name in cert_str
    assert str(sales_certification_a.rep) in cert_str
    assert sales_certification_a.get_status_display() in cert_str

    # CoachingScorecard: f"{number} - {coachee} ({overall_score}%) [{get_review_status_display()}]"
    scorecard_str = str(coaching_scorecard_a)
    assert scorecard_str.startswith(coaching_scorecard_a.number)
    assert str(coaching_scorecard_a.coachee) in scorecard_str
    assert f"({coaching_scorecard_a.overall_score}%)" in scorecard_str
    assert coaching_scorecard_a.get_review_status_display() in scorecard_str


# ============================================================================
# 3. Auto-numbering: prefixes, formatting, and tenant isolation
# ============================================================================

def test_salesenablement_autonumbering_prefixes_and_sequences(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    member_user,
):
    """Verify ECN-, SPB-, SCTF-, CSC- number prefixes and per-tenant sequential generation."""
    c1 = _salesenablement_content(tenant_a, author=admin_user)
    c2 = _salesenablement_content(tenant_a, author=admin_user)
    c_b = _salesenablement_content(tenant_b, author=admin_b)

    p1 = _salesenablement_playbook(tenant_a, owner=admin_user)
    p2 = _salesenablement_playbook(tenant_a, owner=admin_user)
    p_b = _salesenablement_playbook(tenant_b, owner=admin_b)

    cert1 = _salesenablement_certification(tenant_a, rep=member_user, certified_by=admin_user)
    cert2 = _salesenablement_certification(tenant_a, rep=member_user, certified_by=admin_user)
    cert_b = _salesenablement_certification(tenant_b, rep=admin_b, certified_by=admin_b)

    sc1 = _salesenablement_scorecard(tenant_a, coach=admin_user, coachee=member_user)
    sc2 = _salesenablement_scorecard(tenant_a, coach=admin_user, coachee=member_user)
    sc_b = _salesenablement_scorecard(tenant_b, coach=admin_b, coachee=admin_b)

    prefix_map = [
        (c1, c2, c_b, "ECN-"),
        (p1, p2, p_b, "SPB-"),
        (cert1, cert2, cert_b, "SCTF-"),
        (sc1, sc2, sc_b, "CSC-"),
    ]

    for item1, item2, item_b, prefix in prefix_map:
        assert item1.number.startswith(prefix), f"{item1.number} does not start with {prefix}"
        assert item2.number.startswith(prefix), f"{item2.number} does not start with {prefix}"
        assert item_b.number.startswith(prefix), f"{item_b.number} does not start with {prefix}"

        # Digits check
        digits1 = item1.number[len(prefix):]
        digits2 = item2.number[len(prefix):]
        assert digits1.isdigit(), f"{digits1} is not numeric"
        assert digits2.isdigit(), f"{digits2} is not numeric"

        # Sequential within tenant
        seq1 = int(digits1)
        seq2 = int(digits2)
        assert seq2 > seq1, f"Expected {seq2} > {seq1} in sequence"


# ============================================================================
# 4. Business logic & custom methods
# ============================================================================

def test_salesenablement_content_tag_list_property(tenant_a, admin_user):
    """EnablementContent.tag_list parses comma-delimited strings and trims whitespace."""
    content = _salesenablement_content(tenant_a, author=admin_user, tags="enterprise, objection-handling, battlecard , pitch ")
    assert content.tag_list == ["enterprise", "objection-handling", "battlecard", "pitch"]

    # Empty tags
    content.tags = ""
    assert content.tag_list == []

    # Whitespace only
    content.tags = "   ,  , "
    assert content.tag_list == []

    # None handling
    content.tags = None
    assert content.tag_list == []


def test_salesenablement_content_record_view(tenant_a, admin_user):
    """EnablementContent.record_view() increments view_count atomically in database."""
    content = _salesenablement_content(tenant_a, author=admin_user)
    assert content.view_count == 0

    content.record_view()
    content.refresh_from_db()
    assert content.view_count == 1

    content.record_view()
    content.record_view()
    content.refresh_from_db()
    assert content.view_count == 3


def test_salesenablement_content_record_share(tenant_a, admin_user):
    """EnablementContent.record_share() increments share_count atomically in database."""
    content = _salesenablement_content(tenant_a, author=admin_user)
    assert content.share_count == 0

    content.record_share()
    content.refresh_from_db()
    assert content.share_count == 1

    content.record_share()
    content.refresh_from_db()
    assert content.share_count == 2


def test_salesenablement_scorecard_automated_overall_score(tenant_a, admin_user, member_user):
    """CoachingScorecard.save() calculates composite overall_score = round(rubric_sum / 20 * 100)."""
    comm_log = _salesenablement_communication_log(tenant_a, owner=admin_user)

    # Minimum possible score: 1 + 1 + 1 + 1 = 4 -> 4/20 = 20%
    sc_min = CoachingScorecard.objects.create(
        tenant=tenant_a,
        communication_log=comm_log,
        coach=admin_user,
        coachee=member_user,
        discovery_score=1,
        value_prop_score=1,
        objection_handling_score=1,
        next_steps_score=1,
    )
    assert sc_min.overall_score == 20

    # Maximum possible score: 5 + 5 + 5 + 5 = 20 -> 20/20 = 100%
    sc_max = CoachingScorecard.objects.create(
        tenant=tenant_a,
        communication_log=comm_log,
        coach=admin_user,
        coachee=member_user,
        discovery_score=5,
        value_prop_score=5,
        objection_handling_score=5,
        next_steps_score=5,
    )
    assert sc_max.overall_score == 100

    # Intermediate score: 4 + 3 + 4 + 4 = 15 -> 15/20 = 75%
    sc_mid = CoachingScorecard.objects.create(
        tenant=tenant_a,
        communication_log=comm_log,
        coach=admin_user,
        coachee=member_user,
        discovery_score=4,
        value_prop_score=3,
        objection_handling_score=4,
        next_steps_score=4,
    )
    assert sc_mid.overall_score == 75

    # Rounding check: 4 + 4 + 3 + 2 = 13 -> 13/20 = 65%
    sc_round = CoachingScorecard.objects.create(
        tenant=tenant_a,
        communication_log=comm_log,
        coach=admin_user,
        coachee=member_user,
        discovery_score=4,
        value_prop_score=4,
        objection_handling_score=3,
        next_steps_score=2,
    )
    assert sc_round.overall_score == 65

    # Recalculate on update: update discovery_score from 4 to 5 (14 -> 70%)
    sc_round.discovery_score = 5
    sc_round.save()
    sc_round.refresh_from_db()
    assert sc_round.overall_score == 70


# ============================================================================
# 5. Model validation guards in clean()
# ============================================================================

def test_salesenablement_content_g1_requires_document_url_or_description(tenant_a, admin_user):
    """G1: EnablementContent requires at least one of document, external_url, or description."""
    doc = _salesenablement_document(tenant_a, name="Product Spec Sheet")

    # None of the 3 provided -> raises ValidationError
    content = EnablementContent(
        tenant=tenant_a,
        title="Empty Collateral",
        content_type="battle_card",
        description="",
        external_url="",
        document=None,
    )
    with pytest.raises(ValidationError) as exc:
        content.clean()
    assert "Provide a document file attachment, an external cloud URL, or a text description/script." in str(exc.value)

    # Only document provided -> passes clean()
    content.document = doc
    content.clean()

    # Only external_url provided -> passes clean()
    content.document = None
    content.external_url = "https://docs.google.com/presentation/d/sample"
    content.clean()

    # Only description provided -> passes clean()
    content.external_url = ""
    content.description = "Detailed battle-card talk track notes."
    content.clean()


def test_salesenablement_content_cross_tenant_guards(tenant_a, tenant_b, admin_user, admin_b):
    """G2-G5 & User FK: Cross-tenant foreign keys on EnablementContent raise ValidationError."""
    competitor_b = _salesenablement_competitor(tenant_b, name="Competitor B")
    doc_b = _salesenablement_document(tenant_b, name="Doc B")
    stage_b = _salesenablement_pipeline_stage(tenant_b, name="Stage B")

    # G2: Competitor from different tenant
    c_comp = EnablementContent(
        tenant=tenant_a,
        title="Battlecard",
        description="Testing cross-tenant competitor",
        competitor=competitor_b,
    )
    with pytest.raises(ValidationError) as exc:
        c_comp.clean()
    assert "competitor" in exc.value.message_dict
    assert "Competitor profile must belong to the same workspace." in exc.value.message_dict["competitor"]

    # G3: Document from different tenant
    c_doc = EnablementContent(
        tenant=tenant_a,
        title="Deck",
        description="Testing cross-tenant doc",
        document=doc_b,
    )
    with pytest.raises(ValidationError) as exc:
        c_doc.clean()
    assert "document" in exc.value.message_dict
    assert "Document must belong to the same workspace." in exc.value.message_dict["document"]

    # G4: PipelineStage from different tenant
    c_stage = EnablementContent(
        tenant=tenant_a,
        title="Stage Content",
        description="Testing cross-tenant pipeline stage",
        pipeline_stage=stage_b,
    )
    with pytest.raises(ValidationError) as exc:
        c_stage.clean()
    assert "pipeline_stage" in exc.value.message_dict
    assert "Pipeline stage must belong to the same workspace." in exc.value.message_dict["pipeline_stage"]

    # G5 / User FK: Author from different tenant
    c_author = EnablementContent(
        tenant=tenant_a,
        title="Authored Content",
        description="Testing cross-tenant author",
        author=admin_b,
    )
    with pytest.raises(ValidationError) as exc:
        c_author.clean()
    assert "author" in exc.value.message_dict
    assert "Author must belong to the same workspace." in exc.value.message_dict["author"]


def test_salesenablement_playbook_cross_tenant_guards(tenant_a, tenant_b, admin_user, admin_b):
    """Cross-tenant pipeline and owner foreign keys on SalesPlaybook raise ValidationError."""
    pipeline_b = Pipeline.objects.create(tenant=tenant_b, name="Pipeline B")

    # Cross-tenant pipeline
    pb_pipe = SalesPlaybook(
        tenant=tenant_a,
        name="Playbook Pipe Guard",
        pipeline=pipeline_b,
    )
    with pytest.raises(ValidationError) as exc:
        pb_pipe.clean()
    assert "pipeline" in exc.value.message_dict
    assert "Associated pipeline must belong to the same workspace." in exc.value.message_dict["pipeline"]

    # Cross-tenant owner
    pb_owner = SalesPlaybook(
        tenant=tenant_a,
        name="Playbook Owner Guard",
        owner=admin_b,
    )
    with pytest.raises(ValidationError) as exc:
        pb_owner.clean()
    assert "owner" in exc.value.message_dict
    assert "Playbook owner must belong to the same workspace." in exc.value.message_dict["owner"]

    # Same-tenant pipeline and owner pass clean()
    pipeline_a = Pipeline.objects.create(tenant=tenant_a, name="Pipeline A")
    pb_valid = SalesPlaybook(
        tenant=tenant_a,
        name="Playbook Valid",
        pipeline=pipeline_a,
        owner=admin_user,
    )
    pb_valid.clean()


def test_salesenablement_certification_g6_completion_requires_passing_score(tenant_a, member_user, admin_user):
    """G6: SalesCertification completed status requires score_percent >= passing_score_percent."""
    cert = SalesCertification(
        tenant=tenant_a,
        curriculum_name="Cloud Architecture Certification",
        category="product_certification",
        rep=member_user,
        status="completed",
        passing_score_percent=Decimal("80.00"),
        score_percent=Decimal("79.99"),
        certified_by=admin_user,
    )
    with pytest.raises(ValidationError) as exc:
        cert.clean()
    assert "status" in exc.value.message_dict
    assert "is below passing threshold" in str(exc.value.message_dict["status"])

    # Score exactly passing threshold -> passes
    cert.score_percent = Decimal("80.00")
    cert.clean()

    # Score well above passing threshold -> passes
    cert.score_percent = Decimal("95.50")
    cert.clean()

    # When status is "failed" or "enrolled", lower score does not trigger G6
    cert.status = "failed"
    cert.score_percent = Decimal("50.00")
    cert.clean()

    cert.status = "enrolled"
    cert.score_percent = Decimal("50.00")
    cert.clean()


def test_salesenablement_certification_g7_completion_autosets_certified_at(tenant_a, member_user, admin_user):
    """G7: SalesCertification completed status auto-sets certified_at to today if missing."""
    cert = SalesCertification(
        tenant=tenant_a,
        curriculum_name="Onboarding Curriculum",
        category="onboarding",
        rep=member_user,
        status="completed",
        score_percent=Decimal("85.00"),
        certified_at=None,
    )
    assert cert.certified_at is None
    cert.clean()
    assert cert.certified_at == timezone.now().date()

    # If certified_at is explicitly provided, it is preserved
    past_date = date(2025, 6, 1)
    cert.certified_at = past_date
    cert.clean()
    assert cert.certified_at == past_date


def test_salesenablement_certification_g8_expires_at_cannot_precede_certified_at(tenant_a, member_user, admin_user):
    """G8: SalesCertification expires_at < certified_at raises ValidationError."""
    cert = SalesCertification(
        tenant=tenant_a,
        curriculum_name="Security Compliance Certification",
        category="compliance",
        rep=member_user,
        status="completed",
        score_percent=Decimal("90.00"),
        certified_at=date(2026, 6, 1),
        expires_at=date(2026, 5, 31),
    )
    with pytest.raises(ValidationError) as exc:
        cert.clean()
    assert "expires_at" in exc.value.message_dict
    assert "Expiration date cannot precede certification date." in exc.value.message_dict["expires_at"]

    # expires_at equal to certified_at -> passes
    cert.expires_at = date(2026, 6, 1)
    cert.clean()

    # expires_at in the future -> passes
    cert.expires_at = date(2027, 6, 1)
    cert.clean()


def test_salesenablement_certification_score_range_guards(tenant_a, member_user):
    """SalesCertification score_percent and passing_score_percent must be between 0.00 and 100.00."""
    cert = SalesCertification(
        tenant=tenant_a,
        curriculum_name="Pitch Accreditation",
        category="pitch_accreditation",
        rep=member_user,
        score_percent=Decimal("-5.00"),
    )
    with pytest.raises(ValidationError) as exc:
        cert.clean()
    assert "score_percent" in exc.value.message_dict

    cert.score_percent = Decimal("100.01")
    with pytest.raises(ValidationError) as exc:
        cert.clean()
    assert "score_percent" in exc.value.message_dict

    cert.score_percent = Decimal("85.00")
    cert.passing_score_percent = Decimal("-1.00")
    with pytest.raises(ValidationError) as exc:
        cert.clean()
    assert "passing_score_percent" in exc.value.message_dict

    cert.passing_score_percent = Decimal("105.00")
    with pytest.raises(ValidationError) as exc:
        cert.clean()
    assert "passing_score_percent" in exc.value.message_dict


def test_salesenablement_certification_cross_tenant_guards(tenant_a, tenant_b, member_user, admin_b):
    """G9-G11 & User FK: Cross-tenant hrm_course, rep, and certified_by raise ValidationError."""
    course_b = _salesenablement_hrm_course(tenant_b, title="HRM B Course")

    # G9: HRM course from tenant_b
    cert_course = SalesCertification(
        tenant=tenant_a,
        curriculum_name="HRM Bridge Cert",
        category="product_certification",
        rep=member_user,
        hrm_course=course_b,
    )
    with pytest.raises(ValidationError) as exc:
        cert_course.clean()
    assert "hrm_course" in exc.value.message_dict
    assert "Associated HRM training course must belong to the same workspace." in exc.value.message_dict["hrm_course"]

    # G10 / User FK: rep from tenant_b
    cert_rep = SalesCertification(
        tenant=tenant_a,
        curriculum_name="Rep Guard Cert",
        category="onboarding",
        rep=admin_b,
    )
    with pytest.raises(ValidationError) as exc:
        cert_rep.clean()
    assert "rep" in exc.value.message_dict
    assert "Assigned representative must belong to the same workspace." in exc.value.message_dict["rep"]

    # G11 / User FK: certified_by from tenant_b
    cert_by = SalesCertification(
        tenant=tenant_a,
        curriculum_name="Certifier Guard Cert",
        category="onboarding",
        rep=member_user,
        certified_by=admin_b,
    )
    with pytest.raises(ValidationError) as exc:
        cert_by.clean()
    assert "certified_by" in exc.value.message_dict
    assert "Certifying user must belong to the same workspace." in exc.value.message_dict["certified_by"]


def test_salesenablement_scorecard_rubric_range_guards(tenant_a, admin_user, member_user):
    """CoachingScorecard scores must be 1-5 and talk ratio 0-100%."""
    comm_log = _salesenablement_communication_log(tenant_a, owner=admin_user)

    score_fields = ["discovery_score", "value_prop_score", "objection_handling_score", "next_steps_score"]
    for field_name in score_fields:
        for invalid_val in [0, 6]:
            sc = CoachingScorecard(
                tenant=tenant_a,
                communication_log=comm_log,
                coach=admin_user,
                coachee=member_user,
                **{field_name: invalid_val},
            )
            with pytest.raises(ValidationError) as exc:
                sc.clean()
            assert field_name in exc.value.message_dict, f"Expected validation error on {field_name} for value {invalid_val}"
            assert "Rubric score must be between 1 and 5." in exc.value.message_dict[field_name]

    # Talk listen ratio out of range
    sc_ratio_low = CoachingScorecard(
        tenant=tenant_a,
        communication_log=comm_log,
        coach=admin_user,
        coachee=member_user,
        talk_listen_ratio_percent=-1,
    )
    with pytest.raises(ValidationError) as exc:
        sc_ratio_low.clean()
    assert "talk_listen_ratio_percent" in exc.value.message_dict

    sc_ratio_high = CoachingScorecard(
        tenant=tenant_a,
        communication_log=comm_log,
        coach=admin_user,
        coachee=member_user,
        talk_listen_ratio_percent=101,
    )
    with pytest.raises(ValidationError) as exc:
        sc_ratio_high.clean()
    assert "talk_listen_ratio_percent" in exc.value.message_dict

    # Edge values 0 and 100 pass
    sc_edge = CoachingScorecard(
        tenant=tenant_a,
        communication_log=comm_log,
        coach=admin_user,
        coachee=member_user,
        talk_listen_ratio_percent=0,
    )
    sc_edge.clean()

    sc_edge.talk_listen_ratio_percent = 100
    sc_edge.clean()


def test_salesenablement_scorecard_cross_tenant_guards(tenant_a, tenant_b, admin_user, member_user, admin_b):
    """G12 & User FK: Cross-tenant communication_log, activity_log, coachee, coach raise ValidationError."""
    comm_a = _salesenablement_communication_log(tenant_a, owner=admin_user)
    comm_b = _salesenablement_communication_log(tenant_b, owner=admin_b)
    act_b = _salesenablement_activity_log(tenant_b, owner=admin_b)

    # G12: Cross-tenant communication log
    sc_comm = CoachingScorecard(
        tenant=tenant_a,
        communication_log=comm_b,
        coach=admin_user,
        coachee=member_user,
    )
    with pytest.raises(ValidationError) as exc:
        sc_comm.clean()
    assert "communication_log" in exc.value.message_dict
    assert "Communication log must belong to the same workspace." in exc.value.message_dict["communication_log"]

    # Cross-tenant activity log
    sc_act = CoachingScorecard(
        tenant=tenant_a,
        communication_log=comm_a,
        activity_log=act_b,
        coach=admin_user,
        coachee=member_user,
    )
    with pytest.raises(ValidationError) as exc:
        sc_act.clean()
    assert "activity_log" in exc.value.message_dict
    assert "Activity log must belong to the same workspace." in exc.value.message_dict["activity_log"]

    # Cross-tenant coachee
    sc_coachee = CoachingScorecard(
        tenant=tenant_a,
        communication_log=comm_a,
        coach=admin_user,
        coachee=admin_b,
    )
    with pytest.raises(ValidationError) as exc:
        sc_coachee.clean()
    assert "coachee" in exc.value.message_dict
    assert "Coachee must belong to the same workspace." in exc.value.message_dict["coachee"]

    # Cross-tenant coach
    sc_coach = CoachingScorecard(
        tenant=tenant_a,
        communication_log=comm_a,
        coach=admin_b,
        coachee=member_user,
    )
    with pytest.raises(ValidationError) as exc:
        sc_coach.clean()
    assert "coach" in exc.value.message_dict
    assert "Coach must belong to the same workspace." in exc.value.message_dict["coach"]


# ============================================================================
# 6. Relational integrity, cascade, and multi-tenant constraints
# ============================================================================

def test_salesenablement_cascade_and_set_null_behaviors(tenant_a, admin_user, member_user):
    """Verify on_delete policies: rep and communication_log CASCADE, others SET_NULL."""
    doc = _salesenablement_document(tenant_a, name="Collateral To Delete")
    comp = _salesenablement_competitor(tenant_a, name="Competitor To Delete")
    content = _salesenablement_content(tenant_a, author=admin_user, document=doc, competitor=comp)

    # Deleting document sets content.document to NULL (SET_NULL)
    doc_id = doc.id
    doc.delete()
    content.refresh_from_db()
    assert content.document is None

    # Deleting competitor sets content.competitor to NULL (SET_NULL)
    comp.delete()
    content.refresh_from_db()
    assert content.competitor is None

    # Deleting author sets content.author to NULL (SET_NULL)
    # Create temporary author to avoid deleting shared fixture admin_user
    temp_author = User.objects.create_user(
        email="temp_author@example.com",
        username="temp_author",
        password="Password123!",
        tenant=tenant_a,
    )
    content.author = temp_author
    content.save()
    temp_author.delete()
    content.refresh_from_db()
    assert content.author is None

    # SalesPlaybook: deleting pipeline SET_NULL
    pipe = Pipeline.objects.create(tenant=tenant_a, name="Temp Pipeline")
    playbook = _salesenablement_playbook(tenant_a, owner=admin_user, pipeline=pipe)
    pipe.delete()
    playbook.refresh_from_db()
    assert playbook.pipeline is None

    # SalesCertification: deleting rep CASCADES certification
    temp_rep = User.objects.create_user(
        email="temp_rep@example.com",
        username="temp_rep",
        password="Password123!",
        tenant=tenant_a,
    )
    cert = _salesenablement_certification(tenant_a, rep=temp_rep, certified_by=admin_user)
    cert_id = cert.id
    temp_rep.delete()
    assert not SalesCertification.objects.filter(id=cert_id).exists()

    # CoachingScorecard: deleting communication_log CASCADES scorecard
    comm = _salesenablement_communication_log(tenant_a, owner=admin_user)
    scorecard = _salesenablement_scorecard(tenant_a, coach=admin_user, coachee=member_user, communication_log=comm)
    scorecard_id = scorecard.id
    comm.delete()
    assert not CoachingScorecard.objects.filter(id=scorecard_id).exists()


def test_salesenablement_unique_number_per_tenant(tenant_a, tenant_b, admin_user, member_user):
    """Verify that number uniqueness constraint is enforced per-tenant but allowed cross-tenant."""
    content_a = _salesenablement_content(tenant_a, author=admin_user)
    dupe_number = content_a.number

    # Violating unique constraint within same tenant raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EnablementContent.objects.create(
                tenant=tenant_a,
                number=dupe_number,
                title="Duplicate Number In Same Tenant",
                description="Collision test",
            )

    # Same number in different tenant succeeds (multi-tenant safe)
    content_b = EnablementContent.objects.create(
        tenant=tenant_b,
        number=dupe_number,
        title="Same Number In Different Tenant",
        description="Cross-tenant isolation test",
    )
    assert content_b.number == content_a.number
    assert content_b.tenant != content_a.tenant
