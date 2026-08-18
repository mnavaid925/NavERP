"""SCM 4.19 Integration & API Gateway — ISOLATION AND HARDENING.

This lane asserts the things that are invisible when they work and expensive when they do not.

* **Multi-tenant isolation.** A tenant-A session handed a tenant-B pk gets a 404 on every detail,
  edit and verb route in the sub-module; A's five list/report pages never carry B's rows; the two
  filter dropdowns (``endpoints`` / ``subscriptions``) never offer B's records; and a crafted POST
  naming B's pk in an FK field comes back as a FIELD ERROR rather than a save. The two highest-value
  cases here are the ones the views re-scope by hand: ``integrationmessage_detail``'s ``ack_message``
  and ``integrationendpoint_detail``'s ``recent_messages`` panel are BOTH keyed on
  ``tenant=request.tenant`` rather than trusted from the relation, so a row written before the FK
  guard existed (or by a raw import that skipped validation) cannot surface another workspace's
  traffic through a reverse accessor.
* **Auth.** Anonymous is redirected to ``/login/`` on all 17 routes and changes nothing. The gate
  asymmetry is asserted in BOTH directions, because it is the easy thing to get backwards: on the
  ENDPOINT only ``delete`` and ``rotate_credential`` are ``@tenant_admin_required`` (create and edit
  are plain ``@login_required`` and a member must still be able to use them); on the SUBSCRIPTION
  create/edit/delete/rotate_secret are ALL admin-gated; and the two log verbs
  (``integrationmessage_reprocess`` / ``webhookdelivery_retry``) are deliberately NOT. CSRF is
  enforced on every POST.
* **Secrets (L20/L25).** Neither rotate flash carries the plaintext — it rides a pop-once, pk-scoped
  session key and surfaces exactly once as ``plaintext_once``. The stored digest is never rendered,
  the audit row records only ``{"credential": "rotated"}`` / ``{"signing_secret": "rotated"}``, and
  the plaintext is nowhere in the database.
* **Negative input.** A junk query param answers 200 rather than 500 on every page in the
  sub-module (L11), and every hand-typed number, URL and header blob comes back as a form error
  rather than a 500. The page-size and page-past-the-end guards (L9) are asserted once, in
  ``test_integration_views.py``, which owns pagination for all five lists.
* **Absent prerequisites are REJECTED, never fallen through (L35).** ``reprocess`` refuses the two
  blocked statuses and a second press; ``retry`` refuses a non-retryable outcome and exhausts rather
  than inventing a ninth slot.
* **Absent ROUTES are asserted absent.** ``IntegrationMessage`` and ``WebhookDelivery`` are
  append-only: ``reverse()`` on a create/edit/delete name for either must raise ``NoReverseMatch``,
  neither has an importable ModelForm, and no outbound-transport module is imported anywhere under
  ``apps/scm``.

**Every refusal is paired with the POSITIVE path (L44)**, so a guard that merely broke the feature
fails this file instead of quietly passing it.

NAMING: every test function is ``test_integration_*`` and every module-level name (helper, constant,
fixture) is ``_integration_*`` — ``test_suite_hygiene.py`` fails on a module-level name defined
twice, and the prefix keeps the next sub-module's appended helpers from shadowing these.

TIME BASIS (L16): every moment is derived from ``timezone.now()``, the same basis the fixtures,
``occurred_at``, ``triggered_at`` and ``webhookdelivery_retry``'s ``next_attempt_at`` all read —
never ``datetime.date.today()``.
"""
import datetime
import pathlib
import re

import pytest
from django.test import Client
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# =================================================================================================
# Helpers and payloads
# =================================================================================================
def _integration_flash(response):
    """Every flashed message on a RENDERED response, lowercased."""
    return [str(message).lower() for message in response.context["messages"]]


def _integration_endpoint_payload(**over):
    """A minimally valid ``IntegrationEndpointForm`` POST body.

    Every choice column is spelled out because a ``CharField`` with ``choices`` and a model default
    is still ``required=True`` on a BOUND form — the default applies to the model, not to the wire.
    ``is_active`` is ``"on"`` (a checked checkbox); the four FK slots are empty strings, which is how
    "not chosen" is spelled for a ``ModelChoiceField``.
    """
    data = {
        "name": "Crafted connection",
        "category": "custom",
        "system": "",
        "direction": "bidirectional",
        "transport": "api_rest",
        "auth_method": "none",
        "endpoint_url": "",
        "external_account_ref": "",
        "partner_party": "",
        "logistics_client": "",
        "location": "",
        "spec_document": "",
        "interchange_id": "",
        "interchange_qualifier": "",
        "device_identifier": "",
        "trigger_mode": "manual",
        "schedule_note": "",
        "environment": "sandbox",
        "lifecycle_stage": "setup",
        "status": "disconnected",
        "is_active": "on",
        "notes": "",
    }
    data.update(over)
    return data


def _integration_subscription_payload(**over):
    """A minimally valid ``WebhookSubscriptionForm`` POST body — a flat ``{str: str}`` header map."""
    data = {
        "name": "Crafted rule",
        "trigger_entity": "shipment",
        "trigger_event": "created",
        "target_url": "https://hooks.example.com/naverp/crafted",
        "payload_format": "json",
        "filter_expression": "",
        "include_fields": "",
        "headers": '{"X-Source": "NavERP"}',
        "auto_disable_threshold": "8",
        "is_active": "on",
        "description": "",
    }
    data.update(over)
    return data


def _integration_bulk_endpoints(tenant, count, prefix="Bulk connection"):
    """``count`` extra endpoints in ``tenant``. Each carries its own name — ``unique_together
    ("tenant", "name")`` — and they sort after the fixtures' names so page 2 is deterministic."""
    from apps.scm.models import IntegrationEndpoint
    return [IntegrationEndpoint.objects.create(
        tenant=tenant, name=f"{prefix} {index:03d}", category="custom",
        transport="api_rest", status="disconnected") for index in range(count)]


def _integration_bulk_messages(tenant, endpoint, count, **over):
    """``count`` extra exchange rows on one endpoint — nothing constrains the pair."""
    from apps.scm.models import IntegrationMessage
    now = timezone.now()
    fields = {"direction": "outbound", "document_type": "edi_850", "status": "sent"}
    fields.update(over)
    return [IntegrationMessage.objects.create(
        tenant=tenant, endpoint=endpoint,
        occurred_at=now - datetime.timedelta(minutes=index + 1),
        control_number=f"BULK{index:05d}", **fields) for index in range(count)]


def _integration_bulk_deliveries(tenant, subscription, count):
    """``count`` extra attempt rows against one rule — ``WebhookDelivery`` has no unique key."""
    from apps.scm.models import WebhookDelivery
    now = timezone.now()
    return [WebhookDelivery.objects.create(
        tenant=tenant, subscription=subscription, event="shipment.created", status="success",
        attempt_no=1, response_code=200,
        triggered_at=now - datetime.timedelta(minutes=index + 1)) for index in range(count)]


#: Every 4.19 page that takes no pk — the anonymous sweep and the junk-param sweep both walk it.
_INTEGRATION_ANON_PAGES = [
    "scm:integrationendpoint_list",
    "scm:integrationendpoint_erp_list",
    "scm:integrationendpoint_ecommerce_list",
    "scm:integrationendpoint_iot_list",
    "scm:integrationendpoint_edi_list",
    "scm:integrationendpoint_create",
    "scm:integrationmessage_list",
    "scm:integration_exceptions",
    "scm:webhooksubscription_list",
    "scm:webhooksubscription_create",
    "scm:webhookdelivery_list",
]

#: ``(url name, fixture)`` for every pk-taking GET page.
_INTEGRATION_ANON_PK_PAGES = [
    ("scm:integrationendpoint_detail", "integration_endpoint_a"),
    ("scm:integrationendpoint_edit", "integration_endpoint_a"),
    ("scm:integrationmessage_detail", "integration_message_a"),
    ("scm:webhooksubscription_detail", "integration_subscription_a"),
    ("scm:webhooksubscription_edit", "integration_subscription_a"),
    ("scm:webhookdelivery_detail", "integration_delivery_a"),
]

#: Every POST-only route (``@require_POST``). A GET must be a 405 — a link-prefetcher following one
#: of these would be deleting connections and rotating live credentials.
_INTEGRATION_POST_ONLY_ROUTES = [
    ("scm:integrationendpoint_delete", "integration_endpoint_a"),
    ("scm:integrationendpoint_rotate_credential", "integration_endpoint_a"),
    ("scm:integrationmessage_reprocess", "integration_message_a"),
    ("scm:webhooksubscription_delete", "integration_subscription_a"),
    ("scm:webhooksubscription_rotate_secret", "integration_subscription_a"),
    ("scm:webhookdelivery_retry", "integration_delivery_a"),
]

#: Every pk GET route a tenant-A session must 404 on when handed a tenant-B pk.
_INTEGRATION_CROSS_TENANT_GETS = [
    ("scm:integrationendpoint_detail", "integration_endpoint_b"),
    ("scm:integrationendpoint_edit", "integration_endpoint_b"),
    ("scm:integrationmessage_detail", "integration_message_b"),
    ("scm:webhooksubscription_detail", "integration_subscription_b"),
    ("scm:webhooksubscription_edit", "integration_subscription_b"),
    ("scm:webhookdelivery_detail", "integration_delivery_b"),
]

#: Every POST route driven with a tenant-B pk from a tenant-A ADMIN session — admin, so the four
#: ``@tenant_admin_required`` verbs reach their ``get_object_or_404`` rather than stopping at 403.
_INTEGRATION_CROSS_TENANT_POSTS = [
    ("scm:integrationendpoint_delete", "integration_endpoint_b"),
    ("scm:integrationendpoint_rotate_credential", "integration_endpoint_b"),
    ("scm:integrationmessage_reprocess", "integration_message_b"),
    ("scm:webhooksubscription_delete", "integration_subscription_b"),
    ("scm:webhooksubscription_rotate_secret", "integration_subscription_b"),
    ("scm:webhookdelivery_retry", "integration_delivery_b"),
]

#: The four ``@tenant_admin_required`` POST verbs, with the fixture each acts on.
_INTEGRATION_ADMIN_ONLY_POSTS = [
    ("scm:integrationendpoint_delete", "integration_endpoint_a"),
    ("scm:integrationendpoint_rotate_credential", "integration_endpoint_a"),
    ("scm:webhooksubscription_delete", "integration_subscription_a"),
    ("scm:webhooksubscription_rotate_secret", "integration_subscription_a"),
]

#: Everything the five list/report pages must survive in a hand-edited query string. The assertion
#: is 200, never a 500 (L11/L9). ``lifecycle_stage`` is the GET param whose CONTEXT key is
#: ``lifecycle_choices`` — junk on it must narrow, not raise.
_INTEGRATION_JUNK_QUERIES = [
    ("scm:integrationendpoint_list", {"category": "abc"}),
    ("scm:integrationendpoint_list", {"category": "²"}),
    ("scm:integrationendpoint_list", {"system": "banana"}),
    ("scm:integrationendpoint_list", {"direction": "sideways"}),
    ("scm:integrationendpoint_list", {"transport": "carrier-pigeon"}),
    ("scm:integrationendpoint_list", {"status": "banana"}),
    ("scm:integrationendpoint_list", {"status": "True"}),
    ("scm:integrationendpoint_list", {"environment": "lol"}),
    ("scm:integrationendpoint_list", {"lifecycle_stage": "lol"}),
    ("scm:integrationendpoint_list", {"page": "abc"}),
    ("scm:integrationendpoint_list", {"page": "0"}),
    ("scm:integrationendpoint_list", {"page": "-1"}),
    ("scm:integrationendpoint_list", {"page": "999"}),
    ("scm:integrationendpoint_list", {"q": "'); DROP TABLE scm_integrationendpoint;--"}),
    ("scm:integrationendpoint_erp_list", {"category": "abc"}),
    ("scm:integrationendpoint_erp_list", {"page": "999"}),
    ("scm:integrationendpoint_iot_list", {"status": "banana"}),
    ("scm:integrationendpoint_edi_list", {"lifecycle_stage": "³"}),
    ("scm:integrationendpoint_ecommerce_list", {"q": "%%"}),
    ("scm:integrationmessage_list", {"endpoint": "abc"}),
    ("scm:integrationmessage_list", {"endpoint": "²"}),
    ("scm:integrationmessage_list", {"endpoint": "999999999999999999999"}),
    ("scm:integrationmessage_list", {"direction": "sideways"}),
    ("scm:integrationmessage_list", {"document_type": "edi_000"}),
    ("scm:integrationmessage_list", {"status": "banana"}),
    ("scm:integrationmessage_list", {"source": "lol"}),
    ("scm:integrationmessage_list", {"date_from": "lastweek"}),
    ("scm:integrationmessage_list", {"date_to": "2026-02-30"}),
    ("scm:integrationmessage_list", {"date_from": "", "date_to": "not-a-date"}),
    ("scm:integrationmessage_list", {"page": "999"}),
    ("scm:integration_exceptions", {"endpoint": "abc"}),
    ("scm:integration_exceptions", {"endpoint": "²"}),
    ("scm:integration_exceptions", {"endpoint": "999999999999999999999"}),
    ("scm:integration_exceptions", {"document_type": "edi_000"}),
    ("scm:integration_exceptions", {"q": "'); DROP TABLE scm_integrationmessage;--"}),
    ("scm:integration_exceptions", {"page": "999"}),
    ("scm:webhooksubscription_list", {"status": "banana"}),
    ("scm:webhooksubscription_list", {"status": "True"}),
    ("scm:webhooksubscription_list", {"trigger_entity": "unicorn"}),
    ("scm:webhooksubscription_list", {"trigger_event": "exploded"}),
    ("scm:webhooksubscription_list", {"payload_format": "yaml"}),
    ("scm:webhooksubscription_list", {"page": "abc"}),
    ("scm:webhooksubscription_list", {"page": "999"}),
    ("scm:webhookdelivery_list", {"subscription": "abc"}),
    ("scm:webhookdelivery_list", {"subscription": "²"}),
    ("scm:webhookdelivery_list", {"subscription": "999999999999999999999"}),
    ("scm:webhookdelivery_list", {"status": "banana"}),
    ("scm:webhookdelivery_list", {"date_from": "nope"}),
    ("scm:webhookdelivery_list", {"date_to": "2026-13-45"}),
    ("scm:webhookdelivery_list", {"page": "999"}),
]

#: Hand-typed numbers on ``auto_disable_threshold`` that must come back as a FORM ERROR rather than
#: a 500. ``NaN``/``Infinity``/``abc`` die in ``IntegerField.to_python``; ``-1`` and ``0`` in
#: ``MinValueValidator(1)``; ``21`` in ``MaxValueValidator(20)``; the last one is wider than the
#: column and must never reach the driver.
_INTEGRATION_POISONED_NUMBERS = ["NaN", "Infinity", "-Infinity", "abc", "1e5", "3.5",
                                 "-1", "0", "21", "99999999999999999999999"]

#: URLs a ``URLField`` must refuse rather than store.
_INTEGRATION_POISONED_URLS = ["not-a-url", "javascript:alert(1)", "http://", "://nope",
                              "https://" + "a" * 520]

#: ``headers`` values that must each come back keyed on ``headers``.
_INTEGRATION_POISONED_HEADERS = [
    "not json at all",
    '["X-Source", "NavERP"]',
    '"just a string"',
    "42",
    '{"X-Source": 42}',
    '{"X-Source": "NavERP\\r\\nX-Forwarded-For: 10.0.0.1"}',
    '{"X-Source\\n": "NavERP"}',
]

#: Outbound-transport modules. 4.19 ships NO transport, so importing any of these anywhere under
#: ``apps/scm`` would be a new SSRF surface aimed at a tenant-editable ``endpoint_url`` /
#: ``target_url``. ``urllib.parse`` is deliberately NOT matched — four report views build query
#: strings with ``urlencode`` and that reaches no network.
_INTEGRATION_TRANSPORT_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(requests|httpx|aiohttp|urllib3|socket|http\.client|urllib\.request)\b",
    re.MULTILINE)

#: Route names that MUST NOT exist. Both logs are append-only: a wrong row is corrected by appending
#: a later, correct one — never by editing or deleting the first.
_INTEGRATION_ABSENT_ROUTE_NAMES = [
    "scm:integrationmessage_create",
    "scm:integrationmessage_edit",
    "scm:integrationmessage_delete",
    "scm:webhookdelivery_create",
    "scm:webhookdelivery_edit",
    "scm:webhookdelivery_delete",
]


# =================================================================================================
# Local fixtures — shapes the shared conftest deliberately does not pre-build
# =================================================================================================
@pytest.fixture
def _integration_message_pending_a(db, tenant_a, integration_endpoint_a):
    """A queued row. ``pending`` is the other member of ``REPROCESS_BLOCKED_STATUSES``: re-queuing
    something already queued would double the attempt counter for one press, so it is REFUSED."""
    from apps.scm.models import IntegrationMessage
    return IntegrationMessage.objects.create(
        tenant=tenant_a, endpoint=integration_endpoint_a,
        direction="outbound", document_type="edi_856", status="pending",
        control_number="000000901", attempt_count=1,
        occurred_at=timezone.now() - datetime.timedelta(minutes=9))


@pytest.fixture
def _integration_message_rogue_b(db, tenant_b, integration_endpoint_edi_a, integration_message_a):
    """A tenant-B row pointing at BOTH a tenant-A endpoint and a tenant-A message.

    Written straight through ``objects.create``, which does NOT call ``clean()`` — exactly the shape
    a raw import or a row predating the FK guard would leave behind. Nothing on either A-side page
    may surface it: ``recent_messages`` and ``ack_message`` are both keyed on
    ``tenant=request.tenant`` rather than trusted from the relation, and this fixture is what proves
    that term is load-bearing rather than decorative.
    """
    from apps.scm.models import IntegrationMessage
    return IntegrationMessage.objects.create(
        tenant=tenant_b, endpoint=integration_endpoint_edi_a,
        direction="inbound", document_type="edi_997", status="received",
        control_number="ROGUE-001", acknowledges=integration_message_a,
        occurred_at=timezone.now())


@pytest.fixture
def _integration_delivery_pending_a(db, tenant_a, integration_subscription_a):
    """A QUEUED attempt — ``pending`` is in ``RETRYABLE_STATUSES``, so a retry is accepted."""
    from apps.scm.models import WebhookDelivery
    return WebhookDelivery.objects.create(
        tenant=tenant_a, subscription=integration_subscription_a,
        event="shipment.created", status="pending", attempt_no=2,
        triggered_at=timezone.now() - datetime.timedelta(minutes=6))


@pytest.fixture
def _integration_delivery_exhausted_a(db, tenant_a, integration_subscription_a):
    """A row the schedule has already given up on — outside ``RETRYABLE_STATUSES``, so REFUSED."""
    from apps.scm.models import WebhookDelivery
    return WebhookDelivery.objects.create(
        tenant=tenant_a, subscription=integration_subscription_a,
        event="shipment.delivered", status="exhausted", attempt_no=8, response_code=500,
        error_message="Receiver never came back.",
        triggered_at=timezone.now() - datetime.timedelta(days=3))


@pytest.fixture
def _integration_delivery_simulated_a(db, tenant_a, integration_subscription_a):
    """A dry-run row — also outside ``RETRYABLE_STATUSES``."""
    from apps.scm.models import WebhookDelivery
    return WebhookDelivery.objects.create(
        tenant=tenant_a, subscription=integration_subscription_a,
        event="shipment.created", status="simulated", attempt_no=1,
        triggered_at=timezone.now() - datetime.timedelta(minutes=20))


# =================================================================================================
# Anonymous -> login
# =================================================================================================
class TestIntegrationAnonymous:
    @pytest.mark.parametrize("url_name", _INTEGRATION_ANON_PAGES,
                             ids=[name.split(":")[1] for name in _INTEGRATION_ANON_PAGES])
    def test_integration_anonymous_page_redirects_to_login(self, url_name):
        response = Client().get(reverse(url_name))
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    @pytest.mark.parametrize("url_name,fixture_name", _INTEGRATION_ANON_PK_PAGES,
                             ids=[name.split(":")[1] for name, _ in _INTEGRATION_ANON_PK_PAGES])
    def test_integration_anonymous_pk_page_redirects_to_login(self, request, url_name,
                                                              fixture_name):
        obj = request.getfixturevalue(fixture_name)
        response = Client().get(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    @pytest.mark.parametrize("url_name,fixture_name", _INTEGRATION_POST_ONLY_ROUTES,
                             ids=[name.split(":")[1] for name, _ in _INTEGRATION_POST_ONLY_ROUTES])
    def test_integration_anonymous_verb_post_redirects_to_login(self, request, url_name,
                                                                fixture_name):
        obj = request.getfixturevalue(fixture_name)
        response = Client().post(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        assert type(obj).objects.filter(pk=obj.pk).exists()

    def test_integration_anonymous_endpoint_create_post_saves_nothing(self, db):
        from apps.scm.models import IntegrationEndpoint
        before = IntegrationEndpoint.objects.count()
        response = Client().post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload())
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        assert IntegrationEndpoint.objects.count() == before

    def test_integration_anonymous_subscription_create_post_saves_nothing(self, db):
        from apps.scm.models import WebhookSubscription
        before = WebhookSubscription.objects.count()
        response = Client().post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload())
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        assert WebhookSubscription.objects.count() == before

    def test_integration_anonymous_endpoint_edit_post_changes_nothing(self,
                                                                      integration_endpoint_a):
        response = Client().post(
            reverse("scm:integrationendpoint_edit", args=[integration_endpoint_a.pk]),
            _integration_endpoint_payload(name="Hijacked"))
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.name == "SAP S/4HANA master data"

    def test_integration_anonymous_rotate_leaves_the_credential_alone(
            self, integration_endpoint_with_credential_a):
        before = integration_endpoint_with_credential_a.credential_hash
        response = Client().post(reverse("scm:integrationendpoint_rotate_credential",
                                         args=[integration_endpoint_with_credential_a.pk]))
        assert response.status_code == 302
        integration_endpoint_with_credential_a.refresh_from_db()
        assert integration_endpoint_with_credential_a.credential_hash == before

    def test_integration_anonymous_reprocess_leaves_the_log_row_alone(self,
                                                                     integration_message_failed_a):
        response = Client().post(reverse("scm:integrationmessage_reprocess",
                                         args=[integration_message_failed_a.pk]))
        assert response.status_code == 302
        integration_message_failed_a.refresh_from_db()
        assert integration_message_failed_a.status == "failed"
        assert integration_message_failed_a.attempt_count == 3

    def test_integration_anonymous_retry_leaves_the_attempt_alone(self, integration_delivery_a):
        response = Client().post(reverse("scm:webhookdelivery_retry",
                                         args=[integration_delivery_a.pk]))
        assert response.status_code == 302
        integration_delivery_a.refresh_from_db()
        assert integration_delivery_a.status == "failed"
        assert integration_delivery_a.attempt_no == 3


# =================================================================================================
# @tenant_admin_required — and, just as importantly, the routes that are NOT gated
# =================================================================================================
class TestIntegrationAdminGates:
    @pytest.mark.parametrize("url_name,fixture_name", _INTEGRATION_ADMIN_ONLY_POSTS,
                             ids=[name.split(":")[1] for name, _ in _INTEGRATION_ADMIN_ONLY_POSTS])
    def test_integration_admin_only_verb_is_403_for_a_member(self, request, member_client,
                                                             url_name, fixture_name):
        obj = request.getfixturevalue(fixture_name)
        response = member_client.post(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 403
        assert type(obj).objects.filter(pk=obj.pk).exists()

    def test_integration_endpoint_delete_succeeds_for_a_tenant_admin(self, client_a,
                                                                     integration_endpoint_a):
        """The POSITIVE half — the gate must refuse the member, not the feature (L44)."""
        from apps.scm.models import IntegrationEndpoint
        response = client_a.post(
            reverse("scm:integrationendpoint_delete", args=[integration_endpoint_a.pk]))
        assert response.status_code == 302
        assert not IntegrationEndpoint.objects.filter(pk=integration_endpoint_a.pk).exists()

    def test_integration_rotate_credential_succeeds_for_a_tenant_admin(self, client_a,
                                                                       integration_endpoint_a):
        response = client_a.post(
            reverse("scm:integrationendpoint_rotate_credential",
                    args=[integration_endpoint_a.pk]))
        assert response.status_code == 302
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.credential_hash != ""

    def test_integration_member_rotate_credential_writes_no_marker(
            self, member_client, integration_endpoint_a):
        response = member_client.post(
            reverse("scm:integrationendpoint_rotate_credential",
                    args=[integration_endpoint_a.pk]))
        assert response.status_code == 403
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.credential_hash == ""
        assert integration_endpoint_a.credential_prefix == ""

    def test_integration_subscription_create_get_is_403_for_a_member(self, member_client):
        assert member_client.get(reverse("scm:webhooksubscription_create")).status_code == 403

    def test_integration_subscription_create_post_is_403_for_a_member(self, member_client, db):
        from apps.scm.models import WebhookSubscription
        before = WebhookSubscription.objects.count()
        response = member_client.post(reverse("scm:webhooksubscription_create"),
                                      _integration_subscription_payload())
        assert response.status_code == 403
        assert WebhookSubscription.objects.count() == before

    def test_integration_subscription_create_works_for_a_tenant_admin(self, client_a, tenant_a):
        from apps.scm.models import WebhookSubscription
        assert client_a.get(reverse("scm:webhooksubscription_create")).status_code == 200
        response = client_a.post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload())
        assert response.status_code == 302
        saved = WebhookSubscription.objects.get(tenant=tenant_a, name="Crafted rule")
        assert saved.number.startswith("WHK-")

    def test_integration_subscription_edit_is_403_for_a_member(self, member_client,
                                                               integration_subscription_a):
        url = reverse("scm:webhooksubscription_edit", args=[integration_subscription_a.pk])
        assert member_client.get(url).status_code == 403
        assert member_client.post(url, _integration_subscription_payload(
            name="Retargeted", target_url="https://attacker.example.net/collect")).status_code == 403
        integration_subscription_a.refresh_from_db()
        assert integration_subscription_a.target_url.startswith("https://wms.example.com/")

    def test_integration_subscription_edit_works_for_a_tenant_admin(self, client_a,
                                                                    integration_subscription_a):
        url = reverse("scm:webhooksubscription_edit", args=[integration_subscription_a.pk])
        assert client_a.get(url).status_code == 200
        response = client_a.post(url, _integration_subscription_payload(
            name=integration_subscription_a.name,
            target_url="https://wms.example.com/hooks/naverp/v2"))
        assert response.status_code == 302
        integration_subscription_a.refresh_from_db()
        assert integration_subscription_a.target_url == "https://wms.example.com/hooks/naverp/v2"

    def test_integration_subscription_rotate_secret_succeeds_for_a_tenant_admin(
            self, client_a, integration_subscription_a):
        response = client_a.post(reverse("scm:webhooksubscription_rotate_secret",
                                         args=[integration_subscription_a.pk]))
        assert response.status_code == 302
        integration_subscription_a.refresh_from_db()
        assert integration_subscription_a.signing_secret_hash != ""

    def test_integration_member_rotate_secret_writes_no_marker(self, member_client,
                                                               integration_subscription_a):
        response = member_client.post(reverse("scm:webhooksubscription_rotate_secret",
                                              args=[integration_subscription_a.pk]))
        assert response.status_code == 403
        integration_subscription_a.refresh_from_db()
        assert integration_subscription_a.signing_secret_hash == ""

    # --- the ASYMMETRY: these four are deliberately NOT admin-gated ------------------------------
    def test_integration_endpoint_create_is_open_to_a_member(self, member_client, tenant_a):
        """``integrationendpoint_create`` is plain ``@login_required`` — registering a connection is
        ordinary work, and only deleting one or rotating its credential is administrative."""
        from apps.scm.models import IntegrationEndpoint
        assert member_client.get(reverse("scm:integrationendpoint_create")).status_code == 200
        response = member_client.post(reverse("scm:integrationendpoint_create"),
                                      _integration_endpoint_payload())
        assert response.status_code == 302
        saved = IntegrationEndpoint.objects.get(tenant=tenant_a, name="Crafted connection")
        assert saved.number.startswith("CNX-")

    def test_integration_endpoint_edit_is_open_to_a_member(self, member_client,
                                                           integration_endpoint_a):
        url = reverse("scm:integrationendpoint_edit", args=[integration_endpoint_a.pk])
        assert member_client.get(url).status_code == 200
        response = member_client.post(url, _integration_endpoint_payload(
            name=integration_endpoint_a.name, category="erp", system="sap",
            status="connected", lifecycle_stage="live", environment="production",
            schedule_note="Every 30 minutes"))
        assert response.status_code == 302
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.schedule_note == "Every 30 minutes"

    def test_integration_reprocess_is_open_to_a_member(self, member_client,
                                                       integration_message_failed_a):
        """A log verb, not a secret — any member who can work the exceptions page can press it."""
        response = member_client.post(reverse("scm:integrationmessage_reprocess",
                                              args=[integration_message_failed_a.pk]))
        assert response.status_code == 302
        integration_message_failed_a.refresh_from_db()
        assert integration_message_failed_a.status == "pending"
        assert integration_message_failed_a.attempt_count == 4

    def test_integration_retry_is_open_to_a_member(self, member_client, integration_delivery_a):
        response = member_client.post(reverse("scm:webhookdelivery_retry",
                                              args=[integration_delivery_a.pk]))
        assert response.status_code == 302
        integration_delivery_a.refresh_from_db()
        assert integration_delivery_a.status == "pending"
        assert integration_delivery_a.attempt_no == 4

    def test_integration_member_can_read_every_page(self, member_client, integration_endpoint_a,
                                                    integration_message_a,
                                                    integration_subscription_a,
                                                    integration_delivery_a):
        """Nothing in 4.19 is admin-only to READ — the gates are on the four write verbs."""
        for url_name in _INTEGRATION_ANON_PAGES:
            if url_name == "scm:webhooksubscription_create":
                continue
            assert member_client.get(reverse(url_name)).status_code == 200
        for url_name, obj in (
                ("scm:integrationendpoint_detail", integration_endpoint_a),
                ("scm:integrationmessage_detail", integration_message_a),
                ("scm:webhooksubscription_detail", integration_subscription_a),
                ("scm:webhookdelivery_detail", integration_delivery_a)):
            assert member_client.get(reverse(url_name, args=[obj.pk])).status_code == 200

    def test_integration_is_tenant_admin_flag_tracks_the_session(self, client_a, member_client,
                                                                 integration_subscription_a):
        """The template flag and the decorator must agree, or a member is shown a button that 403s."""
        assert client_a.get(reverse("scm:webhooksubscription_list")).context["is_tenant_admin"]
        assert not member_client.get(
            reverse("scm:webhooksubscription_list")).context["is_tenant_admin"]
        assert client_a.get(reverse("scm:integrationendpoint_list")).context["is_tenant_admin"]
        assert not member_client.get(
            reverse("scm:integrationendpoint_list")).context["is_tenant_admin"]


# =================================================================================================
# CSRF
# =================================================================================================
class TestIntegrationCsrf:
    def test_integration_csrf_is_enforced_on_endpoint_create(self, admin_user, db):
        from apps.scm.models import IntegrationEndpoint
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        before = IntegrationEndpoint.objects.count()
        response = strict.post(reverse("scm:integrationendpoint_create"),
                               _integration_endpoint_payload())
        assert response.status_code == 403
        assert IntegrationEndpoint.objects.count() == before

    def test_integration_csrf_is_enforced_on_endpoint_edit(self, admin_user,
                                                           integration_endpoint_a):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(
            reverse("scm:integrationendpoint_edit", args=[integration_endpoint_a.pk]),
            _integration_endpoint_payload(name="Hijacked"))
        assert response.status_code == 403
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.name == "SAP S/4HANA master data"

    def test_integration_csrf_is_enforced_on_endpoint_delete(self, admin_user,
                                                             integration_endpoint_a):
        from apps.scm.models import IntegrationEndpoint
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(
            reverse("scm:integrationendpoint_delete", args=[integration_endpoint_a.pk]))
        assert response.status_code == 403
        assert IntegrationEndpoint.objects.filter(pk=integration_endpoint_a.pk).exists()

    def test_integration_csrf_is_enforced_on_rotate_credential(self, admin_user,
                                                               integration_endpoint_a):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(reverse("scm:integrationendpoint_rotate_credential",
                                       args=[integration_endpoint_a.pk]))
        assert response.status_code == 403
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.credential_hash == ""

    def test_integration_csrf_is_enforced_on_reprocess(self, admin_user,
                                                       integration_message_failed_a):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(reverse("scm:integrationmessage_reprocess",
                                       args=[integration_message_failed_a.pk]))
        assert response.status_code == 403
        integration_message_failed_a.refresh_from_db()
        assert integration_message_failed_a.status == "failed"
        assert integration_message_failed_a.attempt_count == 3

    def test_integration_csrf_is_enforced_on_subscription_create(self, admin_user, db):
        from apps.scm.models import WebhookSubscription
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        before = WebhookSubscription.objects.count()
        response = strict.post(reverse("scm:webhooksubscription_create"),
                               _integration_subscription_payload())
        assert response.status_code == 403
        assert WebhookSubscription.objects.count() == before

    def test_integration_csrf_is_enforced_on_subscription_delete(self, admin_user,
                                                                 integration_subscription_a):
        from apps.scm.models import WebhookSubscription
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(reverse("scm:webhooksubscription_delete",
                                       args=[integration_subscription_a.pk]))
        assert response.status_code == 403
        assert WebhookSubscription.objects.filter(pk=integration_subscription_a.pk).exists()

    def test_integration_csrf_is_enforced_on_rotate_secret(self, admin_user,
                                                           integration_subscription_a):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(reverse("scm:webhooksubscription_rotate_secret",
                                       args=[integration_subscription_a.pk]))
        assert response.status_code == 403
        integration_subscription_a.refresh_from_db()
        assert integration_subscription_a.signing_secret_hash == ""

    def test_integration_csrf_is_enforced_on_delivery_retry(self, admin_user,
                                                            integration_delivery_a):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(reverse("scm:webhookdelivery_retry",
                                       args=[integration_delivery_a.pk]))
        assert response.status_code == 403
        integration_delivery_a.refresh_from_db()
        assert integration_delivery_a.status == "failed"
        assert integration_delivery_a.attempt_no == 3

    def test_integration_a_token_carrying_verb_post_is_accepted(self, admin_user,
                                                                integration_endpoint_a):
        """The POSITIVE half: CSRF enforcement must refuse a forgery, not the feature (L44)."""
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        page = strict.get(reverse("scm:integrationendpoint_create"))
        assert page.status_code == 200
        token = strict.cookies["csrftoken"].value
        response = strict.post(reverse("scm:integrationendpoint_rotate_credential",
                                       args=[integration_endpoint_a.pk]),
                               {"csrfmiddlewaretoken": token})
        assert response.status_code == 302
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.credential_hash != ""

    def test_integration_a_token_carrying_create_post_is_accepted(self, admin_user, tenant_a):
        from apps.scm.models import IntegrationEndpoint
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        strict.get(reverse("scm:integrationendpoint_create"))
        token = strict.cookies["csrftoken"].value
        response = strict.post(reverse("scm:integrationendpoint_create"),
                               _integration_endpoint_payload(csrfmiddlewaretoken=token))
        assert response.status_code == 302
        assert IntegrationEndpoint.objects.filter(tenant=tenant_a,
                                                  name="Crafted connection").exists()


# =================================================================================================
# Multi-tenant isolation
# =================================================================================================
class TestIntegrationCrossTenantIsolation:
    @pytest.mark.parametrize("url_name,fixture_name", _INTEGRATION_CROSS_TENANT_GETS,
                             ids=[name.split(":")[1]
                                  for name, _ in _INTEGRATION_CROSS_TENANT_GETS])
    def test_integration_foreign_pk_on_a_get_route_is_404(self, request, client_a, url_name,
                                                          fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 404

    @pytest.mark.parametrize("url_name,fixture_name", _INTEGRATION_CROSS_TENANT_POSTS,
                             ids=[name.split(":")[1]
                                  for name, _ in _INTEGRATION_CROSS_TENANT_POSTS])
    def test_integration_foreign_pk_on_a_post_route_is_404(self, request, client_a, url_name,
                                                           fixture_name):
        obj = request.getfixturevalue(fixture_name)
        response = client_a.post(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 404
        # A 404 that had already deleted or moved something would be worse than a 200.
        assert type(obj).objects.filter(pk=obj.pk).exists()

    def test_integration_foreign_endpoint_edit_post_changes_nothing(self, client_a,
                                                                    integration_endpoint_b):
        url = reverse("scm:integrationendpoint_edit", args=[integration_endpoint_b.pk])
        assert client_a.post(url, _integration_endpoint_payload(name="Hijacked")).status_code == 404
        integration_endpoint_b.refresh_from_db()
        assert integration_endpoint_b.name == "Globex NetSuite link"

    def test_integration_foreign_subscription_rotate_leaves_the_secret_alone(
            self, client_a, integration_subscription_b):
        response = client_a.post(reverse("scm:webhooksubscription_rotate_secret",
                                         args=[integration_subscription_b.pk]))
        assert response.status_code == 404
        integration_subscription_b.refresh_from_db()
        assert integration_subscription_b.signing_secret_hash == ""

    def test_integration_foreign_message_reprocess_changes_nothing(self, client_a,
                                                                   integration_message_b):
        response = client_a.post(reverse("scm:integrationmessage_reprocess",
                                         args=[integration_message_b.pk]))
        assert response.status_code == 404
        integration_message_b.refresh_from_db()
        assert integration_message_b.status == "failed"
        assert integration_message_b.attempt_count == 1
        assert integration_message_b.error_code == "GBX_ERR"

    def test_integration_foreign_delivery_retry_changes_nothing(self, client_a,
                                                                integration_delivery_b):
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[integration_delivery_b.pk]))
        assert response.status_code == 404
        integration_delivery_b.refresh_from_db()
        assert integration_delivery_b.status == "failed"
        assert integration_delivery_b.attempt_no == 1

    def test_integration_own_routes_still_resolve(self, client_a, integration_endpoint_a,
                                                  integration_message_a,
                                                  integration_subscription_a,
                                                  integration_delivery_a):
        """The POSITIVE half of the 404 sweep — the tenant term must exclude B, not everything."""
        for url_name, obj in (
                ("scm:integrationendpoint_detail", integration_endpoint_a),
                ("scm:integrationendpoint_edit", integration_endpoint_a),
                ("scm:integrationmessage_detail", integration_message_a),
                ("scm:webhooksubscription_detail", integration_subscription_a),
                ("scm:webhooksubscription_edit", integration_subscription_a),
                ("scm:webhookdelivery_detail", integration_delivery_a)):
            assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 200

    def test_integration_endpoint_list_never_carries_the_other_workspace(
            self, client_a, tenant_a, integration_endpoint_a, integration_endpoint_b):
        response = client_a.get(reverse("scm:integrationendpoint_list"))
        assert response.status_code == 200
        rows = list(response.context["object_list"])
        assert integration_endpoint_b.pk not in [row.pk for row in rows]
        assert {row.tenant_id for row in rows} == {tenant_a.pk}
        # The header chips are counted over the ROUTE queryset, so they must not see B either.
        assert response.context["stats"]["total"] == 1

    def test_integration_message_list_never_carries_the_other_workspace(
            self, client_a, tenant_a, integration_message_a, integration_message_b):
        response = client_a.get(reverse("scm:integrationmessage_list"))
        rows = list(response.context["object_list"])
        assert integration_message_b.pk not in [row.pk for row in rows]
        assert {row.tenant_id for row in rows} == {tenant_a.pk}
        assert response.context["stats"]["total"] == 1
        assert response.context["stats"]["failed"] == 0

    def test_integration_exceptions_never_carries_the_other_workspace(
            self, client_a, tenant_a, integration_message_failed_a, integration_message_b):
        response = client_a.get(reverse("scm:integration_exceptions"))
        rows = list(response.context["object_list"])
        assert integration_message_b.pk not in [row.pk for row in rows]
        assert {row.tenant_id for row in rows} == {tenant_a.pk}
        assert response.context["stats"]["failed_total"] == 1
        codes = [group["error_code"] for group in response.context["error_groups"]]
        assert codes == ["LLRP_TIMEOUT"]
        assert "GBX_ERR" not in codes

    def test_integration_subscription_list_never_carries_the_other_workspace(
            self, client_a, tenant_a, integration_subscription_a, integration_subscription_b):
        response = client_a.get(reverse("scm:webhooksubscription_list"))
        rows = list(response.context["object_list"])
        assert integration_subscription_b.pk not in [row.pk for row in rows]
        assert {row.tenant_id for row in rows} == {tenant_a.pk}
        assert response.context["stats"]["total"] == 1

    def test_integration_delivery_list_never_carries_the_other_workspace(
            self, client_a, tenant_a, integration_delivery_a, integration_delivery_b):
        response = client_a.get(reverse("scm:webhookdelivery_list"))
        rows = list(response.context["object_list"])
        assert integration_delivery_b.pk not in [row.pk for row in rows]
        assert {row.tenant_id for row in rows} == {tenant_a.pk}
        assert response.context["stats"]["total"] == 1

    def test_integration_filter_dropdowns_never_offer_the_other_workspace(
            self, client_a, integration_endpoint_a, integration_endpoint_b,
            integration_subscription_a, integration_subscription_b):
        """A dropdown that lists another workspace's rows leaks names even if the filter is safe."""
        messages_page = client_a.get(reverse("scm:integrationmessage_list"))
        endpoint_pks = [row.pk for row in messages_page.context["endpoints"]]
        assert integration_endpoint_a.pk in endpoint_pks
        assert integration_endpoint_b.pk not in endpoint_pks

        exceptions_page = client_a.get(reverse("scm:integration_exceptions"))
        assert integration_endpoint_b.pk not in [row.pk
                                                 for row in exceptions_page.context["endpoints"]]

        deliveries_page = client_a.get(reverse("scm:webhookdelivery_list"))
        subscription_pks = [row.pk for row in deliveries_page.context["subscriptions"]]
        assert integration_subscription_a.pk in subscription_pks
        assert integration_subscription_b.pk not in subscription_pks

    def test_integration_filtering_by_a_foreign_endpoint_pk_returns_nothing(
            self, client_a, integration_message_a, integration_endpoint_b,
            integration_endpoint_edi_a):
        foreign = client_a.get(reverse("scm:integrationmessage_list"),
                               {"endpoint": str(integration_endpoint_b.pk)})
        assert foreign.status_code == 200
        assert list(foreign.context["object_list"]) == []
        # POSITIVE: the same filter with A's own pk still selects A's rows.
        own = client_a.get(reverse("scm:integrationmessage_list"),
                           {"endpoint": str(integration_endpoint_edi_a.pk)})
        assert [row.pk for row in own.context["object_list"]] == [integration_message_a.pk]

    def test_integration_filtering_by_a_foreign_subscription_pk_returns_nothing(
            self, client_a, integration_delivery_a, integration_subscription_b,
            integration_subscription_a):
        foreign = client_a.get(reverse("scm:webhookdelivery_list"),
                               {"subscription": str(integration_subscription_b.pk)})
        assert foreign.status_code == 200
        assert list(foreign.context["object_list"]) == []
        own = client_a.get(reverse("scm:webhookdelivery_list"),
                           {"subscription": str(integration_subscription_a.pk)})
        assert [row.pk for row in own.context["object_list"]] == [integration_delivery_a.pk]

    def test_integration_endpoint_panel_ignores_a_foreign_row_pointing_at_it(
            self, client_a, integration_endpoint_edi_a, integration_message_a,
            _integration_message_rogue_b):
        """``recent_messages`` is keyed on ``tenant`` AND ``endpoint_id``, never on the relation.

        A row written before the FK guard existed (or by a raw import that skipped ``clean()``) can
        carry another workspace's tenant while pointing at this endpoint. It must not appear here.
        """
        response = client_a.get(reverse("scm:integrationendpoint_detail",
                                        args=[integration_endpoint_edi_a.pk]))
        assert response.status_code == 200
        panel_pks = [row.pk for row in response.context["recent_messages"]]
        assert integration_message_a.pk in panel_pks
        assert _integration_message_rogue_b.pk not in panel_pks
        assert response.context["message_stats"]["total"] == 1

    def test_integration_ack_chain_ignores_a_foreign_acknowledgement(
            self, client_a, integration_message_a, _integration_message_rogue_b):
        """``ack_message`` is re-scoped to the request tenant rather than trusted from the reverse
        accessor — so a cross-tenant ``acknowledges`` pointer surfaces nothing."""
        response = client_a.get(reverse("scm:integrationmessage_detail",
                                        args=[integration_message_a.pk]))
        assert response.status_code == 200
        assert response.context["ack_message"] is None

    def test_integration_ack_chain_still_finds_its_own_acknowledgement(
            self, client_a, integration_message_a, integration_message_ack_a):
        """POSITIVE (L44): the re-scoping must exclude the foreign row, not the feature."""
        response = client_a.get(reverse("scm:integrationmessage_detail",
                                        args=[integration_message_a.pk]))
        assert response.context["ack_message"].pk == integration_message_ack_a.pk

    def test_integration_the_other_workspace_sees_only_its_own_rows(
            self, client_b, tenant_b, integration_endpoint_a, integration_endpoint_b):
        """Isolation is symmetric — asserted from B's side so a one-way filter cannot pass."""
        response = client_b.get(reverse("scm:integrationendpoint_list"))
        rows = list(response.context["object_list"])
        assert [row.pk for row in rows] == [integration_endpoint_b.pk]
        assert {row.tenant_id for row in rows} == {tenant_b.pk}
        assert client_b.get(reverse("scm:integrationendpoint_detail",
                                    args=[integration_endpoint_a.pk])).status_code == 404

    def test_integration_numbering_restarts_per_tenant(self, tenant_a, tenant_b,
                                                       integration_endpoint_a,
                                                       integration_endpoint_b):
        """Per-tenant numbering is isolation too: B's first connection must not read CNX-00002."""
        assert integration_endpoint_a.number == "CNX-00001"
        assert integration_endpoint_b.number == "CNX-00001"


# =================================================================================================
# Crafted POST bodies — foreign FKs and non-form columns
# =================================================================================================
class TestIntegrationCraftedPosts:
    @pytest.mark.parametrize("field,fixture_name", [
        ("partner_party", "supplier_b"),
        ("logistics_client", "tpl_client_b"),
        ("location", "location_b"),
        ("spec_document", "evidence_document_b"),
    ])
    def test_integration_endpoint_create_refuses_a_foreign_fk(self, request, client_a, field,
                                                              fixture_name):
        from apps.scm.models import IntegrationEndpoint
        foreign = request.getfixturevalue(fixture_name)
        before = IntegrationEndpoint.objects.count()
        response = client_a.post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload(**{field: str(foreign.pk)}))
        assert response.status_code == 200
        assert field in response.context["form"].errors
        assert IntegrationEndpoint.objects.count() == before

    @pytest.mark.parametrize("field,fixture_name", [
        ("partner_party", "supplier_a"),
        ("location", "location_a"),
        ("spec_document", "evidence_document_a"),
    ])
    def test_integration_endpoint_create_accepts_its_own_fk(self, request, client_a, tenant_a,
                                                            field, fixture_name):
        """POSITIVE (L44): the FK guard must refuse another workspace's row, not every row."""
        from apps.scm.models import IntegrationEndpoint
        own = request.getfixturevalue(fixture_name)
        response = client_a.post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload(**{field: str(own.pk)}))
        assert response.status_code == 302
        saved = IntegrationEndpoint.objects.get(tenant=tenant_a, name="Crafted connection")
        assert getattr(saved, f"{field}_id") == own.pk

    def test_integration_endpoint_create_accepts_its_own_logistics_client(
            self, client_a, tenant_a, tpl_client_shared_a):
        from apps.scm.models import IntegrationEndpoint
        response = client_a.post(
            reverse("scm:integrationendpoint_create"),
            _integration_endpoint_payload(logistics_client=str(tpl_client_shared_a.pk)))
        assert response.status_code == 302
        saved = IntegrationEndpoint.objects.get(tenant=tenant_a, name="Crafted connection")
        assert saved.logistics_client_id == tpl_client_shared_a.pk
        # Constraint A read-through, not a second copy of the partner's EDI identity.
        assert saved.interchange_id == ""
        assert saved.effective_interchange_id == "1234567890123"

    def test_integration_endpoint_edit_refuses_a_foreign_fk(self, client_a,
                                                            integration_endpoint_a, supplier_b):
        response = client_a.post(
            reverse("scm:integrationendpoint_edit", args=[integration_endpoint_a.pk]),
            _integration_endpoint_payload(name=integration_endpoint_a.name,
                                          partner_party=str(supplier_b.pk)))
        assert response.status_code == 200
        assert "partner_party" in response.context["form"].errors
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.partner_party_id is None

    def test_integration_endpoint_create_ignores_a_posted_tenant_and_number(self, client_a,
                                                                           tenant_a, tenant_b):
        """``tenant`` and ``number`` are not form fields — a crafted body cannot reach either."""
        from apps.scm.models import IntegrationEndpoint
        response = client_a.post(
            reverse("scm:integrationendpoint_create"),
            _integration_endpoint_payload(tenant=str(tenant_b.pk), number="CNX-99999"))
        assert response.status_code == 302
        saved = IntegrationEndpoint.objects.get(name="Crafted connection")
        assert saved.tenant_id == tenant_a.pk
        assert saved.number != "CNX-99999"
        assert saved.number.startswith("CNX-")

    def test_integration_endpoint_create_ignores_posted_secret_and_system_columns(self, client_a,
                                                                                  tenant_a):
        """L20/L22: the credential marker, the derived counter and the three ``*_at`` stamps are all
        ``editable=False``, so naming them in the body must change nothing."""
        from apps.scm.models import IntegrationEndpoint
        moment = (timezone.now() - datetime.timedelta(days=400)).isoformat()
        response = client_a.post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload(
                                     credential_prefix="pwned",
                                     credential_hash="f" * 64,
                                     consecutive_failures="99",
                                     last_run_at=moment,
                                     last_success_at=moment,
                                     last_seen_at=moment))
        assert response.status_code == 302
        saved = IntegrationEndpoint.objects.get(tenant=tenant_a, name="Crafted connection")
        assert saved.credential_prefix == ""
        assert saved.credential_hash == ""
        assert saved.masked == ""
        assert saved.consecutive_failures == 0
        assert saved.last_run_at is None
        assert saved.last_success_at is None
        assert saved.last_seen_at is None

    def test_integration_endpoint_edit_cannot_overwrite_a_stored_credential(
            self, client_a, integration_endpoint_with_credential_a):
        from apps.scm.models import IntegrationEndpoint
        before = integration_endpoint_with_credential_a.credential_hash
        response = client_a.post(
            reverse("scm:integrationendpoint_edit",
                    args=[integration_endpoint_with_credential_a.pk]),
            _integration_endpoint_payload(
                name=integration_endpoint_with_credential_a.name, category="ecommerce",
                system="shopify", credential_hash=IntegrationEndpoint.hash_secret("attacker"),
                credential_prefix="attacker"))
        assert response.status_code == 302
        integration_endpoint_with_credential_a.refresh_from_db()
        assert integration_endpoint_with_credential_a.credential_hash == before
        assert integration_endpoint_with_credential_a.credential_prefix == "cred-pla"

    def test_integration_subscription_create_ignores_a_posted_tenant_and_number(self, client_a,
                                                                                tenant_a,
                                                                                tenant_b):
        from apps.scm.models import WebhookSubscription
        response = client_a.post(
            reverse("scm:webhooksubscription_create"),
            _integration_subscription_payload(tenant=str(tenant_b.pk), number="WHK-99999"))
        assert response.status_code == 302
        saved = WebhookSubscription.objects.get(name="Crafted rule")
        assert saved.tenant_id == tenant_a.pk
        assert saved.number != "WHK-99999"

    def test_integration_subscription_create_ignores_posted_secret_and_system_columns(
            self, client_a, tenant_a):
        from apps.scm.models import WebhookSubscription
        response = client_a.post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload(
                                     signing_secret_prefix="pwned",
                                     signing_secret_hash="e" * 64,
                                     consecutive_failures="77",
                                     last_delivery_at=timezone.now().isoformat()))
        assert response.status_code == 302
        saved = WebhookSubscription.objects.get(tenant=tenant_a, name="Crafted rule")
        assert saved.signing_secret_prefix == ""
        assert saved.signing_secret_hash == ""
        assert saved.masked == ""
        assert saved.consecutive_failures == 0
        assert saved.last_delivery_at is None

    def test_integration_subscription_edit_cannot_overwrite_a_stored_secret(
            self, client_a, integration_subscription_with_secret_a):
        from apps.scm.models import WebhookSubscription
        before = integration_subscription_with_secret_a.signing_secret_hash
        response = client_a.post(
            reverse("scm:webhooksubscription_edit",
                    args=[integration_subscription_with_secret_a.pk]),
            _integration_subscription_payload(
                name=integration_subscription_with_secret_a.name,
                trigger_entity="goods_receipt", trigger_event="posted", payload_format="xml",
                target_url=integration_subscription_with_secret_a.target_url,
                signing_secret_hash=WebhookSubscription.hash_secret("attacker"),
                signing_secret_prefix="attacker"))
        assert response.status_code == 302
        integration_subscription_with_secret_a.refresh_from_db()
        assert integration_subscription_with_secret_a.signing_secret_hash == before
        assert integration_subscription_with_secret_a.signing_secret_prefix == "whk-plai"

    def test_integration_neither_secret_column_is_a_form_field(self, client_a,
                                                               integration_endpoint_a,
                                                               integration_subscription_a):
        """L20 restated at the render boundary: a secret in ``Meta.fields`` ships its stored value in
        the edit form's ``value=""`` attribute, so the field must not be there at all."""
        endpoint_form = client_a.get(
            reverse("scm:integrationendpoint_edit",
                    args=[integration_endpoint_a.pk])).context["form"]
        for name in ("credential_prefix", "credential_hash", "consecutive_failures",
                     "last_run_at", "last_success_at", "last_seen_at", "tenant", "number"):
            assert name not in endpoint_form.fields

        subscription_form = client_a.get(
            reverse("scm:webhooksubscription_edit",
                    args=[integration_subscription_a.pk])).context["form"]
        for name in ("signing_secret_prefix", "signing_secret_hash", "consecutive_failures",
                     "last_delivery_at", "tenant", "number"):
            assert name not in subscription_form.fields


# =================================================================================================
# Negative input — junk params, poisoned numbers/URLs/headers
# (page-past-the-end and the page-size guards belong to test_integration_views.py, which owns
#  pagination for all five lists — asserting them twice only creates two places to disagree.)
# =================================================================================================
class TestIntegrationNegativeInput:
    @pytest.mark.parametrize("url_name,params", _INTEGRATION_JUNK_QUERIES,
                             ids=[f"{name.split(':')[1]}-{'-'.join(sorted(params))}"
                                  for name, params in _INTEGRATION_JUNK_QUERIES])
    def test_integration_junk_query_param_is_200_not_500(self, client_a, integration_endpoint_a,
                                                         integration_message_failed_a,
                                                         integration_subscription_a,
                                                         integration_delivery_a, url_name,
                                                         params):
        assert client_a.get(reverse(url_name), params).status_code == 200

    @pytest.mark.parametrize("raw", _INTEGRATION_POISONED_NUMBERS)
    def test_integration_poisoned_threshold_is_a_form_error_not_a_500(self, client_a, db, raw):
        from apps.scm.models import WebhookSubscription
        before = WebhookSubscription.objects.count()
        response = client_a.post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload(auto_disable_threshold=raw))
        assert response.status_code == 200
        assert "auto_disable_threshold" in response.context["form"].errors
        assert WebhookSubscription.objects.count() == before

    @pytest.mark.parametrize("raw", ["1", "8", "20"])
    def test_integration_a_threshold_inside_the_bounds_is_accepted(self, client_a, tenant_a, raw):
        """POSITIVE (L44): the bounds must refuse the poison, not the field."""
        from apps.scm.models import WebhookSubscription
        response = client_a.post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload(
                                     name=f"Rule threshold {raw}", auto_disable_threshold=raw))
        assert response.status_code == 302
        saved = WebhookSubscription.objects.get(tenant=tenant_a, name=f"Rule threshold {raw}")
        assert saved.auto_disable_threshold == int(raw)

    @pytest.mark.parametrize("raw", _INTEGRATION_POISONED_URLS)
    def test_integration_poisoned_target_url_is_a_form_error_not_a_500(self, client_a, db, raw):
        from apps.scm.models import WebhookSubscription
        before = WebhookSubscription.objects.count()
        response = client_a.post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload(target_url=raw))
        assert response.status_code == 200
        assert "target_url" in response.context["form"].errors
        assert WebhookSubscription.objects.count() == before

    @pytest.mark.parametrize("raw", _INTEGRATION_POISONED_HEADERS)
    def test_integration_poisoned_headers_are_a_form_error_not_a_500(self, client_a, db, raw):
        """A CR/LF in a header value is request splitting, not formatting — refused at entry."""
        from apps.scm.models import WebhookSubscription
        before = WebhookSubscription.objects.count()
        response = client_a.post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload(headers=raw))
        assert response.status_code == 200
        assert "headers" in response.context["form"].errors
        assert WebhookSubscription.objects.count() == before

    @pytest.mark.parametrize("raw,expected", [("", {}), ("{}", {}),
                                              ('{"X-Source": "NavERP"}', {"X-Source": "NavERP"})])
    def test_integration_well_formed_headers_are_accepted(self, client_a, tenant_a, raw, expected):
        from apps.scm.models import WebhookSubscription
        response = client_a.post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload(
                                     name=f"Rule headers {len(raw)}", headers=raw))
        assert response.status_code == 302
        saved = WebhookSubscription.objects.get(tenant=tenant_a, name=f"Rule headers {len(raw)}")
        assert saved.headers == expected

    def test_integration_a_missing_name_is_a_form_error_not_a_500(self, client_a, db):
        from apps.scm.models import IntegrationEndpoint
        before = IntegrationEndpoint.objects.count()
        response = client_a.post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload(name=""))
        assert response.status_code == 200
        assert "name" in response.context["form"].errors
        assert IntegrationEndpoint.objects.count() == before

    def test_integration_an_over_length_name_is_a_form_error_not_a_500(self, client_a, db):
        from apps.scm.models import IntegrationEndpoint
        before = IntegrationEndpoint.objects.count()
        response = client_a.post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload(name="x" * 200))
        assert response.status_code == 200
        assert "name" in response.context["form"].errors
        assert IntegrationEndpoint.objects.count() == before

    def test_integration_a_duplicate_name_is_a_form_error_not_an_integrityerror(
            self, client_a, integration_endpoint_a):
        """``unique_together ("tenant", "name")`` must surface on the form, never as a 500."""
        from apps.scm.models import IntegrationEndpoint
        before = IntegrationEndpoint.objects.count()
        response = client_a.post(
            reverse("scm:integrationendpoint_create"),
            _integration_endpoint_payload(name=integration_endpoint_a.name, category="erp",
                                          system="sap"))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert IntegrationEndpoint.objects.count() == before

    def test_integration_the_same_name_is_free_in_the_other_workspace(self, client_b, tenant_b,
                                                                      integration_endpoint_a):
        """POSITIVE (L44): the uniqueness is per TENANT, so B may reuse A's name."""
        from apps.scm.models import IntegrationEndpoint
        response = client_b.post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload(name=integration_endpoint_a.name))
        assert response.status_code == 302
        assert IntegrationEndpoint.objects.filter(tenant=tenant_b,
                                                  name=integration_endpoint_a.name).exists()

    def test_integration_constraint_a_is_a_field_error_not_a_500(self, client_a,
                                                                 tpl_client_shared_a):
        """A 3PL client PLUS a hand-typed interchange id is refused on the field the user is looking
        at — not swallowed, and not raised out of ``add_error``."""
        from apps.scm.models import IntegrationEndpoint
        before = IntegrationEndpoint.objects.count()
        response = client_a.post(
            reverse("scm:integrationendpoint_create"),
            _integration_endpoint_payload(logistics_client=str(tpl_client_shared_a.pk),
                                          interchange_id="ZZ99999999",
                                          interchange_qualifier="ZZ"))
        assert response.status_code == 200
        errors = response.context["form"].errors
        assert "interchange_id" in errors
        assert "interchange_qualifier" in errors
        assert IntegrationEndpoint.objects.count() == before

    def test_integration_search_box_survives_sql_shaped_input(self, client_a,
                                                              integration_endpoint_a):
        response = client_a.get(reverse("scm:integrationendpoint_list"),
                                {"q": "' OR 1=1; DROP TABLE scm_integrationendpoint;--"})
        assert response.status_code == 200
        assert list(response.context["object_list"]) == []
        from apps.scm.models import IntegrationEndpoint
        assert IntegrationEndpoint.objects.filter(pk=integration_endpoint_a.pk).exists()


# =================================================================================================
# Absent prerequisites are REJECTED, never fallen through (L35)
# =================================================================================================
class TestIntegrationPrerequisiteGuards:
    def test_integration_reprocess_refuses_an_acknowledged_row(
            self, client_a, integration_message_acknowledged_a):
        url = reverse("scm:integrationmessage_reprocess",
                      args=[integration_message_acknowledged_a.pk])
        response = client_a.post(url, follow=True)
        assert response.status_code == 200
        assert any("cannot be reprocessed" in text for text in _integration_flash(response))
        integration_message_acknowledged_a.refresh_from_db()
        assert integration_message_acknowledged_a.status == "acknowledged"
        assert integration_message_acknowledged_a.attempt_count == 1

    def test_integration_reprocess_refuses_a_pending_row(self, client_a,
                                                         _integration_message_pending_a):
        url = reverse("scm:integrationmessage_reprocess", args=[_integration_message_pending_a.pk])
        response = client_a.post(url, follow=True)
        assert any("cannot be reprocessed" in text for text in _integration_flash(response))
        _integration_message_pending_a.refresh_from_db()
        assert _integration_message_pending_a.status == "pending"
        assert _integration_message_pending_a.attempt_count == 1

    def test_integration_reprocess_accepts_a_failed_row_and_clears_its_error(
            self, client_a, integration_message_failed_a):
        """POSITIVE (L44) — and the state change is exactly the four documented columns."""
        response = client_a.post(reverse("scm:integrationmessage_reprocess",
                                         args=[integration_message_failed_a.pk]), follow=True)
        assert response.status_code == 200
        integration_message_failed_a.refresh_from_db()
        assert integration_message_failed_a.status == "pending"
        assert integration_message_failed_a.attempt_count == 4
        assert integration_message_failed_a.error_code == ""
        assert integration_message_failed_a.error_message == ""
        assert any("re-queued" in text for text in _integration_flash(response))
        assert any("nothing was sent" in text for text in _integration_flash(response))

    def test_integration_reprocess_accepts_a_sent_row(self, client_a, integration_message_a):
        response = client_a.post(reverse("scm:integrationmessage_reprocess",
                                         args=[integration_message_a.pk]))
        assert response.status_code == 302
        integration_message_a.refresh_from_db()
        assert integration_message_a.status == "pending"
        assert integration_message_a.attempt_count == 2

    def test_integration_a_second_reprocess_press_is_refused(self, client_a,
                                                             integration_message_failed_a):
        """The guard is in the VIEW, not only in the template — a double-click must not bump the
        counter twice for one re-queue."""
        url = reverse("scm:integrationmessage_reprocess", args=[integration_message_failed_a.pk])
        assert client_a.post(url).status_code == 302
        second = client_a.post(url, follow=True)
        assert any("cannot be reprocessed" in text for text in _integration_flash(second))
        integration_message_failed_a.refresh_from_db()
        assert integration_message_failed_a.attempt_count == 4

    def test_integration_can_reprocess_flag_matches_the_view_guard(
            self, client_a, integration_message_failed_a, integration_message_acknowledged_a,
            _integration_message_pending_a):
        """A hidden button and a refused POST must never disagree about which rows are eligible."""
        eligible = client_a.get(reverse("scm:integrationmessage_detail",
                                        args=[integration_message_failed_a.pk]))
        assert eligible.context["can_reprocess"] is True
        for blocked in (integration_message_acknowledged_a, _integration_message_pending_a):
            page = client_a.get(reverse("scm:integrationmessage_detail", args=[blocked.pk]))
            assert page.context["can_reprocess"] is False

    def test_integration_retry_refuses_a_successful_attempt(self, client_a,
                                                            integration_delivery_success_a):
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[integration_delivery_success_a.pk]), follow=True)
        assert response.status_code == 200
        assert any("cannot be retried" in text for text in _integration_flash(response))
        integration_delivery_success_a.refresh_from_db()
        assert integration_delivery_success_a.status == "success"
        assert integration_delivery_success_a.attempt_no == 1

    def test_integration_retry_refuses_an_exhausted_attempt(self, client_a,
                                                            _integration_delivery_exhausted_a):
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[_integration_delivery_exhausted_a.pk]), follow=True)
        assert any("cannot be retried" in text for text in _integration_flash(response))
        _integration_delivery_exhausted_a.refresh_from_db()
        assert _integration_delivery_exhausted_a.status == "exhausted"
        assert _integration_delivery_exhausted_a.attempt_no == 8

    def test_integration_retry_refuses_a_simulated_attempt(self, client_a,
                                                           _integration_delivery_simulated_a):
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[_integration_delivery_simulated_a.pk]), follow=True)
        assert any("cannot be retried" in text for text in _integration_flash(response))
        _integration_delivery_simulated_a.refresh_from_db()
        assert _integration_delivery_simulated_a.status == "simulated"
        assert _integration_delivery_simulated_a.attempt_no == 1

    def test_integration_retry_accepts_a_failed_attempt_and_books_the_next_slot(
            self, client_a, integration_delivery_a):
        """POSITIVE (L44). Attempt 3 consumes slot 2, so the next wait is
        ``DELIVERY_BACKOFF_SECONDS[3] == 1800`` seconds."""
        before = timezone.now()
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[integration_delivery_a.pk]), follow=True)
        assert response.status_code == 200
        integration_delivery_a.refresh_from_db()
        assert integration_delivery_a.status == "pending"
        assert integration_delivery_a.attempt_no == 4
        assert integration_delivery_a.next_attempt_at is not None
        delay = (integration_delivery_a.next_attempt_at - before).total_seconds()
        # Wide enough that a slow request cannot fail it, narrow enough that it can only be slot 3
        # (its neighbours are 300s and 7200s).
        assert 1800 <= delay <= 1920
        assert any("nothing was sent" in text for text in _integration_flash(response))

    def test_integration_retry_accepts_a_pending_attempt(self, client_a,
                                                         _integration_delivery_pending_a):
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[_integration_delivery_pending_a.pk]))
        assert response.status_code == 302
        _integration_delivery_pending_a.refresh_from_db()
        assert _integration_delivery_pending_a.status == "pending"
        assert _integration_delivery_pending_a.attempt_no == 3

    def test_integration_retry_of_the_last_slot_exhausts_rather_than_inventing_one(
            self, client_a, integration_delivery_final_a):
        """Attempt 8 runs off the end of the published schedule: the row is marked ``exhausted`` and
        ``next_attempt_at`` is CLEARED, never given a ninth slot the schedule does not describe."""
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[integration_delivery_final_a.pk]), follow=True)
        assert response.status_code == 200
        integration_delivery_final_a.refresh_from_db()
        assert integration_delivery_final_a.status == "exhausted"
        assert integration_delivery_final_a.attempt_no == 8
        assert integration_delivery_final_a.next_attempt_at is None
        assert any("exhausted" in text for text in _integration_flash(response))

    def test_integration_can_retry_flag_matches_the_view_guard(
            self, client_a, integration_delivery_a, integration_delivery_success_a,
            integration_delivery_final_a, _integration_delivery_exhausted_a):
        eligible = client_a.get(reverse("scm:webhookdelivery_detail",
                                        args=[integration_delivery_a.pk]))
        assert eligible.context["can_retry"] is True
        assert eligible.context["next_backoff_seconds"] == 1800
        assert eligible.context["max_attempts"] == 8
        for blocked in (integration_delivery_success_a, integration_delivery_final_a,
                        _integration_delivery_exhausted_a):
            page = client_a.get(reverse("scm:webhookdelivery_detail", args=[blocked.pk]))
            assert page.context["can_retry"] is False

    def test_integration_deleting_a_connection_says_what_went_with_it(self, client_a,
                                                                      integration_endpoint_iot_a,
                                                                      integration_message_failed_a):
        """The CASCADE takes evidence with it, so the count is reported rather than left to be
        discovered — and it is counted BEFORE the delete, while the rows still exist."""
        from apps.scm.models import IntegrationMessage
        response = client_a.post(
            reverse("scm:integrationendpoint_delete", args=[integration_endpoint_iot_a.pk]),
            follow=True)
        assert response.status_code == 200
        flashes = _integration_flash(response)
        assert any("deleted successfully" in text for text in flashes)
        assert any("1 exchange log row" in text for text in flashes)
        assert not IntegrationMessage.objects.filter(pk=integration_message_failed_a.pk).exists()

    def test_integration_deleting_a_rule_steers_at_the_active_box(self, client_a,
                                                                  integration_subscription_a,
                                                                  integration_delivery_a):
        from apps.scm.models import WebhookDelivery
        response = client_a.post(
            reverse("scm:webhooksubscription_delete", args=[integration_subscription_a.pk]),
            follow=True)
        flashes = _integration_flash(response)
        assert any("delivery record" in text for text in flashes)
        assert any("active box" in text for text in flashes)
        assert not WebhookDelivery.objects.filter(pk=integration_delivery_a.pk).exists()


# =================================================================================================
# Secrets — L20 / L25
# =================================================================================================
class TestIntegrationSecretHandling:
    def test_integration_rotate_credential_keeps_the_plaintext_out_of_the_flash(
            self, client_a, integration_endpoint_a):
        """L25: a flash serialises to the message store — a base64 cookie under the default
        ``FallbackStorage``, falling back to ``django_session`` — where a plaintext credential would
        linger until some later render consumed it."""
        response = client_a.post(reverse("scm:integrationendpoint_rotate_credential",
                                         args=[integration_endpoint_a.pk]))
        assert response.status_code == 302
        stored = client_a.session["_cnx_credential_reveal"]
        secret = stored["secret"]
        assert stored["pk"] == integration_endpoint_a.pk

        detail = client_a.get(reverse("scm:integrationendpoint_detail",
                                      args=[integration_endpoint_a.pk]))
        assert detail.context["plaintext_once"] == secret
        assert all(secret.lower() not in text for text in _integration_flash(detail))
        assert any("shown once" in text for text in _integration_flash(detail))

    def test_integration_credential_reveal_happens_exactly_once(self, client_a,
                                                                integration_endpoint_a):
        client_a.post(reverse("scm:integrationendpoint_rotate_credential",
                              args=[integration_endpoint_a.pk]))
        url = reverse("scm:integrationendpoint_detail", args=[integration_endpoint_a.pk])
        assert client_a.get(url).context["plaintext_once"] is not None
        assert client_a.get(url).context["plaintext_once"] is None
        assert "_cnx_credential_reveal" not in client_a.session

    def test_integration_credential_reveal_is_pk_scoped(self, client_a, integration_endpoint_a,
                                                        integration_endpoint_disabled_a):
        """A reveal must never bleed onto a different connection's page."""
        client_a.post(reverse("scm:integrationendpoint_rotate_credential",
                              args=[integration_endpoint_a.pk]))
        other = client_a.get(reverse("scm:integrationendpoint_detail",
                                     args=[integration_endpoint_disabled_a.pk]))
        assert other.context["plaintext_once"] is None
        # Popped on EVERY visit, so the reveal is now gone from the connection it belonged to too.
        owner = client_a.get(reverse("scm:integrationendpoint_detail",
                                     args=[integration_endpoint_a.pk]))
        assert owner.context["plaintext_once"] is None

    def test_integration_rotate_credential_stores_only_a_marker(self, client_a,
                                                                integration_endpoint_a):
        from apps.scm.models import IntegrationEndpoint
        client_a.post(reverse("scm:integrationendpoint_rotate_credential",
                              args=[integration_endpoint_a.pk]))
        secret = client_a.session["_cnx_credential_reveal"]["secret"]
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.credential_hash == IntegrationEndpoint.hash_secret(secret)
        assert integration_endpoint_a.credential_prefix == secret[:8]
        assert secret not in integration_endpoint_a.credential_hash
        assert integration_endpoint_a.masked == secret[:8] + "•" * 8

    def test_integration_the_credential_digest_is_never_rendered(self, client_a,
                                                                 integration_endpoint_with_credential_a):
        for url_name in ("scm:integrationendpoint_detail", "scm:integrationendpoint_edit"):
            body = client_a.get(reverse(url_name,
                                        args=[integration_endpoint_with_credential_a.pk])
                                ).content.decode()
            assert integration_endpoint_with_credential_a.credential_hash not in body
        listing = client_a.get(reverse("scm:integrationendpoint_list")).content.decode()
        assert integration_endpoint_with_credential_a.credential_hash not in listing

    def test_integration_rotate_credential_audits_the_act_not_the_value(self, client_a,
                                                                        integration_endpoint_a):
        from apps.core.models import AuditLog
        client_a.post(reverse("scm:integrationendpoint_rotate_credential",
                              args=[integration_endpoint_a.pk]))
        secret = client_a.session["_cnx_credential_reveal"]["secret"]
        row = AuditLog.objects.filter(action="update",
                                      object_id=integration_endpoint_a.pk).order_by("-id").first()
        assert row is not None
        assert row.changes == {"credential": "rotated"}
        assert secret not in str(row.changes)

    def test_integration_rotate_secret_keeps_the_plaintext_out_of_the_flash(
            self, client_a, integration_subscription_a):
        response = client_a.post(reverse("scm:webhooksubscription_rotate_secret",
                                         args=[integration_subscription_a.pk]))
        assert response.status_code == 302
        stored = client_a.session["_whk_secret_reveal"]
        secret = stored["secret"]
        assert stored["pk"] == integration_subscription_a.pk

        detail = client_a.get(reverse("scm:webhooksubscription_detail",
                                      args=[integration_subscription_a.pk]))
        assert detail.context["plaintext_once"] == secret
        assert all(secret.lower() not in text for text in _integration_flash(detail))

    def test_integration_secret_reveal_happens_exactly_once(self, client_a,
                                                            integration_subscription_a):
        client_a.post(reverse("scm:webhooksubscription_rotate_secret",
                              args=[integration_subscription_a.pk]))
        url = reverse("scm:webhooksubscription_detail", args=[integration_subscription_a.pk])
        assert client_a.get(url).context["plaintext_once"] is not None
        assert client_a.get(url).context["plaintext_once"] is None
        assert "_whk_secret_reveal" not in client_a.session

    def test_integration_secret_reveal_is_pk_scoped(self, client_a, integration_subscription_a,
                                                    integration_subscription_inactive_a):
        client_a.post(reverse("scm:webhooksubscription_rotate_secret",
                              args=[integration_subscription_a.pk]))
        other = client_a.get(reverse("scm:webhooksubscription_detail",
                                     args=[integration_subscription_inactive_a.pk]))
        assert other.context["plaintext_once"] is None

    def test_integration_rotate_secret_stores_only_a_marker(self, client_a,
                                                            integration_subscription_a):
        from apps.scm.models import WebhookSubscription
        client_a.post(reverse("scm:webhooksubscription_rotate_secret",
                              args=[integration_subscription_a.pk]))
        secret = client_a.session["_whk_secret_reveal"]["secret"]
        integration_subscription_a.refresh_from_db()
        assert integration_subscription_a.signing_secret_hash == WebhookSubscription.hash_secret(
            secret)
        assert integration_subscription_a.signing_secret_prefix == secret[:8]
        assert integration_subscription_a.masked == secret[:8] + "•" * 8

    def test_integration_the_signing_digest_is_never_rendered(
            self, client_a, integration_subscription_with_secret_a):
        for url_name in ("scm:webhooksubscription_detail", "scm:webhooksubscription_edit"):
            body = client_a.get(reverse(url_name,
                                        args=[integration_subscription_with_secret_a.pk])
                                ).content.decode()
            assert integration_subscription_with_secret_a.signing_secret_hash not in body
        listing = client_a.get(reverse("scm:webhooksubscription_list")).content.decode()
        assert integration_subscription_with_secret_a.signing_secret_hash not in listing

    def test_integration_rotate_secret_audits_the_act_not_the_value(self, client_a,
                                                                    integration_subscription_a):
        from apps.core.models import AuditLog
        client_a.post(reverse("scm:webhooksubscription_rotate_secret",
                              args=[integration_subscription_a.pk]))
        secret = client_a.session["_whk_secret_reveal"]["secret"]
        row = AuditLog.objects.filter(
            action="update", object_id=integration_subscription_a.pk).order_by("-id").first()
        assert row is not None
        assert row.changes == {"signing_secret": "rotated"}
        assert secret not in str(row.changes)

    def test_integration_two_rotations_never_mint_the_same_value(self, client_a,
                                                                 integration_endpoint_a):
        """``secrets.token_urlsafe`` from the CSPRNG, never ``random`` and never a uuid4 hex."""
        client_a.post(reverse("scm:integrationendpoint_rotate_credential",
                              args=[integration_endpoint_a.pk]))
        first = client_a.session["_cnx_credential_reveal"]["secret"]
        client_a.get(reverse("scm:integrationendpoint_detail", args=[integration_endpoint_a.pk]))
        client_a.post(reverse("scm:integrationendpoint_rotate_credential",
                              args=[integration_endpoint_a.pk]))
        second = client_a.session["_cnx_credential_reveal"]["secret"]
        assert first != second
        assert len(second) >= 24

    def test_integration_a_rotation_does_not_leak_across_sessions(self, admin_user, member_user,
                                                                  integration_endpoint_a):
        """The reveal rides the ROTATOR's session — a second user's detail GET must not see it."""
        rotator = Client()
        rotator.force_login(admin_user)
        rotator.post(reverse("scm:integrationendpoint_rotate_credential",
                             args=[integration_endpoint_a.pk]))
        bystander = Client()
        bystander.force_login(member_user)
        page = bystander.get(reverse("scm:integrationendpoint_detail",
                                     args=[integration_endpoint_a.pk]))
        assert page.status_code == 200
        assert page.context["plaintext_once"] is None


# =================================================================================================
# POST-only routes, absent routes and the no-transport guarantee
# =================================================================================================
class TestIntegrationPostOnlyRoutes:
    @pytest.mark.parametrize("url_name,fixture_name", _INTEGRATION_POST_ONLY_ROUTES,
                             ids=[name.split(":")[1] for name, _ in _INTEGRATION_POST_ONLY_ROUTES])
    def test_integration_get_on_a_post_only_route_is_405(self, request, client_a, url_name,
                                                         fixture_name):
        obj = request.getfixturevalue(fixture_name)
        response = client_a.get(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 405
        assert type(obj).objects.filter(pk=obj.pk).exists()

    def test_integration_get_on_delete_deletes_nothing(self, client_a, integration_endpoint_a,
                                                       integration_subscription_a):
        from apps.scm.models import IntegrationEndpoint, WebhookSubscription
        assert client_a.get(reverse("scm:integrationendpoint_delete",
                                    args=[integration_endpoint_a.pk])).status_code == 405
        assert IntegrationEndpoint.objects.filter(pk=integration_endpoint_a.pk).exists()
        assert client_a.get(reverse("scm:webhooksubscription_delete",
                                    args=[integration_subscription_a.pk])).status_code == 405
        assert WebhookSubscription.objects.filter(pk=integration_subscription_a.pk).exists()

    def test_integration_get_on_rotate_mints_nothing(self, client_a, integration_endpoint_a,
                                                     integration_subscription_a):
        assert client_a.get(reverse("scm:integrationendpoint_rotate_credential",
                                    args=[integration_endpoint_a.pk])).status_code == 405
        assert client_a.get(reverse("scm:webhooksubscription_rotate_secret",
                                    args=[integration_subscription_a.pk])).status_code == 405
        integration_endpoint_a.refresh_from_db()
        integration_subscription_a.refresh_from_db()
        assert integration_endpoint_a.credential_hash == ""
        assert integration_subscription_a.signing_secret_hash == ""
        assert "_cnx_credential_reveal" not in client_a.session
        assert "_whk_secret_reveal" not in client_a.session

    def test_integration_get_on_a_log_verb_moves_no_queue_state(self, client_a,
                                                                integration_message_failed_a,
                                                                integration_delivery_a):
        assert client_a.get(reverse("scm:integrationmessage_reprocess",
                                    args=[integration_message_failed_a.pk])).status_code == 405
        assert client_a.get(reverse("scm:webhookdelivery_retry",
                                    args=[integration_delivery_a.pk])).status_code == 405
        integration_message_failed_a.refresh_from_db()
        integration_delivery_a.refresh_from_db()
        assert integration_message_failed_a.status == "failed"
        assert integration_message_failed_a.attempt_count == 3
        assert integration_delivery_a.status == "failed"
        assert integration_delivery_a.attempt_no == 3


class TestIntegrationAppendOnlyLogsHaveNoWriteRoutes:
    @pytest.mark.parametrize("url_name", _INTEGRATION_ABSENT_ROUTE_NAMES)
    def test_integration_absent_route_name_does_not_resolve(self, url_name):
        """``IntegrationMessage`` and ``WebhookDelivery`` are append-only: a wrong row is corrected
        by appending a later, correct one. A create/edit/delete route for either would be an audit
        trail that can be rewritten after somebody acted on it."""
        with pytest.raises(NoReverseMatch):
            reverse(url_name)
        with pytest.raises(NoReverseMatch):
            reverse(url_name, args=[1])

    def test_integration_neither_log_has_a_modelform(self):
        from apps.scm import forms as scm_forms
        assert not hasattr(scm_forms, "IntegrationMessageForm")
        assert not hasattr(scm_forms, "WebhookDeliveryForm")

    def test_integration_neither_log_has_a_form_module(self):
        package = pathlib.Path(__file__).resolve().parents[1] / "forms" / "IntegrationApiGateway"
        assert package.is_dir()
        assert not (package / "IntegrationMessages.py").exists()
        assert not (package / "WebhookDeliveries.py").exists()

    def test_integration_no_write_view_exists_for_either_log(self):
        from apps.scm import views as scm_views
        for name in ("integrationmessage_create", "integrationmessage_edit",
                     "integrationmessage_delete", "webhookdelivery_create",
                     "webhookdelivery_edit", "webhookdelivery_delete"):
            assert not hasattr(scm_views, name)

    def test_integration_the_four_read_routes_that_DO_exist_still_resolve(self,
                                                                         integration_message_a,
                                                                         integration_delivery_a):
        """POSITIVE (L44): the logs are readable and workable — only unwritable."""
        assert reverse("scm:integrationmessage_list")
        assert reverse("scm:integrationmessage_detail", args=[integration_message_a.pk])
        assert reverse("scm:webhookdelivery_list")
        assert reverse("scm:webhookdelivery_detail", args=[integration_delivery_a.pk])


class TestIntegrationNoOutboundTransport:
    def test_integration_no_transport_module_is_imported_anywhere_under_apps_scm(self):
        """``endpoint_url`` and ``target_url`` are tenant-editable URLs the server would fetch, i.e.
        textbook SSRF. 4.19 ships no transport at all, and this is the assertion that keeps it that
        way: the day one of these appears, an allow-list plus a private-IP block (RFC1918, loopback,
        169.254.0.0/16, IPv6 ULA) and DNS-rebinding re-resolution have to land in the same change.
        """
        app_root = pathlib.Path(__file__).resolve().parents[1]
        offenders = []
        for path in app_root.rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            match = _INTEGRATION_TRANSPORT_IMPORT_RE.search(path.read_text(encoding="utf-8"))
            if match:
                offenders.append(f"{path.relative_to(app_root)}: {match.group(0).strip()}")
        assert not offenders, ("4.19 ships no outbound transport; these modules import one: "
                               + "; ".join(offenders))

    def test_integration_no_reveal_or_test_connection_route_exists(self):
        for url_name in ("scm:integrationendpoint_test_connection",
                         "scm:integrationendpoint_reveal_credential",
                         "scm:integrationendpoint_sync",
                         "scm:webhooksubscription_test_delivery",
                         "scm:webhooksubscription_reveal_secret"):
            with pytest.raises(NoReverseMatch):
                reverse(url_name, args=[1])

    def test_integration_both_verbs_say_out_loud_that_nothing_was_sent(
            self, client_a, integration_message_failed_a, integration_delivery_a):
        """The buttons are called *Reprocess* and *Retry*, so the flash has to say what they did NOT
        do — otherwise a reader reasonably assumes the partner was contacted."""
        reprocess = client_a.post(reverse("scm:integrationmessage_reprocess",
                                          args=[integration_message_failed_a.pk]), follow=True)
        assert any("nothing was sent" in text for text in _integration_flash(reprocess))
        retry = client_a.post(reverse("scm:webhookdelivery_retry",
                                      args=[integration_delivery_a.pk]), follow=True)
        assert any("nothing was sent" in text for text in _integration_flash(retry))


# =================================================================================================
# Query budgets — the tenant filter must not cost a query per row (L18)
# =================================================================================================
class TestIntegrationQueryBudgets:
    def test_integration_endpoint_list_does_not_scale_with_rows(self, client_a, tenant_a,
                                                                integration_endpoint_client_a,
                                                                django_assert_max_num_queries):
        """``logistics_client.__str__`` is ``f"{code} · {party}"``, so the row walks a SECOND hop —
        without ``logistics_client__party`` in ``select_related`` that is one extra query per row."""
        _integration_bulk_endpoints(tenant_a, 14)
        with django_assert_max_num_queries(14):
            response = client_a.get(reverse("scm:integrationendpoint_list"))
            assert len(response.context["object_list"]) == 15

    def test_integration_message_list_does_not_scale_with_rows(self, client_a, tenant_a,
                                                               integration_endpoint_a,
                                                               django_assert_max_num_queries):
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 30)
        with django_assert_max_num_queries(14):
            response = client_a.get(reverse("scm:integrationmessage_list"))
            assert len(response.context["object_list"]) == 30

    def test_integration_delivery_list_does_not_scale_with_rows(self, client_a, tenant_a,
                                                                integration_subscription_a,
                                                                django_assert_max_num_queries):
        _integration_bulk_deliveries(tenant_a, integration_subscription_a, 30)
        with django_assert_max_num_queries(14):
            response = client_a.get(reverse("scm:webhookdelivery_list"))
            assert len(response.context["object_list"]) == 30

    def test_integration_exceptions_rollup_is_one_grouped_query_not_one_per_row(
            self, client_a, tenant_a, integration_endpoint_a, django_assert_max_num_queries):
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 30, status="failed",
                                   error_code="HTTP_500")
        with django_assert_max_num_queries(14):
            response = client_a.get(reverse("scm:integration_exceptions"))
            assert response.context["error_groups"][0]["count"] == 30
