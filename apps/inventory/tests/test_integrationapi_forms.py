"""Inventory 5.19 - form contract (Third-Party Integrations & API).

Three editable entities: IntegrationChannel, ChannelListingMap, ApiClient. Field sets frozen,
tenant-unique names validated at the form boundary, FK querysets narrowed to the workspace and
re-checked in clean(), credential/lifecycle plumbing never a form field. There is deliberately
NO StockSyncRunForm - sync runs are created only through StockSyncRun.record() (append-only
register), asserted here as a design invariant.
"""
import pytest

from apps.inventory.forms import (
    ApiClientForm,
    ChannelListingMapForm,
    IntegrationChannelForm,
)
from apps.inventory.models import ApiClient, ChannelListingMap, IntegrationChannel

pytestmark = pytest.mark.django_db

_INTEGRATIONAPI_CHANNEL_FIELDS = [
    "name",
    "kind",
    "platform",
    "direction",
    "auth_method",
    "base_url",
    "external_account_ref",
    "environment",
    "status",
    "trigger_mode",
    "schedule_note",
    "rate_limit_note",
    "default_location",
    "is_active",
    "notes",
]

_INTEGRATIONAPI_LISTING_FIELDS = [
    "channel",
    "item",
    "location",
    "external_product_id",
    "external_variant_id",
    "external_sku",
    "price_override",
    "sync_enabled",
    "notes",
]

_INTEGRATIONAPI_CLIENT_FIELDS = [
    "name",
    "protocol",
    "scopes",
    "description",
    "allowed_ips",
    "rate_limit_note",
]

# Credential + lifecycle plumbing that must NEVER be typeable through any 5.19 form. The
# channel's own ``status`` is excluded from this union DELIBERATELY - it is a human-maintained
# health marker ON the channel form by design; ApiClient.status moves only via revoke.
_INTEGRATIONAPI_SENSITIVE_FIELDS = [
    "api_key_prefix",
    "api_key_hash",
    "api_token_prefix",
    "api_token_hash",
    "revoked_at",
    "last_used_at",
    "last_pushed_qty",
    "last_pushed_at",
]


def _integrationapi_channel_data(**overrides):
    data = {
        "name": "Shopify Bridge",
        "kind": "ecommerce",
        "platform": "shopify",
        "direction": "bidirectional",
        "auth_method": "api_key",
        "base_url": "",
        "external_account_ref": "",
        "environment": "sandbox",
        "status": "disconnected",
        "trigger_mode": "manual",
        "schedule_note": "",
        "rate_limit_note": "",
        "default_location": "",
        "is_active": "on",
        "notes": "",
    }
    data.update(overrides)
    return data


def _integrationapi_listing_data(**overrides):
    data = {
        "channel": "",
        "item": "",
        "location": "",
        "external_product_id": "",
        "external_variant_id": "",
        "external_sku": "",
        "price_override": "",
        "sync_enabled": "on",
        "notes": "",
    }
    data.update(overrides)
    return data


def _integrationapi_client_data(**overrides):
    data = {
        "name": "Partner Portal Key",
        "protocol": "rest",
        "scopes": "",
        "description": "",
        "allowed_ips": "",
        "rate_limit_note": "",
    }
    data.update(overrides)
    return data


def _integrationapi_make_channel(tenant, name):
    """Direct ORM row (number auto-assigned on save) - foreign targets and dup seeds."""
    return IntegrationChannel.objects.create(tenant=tenant, name=name)


class TestIntegrationApiFieldContracts:
    def test_integrationapi_channel_meta_fields_match_contract(self):
        assert list(IntegrationChannelForm.Meta.fields) == _INTEGRATIONAPI_CHANNEL_FIELDS
        assert "default_location" in IntegrationChannelForm.Meta.fields
        assert "is_active" in IntegrationChannelForm.Meta.fields

    def test_integrationapi_listing_map_meta_fields_match_contract(self):
        assert list(ChannelListingMapForm.Meta.fields) == _INTEGRATIONAPI_LISTING_FIELDS

    def test_integrationapi_api_client_meta_fields_match_contract(self):
        assert list(ApiClientForm.Meta.fields) == _INTEGRATIONAPI_CLIENT_FIELDS

    def test_integrationapi_sensitive_plumbing_excluded_from_all_forms(self):
        for form_cls in (IntegrationChannelForm, ChannelListingMapForm, ApiClientForm):
            for name in _INTEGRATIONAPI_SENSITIVE_FIELDS:
                assert name not in form_cls.Meta.fields, (form_cls.__name__, name)
            assert "tenant" not in form_cls.Meta.fields

    def test_integrationapi_status_split_channel_on_apiclient_off(self):
        """Channel status is a deliberate human marker; ApiClient status moves ONLY via the
        revoke verb - pin both sides of that split."""
        assert "status" in IntegrationChannelForm.Meta.fields
        assert "status" not in ApiClientForm.Meta.fields
        assert "revoked_at" not in ApiClientForm.Meta.fields

    def test_integrationapi_no_stock_sync_run_form_is_design_invariant(self):
        with pytest.raises(ImportError):
            from apps.inventory.forms import StockSyncRunForm  # noqa: F401


class TestIntegrationApiValidCreates:
    def test_integrationapi_channel_form_minimal_create_persists_with_tenant(self, tenant_a):
        form = IntegrationChannelForm(_integrationapi_channel_data(), tenant=tenant_a)
        assert form.is_valid(), form.errors
        channel = form.save()
        assert channel.tenant_id == tenant_a.pk
        assert IntegrationChannel.objects.filter(pk=channel.pk, tenant=tenant_a).exists()
        assert channel.number.startswith("INT-")

    def test_integrationapi_listing_map_form_minimal_create_persists_with_tenant(
            self, tenant_a, item_a, location_a):
        own = _integrationapi_make_channel(tenant_a, "Acme Link")
        form = ChannelListingMapForm(
            _integrationapi_listing_data(channel=own.pk, item=item_a.pk,
                                         location=location_a.pk),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        listing = form.save()
        assert listing.tenant_id == tenant_a.pk
        assert ChannelListingMap.objects.filter(pk=listing.pk, tenant=tenant_a).exists()
        assert listing.channel_id == own.pk

    def test_integrationapi_api_client_form_minimal_create_persists_with_tenant(self, tenant_a):
        form = ApiClientForm(_integrationapi_client_data(), tenant=tenant_a)
        assert form.is_valid(), form.errors
        client = form.save()
        assert client.tenant_id == tenant_a.pk
        assert ApiClient.objects.filter(pk=client.pk, tenant=tenant_a).exists()
        assert client.number.startswith("API-")
        assert client.status == "active"


class TestIntegrationApiTenantGuards:
    def test_integrationapi_channel_foreign_default_location_rejected_not_saved(
            self, tenant_a, location_b):
        form = IntegrationChannelForm(
            _integrationapi_channel_data(default_location=location_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert "default_location" in form.errors
        assert IntegrationChannel.objects.count() == 0  # no cross-tenant save

    @pytest.mark.parametrize("field_name", ["channel", "item", "location"])
    def test_integrationapi_listing_map_foreign_fk_rejected_not_saved(
            self, tenant_a, tenant_b, item_a, location_a, item_b, location_b, field_name):
        own = _integrationapi_make_channel(tenant_a, "Acme Link")
        foreign = _integrationapi_make_channel(tenant_b, "Globex Link")
        fk_pk = {"channel": foreign.pk, "item": item_b.pk, "location": location_b.pk}[field_name]
        data = _integrationapi_listing_data(**{"channel": own.pk, field_name: fk_pk})
        form = ChannelListingMapForm(data, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors
        assert ChannelListingMap.objects.count() == 0  # no cross-tenant save

    def test_integrationapi_fk_querysets_narrowed_to_own_tenant_only(
            self, tenant_a, tenant_b, item_a, location_a, item_b, location_b):
        own = _integrationapi_make_channel(tenant_a, "Acme Link")
        _integrationapi_make_channel(tenant_b, "Globex Link")

        channel_form = IntegrationChannelForm(tenant=tenant_a)
        loc_pks = set(
            channel_form.fields["default_location"].queryset.values_list("pk", flat=True))
        assert loc_pks == {location_a.pk}

        listing_form = ChannelListingMapForm(tenant=tenant_a)
        chan_pks = set(listing_form.fields["channel"].queryset.values_list("pk", flat=True))
        item_pks = set(listing_form.fields["item"].queryset.values_list("pk", flat=True))
        loc_pks = set(listing_form.fields["location"].queryset.values_list("pk", flat=True))
        assert chan_pks == {own.pk}
        assert item_pks == {item_a.pk}
        assert loc_pks == {location_a.pk}
        assert location_b.pk not in loc_pks

    def test_integrationapi_duplicate_channel_name_same_tenant_rejected_other_allowed(
            self, tenant_a, tenant_b):
        """TenantUniqueMixin makes (tenant, name) validate at the boundary instead of dying
        as an IntegrityError; the same name stays legal across workspaces."""
        _integrationapi_make_channel(tenant_a, "Shared Name")

        dup = IntegrationChannelForm(
            _integrationapi_channel_data(name="Shared Name"), tenant=tenant_a)
        assert not dup.is_valid()
        assert "name" in dup.errors or "__all__" in dup.errors

        other = IntegrationChannelForm(
            _integrationapi_channel_data(name="Shared Name"), tenant=tenant_b)
        assert other.is_valid(), other.errors
        saved = other.save()
        assert saved.tenant_id == tenant_b.pk


class TestIntegrationApiRecordedIntentAndBlanks:
    def test_integrationapi_api_client_scopes_ips_recorded_status_injection_ignored(
            self, tenant_a):
        """scopes/allowed_ips are recorded-intent free text; a crafted POST cannot smuggle
        ``status`` in - the form has no such field and the model default stands."""
        data = _integrationapi_client_data(
            scopes="stock:read,moves:read",
            allowed_ips="203.0.113.7,198.51.100.0/24",
            status="revoked",  # injection attempt - not a form field
        )
        form = ApiClientForm(data, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert "status" not in form.fields
        client = form.save()
        client.refresh_from_db()
        assert client.scopes == "stock:read,moves:read"
        assert client.allowed_ips == "203.0.113.7,198.51.100.0/24"
        assert client.status == "active"

    def test_integrationapi_listing_map_blank_external_ids_local_only_channel_required(
            self, tenant_a):
        """Blank external ids make a legal local-only row (variant id persists as NULL, never
        ''), but the channel FK itself stays required."""
        missing = ChannelListingMapForm(_integrationapi_listing_data(), tenant=tenant_a)
        assert not missing.is_valid()
        assert "channel" in missing.errors

        own = _integrationapi_make_channel(tenant_a, "Acme Link")
        first = ChannelListingMapForm(
            _integrationapi_listing_data(channel=own.pk, external_sku="CAT-1-SHOP"),
            tenant=tenant_a)
        assert first.is_valid(), first.errors
        row_one = first.save()
        assert row_one.external_variant_id is None

        # A second local-only row on the same channel must NOT collide (NULLs coalesce inside
        # the (tenant, channel, external_variant_id) unique_together).
        second = ChannelListingMapForm(
            _integrationapi_listing_data(channel=own.pk), tenant=tenant_a)
        assert second.is_valid(), second.errors
        second.save()
        assert ChannelListingMap.objects.filter(channel=own).count() == 2
