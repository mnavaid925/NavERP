"""Inventory 5.19 Third-Party Integrations & API — model boundary.

Covers the four 5.19 entities against their frozen contract:

* ``IntegrationChannel`` [INT-] — per-tenant auto-numbering (increments, stable on
  re-save, restarts per tenant), the (tenant, name) uniqueness enforced at BOTH paths
  the app uses (``full_clean`` -> ``ValidationError`` for forms, raw ``IntegrityError``
  for the bare ORM), the cross-tenant ``default_location`` refusal in ``clean()``, and
  the credential quartet: ``set_api_key`` persisting ONLY prefix(6)+SHA-256,
  ``generate_api_key`` answering a distinct 32-char urlsafe token, and ``masked``
  answering "" until credentialed then prefix + 8 bullets.
* ``ChannelListingMap`` — the null-coalescing (tenant, channel, external_variant_id)
  uniqueness post-review shape: unlimited local-only NULL-variant rows per channel,
  a hard collision when two rows CLAIM the same variant id inside ONE channel, free
  reuse of the same variant id across channels; foreign item/channel pointers refused
  by ``clean()``.
* ``StockSyncRun`` [SYN-] — ``record()`` as the single append-only front door (assigns
  the passed fields, saves, returns a numbered instance, stamps NOTHING on the
  channel), the cross-tenant channel refusal surfaced through ``full_clean()``, and
  the ``next_backoff_seconds`` ladder: attempt N reads slot N of
  ``SYNC_BACKOFF_SECONDS``, the len-1 boundary still schedules, >= len answers None,
  and a raw attempt_no of 0 degrades safely to slot 0.
* ``ApiClient`` [API-] — ``revoke()`` flipping active->revoked exactly once (a second
  call and a cold refetch of an already-revoked row both leave the original stamp),
  plus Meta-ordering determinism for identical-name rows on all four tables (the id
  tiebreak, descending for the run register).
"""
import hashlib
import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.inventory.models import (
    ApiClient,
    ChannelListingMap,
    IntegrationChannel,
    StockSyncRun,
)
from apps.inventory.models.ThirdPartyIntegrations._choices import SYNC_BACKOFF_SECONDS

pytestmark = pytest.mark.django_db


@pytest.fixture
def _integrationapi_channel_a(db, tenant_a):
    """An Acme connection registration [INT-] — the owned channel."""
    return IntegrationChannel.objects.create(
        tenant=tenant_a, name="Acme Shopify", kind="ecommerce", platform="shopify")


@pytest.fixture
def _integrationapi_channel_b(db, tenant_b):
    """Globex's mirror channel — the foreign-workspace target for guard lanes."""
    return IntegrationChannel.objects.create(
        tenant=tenant_b, name="Globex Shopify", kind="ecommerce", platform="shopify")


@pytest.fixture
def _integrationapi_client_a(db, tenant_a):
    """An ACTIVE third-party caller key [API-], tenant_a."""
    return ApiClient.objects.create(tenant=tenant_a, name="Partner Gateway")


@pytest.fixture
def _integrationapi_listing_a(db, tenant_a, _integrationapi_channel_a, item_a):
    """A LOCAL-ONLY listing (external_variant_id NULL) mapping item_a on the channel."""
    return ChannelListingMap.objects.create(
        tenant=tenant_a, channel=_integrationapi_channel_a, item=item_a,
        external_sku="CAT-1-SHOP")


def _integrationapi_hash(secret):
    """The SHA-256 hex digest the models must persist instead of any plaintext."""
    return hashlib.sha256(secret.encode()).hexdigest()


def _integrationapi_make_run(channel, **fields):
    """A recorded push batch against ``channel``, inheriting its tenant."""
    return StockSyncRun.objects.create(
        tenant=channel.tenant, channel=channel, direction="outbound_push", **fields)


def _integrationapi_make_listing(channel, **fields):
    """A listing join row inheriting the channel's tenant."""
    return ChannelListingMap.objects.create(tenant=channel.tenant, channel=channel, **fields)


def test_integrationapi_channel_numbers_mint_per_tenant_increment_and_survive_resave(
        tenant_a, tenant_b):
    """INT- numbers mint once per row, walk forward within a tenant, survive an
    ordinary re-save untouched, and restart at 00001 for the next tenant."""
    alpha = IntegrationChannel.objects.create(tenant=tenant_a, name="Alpha Feed")
    beta = IntegrationChannel.objects.create(tenant=tenant_a, name="Beta Feed")
    assert alpha.number == "INT-00001"
    assert beta.number == "INT-00002"

    alpha.name = "Alpha Feed Renamed"
    alpha.save()
    alpha.refresh_from_db()
    assert alpha.number == "INT-00001"

    globex = IntegrationChannel.objects.create(tenant=tenant_b, name="Gamma Feed")
    assert globex.number == "INT-00001"


def test_integrationapi_syn_and_api_numbers_mint_per_tenant_through_creators(
        tenant_a, _integrationapi_channel_a):
    """Each numbered entity owns its prefix independently: a recorded run mints SYN-,
    issued clients walk API-, and neither disturbs the channel's INT- sequence."""
    run = StockSyncRun.record(
        _integrationapi_channel_a.tenant, _integrationapi_channel_a,
        direction="outbound_push")
    client_one = ApiClient.objects.create(tenant=tenant_a, name="Gateway One")
    client_two = ApiClient.objects.create(tenant=tenant_a, name="Gateway Two")

    assert run.number == "SYN-00001"
    assert client_one.number == "API-00001"
    assert client_two.number == "API-00002"


def test_integrationapi_channel_duplicate_name_refused_in_tenant_allowed_across(
        tenant_a, tenant_b, _integrationapi_channel_a):
    """A repeated (tenant, name) dies at the form path as a ``ValidationError`` and at
    the raw ORM path as an ``IntegrityError``, while the SAME name on another tenant
    saves cleanly."""
    dup = IntegrationChannel(tenant=tenant_a, name=_integrationapi_channel_a.name)
    with pytest.raises(ValidationError) as err:
        dup.full_clean()
    assert "__all__" in err.value.message_dict

    across = IntegrationChannel.objects.create(
        tenant=tenant_b, name=_integrationapi_channel_a.name)
    assert across.number.startswith("INT-")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IntegrationChannel.objects.create(
                tenant=tenant_a, name=_integrationapi_channel_a.name)


def test_integrationapi_listing_local_only_null_variants_coexist_freely(
        _integrationapi_channel_a, _integrationapi_listing_a, tenant_a):
    """Rows with external_variant_id NULL never collide — several on ONE channel and
    more on a second channel all coexist (the '' default would have broken this)."""
    sibling = _integrationapi_make_listing(_integrationapi_channel_a)
    other_channel = IntegrationChannel.objects.create(
        tenant=tenant_a, name="Acme Amazon")
    elsewhere = _integrationapi_make_listing(other_channel)

    assert _integrationapi_listing_a.external_variant_id is None
    assert ChannelListingMap.objects.filter(
        tenant=tenant_a, external_variant_id__isnull=True).count() == 3
    assert {_integrationapi_listing_a.channel_id, sibling.channel_id,
            elsewhere.channel_id} == {_integrationapi_channel_a.pk, other_channel.pk}


def test_integrationapi_listing_claimed_variant_unique_per_channel_only(
        _integrationapi_channel_a, tenant_a):
    """Two rows CLAIMING the same external variant id cannot both exist inside one
    channel, yet the same id may be claimed freely on a sibling channel."""
    variant = "gid://shopify/ProductVariant/4242"
    original = _integrationapi_make_listing(
        _integrationapi_channel_a, external_variant_id=variant)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _integrationapi_make_listing(
                _integrationapi_channel_a, external_variant_id=variant)

    sibling = IntegrationChannel.objects.create(tenant=tenant_a, name="Acme eBay")
    twin = _integrationapi_make_listing(sibling, external_variant_id=variant)
    assert twin.external_variant_id == variant
    assert original.channel_id != twin.channel_id
    assert ChannelListingMap.objects.filter(
        tenant=tenant_a, external_variant_id=variant).count() == 2


def test_integrationapi_channel_clean_rejects_foreign_default_location(
        tenant_a, location_a, location_b):
    """``clean()`` refuses a default_location belonging to another workspace, naming
    the offending field, and accepts an owned one."""
    foreign = IntegrationChannel(
        tenant=tenant_a, name="Miswired Feed", default_location=location_b)
    with pytest.raises(ValidationError) as err:
        foreign.full_clean()
    assert "default_location" in err.value.message_dict
    assert err.value.message_dict["default_location"] == [
        "That record belongs to another workspace."]

    owned = IntegrationChannel(
        tenant=tenant_a, name="Well Wired", default_location=location_a)
    owned.full_clean()


def test_integrationapi_listing_clean_rejects_foreign_item_and_channel(
        _integrationapi_channel_a, _integrationapi_channel_b, item_a, item_b, tenant_a):
    """Every TENANT_SCOPED_FKS pointer is guarded: a foreign item and a foreign
    channel each come back as a keyed field error, never a silent save."""
    bad_item = ChannelListingMap(
        tenant=tenant_a, channel=_integrationapi_channel_a, item=item_b)
    with pytest.raises(ValidationError) as err:
        bad_item.full_clean()
    assert "item" in err.value.message_dict
    assert err.value.message_dict["item"] == ["That record belongs to another workspace."]

    bad_channel = ChannelListingMap(tenant=tenant_a, channel=_integrationapi_channel_b)
    with pytest.raises(ValidationError) as err:
        bad_channel.full_clean()
    assert "channel" in err.value.message_dict
    assert err.value.message_dict["channel"] == ["That record belongs to another workspace."]

    good = ChannelListingMap(
        tenant=tenant_a, channel=_integrationapi_channel_a, item=item_a)
    good.full_clean()


def test_integrationapi_syncrun_record_foreign_channel_refused_by_full_clean(
        tenant_a, _integrationapi_channel_a, _integrationapi_channel_b):
    """The run register's ``clean()`` is the whole boundary for shell/admin writers: a
    run pointed at another tenant's channel fails ``full_clean()`` on the channel key,
    while an owned channel passes."""
    leak = StockSyncRun.record(
        tenant_a, _integrationapi_channel_b, direction="outbound_push")
    with pytest.raises(ValidationError) as err:
        leak.full_clean()
    assert "channel" in err.value.message_dict
    assert err.value.message_dict["channel"] == ["That record belongs to another workspace."]

    honest = StockSyncRun(
        tenant=tenant_a, channel=_integrationapi_channel_a, direction="inbound_pull")
    honest.full_clean()


def test_integrationapi_set_api_key_persists_prefix_and_digest_only(
        _integrationapi_channel_a):
    """``set_api_key`` stores prefix(6) + SHA-256 and nothing else — the plaintext is
    nowhere on the refreshed instance, not even as a suffix of the digest."""
    secret = "sk_live_" + IntegrationChannel.generate_api_key()
    _integrationapi_channel_a.set_api_key(secret)
    _integrationapi_channel_a.save(update_fields=[
        "api_key_prefix", "api_key_hash", "updated_at"])

    channel = IntegrationChannel.objects.get(pk=_integrationapi_channel_a.pk)
    assert channel.api_key_prefix == secret[:6]
    assert channel.api_key_hash == _integrationapi_hash(secret)
    assert len(channel.api_key_hash) == 64
    persisted = channel.api_key_prefix + channel.api_key_hash
    assert secret not in persisted
    assert secret[6:] not in persisted


def test_integrationapi_generate_api_key_answers_distinct_urlsafe_tokens():
    """Both issuers answer 32-character urlsafe tokens (24 bytes -> 32 chars, no
    padding), and consecutive draws never repeat."""
    first = IntegrationChannel.generate_api_key()
    second = IntegrationChannel.generate_api_key()
    assert first != second
    assert len(first) == len(second) == 32
    assert re.fullmatch(r"[A-Za-z0-9_-]{32}", first)

    token = ApiClient.generate_api_token()
    assert len(token) == 32
    assert re.fullmatch(r"[A-Za-z0-9_-]{32}", token)


def test_integrationapi_masked_blank_until_credentialed_then_prefix_plus_bullets(
        _integrationapi_channel_a):
    """``masked`` — what templates render — is "" while uncredentialed and exactly
    prefix + eight bullets once a key is set, leaking no secret body."""
    assert IntegrationChannel(api_key_prefix="", api_key_hash="").masked == ""

    secret = IntegrationChannel.generate_api_key()
    _integrationapi_channel_a.set_api_key(secret)
    assert _integrationapi_channel_a.masked == f"{secret[:6]}{'•' * 8}"
    assert secret[6:] not in _integrationapi_channel_a.masked


def test_integrationapi_record_assigns_fields_saves_and_leaves_channel_stamps_alone(
        tenant_a, _integrationapi_channel_a):
    """``record()`` assigns exactly the handed-over fields, saves, and returns a
    numbered instance — and stamps nothing upstream: the channel's ``last_sync_at``
    and ``last_run_status`` stay untouched by design."""
    run = StockSyncRun.record(
        tenant_a, _integrationapi_channel_a,
        direction="outbound_push", trigger_mode="webhook_inbound",
        status="simulated", records_total=12, records_ok=10, records_failed=2,
        payload_excerpt='{"skus":["CAT-1"]}')

    assert run.pk is not None
    assert run.number == "SYN-00001"

    stored = StockSyncRun.objects.get(pk=run.pk)
    assert stored.direction == "outbound_push"
    assert stored.trigger_mode == "webhook_inbound"
    assert stored.status == "simulated"
    assert (stored.records_total, stored.records_ok, stored.records_failed) == (12, 10, 2)
    assert stored.attempt_no == 1
    assert stored.started_at is not None
    assert stored.next_retry_at is None

    channel = IntegrationChannel.objects.get(pk=_integrationapi_channel_a.pk)
    assert channel.last_sync_at is None
    assert channel.last_run_status == ""


def test_integrationapi_next_backoff_reads_published_schedule_slots(
        _integrationapi_channel_a):
    """Attempt N reads slot N of the published ladder: the first retry waits five
    seconds and the len-1 boundary still offers the final 36000-second slot."""
    first = _integrationapi_make_run(_integrationapi_channel_a, attempt_no=1)
    boundary = _integrationapi_make_run(
        _integrationapi_channel_a, attempt_no=len(SYNC_BACKOFF_SECONDS) - 1)

    assert first.next_backoff_seconds == SYNC_BACKOFF_SECONDS[1]
    assert first.next_backoff_seconds == 5
    assert boundary.next_backoff_seconds == SYNC_BACKOFF_SECONDS[-1]
    assert boundary.next_backoff_seconds == 36000


def test_integrationapi_next_backoff_spent_schedule_and_zero_edge_answer_safely(
        _integrationapi_channel_a):
    """At len attempts (or beyond) the schedule is spent and answers None — the signal
    the retry verb turns into ``exhausted`` — while a raw attempt_no of 0 degrades to
    slot 0 instead of raising."""
    spent = _integrationapi_make_run(
        _integrationapi_channel_a, attempt_no=len(SYNC_BACKOFF_SECONDS))
    far_past = _integrationapi_make_run(_integrationapi_channel_a, attempt_no=9999)
    immediate = _integrationapi_make_run(_integrationapi_channel_a, attempt_no=0)

    assert spent.next_backoff_seconds is None
    assert far_past.next_backoff_seconds is None
    assert immediate.next_backoff_seconds == 0
    assert StockSyncRun.MAX_ATTEMPTS == len(SYNC_BACKOFF_SECONDS) == 8


def test_integrationapi_api_client_revoke_stamps_once_and_is_noop_safe(
        _integrationapi_client_a):
    """``revoke()`` flips an active client to revoked and stamps ``revoked_at`` exactly
    once: a second call on the live instance and a cold refetch of the already-revoked
    row are both no-ops that preserve the original stamp."""
    client = _integrationapi_client_a
    assert client.status == "active"
    assert client.revoked_at is None

    client.revoke()
    client.refresh_from_db()
    assert client.status == "revoked"
    assert client.revoked_at is not None
    original_stamp = client.revoked_at

    client.revoke()
    client.refresh_from_db()
    assert client.status == "revoked"
    assert client.revoked_at == original_stamp

    refetched = ApiClient.objects.get(pk=client.pk)
    refetched.revoke()
    refetched.refresh_from_db()
    assert refetched.status == "revoked"
    assert refetched.revoked_at == original_stamp


def test_integrationapi_meta_orderings_are_total_and_deterministic(
        tenant_a, _integrationapi_channel_a):
    """(name, id) ascending gives channels/clients a TOTAL order (identical names are
    impossible there by design - unique (tenant, name)), so page 2 never reshuffles;
    listing maps tie-break by id and the run register sorts newest-first even when
    timestamps collide exactly."""
    chan_lo = IntegrationChannel.objects.create(tenant=tenant_a, name="Zeta Feed")
    chan_hi = IntegrationChannel.objects.create(tenant=tenant_a, name="Alpha Feed")
    assert [row.pk for row in IntegrationChannel.objects.filter(
        tenant=tenant_a, pk__in=[chan_lo.pk, chan_hi.pk])] == [chan_hi.pk, chan_lo.pk]

    cli_lo = ApiClient.objects.create(tenant=tenant_a, name="Zeta Gateway")
    cli_hi = ApiClient.objects.create(tenant=tenant_a, name="Alpha Gateway")
    assert [row.pk for row in ApiClient.objects.filter(
        tenant=tenant_a, pk__in=[cli_lo.pk, cli_hi.pk])] == [cli_hi.pk, cli_lo.pk]

    listing_lo = _integrationapi_make_listing(_integrationapi_channel_a)
    listing_hi = _integrationapi_make_listing(_integrationapi_channel_a)
    assert [row.pk for row in _integrationapi_channel_a.listings.all()] == [
        listing_lo.pk, listing_hi.pk]

    stamp = timezone.now()
    run_first = _integrationapi_make_run(_integrationapi_channel_a, started_at=stamp)
    run_second = _integrationapi_make_run(_integrationapi_channel_a, started_at=stamp)
    assert [row.pk for row in StockSyncRun.objects.filter(
        channel=_integrationapi_channel_a)] == [run_second.pk, run_first.pk]
