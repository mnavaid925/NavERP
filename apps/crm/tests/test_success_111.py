"""Tests for CRM sub-module 1.11 — Customer Success & Retention.

Covers:
  - Models: OnboardingTemplate auto-number (OTPL-#####), step_count, OnboardingTemplateStep ordering;
    HealthScoreHistory append-only; Survey.save() classification for all types + boundary scores;
    Survey.token generated on save.
  - compute_health_score: returns HealthScore; idempotent update_or_create but history appends;
    red tier creates ONE churn CrmTask (no duplicate on second compute); config param reuse.
  - Forms: OnboardingTemplateForm, OnboardingTemplateStepForm basics; HealthScoreConfigForm
    weight-sum + threshold constraints; SurveyForm per-type score range enforcement.
  - Views: onboardingtemplate list/detail (@login_required); create/edit/delete + step add/edit/delete
    (@tenant_admin_required); onboardingtemplate_apply (POST clone logic); recompute_all_health_scores
    (@tenant_admin_required); survey_results (NPS aggregate); survey_send (@tenant_admin_required);
    survey_respond (public, clamp, guard, feedback cap, non-ASCII digit rejection).
  - Multi-tenant IDOR: A's client on B's objects → 404 across all relevant models.
  - Auth / Permission: anonymous redirect; member blocked on admin actions; CSRF enforced.
  - Read-only: HealthScoreHistory has no create/edit/delete URL (NoReverseMatch).
"""
import pytest
from django.test import Client
from django.urls import reverse, NoReverseMatch

pytestmark = pytest.mark.django_db


# ======================================================================= helpers

def _make_party(tenant, name="Acme Ltd", kind="organization"):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, kind=kind, name=name)


def _make_template(tenant, name="Standard Onboarding", is_active=True):
    from apps.crm.models import OnboardingTemplate
    return OnboardingTemplate.objects.create(
        tenant=tenant, name=name, is_active=is_active, description="",
    )


def _make_template_step(tenant, template, order=1, title="Step 1", offset_days=0):
    from apps.crm.models import OnboardingTemplateStep
    return OnboardingTemplateStep.objects.create(
        tenant=tenant, template=template, order=order, title=title, offset_days=offset_days,
    )


def _make_survey(tenant, survey_type="nps", account=None, score=None, sent_at=None,
                 responded_at=None, classification=""):
    from apps.crm.models import Survey
    s = Survey.objects.create(
        tenant=tenant,
        survey_type=survey_type,
        account=account,
        score=score,
        sent_at=sent_at,
        responded_at=responded_at,
    )
    return s


def _make_health_score(tenant, account, score=80, tier="green"):
    from apps.crm.models import HealthScore
    return HealthScore.objects.create(tenant=tenant, account=account, score=score, tier=tier)


def _make_case(tenant, account, status="new"):
    from apps.crm.models import Case
    return Case.objects.create(
        tenant=tenant, account=account, subject="Test case",
        priority="medium", status=status,
    )


def _make_opportunity(tenant, account, stage="prospecting", amount="5000.00"):
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant, name="Test Opp", account=account,
        stage=stage, amount=amount, probability=20,
    )


def _make_crm_task(tenant, party=None, status="open", type_="follow_up", subject="Task",
                   priority="medium"):
    from apps.crm.models import CrmTask
    return CrmTask.objects.create(
        tenant=tenant, party=party, status=status, type=type_,
        subject=subject, priority=priority,
    )


# ======================================================================= Group 1 — Models

class TestOnboardingTemplateModel:
    def test_auto_number_has_otpl_prefix(self, tenant_a):
        tmpl = _make_template(tenant_a)
        assert tmpl.number.startswith("OTPL-")

    def test_auto_number_zero_padded(self, tenant_a):
        tmpl = _make_template(tenant_a)
        suffix = tmpl.number.split("-")[1]
        assert len(suffix) == 5

    def test_two_templates_different_numbers(self, tenant_a):
        t1 = _make_template(tenant_a, name="T1")
        t2 = _make_template(tenant_a, name="T2")
        assert t1.number != t2.number

    def test_number_scoped_per_tenant(self, tenant_a, tenant_b):
        t_a = _make_template(tenant_a, name="A")
        t_b = _make_template(tenant_b, name="B")
        # Each tenant gets its own sequence — both start at OTPL-00001
        assert t_a.number == t_b.number

    def test_str_contains_number_and_name(self, tenant_a):
        tmpl = _make_template(tenant_a, name="Onboard Pro")
        s = str(tmpl)
        assert tmpl.number in s
        assert "Onboard Pro" in s

    def test_is_active_default_true(self, tenant_a):
        from apps.crm.models import OnboardingTemplate
        tmpl = OnboardingTemplate.objects.create(tenant=tenant_a, name="Default Active")
        assert tmpl.is_active is True

    def test_step_count_zero_when_no_steps(self, tenant_a):
        tmpl = _make_template(tenant_a)
        assert tmpl.step_count == 0

    def test_step_count_counts_attached_steps(self, tenant_a):
        tmpl = _make_template(tenant_a)
        _make_template_step(tenant_a, tmpl, order=1, title="Step A")
        _make_template_step(tenant_a, tmpl, order=2, title="Step B")
        tmpl.refresh_from_db()
        assert tmpl.step_count == 2

    def test_step_count_property_not_stored(self, tenant_a):
        """step_count is a derived property — not a model field."""
        from apps.crm.models import OnboardingTemplate
        field_names = [f.name for f in OnboardingTemplate._meta.get_fields()]
        assert "step_count" not in field_names

    def test_unique_together_tenant_number(self, tenant_a):
        from django.db import IntegrityError
        t = _make_template(tenant_a)
        with pytest.raises(IntegrityError):
            from apps.crm.models import OnboardingTemplate
            # Force a duplicate number to trigger the unique_together
            OnboardingTemplate.objects.create(tenant=tenant_a, name="Dup", number=t.number)


class TestOnboardingTemplateStepModel:
    def test_step_str_is_title(self, tenant_a):
        tmpl = _make_template(tenant_a)
        step = _make_template_step(tenant_a, tmpl, title="Setup Environment")
        assert str(step) == "Setup Environment"

    def test_step_default_order_is_zero(self, tenant_a):
        from apps.crm.models import OnboardingTemplateStep
        tmpl = _make_template(tenant_a)
        step = OnboardingTemplateStep.objects.create(
            tenant=tenant_a, template=tmpl, title="Auto Order",
        )
        assert step.order == 0

    def test_step_ordering_by_order_then_id(self, tenant_a):
        tmpl = _make_template(tenant_a)
        s1 = _make_template_step(tenant_a, tmpl, order=2, title="Second")
        s2 = _make_template_step(tenant_a, tmpl, order=1, title="First")
        steps = list(tmpl.steps.all())
        assert steps[0] == s2  # order=1 first
        assert steps[1] == s1  # order=2 second

    def test_step_cascade_delete_with_template(self, tenant_a):
        from apps.crm.models import OnboardingTemplateStep
        tmpl = _make_template(tenant_a)
        _make_template_step(tenant_a, tmpl, title="Will be deleted")
        pk = tmpl.pk
        tmpl.delete()
        assert OnboardingTemplateStep.objects.filter(template_id=pk).count() == 0

    def test_step_offset_days_default_zero(self, tenant_a):
        tmpl = _make_template(tenant_a)
        step = _make_template_step(tenant_a, tmpl)
        assert step.offset_days == 0


class TestHealthScoreHistoryModel:
    def test_history_created_on_compute(self, tenant_a):
        from apps.crm.models import HealthScoreHistory, compute_health_score
        account = _make_party(tenant_a)
        compute_health_score(account, tenant_a)
        assert HealthScoreHistory.objects.filter(tenant=tenant_a, account=account).count() == 1

    def test_history_appends_on_second_compute(self, tenant_a):
        from apps.crm.models import HealthScoreHistory, compute_health_score
        account = _make_party(tenant_a)
        compute_health_score(account, tenant_a)
        compute_health_score(account, tenant_a)
        assert HealthScoreHistory.objects.filter(tenant=tenant_a, account=account).count() == 2

    def test_history_str_contains_account_and_score(self, tenant_a):
        from apps.crm.models import HealthScoreHistory
        account = _make_party(tenant_a)
        h = HealthScoreHistory.objects.create(
            tenant=tenant_a, account=account, score=75, tier="yellow",
        )
        s = str(h)
        assert "75" in s

    def test_history_no_create_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:healthscorehistory_create")

    def test_history_no_edit_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:healthscorehistory_edit", args=[1])

    def test_history_no_delete_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:healthscorehistory_delete", args=[1])

    def test_history_computed_at_auto_set(self, tenant_a):
        from apps.crm.models import HealthScoreHistory
        account = _make_party(tenant_a)
        h = HealthScoreHistory.objects.create(tenant=tenant_a, account=account, score=50, tier="yellow")
        assert h.computed_at is not None


class TestSurveySaveClassification:
    """Survey.save() auto-classifies based on survey_type + score at boundary values."""

    # ---- NPS (0–10): ≥9 promoter / ≥7 passive / else detractor
    def test_nps_score_9_is_promoter(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps", score=9)
        assert s.classification == "promoter"

    def test_nps_score_10_is_promoter(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps", score=10)
        assert s.classification == "promoter"

    def test_nps_score_8_is_passive(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps", score=8)
        assert s.classification == "passive"

    def test_nps_score_7_is_passive(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps", score=7)
        assert s.classification == "passive"

    def test_nps_score_6_is_detractor(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps", score=6)
        assert s.classification == "detractor"

    def test_nps_score_0_is_detractor(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps", score=0)
        assert s.classification == "detractor"

    # ---- CSAT (1–5): ≥4 satisfied / 3 neutral / ≤2 dissatisfied
    def test_csat_score_5_is_satisfied(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="csat", score=5)
        assert s.classification == "satisfied"

    def test_csat_score_4_is_satisfied(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="csat", score=4)
        assert s.classification == "satisfied"

    def test_csat_score_3_is_neutral(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="csat", score=3)
        assert s.classification == "neutral"

    def test_csat_score_2_is_dissatisfied(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="csat", score=2)
        assert s.classification == "dissatisfied"

    def test_csat_score_1_is_dissatisfied(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="csat", score=1)
        assert s.classification == "dissatisfied"

    # ---- CES (1–7): ≤2 easy / 3–5 neutral / ≥6 hard
    def test_ces_score_2_is_easy(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="ces", score=2)
        assert s.classification == "easy"

    def test_ces_score_1_is_easy(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="ces", score=1)
        assert s.classification == "easy"

    def test_ces_score_5_is_neutral(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="ces", score=5)
        assert s.classification == "neutral"

    def test_ces_score_3_is_neutral(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="ces", score=3)
        assert s.classification == "neutral"

    def test_ces_score_6_is_hard(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="ces", score=6)
        assert s.classification == "hard"

    def test_ces_score_7_is_hard(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="ces", score=7)
        assert s.classification == "hard"

    # ---- None score → blank classification
    def test_none_score_clears_classification(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps", score=None)
        assert s.classification == ""

    def test_resave_with_none_clears_classification(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps", score=9)
        assert s.classification == "promoter"
        s.score = None
        s.save()
        assert s.classification == ""

    def test_token_generated_on_save(self, tenant_a):
        s = _make_survey(tenant_a)
        assert s.token is not None
        assert len(s.token) > 10  # secrets.token_urlsafe(32) = 43 chars

    def test_token_not_regenerated_on_resave(self, tenant_a):
        s = _make_survey(tenant_a)
        original_token = s.token
        s.score = 9
        s.save()
        assert s.token == original_token

    def test_number_has_nps_prefix(self, tenant_a):
        s = _make_survey(tenant_a)
        assert s.number.startswith("NPS-")


# ======================================================================= Group 2 — compute_health_score

class TestComputeHealthScore:
    def test_returns_health_score_object(self, tenant_a):
        from apps.crm.models import HealthScore, compute_health_score
        account = _make_party(tenant_a)
        obj = compute_health_score(account, tenant_a)
        assert isinstance(obj, HealthScore)

    def test_idempotent_one_score_per_account(self, tenant_a):
        from apps.crm.models import HealthScore, compute_health_score
        account = _make_party(tenant_a)
        compute_health_score(account, tenant_a)
        compute_health_score(account, tenant_a)
        assert HealthScore.objects.filter(tenant=tenant_a, account=account).count() == 1

    def test_history_appends_on_each_compute(self, tenant_a):
        from apps.crm.models import HealthScoreHistory, compute_health_score
        account = _make_party(tenant_a)
        compute_health_score(account, tenant_a)
        compute_health_score(account, tenant_a)
        assert HealthScoreHistory.objects.filter(tenant=tenant_a, account=account).count() == 2

    def test_many_open_cases_lowers_score(self, tenant_a):
        """5 open cases → tickets_score = max(0, 100 - 5*20) = 0 → depressed overall score."""
        from apps.crm.models import compute_health_score
        account = _make_party(tenant_a)
        for _ in range(5):
            _make_case(tenant_a, account, status="new")
        hs = compute_health_score(account, tenant_a)
        assert hs.score < 60

    def test_detractor_nps_and_no_opp_can_be_red(self, tenant_a):
        """Account with many open cases + detractor NPS + no open opp → red tier."""
        from apps.crm.models import compute_health_score, HealthScoreConfig
        account = _make_party(tenant_a)
        # 5 open cases kills the tickets signal
        for _ in range(5):
            _make_case(tenant_a, account, status="new")
        # Detractor NPS survey (score=1 → detractor → nps_score=20)
        s = _make_survey(tenant_a, survey_type="nps", account=account, score=1)
        # no open opportunity → engagement=40
        # Force red by setting thresholds: red=60, yellow=80
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        config.red_threshold = 60
        config.yellow_threshold = 80
        config.save()
        hs = compute_health_score(account, tenant_a)
        assert hs.tier == "red"

    def test_red_tier_creates_churn_task(self, tenant_a):
        """Red tier creates one open follow_up CrmTask starting with 'Churn risk:'."""
        from apps.crm.models import compute_health_score, HealthScoreConfig, CrmTask
        account = _make_party(tenant_a)
        for _ in range(5):
            _make_case(tenant_a, account, status="new")
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        config.red_threshold = 95  # force red (almost everything)
        config.yellow_threshold = 99
        config.save()
        compute_health_score(account, tenant_a)
        tasks = CrmTask.objects.filter(
            tenant=tenant_a, party=account, type="follow_up",
            subject__startswith="Churn risk:", status="open",
        )
        assert tasks.count() == 1

    def test_red_tier_no_duplicate_churn_task(self, tenant_a):
        """Second compute on a red account must NOT create a second churn task."""
        from apps.crm.models import compute_health_score, HealthScoreConfig, CrmTask
        account = _make_party(tenant_a)
        for _ in range(5):
            _make_case(tenant_a, account, status="new")
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        config.red_threshold = 95
        config.yellow_threshold = 99
        config.save()
        compute_health_score(account, tenant_a)
        compute_health_score(account, tenant_a)  # second compute
        tasks = CrmTask.objects.filter(
            tenant=tenant_a, party=account, type="follow_up",
            subject__startswith="Churn risk:", status="open",
        )
        assert tasks.count() == 1

    def test_history_count_grows_after_second_red_compute(self, tenant_a):
        """History count grows on each compute even when tier stays red."""
        from apps.crm.models import compute_health_score, HealthScoreHistory, HealthScoreConfig
        account = _make_party(tenant_a)
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        config.red_threshold = 95
        config.yellow_threshold = 99
        config.save()
        compute_health_score(account, tenant_a)
        count1 = HealthScoreHistory.objects.filter(tenant=tenant_a, account=account).count()
        compute_health_score(account, tenant_a)
        count2 = HealthScoreHistory.objects.filter(tenant=tenant_a, account=account).count()
        assert count2 == count1 + 1

    def test_config_param_reuse(self, tenant_a):
        """Passing a pre-fetched config produces the same result as fetching one inside."""
        from apps.crm.models import compute_health_score, HealthScoreConfig
        account = _make_party(tenant_a)
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        hs_with = compute_health_score(account, tenant_a, config=config)
        # Reset the HealthScore so update_or_create doesn't find it
        hs_with.delete()
        # Clear history for a clean comparison (already 1 entry from first compute)
        account2 = _make_party(tenant_a, name="Acme Ltd 2")
        hs_without = compute_health_score(account2, tenant_a)
        # Both should compute the same score (same signals setup — no cases/tasks/opps)
        assert hs_with.score == hs_without.score
        assert hs_with.tier == hs_without.tier

    def test_score_within_0_100(self, tenant_a):
        from apps.crm.models import compute_health_score
        account = _make_party(tenant_a)
        hs = compute_health_score(account, tenant_a)
        assert 0 <= hs.score <= 100

    def test_open_opp_raises_engagement_score(self, tenant_a):
        """Account with an open opportunity → engagement_score=100 → higher overall score."""
        from apps.crm.models import compute_health_score
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account, stage="prospecting")
        hs = compute_health_score(account, tenant_a)
        # No penalising signals → score should be reasonably healthy
        assert hs.score >= 50

    def test_churn_task_priority_is_high(self, tenant_a):
        from apps.crm.models import compute_health_score, HealthScoreConfig, CrmTask
        account = _make_party(tenant_a)
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        config.red_threshold = 95
        config.yellow_threshold = 99
        config.save()
        compute_health_score(account, tenant_a)
        task = CrmTask.objects.filter(
            tenant=tenant_a, party=account, subject__startswith="Churn risk:",
        ).first()
        assert task is not None
        assert task.priority == "high"
        assert task.type == "follow_up"


# ======================================================================= Group 3 — Forms

class TestOnboardingTemplateForm:
    def test_valid_form_saves(self, tenant_a):
        from apps.crm.forms import OnboardingTemplateForm
        form = OnboardingTemplateForm(
            data={"name": "My Template", "description": "", "is_active": True},
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        from apps.crm.forms import OnboardingTemplateForm
        form = OnboardingTemplateForm(
            data={"name": "", "description": "", "is_active": True},
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "name" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.crm.forms import OnboardingTemplateForm
        form = OnboardingTemplateForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_a_form_field(self, tenant_a):
        from apps.crm.forms import OnboardingTemplateForm
        form = OnboardingTemplateForm(tenant=tenant_a)
        assert "number" not in form.fields


class TestOnboardingTemplateStepForm:
    def test_valid_step_form(self, tenant_a):
        from apps.crm.forms import OnboardingTemplateStepForm
        form = OnboardingTemplateStepForm(
            data={"title": "Step 1", "description": "", "offset_days": 3},
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_title_required(self, tenant_a):
        from apps.crm.forms import OnboardingTemplateStepForm
        form = OnboardingTemplateStepForm(
            data={"title": "", "description": "", "offset_days": 0},
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "title" in form.errors

    def test_template_not_a_form_field(self, tenant_a):
        from apps.crm.forms import OnboardingTemplateStepForm
        form = OnboardingTemplateStepForm(tenant=tenant_a)
        assert "template" not in form.fields


class TestHealthScoreConfigForm:
    def test_valid_weights_sum_100(self, tenant_a):
        from apps.crm.forms import HealthScoreConfigForm
        from apps.crm.models import HealthScoreConfig
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        form = HealthScoreConfigForm(
            data={
                "weight_tickets": "25", "weight_nps": "25",
                "weight_tasks": "25", "weight_engagement": "25",
                "red_threshold": "40", "yellow_threshold": "70",
            },
            instance=config, tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_invalid_weights_not_sum_100(self, tenant_a):
        from apps.crm.forms import HealthScoreConfigForm
        from apps.crm.models import HealthScoreConfig
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        form = HealthScoreConfigForm(
            data={
                "weight_tickets": "30", "weight_nps": "30",
                "weight_tasks": "30", "weight_engagement": "30",  # 120 — wrong
                "red_threshold": "40", "yellow_threshold": "70",
            },
            instance=config, tenant=tenant_a,
        )
        assert not form.is_valid()

    def test_invalid_red_gte_yellow(self, tenant_a):
        from apps.crm.forms import HealthScoreConfigForm
        from apps.crm.models import HealthScoreConfig
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        form = HealthScoreConfigForm(
            data={
                "weight_tickets": "25", "weight_nps": "25",
                "weight_tasks": "25", "weight_engagement": "25",
                "red_threshold": "70", "yellow_threshold": "40",  # red >= yellow — wrong
            },
            instance=config, tenant=tenant_a,
        )
        assert not form.is_valid()

    def test_invalid_red_equal_yellow(self, tenant_a):
        from apps.crm.forms import HealthScoreConfigForm
        from apps.crm.models import HealthScoreConfig
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        form = HealthScoreConfigForm(
            data={
                "weight_tickets": "25", "weight_nps": "25",
                "weight_tasks": "25", "weight_engagement": "25",
                "red_threshold": "50", "yellow_threshold": "50",  # equal — wrong
            },
            instance=config, tenant=tenant_a,
        )
        assert not form.is_valid()


class TestSurveyForm:
    def test_valid_nps_score_10(self, tenant_a):
        from apps.crm.forms import SurveyForm
        form = SurveyForm(
            data={
                "account": "", "contact": "", "survey_type": "nps",
                "trigger": "manual", "related_case": "",
                "score": "10", "feedback_text": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_valid_nps_score_0(self, tenant_a):
        from apps.crm.forms import SurveyForm
        form = SurveyForm(
            data={
                "account": "", "contact": "", "survey_type": "nps",
                "trigger": "manual", "related_case": "",
                "score": "0", "feedback_text": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_invalid_csat_score_8(self, tenant_a):
        """CSAT allows 1–5; score=8 must be rejected."""
        from apps.crm.forms import SurveyForm
        form = SurveyForm(
            data={
                "account": "", "contact": "", "survey_type": "csat",
                "trigger": "manual", "related_case": "",
                "score": "8", "feedback_text": "",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "score" in form.errors

    def test_valid_csat_score_5(self, tenant_a):
        from apps.crm.forms import SurveyForm
        form = SurveyForm(
            data={
                "account": "", "contact": "", "survey_type": "csat",
                "trigger": "manual", "related_case": "",
                "score": "5", "feedback_text": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_invalid_csat_score_0(self, tenant_a):
        """CSAT minimum is 1; score=0 must be rejected."""
        from apps.crm.forms import SurveyForm
        form = SurveyForm(
            data={
                "account": "", "contact": "", "survey_type": "csat",
                "trigger": "manual", "related_case": "",
                "score": "0", "feedback_text": "",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "score" in form.errors

    def test_invalid_ces_score_8(self, tenant_a):
        """CES allows 1–7; score=8 must be rejected."""
        from apps.crm.forms import SurveyForm
        form = SurveyForm(
            data={
                "account": "", "contact": "", "survey_type": "ces",
                "trigger": "manual", "related_case": "",
                "score": "8", "feedback_text": "",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "score" in form.errors

    def test_valid_ces_score_7(self, tenant_a):
        from apps.crm.forms import SurveyForm
        form = SurveyForm(
            data={
                "account": "", "contact": "", "survey_type": "ces",
                "trigger": "manual", "related_case": "",
                "score": "7", "feedback_text": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_sent_at_not_a_form_field(self, tenant_a):
        """sent_at is stamped by the survey_send action — must not be exposed in the form."""
        from apps.crm.forms import SurveyForm
        form = SurveyForm(tenant=tenant_a)
        assert "sent_at" not in form.fields

    def test_blank_score_is_allowed(self, tenant_a):
        """score is optional (null/blank) — blank submit must not raise a range error."""
        from apps.crm.forms import SurveyForm
        form = SurveyForm(
            data={
                "account": "", "contact": "", "survey_type": "nps",
                "trigger": "manual", "related_case": "",
                "score": "", "feedback_text": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors


# ======================================================================= Group 4 — onboardingtemplate_apply

class TestOnboardingTemplateApply:
    def test_apply_creates_plan_with_cloned_steps(self, client_a, tenant_a, admin_user):
        from apps.crm.models import OnboardingPlan, OnboardingStep
        account = _make_party(tenant_a, name="Client A")
        tmpl = _make_template(tenant_a, is_active=True)
        _make_template_step(tenant_a, tmpl, order=1, title="Step One", offset_days=0)
        _make_template_step(tenant_a, tmpl, order=2, title="Step Two", offset_days=7)
        resp = client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {"account": str(account.pk)},
        )
        assert resp.status_code == 302
        plan = OnboardingPlan.objects.filter(tenant=tenant_a, account=account).first()
        assert plan is not None
        assert OnboardingStep.objects.filter(tenant=tenant_a, plan=plan).count() == 2

    def test_apply_sets_correct_due_dates(self, client_a, tenant_a, admin_user):
        from apps.crm.models import OnboardingPlan, OnboardingStep
        from django.utils import timezone
        import datetime
        account = _make_party(tenant_a, name="Due Date Client")
        tmpl = _make_template(tenant_a, is_active=True)
        _make_template_step(tenant_a, tmpl, order=1, title="Day 0", offset_days=0)
        _make_template_step(tenant_a, tmpl, order=2, title="Day 7", offset_days=7)
        today = timezone.now().date()
        client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {"account": str(account.pk)},
        )
        plan = OnboardingPlan.objects.filter(tenant=tenant_a, account=account).first()
        steps = list(OnboardingStep.objects.filter(plan=plan).order_by("order"))
        assert steps[0].due_date == today
        assert steps[1].due_date == today + datetime.timedelta(days=7)

    def test_apply_inactive_template_no_plan(self, client_a, tenant_a):
        from apps.crm.models import OnboardingPlan
        account = _make_party(tenant_a, name="Inactive Client")
        tmpl = _make_template(tenant_a, is_active=False)
        _make_template_step(tenant_a, tmpl, title="Step")
        initial_count = OnboardingPlan.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {"account": str(account.pk)},
        )
        assert resp.status_code == 302
        assert OnboardingPlan.objects.filter(tenant=tenant_a).count() == initial_count

    def test_apply_no_account_no_plan(self, client_a, tenant_a):
        from apps.crm.models import OnboardingPlan
        tmpl = _make_template(tenant_a, is_active=True)
        _make_template_step(tenant_a, tmpl, title="Step")
        initial_count = OnboardingPlan.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {"account": ""},  # blank
        )
        assert resp.status_code == 302
        assert OnboardingPlan.objects.filter(tenant=tenant_a).count() == initial_count

    def test_apply_blank_account_no_plan(self, client_a, tenant_a):
        from apps.crm.models import OnboardingPlan
        tmpl = _make_template(tenant_a, is_active=True)
        _make_template_step(tenant_a, tmpl, title="Step")
        initial = OnboardingPlan.objects.filter(tenant=tenant_a).count()
        client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {},  # no account key at all
        )
        assert OnboardingPlan.objects.filter(tenant=tenant_a).count() == initial

    def test_apply_cross_tenant_account_404(self, client_a, tenant_b):
        """Template belongs to tenant_a; account belongs to tenant_b → 404."""
        account_b = _make_party(tenant_b, name="B's Client")
        # Build a template for tenant_a
        from apps.core.models import Tenant
        tenant_a = client_a.session  # not available — grab from admin_user fixture indirectly
        # Use the admin_user's tenant indirectly via the test
        from apps.accounts.models import User
        admin = User.objects.get(username="admin_acme")
        t_a = admin.tenant
        tmpl = _make_template(t_a, is_active=True)
        _make_template_step(t_a, tmpl, title="Step")
        resp = client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {"account": str(account_b.pk)},
        )
        assert resp.status_code == 404

    def test_apply_plan_is_tenant_scoped(self, client_a, tenant_a, admin_user):
        from apps.crm.models import OnboardingPlan
        account = _make_party(tenant_a, name="Scoped Client")
        tmpl = _make_template(tenant_a, is_active=True)
        _make_template_step(tenant_a, tmpl, title="Step")
        client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {"account": str(account.pk)},
        )
        plan = OnboardingPlan.objects.filter(account=account).first()
        assert plan is not None
        assert plan.tenant == tenant_a

    def test_apply_steps_are_tenant_scoped(self, client_a, tenant_a, admin_user):
        from apps.crm.models import OnboardingPlan, OnboardingStep
        account = _make_party(tenant_a, name="Step-Scoped Client")
        tmpl = _make_template(tenant_a, is_active=True)
        _make_template_step(tenant_a, tmpl, title="Step")
        client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {"account": str(account.pk)},
        )
        plan = OnboardingPlan.objects.filter(account=account).first()
        for step in OnboardingStep.objects.filter(plan=plan):
            assert step.tenant == tenant_a


# ======================================================================= Group 5 — Permissions

class TestOnboardingTemplatePermissions:
    """create/edit/delete + step add/edit/delete = @tenant_admin_required; list/detail = @login_required."""

    def test_list_anonymous_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:onboardingtemplate_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_list_member_200(self, member_client):
        resp = member_client.get(reverse("crm:onboardingtemplate_list"))
        assert resp.status_code == 200

    def test_list_admin_200(self, client_a):
        resp = client_a.get(reverse("crm:onboardingtemplate_list"))
        assert resp.status_code == 200

    def test_detail_member_200(self, member_client, tenant_a):
        tmpl = _make_template(tenant_a)
        resp = member_client.get(reverse("crm:onboardingtemplate_detail", args=[tmpl.pk]))
        assert resp.status_code == 200

    def test_detail_anonymous_redirects(self, tenant_a):
        tmpl = _make_template(tenant_a)
        c = Client()
        resp = c.get(reverse("crm:onboardingtemplate_detail", args=[tmpl.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_create_member_get_blocked(self, member_client):
        resp = member_client.get(reverse("crm:onboardingtemplate_create"))
        assert resp.status_code in (302, 403)

    def test_create_admin_get_200(self, client_a):
        resp = client_a.get(reverse("crm:onboardingtemplate_create"))
        assert resp.status_code == 200

    def test_create_member_post_no_create(self, member_client, tenant_a):
        from apps.crm.models import OnboardingTemplate
        initial = OnboardingTemplate.objects.filter(tenant=tenant_a).count()
        member_client.post(reverse("crm:onboardingtemplate_create"), {
            "name": "Injected Template", "description": "", "is_active": True,
        })
        assert OnboardingTemplate.objects.filter(tenant=tenant_a).count() == initial

    def test_create_admin_post_creates(self, client_a, tenant_a):
        from apps.crm.models import OnboardingTemplate
        resp = client_a.post(reverse("crm:onboardingtemplate_create"), {
            "name": "Admin Template", "description": "Desc", "is_active": True,
        })
        assert resp.status_code == 302
        assert OnboardingTemplate.objects.filter(tenant=tenant_a, name="Admin Template").exists()

    def test_edit_member_get_blocked(self, member_client, tenant_a):
        tmpl = _make_template(tenant_a)
        resp = member_client.get(reverse("crm:onboardingtemplate_edit", args=[tmpl.pk]))
        assert resp.status_code in (302, 403)

    def test_edit_admin_get_200(self, client_a, tenant_a):
        tmpl = _make_template(tenant_a)
        resp = client_a.get(reverse("crm:onboardingtemplate_edit", args=[tmpl.pk]))
        assert resp.status_code == 200

    def test_edit_member_post_no_change(self, member_client, tenant_a):
        tmpl = _make_template(tenant_a, name="Original Name")
        member_client.post(reverse("crm:onboardingtemplate_edit", args=[tmpl.pk]), {
            "name": "Hacked Name", "description": "", "is_active": True,
        })
        tmpl.refresh_from_db()
        assert tmpl.name == "Original Name"

    def test_edit_admin_post_updates(self, client_a, tenant_a):
        tmpl = _make_template(tenant_a, name="Old Name")
        resp = client_a.post(reverse("crm:onboardingtemplate_edit", args=[tmpl.pk]), {
            "name": "New Name", "description": "", "is_active": True,
        })
        assert resp.status_code == 302
        tmpl.refresh_from_db()
        assert tmpl.name == "New Name"

    def test_delete_post_only_for_admin(self, client_a, tenant_a):
        """GET to delete → 405 (POST-only)."""
        tmpl = _make_template(tenant_a)
        resp = client_a.get(reverse("crm:onboardingtemplate_delete", args=[tmpl.pk]))
        assert resp.status_code == 405

    def test_delete_member_blocked(self, member_client, tenant_a):
        from apps.crm.models import OnboardingTemplate
        tmpl = _make_template(tenant_a)
        pk = tmpl.pk
        member_client.post(reverse("crm:onboardingtemplate_delete", args=[pk]))
        assert OnboardingTemplate.objects.filter(pk=pk).exists()

    def test_delete_admin_post_deletes(self, client_a, tenant_a):
        from apps.crm.models import OnboardingTemplate
        tmpl = _make_template(tenant_a)
        pk = tmpl.pk
        resp = client_a.post(reverse("crm:onboardingtemplate_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OnboardingTemplate.objects.filter(pk=pk).exists()

    def test_step_add_member_blocked(self, member_client, tenant_a):
        from apps.crm.models import OnboardingTemplateStep
        tmpl = _make_template(tenant_a)
        initial = OnboardingTemplateStep.objects.filter(template=tmpl).count()
        member_client.post(reverse("crm:onboardingtemplatestep_add", args=[tmpl.pk]), {
            "title": "Hacked Step", "description": "", "offset_days": "0",
        })
        assert OnboardingTemplateStep.objects.filter(template=tmpl).count() == initial

    def test_step_add_admin_creates(self, client_a, tenant_a):
        from apps.crm.models import OnboardingTemplateStep
        tmpl = _make_template(tenant_a)
        resp = client_a.post(reverse("crm:onboardingtemplatestep_add", args=[tmpl.pk]), {
            "title": "Admin Step", "description": "", "offset_days": "5",
        })
        assert resp.status_code == 302
        assert OnboardingTemplateStep.objects.filter(template=tmpl, title="Admin Step").exists()

    def test_step_delete_member_blocked(self, member_client, tenant_a):
        from apps.crm.models import OnboardingTemplateStep
        tmpl = _make_template(tenant_a)
        step = _make_template_step(tenant_a, tmpl, title="Protected Step")
        pk = step.pk
        member_client.post(reverse("crm:onboardingtemplatestep_delete", args=[pk]))
        assert OnboardingTemplateStep.objects.filter(pk=pk).exists()

    def test_step_delete_admin_deletes(self, client_a, tenant_a):
        from apps.crm.models import OnboardingTemplateStep
        tmpl = _make_template(tenant_a)
        step = _make_template_step(tenant_a, tmpl, title="Delete Me")
        pk = step.pk
        resp = client_a.post(reverse("crm:onboardingtemplatestep_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OnboardingTemplateStep.objects.filter(pk=pk).exists()

    def test_step_edit_member_blocked(self, member_client, tenant_a):
        tmpl = _make_template(tenant_a)
        step = _make_template_step(tenant_a, tmpl, title="Original")
        resp = member_client.get(reverse("crm:onboardingtemplatestep_edit", args=[step.pk]))
        assert resp.status_code in (302, 403)

    def test_step_edit_admin_get_200(self, client_a, tenant_a):
        tmpl = _make_template(tenant_a)
        step = _make_template_step(tenant_a, tmpl, title="Editable")
        resp = client_a.get(reverse("crm:onboardingtemplatestep_edit", args=[step.pk]))
        assert resp.status_code == 200


class TestRecomputeAllPermissions:
    def test_member_post_blocked(self, member_client):
        resp = member_client.post(reverse("crm:recompute_all_health_scores"))
        assert resp.status_code in (302, 403)

    def test_admin_post_302(self, client_a):
        resp = client_a.post(reverse("crm:recompute_all_health_scores"))
        assert resp.status_code == 302

    def test_anonymous_redirects(self):
        c = Client()
        resp = c.post(reverse("crm:recompute_all_health_scores"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestSurveySendPermissions:
    def test_member_post_blocked(self, member_client, tenant_a):
        s = _make_survey(tenant_a)
        resp = member_client.post(reverse("crm:survey_send", args=[s.pk]))
        assert resp.status_code in (302, 403)
        s.refresh_from_db()
        assert s.sent_at is None

    def test_admin_post_stamps_sent_at(self, client_a, tenant_a):
        s = _make_survey(tenant_a)
        resp = client_a.post(reverse("crm:survey_send", args=[s.pk]))
        assert resp.status_code == 302
        s.refresh_from_db()
        assert s.sent_at is not None

    def test_anonymous_redirects(self, tenant_a):
        s = _make_survey(tenant_a)
        c = Client()
        resp = c.post(reverse("crm:survey_send", args=[s.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_idempotent_send_no_double_stamp(self, client_a, tenant_a):
        """Sending an already-sent survey must not overwrite sent_at."""
        from django.utils import timezone
        import datetime
        original_time = timezone.now() - datetime.timedelta(hours=1)
        s = _make_survey(tenant_a, sent_at=original_time)
        client_a.post(reverse("crm:survey_send", args=[s.pk]))
        s.refresh_from_db()
        # sent_at should still be the original time (idempotent)
        diff = abs((s.sent_at - original_time).total_seconds())
        assert diff < 5  # within 5 seconds of the original


class TestRecomputeHealthScoreView:
    def test_member_can_recompute_own_tenant_score(self, member_client, tenant_a):
        """recompute_health_score is @login_required (not @tenant_admin_required)."""
        account = _make_party(tenant_a)
        hs = _make_health_score(tenant_a, account)
        resp = member_client.post(reverse("crm:recompute_health_score", args=[hs.pk]))
        assert resp.status_code == 302

    def test_anonymous_redirects(self, tenant_a):
        account = _make_party(tenant_a)
        hs = _make_health_score(tenant_a, account)
        c = Client()
        resp = c.post(reverse("crm:recompute_health_score", args=[hs.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ======================================================================= Group 6 — survey_respond (public)

class TestSurveyRespond:
    def test_get_no_login_returns_200(self, tenant_a):
        """Public endpoint — no login required for GET."""
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client()
        resp = c.get(reverse("crm:survey_respond", args=[s.token]))
        assert resp.status_code == 200

    def test_post_valid_nps_score_saves_and_classifies(self, tenant_a):
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client()
        resp = c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "9"})
        assert resp.status_code == 302
        s.refresh_from_db()
        assert s.score == 9
        assert s.classification == "promoter"
        assert s.responded_at is not None

    def test_post_csat_score_clamped_to_max_5(self, tenant_a):
        """CSAT scale max is 5; posting score=9 must be clamped to 5."""
        s = _make_survey(tenant_a, survey_type="csat")
        c = Client()
        c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "9"})
        s.refresh_from_db()
        assert s.score == 5
        assert s.classification == "satisfied"

    def test_post_csat_score_clamped_to_min_1(self, tenant_a):
        """CSAT scale min is 1; posting score=0 must be clamped to 1."""
        s = _make_survey(tenant_a, survey_type="csat")
        c = Client()
        c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "0"})
        s.refresh_from_db()
        assert s.score == 1

    def test_post_empty_score_no_response_lock(self, tenant_a):
        """Empty score → no responded_at stamp → survey remains open."""
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client()
        resp = c.post(reverse("crm:survey_respond", args=[s.token]), {"score": ""})
        assert resp.status_code == 200  # stays on form
        s.refresh_from_db()
        assert s.responded_at is None

    def test_post_invalid_score_string_no_crash(self, tenant_a):
        """Non-numeric score (plain string) → no crash, no responded_at."""
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client()
        resp = c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "abc"})
        assert resp.status_code == 200
        s.refresh_from_db()
        assert s.responded_at is None

    def test_post_unicode_digit_no_crash(self, tenant_a):
        """Unicode superscript digit '²' looks like int but int() raises ValueError → safe rejection."""
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client()
        # chr(178) = '²', which isdigit() returns True for but int() raises ValueError on
        resp = c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "²"})
        assert resp.status_code == 200
        s.refresh_from_db()
        assert s.responded_at is None

    def test_second_post_after_valid_response_is_noop(self, tenant_a):
        """Once responded_at is set, a second POST must not update score."""
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client()
        c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "9"})
        s.refresh_from_db()
        original_responded_at = s.responded_at
        c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "0"})
        s.refresh_from_db()
        # Score must NOT change after locking
        assert s.score == 9
        assert s.responded_at == original_responded_at

    def test_feedback_capped_at_4000_chars(self, tenant_a):
        """Feedback longer than 4000 characters must be silently truncated."""
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client()
        long_feedback = "x" * 5000
        c.post(reverse("crm:survey_respond", args=[s.token]), {
            "score": "8", "feedback_text": long_feedback,
        })
        s.refresh_from_db()
        assert len(s.feedback_text) <= 4000

    def test_ces_clamped_between_1_and_7(self, tenant_a):
        """CES scale is 1–7; posting 10 → clamped to 7."""
        s = _make_survey(tenant_a, survey_type="ces")
        c = Client()
        c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "10"})
        s.refresh_from_db()
        assert s.score == 7

    def test_respond_sets_classification_correctly(self, tenant_a):
        """NPS score=7 via respond → classification=passive."""
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client()
        c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "7"})
        s.refresh_from_db()
        assert s.classification == "passive"


# ======================================================================= Group 7 — survey_results

class TestSurveyResults:
    def test_results_requires_login(self):
        c = Client()
        resp = c.get(reverse("crm:survey_results"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_results_200_for_member(self, member_client):
        resp = member_client.get(reverse("crm:survey_results"))
        assert resp.status_code == 200

    def test_results_nps_score_calculation(self, client_a, tenant_a):
        """NPS = round((promoters - detractors) / nps_total * 100)."""
        from django.utils import timezone
        now = timezone.now()
        # 2 promoters + 1 passive + 1 detractor = 4 total NPS
        # NPS = round((2 - 1) / 4 * 100) = 25
        for score in [9, 10]:
            s = _make_survey(tenant_a, survey_type="nps", score=score)
            s.sent_at = now
            s.responded_at = now
            s.save()
        s_passive = _make_survey(tenant_a, survey_type="nps", score=8)
        s_passive.sent_at = now
        s_passive.responded_at = now
        s_passive.save()
        s_det = _make_survey(tenant_a, survey_type="nps", score=5)
        s_det.sent_at = now
        s_det.responded_at = now
        s_det.save()
        resp = client_a.get(reverse("crm:survey_results"))
        assert resp.status_code == 200
        assert resp.context["nps_score"] == 25
        assert resp.context["promoters"] == 2
        assert resp.context["passives"] == 1
        assert resp.context["detractors"] == 1

    def test_results_nps_none_when_no_nps_surveys(self, client_a, tenant_a):
        """No NPS surveys → nps_score must be None (not a crash)."""
        resp = client_a.get(reverse("crm:survey_results"))
        assert resp.context["nps_score"] is None

    def test_results_csat_avg_correct(self, client_a, tenant_a):
        """CSAT average computed from responded surveys."""
        from django.utils import timezone
        now = timezone.now()
        for score in [4, 5]:
            s = _make_survey(tenant_a, survey_type="csat", score=score)
            s.sent_at = now
            s.responded_at = now
            s.save()
        resp = client_a.get(reverse("crm:survey_results"))
        assert resp.context["csat_avg"] == pytest.approx(4.5, abs=0.1)
        assert resp.context["csat_count"] == 2

    def test_results_empty_data_no_crash(self, client_a):
        resp = client_a.get(reverse("crm:survey_results"))
        assert resp.status_code == 200
        assert resp.context["nps_score"] is None

    def test_results_context_has_required_keys(self, client_a):
        resp = client_a.get(reverse("crm:survey_results"))
        for key in ("total", "sent", "responded_total", "nps_total", "promoters",
                    "passives", "detractors", "nps_score", "csat_avg", "ces_avg"):
            assert key in resp.context, f"Missing context key: {key}"


# ======================================================================= Group 8 — Multi-tenant IDOR

class TestMultiTenantIsolation:
    """Tenant A's authenticated client must get 404 on Tenant B's objects."""

    def test_onboardingtemplate_detail_cross_tenant_404(self, client_a, tenant_b):
        tmpl_b = _make_template(tenant_b, name="B Template")
        resp = client_a.get(reverse("crm:onboardingtemplate_detail", args=[tmpl_b.pk]))
        assert resp.status_code == 404

    def test_onboardingtemplate_edit_cross_tenant_404(self, client_a, tenant_b):
        tmpl_b = _make_template(tenant_b, name="B Template")
        resp = client_a.get(reverse("crm:onboardingtemplate_edit", args=[tmpl_b.pk]))
        assert resp.status_code == 404

    def test_onboardingtemplate_delete_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import OnboardingTemplate
        tmpl_b = _make_template(tenant_b, name="B Template")
        pk = tmpl_b.pk
        resp = client_a.post(reverse("crm:onboardingtemplate_delete", args=[pk]))
        assert resp.status_code == 404
        assert OnboardingTemplate.objects.filter(pk=pk).exists()

    def test_onboardingtemplate_apply_cross_tenant_404(self, client_a, tenant_b):
        tmpl_b = _make_template(tenant_b, name="B Template", is_active=True)
        _make_template_step(tenant_b, tmpl_b, title="Step")
        account_b = _make_party(tenant_b, name="B Client")
        resp = client_a.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl_b.pk]),
            {"account": str(account_b.pk)},
        )
        assert resp.status_code == 404

    def test_onboardingtemplatestep_edit_cross_tenant_404(self, client_a, tenant_b):
        tmpl_b = _make_template(tenant_b)
        step_b = _make_template_step(tenant_b, tmpl_b, title="B Step")
        resp = client_a.get(reverse("crm:onboardingtemplatestep_edit", args=[step_b.pk]))
        assert resp.status_code == 404

    def test_onboardingtemplatestep_delete_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import OnboardingTemplateStep
        tmpl_b = _make_template(tenant_b)
        step_b = _make_template_step(tenant_b, tmpl_b, title="B Step")
        pk = step_b.pk
        resp = client_a.post(reverse("crm:onboardingtemplatestep_delete", args=[pk]))
        assert resp.status_code == 404
        assert OnboardingTemplateStep.objects.filter(pk=pk).exists()

    def test_healthscore_detail_cross_tenant_404(self, client_a, tenant_b):
        account_b = _make_party(tenant_b, name="B Co")
        hs_b = _make_health_score(tenant_b, account_b)
        resp = client_a.get(reverse("crm:healthscore_detail", args=[hs_b.pk]))
        assert resp.status_code == 404

    def test_recompute_health_score_cross_tenant_404(self, client_a, tenant_b):
        account_b = _make_party(tenant_b, name="B Co Recompute")
        hs_b = _make_health_score(tenant_b, account_b)
        resp = client_a.post(reverse("crm:recompute_health_score", args=[hs_b.pk]))
        assert resp.status_code == 404

    def test_survey_detail_cross_tenant_404(self, client_a, tenant_b):
        s_b = _make_survey(tenant_b)
        resp = client_a.get(reverse("crm:survey_detail", args=[s_b.pk]))
        assert resp.status_code == 404

    def test_survey_send_cross_tenant_404(self, client_a, tenant_b):
        s_b = _make_survey(tenant_b)
        resp = client_a.post(reverse("crm:survey_send", args=[s_b.pk]))
        assert resp.status_code == 404

    def test_onboardingtemplate_list_shows_only_own_tenant(self, client_a, tenant_a, tenant_b):
        tmpl_a = _make_template(tenant_a, name="A Template")
        tmpl_b = _make_template(tenant_b, name="B Template")
        resp = client_a.get(reverse("crm:onboardingtemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert tmpl_a.pk in pks
        assert tmpl_b.pk not in pks

    def test_survey_respond_token_works_regardless_of_tenant(self, tenant_b):
        """survey_respond is PUBLIC — token is the credential; tenant_b's survey accessible."""
        s = _make_survey(tenant_b, survey_type="nps")
        c = Client()
        resp = c.get(reverse("crm:survey_respond", args=[s.token]))
        assert resp.status_code == 200


# ======================================================================= Group 9 — CSRF Enforcement

class TestCsrfEnforcement:
    """CSRF-enforcing client (enforce_csrf_checks=True) must get 403 on unsafe POSTs."""

    def _csrf_client(self, user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        return c

    def test_onboardingtemplate_apply_csrf(self, tenant_a, admin_user):
        tmpl = _make_template(tenant_a, is_active=True)
        _make_template_step(tenant_a, tmpl, title="Step")
        account = _make_party(tenant_a)
        c = self._csrf_client(admin_user)
        resp = c.post(
            reverse("crm:onboardingtemplate_apply", args=[tmpl.pk]),
            {"account": str(account.pk)},
        )
        assert resp.status_code == 403

    def test_recompute_all_health_scores_csrf(self, tenant_a, admin_user):
        c = self._csrf_client(admin_user)
        resp = c.post(reverse("crm:recompute_all_health_scores"))
        assert resp.status_code == 403

    def test_survey_send_csrf(self, tenant_a, admin_user):
        s = _make_survey(tenant_a)
        c = self._csrf_client(admin_user)
        resp = c.post(reverse("crm:survey_send", args=[s.pk]))
        assert resp.status_code == 403

    def test_survey_respond_csrf(self, tenant_a):
        """survey_respond is public but still CSRF-enforced on POST."""
        s = _make_survey(tenant_a, survey_type="nps")
        c = Client(enforce_csrf_checks=True)
        resp = c.post(reverse("crm:survey_respond", args=[s.token]), {"score": "9"})
        assert resp.status_code == 403

    def test_onboardingtemplate_delete_csrf(self, tenant_a, admin_user):
        from apps.crm.models import OnboardingTemplate
        tmpl = _make_template(tenant_a)
        pk = tmpl.pk
        c = self._csrf_client(admin_user)
        resp = c.post(reverse("crm:onboardingtemplate_delete", args=[pk]))
        assert resp.status_code == 403
        assert OnboardingTemplate.objects.filter(pk=pk).exists()


# ======================================================================= Group 10 — Read-only HealthScoreHistory

class TestHealthScoreHistoryReadOnly:
    def test_no_create_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:healthscorehistory_create")

    def test_no_edit_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:healthscorehistory_edit", args=[1])

    def test_no_delete_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:healthscorehistory_delete", args=[1])


# ======================================================================= Group 11 — onboardingtemplate_list context

class TestOnboardingTemplateListView:
    def test_list_context_has_object_list(self, client_a):
        resp = client_a.get(reverse("crm:onboardingtemplate_list"))
        assert "object_list" in resp.context

    def test_list_context_shows_own_templates(self, client_a, tenant_a, tenant_b):
        tmpl_a = _make_template(tenant_a, name="Mine")
        tmpl_b = _make_template(tenant_b, name="Theirs")
        resp = client_a.get(reverse("crm:onboardingtemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert tmpl_a.pk in pks
        assert tmpl_b.pk not in pks


# ======================================================================= Group 12 — health_config_edit

class TestHealthConfigEdit:
    def test_member_get_blocked(self, member_client):
        resp = member_client.get(reverse("crm:health_config_edit"))
        assert resp.status_code in (302, 403)

    def test_admin_get_200(self, client_a):
        resp = client_a.get(reverse("crm:health_config_edit"))
        assert resp.status_code == 200

    def test_admin_post_updates_config(self, client_a, tenant_a):
        from apps.crm.models import HealthScoreConfig
        resp = client_a.post(reverse("crm:health_config_edit"), {
            "weight_tickets": "30", "weight_nps": "30",
            "weight_tasks": "20", "weight_engagement": "20",
            "red_threshold": "35", "yellow_threshold": "65",
        })
        assert resp.status_code == 302
        config = HealthScoreConfig.objects.get(tenant=tenant_a)
        from decimal import Decimal
        assert config.weight_tickets == Decimal("30")
        assert config.red_threshold == 35
