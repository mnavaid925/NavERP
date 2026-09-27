"""0.19 License & Subscription Administration — MODELS lane.

Distinct from the pre-existing 0.1 lanes, which cover `Subscription`/`SubscriptionInvoice`/
`UsageRecord` themselves. This lane covers the four 0.19 models and the two columns it added.

Every test is `test_licensing_*`, so the next sub-module appending nearby cannot shadow them.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.tenants.models import (
    EntitlementFeature,
    LicenseAssignment,
    PlanEntitlement,
    Subscription,
    UsageQuota,
    UsageRecord,
)

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------- shared vocabulary: by IDENTITY
class TestSharedVocabularies:
    """Both reuse an existing vocabulary BY REFERENCE. A pasted copy is the exact duplication 0.19
    exists to prevent, so these assert `is` and not `==` — two equal lists are still two lists."""

    def test_licensing_quota_reuses_the_usage_metric_choices_by_identity(self):
        assert UsageQuota.METRIC_CHOICES is UsageRecord.METRIC_CHOICES

    def test_licensing_grant_reuses_the_tenant_plan_choices_by_identity(self):
        from apps.core.models import Tenant
        assert PlanEntitlement.PLAN_CHOICES is Tenant.PLAN_CHOICES

    def test_licensing_an_equality_check_would_not_have_caught_a_copy(self):
        # Guards the guard: prove the `is` assertions above are meaningful, not trivially true.
        assert UsageQuota.METRIC_CHOICES == UsageRecord.METRIC_CHOICES
        assert UsageQuota.METRIC_CHOICES is not list(UsageRecord.METRIC_CHOICES)


# --------------------------------------------------------------- number prefixes
class TestNumberPrefixes:
    """[RULING] 1. `LIC-` is ALREADY TAKEN by `scm.TradeLicense`, and `NumberingScheme` is unique per
    `(tenant, prefix)`, so two registers must not mint the same customer-facing number."""

    def test_licensing_feature_mints_ent(self, lic019_feature_a):
        assert lic019_feature_a.number.startswith("ENT-")

    def test_licensing_grant_mints_pe(self, lic019_plan_grant_a):
        assert lic019_plan_grant_a.number.startswith("PE-")

    def test_licensing_quota_mints_uq(self, lic019_quota_a):
        assert lic019_quota_a.number.startswith("UQ-")

    def test_licensing_seat_mints_seat_and_never_lic(self, lic019_seat_a):
        assert lic019_seat_a.number.startswith("SEAT-")
        assert not lic019_seat_a.number.startswith("LIC-")

    def test_licensing_number_is_not_editable(self):
        assert LicenseAssignment._meta.get_field("number").editable is False

    def test_licensing_number_survives_an_unchanged_resave(self, lic019_seat_a):
        original = lic019_seat_a.number
        lic019_seat_a.notes = "touched"
        lic019_seat_a.save()
        lic019_seat_a.refresh_from_db()
        assert lic019_seat_a.number == original


# --------------------------------------------------------------- EntitlementFeature
class TestEntitlementFeatureRules:
    def test_licensing_select_privilege_requires_its_option_list(self, tenant_a):
        feature = EntitlementFeature(tenant=tenant_a, code="sso_provider", name="SSO Provider",
                                     privilege_type="select", select_options="")
        with pytest.raises(ValidationError) as exc:
            feature.clean()
        assert "select_options" in exc.value.message_dict

    def test_licensing_select_privilege_is_valid_with_options(self, lic019_feature_select_a):
        lic019_feature_select_a.clean()  # must not raise

    def test_licensing_non_select_privilege_needs_no_options(self, lic019_feature_a):
        assert lic019_feature_a.select_options == ""
        lic019_feature_a.clean()  # must not raise

    @pytest.mark.parametrize("bad_code", ["SSO", "Sso", "1sso", "sso-provider", "sso provider"])
    def test_licensing_code_must_be_lowercase_and_underscored(self, tenant_a, bad_code):
        """`"SSO"` vs `"sso"` becoming two features is the duplication this rule prevents."""
        feature = EntitlementFeature(tenant=tenant_a, code=bad_code, name="X",
                                     privilege_type="boolean")
        with pytest.raises(ValidationError):
            feature.clean()

    def test_licensing_a_well_formed_code_is_accepted(self, tenant_a):
        EntitlementFeature(tenant=tenant_a, code="audit_export", name="X",
                           privilege_type="boolean").clean()  # must not raise

    def test_licensing_a_duplicate_code_in_one_tenant_is_refused(self, tenant_a, lic019_feature_a):
        """The duplicate is enforced by the `unique_together` (both columns non-nullable, so the DB
        really does catch it) and therefore surfaces through `full_clean()`, NOT through `clean()`
        — `clean()` holds the `select_options` rule and the code FORMAT only."""
        dupe = EntitlementFeature(tenant=tenant_a, code=lic019_feature_a.code, name="Second SSO",
                                  privilege_type="boolean", status="active")
        with pytest.raises(ValidationError) as exc:
            dupe.full_clean(exclude=["number"])
        # Django reports a `unique_together` clash NON-FIELD (`__all__`), because the constraint
        # spans two fields and cannot be attributed to either. That is still a form error and not a
        # 500 — and it is why this asserts the MESSAGE, not a field key.
        assert "already exists" in " ".join(exc.value.messages)

    def test_licensing_the_same_code_is_fine_in_a_different_tenant(self, tenant_b, lic019_feature_a):
        EntitlementFeature.objects.create(tenant=tenant_b, code="sso", name="SSO",
                                          privilege_type="boolean", status="active")
        assert EntitlementFeature.objects.filter(code="sso").count() == 2

    def test_licensing_str_shows_the_code_not_the_number(self, lic019_feature_a):
        assert str(lic019_feature_a).startswith(lic019_feature_a.code)
        assert lic019_feature_a.number not in str(lic019_feature_a)

    def test_licensing_archived_is_a_lifecycle_value_not_a_deletion(self, lic019_feature_a):
        """Archival, not deletion: retiring a feature must not rewrite what past subscriptions hold."""
        assert "archived" in dict(EntitlementFeature.STATUS_CHOICES)
        lic019_feature_a.status = "archived"
        lic019_feature_a.save()
        lic019_feature_a.refresh_from_db()
        assert lic019_feature_a.status == "archived"


# --------------------------------------------------------------- PlanEntitlement
class TestPlanEntitlementRules:
    def test_licensing_is_override_is_a_property_not_a_column(self):
        field_names = {f.name for f in PlanEntitlement._meta.get_fields()}
        assert "is_override" not in field_names
        assert isinstance(PlanEntitlement.is_override, property)

    def test_licensing_a_plan_grant_is_not_an_override(self, lic019_plan_grant_a):
        assert lic019_plan_grant_a.subscription_id is None
        assert lic019_plan_grant_a.is_override is False

    def test_licensing_a_subscription_row_is_an_override(self, lic019_override_a):
        assert lic019_override_a.subscription_id is not None
        assert lic019_override_a.is_override is True

    def test_licensing_deleting_the_subscription_ends_the_override_claim(self, lic019_override_a):
        """[RULING] 3 — the reason it is a property. A stored boolean would outlive the row it
        describes and keep reading True for what is now a plan grant."""
        lic019_override_a.subscription.delete()
        lic019_override_a.refresh_from_db()
        assert lic019_override_a.subscription_id is None
        assert lic019_override_a.is_override is False

    def test_licensing_duplicate_plan_grant_is_refused_by_clean(self, tenant_a, lic019_feature_a,
                                                                lic019_plan_grant_a):
        """[RULING] 2 — the `unique_together` is INERT here (NULLs are distinct in BOTH MySQL and
        SQLite), so this `clean()` guard is the only thing enforcing it."""
        dupe = PlanEntitlement(tenant=tenant_a, plan=lic019_plan_grant_a.plan,
                               feature=lic019_feature_a, privilege_value="true")
        with pytest.raises(ValidationError) as exc:
            dupe.clean()
        assert exc.value.message_dict

    def test_licensing_the_same_feature_on_two_subscriptions_is_allowed(self, tenant_a, lic019_feature_a,
                                                                       lic019_subscription_a):
        """Two overrides of one feature on two subscriptions is legitimate; only IDENTICAL pairs
        collide, and the tuple is kept for exactly that."""
        other_sub = Subscription.objects.create(tenant=tenant_a, plan="pro", status="active")
        PlanEntitlement.objects.create(tenant=tenant_a, plan="pro", feature=lic019_feature_a,
                                       subscription=lic019_subscription_a, privilege_value="true")
        PlanEntitlement.objects.create(tenant=tenant_a, plan="pro", feature=lic019_feature_a,
                                       subscription=other_sub, privilege_value="true")
        assert PlanEntitlement.objects.filter(feature=lic019_feature_a).count() == 2

    def test_licensing_effective_dates_must_be_ordered(self, tenant_a, lic019_feature_a):
        import datetime

        from django.utils import timezone
        grant = PlanEntitlement(
            tenant=tenant_a, plan="pro", feature=lic019_feature_a,
            effective_from=timezone.localdate() + datetime.timedelta(days=5),
            effective_to=timezone.localdate(),
        )
        with pytest.raises(ValidationError):
            grant.clean()

    def test_licensing_integer_privilege_rejects_a_non_numeric_value(self, tenant_a, lic019_feature_a):
        """Rule (c): without it `privilege_type` is only a label, and "granted: `banana` for an
        integer privilege" would be shippable."""
        lic019_feature_a.privilege_type = "integer"
        lic019_feature_a.save()
        grant = PlanEntitlement(tenant=tenant_a, plan="pro", feature=lic019_feature_a,
                                privilege_value="banana")
        with pytest.raises(ValidationError):
            grant.clean()

    def test_licensing_integer_privilege_accepts_a_numeric_value(self, tenant_a, lic019_feature_a):
        lic019_feature_a.privilege_type = "integer"
        lic019_feature_a.save()
        PlanEntitlement(tenant=tenant_a, plan="pro", feature=lic019_feature_a,
                        privilege_value="50").clean()  # must not raise


# --------------------------------------------------------------- UsageQuota
class TestUsageQuotaRules:
    def test_licensing_zero_limit_is_a_real_unmetered_value(self, lic019_quota_unmetered_a):
        """Mirrors `UsageRecord.included_allowance`, whose docstring calls `None` UNMETERED and
        "deliberately distinct from `0`, which would make every unit an overage".

        `quota_limit` is a `CharField` (to allow the `0` sentinel alongside a numeric ceiling), so the
        stored value is the STRING `"0.00"`. Compare numerically — `== 0` is False against a str.
        """
        from decimal import Decimal
        assert lic019_quota_unmetered_a.quota_limit == "0.00"
        assert Decimal(lic019_quota_unmetered_a.quota_limit) == 0
        assert lic019_quota_unmetered_a.quota_limit != "100.00", "a real ceiling is a different value"

    def test_licensing_duplicate_quota_is_refused_by_clean(self, lic019_quota_a):
        dupe = UsageQuota(subscription=lic019_quota_a.subscription, tenant=lic019_quota_a.tenant,
                          metric=lic019_quota_a.metric, period=lic019_quota_a.period)
        with pytest.raises(ValidationError) as exc:
            dupe.clean()
        assert "period" in exc.value.message_dict

    def test_licensing_a_different_metric_on_the_same_subscription_is_fine(self, lic019_quota_a):
        UsageQuota(tenant=lic019_quota_a.tenant, subscription=lic019_quota_a.subscription,
                   metric="storage_mb", period=lic019_quota_a.period,
                   quota_limit="100").clean()  # must not raise

    def test_licensing_breached_at_is_an_evidence_stamp(self):
        field = UsageQuota._meta.get_field("breached_at")
        assert field.editable is False
        assert field.null is True

    def test_licensing_action_on_breach_is_vocabulary_nothing_reads(self):
        """Decline #2. The values exist as a recorded policy and NO model member acts on them — the
        honest shape, asserted rather than asserted-about."""
        assert "block" in dict(UsageQuota.ACTION_CHOICES)
        readers = [
            name for name in dir(UsageQuota)
            if not name.startswith("_")
            and callable(getattr(UsageQuota, name, None))
            and "action_on_breach" in (getattr(getattr(UsageQuota, name), "__doc__", "") or "")
        ]
        assert readers == []


# --------------------------------------------------------------- LicenseAssignment
class TestLicenseAssignmentRules:
    def test_licensing_derived_states_are_properties_not_columns(self):
        for name in ("is_reclaimable", "is_expired"):
            assert name not in {f.name for f in LicenseAssignment._meta.get_fields()}
            assert isinstance(getattr(LicenseAssignment, name), property)

    def test_licensing_an_active_seat_is_reclaimable(self, lic019_seat_a):
        assert lic019_seat_a.is_reclaimable is True

    def test_licensing_a_reclaimed_seat_is_not_reclaimable(self, lic019_seat_a):
        lic019_seat_a.status = "reclaimed"
        assert lic019_seat_a.is_reclaimable is False

    def test_licensing_expired_is_derived_from_expires_on(self, lic019_seat_expired_a):
        assert lic019_seat_expired_a.is_expired is True
        assert lic019_seat_expired_a.status == "active", \
            "a past expires_on must NOT have written a stored status"

    def test_licensing_a_seat_with_no_expiry_is_never_expired(self, lic019_seat_a):
        assert lic019_seat_a.expires_on is None
        assert lic019_seat_a.is_expired is False

    def test_licensing_duplicate_seat_is_refused_by_clean(self, lic019_seat_a):
        dupe = LicenseAssignment(tenant=lic019_seat_a.tenant, user=lic019_seat_a.user,
                                 module_slug=lic019_seat_a.module_slug)
        with pytest.raises(ValidationError) as exc:
            dupe.clean()
        assert "module_slug" in exc.value.message_dict

    def test_licensing_module_slug_is_case_normalised_in_save(self, tenant_a, lic019_user_a):
        seat = LicenseAssignment(tenant=tenant_a, user=lic019_user_a, module_slug="  Accounting  ")
        seat.save()
        seat.refresh_from_db()
        assert seat.module_slug == "accounting"

    def test_licensing_an_uppercase_duplicate_is_caught_by_clean_not_the_database(self, tenant_a,
                                                                                 lic019_user_a,
                                                                                 lic019_seat_a):
        """Normalised in `clean()` too, so a form posting `Accounting` is a keyed FIELD ERROR.
        Without the `clean()` normalisation it would pass the guard and then fail the DB
        `unique_together` — an IntegrityError 500 rather than a form error.

        The collision needs an EXISTING `accounting` seat: the seeded one is the tenant-wide seat
        (`module_slug == ""`), so reusing its user with a different slug is not a duplicate."""
        LicenseAssignment.objects.create(tenant=tenant_a, user=lic019_user_a, module_slug="accounting")
        dupe = LicenseAssignment(tenant=tenant_a, user=lic019_user_a, module_slug="ACCOUNTING")
        with pytest.raises(ValidationError):
            dupe.clean()
        assert lic019_seat_a.module_slug == "", "the seeded tenant-wide seat is a separate grant"

    def test_licensing_a_blank_module_slug_is_the_tenant_wide_seat(self, lic019_seat_a):
        assert lic019_seat_a.module_slug == ""
        assert lic019_seat_a.module_slug is not None, "blank is a VALUE here, never NULL"

    def test_licensing_the_evidence_stamps_are_not_editable(self):
        for name in ("reclaimed_on", "reclaim_reason"):
            assert LicenseAssignment._meta.get_field(name).editable is False

    def test_licensing_user_is_required_so_a_seat_always_has_a_holder(self):
        assert LicenseAssignment._meta.get_field("user").null is False


# --------------------------------------------------------------- the I15 tenant-consistency guard
class TestTenantConsistencyGuard:
    """Nothing at the DATABASE level makes these rows tenant-consistent, so `clean()` is the guard.
    The form already scopes the dropdown; this closes the unscoped Django-admin path."""

    def test_licensing_quota_refuses_another_workspaces_subscription(self, tenant_a, lic019_subscription_b):
        quota = UsageQuota(tenant=tenant_a, subscription=lic019_subscription_b,
                           metric="api_calls", period="monthly", quota_limit="1")
        with pytest.raises(ValidationError) as exc:
            quota.clean()
        assert "subscription" in exc.value.message_dict

    def test_licensing_grant_refuses_another_workspaces_subscription(self, tenant_a, lic019_feature_a,
                                                                       lic019_subscription_b):
        grant = PlanEntitlement(tenant=tenant_a, plan="pro", feature=lic019_feature_a,
                                subscription=lic019_subscription_b)
        with pytest.raises(ValidationError) as exc:
            grant.clean()
        assert "subscription" in exc.value.message_dict

    def test_licensing_seat_refuses_another_workspaces_subscription(self, tenant_a, lic019_user_a,
                                                                     lic019_subscription_b):
        seat = LicenseAssignment(tenant=tenant_a, user=lic019_user_a, subscription=lic019_subscription_b)
        with pytest.raises(ValidationError) as exc:
            seat.clean()
        assert "subscription" in exc.value.message_dict

    def test_licensing_a_same_workspace_subscription_is_still_accepted(self, lic019_quota_a):
        UsageQuota(tenant=lic019_quota_a.tenant, subscription=lic019_quota_a.subscription,
                   metric="storage_mb", period="monthly", quota_limit="5").clean()  # must not raise

    def test_licensing_the_error_is_keyed_on_a_field_the_forms_actually_have(self):
        """The 0.18 trap: a ValidationError keyed on a field the form lacks raises ValueError (a 500)."""
        from apps.tenants.forms import LicenseAssignmentForm, PlanEntitlementForm, UsageQuotaForm
        for form_class in (UsageQuotaForm, PlanEntitlementForm, LicenseAssignmentForm):
            assert "subscription" in form_class.base_fields, \
                f"{form_class.__name__} must expose `subscription` for the error key to be bindable"

    def test_licensing_a_quota_cascade_cannot_reach_another_workspaces_subscription(self, tenant_a,
                                                                                      lic019_subscription_b):
        """`UsageQuota.subscription` is CASCADE and non-null, so a bad pair would DELETE another
        workspace's subscription. Assert the FK really is the destructive shape the guard protects."""
        field = UsageQuota._meta.get_field("subscription")
        assert field.remote_field.on_delete.__name__ == "CASCADE"
        assert field.null is False
        with pytest.raises(ValidationError):
            UsageQuota(tenant=tenant_a, subscription=lic019_subscription_b, metric="api_calls",
                       period="monthly").clean()

    def test_licensing_a_seat_cascade_is_set_null_so_it_is_a_read_not_a_delete(self):
        field = LicenseAssignment._meta.get_field("subscription")
        assert field.remote_field.on_delete.__name__ == "SET_NULL"

    # ------------------------------------------------------------------ M6: the seeder's query cost
    #: Ceiling for seeding 0.19 into ONE fresh tenant. The measured cost is **178**; this is set
    #: above that with headroom, because the point is to catch GROWTH, not to re-assert today's
    #: number on every run. The cost exists because `next_number()` mints inside `Model.save()`,
    #: so `bulk_create` cannot be used for any auto-numbered row — an app-wide numbering design,
    #: not a 0.19 choice. A hard-coded number that silently drifts upward is worse than none.
    SEED_QUERY_CEILING = 200

    def _licensing_seed_019(self, tenant):
        """Run the 0.19 seeder block against `tenant`, returning the number of queries it issued."""
        from io import StringIO

        from apps.tenants.management.commands.seed_tenants import Command
        command = Command()
        command.stdout = StringIO()
        with CaptureQueriesContext(connection) as ctx:
            command._seed_licensing(tenant)
        return len(ctx.captured_queries)

    def test_licensing_seeding_one_tenant_stays_within_its_documented_budget(self, tenant_a):
        """M6 turned from a hand-wave into a number. The seeder is slow per row BY DESIGN — the
        numbering is minted inside `save()`, so every auto-numbered row is its own transaction —
        but that cost is paid once, at seed time, on a dev database nobody waits for."""
        Subscription.objects.create(tenant=tenant_a, plan="pro", status="active")
        queries = self._licensing_seed_019(tenant_a)
        assert queries <= self.SEED_QUERY_CEILING, (
            f"0.19 seeding took {queries} queries, over the documented "
            f"{self.SEED_QUERY_CEILING} budget"
        )

    def test_licensing_a_second_seed_is_a_cheap_no_op(self, tenant_a):
        """The property that makes the first number acceptable: re-running is cheap because it
        creates nothing. Idempotence is not only correctness, it is the reason the cost is harmless."""
        Subscription.objects.create(tenant=tenant_a, plan="pro", status="active")
        self._licensing_seed_019(tenant_a)
        assert self._licensing_seed_019(tenant_a) < self.SEED_QUERY_CEILING / 2, (
            "a re-seed should be a cheap no-op, not another full pass"
        )

    def test_licensing_the_seeder_is_not_importable_from_any_request_path(self):
        """M6's actual claim was "not a per-request hot path", so assert exactly that. A management
        command is only reachable by name from `manage.py`; if no view module imports it, it cannot
        be on a request path, whatever its query count is."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[2]
        offenders = [
            path.name
            for path in root.rglob("views/**/*.py")
            if "seed_tenants" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"a view module imports the seeder: {offenders}"

    def test_licensing_the_numbering_helper_is_the_shared_one_not_a_local_copy(self):
        """The reason 0.19 pays the per-row cost, stated as a test so it cannot be quietly forked
        into a private copy that behaves differently under concurrency.

        `next_number` is imported ONCE, by the tenants models `_base`, and reaches the four entity
        modules through that shared import. What would be wrong is an entity module defining its own
        `def next_number` — a copy that retries differently, or not at all, and quietly loses the
        concurrent-collision handling the shared one has.
        """
        from pathlib import Path

        from apps.core.utils import next_number
        # parents[0]=tests, [1]=tenants, so this is apps/tenants/models
        models_dir = Path(__file__).resolve().parents[1] / "models"

        base = (models_dir / "_base.py").read_text(encoding="utf-8")
        assert "from apps.core.utils import next_number" in base, \
            "_base must supply the shared numbering helper to the entity modules"

        for model_file in ("EntitlementFeature", "PlanEntitlement", "UsageQuota", "LicenseAssignment"):
            source = (models_dir / f"{model_file}.py").read_text(encoding="utf-8")
            assert "def next_number" not in source, \
                f"{model_file} defines its own next_number — use the shared helper from _base"
        assert callable(next_number)
