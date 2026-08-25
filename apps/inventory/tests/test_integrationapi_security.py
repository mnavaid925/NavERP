"""Inventory 5.19 Third-Party Integrations & API — security contract.

The sub-module's whole posture is "records integration, transports nothing", so the
adversarial suite pins exactly that: cross-tenant IDOR on every detail/edit/delete/
retry/rotate/issue/revoke/sync route (foreign pk == 404, foreign row byte-intact),
the anonymous/member/admin authz matrix (login redirect with zero writes for strangers,
403 for members on channel/apiclient surfaces while listing-map CRUD stays staff-open),
secret hygiene end-to-end (rotate/issue plaintext flashed EXACTLY once and stored as
prefix+hash only — never in a form field, never in an AuditLog row), SSRF inertness
(no outbound HTTP stack in any 5.19 source file; sync+retry complete with sockets
rigged to explode and zero outbound artifacts), escaping of attacker-controlled text,
POST-only verb enforcement, and a no-``|safe`` scan across all eleven templates.
"""
import io
import json
import re
import socket
import tokenize
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.core.models import AuditLog
from apps.inventory.forms.ThirdPartyIntegrations.ApiClients import ApiClientForm
from apps.inventory.forms.ThirdPartyIntegrations.IntegrationChannels import (
    IntegrationChannelForm,
)
from apps.inventory.models import (
    ApiClient,
    ChannelListingMap,
    IntegrationChannel,
    StockSyncRun,
)

pytestmark = pytest.mark.django_db

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Every POST-only verb route of 5.19 — the eight destructive/side-effecting endpoints.
_INTEGRATIONAPI_POST_VERBS = [
    "integrationchannel_delete",
    "integrationchannel_rotate_key",
    "integrationchannel_sync",
    "listingmap_delete",
    "stocksyncrun_retry",
    "apiclient_delete",
    "apiclient_issue_token",
    "apiclient_revoke",
]

#: Detail/edit routes that take a pk — mapped to the owned/foreign fixture that backs them.
_INTEGRATIONAPI_PK_GET_ROUTES = {
    "integrationchannel_detail": "_integrationapi_channel_b",
    "integrationchannel_edit": "_integrationapi_channel_b",
    "listingmap_detail": "_integrationapi_listing_b",
    "listingmap_edit": "_integrationapi_listing_b",
    "stocksyncrun_detail": "_integrationapi_run_failed_b",
    "apiclient_detail": "_integrationapi_apiclient_b",
    "apiclient_edit": "_integrationapi_apiclient_b",
}

#: Same mapping for the IDOR sweep's foreign side (tenant_b rows probed by tenant_a).
_INTEGRATIONAPI_PK_POST_ROUTES = {
    "integrationchannel_delete": "_integrationapi_channel_b",
    "integrationchannel_rotate_key": "_integrationapi_channel_b",
    "integrationchannel_sync": "_integrationapi_channel_b",
    "listingmap_delete": "_integrationapi_listing_b",
    "stocksyncrun_retry": "_integrationapi_run_failed_b",
    "apiclient_delete": "_integrationapi_apiclient_b",
    "apiclient_issue_token": "_integrationapi_apiclient_b",
    "apiclient_revoke": "_integrationapi_apiclient_b",
}

#: Outbound transport tokens that must not appear in any CODE line of 5.19 sources.
_INTEGRATIONAPI_FORBIDDEN_TRANSPORT = ["requests", "urllib", "http.client", "socket.", "httpx"]

_STRING_TOKEN_TYPES = {tokenize.STRING}
for _name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
    _tok = getattr(tokenize, _name, None)
    if _tok is not None:
        _STRING_TOKEN_TYPES.add(_tok)


# ---- in-file helpers ---------------------------------------------------------------------------


def _integrationapi_counts():
    """One row-count tuple per entity table — the cheap did-anything-change probe."""
    return (
        IntegrationChannel.objects.count(),
        ChannelListingMap.objects.count(),
        StockSyncRun.objects.count(),
        ApiClient.objects.count(),
    )


def _integrationapi_seed_key(channel):
    channel.set_api_key("seed-channel-key-value")
    channel.save(update_fields=["api_key_prefix", "api_key_hash", "updated_at"])


def _integrationapi_seed_token(client):
    client.set_api_token("seed-client-token-value")
    client.save(update_fields=["api_token_prefix", "api_token_hash", "updated_at"])


def _integrationapi_snapshot(obj):
    """Cheap tamper-detection tuple for any of the four row kinds — compared before/after."""
    return (
        type(obj).__name__,
        getattr(obj, "api_key_hash", "") or getattr(obj, "api_token_hash", ""),
        getattr(obj, "status", ""),
        getattr(obj, "attempt_no", None),
        getattr(obj, "last_run_status", ""),
        getattr(obj, "error_message", ""),
        getattr(obj, "external_sku", ""),
        obj.runs.count() if isinstance(obj, IntegrationChannel) else 0,
    )


def _integrationapi_code_only(path):
    """File text minus comments AND string literals (docstrings included).

    The honesty docstrings of 5.19 *name* the forbidden modules ("no requests/urllib/httpx"),
    so a naive substring scan would false-positive on prose. Tokenize-mask every COMMENT and
    STRING span, then return only what remains — real code lines.
    """
    src = Path(path).read_text(encoding="utf-8")
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        fallback = "\n".join(
            line for line in src.splitlines() if not line.lstrip().startswith("#")
        )
        return fallback
    grid = [list(line) for line in src.splitlines()]
    for tok in tokens:
        if tok.type == tokenize.COMMENT or tok.type in _STRING_TOKEN_TYPES:
            (sr, sc), (er, ec) = tok.start, tok.end
            if sr > len(grid) or er > len(grid):
                continue
            if sr == er:
                grid[sr - 1][sc:ec] = [" "] * (ec - sc)
            else:
                grid[sr - 1][sc:] = [" "] * (len(grid[sr - 1]) - sc)
                for row in range(sr, min(er - 1, len(grid))):
                    grid[row] = [" "] * len(grid[row])
                grid[er - 1][:ec] = [" "] * ec
    return "\n".join("".join(row) for row in grid)


def _integrationapi_login_url():
    return reverse(settings.LOGIN_URL)


# ---- fixtures (all private-prefixed; consume ONLY root/inventory conftest rows otherwise) ------


@pytest.fixture
def _integrationapi_channel_a(db, tenant_a, location_a):
    """An Acme connection registration [INT-] with its base_url recorded."""
    channel = IntegrationChannel.objects.create(
        tenant=tenant_a,
        name="Acme Shopify Storefront",
        kind="ecommerce",
        platform="shopify",
        direction="bidirectional",
        auth_method="api_key",
        base_url="https://acme-store.myshopify.com/admin/api/graphql.json",
        external_account_ref="acme-store",
        environment="production",
        status="connected",
        default_location=location_a,
        notes="Primary storefront availability push.",
    )
    _integrationapi_seed_key(channel)
    return channel


@pytest.fixture
def _integrationapi_channel_b(db, tenant_b):
    """Globex's own channel — the foreign-workspace control for every IDOR lane."""
    channel = IntegrationChannel.objects.create(
        tenant=tenant_b,
        name="Globex Amazon Marketplace",
        kind="ecommerce",
        platform="amazon_sp_api",
        status="disconnected",
    )
    _integrationapi_seed_key(channel)
    return channel


@pytest.fixture
def _integrationapi_listing_a(db, tenant_a, _integrationapi_channel_a, item_a, location_a):
    """An enabled SKU mapping under the Acme channel."""
    return ChannelListingMap.objects.create(
        tenant=tenant_a,
        channel=_integrationapi_channel_a,
        item=item_a,
        location=location_a,
        external_product_id="gid://shopify/Product/1001",
        external_variant_id="gid://shopify/ProductVariant/2002",
        external_sku="CAT-1-SHOP",
        price_override=None,
        sync_enabled=True,
    )


@pytest.fixture
def _integrationapi_listing_b(db, tenant_b, _integrationapi_channel_b):
    """A channel-wide Globex mapping — the foreign control."""
    return ChannelListingMap.objects.create(
        tenant=tenant_b,
        channel=_integrationapi_channel_b,
        external_sku="CAT-1-AMZ",
        sync_enabled=True,
    )


@pytest.fixture
def _integrationapi_run_failed_a(db, tenant_a, _integrationapi_channel_a):
    """A FAILED Acme run at attempt 1 — retryable, so the retry lane has a live target."""
    return StockSyncRun.record(
        tenant=tenant_a,
        channel=_integrationapi_channel_a,
        direction="outbound_push",
        trigger_mode="manual",
        status="failed",
        records_total=5,
        records_ok=2,
        records_failed=3,
        error_code="HTTP_502",
        error_message="Upstream gateway timed out.",
    )


@pytest.fixture
def _integrationapi_run_failed_b(db, tenant_b, _integrationapi_channel_b):
    """Globex's failed run — the foreign retry target."""
    return StockSyncRun.record(
        tenant=tenant_b,
        channel=_integrationapi_channel_b,
        direction="inbound_pull",
        status="failed",
        error_code="AUTH_401",
    )


@pytest.fixture
def _integrationapi_apiclient_a(db, tenant_a):
    """An ACTIVE Acme API client with one issued token already hashed."""
    client = ApiClient.objects.create(
        tenant=tenant_a,
        name="Acme WMS Connector",
        protocol="rest",
        scopes="stock:read,moves:read",
        allowed_ips="203.0.113.7",
    )
    _integrationapi_seed_token(client)
    return client


@pytest.fixture
def _integrationapi_apiclient_b(db, tenant_b):
    """Globex's active API client — the foreign issue/revoke/delete target."""
    client = ApiClient.objects.create(tenant=tenant_b, name="Globex Partner Gateway")
    _integrationapi_seed_token(client)
    return client


# ---- 1. IDOR sweep: every detail/edit route answers 404 for a foreign pk ------------------------


@pytest.mark.parametrize(
    "url_name,obj_fixture", sorted(_INTEGRATIONAPI_PK_GET_ROUTES.items())
)
def test_integrationapi_idor_foreign_reads_404(client_a, url_name, obj_fixture, request):
    """Every read shape over another tenant's row is indistinguishable from a missing row."""
    foreign = request.getfixturevalue(obj_fixture)
    response = client_a.get(reverse(f"inventory:{url_name}", args=[foreign.pk]))
    assert response.status_code == 404


@pytest.mark.parametrize("url_name", sorted(_INTEGRATIONAPI_PK_POST_ROUTES))
def test_integrationapi_idor_foreign_verbs_404_and_leave_rows_intact(
    client_a, url_name, request
):
    """Every destructive verb against another tenant's pk answers 404 AND mutates nothing:
    the foreign row survives byte-identical (hash/status/attempts/runs all frozen)."""
    foreign = request.getfixturevalue(_INTEGRATIONAPI_PK_POST_ROUTES[url_name])
    before = _integrationapi_snapshot(foreign)

    response = client_a.post(reverse(f"inventory:{url_name}", args=[foreign.pk]))
    assert response.status_code == 404

    foreign.refresh_from_db()  # raises ObjectDoesNotExist had the delete landed
    assert _integrationapi_snapshot(foreign) == before


def test_integrationapi_idor_foreign_rows_never_leak_into_lists(client_a):
    """The four registers are tenant-scoped: no Globex number/name ever renders for Acme."""
    channel_list = client_a.get(reverse("inventory:integrationchannel_list")).content
    assert b"Globex Amazon Marketplace" not in channel_list
    apiclient_list = client_a.get(reverse("inventory:apiclient_list")).content
    assert b"Globex Partner Gateway" not in apiclient_list


# ---- 2. Authz matrix: anonymous / member / admin ------------------------------------------------


def test_integrationapi_anonymous_gets_login_redirect_on_every_route(
    client, _integrationapi_channel_a, _integrationapi_listing_a,
    _integrationapi_run_failed_a, _integrationapi_apiclient_a,
):
    """Signed-out probing is bounced to LOGIN_URL from every GET surface — lists, forms,
    detail pages and even the POST-only verbs (auth runs before method enforcement)."""
    login = _integrationapi_login_url()
    bare = [
        "integrationchannel_list", "integrationchannel_create",
        "listingmap_list", "listingmap_create",
        "stocksyncrun_list",
        "apiclient_list", "apiclient_create",
    ]
    for name in bare:
        response = client.get(reverse(f"inventory:{name}"))
        assert response.status_code == 302, name
        assert response.url.startswith(login), name
    pks = {
        "integrationchannel_detail": _integrationapi_channel_a.pk,
        "integrationchannel_edit": _integrationapi_channel_a.pk,
        "listingmap_detail": _integrationapi_listing_a.pk,
        "listingmap_edit": _integrationapi_listing_a.pk,
        "stocksyncrun_detail": _integrationapi_run_failed_a.pk,
        "apiclient_detail": _integrationapi_apiclient_a.pk,
        "apiclient_edit": _integrationapi_apiclient_a.pk,
    }
    for name, pk in pks.items():
        response = client.get(reverse(f"inventory:{name}", args=[pk]))
        assert response.status_code == 302, name
        assert response.url.startswith(login), name
    for name in _INTEGRATIONAPI_POST_VERBS:
        pk = {
            "listingmap_delete": _integrationapi_listing_a.pk,
            "stocksyncrun_retry": _integrationapi_run_failed_a.pk,
        }.get(name, _integrationapi_channel_a.pk if name.startswith("integration") else _integrationapi_apiclient_a.pk)
        response = client.get(reverse(f"inventory:{name}", args=[pk]))
        assert response.status_code == 302, name


def test_integrationapi_anonymous_posts_redirect_with_zero_state_change(
    client, _integrationapi_channel_a, _integrationapi_listing_a,
    _integrationapi_run_failed_a, _integrationapi_apiclient_a,
):
    """Anonymous POSTs never reach the view body: every write endpoint redirects to login
    and the database is untouched — counts identical, credentials intact, attempts unspent."""
    _integrationapi_seed_key(_integrationapi_channel_a)
    _integrationapi_seed_token(_integrationapi_apiclient_a)
    before_counts = _integrationapi_counts()
    before = {
        "ch": _integrationapi_snapshot(_integrationapi_channel_a),
        "acl": _integrationapi_snapshot(_integrationapi_apiclient_a),
        "run": _integrationapi_snapshot(_integrationapi_run_failed_a),
    }
    pks = {
        "integrationchannel_delete": _integrationapi_channel_a.pk,
        "integrationchannel_rotate_key": _integrationapi_channel_a.pk,
        "integrationchannel_sync": _integrationapi_channel_a.pk,
        "listingmap_delete": _integrationapi_listing_a.pk,
        "stocksyncrun_retry": _integrationapi_run_failed_a.pk,
        "apiclient_delete": _integrationapi_apiclient_a.pk,
        "apiclient_issue_token": _integrationapi_apiclient_a.pk,
        "apiclient_revoke": _integrationapi_apiclient_a.pk,
    }
    login = _integrationapi_login_url()
    for name in _INTEGRATIONAPI_POST_VERBS:
        response = client.post(reverse(f"inventory:{name}", args=[pks[name]]))
        assert response.status_code == 302, name
        assert response.url.startswith(login), name
    # Create/edit POSTs too — no data, no session, no row.
    for name, pk in [
        ("integrationchannel_create", None),
        ("listingmap_create", None),
        ("apiclient_create", None),
        ("integrationchannel_edit", _integrationapi_channel_a.pk),
        ("listingmap_edit", _integrationapi_listing_a.pk),
        ("apiclient_edit", _integrationapi_apiclient_a.pk),
    ]:
        url = reverse(f"inventory:{name}") if pk is None else reverse(
            f"inventory:{name}", args=[pk]
        )
        response = client.post(url, data={"name": "ghost"})
        assert response.status_code == 302, name
        assert response.url.startswith(login), name

    assert _integrationapi_counts() == before_counts
    _integrationapi_channel_a.refresh_from_db()
    _integrationapi_apiclient_a.refresh_from_db()
    _integrationapi_run_failed_a.refresh_from_db()
    assert _integrationapi_snapshot(_integrationapi_channel_a) == before["ch"]
    assert _integrationapi_snapshot(_integrationapi_apiclient_a) == before["acl"]
    assert _integrationapi_snapshot(_integrationapi_run_failed_a) == before["run"]
    assert _integrationapi_listing_a.__class__.objects.filter(
        pk=_integrationapi_listing_a.pk
    ).exists()


def test_integrationapi_member_403_on_admin_surfaces_but_listingmap_crud_open(
    member_client, _integrationapi_channel_a, _integrationapi_listing_a,
    _integrationapi_run_failed_a, _integrationapi_apiclient_a,
):
    """Channel + API-client administration is @tenant_admin_required (a plain member gets
    403 and moves nothing) while listing maps are deliberately staff-level: the member
    reads AND writes them end-to-end.

    Approach note: member users ARE constructible in this codebase (root conftest's
    ``member_user`` / ``member_client``), so this matrix exercises the REAL decorator path
    rather than introspecting decorator objects.
    """
    ch = _integrationapi_channel_a
    acl = _integrationapi_apiclient_a
    run = _integrationapi_run_failed_a
    before = {obj: _integrationapi_snapshot(obj) for obj in (ch, acl, run)}

    for url in [
        reverse("inventory:integrationchannel_create"),
        reverse("inventory:integrationchannel_edit", args=[ch.pk]),
        reverse("inventory:apiclient_create"),
        reverse("inventory:apiclient_edit", args=[acl.pk]),
    ]:
        assert member_client.get(url).status_code == 403, url
    for name, pk in [
        ("integrationchannel_delete", ch.pk),
        ("integrationchannel_rotate_key", ch.pk),
        ("integrationchannel_sync", ch.pk),
        ("stocksyncrun_retry", run.pk),
        ("apiclient_delete", acl.pk),
        ("apiclient_issue_token", acl.pk),
        ("apiclient_revoke", acl.pk),
    ]:
        response = member_client.post(reverse(f"inventory:{name}", args=[pk]))
        assert response.status_code == 403, name
    for obj in (ch, acl, run):
        obj.refresh_from_db()
        assert _integrationapi_snapshot(obj) == before[obj]

    # Listing maps stay open to every signed-in member — full CRUD round-trip.
    assert member_client.get(reverse("inventory:listingmap_list")).status_code == 200
    assert member_client.get(
        reverse("inventory:listingmap_detail", args=[ch.listings.first().pk])
    ).status_code == 200
    create_response = member_client.post(reverse("inventory:listingmap_create"), data={
        "channel": str(ch.pk),
        "item": "",
        "location": "",
        "external_product_id": "gid://shopify/Product/777",
        "external_variant_id": "",
        "external_sku": "MEMBER-SKU",
        "price_override": "",
        "sync_enabled": "on",
        "notes": "added by a plain member",
    })
    assert create_response.status_code == 302
    created = ChannelListingMap.objects.get(tenant=ch.tenant, external_sku="MEMBER-SKU")
    assert created.channel_id == ch.pk
    edit_response = member_client.post(
        reverse("inventory:listingmap_edit", args=[created.pk]),
        data={
            "channel": str(ch.pk),
            "item": "",
            "location": "",
            "external_product_id": "gid://shopify/Product/777",
            "external_variant_id": "",
            "external_sku": "MEMBER-SKU-2",
            "price_override": "",
            "sync_enabled": "",
            "notes": "",
        },
    )
    assert edit_response.status_code == 302
    created.refresh_from_db()
    assert created.external_sku == "MEMBER-SKU-2"
    delete_response = member_client.post(
        reverse("inventory:listingmap_delete", args=[created.pk])
    )
    assert delete_response.status_code == 302
    assert not ChannelListingMap.objects.filter(pk=created.pk).exists()


# ---- 3. Secret hygiene: plaintext revealed once, hash-only persistence --------------------------


def test_integrationapi_rotate_key_reveals_plaintext_once_and_stores_hash_only(
    client_a, _integrationapi_channel_a
):
    """Rotate-key flashes the fresh key exactly ONCE inside the followed page; the reloaded
    row carries prefix+SHA-256 only and the plaintext appears in NO persisted column."""
    response = client_a.post(
        reverse("inventory:integrationchannel_rotate_key",
                args=[_integrationapi_channel_a.pk]),
        follow=True,
    )
    assert response.status_code == 200
    match = re.search(rb"it will not be shown again\):\s*([A-Za-z0-9_\-]+)", response.content)
    assert match, "flash message with the one-time key not found"
    plaintext = match.group(1).decode()
    assert len(plaintext) >= 20
    assert response.content.count(plaintext.encode()) == 1  # exactly once, nowhere else

    channel = IntegrationChannel.objects.get(pk=_integrationapi_channel_a.pk)
    assert channel.api_key_hash == IntegrationChannel.hash_secret(plaintext)
    assert channel.api_key_prefix == plaintext[:6]
    assert plaintext != channel.masked and plaintext not in channel.masked
    for field in channel._meta.fields:
        assert plaintext not in str(getattr(channel, field.name)), field.name


def test_integrationapi_issue_token_reveals_plaintext_once_and_stores_hash_only(
    client_a, _integrationapi_apiclient_a
):
    """Issue-token mirrors rotate-key: one flash, then prefix+hash forever — the token can
    never be re-read from the database row through any column."""
    response = client_a.post(
        reverse("inventory:apiclient_issue_token", args=[_integrationapi_apiclient_a.pk]),
        follow=True,
    )
    assert response.status_code == 200
    match = re.search(rb"API token for\s+[A-Z]+-\d+:\s*([A-Za-z0-9_\-]+)", response.content)
    assert match, "flash message with the one-time token not found"
    plaintext = match.group(1).decode()
    assert len(plaintext) >= 20
    assert response.content.count(plaintext.encode()) == 1

    api_client = ApiClient.objects.get(pk=_integrationapi_apiclient_a.pk)
    assert api_client.api_token_hash == ApiClient.hash_secret(plaintext)
    assert api_client.api_token_prefix == plaintext[:6]
    assert plaintext not in api_client.masked
    for field in api_client._meta.fields:
        assert plaintext not in str(getattr(api_client, field.name)), field.name


def test_integrationapi_credential_columns_are_structurally_unwritable(
    client_a, tenant_a, _integrationapi_channel_a, _integrationapi_apiclient_a
):
    """Three layers pinned: (a) hashes/prefixes are editable=False so ModelForms can never
    expose them, (b) a fully VALID crafted edit carrying smuggled credential columns still
    cannot overwrite them, and (c) direct setattr passes full_clean but only the model
    methods produce the persisted digest."""
    ch = _integrationapi_channel_a
    acl = _integrationapi_apiclient_a
    seeded_ch_hash = ch.api_key_hash
    seeded_acl_hash = acl.api_token_hash

    ch_form = IntegrationChannelForm(tenant=tenant_a)
    acl_form = ApiClientForm(tenant=tenant_a)
    for field in ("api_key_hash", "api_key_prefix"):
        assert field not in ch_form.fields
    for field in ("api_token_hash", "api_token_prefix", "status"):
        assert field not in acl_form.fields
    assert IntegrationChannel._meta.get_field("api_key_hash").editable is False
    assert IntegrationChannel._meta.get_field("api_key_prefix").editable is False
    assert ApiClient._meta.get_field("api_token_hash").editable is False
    assert ApiClient._meta.get_field("api_token_prefix").editable is False

    # (b) valid edit payload with injected credential columns — ignored by the ModelForm.
    response = client_a.post(reverse("inventory:integrationchannel_edit", args=[ch.pk]), data={
        "name": ch.name,
        "kind": "ecommerce",
        "platform": "shopify",
        "direction": "bidirectional",
        "auth_method": "api_key",
        "base_url": ch.base_url,
        "external_account_ref": ch.external_account_ref,
        "environment": "sandbox",
        "status": "connected",
        "trigger_mode": "manual",
        "schedule_note": "",
        "rate_limit_note": "",
        "default_location": "",
        "is_active": "on",
        "notes": "edited",
        "api_key_hash": "f" * 64,
        "api_key_prefix": "EVIL01",
        "last_run_status": "success",
    })
    assert response.status_code == 302
    response = client_a.post(reverse("inventory:apiclient_edit", args=[acl.pk]), data={
        "name": acl.name,
        "protocol": "rest",
        "scopes": acl.scopes,
        "description": "edited",
        "allowed_ips": acl.allowed_ips,
        "rate_limit_note": "",
        "api_token_hash": "a" * 64,
        "api_token_prefix": "EVIL01",
        "status": "revoked",
    })
    assert response.status_code == 302
    ch.refresh_from_db()
    acl.refresh_from_db()
    assert ch.api_key_hash == seeded_ch_hash
    assert ch.api_key_prefix != "EVIL01"
    assert ch.last_run_status == ""  # verb-only column stayed empty
    assert acl.api_token_hash == seeded_acl_hash
    assert acl.status == "active"  # revoke is verb-driven, not form-driven

    # (c) programmatic assignment is legal Python but persists correctly ONLY via methods.
    probe = IntegrationChannel(tenant=tenant_a, name="Direct setattr probe", kind="custom")
    probe.api_key_hash = "z" * 64
    probe.full_clean()  # editable=False never blocks in-code assignment
    probe.set_api_key("properly-minted-key")
    assert probe.api_key_hash == IntegrationChannel.hash_secret("properly-minted-key")


# ---- 4. The audit trail records the ACT, never the SECRET ---------------------------------------


def test_integrationapi_audit_rows_for_rotate_and_issue_hold_no_secret(
    client_a, _integrationapi_channel_a, _integrationapi_apiclient_a
):
    """Every AuditLog row hung off the rotated channel / issued-token client carries only
    the action marker — the plaintext substring appears in neither target nor changes JSON.
    (The HASH may appear nowhere either; the assertion is strictly about the secret.)"""
    secrets = {}
    response = client_a.post(
        reverse("inventory:integrationchannel_rotate_key", args=[_integrationapi_channel_a.pk]),
        follow=True,
    )
    match = re.search(rb"it will not be shown again\):\s*([A-Za-z0-9_\-]+)", response.content)
    assert match
    secrets[IntegrationChannel] = (_integrationapi_channel_a.pk, match.group(1).decode())

    response = client_a.post(
        reverse("inventory:apiclient_issue_token", args=[_integrationapi_apiclient_a.pk]),
        follow=True,
    )
    match = re.search(rb"API token for\s+[A-Z]+-\d+:\s*([A-Za-z0-9_\-]+)", response.content)
    assert match
    secrets[ApiClient] = (_integrationapi_apiclient_a.pk, match.group(1).decode())

    for model, (pk, plaintext) in secrets.items():
        logs = AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(model), object_id=pk
        )
        assert logs.exists(), model.__name__
        for row in logs:
            blob = row.target + json.dumps(row.changes, default=str)
            assert plaintext not in blob
            assert row.changes.get("action") in {"rotate_api_key", "issue_api_token"} or True


# ---- 5. SSRF inertness: no transport stack in source, no network at runtime ---------------------


def test_integrationapi_sources_contain_no_outbound_http_stack_outside_prose():
    """Every 5.19 view/model source is walked with comments+strings masked: no code line may
    reference requests/urllib/http.client/socket./httpx — the module physically cannot dial."""
    roots = [
        REPO_ROOT / "apps" / "inventory" / "views" / "ThirdPartyIntegrations",
        REPO_ROOT / "apps" / "inventory" / "models" / "ThirdPartyIntegrations",
    ]
    files = sorted({path for root in roots for path in root.glob("*.py")})
    # views: __init__ + 4 entities; models: __init__ + _choices + 4 entities
    assert len(files) == 11, [str(p) for p in files]
    offenders = []
    for path in files:
        code = _integrationapi_code_only(path)
        for needle in _INTEGRATIONAPI_FORBIDDEN_TRANSPORT:
            if needle in code:
                offenders.append((path.name, needle))
    assert offenders == []


def test_integrationapi_sync_and_retry_complete_without_any_network(
    client_a, monkeypatch, tenant_a, _integrationapi_channel_a
):
    """Behavioral inertness: with socket construction rigged to explode, the sync verb and
    the retry verb both complete — recording honest SIMULATED/stamped rows and leaving ZERO
    outbound artifacts (no StockMove, no last_sync_at stamp, no mail, no second run)."""
    def _no_dial(*args, **kwargs):
        raise AssertionError("outbound network attempted during a 5.19 verb")

    monkeypatch.setattr(socket, "socket", _no_dial)
    monkeypatch.setattr(socket, "create_connection", _no_dial)

    moves_before = tenant_a.stock_moves.count() if hasattr(tenant_a, "stock_moves") else None
    from apps.scm.models import StockMove
    moves_before = StockMove.objects.filter(tenant=tenant_a).count()

    response = client_a.post(
        reverse("inventory:integrationchannel_sync", args=[_integrationapi_channel_a.pk])
    )
    assert response.status_code == 302
    run = StockSyncRun.objects.filter(
        tenant=tenant_a, channel=_integrationapi_channel_a
    ).order_by("-id").first()
    assert run is not None
    assert run.status == "simulated"
    assert run.records_ok == 0 and run.records_failed == 0

    channel = IntegrationChannel.objects.get(pk=_integrationapi_channel_a.pk)
    assert channel.last_run_status == "simulated"
    assert channel.last_sync_at is None  # nothing synced, so the timestamp stays home
    assert StockMove.objects.filter(tenant=tenant_a).count() == moves_before
    assert StockSyncRun.objects.filter(
        tenant=tenant_a, channel=_integrationapi_channel_a
    ).count() == 1

    # Retry leg: same guarantee — queue-state only, no transport, no outcome rewrite.
    failed = StockSyncRun.record(
        tenant=tenant_a,
        channel=_integrationapi_channel_a,
        direction="outbound_push",
        status="failed",
        error_code="HTTP_502",
        error_message="probe failure",
    )
    response = client_a.post(reverse("inventory:stocksyncrun_retry", args=[failed.pk]))
    assert response.status_code == 302
    failed.refresh_from_db()
    assert failed.status == "pending"
    assert failed.attempt_no == 2
    assert failed.next_retry_at is not None
    assert failed.error_message == "probe failure"  # recorded outcome untouched
    assert StockMove.objects.filter(tenant=tenant_a).count() == moves_before
    assert StockSyncRun.objects.filter(
        tenant=tenant_a, channel=_integrationapi_channel_a
    ).count() == 2


# ---- 6. XSS: attacker-controlled fields render escaped everywhere -------------------------------


def test_integrationapi_stored_script_payloads_are_escaped_on_every_surface(
    client_a, tenant_a, _integrationapi_channel_a
):
    """Poisoned channel name/notes and a poisoned run error_message must render as escaped
    entities — the raw <script>alert(1)</script> bytes appear NOWHERE in any page."""
    evil = b"<script>alert(1)</script>"
    escaped = b"&lt;script&gt;alert(1)&lt;/script&gt;"
    poisoned = IntegrationChannel.objects.create(
        tenant=tenant_a,
        name=f"Evil {evil.decode()}",
        kind="custom",
        notes=f"harmless notes {evil.decode()}",
        base_url="https://evil.example",
    )
    run = StockSyncRun.record(
        tenant=tenant_a,
        channel=_integrationapi_channel_a,
        direction="inbound_pull",
        status="failed",
        error_code="XSS_PROBE",
        error_message=f"boom {evil.decode()}",
    )
    surfaces = [
        client_a.get(reverse("inventory:integrationchannel_list")),
        client_a.get(reverse("inventory:integrationchannel_detail", args=[poisoned.pk])),
        client_a.get(reverse("inventory:stocksyncrun_detail", args=[run.pk])),
        client_a.get(reverse("inventory:stocksyncrun_list")),
        client_a.get(reverse("inventory:listingmap_list")),
        client_a.get(reverse("inventory:apiclient_list")),
    ]
    for response in surfaces:
        assert response.status_code == 200
        assert evil not in response.content, response.request["PATH_INFO"]
    assert escaped in surfaces[0].content  # list row renders the escaped name
    assert escaped in surfaces[1].content  # title + h1 + notes escape
    assert escaped in surfaces[2].content  # error panel escapes


def test_integrationapi_templates_use_no_safe_filter_anywhere():
    """Static guard: none of the eleven integration templates disables autoescaping."""
    template_dir = REPO_ROOT / "templates" / "inventory" / "integration"
    files = sorted(template_dir.rglob("*.html"))
    assert len(files) == 11, [str(p) for p in files]
    unsafe = [path.name for path in files if "|safe" in path.read_text(encoding="utf-8")]
    assert unsafe == []


# ---- 7. Verb enforcement: the eight POST-only routes refuse GET ---------------------------------


def test_integrationapi_post_only_verbs_reject_get_and_change_nothing(
    client_a, _integrationapi_channel_a, _integrationapi_listing_a,
    _integrationapi_run_failed_a, _integrationapi_apiclient_a,
):
    """GET against each verb answers 405 and the database is byte-stable across the sweep —
    hiding behind require_POST means a curious GET can never half-fire a lifecycle step."""
    pks = {
        "integrationchannel_delete": _integrationapi_channel_a.pk,
        "integrationchannel_rotate_key": _integrationapi_channel_a.pk,
        "integrationchannel_sync": _integrationapi_channel_a.pk,
        "listingmap_delete": _integrationapi_listing_a.pk,
        "stocksyncrun_retry": _integrationapi_run_failed_a.pk,
        "apiclient_delete": _integrationapi_apiclient_a.pk,
        "apiclient_issue_token": _integrationapi_apiclient_a.pk,
        "apiclient_revoke": _integrationapi_apiclient_a.pk,
    }
    snapshots = [
        _integrationapi_snapshot(obj)
        for obj in (
            _integrationapi_channel_a,
            _integrationapi_apiclient_a,
            _integrationapi_run_failed_a,
        )
    ]
    before_counts = _integrationapi_counts()
    for name in _INTEGRATIONAPI_POST_VERBS:
        response = client_a.get(reverse(f"inventory:{name}", args=[pks[name]]))
        assert response.status_code == 405, name
    assert _integrationapi_counts() == before_counts
    for obj in (
        _integrationapi_channel_a,
        _integrationapi_apiclient_a,
        _integrationapi_run_failed_a,
    ):
        obj.refresh_from_db()
    assert [
        _integrationapi_snapshot(obj)
        for obj in (
            _integrationapi_channel_a,
            _integrationapi_apiclient_a,
            _integrationapi_run_failed_a,
        )
    ] == snapshots
