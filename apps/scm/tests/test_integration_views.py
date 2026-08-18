"""SCM 4.19 Integration & API Gateway - the VIEW / CRUD integration lane.

What a **request** does, end to end, across the sub-module's nineteen routes. The other three 4.19
lanes own the model arithmetic (``test_integration_models.py``), the two form field lists
(``test_integration_forms.py``) and tenant isolation / auth gates / CSRF / the method guards
(``test_integration_security.py``). This file asserts that every GET page renders its contracted
template with every contracted context key **populated** - a key that merely exists proves nothing
(L41) - that each filter narrows, that page 2 is real, that every create/edit POST lands in
``request.tenant``, and that each of the four POST verbs DOES what it says and SAYS what it did.

Seven things worth knowing before editing this file:

* **PAGE SIZE IS NOT UNIFORM.** ``integrationendpoint_list`` and ``webhooksubscription_list`` use
  ``crud_list``'s default 15 (a page-2 case needs 16+ rows); ``integrationmessage_list``,
  ``webhookdelivery_list`` and ``integration_exceptions`` use 30 (``MESSAGES_PER_PAGE`` /
  ``DELIVERIES_PER_PAGE`` - a page-2 case needs 31+). Getting this backwards makes a pagination
  test silently assert nothing (L9).
* **Five list routes, one view.** ``integrationendpoint_list`` also serves the four category routes;
  ``category`` arrives from the URLconf's extra-options dict, so it is code-controlled and pins both
  the queryset AND ``stats`` before pagination.
* **The context key is ``lifecycle_choices`` while its GET param is ``lifecycle_stage``.** Pinned,
  not a typo - both halves are asserted below so a rename cannot silently blank the widget (L7).
* **Two logs are append-only.** ``IntegrationMessage`` and ``WebhookDelivery`` have no form and no
  create/edit/delete route; the only writes they take are ``reprocess`` and ``retry``. Asserting
  the ABSENCE of those routes is the security lane's job, not this one's.
* **Neither rotate verb dials anything** and neither flash carries the plaintext (L25) - the secret
  rides a pop-once session key and surfaces exactly once as ``plaintext_once``. What is asserted
  HERE is the verb's own contract (the marker it stores, its redirect, its flash); the pop-once
  reveal itself belongs to the security lane's ``TestIntegrationSecretHandling``.
* **Gate asymmetry**: the ENDPOINT's create and edit are plain ``@login_required`` (only delete and
  rotate are admin-gated), while the SUBSCRIPTION's create/edit/delete/rotate are ALL admin-gated.
  Every POST below therefore runs as ``client_a`` (a tenant admin); the member half is the security
  lane's.
* **Dates come from ``timezone.localdate()`` / ``timezone.now()``**, never ``datetime.date.today()``
  (L16) - the same basis ``occurred_at``, ``triggered_at`` and both date-window helpers read. Every
  window assertion below pins its rows to explicit moments rather than to "a few hours ago", so it
  cannot flake in the hours either side of local midnight.

NAMING: every test is ``test_integration_*`` and every module-level helper/fixture
``_integration_*`` (the hygiene guard in ``test_suite_hygiene.py`` parses this file and fails on any
module-level name defined twice).
"""
import datetime

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone


# =================================================================================================
# Module-level helpers - all `_integration_` prefixed.
# =================================================================================================
def _integration_templates(response):
    """Every template name that took part in rendering ``response``."""
    return [t.name for t in response.templates if t.name]


def _integration_flashes(response):
    """Every flashed message on the request that produced ``response``, as plain strings."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _integration_said(response, fragment):
    """True when any flashed message contains ``fragment`` (case-insensitive)."""
    return any(fragment.lower() in message.lower() for message in _integration_flashes(response))


def _integration_query_count(client, url, params=None):
    """How many queries one GET of ``url`` costs.

    The N+1 assertions below are that this number does not MOVE as the page fills up; a fixed
    ceiling alone only ever says "not too many today".
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url, params or {})
    assert response.status_code == 200
    return len(captured.captured_queries)


def _integration_moment_today(hour, minute=0):
    """An AWARE moment inside today, derived from ``timezone.localdate()`` (L16).

    The two date-window cases need a row whose time-of-day is known: one at 23:30 is exactly the row
    a midnight-truncated upper bound silently drops. Pinning it to a literal hour rather than to
    "an hour ago" keeps the assertion true at whatever hour the suite runs.
    """
    naive = datetime.datetime.combine(timezone.localdate(), datetime.time(hour, minute))
    return timezone.make_aware(naive) if timezone.is_naive(naive) else naive


def _integration_bulk_endpoints(tenant, count, start=0, category="custom", client=None,
                                party=None, location=None):
    """``count`` extra connections - enough to push a 15-row page into a second one.

    ``name`` varies because ``("tenant", "name")`` is unique, and ``start`` lets a caller add a
    SECOND batch without colliding. The three FK arguments exist for the N+1 case: with
    ``logistics_client`` set, each row's rendering walks ``LogisticsClient.party`` as well, which is
    the chained ``__str__`` hop ``select_related("logistics_client__party")`` is there to cover.
    """
    from apps.scm.models import IntegrationEndpoint
    return [IntegrationEndpoint.objects.create(
        tenant=tenant, name=f"Bulk connector {index:03d}", category=category,
        system="custom", direction="outbound", transport="api_rest",
        endpoint_url=f"https://bulk-{index:03d}.example.com/hook",
        environment="sandbox", lifecycle_stage="setup", status="disconnected",
        logistics_client=client, partner_party=party, location=location)
        for index in range(start, start + count)]


def _integration_bulk_messages(tenant, endpoint, count, start=0, status="sent",
                               document_type="edi_850"):
    """``count`` extra exchange rows on one endpoint - what makes ``?page=2`` real at 30.

    ``occurred_at`` steps backwards so the ``["-occurred_at", "-id"]`` order is a total one and
    page 2 is deterministic rather than depending on row order.
    """
    from apps.scm.models import IntegrationMessage
    now = timezone.now()
    return [IntegrationMessage.objects.create(
        tenant=tenant, endpoint=endpoint, direction="outbound", document_type=document_type,
        status=status, control_number=f"9{index:08d}", record_count=1,
        occurred_at=now - datetime.timedelta(minutes=index + 1),
        source="none", error_code="BULK_CODE" if status == "failed" else "")
        for index in range(start, start + count)]


def _integration_bulk_subscriptions(tenant, count, start=0):
    """``count`` extra push rules - a full 15-row page plus a second one."""
    from apps.scm.models import WebhookSubscription
    return [WebhookSubscription.objects.create(
        tenant=tenant, name=f"Bulk rule {index:03d}", trigger_entity="stock_move",
        trigger_event="created", target_url=f"https://bulk-{index:03d}.example.com/events",
        payload_format="json")
        for index in range(start, start + count)]


def _integration_bulk_deliveries(tenant, subscription, count, start=0, status="pending"):
    """``count`` extra delivery attempts - what makes ``?page=2`` real at 30."""
    from apps.scm.models import WebhookDelivery
    now = timezone.now()
    return [WebhookDelivery.objects.create(
        tenant=tenant, subscription=subscription, event="stock_move.created", status=status,
        attempt_no=1, triggered_at=now - datetime.timedelta(minutes=index + 1))
        for index in range(start, start + count)]


def _integration_endpoint_payload(**overrides):
    """A POST body ``IntegrationEndpointForm`` accepts.

    ``number`` is auto (CNX-#####) and never posted; neither credential column can be posted at all
    (both are ``editable=False``). The eight choice columns are ``blank=False`` with a model
    default, so a BOUND form requires each of them even though ``objects.create()`` does not.
    """
    payload = {
        "name": "Oracle Fusion procurement link",
        "category": "erp",
        "system": "oracle",
        "direction": "outbound",
        "transport": "sftp",
        "auth_method": "ssh_key",
        "endpoint_url": "sftp://edi.oracle-partner.example.net/outbound",
        "external_account_ref": "ACME-ORA-01",
        "partner_party": "",
        "logistics_client": "",
        "location": "",
        "spec_document": "",
        "interchange_id": "",
        "interchange_qualifier": "",
        "device_identifier": "",
        "trigger_mode": "scheduled",
        "schedule_note": "Nightly at 02:00 local",
        "environment": "sandbox",
        "lifecycle_stage": "setup",
        "status": "disconnected",
        "is_active": "on",
        "notes": "Registered by the CRUD test.",
    }
    payload.update(overrides)
    return payload


def _integration_subscription_payload(**overrides):
    """A POST body ``WebhookSubscriptionForm`` accepts.

    ``headers`` posts blank on purpose - ``clean_headers`` turns an empty value into ``{}`` rather
    than ``None``, which is what keeps the JSON column's ``default=dict`` honest.
    """
    payload = {
        "name": "Notify the ERP when a work order is approved",
        "trigger_entity": "work_order",
        "trigger_event": "approved",
        "target_url": "https://erp.example.com/hooks/work-order-approved",
        "payload_format": "json",
        "filter_expression": "",
        "include_fields": "number,status",
        "headers": "",
        "auto_disable_threshold": "8",
        "is_active": "on",
        "description": "Registered by the CRUD test.",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def _integration_endpoint_world(integration_endpoint_a, integration_endpoint_iot_a,
                                integration_endpoint_edi_a, integration_endpoint_client_a,
                                integration_endpoint_disabled_a,
                                integration_endpoint_with_credential_a):
    """All six tenant_a connections at once, keyed by the value each one is the ONLY carrier of.

    Every filter case below narrows on a value no other row in this workspace holds, so a filter
    that silently stopped applying would show six rows where the test demands one.
    """
    return {
        "erp": integration_endpoint_a,
        "iot": integration_endpoint_iot_a,
        "edi": integration_endpoint_edi_a,
        "client": integration_endpoint_client_a,
        "disabled": integration_endpoint_disabled_a,
        "credential": integration_endpoint_with_credential_a,
    }


# =================================================================================================
# 1. IntegrationEndpoint - the connection register (five routes, one view)
# =================================================================================================
@pytest.mark.django_db
class TestIntegrationEndpointList:
    """200, the pinned context, seven filters, search, page 2 and a flat query count."""

    def test_integration_endpoint_list_renders_the_contracted_template_and_context(
            self, client_a, _integration_endpoint_world):
        from apps.scm.models import (ENDPOINT_CATEGORY_CHOICES, ENDPOINT_DIRECTION_CHOICES,
                                     ENDPOINT_STATUS_CHOICES, ENDPOINT_SYSTEM_CHOICES,
                                     ENVIRONMENT_CHOICES, LIFECYCLE_STAGE_CHOICES,
                                     TRANSPORT_CHOICES)
        response = client_a.get(reverse("scm:integrationendpoint_list"))
        assert response.status_code == 200
        assert "scm/integration/integrationendpoint/list.html" in _integration_templates(response)

        ctx = response.context
        assert {obj.pk for obj in ctx["object_list"]} == {
            obj.pk for obj in _integration_endpoint_world.values()}
        assert ctx["page_obj"].paginator.count == 6
        assert ctx["q"] == ""
        # Populated, not merely present (L41) - an empty <select> is a filter nobody can use.
        assert list(ctx["category_choices"]) == list(ENDPOINT_CATEGORY_CHOICES)
        assert list(ctx["system_choices"]) == list(ENDPOINT_SYSTEM_CHOICES)
        assert list(ctx["direction_choices"]) == list(ENDPOINT_DIRECTION_CHOICES)
        assert list(ctx["transport_choices"]) == list(TRANSPORT_CHOICES)
        assert list(ctx["status_choices"]) == list(ENDPOINT_STATUS_CHOICES)
        assert list(ctx["environment_choices"]) == list(ENVIRONMENT_CHOICES)
        # The KEY is `lifecycle_choices` while the GET PARAM is `lifecycle_stage` - pinned (L7).
        assert list(ctx["lifecycle_choices"]) == list(LIFECYCLE_STAGE_CHOICES)
        assert ctx["active_category"] == ""
        assert ctx["is_tenant_admin"] is True

    def test_integration_endpoint_list_orders_by_name_then_id(
            self, client_a, _integration_endpoint_world):
        """A total order, stated on the queryset - without it page 2 depends on row order."""
        names = [obj.name for obj in
                 client_a.get(reverse("scm:integrationendpoint_list")).context["object_list"]]
        assert names == sorted(names)

    def test_integration_endpoint_list_stats_carry_exactly_five_keys(
            self, client_a, _integration_endpoint_world):
        stats = client_a.get(reverse("scm:integrationendpoint_list")).context["stats"]
        assert set(stats) == {"total", "connected", "error", "disabled", "active"}
        assert stats["total"] == 6
        assert stats["connected"] == 4
        assert stats["error"] == 1
        assert stats["disabled"] == 1
        assert stats["active"] == 5

    def test_integration_endpoint_list_stats_ignore_the_search_and_the_filters(
            self, client_a, _integration_endpoint_world):
        """The header answers "how is the workspace", the table answers "what did I filter to"."""
        response = client_a.get(reverse("scm:integrationendpoint_list"),
                                {"q": "zzz-matches-nothing", "status": "error"})
        assert response.status_code == 200
        assert list(response.context["object_list"]) == []
        assert response.context["stats"]["total"] == 6, "stats must not follow the filtered page"

    def test_integration_endpoint_list_is_not_tenant_admin_for_a_member(
            self, member_client, integration_endpoint_a):
        """The key gates the row Delete form only; the decorator on the route is the boundary."""
        response = member_client.get(reverse("scm:integrationendpoint_list"))
        assert response.status_code == 200
        assert response.context["is_tenant_admin"] is False

    @pytest.mark.parametrize("term,expected", [
        ("SAP S/4HANA", "erp"),
        ("NAVERP-SCM-PRD", "erp"),
        ("ZZ12345678", "edi"),
        ("RDR-DOCK-01", "iot"),
    ])
    def test_integration_endpoint_list_search_covers_every_contracted_field(
            self, client_a, _integration_endpoint_world, term, expected):
        """name / external_account_ref / interchange_id / device_identifier (number below)."""
        response = client_a.get(reverse("scm:integrationendpoint_list"), {"q": term})
        assert response.status_code == 200
        assert response.context["q"] == term
        assert [obj.pk for obj in response.context["object_list"]] == [
            _integration_endpoint_world[expected].pk]

    def test_integration_endpoint_list_search_matches_the_auto_number(
            self, client_a, _integration_endpoint_world):
        target = _integration_endpoint_world["credential"]
        response = client_a.get(reverse("scm:integrationendpoint_list"), {"q": target.number})
        assert [obj.pk for obj in response.context["object_list"]] == [target.pk]

    @pytest.mark.parametrize("param,value,expected", [
        ("category", "iot", ["iot"]),
        ("system", "shopify", ["credential"]),
        ("direction", "inbound", ["credential", "iot"]),
        ("transport", "as2", ["edi"]),
        ("status", "disabled", ["disabled"]),
        ("environment", "sandbox", ["disabled"]),
        ("lifecycle_stage", "setup", ["disabled"]),
    ])
    def test_integration_endpoint_list_every_filter_narrows(
            self, client_a, _integration_endpoint_world, param, value, expected):
        """All seven are plain STRING equality - no `is_int` guard is involved on this page."""
        response = client_a.get(reverse("scm:integrationendpoint_list"), {param: value})
        assert response.status_code == 200
        assert {obj.pk for obj in response.context["object_list"]} == {
            _integration_endpoint_world[key].pk for key in expected}

    @pytest.mark.parametrize("param", ["category", "system", "direction", "transport", "status",
                                       "environment", "lifecycle_stage"])
    def test_integration_endpoint_list_junk_filter_value_is_an_empty_200(
            self, client_a, _integration_endpoint_world, param):
        """A hand-edited value narrows to nothing rather than 500-ing (L11)."""
        response = client_a.get(reverse("scm:integrationendpoint_list"), {param: "abc"})
        assert response.status_code == 200, f"?{param}=abc 500'd"
        assert list(response.context["object_list"]) == []
        assert response.context["stats"]["total"] == 6

    def test_integration_endpoint_list_paginates_at_fifteen_with_a_real_page_two(
            self, client_a, tenant_a):
        _integration_bulk_endpoints(tenant_a, 21)
        page1 = client_a.get(reverse("scm:integrationendpoint_list"))
        assert len(page1.context["object_list"]) == 15
        assert page1.context["page_obj"].has_next() is True

        page2 = client_a.get(reverse("scm:integrationendpoint_list"), {"page": "2"})
        assert page2.status_code == 200
        assert len(page2.context["object_list"]) == 6
        assert page2.context["page_obj"].number == 2
        assert not ({obj.pk for obj in page1.context["object_list"]}
                    & {obj.pk for obj in page2.context["object_list"]})

    @pytest.mark.parametrize("page", ["999", "abc", "0", "-1", ""])
    def test_integration_endpoint_list_page_past_the_end_or_junk_is_200(
            self, client_a, tenant_a, page):
        _integration_bulk_endpoints(tenant_a, 21)
        response = client_a.get(reverse("scm:integrationendpoint_list"), {"page": page})
        assert response.status_code == 200, f"?page={page} 500'd"
        assert response.context["object_list"], "a junk page must still render rows"

    def test_integration_endpoint_list_is_flat_not_one_query_per_row(
            self, client_a, tenant_a, tpl_client_shared_a, supplier_a, location_a,
            django_assert_max_num_queries):
        """`select_related` must cover the CHAINED hop: LogisticsClient.__str__ walks `party`."""
        url = reverse("scm:integrationendpoint_list")
        _integration_bulk_endpoints(tenant_a, 3, client=tpl_client_shared_a, party=supplier_a,
                                    location=location_a)
        few = _integration_query_count(client_a, url)

        _integration_bulk_endpoints(tenant_a, 18, start=50, client=tpl_client_shared_a,
                                    party=supplier_a, location=location_a)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 15
        assert _integration_query_count(client_a, url) == few, (
            "the connection register queries per row - join the FKs (including "
            "logistics_client__party) instead")

    def test_integration_endpoint_list_never_shows_another_workspaces_rows(
            self, client_a, integration_endpoint_a, integration_endpoint_b):
        rows = client_a.get(reverse("scm:integrationendpoint_list")).context["object_list"]
        assert [obj.pk for obj in rows] == [integration_endpoint_a.pk]


@pytest.mark.django_db
class TestIntegrationEndpointCategoryRoutes:
    """Four sidebar bullets, one view - `category` arrives from the URLconf, never from the query."""

    @pytest.mark.parametrize("route,category,expected", [
        ("scm:integrationendpoint_erp_list", "erp", ["erp"]),
        ("scm:integrationendpoint_ecommerce_list", "ecommerce", ["credential"]),
        ("scm:integrationendpoint_iot_list", "iot", ["iot"]),
        ("scm:integrationendpoint_edi_list", "edi", ["edi", "client"]),
    ])
    def test_integration_endpoint_category_route_pins_the_queryset_and_active_category(
            self, client_a, _integration_endpoint_world, route, category, expected):
        response = client_a.get(reverse(route))
        assert response.status_code == 200
        assert "scm/integration/integrationendpoint/list.html" in _integration_templates(response)
        assert response.context["active_category"] == category
        assert {obj.pk for obj in response.context["object_list"]} == {
            _integration_endpoint_world[key].pk for key in expected}

    def test_integration_endpoint_category_route_scopes_the_stats_too(
            self, client_a, _integration_endpoint_world):
        """On the EDI page "2 total" must mean 2 EDI connections, not 6 connections."""
        stats = client_a.get(reverse("scm:integrationendpoint_edi_list")).context["stats"]
        assert stats["total"] == 2
        assert stats["connected"] == 2
        assert stats["error"] == 0
        assert stats["disabled"] == 0
        assert stats["active"] == 2

    def test_integration_endpoint_category_route_applies_the_pin_before_pagination(
            self, client_a, tenant_a):
        """A category applied AFTER paging would show custom rows on the EDI page's page 2."""
        _integration_bulk_endpoints(tenant_a, 20, category="custom")
        _integration_bulk_endpoints(tenant_a, 3, start=90, category="edi")
        response = client_a.get(reverse("scm:integrationendpoint_edi_list"))
        assert response.context["page_obj"].paginator.count == 3
        assert {obj.category for obj in response.context["object_list"]} == {"edi"}

    def test_integration_endpoint_category_route_with_a_conflicting_query_param_is_empty_200(
            self, client_a, _integration_endpoint_world):
        """Only reachable by hand-editing the URL; it narrows to nothing, never 500s."""
        response = client_a.get(reverse("scm:integrationendpoint_edi_list"), {"category": "iot"})
        assert response.status_code == 200
        assert list(response.context["object_list"]) == []


@pytest.mark.django_db
class TestIntegrationEndpointCrud:
    """create / detail / edit / delete, and what each one puts in the context."""

    def test_integration_endpoint_create_get_renders_the_form_without_obj(self, client_a):
        response = client_a.get(reverse("scm:integrationendpoint_create"))
        assert response.status_code == 200
        assert "scm/integration/integrationendpoint/form.html" in _integration_templates(response)
        assert response.context["is_edit"] is False
        assert response.context["form"] is not None
        # `obj` DOES NOT EXIST here - every {{ obj.* }} must sit inside {% if is_edit %} (L7/L8).
        assert response.context.get("obj") is None

    def test_integration_endpoint_create_post_saves_into_the_request_tenant(
            self, client_a, tenant_a, tenant_b):
        from apps.scm.models import IntegrationEndpoint
        response = client_a.post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload())
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:integrationendpoint_list")

        obj = IntegrationEndpoint.objects.get(name="Oracle Fusion procurement link")
        assert obj.tenant_id == tenant_a.pk and obj.tenant_id != tenant_b.pk
        assert obj.number.startswith("CNX-") and len(obj.number) == len("CNX-00001")
        assert obj.transport == "sftp" and obj.category == "erp"
        # Nothing on the form can reach the credential columns or the system counters.
        assert obj.credential_prefix == "" and obj.credential_hash == ""
        assert obj.consecutive_failures == 0 and obj.last_run_at is None
        assert _integration_said(response, "Created successfully")

    def test_integration_endpoint_create_post_rejects_a_missing_name_without_saving(
            self, client_a):
        from apps.scm.models import IntegrationEndpoint
        response = client_a.post(reverse("scm:integrationendpoint_create"),
                                 _integration_endpoint_payload(name=""))
        assert response.status_code == 200
        assert "name" in response.context["form"].errors
        assert IntegrationEndpoint.objects.count() == 0

    def test_integration_endpoint_detail_renders_every_contracted_key(
            self, client_a, integration_endpoint_edi_a, integration_message_a,
            integration_message_ack_a, integration_message_acknowledged_a):
        response = client_a.get(reverse("scm:integrationendpoint_detail",
                                        args=[integration_endpoint_edi_a.pk]))
        assert response.status_code == 200
        assert "scm/integration/integrationendpoint/detail.html" in _integration_templates(response)

        ctx = response.context
        assert ctx["obj"].pk == integration_endpoint_edi_a.pk
        assert [row.pk for row in ctx["recent_messages"]] == [
            integration_message_acknowledged_a.pk, integration_message_ack_a.pk,
            integration_message_a.pk]
        assert set(ctx["message_stats"]) == {"total", "pending", "sent", "received",
                                             "acknowledged", "failed", "ignored"}
        assert ctx["message_stats"]["total"] == 3
        assert ctx["message_stats"]["sent"] == 1
        assert ctx["message_stats"]["received"] == 1
        assert ctx["message_stats"]["acknowledged"] == 1
        assert ctx["message_stats"]["failed"] == 0
        assert ctx["is_tenant_admin"] is True
        # No rotation happened on this request, so the pop-once reveal is empty.
        assert ctx["plaintext_once"] is None

    def test_integration_endpoint_detail_panel_is_capped_at_ten_newest_first(
            self, client_a, tenant_a, integration_endpoint_a):
        rows = _integration_bulk_messages(tenant_a, integration_endpoint_a, 12)
        ctx = client_a.get(reverse("scm:integrationendpoint_detail",
                                   args=[integration_endpoint_a.pk])).context
        assert len(ctx["recent_messages"]) == 10, "the panel slice must bound what is FETCHED"
        assert [row.pk for row in ctx["recent_messages"]] == [row.pk for row in rows[:10]]
        assert ctx["message_stats"]["total"] == 12, "the aggregate counts ALL rows, not the slice"

    def test_integration_endpoint_detail_panel_never_shows_another_workspaces_log(
            self, client_a, integration_endpoint_a, integration_message_b):
        ctx = client_a.get(reverse("scm:integrationendpoint_detail",
                                   args=[integration_endpoint_a.pk])).context
        assert list(ctx["recent_messages"]) == []
        assert ctx["message_stats"]["total"] == 0

    def test_integration_endpoint_edit_get_carries_form_obj_and_is_edit(
            self, client_a, integration_endpoint_a):
        response = client_a.get(reverse("scm:integrationendpoint_edit",
                                        args=[integration_endpoint_a.pk]))
        assert response.status_code == 200
        assert "scm/integration/integrationendpoint/form.html" in _integration_templates(response)
        assert response.context["is_edit"] is True
        assert response.context["obj"].pk == integration_endpoint_a.pk
        assert response.context["form"].instance.pk == integration_endpoint_a.pk

    def test_integration_endpoint_edit_post_updates_and_returns_to_the_list(
            self, client_a, tenant_a, integration_endpoint_a):
        payload = _integration_endpoint_payload(name="SAP S/4HANA master data (retargeted)",
                                                status="error", lifecycle_stage="suspended")
        response = client_a.post(
            reverse("scm:integrationendpoint_edit", args=[integration_endpoint_a.pk]), payload)
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:integrationendpoint_list")

        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.name == "SAP S/4HANA master data (retargeted)"
        assert integration_endpoint_a.status == "error"
        assert integration_endpoint_a.lifecycle_stage == "suspended"
        assert integration_endpoint_a.tenant_id == tenant_a.pk
        assert _integration_said(response, "Updated successfully")

    def test_integration_endpoint_delete_get_is_405_and_deletes_nothing(
            self, client_a, integration_endpoint_a):
        from apps.scm.models import IntegrationEndpoint
        response = client_a.get(reverse("scm:integrationendpoint_delete",
                                        args=[integration_endpoint_a.pk]))
        assert response.status_code == 405
        assert IntegrationEndpoint.objects.filter(pk=integration_endpoint_a.pk).exists()

    def test_integration_endpoint_delete_post_removes_the_row_and_its_exchange_log(
            self, client_a, integration_endpoint_iot_a, integration_message_failed_a):
        from apps.scm.models import IntegrationEndpoint, IntegrationMessage
        response = client_a.post(reverse("scm:integrationendpoint_delete",
                                         args=[integration_endpoint_iot_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:integrationendpoint_list")
        assert not IntegrationEndpoint.objects.filter(pk=integration_endpoint_iot_a.pk).exists()
        assert not IntegrationMessage.objects.filter(pk=integration_message_failed_a.pk).exists()

        assert _integration_said(response, "Deleted successfully")
        # The extra info line says what ELSE went - the green bar cannot express that.
        assert _integration_said(response, "1 exchange log row(s)")

    def test_integration_endpoint_delete_post_without_a_log_flashes_only_the_green_bar(
            self, client_a, integration_endpoint_a):
        response = client_a.post(reverse("scm:integrationendpoint_delete",
                                         args=[integration_endpoint_a.pk]))
        assert response.status_code == 302
        assert _integration_said(response, "Deleted successfully")
        assert not _integration_said(response, "exchange log row")


@pytest.mark.django_db
class TestIntegrationEndpointRotateCredential:
    """The one action: mint, store a marker, redirect. It dials nothing.

    The pop-once reveal itself is asserted next door in ``test_integration_security.py``'s
    ``TestIntegrationSecretHandling`` - that lane owns secret handling, and duplicating it here only
    creates two places to disagree about it.
    """

    def test_integration_endpoint_rotate_credential_get_is_405(
            self, client_a, integration_endpoint_a):
        response = client_a.get(reverse("scm:integrationendpoint_rotate_credential",
                                        args=[integration_endpoint_a.pk]))
        assert response.status_code == 405
        integration_endpoint_a.refresh_from_db()
        assert integration_endpoint_a.credential_hash == ""

    def test_integration_endpoint_rotate_credential_post_stores_only_a_prefix_and_a_digest(
            self, client_a, integration_endpoint_a):
        from apps.scm.models import IntegrationEndpoint
        response = client_a.post(reverse("scm:integrationendpoint_rotate_credential",
                                         args=[integration_endpoint_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:integrationendpoint_detail",
                                               args=[integration_endpoint_a.pk])

        integration_endpoint_a.refresh_from_db()
        assert len(integration_endpoint_a.credential_prefix) == 8
        assert len(integration_endpoint_a.credential_hash) == 64
        plaintext = client_a.session["_cnx_credential_reveal"]["secret"]
        assert integration_endpoint_a.credential_hash == IntegrationEndpoint.hash_secret(plaintext)
        assert integration_endpoint_a.masked == (integration_endpoint_a.credential_prefix
                                                 + "•" * 8)
        # L25: the flash fires but carries no secret - the plaintext rides the session key.
        assert _integration_said(response, "Credential rotated")
        assert all(plaintext not in flash for flash in _integration_flashes(response))


# =================================================================================================
# 2. IntegrationMessage - the append-only exchange log
# =================================================================================================
@pytest.mark.django_db
class TestIntegrationMessageList:
    """200, the pinned context, five filters plus the date window, page 2 at THIRTY."""

    def test_integration_message_list_renders_the_contracted_template_and_context(
            self, client_a, integration_message_a, integration_message_failed_a,
            integration_endpoint_edi_a):
        from apps.scm.models import (DOCUMENT_TYPE_CHOICES, MESSAGE_DIRECTION_CHOICES,
                                     MESSAGE_SOURCE_CHOICES, MESSAGE_STATUS_CHOICES)
        response = client_a.get(reverse("scm:integrationmessage_list"))
        assert response.status_code == 200
        assert "scm/integration/integrationmessage/list.html" in _integration_templates(response)

        ctx = response.context
        assert {row.pk for row in ctx["object_list"]} == {integration_message_a.pk,
                                                          integration_message_failed_a.pk}
        assert ctx["page_obj"].paginator.count == 2
        assert ctx["q"] == ""
        assert integration_endpoint_edi_a.pk in {e.pk for e in ctx["endpoints"]}
        assert list(ctx["direction_choices"]) == list(MESSAGE_DIRECTION_CHOICES)
        assert list(ctx["document_type_choices"]) == list(DOCUMENT_TYPE_CHOICES)
        assert list(ctx["status_choices"]) == list(MESSAGE_STATUS_CHOICES)
        assert list(ctx["source_choices"]) == list(MESSAGE_SOURCE_CHOICES)
        assert ctx["date_from"] == "" and ctx["date_to"] == ""
        assert "append-only" in ctx["append_only_note"].lower()

    def test_integration_message_list_orders_newest_first(
            self, client_a, integration_message_a, integration_message_failed_a):
        rows = list(client_a.get(reverse("scm:integrationmessage_list")).context["object_list"])
        assert [row.pk for row in rows] == [integration_message_failed_a.pk,
                                            integration_message_a.pk]

    def test_integration_message_list_stats_carry_exactly_four_keys_over_the_workspace(
            self, client_a, integration_message_a, integration_message_acknowledged_a,
            integration_message_failed_a):
        response = client_a.get(reverse("scm:integrationmessage_list"), {"status": "failed"})
        stats = response.context["stats"]
        assert set(stats) == {"total", "pending", "failed", "acknowledged"}
        assert stats["total"] == 3, "stats must not follow the filtered page"
        assert stats["failed"] == 1
        assert stats["acknowledged"] == 1
        assert stats["pending"] == 0

    def test_integration_message_list_endpoints_dropdown_is_tenant_scoped(
            self, client_a, integration_endpoint_a, integration_endpoint_b):
        endpoints = client_a.get(reverse("scm:integrationmessage_list")).context["endpoints"]
        assert [e.pk for e in endpoints] == [integration_endpoint_a.pk]

    @pytest.mark.parametrize("field,term", [
        ("number", None),
        ("control_number", "000000412"),
        ("source_reference", "PO-"),
    ])
    def test_integration_message_list_search_covers_the_contracted_fields(
            self, client_a, integration_message_a, integration_message_failed_a, field, term):
        value = integration_message_a.number if term is None else term
        response = client_a.get(reverse("scm:integrationmessage_list"), {"q": value})
        assert response.status_code == 200
        assert integration_message_a.pk in {row.pk for row in response.context["object_list"]}
        assert integration_message_failed_a.pk not in {
            row.pk for row in response.context["object_list"]}

    def test_integration_message_list_search_matches_the_external_id(
            self, client_a, integration_message_a, integration_message_failed_http_a):
        response = client_a.get(reverse("scm:integrationmessage_list"),
                                {"q": "c8a0d4b2-1f77-42de-9c05-6b1e83f5aa10"})
        assert [row.pk for row in response.context["object_list"]] == [
            integration_message_failed_http_a.pk]

    def test_integration_message_list_endpoint_filter_narrows_by_pk(
            self, client_a, integration_message_a, integration_message_failed_a,
            integration_endpoint_iot_a):
        response = client_a.get(reverse("scm:integrationmessage_list"),
                                {"endpoint": str(integration_endpoint_iot_a.pk)})
        assert response.status_code == 200
        assert [row.pk for row in response.context["object_list"]] == [
            integration_message_failed_a.pk]

    @pytest.mark.parametrize("param,value,expected_failed", [
        ("direction", "inbound", True),
        ("direction", "outbound", False),
        ("document_type", "tag_read_batch", True),
        ("status", "failed", True),
        ("status", "sent", False),
        ("source", "stock_move", True),
        ("source", "purchase_order", False),
    ])
    def test_integration_message_list_every_string_filter_narrows(
            self, client_a, integration_message_a, integration_message_failed_a,
            param, value, expected_failed):
        response = client_a.get(reverse("scm:integrationmessage_list"), {param: value})
        assert response.status_code == 200
        wanted = integration_message_failed_a if expected_failed else integration_message_a
        assert [row.pk for row in response.context["object_list"]] == [wanted.pk]

    @pytest.mark.parametrize("value", ["abc", "²", "999999999999999999999", "-4"])
    def test_integration_message_list_junk_endpoint_param_skips_the_filter(
            self, client_a, integration_message_a, value):
        """L11 in all three of its shapes: not decimal, category-No, and over the column width."""
        response = client_a.get(reverse("scm:integrationmessage_list"), {"endpoint": value})
        assert response.status_code == 200, f"?endpoint={value} 500'd"
        assert [row.pk for row in response.context["object_list"]] == [integration_message_a.pk]

    def test_integration_message_list_date_window_is_inclusive_of_the_whole_upper_day(
            self, client_a, tenant_a, integration_endpoint_a):
        """A bare upper bound resolves to MIDNIGHT - the 23:30 row is the one that proves the fix."""
        from apps.scm.models import IntegrationMessage
        late = IntegrationMessage.objects.create(
            tenant=tenant_a, endpoint=integration_endpoint_a, direction="inbound",
            document_type="order_import", status="received",
            occurred_at=_integration_moment_today(23, 30))
        today = timezone.localdate().isoformat()
        response = client_a.get(reverse("scm:integrationmessage_list"),
                                {"date_from": today, "date_to": today})
        assert response.status_code == 200
        assert [row.pk for row in response.context["object_list"]] == [late.pk]
        assert response.context["date_from"] == today and response.context["date_to"] == today

    def test_integration_message_list_date_window_excludes_rows_outside_it(
            self, client_a, tenant_a, integration_endpoint_a):
        from apps.scm.models import IntegrationMessage
        recent = IntegrationMessage.objects.create(
            tenant=tenant_a, endpoint=integration_endpoint_a, direction="inbound",
            document_type="order_import", status="received",
            occurred_at=_integration_moment_today(0, 30))
        old = IntegrationMessage.objects.create(
            tenant=tenant_a, endpoint=integration_endpoint_a, direction="inbound",
            document_type="order_import", status="received",
            occurred_at=timezone.now() - datetime.timedelta(days=10))

        cut = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        newer = client_a.get(reverse("scm:integrationmessage_list"), {"date_from": cut})
        assert [row.pk for row in newer.context["object_list"]] == [recent.pk]

        older_cut = (timezone.localdate() - datetime.timedelta(days=5)).isoformat()
        older = client_a.get(reverse("scm:integrationmessage_list"), {"date_to": older_cut})
        assert [row.pk for row in older.context["object_list"]] == [old.pk]

    @pytest.mark.parametrize("params", [
        {"date_from": "lastweek"},
        {"date_to": "2026-02-30"},
        {"date_from": "", "date_to": ""},
        {"date_from": "13/08/2026"},
    ])
    def test_integration_message_list_junk_date_window_is_skipped_not_raised(
            self, client_a, integration_message_a, params):
        response = client_a.get(reverse("scm:integrationmessage_list"), params)
        assert response.status_code == 200, f"{params} 500'd"
        assert [row.pk for row in response.context["object_list"]] == [integration_message_a.pk]

    def test_integration_message_list_paginates_at_thirty_with_a_real_page_two(
            self, client_a, tenant_a, integration_endpoint_a):
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 31)
        page1 = client_a.get(reverse("scm:integrationmessage_list"))
        assert len(page1.context["object_list"]) == 30, "MESSAGES_PER_PAGE is 30, not 15"
        assert page1.context["page_obj"].has_next() is True

        page2 = client_a.get(reverse("scm:integrationmessage_list"), {"page": "2"})
        assert page2.status_code == 200
        assert len(page2.context["object_list"]) == 1
        assert not ({row.pk for row in page1.context["object_list"]}
                    & {row.pk for row in page2.context["object_list"]})

    @pytest.mark.parametrize("page", ["999", "abc", "0", "-1"])
    def test_integration_message_list_page_past_the_end_or_junk_is_200(
            self, client_a, tenant_a, integration_endpoint_a, page):
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 31)
        response = client_a.get(reverse("scm:integrationmessage_list"), {"page": page})
        assert response.status_code == 200, f"?page={page} 500'd"
        assert response.context["object_list"]

    def test_integration_message_list_is_flat_not_one_query_per_row(
            self, client_a, tenant_a, integration_endpoint_a, django_assert_max_num_queries):
        """`select_related("endpoint")` - without it a page of 30 costs 30 extra queries (L18)."""
        url = reverse("scm:integrationmessage_list")
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 3)
        few = _integration_query_count(client_a, url)

        _integration_bulk_messages(tenant_a, integration_endpoint_a, 31, start=50)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 30
        assert _integration_query_count(client_a, url) == few, (
            "the exchange log queries per row - join the endpoint instead")

    def test_integration_message_list_never_shows_another_workspaces_rows(
            self, client_a, integration_message_a, integration_message_b):
        rows = client_a.get(reverse("scm:integrationmessage_list")).context["object_list"]
        assert [row.pk for row in rows] == [integration_message_a.pk]


@pytest.mark.django_db
class TestIntegrationMessageDetail:
    """One exchange, both ends of its acknowledgement chain, and whether it can be re-queued."""

    def test_integration_message_detail_renders_every_contracted_key(
            self, client_a, integration_message_a, integration_message_ack_a):
        response = client_a.get(reverse("scm:integrationmessage_detail",
                                        args=[integration_message_a.pk]))
        assert response.status_code == 200
        assert "scm/integration/integrationmessage/detail.html" in _integration_templates(response)

        ctx = response.context
        assert ctx["obj"].pk == integration_message_a.pk
        # The chain is rendered BOTH ways: this row's answer is the 997 that acknowledges it.
        assert ctx["ack_message"].pk == integration_message_ack_a.pk
        assert ctx["can_reprocess"] is True
        assert "append-only" in ctx["append_only_note"].lower()

    def test_integration_message_detail_ack_message_is_none_when_nothing_answered_it(
            self, client_a, integration_message_failed_a):
        ctx = client_a.get(reverse("scm:integrationmessage_detail",
                                   args=[integration_message_failed_a.pk])).context
        assert ctx["ack_message"] is None
        assert ctx["can_reprocess"] is True

    def test_integration_message_detail_forward_pointer_is_the_row_it_acknowledges(
            self, client_a, integration_message_a, integration_message_ack_a):
        ctx = client_a.get(reverse("scm:integrationmessage_detail",
                                   args=[integration_message_ack_a.pk])).context
        assert ctx["obj"].acknowledges_id == integration_message_a.pk
        assert ctx["ack_message"] is None

    @pytest.mark.parametrize("status,expected", [("acknowledged", False), ("pending", False)])
    def test_integration_message_detail_can_reprocess_is_false_for_a_blocked_status(
            self, client_a, integration_message_a, status, expected):
        from apps.scm.models import IntegrationMessage
        IntegrationMessage.objects.filter(pk=integration_message_a.pk).update(status=status)
        ctx = client_a.get(reverse("scm:integrationmessage_detail",
                                   args=[integration_message_a.pk])).context
        assert ctx["can_reprocess"] is expected

    def test_integration_message_detail_cross_tenant_pk_is_404(
            self, client_a, integration_message_b):
        response = client_a.get(reverse("scm:integrationmessage_detail",
                                        args=[integration_message_b.pk]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestIntegrationMessageReprocess:
    """Re-queue one row. It sends nothing, and it refuses the two closed statuses (L35).

    The eligible/blocked STATUS MATRIX (and the ``can_reprocess`` flag that has to agree with it)
    lives in ``test_integration_security.py``'s ``TestIntegrationPrerequisiteGuards``; what is
    asserted here is the verb's own contract - the redirect target, the counter, the flash.
    """

    def test_integration_message_reprocess_post_requeues_and_bumps_the_attempt_counter(
            self, client_a, integration_message_failed_a):
        response = client_a.post(reverse("scm:integrationmessage_reprocess",
                                         args=[integration_message_failed_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:integrationmessage_detail",
                                               args=[integration_message_failed_a.pk])

        integration_message_failed_a.refresh_from_db()
        assert integration_message_failed_a.status == "pending"
        assert integration_message_failed_a.attempt_count == 4
        assert integration_message_failed_a.error_code == ""
        assert integration_message_failed_a.error_message == ""
        assert _integration_said(response, "re-queued (attempt 4)")
        assert _integration_said(response, "Nothing was sent to the partner")

    def test_integration_message_reprocess_refuses_an_acknowledged_row_and_changes_nothing(
            self, client_a, integration_message_acknowledged_a):
        before = integration_message_acknowledged_a.attempt_count
        response = client_a.post(reverse("scm:integrationmessage_reprocess",
                                         args=[integration_message_acknowledged_a.pk]))
        assert response.status_code == 302
        integration_message_acknowledged_a.refresh_from_db()
        assert integration_message_acknowledged_a.status == "acknowledged"
        assert integration_message_acknowledged_a.attempt_count == before
        assert _integration_said(response, "cannot be reprocessed")
        assert _integration_said(response, "acknowledged")

    def test_integration_message_reprocess_refuses_a_pending_row(
            self, client_a, integration_message_a):
        from apps.scm.models import IntegrationMessage
        IntegrationMessage.objects.filter(pk=integration_message_a.pk).update(status="pending")
        response = client_a.post(reverse("scm:integrationmessage_reprocess",
                                         args=[integration_message_a.pk]))
        integration_message_a.refresh_from_db()
        assert integration_message_a.attempt_count == 1, "a blocked press must not inflate the count"
        assert _integration_said(response, "cannot be reprocessed")

    def test_integration_message_reprocess_get_is_405_and_changes_nothing(
            self, client_a, integration_message_failed_a):
        response = client_a.get(reverse("scm:integrationmessage_reprocess",
                                        args=[integration_message_failed_a.pk]))
        assert response.status_code == 405
        integration_message_failed_a.refresh_from_db()
        assert integration_message_failed_a.status == "failed"
        assert integration_message_failed_a.attempt_count == 3


@pytest.mark.django_db
class TestIntegrationExceptions:
    """The failure cockpit: the paginated slice AND the grouped roll-up beside it."""

    def test_integration_exceptions_renders_the_contracted_template_and_context(
            self, client_a, integration_message_a, integration_message_failed_a,
            integration_message_failed_http_a):
        from apps.scm.models import DOCUMENT_TYPE_CHOICES, IntegrationEndpoint
        response = client_a.get(reverse("scm:integration_exceptions"))
        assert response.status_code == 200
        # Template rule 6: the report sits at the SUB-MODULE ROOT, not in an entity folder.
        assert "scm/integration/exceptions.html" in _integration_templates(response)

        ctx = response.context
        assert {row.pk for row in ctx["object_list"]} == {integration_message_failed_a.pk,
                                                          integration_message_failed_http_a.pk}
        assert ctx["page_obj"].paginator.count == 2
        assert ctx["q"] == ""
        assert list(ctx["document_type_choices"]) == list(DOCUMENT_TYPE_CHOICES)
        # `endpoints` is the DROPDOWN vocabulary - every connection in the workspace, including the
        # ones with nothing failing on them, so an operator can ask "and this one?" from here.
        assert {e.pk for e in ctx["endpoints"]} >= {integration_message_failed_a.endpoint_id,
                                                    integration_message_failed_http_a.endpoint_id}
        assert {e.pk for e in ctx["endpoints"]} == {
            e.pk for e in IntegrationEndpoint.objects.filter(tenant=integration_message_a.tenant)}
        assert "append-only" in ctx["append_only_note"].lower()

    def test_integration_exceptions_error_groups_roll_up_by_code(
            self, client_a, integration_message_failed_a, integration_message_failed_http_a):
        groups = client_a.get(reverse("scm:integration_exceptions")).context["error_groups"]
        assert groups, "the roll-up must be populated, not merely present"
        assert all(set(group) == {"error_code", "count", "endpoint_count"} for group in groups)
        # -count then error_code: two singletons, so alphabetical.
        assert [group["error_code"] for group in groups] == ["HTTP_429", "LLRP_TIMEOUT"]
        assert [group["count"] for group in groups] == [1, 1]
        assert [group["endpoint_count"] for group in groups] == [1, 1]

    def test_integration_exceptions_group_counts_grow_with_the_rows(
            self, client_a, tenant_a, integration_endpoint_a, integration_message_failed_a):
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 4, status="failed")
        groups = client_a.get(reverse("scm:integration_exceptions")).context["error_groups"]
        assert groups[0] == {"error_code": "BULK_CODE", "count": 4, "endpoint_count": 1}

    def test_integration_exceptions_stats_carry_exactly_three_keys(
            self, client_a, integration_message_failed_a, integration_message_failed_http_a):
        stats = client_a.get(reverse("scm:integration_exceptions")).context["stats"]
        assert set(stats) == {"failed_total", "endpoints_affected", "codes"}
        assert stats["failed_total"] == 2
        assert stats["endpoints_affected"] == 2
        assert stats["codes"] == 2

    def test_integration_exceptions_stats_ignore_the_filters(
            self, client_a, integration_message_failed_a, integration_message_failed_http_a):
        response = client_a.get(reverse("scm:integration_exceptions"), {"q": "zzz"})
        assert list(response.context["object_list"]) == []
        assert response.context["stats"]["failed_total"] == 2

    def test_integration_exceptions_shows_only_failed_rows(
            self, client_a, integration_message_a, integration_message_acknowledged_a,
            integration_message_failed_a):
        rows = client_a.get(reverse("scm:integration_exceptions")).context["object_list"]
        assert [row.pk for row in rows] == [integration_message_failed_a.pk]

    def test_integration_exceptions_filters_narrow_the_table(
            self, client_a, integration_message_failed_a, integration_message_failed_http_a):
        url = reverse("scm:integration_exceptions")
        by_endpoint = client_a.get(url, {"endpoint": str(integration_message_failed_a.endpoint_id)})
        assert [row.pk for row in by_endpoint.context["object_list"]] == [
            integration_message_failed_a.pk]

        by_type = client_a.get(url, {"document_type": "inventory_feed"})
        assert [row.pk for row in by_type.context["object_list"]] == [
            integration_message_failed_http_a.pk]

        by_q = client_a.get(url, {"q": "Dock inbound sweep"})
        assert by_q.context["q"] == "Dock inbound sweep"
        assert [row.pk for row in by_q.context["object_list"]] == [integration_message_failed_a.pk]

    @pytest.mark.parametrize("value", ["abc", "²", "999999999999999999999"])
    def test_integration_exceptions_junk_endpoint_param_skips_the_filter(
            self, client_a, integration_message_failed_a, value):
        response = client_a.get(reverse("scm:integration_exceptions"), {"endpoint": value})
        assert response.status_code == 200, f"?endpoint={value} 500'd"
        assert [row.pk for row in response.context["object_list"]] == [
            integration_message_failed_a.pk]

    def test_integration_exceptions_paginates_at_thirty_with_a_real_page_two(
            self, client_a, tenant_a, integration_endpoint_a):
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 31, status="failed")
        page1 = client_a.get(reverse("scm:integration_exceptions"))
        assert len(page1.context["object_list"]) == 30
        page2 = client_a.get(reverse("scm:integration_exceptions"), {"page": "2"})
        assert page2.status_code == 200
        assert len(page2.context["object_list"]) == 1
        # The roll-up is over the WHOLE filtered set, not the page slice - and so are the stats.
        assert page2.context["error_groups"][0]["count"] == 31
        assert page2.context["stats"]["failed_total"] == 31

    @pytest.mark.parametrize("page", ["999", "abc", "0"])
    def test_integration_exceptions_page_past_the_end_or_junk_is_200(
            self, client_a, tenant_a, integration_endpoint_a, page):
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 31, status="failed")
        response = client_a.get(reverse("scm:integration_exceptions"), {"page": page})
        assert response.status_code == 200, f"?page={page} 500'd"
        assert response.context["object_list"]

    def test_integration_exceptions_is_flat_not_one_query_per_row(
            self, client_a, tenant_a, integration_endpoint_a, django_assert_max_num_queries):
        url = reverse("scm:integration_exceptions")
        _integration_bulk_messages(tenant_a, integration_endpoint_a, 3, status="failed")
        few = _integration_query_count(client_a, url)

        _integration_bulk_messages(tenant_a, integration_endpoint_a, 31, start=50, status="failed")
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 30
        assert _integration_query_count(client_a, url) == few

    def test_integration_exceptions_never_counts_another_workspace(
            self, client_a, integration_message_failed_a, integration_message_b):
        ctx = client_a.get(reverse("scm:integration_exceptions")).context
        assert [row.pk for row in ctx["object_list"]] == [integration_message_failed_a.pk]
        assert ctx["stats"]["failed_total"] == 1


# =================================================================================================
# 3. WebhookSubscription - the outbound event rules
# =================================================================================================
@pytest.mark.django_db
class TestIntegrationWebhookSubscriptionList:
    """200, the pinned context, the is_active translation, three filters and page 2 at FIFTEEN."""

    def test_integration_subscription_list_renders_the_contracted_template_and_context(
            self, client_a, integration_subscription_a, integration_subscription_with_secret_a,
            integration_subscription_inactive_a):
        from apps.scm.models import (PAYLOAD_FORMAT_CHOICES, WEBHOOK_ENTITY_CHOICES,
                                     WEBHOOK_EVENT_CHOICES)
        response = client_a.get(reverse("scm:webhooksubscription_list"))
        assert response.status_code == 200
        assert "scm/integration/webhooksubscription/list.html" in _integration_templates(response)

        ctx = response.context
        assert {obj.pk for obj in ctx["object_list"]} == {
            integration_subscription_a.pk, integration_subscription_with_secret_a.pk,
            integration_subscription_inactive_a.pk}
        assert ctx["page_obj"].paginator.count == 3
        assert ctx["q"] == ""
        assert list(ctx["entity_choices"]) == list(WEBHOOK_ENTITY_CHOICES)
        assert list(ctx["event_choices"]) == list(WEBHOOK_EVENT_CHOICES)
        assert list(ctx["format_choices"]) == list(PAYLOAD_FORMAT_CHOICES)
        # This model has NO status column - the vocabulary is view-local and maps onto is_active.
        assert list(ctx["status_choices"]) == [("active", "Active"), ("inactive", "Inactive")]
        assert ctx["is_tenant_admin"] is True

    def test_integration_subscription_list_stats_carry_exactly_four_keys(
            self, client_a, integration_subscription_a, integration_subscription_with_secret_a,
            integration_subscription_inactive_a):
        stats = client_a.get(reverse("scm:webhooksubscription_list")).context["stats"]
        assert set(stats) == {"total", "active", "inactive", "failing"}
        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["inactive"] == 1
        assert stats["failing"] == 1

    def test_integration_subscription_list_stats_ignore_the_filters(
            self, client_a, integration_subscription_a, integration_subscription_inactive_a):
        response = client_a.get(reverse("scm:webhooksubscription_list"), {"status": "inactive"})
        assert [obj.pk for obj in response.context["object_list"]] == [
            integration_subscription_inactive_a.pk]
        assert response.context["stats"]["total"] == 2

    @pytest.mark.parametrize("value,active_expected", [("active", True), ("inactive", False)])
    def test_integration_subscription_list_status_is_translated_onto_is_active(
            self, client_a, integration_subscription_a, integration_subscription_inactive_a,
            value, active_expected):
        response = client_a.get(reverse("scm:webhooksubscription_list"), {"status": value})
        assert response.status_code == 200
        rows = list(response.context["object_list"])
        assert rows, "the translation must narrow to something"
        assert all(obj.is_active is active_expected for obj in rows)

    @pytest.mark.parametrize("value", ["banana", "True", "1", "enabled"])
    def test_integration_subscription_list_unknown_status_is_ignored_not_applied(
            self, client_a, integration_subscription_a, integration_subscription_inactive_a, value):
        """`_STATUS_TO_ACTIVE.get()` returns None for anything else, so the filter never runs."""
        response = client_a.get(reverse("scm:webhooksubscription_list"), {"status": value})
        assert response.status_code == 200, f"?status={value} 500'd"
        assert len(response.context["object_list"]) == 2

    @pytest.mark.parametrize("param,value,expect_secret_row", [
        ("trigger_entity", "goods_receipt", True),
        ("trigger_entity", "shipment", False),
        ("trigger_event", "posted", True),
        ("trigger_event", "delivered", False),
        ("payload_format", "xml", True),
        ("payload_format", "json", False),
    ])
    def test_integration_subscription_list_every_filter_narrows(
            self, client_a, integration_subscription_a, integration_subscription_with_secret_a,
            param, value, expect_secret_row):
        response = client_a.get(reverse("scm:webhooksubscription_list"), {param: value})
        assert response.status_code == 200
        wanted = (integration_subscription_with_secret_a if expect_secret_row
                  else integration_subscription_a)
        assert [obj.pk for obj in response.context["object_list"]] == [wanted.pk]

    @pytest.mark.parametrize("param", ["trigger_entity", "trigger_event", "payload_format"])
    def test_integration_subscription_list_junk_filter_value_is_an_empty_200(
            self, client_a, integration_subscription_a, param):
        response = client_a.get(reverse("scm:webhooksubscription_list"), {param: "abc"})
        assert response.status_code == 200, f"?{param}=abc 500'd"
        assert list(response.context["object_list"]) == []

    @pytest.mark.parametrize("term", ["Notify WMS", "wms.example.com/hooks"])
    def test_integration_subscription_list_search_covers_name_and_target_url(
            self, client_a, integration_subscription_a, integration_subscription_inactive_a, term):
        response = client_a.get(reverse("scm:webhooksubscription_list"), {"q": term})
        assert response.context["q"] == term
        assert [obj.pk for obj in response.context["object_list"]] == [
            integration_subscription_a.pk]

    def test_integration_subscription_list_search_matches_the_auto_number(
            self, client_a, integration_subscription_a, integration_subscription_inactive_a):
        response = client_a.get(reverse("scm:webhooksubscription_list"),
                                {"q": integration_subscription_a.number})
        assert [obj.pk for obj in response.context["object_list"]] == [
            integration_subscription_a.pk]

    def test_integration_subscription_list_paginates_at_fifteen_with_a_real_page_two(
            self, client_a, tenant_a):
        _integration_bulk_subscriptions(tenant_a, 21)
        page1 = client_a.get(reverse("scm:webhooksubscription_list"))
        assert len(page1.context["object_list"]) == 15
        page2 = client_a.get(reverse("scm:webhooksubscription_list"), {"page": "2"})
        assert page2.status_code == 200
        assert len(page2.context["object_list"]) == 6
        assert not ({obj.pk for obj in page1.context["object_list"]}
                    & {obj.pk for obj in page2.context["object_list"]})

    @pytest.mark.parametrize("page", ["999", "abc", "0", "-1"])
    def test_integration_subscription_list_page_past_the_end_or_junk_is_200(
            self, client_a, tenant_a, page):
        _integration_bulk_subscriptions(tenant_a, 21)
        response = client_a.get(reverse("scm:webhooksubscription_list"), {"page": page})
        assert response.status_code == 200, f"?page={page} 500'd"
        assert response.context["object_list"]

    def test_integration_subscription_list_is_flat_not_one_query_per_row(
            self, client_a, tenant_a, django_assert_max_num_queries):
        url = reverse("scm:webhooksubscription_list")
        _integration_bulk_subscriptions(tenant_a, 3)
        few = _integration_query_count(client_a, url)

        _integration_bulk_subscriptions(tenant_a, 18, start=50)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 15
        assert _integration_query_count(client_a, url) == few

    def test_integration_subscription_list_never_shows_another_workspaces_rows(
            self, client_a, integration_subscription_a, integration_subscription_b):
        rows = client_a.get(reverse("scm:webhooksubscription_list")).context["object_list"]
        assert [obj.pk for obj in rows] == [integration_subscription_a.pk]


@pytest.mark.django_db
class TestIntegrationWebhookSubscriptionCrud:
    """create / detail / edit / delete - every write here is tenant-admin work."""

    def test_integration_subscription_create_get_renders_the_form_without_obj(self, client_a):
        response = client_a.get(reverse("scm:webhooksubscription_create"))
        assert response.status_code == 200
        assert "scm/integration/webhooksubscription/form.html" in _integration_templates(response)
        assert response.context["is_edit"] is False
        assert response.context["form"] is not None
        assert response.context.get("obj") is None

    def test_integration_subscription_create_post_saves_into_the_request_tenant(
            self, client_a, tenant_a, tenant_b):
        from apps.scm.models import WebhookSubscription
        response = client_a.post(reverse("scm:webhooksubscription_create"),
                                 _integration_subscription_payload())
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:webhooksubscription_list")

        obj = WebhookSubscription.objects.get(trigger_entity="work_order")
        assert obj.tenant_id == tenant_a.pk and obj.tenant_id != tenant_b.pk
        assert obj.number.startswith("WHK-") and len(obj.number) == len("WHK-00001")
        assert obj.headers == {}, "a blank headers box means {}, never None"
        assert obj.auto_disable_threshold == 8 and obj.is_active is True
        # The secret columns are editable=False - no form can reach them (L20/L22).
        assert obj.signing_secret_prefix == "" and obj.signing_secret_hash == ""
        assert obj.consecutive_failures == 0 and obj.last_delivery_at is None
        assert _integration_said(response, "Created successfully")

    def test_integration_subscription_create_post_stores_a_posted_headers_object(
            self, client_a):
        from apps.scm.models import WebhookSubscription
        client_a.post(reverse("scm:webhooksubscription_create"),
                      _integration_subscription_payload(headers='{"X-Source": "NavERP"}'))
        assert WebhookSubscription.objects.get(
            trigger_entity="work_order").headers == {"X-Source": "NavERP"}

    def test_integration_subscription_create_post_duplicate_name_is_a_form_error_not_a_500(
            self, client_a, integration_subscription_a):
        """TenantUniqueMixin turns the ("tenant", "name") clash into a field error."""
        from apps.scm.models import WebhookSubscription
        response = client_a.post(
            reverse("scm:webhooksubscription_create"),
            _integration_subscription_payload(name=integration_subscription_a.name))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert WebhookSubscription.objects.filter(
            name=integration_subscription_a.name).count() == 1

    def test_integration_subscription_detail_renders_every_contracted_key(
            self, client_a, integration_subscription_a, integration_delivery_a,
            integration_delivery_success_a):
        response = client_a.get(reverse("scm:webhooksubscription_detail",
                                        args=[integration_subscription_a.pk]))
        assert response.status_code == 200
        assert "scm/integration/webhooksubscription/detail.html" in _integration_templates(response)

        ctx = response.context
        assert ctx["obj"].pk == integration_subscription_a.pk
        assert [row.pk for row in ctx["recent_deliveries"]] == [
            integration_delivery_success_a.pk, integration_delivery_a.pk]
        assert set(ctx["delivery_stats"]) == {"total", "pending", "success", "failed",
                                              "exhausted", "simulated"}
        assert ctx["delivery_stats"]["total"] == 2
        assert ctx["delivery_stats"]["failed"] == 1
        assert ctx["delivery_stats"]["success"] == 1
        assert ctx["delivery_stats"]["simulated"] == 0
        assert ctx["is_tenant_admin"] is True
        assert ctx["plaintext_once"] is None

    def test_integration_subscription_detail_panel_is_capped_at_ten_newest_first(
            self, client_a, tenant_a, integration_subscription_a):
        rows = _integration_bulk_deliveries(tenant_a, integration_subscription_a, 12)
        ctx = client_a.get(reverse("scm:webhooksubscription_detail",
                                   args=[integration_subscription_a.pk])).context
        assert [row.pk for row in ctx["recent_deliveries"]] == [row.pk for row in rows[:10]]
        assert ctx["delivery_stats"]["total"] == 12

    def test_integration_subscription_detail_panel_never_shows_another_workspaces_attempts(
            self, client_a, integration_subscription_a, integration_delivery_b):
        ctx = client_a.get(reverse("scm:webhooksubscription_detail",
                                   args=[integration_subscription_a.pk])).context
        assert list(ctx["recent_deliveries"]) == []
        assert ctx["delivery_stats"]["total"] == 0

    def test_integration_subscription_edit_get_carries_form_obj_and_is_edit(
            self, client_a, integration_subscription_a):
        response = client_a.get(reverse("scm:webhooksubscription_edit",
                                        args=[integration_subscription_a.pk]))
        assert response.status_code == 200
        assert "scm/integration/webhooksubscription/form.html" in _integration_templates(response)
        assert response.context["is_edit"] is True
        assert response.context["obj"].pk == integration_subscription_a.pk

    def test_integration_subscription_edit_post_retargets_and_returns_to_the_list(
            self, client_a, tenant_a, integration_subscription_a):
        payload = _integration_subscription_payload(
            name=integration_subscription_a.name, trigger_entity="shipment",
            trigger_event="delivered", target_url="https://wms2.example.com/hooks/naverp",
            is_active="")
        response = client_a.post(
            reverse("scm:webhooksubscription_edit", args=[integration_subscription_a.pk]), payload)
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:webhooksubscription_list")

        integration_subscription_a.refresh_from_db()
        assert integration_subscription_a.target_url == "https://wms2.example.com/hooks/naverp"
        assert integration_subscription_a.is_active is False
        assert integration_subscription_a.tenant_id == tenant_a.pk
        assert _integration_said(response, "Updated successfully")

    def test_integration_subscription_edit_post_leaves_the_secret_marker_untouched(
            self, client_a, integration_subscription_with_secret_a):
        """An edit cannot reach the two secret columns - they are editable=False (L20)."""
        before = integration_subscription_with_secret_a.signing_secret_hash
        client_a.post(
            reverse("scm:webhooksubscription_edit",
                    args=[integration_subscription_with_secret_a.pk]),
            _integration_subscription_payload(
                name=integration_subscription_with_secret_a.name,
                trigger_entity="goods_receipt", trigger_event="posted", payload_format="xml",
                target_url=integration_subscription_with_secret_a.target_url))
        integration_subscription_with_secret_a.refresh_from_db()
        assert integration_subscription_with_secret_a.signing_secret_hash == before
        assert integration_subscription_with_secret_a.signing_secret_prefix == "whk-plai"

    def test_integration_subscription_delete_get_is_405_and_deletes_nothing(
            self, client_a, integration_subscription_a):
        from apps.scm.models import WebhookSubscription
        response = client_a.get(reverse("scm:webhooksubscription_delete",
                                        args=[integration_subscription_a.pk]))
        assert response.status_code == 405
        assert WebhookSubscription.objects.filter(pk=integration_subscription_a.pk).exists()

    def test_integration_subscription_delete_post_takes_its_delivery_log_with_it(
            self, client_a, integration_subscription_a, integration_delivery_a,
            integration_delivery_success_a):
        from apps.scm.models import WebhookDelivery, WebhookSubscription
        response = client_a.post(reverse("scm:webhooksubscription_delete",
                                         args=[integration_subscription_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:webhooksubscription_list")
        assert not WebhookSubscription.objects.filter(pk=integration_subscription_a.pk).exists()
        assert not WebhookDelivery.objects.filter(
            pk__in=[integration_delivery_a.pk, integration_delivery_success_a.pk]).exists()

        assert _integration_said(response, "Deleted successfully")
        assert _integration_said(response, "2 delivery records went with it")
        assert _integration_said(response, "clear its Active box instead")

    def test_integration_subscription_delete_post_without_deliveries_still_gives_the_advice(
            self, client_a, integration_subscription_with_secret_a):
        response = client_a.post(reverse("scm:webhooksubscription_delete",
                                         args=[integration_subscription_with_secret_a.pk]))
        assert response.status_code == 302
        assert _integration_said(response, "Deleted successfully")
        assert _integration_said(response, "an inactive subscription fires nothing")
        assert not _integration_said(response, "delivery record")


@pytest.mark.django_db
class TestIntegrationWebhookSubscriptionRotateSecret:
    """The sibling of the credential rotate - same shape, same silence.

    The pop-once reveal is asserted in ``test_integration_security.py``'s
    ``TestIntegrationSecretHandling``, which owns it for both entities.
    """

    def test_integration_subscription_rotate_secret_get_is_405(
            self, client_a, integration_subscription_a):
        response = client_a.get(reverse("scm:webhooksubscription_rotate_secret",
                                        args=[integration_subscription_a.pk]))
        assert response.status_code == 405
        integration_subscription_a.refresh_from_db()
        assert integration_subscription_a.signing_secret_hash == ""

    def test_integration_subscription_rotate_secret_post_stores_only_a_prefix_and_a_digest(
            self, client_a, integration_subscription_a):
        from apps.scm.models import WebhookSubscription
        response = client_a.post(reverse("scm:webhooksubscription_rotate_secret",
                                         args=[integration_subscription_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:webhooksubscription_detail",
                                               args=[integration_subscription_a.pk])

        integration_subscription_a.refresh_from_db()
        assert len(integration_subscription_a.signing_secret_prefix) == 8
        assert len(integration_subscription_a.signing_secret_hash) == 64
        plaintext = client_a.session["_whk_secret_reveal"]["secret"]
        assert integration_subscription_a.signing_secret_hash == WebhookSubscription.hash_secret(
            plaintext)
        assert _integration_said(response, "Signing secret rotated")
        assert all(plaintext not in flash for flash in _integration_flashes(response))


# =================================================================================================
# 4. WebhookDelivery - the append-only attempt log
# =================================================================================================
@pytest.mark.django_db
class TestIntegrationWebhookDeliveryList:
    """200, the pinned context, two filters plus the date window, page 2 at THIRTY."""

    def test_integration_delivery_list_renders_the_contracted_template_and_context(
            self, client_a, integration_delivery_a, integration_delivery_success_a,
            integration_subscription_a):
        from apps.scm.models import DELIVERY_STATUS_CHOICES
        response = client_a.get(reverse("scm:webhookdelivery_list"))
        assert response.status_code == 200
        assert "scm/integration/webhookdelivery/list.html" in _integration_templates(response)

        ctx = response.context
        assert {row.pk for row in ctx["object_list"]} == {integration_delivery_a.pk,
                                                          integration_delivery_success_a.pk}
        assert ctx["page_obj"].paginator.count == 2
        assert ctx["q"] == ""
        assert [s.pk for s in ctx["subscriptions"]] == [integration_subscription_a.pk]
        assert list(ctx["status_choices"]) == list(DELIVERY_STATUS_CHOICES)
        assert ctx["date_from"] == "" and ctx["date_to"] == ""
        assert "append-only" in ctx["append_only_note"].lower()

    def test_integration_delivery_list_stats_carry_exactly_five_keys_and_no_simulated(
            self, client_a, integration_delivery_a, integration_delivery_success_a,
            integration_delivery_final_a):
        """Unlike the subscription detail's `delivery_stats`, this one has NO `simulated` key."""
        response = client_a.get(reverse("scm:webhookdelivery_list"), {"status": "success"})
        stats = response.context["stats"]
        assert set(stats) == {"total", "pending", "success", "failed", "exhausted"}
        assert stats["total"] == 3, "stats must not follow the filtered page"
        assert stats["failed"] == 2
        assert stats["success"] == 1
        assert stats["exhausted"] == 0

    def test_integration_delivery_list_orders_newest_first(
            self, client_a, integration_delivery_a, integration_delivery_success_a):
        rows = list(client_a.get(reverse("scm:webhookdelivery_list")).context["object_list"])
        assert [row.pk for row in rows] == [integration_delivery_success_a.pk,
                                            integration_delivery_a.pk]

    @pytest.mark.parametrize("term,expect_final", [
        ("supply_chain_alert.created", True),
        ("shipment.delivered", False),
        ("Escalate supply chain alerts", True),
        ("Notify WMS", False),
    ])
    def test_integration_delivery_list_search_covers_event_and_subscription_name(
            self, client_a, integration_delivery_a, integration_delivery_final_a,
            term, expect_final):
        response = client_a.get(reverse("scm:webhookdelivery_list"), {"q": term})
        assert response.status_code == 200
        wanted = integration_delivery_final_a if expect_final else integration_delivery_a
        assert [row.pk for row in response.context["object_list"]] == [wanted.pk]

    def test_integration_delivery_list_subscription_filter_narrows_by_pk(
            self, client_a, integration_delivery_a, integration_delivery_final_a,
            integration_subscription_inactive_a):
        response = client_a.get(reverse("scm:webhookdelivery_list"),
                                {"subscription": str(integration_subscription_inactive_a.pk)})
        assert [row.pk for row in response.context["object_list"]] == [
            integration_delivery_final_a.pk]

    @pytest.mark.parametrize("value", ["abc", "²", "999999999999999999999"])
    def test_integration_delivery_list_junk_subscription_param_skips_the_filter(
            self, client_a, integration_delivery_a, value):
        response = client_a.get(reverse("scm:webhookdelivery_list"), {"subscription": value})
        assert response.status_code == 200, f"?subscription={value} 500'd"
        assert [row.pk for row in response.context["object_list"]] == [integration_delivery_a.pk]

    @pytest.mark.parametrize("status,expect_success", [("failed", False), ("success", True)])
    def test_integration_delivery_list_status_filter_narrows(
            self, client_a, integration_delivery_a, integration_delivery_success_a,
            status, expect_success):
        response = client_a.get(reverse("scm:webhookdelivery_list"), {"status": status})
        wanted = integration_delivery_success_a if expect_success else integration_delivery_a
        assert [row.pk for row in response.context["object_list"]] == [wanted.pk]

    def test_integration_delivery_list_unknown_status_is_an_empty_200(
            self, client_a, integration_delivery_a):
        response = client_a.get(reverse("scm:webhookdelivery_list"), {"status": "banana"})
        assert response.status_code == 200
        assert list(response.context["object_list"]) == []

    def test_integration_delivery_list_date_window_is_inclusive_of_the_whole_upper_day(
            self, client_a, tenant_a, integration_subscription_a):
        from apps.scm.models import WebhookDelivery
        late = WebhookDelivery.objects.create(
            tenant=tenant_a, subscription=integration_subscription_a, event="shipment.delivered",
            status="pending", triggered_at=_integration_moment_today(23, 30))
        today = timezone.localdate().isoformat()
        response = client_a.get(reverse("scm:webhookdelivery_list"),
                                {"date_from": today, "date_to": today})
        assert response.status_code == 200
        assert [row.pk for row in response.context["object_list"]] == [late.pk]

    @pytest.mark.parametrize("params", [{"date_from": "lastweek"}, {"date_to": "2026-02-30"}])
    def test_integration_delivery_list_junk_date_window_is_skipped_not_raised(
            self, client_a, integration_delivery_a, params):
        response = client_a.get(reverse("scm:webhookdelivery_list"), params)
        assert response.status_code == 200, f"{params} 500'd"
        assert [row.pk for row in response.context["object_list"]] == [integration_delivery_a.pk]

    def test_integration_delivery_list_paginates_at_thirty_with_a_real_page_two(
            self, client_a, tenant_a, integration_subscription_a):
        _integration_bulk_deliveries(tenant_a, integration_subscription_a, 31)
        page1 = client_a.get(reverse("scm:webhookdelivery_list"))
        assert len(page1.context["object_list"]) == 30, "DELIVERIES_PER_PAGE is 30, not 15"
        page2 = client_a.get(reverse("scm:webhookdelivery_list"), {"page": "2"})
        assert page2.status_code == 200
        assert len(page2.context["object_list"]) == 1
        assert not ({row.pk for row in page1.context["object_list"]}
                    & {row.pk for row in page2.context["object_list"]})

    @pytest.mark.parametrize("page", ["999", "abc", "0", "-1"])
    def test_integration_delivery_list_page_past_the_end_or_junk_is_200(
            self, client_a, tenant_a, integration_subscription_a, page):
        _integration_bulk_deliveries(tenant_a, integration_subscription_a, 31)
        response = client_a.get(reverse("scm:webhookdelivery_list"), {"page": page})
        assert response.status_code == 200, f"?page={page} 500'd"
        assert response.context["object_list"]

    def test_integration_delivery_list_is_flat_not_one_query_per_row(
            self, client_a, tenant_a, integration_subscription_a, django_assert_max_num_queries):
        url = reverse("scm:webhookdelivery_list")
        _integration_bulk_deliveries(tenant_a, integration_subscription_a, 3)
        few = _integration_query_count(client_a, url)

        _integration_bulk_deliveries(tenant_a, integration_subscription_a, 31, start=50)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 30
        assert _integration_query_count(client_a, url) == few, (
            "the attempt log queries per row - join the subscription instead")

    def test_integration_delivery_list_never_shows_another_workspaces_rows(
            self, client_a, integration_delivery_a, integration_delivery_b):
        ctx = client_a.get(reverse("scm:webhookdelivery_list")).context
        assert [row.pk for row in ctx["object_list"]] == [integration_delivery_a.pk]
        assert list(ctx["subscriptions"]) == [integration_delivery_a.subscription]


@pytest.mark.django_db
class TestIntegrationWebhookDeliveryDetail:
    """One attempt, and what pressing Retry would actually schedule."""

    def test_integration_delivery_detail_renders_every_contracted_key(
            self, client_a, integration_delivery_a):
        response = client_a.get(reverse("scm:webhookdelivery_detail",
                                        args=[integration_delivery_a.pk]))
        assert response.status_code == 200
        assert "scm/integration/webhookdelivery/detail.html" in _integration_templates(response)

        ctx = response.context
        assert ctx["obj"].pk == integration_delivery_a.pk
        assert ctx["can_retry"] is True
        # attempt 3 has consumed slot 2, so the next slot is index 3 == 1800s.
        assert ctx["next_backoff_seconds"] == 1800
        assert ctx["max_attempts"] == 8
        assert "append-only" in ctx["append_only_note"].lower()

    def test_integration_delivery_detail_can_retry_is_false_for_a_succeeded_attempt(
            self, client_a, integration_delivery_success_a):
        ctx = client_a.get(reverse("scm:webhookdelivery_detail",
                                   args=[integration_delivery_success_a.pk])).context
        assert ctx["can_retry"] is False
        assert ctx["next_backoff_seconds"] == 5, "the property is about the schedule, not the gate"

    def test_integration_delivery_detail_last_slot_has_no_next_backoff(
            self, client_a, integration_delivery_final_a):
        ctx = client_a.get(reverse("scm:webhookdelivery_detail",
                                   args=[integration_delivery_final_a.pk])).context
        assert ctx["can_retry"] is False, "attempt 8 is not below the 8-slot ceiling"
        assert ctx["next_backoff_seconds"] is None

    def test_integration_delivery_detail_cross_tenant_pk_is_404(
            self, client_a, integration_delivery_b):
        response = client_a.get(reverse("scm:webhookdelivery_detail",
                                        args=[integration_delivery_b.pk]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestIntegrationWebhookDeliveryRetry:
    """Queue the next slot, exhaust the schedule, or refuse. It fires no HTTP request."""

    def test_integration_delivery_retry_post_queues_the_next_slot(
            self, client_a, integration_delivery_a):
        before = timezone.now()
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[integration_delivery_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:webhookdelivery_detail",
                                               args=[integration_delivery_a.pk])

        integration_delivery_a.refresh_from_db()
        assert integration_delivery_a.status == "pending"
        assert integration_delivery_a.attempt_no == 4
        waited = (integration_delivery_a.next_attempt_at - before).total_seconds()
        # The view stamps `timezone.now() + 1800`, and its `now()` is never EARLIER than `before`,
        # so the lower bound is exact. The upper bound only has to stay clear of the neighbouring
        # slots (300 and 7200) - a tight one measures how long the request took under load rather
        # than which slot was booked, which is how a real assertion turns into a flake.
        assert 1800 <= waited <= 1920, "attempt 3 must queue onto the 1800-second slot"
        assert _integration_said(response, "Attempt 4 of 8 queued")
        assert _integration_said(response, "nothing was sent") or _integration_said(
            response, "no request was made") or _integration_said(response, "not part of this")

    def test_integration_delivery_retry_post_on_the_last_slot_exhausts_the_row(
            self, client_a, integration_delivery_final_a):
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[integration_delivery_final_a.pk]))
        assert response.status_code == 302
        integration_delivery_final_a.refresh_from_db()
        assert integration_delivery_final_a.status == "exhausted"
        assert integration_delivery_final_a.attempt_no == 8, "no ninth attempt is invented"
        assert integration_delivery_final_a.next_attempt_at is None
        assert _integration_said(response, "attempts in the retry schedule have been used")

    def test_integration_delivery_retry_refuses_a_succeeded_attempt_and_changes_nothing(
            self, client_a, integration_delivery_success_a):
        response = client_a.post(reverse("scm:webhookdelivery_retry",
                                         args=[integration_delivery_success_a.pk]))
        assert response.status_code == 302
        integration_delivery_success_a.refresh_from_db()
        assert integration_delivery_success_a.status == "success"
        assert integration_delivery_success_a.attempt_no == 1
        assert integration_delivery_success_a.next_attempt_at is None
        assert _integration_said(response, "cannot be retried")

    def test_integration_delivery_retry_get_is_405_and_changes_nothing(
            self, client_a, integration_delivery_a):
        response = client_a.get(reverse("scm:webhookdelivery_retry",
                                        args=[integration_delivery_a.pk]))
        assert response.status_code == 405
        integration_delivery_a.refresh_from_db()
        assert integration_delivery_a.status == "failed"
        assert integration_delivery_a.attempt_no == 3
