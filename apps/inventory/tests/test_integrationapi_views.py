"""Inventory 5.19 Third-Party Integrations & API — view behaviour through real HTTP.

The four registers render 200 with their contracted KPI strips and lenses, CRUD round-trips
stay tenant-scoped, and every verb keeps its honesty contract: ``sync`` records a SIMULATED
run (never touching ``last_sync_at``), ``rotate_key``/``issue_token`` reveal the plaintext
exactly once while only prefix+hash persist, issuing onto a revoked client is refused (I7),
``revoke`` is a graceful one-way lifecycle, and ``retry`` advances only genuinely retryable
runs onto the published backoff schedule — or marks them ``exhausted`` once it is spent (I1).
Foreign-workspace pks answer 404 on every route.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import (
    ApiClient,
    ChannelListingMap,
    IntegrationChannel,
    StockSyncRun,
)
from apps.inventory.models.ThirdPartyIntegrations._choices import SYNC_BACKOFF_SECONDS

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- builders


def _integrationapi_make_channel(tenant, name, **fields):
    fields.setdefault("kind", "ecommerce")
    fields.setdefault("platform", "shopify")
    fields.setdefault("status", "connected")
    return IntegrationChannel.objects.create(tenant=tenant, name=name, **fields)


def _integrationapi_make_listing(tenant, channel, *, item=None, location=None,
                                 external_sku="EXT-1", sync_enabled=True):
    return ChannelListingMap.objects.create(
        tenant=tenant, channel=channel, item=item, location=location,
        external_sku=external_sku, sync_enabled=sync_enabled)


def _integrationapi_make_run(tenant, channel, *, status="failed", attempt_no=1,
                             error_code=None, **fields):
    return StockSyncRun.record(
        tenant, channel, direction="outbound_push", trigger_mode="manual",
        status=status, attempt_no=attempt_no,
        records_total=0, records_ok=0,
        records_failed=1 if status == "failed" else 0,
        error_code=("TIMEOUT" if status == "failed" else "") if error_code is None else error_code,
        **fields)


def _integrationapi_make_api_client(tenant, name, **fields):
    return ApiClient.objects.create(tenant=tenant, name=name, **fields)


def _integrationapi_seed_registers(tenant, item=None, location=None):
    """A small two-sided register per surface: one connected channel + one disconnected ERP."""
    connected = _integrationapi_make_channel(
        tenant, "Connected Shop", external_account_ref="ACCT-99")
    erp = _integrationapi_make_channel(
        tenant, "Legacy ERP", kind="erp", platform="sap", status="disconnected")
    enabled_map = _integrationapi_make_listing(
        tenant, connected, item=item, location=location, external_sku="EN-1")
    paused_map = _integrationapi_make_listing(
        tenant, connected, external_sku="PAUSED-1", sync_enabled=False)
    ok_run = _integrationapi_make_run(tenant, connected, status="success", error_code="")
    bad_run = _integrationapi_make_run(tenant, erp, status="failed")
    live_bot = _integrationapi_make_api_client(
        tenant, "Live bot", scopes="stock:read,moves:read")
    dead_bot = _integrationapi_make_api_client(
        tenant, "Dead bot", status="revoked", protocol="graphql")
    return {
        "connected": connected, "erp": erp,
        "enabled_map": enabled_map, "paused_map": paused_map,
        "ok_run": ok_run, "bad_run": bad_run,
        "live_bot": live_bot, "dead_bot": dead_bot,
    }


def _integrationapi_flash(response):
    return [str(message) for message in response.context["messages"]]


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def _integrationapi_channel_a(db, tenant_a):
    return _integrationapi_make_channel(tenant_a, "Acme Shopify")


@pytest.fixture
def _integrationapi_channel_b(db, tenant_b):
    return _integrationapi_make_channel(tenant_b, "Globex Shopify")


@pytest.fixture
def _integrationapi_listing_a(db, tenant_a, _integrationapi_channel_a, item_a, location_a):
    return _integrationapi_make_listing(
        tenant_a, _integrationapi_channel_a, item=item_a, location=location_a,
        external_sku="CAT-1-EXT")


@pytest.fixture
def _integrationapi_listing_paused_a(db, tenant_a, _integrationapi_channel_a):
    return _integrationapi_make_listing(
        tenant_a, _integrationapi_channel_a, external_sku="CAT-PAUSED",
        sync_enabled=False)


@pytest.fixture
def _integrationapi_channel_listed_a(db, tenant_a, item_a, location_a):
    """A channel carrying THREE listings — two sync-enabled, one paused."""
    channel = _integrationapi_make_channel(tenant_a, "Acme Listed Shopify")
    _integrationapi_make_listing(tenant_a, channel, item=item_a, location=location_a,
                                 external_sku="ON-1")
    _integrationapi_make_listing(tenant_a, channel, item=item_a, external_sku="ON-2")
    _integrationapi_make_listing(tenant_a, channel, external_sku="OFF-1",
                                 sync_enabled=False)
    return channel


@pytest.fixture
def _integrationapi_run_failed_a(db, tenant_a, _integrationapi_channel_a):
    return _integrationapi_make_run(tenant_a, _integrationapi_channel_a, status="failed")


@pytest.fixture
def _integrationapi_api_client_a(db, tenant_a):
    return _integrationapi_make_api_client(
        tenant_a, "Acme Partner Bot", scopes="stock:read,moves:read")


@pytest.fixture
def _integrationapi_api_client_revoked_a(db, tenant_a):
    api_client = _integrationapi_make_api_client(tenant_a, "Acme Retired Bot")
    api_client.revoke()
    return api_client


# --------------------------------------------------------------------- registers + stats


def test_integrationapi_channel_list_renders_with_contracted_stats(
        client_a, _integrationapi_channel_a):
    response = client_a.get(reverse("inventory:integrationchannel_list"))
    assert response.status_code == 200
    assert response.context["stats"] == {
        "total": 1, "connected": 1, "error": 0, "disabled": 0}
    assert list(response.context["object_list"]) == [_integrationapi_channel_a]
    assert "page_obj" in response.context


def test_integrationapi_listingmap_list_renders_with_contracted_stats(
        client_a, _integrationapi_channel_a, _integrationapi_listing_a,
        _integrationapi_listing_paused_a):
    response = client_a.get(reverse("inventory:listingmap_list"))
    assert response.status_code == 200
    assert response.context["stats"] == {"total": 2, "enabled": 1, "paused": 1}
    assert response.context["object_list"].count() == 2
    assert "page_obj" in response.context


def test_integrationapi_syncrun_list_renders_with_contracted_stats(
        client_a, _integrationapi_channel_a, _integrationapi_run_failed_a):
    _integrationapi_make_run(_integrationapi_channel_a.tenant, _integrationapi_channel_a,
                             status="simulated", error_code="")
    response = client_a.get(reverse("inventory:stocksyncrun_list"))
    assert response.status_code == 200
    assert response.context["stats"] == {
        "total": 2, "success": 0, "partial": 0, "failed": 1, "simulated": 1}
    assert response.context["object_list"].count() == 2
    assert "page_obj" in response.context


def test_integrationapi_apiclient_list_renders_with_contracted_stats(
        client_a, _integrationapi_api_client_a, _integrationapi_api_client_revoked_a):
    response = client_a.get(reverse("inventory:apiclient_list"))
    assert response.status_code == 200
    assert response.context["stats"] == {"total": 2, "active": 1, "revoked": 1}
    assert response.context["object_list"].count() == 2
    assert "page_obj" in response.context


# ----------------------------------------------------------------------------- details


def test_integrationapi_channel_detail_context_keys(
        client_a, _integrationapi_channel_a, _integrationapi_listing_a,
        _integrationapi_run_failed_a):
    response = client_a.get(reverse(
        "inventory:integrationchannel_detail", args=[_integrationapi_channel_a.pk]))
    assert response.status_code == 200
    ctx = response.context
    assert ctx["obj"] == _integrationapi_channel_a
    assert list(ctx["listings"]) == [_integrationapi_listing_a]
    assert ctx["listings_total"] == 1
    assert ctx["run_stats"] == {"total": 1, "failed": 1}
    assert ctx["is_admin"] is True


def test_integrationapi_syncrun_detail_reports_backoff_ceiling(
        client_a, _integrationapi_run_failed_a):
    response = client_a.get(reverse(
        "inventory:stocksyncrun_detail", args=[_integrationapi_run_failed_a.pk]))
    assert response.status_code == 200
    assert response.context["max_attempts"] == len(SYNC_BACKOFF_SECONDS)
    assert response.context["obj"] == _integrationapi_run_failed_a
    assert response.context["is_admin"] is True


def test_integrationapi_listingmap_and_apiclient_details_render(
        client_a, _integrationapi_listing_a, _integrationapi_api_client_a):
    listing_page = client_a.get(reverse(
        "inventory:listingmap_detail", args=[_integrationapi_listing_a.pk]))
    assert listing_page.status_code == 200
    assert listing_page.context["obj"] == _integrationapi_listing_a
    assert listing_page.context["is_admin"] is True

    client_page = client_a.get(reverse(
        "inventory:apiclient_detail", args=[_integrationapi_api_client_a.pk]))
    assert client_page.status_code == 200
    assert client_page.context["obj"] == _integrationapi_api_client_a
    assert client_page.context["is_admin"] is True


# -------------------------------------------------------------------------- CRUD flows


def test_integrationapi_channel_crud_roundtrip(client_a, tenant_a):
    form = client_a.get(reverse("inventory:integrationchannel_create"))
    assert form.status_code == 200
    assert form.context["is_edit"] is False

    invalid = client_a.post(reverse("inventory:integrationchannel_create"), {})
    assert invalid.status_code == 200
    assert invalid.context["form"].errors
    assert not IntegrationChannel.objects.filter(tenant=tenant_a).exists()

    choice_fields = {
        "kind": "ecommerce", "platform": "shopify", "direction": "push_stock",
        "auth_method": "api_key", "environment": "sandbox",
        "status": "connected", "trigger_mode": "manual",
    }
    made = client_a.post(reverse("inventory:integrationchannel_create"),
                         {"name": "View-made channel", "is_active": "on", **choice_fields})
    assert made.status_code == 302
    assert made.url == reverse("inventory:integrationchannel_list")
    channel = IntegrationChannel.objects.get(tenant=tenant_a, name="View-made channel")
    assert channel.number.startswith("INT-")

    edited = client_a.post(reverse("inventory:integrationchannel_edit", args=[channel.pk]),
                           {"name": "Renamed channel", "is_active": "on", **choice_fields})
    assert edited.status_code == 302
    channel.refresh_from_db()
    assert channel.name == "Renamed channel"

    assert client_a.get(reverse("inventory:integrationchannel_delete",
                                args=[channel.pk])).status_code == 405
    assert IntegrationChannel.objects.filter(pk=channel.pk).exists()
    deleted = client_a.post(reverse("inventory:integrationchannel_delete",
                                    args=[channel.pk]))
    assert deleted.status_code == 302
    assert not IntegrationChannel.objects.filter(pk=channel.pk).exists()


def test_integrationapi_listingmap_crud_roundtrip(client_a, tenant_a,
                                                  _integrationapi_channel_a):
    channel = _integrationapi_channel_a

    invalid = client_a.post(reverse("inventory:listingmap_create"), {})
    assert invalid.status_code == 200
    assert invalid.context["form"].errors
    assert not ChannelListingMap.objects.filter(tenant=tenant_a).exists()

    made = client_a.post(reverse("inventory:listingmap_create"),
                         {"channel": str(channel.pk), "sync_enabled": "on"})
    assert made.status_code == 302
    assert made.url == reverse("inventory:listingmap_list")
    mapping = ChannelListingMap.objects.get(tenant=tenant_a, channel=channel)
    assert mapping.sync_enabled is True

    edited = client_a.post(reverse("inventory:listingmap_edit", args=[mapping.pk]),
                           {"channel": str(channel.pk), "external_sku": "RENAMED-SKU",
                            "sync_enabled": "on"})
    assert edited.status_code == 302
    mapping.refresh_from_db()
    assert mapping.external_sku == "RENAMED-SKU"

    assert client_a.get(reverse("inventory:listingmap_delete",
                                args=[mapping.pk])).status_code == 405
    deleted = client_a.post(reverse("inventory:listingmap_delete", args=[mapping.pk]))
    assert deleted.status_code == 302
    assert not ChannelListingMap.objects.filter(pk=mapping.pk).exists()


def test_integrationapi_apiclient_crud_roundtrip(client_a, tenant_a):
    form = client_a.get(reverse("inventory:apiclient_create"))
    assert form.status_code == 200
    assert form.context["is_edit"] is False

    invalid = client_a.post(reverse("inventory:apiclient_create"), {})
    assert invalid.status_code == 200
    assert invalid.context["form"].errors
    assert not ApiClient.objects.filter(tenant=tenant_a).exists()

    made = client_a.post(reverse("inventory:apiclient_create"),
                         {"name": "View-made bot", "protocol": "rest"})
    assert made.status_code == 302
    assert made.url == reverse("inventory:apiclient_list")
    api_client = ApiClient.objects.get(tenant=tenant_a, name="View-made bot")
    assert api_client.number.startswith("API-")
    assert api_client.status == "active"

    edited = client_a.post(reverse("inventory:apiclient_edit", args=[api_client.pk]),
                           {"name": "Renamed bot", "scopes": "stock:read",
                            "protocol": "rest"})
    assert edited.status_code == 302
    api_client.refresh_from_db()
    assert api_client.name == "Renamed bot"

    assert client_a.get(reverse("inventory:apiclient_delete",
                                args=[api_client.pk])).status_code == 405
    deleted = client_a.post(reverse("inventory:apiclient_delete", args=[api_client.pk]))
    assert deleted.status_code == 302
    assert not ApiClient.objects.filter(pk=api_client.pk).exists()


# --------------------------------------------------------------------------- sync verb


def test_integrationapi_sync_records_simulated_runs_and_never_touches_last_sync(
        client_a, _integrationapi_channel_listed_a):
    channel = _integrationapi_channel_listed_a
    assert channel.listings.filter(sync_enabled=True).count() == 2

    first = client_a.post(reverse("inventory:integrationchannel_sync", args=[channel.pk]))
    assert first.status_code == 302
    runs = list(channel.runs.order_by("id"))
    assert len(runs) == 1
    run = runs[0]
    assert run.status == "simulated"
    assert run.records_total == 2
    assert run.number.startswith("SYN-")
    assert first.url == reverse("inventory:stocksyncrun_detail", args=[run.pk])

    channel.refresh_from_db()
    assert channel.last_run_status == "simulated"
    assert channel.last_sync_at is None

    second = client_a.post(reverse("inventory:integrationchannel_sync", args=[channel.pk]))
    assert second.status_code == 302
    runs = list(channel.runs.order_by("id"))
    assert len(runs) == 2
    numbers = [r.number for r in runs]
    assert numbers[0].startswith("SYN-") and numbers[1].startswith("SYN-")
    assert numbers[0] != numbers[1]
    assert second.url == reverse("inventory:stocksyncrun_detail", args=[runs[-1].pk])
    channel.refresh_from_db()
    assert channel.last_sync_at is None


# ------------------------------------------------------------------ credential secrets


def test_integrationapi_rotate_key_reveals_secret_once_and_stores_prefix_hash_only(
        client_a, _integrationapi_channel_a):
    channel = _integrationapi_channel_a
    old_prefix, old_hash = channel.api_key_prefix, channel.api_key_hash

    response = client_a.post(reverse("inventory:integrationchannel_rotate_key",
                                     args=[channel.pk]), follow=True)
    assert response.status_code == 200
    flashes = [m for m in _integrationapi_flash(response) if "copy it now" in m]
    assert len(flashes) == 1
    plaintext = flashes[0].rsplit(": ", 1)[1]
    assert len(plaintext) >= 24
    assert response.content.decode().count(plaintext) == 1

    channel.refresh_from_db()
    assert channel.api_key_hash != old_hash
    assert channel.api_key_prefix != old_prefix
    assert channel.api_key_hash == IntegrationChannel.hash_secret(plaintext)
    assert channel.api_key_prefix == plaintext[:6]


def test_integrationapi_issue_token_reveals_once_and_refuses_revoked_client(
        client_a, _integrationapi_api_client_a, _integrationapi_api_client_revoked_a):
    active = _integrationapi_api_client_a
    issued = client_a.post(reverse("inventory:apiclient_issue_token", args=[active.pk]),
                           follow=True)
    assert issued.status_code == 200
    flashes = [m for m in _integrationapi_flash(issued) if "API token for" in m]
    assert len(flashes) == 1
    secret = flashes[0].split(": ", 1)[1].split(" —", 1)[0]
    assert len(secret) >= 24
    assert issued.content.decode().count(secret) == 1
    active.refresh_from_db()
    assert active.api_token_hash == ApiClient.hash_secret(secret)
    assert active.api_token_prefix == secret[:6]

    revoked = _integrationapi_api_client_revoked_a
    before_hash = revoked.api_token_hash
    before_prefix = revoked.api_token_prefix
    refusal = client_a.post(reverse("inventory:apiclient_issue_token", args=[revoked.pk]),
                            follow=True)
    assert refusal.status_code == 200
    assert any("revoked" in m.lower() for m in _integrationapi_flash(refusal))
    revoked.refresh_from_db()
    assert revoked.api_token_hash == before_hash
    assert revoked.api_token_prefix == before_prefix


# ------------------------------------------------------------------------ revoke verb


def test_integrationapi_revoke_then_repeat_is_graceful_noop(
        client_a, _integrationapi_api_client_a):
    api_client = _integrationapi_api_client_a
    first = client_a.post(reverse("inventory:apiclient_revoke", args=[api_client.pk]),
                          follow=True)
    assert first.status_code == 200
    api_client.refresh_from_db()
    assert api_client.status == "revoked"
    stamp = api_client.revoked_at
    assert stamp is not None

    repeat = client_a.post(reverse("inventory:apiclient_revoke", args=[api_client.pk]),
                           follow=True)
    assert repeat.status_code == 200
    api_client.refresh_from_db()
    assert api_client.revoked_at == stamp
    assert any("already revoked" in m for m in _integrationapi_flash(repeat))


# ------------------------------------------------------------------------- retry verb


def test_integrationapi_retry_advances_failed_run_and_refuses_simulated(
        client_a, _integrationapi_run_failed_a):
    failed = _integrationapi_run_failed_a
    response = client_a.post(reverse("inventory:stocksyncrun_retry", args=[failed.pk]),
                             follow=True)
    assert response.status_code == 200
    failed.refresh_from_db()
    assert failed.status == "pending"
    assert failed.attempt_no == 2
    assert failed.next_retry_at is not None
    assert failed.next_retry_at > timezone.now()

    simulated = _integrationapi_make_run(failed.tenant, failed.channel,
                                         status="simulated", error_code="")
    before = (simulated.status, simulated.attempt_no, simulated.next_retry_at)
    refusal = client_a.post(reverse("inventory:stocksyncrun_retry", args=[simulated.pk]),
                            follow=True)
    assert refusal.status_code == 200
    assert any("cannot be retried" in m for m in _integrationapi_flash(refusal))
    simulated.refresh_from_db()
    assert (simulated.status, simulated.attempt_no, simulated.next_retry_at) == before


def test_integrationapi_retry_marks_exhausted_once_schedule_spent(
        client_a, tenant_a, _integrationapi_channel_a):
    spent = _integrationapi_make_run(
        tenant_a, _integrationapi_channel_a, status="failed",
        attempt_no=len(SYNC_BACKOFF_SECONDS) - 1)

    first = client_a.post(reverse("inventory:stocksyncrun_retry", args=[spent.pk]),
                          follow=True)
    assert first.status_code == 200
    spent.refresh_from_db()
    assert spent.status == "pending"
    assert spent.attempt_no == len(SYNC_BACKOFF_SECONDS)

    second = client_a.post(reverse("inventory:stocksyncrun_retry", args=[spent.pk]),
                           follow=True)
    assert second.status_code == 200
    spent.refresh_from_db()
    assert spent.status == "exhausted"
    assert spent.next_retry_at is None


# ------------------------------------------------------- filters, junk fallback, search


def test_integrationapi_filter_lenses_and_junk_fallback_across_registers(
        client_a, tenant_a, item_a, location_a):
    seeds = _integrationapi_seed_registers(tenant_a, item=item_a, location=location_a)

    hit = client_a.get(reverse("inventory:integrationchannel_list"), {"kind": "erp"})
    assert list(hit.context["object_list"]) == [seeds["erp"]]
    hit = client_a.get(reverse("inventory:integrationchannel_list"),
                       {"status": "connected"})
    assert list(hit.context["object_list"]) == [seeds["connected"]]
    hit = client_a.get(reverse("inventory:integrationchannel_list"), {"platform": "sap"})
    assert list(hit.context["object_list"]) == [seeds["erp"]]
    junk = client_a.get(reverse("inventory:integrationchannel_list"),
                        {"kind": "zzz", "status": "bogus", "platform": "nada"})
    assert junk.context["object_list"].count() == 2

    hit = client_a.get(reverse("inventory:listingmap_list"),
                       {"channel": str(seeds["connected"].pk), "sync_enabled": "true"})
    assert list(hit.context["object_list"]) == [seeds["enabled_map"]]
    hit = client_a.get(reverse("inventory:listingmap_list"), {"sync_enabled": "false"})
    assert list(hit.context["object_list"]) == [seeds["paused_map"]]
    junk = client_a.get(reverse("inventory:listingmap_list"), {"sync_enabled": "maybe"})
    assert junk.context["object_list"].count() == 2

    hit = client_a.get(reverse("inventory:stocksyncrun_list"),
                       {"status": "failed", "channel": str(seeds["erp"].pk)})
    assert list(hit.context["object_list"]) == [seeds["bad_run"]]
    hit = client_a.get(reverse("inventory:stocksyncrun_list"),
                       {"channel": str(seeds["connected"].pk)})
    assert list(hit.context["object_list"]) == [seeds["ok_run"]]
    junk = client_a.get(reverse("inventory:stocksyncrun_list"), {"channel": "abc"})
    assert junk.context["object_list"].count() == 2
    junk = client_a.get(reverse("inventory:stocksyncrun_list"),
                        {"channel": "999999999999999999999", "status": "nope"})
    assert junk.context["object_list"].count() == 2

    hit = client_a.get(reverse("inventory:apiclient_list"), {"status": "active"})
    assert list(hit.context["object_list"]) == [seeds["live_bot"]]
    hit = client_a.get(reverse("inventory:apiclient_list"), {"protocol": "graphql"})
    assert list(hit.context["object_list"]) == [seeds["dead_bot"]]
    junk = client_a.get(reverse("inventory:apiclient_list"),
                        {"status": "zzz", "protocol": "zzz"})
    assert junk.context["object_list"].count() == 2


def test_integrationapi_q_search_hits_name_sku_error_code_paths(
        client_a, tenant_a, item_a):
    seeds = _integrationapi_seed_registers(tenant_a, item=item_a)

    hit = client_a.get(reverse("inventory:integrationchannel_list"), {"q": "Connected"})
    assert list(hit.context["object_list"]) == [seeds["connected"]]
    hit = client_a.get(reverse("inventory:integrationchannel_list"), {"q": "ACCT-99"})
    assert list(hit.context["object_list"]) == [seeds["connected"]]

    hit = client_a.get(reverse("inventory:listingmap_list"), {"q": "EN-1"})
    assert list(hit.context["object_list"]) == [seeds["enabled_map"]]
    hit = client_a.get(reverse("inventory:listingmap_list"), {"q": item_a.sku})
    assert list(hit.context["object_list"]) == [seeds["enabled_map"]]

    hit = client_a.get(reverse("inventory:stocksyncrun_list"),
                       {"q": seeds["ok_run"].number})
    assert list(hit.context["object_list"]) == [seeds["ok_run"]]
    hit = client_a.get(reverse("inventory:stocksyncrun_list"), {"q": "timeout"})
    assert list(hit.context["object_list"]) == [seeds["bad_run"]]

    hit = client_a.get(reverse("inventory:apiclient_list"), {"q": "Live"})
    assert list(hit.context["object_list"]) == [seeds["live_bot"]]
    hit = client_a.get(reverse("inventory:apiclient_list"), {"q": "stock:read"})
    assert list(hit.context["object_list"]) == [seeds["live_bot"]]


# -------------------------------------------------------------------------- pagination


def test_integrationapi_pagination_page_object_and_second_page(client_a, tenant_a):
    for i in range(16):
        _integrationapi_make_channel(tenant_a, f"Bulk channel {i:02d}")

    first = client_a.get(reverse("inventory:integrationchannel_list"))
    assert first.status_code == 200
    assert "page_obj" in first.context
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(reverse("inventory:integrationchannel_list"), {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 1


# ---------------------------------------------------------------------- tenant isolation


def test_integrationapi_foreign_tenant_rows_404_on_every_route(
        client_a, tenant_b):
    channel = _integrationapi_make_channel(tenant_b, "Globex Shopify")
    listing = _integrationapi_make_listing(tenant_b, channel)
    run = _integrationapi_make_run(tenant_b, channel)
    api_client = _integrationapi_make_api_client(tenant_b, "Globex bot")

    gets = [
        ("inventory:integrationchannel_detail", [channel.pk]),
        ("inventory:integrationchannel_edit", [channel.pk]),
        ("inventory:listingmap_detail", [listing.pk]),
        ("inventory:listingmap_edit", [listing.pk]),
        ("inventory:stocksyncrun_detail", [run.pk]),
        ("inventory:apiclient_detail", [api_client.pk]),
        ("inventory:apiclient_edit", [api_client.pk]),
    ]
    posts = [
        ("inventory:integrationchannel_delete", [channel.pk]),
        ("inventory:integrationchannel_rotate_key", [channel.pk]),
        ("inventory:integrationchannel_sync", [channel.pk]),
        ("inventory:listingmap_delete", [listing.pk]),
        ("inventory:stocksyncrun_retry", [run.pk]),
        ("inventory:apiclient_delete", [api_client.pk]),
        ("inventory:apiclient_issue_token", [api_client.pk]),
        ("inventory:apiclient_revoke", [api_client.pk]),
    ]
    for url_name, args in gets:
        assert client_a.get(reverse(url_name, args=args)).status_code == 404, url_name
    for url_name, args in posts:
        assert client_a.post(reverse(url_name, args=args)).status_code == 404, url_name

    assert IntegrationChannel.objects.filter(pk=channel.pk).exists()
    assert ChannelListingMap.objects.filter(pk=listing.pk).exists()
    assert StockSyncRun.objects.filter(pk=run.pk).exists()
    assert ApiClient.objects.filter(pk=api_client.pk).exists()
