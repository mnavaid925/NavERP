"""0.19 License & Subscription Administration — FORMS lane.

Distinct from the pre-existing 0.1 lanes, which cover `SubscriptionForm`/`UsageRecordForm` for 0.1's
own models. This lane covers the four 0.19 forms and the two columns 0.19 added to the subscription
form.

The rule this lane exists to protect: **a `ValidationError` keyed on a field the form does not have
raises `ValueError` — which is a 500, not a form error.** Every guard test asserts the error key IS a
field the form actually declares.
"""
import pytest

from apps.tenants.forms import (
    EntitlementFeatureForm,
    LicenseAssignmentForm,
    PlanEntitlementForm,
    SubscriptionForm,
    UsageQuotaForm,
)
from apps.tenants.models import LicenseAssignment, UsageQuota

pytestmark = pytest.mark.django_db


def _licensing_fields(form_class):
    """The form's own field set — the set an error key must land inside."""
    return set(form_class.base_fields)


def _licensing_feature_payload(**overrides):
    """A complete, valid `EntitlementFeatureForm` payload.

    `status` is REQUIRED on this form (no model default reaches a bound form), so a payload that
    omits it is not testing the duplicate guard — it is testing a missing required field. This
    helper exists so every duplicate test below fails for the ONE reason it names.
    """
    payload = {
        "code": "sso", "name": "Single Sign-On", "description": "",
        "privilege_type": "boolean", "select_options": "", "status": "active",
        "is_add_on": False, "is_active": True, "notes": "",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------- base class: the TenantModelForm rule
class TestFormBaseClass:
    """[RULING] 9. `crud_create`/`crud_edit` call `form_class(..., tenant=request.tenant)`
    unconditionally, so a plain `ModelForm` raises `TypeError` at instantiation."""

    @pytest.mark.parametrize("form_class", [EntitlementFeatureForm, PlanEntitlementForm,
                                            UsageQuotaForm, LicenseAssignmentForm])
    def test_licensing_every_form_takes_a_tenant_kwarg(self, form_class):
        from apps.tenants.forms._common import TenantModelForm
        assert issubclass(form_class, TenantModelForm)
        form_class(tenant=None)  # the exact call the view makes

    @pytest.mark.parametrize("form_class", [EntitlementFeatureForm, PlanEntitlementForm,
                                            UsageQuotaForm, LicenseAssignmentForm])
    def test_licensing_tenant_is_absent_from_every_form(self, form_class):
        assert "tenant" not in _licensing_fields(form_class)


# --------------------------------------------------------------- the one-writer exclusions (L22)
class TestEvidenceStampsAreOffEveryForm:
    """The verbs are the SOLE writers. A form carrying these would let a member forge the very
    evidence the one-writer discipline exists to establish."""

    def test_licensing_breached_at_is_absent_from_the_quota_form(self):
        assert "breached_at" not in _licensing_fields(UsageQuotaForm)

    @pytest.mark.parametrize("field", ["status", "reclaimed_on", "reclaim_reason"])
    def test_licensing_the_seat_verb_fields_are_absent_from_the_seat_form(self, field):
        assert field not in _licensing_fields(LicenseAssignmentForm)

    @pytest.mark.parametrize("field", ["number", "created_at"])
    def test_licensing_system_fields_are_absent_from_the_feature_form(self, field):
        assert field not in _licensing_fields(EntitlementFeatureForm)

    def test_licensing_a_posted_breached_at_cannot_reach_the_instance(self, tenant_a, lic019_subscription_a):
        """The forgery the exclusion prevents, asserted on `cleaned_data` — what a view actually saves.
        A field that is not on the form never appears there."""
        form = UsageQuotaForm({
            "subscription": lic019_subscription_a.pk, "metric": "api_calls",
            "quota_limit": "999", "warn_at_pct": 80, "action_on_breach": "block", "period": "monthly",
            "breached_at": "2020-01-01T00:00",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert "breached_at" not in form.cleaned_data

    def test_licensing_a_posted_status_cannot_reach_the_seat_instance(self, tenant_a, lic019_user_a):
        form = LicenseAssignmentForm({
            "user": lic019_user_a.pk, "module_slug": "crm", "assignment_source": "direct",
            "status": "revoked", "reclaimed_on": "2020-01-01T00:00", "reclaim_reason": "forged",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        for field in ("status", "reclaimed_on", "reclaim_reason"):
            assert field not in form.cleaned_data


# --------------------------------------------------------------- the three duplicate guards
class TestDuplicateGuardsAreFieldErrorsNotFiveHundreds:
    """[RULING] 8. A repeated POST used to be an `IntegrityError` 500. Each must be a keyed error,
    on CREATE and on EDIT."""

    def test_licensing_a_duplicate_feature_code_is_a_keyed_error_on_create(self, tenant_a, lic019_feature_a):
        form = EntitlementFeatureForm(_licensing_feature_payload(code=lic019_feature_a.code),
                                      tenant=tenant_a)
        assert not form.is_valid()
        assert "code" in form.errors
        assert "code" in _licensing_fields(EntitlementFeatureForm)

    def test_licensing_editing_a_row_to_its_own_code_is_fine(self, lic019_feature_a):
        form = EntitlementFeatureForm(_licensing_feature_payload(code=lic019_feature_a.code,
                                                                 name="Renamed"),
                                      instance=lic019_feature_a, tenant=lic019_feature_a.tenant)
        assert form.is_valid(), form.errors

    def test_licensing_a_duplicate_feature_code_is_refused_on_edit_too(self, tenant_a, lic019_feature_a):
        from apps.tenants.models import EntitlementFeature
        other = EntitlementFeature.objects.create(tenant=tenant_a, code="other", name="Other",
                                                  privilege_type="boolean")
        form = EntitlementFeatureForm(_licensing_feature_payload(code=lic019_feature_a.code),
                                      instance=other, tenant=tenant_a)
        assert not form.is_valid(), "an edit that collides with another row must be refused"
        assert "code" in form.errors

    def test_licensing_a_duplicate_quota_is_a_keyed_error(self, lic019_quota_a):
        form = UsageQuotaForm({"subscription": lic019_quota_a.subscription_id,
                               "metric": lic019_quota_a.metric, "period": lic019_quota_a.period,
                               "quota_limit": "1", "warn_at_pct": 80, "action_on_breach": "alert"},
                              tenant=lic019_quota_a.tenant)
        assert not form.is_valid()
        assert "period" in form.errors
        assert "period" in _licensing_fields(UsageQuotaForm)

    def test_licensing_a_duplicate_quota_on_edit_is_a_keyed_error(self, tenant_a, lic019_subscription_a):
        """The EDIT path needs a row ALREADY in the slot the edit moves `other` into — creating `other`
        on a different metric and then editing it there is not a collision at all."""
        UsageQuota.objects.create(tenant=tenant_a, subscription=lic019_subscription_a,
                                  metric="api_calls", period="monthly", quota_limit="10")
        other = UsageQuota.objects.create(tenant=tenant_a, subscription=lic019_subscription_a,
                                          metric="storage_mb", period="monthly", quota_limit="10")
        form = UsageQuotaForm({"subscription": lic019_subscription_a.pk, "metric": "api_calls",
                               "period": "monthly", "quota_limit": "5", "warn_at_pct": 80,
                               "action_on_breach": "alert"}, instance=other, tenant=tenant_a)
        assert not form.is_valid()
        assert "period" in form.errors

    def test_licensing_a_duplicate_seat_is_a_keyed_error(self, lic019_seat_a):
        form = LicenseAssignmentForm({"user": lic019_seat_a.user_id,
                                      "module_slug": lic019_seat_a.module_slug,
                                      "assignment_source": "direct"},
                                     tenant=lic019_seat_a.tenant)
        assert not form.is_valid()
        assert "module_slug" in form.errors
        assert "module_slug" in _licensing_fields(LicenseAssignmentForm)

    def test_licensing_an_uppercase_duplicate_seat_is_a_keyed_error_not_an_integrity_error(self,
                                                                                          tenant_a,
                                                                                          lic019_user_a,
                                                                                          lic019_subscription_a):
        """`module_slug` is normalised in `clean()`, so `ACCOUNTING` collides with an EXISTING
        `accounting` seat HERE rather than at the database — which is where it would be a 500.
        The seeded seat is the tenant-wide one (`module_slug == ""`), which is NOT a collision."""
        LicenseAssignment.objects.create(tenant=tenant_a, user=lic019_user_a, module_slug="accounting",
                                         subscription=lic019_subscription_a)
        form = LicenseAssignmentForm({"user": lic019_user_a.pk, "module_slug": "ACCOUNTING",
                                      "assignment_source": "direct"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "module_slug" in form.errors

    def test_licensing_a_duplicate_plan_grant_is_a_keyed_error(self, tenant_a, lic019_plan_grant_a,
                                                               lic019_feature_a):
        form = PlanEntitlementForm({"plan": lic019_plan_grant_a.plan, "feature": lic019_feature_a.pk,
                                    "privilege_value": "true"}, tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors
        for key in form.errors:
            assert key in _licensing_fields(PlanEntitlementForm), \
                f"error keyed on {key!r}, which the form does not declare — that is a 500, not an error"


# --------------------------------------------------------------- the I10 tri-state
class TestAutoRenewIsThreeState:
    """I10. `auto_renew` shipped as `BooleanField(default=True)`, which stamped every pre-existing
    subscription with an intent nobody expressed. It is now `null=True`, and the widget must carry
    the third state through a round trip — a checkbox would silently turn "nobody said" into "no"."""

    @pytest.mark.parametrize("posted,expected", [("true", True), ("false", False), ("unknown", None)])
    def test_licensing_each_state_round_trips(self, tenant_a, posted, expected):
        form = SubscriptionForm({"plan": "pro", "status": "active", "billing_cycle": "monthly",
                                 "amount": "1", "seats": "1", "auto_renew": posted}, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["auto_renew"] is expected

    def test_licensing_the_widget_is_not_a_checkbox(self):
        from django import forms as django_forms
        widget = SubscriptionForm.base_fields["auto_renew"].widget
        assert not isinstance(widget, django_forms.CheckboxInput), \
            "a two-state widget cannot carry 'nobody has said'"

    def test_licensing_an_unanswered_intent_survives_a_save(self, tenant_a):
        from apps.tenants.models import Subscription
        subscription = Subscription.objects.create(tenant=tenant_a, plan="pro", status="active")
        assert subscription.auto_renew is None, "an unanswered intent must not be coerced"
        subscription.refresh_from_db()
        assert subscription.auto_renew is None

    def test_licensing_the_renewal_columns_are_editable_on_the_form(self):
        """Negotiated commercial terms an operator sets, NOT system stamps — which is exactly why
        they differ from `UsageQuota.breached_at`."""
        assert "auto_renew" in _licensing_fields(SubscriptionForm)
        assert "grace_ends_on" in _licensing_fields(SubscriptionForm)

    def test_licensing_the_renewal_columns_stay_editable_on_the_model(self):
        from apps.tenants.models import Subscription
        assert Subscription._meta.get_field("auto_renew").editable is True
        assert Subscription._meta.get_field("grace_ends_on").editable is True
        assert Subscription._meta.get_field("auto_renew").null is True, \
            "nullable is the whole point: it is what lets 'nobody has said' be a stored state"


# --------------------------------------------------------------- tenant-scoped FK pickers
class TestForeignKeyPickersAreTenantScoped:
    """A crafted POST naming another workspace's pk must be refused. The admin is NOT tenant-scoped,
    so the three models' own `clean()` guards are the second line of defence (I15)."""

    def test_licensing_a_cross_tenant_subscription_is_refused_by_the_form(self, tenant_a, lic019_subscription_b):
        form = UsageQuotaForm({"subscription": lic019_subscription_b.pk, "metric": "api_calls",
                               "period": "monthly", "quota_limit": "1", "warn_at_pct": 80,
                               "action_on_breach": "alert"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "subscription" in form.errors

    def test_licensing_a_cross_tenant_feature_is_refused_by_the_form(self, tenant_a, tenant_b):
        from apps.tenants.models import EntitlementFeature
        foreign = EntitlementFeature.objects.create(tenant=tenant_b, code="sso", name="SSO",
                                                    privilege_type="boolean")
        form = PlanEntitlementForm({"plan": "pro", "feature": foreign.pk,
                                    "privilege_value": "true"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "feature" in form.errors

    def test_licensing_a_cross_tenant_user_is_refused_by_the_form(self, tenant_a, lic019_user_b):
        form = LicenseAssignmentForm({"user": lic019_user_b.pk, "module_slug": "crm",
                                      "assignment_source": "direct"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "user" in form.errors

    def test_licensing_the_picker_offers_no_other_workspaces_rows(self, tenant_a, lic019_user_b,
                                                                  lic019_subscription_b):
        """Asserted on the form's own queryset, which is what the rendered `<select>` is built from."""
        seat_form = LicenseAssignmentForm(tenant=tenant_a)
        offered = {u.pk for u in seat_form.fields["user"].queryset}
        assert lic019_user_b.pk not in offered
        quota_form = UsageQuotaForm(tenant=tenant_a)
        assert lic019_subscription_b.pk not in {s.pk for s in quota_form.fields["subscription"].queryset}
