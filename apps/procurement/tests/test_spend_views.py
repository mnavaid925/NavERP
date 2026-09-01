"""Procurement 6.14 Spend Analytics & Reporting - view / CRUD integration flows.

Everything here goes through the real URLconf and the real templates: the three registers
(classification rules, maverick findings, saved reports), the six computed pages (spend
dashboard, category spend, export page + CSV, classification workbench, maverick board), and
every verb POST (preview, disposition, scan, run, snapshot, favourite, both exports and the
three deletes).

Lane discipline followed here:

* a context key is never asserted "present" alone - it is asserted POPULATED (L41);
* every reference date derives from ``timezone.localdate()``, never ``date.today()`` (L16);
* the page-2 cases build enough rows to actually cross the page size (15 for the three
  ``crud_list`` registers, 25 for the workbench's grouped rows) - a page-2 guard is invisible at
  fixture size (L9);
* junk FK params, junk enum params and junk dates render 200 with the filter skipped, never a
  500 (L11);
* the money POST surfaces are probed with NaN / Infinity / negative / over-``max_digits``, and a
  verb POST missing its prerequisite is REJECTED rather than falling through to a disposition
  (L35);
* every register is wrapped in ``django_assert_max_num_queries`` - each one renders chained
  ``__str__`` FK hops.

Every test is ``test_spend_*`` and every module-level helper / fixture ``_spend_*`` so the next
sub-module appending nearby cannot shadow them.
"""
import datetime
from decimal import Decimal

import pytest

from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.procurement.models import (
    MaverickSpendFinding,
    SpendClassificationRule,
    SpendReport,
    SpendReportSnapshot,
    SupplierInvoice,
    SupplierInvoiceLine,
)

pytestmark = pytest.mark.django_db


# ================================================================== helpers

def _spend_today():
    """The SAME basis every 6.14 window uses - never ``date.today()`` (L16)."""
    return timezone.localdate()


def _spend_templates(response):
    return [t.name for t in response.templates if t.name]


def _spend_messages(response):
    """Works on a 302 too - the storage hangs off the request, not the context."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _spend_pks(response):
    return [obj.pk for obj in response.context["object_list"]]


#: Junk values every int-FK filter on every 6.14 page must SKIP rather than 500 on (L11). The
#: superscript two is the sharp one: ``isdigit()`` is True for it but ``int()`` refuses it.
_SPEND_JUNK_INTS = ["abc", "999999999999999999999", "²", "-1", "1.5", "0"]

#: Junk money every hand-typed decimal surface must turn into a FIELD error, never a 500 (L35).
_SPEND_JUNK_MONEY = ["NaN", "Infinity", "-Infinity", "-1", "not-a-number",
                     "99999999999999999999.99"]


def _spend_rule_body(**overrides):
    """A complete, valid ``SpendClassificationRuleForm`` POST body."""
    body = {
        "name": "Cobalt -> Facilities", "match_type": "vendor", "vendor": "",
        "gl_account": "", "org_unit": "", "keyword": "", "invoice_type": "",
        "category": "", "priority": "20", "applies_to": "both", "is_active": "on",
        "notes": "Written from the workbench.",
    }
    body.update(overrides)
    return body


def _spend_finding_body(**overrides):
    """A complete, valid ``MaverickSpendFindingForm`` POST body."""
    body = {
        "reason": "non_preferred_vendor", "severity": "medium",
        "supplier_invoice": "", "invoice_line": "", "purchase_order": "",
        "vendor": "", "category": "", "org_unit": "", "contract": "", "catalog_item": "",
        "document_date": _spend_today().isoformat(),
        "amount": "125.00", "benchmark_amount": "", "is_addressable": "on",
        "detail": "Bought away from the preferred supplier.",
    }
    body.update(overrides)
    return body


def _spend_report_body(**overrides):
    """A complete, valid ``SpendReportForm`` POST body."""
    body = {
        "name": "Suppliers this quarter", "description": "Built by the view test.",
        "basis": "invoiced", "measure": "net_spend", "dimension_1": "supplier",
        "dimension_2": "none", "date_range": "last_90", "date_from": "", "date_to": "",
        "vendor": "", "category": "", "org_unit": "", "gl_account": "", "min_amount": "",
        "chart_type": "bar", "top_n": "20", "is_shared": "on",
    }
    body.update(overrides)
    return body


def _spend_invoice_with_line(tenant, vendor, *, number, price="100.00", description="Cleaning",
                             sku="SVC-1", currency=None, status="approved", item=None,
                             gl_account=None):
    """One RECOGNISED invoice + one line, dated today so it sits inside every default window.

    Used wherever a page needs spend the fixtures do not already provide - an extra supplier for
    the Pareto league, an unclassified line for the workbench, a page-2 population.
    """
    invoice = SupplierInvoice.objects.create(
        tenant=tenant, vendor=vendor, invoice_number=number, invoice_date=_spend_today(),
        status=status, invoice_type="standard", currency=currency)
    return SupplierInvoiceLine.objects.create(
        invoice=invoice, description=description, sku_hint=sku, item=item,
        gl_account=gl_account, quantity=Decimal("1"), unit_price=Decimal(price))


def _spend_supplier(tenant, name):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="supplier", status="active")
    return party


# ================================================================== bulk fixtures (page 2, L9)

@pytest.fixture
def _spend_bulk_rules(db, tenant_a, spend_category_a):
    """20 extra rules - the three fixtures plus these cross the 15-row register page size."""
    return [SpendClassificationRule.objects.create(
        tenant=tenant_a, name=f"Bulk rule {i:02d}", match_type="keyword",
        keyword=f"bulk-{i:02d}", category=spend_category_a, priority=100 + i)
        for i in range(20)]


@pytest.fixture
def _spend_bulk_findings(db, tenant_a, spend_vendor_a):
    """18 pointer-less findings. ``dedupe_key`` falls back to a random token with no source
    pointer, so ``unique_together (tenant, dedupe_key)`` is satisfied without varying the
    reason."""
    return [MaverickSpendFinding.objects.create(
        tenant=tenant_a, vendor=spend_vendor_a, reason="no_contract", severity="low",
        document_date=_spend_today(), amount=Decimal("10.00"),
        detail=f"Bulk finding {i:02d}") for i in range(18)]


@pytest.fixture
def _spend_bulk_reports(db, tenant_a, admin_user):
    return [SpendReport.objects.create(
        tenant=tenant_a, name=f"Bulk report {i:02d}", owner=admin_user, is_shared=True)
        for i in range(18)]


# =================================================================================================
# SpendClassificationRule register
# =================================================================================================

def test_spend_rule_list_renders_contract_context(client_a, spend_rule_vendor_a,
                                                  spend_rule_keyword_a, spend_rule_inactive_a,
                                                  spend_invoice_line_a, org_unit_a):
    resp = client_a.get(reverse("procurement:spendrule_list"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/spendrule/list.html" in _spend_templates(resp)
    assert set(_spend_pks(resp)) == {spend_rule_vendor_a.pk, spend_rule_keyword_a.pk,
                                     spend_rule_inactive_a.pk}
    ctx = resp.context
    assert ctx["q"] == ""
    assert dict(ctx["match_type_choices"])["vendor"] == "Supplier"
    assert dict(ctx["applies_to_choices"])["both"] == "Invoiced + Committed"
    assert [c.pk for c in ctx["categories"]], "category dropdown must be populated"
    assert [v.pk for v in ctx["vendors"]], "supplier dropdown must be populated"
    assert [g.pk for g in ctx["gl_accounts"]], "GL dropdown must be populated"
    assert [o.pk for o in ctx["org_units"]] == [org_unit_a.pk]
    assert ctx["stats"] == {"total": 3, "active": 2, "inactive": 1,
                            "matched_value": Decimal("250.00")}


def test_spend_rule_list_search_narrows_rows_but_not_stats(client_a, spend_rule_vendor_a,
                                                           spend_rule_keyword_a,
                                                           spend_rule_inactive_a):
    resp = client_a.get(reverse("procurement:spendrule_list"), {"q": "Toner"})

    assert resp.status_code == 200
    assert _spend_pks(resp) == [spend_rule_keyword_a.pk]
    assert resp.context["q"] == "Toner"
    # The stat strip describes the WORKSPACE, so a search must not move it.
    assert resp.context["stats"]["total"] == 3


def test_spend_rule_list_filters_each_narrow(client_a, spend_rule_vendor_a, spend_rule_keyword_a,
                                             spend_rule_inactive_a, spend_category_a):
    url = reverse("procurement:spendrule_list")

    by_type = client_a.get(url, {"match_type": "keyword"})
    assert _spend_pks(by_type) == [spend_rule_keyword_a.pk]

    by_category = client_a.get(url, {"category": str(spend_category_a.pk)})
    assert set(_spend_pks(by_category)) == {spend_rule_vendor_a.pk, spend_rule_inactive_a.pk}

    active = client_a.get(url, {"is_active": "True"})
    assert set(_spend_pks(active)) == {spend_rule_vendor_a.pk, spend_rule_keyword_a.pk}

    inactive = client_a.get(url, {"is_active": "False"})
    assert _spend_pks(inactive) == [spend_rule_inactive_a.pk]


@pytest.mark.parametrize("junk", _SPEND_JUNK_INTS)
def test_spend_rule_list_junk_category_param_renders_200(client_a, spend_rule_vendor_a, junk):
    resp = client_a.get(reverse("procurement:spendrule_list"), {"category": junk})
    assert resp.status_code == 200


def test_spend_rule_list_junk_enum_and_boolean_params_render_200(client_a, spend_rule_vendor_a):
    resp = client_a.get(reverse("procurement:spendrule_list"),
                        {"match_type": "not-a-type", "is_active": "abc"})
    assert resp.status_code == 200
    # A bogus BooleanField value is swallowed, so the row is still listed.
    assert _spend_pks(resp) == [spend_rule_vendor_a.pk]


def test_spend_rule_list_page_two_and_past_the_end(client_a, spend_rule_vendor_a,
                                                   _spend_bulk_rules):
    url = reverse("procurement:spendrule_list")

    page_one = client_a.get(url)
    assert len(_spend_pks(page_one)) == 15
    assert page_one.context["page_obj"].paginator.num_pages == 2

    page_two = client_a.get(url, {"page": "2"})
    assert page_two.status_code == 200
    assert len(_spend_pks(page_two)) == 6
    assert set(_spend_pks(page_one)).isdisjoint(_spend_pks(page_two))

    past_end = client_a.get(url, {"page": "999"})
    assert past_end.status_code == 200
    assert past_end.context["page_obj"].number == 2

    junk_page = client_a.get(url, {"page": "abc"})
    assert junk_page.status_code == 200
    assert junk_page.context["page_obj"].number == 1


def test_spend_rule_list_query_budget(client_a, _spend_bulk_rules, spend_rule_vendor_a,
                                      spend_invoice_line_a, django_assert_max_num_queries):
    """15 rows whose ``__str__`` walks ``category`` and whose columns walk three more FKs."""
    with django_assert_max_num_queries(18):
        resp = client_a.get(reverse("procurement:spendrule_list"))
    assert resp.status_code == 200
    assert len(_spend_pks(resp)) == 15


def test_spend_rule_list_never_shows_another_tenants_rows(client_a, spend_rule_vendor_a,
                                                          spend_rule_b):
    resp = client_a.get(reverse("procurement:spendrule_list"))
    assert _spend_pks(resp) == [spend_rule_vendor_a.pk]
    assert resp.context["stats"]["total"] == 1


# =================================================================================================
# SpendClassificationRule create / detail / edit / delete / preview
# =================================================================================================

def test_spend_rule_create_get_renders_form_contract(client_a, spend_category_a):
    resp = client_a.get(reverse("procurement:spendrule_create"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/spendrule/form.html" in _spend_templates(resp)
    assert resp.context["is_edit"] is False
    assert resp.context["title"] == "New classification rule"
    assert resp.context["submit_label"] == "Create rule"
    assert resp.context["cancel_url"] == reverse("procurement:spendrule_list")
    fields = resp.context["form"].fields
    assert "category" in fields
    # Derived usage stamps are never form fields (L22).
    assert "match_count" not in fields and "last_matched_at" not in fields
    assert "tenant" not in fields


def test_spend_rule_create_post_saves_with_the_request_tenant(client_a, tenant_a,
                                                              spend_vendor_a, spend_category_a):
    resp = client_a.post(reverse("procurement:spendrule_create"), _spend_rule_body(
        vendor=str(spend_vendor_a.pk), category=str(spend_category_a.pk)))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendrule_list")
    rule = SpendClassificationRule.objects.get(name="Cobalt -> Facilities")
    assert rule.tenant_id == tenant_a.id
    assert rule.vendor_id == spend_vendor_a.pk
    assert rule.category_id == spend_category_a.pk
    assert rule.match_count == 0 and rule.last_matched_at is None


def test_spend_rule_create_honours_a_workbench_prefill(client_a, spend_vendor_a,
                                                       spend_category_a):
    resp = client_a.get(reverse("procurement:spendrule_create"),
                        {"match_type": "vendor", "vendor": str(spend_vendor_a.pk),
                         "keyword": "paper"})

    assert resp.status_code == 200
    initial = resp.context["form"].initial
    assert initial["vendor"] == spend_vendor_a.pk
    assert initial["match_type"] == "vendor"
    assert initial["keyword"] == "paper"


def test_spend_rule_create_junk_prefill_is_skipped_not_500(client_a, spend_category_a,
                                                           spend_vendor_b):
    resp = client_a.get(reverse("procurement:spendrule_create"),
                        {"vendor": "abc", "gl_account": "999999999999999999999",
                         "org_unit": "-1", "match_type": "nonsense", "invoice_type": "zzz",
                         "keyword": "k" * 400})

    assert resp.status_code == 200
    initial = resp.context["form"].initial
    assert "vendor" not in initial and "gl_account" not in initial
    assert "org_unit" not in initial and "match_type" not in initial
    assert "invoice_type" not in initial
    assert len(initial["keyword"]) == 120

    # A crafted prefill pointing at ANOTHER workspace's supplier is dropped too.
    crafted = client_a.get(reverse("procurement:spendrule_create"),
                           {"vendor": str(spend_vendor_b.pk)})
    assert crafted.status_code == 200
    assert "vendor" not in crafted.context["form"].initial


def test_spend_rule_create_rejects_a_crafted_cross_tenant_category(client_a, spend_category_b,
                                                                   spend_category_a):
    body = _spend_rule_body(match_type="keyword", keyword="glue",
                            category=str(spend_category_b.pk))
    resp = client_a.post(reverse("procurement:spendrule_create"), body)

    assert resp.status_code == 200
    assert "category" in resp.context["form"].errors
    assert not SpendClassificationRule.objects.filter(name="Cobalt -> Facilities").exists()


def test_spend_rule_detail_runs_the_rule_against_real_spend(client_a, spend_rule_vendor_a,
                                                            spend_invoice_line_a):
    resp = client_a.get(reverse("procurement:spendrule_detail", args=[spend_rule_vendor_a.pk]))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/spendrule/detail.html" in _spend_templates(resp)
    ctx = resp.context
    assert ctx["obj"].pk == spend_rule_vendor_a.pk
    assert ctx["rule"].pk == spend_rule_vendor_a.pk
    assert ctx["preview"]["count"] == 1
    assert ctx["preview"]["value"] == Decimal("250.00")
    assert ctx["preview"]["start"] < ctx["preview"]["end"]
    assert ctx["category"].pk == spend_rule_vendor_a.category_id
    assert ctx["can_delete"] is True
    match = ctx["recent_matches"][0]
    assert match["amount"] == Decimal("250.00")
    assert match["date"] == _spend_today()
    assert match["document_url"] == reverse(
        "procurement:supplierinvoice_detail", args=[spend_invoice_line_a.invoice_id])
    assert ctx["stats"] == {"match_count": 0, "last_matched_at": None,
                            "preview_count": 1, "preview_value": Decimal("250.00")}


def test_spend_rule_detail_of_another_tenant_is_404(client_a, spend_rule_b):
    resp = client_a.get(reverse("procurement:spendrule_detail", args=[spend_rule_b.pk]))
    assert resp.status_code == 404


def test_spend_rule_edit_get_and_post(client_a, spend_rule_vendor_a, spend_vendor_a,
                                      spend_category_other_a):
    url = reverse("procurement:spendrule_edit", args=[spend_rule_vendor_a.pk])

    page = client_a.get(url)
    assert page.status_code == 200
    assert page.context["is_edit"] is True
    assert page.context["obj"].pk == spend_rule_vendor_a.pk
    assert page.context["title"] == "Edit rule"

    resp = client_a.post(url, _spend_rule_body(
        name="Meridian -> Facilities", vendor=str(spend_vendor_a.pk),
        category=str(spend_category_other_a.pk), priority="5"))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendrule_detail",
                                       args=[spend_rule_vendor_a.pk])
    spend_rule_vendor_a.refresh_from_db()
    assert spend_rule_vendor_a.name == "Meridian -> Facilities"
    assert spend_rule_vendor_a.category_id == spend_category_other_a.pk
    assert spend_rule_vendor_a.priority == 5


def test_spend_rule_edit_of_another_tenant_is_404(client_a, spend_rule_b):
    url = reverse("procurement:spendrule_edit", args=[spend_rule_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, _spend_rule_body()).status_code == 404


def test_spend_rule_delete_is_post_only(client_a, spend_rule_vendor_a):
    url = reverse("procurement:spendrule_delete", args=[spend_rule_vendor_a.pk])

    getter = client_a.get(url)
    assert getter.status_code == 405
    assert SpendClassificationRule.objects.filter(pk=spend_rule_vendor_a.pk).exists()

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendrule_list")
    assert not SpendClassificationRule.objects.filter(pk=spend_rule_vendor_a.pk).exists()


def test_spend_rule_delete_of_another_tenant_is_404(client_a, spend_rule_b):
    resp = client_a.post(reverse("procurement:spendrule_delete", args=[spend_rule_b.pk]))
    assert resp.status_code == 404
    assert SpendClassificationRule.objects.filter(pk=spend_rule_b.pk).exists()


def test_spend_rule_preview_is_post_only_and_stamps_usage(client_a, spend_rule_vendor_a,
                                                          spend_invoice_line_a):
    url = reverse("procurement:spendrule_preview", args=[spend_rule_vendor_a.pk])

    assert client_a.get(url).status_code == 405
    spend_rule_vendor_a.refresh_from_db()
    assert spend_rule_vendor_a.last_matched_at is None

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendrule_detail",
                                       args=[spend_rule_vendor_a.pk])
    spend_rule_vendor_a.refresh_from_db()
    assert spend_rule_vendor_a.match_count == 1
    assert spend_rule_vendor_a.last_matched_at is not None
    assert any("Preview run: 1 line(s) worth 250.00" in m for m in _spend_messages(resp))


def test_spend_rule_preview_of_another_tenant_is_404(client_a, spend_rule_b):
    resp = client_a.post(reverse("procurement:spendrule_preview", args=[spend_rule_b.pk]))
    assert resp.status_code == 404
    spend_rule_b.refresh_from_db()
    assert spend_rule_b.match_count == 0


# =================================================================================================
# MaverickSpendFinding register
# =================================================================================================

def test_spend_finding_list_renders_contract_context(client_a, spend_finding_open_a,
                                                     spend_finding_ack_a,
                                                     spend_finding_leakage_a,
                                                     spend_finding_dismissed_a, org_unit_a):
    resp = client_a.get(reverse("procurement:maverickfinding_list"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/maverickfinding/list.html" in _spend_templates(resp)
    assert set(_spend_pks(resp)) == {spend_finding_open_a.pk, spend_finding_ack_a.pk,
                                     spend_finding_leakage_a.pk, spend_finding_dismissed_a.pk}
    ctx = resp.context
    assert dict(ctx["reason_choices"])["no_contract"] == "No active contract"
    assert dict(ctx["status_choices"])["open"] == "Open"
    assert dict(ctx["severity_choices"])["high"] == "High"
    assert [v.pk for v in ctx["vendors"]], "supplier dropdown must be populated"
    assert [c.pk for c in ctx["categories"]], "category dropdown must be populated"
    assert [o.pk for o in ctx["org_units"]] == [org_unit_a.pk]
    assert ctx["is_admin"] is True
    stats = ctx["stats"]
    # open + acknowledged + leakage are live; the dismissed one is not work any more.
    assert stats["open"] == 3
    assert stats["high"] == 1
    assert stats["value_at_risk"] == Decimal("750.00")
    assert stats["leakage"] == Decimal("50.00")


def test_spend_finding_list_search_matches_number_and_vendor(client_a, spend_finding_open_a,
                                                             spend_finding_dismissed_a):
    url = reverse("procurement:maverickfinding_list")

    by_number = client_a.get(url, {"q": spend_finding_open_a.number})
    assert _spend_pks(by_number) == [spend_finding_open_a.pk]

    by_vendor = client_a.get(url, {"q": "Meridian"})
    assert set(_spend_pks(by_vendor)) == {spend_finding_open_a.pk, spend_finding_dismissed_a.pk}

    by_invoice = client_a.get(url, {"q": "SUP-4400"})
    assert _spend_pks(by_invoice) == [spend_finding_open_a.pk]


def test_spend_finding_list_filters_each_narrow(client_a, tenant_a, spend_vendor_a,
                                                spend_vendor_other_a, spend_finding_open_a,
                                                spend_finding_leakage_a,
                                                spend_finding_dismissed_a, spend_category_a,
                                                org_unit_a):
    non_addressable = MaverickSpendFinding.objects.create(
        tenant=tenant_a, vendor=spend_vendor_other_a, reason="split_purchase",
        document_date=_spend_today(), amount=Decimal("40.00"), is_addressable=False,
        detail="Statutory settlement.")
    url = reverse("procurement:maverickfinding_list")

    assert _spend_pks(client_a.get(url, {"reason": "price_above_contract"})) == [
        spend_finding_leakage_a.pk]
    assert _spend_pks(client_a.get(url, {"status": "dismissed"})) == [
        spend_finding_dismissed_a.pk]
    assert _spend_pks(client_a.get(url, {"severity": "high"})) == [spend_finding_leakage_a.pk]
    assert _spend_pks(client_a.get(url, {"vendor": str(spend_vendor_other_a.pk)})) == [
        non_addressable.pk]
    assert _spend_pks(client_a.get(url, {"category": str(spend_category_a.pk)})) == [
        spend_finding_open_a.pk]
    assert _spend_pks(client_a.get(url, {"org_unit": str(org_unit_a.pk)})) == [
        spend_finding_open_a.pk]
    assert _spend_pks(client_a.get(url, {"addressable": "False"})) == [non_addressable.pk]


@pytest.mark.parametrize("param", ["vendor", "category", "org_unit"])
def test_spend_finding_list_junk_fk_params_render_200(client_a, spend_finding_open_a, param):
    for junk in _SPEND_JUNK_INTS:
        resp = client_a.get(reverse("procurement:maverickfinding_list"), {param: junk})
        assert resp.status_code == 200, f"{param}={junk} must not 500"


def test_spend_finding_list_junk_enum_params_render_200(client_a, spend_finding_open_a):
    """A hand-edited enum is junk, not a narrowing request, so it is IGNORED — the register still
    shows its rows.

    This asserted ``== []`` when the suite was written, which encoded the bug rather than the
    contract: ``.filter(reason="nope")`` neither raises nor narrows, so a value anyone can type
    into the address bar silently emptied the page. The rule register (``spendrule_list``) already
    ignores its unrecognised ``match_type``; both registers in this sub-module now agree.
    """
    resp = client_a.get(reverse("procurement:maverickfinding_list"),
                        {"reason": "nope", "status": "??", "severity": "x",
                         "addressable": "maybe"})
    assert resp.status_code == 200
    assert _spend_pks(resp) == [spend_finding_open_a.pk]


def test_spend_finding_list_valid_enum_still_narrows(client_a, spend_finding_open_a):
    """The junk guard must not disarm the real filter: a VALID enum still narrows."""
    url = reverse("procurement:maverickfinding_list")
    assert _spend_pks(client_a.get(url, {"status": spend_finding_open_a.status})) == [
        spend_finding_open_a.pk]
    other = next(v for v, _ in MaverickSpendFinding.STATUS_CHOICES
                 if v != spend_finding_open_a.status)
    assert _spend_pks(client_a.get(url, {"status": other})) == []


def test_spend_finding_list_page_two_and_past_the_end(client_a, _spend_bulk_findings,
                                                      spend_finding_open_a):
    url = reverse("procurement:maverickfinding_list")

    page_one = client_a.get(url)
    assert len(_spend_pks(page_one)) == 15
    assert page_one.context["page_obj"].paginator.num_pages == 2

    page_two = client_a.get(url, {"page": "2"})
    assert page_two.status_code == 200
    assert len(_spend_pks(page_two)) == 4

    past_end = client_a.get(url, {"page": "12345"})
    assert past_end.status_code == 200
    assert past_end.context["page_obj"].number == 2


def test_spend_finding_list_query_budget(client_a, _spend_bulk_findings, spend_finding_open_a,
                                         spend_finding_leakage_a,
                                         django_assert_max_num_queries):
    """15 rows, each rendering supplier / category / department / source document."""
    with django_assert_max_num_queries(18):
        resp = client_a.get(reverse("procurement:maverickfinding_list"))
    assert resp.status_code == 200
    assert len(_spend_pks(resp)) == 15


def test_spend_finding_list_never_shows_another_tenants_rows(client_a, spend_finding_open_a,
                                                             spend_finding_b):
    resp = client_a.get(reverse("procurement:maverickfinding_list"))
    assert _spend_pks(resp) == [spend_finding_open_a.pk]
    assert resp.context["stats"]["open"] == 1


# =================================================================================================
# MaverickSpendFinding create / detail / edit / delete / disposition
# =================================================================================================

def test_spend_finding_create_get_renders_form_contract(client_a, spend_invoice_a):
    resp = client_a.get(reverse("procurement:maverickfinding_create"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/maverickfinding/form.html" in _spend_templates(resp)
    assert resp.context["is_edit"] is False
    assert resp.context["title"] == "Raise a maverick-spend finding"
    assert resp.context["submit_label"] == "Raise finding"
    assert resp.context["cancel_url"] == reverse("procurement:maverickfinding_list")
    fields = resp.context["form"].fields
    for excluded in ("tenant", "number", "status", "dedupe_key", "leakage_amount",
                     "detected_at", "resolution_note", "resolved_by", "resolved_at"):
        assert excluded not in fields, f"{excluded} must not be a form field"


def test_spend_finding_create_post_saves_with_the_request_tenant(client_a, tenant_a,
                                                                 spend_vendor_a,
                                                                 spend_invoice_a,
                                                                 spend_category_a):
    resp = client_a.post(reverse("procurement:maverickfinding_create"), _spend_finding_body(
        vendor=str(spend_vendor_a.pk), supplier_invoice=str(spend_invoice_a.pk),
        category=str(spend_category_a.pk), amount="250.00", benchmark_amount="200.00"))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:maverickfinding_list")
    finding = MaverickSpendFinding.objects.get(reason="non_preferred_vendor")
    assert finding.tenant_id == tenant_a.id
    assert finding.status == "open"
    assert finding.number.startswith("MSF-")
    # leakage is DERIVED in save(), never posted (L29).
    assert finding.leakage_amount == Decimal("50.00")


@pytest.mark.parametrize("amount", _SPEND_JUNK_MONEY)
def test_spend_finding_create_rejects_junk_money_without_500(client_a, spend_vendor_a,
                                                             spend_invoice_a, amount):
    resp = client_a.post(reverse("procurement:maverickfinding_create"), _spend_finding_body(
        vendor=str(spend_vendor_a.pk), supplier_invoice=str(spend_invoice_a.pk),
        amount=amount))

    assert resp.status_code == 200
    assert "amount" in resp.context["form"].errors
    assert not MaverickSpendFinding.objects.filter(reason="non_preferred_vendor").exists()


def test_spend_finding_create_without_a_source_document_is_rejected(client_a, spend_vendor_a):
    """L35: the absent prerequisite is REFUSED, never allowed to fall through."""
    resp = client_a.post(reverse("procurement:maverickfinding_create"),
                         _spend_finding_body(vendor=str(spend_vendor_a.pk)))

    assert resp.status_code == 200
    assert "supplier_invoice" in resp.context["form"].errors
    assert MaverickSpendFinding.objects.count() == 0


def test_spend_finding_create_rejects_a_crafted_cross_tenant_vendor(client_a, spend_vendor_b,
                                                                    spend_invoice_a):
    resp = client_a.post(reverse("procurement:maverickfinding_create"), _spend_finding_body(
        vendor=str(spend_vendor_b.pk), supplier_invoice=str(spend_invoice_a.pk)))

    assert resp.status_code == 200
    assert "vendor" in resp.context["form"].errors
    assert MaverickSpendFinding.objects.count() == 0


def test_spend_finding_detail_context(client_a, spend_finding_leakage_a, spend_catalog_item_a):
    resp = client_a.get(reverse("procurement:maverickfinding_detail",
                                args=[spend_finding_leakage_a.pk]))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/maverickfinding/detail.html" in _spend_templates(resp)
    ctx = resp.context
    assert ctx["obj"].pk == spend_finding_leakage_a.pk
    assert ctx["finding"].pk == spend_finding_leakage_a.pk
    assert ctx["supplier_invoice"] is not None
    assert ctx["invoice_line"] is not None
    assert ctx["contract"] is not None
    assert ctx["catalog_item"].pk == spend_catalog_item_a.pk
    assert [a.pk for a in ctx["alternatives"]] == [spend_catalog_item_a.pk]
    assert ctx["benchmark"] == {"expected": Decimal("200.00"), "actual": Decimal("250.00"),
                                "variance_pct": Decimal("25.00")}
    assert [a["action"] for a in ctx["allowed_actions"]] == ["acknowledge", "justify",
                                                             "remediate", "dismiss"]
    assert ctx["is_resolved"] is False
    assert ctx["severity_css"] == "badge-red"
    assert ctx["status_css"] == "badge-red"
    assert ctx["is_admin"] is True
    assert ctx["disposition_url"] == reverse("procurement:maverickfinding_disposition",
                                             args=[spend_finding_leakage_a.pk])


def test_spend_finding_detail_of_a_resolved_row_offers_no_actions(client_a,
                                                                  spend_finding_dismissed_a):
    resp = client_a.get(reverse("procurement:maverickfinding_detail",
                                args=[spend_finding_dismissed_a.pk]))
    assert resp.status_code == 200
    assert resp.context["is_resolved"] is True
    assert resp.context["allowed_actions"] == []


def test_spend_finding_detail_of_another_tenant_is_404(client_a, spend_finding_b):
    resp = client_a.get(reverse("procurement:maverickfinding_detail", args=[spend_finding_b.pk]))
    assert resp.status_code == 404


def test_spend_finding_edit_amends_an_open_finding(client_a, spend_finding_open_a,
                                                   spend_vendor_a, spend_invoice_a):
    url = reverse("procurement:maverickfinding_edit", args=[spend_finding_open_a.pk])

    page = client_a.get(url)
    assert page.status_code == 200
    assert page.context["is_edit"] is True
    assert page.context["obj"].pk == spend_finding_open_a.pk
    assert page.context["title"] == "Edit finding"

    resp = client_a.post(url, _spend_finding_body(
        reason="no_contract", vendor=str(spend_vendor_a.pk),
        supplier_invoice=str(spend_invoice_a.pk), amount="311.00",
        detail="Re-checked against the contract register."))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:maverickfinding_detail",
                                       args=[spend_finding_open_a.pk])
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.amount == Decimal("311.00")
    assert spend_finding_open_a.status == "open"


def test_spend_finding_edit_of_a_resolved_row_is_refused(client_a, spend_finding_dismissed_a,
                                                         spend_vendor_a, spend_po_a):
    url = reverse("procurement:maverickfinding_edit", args=[spend_finding_dismissed_a.pk])
    detail = reverse("procurement:maverickfinding_detail", args=[spend_finding_dismissed_a.pk])

    getter = client_a.get(url)
    assert getter.status_code == 302 and getter["Location"] == detail
    assert any("only an open finding can be edited" in m for m in _spend_messages(getter))

    poster = client_a.post(url, _spend_finding_body(
        vendor=str(spend_vendor_a.pk), purchase_order=str(spend_po_a.pk), amount="1.00"))
    assert poster.status_code == 302 and poster["Location"] == detail
    spend_finding_dismissed_a.refresh_from_db()
    assert spend_finding_dismissed_a.amount == Decimal("240.00")


def test_spend_finding_edit_of_another_tenant_is_404(client_a, spend_finding_b):
    url = reverse("procurement:maverickfinding_edit", args=[spend_finding_b.pk])
    assert client_a.get(url).status_code == 404


def test_spend_finding_delete_is_post_only(client_a, spend_finding_open_a):
    url = reverse("procurement:maverickfinding_delete", args=[spend_finding_open_a.pk])

    assert client_a.get(url).status_code == 405
    assert MaverickSpendFinding.objects.filter(pk=spend_finding_open_a.pk).exists()

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:maverickfinding_list")
    assert not MaverickSpendFinding.objects.filter(pk=spend_finding_open_a.pk).exists()


def test_spend_finding_delete_of_a_resolved_row_is_refused(client_a, spend_finding_dismissed_a):
    resp = client_a.post(reverse("procurement:maverickfinding_delete",
                                 args=[spend_finding_dismissed_a.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:maverickfinding_detail",
                                       args=[spend_finding_dismissed_a.pk])
    assert MaverickSpendFinding.objects.filter(pk=spend_finding_dismissed_a.pk).exists()
    assert any("cannot be deleted" in m for m in _spend_messages(resp))


def test_spend_finding_delete_of_another_tenant_is_404(client_a, spend_finding_b):
    resp = client_a.post(reverse("procurement:maverickfinding_delete", args=[spend_finding_b.pk]))
    assert resp.status_code == 404
    assert MaverickSpendFinding.objects.filter(pk=spend_finding_b.pk).exists()


def test_spend_finding_disposition_acknowledges_then_remediates(client_a, admin_user,
                                                                spend_finding_open_a):
    url = reverse("procurement:maverickfinding_disposition", args=[spend_finding_open_a.pk])
    detail = reverse("procurement:maverickfinding_detail", args=[spend_finding_open_a.pk])

    assert client_a.get(url).status_code == 405

    ack = client_a.post(url, {"action": "acknowledge"})
    assert ack.status_code == 302 and ack["Location"] == detail
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "acknowledged"

    done = client_a.post(url, {"action": "remediate",
                               "resolution_note": "Moved onto the framework contract."})
    assert done.status_code == 302
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "remediated"
    assert spend_finding_open_a.resolution_note == "Moved onto the framework contract."
    assert spend_finding_open_a.resolved_by_id == admin_user.pk
    assert spend_finding_open_a.resolved_at is not None


def test_spend_finding_disposition_without_a_note_is_refused_not_approved(client_a,
                                                                          spend_finding_open_a):
    """L35: a missing prerequisite must be REJECTED, never fall through to a disposition."""
    resp = client_a.post(
        reverse("procurement:maverickfinding_disposition", args=[spend_finding_open_a.pk]),
        {"action": "justify", "resolution_note": "   "})

    assert resp.status_code == 302
    assert any("A note is required to justify a finding." in m for m in _spend_messages(resp))
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "open"
    assert spend_finding_open_a.resolved_at is None


def test_spend_finding_disposition_rejects_a_bogus_action(client_a, spend_finding_open_a):
    resp = client_a.post(
        reverse("procurement:maverickfinding_disposition", args=[spend_finding_open_a.pk]),
        {"action": "delete-everything", "resolution_note": "hi"})

    assert resp.status_code == 302
    assert any("Choose what to do with this finding." in m for m in _spend_messages(resp))
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "open"


def test_spend_finding_disposition_of_a_terminal_row_is_refused(client_a,
                                                                spend_finding_dismissed_a):
    resp = client_a.post(
        reverse("procurement:maverickfinding_disposition", args=[spend_finding_dismissed_a.pk]),
        {"action": "remediate", "resolution_note": "Try again."})

    assert resp.status_code == 302
    assert any("cannot be remediated" in m for m in _spend_messages(resp))
    spend_finding_dismissed_a.refresh_from_db()
    assert spend_finding_dismissed_a.status == "dismissed"


def test_spend_finding_disposition_of_another_tenant_is_404(client_a, spend_finding_b):
    resp = client_a.post(
        reverse("procurement:maverickfinding_disposition", args=[spend_finding_b.pk]),
        {"action": "acknowledge"})
    assert resp.status_code == 404
    spend_finding_b.refresh_from_db()
    assert spend_finding_b.status == "open"


def test_spend_finding_disposition_is_admin_only(member_client, spend_finding_open_a):
    resp = member_client.post(
        reverse("procurement:maverickfinding_disposition", args=[spend_finding_open_a.pk]),
        {"action": "acknowledge"})
    assert resp.status_code == 403
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "open"


# =================================================================================================
# SpendReport register
# =================================================================================================

def test_spend_report_list_renders_contract_context(client_a, spend_report_a,
                                                    spend_report_favorite_a, spend_snapshot_a):
    resp = client_a.get(reverse("procurement:spendreport_list"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/spendreport/list.html" in _spend_templates(resp)
    assert set(_spend_pks(resp)) == {spend_report_a.pk, spend_report_favorite_a.pk}
    ctx = resp.context
    assert dict(ctx["measure_choices"])["net_spend"] == "Net spend"
    assert dict(ctx["basis_choices"])["invoiced"].startswith("Invoiced")
    assert dict(ctx["dimension_choices"])["supplier"] == "Supplier"
    assert dict(ctx["chart_type_choices"])["bar"] == "Bar"
    assert dict(ctx["date_range_choices"])["last_90"] == "Last 90 days"
    assert ctx["stats"] == {"total": 2, "favorites": 1, "shared": 2, "snapshots": 1}
    assert "guided" in ctx["builder_note"]


def test_spend_report_list_hides_a_colleagues_private_report(client_a, spend_report_a,
                                                             spend_report_private_a,
                                                             spend_snapshot_private_a):
    resp = client_a.get(reverse("procurement:spendreport_list"))

    assert _spend_pks(resp) == [spend_report_a.pk]
    # Neither listed NOR counted - and its snapshot is invisible too.
    assert resp.context["stats"] == {"total": 1, "favorites": 0, "shared": 1, "snapshots": 0}


def test_spend_report_list_search_and_filters(client_a, spend_report_a, spend_report_favorite_a):
    url = reverse("procurement:spendreport_list")

    assert _spend_pks(client_a.get(url, {"q": "Category by month"})) == [
        spend_report_favorite_a.pk]
    assert _spend_pks(client_a.get(url, {"q": spend_report_a.number})) == [spend_report_a.pk]
    assert _spend_pks(client_a.get(url, {"is_favorite": "True"})) == [spend_report_favorite_a.pk]
    assert set(_spend_pks(client_a.get(url, {"basis": "invoiced"}))) == {
        spend_report_a.pk, spend_report_favorite_a.pk}
    assert _spend_pks(client_a.get(url, {"measure": "leakage"})) == []


def test_spend_report_list_junk_params_render_200(client_a, spend_report_a):
    resp = client_a.get(reverse("procurement:spendreport_list"),
                        {"measure": "nope", "basis": "??", "is_favorite": "abc"})
    assert resp.status_code == 200


def test_spend_report_list_page_two_and_past_the_end(client_a, _spend_bulk_reports,
                                                     spend_report_a):
    url = reverse("procurement:spendreport_list")

    page_one = client_a.get(url)
    assert len(_spend_pks(page_one)) == 15
    assert page_one.context["page_obj"].paginator.num_pages == 2

    page_two = client_a.get(url, {"page": "2"})
    assert page_two.status_code == 200
    assert len(_spend_pks(page_two)) == 4

    past_end = client_a.get(url, {"page": "999"})
    assert past_end.status_code == 200
    assert past_end.context["page_obj"].number == 2


def test_spend_report_list_query_budget(client_a, _spend_bulk_reports, spend_report_favorite_a,
                                        django_assert_max_num_queries):
    with django_assert_max_num_queries(18):
        resp = client_a.get(reverse("procurement:spendreport_list"))
    assert resp.status_code == 200
    assert len(_spend_pks(resp)) == 15


def test_spend_report_list_never_shows_another_tenants_rows(client_a, spend_report_a,
                                                            spend_report_b):
    resp = client_a.get(reverse("procurement:spendreport_list"))
    assert _spend_pks(resp) == [spend_report_a.pk]


# =================================================================================================
# SpendReport create / detail / edit / delete
# =================================================================================================

def test_spend_report_create_get_renders_form_contract(client_a):
    resp = client_a.get(reverse("procurement:spendreport_create"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/spendreport/form.html" in _spend_templates(resp)
    assert resp.context["is_edit"] is False
    assert resp.context["title"] == "New spend report"
    assert resp.context["submit_label"] == "Create report"
    assert resp.context["cancel_url"] == reverse("procurement:spendreport_list")
    assert "guided" in resp.context["builder_note"]
    # ``obj`` is deliberately absent from the CREATE context.
    assert "obj" not in resp.context
    fields = resp.context["form"].fields
    assert "owner" not in fields and "last_run_at" not in fields and "number" not in fields


def test_spend_report_create_post_saves_with_tenant_and_owner(client_a, tenant_a, admin_user):
    resp = client_a.post(reverse("procurement:spendreport_create"), _spend_report_body())

    assert resp.status_code == 302
    report = SpendReport.objects.get(name="Suppliers this quarter")
    assert resp["Location"] == reverse("procurement:spendreport_detail", args=[report.pk])
    assert report.tenant_id == tenant_a.id
    assert report.owner_id == admin_user.pk
    assert report.number.startswith("SPR-")
    assert report.last_run_at is None
    assert any(f"Report {report.number} saved." in m for m in _spend_messages(resp))


@pytest.mark.parametrize("floor", ["NaN", "Infinity", "-5", "99999999999999999999.99"])
def test_spend_report_create_rejects_junk_min_amount(client_a, floor):
    resp = client_a.post(reverse("procurement:spendreport_create"),
                         _spend_report_body(min_amount=floor))

    assert resp.status_code == 200
    assert "min_amount" in resp.context["form"].errors
    assert not SpendReport.objects.filter(name="Suppliers this quarter").exists()


def test_spend_report_create_rejects_a_crafted_cross_tenant_vendor(client_a, spend_vendor_b):
    resp = client_a.post(reverse("procurement:spendreport_create"),
                         _spend_report_body(vendor=str(spend_vendor_b.pk)))

    assert resp.status_code == 200
    assert "vendor" in resp.context["form"].errors
    assert not SpendReport.objects.filter(name="Suppliers this quarter").exists()


def test_spend_report_create_rejects_a_reversed_custom_range(client_a):
    today = _spend_today()
    resp = client_a.post(reverse("procurement:spendreport_create"), _spend_report_body(
        date_range="custom", date_from=today.isoformat(),
        date_to=(today - datetime.timedelta(days=5)).isoformat()))

    assert resp.status_code == 200
    assert "date_from" in resp.context["form"].errors


def test_spend_report_detail_runs_live_and_stamps_nothing(client_a, spend_report_a,
                                                          spend_invoice_line_a,
                                                          spend_snapshot_a):
    resp = client_a.get(reverse("procurement:spendreport_detail", args=[spend_report_a.pk]))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/spendreport/detail.html" in _spend_templates(resp)
    ctx = resp.context
    assert ctx["obj"].pk == spend_report_a.pk
    assert ctx["report"].pk == spend_report_a.pk
    result = ctx["result"]
    assert result["columns"] == ["Supplier", "Net spend", "Share", "Lines"]
    assert result["rows"][0][0] == "Meridian Office Supplies"
    assert result["rows"][0][1] == "250.00"
    assert [s["label"] for s in result["summary"]][:2] == ["Net spend", "Lines"]
    assert [s.pk for s in ctx["snapshots"]] == [spend_snapshot_a.pk]
    assert ctx["start"] < ctx["end"]
    assert ctx["mixed_currency"] is False
    assert "capped" in ctx["row_cap_note"]
    assert ctx["last_run_at"] is None
    assert ctx["export_url"] == reverse("procurement:spendreport_export",
                                        args=[spend_report_a.pk])
    assert ctx["snapshot_url"] == reverse("procurement:spendreport_snapshot",
                                          args=[spend_report_a.pk])
    assert ctx["run_url"] == reverse("procurement:spendreport_run", args=[spend_report_a.pk])
    assert ctx["favorite_url"] == reverse("procurement:spendreport_favorite",
                                          args=[spend_report_a.pk])
    # A supplier-axis report prints no department caveat.
    assert ctx["department_caveat"] == ""

    spend_report_a.refresh_from_db()
    assert spend_report_a.last_run_at is None, "opening the page must not count as a run"


def test_spend_report_detail_is_derived_not_stored(client_a, spend_report_a,
                                                   spend_invoice_line_a):
    """L29: the report row holds the QUESTION only - editing a line changes what it renders."""
    url = reverse("procurement:spendreport_detail", args=[spend_report_a.pk])
    before = client_a.get(url).context["result"]["rows"][0][1]

    spend_invoice_line_a.unit_price = Decimal("30.00")
    spend_invoice_line_a.save()
    stamp = SpendReport.objects.get(pk=spend_report_a.pk).updated_at

    after = client_a.get(url).context["result"]["rows"][0][1]
    assert before == "250.00" and after == "300.00"
    assert SpendReport.objects.get(pk=spend_report_a.pk).updated_at == stamp


def test_spend_report_detail_prints_the_department_caveat_on_that_axis(client_a, tenant_a,
                                                                       admin_user):
    report = SpendReport.objects.create(tenant=tenant_a, name="By cost centre",
                                        owner=admin_user, dimension_1="department")
    resp = client_a.get(reverse("procurement:spendreport_detail", args=[report.pk]))

    assert resp.status_code == 200
    assert "(unassigned)" in resp.context["department_caveat"]


def test_spend_report_detail_of_another_tenant_or_a_private_row_is_404(client_a, spend_report_b,
                                                                       spend_report_private_a):
    assert client_a.get(reverse("procurement:spendreport_detail",
                                args=[spend_report_b.pk])).status_code == 404
    assert client_a.get(reverse("procurement:spendreport_detail",
                                args=[spend_report_private_a.pk])).status_code == 404


def test_spend_report_edit_never_transfers_ownership(client_a, tenant_a, member_user):
    report = SpendReport.objects.create(tenant=tenant_a, name="Shared by a colleague",
                                        owner=member_user, is_shared=True)
    url = reverse("procurement:spendreport_edit", args=[report.pk])

    page = client_a.get(url)
    assert page.status_code == 200
    assert page.context["is_edit"] is True
    assert page.context["obj"].pk == report.pk
    assert page.context["title"] == "Edit report"

    resp = client_a.post(url, _spend_report_body(name="Renamed by the admin", measure="leakage"))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendreport_detail", args=[report.pk])
    report.refresh_from_db()
    assert report.name == "Renamed by the admin"
    assert report.measure == "leakage"
    assert report.owner_id == member_user.pk


def test_spend_report_edit_of_a_private_row_is_404(client_a, spend_report_private_a):
    assert client_a.get(reverse("procurement:spendreport_edit",
                                args=[spend_report_private_a.pk])).status_code == 404


def test_spend_report_delete_is_post_only(client_a, spend_report_a):
    url = reverse("procurement:spendreport_delete", args=[spend_report_a.pk])

    assert client_a.get(url).status_code == 405
    assert SpendReport.objects.filter(pk=spend_report_a.pk).exists()

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendreport_list")
    assert not SpendReport.objects.filter(pk=spend_report_a.pk).exists()


def test_spend_report_delete_of_a_private_or_foreign_row_is_404(client_a,
                                                                spend_report_private_a,
                                                                spend_report_b):
    assert client_a.post(reverse("procurement:spendreport_delete",
                                 args=[spend_report_private_a.pk])).status_code == 404
    assert client_a.post(reverse("procurement:spendreport_delete",
                                 args=[spend_report_b.pk])).status_code == 404
    assert SpendReport.objects.filter(pk=spend_report_private_a.pk).exists()
    assert SpendReport.objects.filter(pk=spend_report_b.pk).exists()


# =================================================================================================
# SpendReport verbs
# =================================================================================================

def test_spend_report_run_stamps_last_run_without_bumping_updated_at(client_a, spend_report_a):
    url = reverse("procurement:spendreport_run", args=[spend_report_a.pk])
    stamp = spend_report_a.updated_at

    assert client_a.get(url).status_code == 405
    spend_report_a.refresh_from_db()
    assert spend_report_a.last_run_at is None

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendreport_detail", args=[spend_report_a.pk])
    spend_report_a.refresh_from_db()
    assert spend_report_a.last_run_at is not None
    assert spend_report_a.updated_at == stamp
    assert any(f"{spend_report_a.number} re-run." in m for m in _spend_messages(resp))


def test_spend_report_snapshot_freezes_the_current_result(client_a, admin_user, spend_report_a,
                                                          spend_invoice_line_a):
    url = reverse("procurement:spendreport_snapshot", args=[spend_report_a.pk])

    assert client_a.get(url).status_code == 405
    assert SpendReportSnapshot.objects.count() == 0

    resp = client_a.post(url)
    assert resp.status_code == 302
    snapshot = SpendReportSnapshot.objects.get()
    assert resp["Location"] == reverse("procurement:spendreportsnapshot_detail",
                                       args=[snapshot.pk])
    assert snapshot.tenant_id == spend_report_a.tenant_id
    assert snapshot.report_id == spend_report_a.pk
    assert snapshot.generated_by_id == admin_user.pk
    assert snapshot.row_count == 1
    assert snapshot.data["rows"][0][0] == "Meridian Office Supplies"
    assert set(snapshot.data) == {"columns", "rows", "chart_type", "chart_labels", "chart_data"}
    assert any("Snapshot saved" in m for m in _spend_messages(resp))
    spend_report_a.refresh_from_db()
    assert spend_report_a.last_run_at is not None


def test_spend_report_favorite_toggles_and_guards_the_next_url(client_a, spend_report_a):
    url = reverse("procurement:spendreport_favorite", args=[spend_report_a.pk])
    detail = reverse("procurement:spendreport_detail", args=[spend_report_a.pk])

    assert client_a.get(url).status_code == 405

    on = client_a.post(url)
    assert on.status_code == 302 and on["Location"] == detail
    spend_report_a.refresh_from_db()
    assert spend_report_a.is_favorite is True

    off = client_a.post(url, {"next": reverse("procurement:spendreport_list")})
    assert off["Location"] == reverse("procurement:spendreport_list")
    spend_report_a.refresh_from_db()
    assert spend_report_a.is_favorite is False

    # An off-host ``next`` is an open redirect - it must fall back to the detail page.
    crafted = client_a.post(url, {"next": "https://evil.example.com/steal"})
    assert crafted["Location"] == detail


def test_spend_report_verbs_on_a_private_row_are_404(client_a, spend_report_private_a):
    pk = spend_report_private_a.pk
    for name in ("spendreport_run", "spendreport_snapshot", "spendreport_favorite"):
        assert client_a.post(reverse(f"procurement:{name}", args=[pk])).status_code == 404
    assert client_a.get(reverse("procurement:spendreport_export",
                                args=[pk])).status_code == 404
    spend_report_private_a.refresh_from_db()
    assert spend_report_private_a.last_run_at is None
    assert SpendReportSnapshot.objects.count() == 0


def test_spend_report_export_is_a_neutralised_csv(client_a, tenant_a, spend_report_a, usd):
    nasty = _spend_supplier(tenant_a, "=cmd|'/c calc'!A1")
    _spend_invoice_with_line(tenant_a, nasty, number="SUP-9100", price="75.00", currency=usd)

    resp = client_a.get(reverse("procurement:spendreport_export", args=[spend_report_a.pk]))

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert resp["Content-Disposition"] == (
        f'attachment; filename="spend-report-{spend_report_a.number}.csv"')
    body = resp.content.decode()
    assert body.splitlines()[0].startswith("Supplier,Net spend")
    assert "'=cmd|'" in body, "a leading = must be neutralised by csv_safe"


# =================================================================================================
# SpendReportSnapshot
# =================================================================================================

def test_spend_snapshot_detail_renders_the_stored_payload(client_a, spend_snapshot_a,
                                                          spend_report_a):
    resp = client_a.get(reverse("procurement:spendreportsnapshot_detail",
                                args=[spend_snapshot_a.pk]))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/spendreportsnapshot/detail.html" in _spend_templates(resp)
    ctx = resp.context
    assert ctx["obj"].pk == spend_snapshot_a.pk
    assert ctx["snapshot"].pk == spend_snapshot_a.pk
    assert ctx["report"].pk == spend_report_a.pk
    assert ctx["summary"] == [{"label": "Net spend", "value": "250.00"}]
    assert ctx["columns"] == ["Supplier", "Net spend", "Share", "Lines"]
    assert ctx["rows"] == [["Meridian Office Supplies", "250.00", "100.0%", "1"]]
    assert ctx["chart_type"] == "bar"
    assert ctx["chart_labels"] == ["Meridian Office Supplies"]
    assert ctx["chart_data"] == [250.0]
    assert ctx["chart_rows"] == [{"label": "Meridian Office Supplies", "value": 250.0}]
    assert ctx["export_url"] == reverse("procurement:spendreportsnapshot_export",
                                        args=[spend_snapshot_a.pk])
    assert ctx["delete_url"] == reverse("procurement:spendreportsnapshot_delete",
                                        args=[spend_snapshot_a.pk])
    assert ctx["back_url"] == reverse("procurement:spendreport_detail", args=[spend_report_a.pk])


def test_spend_snapshot_detail_survives_a_malformed_payload(client_a, tenant_a, spend_report_a):
    broken = SpendReportSnapshot.objects.create(
        tenant=tenant_a, report=spend_report_a, title="Broken payload",
        summary="not-a-list",
        data={"columns": "nope", "rows": {"a": 1}, "chart_type": 5,
              "chart_labels": None, "chart_data": "x"})

    resp = client_a.get(reverse("procurement:spendreportsnapshot_detail", args=[broken.pk]))

    assert resp.status_code == 200
    assert resp.context["columns"] == []
    assert resp.context["rows"] == []
    assert resp.context["chart_type"] == "table"
    assert resp.context["chart_rows"] == []


def test_spend_snapshot_export_comes_straight_from_the_payload(client_a, spend_snapshot_a):
    resp = client_a.get(reverse("procurement:spendreportsnapshot_export",
                                args=[spend_snapshot_a.pk]))

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert resp["Content-Disposition"] == (
        f'attachment; filename="spend-report-snapshot-{spend_snapshot_a.pk}.csv"')
    lines = resp.content.decode().splitlines()
    assert lines[0] == "Supplier,Net spend,Share,Lines"
    assert lines[1] == "Meridian Office Supplies,250.00,100.0%,1"


def test_spend_snapshot_delete_is_post_only(client_a, spend_snapshot_a, spend_report_a):
    url = reverse("procurement:spendreportsnapshot_delete", args=[spend_snapshot_a.pk])

    assert client_a.get(url).status_code == 405
    assert SpendReportSnapshot.objects.filter(pk=spend_snapshot_a.pk).exists()

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendreport_detail", args=[spend_report_a.pk])
    assert not SpendReportSnapshot.objects.filter(pk=spend_snapshot_a.pk).exists()
    assert any("Snapshot deleted." in m for m in _spend_messages(resp))


def test_spend_snapshot_of_another_tenant_or_a_private_parent_is_404(client_a, spend_snapshot_b,
                                                                     spend_snapshot_private_a):
    for pk in (spend_snapshot_b.pk, spend_snapshot_private_a.pk):
        assert client_a.get(reverse("procurement:spendreportsnapshot_detail",
                                    args=[pk])).status_code == 404
        assert client_a.get(reverse("procurement:spendreportsnapshot_export",
                                    args=[pk])).status_code == 404
        assert client_a.post(reverse("procurement:spendreportsnapshot_delete",
                                     args=[pk])).status_code == 404
    assert SpendReportSnapshot.objects.filter(pk=spend_snapshot_b.pk).exists()
    assert SpendReportSnapshot.objects.filter(pk=spend_snapshot_private_a.pk).exists()


# =================================================================================================
# The computed pages
# =================================================================================================

def test_spend_dashboard_renders_every_contract_key_populated(client_a, spend_invoice_line_a,
                                                              spend_po_line_a, org_unit_a):
    resp = client_a.get(reverse("procurement:spend_dashboard"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/dashboard.html" in _spend_templates(resp)
    ctx = resp.context
    kpis = ctx["kpis"]
    assert set(kpis) == {"net_spend", "invoice_count", "supplier_count", "avg_invoice",
                         "classified_pct", "maverick_pct", "top5_share_pct",
                         "po_less_share_pct"}
    assert kpis["net_spend"]["value"] == Decimal("250.00")
    assert kpis["invoice_count"]["value"] == 1
    assert ctx["by_supplier"][0]["label"] == "Meridian Office Supplies"
    assert ctx["by_supplier"][0]["value"] == Decimal("250.00")
    assert ctx["by_category"][0]["label"] == "Office Supplies"
    assert ctx["by_department"][0]["label"] == "(unassigned)"
    assert ctx["by_gl_account"][0]["label"].startswith("5000")
    assert ctx["trend"]["labels"] and ctx["trend"]["data"]
    assert [row["code"] for row in ctx["currency_rows"]] == ["USD"]
    assert ctx["mixed_currency"] is False
    assert ctx["basis"] == "invoiced"
    assert dict(ctx["basis_choices"])["committed"].startswith("Committed")
    assert ctx["range_key"] == "last_90"
    assert dict(ctx["date_range_choices"])["all"] == "All time"
    assert ctx["end"] == _spend_today() + datetime.timedelta(days=1)
    assert ctx["stats"] == {"invoice_count": 1, "line_count": 1, "supplier_count": 1,
                            "unclassified_value": Decimal("0.00")}
    assert ctx["scm_analytics_url"] == reverse("scm:spend_analytics")
    assert "(unassigned)" in ctx["department_caveat"]
    assert ctx["drill_url_name"] == "procurement:supplierinvoice_detail"
    assert ctx["maverick_dashboard_url"] == reverse("procurement:maverick_dashboard")
    assert ctx["category_spend_url"] == reverse("procurement:category_spend")
    assert ctx["workbench_url"] == reverse("procurement:classification_workbench")
    assert ctx["export_url"] == reverse("procurement:spend_export")


def test_spend_dashboard_excludes_a_draft_invoice(client_a, spend_invoice_line_a,
                                                  spend_invoice_draft_a):
    SupplierInvoiceLine.objects.create(
        invoice=spend_invoice_draft_a, description="Not recognised yet",
        quantity=Decimal("1"), unit_price=Decimal("999.00"))

    resp = client_a.get(reverse("procurement:spend_dashboard"))

    assert resp.context["stats"]["line_count"] == 1
    assert resp.context["kpis"]["net_spend"]["value"] == Decimal("250.00")


def test_spend_dashboard_committed_basis_and_junk_params(client_a, spend_po_line_a,
                                                         spend_invoice_line_a):
    committed = client_a.get(reverse("procurement:spend_dashboard"), {"basis": "committed"})
    assert committed.status_code == 200
    assert committed.context["basis"] == "committed"
    assert committed.context["kpis"]["net_spend"]["value"] == Decimal("240.00")

    junk = client_a.get(reverse("procurement:spend_dashboard"), {
        "basis": "xx", "range": "yy", "vendor": "abc",
        "category": "999999999999999999999", "org_unit": "-1", "gl_account": "²",
        "date_from": "not-a-date", "date_to": "9999-99-99"})
    assert junk.status_code == 200
    assert junk.context["basis"] == "invoiced"
    assert junk.context["range_key"] == "last_90"
    assert junk.context["kpis"]["net_spend"]["value"] == Decimal("250.00")


def test_spend_dashboard_custom_range_is_honoured(client_a, spend_invoice_line_a):
    today = _spend_today()
    resp = client_a.get(reverse("procurement:spend_dashboard"), {
        "range": "custom", "date_from": (today - datetime.timedelta(days=3)).isoformat(),
        "date_to": today.isoformat()})

    assert resp.status_code == 200
    assert resp.context["range_key"] == "custom"
    assert resp.context["start"] == today - datetime.timedelta(days=3)
    assert resp.context["end"] == today + datetime.timedelta(days=1)
    assert resp.context["kpis"]["net_spend"]["value"] == Decimal("250.00")


def test_spend_category_page_renders_the_pareto_league(client_a, tenant_a, spend_invoice_line_a,
                                                       spend_vendor_other_a, usd,
                                                       spend_category_a):
    _spend_invoice_with_line(tenant_a, spend_vendor_other_a, number="SUP-7700", price="50.00",
                             description="Window cleaning", sku="SVC-CLEAN", currency=usd)

    resp = client_a.get(reverse("procurement:category_spend"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/category_spend.html" in _spend_templates(resp)
    ctx = resp.context
    assert [c.pk for c in ctx["categories"]], "category dropdown must be populated"
    assert ctx["category"] is None
    labels = [row["label"] for row in ctx["rows"]]
    assert labels == ["Meridian Office Supplies", "Cobalt Facilities Group"]
    assert ctx["rows"][0]["band"] == "A"
    assert ctx["hhi"] > 0
    assert ctx["trend"]["labels"]
    assert [row["item"] for row in ctx["item_rows"]]
    assert ctx["sole_source_count"] == 2
    assert [row["band"] for row in ctx["abc_rows"]] == ["A", "B", "C"]
    assert ctx["consolidation_opportunity"] >= 0
    assert ctx["tail_share_pct"] >= 0
    assert ctx["stats"] == {"suppliers": 2, "txns": 2, "net_spend": Decimal("300.00"),
                            "avg_price": Decimal("150.00")}
    assert ctx["unclassified_value"] == Decimal("50.00")
    assert ctx["fallback_note"] and ctx["committed_category_note"]
    assert ctx["mixed_currency"] is False
    assert [row["code"] for row in ctx["currency_rows"]] == ["USD"]
    assert ctx["workbench_url"] == reverse("procurement:classification_workbench")


def test_spend_category_page_filters_to_one_category(client_a, spend_invoice_line_a,
                                                     spend_category_a):
    resp = client_a.get(reverse("procurement:category_spend"),
                        {"category": str(spend_category_a.pk)})

    assert resp.status_code == 200
    assert resp.context["category"].pk == spend_category_a.pk
    assert resp.context["stats"]["net_spend"] == Decimal("250.00")


@pytest.mark.parametrize("junk", _SPEND_JUNK_INTS)
def test_spend_category_page_junk_category_renders_200(client_a, spend_invoice_line_a, junk):
    resp = client_a.get(reverse("procurement:category_spend"), {"category": junk})
    assert resp.status_code == 200
    assert resp.context["category"] is None


def test_spend_category_page_ignores_another_tenants_category(client_a, spend_invoice_line_a,
                                                              spend_category_b):
    resp = client_a.get(reverse("procurement:category_spend"),
                        {"category": str(spend_category_b.pk)})
    assert resp.status_code == 200
    assert resp.context["category"] is None


def test_spend_export_page_previews_what_will_download(client_a, spend_invoice_line_a,
                                                       spend_report_a, spend_snapshot_a):
    resp = client_a.get(reverse("procurement:spend_export"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/export.html" in _spend_templates(resp)
    ctx = resp.context
    assert [r.pk for r in ctx["reports"]] == [spend_report_a.pk]
    assert [s.pk for s in ctx["snapshots"]] == [spend_snapshot_a.pk]
    assert ctx["dimension"] == "supplier"
    assert ctx["preview_columns"] == ["Supplier", "Spend", "Share %", "Transactions"]
    assert ctx["preview_rows"][0][0] == "Meridian Office Supplies"
    assert ctx["row_count"] == 1
    assert ctx["max_rows"] == 5000
    assert "Showing 1 of 1 rows" in ctx["showing_note"]
    assert ctx["download_url"] == reverse("procurement:spend_export_download")
    assert "CSV" in ctx["bi_note"]
    assert ctx["stats"] == {"reports": 1, "snapshots": 1, "rows": 1, "max_rows": 5000}
    assert dict(ctx["dimension_choices"])["none"] == "- none -"


def test_spend_export_page_line_register_dimension(client_a, spend_invoice_line_a):
    resp = client_a.get(reverse("procurement:spend_export"), {"dimension": "none"})

    assert resp.status_code == 200
    assert resp.context["dimension"] == "none"
    assert resp.context["preview_columns"][0] == "Date"
    assert resp.context["preview_columns"][-1] == "Line total"
    row = resp.context["preview_rows"][0]
    assert row[2] == "Meridian Office Supplies"
    assert row[-1] == Decimal("250.00")


def test_spend_export_page_junk_params_render_200(client_a, spend_invoice_line_a):
    resp = client_a.get(reverse("procurement:spend_export"),
                        {"dimension": "zzz", "basis": "xx", "range": "yy", "vendor": "abc"})
    assert resp.status_code == 200
    assert resp.context["dimension"] == "supplier"
    assert resp.context["basis"] == "invoiced"


def test_spend_export_page_hides_a_colleagues_private_report(client_a, spend_report_private_a,
                                                             spend_snapshot_private_a,
                                                             spend_report_a):
    resp = client_a.get(reverse("procurement:spend_export"))
    assert [r.pk for r in resp.context["reports"]] == [spend_report_a.pk]
    assert resp.context["stats"]["reports"] == 1
    assert resp.context["stats"]["snapshots"] == 0


def test_spend_export_download_is_a_neutralised_csv(client_a, tenant_a, spend_invoice_line_a,
                                                    usd):
    nasty = _spend_supplier(tenant_a, "@SUM(1+1)*cmd")
    _spend_invoice_with_line(tenant_a, nasty, number="SUP-7300", price="12.00", currency=usd)
    start = _spend_today() + datetime.timedelta(days=1) - datetime.timedelta(days=90)
    end = _spend_today() + datetime.timedelta(days=1)

    resp = client_a.get(reverse("procurement:spend_export_download"))

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert resp["Content-Disposition"] == (
        f'attachment; filename="spend-invoiced-{start:%Y%m%d}-{end:%Y%m%d}.csv"')
    body = resp.content.decode()
    assert body.splitlines()[0].startswith("Supplier,Spend")
    assert "'@SUM(1+1)*cmd" in body


def test_spend_export_download_line_register_and_junk_params(client_a, spend_invoice_line_a):
    resp = client_a.get(reverse("procurement:spend_export_download"),
                        {"dimension": "none", "basis": "zz", "category": "abc",
                         "date_from": "oops"})

    assert resp.status_code == 200
    lines = resp.content.decode().splitlines()
    assert lines[0].startswith("Date,Document,Supplier")
    assert "Meridian Office Supplies" in lines[1]


# =================================================================================================
# Classification workbench
# =================================================================================================

def test_spend_workbench_ranks_the_unclassified_queue(client_a, tenant_a, spend_vendor_a,
                                                      spend_invoice_line_a, spend_rule_keyword_a,
                                                      gl_expense_a, usd):
    # An unclassified line: no item, and no active rule claims it.
    _spend_invoice_with_line(tenant_a, spend_vendor_a, number="SUP-8800", price="500.00",
                             description="Consultancy retainer", sku="CONSULT",
                             gl_account=gl_expense_a, currency=usd)

    resp = client_a.get(reverse("procurement:classification_workbench"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/classification_workbench.html" in _spend_templates(resp)
    ctx = resp.context
    top = ctx["rows"][0]
    assert top["label"] == "Meridian Office Supplies"
    assert top["value"] == Decimal("500.00")
    assert top["count"] == 1
    assert top["match_type"] == "vendor"
    assert top["create_url"].startswith(reverse("procurement:spendrule_create"))
    assert f"vendor={spend_vendor_a.pk}" in top["create_url"]
    assert ctx["page_obj"].paginator is ctx["paginator"]
    assert ctx["classified_pct"] >= 0
    assert ctx["unclassified_value"] == Decimal("500.00")
    assert ctx["unclassified_display"]
    assert ctx["total_value"] == Decimal("750.00")
    assert ctx["total_display"]
    assert [r.pk for r in ctx["rules"]] == [spend_rule_keyword_a.pk]
    assert ctx["rule_count"] == 1
    assert ctx["group_by"] == "vendor"
    assert dict(ctx["group_by_choices"])["keyword"] == "Description / SKU keyword"
    assert ctx["basis"] == "invoiced"
    assert ctx["range_key"] == "last_90"
    assert ctx["start"] < ctx["end"]
    assert ctx["stats"] == {"lines": 2, "total_value": Decimal("750.00"),
                            "unclassified_value": Decimal("500.00"),
                            "classified_pct": ctx["classified_pct"], "rules": 1, "groups": 1}
    assert ctx["create_rule_url"] == reverse("procurement:spendrule_create")
    assert ctx["rules_url"] == reverse("procurement:spendrule_list")
    assert ctx["dashboard_url"] == reverse("procurement:spend_dashboard")
    assert ctx["category_spend_url"] == reverse("procurement:category_spend")
    assert "rule" in ctx["engine_note"].lower()


def test_spend_workbench_group_by_gl_account_and_keyword(client_a, tenant_a, spend_vendor_a,
                                                         gl_expense_a, usd):
    _spend_invoice_with_line(tenant_a, spend_vendor_a, number="SUP-8801", price="120.00",
                             description="Toner refill", sku="TNR-99",
                             gl_account=gl_expense_a, currency=usd)
    url = reverse("procurement:classification_workbench")

    by_gl = client_a.get(url, {"group_by": "gl_account"})
    assert by_gl.status_code == 200
    assert by_gl.context["group_by"] == "gl_account"
    assert by_gl.context["rows"][0]["label"].startswith("5000")
    assert f"gl_account={gl_expense_a.pk}" in by_gl.context["rows"][0]["create_url"]

    by_keyword = client_a.get(url, {"group_by": "keyword"})
    assert by_keyword.context["group_by"] == "keyword"
    assert by_keyword.context["rows"][0]["label"] == "TNR-99"
    assert "keyword=TNR-99" in by_keyword.context["rows"][0]["create_url"]


def test_spend_workbench_page_two_and_past_the_end(client_a, tenant_a, usd):
    for i in range(27):
        supplier = _spend_supplier(tenant_a, f"Tail supplier {i:02d}")
        _spend_invoice_with_line(tenant_a, supplier, number=f"SUP-90{i:02d}",
                                 price=str(10 + i), currency=usd)
    url = reverse("procurement:classification_workbench")

    page_one = client_a.get(url)
    assert len(page_one.context["rows"]) == 25
    assert page_one.context["paginator"].num_pages == 2
    assert page_one.context["stats"]["groups"] == 27

    page_two = client_a.get(url, {"page": "2"})
    assert page_two.status_code == 200
    assert len(page_two.context["rows"]) == 2

    past_end = client_a.get(url, {"page": "999"})
    assert past_end.status_code == 200
    assert past_end.context["page_obj"].number == 2

    junk_page = client_a.get(url, {"page": "abc"})
    assert junk_page.context["page_obj"].number == 1


def test_spend_workbench_junk_params_render_200(client_a, spend_invoice_line_a):
    resp = client_a.get(reverse("procurement:classification_workbench"),
                        {"group_by": "qq", "basis": "zz", "range": "nope", "vendor": "abc",
                         "category": "999999999999999999999", "org_unit": "-1",
                         "gl_account": "²"})

    assert resp.status_code == 200
    assert resp.context["group_by"] == "vendor"
    assert resp.context["basis"] == "invoiced"
    assert resp.context["range_key"] == "last_90"


def test_spend_workbench_committed_basis_is_rules_only(client_a, spend_po_line_a):
    resp = client_a.get(reverse("procurement:classification_workbench"), {"basis": "committed"})

    assert resp.status_code == 200
    assert resp.context["basis"] == "committed"
    assert resp.context["total_value"] == Decimal("240.00")
    assert resp.context["rows"][0]["label"] == "Meridian Office Supplies"


# =================================================================================================
# Maverick board + scan
# =================================================================================================

def test_spend_maverick_dashboard_renders_every_contract_key(client_a, spend_finding_open_a,
                                                             spend_finding_leakage_a,
                                                             spend_finding_dismissed_a,
                                                             org_unit_a, spend_invoice_line_a):
    resp = client_a.get(reverse("procurement:maverick_dashboard"))

    assert resp.status_code == 200
    assert "procurement/spendanalytics/maverick_dashboard.html" in _spend_templates(resp)
    ctx = resp.context
    reasons = {row["reason"]: row for row in ctx["by_reason"]}
    assert len(reasons) == 8, "every reason is padded to a zero row"
    assert reasons["no_contract"]["n"] == 1
    assert reasons["price_above_contract"]["value"] == Decimal("250.00")
    # The dismissed finding is out of the live figures.
    assert reasons["off_catalog"]["n"] == 0
    assert ctx["rate"]["band"] in {"low", "medium", "high"}
    assert ctx["by_vendor"][0]["label"] == "Meridian Office Supplies"
    assert ctx["by_category"][0]["label"] in {"Office Supplies", "(Unclassified)"}
    assert ctx["by_department"][0]["label"] in {"Acme Facilities", "(unassigned)"}
    assert [row["label"] for row in ctx["by_severity"]]
    assert ctx["trend"]["labels"] and ctx["trend"]["data"]
    assert ctx["trend_rows"][0]["label"] == ctx["trend"]["labels"][0]
    assert ctx["leakage_total"] == Decimal("50.00")
    assert ctx["leakage_display"]
    assert ctx["open_findings"] == 2
    assert ctx["total_value"] == Decimal("500.00")
    assert ctx["stats"] == {"findings": 2, "open": 2, "acknowledged": 0, "justified": 0,
                            "remediated": 0, "dismissed": 1,
                            "value_at_risk": Decimal("500.00"), "leakage": Decimal("50.00")}
    assert len(ctx["reason_choices"]) == 8
    assert len(ctx["severity_choices"]) == 3
    assert len(ctx["status_choices"]) == 5
    assert ctx["range_key"] == "last_90"
    assert ctx["start"] < ctx["end"]
    assert ctx["scan_url"] == reverse("procurement:maverick_scan")
    assert ctx["findings_url"] == reverse("procurement:maverickfinding_list")
    assert ctx["dashboard_url"] == reverse("procurement:spend_dashboard")
    assert "addressable" in ctx["exclusions_note"]
    assert "scan" in ctx["scan_note"].lower()
    assert ctx["is_admin"] is True


def test_spend_maverick_dashboard_junk_range_falls_back(client_a, spend_finding_open_a):
    resp = client_a.get(reverse("procurement:maverick_dashboard"), {"range": "since-forever"})
    assert resp.status_code == 200
    assert resp.context["range_key"] == "last_90"


def test_spend_maverick_dashboard_never_counts_another_tenant(client_a, spend_finding_open_a,
                                                              spend_finding_b):
    resp = client_a.get(reverse("procurement:maverick_dashboard"))
    assert resp.context["stats"]["findings"] == 1


def test_spend_maverick_scan_is_post_only_and_admin_gated(client_a, member_client,
                                                          spend_invoice_line_a):
    url = reverse("procurement:maverick_scan")

    assert client_a.get(url).status_code == 405
    assert member_client.post(url, {"range": "last_90"}).status_code == 403

    resp = client_a.post(url, {"range": "last_30"})
    assert resp.status_code == 302
    assert resp["Location"] == f"{reverse('procurement:maverick_dashboard')}?range=last_30"


def test_spend_maverick_scan_ignores_an_unknown_reason(client_a, spend_invoice_line_a):
    resp = client_a.post(reverse("procurement:maverick_scan"),
                         {"range": "not-a-range", "reason": ["drop-tables", "no_contract"]})

    assert resp.status_code == 302
    assert resp["Location"] == f"{reverse('procurement:maverick_dashboard')}?range=last_90"
    # Only the recognised reason could have raised anything.
    assert set(MaverickSpendFinding.objects.values_list("reason", flat=True)) <= {"no_contract"}


def test_spend_maverick_scan_is_idempotent(client_a, spend_invoice_line_a):
    url = reverse("procurement:maverick_scan")

    client_a.post(url, {"range": "last_90"})
    first = MaverickSpendFinding.objects.count()

    second = client_a.post(url, {"range": "last_90"})
    assert second.status_code == 302
    assert MaverickSpendFinding.objects.count() == first
    assert any("no new findings" in m for m in _spend_messages(second))


# =================================================================================================
# Anonymous access (the login gate every page shares)
# =================================================================================================

@pytest.mark.parametrize("name", ["spend_dashboard", "category_spend", "spend_export",
                                  "spend_export_download", "classification_workbench",
                                  "maverick_dashboard", "spendrule_list", "spendrule_create",
                                  "maverickfinding_list", "maverickfinding_create",
                                  "spendreport_list", "spendreport_create"])
def test_spend_anonymous_is_sent_to_the_login_page(client, name):
    url = reverse(f"procurement:{name}")
    resp = client.get(url)

    assert resp.status_code == 302
    assert resp["Location"] == f"/login/?next={url}"
