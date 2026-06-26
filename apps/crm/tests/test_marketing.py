"""Tests for CRM §1.3 Marketing Automation sub-module.

Covers: Campaign (enhanced), CampaignMember, EmailTemplate, EmailCampaign,
LandingPage, FormSubmission — models, forms, views, public endpoint, and
multi-tenant IDOR isolation.
"""
import pytest
from decimal import Decimal
from django.urls import reverse
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================= Fixtures
@pytest.fixture
def campaign_a(db, tenant_a):
    from apps.crm.models import Campaign
    return Campaign.objects.create(
        tenant=tenant_a,
        name="Spring Promo",
        type="email",
        status="planned",
        budget_planned="2000.00",
        budget_actual="0.00",
        actual_revenue="0.00",
    )


@pytest.fixture
def campaign_b(db, tenant_b):
    from apps.crm.models import Campaign
    return Campaign.objects.create(
        tenant=tenant_b,
        name="B Corp Promo",
        type="social",
        status="active",
    )


@pytest.fixture
def email_template_a(db, tenant_a):
    from apps.crm.models import EmailTemplate
    return EmailTemplate.objects.create(
        tenant=tenant_a,
        name="Welcome Email",
        subject="Welcome to Acme!",
        category="newsletter",
    )


@pytest.fixture
def email_template_b(db, tenant_b):
    from apps.crm.models import EmailTemplate
    return EmailTemplate.objects.create(
        tenant=tenant_b,
        name="Globex Newsletter",
        subject="Globex Updates",
        category="newsletter",
    )


@pytest.fixture
def email_campaign_a(db, tenant_a, campaign_a, email_template_a):
    from apps.crm.models import EmailCampaign
    return EmailCampaign.objects.create(
        tenant=tenant_a,
        name="Spring Blast",
        campaign=campaign_a,
        template=email_template_a,
        send_type="one_time",
        status="draft",
    )


@pytest.fixture
def email_campaign_b(db, tenant_b, campaign_b, email_template_b):
    from apps.crm.models import EmailCampaign
    return EmailCampaign.objects.create(
        tenant=tenant_b,
        name="Globex Blast",
        campaign=campaign_b,
        template=email_template_b,
        status="draft",
    )


@pytest.fixture
def landing_page_a(db, tenant_a, campaign_a):
    from apps.crm.models import LandingPage
    return LandingPage.objects.create(
        tenant=tenant_a,
        name="Spring LP",
        campaign=campaign_a,
        headline="Get 20% off this spring!",
        status="draft",
    )


@pytest.fixture
def landing_page_published(db, tenant_a, campaign_a):
    from apps.crm.models import LandingPage
    return LandingPage.objects.create(
        tenant=tenant_a,
        name="Live LP",
        campaign=campaign_a,
        headline="Sign up now!",
        status="published",
    )


@pytest.fixture
def landing_page_b(db, tenant_b, campaign_b):
    from apps.crm.models import LandingPage
    return LandingPage.objects.create(
        tenant=tenant_b,
        name="Globex LP",
        campaign=campaign_b,
        headline="Globex Sign Up",
        status="draft",
    )


@pytest.fixture
def campaign_member_a(db, tenant_a, campaign_a):
    from apps.crm.models import CampaignMember
    return CampaignMember.objects.create(
        tenant=tenant_a,
        campaign=campaign_a,
        member_name="Alice Target",
        member_email="alice@example.com",
        status="targeted",
    )


@pytest.fixture
def campaign_member_b(db, tenant_b, campaign_b):
    from apps.crm.models import CampaignMember
    return CampaignMember.objects.create(
        tenant=tenant_b,
        campaign=campaign_b,
        member_name="Bob Target",
        member_email="bob@example.com",
        status="targeted",
    )


@pytest.fixture
def form_submission_a(db, tenant_a, landing_page_a):
    from apps.crm.models import FormSubmission
    return FormSubmission.objects.create(
        tenant=tenant_a,
        landing_page=landing_page_a,
        name="Sam Visitor",
        email="sam@example.com",
        status="new",
    )


@pytest.fixture
def form_submission_b(db, tenant_b, landing_page_b):
    from apps.crm.models import FormSubmission
    return FormSubmission.objects.create(
        tenant=tenant_b,
        landing_page=landing_page_b,
        name="Globex Visitor",
        email="visitor@globex.com",
        status="new",
    )


# ============================================================= MODEL INVARIANTS
# ---- Campaign enhanced fields
class TestCampaignEnhancedModel:
    def test_roi_none_when_no_spend(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="Zero Spend", budget_actual=0, actual_revenue=500
        )
        assert cam.roi is None

    def test_roi_correct_pct(self, tenant_a):
        from apps.crm.models import Campaign
        # ROI = (revenue - spend) / spend * 100 = (1500 - 1000) / 1000 * 100 = 50%
        cam = Campaign.objects.create(
            tenant=tenant_a, name="ROI Test",
            budget_actual="1000.00", actual_revenue="1500.00",
        )
        cam.refresh_from_db()
        assert float(cam.roi) == pytest.approx(50.0)

    def test_roi_negative(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="Loss",
            budget_actual="2000.00", actual_revenue="1000.00",
        )
        cam.refresh_from_db()
        assert float(cam.roi) == pytest.approx(-50.0)

    def test_roi_decimal_safe_on_fresh_instance(self, tenant_a):
        """roi must not raise TypeError on a freshly .create()'d instance.
        The model casts via Decimal() so the property works before DB round-trip."""
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="Fresh",
            budget_actual="1000.00", actual_revenue="2000.00",
        )
        # Should NOT raise — model uses Decimal(self.budget_actual or 0)
        result = cam.roi
        assert result is not None

    def test_objective_field_exists(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="With Objective", objective="lead_gen"
        )
        assert cam.objective == "lead_gen"

    def test_objective_choices(self):
        from apps.crm.models import Campaign
        keys = [k for k, _ in Campaign.OBJECTIVE_CHOICES]
        for expected in ("awareness", "lead_gen", "nurture", "conversion", "event", "retention"):
            assert expected in keys

    def test_utm_fields_exist(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="UTM Campaign",
            utm_source="google", utm_medium="cpc", utm_campaign="spring2025",
        )
        cam.refresh_from_db()
        assert cam.utm_source == "google"
        assert cam.utm_medium == "cpc"
        assert cam.utm_campaign == "spring2025"

    def test_parent_campaign_self_fk(self, tenant_a):
        from apps.crm.models import Campaign
        parent = Campaign.objects.create(tenant=tenant_a, name="Q3 Program")
        child = Campaign.objects.create(
            tenant=tenant_a, name="Q3 Email Blast", parent_campaign=parent
        )
        assert child.parent_campaign == parent

    def test_parent_campaign_default_null(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(tenant=tenant_a, name="No Parent")
        assert cam.parent_campaign is None

    def test_number_format(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(tenant=tenant_a, name="Numbered")
        assert cam.number == "CAM-00001"

    def test_str(self, campaign_a):
        s = str(campaign_a)
        assert "CAM-00001" in s
        assert "Spring Promo" in s


# ---- Campaign form: self-parent rejection
class TestCampaignFormSelfParent:
    def test_self_parent_excluded_from_queryset(self, tenant_a, campaign_a):
        from apps.crm.forms import CampaignForm
        # On an edit form (instance has pk), the campaign itself must be excluded from
        # parent_campaign dropdown.
        form = CampaignForm(tenant=tenant_a, instance=campaign_a)
        qs = form.fields["parent_campaign"].queryset
        assert campaign_a.pk not in list(qs.values_list("pk", flat=True))

    def test_new_form_does_not_exclude_self(self, tenant_a, campaign_a):
        """On a create form (no instance pk), all same-tenant campaigns are available."""
        from apps.crm.forms import CampaignForm
        form = CampaignForm(tenant=tenant_a)  # no instance
        qs = form.fields["parent_campaign"].queryset
        assert campaign_a.pk in list(qs.values_list("pk", flat=True))


# ---- CampaignMember.save() — responded_at stamping
class TestCampaignMemberSave:
    def test_responded_at_none_on_create_targeted(self, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        m = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a,
            member_name="T1", status="targeted"
        )
        assert m.responded_at is None

    def test_responded_at_none_for_sent_status(self, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        m = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a,
            member_name="T2", status="sent"
        )
        assert m.responded_at is None

    def test_responded_at_none_for_opened_status(self, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        m = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a,
            member_name="T3", status="opened"
        )
        assert m.responded_at is None

    def test_responded_at_stamped_when_responded(self, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        m = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a,
            member_name="T4", status="responded"
        )
        assert m.responded_at is not None

    def test_responded_at_stamped_when_converted(self, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        m = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a,
            member_name="T5", status="converted"
        )
        assert m.responded_at is not None

    def test_responded_at_not_overwritten_on_resave(self, tenant_a, campaign_a):
        """Re-saving a responded member must not change responded_at."""
        from apps.crm.models import CampaignMember
        m = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a,
            member_name="T6", status="responded"
        )
        first_stamp = m.responded_at
        m.notes = "updated"
        m.save()
        m.refresh_from_db()
        assert m.responded_at == first_stamp

    def test_responded_at_stays_none_on_transition_to_bounced(self, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        m = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a,
            member_name="T7", status="bounced"
        )
        assert m.responded_at is None

    def test_has_responded_property(self, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        m_responded = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a, member_name="R", status="responded"
        )
        m_targeted = CampaignMember.objects.create(
            tenant=tenant_a, campaign=campaign_a, member_name="T", status="targeted"
        )
        assert m_responded.has_responded is True
        assert m_targeted.has_responded is False

    def test_str(self, campaign_member_a):
        s = str(campaign_member_a)
        assert "Alice Target" in s
        assert "Targeted" in s  # display value

    def test_status_choices(self):
        from apps.crm.models import CampaignMember
        keys = [k for k, _ in CampaignMember.STATUS_CHOICES]
        for expected in ("targeted", "sent", "opened", "clicked", "responded",
                         "converted", "bounced", "unsubscribed"):
            assert expected in keys


# ---- EmailTemplate auto-number
class TestEmailTemplateModel:
    def test_number_format(self, tenant_a):
        from apps.crm.models import EmailTemplate
        et = EmailTemplate.objects.create(
            tenant=tenant_a, name="Tmpl1", subject="Hello"
        )
        assert et.number == "EMT-00001"

    def test_sequential_numbers(self, tenant_a):
        from apps.crm.models import EmailTemplate
        et1 = EmailTemplate.objects.create(tenant=tenant_a, name="A", subject="A")
        et2 = EmailTemplate.objects.create(tenant=tenant_a, name="B", subject="B")
        assert et1.number == "EMT-00001"
        assert et2.number == "EMT-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import EmailTemplate
        a = EmailTemplate.objects.create(tenant=tenant_a, name="A", subject="A")
        b = EmailTemplate.objects.create(tenant=tenant_b, name="B", subject="B")
        assert a.number == "EMT-00001"
        assert b.number == "EMT-00001"

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import EmailTemplate
        from django.db import IntegrityError
        EmailTemplate.objects.create(tenant=tenant_a, name="First", subject="X")
        with pytest.raises(IntegrityError):
            EmailTemplate.objects.create(
                tenant=tenant_a, name="Dup", subject="Y", number="EMT-00001"
            )

    def test_str(self, email_template_a):
        s = str(email_template_a)
        assert "EMT-00001" in s
        assert "Welcome Email" in s

    def test_category_choices(self):
        from apps.crm.models import EmailTemplate
        keys = [k for k, _ in EmailTemplate.CATEGORY_CHOICES]
        for expected in ("newsletter", "promotional", "transactional", "drip", "announcement", "other"):
            assert expected in keys

    def test_is_active_default(self, tenant_a):
        from apps.crm.models import EmailTemplate
        et = EmailTemplate.objects.create(tenant=tenant_a, name="New", subject="Sub")
        assert et.is_active is True


# ---- EmailCampaign auto-number and properties
class TestEmailCampaignModel:
    def test_number_format(self, tenant_a, campaign_a):
        from apps.crm.models import EmailCampaign
        ec = EmailCampaign.objects.create(
            tenant=tenant_a, name="Blast1", campaign=campaign_a, status="draft"
        )
        assert ec.number == "BLAST-00001"

    def test_sequential_numbers(self, tenant_a, campaign_a):
        from apps.crm.models import EmailCampaign
        ec1 = EmailCampaign.objects.create(tenant=tenant_a, name="B1", campaign=campaign_a)
        ec2 = EmailCampaign.objects.create(tenant=tenant_a, name="B2", campaign=campaign_a)
        assert ec1.number == "BLAST-00001"
        assert ec2.number == "BLAST-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b, campaign_a, campaign_b):
        from apps.crm.models import EmailCampaign
        a = EmailCampaign.objects.create(tenant=tenant_a, name="A", campaign=campaign_a)
        b = EmailCampaign.objects.create(tenant=tenant_b, name="B", campaign=campaign_b)
        assert a.number == "BLAST-00001"
        assert b.number == "BLAST-00001"

    def test_str(self, email_campaign_a):
        s = str(email_campaign_a)
        assert "BLAST-00001" in s
        assert "Spring Blast" in s

    def test_open_rate_none_when_nothing_delivered(self, email_campaign_a):
        """open_rate must be None when delivered_count = 0."""
        assert email_campaign_a.open_rate is None

    def test_click_rate_none_when_nothing_delivered(self, email_campaign_a):
        assert email_campaign_a.click_rate is None

    def test_bounce_rate_none_when_nothing_sent(self, email_campaign_a):
        assert email_campaign_a.bounce_rate is None

    def test_delivered_count_is_sent_minus_bounced(self, tenant_a, campaign_a):
        from apps.crm.models import EmailCampaign
        ec = EmailCampaign.objects.create(
            tenant=tenant_a, name="Metrics", campaign=campaign_a,
            sent_count=100, bounced_count=5
        )
        assert ec.delivered_count == 95

    def test_delivered_count_zero_when_no_sent(self, tenant_a, campaign_a):
        from apps.crm.models import EmailCampaign
        ec = EmailCampaign.objects.create(
            tenant=tenant_a, name="No Sent", campaign=campaign_a,
            sent_count=0, bounced_count=0
        )
        assert ec.delivered_count == 0

    def test_open_rate_correct(self, tenant_a, campaign_a):
        from apps.crm.models import EmailCampaign
        ec = EmailCampaign.objects.create(
            tenant=tenant_a, name="OpenRate", campaign=campaign_a,
            sent_count=100, bounced_count=0, opened_count=30
        )
        # delivered = 100; open_rate = 30/100 * 100 = 30%
        assert float(ec.open_rate) == pytest.approx(30.0)

    def test_click_rate_correct(self, tenant_a, campaign_a):
        from apps.crm.models import EmailCampaign
        ec = EmailCampaign.objects.create(
            tenant=tenant_a, name="ClickRate", campaign=campaign_a,
            sent_count=100, bounced_count=0, clicked_count=20
        )
        assert float(ec.click_rate) == pytest.approx(20.0)

    def test_bounce_rate_correct(self, tenant_a, campaign_a):
        from apps.crm.models import EmailCampaign
        ec = EmailCampaign.objects.create(
            tenant=tenant_a, name="BounceRate", campaign=campaign_a,
            sent_count=200, bounced_count=10
        )
        # bounce_rate = 10/200 * 100 = 5%
        assert float(ec.bounce_rate) == pytest.approx(5.0)

    def test_open_rate_decimal_safe_on_fresh_instance(self, tenant_a, campaign_a):
        """Properties must not raise on a fresh (un-round-tripped) instance with counters."""
        from apps.crm.models import EmailCampaign
        ec = EmailCampaign.objects.create(
            tenant=tenant_a, name="Fresh", campaign=campaign_a,
            sent_count=100, bounced_count=0, opened_count=50
        )
        # Must not raise TypeError
        result = ec.open_rate
        assert result is not None

    def test_status_choices(self):
        from apps.crm.models import EmailCampaign
        keys = [k for k, _ in EmailCampaign.STATUS_CHOICES]
        for expected in ("draft", "scheduled", "sending", "sent", "paused", "cancelled"):
            assert expected in keys


# ---- LandingPage auto-number, token, is_published
class TestLandingPageModel:
    def test_number_format(self, tenant_a):
        from apps.crm.models import LandingPage
        lp = LandingPage.objects.create(
            tenant=tenant_a, name="LP1", headline="Hello"
        )
        assert lp.number == "LP-00001"

    def test_sequential_numbers(self, tenant_a):
        from apps.crm.models import LandingPage
        lp1 = LandingPage.objects.create(tenant=tenant_a, name="A", headline="A")
        lp2 = LandingPage.objects.create(tenant=tenant_a, name="B", headline="B")
        assert lp1.number == "LP-00001"
        assert lp2.number == "LP-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import LandingPage
        a = LandingPage.objects.create(tenant=tenant_a, name="A", headline="A")
        b = LandingPage.objects.create(tenant=tenant_b, name="B", headline="B")
        assert a.number == "LP-00001"
        assert b.number == "LP-00001"

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import LandingPage
        from django.db import IntegrityError
        LandingPage.objects.create(tenant=tenant_a, name="First", headline="F")
        with pytest.raises(IntegrityError):
            LandingPage.objects.create(
                tenant=tenant_a, name="Dup", headline="D", number="LP-00001"
            )

    def test_public_token_generated_on_save(self, tenant_a):
        from apps.crm.models import LandingPage
        lp = LandingPage.objects.create(tenant=tenant_a, name="Tokenized", headline="H")
        assert lp.public_token
        assert len(lp.public_token) > 10

    def test_public_token_generated_only_once(self, landing_page_a):
        """Re-saving a LandingPage must not change public_token."""
        original_token = landing_page_a.public_token
        landing_page_a.name = "Renamed"
        landing_page_a.save()
        landing_page_a.refresh_from_db()
        assert landing_page_a.public_token == original_token

    def test_public_token_unique_across_instances(self, tenant_a):
        from apps.crm.models import LandingPage
        lp1 = LandingPage.objects.create(tenant=tenant_a, name="A", headline="A")
        lp2 = LandingPage.objects.create(tenant=tenant_a, name="B", headline="B")
        assert lp1.public_token != lp2.public_token

    def test_is_published_when_published(self, landing_page_published):
        assert landing_page_published.is_published is True

    def test_is_published_false_when_draft(self, landing_page_a):
        assert landing_page_a.is_published is False

    def test_status_choices(self):
        from apps.crm.models import LandingPage
        keys = [k for k, _ in LandingPage.STATUS_CHOICES]
        assert set(keys) == {"draft", "published", "archived"}

    def test_str(self, landing_page_a):
        s = str(landing_page_a)
        assert "LP-00001" in s
        assert "Spring LP" in s

    def test_default_status_is_draft(self, tenant_a):
        from apps.crm.models import LandingPage
        lp = LandingPage.objects.create(tenant=tenant_a, name="New", headline="H")
        assert lp.status == "draft"

    def test_submission_count_default_zero(self, landing_page_a):
        assert landing_page_a.submission_count == 0


# ---- FormSubmission model
class TestFormSubmissionModel:
    def test_str(self, form_submission_a):
        s = str(form_submission_a)
        assert "Sam Visitor" in s
        assert "New" in s  # display value

    def test_status_default_new(self, tenant_a, landing_page_a):
        from apps.crm.models import FormSubmission
        fs = FormSubmission.objects.create(
            tenant=tenant_a, landing_page=landing_page_a, name="X"
        )
        assert fs.status == "new"

    def test_status_choices(self):
        from apps.crm.models import FormSubmission
        keys = [k for k, _ in FormSubmission.STATUS_CHOICES]
        assert set(keys) == {"new", "routed", "converted", "spam"}

    def test_converted_lead_default_null(self, form_submission_a):
        assert form_submission_a.converted_lead is None


# ============================================================= FORM SECURITY
class TestEmailCampaignFormExclusions:
    def test_status_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "status" not in form.fields

    def test_sent_at_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "sent_at" not in form.fields

    def test_recipients_count_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "recipients_count" not in form.fields

    def test_sent_count_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "sent_count" not in form.fields

    def test_opened_count_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "opened_count" not in form.fields

    def test_clicked_count_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "clicked_count" not in form.fields

    def test_bounced_count_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "bounced_count" not in form.fields

    def test_unsubscribed_count_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "unsubscribed_count" not in form.fields

    def test_tenant_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_in_form(self, tenant_a):
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(tenant=tenant_a)
        assert "number" not in form.fields


class TestLandingPageFormExclusions:
    def test_status_not_in_form(self, tenant_a):
        from apps.crm.forms import LandingPageForm
        form = LandingPageForm(tenant=tenant_a)
        assert "status" not in form.fields

    def test_public_token_not_in_form(self, tenant_a):
        from apps.crm.forms import LandingPageForm
        form = LandingPageForm(tenant=tenant_a)
        assert "public_token" not in form.fields

    def test_submission_count_not_in_form(self, tenant_a):
        from apps.crm.forms import LandingPageForm
        form = LandingPageForm(tenant=tenant_a)
        assert "submission_count" not in form.fields

    def test_tenant_not_in_form(self, tenant_a):
        from apps.crm.forms import LandingPageForm
        form = LandingPageForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_in_form(self, tenant_a):
        from apps.crm.forms import LandingPageForm
        form = LandingPageForm(tenant=tenant_a)
        assert "number" not in form.fields


class TestCampaignMemberFormExclusions:
    def test_responded_at_not_in_form(self, tenant_a):
        from apps.crm.forms import CampaignMemberForm
        form = CampaignMemberForm(tenant=tenant_a)
        assert "responded_at" not in form.fields

    def test_tenant_not_in_form(self, tenant_a):
        from apps.crm.forms import CampaignMemberForm
        form = CampaignMemberForm(tenant=tenant_a)
        assert "tenant" not in form.fields


class TestCampaignFormExclusions:
    def test_number_not_in_form(self, tenant_a):
        from apps.crm.forms import CampaignForm
        form = CampaignForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_tenant_not_in_form(self, tenant_a):
        from apps.crm.forms import CampaignForm
        form = CampaignForm(tenant=tenant_a)
        assert "tenant" not in form.fields


class TestCrossTenantFKRejection:
    """EmailCampaignForm/CampaignMemberForm must reject FK pks from another tenant."""

    def test_emailcampaign_form_rejects_cross_tenant_campaign(
        self, tenant_a, tenant_b, campaign_a, campaign_b, email_template_a
    ):
        """EmailCampaignForm scoped to tenant_a must not accept campaign_b (tenant_b)."""
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(
            tenant=tenant_a,
            data={
                "name": "Injected",
                "campaign": str(campaign_b.pk),  # cross-tenant injection
                "send_type": "one_time",
            },
        )
        assert not form.is_valid()
        assert "campaign" in form.errors

    def test_emailcampaign_form_rejects_cross_tenant_template(
        self, tenant_a, tenant_b, campaign_a, email_template_b
    ):
        """EmailCampaignForm scoped to tenant_a must not accept email_template_b (tenant_b)."""
        from apps.crm.forms import EmailCampaignForm
        form = EmailCampaignForm(
            tenant=tenant_a,
            data={
                "name": "Tmpl Injection",
                "campaign": str(campaign_a.pk),
                "template": str(email_template_b.pk),  # cross-tenant injection
                "send_type": "one_time",
            },
        )
        assert not form.is_valid()
        assert "template" in form.errors

    def test_campaignmember_form_rejects_cross_tenant_campaign(
        self, tenant_a, campaign_b
    ):
        """CampaignMemberForm scoped to tenant_a must not accept campaign_b (tenant_b)."""
        from apps.crm.forms import CampaignMemberForm
        form = CampaignMemberForm(
            tenant=tenant_a,
            data={
                "campaign": str(campaign_b.pk),  # cross-tenant injection
                "member_name": "Injected Member",
                "member_email": "injected@example.com",
                "status": "targeted",
            },
        )
        assert not form.is_valid()
        assert "campaign" in form.errors


# ============================================================= VIEWS / CRUD
# ---- EmailTemplate CRUD
class TestEmailTemplateViews:
    def test_list_200(self, client_a, email_template_a):
        resp = client_a.get(reverse("crm:emailtemplate_list"))
        assert resp.status_code == 200

    def test_list_shows_own_template(self, client_a, email_template_a):
        resp = client_a.get(reverse("crm:emailtemplate_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert email_template_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, email_template_a, email_template_b):
        resp = client_a.get(reverse("crm:emailtemplate_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert email_template_b.pk not in pks

    def test_detail_200(self, client_a, email_template_a):
        resp = client_a.get(reverse("crm:emailtemplate_detail", args=[email_template_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, email_template_a):
        resp = client_a.get(reverse("crm:emailtemplate_detail", args=[email_template_a.pk]))
        assert resp.context["obj"].pk == email_template_a.pk

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:emailtemplate_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import EmailTemplate
        resp = client_a.post(reverse("crm:emailtemplate_create"), {
            "name": "New Template",
            "subject": "Hello World",
            "category": "promotional",
            "is_active": "on",
        })
        assert resp.status_code == 302
        et = EmailTemplate.objects.filter(tenant=tenant_a, name="New Template").first()
        assert et is not None
        assert et.number.startswith("EMT-")

    def test_edit_get_200(self, client_a, email_template_a):
        resp = client_a.get(reverse("crm:emailtemplate_edit", args=[email_template_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, email_template_a):
        resp = client_a.post(reverse("crm:emailtemplate_edit", args=[email_template_a.pk]), {
            "name": "Updated Template",
            "subject": "Updated Subject",
            "category": "newsletter",
            "is_active": "on",
        })
        assert resp.status_code == 302
        email_template_a.refresh_from_db()
        assert email_template_a.name == "Updated Template"

    def test_delete_removes_record(self, client_a, email_template_a):
        from apps.crm.models import EmailTemplate
        pk = email_template_a.pk
        resp = client_a.post(reverse("crm:emailtemplate_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmailTemplate.objects.filter(pk=pk).exists()

    def test_anon_redirected_from_list(self, client):
        resp = client.get(reverse("crm:emailtemplate_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ---- EmailCampaign CRUD
class TestEmailCampaignViews:
    def test_list_200(self, client_a, email_campaign_a):
        resp = client_a.get(reverse("crm:emailcampaign_list"))
        assert resp.status_code == 200

    def test_list_shows_own_blast(self, client_a, email_campaign_a):
        resp = client_a.get(reverse("crm:emailcampaign_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert email_campaign_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, email_campaign_a, email_campaign_b):
        resp = client_a.get(reverse("crm:emailcampaign_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert email_campaign_b.pk not in pks

    def test_detail_200(self, client_a, email_campaign_a):
        resp = client_a.get(reverse("crm:emailcampaign_detail", args=[email_campaign_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, email_campaign_a):
        resp = client_a.get(reverse("crm:emailcampaign_detail", args=[email_campaign_a.pk]))
        assert resp.context["obj"].pk == email_campaign_a.pk

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:emailcampaign_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a, campaign_a, email_template_a):
        from apps.crm.models import EmailCampaign
        resp = client_a.post(reverse("crm:emailcampaign_create"), {
            "name": "New Blast",
            "campaign": str(campaign_a.pk),
            "template": str(email_template_a.pk),
            "send_type": "one_time",
        })
        assert resp.status_code == 302
        ec = EmailCampaign.objects.filter(tenant=tenant_a, name="New Blast").first()
        assert ec is not None
        assert ec.number.startswith("BLAST-")
        assert ec.status == "draft"  # default

    def test_edit_get_200(self, client_a, email_campaign_a):
        resp = client_a.get(reverse("crm:emailcampaign_edit", args=[email_campaign_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_record(self, client_a, email_campaign_a):
        from apps.crm.models import EmailCampaign
        pk = email_campaign_a.pk
        client_a.post(reverse("crm:emailcampaign_delete", args=[pk]))
        assert not EmailCampaign.objects.filter(pk=pk).exists()

    def test_anon_redirected_from_list(self, client):
        resp = client.get(reverse("crm:emailcampaign_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ---- emailcampaign_send — the privileged blast action
class TestEmailCampaignSend:
    def _make_members(self, tenant_a, campaign_a, count=3):
        from apps.crm.models import CampaignMember
        for i in range(count):
            CampaignMember.objects.create(
                tenant=tenant_a, campaign=campaign_a,
                member_name=f"Target {i}", status="targeted"
            )

    def test_send_sets_status_sent(self, client_a, tenant_a, email_campaign_a, campaign_a):
        self._make_members(tenant_a, campaign_a, 2)
        client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        email_campaign_a.refresh_from_db()
        assert email_campaign_a.status == "sent"

    def test_send_sets_recipients_count(self, client_a, tenant_a, email_campaign_a, campaign_a):
        self._make_members(tenant_a, campaign_a, 3)
        client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        email_campaign_a.refresh_from_db()
        assert email_campaign_a.recipients_count == 3

    def test_send_sets_sent_count(self, client_a, tenant_a, email_campaign_a, campaign_a):
        self._make_members(tenant_a, campaign_a, 4)
        client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        email_campaign_a.refresh_from_db()
        assert email_campaign_a.sent_count == 4

    def test_send_sets_sent_at(self, client_a, tenant_a, email_campaign_a, campaign_a):
        self._make_members(tenant_a, campaign_a, 1)
        client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        email_campaign_a.refresh_from_db()
        assert email_campaign_a.sent_at is not None

    def test_send_advances_targeted_members_to_sent(
        self, client_a, tenant_a, email_campaign_a, campaign_a
    ):
        from apps.crm.models import CampaignMember
        self._make_members(tenant_a, campaign_a, 2)
        client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        still_targeted = CampaignMember.objects.filter(
            tenant=tenant_a, campaign=campaign_a, status="targeted"
        ).count()
        assert still_targeted == 0

    def test_send_idempotent_second_post_noop(
        self, client_a, tenant_a, email_campaign_a, campaign_a
    ):
        """A second POST to send must not double-count — status stays 'sent'."""
        self._make_members(tenant_a, campaign_a, 2)
        client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        email_campaign_a.refresh_from_db()
        first_sent_at = email_campaign_a.sent_at
        first_count = email_campaign_a.sent_count

        # Add more members and POST again — the second send must be a no-op.
        self._make_members(tenant_a, campaign_a, 5)
        client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        email_campaign_a.refresh_from_db()
        assert email_campaign_a.status == "sent"
        assert email_campaign_a.sent_count == first_count  # unchanged
        assert email_campaign_a.sent_at == first_sent_at  # unchanged

    def test_send_blocked_for_non_admin(
        self, member_client, tenant_a, email_campaign_a, campaign_a
    ):
        """A non-admin tenant member must not be able to fire a blast."""
        self._make_members(tenant_a, campaign_a, 1)
        resp = member_client.post(
            reverse("crm:emailcampaign_send", args=[email_campaign_a.pk])
        )
        # admin-gated: must return 302 (redirect) or 403 — NOT change the status
        assert resp.status_code in (302, 403)
        email_campaign_a.refresh_from_db()
        assert email_campaign_a.status == "draft"

    def test_send_redirects_to_detail(self, client_a, tenant_a, email_campaign_a, campaign_a):
        self._make_members(tenant_a, campaign_a, 1)
        resp = client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        assert resp.status_code == 302
        assert str(email_campaign_a.pk) in resp["Location"]

    def test_get_method_blocked(self, client_a, email_campaign_a):
        """emailcampaign_send is POST-only."""
        resp = client_a.get(reverse("crm:emailcampaign_send", args=[email_campaign_a.pk]))
        assert resp.status_code in (405, 302, 403)


# ---- LandingPage CRUD
class TestLandingPageViews:
    def test_list_200(self, client_a, landing_page_a):
        resp = client_a.get(reverse("crm:landingpage_list"))
        assert resp.status_code == 200

    def test_list_shows_own_page(self, client_a, landing_page_a):
        resp = client_a.get(reverse("crm:landingpage_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert landing_page_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, landing_page_a, landing_page_b):
        resp = client_a.get(reverse("crm:landingpage_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert landing_page_b.pk not in pks

    def test_detail_200(self, client_a, landing_page_a):
        resp = client_a.get(reverse("crm:landingpage_detail", args=[landing_page_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, landing_page_a):
        resp = client_a.get(reverse("crm:landingpage_detail", args=[landing_page_a.pk]))
        assert resp.context["obj"].pk == landing_page_a.pk

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:landingpage_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a, campaign_a):
        from apps.crm.models import LandingPage
        resp = client_a.post(reverse("crm:landingpage_create"), {
            "name": "New LP",
            "headline": "Sign Up Today",
            "cta_label": "Submit",
            "lead_source": "web",
        })
        assert resp.status_code == 302
        lp = LandingPage.objects.filter(tenant=tenant_a, name="New LP").first()
        assert lp is not None
        assert lp.public_token  # generated automatically
        assert lp.status == "draft"

    def test_edit_get_200(self, client_a, landing_page_a):
        resp = client_a.get(reverse("crm:landingpage_edit", args=[landing_page_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_name(self, client_a, landing_page_a):
        resp = client_a.post(reverse("crm:landingpage_edit", args=[landing_page_a.pk]), {
            "name": "Renamed LP",
            "headline": "New Headline",
            "cta_label": "Go",
            "lead_source": "web",
        })
        assert resp.status_code == 302
        landing_page_a.refresh_from_db()
        assert landing_page_a.name == "Renamed LP"

    def test_delete_removes_record(self, client_a, landing_page_a):
        from apps.crm.models import LandingPage
        pk = landing_page_a.pk
        client_a.post(reverse("crm:landingpage_delete", args=[pk]))
        assert not LandingPage.objects.filter(pk=pk).exists()

    def test_anon_redirected_from_list(self, client):
        resp = client.get(reverse("crm:landingpage_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ---- landingpage_publish — admin-gated toggle
class TestLandingPagePublish:
    def test_publish_draft_becomes_published(self, client_a, landing_page_a):
        assert landing_page_a.status == "draft"
        client_a.post(reverse("crm:landingpage_publish", args=[landing_page_a.pk]))
        landing_page_a.refresh_from_db()
        assert landing_page_a.status == "published"

    def test_publish_published_becomes_draft(self, client_a, landing_page_published):
        assert landing_page_published.status == "published"
        client_a.post(reverse("crm:landingpage_publish", args=[landing_page_published.pk]))
        landing_page_published.refresh_from_db()
        assert landing_page_published.status == "draft"

    def test_publish_blocked_for_non_admin(self, member_client, landing_page_a):
        """Non-admin member must not toggle publish status."""
        resp = member_client.post(
            reverse("crm:landingpage_publish", args=[landing_page_a.pk])
        )
        assert resp.status_code in (302, 403)
        landing_page_a.refresh_from_db()
        assert landing_page_a.status == "draft"  # unchanged

    def test_publish_get_blocked(self, client_a, landing_page_a):
        """landingpage_publish is POST-only."""
        resp = client_a.get(reverse("crm:landingpage_publish", args=[landing_page_a.pk]))
        assert resp.status_code in (405, 302, 403)

    def test_publish_redirects_to_detail(self, client_a, landing_page_a):
        resp = client_a.post(reverse("crm:landingpage_publish", args=[landing_page_a.pk]))
        assert resp.status_code == 302
        assert str(landing_page_a.pk) in resp["Location"]


# ---- CampaignMember inline add (campaignmember_add)
class TestCampaignMemberAddInline:
    def test_add_creates_member(self, client_a, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        resp = client_a.post(
            reverse("crm:campaignmember_add", args=[campaign_a.pk]),
            {"member_name": "Inline Member", "member_email": "inline@example.com", "status": "targeted"},
        )
        assert resp.status_code == 302
        assert CampaignMember.objects.filter(
            tenant=tenant_a, campaign=campaign_a, member_name="Inline Member"
        ).exists()

    def test_add_empty_name_rejected(self, client_a, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        before = CampaignMember.objects.filter(tenant=tenant_a, campaign=campaign_a).count()
        resp = client_a.post(
            reverse("crm:campaignmember_add", args=[campaign_a.pk]),
            {"member_name": "", "status": "targeted"},
        )
        after = CampaignMember.objects.filter(tenant=tenant_a, campaign=campaign_a).count()
        assert after == before  # no new row
        # View should redirect back to campaign detail with an error message
        assert resp.status_code == 302

    def test_add_invalid_email_silently_cleared(self, client_a, tenant_a, campaign_a):
        """Inline add with a bad email should save the member but leave email blank."""
        from apps.crm.models import CampaignMember
        client_a.post(
            reverse("crm:campaignmember_add", args=[campaign_a.pk]),
            {"member_name": "Bad Email", "member_email": "notanemail", "status": "targeted"},
        )
        m = CampaignMember.objects.filter(
            tenant=tenant_a, campaign=campaign_a, member_name="Bad Email"
        ).first()
        assert m is not None
        assert m.member_email == ""  # cleared by view


# ---- CampaignMember CRUD views
class TestCampaignMemberViews:
    def test_list_200(self, client_a, campaign_member_a):
        resp = client_a.get(reverse("crm:campaignmember_list"))
        assert resp.status_code == 200

    def test_list_shows_own_member(self, client_a, campaign_member_a):
        resp = client_a.get(reverse("crm:campaignmember_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert campaign_member_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, campaign_member_a, campaign_member_b):
        resp = client_a.get(reverse("crm:campaignmember_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert campaign_member_b.pk not in pks

    def test_detail_200(self, client_a, campaign_member_a):
        resp = client_a.get(reverse("crm:campaignmember_detail", args=[campaign_member_a.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:campaignmember_create"))
        assert resp.status_code == 200

    def test_create_post_persists(self, client_a, tenant_a, campaign_a):
        from apps.crm.models import CampaignMember
        resp = client_a.post(reverse("crm:campaignmember_create"), {
            "campaign": str(campaign_a.pk),
            "member_name": "New Member",
            "member_email": "newmember@example.com",
            "status": "targeted",
        })
        assert resp.status_code == 302
        assert CampaignMember.objects.filter(tenant=tenant_a, member_name="New Member").exists()

    def test_delete_removes_record(self, client_a, campaign_member_a):
        from apps.crm.models import CampaignMember
        pk = campaign_member_a.pk
        client_a.post(reverse("crm:campaignmember_delete", args=[pk]))
        assert not CampaignMember.objects.filter(pk=pk).exists()


# ---- FormSubmission list, detail, convert
class TestFormSubmissionViews:
    def test_list_200(self, client_a, form_submission_a):
        resp = client_a.get(reverse("crm:formsubmission_list"))
        assert resp.status_code == 200

    def test_list_shows_own_submission(self, client_a, form_submission_a):
        resp = client_a.get(reverse("crm:formsubmission_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert form_submission_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, form_submission_a, form_submission_b):
        resp = client_a.get(reverse("crm:formsubmission_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert form_submission_b.pk not in pks

    def test_detail_200(self, client_a, form_submission_a):
        resp = client_a.get(reverse("crm:formsubmission_detail", args=[form_submission_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, form_submission_a):
        resp = client_a.get(reverse("crm:formsubmission_detail", args=[form_submission_a.pk]))
        assert resp.context["obj"].pk == form_submission_a.pk


class TestFormSubmissionConvert:
    def test_convert_creates_lead(self, client_a, tenant_a, form_submission_a):
        from apps.crm.models import Lead
        resp = client_a.post(
            reverse("crm:formsubmission_convert", args=[form_submission_a.pk])
        )
        assert resp.status_code == 302
        assert Lead.objects.filter(tenant=tenant_a, name="Sam Visitor").exists()

    def test_convert_sets_submission_status_converted(self, client_a, form_submission_a):
        from apps.crm.models import FormSubmission
        client_a.post(
            reverse("crm:formsubmission_convert", args=[form_submission_a.pk])
        )
        form_submission_a.refresh_from_db()
        assert form_submission_a.status == "converted"

    def test_convert_links_converted_lead(self, client_a, form_submission_a):
        client_a.post(
            reverse("crm:formsubmission_convert", args=[form_submission_a.pk])
        )
        form_submission_a.refresh_from_db()
        assert form_submission_a.converted_lead_id is not None

    def test_convert_routes_to_page_routing_owner(self, client_a, tenant_a, admin_user):
        """The created lead's owner must be the landing page's routing_owner."""
        from apps.crm.models import Campaign, FormSubmission, LandingPage, Lead
        cam = Campaign.objects.create(tenant=tenant_a, name="RC")
        lp = LandingPage.objects.create(
            tenant=tenant_a, name="Routed LP", headline="H",
            routing_owner=admin_user, status="published"
        )
        sub = FormSubmission.objects.create(
            tenant=tenant_a, landing_page=lp, name="Routed Visitor",
            email="rv@example.com", routed_to=admin_user
        )
        client_a.post(reverse("crm:formsubmission_convert", args=[sub.pk]))
        lead = Lead.objects.get(tenant=tenant_a, name="Routed Visitor")
        assert lead.owner == admin_user

    def test_convert_idempotent_second_post(self, client_a, tenant_a, form_submission_a):
        """Second POST on an already-converted submission must be a no-op."""
        from apps.crm.models import Lead
        client_a.post(
            reverse("crm:formsubmission_convert", args=[form_submission_a.pk])
        )
        first_lead_count = Lead.objects.filter(tenant=tenant_a).count()

        client_a.post(
            reverse("crm:formsubmission_convert", args=[form_submission_a.pk])
        )
        assert Lead.objects.filter(tenant=tenant_a).count() == first_lead_count

    def test_anon_redirected_from_convert(self, client, form_submission_a):
        resp = client.post(
            reverse("crm:formsubmission_convert", args=[form_submission_a.pk])
        )
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================= PUBLIC ENDPOINT
class TestLandingPublicView:
    """landing_public — unauthenticated GET/POST at /crm/p/<token>/"""

    def test_published_page_get_200(self, client, landing_page_published):
        resp = client.get(
            reverse("crm:landing_public", args=[landing_page_published.public_token])
        )
        assert resp.status_code == 200

    def test_draft_page_returns_404(self, client, landing_page_a):
        """A draft page must not be accessible via the public URL."""
        assert landing_page_a.status == "draft"
        resp = client.get(
            reverse("crm:landing_public", args=[landing_page_a.public_token])
        )
        assert resp.status_code == 404

    def test_bogus_token_returns_404(self, client):
        resp = client.get(reverse("crm:landing_public", args=["not-a-real-token-xyz"]))
        assert resp.status_code == 404

    def test_valid_post_creates_form_submission(self, client, landing_page_published, tenant_a):
        from apps.crm.models import FormSubmission
        resp = client.post(
            reverse("crm:landing_public", args=[landing_page_published.public_token]),
            {"name": "Public User", "email": "pub@example.com"},
        )
        # PRG redirect
        assert resp.status_code == 302
        sub = FormSubmission.objects.filter(
            tenant=tenant_a, name="Public User"
        ).first()
        assert sub is not None
        assert sub.landing_page == landing_page_published

    def test_valid_post_uses_page_tenant(self, client, landing_page_published, tenant_a):
        from apps.crm.models import FormSubmission
        client.post(
            reverse("crm:landing_public", args=[landing_page_published.public_token]),
            {"name": "Tenant Check", "email": "tc@example.com"},
        )
        sub = FormSubmission.objects.filter(name="Tenant Check").first()
        assert sub is not None
        assert sub.tenant == tenant_a

    def test_valid_post_increments_submission_count(
        self, client, landing_page_published
    ):
        before = landing_page_published.submission_count
        client.post(
            reverse("crm:landing_public", args=[landing_page_published.public_token]),
            {"name": "Counter User", "email": "counter@example.com"},
        )
        landing_page_published.refresh_from_db()
        assert landing_page_published.submission_count == before + 1

    def test_valid_post_redirects_prg(self, client, landing_page_published):
        """POST must redirect (PRG pattern) to prevent duplicate submissions on refresh."""
        resp = client.post(
            reverse("crm:landing_public", args=[landing_page_published.public_token]),
            {"name": "PRG User", "email": "prg@example.com"},
        )
        assert resp.status_code == 302

    def test_missing_name_rerenders_form(self, client, landing_page_published):
        """Missing required 'name' field must re-render the form (200), not create a row."""
        from apps.crm.models import FormSubmission
        before = FormSubmission.objects.filter(landing_page=landing_page_published).count()
        resp = client.post(
            reverse("crm:landing_public", args=[landing_page_published.public_token]),
            {"name": "", "email": "noemail@example.com"},
        )
        assert resp.status_code == 200
        assert FormSubmission.objects.filter(
            landing_page=landing_page_published
        ).count() == before

    def test_missing_email_rerenders_form(self, client, landing_page_published):
        """Missing required 'email' field must re-render the form (200), not create a row."""
        from apps.crm.models import FormSubmission
        before = FormSubmission.objects.filter(landing_page=landing_page_published).count()
        resp = client.post(
            reverse("crm:landing_public", args=[landing_page_published.public_token]),
            {"name": "No Email"},
        )
        assert resp.status_code == 200
        assert FormSubmission.objects.filter(
            landing_page=landing_page_published
        ).count() == before

    def test_invalid_email_rerenders_form(self, client, landing_page_published):
        """Invalid email must re-render the form, not create a row."""
        from apps.crm.models import FormSubmission
        before = FormSubmission.objects.filter(landing_page=landing_page_published).count()
        resp = client.post(
            reverse("crm:landing_public", args=[landing_page_published.public_token]),
            {"name": "Bad Email", "email": "notanemail"},
        )
        assert resp.status_code == 200
        assert FormSubmission.objects.filter(
            landing_page=landing_page_published
        ).count() == before

    def test_submitted_querystring_shows_success(self, client, landing_page_published):
        """GET with ?submitted=1 should render the page (200) with submitted flag in context."""
        resp = client.get(
            reverse("crm:landing_public", args=[landing_page_published.public_token])
            + "?submitted=1"
        )
        assert resp.status_code == 200
        assert resp.context["submitted"] is True


# ============================================================= MULTI-TENANT IDOR
class TestEmailTemplateIDOR:
    def test_detail_cross_tenant_404(self, client_a, email_template_b):
        resp = client_a.get(reverse("crm:emailtemplate_detail", args=[email_template_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, email_template_b):
        resp = client_a.get(reverse("crm:emailtemplate_edit", args=[email_template_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, email_template_b):
        resp = client_a.post(
            reverse("crm:emailtemplate_edit", args=[email_template_b.pk]),
            {"name": "Hijacked", "subject": "Evil", "category": "other"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, email_template_b):
        resp = client_a.post(reverse("crm:emailtemplate_delete", args=[email_template_b.pk]))
        assert resp.status_code == 404


class TestEmailCampaignIDOR:
    def test_detail_cross_tenant_404(self, client_a, email_campaign_b):
        resp = client_a.get(reverse("crm:emailcampaign_detail", args=[email_campaign_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, email_campaign_b):
        resp = client_a.get(reverse("crm:emailcampaign_edit", args=[email_campaign_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, email_campaign_b):
        resp = client_a.post(
            reverse("crm:emailcampaign_edit", args=[email_campaign_b.pk]),
            {"name": "Hijacked"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, email_campaign_b):
        resp = client_a.post(reverse("crm:emailcampaign_delete", args=[email_campaign_b.pk]))
        assert resp.status_code == 404

    def test_send_cross_tenant_404(self, client_a, email_campaign_b):
        resp = client_a.post(reverse("crm:emailcampaign_send", args=[email_campaign_b.pk]))
        assert resp.status_code == 404


class TestLandingPageIDOR:
    def test_detail_cross_tenant_404(self, client_a, landing_page_b):
        resp = client_a.get(reverse("crm:landingpage_detail", args=[landing_page_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, landing_page_b):
        resp = client_a.get(reverse("crm:landingpage_edit", args=[landing_page_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, landing_page_b):
        resp = client_a.post(
            reverse("crm:landingpage_edit", args=[landing_page_b.pk]),
            {"name": "Hijacked", "headline": "Evil"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, landing_page_b):
        resp = client_a.post(reverse("crm:landingpage_delete", args=[landing_page_b.pk]))
        assert resp.status_code == 404

    def test_publish_cross_tenant_404(self, client_a, landing_page_b):
        resp = client_a.post(reverse("crm:landingpage_publish", args=[landing_page_b.pk]))
        assert resp.status_code == 404


class TestCampaignMemberIDOR:
    def test_detail_cross_tenant_404(self, client_a, campaign_member_b):
        resp = client_a.get(reverse("crm:campaignmember_detail", args=[campaign_member_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, campaign_member_b):
        resp = client_a.get(reverse("crm:campaignmember_edit", args=[campaign_member_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, campaign_member_b):
        resp = client_a.post(reverse("crm:campaignmember_delete", args=[campaign_member_b.pk]))
        assert resp.status_code == 404

    def test_campaignmember_add_cross_tenant_campaign_404(self, client_a, campaign_b):
        """Inline-add on a cross-tenant campaign must return 404."""
        resp = client_a.post(
            reverse("crm:campaignmember_add", args=[campaign_b.pk]),
            {"member_name": "Injected", "status": "targeted"},
        )
        assert resp.status_code == 404


class TestFormSubmissionIDOR:
    def test_detail_cross_tenant_404(self, client_a, form_submission_b):
        resp = client_a.get(reverse("crm:formsubmission_detail", args=[form_submission_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, form_submission_b):
        resp = client_a.post(reverse("crm:formsubmission_delete", args=[form_submission_b.pk]))
        assert resp.status_code == 404

    def test_convert_cross_tenant_404(self, client_a, form_submission_b):
        resp = client_a.post(reverse("crm:formsubmission_convert", args=[form_submission_b.pk]))
        assert resp.status_code == 404


# ============================================================= AUTH / ANONYMOUS
class TestMarketingAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("crm:emailtemplate_list", []),
        ("crm:emailcampaign_list", []),
        ("crm:landingpage_list", []),
        ("crm:campaignmember_list", []),
        ("crm:formsubmission_list", []),
        ("crm:emailtemplate_create", []),
        ("crm:emailcampaign_create", []),
        ("crm:landingpage_create", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================= N+1 QUERY BUDGET
class TestMarketingListQueryBudget:
    def test_emailtemplate_list_query_count(self, client_a, tenant_a, django_assert_max_num_queries):
        from apps.crm.models import EmailTemplate
        for i in range(5):
            EmailTemplate.objects.create(tenant=tenant_a, name=f"T{i}", subject=f"S{i}")
        # Allow a generous budget; the real guard is "not O(n)"
        with django_assert_max_num_queries(15):
            client_a.get(reverse("crm:emailtemplate_list"))

    def test_emailcampaign_list_query_count(
        self, client_a, tenant_a, campaign_a, email_template_a, django_assert_max_num_queries
    ):
        from apps.crm.models import EmailCampaign
        for i in range(5):
            EmailCampaign.objects.create(
                tenant=tenant_a, name=f"B{i}", campaign=campaign_a, template=email_template_a
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("crm:emailcampaign_list"))

    def test_landingpage_list_query_count(
        self, client_a, tenant_a, campaign_a, django_assert_max_num_queries
    ):
        from apps.crm.models import LandingPage
        for i in range(5):
            LandingPage.objects.create(
                tenant=tenant_a, name=f"LP{i}", headline=f"H{i}"
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("crm:landingpage_list"))
