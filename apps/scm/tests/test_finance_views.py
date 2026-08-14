"""SCM 4.18 Finance & Accounting Integration — the VIEW/CRUD integration lane.

What a **request** does, end to end. The other three 4.18 lanes own the model arithmetic
(``test_finance_models.py``), the form field lists (``test_finance_forms.py``) and tenant isolation /
auth / CSRF / the method guards (``test_finance_security.py``); this file asserts that every one of
the sub-module's **eight GET pages** renders its contracted template with its contracted context keys
**populated** (a key that exists but is empty proves nothing — L41), that every filter narrows, that
page 2 is real, that every create/edit POST lands in ``request.tenant``, and that each rung of the
four-verb ladder DOES what it says and SAYS what it did.

**Deliberately NOT repeated here** (each is asserted once, in the lane that owns it —
``test_finance_security.py``): the ``@tenant_admin_required`` gate on the four money verbs, the 405
on a GET to a POST-only route, the junk-filter-param and poisoned-decimal sweeps, cross-tenant
isolation on the two lists and the four reports, and the ladder's REFUSALS (L35). This lane owns the
positive half of those verbs plus the pagination and query-budget assertions.

Five things worth knowing before editing:

* **Page size is 15** (``crud_list``'s default; no 4.18 list overrides it), so a page-2 guard is
  invisible at fixture size — every pagination test below builds 21 rows on purpose (L9). The FOUR
  REPORTS are not paginated at all: they cap at ``ROW_CAP = 500`` and report ``truncated``, so
  ``?page=`` on a report is simply ignored.
* **The allocation base is the STOCK LEDGER, not the receipt's lines.**
  ``LandedCostVoucher.receipt_moves()`` reads ``StockMove(reference=<GRN number>,
  move_type="receipt", quantity > 0)``, which is why ``finance_receipt_a`` posts a real move through
  ``_helpers.seed_stock`` and ``finance_receipt_unposted_a`` deliberately does not.
* **``status`` is ``editable=False``** on ``LandedCostVoucher`` — every state below is reached by
  CALLING the verb (``allocate`` / ``accrue`` / ``draft_bill`` / ``cancel``), never by writing the
  column, so a test asserting a refusal is asserting the ladder rather than a fixture.
* **``LandedCostCharge`` carries no ``tenant`` column** and is resolved through
  ``voucher__tenant=request.tenant``; the charge routes therefore take the CHARGE's pk on edit/delete
  and the VOUCHER's pk on create.
* **Dates come from ``timezone.localdate()``**, never ``datetime.date.today()`` (L16) — the same
  basis ``DutyTariff.is_current``, ``DutyTariff.rate_for``, ``dutytariff_list``'s ``today`` statistic
  and ``draft_bill()``'s ``bill_date`` all read.

NAMING: every test is ``test_finance_*`` and every module-level helper/fixture ``_finance_*`` (the
hygiene guard in ``test_suite_hygiene.py`` parses this file and fails on any module-level name
defined twice).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone


# =================================================================================================
# Module-level helpers — all `_finance_` prefixed.
# =================================================================================================
def _finance_messages(response):
    """Every flashed message on the request that produced ``response``, as plain strings."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _finance_said(response, fragment):
    """True when any flashed message contains ``fragment`` (case-insensitive)."""
    return any(fragment.lower() in m.lower() for m in _finance_messages(response))


def _finance_templates(response):
    return [t.name for t in response.templates if t.name]


def _finance_query_count(client, url):
    """How many queries one GET of ``url`` costs.

    The N+1 assertion is that this number does not MOVE as the page fills up — a fixed ceiling alone
    only ever says "not too many today".
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)
    assert response.status_code == 200
    return len(captured.captured_queries)


def _finance_tariff_payload(**overrides):
    """A POST body ``DutyTariffForm`` accepts. ``number`` is auto (DTY-#####) and never posted."""
    payload = {
        "hs_code": "9403.20",
        "country_of_origin": "France",
        "description": "Other metal furniture",
        "duty_rate_pct": "3.250",
        "effective_from": timezone.localdate().isoformat(),
        "effective_to": "",
        "tax_code": "",
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


def _finance_voucher_payload(grn, party, **overrides):
    """A POST body ``LandedCostVoucherForm`` accepts. It carries NO money at all — every figure on a
    voucher is derived by ``recalc_totals()`` / ``allocate()``."""
    payload = {
        "goods_receipt": str(grn.pk),
        "party": str(party.pk),
        "shipment": "",
        "trade_document": "",
        "currency": "",
        "cost_date": timezone.localdate().isoformat(),
        "allocation_basis": "value",
        "notes": "Ocean freight on the container.",
    }
    payload.update(overrides)
    return payload


def _finance_charge_payload(**overrides):
    """A POST body ``LandedCostChargeForm`` accepts.

    ``is_recoverable`` is OMITTED to mean False (an unchecked checkbox posts nothing), blank
    ``allocation_basis`` means "inherit the voucher's", and a blank ``duty_rate_pct`` is coerced to
    ``Decimal("0")`` by ``clean_duty_rate_pct``.
    """
    payload = {
        "charge_type": "handling",
        "description": "Terminal handling",
        "party": "",
        "freight_invoice": "",
        "estimated_amount": "40.00",
        "actual_amount": "0",
        "allocation_basis": "",
        "gl_account": "",
        "tax_code": "",
        "hs_code": "",
        "country_of_origin": "",
        "duty_rate_pct": "",
        "capitalise_to_inventory": "on",
    }
    payload.update(overrides)
    return payload


def _finance_bulk_tariffs(tenant, count, start=0, country="Spain"):
    """``count`` extra duty tariffs — enough to push a 15-row page into a second one.

    ``hs_code`` varies so the ``(tenant, hs_code, country_of_origin, effective_from)``
    unique_together holds, and ``start`` lets a caller add a SECOND batch without colliding.
    """
    from apps.scm.models import DutyTariff
    today = timezone.localdate()
    return [DutyTariff.objects.create(
        tenant=tenant, hs_code=f"7318.{index:02d}", country_of_origin=country,
        description=f"Bulk classification {index:02d}", duty_rate_pct=Decimal("1.000"),
        effective_from=today - datetime.timedelta(days=index + 1), is_active=True)
        for index in range(start, start + count)]


def _finance_bulk_vouchers(tenant, grn, party, count, start=0):
    """``count`` DRAFT vouchers over one receipt — the shape that makes ``?page=2`` real.

    Nothing constrains (tenant, goods_receipt) to be unique, so one receipt carries them all; the
    cost dates step backwards so the ``["-cost_date", "-id"]`` order is a total one.
    """
    from apps.scm.models import LandedCostVoucher
    today = timezone.localdate()
    return [LandedCostVoucher.objects.create(
        tenant=tenant, goods_receipt=grn, party=party,
        cost_date=today - datetime.timedelta(days=index + 1),
        allocation_basis="value", notes=f"Bulk voucher {index:02d}")
        for index in range(start, start + count)]


@pytest.fixture
def _finance_rootless_client(db):
    """A logged-in SUPERUSER, i.e. ``request.tenant is None`` (multi-tenancy rule 1, by design).

    Every 4.18 report has to return an EMPTY report for this caller rather than 500 on a
    ``tenant=None`` filter or — far worse — render another workspace's figures. The root conftest
    has no tenant-less client, so this lives here.
    """
    from django.test import Client
    from apps.accounts.models import User
    user = User.objects.create_superuser(email="root@naverp.test", username="root",
                                         password="TestPass123!")
    client = Client()
    client.force_login(user)
    return client


# =================================================================================================
# 1. DutyTariff — the customs duty register
# =================================================================================================
@pytest.mark.django_db
class TestFinanceDutyTariffList:
    """200, the pinned context, both filters, search, page 2 and a flat query count."""

    def test_finance_dutytariff_list_renders_the_contracted_template_and_context(
            self, client_a, finance_duty_tariff_a, finance_duty_tariff_any_a):
        response = client_a.get(reverse("scm:dutytariff_list"))
        assert response.status_code == 200
        assert "scm/finance/dutytariff/list.html" in _finance_templates(response)

        ctx = response.context
        assert {obj.pk for obj in ctx["object_list"]} == {finance_duty_tariff_a.pk,
                                                          finance_duty_tariff_any_a.pk}
        assert ctx["page_obj"].paginator.count == 2
        assert ctx["q"] == ""
        # Populated, not merely present (L41): an empty <select> is a filter nobody can use.
        assert list(ctx["status_choices"]) == [("active", "Active"), ("inactive", "Inactive")]
        # A list of STRINGS, and the blank any-origin row is excluded on purpose.
        assert ctx["countries"] == ["Germany"]
        assert ctx["today"] == timezone.localdate()

    def test_finance_dutytariff_list_stats_carry_four_keys_over_the_whole_workspace(
            self, client_a, finance_duty_tariff_a, finance_duty_tariff_any_a):
        """``stats`` is workspace-wide, never the filtered page — a tile that moved as you typed
        would be a different number from the one the dashboard quotes."""
        from apps.scm.models import DutyTariff
        DutyTariff.objects.create(
            tenant=finance_duty_tariff_a.tenant, hs_code="8471.49", country_of_origin="Germany",
            duty_rate_pct=Decimal("4.000"),
            effective_from=timezone.localdate() - datetime.timedelta(days=5), is_active=False)

        stats = client_a.get(reverse("scm:dutytariff_list"), {"q": "zzz"}).context["stats"]
        assert set(stats) == {"total", "active", "inactive", "current"}
        assert stats["total"] == 3
        assert stats["active"] == 2 and stats["inactive"] == 1
        # Both active rows started in the past and are open-ended, so both are in force today.
        assert stats["current"] == 2

    def test_finance_dutytariff_list_current_stat_skips_a_window_that_has_closed(
            self, client_a, tenant_a):
        from apps.scm.models import DutyTariff
        today = timezone.localdate()
        DutyTariff.objects.create(
            tenant=tenant_a, hs_code="8501.10", country_of_origin="Italy",
            duty_rate_pct=Decimal("2.000"),
            effective_from=today - datetime.timedelta(days=40),
            effective_to=today - datetime.timedelta(days=5), is_active=True)
        stats = client_a.get(reverse("scm:dutytariff_list")).context["stats"]
        assert stats["total"] == 1 and stats["active"] == 1
        assert stats["current"] == 0, "a retired window must not count as in force"

    @pytest.mark.parametrize("term,expected_codes", [
        ("8471.30", {"8471.30", "8471.30"}),
        ("Germany", {"8471.30"}),
        ("fallback", {"8471.30"}),
    ])
    def test_finance_dutytariff_list_search_covers_code_country_and_description(
            self, client_a, finance_duty_tariff_a, finance_duty_tariff_any_a, term, expected_codes):
        response = client_a.get(reverse("scm:dutytariff_list"), {"q": term})
        assert response.status_code == 200
        assert response.context["q"] == term
        found = list(response.context["object_list"])
        assert found, f"?q={term} matched nothing"
        assert {obj.hs_code for obj in found} == expected_codes

    def test_finance_dutytariff_list_search_matches_the_auto_number(
            self, client_a, finance_duty_tariff_a):
        response = client_a.get(reverse("scm:dutytariff_list"), {"q": finance_duty_tariff_a.number})
        assert [obj.pk for obj in response.context["object_list"]] == [finance_duty_tariff_a.pk]

    @pytest.mark.parametrize("status,expected", [("active", 2), ("inactive", 1)])
    def test_finance_dutytariff_list_status_maps_onto_the_is_active_boolean(
            self, client_a, tenant_a, finance_duty_tariff_a, finance_duty_tariff_any_a,
            status, expected):
        """``?status=`` is a TRANSLATION, not a lookup — ``DutyTariff`` has no status column."""
        from apps.scm.models import DutyTariff
        DutyTariff.objects.create(
            tenant=tenant_a, hs_code="8471.49", country_of_origin="Germany",
            duty_rate_pct=Decimal("4.000"), effective_from=timezone.localdate(), is_active=False)
        response = client_a.get(reverse("scm:dutytariff_list"), {"status": status})
        assert response.status_code == 200
        assert len(response.context["object_list"]) == expected

    def test_finance_dutytariff_list_country_filter_narrows_by_string(
            self, client_a, finance_duty_tariff_a, finance_duty_tariff_any_a):
        response = client_a.get(reverse("scm:dutytariff_list"), {"country": "Germany"})
        assert response.status_code == 200
        assert [obj.pk for obj in response.context["object_list"]] == [finance_duty_tariff_a.pk]

    def test_finance_dutytariff_list_paginates_at_fifteen_with_a_real_page_two(
            self, client_a, tenant_a):
        _finance_bulk_tariffs(tenant_a, 21)
        page1 = client_a.get(reverse("scm:dutytariff_list"))
        assert len(page1.context["object_list"]) == 15
        assert page1.context["page_obj"].has_next() is True

        page2 = client_a.get(reverse("scm:dutytariff_list"), {"page": "2"})
        assert page2.status_code == 200
        assert len(page2.context["object_list"]) == 6
        assert page2.context["page_obj"].number == 2
        assert not ({o.pk for o in page1.context["object_list"]}
                    & {o.pk for o in page2.context["object_list"]})

    @pytest.mark.parametrize("page", ["999", "abc", "0", "-1", ""])
    def test_finance_dutytariff_list_page_past_the_end_or_junk_is_200(
            self, client_a, tenant_a, page):
        _finance_bulk_tariffs(tenant_a, 21)
        response = client_a.get(reverse("scm:dutytariff_list"), {"page": page})
        assert response.status_code == 200, f"?page={page} 500'd"
        assert response.context["object_list"], "a junk page must still render rows"

    def test_finance_dutytariff_list_is_flat_not_one_query_per_row(
            self, client_a, tenant_a, django_assert_max_num_queries):
        """``select_related("tax_code")`` is what keeps the ``TaxCode.__str__`` hop off the row loop."""
        url = reverse("scm:dutytariff_list")
        _finance_bulk_tariffs(tenant_a, 3, country="Portugal")
        few = _finance_query_count(client_a, url)

        _finance_bulk_tariffs(tenant_a, 18, start=50, country="Norway")
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 15
        assert _finance_query_count(client_a, url) == few, (
            "the duty tariff register queries per row — join the tax code instead")


@pytest.mark.django_db
class TestFinanceDutyTariffCrud:
    """create / detail / edit / delete, and what each one puts in the context."""

    def test_finance_dutytariff_create_get_renders_the_form_without_obj(self, client_a):
        response = client_a.get(reverse("scm:dutytariff_create"))
        assert response.status_code == 200
        assert "scm/finance/dutytariff/form.html" in _finance_templates(response)
        assert response.context["is_edit"] is False
        assert response.context["form"] is not None
        # `obj` DOES NOT EXIST on the create path — every {{ obj.* }} must sit inside {% if is_edit %}.
        assert response.context.get("obj") is None

    def test_finance_dutytariff_create_post_saves_into_the_request_tenant(
            self, client_a, tenant_a, tenant_b):
        from apps.scm.models import DutyTariff
        response = client_a.post(reverse("scm:dutytariff_create"), _finance_tariff_payload())
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:dutytariff_list")

        obj = DutyTariff.objects.get(hs_code="9403.20")
        assert obj.tenant_id == tenant_a.pk and obj.tenant_id != tenant_b.pk
        assert obj.number.startswith("DTY-") and len(obj.number) == 9
        assert obj.duty_rate_pct == Decimal("3.250")
        assert obj.effective_to is None and obj.is_active is True
        assert _finance_said(response, "Created successfully")

    def test_finance_dutytariff_create_post_upper_cases_and_strips_the_hs_code(
            self, client_a):
        from apps.scm.models import DutyTariff
        client_a.post(reverse("scm:dutytariff_create"),
                      _finance_tariff_payload(hs_code="  8471.30a  "))
        assert DutyTariff.objects.filter(hs_code="8471.30A").exists()

    def test_finance_dutytariff_create_post_with_an_inverted_window_is_200_with_errors(
            self, client_a):
        from apps.scm.models import DutyTariff
        today = timezone.localdate()
        response = client_a.post(reverse("scm:dutytariff_create"), _finance_tariff_payload(
            effective_from=today.isoformat(),
            effective_to=(today - datetime.timedelta(days=1)).isoformat()))
        assert response.status_code == 200
        assert "effective_to" in response.context["form"].errors
        assert not DutyTariff.objects.filter(hs_code="9403.20").exists()

    def test_finance_dutytariff_detail_carries_obj_and_today(
            self, client_a, finance_duty_tariff_a):
        response = client_a.get(reverse("scm:dutytariff_detail",
                                        args=[finance_duty_tariff_a.pk]))
        assert response.status_code == 200
        assert "scm/finance/dutytariff/detail.html" in _finance_templates(response)
        assert response.context["obj"].pk == finance_duty_tariff_a.pk
        assert response.context["today"] == timezone.localdate()
        assert response.context["obj"].is_current is True

    def test_finance_dutytariff_edit_get_carries_form_obj_and_is_edit(
            self, client_a, finance_duty_tariff_a):
        response = client_a.get(reverse("scm:dutytariff_edit", args=[finance_duty_tariff_a.pk]))
        assert response.status_code == 200
        assert "scm/finance/dutytariff/form.html" in _finance_templates(response)
        assert response.context["is_edit"] is True
        assert response.context["obj"].pk == finance_duty_tariff_a.pk
        assert response.context["form"].instance.pk == finance_duty_tariff_a.pk

    def test_finance_dutytariff_edit_post_round_trips_and_redirects_to_the_detail(
            self, client_a, finance_duty_tariff_a):
        url = reverse("scm:dutytariff_edit", args=[finance_duty_tariff_a.pk])
        response = client_a.post(url, _finance_tariff_payload(
            hs_code=finance_duty_tariff_a.hs_code,
            country_of_origin=finance_duty_tariff_a.country_of_origin,
            description="Re-classified",
            duty_rate_pct="4.750",
            effective_from=finance_duty_tariff_a.effective_from.isoformat()))
        assert response.status_code == 302
        # The EDIT path lands on the detail page, not the list.
        assert response["Location"] == reverse("scm:dutytariff_detail",
                                               args=[finance_duty_tariff_a.pk])
        finance_duty_tariff_a.refresh_from_db()
        assert finance_duty_tariff_a.duty_rate_pct == Decimal("4.750")
        assert finance_duty_tariff_a.description == "Re-classified"

    def test_finance_dutytariff_edit_post_never_mints_a_second_number(
            self, client_a, finance_duty_tariff_a):
        original = finance_duty_tariff_a.number
        client_a.post(reverse("scm:dutytariff_edit", args=[finance_duty_tariff_a.pk]),
                      _finance_tariff_payload(
                          hs_code=finance_duty_tariff_a.hs_code,
                          country_of_origin=finance_duty_tariff_a.country_of_origin,
                          effective_from=finance_duty_tariff_a.effective_from.isoformat(),
                          number="DTY-99999"))
        finance_duty_tariff_a.refresh_from_db()
        assert finance_duty_tariff_a.number == original

    def test_finance_dutytariff_delete_post_removes_the_row_and_steers_to_is_active(
            self, client_a, finance_duty_tariff_a):
        from apps.scm.models import DutyTariff
        response = client_a.post(reverse("scm:dutytariff_delete",
                                         args=[finance_duty_tariff_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:dutytariff_list")
        assert not DutyTariff.objects.filter(pk=finance_duty_tariff_a.pk).exists()
        assert _finance_said(response, "Deleted successfully")
        assert _finance_said(response, "clear its Active box instead")


# =================================================================================================
# 2. LandedCostVoucher — the register
# =================================================================================================
@pytest.mark.django_db
class TestFinanceLandedCostVoucherList:

    def test_finance_voucher_list_renders_the_contracted_template_and_context(
            self, client_a, finance_voucher_a):
        response = client_a.get(reverse("scm:landedcostvoucher_list"))
        assert response.status_code == 200
        assert "scm/finance/landedcostvoucher/list.html" in _finance_templates(response)

        ctx = response.context
        assert [obj.pk for obj in ctx["object_list"]] == [finance_voucher_a.pk]
        assert ctx["page_obj"].paginator.count == 1
        assert ctx["q"] == ""
        assert ("allocated", "Allocated") in list(ctx["status_choices"])
        assert ("cancelled", "Cancelled") in list(ctx["status_choices"])
        assert ("equal", "Equal") in list(ctx["basis_choices"])
        assert len(list(ctx["basis_choices"])) == 5, "five bases, no 'manual' sixth"
        assert ("port_fees", "Port & Terminal Fees") in list(ctx["charge_type_choices"])
        assert len(list(ctx["charge_type_choices"])) == 11
        # `parties` is the payees IN USE, not the whole party book.
        assert [p.pk for p in ctx["parties"]] == [finance_voucher_a.party_id]

    def test_finance_voucher_list_parties_dropdown_omits_a_party_never_used_as_a_payee(
            self, client_a, finance_voucher_a, vendor_a):
        parties = client_a.get(reverse("scm:landedcostvoucher_list")).context["parties"]
        assert vendor_a.pk not in {p.pk for p in parties}

    def test_finance_voucher_list_stats_carry_all_ten_keys_with_real_figures(
            self, client_a, finance_allocated_voucher_a):
        stats = client_a.get(reverse("scm:landedcostvoucher_list")).context["stats"]
        assert set(stats) == {"total", "draft", "allocated", "accrued", "reconciled", "cancelled",
                              "sum_actual", "sum_variance", "actual_total", "variance_total"}
        assert stats["total"] == 1 and stats["allocated"] == 1 and stats["draft"] == 0
        # The charge is estimated 100.00 with no actual yet, so actual is 0 and variance is -100.
        assert stats["actual_total"] == Decimal("0.00")
        assert stats["variance_total"] == Decimal("-100.00")
        assert stats["actual_total"] == stats["sum_actual"]
        assert stats["variance_total"] == stats["sum_variance"]

    @pytest.mark.parametrize("field", ["number", "grn", "party", "notes"])
    def test_finance_voucher_list_search_covers_all_four_declared_fields(
            self, client_a, finance_voucher_a, field):
        term = {
            "number": finance_voucher_a.number,
            "grn": finance_voucher_a.goods_receipt.number,
            "party": "Acme Supplies",
            "notes": "January container",
        }[field]
        response = client_a.get(reverse("scm:landedcostvoucher_list"), {"q": term})
        assert response.status_code == 200
        assert [obj.pk for obj in response.context["object_list"]] == [finance_voucher_a.pk], (
            f"search over {field} ({term!r}) matched nothing")

    def test_finance_voucher_list_status_filter_narrows(
            self, client_a, finance_allocated_voucher_a, tenant_a, finance_receipt_a, supplier_a):
        _finance_bulk_vouchers(tenant_a, finance_receipt_a, supplier_a, 2)
        allocated = client_a.get(reverse("scm:landedcostvoucher_list"), {"status": "allocated"})
        assert [o.pk for o in allocated.context["object_list"]] == [finance_allocated_voucher_a.pk]
        draft = client_a.get(reverse("scm:landedcostvoucher_list"), {"status": "draft"})
        assert len(draft.context["object_list"]) == 2

    def test_finance_voucher_list_basis_filter_narrows(
            self, client_a, finance_voucher_a, finance_voucher_multi_a):
        response = client_a.get(reverse("scm:landedcostvoucher_list"), {"basis": "value"})
        assert response.status_code == 200
        # Both fixtures declare "value" on the voucher; the "equal" override lives on the CHARGE.
        assert len(response.context["object_list"]) == 2
        empty = client_a.get(reverse("scm:landedcostvoucher_list"), {"basis": "weight"})
        assert list(empty.context["object_list"]) == []

    def test_finance_voucher_list_party_filter_narrows_by_pk(
            self, client_a, tenant_a, finance_voucher_a, finance_receipt_a, vendor_a):
        other = _finance_bulk_vouchers(tenant_a, finance_receipt_a, vendor_a, 1)[0]
        response = client_a.get(reverse("scm:landedcostvoucher_list"),
                                {"party": str(vendor_a.pk)})
        assert [obj.pk for obj in response.context["object_list"]] == [other.pk]

    def test_finance_voucher_list_paginates_at_fifteen_with_a_real_page_two(
            self, client_a, tenant_a, finance_receipt_a, supplier_a):
        _finance_bulk_vouchers(tenant_a, finance_receipt_a, supplier_a, 21)
        page1 = client_a.get(reverse("scm:landedcostvoucher_list"))
        assert len(page1.context["object_list"]) == 15
        assert page1.context["page_obj"].has_next() is True

        page2 = client_a.get(reverse("scm:landedcostvoucher_list"), {"page": "2"})
        assert page2.status_code == 200
        assert len(page2.context["object_list"]) == 6
        assert page2.context["page_obj"].number == 2
        assert not ({o.pk for o in page1.context["object_list"]}
                    & {o.pk for o in page2.context["object_list"]})

    @pytest.mark.parametrize("page", ["999", "abc", "0", "-1", ""])
    def test_finance_voucher_list_page_past_the_end_or_junk_is_200(
            self, client_a, tenant_a, finance_receipt_a, supplier_a, page):
        _finance_bulk_vouchers(tenant_a, finance_receipt_a, supplier_a, 21)
        response = client_a.get(reverse("scm:landedcostvoucher_list"), {"page": page})
        assert response.status_code == 200, f"?page={page} 500'd"
        assert response.context["object_list"]

    def test_finance_voucher_list_is_flat_not_one_query_per_row(
            self, client_a, tenant_a, finance_receipt_a, supplier_a, vendor_a,
            django_assert_max_num_queries):
        """``__str__`` walks ``party.name`` and every row renders the receipt, shipment, currency and
        bill — an unjoined queryset costs four queries per row on a full page."""
        url = reverse("scm:landedcostvoucher_list")
        _finance_bulk_vouchers(tenant_a, finance_receipt_a, supplier_a, 3)
        few = _finance_query_count(client_a, url)

        _finance_bulk_vouchers(tenant_a, finance_receipt_a, vendor_a, 18, start=10)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["object_list"]) == 15
        assert _finance_query_count(client_a, url) == few, (
            "the voucher register queries per row — select_related the five FKs the rows render")


@pytest.mark.django_db
class TestFinanceLandedCostVoucherCrud:

    def test_finance_voucher_create_get_renders_the_form(self, client_a, finance_receipt_a,
                                                         supplier_a):
        response = client_a.get(reverse("scm:landedcostvoucher_create"))
        assert response.status_code == 200
        assert "scm/finance/landedcostvoucher/form.html" in _finance_templates(response)
        assert response.context["is_edit"] is False
        # The receipt dropdown offers RECEIVED receipts only — a draft one has posted nothing.
        offered = response.context["form"].fields["goods_receipt"].queryset
        assert finance_receipt_a.pk in {g.pk for g in offered}

    def test_finance_voucher_create_get_hides_a_draft_receipt(
            self, client_a, goods_receipt_a, finance_receipt_a):
        offered = (client_a.get(reverse("scm:landedcostvoucher_create"))
                   .context["form"].fields["goods_receipt"].queryset)
        assert goods_receipt_a.status == "draft"
        assert goods_receipt_a.pk not in {g.pk for g in offered}

    def test_finance_voucher_create_post_saves_into_the_request_tenant(
            self, client_a, tenant_a, finance_receipt_a, supplier_a):
        from apps.scm.models import LandedCostVoucher
        response = client_a.post(reverse("scm:landedcostvoucher_create"),
                                 _finance_voucher_payload(finance_receipt_a, supplier_a))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:landedcostvoucher_list")

        obj = LandedCostVoucher.objects.get(goods_receipt=finance_receipt_a)
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("LC-") and len(obj.number) == 8
        # Every derived column starts where recalc_totals()/allocate() left it — at nothing.
        assert obj.status == "draft" and obj.bill_id is None
        assert obj.estimated_total == Decimal("0.00") and obj.allocated_total == Decimal("0.00")
        assert obj.variance_pct is None and obj.accrued_at is None

    def test_finance_voucher_create_post_without_a_cost_date_is_200_with_errors(
            self, client_a, finance_receipt_a, supplier_a):
        from apps.scm.models import LandedCostVoucher
        response = client_a.post(reverse("scm:landedcostvoucher_create"),
                                 _finance_voucher_payload(finance_receipt_a, supplier_a,
                                                          cost_date=""))
        assert response.status_code == 200
        assert "cost_date" in response.context["form"].errors
        assert not LandedCostVoucher.objects.filter(goods_receipt=finance_receipt_a).exists()

    def test_finance_voucher_detail_carries_every_contracted_key_populated(
            self, client_a, finance_allocated_voucher_a, finance_charge_a):
        response = client_a.get(reverse("scm:landedcostvoucher_detail",
                                        args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 200
        assert "scm/finance/landedcostvoucher/detail.html" in _finance_templates(response)

        ctx = response.context
        assert ctx["obj"].pk == finance_allocated_voucher_a.pk
        assert [c.pk for c in ctx["charges"]] == [finance_charge_a.pk]
        assert ctx["charge_count"] == 1
        assert ctx["allocation_count"] == 1 and len(ctx["allocations"]) == 1
        assert ctx["receipt_move_count"] == 1 and len(ctx["receipt_moves"]) == 1
        assert [c.pk for c in ctx["billable_charges"]] == [finance_charge_a.pk]
        assert ctx["billable_total"] == Decimal("100.00")
        assert list(ctx["excluded_charges"]) == [] and ctx["excluded_total"] == Decimal("0.00")
        assert ctx["bill"] is None
        assert ctx["grn"].pk == finance_allocated_voucher_a.goods_receipt_id

        groups = ctx["allocation_groups"]
        assert len(groups) == 1
        group = groups[0]
        assert group["item"].sku == "WIDGET-1"
        assert group["quantity"] == Decimal("10.0000")
        assert group["allocated_amount"] == Decimal("100.00")
        assert group["unit_cost_uplift"] == Decimal("10.0000")
        assert group["basis_used"] == "value"
        assert len(group["rows"]) == 1

    def test_finance_voucher_detail_gates_are_the_status_half_only(
            self, client_a, finance_allocated_voucher_a):
        ctx = client_a.get(reverse("scm:landedcostvoucher_detail",
                                   args=[finance_allocated_voucher_a.pk])).context
        assert ctx["can_edit"] is False and ctx["can_delete"] is False
        assert ctx["can_add_charge"] is False
        assert ctx["can_allocate"] is True
        assert ctx["can_accrue"] is True
        assert ctx["can_draft_bill"] is True
        assert ctx["can_cancel"] is True

    def test_finance_voucher_detail_gates_on_a_bare_draft(self, client_a, finance_voucher_a):
        ctx = client_a.get(reverse("scm:landedcostvoucher_detail",
                                   args=[finance_voucher_a.pk])).context
        assert ctx["can_edit"] is True and ctx["can_delete"] is True
        assert ctx["can_add_charge"] is True
        assert ctx["can_allocate"] is True
        assert ctx["can_accrue"] is False, "a draft has nothing to accrue"
        # Nothing billable on a voucher with no charges at all.
        assert ctx["can_draft_bill"] is False
        assert ctx["charge_count"] == 0 and ctx["allocation_count"] == 0
        # The allocation BASE still renders — that is what the empty state explains.
        assert ctx["receipt_move_count"] == 1

    def test_finance_voucher_detail_excludes_a_charge_naming_another_vendor(
            self, client_a, finance_voucher_a, vendor_a, gl_expense):
        from apps.scm.models import LandedCostCharge
        LandedCostCharge.objects.create(
            voucher=finance_voucher_a, charge_type="brokerage", description="Broker fee",
            estimated_amount=Decimal("25.00"), party=vendor_a, gl_account=gl_expense)
        ctx = client_a.get(reverse("scm:landedcostvoucher_detail",
                                   args=[finance_voucher_a.pk])).context
        assert [c.description for c in ctx["excluded_charges"]] == ["Broker fee"]
        assert ctx["excluded_total"] == Decimal("25.00")
        assert list(ctx["billable_charges"]) == []
        assert ctx["billable_total"] == Decimal("0.00")

    def test_finance_voucher_edit_get_carries_form_obj_and_is_edit(
            self, client_a, finance_voucher_a):
        response = client_a.get(reverse("scm:landedcostvoucher_edit", args=[finance_voucher_a.pk]))
        assert response.status_code == 200
        assert "scm/finance/landedcostvoucher/form.html" in _finance_templates(response)
        assert response.context["is_edit"] is True
        assert response.context["obj"].pk == finance_voucher_a.pk

    def test_finance_voucher_edit_post_round_trips_to_the_detail_page(
            self, client_a, finance_voucher_a, finance_receipt_a, vendor_a, shipment_a):
        url = reverse("scm:landedcostvoucher_edit", args=[finance_voucher_a.pk])
        response = client_a.post(url, _finance_voucher_payload(
            finance_receipt_a, vendor_a, shipment=str(shipment_a.pk),
            allocation_basis="quantity", notes="Re-assigned to the vendor."))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:landedcostvoucher_detail",
                                               args=[finance_voucher_a.pk])
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.party_id == vendor_a.pk
        assert finance_voucher_a.allocation_basis == "quantity"
        assert finance_voucher_a.notes == "Re-assigned to the vendor."

    def test_finance_voucher_edit_refuses_an_allocated_voucher_before_the_form(
            self, client_a, finance_allocated_voucher_a, finance_receipt_a, vendor_a):
        url = reverse("scm:landedcostvoucher_edit", args=[finance_allocated_voucher_a.pk])
        get_response = client_a.get(url)
        assert get_response.status_code == 302
        assert get_response["Location"] == reverse("scm:landedcostvoucher_detail",
                                                   args=[finance_allocated_voucher_a.pk])
        assert _finance_said(get_response, "can no longer be edited")

        post_response = client_a.post(url, _finance_voucher_payload(finance_receipt_a, vendor_a))
        assert post_response.status_code == 302
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.party_id != vendor_a.pk, (
            "an allocated voucher must not be re-pointed at a different payee")

    def test_finance_voucher_edit_refuses_a_billed_voucher_naming_the_bill(
            self, client_a, finance_recoverable_voucher_a):
        finance_recoverable_voucher_a.draft_bill()
        finance_recoverable_voucher_a.refresh_from_db()
        response = client_a.get(reverse("scm:landedcostvoucher_edit",
                                        args=[finance_recoverable_voucher_a.pk]))
        assert response.status_code == 302
        assert _finance_said(response, "has been billed and can no longer be edited")

    def test_finance_voucher_delete_post_removes_a_draft(self, client_a, finance_voucher_a):
        from apps.scm.models import LandedCostVoucher
        response = client_a.post(reverse("scm:landedcostvoucher_delete",
                                         args=[finance_voucher_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:landedcostvoucher_list")
        assert not LandedCostVoucher.objects.filter(pk=finance_voucher_a.pk).exists()


# =================================================================================================
# 3. The verb ladder — allocate / accrue / draft bill / cancel
# =================================================================================================
@pytest.mark.django_db
class TestFinanceVoucherVerbLadder:
    """What each rung DOES and SAYS on the happy path — the state it writes, the message it flashes
    and the fact that pressing it twice is safe.

    The other half of every verb — POST-only (405 on a GET), ``@tenant_admin_required`` (403 for a
    member), and the refusal of each bad transition (L35) — lives in ``test_finance_security.py``
    (``TestFinanceAdminGates`` / ``TestFinancePostOnlyRoutes`` / ``TestFinanceLadderPrerequisites``),
    which pairs every refusal with its positive case.
    """

    def test_finance_allocate_post_lands_the_cost_on_the_receipt_units(
            self, client_a, finance_voucher_a, finance_charge_a, item_a):
        from apps.scm.models import LandedCostAllocation
        before = item_a.average_cost
        response = client_a.post(reverse("scm:landedcostvoucher_allocate",
                                         args=[finance_voucher_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:landedcostvoucher_detail",
                                               args=[finance_voucher_a.pk])

        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "allocated"
        assert finance_voucher_a.allocated_total == Decimal("100.00")
        rows = list(LandedCostAllocation.objects.filter(voucher=finance_voucher_a))
        assert len(rows) == 1
        assert rows[0].allocated_amount == Decimal("100.00")
        assert rows[0].unit_cost_uplift == Decimal("10.0000")
        item_a.refresh_from_db()
        assert item_a.average_cost > before

    def test_finance_allocate_post_message_names_rows_amount_and_charges(
            self, client_a, finance_voucher_a, finance_charge_a):
        response = client_a.post(reverse("scm:landedcostvoucher_allocate",
                                         args=[finance_voucher_a.pk]))
        finance_voucher_a.refresh_from_db()
        assert _finance_said(response, f"{finance_voucher_a.number} allocated")
        assert _finance_said(response, "across 1 lines from 1 charges")

    def test_finance_allocate_post_reports_a_basis_fallback(
            self, client_a, finance_voucher_a, gl_expense):
        """A weight-basis charge over items nobody has weighed falls back to quantity, and the
        message DISCLOSES it — the one outcome here that looks right and is not what was asked for."""
        from apps.scm.models import LandedCostCharge
        LandedCostCharge.objects.create(
            voucher=finance_voucher_a, charge_type="freight", description="Weighted freight",
            estimated_amount=Decimal("60.00"), allocation_basis="weight", gl_account=gl_expense)
        response = client_a.post(reverse("scm:landedcostvoucher_allocate",
                                         args=[finance_voucher_a.pk]))
        assert _finance_said(response, "Basis fell back: By Weight → By Quantity")

    def test_finance_allocate_post_is_idempotent(
            self, client_a, finance_voucher_a, finance_charge_a, item_a):
        from apps.scm.models import LandedCostAllocation
        url = reverse("scm:landedcostvoucher_allocate", args=[finance_voucher_a.pk])
        client_a.post(url)
        item_a.refresh_from_db()
        once = item_a.average_cost
        client_a.post(url)
        item_a.refresh_from_db()
        assert item_a.average_cost == once, "re-allocating must reverse its own roll first"
        assert LandedCostAllocation.objects.filter(voucher=finance_voucher_a).count() == 1

    def test_finance_accrue_post_stamps_accrued_at(self, client_a, finance_allocated_voucher_a):
        response = client_a.post(reverse("scm:landedcostvoucher_accrue",
                                         args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 302
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "accrued"
        assert finance_allocated_voucher_a.accrued_at is not None
        assert _finance_said(response, "awaiting the vendor bill")

    def test_finance_draft_bill_post_raises_a_draft_bill_and_no_journal_entry(
            self, client_a, finance_allocated_voucher_a):
        from apps.accounting.models import JournalEntry
        response = client_a.post(reverse("scm:landedcostvoucher_draft_bill",
                                         args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 302
        finance_allocated_voucher_a.refresh_from_db()
        bill = finance_allocated_voucher_a.bill
        assert bill is not None and bill.status == "draft"
        assert bill.party_id == finance_allocated_voucher_a.party_id
        assert bill.bill_date == timezone.localdate()
        assert finance_allocated_voucher_a.status == "reconciled"
        assert _finance_said(response, f"Drafted bill {bill.number}")
        assert _finance_said(response, "Approve it in Accounts Payable")
        # Ruling 1: SCM stops at a DRAFT accounting.Bill and posts nothing to the GL.
        assert not JournalEntry.objects.filter(
            tenant=finance_allocated_voucher_a.tenant).exists()

    def test_finance_draft_bill_post_is_idempotent_and_writes_nothing_the_second_time(
            self, client_a, finance_allocated_voucher_a):
        from apps.accounting.models import Bill
        url = reverse("scm:landedcostvoucher_draft_bill", args=[finance_allocated_voucher_a.pk])
        client_a.post(url)
        finance_allocated_voucher_a.refresh_from_db()
        first = finance_allocated_voucher_a.bill_id

        again = client_a.post(url)
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.bill_id == first
        assert Bill.objects.filter(tenant=finance_allocated_voucher_a.tenant).count() == 1
        assert _finance_said(again, "is already billed as")

    def test_finance_draft_bill_post_bills_a_purely_recoverable_voucher_from_draft(
            self, client_a, finance_recoverable_voucher_a):
        """The deliberate relaxation: a voucher ``allocate()`` refuses must still reach AP."""
        response = client_a.post(reverse("scm:landedcostvoucher_draft_bill",
                                         args=[finance_recoverable_voucher_a.pk]))
        assert response.status_code == 302
        finance_recoverable_voucher_a.refresh_from_db()
        assert finance_recoverable_voucher_a.bill is not None
        assert finance_recoverable_voucher_a.status == "reconciled"

    def test_finance_draft_bill_post_reports_the_excluded_vendor_count(
            self, client_a, finance_allocated_voucher_a, vendor_a, gl_expense):
        from apps.scm.models import LandedCostCharge
        LandedCostCharge.objects.create(
            voucher=finance_allocated_voucher_a, charge_type="brokerage",
            description="Broker fee", estimated_amount=Decimal("25.00"), party=vendor_a,
            gl_account=gl_expense)
        response = client_a.post(reverse("scm:landedcostvoucher_draft_bill",
                                         args=[finance_allocated_voucher_a.pk]))
        assert _finance_said(response, "1 charge(s) naming a different vendor were excluded")

    def test_finance_cancel_post_reverses_the_allocation_and_warns(
            self, client_a, finance_allocated_voucher_a, item_a):
        from apps.scm.models import LandedCostAllocation
        item_a.refresh_from_db()
        uplifted = item_a.average_cost

        response = client_a.post(reverse("scm:landedcostvoucher_cancel",
                                         args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 302
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "cancelled"
        assert finance_allocated_voucher_a.allocated_total == Decimal("0.00")
        assert not LandedCostAllocation.objects.filter(
            voucher=finance_allocated_voucher_a).exists()
        item_a.refresh_from_db()
        assert item_a.average_cost < uplifted, "cancel must roll the uplift back OUT"
        assert _finance_said(response, "rolled back out of the affected items")


# =================================================================================================
# 4. LandedCostCharge — the tenant-less child whose parent comes from the ROUTE
# =================================================================================================
@pytest.mark.django_db
class TestFinanceLandedCostCharge:

    def test_finance_charge_create_get_carries_the_voucher_and_the_form(
            self, client_a, finance_voucher_a):
        response = client_a.get(reverse("scm:landedcostcharge_create",
                                        args=[finance_voucher_a.pk]))
        assert response.status_code == 200
        assert "scm/finance/landedcostcharge/form.html" in _finance_templates(response)
        assert response.context["is_edit"] is False
        assert response.context["voucher"].pk == finance_voucher_a.pk
        # `voucher` is NOT a form field — the parent comes from the URL (a security decision).
        assert "voucher" not in response.context["form"].fields

    def test_finance_charge_create_get_offers_the_inherit_basis_option(
            self, client_a, finance_voucher_a):
        field = (client_a.get(reverse("scm:landedcostcharge_create",
                                      args=[finance_voucher_a.pk]))
                 .context["form"].fields["allocation_basis"])
        assert field.required is False
        assert list(field.choices)[0] == ("", "Inherit the voucher's basis")

    def test_finance_charge_create_post_attaches_to_the_route_voucher_and_re_totals_it(
            self, client_a, finance_voucher_a, gl_expense):
        response = client_a.post(reverse("scm:landedcostcharge_create",
                                         args=[finance_voucher_a.pk]),
                                 _finance_charge_payload(gl_account=str(gl_expense.pk)))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:landedcostvoucher_detail",
                                               args=[finance_voucher_a.pk])

        charge = finance_voucher_a.charges.get()
        assert charge.voucher_id == finance_voucher_a.pk
        assert charge.estimated_amount == Decimal("40.00")
        assert charge.duty_rate_pct == Decimal("0"), "a blank rate is coerced to zero, not NULL"
        assert charge.allocation_basis == "", "blank INHERITS the voucher's basis"
        assert charge.effective_basis == "value"
        assert charge.is_recoverable is False and charge.capitalise_to_inventory is True
        # recalc_totals() runs in the SAME transaction as the insert.
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.estimated_total == Decimal("40.00")
        assert finance_voucher_a.variance_amount == Decimal("-40.00")
        assert _finance_said(response, f"to {finance_voucher_a.number}")

    def test_finance_charge_create_post_defaults_the_duty_rate_from_the_tariff(
            self, client_a, finance_voucher_a, finance_duty_tariff_a, finance_duty_tariff_any_a,
            gl_expense):
        """The request-path caller of ``DutyTariff.rate_for()`` — a named origin beats the blank
        any-origin row, so 2.500 rather than the catch-all's 5.000."""
        client_a.post(reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
                      _finance_charge_payload(charge_type="duty", description="Import duty",
                                              hs_code="8471.30", country_of_origin="Germany",
                                              duty_rate_pct="", gl_account=str(gl_expense.pk)))
        charge = finance_voucher_a.charges.get()
        assert charge.duty_rate_pct == Decimal("2.500")

    def test_finance_charge_create_post_never_overwrites_a_typed_duty_rate(
            self, client_a, finance_voucher_a, finance_duty_tariff_a, gl_expense):
        client_a.post(reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
                      _finance_charge_payload(charge_type="duty", hs_code="8471.30",
                                              country_of_origin="Germany", duty_rate_pct="7.125",
                                              gl_account=str(gl_expense.pk)))
        assert finance_voucher_a.charges.get().duty_rate_pct == Decimal("7.125")

    def test_finance_charge_create_post_rejects_a_duty_rate_on_a_non_duty_charge(
            self, client_a, finance_voucher_a, gl_expense):
        response = client_a.post(reverse("scm:landedcostcharge_create",
                                         args=[finance_voucher_a.pk]),
                                 _finance_charge_payload(charge_type="freight",
                                                         duty_rate_pct="2.500",
                                                         gl_account=str(gl_expense.pk)))
        assert response.status_code == 200
        assert "duty_rate_pct" in response.context["form"].errors
        assert finance_voucher_a.charges.count() == 0

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "abc", "-10.00",
                                       "999999999999999999.00", "1e400"])
    def test_finance_charge_create_post_junk_money_is_200_with_errors_never_a_500(
            self, client_a, finance_voucher_a, gl_expense, value):
        """Every one of these has 500'd a hand-parsed decimal somewhere in this repo before."""
        response = client_a.post(reverse("scm:landedcostcharge_create",
                                         args=[finance_voucher_a.pk]),
                                 _finance_charge_payload(estimated_amount=value,
                                                         gl_account=str(gl_expense.pk)))
        assert response.status_code == 200, f"estimated_amount={value!r} 500'd the charge form"
        assert "estimated_amount" in response.context["form"].errors
        assert finance_voucher_a.charges.count() == 0

    def test_finance_charge_edit_get_takes_the_charge_pk_and_carries_both_objects(
            self, client_a, finance_voucher_a, finance_charge_a):
        response = client_a.get(reverse("scm:landedcostcharge_edit", args=[finance_charge_a.pk]))
        assert response.status_code == 200
        assert "scm/finance/landedcostcharge/form.html" in _finance_templates(response)
        assert response.context["is_edit"] is True
        assert response.context["obj"].pk == finance_charge_a.pk
        assert response.context["voucher"].pk == finance_voucher_a.pk

    def test_finance_charge_edit_post_re_totals_the_parent(
            self, client_a, finance_voucher_a, finance_charge_a, gl_expense):
        response = client_a.post(reverse("scm:landedcostcharge_edit", args=[finance_charge_a.pk]),
                                 _finance_charge_payload(charge_type="freight",
                                                         description="Ocean freight",
                                                         estimated_amount="100.00",
                                                         actual_amount="130.00",
                                                         gl_account=str(gl_expense.pk)))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:landedcostvoucher_detail",
                                               args=[finance_voucher_a.pk])
        finance_charge_a.refresh_from_db()
        assert finance_charge_a.actual_amount == Decimal("130.00")
        assert finance_charge_a.allocatable_amount == Decimal("130.00")
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.actual_total == Decimal("130.00")
        assert finance_voucher_a.variance_amount == Decimal("30.00")
        assert finance_voucher_a.variance_pct == Decimal("30.00")

    def test_finance_charge_delete_post_removes_it_and_re_totals(
            self, client_a, finance_voucher_a, finance_charge_a):
        from apps.scm.models import LandedCostCharge
        response = client_a.post(reverse("scm:landedcostcharge_delete",
                                         args=[finance_charge_a.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("scm:landedcostvoucher_detail",
                                               args=[finance_voucher_a.pk])
        assert not LandedCostCharge.objects.filter(pk=finance_charge_a.pk).exists()
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.estimated_total == Decimal("0.00")
        assert finance_voucher_a.variance_pct is None
        assert _finance_said(response, f"from {finance_voucher_a.number}")


# =================================================================================================
# 5. The four READ-ONLY reports
# =================================================================================================
@pytest.mark.django_db
class TestFinancePayablesReport:
    """``scm:finance_payables`` — a UNION OF POINTERS at ``accounting.Bill``, never a fourth ledger."""

    def test_finance_payables_renders_the_contracted_template_and_context(
            self, client_a, finance_voucher_a, finance_charge_a, freight_invoice_a):
        response = client_a.get(reverse("scm:finance_payables"))
        assert response.status_code == 200
        assert "scm/finance/payables.html" in _finance_templates(response)

        ctx = response.context
        assert ctx["row_cap"] == 500 and ctx["truncated"] is False
        assert list(ctx["source_choices"]) == [("grn", "Goods Receipts"),
                                               ("freight", "Freight Invoices"),
                                               ("landed", "Landed Cost Vouchers")]
        assert ("draft", "Draft") in list(ctx["status_choices"])
        assert ("void", "Void") in list(ctx["status_choices"])

        sources = {row["source"] for row in ctx["rows"]}
        assert sources == {"grn", "freight", "landed"}, "all three sources must contribute"
        assert set(ctx["totals"]) == {"count", "amount", "billed", "unbilled"}
        assert ctx["totals"]["count"] == len(ctx["rows"])
        # Nothing is billed yet, so every penny is unbilled — and never invented as a payable.
        assert ctx["totals"]["billed"] == Decimal("0.00")
        assert ctx["totals"]["unbilled"] == ctx["totals"]["amount"]

    def test_finance_payables_grn_row_carries_a_reversed_url_and_a_string_party(
            self, client_a, finance_voucher_a):
        rows = client_a.get(reverse("scm:finance_payables")).context["rows"]
        grn_row = next(r for r in rows if r["source"] == "grn")
        assert set(grn_row) == {"source", "source_label", "document", "number", "url", "party",
                                "bill", "bill_number", "bill_status", "bill_status_label",
                                "amount", "variance", "match_status", "match_status_label"}
        assert grn_row["url"] == reverse(
            "scm:goodsreceipt_detail", args=[finance_voucher_a.goods_receipt_id])
        assert isinstance(grn_row["party"], str) and grn_row["party"] == "Acme Supplies Ltd"
        assert grn_row["amount"] == Decimal("150.00")
        # None, NOT 0.00: an unbilled receipt has no variance yet.
        assert grn_row["variance"] is None
        assert grn_row["bill"] is None and grn_row["bill_number"] == ""

    def test_finance_payables_landed_row_points_at_the_voucher_detail(
            self, client_a, finance_voucher_a, finance_charge_a):
        rows = client_a.get(reverse("scm:finance_payables")).context["rows"]
        landed = next(r for r in rows if r["source"] == "landed")
        assert landed["number"] == finance_voucher_a.number
        assert landed["url"] == reverse("scm:landedcostvoucher_detail",
                                        args=[finance_voucher_a.pk])
        assert landed["match_status"] == "draft"
        assert landed["match_status_label"] == "Draft"

    def test_finance_payables_shows_the_bill_once_a_voucher_is_billed(
            self, client_a, finance_recoverable_voucher_a):
        bill = finance_recoverable_voucher_a.draft_bill()
        rows = client_a.get(reverse("scm:finance_payables")).context["rows"]
        landed = next(r for r in rows if r["number"] == finance_recoverable_voucher_a.number)
        assert landed["bill_number"] == bill.number
        assert landed["bill_status"] == "draft" and landed["bill_status_label"] == "Draft"

    @pytest.mark.parametrize("source", ["grn", "freight", "landed"])
    def test_finance_payables_source_filter_keeps_one_source(
            self, client_a, finance_voucher_a, freight_invoice_a, source):
        response = client_a.get(reverse("scm:finance_payables"), {"source": source})
        assert response.status_code == 200
        assert {row["source"] for row in response.context["rows"]} == {source}

    def test_finance_payables_search_narrows_by_document_number(
            self, client_a, finance_voucher_a, freight_invoice_a):
        response = client_a.get(reverse("scm:finance_payables"),
                                {"q": finance_voucher_a.number})
        assert [row["number"] for row in response.context["rows"]] == [finance_voucher_a.number]

    def test_finance_payables_status_filter_narrows_to_a_bill_status(
            self, client_a, finance_recoverable_voucher_a, freight_invoice_a):
        finance_recoverable_voucher_a.draft_bill()
        response = client_a.get(reverse("scm:finance_payables"), {"status": "draft"})
        assert response.status_code == 200
        assert {row["source"] for row in response.context["rows"]} == {"landed"}
        empty = client_a.get(reverse("scm:finance_payables"), {"status": "paid"})
        assert list(empty.context["rows"]) == []

    def test_finance_payables_is_empty_for_a_tenant_less_user(
            self, _finance_rootless_client, finance_voucher_a):
        response = _finance_rootless_client.get(reverse("scm:finance_payables"))
        assert response.status_code == 200, "a superuser must get an empty report, never a 500"
        assert list(response.context["rows"]) == []
        assert response.context["totals"]["count"] == 0
        assert response.context["totals"]["amount"] == Decimal("0.00")

    def test_finance_payables_is_flat_as_rows_are_added(
            self, client_a, tenant_a, finance_receipt_a, supplier_a, finance_voucher_a,
            django_assert_max_num_queries):
        url = reverse("scm:finance_payables")
        few = _finance_query_count(client_a, url)
        _finance_bulk_vouchers(tenant_a, finance_receipt_a, supplier_a, 20)
        with django_assert_max_num_queries(few):
            response = client_a.get(url)
        assert len(response.context["rows"]) >= 21


@pytest.mark.django_db
class TestFinanceReceivablesReport:
    """``scm:finance_receivables`` — the same posture, pointed at ``accounting.Invoice``."""

    def test_finance_receivables_renders_the_contracted_template_and_context(
            self, client_a, sales_order_a, tpl_billing_run_a, return_authorization_a):
        response = client_a.get(reverse("scm:finance_receivables"))
        assert response.status_code == 200
        assert "scm/finance/receivables.html" in _finance_templates(response)

        ctx = response.context
        assert ctx["row_cap"] == 500 and ctx["truncated"] is False
        assert list(ctx["source_choices"]) == [("sales_order", "Sales Orders"),
                                               ("billing_run", "3PL Billing Runs"),
                                               ("return", "Return Credit Notes")]
        assert ("sent", "Sent") in list(ctx["status_choices"])
        assert {row["source"] for row in ctx["rows"]} == {"sales_order", "billing_run", "return"}
        assert set(ctx["totals"]) == {"count", "total", "balance", "uninvoiced"}
        assert ctx["totals"]["count"] == len(ctx["rows"])
        # Nothing is invoiced, so the whole book is uninvoiced and the balance is zero.
        assert ctx["totals"]["balance"] == Decimal("0.00")
        assert ctx["totals"]["uninvoiced"] == ctx["totals"]["total"]

    def test_finance_receivables_sales_order_row_shape(self, client_a, sales_order_a):
        rows = client_a.get(reverse("scm:finance_receivables")).context["rows"]
        row = next(r for r in rows if r["source"] == "sales_order")
        assert set(row) == {"source", "source_label", "document", "number", "url", "party",
                            "invoice", "invoice_number", "invoice_status", "invoice_status_label",
                            "total", "balance"}
        assert row["url"] == reverse("scm:salesorder_detail", args=[sales_order_a.pk])
        assert isinstance(row["party"], str) and row["party"]
        assert row["total"] == Decimal("150.00")
        # None while uninvoiced — never 0.00, which would read as "settled".
        assert row["balance"] is None
        assert row["invoice"] is None and row["invoice_status"] == ""

    @pytest.mark.parametrize("source", ["sales_order", "billing_run", "return"])
    def test_finance_receivables_source_filter_keeps_one_source(
            self, client_a, sales_order_a, tpl_billing_run_a, return_authorization_a, source):
        response = client_a.get(reverse("scm:finance_receivables"), {"source": source})
        assert response.status_code == 200
        assert {row["source"] for row in response.context["rows"]} == {source}

    def test_finance_receivables_search_narrows_by_number(self, client_a, sales_order_a,
                                                          tpl_billing_run_a):
        response = client_a.get(reverse("scm:finance_receivables"), {"q": sales_order_a.number})
        assert [row["number"] for row in response.context["rows"]] == [sales_order_a.number]

    def test_finance_receivables_is_empty_for_a_tenant_less_user(
            self, _finance_rootless_client, sales_order_a):
        response = _finance_rootless_client.get(reverse("scm:finance_receivables"))
        assert response.status_code == 200
        assert list(response.context["rows"]) == []
        assert response.context["totals"]["total"] == Decimal("0.00")


@pytest.mark.django_db
class TestFinanceBudgetVarianceReport:
    """``scm:finance_budget_variance`` — a VIEW-TIME comparison; 4.18 stores no encumbrance."""

    def test_finance_budget_variance_renders_the_contracted_template_and_context(
            self, client_a, finance_budget_a, org_unit_a):
        response = client_a.get(reverse("scm:finance_budget_variance"))
        assert response.status_code == 200
        assert "scm/finance/budget_variance.html" in _finance_templates(response)

        ctx = response.context
        assert ctx["row_cap"] == 500 and ctx["truncated"] is False
        assert ctx["selected_budget"] is None and ctx["selected_period"] is None
        assert [b.pk for b in ctx["budgets"]] == [finance_budget_a.pk]
        assert [p.pk for p in ctx["fiscal_periods"]] == [finance_budget_a.fiscal_period_id]
        assert set(ctx["totals"]) == {"budgeted", "committed", "incurred", "remaining"}

        named = next(r for r in ctx["rows"] if r["org_unit_name"] == org_unit_a.name)
        assert set(named) == {"org_unit", "org_unit_name", "budgeted", "committed", "incurred",
                              "remaining", "variance_pct", "over_budget"}
        assert named["budgeted"] == Decimal("10000.00")
        assert named["remaining"] == Decimal("10000.00")
        assert named["variance_pct"] == Decimal("100.00")
        assert named["over_budget"] is False
        assert ctx["totals"]["budgeted"] == Decimal("10000.00")

    def test_finance_budget_variance_unassigned_row_always_carries_a_name(
            self, client_a, finance_budget_a, purchase_order_a):
        """``purchase_order_a`` is approved and its chain to an org unit is broken (no requisition),
        so its commitment lands in Unassigned — which must never render blank."""
        rows = client_a.get(reverse("scm:finance_budget_variance")).context["rows"]
        unassigned = next(r for r in rows if r["org_unit"] is None)
        assert unassigned["org_unit_name"] == "Unassigned"
        assert unassigned["committed"] == Decimal("150.00")
        assert unassigned["budgeted"] == Decimal("0.00")
        # No budget to divide by, so None — not zero, which would read as "exactly on budget".
        assert unassigned["variance_pct"] is None
        assert unassigned["over_budget"] is True

    def test_finance_budget_variance_counts_an_allocated_voucher_as_incurred(
            self, client_a, finance_budget_a, finance_allocated_voucher_a, finance_charge_a):
        """The voucher's ACTUAL is what is incurred — an estimated-only charge contributes nothing,
        which is the finding rather than a gap."""
        finance_charge_a.actual_amount = Decimal("120.00")
        finance_charge_a.save()
        finance_allocated_voucher_a.recalc_totals()
        rows = client_a.get(reverse("scm:finance_budget_variance")).context["rows"]
        unassigned = next(r for r in rows if r["org_unit"] is None)
        assert unassigned["incurred"] == Decimal("120.00")

    def test_finance_budget_variance_selecting_a_budget_scopes_the_report(
            self, client_a, finance_budget_a, org_unit_a, purchase_order_a):
        response = client_a.get(reverse("scm:finance_budget_variance"),
                                {"budget": str(finance_budget_a.pk)})
        assert response.status_code == 200
        ctx = response.context
        assert ctx["selected_budget"].pk == finance_budget_a.pk
        # Scoped: the un-attributable PO commitment is excluded rather than dumped on this budget.
        assert [r["org_unit_name"] for r in ctx["rows"]] == [org_unit_a.name]
        assert ctx["rows"][0]["committed"] == Decimal("0.00")

    def test_finance_budget_variance_selecting_a_fiscal_period_scopes_the_report(
            self, client_a, finance_budget_a, finance_fiscal_period_a, org_unit_a):
        response = client_a.get(reverse("scm:finance_budget_variance"),
                                {"fiscal_period": str(finance_fiscal_period_a.pk)})
        assert response.status_code == 200
        assert response.context["selected_period"].pk == finance_fiscal_period_a.pk
        assert [r["org_unit_name"] for r in response.context["rows"]] == [org_unit_a.name]

    @pytest.mark.parametrize("query", [
        {"budget": "abc"}, {"budget": "²"}, {"budget": "999999999999999999999"},
        {"fiscal_period": "abc"}, {"fiscal_period": "-1"}, {"page": "999"},
    ])
    def test_finance_budget_variance_junk_params_are_200_not_500(
            self, client_a, finance_budget_a, query):
        response = client_a.get(reverse("scm:finance_budget_variance"), query)
        assert response.status_code == 200, f"{query} 500'd the budget variance report"
        assert response.context["selected_budget"] is None
        assert response.context["selected_period"] is None

    def test_finance_budget_variance_is_empty_for_a_tenant_less_user(
            self, _finance_rootless_client, finance_budget_a):
        response = _finance_rootless_client.get(reverse("scm:finance_budget_variance"))
        assert response.status_code == 200
        assert list(response.context["rows"]) == []
        assert list(response.context["budgets"]) == []
        assert list(response.context["fiscal_periods"]) == []
        assert response.context["totals"]["budgeted"] == Decimal("0.00")


@pytest.mark.django_db
class TestFinanceLandedCostVarianceReport:
    """``scm:landed_cost_variance`` — estimated vs. actual vs. allocated, grouped three ways."""

    def test_finance_landed_variance_renders_the_contracted_template_and_context(
            self, client_a, finance_allocated_voucher_a, finance_charge_a):
        response = client_a.get(reverse("scm:landed_cost_variance"))
        assert response.status_code == 200
        assert "scm/finance/landed_cost_variance.html" in _finance_templates(response)

        ctx = response.context
        assert ctx["group"] == "charge_type"
        assert list(ctx["group_choices"]) == [("charge_type", "By Charge Type"),
                                              ("item", "By Item"),
                                              ("shipment", "By Shipment")]
        assert len(list(ctx["charge_type_choices"])) == 11
        assert ctx["date_from"] is None and ctx["date_to"] is None
        assert ctx["row_cap"] == 500 and ctx["truncated"] is False
        assert set(ctx["totals"]) == {"estimated", "actual", "variance", "allocated"}

        assert len(ctx["rows"]) == 1
        row = ctx["rows"][0]
        assert set(row) == {"key", "label", "estimated", "actual", "variance", "allocated",
                            "variance_pct", "quantity", "uplift_per_unit"}
        assert row["key"] == "freight" and row["label"] == "Freight"
        assert row["estimated"] == Decimal("100.00")
        assert row["actual"] == Decimal("0.00")
        assert row["variance"] == Decimal("-100.00")
        assert row["allocated"] == Decimal("100.00")
        assert row["variance_pct"] == Decimal("-100.00")
        assert row["quantity"] == Decimal("10.0000")
        assert row["uplift_per_unit"] == Decimal("10.0000")
        assert ctx["totals"]["allocated"] == Decimal("100.00")

    def test_finance_landed_variance_group_by_item_prorates_onto_the_sku(
            self, client_a, finance_allocated_voucher_a, item_a):
        response = client_a.get(reverse("scm:landed_cost_variance"), {"group": "item"})
        assert response.status_code == 200
        assert response.context["group"] == "item"
        rows = response.context["rows"]
        assert len(rows) == 1
        assert rows[0]["key"] == item_a.pk
        assert rows[0]["label"] == f"{item_a.sku} · {item_a.name}"
        # One allocation carrying the whole charge, so its share is 100 % of the estimate.
        assert rows[0]["estimated"] == Decimal("100.00")
        assert rows[0]["allocated"] == Decimal("100.00")
        assert rows[0]["quantity"] == Decimal("10.0000")

    def test_finance_landed_variance_group_by_shipment_labels_the_consignment(
            self, client_a, finance_allocated_voucher_a, shipment_a):
        response = client_a.get(reverse("scm:landed_cost_variance"), {"group": "shipment"})
        assert response.context["group"] == "shipment"
        assert [r["label"] for r in response.context["rows"]] == [shipment_a.number]

    def test_finance_landed_variance_group_by_shipment_names_a_voucher_without_one(
            self, client_a, finance_voucher_multi_a):
        response = client_a.get(reverse("scm:landed_cost_variance"), {"group": "shipment"})
        assert [r["label"] for r in response.context["rows"]] == ["No shipment"]

    def test_finance_landed_variance_charge_type_filter_narrows(
            self, client_a, finance_allocated_voucher_a):
        keep = client_a.get(reverse("scm:landed_cost_variance"), {"charge_type": "freight"})
        assert [r["key"] for r in keep.context["rows"]] == ["freight"]
        drop = client_a.get(reverse("scm:landed_cost_variance"), {"charge_type": "duty"})
        assert list(drop.context["rows"]) == []

    def test_finance_landed_variance_date_window_is_echoed_back_as_dates(
            self, client_a, finance_allocated_voucher_a):
        today = timezone.localdate()
        response = client_a.get(reverse("scm:landed_cost_variance"), {
            "date_from": (today - datetime.timedelta(days=1)).isoformat(),
            "date_to": (today + datetime.timedelta(days=1)).isoformat()})
        assert response.context["date_from"] == today - datetime.timedelta(days=1)
        assert response.context["date_to"] == today + datetime.timedelta(days=1)
        assert len(response.context["rows"]) == 1

    def test_finance_landed_variance_date_window_excludes_an_out_of_range_voucher(
            self, client_a, finance_allocated_voucher_a):
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        response = client_a.get(reverse("scm:landed_cost_variance"),
                                {"date_from": tomorrow.isoformat()})
        assert response.status_code == 200
        assert list(response.context["rows"]) == []
        assert response.context["totals"]["actual"] == Decimal("0.00")

    def test_finance_landed_variance_excludes_a_cancelled_voucher(
            self, client_a, finance_allocated_voucher_a):
        finance_allocated_voucher_a.cancel()
        response = client_a.get(reverse("scm:landed_cost_variance"))
        assert list(response.context["rows"]) == []

    def test_finance_landed_variance_is_empty_for_a_tenant_less_user(
            self, _finance_rootless_client, finance_allocated_voucher_a):
        response = _finance_rootless_client.get(reverse("scm:landed_cost_variance"))
        assert response.status_code == 200
        assert list(response.context["rows"]) == []
        assert response.context["totals"]["estimated"] == Decimal("0.00")
