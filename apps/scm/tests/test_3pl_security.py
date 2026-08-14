"""SCM 4.17 Third-Party Logistics (3PL) — ISOLATION AND HARDENING.

This lane asserts the things that are invisible when they work and catastrophic when they do not:

* **Multi-tenant isolation.** Tenant A asking for a tenant B pk gets a 404 on every detail, edit,
  delete and verb route — including the two TENANT-LESS children (``ClientRateCardLine`` is resolved
  through ``rate_card__tenant``, ``ClientBillingRunLine`` through ``run__tenant``), which are the
  dangerous ones: a bare pk lookup there would be a silent cross-tenant write that nothing about the
  response would reveal. A's lists and both report pages never carry B's rows, and a crafted POST
  naming B's pk in an FK field is refused rather than saved.
* **Auth.** Anonymous is redirected to ``/login/``; ``@tenant_admin_required`` (``approve`` and
  ``draft_invoice`` — the two verbs that turn warehouse activity into an AR document) 403s a plain
  member while the ordinary verbs still work for one; CSRF is enforced on every POST.
* **Negative input.** A junk FK filter param answers 200 rather than 500 (L11), pagination survives
  page 2 and a page past the end (L9), and every hand-typed decimal — ``NaN``, ``Infinity``, garbage,
  negative, over-``max_digits`` — comes back as a form error rather than a 500.
* **Absent prerequisites are REJECTED, never fallen through (L35).** Approving a run that was never
  calculated, invoicing one that was never approved, invoicing twice, voiding an invoiced run,
  recomputing an inactive SLA, and writing to a frozen tariff or a signed-off run all refuse.

**Every refusal is paired with the POSITIVE path (L44)**, so a guard that simply broke the feature
fails this file instead of passing it.

NAMING: test functions are ``test_3pl_*`` and every module-level name (helper, constant, fixture) is
``_3pl_*``. The ``tpl_`` fixtures in ``conftest.py`` carry a different prefix on purpose — ``3pl_x``
is not a legal Python identifier, while ``_3pl_x`` and ``test_3pl_x`` both are.

TIME BASIS (L16): every date is derived from ``timezone.localdate()``, the same basis the views and
models use, so nothing here flakes in the hours after local midnight.
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# =================================================================================================
# Helpers and payloads
# =================================================================================================
def _3pl_messages(response):
    """Every flashed message on a FOLLOWED response, as lowercase strings."""
    return [str(message).lower() for message in response.context["messages"]]


def _3pl_client_payload(party, **over):
    """A minimally valid ``LogisticsClientForm`` POST body (shared space, no commitment)."""
    data = {
        "party": str(party.pk), "code": "NEWCO", "parent_client": "", "status": "prospect",
        "billing_cycle": "monthly", "billing_day": "1", "next_billing_date": "",
        "storage_billing_method": "calendar_month", "minimum_monthly_charge": "0.00",
        "default_tax_rate_pct": "0.00", "currency": "", "payment_terms": "",
        "default_revenue_account": "", "space_model": "shared", "committed_sqft": "0.00",
        "committed_pallet_positions": "0", "contract_start": "", "contract_end": "",
        "notice_days": "0", "contract_document": "", "integration_mode": "none",
        "client_system": "", "edi_partner_id": "", "edi_qualifier": "", "account_manager": "",
        "notes": "",
    }
    data.update(over)
    return data


def _3pl_rate_card_payload(client, **over):
    """A valid ``ClientRateCardForm`` POST body — a DRAFT card starting the day after tomorrow."""
    today = timezone.localdate()
    data = {
        "client": str(client.pk), "name": "Crafted tariff", "version": "1", "status": "draft",
        "effective_from": (today + datetime.timedelta(days=2)).isoformat(),
        "effective_to": "", "currency": "", "notes": "",
    }
    data.update(over)
    return data


def _3pl_run_payload(client, rate_card, start, end, **over):
    """A valid ``ClientBillingRunForm`` POST body."""
    data = {
        "client": str(client.pk), "rate_card": str(rate_card.pk),
        "period_start": start.isoformat(), "period_end": end.isoformat(), "notes": "",
    }
    data.update(over)
    return data


def _3pl_sla_payload(client, **over):
    """A valid ``ClientSLAForm`` POST body.

    ``order_accuracy_pct`` fixes its own unit and direction in ``SLA_METRIC_META`` and it is NOT in
    ``LOCATION_SCOPABLE_METRICS``, so ``scope_location`` stays blank. It is also a different metric
    from ``tpl_sla_a``'s, so the ``(tenant, client, metric, scope_location)`` constraint is clear.
    """
    data = {
        "client": str(client.pk), "metric": "order_accuracy_pct", "name": "Order accuracy",
        "target_value": "99.50", "unit": "pct", "direction": "higher_is_better",
        "warning_threshold": "", "measurement_window": "monthly", "scope_location": "",
        "service_credit_pct": "0.00", "service_credit_cap_pct": "0.00", "is_active": "on",
        "notes": "",
    }
    data.update(over)
    return data


def _3pl_rate_line_payload(**over):
    """A valid ``ClientRateCardLineForm`` POST body — an EVENT basis, so ``period`` is blank."""
    data = {
        "charge_category": "receiving", "charge_basis": "per_receipt",
        "description": "Inbound receipt handling", "rate": "12.0000", "period": "",
        "included_quantity": "0", "minimum_charge": "0", "tier_from": "0", "tier_to": "",
        "applies_to_location": "", "applies_to_item_category": "", "gl_account": "",
        "is_active": "on",
    }
    data.update(over)
    return data


def _3pl_run_line_payload(**over):
    """A valid ``ClientBillingRunLineForm`` POST body — one manual charge, 2 x 25.00."""
    data = {
        "charge_category": "value_added", "charge_basis": "per_hour",
        "description": "Kitting labour", "quantity": "2.0000", "rate": "25.0000",
        "source_reference": "",
    }
    data.update(over)
    return data


def _3pl_bulk_clients(tenant, count, prefix="BULK"):
    """``count`` extra clients in ``tenant`` — the pagination and query-budget fixture material.

    Each needs its OWN party: ``LogisticsClient`` carries ``unique_together ("tenant", "party")``.
    """
    from apps.core.models import Party
    from apps.scm.models import LogisticsClient
    made = []
    for index in range(count):
        party = Party.objects.create(tenant=tenant, name=f"{prefix} Depositor {index:03d}",
                                     kind="organization")
        made.append(LogisticsClient.objects.create(
            tenant=tenant, party=party, code=f"{prefix}{index:03d}"[:8], status="prospect"))
    return made


#: Everything the four list pages and the two report pages must survive in a hand-edited query
#: string. Each pair is ``(url name, GET params)``; the assertion is 200, never a 500 (L11/L9).
_3PL_JUNK_QUERIES = [
    ("scm:logisticsclient_list", {"status": "zzz"}),
    ("scm:logisticsclient_list", {"billing_cycle": "zzz"}),
    ("scm:logisticsclient_list", {"space_model": "zzz"}),
    ("scm:logisticsclient_list", {"integration_mode": "zzz"}),
    ("scm:logisticsclient_list", {"page": "abc"}),
    ("scm:logisticsclient_list", {"page": "999"}),
    ("scm:logisticsclient_list", {"q": "'); DROP TABLE scm_logisticsclient;--"}),
    ("scm:clientratecard_list", {"client": "abc"}),
    ("scm:clientratecard_list", {"client": "²"}),
    ("scm:clientratecard_list", {"client": "99999999999999999999"}),
    ("scm:clientratecard_list", {"status": "zzz"}),
    ("scm:clientratecard_list", {"page": "abc"}),
    ("scm:clientbillingrun_list", {"client": "abc"}),
    ("scm:clientbillingrun_list", {"client": "99999999999999999999"}),
    ("scm:clientbillingrun_list", {"status": "zzz"}),
    ("scm:clientbillingrun_list", {"period_from": "lastweek"}),
    ("scm:clientbillingrun_list", {"period_to": "2026-13-45"}),
    ("scm:clientbillingrun_list", {"period_from": "", "period_to": "not-a-date"}),
    ("scm:clientbillingrun_list", {"page": "999"}),
    ("scm:clientsla_list", {"client": "abc"}),
    ("scm:clientsla_list", {"client": "²"}),
    ("scm:clientsla_list", {"metric": "zzz"}),
    ("scm:clientsla_list", {"status": "zzz"}),
    ("scm:clientsla_list", {"active": "abc"}),
    ("scm:clientsla_list", {"page": "abc"}),
    ("scm:client_inventory_report", {"client": "abc"}),
    ("scm:client_inventory_report", {"category": "abc"}),
    ("scm:client_inventory_report", {"location": "abc"}),
    ("scm:client_inventory_report", {"client": "99999999999999999999"}),
    ("scm:client_inventory_report", {"client": "²", "category": "³"}),
    ("scm:client_space_report", {"client": "abc"}),
    ("scm:client_space_report", {"space_model": "zzz"}),
    ("scm:client_space_report", {"client": "99999999999999999999"}),
]

#: Every 4.17 GET page that takes no pk — the anonymous-redirect sweep.
_3PL_ANON_PAGES = [
    "scm:logisticsclient_list", "scm:logisticsclient_create",
    "scm:clientratecard_list", "scm:clientratecard_create",
    "scm:clientbillingrun_list", "scm:clientbillingrun_create",
    "scm:clientsla_list", "scm:clientsla_create",
    "scm:client_inventory_report", "scm:client_space_report",
]

#: ``(url name, fixture name)`` for every POST-only route that takes a pk. A GET must be a 405 — a
#: link-prefetcher following one of these would be drafting invoices and deleting tariffs.
_3PL_POST_ONLY_ROUTES = [
    ("scm:logisticsclient_delete", "tpl_client_shared_a"),
    ("scm:clientratecard_delete", "tpl_rate_card_a"),
    ("scm:clientratecard_activate", "tpl_rate_card_a"),
    ("scm:clientratecard_supersede", "tpl_active_card_a"),
    ("scm:clientratecardline_delete", "tpl_rate_card_line_a"),
    ("scm:clientbillingrun_delete", "tpl_billing_run_a"),
    ("scm:clientbillingrun_calculate", "tpl_billing_run_a"),
    ("scm:clientbillingrun_approve", "tpl_billing_run_a"),
    ("scm:clientbillingrun_draft_invoice", "tpl_billing_run_a"),
    ("scm:clientbillingrun_void", "tpl_billing_run_a"),
    ("scm:clientbillingrunline_delete", "tpl_billing_run_line_a"),
    ("scm:clientsla_delete", "tpl_sla_a"),
    ("scm:clientsla_recompute", "tpl_sla_a"),
]

#: ``(url name, fixture name)`` for every pk route a tenant-A session must 404 on when handed a
#: tenant-B pk. GET routes only — the POST ones are driven separately so the object can be re-read.
_3PL_CROSS_TENANT_GETS = [
    ("scm:logisticsclient_detail", "tpl_client_b"),
    ("scm:logisticsclient_edit", "tpl_client_b"),
    ("scm:clientratecard_detail", "tpl_rate_card_b"),
    ("scm:clientratecard_edit", "tpl_rate_card_b"),
    ("scm:clientratecardline_create", "tpl_rate_card_b"),
    ("scm:clientbillingrun_detail", "tpl_billing_run_b"),
    ("scm:clientbillingrun_edit", "tpl_billing_run_b"),
    ("scm:clientbillingrunline_create", "tpl_billing_run_b"),
    ("scm:clientsla_detail", "tpl_sla_b"),
    ("scm:clientsla_edit", "tpl_sla_b"),
]

#: Every POST verb, driven with a tenant-B pk from a tenant-A ADMIN session (admin, so the two
#: ``@tenant_admin_required`` verbs reach their ``get_object_or_404`` rather than stopping at 403).
_3PL_CROSS_TENANT_POSTS = [
    ("scm:logisticsclient_delete", "tpl_client_b"),
    ("scm:clientratecard_delete", "tpl_rate_card_b"),
    ("scm:clientratecard_activate", "tpl_rate_card_b"),
    ("scm:clientratecard_supersede", "tpl_rate_card_b"),
    ("scm:clientbillingrun_delete", "tpl_billing_run_b"),
    ("scm:clientbillingrun_calculate", "tpl_billing_run_b"),
    ("scm:clientbillingrun_approve", "tpl_billing_run_b"),
    ("scm:clientbillingrun_draft_invoice", "tpl_billing_run_b"),
    ("scm:clientbillingrun_void", "tpl_billing_run_b"),
    ("scm:clientsla_delete", "tpl_sla_b"),
    ("scm:clientsla_recompute", "tpl_sla_b"),
]


# =================================================================================================
# Local fixtures — the two TENANT-LESS children on the tenant_b side, which conftest does not build
# =================================================================================================
@pytest.fixture
def _3pl_rate_card_line_b(db, tpl_rate_card_b):
    """A rate line on tenant_b's tariff. It carries NO tenant column of its own."""
    from apps.scm.models import ClientRateCardLine
    return ClientRateCardLine.objects.create(
        rate_card=tpl_rate_card_b, charge_category="receiving", charge_basis="per_receipt",
        description="Globex inbound handling", rate=Decimal("9.0000"), period="")


@pytest.fixture
def _3pl_run_line_b(db, tpl_billing_run_b):
    """A manual charge on tenant_b's run. Reached only through ``run__tenant``."""
    from apps.scm.models import ClientBillingRunLine
    return ClientBillingRunLine.objects.create(
        run=tpl_billing_run_b, charge_category="value_added", charge_basis="per_hour",
        description="Globex rework labour", quantity=Decimal("1.0000"), rate=Decimal("40.0000"),
        is_manual=True)


# =================================================================================================
# Anonymous -> login
# =================================================================================================
class Test3plAnonymous:
    @pytest.mark.parametrize("url_name", _3PL_ANON_PAGES)
    def test_3pl_anonymous_page_redirects_to_login(self, url_name):
        response = Client().get(reverse(url_name))
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_3pl_anonymous_detail_redirects_to_login(self, tpl_client_a):
        response = Client().get(reverse("scm:logisticsclient_detail", args=[tpl_client_a.pk]))
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    @pytest.mark.parametrize("url_name", ["scm:clientbillingrun_calculate",
                                          "scm:clientbillingrun_approve",
                                          "scm:clientbillingrun_void"])
    def test_3pl_anonymous_verb_redirects_and_changes_nothing(self, url_name, tpl_billing_run_a):
        response = Client().post(reverse(url_name, args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "draft"

    def test_3pl_anonymous_create_post_saves_nothing(self, tpl_customer_a2):
        from apps.scm.models import LogisticsClient
        before = LogisticsClient.objects.count()
        response = Client().post(reverse("scm:logisticsclient_create"),
                                 _3pl_client_payload(tpl_customer_a2))
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        assert LogisticsClient.objects.count() == before

    def test_3pl_anonymous_recompute_all_redirects(self, tpl_sla_a):
        response = Client().post(reverse("scm:clientsla_recompute_all"))
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.measurement_window_end is None


# =================================================================================================
# @tenant_admin_required — approve and draft_invoice move money (L27)
# =================================================================================================
class Test3plAdminGates:
    def test_3pl_approve_is_refused_for_a_plain_member(self, member_client, tpl_billing_run_a):
        tpl_billing_run_a.calculate()
        response = member_client.post(
            reverse("scm:clientbillingrun_approve", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 403
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "calculated"
        assert tpl_billing_run_a.approved_by_id is None

    def test_3pl_approve_succeeds_for_a_tenant_admin(self, client_a, admin_user, tpl_billing_run_a):
        tpl_billing_run_a.calculate()
        response = client_a.post(
            reverse("scm:clientbillingrun_approve", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "approved"
        assert tpl_billing_run_a.approved_by_id == admin_user.pk

    def test_3pl_draft_invoice_is_refused_for_a_plain_member(self, member_client, admin_user,
                                                             tpl_billing_run_a):
        from apps.accounting.models import Invoice
        tpl_billing_run_a.calculate()
        tpl_billing_run_a.approve(user=admin_user)
        response = member_client.post(
            reverse("scm:clientbillingrun_draft_invoice", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 403
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "approved"
        assert tpl_billing_run_a.invoice_id is None
        assert Invoice.objects.count() == 0

    def test_3pl_draft_invoice_succeeds_for_a_tenant_admin(self, client_a, admin_user,
                                                           tpl_billing_run_a):
        from apps.accounting.models import Invoice
        tpl_billing_run_a.calculate()
        tpl_billing_run_a.approve(user=admin_user)
        response = client_a.post(
            reverse("scm:clientbillingrun_draft_invoice", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "invoiced"
        invoice = Invoice.objects.get(pk=tpl_billing_run_a.invoice_id)
        assert invoice.status == "draft"
        assert invoice.subtotal == tpl_billing_run_a.total

    def test_3pl_member_can_calculate(self, member_client, tpl_billing_run_a):
        """``calculate`` is plain ``@login_required`` — the admin gate must not have spread."""
        response = member_client.post(
            reverse("scm:clientbillingrun_calculate", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "calculated"
        assert tpl_billing_run_a.total == Decimal("500.00")

    def test_3pl_member_can_void(self, member_client, tpl_billing_run_a):
        response = member_client.post(
            reverse("scm:clientbillingrun_void", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "void"

    def test_3pl_member_can_activate_a_rate_card(self, member_client, tpl_rate_card_a):
        response = member_client.post(
            reverse("scm:clientratecard_activate", args=[tpl_rate_card_a.pk]))
        assert response.status_code == 302
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.status == "active"

    def test_3pl_member_can_recompute_one_sla(self, member_client, tpl_sla_a):
        response = member_client.post(reverse("scm:clientsla_recompute", args=[tpl_sla_a.pk]))
        assert response.status_code == 302
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.measurement_window_end is not None

    def test_3pl_member_can_create_a_client(self, member_client, tpl_customer_a2, tenant_a):
        from apps.scm.models import LogisticsClient
        response = member_client.post(reverse("scm:logisticsclient_create"),
                                      _3pl_client_payload(tpl_customer_a2))
        assert response.status_code == 302
        assert LogisticsClient.objects.filter(tenant=tenant_a, code="NEWCO").exists()


# =================================================================================================
# CSRF
# =================================================================================================
class Test3plCsrf:
    def test_3pl_csrf_is_enforced_on_a_verb_post(self, admin_user, tpl_billing_run_a):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(
            reverse("scm:clientbillingrun_calculate", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 403
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "draft"

    def test_3pl_csrf_is_enforced_on_a_create_post(self, admin_user, tpl_customer_a2):
        from apps.scm.models import LogisticsClient
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        before = LogisticsClient.objects.count()
        response = strict.post(reverse("scm:logisticsclient_create"),
                               _3pl_client_payload(tpl_customer_a2))
        assert response.status_code == 403
        assert LogisticsClient.objects.count() == before

    def test_3pl_csrf_is_enforced_on_a_delete_post(self, admin_user, tpl_client_shared_a):
        from apps.scm.models import LogisticsClient
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(
            reverse("scm:logisticsclient_delete", args=[tpl_client_shared_a.pk]))
        assert response.status_code == 403
        assert LogisticsClient.objects.filter(pk=tpl_client_shared_a.pk).exists()

    def test_3pl_a_token_carrying_post_is_accepted(self, admin_user, tpl_billing_run_a):
        """The POSITIVE half: CSRF enforcement must refuse a forgery, not the feature (L44)."""
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        page = strict.get(reverse("scm:clientbillingrun_detail", args=[tpl_billing_run_a.pk]))
        assert page.status_code == 200
        token = strict.cookies["csrftoken"].value
        response = strict.post(
            reverse("scm:clientbillingrun_calculate", args=[tpl_billing_run_a.pk]),
            {"csrfmiddlewaretoken": token})
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "calculated"


# =================================================================================================
# Multi-tenant isolation
# =================================================================================================
class Test3plCrossTenantIsolation:
    @pytest.mark.parametrize("url_name,fixture_name", _3PL_CROSS_TENANT_GETS)
    def test_3pl_foreign_pk_on_a_get_route_is_404(self, request, client_a, url_name, fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 404

    @pytest.mark.parametrize("url_name,fixture_name", _3PL_CROSS_TENANT_POSTS)
    def test_3pl_foreign_pk_on_a_post_route_is_404(self, request, client_a, url_name, fixture_name):
        obj = request.getfixturevalue(fixture_name)
        response = client_a.post(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 404
        # The row is untouched — a 404 that had already deleted or moved something would be worse
        # than a 200.
        assert type(obj).objects.filter(pk=obj.pk).exists()

    def test_3pl_foreign_rate_card_line_edit_is_404(self, client_a, _3pl_rate_card_line_b):
        """The child carries NO tenant column — it is resolved through ``rate_card__tenant``."""
        url = reverse("scm:clientratecardline_edit", args=[_3pl_rate_card_line_b.pk])
        assert client_a.get(url).status_code == 404
        assert client_a.post(url, _3pl_rate_line_payload(description="hijacked")).status_code == 404
        _3pl_rate_card_line_b.refresh_from_db()
        assert _3pl_rate_card_line_b.description == "Globex inbound handling"

    def test_3pl_foreign_rate_card_line_delete_is_404(self, client_a, _3pl_rate_card_line_b):
        from apps.scm.models import ClientRateCardLine
        response = client_a.post(
            reverse("scm:clientratecardline_delete", args=[_3pl_rate_card_line_b.pk]))
        assert response.status_code == 404
        assert ClientRateCardLine.objects.filter(pk=_3pl_rate_card_line_b.pk).exists()

    def test_3pl_foreign_run_line_edit_is_404(self, client_a, _3pl_run_line_b):
        """Resolved through ``run__tenant`` — a bare pk lookup here would be a silent foreign write."""
        url = reverse("scm:clientbillingrunline_edit", args=[_3pl_run_line_b.pk])
        assert client_a.get(url).status_code == 404
        assert client_a.post(url, _3pl_run_line_payload(rate="999.0000")).status_code == 404
        _3pl_run_line_b.refresh_from_db()
        assert _3pl_run_line_b.rate == Decimal("40.0000")

    def test_3pl_foreign_run_line_delete_is_404(self, client_a, _3pl_run_line_b):
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_delete", args=[_3pl_run_line_b.pk]))
        assert response.status_code == 404
        assert ClientBillingRunLine.objects.filter(pk=_3pl_run_line_b.pk).exists()

    def test_3pl_own_child_line_routes_still_resolve(self, client_a, tpl_rate_card_line_a,
                                                     tpl_billing_run_line_a):
        """The POSITIVE half of the two child-scoping tests (L44)."""
        assert client_a.get(reverse("scm:clientratecardline_edit",
                                    args=[tpl_rate_card_line_a.pk])).status_code == 200
        assert client_a.get(reverse("scm:clientbillingrunline_edit",
                                    args=[tpl_billing_run_line_a.pk])).status_code == 200

    def test_3pl_client_list_excludes_the_other_tenant(self, client_a, tpl_client_a, tpl_client_b):
        response = client_a.get(reverse("scm:logisticsclient_list"))
        assert response.status_code == 200
        pks = {obj.pk for obj in response.context["object_list"]}
        assert tpl_client_a.pk in pks
        assert tpl_client_b.pk not in pks
        assert b"GLOBEX" not in response.content

    def test_3pl_rate_card_list_excludes_the_other_tenant(self, client_a, tpl_rate_card_a,
                                                          tpl_rate_card_b):
        response = client_a.get(reverse("scm:clientratecard_list"))
        pks = {obj.pk for obj in response.context["object_list"]}
        assert tpl_rate_card_a.pk in pks
        assert tpl_rate_card_b.pk not in pks

    def test_3pl_billing_run_list_excludes_the_other_tenant(self, client_a, tpl_billing_run_a,
                                                            tpl_billing_run_b):
        response = client_a.get(reverse("scm:clientbillingrun_list"))
        pks = {obj.pk for obj in response.context["object_list"]}
        assert tpl_billing_run_a.pk in pks
        assert tpl_billing_run_b.pk not in pks
        # NOT asserted on the NUMBER: the CBR- sequence is per tenant, so both workspaces' first
        # run is CBR-00001. The other tenant's CLIENT CODE is the string that can only be theirs.
        assert b"GLOBEX" not in response.content

    def test_3pl_sla_list_excludes_the_other_tenant(self, client_a, tpl_sla_a, tpl_sla_b):
        response = client_a.get(reverse("scm:clientsla_list"))
        pks = {obj.pk for obj in response.context["object_list"]}
        assert tpl_sla_a.pk in pks
        assert tpl_sla_b.pk not in pks

    def test_3pl_list_stats_count_only_this_workspace(self, client_a, tpl_client_a, tpl_client_b):
        response = client_a.get(reverse("scm:logisticsclient_list"))
        assert response.context["stats"]["total"] == 1

    def test_3pl_inventory_report_excludes_the_other_tenant(self, client_a, tpl_client_a,
                                                            tpl_client_b, tpl_stock_move_a):
        response = client_a.get(reverse("scm:client_inventory_report"))
        assert response.status_code == 200
        listed = {row["client"].pk for row in response.context["rows"]}
        assert tpl_client_a.pk in listed
        assert tpl_client_b.pk not in listed

    def test_3pl_space_report_excludes_the_other_tenant(self, client_a, tpl_client_a, tpl_client_b,
                                                        tpl_dedicated_location_a):
        response = client_a.get(reverse("scm:client_space_report"))
        assert response.status_code == 200
        listed = {row["client"].pk for row in response.context["rows"]}
        assert tpl_client_a.pk in listed
        assert tpl_client_b.pk not in listed

    def test_3pl_report_client_filter_cannot_reach_a_foreign_pk(self, client_a, tpl_client_a,
                                                                tpl_client_b):
        """A valid-looking pk from another workspace narrows to NOTHING, never to that row."""
        response = client_a.get(reverse("scm:client_inventory_report"),
                                {"client": str(tpl_client_b.pk)})
        assert response.status_code == 200
        assert response.context["rows"] == []
        assert response.context["selected_client"] is None

    def test_3pl_tenant_b_list_shows_only_its_own_rows(self, client_b, tpl_client_a, tpl_client_b):
        """The B-side of the register: not merely "no A rows" but "exactly B's row"."""
        response = client_b.get(reverse("scm:logisticsclient_list"))
        assert response.status_code == 200
        assert [obj.pk for obj in response.context["object_list"]] == [tpl_client_b.pk]

    def test_3pl_isolation_runs_both_ways(self, client_b, tpl_client_a, tpl_billing_run_a):
        """Tenant B must not reach tenant A either — the guard is symmetric, not A-shaped."""
        assert client_b.get(
            reverse("scm:logisticsclient_detail", args=[tpl_client_a.pk])).status_code == 404
        assert client_b.post(
            reverse("scm:clientbillingrun_calculate", args=[tpl_billing_run_a.pk])).status_code == 404
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "draft"

    def test_3pl_recompute_all_sweeps_only_this_workspace(self, client_a, tpl_sla_a, tpl_sla_b):
        response = client_a.post(reverse("scm:clientsla_recompute_all"))
        assert response.status_code == 302
        tpl_sla_a.refresh_from_db()
        tpl_sla_b.refresh_from_db()
        assert tpl_sla_a.measurement_window_end is not None
        assert tpl_sla_b.measurement_window_end is None


# =================================================================================================
# Crafted POSTs — a foreign pk in an FK field
# =================================================================================================
class Test3plCraftedForeignKeys:
    def test_3pl_rate_card_create_refuses_a_foreign_client(self, client_a, tpl_client_b):
        from apps.scm.models import ClientRateCard
        before = ClientRateCard.objects.count()
        response = client_a.post(reverse("scm:clientratecard_create"),
                                 _3pl_rate_card_payload(tpl_client_b))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientRateCard.objects.count() == before

    def test_3pl_rate_card_create_accepts_its_own_client(self, client_a, tenant_a, tpl_client_a):
        from apps.scm.models import ClientRateCard
        response = client_a.post(reverse("scm:clientratecard_create"),
                                 _3pl_rate_card_payload(tpl_client_a))
        assert response.status_code == 302
        card = ClientRateCard.objects.get(tenant=tenant_a, name="Crafted tariff")
        assert card.client_id == tpl_client_a.pk
        assert card.number.startswith("TAR-")

    def test_3pl_billing_run_create_refuses_a_foreign_client(self, client_a, tpl_client_b,
                                                             tpl_rate_card_b, tpl_period):
        from apps.scm.models import ClientBillingRun
        before = ClientBillingRun.objects.count()
        start, end = tpl_period
        response = client_a.post(
            reverse("scm:clientbillingrun_create"),
            _3pl_run_payload(tpl_client_b, tpl_rate_card_b, start, end))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientBillingRun.objects.count() == before

    def test_3pl_billing_run_create_refuses_a_foreign_rate_card(self, client_a, tpl_client_a,
                                                                tpl_rate_card_b, tpl_period):
        """The mixed case: OUR client, THEIR tariff — the one whose output looks plausible."""
        from apps.scm.models import ClientBillingRun
        before = ClientBillingRun.objects.count()
        start, end = tpl_period
        response = client_a.post(
            reverse("scm:clientbillingrun_create"),
            _3pl_run_payload(tpl_client_a, tpl_rate_card_b, start, end))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientBillingRun.objects.count() == before

    def test_3pl_billing_run_create_accepts_its_own_pair(self, client_a, tenant_a, tpl_client_a,
                                                         tpl_active_card_a):
        from apps.scm.models import ClientBillingRun
        today = timezone.localdate()
        start = today.replace(day=1)
        response = client_a.post(
            reverse("scm:clientbillingrun_create"),
            _3pl_run_payload(tpl_client_a, tpl_active_card_a, start, today))
        assert response.status_code == 302
        run = ClientBillingRun.objects.get(tenant=tenant_a, period_start=start, period_end=today)
        assert run.status == "draft"
        assert run.number.startswith("CBR-")

    def test_3pl_sla_create_refuses_a_foreign_client(self, client_a, tpl_client_b):
        from apps.scm.models import ClientSLA
        before = ClientSLA.objects.count()
        response = client_a.post(reverse("scm:clientsla_create"), _3pl_sla_payload(tpl_client_b))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientSLA.objects.count() == before

    def test_3pl_sla_create_refuses_a_foreign_scope_location(self, client_a, tpl_client_a,
                                                             location_b):
        from apps.scm.models import ClientSLA
        before = ClientSLA.objects.count()
        response = client_a.post(
            reverse("scm:clientsla_create"),
            _3pl_sla_payload(tpl_client_a, metric="inventory_accuracy_pct",
                             target_value="99.00", scope_location=str(location_b.pk)))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientSLA.objects.count() == before

    def test_3pl_sla_create_accepts_its_own_client(self, client_a, tenant_a, tpl_client_a):
        from apps.scm.models import ClientSLA
        response = client_a.post(reverse("scm:clientsla_create"), _3pl_sla_payload(tpl_client_a))
        assert response.status_code == 302
        sla = ClientSLA.objects.get(tenant=tenant_a, metric="order_accuracy_pct")
        assert sla.client_id == tpl_client_a.pk
        assert sla.status == "no_data"

    def test_3pl_client_create_refuses_a_foreign_parent(self, client_a, tpl_customer_a2,
                                                        tpl_client_b):
        from apps.scm.models import LogisticsClient
        before = LogisticsClient.objects.count()
        response = client_a.post(
            reverse("scm:logisticsclient_create"),
            _3pl_client_payload(tpl_customer_a2, parent_client=str(tpl_client_b.pk)))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert LogisticsClient.objects.count() == before

    def test_3pl_client_create_refuses_a_foreign_gl_account(self, client_a, tpl_customer_a2,
                                                            gl_expense_b):
        from apps.scm.models import LogisticsClient
        before = LogisticsClient.objects.count()
        response = client_a.post(
            reverse("scm:logisticsclient_create"),
            _3pl_client_payload(tpl_customer_a2, default_revenue_account=str(gl_expense_b.pk)))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert LogisticsClient.objects.count() == before

    def test_3pl_client_create_accepts_its_own_workspace_rows(self, client_a, tenant_a,
                                                              tpl_customer_a2, tpl_client_a,
                                                              gl_expense):
        from apps.scm.models import LogisticsClient
        response = client_a.post(
            reverse("scm:logisticsclient_create"),
            _3pl_client_payload(tpl_customer_a2, parent_client=str(tpl_client_a.pk),
                                default_revenue_account=str(gl_expense.pk)))
        assert response.status_code == 302
        obj = LogisticsClient.objects.get(tenant=tenant_a, code="NEWCO")
        assert obj.parent_client_id == tpl_client_a.pk
        assert obj.number.startswith("3PL-")

    def test_3pl_rate_line_create_refuses_a_foreign_location(self, client_a, tpl_rate_card_a,
                                                             location_b):
        from apps.scm.models import ClientRateCardLine
        before = ClientRateCardLine.objects.count()
        response = client_a.post(
            reverse("scm:clientratecardline_create", args=[tpl_rate_card_a.pk]),
            _3pl_rate_line_payload(applies_to_location=str(location_b.pk)))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientRateCardLine.objects.count() == before

    def test_3pl_rate_line_create_refuses_another_clients_bin(self, client_a, tpl_rate_card_a,
                                                              tpl_other_client_location_a):
        """SAME workspace, DIFFERENT depositor — pricing Acme against Shared's aisle is refused."""
        from apps.scm.models import ClientRateCardLine
        before = ClientRateCardLine.objects.count()
        response = client_a.post(
            reverse("scm:clientratecardline_create", args=[tpl_rate_card_a.pk]),
            _3pl_rate_line_payload(applies_to_location=str(tpl_other_client_location_a.pk)))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientRateCardLine.objects.count() == before

    def test_3pl_rate_line_create_accepts_its_own_clients_bin(self, client_a, tpl_rate_card_a,
                                                              tpl_dedicated_location_a):
        from apps.scm.models import ClientRateCardLine
        response = client_a.post(
            reverse("scm:clientratecardline_create", args=[tpl_rate_card_a.pk]),
            _3pl_rate_line_payload(applies_to_location=str(tpl_dedicated_location_a.pk)))
        assert response.status_code == 302
        line = ClientRateCardLine.objects.get(rate_card=tpl_rate_card_a,
                                              applies_to_location=tpl_dedicated_location_a)
        assert line.rate == Decimal("12.0000")

    def test_3pl_rate_line_create_ignores_a_posted_parent(self, client_a, tpl_rate_card_a,
                                                          tpl_rate_card_b):
        """``rate_card`` is not a form field — the parent comes from the ROUTE, never the body."""
        from apps.scm.models import ClientRateCardLine
        response = client_a.post(
            reverse("scm:clientratecardline_create", args=[tpl_rate_card_a.pk]),
            _3pl_rate_line_payload(rate_card=str(tpl_rate_card_b.pk)))
        assert response.status_code == 302
        assert ClientRateCardLine.objects.filter(rate_card=tpl_rate_card_a).count() == 1
        assert not ClientRateCardLine.objects.filter(rate_card=tpl_rate_card_b).exists()

    def test_3pl_run_line_create_ignores_a_posted_parent(self, client_a, tpl_billing_run_a,
                                                         tpl_billing_run_b):
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload(run=str(tpl_billing_run_b.pk)))
        assert response.status_code == 302
        assert ClientBillingRunLine.objects.filter(run=tpl_billing_run_a).count() == 1
        assert not ClientBillingRunLine.objects.filter(run=tpl_billing_run_b).exists()

    def test_3pl_run_line_create_forces_is_manual(self, client_a, tpl_billing_run_a):
        """``is_manual`` is FORCED by the view — a posted False must not freeze a wrong figure."""
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload(is_manual="", rate_card_line="", amount="9999.99"))
        assert response.status_code == 302
        line = ClientBillingRunLine.objects.get(run=tpl_billing_run_a)
        assert line.is_manual is True
        assert line.rate_card_line_id is None
        # `amount` is editable=False and computed in save() — a posted figure is ignored.
        assert line.amount == Decimal("50.00")


# =================================================================================================
# Negative input — junk filters, pagination, and hand-typed decimals
# =================================================================================================
class Test3plNegativeInput:
    @pytest.mark.parametrize("url_name,params", _3PL_JUNK_QUERIES,
                             ids=[f"{name.split(':')[1]}-{'&'.join(params)}"
                                  for name, params in _3PL_JUNK_QUERIES])
    def test_3pl_junk_filter_param_is_200(self, client_a, tpl_client_a, url_name, params):
        assert client_a.get(reverse(url_name), params).status_code == 200

    def test_3pl_junk_client_filter_does_not_narrow_the_rate_card_list(self, client_a,
                                                                       tpl_rate_card_a):
        """L11 posture: a non-pk value SKIPS the filter rather than matching nothing (or 500ing)."""
        response = client_a.get(reverse("scm:clientratecard_list"), {"client": "abc"})
        assert tpl_rate_card_a.pk in {obj.pk for obj in response.context["object_list"]}

    def test_3pl_real_client_filter_narrows_the_rate_card_list(self, client_a, tpl_rate_card_a,
                                                               tpl_client_shared_a):
        """The POSITIVE half — the L11 guard must not have disabled the filter (L44)."""
        response = client_a.get(reverse("scm:clientratecard_list"),
                                {"client": str(tpl_client_shared_a.pk)})
        assert response.status_code == 200
        assert list(response.context["object_list"]) == []
        response = client_a.get(reverse("scm:clientratecard_list"),
                                {"client": str(tpl_rate_card_a.client_id)})
        assert tpl_rate_card_a.pk in {obj.pk for obj in response.context["object_list"]}

    def test_3pl_junk_period_bound_does_not_narrow_the_run_list(self, client_a, tpl_billing_run_a):
        response = client_a.get(reverse("scm:clientbillingrun_list"),
                                {"period_from": "lastweek", "period_to": "soon"})
        assert response.status_code == 200
        assert tpl_billing_run_a.pk in {obj.pk for obj in response.context["object_list"]}

    def test_3pl_real_period_bound_narrows_the_run_list(self, client_a, tpl_billing_run_a):
        """A run over LAST month is excluded by a ``period_from`` of the 1st of THIS month."""
        this_month = timezone.localdate().replace(day=1)
        response = client_a.get(reverse("scm:clientbillingrun_list"),
                                {"period_from": this_month.isoformat()})
        assert response.status_code == 200
        assert tpl_billing_run_a.pk not in {obj.pk for obj in response.context["object_list"]}
        response = client_a.get(reverse("scm:clientbillingrun_list"),
                                {"period_from": tpl_billing_run_a.period_start.isoformat()})
        assert tpl_billing_run_a.pk in {obj.pk for obj in response.context["object_list"]}

    # The 15-rows-then-a-real-page-2 walk is asserted once, in
    # ``test_3pl_views.py::Test3plLogisticsClientList`` (which owns list rendering and does it for
    # all four lists). What stays HERE is the boundary below: a page number past the end must clamp,
    # not 404 and not 500.

    def test_3pl_page_past_the_end_is_200(self, client_a, tenant_a):
        _3pl_bulk_clients(tenant_a, 21)
        response = client_a.get(reverse("scm:logisticsclient_list"), {"page": "999"})
        assert response.status_code == 200
        assert response.context["page_obj"].number == response.context["page_obj"].paginator.num_pages

    @pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "abc", "-1",
                                     "99999999999999999999.9999"])
    def test_3pl_run_line_refuses_a_poisoned_quantity(self, client_a, tpl_billing_run_a, bad):
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload(quantity=bad))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert not ClientBillingRunLine.objects.filter(run=tpl_billing_run_a).exists()
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.total == Decimal("0.00")

    @pytest.mark.parametrize("bad", ["NaN", "Infinity", "abc", "-25", "999999999999999.9999"])
    def test_3pl_run_line_refuses_a_poisoned_rate(self, client_a, tpl_billing_run_a, bad):
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload(rate=bad))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert not ClientBillingRunLine.objects.filter(run=tpl_billing_run_a).exists()

    def test_3pl_run_line_negative_refusal_names_the_credit_note(self, client_a,
                                                                 tpl_billing_run_a):
        """A negative would silently floor to 0.00 in ``save()``, so it is refused OUT LOUD."""
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload(quantity="-2.0000"))
        assert response.status_code == 200
        assert "credit note" in str(response.context["form"].errors["quantity"]).lower()

    def test_3pl_run_line_accepts_a_sane_figure(self, client_a, tpl_billing_run_a):
        """The POSITIVE half — the decimal guards must not have blocked the feature (L44)."""
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload())
        assert response.status_code == 302
        line = ClientBillingRunLine.objects.get(run=tpl_billing_run_a)
        assert line.amount == Decimal("50.00")
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.subtotal == Decimal("50.00")
        # The client's 500.00 monthly minimum then tops the run up — the charge landed, and the
        # floor is applied on TOP of it rather than instead of it.
        assert tpl_billing_run_a.minimum_adjustment == Decimal("450.00")
        assert tpl_billing_run_a.total == Decimal("500.00")

    @pytest.mark.parametrize("bad", ["NaN", "Infinity", "abc", "-3", "9999999999999999.9999"])
    def test_3pl_rate_line_refuses_a_poisoned_rate(self, client_a, tpl_rate_card_a, bad):
        from apps.scm.models import ClientRateCardLine
        response = client_a.post(
            reverse("scm:clientratecardline_create", args=[tpl_rate_card_a.pk]),
            _3pl_rate_line_payload(rate=bad))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert not ClientRateCardLine.objects.filter(rate_card=tpl_rate_card_a).exists()

    def test_3pl_rate_line_accepts_a_sane_rate(self, client_a, tpl_rate_card_a):
        from apps.scm.models import ClientRateCardLine
        response = client_a.post(
            reverse("scm:clientratecardline_create", args=[tpl_rate_card_a.pk]),
            _3pl_rate_line_payload(rate="12.5000"))
        assert response.status_code == 302
        assert ClientRateCardLine.objects.get(rate_card=tpl_rate_card_a).rate == Decimal("12.5000")

    @pytest.mark.parametrize("field,bad", [
        ("minimum_monthly_charge", "NaN"),
        ("minimum_monthly_charge", "Infinity"),
        ("minimum_monthly_charge", "-100.00"),
        ("minimum_monthly_charge", "999999999999999.00"),
        ("default_tax_rate_pct", "abc"),
        ("committed_sqft", "NaN"),
        ("billing_day", "abc"),
        ("notice_days", "-5"),
    ])
    def test_3pl_client_create_refuses_a_poisoned_number(self, client_a, tpl_customer_a2, field,
                                                         bad):
        from apps.scm.models import LogisticsClient
        before = LogisticsClient.objects.count()
        response = client_a.post(reverse("scm:logisticsclient_create"),
                                 _3pl_client_payload(tpl_customer_a2, **{field: bad}))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert LogisticsClient.objects.count() == before

    def test_3pl_client_create_refuses_an_over_range_commitment(self, client_a, tpl_customer_a2):
        """``MAX_COMMITTED_SQFT`` is a model ``clean()`` bound — a friendly error, never a 500."""
        from apps.scm.models import LogisticsClient
        before = LogisticsClient.objects.count()
        response = client_a.post(
            reverse("scm:logisticsclient_create"),
            _3pl_client_payload(tpl_customer_a2, space_model="dedicated",
                                committed_sqft="99999999.99"))
        assert response.status_code == 200
        assert "committed_sqft" in response.context["form"].errors
        assert LogisticsClient.objects.count() == before

    def test_3pl_client_create_accepts_a_sane_commitment(self, client_a, tenant_a,
                                                         tpl_customer_a2):
        from apps.scm.models import LogisticsClient
        response = client_a.post(
            reverse("scm:logisticsclient_create"),
            _3pl_client_payload(tpl_customer_a2, space_model="dedicated",
                                committed_sqft="1500.00", committed_pallet_positions="40",
                                minimum_monthly_charge="250.00"))
        assert response.status_code == 302
        obj = LogisticsClient.objects.get(tenant=tenant_a, code="NEWCO")
        assert obj.committed_sqft == Decimal("1500.00")

    @pytest.mark.parametrize("bad", ["NaN", "Infinity", "abc", "150.00"])
    def test_3pl_sla_create_refuses_a_poisoned_target(self, client_a, tpl_client_a, bad):
        """A pct target above 100 is refused by ``clean()`` alongside the unparseable ones."""
        from apps.scm.models import ClientSLA
        before = ClientSLA.objects.count()
        response = client_a.post(reverse("scm:clientsla_create"),
                                 _3pl_sla_payload(tpl_client_a, target_value=bad))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientSLA.objects.count() == before

    def test_3pl_sla_create_refuses_a_unit_the_registry_forbids(self, client_a, tpl_client_a):
        from apps.scm.models import ClientSLA
        before = ClientSLA.objects.count()
        response = client_a.post(reverse("scm:clientsla_create"),
                                 _3pl_sla_payload(tpl_client_a, unit="hours"))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientSLA.objects.count() == before

    def test_3pl_duplicate_client_code_is_a_form_error_not_a_500(self, client_a, tpl_client_a,
                                                                 tpl_customer_a2):
        """``unique_together`` on (tenant, code) — the mixin makes it a field error, not IntegrityError."""
        from apps.scm.models import LogisticsClient
        before = LogisticsClient.objects.count()
        response = client_a.post(reverse("scm:logisticsclient_create"),
                                 _3pl_client_payload(tpl_customer_a2, code=tpl_client_a.code))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert LogisticsClient.objects.count() == before

    def test_3pl_duplicate_billing_period_is_a_form_error_not_a_500(self, client_a, tpl_client_a,
                                                                    tpl_active_card_a,
                                                                    tpl_billing_run_a, tpl_period):
        from apps.scm.models import ClientBillingRun
        before = ClientBillingRun.objects.count()
        start, end = tpl_period
        response = client_a.post(
            reverse("scm:clientbillingrun_create"),
            _3pl_run_payload(tpl_client_a, tpl_active_card_a, start, end))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert ClientBillingRun.objects.count() == before


# =================================================================================================
# Absent prerequisites are REJECTED, not fallen through (L35)
# =================================================================================================
class Test3plLadderPrerequisites:
    def test_3pl_approve_refuses_an_uncalculated_run(self, client_a, tpl_billing_run_a):
        response = client_a.post(
            reverse("scm:clientbillingrun_approve", args=[tpl_billing_run_a.pk]), follow=True)
        assert response.status_code == 200
        assert any("calculated" in message for message in _3pl_messages(response))
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "draft"
        assert tpl_billing_run_a.approved_at is None

    def test_3pl_approve_accepts_a_calculated_run(self, client_a, tpl_billing_run_a):
        client_a.post(reverse("scm:clientbillingrun_calculate", args=[tpl_billing_run_a.pk]))
        response = client_a.post(
            reverse("scm:clientbillingrun_approve", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "approved"
        assert tpl_billing_run_a.approved_at is not None

    def test_3pl_draft_invoice_refuses_an_unapproved_run(self, client_a, tpl_billing_run_a):
        from apps.accounting.models import Invoice
        tpl_billing_run_a.calculate()
        response = client_a.post(
            reverse("scm:clientbillingrun_draft_invoice", args=[tpl_billing_run_a.pk]), follow=True)
        assert any("approve" in message for message in _3pl_messages(response))
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "calculated"
        assert Invoice.objects.count() == 0

    def test_3pl_draft_invoice_refuses_a_second_draft(self, client_a, admin_user,
                                                      tpl_billing_run_a):
        """Pressing Draft Invoice twice must not raise a second AR document — and must SAY why.

        The outcome (one invoice, still ``invoiced``) was always right; the sentence was not.
        ``draft_invoice`` checked ``status != "approved"`` before the already-invoiced guard, and a
        second press leaves the run at ``invoiced``, so the unreachable branch was the one that
        names the invoice: the user was told to approve a run that had already been invoiced. The
        guards were reordered (``ClientBillingRuns.py`` ``draft_invoice``) and the wording is
        asserted here so the order cannot drift back.
        """
        from apps.accounting.models import Invoice
        tpl_billing_run_a.calculate()
        tpl_billing_run_a.approve(user=admin_user)
        url = reverse("scm:clientbillingrun_draft_invoice", args=[tpl_billing_run_a.pk])
        assert client_a.post(url).status_code == 302
        response = client_a.post(url, follow=True)
        assert response.status_code == 200
        assert _3pl_messages(response), "a second draft attempt must say something, not pass silently"
        tpl_billing_run_a.refresh_from_db()
        assert any("already invoiced" in message for message in _3pl_messages(response)), (
            "the second press must name the invoice that already exists, not ask for an approval")
        # `_3pl_messages` lowercases, so the number has to be lowercased to be compared.
        assert tpl_billing_run_a.invoice.number.lower() in " ".join(_3pl_messages(response))
        assert Invoice.objects.count() == 1
        assert tpl_billing_run_a.status == "invoiced"

    def test_3pl_void_refuses_an_invoiced_run(self, client_a, admin_user, tpl_billing_run_a):
        tpl_billing_run_a.calculate()
        tpl_billing_run_a.approve(user=admin_user)
        tpl_billing_run_a.draft_invoice(user=admin_user)
        response = client_a.post(
            reverse("scm:clientbillingrun_void", args=[tpl_billing_run_a.pk]), follow=True)
        assert any("cannot be voided" in message for message in _3pl_messages(response))
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "invoiced"

    def test_3pl_void_accepts_a_draft_run(self, client_a, tpl_billing_run_a):
        response = client_a.post(reverse("scm:clientbillingrun_void", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "void"

    def test_3pl_calculate_refuses_a_voided_run(self, client_a, tpl_billing_run_a):
        tpl_billing_run_a.void()
        response = client_a.post(
            reverse("scm:clientbillingrun_calculate", args=[tpl_billing_run_a.pk]), follow=True)
        assert any("recalculated" in message for message in _3pl_messages(response))
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.status == "void"

    def test_3pl_run_edit_refuses_an_approved_run(self, client_a, admin_user, tpl_billing_run_a,
                                                  tpl_client_a, tpl_active_card_a, tpl_period):
        tpl_billing_run_a.calculate()
        tpl_billing_run_a.approve(user=admin_user)
        start, end = tpl_period
        response = client_a.post(
            reverse("scm:clientbillingrun_edit", args=[tpl_billing_run_a.pk]),
            _3pl_run_payload(tpl_client_a, tpl_active_card_a, start, end, notes="rewritten"),
            follow=True)
        assert any("can no longer be edited" in message for message in _3pl_messages(response))
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.notes != "rewritten"

    def test_3pl_run_edit_accepts_a_draft_run(self, client_a, tpl_billing_run_a, tpl_client_a,
                                              tpl_active_card_a, tpl_period):
        start, end = tpl_period
        response = client_a.post(
            reverse("scm:clientbillingrun_edit", args=[tpl_billing_run_a.pk]),
            _3pl_run_payload(tpl_client_a, tpl_active_card_a, start, end, notes="rewritten"))
        assert response.status_code == 302
        tpl_billing_run_a.refresh_from_db()
        assert tpl_billing_run_a.notes == "rewritten"

    def test_3pl_run_line_write_refuses_an_approved_run(self, client_a, admin_user,
                                                        tpl_billing_run_a,
                                                        tpl_billing_run_line_a):
        from apps.scm.models import ClientBillingRunLine
        tpl_billing_run_a.calculate()
        tpl_billing_run_a.approve(user=admin_user)
        create = client_a.post(
            reverse("scm:clientbillingrunline_create", args=[tpl_billing_run_a.pk]),
            _3pl_run_line_payload(description="sneaked in"), follow=True)
        assert any("no longer take new charges" in message for message in _3pl_messages(create))
        assert not ClientBillingRunLine.objects.filter(description="sneaked in").exists()

        delete = client_a.post(
            reverse("scm:clientbillingrunline_delete", args=[tpl_billing_run_line_a.pk]),
            follow=True)
        assert any("can no longer be deleted" in message for message in _3pl_messages(delete))
        assert ClientBillingRunLine.objects.filter(pk=tpl_billing_run_line_a.pk).exists()

    def test_3pl_run_line_delete_accepts_a_draft_run(self, client_a, tpl_billing_run_a,
                                                     tpl_billing_run_line_a):
        from apps.scm.models import ClientBillingRunLine
        response = client_a.post(
            reverse("scm:clientbillingrunline_delete", args=[tpl_billing_run_line_a.pk]))
        assert response.status_code == 302
        assert not ClientBillingRunLine.objects.filter(pk=tpl_billing_run_line_a.pk).exists()
        tpl_billing_run_a.refresh_from_db()
        # The run was re-totalled in the same transaction: the charge is gone from the subtotal, and
        # the 500.00 monthly minimum is all that is left standing.
        assert tpl_billing_run_a.subtotal == Decimal("0.00")
        assert tpl_billing_run_a.total == Decimal("500.00")

    def test_3pl_rate_card_edit_refuses_a_non_draft_card(self, client_a, tpl_active_card_a,
                                                         tpl_client_a):
        response = client_a.post(
            reverse("scm:clientratecard_edit", args=[tpl_active_card_a.pk]),
            _3pl_rate_card_payload(tpl_client_a, name="Rewritten", status="active"), follow=True)
        assert any("can no longer be changed" in message for message in _3pl_messages(response))
        tpl_active_card_a.refresh_from_db()
        assert tpl_active_card_a.name == "Live tariff"

    def test_3pl_rate_card_edit_accepts_a_draft_card(self, client_a, tpl_rate_card_a,
                                                     tpl_client_a):
        today = timezone.localdate()
        response = client_a.post(
            reverse("scm:clientratecard_edit", args=[tpl_rate_card_a.pk]),
            _3pl_rate_card_payload(tpl_client_a, name="Renamed draft",
                                   effective_from=(today + datetime.timedelta(days=1)).isoformat()))
        assert response.status_code == 302
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.name == "Renamed draft"

    def test_3pl_rate_line_write_refuses_a_frozen_card(self, client_a, tpl_active_card_a):
        from apps.scm.models import ClientRateCardLine
        before = ClientRateCardLine.objects.filter(rate_card=tpl_active_card_a).count()
        response = client_a.post(
            reverse("scm:clientratecardline_create", args=[tpl_active_card_a.pk]),
            _3pl_rate_line_payload(description="sneaked in"), follow=True)
        assert any("can no longer be changed" in message for message in _3pl_messages(response))
        assert ClientRateCardLine.objects.filter(rate_card=tpl_active_card_a).count() == before

    def test_3pl_rate_line_delete_refuses_a_frozen_card(self, client_a, tpl_active_card_a):
        from apps.scm.models import ClientRateCardLine
        line = ClientRateCardLine.objects.filter(rate_card=tpl_active_card_a).first()
        response = client_a.post(
            reverse("scm:clientratecardline_delete", args=[line.pk]), follow=True)
        assert any("can no longer be changed" in message for message in _3pl_messages(response))
        assert ClientRateCardLine.objects.filter(pk=line.pk).exists()

    def test_3pl_rate_line_delete_accepts_a_draft_card(self, client_a, tpl_rate_card_line_a):
        from apps.scm.models import ClientRateCardLine
        response = client_a.post(
            reverse("scm:clientratecardline_delete", args=[tpl_rate_card_line_a.pk]))
        assert response.status_code == 302
        assert not ClientRateCardLine.objects.filter(pk=tpl_rate_card_line_a.pk).exists()

    def test_3pl_activate_refuses_a_non_draft_card(self, client_a, tpl_active_card_a):
        response = client_a.post(
            reverse("scm:clientratecard_activate", args=[tpl_active_card_a.pk]), follow=True)
        assert any("cannot be activated" in message for message in _3pl_messages(response))
        tpl_active_card_a.refresh_from_db()
        assert tpl_active_card_a.status == "active"

    def test_3pl_activate_refuses_an_overlapping_card(self, client_a, tpl_active_card_a,
                                                      tpl_rate_card_a):
        """Two live tariffs over one day means the billing run has two prices for it."""
        today = timezone.localdate()
        tpl_rate_card_a.effective_from = today - datetime.timedelta(days=1)
        tpl_rate_card_a.save(update_fields=["effective_from"])
        response = client_a.post(
            reverse("scm:clientratecard_activate", args=[tpl_rate_card_a.pk]), follow=True)
        assert any("overlap" in message for message in _3pl_messages(response))
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.status == "draft"

    def test_3pl_activate_accepts_a_non_overlapping_draft(self, client_a, tpl_active_card_a,
                                                          tpl_rate_card_a):
        response = client_a.post(
            reverse("scm:clientratecard_activate", args=[tpl_rate_card_a.pk]))
        assert response.status_code == 302
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.status == "active"

    def test_3pl_supersede_refuses_a_draft_card(self, client_a, tpl_rate_card_a):
        response = client_a.post(
            reverse("scm:clientratecard_supersede", args=[tpl_rate_card_a.pk]), follow=True)
        assert any("cannot be superseded" in message for message in _3pl_messages(response))
        tpl_rate_card_a.refresh_from_db()
        assert tpl_rate_card_a.status == "draft"

    def test_3pl_supersede_accepts_an_active_card(self, client_a, tpl_active_card_a):
        response = client_a.post(
            reverse("scm:clientratecard_supersede", args=[tpl_active_card_a.pk]))
        assert response.status_code == 302
        tpl_active_card_a.refresh_from_db()
        assert tpl_active_card_a.status == "superseded"
        assert tpl_active_card_a.effective_to is not None

    def test_3pl_recompute_refuses_an_inactive_sla(self, client_a, tpl_sla_a):
        from apps.scm.models import ClientSLA
        ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(is_active=False)
        response = client_a.post(reverse("scm:clientsla_recompute", args=[tpl_sla_a.pk]),
                                 follow=True)
        assert any("not active" in message for message in _3pl_messages(response))
        tpl_sla_a.refresh_from_db()
        # No evidence was written — an inactive promise must not accrue a breach.
        assert tpl_sla_a.measurement_window_end is None
        assert tpl_sla_a.measurement_summary == ""
        assert tpl_sla_a.breach_count == 0

    def test_3pl_recompute_accepts_an_active_sla(self, client_a, tpl_sla_a):
        response = client_a.post(reverse("scm:clientsla_recompute", args=[tpl_sla_a.pk]))
        assert response.status_code == 302
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.measurement_window_end is not None
        # Nothing shipped in the window, so the honest answer is no_data — never a 0 that would
        # read as total failure on a higher-is-better metric.
        assert tpl_sla_a.status == "no_data"
        assert tpl_sla_a.last_measured_value is None

    def test_3pl_recompute_all_skips_inactive_promises(self, client_a, tpl_sla_a):
        from apps.scm.models import ClientSLA
        ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(is_active=False)
        response = client_a.post(reverse("scm:clientsla_recompute_all"))
        assert response.status_code == 302
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.measurement_window_end is None


# =================================================================================================
# Delete guards — a PROTECTed reference is a message, never a 500 and never a silent cascade
# =================================================================================================
class Test3plDeleteGuards:
    def test_3pl_client_delete_refuses_while_a_tariff_references_it(self, client_a, tpl_client_a,
                                                                    tpl_active_card_a):
        from apps.scm.models import LogisticsClient
        response = client_a.post(
            reverse("scm:logisticsclient_delete", args=[tpl_client_a.pk]), follow=True)
        assert response.status_code == 200
        assert any("cannot be deleted" in message for message in _3pl_messages(response))
        assert LogisticsClient.objects.filter(pk=tpl_client_a.pk).exists()

    def test_3pl_client_delete_accepts_an_unreferenced_client(self, client_a,
                                                              tpl_client_shared_a):
        from apps.scm.models import LogisticsClient
        response = client_a.post(
            reverse("scm:logisticsclient_delete", args=[tpl_client_shared_a.pk]))
        assert response.status_code == 302
        assert not LogisticsClient.objects.filter(pk=tpl_client_shared_a.pk).exists()

    def test_3pl_rate_card_delete_refuses_while_it_has_priced_a_bill(self, client_a,
                                                                     tpl_active_card_a,
                                                                     tpl_billing_run_a):
        from apps.scm.models import ClientRateCard
        response = client_a.post(
            reverse("scm:clientratecard_delete", args=[tpl_active_card_a.pk]), follow=True)
        assert any("can't be deleted" in message for message in _3pl_messages(response))
        assert ClientRateCard.objects.filter(pk=tpl_active_card_a.pk).exists()

    def test_3pl_rate_card_delete_accepts_an_unbilled_card(self, client_a, tpl_rate_card_a):
        from apps.scm.models import ClientRateCard
        response = client_a.post(reverse("scm:clientratecard_delete", args=[tpl_rate_card_a.pk]))
        assert response.status_code == 302
        assert not ClientRateCard.objects.filter(pk=tpl_rate_card_a.pk).exists()

    def test_3pl_run_delete_refuses_an_approved_run(self, client_a, admin_user,
                                                    tpl_billing_run_a):
        from apps.scm.models import ClientBillingRun
        tpl_billing_run_a.calculate()
        tpl_billing_run_a.approve(user=admin_user)
        response = client_a.post(
            reverse("scm:clientbillingrun_delete", args=[tpl_billing_run_a.pk]), follow=True)
        assert any("approved" in message for message in _3pl_messages(response))
        assert ClientBillingRun.objects.filter(pk=tpl_billing_run_a.pk).exists()

    def test_3pl_run_delete_accepts_a_draft_run(self, client_a, tpl_billing_run_a):
        from apps.scm.models import ClientBillingRun
        response = client_a.post(
            reverse("scm:clientbillingrun_delete", args=[tpl_billing_run_a.pk]))
        assert response.status_code == 302
        assert not ClientBillingRun.objects.filter(pk=tpl_billing_run_a.pk).exists()

    def test_3pl_sla_delete_removes_the_row(self, client_a, tpl_sla_a):
        from apps.scm.models import ClientSLA
        response = client_a.post(reverse("scm:clientsla_delete", args=[tpl_sla_a.pk]))
        assert response.status_code == 302
        assert not ClientSLA.objects.filter(pk=tpl_sla_a.pk).exists()


# =================================================================================================
# POST-only routes — a GET must be a 405, never a silent state change
# =================================================================================================
class Test3plPostOnlyRoutes:
    @pytest.mark.parametrize("url_name,fixture_name", _3PL_POST_ONLY_ROUTES,
                             ids=[name.split(":")[1] for name, _ in _3PL_POST_ONLY_ROUTES])
    def test_3pl_get_on_a_post_only_route_is_405(self, request, client_a, url_name, fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 405

    def test_3pl_get_on_recompute_all_is_405(self, client_a, tpl_sla_a):
        response = client_a.get(reverse("scm:clientsla_recompute_all"))
        assert response.status_code == 405
        tpl_sla_a.refresh_from_db()
        assert tpl_sla_a.measurement_window_end is None

    def test_3pl_get_on_delete_does_not_delete(self, client_a, tpl_client_shared_a):
        from apps.scm.models import LogisticsClient
        client_a.get(reverse("scm:logisticsclient_delete", args=[tpl_client_shared_a.pk]))
        assert LogisticsClient.objects.filter(pk=tpl_client_shared_a.pk).exists()


# =================================================================================================
# Query budget — the six derived LogisticsClient methods must never run per row
# =================================================================================================
class Test3plQueryBudget:
    def test_3pl_client_list_query_count_does_not_scale_with_rows(self, client_a, tenant_a,
                                                                  django_assert_max_num_queries):
        """15 rows x six per-row methods would be 90 extra queries (the 4.13 asset_list finding)."""
        _3pl_bulk_clients(tenant_a, 21)
        with django_assert_max_num_queries(15):
            response = client_a.get(reverse("scm:logisticsclient_list"))
        assert response.status_code == 200
        assert len(response.context["object_list"]) == 15

    def test_3pl_rate_card_list_query_count_is_flat(self, client_a, tenant_a, tpl_client_a,
                                                    django_assert_max_num_queries):
        """``ClientRateCard.__str__`` walks ``client.code`` — the join must be select_related."""
        from apps.scm.models import ClientRateCard
        today = timezone.localdate()
        for index in range(18):
            ClientRateCard.objects.create(
                tenant=tenant_a, client=tpl_client_a, name=f"Tariff {index:02d}", version=1,
                status="draft", effective_from=today - datetime.timedelta(days=index + 1))
        with django_assert_max_num_queries(15):
            response = client_a.get(reverse("scm:clientratecard_list"))
        assert response.status_code == 200
        assert len(response.context["object_list"]) == 15
