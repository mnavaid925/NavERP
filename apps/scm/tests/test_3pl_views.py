"""SCM 4.17 Third-Party Logistics (3PL) — the VIEW/CRUD integration lane.

What this file proves, and what it deliberately leaves to its sibling lanes (models / forms /
security): everything a **request** does. Every one of the sub-module's four list pages renders with
the exact context keys its templates were written against and with those keys POPULATED (a key that
exists but is empty proves nothing — L41); every filter narrows; page 2 exists and is reachable;
every create POST lands in ``request.tenant``; every edit round-trips; every delete is POST-only and
a GET changes nothing; and every rung of the two verb ladders refuses the transitions it is supposed
to refuse rather than falling through to an approval (L35).

Three things worth knowing before editing:

* **Page size is 15** (``crud_list``'s default; no 4.17 list overrides it), so a page-2 guard is
  invisible at fixture size. Every pagination test below builds 21 rows on purpose — the shape that
  makes ``?page=2`` real and ``?page=999`` a boundary rather than a formality (L9).
* **The two tenant-LESS children** (``ClientRateCardLine``, ``ClientBillingRunLine``) carry no
  ``tenant`` column at all. They are resolved through ``rate_card__tenant`` / ``run__tenant``. Their
  cross-tenant tests are the ones that matter most — a bare pk lookup there is a silent cross-tenant
  write, and nothing about the response would look wrong afterwards — and they live one file over,
  in ``test_3pl_security.py``, which owns tenant isolation, auth, CSRF and the method guards for
  this sub-module. This lane asserts what a request RENDERS; it no longer keeps a second copy of
  those (see the closing note at the bottom of the file).
* **Dates come from ``timezone.localdate()``**, never ``datetime.date.today()`` (L16) — the same
  basis ``LogisticsClient.save()``, ``ClientRateCard.is_effective_on()``,
  ``ClientSLA.resolve_window()`` and ``clientratecard_supersede`` all use.

NAMING: every test is ``test_3pl_*`` and every module-level helper ``_3pl_*``. Fixtures use the
``tpl_`` prefix instead, because ``3pl_client_a`` is not a legal Python identifier while
``_3pl_helper`` is (only the FIRST character of a name may not be a digit).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone


# =================================================================================================
# Module-level helpers — all `_3pl_` prefixed (the hygiene guard in test_suite_hygiene.py parses
# this file and fails on any module-level name defined twice).
# =================================================================================================
def _3pl_messages(response):
    """Every flashed message on the request that produced ``response``, as plain strings."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _3pl_said(response, fragment):
    """True when any flashed message contains ``fragment`` (case-insensitive)."""
    return any(fragment.lower() in m.lower() for m in _3pl_messages(response))


def _3pl_templates(response):
    return [t.name for t in response.templates if t.name]


def _3pl_party(tenant, name):
    """A tenant party carrying the ``customer`` PartyRole ``LogisticsClientForm`` narrows to."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="customer", status="active",
                             start_date=timezone.localdate())
    return party


def _3pl_client_payload(party, code, **overrides):
    """A POST body ``LogisticsClientForm`` accepts. Shared-space, so ``clean()`` wants no commitment."""
    payload = {
        "party": str(party.pk),
        "code": code,
        "status": "prospect",
        "billing_cycle": "monthly",
        "billing_day": "1",
        "storage_billing_method": "calendar_month",
        "minimum_monthly_charge": "0.00",
        "default_tax_rate_pct": "0.00",
        "space_model": "shared",
        "committed_sqft": "0.00",
        "committed_pallet_positions": "0",
        "notice_days": "0",
        "integration_mode": "none",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _3pl_card_payload(client_obj, name, effective_from, **overrides):
    payload = {
        "client": str(client_obj.pk),
        "name": name,
        "version": "1",
        "status": "draft",
        "effective_from": effective_from.isoformat(),
        "effective_to": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _3pl_card_line_payload(**overrides):
    """An EVENT-basis rate line: ``period`` must be blank on anything outside PERIODIC_BASES."""
    payload = {
        "charge_category": "outbound",
        "charge_basis": "per_order",
        "description": "Order handling",
        "rate": "3.5000",
        "period": "",
        "included_quantity": "0",
        "minimum_charge": "0",
        "tier_from": "0",
        "tier_to": "",
        "applies_to_location": "",
        "applies_to_item_category": "",
        "gl_account": "",
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


def _3pl_run_payload(client_obj, card, start, end, **overrides):
    payload = {
        "client": str(client_obj.pk),
        "rate_card": str(card.pk),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _3pl_run_line_payload(**overrides):
    payload = {
        "charge_category": "value_added",
        "charge_basis": "per_hour",
        "description": "Rework labour",
        "quantity": "3",
        "rate": "20.00",
        "source_reference": "",
    }
    payload.update(overrides)
    return payload


def _3pl_sla_payload(client_obj, **overrides):
    """``order_accuracy_pct`` fixes unit=pct / direction=higher_is_better in SLA_METRIC_META, and
    ``ClientSLA.clean()`` refuses a row that disagrees with the registry."""
    payload = {
        "client": str(client_obj.pk),
        "metric": "order_accuracy_pct",
        "name": "Order accuracy",
        "target_value": "99.50",
        "unit": "pct",
        "direction": "higher_is_better",
        "warning_threshold": "",
        "measurement_window": "monthly",
        "scope_location": "",
        "service_credit_pct": "0.00",
        "service_credit_cap_pct": "0.00",
        "is_active": "on",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _3pl_bulk_clients(tenant, count, prefix="BULK", start=0):
    """``count`` extra LogisticsClients — enough to push a 15-row page over into a second one.

    ``start`` lets a caller add a SECOND batch without colliding on ``(tenant, code)`` — which is
    what the N+1 tests below need: measure the page at a few rows, add more, measure again.
    """
    from apps.scm.models import LogisticsClient
    made = []
    for index in range(start, start + count):
        party = _3pl_party(tenant, f"{prefix} Depositor {index:02d}")
        made.append(LogisticsClient.objects.create(
            tenant=tenant, party=party, code=f"{prefix}{index:02d}", status="prospect",
            billing_cycle="monthly", billing_day=1, storage_billing_method="calendar_month",
            space_model="shared", integration_mode="none"))
    return made


def _3pl_bulk_cards(tenant, client_obj, count, start=0):
    """``count`` DRAFT tariffs on one client — ``version`` varies so the unique_together holds."""
    from apps.scm.models import ClientRateCard
    today = timezone.localdate()
    return [ClientRateCard.objects.create(
        tenant=tenant, client=client_obj, name="Bulk tariff", version=index + 10, status="draft",
        effective_from=today - datetime.timedelta(days=index + 1))
        for index in range(start, start + count)]


def _3pl_bulk_runs(tenant, client_obj, card, count, start=0):
    """``count`` DRAFT runs over non-overlapping periods (the unique_together is per period)."""
    from apps.scm.models import ClientBillingRun
    today = timezone.localdate()
    made = []
    for index in range(start, start + count):
        end = today - datetime.timedelta(days=index * 3 + 1)
        made.append(ClientBillingRun.objects.create(
            tenant=tenant, client=client_obj, rate_card=card,
            period_start=end - datetime.timedelta(days=2), period_end=end))
    return made


def _3pl_bulk_slas(tenant, clients, count, start=0):
    """``count`` SLAs spread across ``clients`` — one row per (client, metric) pair."""
    from apps.scm.models import ClientSLA
    metrics = ["on_time_shipment_pct", "otif_pct", "same_day_ship_pct", "order_accuracy_pct",
               "inventory_accuracy_pct", "damage_rate_pct", "shrinkage_pct"]
    made = []
    for index in range(start, start + count):
        client_obj = clients[index % len(clients)]
        metric = metrics[(index // len(clients)) % len(metrics)]
        lower = metric in ("damage_rate_pct", "shrinkage_pct")
        made.append(ClientSLA.objects.create(
            tenant=tenant, client=client_obj, metric=metric, target_value=Decimal("95.00"),
            unit="pct", direction="lower_is_better" if lower else "higher_is_better",
            measurement_window="monthly", is_active=True))
    return made


def _3pl_query_count(client, url):
    """How many queries one GET of ``url`` costs. The N+1 test is: this number must not MOVE when
    the page fills up — a cap alone only says "not too many today"."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)
    assert response.status_code == 200
    return len(captured.captured_queries)


def _3pl_calculated_run(run):
    """Drive a draft run one rung up the ladder with the model's own verb (status is editable=False)."""
    run.calculate()
    run.refresh_from_db()
    return run


def _3pl_approved_run(run, user):
    _3pl_calculated_run(run)
    run.approve(user=user)
    run.refresh_from_db()
    return run


# NOTE: the POST-only route table, the anonymous-redirect table and the cross-tenant pk tables all
# live in ``test_3pl_security.py`` — that lane owns auth, CSRF, method guards and tenant isolation
# for 4.17, and duplicating them here only doubled the runtime of the same assertions.


# =================================================================================================
# 1. LogisticsClient — the register
# =================================================================================================
@pytest.mark.django_db
class Test3plLogisticsClientList:
    """The depositor register: 200, the pinned context, four filters, search, and page 2."""

    def test_3pl_client_list_renders_the_contracted_template_and_context(
            self, client_a, tpl_client_a, tpl_client_shared_a):
        response = client_a.get(reverse("scm:logisticsclient_list"))
        assert response.status_code == 200
        assert "scm/3pl/logisticsclient/list.html" in _3pl_templates(response)

        ctx = response.context
        codes = {obj.code for obj in ctx["object_list"]}
        assert codes == {"ACME", "SHARED"}, "the list must show this workspace's clients"
        assert ctx["page_obj"].paginator.count == 2
        assert ctx["q"] == ""
        # Populated, not merely present (L41): a choices list the template renders as an empty
        # <select> is a filter nobody can use.
        assert ("active", "Active") in list(ctx["status_choices"])
        assert ("monthly", "Monthly") in list(ctx["billing_cycle_choices"])
        assert ("dedicated", "Dedicated") in list(ctx["space_model_choices"])
        assert ("edi", "EDI") in list(ctx["integration_mode_choices"])

    def test_3pl_client_list_stats_carry_all_six_keys_with_real_counts(
            self, client_a, tpl_client_a, tpl_client_shared_a):
        stats = client_a.get(reverse("scm:logisticsclient_list")).context["stats"]
        assert set(stats) == {"total", "active", "onboarding", "prospect", "suspended", "breaching"}
        assert stats["total"] == 2 and stats["active"] == 2
        assert stats["onboarding"] == 0 and stats["prospect"] == 0 and stats["suspended"] == 0
        assert stats["breaching"] == 0

    def test_3pl_client_list_breaching_chip_counts_a_client_once_not_once_per_sla(
            self, client_a, tpl_client_a, tpl_sla_a):
        """``.distinct()`` is load-bearing: a client with two breached SLAs is ONE breaching client."""
        from apps.scm.models import ClientSLA
        ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(status="breached")
        ClientSLA.objects.create(tenant=tpl_client_a.tenant, client=tpl_client_a,
                                 metric="otif_pct", target_value=Decimal("95.00"), unit="pct",
                                 direction="higher_is_better", measurement_window="monthly",
                                 is_active=True)
        ClientSLA.objects.filter(client=tpl_client_a, metric="otif_pct").update(status="breached")
        stats = client_a.get(reverse("scm:logisticsclient_list")).context["stats"]
        assert stats["breaching"] == 1

    def test_3pl_client_list_search_matches_the_party_name(
            self, client_a, tpl_client_a, tpl_client_shared_a):
        response = client_a.get(reverse("scm:logisticsclient_list"), {"q": "Second Depositor"})
        assert response.status_code == 200
        assert [obj.code for obj in response.context["object_list"]] == ["SHARED"]
        assert response.context["q"] == "Second Depositor"

    @pytest.mark.parametrize("param,value,expected", [
        ("status", "active", {"ACME", "SHARED"}),
        ("billing_cycle", "weekly", {"SHARED"}),
        ("space_model", "dedicated", {"ACME"}),
        ("integration_mode", "api", {"ACME"}),
        ("integration_mode", "edi", {"SHARED"}),
    ])
    def test_3pl_client_list_each_filter_narrows(
            self, client_a, tpl_client_a, tpl_client_shared_a, param, value, expected):
        response = client_a.get(reverse("scm:logisticsclient_list"), {param: value})
        assert response.status_code == 200
        assert {obj.code for obj in response.context["object_list"]} == expected

    @pytest.mark.parametrize("query", [
        {"status": "zzz"}, {"billing_cycle": "abc"}, {"space_model": "²"},
        {"integration_mode": "99999999999999999999"}, {"q": "'; DROP TABLE"},
    ])
    def test_3pl_client_list_junk_filter_values_are_200_not_500(
            self, client_a, tpl_client_a, query):
        response = client_a.get(reverse("scm:logisticsclient_list"), query)
        assert response.status_code == 200, f"{query} 500'd the list page"
        assert list(response.context["object_list"]) == []

    def test_3pl_client_list_paginates_at_fifteen_with_a_real_page_two(self, client_a, tenant_a):
        _3pl_bulk_clients(tenant_a, 21)
        page1 = client_a.get(reverse("scm:logisticsclient_list"))
        assert len(page1.context["object_list"]) == 15
        assert page1.context["page_obj"].has_next() is True

        page2 = client_a.get(reverse("scm:logisticsclient_list"), {"page": "2"})
        assert page2.status_code == 200
        assert len(page2.context["object_list"]) == 6
        assert page2.context["page_obj"].number == 2
        # A total order (code, id), so page 2 cannot repeat a row page 1 already showed.
        assert not ({o.pk for o in page1.context["object_list"]}
                    & {o.pk for o in page2.context["object_list"]})

    @pytest.mark.parametrize("page", ["999", "abc", "0", "-1", ""])
    def test_3pl_client_list_page_past_the_end_or_junk_is_200(self, client_a, tenant_a, page):
        _3pl_bulk_clients(tenant_a, 21)
        response = client_a.get(reverse("scm:logisticsclient_list"), {"page": page})
        assert response.status_code == 200, f"?page={page} 500'd"
        assert response.context["object_list"], "a junk page must still render rows"

    def test_3pl_client_list_is_flat_not_one_query_per_row(
            self, client_a, tenant_a, django_assert_max_num_queries):
        """The six derived methods are one query EACH — 15 rows x 6 is the 4.13 asset_list finding.

        ``__str__`` also walks ``party``, so an unjoined queryset costs a query per row on any page
        that renders ``{{ obj }}``. The assertion is that the count does not MOVE between 3 rows and
        a full page of 15: a fixed ceiling alone only ever says "not too many today".
        """
        url = reverse("scm:logisticsclient_list")
        _3pl_bulk_clients(tenant_a, 3, prefix="FEW")
        few = _3pl_query_count(client_a, url)

        _3pl_bulk_clients(tenant_a, 18, prefix="MANY")
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 15
        assert _3pl_query_count(client_a, url) == few, (
            "the depositor register queries per row — the six derived methods must never be "
            "called from a list page")


@pytest.mark.django_db
class Test3plLogisticsClientCrud:

    def test_3pl_client_create_get_renders_the_form(self, client_a):
        response = client_a.get(reverse("scm:logisticsclient_create"))
        assert response.status_code == 200
        assert "scm/3pl/logisticsclient/form.html" in _3pl_templates(response)
        assert response.context["is_edit"] is False
        assert response.context["form"] is not None

    def test_3pl_client_create_post_saves_against_the_request_tenant(
            self, client_a, tenant_a, tenant_b):
        from apps.scm.models import LogisticsClient
        party = _3pl_party(tenant_a, "Brand New Depositor")
        response = client_a.post(reverse("scm:logisticsclient_create"),
                                 _3pl_client_payload(party, "NEWCO"))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:logisticsclient_list")
        obj = LogisticsClient.objects.get(code="NEWCO")
        assert obj.tenant_id == tenant_a.pk and obj.tenant_id != tenant_b.pk
        assert obj.number.startswith("3PL-"), "the auto-number must be minted on the create path"

    def test_3pl_client_create_stamps_onboarded_on_only_for_an_active_client(
            self, client_a, tenant_a):
        from apps.scm.models import LogisticsClient
        party = _3pl_party(tenant_a, "Go-Live Depositor")
        client_a.post(reverse("scm:logisticsclient_create"),
                      _3pl_client_payload(party, "LIVE", status="active"))
        obj = LogisticsClient.objects.get(code="LIVE")
        assert obj.onboarded_on == timezone.localdate()

    def test_3pl_client_create_rejects_a_dedicated_client_with_no_commitment(
            self, client_a, tenant_a):
        from apps.scm.models import LogisticsClient
        party = _3pl_party(tenant_a, "Dedicated No Commitment")
        response = client_a.post(reverse("scm:logisticsclient_create"),
                                 _3pl_client_payload(party, "DEDNO", space_model="dedicated"))
        assert response.status_code == 200, "a refused create must re-render, never redirect"
        assert not LogisticsClient.objects.filter(code="DEDNO").exists()

    def test_3pl_client_create_rejects_a_foreign_party_in_the_post_body(
            self, client_a, tenant_a, customer_b):
        """A narrowed <select> has never held against a crafted POST (L39 §2)."""
        from apps.scm.models import LogisticsClient
        response = client_a.post(reverse("scm:logisticsclient_create"),
                                 _3pl_client_payload(customer_b, "STOLEN"))
        assert response.status_code == 200
        assert not LogisticsClient.objects.filter(code="STOLEN").exists()

    def test_3pl_client_detail_carries_every_pinned_key_populated(
            self, client_a, tpl_client_a, tpl_active_card_a, tpl_billing_run_a, tpl_sla_a,
            tpl_stock_move_a):
        response = client_a.get(reverse("scm:logisticsclient_detail", args=[tpl_client_a.pk]))
        assert response.status_code == 200
        assert "scm/3pl/logisticsclient/detail.html" in _3pl_templates(response)
        ctx = response.context
        assert ctx["obj"].pk == tpl_client_a.pk
        assert [c.pk for c in ctx["rate_cards"]] == [tpl_active_card_a.pk]
        assert ctx["rate_card_count"] == 1 and ctx["rate_cards_truncated"] is False
        assert ctx["active_rate_card"] is not None
        assert ctx["active_rate_card"].pk == tpl_active_card_a.pk
        assert [r.pk for r in ctx["billing_runs"]] == [tpl_billing_run_a.pk]
        assert ctx["billing_run_count"] == 1 and ctx["billing_runs_truncated"] is False
        assert [s.pk for s in ctx["slas"]] == [tpl_sla_a.pk]
        assert ctx["sla_count"] == 1 and ctx["slas_truncated"] is False
        assert ctx["open_breach_count"] == 0
        assert list(ctx["child_clients"]) == [] and ctx["child_clients_truncated"] is False
        assert ctx["on_hand_quantity"] == Decimal("100.0000")
        assert ctx["on_hand_value"] == Decimal("1000.00")
        assert ctx["sku_count"] == 1
        assert ctx["dedicated_location_count"] == 1
        assert ctx["has_customer_role"] is True
        assert ctx["panel_limit"] == 20
        assert ctx["can_delete"] is False, "a client with a tariff and a run is not deletable"

    def test_3pl_client_detail_can_delete_is_true_for_an_unreferenced_client(
            self, client_a, tpl_client_shared_a):
        ctx = client_a.get(reverse("scm:logisticsclient_detail",
                                   args=[tpl_client_shared_a.pk])).context
        assert ctx["can_delete"] is True
        assert ctx["active_rate_card"] is None, "no tariff must be None, not a blank object"

    def test_3pl_client_edit_get_prefills_and_flags_is_edit(self, client_a, tpl_client_a):
        response = client_a.get(reverse("scm:logisticsclient_edit", args=[tpl_client_a.pk]))
        assert response.status_code == 200
        assert "scm/3pl/logisticsclient/form.html" in _3pl_templates(response)
        assert response.context["is_edit"] is True
        assert response.context["obj"].pk == tpl_client_a.pk
        assert response.context["form"].initial["code"] == "ACME"

    def test_3pl_client_edit_post_saves_the_change(self, client_a, tpl_client_a, customer_a):
        response = client_a.post(
            reverse("scm:logisticsclient_edit", args=[tpl_client_a.pk]),
            _3pl_client_payload(customer_a, "ACME", status="suspended", space_model="dedicated",
                                committed_sqft="4000.00", committed_pallet_positions="250",
                                billing_cycle="monthly", notes="paused"))
        assert response.status_code == 302
        tpl_client_a.refresh_from_db()
        assert tpl_client_a.status == "suspended"
        assert tpl_client_a.notes == "paused"

    def test_3pl_client_edit_cannot_rewrite_the_onboarding_date(
            self, client_a, tpl_client_a, customer_a):
        """``onboarded_on`` is editable=False and stamped ONCE — a suspend/reactivate cycle must not
        move the go-live date."""
        stamped = tpl_client_a.onboarded_on
        assert stamped is not None
        client_a.post(reverse("scm:logisticsclient_edit", args=[tpl_client_a.pk]),
                      _3pl_client_payload(customer_a, "ACME", status="active",
                                          space_model="dedicated", committed_sqft="4000.00",
                                          committed_pallet_positions="250",
                                          onboarded_on="2000-01-01"))
        tpl_client_a.refresh_from_db()
        assert tpl_client_a.onboarded_on == stamped

    def test_3pl_client_delete_get_is_405_and_deletes_nothing(self, client_a, tpl_client_shared_a):
        from apps.scm.models import LogisticsClient
        response = client_a.get(reverse("scm:logisticsclient_delete", args=[tpl_client_shared_a.pk]))
        assert response.status_code == 405
        assert LogisticsClient.objects.filter(pk=tpl_client_shared_a.pk).exists()

    def test_3pl_client_delete_post_removes_an_unreferenced_client(
            self, client_a, tpl_client_shared_a):
        from apps.scm.models import LogisticsClient
        response = client_a.post(reverse("scm:logisticsclient_delete",
                                         args=[tpl_client_shared_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:logisticsclient_list")
        assert not LogisticsClient.objects.filter(pk=tpl_client_shared_a.pk).exists()

    def test_3pl_client_delete_is_refused_while_a_tariff_references_it(
            self, client_a, tpl_client_a, tpl_active_card_a):
        from apps.scm.models import LogisticsClient
        response = client_a.post(reverse("scm:logisticsclient_delete", args=[tpl_client_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:logisticsclient_detail",
                                               args=[tpl_client_a.pk])
        assert LogisticsClient.objects.filter(pk=tpl_client_a.pk).exists()
        assert _3pl_said(response, "cannot be deleted")

    def test_3pl_client_delete_reports_the_slas_and_assignments_it_took_with_it(
            self, client_a, tpl_client_shared_a, tpl_other_client_location_a):
        """SLAs CASCADE and the two ``owner_client`` columns SET_NULL — the quiet half of the damage."""
        from apps.scm.models import ClientSLA, Location
        ClientSLA.objects.create(tenant=tpl_client_shared_a.tenant, client=tpl_client_shared_a,
                                 metric="otif_pct", target_value=Decimal("95.00"), unit="pct",
                                 direction="higher_is_better", measurement_window="monthly")
        response = client_a.post(reverse("scm:logisticsclient_delete",
                                         args=[tpl_client_shared_a.pk]))
        assert response.status_code == 302
        assert _3pl_said(response, "unassigned")
        tpl_other_client_location_a.refresh_from_db()
        assert tpl_other_client_location_a.owner_client_id is None
        assert Location.objects.filter(pk=tpl_other_client_location_a.pk).exists()


# =================================================================================================
# 2. ClientRateCard — the tariff, its ladder and its lines
# =================================================================================================
@pytest.mark.django_db
class Test3plRateCardList:

    def test_3pl_rate_card_list_renders_with_its_pinned_context(
            self, client_a, tpl_active_card_a, tpl_rate_card_a):
        response = client_a.get(reverse("scm:clientratecard_list"))
        assert response.status_code == 200
        assert "scm/3pl/clientratecard/list.html" in _3pl_templates(response)
        ctx = response.context
        assert {c.pk for c in ctx["object_list"]} == {tpl_active_card_a.pk, tpl_rate_card_a.pk}
        assert list(ctx["clients"]), "the ?client= dropdown must be populated"
        assert ("draft", "Draft") in list(ctx["status_choices"])
        assert ctx["stats"] == {"total": 2, "draft": 1, "active": 1, "superseded": 0, "expired": 0}

    def test_3pl_rate_card_rows_carry_the_annotated_line_count(
            self, client_a, tpl_active_card_a, tpl_rate_card_a, tpl_rate_card_line_a):
        rows = {c.pk: c for c in
                client_a.get(reverse("scm:clientratecard_list")).context["object_list"]}
        assert rows[tpl_active_card_a.pk].line_count == 2
        assert rows[tpl_rate_card_a.pk].line_count == 1

    def test_3pl_rate_card_list_search_and_filters_narrow(
            self, client_a, tpl_active_card_a, tpl_rate_card_a, tpl_client_a):
        by_name = client_a.get(reverse("scm:clientratecard_list"), {"q": "Next version"})
        assert [c.pk for c in by_name.context["object_list"]] == [tpl_rate_card_a.pk]

        by_status = client_a.get(reverse("scm:clientratecard_list"), {"status": "active"})
        assert [c.pk for c in by_status.context["object_list"]] == [tpl_active_card_a.pk]

        by_client = client_a.get(reverse("scm:clientratecard_list"),
                                 {"client": str(tpl_client_a.pk)})
        assert len(by_client.context["object_list"]) == 2

    @pytest.mark.parametrize("query", [
        {"client": "abc"}, {"client": "²"}, {"client": "99999999999999999999"},
        {"status": "zzz"},
    ])
    def test_3pl_rate_card_list_junk_params_are_200(self, client_a, tpl_rate_card_a, query):
        """L11: a junk FK filter SKIPS the filter; a junk status matches nothing. Neither 500s."""
        response = client_a.get(reverse("scm:clientratecard_list"), query)
        assert response.status_code == 200, f"{query} 500'd the rate-card list"

    def test_3pl_rate_card_list_paginates_with_a_real_page_two(
            self, client_a, tenant_a, tpl_client_a):
        _3pl_bulk_cards(tenant_a, tpl_client_a, 21)
        page1 = client_a.get(reverse("scm:clientratecard_list"))
        assert len(page1.context["object_list"]) == 15
        page2 = client_a.get(reverse("scm:clientratecard_list"), {"page": "2"})
        assert len(page2.context["object_list"]) == 6
        assert client_a.get(reverse("scm:clientratecard_list"),
                            {"page": "999"}).status_code == 200

    def test_3pl_rate_card_list_does_not_query_per_row(
            self, client_a, tenant_a, tpl_client_a, django_assert_max_num_queries):
        """``__str__`` walks ``client.code`` and the row prints the client — two FK hops per row.

        ``line_count`` is ANNOTATED for the same reason: ``active_line_count`` is a property that
        COUNTs, so reading it per row would be one query per card.
        """
        url = reverse("scm:clientratecard_list")
        _3pl_bulk_cards(tenant_a, tpl_client_a, 3)
        few = _3pl_query_count(client_a, url)

        _3pl_bulk_cards(tenant_a, tpl_client_a, 18, start=3)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 15
        assert _3pl_query_count(client_a, url) == few, "the tariff register queries per row"


@pytest.mark.django_db
class Test3plRateCardCrud:

    def test_3pl_rate_card_create_post_saves_with_the_request_tenant(
            self, client_a, tenant_a, tpl_client_a):
        from apps.scm.models import ClientRateCard
        today = timezone.localdate()
        response = client_a.post(
            reverse("scm:clientratecard_create"),
            _3pl_card_payload(tpl_client_a, "Fresh tariff", today + datetime.timedelta(days=30)))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientratecard_list")
        card = ClientRateCard.objects.get(name="Fresh tariff")
        assert card.tenant_id == tenant_a.pk
        assert card.number.startswith("TAR-")
        assert card.status == "draft"

    def test_3pl_rate_card_create_rejects_another_workspaces_client(
            self, client_a, tpl_client_b):
        from apps.scm.models import ClientRateCard
        response = client_a.post(
            reverse("scm:clientratecard_create"),
            _3pl_card_payload(tpl_client_b, "Cross tenant", timezone.localdate()))
        assert response.status_code == 200
        assert not ClientRateCard.objects.filter(name="Cross tenant").exists()

    def test_3pl_rate_card_detail_carries_every_gate_and_panel(
            self, client_a, tpl_active_card_a, tpl_billing_run_a):
        response = client_a.get(reverse("scm:clientratecard_detail", args=[tpl_active_card_a.pk]))
        assert response.status_code == 200
        assert "scm/3pl/clientratecard/detail.html" in _3pl_templates(response)
        ctx = response.context
        assert ctx["obj"].pk == tpl_active_card_a.pk
        assert len(ctx["lines"]) == 2 and ctx["line_count"] == 2
        assert ctx["active_line_count"] == 2
        assert "per_sqft" in ctx["manual_only_bases"]
        assert [r.pk for r in ctx["billing_runs"]] == [tpl_billing_run_a.pk]
        assert ctx["billing_run_count"] == 1
        assert ctx["panel_limit"] == 25
        assert ctx["is_effective_today"] is True
        assert ctx["can_edit"] is False and ctx["can_add_line"] is False
        assert ctx["can_activate"] is False and ctx["can_supersede"] is True
        assert ctx["can_delete"] is False, "a card that priced a run is PROTECTed"

    def test_3pl_rate_card_detail_gates_open_on_a_draft(self, client_a, tpl_rate_card_a):
        ctx = client_a.get(reverse("scm:clientratecard_detail",
                                   args=[tpl_rate_card_a.pk])).context
        assert ctx["can_edit"] is True and ctx["can_add_line"] is True
        assert ctx["can_activate"] is True and ctx["can_supersede"] is False
        assert ctx["can_delete"] is True
        assert ctx["is_effective_today"] is False, "this draft starts tomorrow"

    def test_3pl_rate_card_edit_post_updates_a_draft(self, client_a, tpl_rate_card_a, tpl_client_a):
        today = timezone.localdate()
        response = client_a.post(
            reverse("scm:clientratecard_edit", args=[tpl_rate_card_a.pk]),
            _3pl_card_payload(tpl_client_a, "Renamed draft", today + datetime.timedelta(days=1)))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientratecard_detail",
                                               args=[tpl_rate_card_a.pk])
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.name == "Renamed draft"

    def test_3pl_rate_card_edit_is_refused_once_active(
            self, client_a, tpl_active_card_a, tpl_client_a):
        response = client_a.get(reverse("scm:clientratecard_edit", args=[tpl_active_card_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientratecard_detail",
                                               args=[tpl_active_card_a.pk])
        assert _3pl_said(response, "can no longer be changed")

        blocked = client_a.post(
            reverse("scm:clientratecard_edit", args=[tpl_active_card_a.pk]),
            _3pl_card_payload(tpl_client_a, "Rewritten", timezone.localdate()))
        assert blocked.status_code == 302
        tpl_active_card_a.refresh_from_db()
        assert tpl_active_card_a.name == "Live tariff"

    def test_3pl_rate_card_delete_get_is_405(self, client_a, tpl_rate_card_a):
        from apps.scm.models import ClientRateCard
        response = client_a.get(reverse("scm:clientratecard_delete", args=[tpl_rate_card_a.pk]))
        assert response.status_code == 405
        assert ClientRateCard.objects.filter(pk=tpl_rate_card_a.pk).exists()

    def test_3pl_rate_card_delete_post_removes_an_unbilled_card(self, client_a, tpl_rate_card_a):
        from apps.scm.models import ClientRateCard
        response = client_a.post(reverse("scm:clientratecard_delete", args=[tpl_rate_card_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientratecard_list")
        assert not ClientRateCard.objects.filter(pk=tpl_rate_card_a.pk).exists()

    def test_3pl_rate_card_delete_is_refused_once_it_has_priced_a_run(
            self, client_a, tpl_active_card_a, tpl_billing_run_a):
        from apps.scm.models import ClientRateCard
        response = client_a.post(reverse("scm:clientratecard_delete", args=[tpl_active_card_a.pk]))
        assert response.status_code == 302
        assert ClientRateCard.objects.filter(pk=tpl_active_card_a.pk).exists()
        assert _3pl_said(response, "can't be deleted")


@pytest.mark.django_db
class Test3plRateCardLadder:

    def test_3pl_rate_card_activate_moves_a_draft_live(
            self, client_a, tpl_rate_card_a, tpl_active_card_a):
        """The two fixtures do NOT overlap (the live one ends today, the draft starts tomorrow)."""
        response = client_a.post(reverse("scm:clientratecard_activate", args=[tpl_rate_card_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientratecard_detail",
                                               args=[tpl_rate_card_a.pk])
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.status == "active"
        assert _3pl_said(response, "active tariff")

    def test_3pl_rate_card_activate_warns_when_the_card_has_no_lines(
            self, client_a, tpl_rate_card_a):
        response = client_a.post(reverse("scm:clientratecard_activate", args=[tpl_rate_card_a.pk]))
        assert _3pl_said(response, "no active rate lines")

    def test_3pl_rate_card_activate_refuses_an_overlapping_range(
            self, client_a, tpl_rate_card_a, tpl_active_card_a):
        """Move the draft's start back so the two ranges collide — two live tariffs over one day
        means the billing run has two prices for it."""
        from apps.scm.models import ClientRateCard
        ClientRateCard.objects.filter(pk=tpl_rate_card_a.pk).update(
            effective_from=timezone.localdate() - datetime.timedelta(days=5))
        response = client_a.post(reverse("scm:clientratecard_activate", args=[tpl_rate_card_a.pk]))
        assert response.status_code == 302
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.status == "draft", "the overlapping card must NOT go live"
        assert _3pl_said(response, "overlap")

    def test_3pl_rate_card_activate_refuses_a_card_that_is_already_active(
            self, client_a, tpl_active_card_a):
        response = client_a.post(reverse("scm:clientratecard_activate",
                                         args=[tpl_active_card_a.pk]))
        assert response.status_code == 302
        assert _3pl_said(response, "cannot be activated")

    def test_3pl_rate_card_supersede_stamps_the_end_date(self, client_a, tpl_active_card_a):
        response = client_a.post(reverse("scm:clientratecard_supersede",
                                         args=[tpl_active_card_a.pk]))
        assert response.status_code == 302
        tpl_active_card_a.refresh_from_db()
        assert tpl_active_card_a.status == "superseded"
        assert tpl_active_card_a.effective_to <= timezone.localdate()

    def test_3pl_rate_card_supersede_refuses_a_draft(self, client_a, tpl_rate_card_a):
        response = client_a.post(reverse("scm:clientratecard_supersede",
                                         args=[tpl_rate_card_a.pk]))
        assert response.status_code == 302
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.status == "draft"
        assert _3pl_said(response, "cannot be superseded")


@pytest.mark.django_db
class Test3plRateCardLineCrud:

    def test_3pl_rate_card_line_create_get_names_the_parent_not_an_obj(
            self, client_a, tpl_rate_card_a):
        response = client_a.get(reverse("scm:clientratecardline_create",
                                        args=[tpl_rate_card_a.pk]))
        assert response.status_code == 200
        assert "scm/3pl/clientratecardline/form.html" in _3pl_templates(response)
        ctx = response.context
        assert ctx["is_edit"] is False
        assert ctx["rate_card"].pk == tpl_rate_card_a.pk
        assert "rate_card" not in ctx["form"].fields, (
            "the parent comes from the URL — a parent pk in a POST body is how a caller grafts a "
            "priced line onto somebody else's tariff")

    def test_3pl_rate_card_line_create_post_attaches_to_the_route_parent(
            self, client_a, tpl_rate_card_a):
        from apps.scm.models import ClientRateCardLine
        response = client_a.post(reverse("scm:clientratecardline_create",
                                         args=[tpl_rate_card_a.pk]),
                                 _3pl_card_line_payload())
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientratecard_detail",
                                               args=[tpl_rate_card_a.pk])
        line = ClientRateCardLine.objects.get(description="Order handling")
        assert line.rate_card_id == tpl_rate_card_a.pk

    def test_3pl_rate_card_line_create_ignores_a_rate_card_pk_in_the_body(
            self, client_a, tpl_rate_card_a, tpl_rate_card_b):
        """The IDOR shape: the body names tenant_b's tariff, the route names tenant_a's."""
        from apps.scm.models import ClientRateCardLine
        client_a.post(reverse("scm:clientratecardline_create", args=[tpl_rate_card_a.pk]),
                      _3pl_card_line_payload(rate_card=str(tpl_rate_card_b.pk)))
        line = ClientRateCardLine.objects.get(description="Order handling")
        assert line.rate_card_id == tpl_rate_card_a.pk
        assert not tpl_rate_card_b.lines.exists()

    def test_3pl_rate_card_line_create_is_refused_on_an_active_card(
            self, client_a, tpl_active_card_a):
        response = client_a.post(reverse("scm:clientratecardline_create",
                                         args=[tpl_active_card_a.pk]),
                                 _3pl_card_line_payload())
        assert response.status_code == 302
        assert tpl_active_card_a.lines.count() == 2, "no line may be added to a live tariff"
        assert _3pl_said(response, "can no longer be changed")

    def test_3pl_rate_card_line_create_refuses_a_period_on_an_event_basis(
            self, client_a, tpl_rate_card_a):
        response = client_a.post(reverse("scm:clientratecardline_create",
                                         args=[tpl_rate_card_a.pk]),
                                 _3pl_card_line_payload(period="month"))
        assert response.status_code == 200, "a rejected line re-renders the form"
        assert not tpl_rate_card_a.lines.filter(description="Order handling").exists()

    def test_3pl_rate_card_line_create_refuses_another_clients_dedicated_bin(
            self, client_a, tpl_rate_card_a, tpl_other_client_location_a):
        """Pricing one client's storage against another client's aisle is the mistake whose output
        looks entirely plausible."""
        response = client_a.post(
            reverse("scm:clientratecardline_create", args=[tpl_rate_card_a.pk]),
            _3pl_card_line_payload(applies_to_location=str(tpl_other_client_location_a.pk)))
        assert response.status_code == 200
        assert not tpl_rate_card_a.lines.filter(description="Order handling").exists()

    def test_3pl_rate_card_line_edit_round_trips(self, client_a, tpl_rate_card_line_a,
                                                 tpl_rate_card_a):
        url = reverse("scm:clientratecardline_edit", args=[tpl_rate_card_line_a.pk])
        page = client_a.get(url)
        assert page.status_code == 200
        assert page.context["is_edit"] is True
        assert page.context["obj"].pk == tpl_rate_card_line_a.pk
        assert page.context["rate_card"].pk == tpl_rate_card_a.pk

        response = client_a.post(url, _3pl_card_line_payload(
            charge_category="receiving", charge_basis="per_receipt",
            description="Receipt handling v2", rate="15.0000"))
        assert response.status_code == 302
        tpl_rate_card_line_a.refresh_from_db()
        assert tpl_rate_card_line_a.description == "Receipt handling v2"
        assert tpl_rate_card_line_a.rate == Decimal("15.0000")

    def test_3pl_rate_card_line_delete_get_is_405(self, client_a, tpl_rate_card_line_a):
        from apps.scm.models import ClientRateCardLine
        response = client_a.get(reverse("scm:clientratecardline_delete",
                                        args=[tpl_rate_card_line_a.pk]))
        assert response.status_code == 405
        assert ClientRateCardLine.objects.filter(pk=tpl_rate_card_line_a.pk).exists()

    def test_3pl_rate_card_line_delete_post_removes_it(self, client_a, tpl_rate_card_line_a,
                                                       tpl_rate_card_a):
        from apps.scm.models import ClientRateCardLine
        response = client_a.post(reverse("scm:clientratecardline_delete",
                                         args=[tpl_rate_card_line_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientratecard_detail",
                                               args=[tpl_rate_card_a.pk])
        assert not ClientRateCardLine.objects.filter(pk=tpl_rate_card_line_a.pk).exists()


# =================================================================================================
# 3. ClientBillingRun — the register, the ladder and the manual charges
# =================================================================================================
@pytest.mark.django_db
class Test3plBillingRunList:

    def test_3pl_run_list_renders_with_its_pinned_context(self, client_a, tpl_billing_run_a):
        response = client_a.get(reverse("scm:clientbillingrun_list"))
        assert response.status_code == 200
        assert "scm/3pl/clientbillingrun/list.html" in _3pl_templates(response)
        ctx = response.context
        assert [r.pk for r in ctx["object_list"]] == [tpl_billing_run_a.pk]
        assert list(ctx["clients"])
        assert ("draft", "Draft") in list(ctx["status_choices"])
        assert set(ctx["stats"]) == {"total", "draft", "calculated", "approved", "invoiced",
                                     "void", "approved_value"}
        assert ctx["stats"]["total"] == 1 and ctx["stats"]["draft"] == 1
        assert ctx["stats"]["approved_value"] == Decimal("0")

    def test_3pl_run_list_approved_value_sums_approved_and_invoiced_runs(
            self, client_a, admin_user, tpl_billing_run_a):
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        stats = client_a.get(reverse("scm:clientbillingrun_list")).context["stats"]
        assert stats["approved"] == 1
        assert stats["approved_value"] == Decimal("500.00")

    def test_3pl_run_list_search_and_client_filter_narrow(
            self, client_a, tpl_billing_run_a, tpl_client_a):
        by_number = client_a.get(reverse("scm:clientbillingrun_list"),
                                 {"q": tpl_billing_run_a.number})
        assert [r.pk for r in by_number.context["object_list"]] == [tpl_billing_run_a.pk]

        by_client = client_a.get(reverse("scm:clientbillingrun_list"),
                                 {"client": str(tpl_client_a.pk)})
        assert [r.pk for r in by_client.context["object_list"]] == [tpl_billing_run_a.pk]

        by_status = client_a.get(reverse("scm:clientbillingrun_list"), {"status": "approved"})
        assert list(by_status.context["object_list"]) == []

    def test_3pl_run_list_period_bounds_filter_on_iso_dates(
            self, client_a, tpl_billing_run_a, tpl_period):
        start, end = tpl_period
        inside = client_a.get(reverse("scm:clientbillingrun_list"),
                              {"period_from": start.isoformat(), "period_to": end.isoformat()})
        assert [r.pk for r in inside.context["object_list"]] == [tpl_billing_run_a.pk]

        after = client_a.get(reverse("scm:clientbillingrun_list"),
                             {"period_from": (end + datetime.timedelta(days=1)).isoformat()})
        assert list(after.context["object_list"]) == []

    @pytest.mark.parametrize("query", [
        {"period_from": "lastweek"}, {"period_to": "2026-13-45"}, {"period_from": "  "},
        {"period_from": "99999-01-01"}, {"client": "abc"}, {"status": "zzz"},
    ])
    def test_3pl_run_list_junk_params_are_200(self, client_a, tpl_billing_run_a, query):
        """``_as_date`` hand-parses both bounds — junk must SKIP the filter, never raise."""
        response = client_a.get(reverse("scm:clientbillingrun_list"), query)
        assert response.status_code == 200, f"{query} 500'd the billing-run list"

    def test_3pl_run_list_junk_date_does_not_silently_filter_rows_out(
            self, client_a, tpl_billing_run_a):
        response = client_a.get(reverse("scm:clientbillingrun_list"),
                                {"period_from": "lastweek"})
        assert [r.pk for r in response.context["object_list"]] == [tpl_billing_run_a.pk]

    def test_3pl_run_list_paginates_with_a_real_page_two(
            self, client_a, tenant_a, tpl_client_a, tpl_active_card_a):
        _3pl_bulk_runs(tenant_a, tpl_client_a, tpl_active_card_a, 21)
        page1 = client_a.get(reverse("scm:clientbillingrun_list"))
        assert len(page1.context["object_list"]) == 15
        page2 = client_a.get(reverse("scm:clientbillingrun_list"), {"page": "2"})
        assert len(page2.context["object_list"]) == 6
        assert client_a.get(reverse("scm:clientbillingrun_list"),
                            {"page": "abc"}).status_code == 200

    def test_3pl_run_list_does_not_query_per_row(
            self, client_a, tenant_a, tpl_client_a, tpl_active_card_a,
            django_assert_max_num_queries):
        """A row prints ``client.code``, ``rate_card.number`` and the invoice chip — three FKs, plus
        the ``client.party`` hop ``__str__`` walks."""
        url = reverse("scm:clientbillingrun_list")
        _3pl_bulk_runs(tenant_a, tpl_client_a, tpl_active_card_a, 3)
        few = _3pl_query_count(client_a, url)

        _3pl_bulk_runs(tenant_a, tpl_client_a, tpl_active_card_a, 18, start=3)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 15
        assert _3pl_query_count(client_a, url) == few, "the billing-run register queries per row"


@pytest.mark.django_db
class Test3plBillingRunCrud:

    def test_3pl_run_create_post_saves_with_the_request_tenant(
            self, client_a, tenant_a, tpl_client_a, tpl_active_card_a):
        from apps.scm.models import ClientBillingRun
        today = timezone.localdate()
        response = client_a.post(
            reverse("scm:clientbillingrun_create"),
            _3pl_run_payload(tpl_client_a, tpl_active_card_a,
                             today - datetime.timedelta(days=20),
                             today - datetime.timedelta(days=10)))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientbillingrun_list")
        run = ClientBillingRun.objects.get(period_end=today - datetime.timedelta(days=10))
        assert run.tenant_id == tenant_a.pk
        assert run.number.startswith("CBR-")
        assert run.status == "draft", "status is editable=False — the ladder is its only writer"
        assert run.total == Decimal("0")

    def test_3pl_run_create_refuses_a_tariff_belonging_to_another_client(
            self, client_a, tpl_client_shared_a, tpl_active_card_a):
        """"Bill Acme at Contoso's rates" is the one mistake here whose output looks plausible."""
        from apps.scm.models import ClientBillingRun
        today = timezone.localdate()
        response = client_a.post(
            reverse("scm:clientbillingrun_create"),
            _3pl_run_payload(tpl_client_shared_a, tpl_active_card_a,
                             today - datetime.timedelta(days=20), today))
        assert response.status_code == 200
        assert not ClientBillingRun.objects.filter(client=tpl_client_shared_a).exists()

    def test_3pl_run_create_refuses_another_workspaces_client_and_card(
            self, client_a, tpl_client_b, tpl_rate_card_b):
        from apps.scm.models import ClientBillingRun
        today = timezone.localdate()
        before = ClientBillingRun.objects.count()
        response = client_a.post(
            reverse("scm:clientbillingrun_create"),
            _3pl_run_payload(tpl_client_b, tpl_rate_card_b,
                             today - datetime.timedelta(days=20), today))
        assert response.status_code == 200
        assert ClientBillingRun.objects.count() == before

    def test_3pl_run_detail_carries_every_pinned_key(
            self, client_a, tpl_billing_run_a, tpl_billing_run_line_a):
        response = client_a.get(reverse("scm:clientbillingrun_detail",
                                        args=[tpl_billing_run_a.pk]))
        assert response.status_code == 200
        assert "scm/3pl/clientbillingrun/detail.html" in _3pl_templates(response)
        ctx = response.context
        assert ctx["obj"].pk == tpl_billing_run_a.pk
        assert [line.pk for line in ctx["lines"]] == [tpl_billing_run_line_a.pk]
        assert ctx["line_count"] == 1 and ctx["manual_line_count"] == 1
        assert ctx["needs_quantity_count"] == 0
        groups = ctx["line_groups"]
        assert len(groups) == 1
        assert groups[0]["category"] == "value_added"
        assert groups[0]["subtotal"] == Decimal("50.00")
        assert ctx["subtotal"] == tpl_billing_run_a.subtotal
        assert ctx["minimum_adjustment"] == tpl_billing_run_a.minimum_adjustment
        assert ctx["total"] == tpl_billing_run_a.total
        assert isinstance(ctx["minimum_applied"], bool) and ctx["minimum_reason"]
        assert ctx["unbilled"] is not None
        assert ctx["sla_credits"] == [] and ctx["sla_credit_total"] == Decimal("0.00")
        assert ctx["invoice"] is None
        assert ctx["panel_limit"] == 20
        assert ctx["can_edit"] and ctx["can_add_line"] and ctx["can_calculate"]
        assert ctx["can_approve"] is False, "a draft has not been calculated yet"
        assert ctx["can_draft_invoice"] is False
        assert ctx["can_void"] and ctx["can_delete"]

    def test_3pl_run_detail_suggests_a_credit_only_once_an_sla_is_breached(
            self, client_a, admin_user, tpl_billing_run_a, tpl_sla_a):
        from apps.scm.models import ClientSLA
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(status="breached")
        ctx = client_a.get(reverse("scm:clientbillingrun_detail",
                                   args=[tpl_billing_run_a.pk])).context
        assert len(ctx["sla_credits"]) == 1
        # 5% of the 500.00 run, capped at 10% — a SUGGESTION, applied to nothing.
        assert ctx["sla_credit_total"] == Decimal("25.00")

    def test_3pl_run_edit_round_trips_while_draft(
            self, client_a, tpl_billing_run_a, tpl_client_a, tpl_active_card_a, tpl_period):
        start, end = tpl_period
        response = client_a.post(
            reverse("scm:clientbillingrun_edit", args=[tpl_billing_run_a.pk]),
            _3pl_run_payload(tpl_client_a, tpl_active_card_a, start, end, notes="amended"))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientbillingrun_detail",
                                               args=[tpl_billing_run_a.pk])
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.notes == "amended"

    def test_3pl_run_edit_is_refused_once_approved(
            self, client_a, admin_user, tpl_billing_run_a, tpl_client_a, tpl_active_card_a,
            tpl_period):
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        start, end = tpl_period
        response = client_a.post(
            reverse("scm:clientbillingrun_edit", args=[tpl_billing_run_a.pk]),
            _3pl_run_payload(tpl_client_a, tpl_active_card_a, start, end, notes="rewritten"))
        assert response.status_code == 302
        assert _3pl_said(response, "can no longer be edited")
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.notes != "rewritten"

    def test_3pl_run_delete_get_is_405(self, client_a, tpl_billing_run_a):
        from apps.scm.models import ClientBillingRun
        response = client_a.get(reverse("scm:clientbillingrun_delete",
                                        args=[tpl_billing_run_a.pk]))
        assert response.status_code == 405
        assert ClientBillingRun.objects.filter(pk=tpl_billing_run_a.pk).exists()

    def test_3pl_run_delete_post_removes_a_draft(self, client_a, tpl_billing_run_a):
        from apps.scm.models import ClientBillingRun
        response = client_a.post(reverse("scm:clientbillingrun_delete",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientbillingrun_list")
        assert not ClientBillingRun.objects.filter(pk=tpl_billing_run_a.pk).exists()

    def test_3pl_run_delete_is_refused_once_approved(
            self, client_a, admin_user, tpl_billing_run_a):
        """``approve`` is tenant-admin gated, so a deletable approved run let a member erase an
        admin's signature through a route the ladder itself refuses."""
        from apps.scm.models import ClientBillingRun
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        response = client_a.post(reverse("scm:clientbillingrun_delete",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        assert ClientBillingRun.objects.filter(pk=tpl_billing_run_a.pk).exists()
        assert _3pl_said(response, "approved")


@pytest.mark.django_db
class Test3plBillingRunLadder:

    def test_3pl_run_calculate_prices_the_period_and_applies_the_monthly_minimum(
            self, client_a, tpl_billing_run_a):
        response = client_a.post(reverse("scm:clientbillingrun_calculate",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "calculated"
        assert tpl_billing_run_a.subtotal == Decimal("250.00")
        assert tpl_billing_run_a.minimum_adjustment == Decimal("250.00")
        assert tpl_billing_run_a.total == Decimal("500.00")
        assert tpl_billing_run_a.calculated_at is not None
        assert _3pl_said(response, "calculated")

    def test_3pl_run_calculate_keeps_manual_lines_and_regenerates_derived_ones(
            self, client_a, tpl_billing_run_a, tpl_billing_run_line_a):
        client_a.post(reverse("scm:clientbillingrun_calculate", args=[tpl_billing_run_a.pk]))
        client_a.post(reverse("scm:clientbillingrun_calculate", args=[tpl_billing_run_a.pk]))
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.lines.filter(pk=tpl_billing_run_line_a.pk).exists()
        assert tpl_billing_run_a.lines.filter(is_manual=False).count() == 1, (
            "pressing calculate twice must not duplicate the derived lines")
        assert tpl_billing_run_a.subtotal == Decimal("300.00")

    def test_3pl_run_approve_refuses_a_run_that_was_never_calculated(
            self, client_a, tpl_billing_run_a):
        """L35: an absent prerequisite is REJECTED, never fallen through to approval."""
        response = client_a.post(reverse("scm:clientbillingrun_approve",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "draft"
        assert tpl_billing_run_a.approved_by_id is None and tpl_billing_run_a.approved_at is None
        assert _3pl_messages(response), "a refused approval must say why"

    def test_3pl_run_approve_stamps_the_signature(self, client_a, admin_user, tpl_billing_run_a):
        _3pl_calculated_run(tpl_billing_run_a)
        response = client_a.post(reverse("scm:clientbillingrun_approve",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "approved"
        assert tpl_billing_run_a.approved_by_id == admin_user.pk
        assert tpl_billing_run_a.approved_at is not None

    # The ``@tenant_admin_required`` half of approve / draft_invoice (403 for a plain member, and the
    # positive admin case) is asserted in ``test_3pl_security.py::Test3plAdminGates``.

    def test_3pl_run_draft_invoice_refuses_a_run_that_was_never_approved(
            self, client_a, tpl_billing_run_a):
        _3pl_calculated_run(tpl_billing_run_a)
        response = client_a.post(reverse("scm:clientbillingrun_draft_invoice",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "calculated"
        assert tpl_billing_run_a.invoice_id is None

    def test_3pl_run_draft_invoice_creates_a_draft_invoice_matching_the_total(
            self, client_a, admin_user, tpl_billing_run_a):
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        response = client_a.post(reverse("scm:clientbillingrun_draft_invoice",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "invoiced"
        invoice = tpl_billing_run_a.invoice
        assert invoice is not None
        assert invoice.status == "draft"
        assert invoice.subtotal == tpl_billing_run_a.total

    def test_3pl_run_draft_invoice_refuses_a_second_draft(
            self, client_a, admin_user, tpl_billing_run_a):
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        client_a.post(reverse("scm:clientbillingrun_draft_invoice", args=[tpl_billing_run_a.pk]))
        tpl_billing_run_a.refresh_from_db()
        first = tpl_billing_run_a.invoice_id

        response = client_a.post(reverse("scm:clientbillingrun_draft_invoice",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.invoice_id == first, "a second draft would double-bill the client"

    def test_3pl_run_void_retires_a_draft(self, client_a, tpl_billing_run_a):
        response = client_a.post(reverse("scm:clientbillingrun_void",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "void"

    def test_3pl_run_void_refuses_an_invoiced_run(self, client_a, admin_user, tpl_billing_run_a):
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        client_a.post(reverse("scm:clientbillingrun_draft_invoice", args=[tpl_billing_run_a.pk]))
        response = client_a.post(reverse("scm:clientbillingrun_void",
                                         args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "invoiced"


@pytest.mark.django_db
class Test3plBillingRunLineCrud:

    def test_3pl_run_line_create_get_names_the_parent_run(self, client_a, tpl_billing_run_a):
        response = client_a.get(reverse("scm:clientbillingrunline_create",
                                        args=[tpl_billing_run_a.pk]))
        assert response.status_code == 200
        assert "scm/3pl/clientbillingrunline/form.html" in _3pl_templates(response)
        assert response.context["is_edit"] is False
        assert response.context["run"].pk == tpl_billing_run_a.pk
        assert "run" not in response.context["form"].fields
        assert "is_manual" not in response.context["form"].fields

    def test_3pl_run_line_create_forces_is_manual_and_retotals_the_run(
            self, client_a, tpl_billing_run_a):
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload(is_manual="false"))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientbillingrun_detail",
                                               args=[tpl_billing_run_a.pk])
        line = ClientBillingRunLine.objects.get(description="Rework labour")
        assert line.run_id == tpl_billing_run_a.pk
        assert line.is_manual is True, "is_manual is FORCED by the view, never posted"
        assert line.amount == Decimal("60.00")
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.subtotal == Decimal("60.00")

    @pytest.mark.parametrize("field,value", [
        ("quantity", "-1"), ("rate", "-5.00"),
        ("quantity", "NaN"), ("rate", "NaN"),
        ("quantity", "Infinity"), ("rate", "-Infinity"),
        ("quantity", "abc"), ("rate", "1e999"),
        ("quantity", "99999999999999999999.0000"), ("rate", "999999999999999999.0000"),
        ("quantity", ""), ("rate", ""),
    ])
    def test_3pl_run_line_create_refuses_a_poisoned_number_without_a_500(
            self, client_a, tpl_billing_run_a, field, value):
        """NaN/Infinity/garbage/negative/over-max_digits are FORM errors, never a traceback — and a
        negative would silently floor to 0.00 in ``save()``, which is worse than a refusal."""
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload(**{field: value}))
        assert response.status_code == 200, f"{field}={value!r} 500'd the manual-charge form"
        assert not ClientBillingRunLine.objects.filter(description="Rework labour").exists()
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.subtotal == Decimal("0.00")

    def test_3pl_run_line_create_is_refused_on_an_approved_run(
            self, client_a, admin_user, tpl_billing_run_a):
        from apps.scm.models import ClientBillingRunLine
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload())
        assert response.status_code == 302
        assert not ClientBillingRunLine.objects.filter(description="Rework labour").exists()
        assert _3pl_said(response, "can no longer take new charges")

    def test_3pl_run_line_edit_round_trips_and_retotals(
            self, client_a, tpl_billing_run_a, tpl_billing_run_line_a):
        url = reverse("scm:clientbillingrunline_edit", args=[tpl_billing_run_line_a.pk])
        page = client_a.get(url)
        assert page.status_code == 200
        assert page.context["is_edit"] is True
        assert page.context["run"].pk == tpl_billing_run_a.pk
        assert page.context["obj"].pk == tpl_billing_run_line_a.pk

        response = client_a.post(url, _3pl_run_line_payload(
            description="Kitting and rework labour", quantity="4", rate="25.0000"))
        assert response.status_code == 302
        tpl_billing_run_line_a.refresh_from_db()
        assert tpl_billing_run_line_a.amount == Decimal("100.00")
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.subtotal == Decimal("100.00")

    def test_3pl_run_line_delete_get_is_405(self, client_a, tpl_billing_run_line_a):
        from apps.scm.models import ClientBillingRunLine
        response = client_a.get(reverse("scm:clientbillingrunline_delete",
                                        args=[tpl_billing_run_line_a.pk]))
        assert response.status_code == 405
        assert ClientBillingRunLine.objects.filter(pk=tpl_billing_run_line_a.pk).exists()

    def test_3pl_run_line_delete_post_removes_it_and_retotals(
            self, client_a, tpl_billing_run_a, tpl_billing_run_line_a):
        from apps.scm.models import ClientBillingRunLine
        tpl_billing_run_a.recalc_amounts()
        response = client_a.post(reverse("scm:clientbillingrunline_delete",
                                         args=[tpl_billing_run_line_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientbillingrun_detail",
                                               args=[tpl_billing_run_a.pk])
        assert not ClientBillingRunLine.objects.filter(pk=tpl_billing_run_line_a.pk).exists()
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.subtotal == Decimal("0.00")


# =================================================================================================
# 4. ClientSLA — the register and the two measurement verbs
# =================================================================================================
@pytest.mark.django_db
class Test3plSlaList:

    def test_3pl_sla_list_renders_with_its_pinned_context(self, client_a, tpl_sla_a):
        response = client_a.get(reverse("scm:clientsla_list"))
        assert response.status_code == 200
        assert "scm/3pl/clientsla/list.html" in _3pl_templates(response)
        ctx = response.context
        assert [s.pk for s in ctx["object_list"]] == [tpl_sla_a.pk]
        assert list(ctx["clients"])
        assert ("otif_pct", "OTIF %") in list(ctx["metric_choices"])
        # THIS EXACT NAME — not `status_choices`, so a shared partial cannot confuse it with a
        # rate-card or billing-run status list.
        assert ("breached", "Breached") in list(ctx["sla_status_choices"])
        assert "status_choices" not in ctx or ctx["status_choices"] is None
        assert ctx["stats"] == {"total": 1, "meeting": 0, "at_risk": 0, "breached": 0,
                                "no_data": 1}
        assert ctx["not_measured_note"], "the never-measured caveat must reach the template"

    @pytest.mark.parametrize("param,value,hit", [
        ("metric", "on_time_shipment_pct", True),
        ("metric", "damage_rate_pct", False),
        ("status", "no_data", True),
        ("status", "breached", False),
        ("active", "True", True),
        ("active", "False", False),
    ])
    def test_3pl_sla_list_each_filter_narrows(self, client_a, tpl_sla_a, param, value, hit):
        response = client_a.get(reverse("scm:clientsla_list"), {param: value})
        assert response.status_code == 200
        found = [s.pk for s in response.context["object_list"]]
        assert (found == [tpl_sla_a.pk]) is hit

    @pytest.mark.parametrize("query", [
        {"client": "abc"}, {"metric": "zzz"}, {"status": "zzz"}, {"active": "abc"},
        {"client": "99999999999999999999"},
    ])
    def test_3pl_sla_list_junk_params_are_200(self, client_a, tpl_sla_a, query):
        assert client_a.get(reverse("scm:clientsla_list"), query).status_code == 200

    def test_3pl_sla_list_search_matches_the_client_code(self, client_a, tpl_sla_a):
        response = client_a.get(reverse("scm:clientsla_list"), {"q": "ACME"})
        assert [s.pk for s in response.context["object_list"]] == [tpl_sla_a.pk]

    def test_3pl_sla_list_paginates_with_a_real_page_two(
            self, client_a, tenant_a, tpl_client_a, tpl_client_shared_a):
        third = _3pl_bulk_clients(tenant_a, 1, prefix="THIRD")[0]
        _3pl_bulk_slas(tenant_a, [tpl_client_a, tpl_client_shared_a, third], 21)
        page1 = client_a.get(reverse("scm:clientsla_list"))
        assert len(page1.context["object_list"]) == 15
        page2 = client_a.get(reverse("scm:clientsla_list"), {"page": "2"})
        assert len(page2.context["object_list"]) == 6
        assert client_a.get(reverse("scm:clientsla_list"), {"page": "999"}).status_code == 200

    def test_3pl_sla_list_does_not_query_per_row(
            self, client_a, tenant_a, tpl_client_a, tpl_client_shared_a,
            django_assert_max_num_queries):
        """Every row prints ``client.code`` and ``ClientSLA.__str__`` walks the client too."""
        url = reverse("scm:clientsla_list")
        third = _3pl_bulk_clients(tenant_a, 1, prefix="THIRD")[0]
        clients = [tpl_client_a, tpl_client_shared_a, third]
        _3pl_bulk_slas(tenant_a, clients, 3)
        few = _3pl_query_count(client_a, url)

        _3pl_bulk_slas(tenant_a, clients, 18, start=3)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 15
        assert _3pl_query_count(client_a, url) == few, "the SLA register queries per row"


@pytest.mark.django_db
class Test3plSlaCrud:

    def test_3pl_sla_create_post_saves_with_the_request_tenant(
            self, client_a, tenant_a, tpl_client_a):
        from apps.scm.models import ClientSLA
        response = client_a.post(reverse("scm:clientsla_create"), _3pl_sla_payload(tpl_client_a))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientsla_list")
        sla = ClientSLA.objects.get(metric="order_accuracy_pct")
        assert sla.tenant_id == tenant_a.pk
        assert sla.number.startswith("SLA-")
        assert sla.status == "no_data", "never measured is the honest default, not 0"
        assert sla.last_measured_value is None

    def test_3pl_sla_create_refuses_a_unit_the_registry_disagrees_with(
            self, client_a, tpl_client_a):
        from apps.scm.models import ClientSLA
        response = client_a.post(reverse("scm:clientsla_create"),
                                 _3pl_sla_payload(tpl_client_a, unit="hours"))
        assert response.status_code == 200
        assert not ClientSLA.objects.filter(metric="order_accuracy_pct").exists()

    def test_3pl_sla_create_refuses_another_workspaces_client(self, client_a, tpl_client_b):
        from apps.scm.models import ClientSLA
        before = ClientSLA.objects.count()
        response = client_a.post(reverse("scm:clientsla_create"), _3pl_sla_payload(tpl_client_b))
        assert response.status_code == 200
        assert ClientSLA.objects.count() == before

    def test_3pl_sla_detail_carries_every_pinned_key(self, client_a, tpl_sla_a):
        response = client_a.get(reverse("scm:clientsla_detail", args=[tpl_sla_a.pk]))
        assert response.status_code == 200
        assert "scm/3pl/clientsla/detail.html" in _3pl_templates(response)
        ctx = response.context
        assert ctx["obj"].pk == tpl_sla_a.pk
        assert set(ctx["metric_meta"]) == {"label", "unit", "direction", "default_target", "source"}
        assert ctx["metric_meta"]["source"], "the page's job is to say where the figure came from"
        assert ctx["status_css"] == "badge-muted"
        assert ctx["is_measured"] is False
        assert ctx["variance"] is None, "never measured must be None, never 0"
        assert ctx["is_breaching"] is False
        assert ctx["window_label"]
        assert ctx["suggested_credit"] == Decimal("0")
        assert ctx["credit_basis"] == Decimal("0")
        assert ctx["credit_basis_run"] is None
        assert ctx["credit_pct"] == Decimal("5.00")
        assert ctx["credit_cap_pct"] == Decimal("10.00")
        assert ctx["can_recompute"] is True

    def test_3pl_sla_detail_names_the_billed_run_a_credit_would_be_sized_from(
            self, client_a, admin_user, tpl_sla_a, tpl_billing_run_a):
        _3pl_approved_run(tpl_billing_run_a, admin_user)
        ctx = client_a.get(reverse("scm:clientsla_detail", args=[tpl_sla_a.pk])).context
        assert ctx["credit_basis_run"] is not None
        assert ctx["credit_basis_run"].pk == tpl_billing_run_a.pk
        assert ctx["credit_basis"] == Decimal("500.00")

    def test_3pl_sla_edit_round_trips(self, client_a, tpl_sla_a, tpl_client_a):
        response = client_a.post(
            reverse("scm:clientsla_edit", args=[tpl_sla_a.pk]),
            _3pl_sla_payload(tpl_client_a, metric="on_time_shipment_pct",
                             name="On-time shipment", target_value="97.00",
                             warning_threshold="94.00", service_credit_pct="5.00",
                             service_credit_cap_pct="10.00"))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientsla_list")
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.target_value == Decimal("97.00")

    def test_3pl_sla_edit_cannot_reach_the_evidence_columns(self, client_a, tpl_sla_a,
                                                            tpl_client_a):
        """All eight measurement columns are editable=False; an edit changes the promise, never what
        was measured."""
        client_a.post(reverse("scm:clientsla_edit", args=[tpl_sla_a.pk]),
                      _3pl_sla_payload(tpl_client_a, metric="on_time_shipment_pct",
                                       target_value="97.00", warning_threshold="94.00",
                                       status="meeting", last_measured_value="99.99",
                                       breach_count="7", sample_size="42"))
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.status == "no_data"
        assert tpl_sla_a.last_measured_value is None
        assert tpl_sla_a.breach_count == 0
        assert tpl_sla_a.sample_size == 0

    def test_3pl_sla_delete_get_is_405(self, client_a, tpl_sla_a):
        from apps.scm.models import ClientSLA
        response = client_a.get(reverse("scm:clientsla_delete", args=[tpl_sla_a.pk]))
        assert response.status_code == 405
        assert ClientSLA.objects.filter(pk=tpl_sla_a.pk).exists()

    def test_3pl_sla_delete_post_removes_it(self, client_a, tpl_sla_a):
        from apps.scm.models import ClientSLA
        response = client_a.post(reverse("scm:clientsla_delete", args=[tpl_sla_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientsla_list")
        assert not ClientSLA.objects.filter(pk=tpl_sla_a.pk).exists()

    def test_3pl_sla_delete_steers_to_deactivating_when_breaches_were_recorded(
            self, client_a, tpl_sla_a):
        from apps.scm.models import ClientSLA
        ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(breach_count=3)
        response = client_a.post(reverse("scm:clientsla_delete", args=[tpl_sla_a.pk]))
        assert response.status_code == 302
        assert _3pl_said(response, "breach window")


@pytest.mark.django_db
class Test3plSlaRecompute:

    def test_3pl_sla_recompute_measures_and_reports_no_data_honestly(self, client_a, tpl_sla_a):
        """No shipments in the window: ``recompute()`` must leave the value NULL and SAY why rather
        than writing a flattering 0."""
        response = client_a.post(reverse("scm:clientsla_recompute", args=[tpl_sla_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientsla_detail", args=[tpl_sla_a.pk])
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.status == "no_data"
        assert tpl_sla_a.last_measured_value is None
        assert tpl_sla_a.measurement_summary, "no-data must carry the resolver's own reason"
        assert _3pl_said(response, "could not be measured")

    def test_3pl_sla_recompute_refuses_an_inactive_promise(self, client_a, tpl_sla_a):
        from apps.scm.models import ClientSLA
        ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(is_active=False, breach_count=0)
        response = client_a.post(reverse("scm:clientsla_recompute", args=[tpl_sla_a.pk]))
        assert response.status_code == 302
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.measurement_window_start is None
        assert _3pl_said(response, "not active")

    def test_3pl_sla_recompute_all_sweeps_the_workspace(self, client_a, tpl_sla_a):
        response = client_a.post(reverse("scm:clientsla_recompute_all"))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:clientsla_list")
        assert _3pl_said(response, "recompute complete")

    def test_3pl_sla_recompute_all_says_so_when_there_is_nothing_active(self, client_a, tenant_a):
        response = client_a.post(reverse("scm:clientsla_recompute_all"))
        assert response.status_code == 302
        assert _3pl_said(response, "no active slas")

    def test_3pl_sla_recompute_all_skips_another_workspaces_promises(
            self, client_a, tpl_sla_a, tpl_sla_b):
        client_a.post(reverse("scm:clientsla_recompute_all"))
        tpl_sla_b.refresh_from_db()
        assert tpl_sla_b.measurement_window_start is None, (
            "the sweep must never touch another workspace's row")


# =================================================================================================
# 5. The two computed report pages — they write NOTHING
# =================================================================================================
@pytest.mark.django_db
class Test3plReports:

    def test_3pl_inventory_report_carries_every_pinned_key_populated(
            self, client_a, tpl_client_a, tpl_stock_move_a, item_a):
        response = client_a.get(reverse("scm:client_inventory_report"))
        assert response.status_code == 200
        assert "scm/3pl/client_inventory_report.html" in _3pl_templates(response)
        ctx = response.context
        row = next(r for r in ctx["rows"] if r["client"].pk == tpl_client_a.pk)
        assert set(row) == {"client", "sku_count", "on_hand_quantity", "on_hand_value",
                            "dedicated_locations"}
        assert row["sku_count"] == 1
        assert row["on_hand_quantity"] == Decimal("100.0000")
        assert row["on_hand_value"] == Decimal("1000.00")
        assert row["dedicated_locations"] == 1
        assert ctx["totals"]["on_hand_value"] == Decimal("1000.00")
        assert list(ctx["clients"]) and list(ctx["categories"]) and list(ctx["locations"])
        assert ctx["selected_client"] is None
        assert ctx["item_rows"] == [], "no client selected means an EMPTY list, never absent"
        assert ctx["unassigned_sku_count"] == 1, "item_a has no owner — that is the segregation gap"
        assert ctx["truncated"] is False and ctx["ledger_truncated"] is False
        assert ctx["row_cap"] == 100 and ctx["ledger_cap"] == 20000
        assert ctx["location_note"] and ctx["reads_only_note"]

    def test_3pl_inventory_report_selecting_a_client_fills_the_per_sku_breakdown(
            self, client_a, tpl_client_a, tpl_owned_item_a, tpl_stock_move_a):
        response = client_a.get(reverse("scm:client_inventory_report"),
                                {"client": str(tpl_client_a.pk)})
        ctx = response.context
        assert ctx["selected_client"].pk == tpl_client_a.pk
        assert len(ctx["rows"]) == 1
        assert [r["item"].pk for r in ctx["item_rows"]] == [tpl_owned_item_a.pk]
        assert ctx["item_rows"][0]["quantity"] == Decimal("100.0000")
        assert ctx["item_rows"][0]["value"] == Decimal("1000.00")

    def test_3pl_inventory_report_location_filter_narrows_the_ledger_not_the_sku_count(
            self, client_a, tpl_client_a, tpl_stock_move_a, location_a):
        response = client_a.get(reverse("scm:client_inventory_report"),
                                {"location": str(location_a.pk)})
        row = next(r for r in response.context["rows"] if r["client"].pk == tpl_client_a.pk)
        assert row["on_hand_quantity"] == Decimal("0"), "no stock of theirs sits in WH1"
        assert row["sku_count"] == 1, "the assigned-SKU count is a property of the item master"

    @pytest.mark.parametrize("query", [
        {"client": "abc"}, {"category": "abc"}, {"location": "²"},
        {"client": "99999999999999999999"}, {"category": "-1"},
    ])
    def test_3pl_inventory_report_junk_params_are_200(self, client_a, tpl_client_a, query):
        response = client_a.get(reverse("scm:client_inventory_report"), query)
        assert response.status_code == 200, f"{query} 500'd the segregation report"

    def test_3pl_inventory_report_renders_200_on_an_empty_workspace(self, client_a, tenant_a):
        response = client_a.get(reverse("scm:client_inventory_report"))
        assert response.status_code == 200
        assert response.context["rows"] == []
        assert response.context["totals"]["on_hand_value"] == Decimal("0.00")

    def test_3pl_space_report_carries_every_pinned_key(
            self, client_a, tpl_client_a, tpl_dedicated_location_a):
        response = client_a.get(reverse("scm:client_space_report"))
        assert response.status_code == 200
        assert "scm/3pl/client_space_report.html" in _3pl_templates(response)
        ctx = response.context
        row = next(r for r in ctx["rows"] if r["client"].pk == tpl_client_a.pk)
        assert set(row) == {"client", "space_model", "space_model_label", "committed_sqft",
                            "committed_pallet_positions", "dedicated_locations",
                            "dedicated_capacity", "contract_start", "contract_end",
                            "days_to_expiry"}
        assert row["space_model"] == "dedicated" and row["space_model_label"] == "Dedicated"
        assert row["committed_sqft"] == Decimal("4000.00")
        assert row["committed_pallet_positions"] == 250
        assert row["dedicated_locations"] == 1
        assert row["dedicated_capacity"] == Decimal("120.00")
        assert row["days_to_expiry"] == 330
        assert set(ctx["totals"]) == {"committed_sqft", "committed_pallet_positions",
                                      "dedicated_locations", "dedicated_capacity"}
        assert ("hybrid", "Hybrid") in list(ctx["space_model_choices"])
        assert ctx["truncated"] is False and ctx["row_cap"] == 100
        assert ctx["today"] == timezone.localdate()
        assert ctx["capacity_note"] and ctx["reads_only_note"]

    def test_3pl_space_report_keeps_an_unrecorded_capacity_and_end_date_as_none(
            self, client_a, tpl_client_shared_a):
        """``None`` must never render as 0: no bin capacity on file is not zero capacity, and no
        contract end is not "expires today"."""
        row = next(r for r in client_a.get(reverse("scm:client_space_report")).context["rows"]
                   if r["client"].pk == tpl_client_shared_a.pk)
        assert row["dedicated_capacity"] is None
        assert row["days_to_expiry"] is None
        assert row["contract_end"] is None

    def test_3pl_space_report_space_model_filter_narrows_and_junk_is_ignored(
            self, client_a, tpl_client_a, tpl_client_shared_a):
        dedicated = client_a.get(reverse("scm:client_space_report"),
                                 {"space_model": "dedicated"})
        assert [r["client"].pk for r in dedicated.context["rows"]] == [tpl_client_a.pk]

        junk = client_a.get(reverse("scm:client_space_report"), {"space_model": "zzz"})
        assert junk.status_code == 200
        assert len(junk.context["rows"]) == 2, (
            "an unknown space model is IGNORED, not filtered down to nothing")

    @pytest.mark.parametrize("query", [
        {"client": "abc"}, {"client": "²"}, {"client": "99999999999999999999"},
    ])
    def test_3pl_space_report_junk_client_param_is_200(self, client_a, tpl_client_a, query):
        assert client_a.get(reverse("scm:client_space_report"), query).status_code == 200


# =================================================================================================
# 6. Cross-tenant isolation, auth, CSRF and the method guards
# =================================================================================================
# Deliberately EMPTY in this lane. Every one of those request-level guarantees is asserted in
# ``test_3pl_security.py`` and was asserted here too until this file and that one were reconciled:
#
#   * anonymous -> /login/ on all four lists, all four create pages and both reports
#     -> ``Test3plAnonymous``
#   * a tenant-B pk on any detail/edit/child-create GET, on any POST verb, and on either tenant-LESS
#     child line -> ``Test3plCrossTenantIsolation``
#   * every list and both reports excluding the other workspace, both directions
#     -> ``Test3plCrossTenantIsolation``
#   * GET on a POST-only route -> 405, and a GET on delete deleting nothing
#     -> ``Test3plPostOnlyRoutes``
#   * CSRF on a verb POST, a create POST and a delete POST, plus the token-carrying positive case
#     -> ``Test3plCsrf``
#   * ``@tenant_admin_required`` on approve / draft_invoice, and the members-can-still-use-the-rest
#     half -> ``Test3plAdminGates``
#
# Keeping a second copy here doubled the runtime of those assertions and gave two places to update
# when a route moves. What stays in THIS lane is what a request RENDERS: context keys, filters,
# pagination and the CRUD round-trip.
