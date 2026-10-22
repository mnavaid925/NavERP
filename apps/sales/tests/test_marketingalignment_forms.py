"""Sales 8.13 Marketing Alignment & Attribution — Form tests.

Verifies form field inclusion, widget classes, tenant queryset scoping,
custom clean validation (SLA deadlines, status locking, rejection reasons, custom models),
and cross-tenant foreign key rejection across all 6 forms.
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.sales.forms.MarketingAlignment.AttributionTouchpoints import (
    AttributionTouchpointForm,
)
from apps.sales.forms.MarketingAlignment.CampaignAttributions import (
    CampaignAttributionForm,
)
from apps.sales.forms.MarketingAlignment.ContentEngagements import (
    ContentEngagementForm,
)
from apps.sales.forms.MarketingAlignment.MarketingEvents import (
    EventRegistrationForm,
    MarketingEventForm,
)
from apps.sales.forms.MarketingAlignment.MqlHandoffs import MqlHandoffForm


@pytest.mark.django_db
def test_marketingalignment_touchpoint_form_valid(tenant_a, ma_campaign_a, ma_lead_a, ma_currency):
    form_data = {
        "campaign": ma_campaign_a.pk,
        "lead": ma_lead_a.pk,
        "channel": "paid_search",
        "touch_type": "click",
        "touch_date": timezone.now().date(),
        "touch_position": "first",
        "cost": "15.50",
        "engagement_value": "120.00",
        "currency": ma_currency.pk,
        "source_reference": "utm_source=google&utm_medium=cpc",
        "notes": "Top of funnel paid click",
    }
    form = AttributionTouchpointForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.number.startswith("ATB-")


@pytest.mark.django_db
def test_marketingalignment_touchpoint_form_tenant_scoping(
    tenant_a, ma_campaign_a, ma_campaign_b, ma_lead_a, ma_lead_b
):
    form = AttributionTouchpointForm(tenant=tenant_a)
    campaign_ids = set(form.fields["campaign"].queryset.values_list("id", flat=True))
    assert ma_campaign_a.pk in campaign_ids
    assert ma_campaign_b.pk not in campaign_ids

    lead_ids = set(form.fields["lead"].queryset.values_list("id", flat=True))
    assert ma_lead_a.pk in lead_ids
    assert ma_lead_b.pk not in lead_ids


@pytest.mark.django_db
def test_marketingalignment_touchpoint_form_cross_tenant_rejection(
    tenant_a, ma_campaign_b, ma_lead_a
):
    form_data = {
        "campaign": ma_campaign_b.pk,
        "lead": ma_lead_a.pk,
        "channel": "paid_search",
        "touch_type": "click",
        "touch_date": timezone.now().date(),
        "touch_position": "first",
        "cost": "10.00",
        "engagement_value": "100.00",
    }
    form = AttributionTouchpointForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "campaign" in form.errors


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_form_valid(
    tenant_a, ma_touchpoint_a, admin_user
):
    form_data = {
        "touchpoint": ma_touchpoint_a.pk,
        "attribution_model": "first_touch",
        "credit_pct": "100.00",
        "attributed_revenue": "25000.00",
        "attributed_cost": "25.00",
        "status": "approved",
        "computed_on": timezone.now().date(),
        "computed_by": admin_user.pk,
        "notes": "Full first touch credit",
    }
    form = CampaignAttributionForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.number.startswith("ATR-")


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_form_custom_model_validation(
    tenant_a, ma_touchpoint_a, admin_user
):
    form_data = {
        "touchpoint": ma_touchpoint_a.pk,
        "attribution_model": "custom",
        "credit_pct": "0.00",
        "attributed_revenue": "0.00",
        "attributed_cost": "0.00",
        "status": "draft",
        "computed_on": timezone.now().date(),
        "computed_by": admin_user.pk,
    }
    form = CampaignAttributionForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "credit_pct" in form.errors


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_form_cross_tenant_rejection(
    tenant_a, ma_touchpoint_b, admin_user
):
    form_data = {
        "touchpoint": ma_touchpoint_b.pk,
        "attribution_model": "linear",
        "credit_pct": "50.00",
        "attributed_revenue": "10000.00",
        "attributed_cost": "20.00",
        "status": "computed",
        "computed_on": timezone.now().date(),
        "computed_by": admin_user.pk,
    }
    form = CampaignAttributionForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "touchpoint" in form.errors


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_form_initial_status_disabled_on_create(tenant_a):
    form = MqlHandoffForm(tenant=tenant_a)
    assert form.fields["status"].initial == "pending"
    assert form.fields["status"].disabled is True


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_form_rejected_requires_reason(
    tenant_a, ma_handoff_a, ma_lead_a, ma_customer_a, admin_user
):
    now = timezone.now()
    form_data = {
        "lead": ma_lead_a.pk,
        "account": ma_customer_a.pk,
        "owner": admin_user.pk,
        "assigned_to": admin_user.pk,
        "status": "rejected",
        "source_kind": "scoring_threshold",
        "handoff_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sla_due_at": (now + timezone.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
        "rejection_reason": "",
    }
    form = MqlHandoffForm(data=form_data, instance=ma_handoff_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "rejection_reason" in form.errors


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_form_sla_date_validation(
    tenant_a, ma_handoff_a, ma_lead_a, ma_customer_a, admin_user
):
    now = timezone.now()
    form_data = {
        "lead": ma_lead_a.pk,
        "account": ma_customer_a.pk,
        "owner": admin_user.pk,
        "assigned_to": admin_user.pk,
        "status": "pending",
        "source_kind": "scoring_threshold",
        "handoff_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sla_due_at": (now - timezone.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
    }
    form = MqlHandoffForm(data=form_data, instance=ma_handoff_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "sla_due_at" in form.errors


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_form_cross_tenant_rejection(
    tenant_a, ma_lead_b, ma_customer_a, admin_user
):
    now = timezone.now()
    form_data = {
        "lead": ma_lead_b.pk,
        "account": ma_customer_a.pk,
        "owner": admin_user.pk,
        "assigned_to": admin_user.pk,
        "status": "pending",
        "source_kind": "scoring_threshold",
        "handoff_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sla_due_at": (now + timezone.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
    }
    form = MqlHandoffForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lead" in form.errors


@pytest.mark.django_db
def test_marketingalignment_content_engagement_form_valid(
    tenant_a, ma_content_a, ma_customer_a, ma_lead_a, ma_currency
):
    now = timezone.now()
    form_data = {
        "content": ma_content_a.pk,
        "account": ma_customer_a.pk,
        "lead": ma_lead_a.pk,
        "engagement_type": "download",
        "engagement_channel": "web",
        "engagement_score": 90,
        "revenue_attributed": "5000.00",
        "currency": ma_currency.pk,
        "engaged_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "Whitepaper downloaded by decision maker",
    }
    form = ContentEngagementForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.number.startswith("CNG-")


@pytest.mark.django_db
def test_marketingalignment_content_engagement_form_cross_tenant_rejection(
    tenant_a, ma_content_b, ma_customer_a, ma_lead_a
):
    now = timezone.now()
    form_data = {
        "content": ma_content_b.pk,
        "account": ma_customer_a.pk,
        "lead": ma_lead_a.pk,
        "engagement_type": "view",
        "engagement_channel": "web",
        "engagement_score": 60,
        "engaged_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    form = ContentEngagementForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "content" in form.errors


@pytest.mark.django_db
def test_marketingalignment_marketing_event_form_valid(tenant_a, admin_user, ma_currency):
    now = timezone.now()
    form_data = {
        "name": "Q4 Cloud Transformation Webinar",
        "event_type": "webinar",
        "status": "planned",
        "start_at": (now + timezone.timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S"),
        "end_at": (now + timezone.timedelta(days=14, hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
        "timezone_name": "UTC",
        "venue": "Virtual Stage A",
        "virtual_url": "https://stream.example.com/live",
        "capacity": 300,
        "budget": "7500.00",
        "currency": ma_currency.pk,
        "owner": admin_user.pk,
        "description": "Enterprise cloud webinar",
    }
    form = MarketingEventForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.number.startswith("EVT-")


@pytest.mark.django_db
def test_marketingalignment_marketing_event_form_end_date_validation(tenant_a, admin_user):
    now = timezone.now()
    form_data = {
        "name": "Invalid Timing Event",
        "event_type": "workshop",
        "status": "planned",
        "start_at": (now + timezone.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
        "end_at": (now + timezone.timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"),
        "owner": admin_user.pk,
    }
    form = MarketingEventForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "end_at" in form.errors


@pytest.mark.django_db
def test_marketingalignment_marketing_event_form_cross_tenant_rejection(tenant_a, admin_b):
    now = timezone.now()
    form_data = {
        "name": "Cross Tenant Owner Event",
        "event_type": "roundtable",
        "status": "planned",
        "start_at": (now + timezone.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
        "end_at": (now + timezone.timedelta(days=2, hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "owner": admin_b.pk,
    }
    form = MarketingEventForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors


@pytest.mark.django_db
def test_marketingalignment_event_registration_form_valid(tenant_a, ma_event_a, ma_lead_a):
    now = timezone.now()
    form_data = {
        "event": ma_event_a.pk,
        "lead": ma_lead_a.pk,
        "registrant_name": "Marcus Aurelius",
        "registrant_email": "marcus@rome.example",
        "registration_status": "registered",
        "source_channel": "campaign",
        "registered_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "followup_status": "pending",
        "engagement_score": 80,
        "revenue_attributed": "0.00",
    }
    form = EventRegistrationForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.registrant_name == "Marcus Aurelius"


@pytest.mark.django_db
def test_marketingalignment_event_registration_form_cross_tenant_rejection(
    tenant_a, ma_event_a, ma_lead_b
):
    now = timezone.now()
    form_data = {
        "event": ma_event_a.pk,
        "lead": ma_lead_b.pk,
        "registrant_name": "Infiltrator",
        "registrant_email": "infiltrator@globex.example",
        "registration_status": "registered",
        "source_channel": "campaign",
        "registered_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "followup_status": "pending",
    }
    form = EventRegistrationForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lead" in form.errors
