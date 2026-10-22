from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.sales.models import (
    AttributionTouchpoint,
    CampaignAttribution,
    ContentEngagement,
    EventRegistration,
    MarketingEvent,
    MqlHandoff,
)
from apps.sales.tests.conftest import (
    MARKETINGALIGNMENT_CHOICES,
    MARKETINGALIGNMENT_MODEL_FIELDS,
    _marketingalignment_attribution,
    _marketingalignment_campaign,
    _marketingalignment_content,
    _marketingalignment_currency,
    _marketingalignment_customer,
    _marketingalignment_engagement,
    _marketingalignment_event,
    _marketingalignment_handoff,
    _marketingalignment_lead,
    _marketingalignment_registration,
    _marketingalignment_touchpoint,
)


@pytest.mark.django_db
def test_marketingalignment_touchpoint_model_fields_and_contract(ma_touchpoint_a):
    fields = {f.name for f in AttributionTouchpoint._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one}
    expected = set(MARKETINGALIGNMENT_MODEL_FIELDS["AttributionTouchpoint"])
    assert expected.issubset(fields)
    assert ma_touchpoint_a.number.startswith("ATB-")


@pytest.mark.django_db
def test_marketingalignment_touchpoint_choices_contract():
    channel_choices = [c[0] for c in AttributionTouchpoint.CHANNEL_CHOICES]
    expected_channels = [c[0] for c in MARKETINGALIGNMENT_CHOICES["AttributionTouchpoint"]["channel"]]
    assert channel_choices == expected_channels

    type_choices = [c[0] for c in AttributionTouchpoint.TOUCH_TYPE_CHOICES]
    expected_types = [c[0] for c in MARKETINGALIGNMENT_CHOICES["AttributionTouchpoint"]["touch_type"]]
    assert type_choices == expected_types


@pytest.mark.django_db
def test_marketingalignment_touchpoint_properties(tenant_a, ma_campaign_a, ma_lead_a, ma_currency):
    tp_first = _marketingalignment_touchpoint(
        tenant_a, campaign=ma_campaign_a, lead=ma_lead_a, currency=ma_currency, touch_position="first"
    )
    assert tp_first.is_first_touch is True
    assert tp_first.is_last_touch is False

    tp_last = _marketingalignment_touchpoint(
        tenant_a, campaign=ma_campaign_a, lead=ma_lead_a, currency=ma_currency, touch_position="last"
    )
    assert tp_last.is_first_touch is False
    assert tp_last.is_last_touch is True


@pytest.mark.django_db
def test_marketingalignment_touchpoint_attributed_revenue_property(tenant_a, ma_touchpoint_a, admin_user):
    _marketingalignment_attribution(
        tenant_a, ma_touchpoint_a, computed_by=admin_user,
        attribution_model="first_touch", attributed_revenue=Decimal("15000.00")
    )
    _marketingalignment_attribution(
        tenant_a, ma_touchpoint_a, computed_by=admin_user,
        attribution_model="last_touch", attributed_revenue=Decimal("10000.00")
    )
    assert ma_touchpoint_a.attributed_revenue == Decimal("25000.00")


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_model_fields_and_contract(ma_attribution_a):
    fields = {f.name for f in CampaignAttribution._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one}
    expected = set(MARKETINGALIGNMENT_MODEL_FIELDS["CampaignAttribution"])
    assert expected.issubset(fields)
    assert ma_attribution_a.number.startswith("ATR-")


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_credit_pct_validation(tenant_a, ma_touchpoint_a, admin_user):
    attr = CampaignAttribution(
        tenant=tenant_a,
        touchpoint=ma_touchpoint_a,
        attribution_model="first_touch",
        credit_pct=Decimal("105.00"),
        computed_by=admin_user,
    )
    with pytest.raises(ValidationError):
        attr.full_clean()


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_unique_per_touchpoint(tenant_a, ma_touchpoint_a, admin_user):
    _marketingalignment_attribution(
        tenant_a, ma_touchpoint_a, computed_by=admin_user, attribution_model="linear"
    )
    dup = CampaignAttribution(
        tenant=tenant_a,
        touchpoint=ma_touchpoint_a,
        attribution_model="linear",
        credit_pct=Decimal("50.00"),
        computed_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        dup.save()


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_model_fields_and_contract(ma_handoff_a):
    fields = {f.name for f in MqlHandoff._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one}
    expected = set(MARKETINGALIGNMENT_MODEL_FIELDS["MqlHandoff"])
    assert expected.issubset(fields)
    assert ma_handoff_a.number.startswith("MQL-")


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_sla_validation(tenant_a, ma_lead_a):
    now = timezone.now()
    handoff = MqlHandoff(
        tenant=tenant_a,
        lead=ma_lead_a,
        handoff_at=now,
        sla_due_at=now - timezone.timedelta(hours=2),
        status="pending",
    )
    with pytest.raises(ValidationError) as exc:
        handoff.clean()
    assert "sla_due_at" in exc.value.message_dict


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_rejection_reason_validation(tenant_a, ma_lead_a):
    now = timezone.now()
    handoff = MqlHandoff(
        tenant=tenant_a,
        lead=ma_lead_a,
        handoff_at=now,
        sla_due_at=now + timezone.timedelta(hours=24),
        status="rejected",
        rejection_reason="",
    )
    with pytest.raises(ValidationError) as exc:
        handoff.clean()
    assert "rejection_reason" in exc.value.message_dict


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_cross_tenant_validation(tenant_a, tenant_b, ma_lead_a, ma_lead_b):
    now = timezone.now()
    handoff = MqlHandoff(
        tenant=tenant_a,
        lead=ma_lead_b,
        handoff_at=now,
        sla_due_at=now + timezone.timedelta(hours=24),
        status="pending",
    )
    with pytest.raises(ValidationError) as exc:
        handoff.clean()
    assert "lead" in exc.value.message_dict


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_auto_stamps_responded_at(tenant_a, ma_lead_a):
    now = timezone.now()
    handoff = _marketingalignment_handoff(
        tenant_a, ma_lead_a, status="pending", handoff_at=now - timezone.timedelta(hours=5)
    )
    assert handoff.responded_at is None
    handoff.status = "accepted"
    handoff.acceptance_reason = "Strong enterprise fit"
    handoff.save()
    handoff.refresh_from_db()
    assert handoff.responded_at is not None
    assert handoff.is_responded is True


@pytest.mark.django_db
def test_marketingalignment_content_engagement_model_fields_and_contract(ma_engagement_a):
    fields = {f.name for f in ContentEngagement._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one}
    expected = set(MARKETINGALIGNMENT_MODEL_FIELDS["ContentEngagement"])
    assert expected.issubset(fields)
    assert ma_engagement_a.number.startswith("CNG-")


@pytest.mark.django_db
def test_marketingalignment_content_engagement_high_intent_property(tenant_a, ma_content_a):
    eng_high = _marketingalignment_engagement(tenant_a, ma_content_a, engagement_score=85)
    assert eng_high.is_high_intent is True

    eng_low = _marketingalignment_engagement(tenant_a, ma_content_a, engagement_score=45)
    assert eng_low.is_high_intent is False


@pytest.mark.django_db
def test_marketingalignment_marketing_event_model_fields_and_contract(ma_event_a):
    fields = {f.name for f in MarketingEvent._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one}
    expected = set(MARKETINGALIGNMENT_MODEL_FIELDS["MarketingEvent"])
    assert expected.issubset(fields)
    assert ma_event_a.number.startswith("EVT-")


@pytest.mark.django_db
def test_marketingalignment_marketing_event_dates_validation(tenant_a, admin_user):
    now = timezone.now()
    evt = MarketingEvent(
        tenant=tenant_a,
        name="Invalid Date Event",
        event_type="webinar",
        status="planned",
        start_at=now + timezone.timedelta(days=2),
        end_at=now + timezone.timedelta(days=1),
        owner=admin_user,
    )
    with pytest.raises(ValidationError) as exc:
        evt.clean()
    assert "end_at" in exc.value.message_dict


@pytest.mark.django_db
def test_marketingalignment_event_registration_model_fields(ma_registration_a):
    fields = {f.name for f in EventRegistration._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one}
    expected = set(MARKETINGALIGNMENT_MODEL_FIELDS["EventRegistration"])
    assert expected.issubset(fields)


@pytest.mark.django_db
def test_marketingalignment_event_registration_auto_stamps_attended_at(tenant_a, ma_event_a):
    reg = _marketingalignment_registration(tenant_a, ma_event_a, registration_status="registered")
    assert reg.attended_at is None
    reg.registration_status = "attended"
    reg.save()
    reg.refresh_from_db()
    assert reg.attended_at is not None


@pytest.mark.django_db
def test_marketingalignment_event_registration_cross_tenant_validation(tenant_a, ma_event_a, ma_lead_b):
    reg = EventRegistration(
        tenant=tenant_a,
        event=ma_event_a,
        lead=ma_lead_b,
        registrant_name="Cross Tenant Registrant",
        registrant_email="cross@example.com",
    )
    with pytest.raises(ValidationError) as exc:
        reg.clean()
    assert "lead" in exc.value.message_dict


@pytest.mark.django_db
def test_marketingalignment_models_str_representations(
    ma_touchpoint_a, ma_attribution_a, ma_handoff_a, ma_engagement_a, ma_event_a, ma_registration_a
):
    assert str(ma_touchpoint_a).startswith("ATB-")
    assert str(ma_attribution_a).startswith("ATR-")
    assert str(ma_handoff_a).startswith("MQL-")
    assert str(ma_engagement_a).startswith("CNG-")
    assert str(ma_event_a).startswith("EVT-")
    assert ma_registration_a.registrant_name in str(ma_registration_a)
