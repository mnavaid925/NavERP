"""Tests for Sales 8.16 Mobile Sales & Field Execution forms.

Covers all forms under apps/sales/forms/MobileSales/:
1. FieldSalesRouteForm & FieldSalesRouteFilterForm:
   - Excluded fields: tenant, number, created_at, updated_at
   - Optional execution metrics: planned_distance_km, actual_distance_km,
     estimated_duration_minutes, actual_duration_minutes (required=False)
   - Metrics clean defaults: empty/None cleans to Decimal("0.00") and 0
   - Tenant scoping on sales_rep ModelChoiceField
   - Filter form: status, sales_rep, route_date, q
2. FieldCheckInForm, FieldCheckOutForm & FieldCheckInFilterForm:
   - Excluded fields in FieldCheckInForm: tenant, number, created_at, updated_at,
     duration_minutes, is_geofence_verified
   - Optional technical defaults: geofence_radius_m (defaults to 150),
     verification_status (defaults to "verified")
   - Tenant scoping on party, contact, opportunity, resulting_quote, route,
     photo_document, sales_rep ModelChoiceFields
   - FieldCheckOutForm: checkout lat/lng, outcome, notes, next_step, next_step_due
   - Filter form: verification_status, visit_purpose, outcome, sales_rep, q
3. MobileDeviceSessionForm & MobileDeviceSessionFilterForm:
   - Excluded fields: tenant, number, created_at, updated_at, last_sync_at
   - Optional technical defaults: last_sync_status (defaults to "pending")
   - is_trusted disabled/omitted if not tenant admin:
     - Editable for tenant admin and superuser
     - Disabled for non-tenant-admin (cleans to False on create, preserves on update)
   - Tenant scoping on user ModelChoiceField
   - Filter form: platform, last_sync_status, user, q
4. MobileDealAlertForm & MobileDealAlertFilterForm:
   - Excluded fields: tenant, number, created_at, updated_at, is_read, read_at,
     push_sent_at, push_status
   - Optional urgency defaults to normal (required=False)
   - Tenant scoping on recipient, device, related_route, related_quote,
     related_opportunity ModelChoiceFields (device queryset uses select_related("user"))
   - Filter form: alert_type, urgency, is_read, recipient, q
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import Document
from apps.crm.models import Opportunity
from apps.sales.forms.MobileSales.FieldCheckIns import (
    FieldCheckInFilterForm,
    FieldCheckInForm,
    FieldCheckOutForm,
)
from apps.sales.forms.MobileSales.FieldSalesRoutes import (
    FieldSalesRouteFilterForm,
    FieldSalesRouteForm,
)
from apps.sales.forms.MobileSales.MobileDealAlerts import (
    MobileDealAlertFilterForm,
    MobileDealAlertForm,
)
from apps.sales.forms.MobileSales.MobileDeviceSessions import (
    MobileDeviceSessionFilterForm,
    MobileDeviceSessionForm,
)
from apps.sales.models.MobileSales.FieldCheckIns import FieldCheckIn
from apps.sales.models.MobileSales.FieldSalesRoutes import FieldSalesRoute
from apps.sales.models.MobileSales.MobileDealAlerts import MobileDealAlert
from apps.sales.models.MobileSales.MobileDeviceSessions import MobileDeviceSession
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote


# ==============================================================================
# HELPERS (_mobilesales_*)
# ==============================================================================


def _mobilesales_opportunity(tenant, **overrides):
    defaults = {
        "tenant": tenant,
        "name": f"{tenant.slug.title()} Pipeline Opportunity",
        "stage": "qualification",
        "forecast_category": "pipeline",
        "amount": Decimal("25000.00"),
        "probability": 40,
    }
    defaults.update(overrides)
    return Opportunity.objects.create(**defaults)


def _mobilesales_document(tenant, **overrides):
    defaults = {
        "tenant": tenant,
        "name": "storefront_display.jpg",
        "file": "uploads/storefront_display.jpg",
    }
    defaults.update(overrides)
    return Document.objects.create(**defaults)


def _mobilesales_quote(tenant, **overrides):
    from apps.accounting.models import Currency

    currency = overrides.pop("currency", None)
    if currency is None:
        currency, _ = Currency.objects.get_or_create(
            code="USD",
            defaults={"name": "US Dollar", "symbol": "$"},
        )
    defaults = {
        "tenant": tenant,
        "name": f"{tenant.slug.title()} Deal Quote",
        "currency": currency,
        "status": "draft",
    }
    defaults.update(overrides)
    return CPQQuote.objects.create(**defaults)


def _mobilesales_superuser(email="super@example.com", username="superuser"):
    return User.objects.create_superuser(
        email=email,
        username=username,
        password="SuperPass123!",
    )


# ==============================================================================
# 1. FieldSalesRouteForm & FieldSalesRouteFilterForm
# ==============================================================================


@pytest.mark.django_db
def test_mobilesales_route_form_excluded_fields():
    """Verify tenant, number, created_at, updated_at are strictly excluded."""
    excluded = {"tenant", "number", "created_at", "updated_at"}
    meta_fields = set(FieldSalesRouteForm.Meta.fields)
    assert meta_fields.isdisjoint(excluded), f"Found excluded fields in Meta.fields: {meta_fields & excluded}"

    form = FieldSalesRouteForm()
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must not be present in form.fields"


@pytest.mark.django_db
def test_mobilesales_route_form_optional_execution_metrics(tenant_a):
    """Verify planned_distance_km, actual_distance_km, estimated_duration_minutes, actual_duration_minutes are required=False."""
    form = FieldSalesRouteForm(tenant=tenant_a)
    optional_fields = [
        "planned_distance_km",
        "actual_distance_km",
        "estimated_duration_minutes",
        "actual_duration_minutes",
    ]
    for name in optional_fields:
        assert not form.fields[name].required, f"Field '{name}' should have required=False"


@pytest.mark.django_db
def test_mobilesales_route_form_clean_metrics_defaults(tenant_a, admin_user):
    """When execution metrics are omitted or blank, clean methods default them to 0 / 0.00."""
    today = timezone.localdate()
    data = {
        "name": "Downtown Express Sweep",
        "sales_rep": admin_user.pk,
        "route_date": today.isoformat(),
        "status": "scheduled",
        "optimization_status": "unoptimized",
        "total_stops": 4,
        "planned_distance_km": "",
        "actual_distance_km": "",
        "estimated_duration_minutes": "",
        "actual_duration_minutes": "",
    }
    form = FieldSalesRouteForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["planned_distance_km"] == Decimal("0.00")
    assert form.cleaned_data["actual_distance_km"] == Decimal("0.00")
    assert form.cleaned_data["estimated_duration_minutes"] == 0
    assert form.cleaned_data["actual_duration_minutes"] == 0


@pytest.mark.django_db
def test_mobilesales_route_form_valid_submission_with_metrics(tenant_a, admin_user):
    """Submitting valid route data with explicit metrics successfully validates and saves."""
    today = timezone.localdate()
    data = {
        "name": "West Coast Field Run",
        "sales_rep": admin_user.pk,
        "route_date": today.isoformat(),
        "status": "in_progress",
        "start_location": "37.7749,-122.4194",
        "end_location": "37.7849,-122.4094",
        "total_stops": 5,
        "planned_distance_km": "42.50",
        "actual_distance_km": "10.20",
        "estimated_duration_minutes": 240,
        "actual_duration_minutes": 60,
        "optimization_status": "optimized",
        "notes": "Route verified by dispatch coordinator.",
    }
    form = FieldSalesRouteForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    route = form.save(commit=False)
    route.tenant = tenant_a
    route.save()

    assert route.pk is not None
    assert route.number.startswith("FSR-")
    assert route.name == "West Coast Field Run"
    assert route.planned_distance_km == Decimal("42.50")
    assert route.actual_distance_km == Decimal("10.20")
    assert route.estimated_duration_minutes == 240
    assert route.actual_duration_minutes == 60


@pytest.mark.django_db
def test_mobilesales_route_form_sales_rep_tenant_scoping(tenant_a, tenant_b, admin_user, admin_b):
    """sales_rep ModelChoiceField queryset must be scoped to the form's tenant."""
    form_a = FieldSalesRouteForm(tenant=tenant_a)
    assert admin_user in form_a.fields["sales_rep"].queryset
    assert admin_b not in form_a.fields["sales_rep"].queryset

    form_b = FieldSalesRouteForm(tenant=tenant_b)
    assert admin_b in form_b.fields["sales_rep"].queryset
    assert admin_user not in form_b.fields["sales_rep"].queryset


@pytest.mark.django_db
def test_mobilesales_route_form_rejects_foreign_sales_rep(tenant_a, admin_b):
    """Attempting to assign a sales_rep from another tenant must fail validation."""
    today = timezone.localdate()
    data = {
        "name": "Cross-tenant Route Attempt",
        "sales_rep": admin_b.pk,  # From tenant_b
        "route_date": today.isoformat(),
        "status": "scheduled",
        "total_stops": 3,
    }
    form = FieldSalesRouteForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "sales_rep" in form.errors


@pytest.mark.django_db
def test_mobilesales_route_form_missing_required_fields(tenant_a):
    """Missing required fields (name, route_date) triggers form errors."""
    form = FieldSalesRouteForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "route_date" in form.errors


@pytest.mark.django_db
def test_mobilesales_route_filter_form_fields():
    """Verify FieldSalesRouteFilterForm has expected filter fields: status, sales_rep, route_date, q."""
    form = FieldSalesRouteFilterForm()
    assert "q" in form.fields
    assert "status" in form.fields
    assert "sales_rep" in form.fields
    assert "route_date" in form.fields


@pytest.mark.django_db
def test_mobilesales_route_filter_form_empty(tenant_a):
    """Empty GET data is completely valid on FieldSalesRouteFilterForm."""
    filter_form = FieldSalesRouteFilterForm(data={}, tenant=tenant_a)
    assert filter_form.is_valid(), filter_form.errors


@pytest.mark.django_db
def test_mobilesales_route_filter_form_valid_filters(tenant_a, admin_user):
    """FieldSalesRouteFilterForm correctly validates populated query parameters."""
    today = timezone.localdate()
    data = {
        "q": "Express",
        "status": "scheduled",
        "sales_rep": admin_user.pk,
        "route_date": today.isoformat(),
    }
    filter_form = FieldSalesRouteFilterForm(data=data, tenant=tenant_a)
    assert filter_form.is_valid(), filter_form.errors
    assert filter_form.cleaned_data["q"] == "Express"
    assert filter_form.cleaned_data["status"] == "scheduled"
    assert filter_form.cleaned_data["sales_rep"] == admin_user
    assert filter_form.cleaned_data["route_date"] == today


@pytest.mark.django_db
def test_mobilesales_route_filter_form_sales_rep_tenant_scoping(tenant_a, tenant_b, admin_user, admin_b):
    """FieldSalesRouteFilterForm scopes sales_rep queryset to provided tenant."""
    filter_a = FieldSalesRouteFilterForm(tenant=tenant_a)
    assert admin_user in filter_a.fields["sales_rep"].queryset
    assert admin_b not in filter_a.fields["sales_rep"].queryset


# ==============================================================================
# 2. FieldCheckInForm, FieldCheckOutForm & FieldCheckInFilterForm
# ==============================================================================


@pytest.mark.django_db
def test_mobilesales_check_in_form_excluded_fields():
    """Verify tenant, number, created_at, updated_at, duration_minutes, is_geofence_verified are excluded."""
    excluded = {
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "duration_minutes",
        "is_geofence_verified",
    }
    meta_fields = set(FieldCheckInForm.Meta.fields)
    assert meta_fields.isdisjoint(excluded), f"Found excluded fields in Meta.fields: {meta_fields & excluded}"

    form = FieldCheckInForm()
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must not be present in form.fields"


@pytest.mark.django_db
def test_mobilesales_check_in_form_optional_technical_defaults(tenant_a):
    """Verify geofence_radius_m and verification_status are required=False."""
    form = FieldCheckInForm(tenant=tenant_a)
    assert not form.fields["geofence_radius_m"].required
    assert not form.fields["verification_status"].required


@pytest.mark.django_db
def test_mobilesales_check_in_form_clean_technical_defaults(tenant_a, ms_party_a, admin_user):
    """When geofence_radius_m and verification_status are blank, clean methods default them to 150 and 'verified'."""
    data = {
        "stop_number": 1,
        "party": ms_party_a.pk,
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
        "geofence_radius_m": "",
        "verification_status": "",
        "visit_purpose": "relationship",
        "outcome": "successful",
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["geofence_radius_m"] == 150
    assert form.cleaned_data["verification_status"] == "verified"


@pytest.mark.django_db
def test_mobilesales_check_in_form_explicit_technical_values(tenant_a, ms_party_a, admin_user):
    """Explicit technical parameters are preserved by clean methods."""
    data = {
        "stop_number": 2,
        "party": ms_party_a.pk,
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
        "geofence_radius_m": 350,
        "verification_status": "manual_override",
        "visit_purpose": "quote_review",
        "outcome": "order_placed",
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["geofence_radius_m"] == 350
    assert form.cleaned_data["verification_status"] == "manual_override"


@pytest.mark.django_db
def test_mobilesales_check_in_form_tenant_scoping_querysets(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    ms_party_a,
    ms_party_b,
    ms_route_a,
    ms_route_b,
):
    """ModelChoiceFields (party, contact, opportunity, resulting_quote, route, photo_document, sales_rep) are tenant-scoped."""
    opp_a = _mobilesales_opportunity(tenant_a)
    opp_b = _mobilesales_opportunity(tenant_b)
    doc_a = _mobilesales_document(tenant_a)
    doc_b = _mobilesales_document(tenant_b)
    quote_a = _mobilesales_quote(tenant_a)
    quote_b = _mobilesales_quote(tenant_b)

    form = FieldCheckInForm(tenant=tenant_a)

    # Party & Contact
    assert ms_party_a in form.fields["party"].queryset
    assert ms_party_b not in form.fields["party"].queryset
    assert ms_party_a in form.fields["contact"].queryset
    assert ms_party_b not in form.fields["contact"].queryset

    # Route & Sales rep
    assert ms_route_a in form.fields["route"].queryset
    assert ms_route_b not in form.fields["route"].queryset
    assert admin_user in form.fields["sales_rep"].queryset
    assert admin_b not in form.fields["sales_rep"].queryset

    # Spine integrations: Opportunity, Quote, Document
    assert opp_a in form.fields["opportunity"].queryset
    assert opp_b not in form.fields["opportunity"].queryset
    assert quote_a in form.fields["resulting_quote"].queryset
    assert quote_b not in form.fields["resulting_quote"].queryset
    assert doc_a in form.fields["photo_document"].queryset
    assert doc_b not in form.fields["photo_document"].queryset


@pytest.mark.django_db
def test_mobilesales_check_in_form_rejects_foreign_party(tenant_a, ms_party_b, admin_user):
    """Submitting a foreign tenant party triggers a validation error."""
    data = {
        "stop_number": 1,
        "party": ms_party_b.pk,  # From tenant_b
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors


@pytest.mark.django_db
def test_mobilesales_check_in_form_rejects_foreign_route(tenant_a, ms_party_a, ms_route_b, admin_user):
    """Submitting a foreign route triggers a validation error."""
    data = {
        "stop_number": 1,
        "party": ms_party_a.pk,
        "route": ms_route_b.pk,  # From tenant_b
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "route" in form.errors


@pytest.mark.django_db
def test_mobilesales_check_in_form_rejects_foreign_sales_rep(tenant_a, ms_party_a, admin_b):
    """Submitting a foreign sales_rep triggers a validation error."""
    data = {
        "stop_number": 1,
        "party": ms_party_a.pk,
        "sales_rep": admin_b.pk,  # From tenant_b
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "sales_rep" in form.errors


@pytest.mark.django_db
def test_mobilesales_check_in_form_rejects_foreign_opportunity(tenant_a, tenant_b, ms_party_a, admin_user):
    """Submitting a foreign opportunity triggers a validation error."""
    opp_b = _mobilesales_opportunity(tenant_b)
    data = {
        "stop_number": 1,
        "party": ms_party_a.pk,
        "opportunity": opp_b.pk,
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "opportunity" in form.errors


@pytest.mark.django_db
def test_mobilesales_check_in_form_rejects_foreign_quote(tenant_a, tenant_b, ms_party_a, admin_user):
    """Submitting a foreign quote triggers a validation error."""
    quote_b = _mobilesales_quote(tenant_b)
    data = {
        "stop_number": 1,
        "party": ms_party_a.pk,
        "resulting_quote": quote_b.pk,
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "resulting_quote" in form.errors


@pytest.mark.django_db
def test_mobilesales_check_in_form_rejects_foreign_document(tenant_a, tenant_b, ms_party_a, admin_user):
    """Submitting a foreign document triggers a validation error."""
    doc_b = _mobilesales_document(tenant_b)
    data = {
        "stop_number": 1,
        "party": ms_party_a.pk,
        "photo_document": doc_b.pk,
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "photo_document" in form.errors


@pytest.mark.django_db
def test_mobilesales_check_in_form_valid_submission(
    tenant_a,
    ms_party_a,
    ms_route_a,
    admin_user,
):
    """Valid complete check-in data saves successfully and generates number."""
    opp_a = _mobilesales_opportunity(tenant_a)
    doc_a = _mobilesales_document(tenant_a)
    quote_a = _mobilesales_quote(tenant_a)
    tomorrow = timezone.localdate() + timezone.timedelta(days=1)

    data = {
        "route": ms_route_a.pk,
        "stop_number": 1,
        "party": ms_party_a.pk,
        "contact": ms_party_a.pk,
        "opportunity": opp_a.pk,
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
        "target_lat": "37.775000",
        "target_lng": "-122.419500",
        "geofence_radius_m": 200,
        "verification_status": "verified",
        "visit_purpose": "relationship",
        "outcome": "order_placed",
        "notes": "Delivered promotional samples and discussed bulk replenishment.",
        "next_step": "Draft master supply agreement.",
        "next_step_due": tomorrow.isoformat(),
        "photo_document": doc_a.pk,
        "resulting_quote": quote_a.pk,
    }
    form = FieldCheckInForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    check_in = form.save(commit=False)
    check_in.tenant = tenant_a
    check_in.save()

    assert check_in.pk is not None
    assert check_in.number.startswith("CHK-")
    assert check_in.party == ms_party_a
    assert check_in.resulting_quote == quote_a
    assert check_in.photo_document == doc_a
    assert check_in.is_geofence_verified is True


@pytest.mark.django_db
def test_mobilesales_check_in_form_missing_required_fields(tenant_a):
    """Missing party or lat/lng fails form validation."""
    form = FieldCheckInForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors
    assert "check_in_lat" in form.errors
    assert "check_in_lng" in form.errors


@pytest.mark.django_db
def test_mobilesales_checkout_form_fields():
    """FieldCheckOutForm exposes check_out_lat, check_out_lng, outcome, notes, next_step, next_step_due."""
    form = FieldCheckOutForm()
    expected = {"check_out_lat", "check_out_lng", "outcome", "notes", "next_step", "next_step_due"}
    assert set(form.fields.keys()) == expected


@pytest.mark.django_db
def test_mobilesales_checkout_form_valid_update(ms_check_in_a):
    """FieldCheckOutForm successfully updates an existing check-in instance."""
    tomorrow = timezone.localdate() + timezone.timedelta(days=1)
    data = {
        "check_out_lat": "37.774950",
        "check_out_lng": "-122.419450",
        "outcome": "order_placed",
        "notes": "Completed demo, client accepted proposal.",
        "next_step": "Issue invoice",
        "next_step_due": tomorrow.isoformat(),
    }
    form = FieldCheckOutForm(data=data, instance=ms_check_in_a)
    assert form.is_valid(), form.errors
    updated = form.save()

    assert updated.pk == ms_check_in_a.pk
    assert updated.check_out_lat == Decimal("37.774950")
    assert updated.check_out_lng == Decimal("-122.419450")
    assert updated.outcome == "order_placed"
    assert "accepted proposal" in updated.notes
    assert updated.next_step == "Issue invoice"


@pytest.mark.django_db
def test_mobilesales_checkout_form_optional_fields(ms_check_in_a):
    """notes, next_step, next_step_due can be omitted on checkout."""
    data = {
        "check_out_lat": "37.774950",
        "check_out_lng": "-122.419450",
        "outcome": "successful",
        "notes": "",
        "next_step": "",
        "next_step_due": "",
    }
    form = FieldCheckOutForm(data=data, instance=ms_check_in_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_mobilesales_check_in_filter_form_fields():
    """Verify FieldCheckInFilterForm contains verification_status, visit_purpose, outcome, sales_rep, q."""
    form = FieldCheckInFilterForm()
    expected = {"verification_status", "visit_purpose", "outcome", "sales_rep", "q"}
    assert set(form.fields.keys()) == expected


@pytest.mark.django_db
def test_mobilesales_check_in_filter_form_empty(tenant_a):
    """Empty GET parameters validate cleanly on FieldCheckInFilterForm."""
    filter_form = FieldCheckInFilterForm(data={}, tenant=tenant_a)
    assert filter_form.is_valid(), filter_form.errors


@pytest.mark.django_db
def test_mobilesales_check_in_filter_form_valid_filters(tenant_a, admin_user):
    """FieldCheckInFilterForm parses and validates filter criteria."""
    data = {
        "q": "Apex",
        "verification_status": "verified",
        "visit_purpose": "relationship",
        "outcome": "order_placed",
        "sales_rep": admin_user.pk,
    }
    filter_form = FieldCheckInFilterForm(data=data, tenant=tenant_a)
    assert filter_form.is_valid(), filter_form.errors
    assert filter_form.cleaned_data["q"] == "Apex"
    assert filter_form.cleaned_data["verification_status"] == "verified"
    assert filter_form.cleaned_data["visit_purpose"] == "relationship"
    assert filter_form.cleaned_data["outcome"] == "order_placed"
    assert filter_form.cleaned_data["sales_rep"] == admin_user


@pytest.mark.django_db
def test_mobilesales_check_in_filter_form_sales_rep_tenant_scoping(tenant_a, tenant_b, admin_user, admin_b):
    """FieldCheckInFilterForm scopes sales_rep queryset to the current workspace."""
    filter_a = FieldCheckInFilterForm(tenant=tenant_a)
    assert admin_user in filter_a.fields["sales_rep"].queryset
    assert admin_b not in filter_a.fields["sales_rep"].queryset


# ==============================================================================
# 3. MobileDeviceSessionForm & MobileDeviceSessionFilterForm
# ==============================================================================


@pytest.mark.django_db
def test_mobilesales_device_form_excluded_fields():
    """Verify tenant, number, created_at, updated_at, last_sync_at are excluded."""
    excluded = {"tenant", "number", "created_at", "updated_at", "last_sync_at"}
    meta_fields = set(MobileDeviceSessionForm.Meta.fields)
    assert meta_fields.isdisjoint(excluded), f"Found excluded fields in Meta.fields: {meta_fields & excluded}"

    form = MobileDeviceSessionForm()
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must not be present in form.fields"


@pytest.mark.django_db
def test_mobilesales_device_form_optional_technical_defaults(tenant_a):
    """Verify last_sync_status is required=False."""
    form = MobileDeviceSessionForm(tenant=tenant_a)
    assert not form.fields["last_sync_status"].required


@pytest.mark.django_db
def test_mobilesales_device_form_clean_last_sync_status_default(tenant_a, admin_user):
    """When last_sync_status is blank, it cleans to 'pending'."""
    data = {
        "user": admin_user.pk,
        "device_uuid": "IPAD-MINI-001",
        "device_name": "Field Rep iPad Mini",
        "platform": "ios",
        "app_version": "2.5.0",
        "push_token": "token-xyz-123",
        "is_active": True,
        "is_trusted": True,
        "last_sync_status": "",
    }
    form = MobileDeviceSessionForm(data=data, tenant=tenant_a, user=admin_user)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["last_sync_status"] == "pending"


@pytest.mark.django_db
def test_mobilesales_device_form_is_trusted_tenant_admin(tenant_a, admin_user):
    """Tenant admin can toggle is_trusted without field being disabled."""
    form = MobileDeviceSessionForm(tenant=tenant_a, user=admin_user)
    assert not form.fields["is_trusted"].disabled

    data = {
        "user": admin_user.pk,
        "device_uuid": "IPAD-PRO-999",
        "device_name": "Admin iPad Pro",
        "platform": "ios",
        "app_version": "2.5.0",
        "push_token": "token-admin",
        "is_active": True,
        "is_trusted": True,
    }
    form = MobileDeviceSessionForm(data=data, tenant=tenant_a, user=admin_user)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["is_trusted"] is True


@pytest.mark.django_db
def test_mobilesales_device_form_is_trusted_superuser(tenant_a, admin_user):
    """Superuser can toggle is_trusted without field being disabled."""
    super_user = _mobilesales_superuser()
    form = MobileDeviceSessionForm(tenant=tenant_a, user=super_user)
    assert not form.fields["is_trusted"].disabled

    data = {
        "user": admin_user.pk,
        "device_uuid": "PIXEL-SUPER-01",
        "device_name": "Superuser Device",
        "platform": "android",
        "app_version": "2.5.0",
        "push_token": "token-super",
        "is_active": True,
        "is_trusted": True,
    }
    form = MobileDeviceSessionForm(data=data, tenant=tenant_a, user=super_user)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["is_trusted"] is True


@pytest.mark.django_db
def test_mobilesales_device_form_is_trusted_non_admin_creation(tenant_a, member_user):
    """Non-tenant-admin user has is_trusted disabled and cleaned to False on create."""
    form = MobileDeviceSessionForm(tenant=tenant_a, user=member_user)
    assert form.fields["is_trusted"].disabled is True

    # Even if client sends is_trusted=True in POST, clean_is_trusted returns False for new record
    data = {
        "user": member_user.pk,
        "device_uuid": "SAMSUNG-S23-01",
        "device_name": "Member Galaxy S23",
        "platform": "android",
        "app_version": "2.5.0",
        "push_token": "token-member",
        "is_active": True,
        "is_trusted": True,
    }
    form = MobileDeviceSessionForm(data=data, tenant=tenant_a, user=member_user)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["is_trusted"] is False


@pytest.mark.django_db
def test_mobilesales_device_form_is_trusted_non_admin_preserves_existing_trusted(tenant_a, member_user, ms_device_a):
    """When editing an existing trusted device, non-tenant-admin cleans to existing instance.is_trusted (True)."""
    assert ms_device_a.is_trusted is True
    form = MobileDeviceSessionForm(
        instance=ms_device_a,
        tenant=tenant_a,
        user=member_user,
    )
    assert form.fields["is_trusted"].disabled is True

    data = {
        "user": ms_device_a.user.pk,
        "device_uuid": ms_device_a.device_uuid,
        "device_name": "Renamed Device",
        "platform": ms_device_a.platform,
        "app_version": "2.6.0",
        "push_token": ms_device_a.push_token,
        "is_active": True,
        "is_trusted": False,  # Non-admin cannot revoke existing trust
    }
    form = MobileDeviceSessionForm(
        data=data,
        instance=ms_device_a,
        tenant=tenant_a,
        user=member_user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["is_trusted"] is True


@pytest.mark.django_db
def test_mobilesales_device_form_is_trusted_non_admin_preserves_existing_untrusted(tenant_a, member_user, ms_device_a):
    """When editing an existing untrusted device, non-tenant-admin cannot elevate trust."""
    ms_device_a.is_trusted = False
    ms_device_a.save()

    data = {
        "user": ms_device_a.user.pk,
        "device_uuid": ms_device_a.device_uuid,
        "device_name": ms_device_a.device_name,
        "platform": ms_device_a.platform,
        "app_version": "2.6.0",
        "push_token": ms_device_a.push_token,
        "is_active": True,
        "is_trusted": True,  # Non-admin cannot grant trust
    }
    form = MobileDeviceSessionForm(
        data=data,
        instance=ms_device_a,
        tenant=tenant_a,
        user=member_user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["is_trusted"] is False


@pytest.mark.django_db
def test_mobilesales_device_form_tenant_scoping_user(tenant_a, tenant_b, admin_user, admin_b):
    """MobileDeviceSessionForm scopes user queryset to the tenant."""
    form_a = MobileDeviceSessionForm(tenant=tenant_a)
    assert admin_user in form_a.fields["user"].queryset
    assert admin_b not in form_a.fields["user"].queryset


@pytest.mark.django_db
def test_mobilesales_device_form_rejects_foreign_user(tenant_a, admin_b):
    """Submitting a foreign user triggers a form validation error."""
    data = {
        "user": admin_b.pk,  # From tenant_b
        "device_uuid": "IPAD-CROSS-01",
        "device_name": "Foreign Device",
        "platform": "ios",
        "app_version": "2.5.0",
    }
    form = MobileDeviceSessionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "user" in form.errors


@pytest.mark.django_db
def test_mobilesales_device_form_valid_submission(tenant_a, admin_user):
    """Valid data saves a new MobileDeviceSession instance."""
    data = {
        "user": admin_user.pk,
        "device_uuid": "DEV-TEST-555",
        "device_name": "Logistics Tablet",
        "platform": "android",
        "app_version": "3.1.2",
        "push_token": "fcm-registration-token-999",
        "is_active": True,
        "is_trusted": True,
        "last_sync_status": "success",
    }
    form = MobileDeviceSessionForm(data=data, tenant=tenant_a, user=admin_user)
    assert form.is_valid(), form.errors
    device = form.save(commit=False)
    device.tenant = tenant_a
    device.save()

    assert device.pk is not None
    assert device.number.startswith("MDS-")
    assert device.device_name == "Logistics Tablet"
    assert device.is_trusted is True
    assert device.last_sync_status == "success"


@pytest.mark.django_db
def test_mobilesales_device_form_missing_required_fields(tenant_a):
    """Missing user, device_uuid, or device_name triggers errors."""
    form = MobileDeviceSessionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "user" in form.errors
    assert "device_uuid" in form.errors
    assert "device_name" in form.errors


@pytest.mark.django_db
def test_mobilesales_device_filter_form_fields():
    """Verify MobileDeviceSessionFilterForm exposes platform, last_sync_status, user, q."""
    form = MobileDeviceSessionFilterForm()
    expected = {"platform", "last_sync_status", "user", "q"}
    assert set(form.fields.keys()) == expected


@pytest.mark.django_db
def test_mobilesales_device_filter_form_empty(tenant_a):
    """Empty GET parameters validate cleanly on MobileDeviceSessionFilterForm."""
    filter_form = MobileDeviceSessionFilterForm(data={}, tenant=tenant_a)
    assert filter_form.is_valid(), filter_form.errors


@pytest.mark.django_db
def test_mobilesales_device_filter_form_valid_filters(tenant_a, admin_user):
    """MobileDeviceSessionFilterForm correctly parses populated parameters."""
    data = {
        "q": "iPad",
        "platform": "ios",
        "last_sync_status": "success",
        "user": admin_user.pk,
    }
    filter_form = MobileDeviceSessionFilterForm(data=data, tenant=tenant_a)
    assert filter_form.is_valid(), filter_form.errors
    assert filter_form.cleaned_data["q"] == "iPad"
    assert filter_form.cleaned_data["platform"] == "ios"
    assert filter_form.cleaned_data["last_sync_status"] == "success"
    assert filter_form.cleaned_data["user"] == admin_user


@pytest.mark.django_db
def test_mobilesales_device_filter_form_user_tenant_scoping(tenant_a, tenant_b, admin_user, admin_b):
    """MobileDeviceSessionFilterForm user queryset is scoped to tenant."""
    filter_a = MobileDeviceSessionFilterForm(tenant=tenant_a)
    assert admin_user in filter_a.fields["user"].queryset
    assert admin_b not in filter_a.fields["user"].queryset


# ==============================================================================
# 4. MobileDealAlertForm & MobileDealAlertFilterForm
# ==============================================================================


@pytest.mark.django_db
def test_mobilesales_alert_form_excluded_fields():
    """Verify tenant, number, created_at, updated_at, is_read, read_at, push_sent_at, push_status are excluded."""
    excluded = {
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "is_read",
        "read_at",
        "push_sent_at",
        "push_status",
    }
    meta_fields = set(MobileDealAlertForm.Meta.fields)
    assert meta_fields.isdisjoint(excluded), f"Found excluded fields in Meta.fields: {meta_fields & excluded}"

    form = MobileDealAlertForm()
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must not be present in form.fields"


@pytest.mark.django_db
def test_mobilesales_alert_form_optional_urgency_default(tenant_a):
    """Verify urgency is required=False."""
    form = MobileDealAlertForm(tenant=tenant_a)
    assert not form.fields["urgency"].required


@pytest.mark.django_db
def test_mobilesales_alert_form_clean_urgency_default(tenant_a, admin_user):
    """When urgency is blank, clean_urgency defaults to 'normal'."""
    data = {
        "recipient": admin_user.pk,
        "alert_type": "contract_expiring",
        "title": "Quarterly Renewal Reminder",
        "message": "Contract renewal window opens next week.",
        "urgency": "",
    }
    form = MobileDealAlertForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["urgency"] == "normal"


@pytest.mark.django_db
def test_mobilesales_alert_form_clean_urgency_explicit(tenant_a, admin_user):
    """Explicit urgency choices (high, urgent) are preserved."""
    data = {
        "recipient": admin_user.pk,
        "alert_type": "deal_stage_changed",
        "title": "High Margin Opportunity",
        "message": "Deal has advanced to final negotiation stage.",
        "urgency": "urgent",
    }
    form = MobileDealAlertForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["urgency"] == "urgent"


@pytest.mark.django_db
def test_mobilesales_alert_form_tenant_scoping_querysets(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    ms_device_a,
    ms_device_b,
    ms_route_a,
    ms_route_b,
):
    """recipient, device, related_route, related_quote, related_opportunity are tenant-scoped."""
    opp_a = _mobilesales_opportunity(tenant_a)
    opp_b = _mobilesales_opportunity(tenant_b)
    quote_a = _mobilesales_quote(tenant_a)
    quote_b = _mobilesales_quote(tenant_b)

    form = MobileDealAlertForm(tenant=tenant_a)

    assert admin_user in form.fields["recipient"].queryset
    assert admin_b not in form.fields["recipient"].queryset

    assert ms_device_a in form.fields["device"].queryset
    assert ms_device_b not in form.fields["device"].queryset

    assert ms_route_a in form.fields["related_route"].queryset
    assert ms_route_b not in form.fields["related_route"].queryset

    assert opp_a in form.fields["related_opportunity"].queryset
    assert opp_b not in form.fields["related_opportunity"].queryset

    assert quote_a in form.fields["related_quote"].queryset
    assert quote_b not in form.fields["related_quote"].queryset


@pytest.mark.django_db
def test_mobilesales_alert_form_device_queryset_select_related_user(tenant_a):
    """device queryset must use select_related('user') for optimal rendering."""
    form = MobileDealAlertForm(tenant=tenant_a)
    select_related = form.fields["device"].queryset.query.select_related
    assert "user" in select_related, f"Expected 'user' in select_related, got {select_related}"


@pytest.mark.django_db
def test_mobilesales_alert_form_rejects_foreign_recipient(tenant_a, admin_b):
    """Submitting a foreign recipient fails form validation."""
    data = {
        "recipient": admin_b.pk,  # From tenant_b
        "alert_type": "quote_approval_required",
        "title": "Cross Tenant Alert",
        "message": "Testing cross-tenant isolation.",
    }
    form = MobileDealAlertForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "recipient" in form.errors


@pytest.mark.django_db
def test_mobilesales_alert_form_rejects_foreign_device(tenant_a, admin_user, ms_device_b):
    """Submitting a foreign device fails form validation."""
    data = {
        "recipient": admin_user.pk,
        "device": ms_device_b.pk,  # From tenant_b
        "alert_type": "quote_approval_required",
        "title": "Foreign Device Alert",
        "message": "Testing device isolation.",
    }
    form = MobileDealAlertForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "device" in form.errors


@pytest.mark.django_db
def test_mobilesales_alert_form_rejects_foreign_route(tenant_a, admin_user, ms_route_b):
    """Submitting a foreign route fails form validation."""
    data = {
        "recipient": admin_user.pk,
        "related_route": ms_route_b.pk,  # From tenant_b
        "alert_type": "route_dispatched",
        "title": "Route Assigned Alert",
        "message": "Testing route isolation.",
    }
    form = MobileDealAlertForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "related_route" in form.errors


@pytest.mark.django_db
def test_mobilesales_alert_form_rejects_foreign_opportunity(tenant_a, tenant_b, admin_user):
    """Submitting a foreign opportunity fails form validation."""
    opp_b = _mobilesales_opportunity(tenant_b)
    data = {
        "recipient": admin_user.pk,
        "related_opportunity": opp_b.pk,
        "alert_type": "deal_stage_changed",
        "title": "Stage Change Alert",
        "message": "Testing opportunity isolation.",
    }
    form = MobileDealAlertForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "related_opportunity" in form.errors


@pytest.mark.django_db
def test_mobilesales_alert_form_rejects_foreign_quote(tenant_a, tenant_b, admin_user):
    """Submitting a foreign quote fails form validation."""
    quote_b = _mobilesales_quote(tenant_b)
    data = {
        "recipient": admin_user.pk,
        "related_quote": quote_b.pk,
        "alert_type": "quote_approval_required",
        "title": "Quote Approval Alert",
        "message": "Testing quote isolation.",
    }
    form = MobileDealAlertForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "related_quote" in form.errors


@pytest.mark.django_db
def test_mobilesales_alert_form_valid_submission(
    tenant_a,
    admin_user,
    ms_device_a,
    ms_route_a,
):
    """Valid alert data saves successfully and generates number."""
    opp_a = _mobilesales_opportunity(tenant_a)
    quote_a = _mobilesales_quote(tenant_a)

    data = {
        "recipient": admin_user.pk,
        "device": ms_device_a.pk,
        "alert_type": "quote_approval_required",
        "title": "Urgent Discount Sign-off Required",
        "message": "Deal discount at 20% requires supervisor review.",
        "urgency": "urgent",
        "related_opportunity": opp_a.pk,
        "related_quote": quote_a.pk,
        "related_route": ms_route_a.pk,
    }
    form = MobileDealAlertForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    alert = form.save(commit=False)
    alert.tenant = tenant_a
    alert.save()

    assert alert.pk is not None
    assert alert.number.startswith("MDA-")
    assert alert.recipient == admin_user
    assert alert.device == ms_device_a
    assert alert.urgency == "urgent"
    assert alert.related_quote == quote_a
    assert alert.is_read is False


@pytest.mark.django_db
def test_mobilesales_alert_form_missing_required_fields(tenant_a):
    """Missing recipient, title, or message fails form validation."""
    form = MobileDealAlertForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "recipient" in form.errors
    assert "title" in form.errors
    assert "message" in form.errors


@pytest.mark.django_db
def test_mobilesales_alert_filter_form_fields():
    """Verify MobileDealAlertFilterForm contains alert_type, urgency, is_read, recipient, q."""
    form = MobileDealAlertFilterForm()
    expected = {"alert_type", "urgency", "is_read", "recipient", "q"}
    assert set(form.fields.keys()) == expected


@pytest.mark.django_db
def test_mobilesales_alert_filter_form_empty(tenant_a):
    """Empty GET parameters validate cleanly on MobileDealAlertFilterForm."""
    filter_form = MobileDealAlertFilterForm(data={}, tenant=tenant_a)
    assert filter_form.is_valid(), filter_form.errors


@pytest.mark.django_db
def test_mobilesales_alert_filter_form_valid_filters(tenant_a, admin_user):
    """MobileDealAlertFilterForm correctly parses populated parameters."""
    data = {
        "q": "Discount",
        "alert_type": "quote_approval_required",
        "urgency": "urgent",
        "is_read": "0",
        "recipient": admin_user.pk,
    }
    filter_form = MobileDealAlertFilterForm(data=data, tenant=tenant_a)
    assert filter_form.is_valid(), filter_form.errors
    assert filter_form.cleaned_data["q"] == "Discount"
    assert filter_form.cleaned_data["alert_type"] == "quote_approval_required"
    assert filter_form.cleaned_data["urgency"] == "urgent"
    assert filter_form.cleaned_data["is_read"] == "0"
    assert filter_form.cleaned_data["recipient"] == admin_user


@pytest.mark.django_db
def test_mobilesales_alert_filter_form_is_read_choices(tenant_a):
    """Test is_read choice field accepts empty string, '0' (unread), and '1' (read)."""
    for choice in ["", "0", "1"]:
        filter_form = MobileDealAlertFilterForm(data={"is_read": choice}, tenant=tenant_a)
        assert filter_form.is_valid(), f"Failed for is_read='{choice}': {filter_form.errors}"
        assert filter_form.cleaned_data["is_read"] == choice

    # Invalid choice rejected
    invalid_form = MobileDealAlertFilterForm(data={"is_read": "invalid"}, tenant=tenant_a)
    assert not invalid_form.is_valid()
    assert "is_read" in invalid_form.errors


@pytest.mark.django_db
def test_mobilesales_alert_filter_form_recipient_tenant_scoping(tenant_a, tenant_b, admin_user, admin_b):
    """MobileDealAlertFilterForm recipient queryset is scoped to the tenant."""
    filter_a = MobileDealAlertFilterForm(tenant=tenant_a)
    assert admin_user in filter_a.fields["recipient"].queryset
    assert admin_b not in filter_a.fields["recipient"].queryset
