"""SCM 4.18 Finance & Accounting Integration — ISOLATION AND HARDENING.

This lane asserts the things that are invisible when they work and expensive when they do not:

* **Multi-tenant isolation.** A tenant-A session handed a tenant-B pk gets a 404 on every detail,
  edit, delete and verb route — including ``LandedCostCharge``, the TENANT-LESS child that is
  resolved only through ``voucher__tenant=request.tenant``. That one is the highest-value IDOR test
  in this sub-module: a bare pk lookup there would be a silent cross-tenant write that nothing on the
  response would look wrong about. A's two lists and all four reports never carry B's rows, and a
  crafted POST naming B's pk in an FK field is refused rather than saved.
* **Auth.** Anonymous is redirected to ``/login/`` on all 21 routes; the FOUR money verbs
  (``allocate`` / ``accrue`` / ``draft-bill`` / ``cancel``) are ``@tenant_admin_required`` and 403 a
  plain member, while the ordinary clerical routes still work for one; CSRF is enforced on every
  POST.
* **Negative input.** A junk filter param answers 200 rather than 500 (L11), pagination survives page
  2 and a page past the end (L9), and every hand-typed decimal — ``NaN``, ``Infinity``, garbage,
  negative, over-``max_digits``, over-``MaxValueValidator`` — comes back as a form error, never a
  500.
* **Absent prerequisites are REJECTED, never fallen through (L35).** Allocating a receipt that posted
  nothing to the stock ledger, allocating a voucher on which nothing capitalises, accruing a voucher
  that was never allocated, billing one that was never allocated, billing twice, cancelling twice and
  writing to an already-allocated voucher all refuse — with the pinned sentence, not silently.
* **Derived / workflow columns are not writable from a POST body** (L20/L22): ``status``, ``number``,
  ``bill``, the five ``recalc_totals()`` money columns and the system ``accrued_at`` stamp are all
  ignored when a crafted body names them.

**Every refusal is paired with the POSITIVE path (L44)**, so a guard that simply broke the feature
fails this file instead of quietly passing it.

NAMING: every test function is ``test_finance_*`` and every module-level name (helper, constant,
fixture) is ``_finance_*`` — the ``test_suite_hygiene.py`` guard fails on a module-level name defined
twice, and the prefix keeps the next sub-module's appended helpers from shadowing these.

TIME BASIS (L16): every date is derived from ``timezone.localdate()``, the same basis
``DutyTariff.is_current`` / ``rate_for()`` / ``draft_bill()`` read, so nothing here flakes in the
hours after local midnight.
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
def _finance_flash(response):
    """Every flashed message on a FOLLOWED response, as lowercase strings."""
    return [str(message).lower() for message in response.context["messages"]]


def _finance_tariff_payload(**over):
    """A minimally valid ``DutyTariffForm`` POST body — a brand-new classification/origin/date."""
    data = {
        "hs_code": "9403.30",
        "country_of_origin": "France",
        "description": "Office furniture",
        "duty_rate_pct": "3.250",
        "effective_from": timezone.localdate().isoformat(),
        "effective_to": "",
        "tax_code": "",
        "is_active": "on",
    }
    data.update(over)
    return data


def _finance_voucher_payload(goods_receipt, party, **over):
    """A valid ``LandedCostVoucherForm`` POST body. The envelope only — it carries NO money."""
    data = {
        "goods_receipt": str(goods_receipt.pk),
        "party": str(party.pk),
        "shipment": "",
        "trade_document": "",
        "currency": "",
        "cost_date": timezone.localdate().isoformat(),
        "allocation_basis": "value",
        "notes": "Crafted voucher",
    }
    data.update(over)
    return data


def _finance_charge_payload(**over):
    """A valid ``LandedCostChargeForm`` POST body — one capitalising freight estimate.

    ``is_recoverable`` is deliberately ABSENT: an unchecked checkbox posts no key at all, which is
    how ``False`` is spelled on the wire. ``duty_rate_pct`` is blank, which
    ``clean_duty_rate_pct()`` coerces to ``Decimal("0")`` (the column is NOT NULL).
    """
    data = {
        "charge_type": "freight",
        "description": "Ocean freight leg",
        "party": "",
        "freight_invoice": "",
        "estimated_amount": "75.00",
        "actual_amount": "0.00",
        "allocation_basis": "",
        "gl_account": "",
        "tax_code": "",
        "hs_code": "",
        "country_of_origin": "",
        "duty_rate_pct": "",
        "capitalise_to_inventory": "on",
    }
    data.update(over)
    return data


def _finance_bulk_tariffs(tenant, count, prefix="99"):
    """``count`` extra duty rates in ``tenant`` — the pagination and query-budget material.

    Each carries its OWN ``hs_code`` because of ``unique_together ("tenant", "hs_code",
    "country_of_origin", "effective_from")``.
    """
    from apps.scm.models import DutyTariff
    today = timezone.localdate()
    return [DutyTariff.objects.create(
        tenant=tenant, hs_code=f"{prefix}{index:02d}.10", country_of_origin="Japan",
        description=f"Bulk classification {index:02d}", duty_rate_pct=Decimal("1.000"),
        effective_from=today - datetime.timedelta(days=index + 1)) for index in range(count)]


def _finance_bulk_vouchers(tenant, goods_receipt, party, count):
    """``count`` extra vouchers over ONE receipt — nothing constrains that pair, and re-using the
    receipt keeps the fixture cost linear instead of building a GRN per row."""
    from apps.scm.models import LandedCostVoucher
    today = timezone.localdate()
    return [LandedCostVoucher.objects.create(
        tenant=tenant, goods_receipt=goods_receipt, party=party,
        cost_date=today - datetime.timedelta(days=index)) for index in range(count)]


#: Everything the two list pages and the four report pages must survive in a hand-edited query
#: string. Each pair is ``(url name, GET params)``; the assertion is 200, never a 500 (L11/L9).
_FINANCE_JUNK_QUERIES = [
    ("scm:dutytariff_list", {"status": "banana"}),
    ("scm:dutytariff_list", {"status": "True"}),
    ("scm:dutytariff_list", {"country": "Atlantis"}),
    ("scm:dutytariff_list", {"country": "²"}),
    ("scm:dutytariff_list", {"page": "abc"}),
    ("scm:dutytariff_list", {"page": "999"}),
    ("scm:dutytariff_list", {"page": "-1"}),
    ("scm:dutytariff_list", {"q": "'); DROP TABLE scm_dutytariff;--"}),
    ("scm:landedcostvoucher_list", {"party": "abc"}),
    ("scm:landedcostvoucher_list", {"party": "²"}),
    ("scm:landedcostvoucher_list", {"party": "99999999999999999999"}),
    ("scm:landedcostvoucher_list", {"status": "banana"}),
    ("scm:landedcostvoucher_list", {"basis": "lol"}),
    ("scm:landedcostvoucher_list", {"page": "abc"}),
    ("scm:landedcostvoucher_list", {"page": "999"}),
    ("scm:landedcostvoucher_list", {"q": "%%"}),
    ("scm:finance_payables", {"source": "lol"}),
    ("scm:finance_payables", {"status": "lol"}),
    ("scm:finance_payables", {"source": "²", "status": "³"}),
    ("scm:finance_payables", {"page": "999"}),
    ("scm:finance_receivables", {"source": "lol"}),
    ("scm:finance_receivables", {"status": "lol"}),
    ("scm:finance_receivables", {"q": "'); DROP TABLE accounting_invoice;--"}),
    ("scm:finance_budget_variance", {"budget": "abc"}),
    ("scm:finance_budget_variance", {"budget": "²"}),
    ("scm:finance_budget_variance", {"budget": "99999999999999999999"}),
    ("scm:finance_budget_variance", {"fiscal_period": "abc"}),
    ("scm:finance_budget_variance", {"fiscal_period": "99999999999999999999"}),
    ("scm:landed_cost_variance", {"group": "lol"}),
    ("scm:landed_cost_variance", {"charge_type": "lol"}),
    ("scm:landed_cost_variance", {"date_from": "nope"}),
    ("scm:landed_cost_variance", {"date_to": "2026-13-45"}),
    ("scm:landed_cost_variance", {"date_from": "", "date_to": "not-a-date"}),
    ("scm:landed_cost_variance", {"page": "999"}),
]

#: Every 4.18 GET page that takes no pk — the anonymous-redirect sweep.
_FINANCE_ANON_PAGES = [
    "scm:dutytariff_list",
    "scm:dutytariff_create",
    "scm:landedcostvoucher_list",
    "scm:landedcostvoucher_create",
    "scm:finance_payables",
    "scm:finance_receivables",
    "scm:finance_budget_variance",
    "scm:landed_cost_variance",
]

#: ``(url name, fixture name)`` for every POST-only route. A GET must be a 405 — a link-prefetcher
#: following one of these would be re-valuing inventory and raising vendor bills.
_FINANCE_POST_ONLY_ROUTES = [
    ("scm:dutytariff_delete", "finance_duty_tariff_a"),
    ("scm:landedcostvoucher_delete", "finance_voucher_a"),
    ("scm:landedcostvoucher_allocate", "finance_voucher_a"),
    ("scm:landedcostvoucher_accrue", "finance_voucher_a"),
    ("scm:landedcostvoucher_draft_bill", "finance_voucher_a"),
    ("scm:landedcostvoucher_cancel", "finance_voucher_a"),
    ("scm:landedcostcharge_delete", "finance_charge_a"),
]

#: ``(url name, fixture name)`` for every pk GET route a tenant-A session must 404 on when handed a
#: tenant-B pk. ``landedcostcharge_create`` takes the VOUCHER's pk; ``landedcostcharge_edit`` the
#: CHARGE's own — and the charge carries no tenant column, so it resolves through ``voucher__tenant``.
_FINANCE_CROSS_TENANT_GETS = [
    ("scm:dutytariff_detail", "finance_duty_tariff_b"),
    ("scm:dutytariff_edit", "finance_duty_tariff_b"),
    ("scm:landedcostvoucher_detail", "finance_voucher_b"),
    ("scm:landedcostvoucher_edit", "finance_voucher_b"),
    ("scm:landedcostcharge_create", "finance_voucher_b"),
    ("scm:landedcostcharge_edit", "finance_charge_b"),
]

#: Every POST route driven with a tenant-B pk from a tenant-A ADMIN session (admin, so the four
#: ``@tenant_admin_required`` verbs reach their ``get_object_or_404`` rather than stopping at 403).
_FINANCE_CROSS_TENANT_POSTS = [
    ("scm:dutytariff_delete", "finance_duty_tariff_b"),
    ("scm:landedcostvoucher_delete", "finance_voucher_b"),
    ("scm:landedcostvoucher_allocate", "finance_voucher_b"),
    ("scm:landedcostvoucher_accrue", "finance_voucher_b"),
    ("scm:landedcostvoucher_draft_bill", "finance_voucher_b"),
    ("scm:landedcostvoucher_cancel", "finance_voucher_b"),
    ("scm:landedcostcharge_delete", "finance_charge_b"),
]

#: The four money verbs. All ``@tenant_admin_required`` (L27) and all ``@require_POST``.
_FINANCE_MONEY_VERBS = [
    "scm:landedcostvoucher_allocate",
    "scm:landedcostvoucher_accrue",
    "scm:landedcostvoucher_draft_bill",
    "scm:landedcostvoucher_cancel",
]

#: Hand-typed decimals that must come back as a form error rather than a 500. ``NaN`` / ``Infinity``
#: are refused by ``forms.DecimalField.validate`` (``is_finite``), the negative by
#: ``MinValueValidator(0)`` and the wide one by ``max_digits=14``.
_FINANCE_POISONED_MONEY = ["NaN", "Infinity", "-Infinity", "abc", "-25.00",
                           "999999999999999.99"]


# =================================================================================================
# Local fixtures — the shapes conftest deliberately does not pre-build
# =================================================================================================
@pytest.fixture
def _finance_unposted_voucher_a(db, tenant_a, finance_receipt_unposted_a, supplier_a, usd,
                                gl_expense):
    """A DRAFT voucher with a real capitalising charge over a receipt that posted NOTHING.

    The absent-prerequisite case (L35): everything about it looks allocatable except the one fact
    that matters, so ``allocate()`` must REFUSE it by name rather than fall through to a 0-row
    allocation that would read as success.
    """
    from apps.scm.models import LandedCostCharge, LandedCostVoucher
    voucher = LandedCostVoucher.objects.create(
        tenant=tenant_a, goods_receipt=finance_receipt_unposted_a, party=supplier_a,
        currency=usd, cost_date=timezone.localdate())
    LandedCostCharge.objects.create(
        voucher=voucher, charge_type="freight", description="Ocean freight",
        estimated_amount=Decimal("100.00"), gl_account=gl_expense,
        capitalise_to_inventory=True, is_recoverable=False)
    voucher.recalc_totals()
    return voucher


@pytest.fixture
def _finance_budget_b(db, tenant_b, gl_expense_b, org_unit_b):
    """tenant_b's approved budget — what ``?budget=<foreign pk>`` must fail to select."""
    from apps.accounting.models import Budget, BudgetLine
    budget = Budget.objects.create(tenant=tenant_b, name="Globex Supply Chain",
                                   version="original", status="approved")
    BudgetLine.objects.create(tenant=tenant_b, budget=budget, gl_account=gl_expense_b,
                              org_unit=org_unit_b, amount=Decimal("7500.00"))
    return budget


@pytest.fixture
def _finance_billed_voucher_a(db, finance_recoverable_voucher_a):
    """A voucher already handed to Accounts Payable — ``draft_bill()`` straight from ``draft``.

    Its only charge is RECOVERABLE import VAT, so nothing capitalises: ``allocate()`` refuses it and
    ``draft_bill()`` therefore relaxes its allocation precondition for exactly this shape. The result
    is a ``reconciled`` voucher with a DRAFT ``accounting.Bill`` behind it — the state every
    "refused once billed" assertion needs.
    """
    finance_recoverable_voucher_a.draft_bill()
    finance_recoverable_voucher_a.refresh_from_db()
    return finance_recoverable_voucher_a


# =================================================================================================
# Anonymous -> login
# =================================================================================================
class TestFinanceAnonymous:
    @pytest.mark.parametrize("url_name", _FINANCE_ANON_PAGES,
                             ids=[name.split(":")[1] for name in _FINANCE_ANON_PAGES])
    def test_finance_anonymous_page_redirects_to_login(self, url_name):
        response = Client().get(reverse(url_name))
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    @pytest.mark.parametrize("url_name,fixture_name", [
        ("scm:dutytariff_detail", "finance_duty_tariff_a"),
        ("scm:dutytariff_edit", "finance_duty_tariff_a"),
        ("scm:landedcostvoucher_detail", "finance_voucher_a"),
        ("scm:landedcostvoucher_edit", "finance_voucher_a"),
        ("scm:landedcostcharge_create", "finance_voucher_a"),
        ("scm:landedcostcharge_edit", "finance_charge_a"),
    ], ids=lambda value: value.split(":")[-1])
    def test_finance_anonymous_pk_page_redirects_to_login(self, request, url_name, fixture_name):
        obj = request.getfixturevalue(fixture_name)
        response = Client().get(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    @pytest.mark.parametrize("url_name", _FINANCE_MONEY_VERBS,
                             ids=[name.split(":")[1] for name in _FINANCE_MONEY_VERBS])
    def test_finance_anonymous_verb_redirects_and_changes_nothing(self, url_name,
                                                                  finance_voucher_a,
                                                                  finance_charge_a):
        from apps.scm.models import LandedCostAllocation
        response = Client().post(reverse(url_name, args=[finance_voucher_a.pk]))
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "draft"
        assert finance_voucher_a.bill_id is None
        assert not LandedCostAllocation.objects.exists()

    def test_finance_anonymous_tariff_create_post_saves_nothing(self, db):
        from apps.scm.models import DutyTariff
        before = DutyTariff.objects.count()
        response = Client().post(reverse("scm:dutytariff_create"), _finance_tariff_payload())
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        assert DutyTariff.objects.count() == before

    def test_finance_anonymous_voucher_create_post_saves_nothing(self, finance_receipt_a,
                                                                 supplier_a):
        from apps.scm.models import LandedCostVoucher
        before = LandedCostVoucher.objects.count()
        response = Client().post(reverse("scm:landedcostvoucher_create"),
                                 _finance_voucher_payload(finance_receipt_a, supplier_a))
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        assert LandedCostVoucher.objects.count() == before

    def test_finance_anonymous_charge_create_post_saves_nothing(self, finance_voucher_a):
        from apps.scm.models import LandedCostCharge
        response = Client().post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload())
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_a).exists()

    def test_finance_anonymous_delete_post_deletes_nothing(self, finance_duty_tariff_a):
        from apps.scm.models import DutyTariff
        response = Client().post(reverse("scm:dutytariff_delete", args=[finance_duty_tariff_a.pk]))
        assert response.status_code == 302
        assert "/login/" in response["Location"]
        assert DutyTariff.objects.filter(pk=finance_duty_tariff_a.pk).exists()


# =================================================================================================
# @tenant_admin_required — the four money verbs (L27), and everything that is NOT gated
# =================================================================================================
class TestFinanceAdminGates:
    def test_finance_allocate_is_refused_for_a_plain_member(self, member_client, finance_voucher_a,
                                                            finance_charge_a):
        from apps.scm.models import LandedCostAllocation
        response = member_client.post(
            reverse("scm:landedcostvoucher_allocate", args=[finance_voucher_a.pk]))
        assert response.status_code == 403
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "draft"
        assert finance_voucher_a.allocated_total == Decimal("0.00")
        assert not LandedCostAllocation.objects.exists()

    def test_finance_allocate_succeeds_for_a_tenant_admin(self, client_a, finance_voucher_a,
                                                          finance_charge_a):
        """The POSITIVE half — the admin gate must refuse the member, not the feature (L44)."""
        from apps.scm.models import LandedCostAllocation
        response = client_a.post(
            reverse("scm:landedcostvoucher_allocate", args=[finance_voucher_a.pk]))
        assert response.status_code == 302
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "allocated"
        assert finance_voucher_a.allocated_total == Decimal("100.00")
        assert LandedCostAllocation.objects.filter(voucher=finance_voucher_a).count() == 1

    def test_finance_accrue_is_refused_for_a_plain_member(self, member_client,
                                                          finance_allocated_voucher_a):
        response = member_client.post(
            reverse("scm:landedcostvoucher_accrue", args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 403
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "allocated"
        assert finance_allocated_voucher_a.accrued_at is None

    def test_finance_accrue_succeeds_for_a_tenant_admin(self, client_a,
                                                        finance_allocated_voucher_a):
        response = client_a.post(
            reverse("scm:landedcostvoucher_accrue", args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 302
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "accrued"
        assert finance_allocated_voucher_a.accrued_at is not None

    def test_finance_draft_bill_is_refused_for_a_plain_member(self, member_client,
                                                              finance_allocated_voucher_a):
        from apps.accounting.models import Bill
        before = Bill.objects.count()
        response = member_client.post(
            reverse("scm:landedcostvoucher_draft_bill", args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 403
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "allocated"
        assert finance_allocated_voucher_a.bill_id is None
        assert Bill.objects.count() == before

    def test_finance_draft_bill_succeeds_for_a_tenant_admin(self, client_a,
                                                            finance_allocated_voucher_a):
        from apps.accounting.models import Bill
        response = client_a.post(
            reverse("scm:landedcostvoucher_draft_bill", args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 302
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "reconciled"
        bill = Bill.objects.get(pk=finance_allocated_voucher_a.bill_id)
        # A DRAFT bill and NOTHING else — SCM posts no JournalEntry (ruling 1).
        assert bill.status == "draft"

    def test_finance_cancel_is_refused_for_a_plain_member(self, member_client,
                                                          finance_allocated_voucher_a):
        from apps.scm.models import LandedCostAllocation
        response = member_client.post(
            reverse("scm:landedcostvoucher_cancel", args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 403
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "allocated"
        # The uplift is still on the units — a 403 that had already reversed it would be worse.
        assert LandedCostAllocation.objects.filter(voucher=finance_allocated_voucher_a).exists()

    def test_finance_cancel_succeeds_for_a_tenant_admin(self, client_a,
                                                        finance_allocated_voucher_a):
        from apps.scm.models import LandedCostAllocation
        response = client_a.post(
            reverse("scm:landedcostvoucher_cancel", args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 302
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "cancelled"
        assert not LandedCostAllocation.objects.filter(
            voucher=finance_allocated_voucher_a).exists()

    def test_finance_member_can_create_a_duty_tariff(self, member_client, tenant_a):
        """The admin gate must NOT have spread — a tariff is clerical master data."""
        from apps.scm.models import DutyTariff
        response = member_client.post(reverse("scm:dutytariff_create"), _finance_tariff_payload())
        assert response.status_code == 302
        assert DutyTariff.objects.filter(tenant=tenant_a, hs_code="9403.30").exists()

    def test_finance_member_can_delete_a_duty_tariff(self, member_client, finance_duty_tariff_a):
        from apps.scm.models import DutyTariff
        response = member_client.post(
            reverse("scm:dutytariff_delete", args=[finance_duty_tariff_a.pk]))
        assert response.status_code == 302
        assert not DutyTariff.objects.filter(pk=finance_duty_tariff_a.pk).exists()

    def test_finance_member_can_create_a_voucher(self, member_client, tenant_a, finance_receipt_a,
                                                 supplier_a):
        from apps.scm.models import LandedCostVoucher
        response = member_client.post(reverse("scm:landedcostvoucher_create"),
                                      _finance_voucher_payload(finance_receipt_a, supplier_a))
        assert response.status_code == 302
        assert LandedCostVoucher.objects.filter(tenant=tenant_a,
                                                notes="Crafted voucher").exists()

    def test_finance_member_can_add_a_charge(self, member_client, finance_voucher_a):
        """Charges stay at ``@login_required`` on purpose — a draft charge has landed on nothing."""
        from apps.scm.models import LandedCostCharge
        response = member_client.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload())
        assert response.status_code == 302
        assert LandedCostCharge.objects.filter(voucher=finance_voucher_a).count() == 1

    def test_finance_member_can_delete_a_charge(self, member_client, finance_charge_a,
                                                finance_voucher_a):
        from apps.scm.models import LandedCostCharge
        response = member_client.post(
            reverse("scm:landedcostcharge_delete", args=[finance_charge_a.pk]))
        assert response.status_code == 302
        assert not LandedCostCharge.objects.filter(pk=finance_charge_a.pk).exists()

    @pytest.mark.parametrize("url_name", ["scm:finance_payables", "scm:finance_receivables",
                                          "scm:finance_budget_variance",
                                          "scm:landed_cost_variance"],
                             ids=["payables", "receivables", "budget_variance", "landed_variance"])
    def test_finance_member_can_read_every_report(self, member_client, url_name):
        """The four reports are deliberately NOT admin-gated: they only read."""
        assert member_client.get(reverse(url_name)).status_code == 200


# =================================================================================================
# CSRF
# =================================================================================================
class TestFinanceCsrf:
    def test_finance_csrf_is_enforced_on_a_verb_post(self, admin_user, finance_voucher_a,
                                                     finance_charge_a):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(
            reverse("scm:landedcostvoucher_allocate", args=[finance_voucher_a.pk]))
        assert response.status_code == 403
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "draft"

    def test_finance_csrf_is_enforced_on_a_create_post(self, admin_user, db):
        from apps.scm.models import DutyTariff
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        before = DutyTariff.objects.count()
        response = strict.post(reverse("scm:dutytariff_create"), _finance_tariff_payload())
        assert response.status_code == 403
        assert DutyTariff.objects.count() == before

    def test_finance_csrf_is_enforced_on_a_charge_create_post(self, admin_user, finance_voucher_a):
        from apps.scm.models import LandedCostCharge
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload())
        assert response.status_code == 403
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_a).exists()

    def test_finance_csrf_is_enforced_on_a_delete_post(self, admin_user, finance_duty_tariff_a):
        from apps.scm.models import DutyTariff
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        response = strict.post(
            reverse("scm:dutytariff_delete", args=[finance_duty_tariff_a.pk]))
        assert response.status_code == 403
        assert DutyTariff.objects.filter(pk=finance_duty_tariff_a.pk).exists()

    def test_finance_a_token_carrying_post_is_accepted(self, admin_user, finance_voucher_a,
                                                       finance_charge_a):
        """The POSITIVE half: CSRF enforcement must refuse a forgery, not the feature (L44)."""
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin_user)
        page = strict.get(reverse("scm:dutytariff_create"))
        assert page.status_code == 200
        token = strict.cookies["csrftoken"].value
        response = strict.post(
            reverse("scm:landedcostvoucher_allocate", args=[finance_voucher_a.pk]),
            {"csrfmiddlewaretoken": token})
        assert response.status_code == 302
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "allocated"


# =================================================================================================
# Multi-tenant isolation
# =================================================================================================
class TestFinanceCrossTenantIsolation:
    @pytest.mark.parametrize("url_name,fixture_name", _FINANCE_CROSS_TENANT_GETS,
                             ids=[name.split(":")[1] for name, _ in _FINANCE_CROSS_TENANT_GETS])
    def test_finance_foreign_pk_on_a_get_route_is_404(self, request, client_a, url_name,
                                                      fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 404

    @pytest.mark.parametrize("url_name,fixture_name", _FINANCE_CROSS_TENANT_POSTS,
                             ids=[name.split(":")[1] for name, _ in _FINANCE_CROSS_TENANT_POSTS])
    def test_finance_foreign_pk_on_a_post_route_is_404(self, request, client_a, url_name,
                                                       fixture_name):
        obj = request.getfixturevalue(fixture_name)
        response = client_a.post(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 404
        # The row is untouched — a 404 that had already deleted or moved something would be worse
        # than a 200.
        assert type(obj).objects.filter(pk=obj.pk).exists()

    def test_finance_foreign_voucher_verbs_change_nothing(self, client_a, finance_voucher_b):
        """All four verbs, driven at tenant B's voucher from tenant A's admin session."""
        from apps.accounting.models import Bill
        before = Bill.objects.count()
        for url_name in _FINANCE_MONEY_VERBS:
            assert client_a.post(
                reverse(url_name, args=[finance_voucher_b.pk])).status_code == 404
        finance_voucher_b.refresh_from_db()
        assert finance_voucher_b.status == "draft"
        assert finance_voucher_b.bill_id is None
        assert Bill.objects.count() == before

    def test_finance_foreign_charge_edit_is_404(self, client_a, finance_charge_b):
        """The child carries NO tenant column — it is resolved through ``voucher__tenant``.

        A bare pk lookup here would be a silent cross-tenant write that nothing about the response
        would look wrong about, which is why this is the highest-value IDOR case in 4.18.
        """
        url = reverse("scm:landedcostcharge_edit", args=[finance_charge_b.pk])
        assert client_a.get(url).status_code == 404
        assert client_a.post(url, _finance_charge_payload(
            description="hijacked", estimated_amount="9999.00")).status_code == 404
        finance_charge_b.refresh_from_db()
        assert finance_charge_b.description == "Globex handling"
        assert finance_charge_b.estimated_amount == Decimal("40.00")

    def test_finance_foreign_charge_delete_is_404(self, client_a, finance_charge_b,
                                                  finance_voucher_b):
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_delete", args=[finance_charge_b.pk]))
        assert response.status_code == 404
        assert LandedCostCharge.objects.filter(pk=finance_charge_b.pk).exists()
        finance_voucher_b.refresh_from_db()
        assert finance_voucher_b.estimated_total == Decimal("40.00")

    def test_finance_own_charge_routes_still_resolve(self, client_a, finance_charge_a):
        """The POSITIVE half of the tenant-less-child scoping (L44)."""
        assert client_a.get(reverse("scm:landedcostcharge_edit",
                                    args=[finance_charge_a.pk])).status_code == 200

    def test_finance_tariff_list_excludes_the_other_tenant(self, client_a, finance_duty_tariff_a,
                                                           finance_duty_tariff_b):
        response = client_a.get(reverse("scm:dutytariff_list"))
        assert response.status_code == 200
        pks = {obj.pk for obj in response.context["object_list"]}
        assert finance_duty_tariff_a.pk in pks
        assert finance_duty_tariff_b.pk not in pks
        # tenant_b's classification is the string that can only be theirs (the DTY- sequence
        # restarts per tenant, so the NUMBER is identical in both workspaces).
        assert b"8528.52" not in response.content

    def test_finance_tariff_list_stats_count_only_this_workspace(self, client_a,
                                                                 finance_duty_tariff_a,
                                                                 finance_duty_tariff_b):
        response = client_a.get(reverse("scm:dutytariff_list"))
        assert response.context["stats"]["total"] == 1
        assert response.context["stats"]["current"] == 1
        assert response.context["countries"] == ["Germany"]

    def test_finance_voucher_list_excludes_the_other_tenant(self, client_a, finance_voucher_a,
                                                            finance_voucher_b):
        response = client_a.get(reverse("scm:landedcostvoucher_list"))
        assert response.status_code == 200
        pks = {obj.pk for obj in response.context["object_list"]}
        assert finance_voucher_a.pk in pks
        assert finance_voucher_b.pk not in pks
        assert b"Globex" not in response.content

    def test_finance_voucher_list_stats_count_only_this_workspace(self, client_a,
                                                                  finance_voucher_a,
                                                                  finance_voucher_b):
        response = client_a.get(reverse("scm:landedcostvoucher_list"))
        assert response.context["stats"]["total"] == 1
        assert {party.pk for party in response.context["parties"]} == {finance_voucher_a.party_id}

    def test_finance_payables_report_excludes_the_other_tenant(self, client_a, finance_voucher_a,
                                                               finance_voucher_b):
        """Compared by URL, not by number: ``number`` RESTARTS per tenant, so both workspaces hold an
        ``LC-00001`` and a name test here would pass on a genuinely leaking report."""
        response = client_a.get(reverse("scm:finance_payables"))
        assert response.status_code == 200
        rows = response.context["rows"]
        assert any(row["source"] == "landed" for row in rows)
        urls = {row["url"] for row in rows}
        assert reverse("scm:landedcostvoucher_detail", args=[finance_voucher_a.pk]) in urls
        assert reverse("scm:landedcostvoucher_detail", args=[finance_voucher_b.pk]) not in urls
        assert not any("Globex" in (row["party"] or "") for row in rows)

    def test_finance_receivables_report_excludes_the_other_tenant(self, client_a, sales_order_a,
                                                                  sales_order_b):
        """By URL too — ``SO-#####`` restarts per tenant and both fixtures are ``SO-00001``."""
        response = client_a.get(reverse("scm:finance_receivables"))
        assert response.status_code == 200
        rows = response.context["rows"]
        numbers = {row["number"] for row in rows}
        assert sales_order_a.number in numbers
        urls = {row["url"] for row in rows}
        assert reverse("scm:salesorder_detail", args=[sales_order_a.pk]) in urls
        assert reverse("scm:salesorder_detail", args=[sales_order_b.pk]) not in urls
        assert not any("Globex" in (row["party"] or "") for row in rows)

    def test_finance_budget_variance_excludes_the_other_tenant(self, client_a, finance_budget_a,
                                                               _finance_budget_b):
        response = client_a.get(reverse("scm:finance_budget_variance"))
        assert response.status_code == 200
        names = {row["org_unit_name"] for row in response.context["rows"]}
        assert "Operations" in names
        assert "Globex Operations" not in names
        assert response.context["totals"]["budgeted"] == Decimal("10000.00")
        assert {budget.pk for budget in response.context["budgets"]} == {finance_budget_a.pk}

    def test_finance_budget_filter_cannot_reach_a_foreign_pk(self, client_a, finance_budget_a,
                                                             _finance_budget_b):
        """A valid-looking pk from another workspace selects NOTHING, never that budget."""
        response = client_a.get(reverse("scm:finance_budget_variance"),
                                {"budget": str(_finance_budget_b.pk)})
        assert response.status_code == 200
        assert response.context["selected_budget"] is None
        assert not any(row["org_unit_name"] == "Globex Operations"
                       for row in response.context["rows"])

    def test_finance_own_budget_filter_selects_it(self, client_a, finance_budget_a):
        """The POSITIVE half — the tenant-scoped resolution must not have broken the filter (L44)."""
        response = client_a.get(reverse("scm:finance_budget_variance"),
                                {"budget": str(finance_budget_a.pk)})
        assert response.status_code == 200
        assert response.context["selected_budget"] == finance_budget_a

    def test_finance_landed_variance_excludes_the_other_tenant(self, client_a, finance_charge_a,
                                                               finance_charge_b):
        response = client_a.get(reverse("scm:landed_cost_variance"))
        assert response.status_code == 200
        labels = {row["label"] for row in response.context["rows"]}
        assert labels == {"Freight"}
        assert response.context["totals"]["estimated"] == Decimal("100.00")

    def test_finance_tenant_b_list_shows_only_its_own_rows(self, client_b, finance_voucher_a,
                                                           finance_voucher_b):
        """The B-side of the register: not merely "no A rows" but "exactly B's row"."""
        response = client_b.get(reverse("scm:landedcostvoucher_list"))
        assert response.status_code == 200
        assert [obj.pk for obj in response.context["object_list"]] == [finance_voucher_b.pk]

    def test_finance_isolation_runs_both_ways(self, client_b, finance_duty_tariff_a,
                                              finance_voucher_a, finance_charge_a):
        """Tenant B must not reach tenant A either — the guard is symmetric, not A-shaped."""
        assert client_b.get(
            reverse("scm:dutytariff_detail", args=[finance_duty_tariff_a.pk])).status_code == 404
        assert client_b.get(
            reverse("scm:landedcostcharge_edit", args=[finance_charge_a.pk])).status_code == 404
        assert client_b.post(
            reverse("scm:landedcostvoucher_allocate",
                    args=[finance_voucher_a.pk])).status_code == 404
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "draft"


# =================================================================================================
# Crafted POSTs — a foreign pk in an FK field, and a body naming a derived column
# =================================================================================================
class TestFinanceCraftedForeignKeys:
    def test_finance_tariff_create_refuses_a_foreign_tax_code(self, client_a, finance_tax_code_b):
        from apps.scm.models import DutyTariff
        before = DutyTariff.objects.count()
        response = client_a.post(reverse("scm:dutytariff_create"),
                                 _finance_tariff_payload(tax_code=str(finance_tax_code_b.pk)))
        assert response.status_code == 200
        assert "tax_code" in response.context["form"].errors
        assert DutyTariff.objects.count() == before

    def test_finance_tariff_create_accepts_its_own_tax_code(self, client_a, tenant_a,
                                                            finance_tax_code_a):
        from apps.scm.models import DutyTariff
        response = client_a.post(reverse("scm:dutytariff_create"),
                                 _finance_tariff_payload(tax_code=str(finance_tax_code_a.pk)))
        assert response.status_code == 302
        tariff = DutyTariff.objects.get(tenant=tenant_a, hs_code="9403.30")
        assert tariff.tax_code_id == finance_tax_code_a.pk
        assert tariff.number.startswith("DTY-")

    def test_finance_tariff_create_ignores_a_posted_tenant_and_number(self, client_a, tenant_a,
                                                                      tenant_b):
        """``tenant`` and ``number`` are NOT form fields — a crafted body cannot reach either."""
        from apps.scm.models import DutyTariff
        response = client_a.post(
            reverse("scm:dutytariff_create"),
            _finance_tariff_payload(tenant=str(tenant_b.pk), number="DTY-99999"))
        assert response.status_code == 302
        tariff = DutyTariff.objects.get(hs_code="9403.30")
        assert tariff.tenant_id == tenant_a.pk
        assert tariff.number != "DTY-99999"

    @pytest.mark.parametrize("field,fixture_name", [
        ("goods_receipt", "finance_receipt_b"),
        ("party", "supplier_b"),
        ("shipment", "shipment_b"),
        ("trade_document", "trade_document_b"),
    ])
    def test_finance_voucher_create_refuses_a_foreign_fk(self, request, client_a,
                                                         finance_receipt_a, supplier_a, field,
                                                         fixture_name):
        from apps.scm.models import LandedCostVoucher
        foreign = request.getfixturevalue(fixture_name)
        before = LandedCostVoucher.objects.count()
        # Built first, then overridden by NAME: `goods_receipt` and `party` are positional on the
        # payload helper, so passing them through **kwargs would be a duplicate argument.
        payload = _finance_voucher_payload(finance_receipt_a, supplier_a)
        payload[field] = str(foreign.pk)
        response = client_a.post(reverse("scm:landedcostvoucher_create"), payload)
        assert response.status_code == 200
        assert field in response.context["form"].errors
        assert LandedCostVoucher.objects.count() == before

    def test_finance_voucher_create_accepts_its_own_workspace_rows(self, client_a, tenant_a,
                                                                   finance_receipt_a, supplier_a,
                                                                   shipment_a, trade_document_a,
                                                                   usd):
        from apps.scm.models import LandedCostVoucher
        response = client_a.post(
            reverse("scm:landedcostvoucher_create"),
            _finance_voucher_payload(finance_receipt_a, supplier_a,
                                     shipment=str(shipment_a.pk),
                                     trade_document=str(trade_document_a.pk),
                                     currency=str(usd.pk)))
        assert response.status_code == 302
        voucher = LandedCostVoucher.objects.get(tenant=tenant_a, notes="Crafted voucher")
        assert voucher.goods_receipt_id == finance_receipt_a.pk
        assert voucher.shipment_id == shipment_a.pk
        assert voucher.number.startswith("LC-")

    def test_finance_voucher_create_ignores_posted_workflow_columns(self, client_a, tenant_a,
                                                                    finance_receipt_a, supplier_a,
                                                                    bill_a):
        """``status`` / ``bill`` / the five derived money columns / ``accrued_at`` are OFF the form.

        A body naming them must be ignored wholesale (L20/L22) — a voucher that could be POSTed
        straight to ``reconciled`` with a bill attached would skip every guard in the ladder.
        """
        from apps.scm.models import LandedCostVoucher
        response = client_a.post(
            reverse("scm:landedcostvoucher_create"),
            _finance_voucher_payload(finance_receipt_a, supplier_a,
                                     status="reconciled", bill=str(bill_a.pk),
                                     number="LC-99999",
                                     estimated_total="9999.99", actual_total="9999.99",
                                     variance_amount="1.00", variance_pct="1.00",
                                     allocated_total="9999.99",
                                     accrued_at=timezone.now().isoformat()))
        assert response.status_code == 302
        voucher = LandedCostVoucher.objects.get(tenant=tenant_a, notes="Crafted voucher")
        assert voucher.status == "draft"
        assert voucher.bill_id is None
        assert voucher.number != "LC-99999"
        assert voucher.estimated_total == Decimal("0.00")
        assert voucher.actual_total == Decimal("0.00")
        assert voucher.allocated_total == Decimal("0.00")
        assert voucher.variance_pct is None
        assert voucher.accrued_at is None

    @pytest.mark.parametrize("field,fixture_name", [
        ("party", "supplier_b"),
        ("freight_invoice", "freight_invoice_b"),
        ("gl_account", "gl_expense_b"),
        ("tax_code", "finance_tax_code_b"),
    ])
    def test_finance_charge_create_refuses_a_foreign_fk(self, request, client_a, finance_voucher_a,
                                                        field, fixture_name):
        from apps.scm.models import LandedCostCharge
        foreign = request.getfixturevalue(fixture_name)
        response = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload(**{field: str(foreign.pk)}))
        assert response.status_code == 200
        assert field in response.context["form"].errors
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_a).exists()
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.estimated_total == Decimal("0.00")

    def test_finance_charge_create_accepts_its_own_workspace_rows(self, client_a,
                                                                  finance_voucher_a, supplier_a,
                                                                  freight_invoice_a, gl_expense,
                                                                  finance_tax_code_a):
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload(party=str(supplier_a.pk),
                                    freight_invoice=str(freight_invoice_a.pk),
                                    gl_account=str(gl_expense.pk),
                                    tax_code=str(finance_tax_code_a.pk)))
        assert response.status_code == 302
        charge = LandedCostCharge.objects.get(voucher=finance_voucher_a)
        assert charge.gl_account_id == gl_expense.pk
        assert charge.tax_code_id == finance_tax_code_a.pk
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.estimated_total == Decimal("75.00")

    def test_finance_charge_edit_refuses_a_foreign_gl_account(self, client_a, finance_charge_a,
                                                              gl_expense_b):
        response = client_a.post(
            reverse("scm:landedcostcharge_edit", args=[finance_charge_a.pk]),
            _finance_charge_payload(description="Ocean freight",
                                    estimated_amount="100.00",
                                    gl_account=str(gl_expense_b.pk)))
        assert response.status_code == 200
        assert "gl_account" in response.context["form"].errors
        finance_charge_a.refresh_from_db()
        assert finance_charge_a.gl_account_id != gl_expense_b.pk

    def test_finance_charge_create_ignores_a_posted_parent(self, client_a, finance_voucher_a,
                                                           finance_voucher_b):
        """``voucher`` is NOT a form field — the parent comes from the ROUTE, never the body.

        A parent pk in a POST body is exactly how a caller grafts a charge onto another workspace's
        voucher, which is why the route is nested and the field excluded.
        """
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload(voucher=str(finance_voucher_b.pk)))
        assert response.status_code == 302
        assert LandedCostCharge.objects.filter(voucher=finance_voucher_a).count() == 1
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_b).exists()

    def test_finance_charge_edit_ignores_a_posted_parent(self, client_a, finance_charge_a,
                                                         finance_voucher_a, finance_voucher_b):
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_edit", args=[finance_charge_a.pk]),
            _finance_charge_payload(description="Re-described", estimated_amount="100.00",
                                    voucher=str(finance_voucher_b.pk)))
        assert response.status_code == 302
        finance_charge_a.refresh_from_db()
        assert finance_charge_a.voucher_id == finance_voucher_a.pk
        assert finance_charge_a.description == "Re-described"
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_b).exists()


# =================================================================================================
# Negative input — junk filters, pagination, and hand-typed decimals
# =================================================================================================
class TestFinanceNegativeInput:
    @pytest.mark.parametrize("url_name,params", _FINANCE_JUNK_QUERIES,
                             ids=[f"{name.split(':')[1]}-{'&'.join(params) or 'none'}"
                                  for name, params in _FINANCE_JUNK_QUERIES])
    def test_finance_junk_filter_param_is_200(self, client_a, finance_duty_tariff_a, url_name,
                                              params):
        assert client_a.get(reverse(url_name), params).status_code == 200

    def test_finance_junk_status_does_not_narrow_the_tariff_list(self, client_a,
                                                                 finance_duty_tariff_a):
        """L11 posture: an unrecognised ``?status`` narrows NOTHING (and does not 500)."""
        response = client_a.get(reverse("scm:dutytariff_list"), {"status": "banana"})
        assert response.status_code == 200
        assert finance_duty_tariff_a.pk in {obj.pk for obj in response.context["object_list"]}

    def test_finance_real_status_narrows_the_tariff_list(self, client_a, tenant_a,
                                                         finance_duty_tariff_a):
        """The POSITIVE half — the guard must not have disabled the filter (L44)."""
        from apps.scm.models import DutyTariff
        retired = DutyTariff.objects.create(
            tenant=tenant_a, hs_code="1234.56", country_of_origin="Italy",
            duty_rate_pct=Decimal("1.000"), is_active=False,
            effective_from=timezone.localdate() - datetime.timedelta(days=5))
        active = client_a.get(reverse("scm:dutytariff_list"), {"status": "active"})
        assert {obj.pk for obj in active.context["object_list"]} == {finance_duty_tariff_a.pk}
        inactive = client_a.get(reverse("scm:dutytariff_list"), {"status": "inactive"})
        assert {obj.pk for obj in inactive.context["object_list"]} == {retired.pk}

    def test_finance_junk_party_does_not_narrow_the_voucher_list(self, client_a,
                                                                 finance_voucher_a):
        response = client_a.get(reverse("scm:landedcostvoucher_list"), {"party": "abc"})
        assert response.status_code == 200
        assert finance_voucher_a.pk in {obj.pk for obj in response.context["object_list"]}

    def test_finance_real_party_narrows_the_voucher_list(self, client_a, finance_voucher_a,
                                                         vendor_a):
        response = client_a.get(reverse("scm:landedcostvoucher_list"),
                                {"party": str(finance_voucher_a.party_id)})
        assert finance_voucher_a.pk in {obj.pk for obj in response.context["object_list"]}
        other = client_a.get(reverse("scm:landedcostvoucher_list"), {"party": str(vendor_a.pk)})
        assert list(other.context["object_list"]) == []

    def test_finance_junk_group_falls_back_to_the_default(self, client_a, finance_charge_a):
        response = client_a.get(reverse("scm:landed_cost_variance"), {"group": "lol"})
        assert response.status_code == 200
        assert response.context["group"] == "charge_type"
        assert {row["label"] for row in response.context["rows"]} == {"Freight"}

    def test_finance_real_group_switch_regroups(self, client_a, finance_allocated_voucher_a,
                                               item_a):
        """The POSITIVE half — ``?group=item`` must genuinely regroup, not just survive."""
        response = client_a.get(reverse("scm:landed_cost_variance"), {"group": "item"})
        assert response.status_code == 200
        assert response.context["group"] == "item"
        assert {row["key"] for row in response.context["rows"]} == {item_a.pk}

    def test_finance_junk_date_window_narrows_nothing(self, client_a, finance_charge_a):
        response = client_a.get(reverse("scm:landed_cost_variance"),
                                {"date_from": "nope", "date_to": "2026-13-45"})
        assert response.status_code == 200
        assert response.context["date_from"] is None
        assert response.context["date_to"] is None
        assert response.context["rows"]

    def test_finance_real_date_window_narrows(self, client_a, finance_charge_a):
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        response = client_a.get(reverse("scm:landed_cost_variance"),
                                {"date_from": tomorrow.isoformat()})
        assert response.status_code == 200
        assert response.context["date_from"] == tomorrow
        assert response.context["rows"] == []

    def test_finance_page_past_the_end_is_200_on_the_tariff_list(self, client_a, tenant_a):
        _finance_bulk_tariffs(tenant_a, 21)
        response = client_a.get(reverse("scm:dutytariff_list"), {"page": "999"})
        assert response.status_code == 200
        page = response.context["page_obj"]
        assert page.number == page.paginator.num_pages

    def test_finance_page_past_the_end_is_200_on_the_voucher_list(self, client_a, tenant_a,
                                                                  finance_receipt_a, supplier_a):
        _finance_bulk_vouchers(tenant_a, finance_receipt_a, supplier_a, 21)
        response = client_a.get(reverse("scm:landedcostvoucher_list"), {"page": "999"})
        assert response.status_code == 200
        page = response.context["page_obj"]
        assert page.number == page.paginator.num_pages

    @pytest.mark.parametrize("bad", _FINANCE_POISONED_MONEY)
    def test_finance_charge_refuses_a_poisoned_estimate(self, client_a, finance_voucher_a, bad):
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload(estimated_amount=bad))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_a).exists()
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.estimated_total == Decimal("0.00")

    @pytest.mark.parametrize("bad", _FINANCE_POISONED_MONEY)
    def test_finance_charge_refuses_a_poisoned_actual(self, client_a, finance_voucher_a, bad):
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload(actual_amount=bad))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_a).exists()

    @pytest.mark.parametrize("bad", ["NaN", "Infinity", "abc", "-1.000", "150.000",
                                     "9999999.999"])
    def test_finance_charge_refuses_a_poisoned_duty_rate(self, client_a, finance_voucher_a, bad):
        """``duty_rate_pct`` is ``DECIMAL(6,3)`` with ``Min 0`` / ``Max 100`` — all six are errors."""
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload(charge_type="duty", hs_code="8471.30", duty_rate_pct=bad))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_a).exists()

    def test_finance_charge_refuses_a_duty_rate_on_a_non_duty_type(self, client_a,
                                                                   finance_voucher_a):
        """``LandedCostCharge.clean()`` — a friendly field error, never a 500."""
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload(charge_type="freight", duty_rate_pct="2.500"))
        assert response.status_code == 200
        assert "duty_rate_pct" in response.context["form"].errors
        assert "customs duty charge" in str(
            response.context["form"].errors["duty_rate_pct"]).lower()
        assert not LandedCostCharge.objects.filter(voucher=finance_voucher_a).exists()

    def test_finance_charge_accepts_a_sane_figure(self, client_a, finance_voucher_a, gl_expense):
        """The POSITIVE half — the decimal guards must not have blocked the feature (L44)."""
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_voucher_a.pk]),
            _finance_charge_payload(estimated_amount="120.50", actual_amount="130.75",
                                    gl_account=str(gl_expense.pk)))
        assert response.status_code == 302
        charge = LandedCostCharge.objects.get(voucher=finance_voucher_a)
        assert charge.allocatable_amount == Decimal("130.75")
        assert charge.duty_rate_pct == Decimal("0")
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.actual_total == Decimal("130.75")
        assert finance_voucher_a.variance_amount == Decimal("10.25")

    @pytest.mark.parametrize("bad", ["NaN", "Infinity", "abc", "-1.000", "150.000",
                                     "9999999.999"])
    def test_finance_tariff_refuses_a_poisoned_rate(self, client_a, bad):
        from apps.scm.models import DutyTariff
        before = DutyTariff.objects.count()
        response = client_a.post(reverse("scm:dutytariff_create"),
                                 _finance_tariff_payload(duty_rate_pct=bad))
        assert response.status_code == 200
        assert "duty_rate_pct" in response.context["form"].errors
        assert DutyTariff.objects.count() == before

    def test_finance_tariff_refuses_an_inverted_window(self, client_a):
        """``effective_to < effective_from`` — a model ``clean()`` bound keyed on a real form field."""
        from apps.scm.models import DutyTariff
        today = timezone.localdate()
        before = DutyTariff.objects.count()
        response = client_a.post(
            reverse("scm:dutytariff_create"),
            _finance_tariff_payload(effective_from=today.isoformat(),
                                    effective_to=(today - datetime.timedelta(days=3)).isoformat()))
        assert response.status_code == 200
        assert "effective_to" in response.context["form"].errors
        assert "would stop applying" in str(
            response.context["form"].errors["effective_to"]).lower()
        assert DutyTariff.objects.count() == before

    def test_finance_tariff_refuses_a_missing_start_date(self, client_a):
        from apps.scm.models import DutyTariff
        before = DutyTariff.objects.count()
        response = client_a.post(reverse("scm:dutytariff_create"),
                                 _finance_tariff_payload(effective_from=""))
        assert response.status_code == 200
        assert "effective_from" in response.context["form"].errors
        assert DutyTariff.objects.count() == before

    def test_finance_duplicate_tariff_key_is_a_form_error_not_a_500(self, client_a,
                                                                    finance_duty_tariff_a):
        """``TenantUniqueMixin`` is load-bearing: without it this is an uncaught IntegrityError."""
        from apps.scm.models import DutyTariff
        before = DutyTariff.objects.count()
        response = client_a.post(
            reverse("scm:dutytariff_create"),
            _finance_tariff_payload(hs_code="  8471.30  ", country_of_origin="Germany",
                                    effective_from=finance_duty_tariff_a.effective_from.isoformat()))
        assert response.status_code == 200
        assert response.context["form"].errors
        assert DutyTariff.objects.count() == before

    def test_finance_a_different_origin_on_the_same_code_still_saves(self, client_a, tenant_a,
                                                                     finance_duty_tariff_a):
        """The POSITIVE half — the uniqueness guard must not have blocked a legitimate row (L44)."""
        from apps.scm.models import DutyTariff
        response = client_a.post(
            reverse("scm:dutytariff_create"),
            _finance_tariff_payload(hs_code="8471.30", country_of_origin="Japan",
                                    effective_from=finance_duty_tariff_a.effective_from.isoformat()))
        assert response.status_code == 302
        assert DutyTariff.objects.filter(tenant=tenant_a, hs_code="8471.30",
                                         country_of_origin="Japan").exists()

    def test_finance_report_source_filter_survives_junk_and_still_works(self, client_a,
                                                                        finance_voucher_a):
        junk = client_a.get(reverse("scm:finance_payables"), {"source": "lol"})
        assert junk.status_code == 200
        # Junk narrows NOTHING, so every source is still built.
        assert {row["source"] for row in junk.context["rows"]} >= {"grn", "landed"}
        real = client_a.get(reverse("scm:finance_payables"), {"source": "landed"})
        assert real.status_code == 200
        assert {row["source"] for row in real.context["rows"]} == {"landed"}


# =================================================================================================
# Absent prerequisites are REJECTED, not fallen through (L35)
# =================================================================================================
class TestFinanceLadderPrerequisites:
    def test_finance_allocate_refuses_an_unposted_receipt(self, client_a,
                                                          _finance_unposted_voucher_a):
        from apps.scm.models import LandedCostAllocation
        response = client_a.post(
            reverse("scm:landedcostvoucher_allocate", args=[_finance_unposted_voucher_a.pk]),
            follow=True)
        assert response.status_code == 200
        assert any("not been posted to the stock ledger" in message
                   for message in _finance_flash(response))
        _finance_unposted_voucher_a.refresh_from_db()
        assert _finance_unposted_voucher_a.status == "draft"
        assert _finance_unposted_voucher_a.allocated_total == Decimal("0.00")
        assert not LandedCostAllocation.objects.filter(
            voucher=_finance_unposted_voucher_a).exists()

    def test_finance_allocate_accepts_a_posted_receipt(self, client_a, finance_voucher_a,
                                                       finance_charge_a):
        """The POSITIVE half of the prerequisite (L44)."""
        from apps.scm.models import LandedCostAllocation
        response = client_a.post(
            reverse("scm:landedcostvoucher_allocate", args=[finance_voucher_a.pk]), follow=True)
        assert any("allocated" in message for message in _finance_flash(response))
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "allocated"
        allocation = LandedCostAllocation.objects.get(voucher=finance_voucher_a)
        assert allocation.allocated_amount == Decimal("100.00")
        assert allocation.unit_cost_uplift == Decimal("10.0000")

    def test_finance_allocate_refuses_a_voucher_where_nothing_capitalises(
            self, client_a, finance_recoverable_voucher_a):
        from apps.scm.models import LandedCostAllocation
        response = client_a.post(
            reverse("scm:landedcostvoucher_allocate", args=[finance_recoverable_voucher_a.pk]),
            follow=True)
        assert any("capitalises into inventory" in message
                   for message in _finance_flash(response))
        finance_recoverable_voucher_a.refresh_from_db()
        assert finance_recoverable_voucher_a.status == "draft"
        assert not LandedCostAllocation.objects.exists()

    def test_finance_allocate_refuses_a_cancelled_voucher(self, client_a, finance_voucher_a,
                                                          finance_charge_a):
        finance_voucher_a.cancel()
        response = client_a.post(
            reverse("scm:landedcostvoucher_allocate", args=[finance_voucher_a.pk]), follow=True)
        assert any("cancelled landed cost voucher cannot be allocated" in message
                   for message in _finance_flash(response))
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "cancelled"

    def test_finance_allocate_refuses_a_billed_voucher(self, client_a, _finance_billed_voucher_a):
        response = client_a.post(
            reverse("scm:landedcostvoucher_allocate", args=[_finance_billed_voucher_a.pk]),
            follow=True)
        assert any("has been billed as" in message for message in _finance_flash(response))
        _finance_billed_voucher_a.refresh_from_db()
        assert _finance_billed_voucher_a.status == "reconciled"

    def test_finance_accrue_refuses_a_draft_voucher(self, client_a, finance_voucher_a,
                                                    finance_charge_a):
        response = client_a.post(
            reverse("scm:landedcostvoucher_accrue", args=[finance_voucher_a.pk]), follow=True)
        assert any("only an allocated voucher can be accrued" in message
                   for message in _finance_flash(response))
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "draft"
        assert finance_voucher_a.accrued_at is None

    def test_finance_accrue_accepts_an_allocated_voucher(self, client_a,
                                                         finance_allocated_voucher_a):
        response = client_a.post(
            reverse("scm:landedcostvoucher_accrue", args=[finance_allocated_voucher_a.pk]))
        assert response.status_code == 302
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.status == "accrued"

    def test_finance_draft_bill_refuses_an_unallocated_capitalising_voucher(
            self, client_a, finance_voucher_a, finance_charge_a):
        from apps.accounting.models import Bill
        before = Bill.objects.count()
        response = client_a.post(
            reverse("scm:landedcostvoucher_draft_bill", args=[finance_voucher_a.pk]), follow=True)
        assert any("allocate the landed costs before drafting" in message
                   for message in _finance_flash(response))
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "draft"
        assert finance_voucher_a.bill_id is None
        assert Bill.objects.count() == before

    def test_finance_draft_bill_accepts_an_allocated_voucher(self, client_a,
                                                             finance_allocated_voucher_a):
        from apps.accounting.models import Bill
        response = client_a.post(
            reverse("scm:landedcostvoucher_draft_bill", args=[finance_allocated_voucher_a.pk]),
            follow=True)
        assert any("drafted bill" in message for message in _finance_flash(response))
        finance_allocated_voucher_a.refresh_from_db()
        bill = Bill.objects.get(pk=finance_allocated_voucher_a.bill_id)
        assert bill.status == "draft"
        assert finance_allocated_voucher_a.status == "reconciled"

    def test_finance_draft_bill_refuses_a_second_draft(self, client_a,
                                                       finance_allocated_voucher_a):
        """Pressing the button twice must not raise a second vendor bill — and must SAY why."""
        from apps.accounting.models import Bill
        url = reverse("scm:landedcostvoucher_draft_bill",
                      args=[finance_allocated_voucher_a.pk])
        assert client_a.post(url).status_code == 302
        before = Bill.objects.count()
        response = client_a.post(url, follow=True)
        assert response.status_code == 200
        messages = _finance_flash(response)
        assert messages, "a second draft attempt must say something, not pass silently"
        assert any("is already billed as" in message for message in messages)
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.bill.number.lower() in " ".join(messages)
        assert Bill.objects.count() == before

    def test_finance_cancel_refuses_a_second_cancel(self, client_a, finance_voucher_a,
                                                    finance_charge_a):
        url = reverse("scm:landedcostvoucher_cancel", args=[finance_voucher_a.pk])
        assert client_a.post(url).status_code == 302
        response = client_a.post(url, follow=True)
        assert any("already cancelled" in message for message in _finance_flash(response))
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "cancelled"

    def test_finance_cancel_refuses_a_billed_voucher(self, client_a, _finance_billed_voucher_a):
        response = client_a.post(
            reverse("scm:landedcostvoucher_cancel", args=[_finance_billed_voucher_a.pk]),
            follow=True)
        assert any("cannot be cancelled here" in message for message in _finance_flash(response))
        _finance_billed_voucher_a.refresh_from_db()
        assert _finance_billed_voucher_a.status == "reconciled"

    def test_finance_voucher_edit_refuses_an_allocated_voucher(self, client_a,
                                                               finance_allocated_voucher_a,
                                                               finance_receipt_a, supplier_a):
        response = client_a.post(
            reverse("scm:landedcostvoucher_edit", args=[finance_allocated_voucher_a.pk]),
            _finance_voucher_payload(finance_receipt_a, supplier_a, notes="rewritten"),
            follow=True)
        assert any("can no longer be edited" in message for message in _finance_flash(response))
        finance_allocated_voucher_a.refresh_from_db()
        assert finance_allocated_voucher_a.notes != "rewritten"

    def test_finance_voucher_edit_accepts_a_draft_voucher(self, client_a, finance_voucher_a,
                                                          finance_receipt_a, supplier_a):
        response = client_a.post(
            reverse("scm:landedcostvoucher_edit", args=[finance_voucher_a.pk]),
            _finance_voucher_payload(finance_receipt_a, supplier_a, notes="rewritten"))
        assert response.status_code == 302
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.notes == "rewritten"

    def test_finance_voucher_delete_refuses_an_allocated_voucher(self, client_a,
                                                                 finance_allocated_voucher_a):
        from apps.scm.models import LandedCostVoucher
        response = client_a.post(
            reverse("scm:landedcostvoucher_delete", args=[finance_allocated_voucher_a.pk]),
            follow=True)
        assert any("can't be deleted" in message for message in _finance_flash(response))
        assert LandedCostVoucher.objects.filter(pk=finance_allocated_voucher_a.pk).exists()

    def test_finance_voucher_delete_refuses_a_billed_voucher(self, client_a,
                                                             _finance_billed_voucher_a):
        from apps.scm.models import LandedCostVoucher
        response = client_a.post(
            reverse("scm:landedcostvoucher_delete", args=[_finance_billed_voucher_a.pk]),
            follow=True)
        assert any("can't be deleted" in message for message in _finance_flash(response))
        assert LandedCostVoucher.objects.filter(pk=_finance_billed_voucher_a.pk).exists()

    def test_finance_voucher_delete_accepts_a_draft_voucher(self, client_a, finance_voucher_a):
        from apps.scm.models import LandedCostVoucher
        response = client_a.post(
            reverse("scm:landedcostvoucher_delete", args=[finance_voucher_a.pk]))
        assert response.status_code == 302
        assert not LandedCostVoucher.objects.filter(pk=finance_voucher_a.pk).exists()

    def test_finance_charge_writes_are_refused_on_an_allocated_voucher(
            self, client_a, finance_allocated_voucher_a, finance_charge_a):
        from apps.scm.models import LandedCostCharge
        create = client_a.post(
            reverse("scm:landedcostcharge_create", args=[finance_allocated_voucher_a.pk]),
            _finance_charge_payload(description="sneaked in"), follow=True)
        assert any("no longer take new charges" in message for message in _finance_flash(create))
        assert not LandedCostCharge.objects.filter(description="sneaked in").exists()

        edit = client_a.post(
            reverse("scm:landedcostcharge_edit", args=[finance_charge_a.pk]),
            _finance_charge_payload(description="rewritten"), follow=True)
        assert any("can no longer be edited" in message for message in _finance_flash(edit))
        finance_charge_a.refresh_from_db()
        assert finance_charge_a.description == "Ocean freight"

        delete = client_a.post(
            reverse("scm:landedcostcharge_delete", args=[finance_charge_a.pk]), follow=True)
        assert any("can no longer be deleted" in message for message in _finance_flash(delete))
        assert LandedCostCharge.objects.filter(pk=finance_charge_a.pk).exists()

    def test_finance_charge_delete_accepts_a_draft_voucher(self, client_a, finance_voucher_a,
                                                           finance_charge_a):
        """The POSITIVE half — and the parent is re-totalled in the SAME transaction."""
        from apps.scm.models import LandedCostCharge
        response = client_a.post(
            reverse("scm:landedcostcharge_delete", args=[finance_charge_a.pk]))
        assert response.status_code == 302
        assert not LandedCostCharge.objects.filter(pk=finance_charge_a.pk).exists()
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.estimated_total == Decimal("0.00")


# =================================================================================================
# POST-only routes — a GET must be a 405, never a silent state change
# =================================================================================================
class TestFinancePostOnlyRoutes:
    @pytest.mark.parametrize("url_name,fixture_name", _FINANCE_POST_ONLY_ROUTES,
                             ids=[name.split(":")[1] for name, _ in _FINANCE_POST_ONLY_ROUTES])
    def test_finance_get_on_a_post_only_route_is_405(self, request, client_a, url_name,
                                                     fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 405

    def test_finance_get_on_a_post_only_route_is_405_even_for_a_bogus_pk(self, client_a):
        """``@require_POST`` fires BEFORE ``get_object_or_404`` — so this is 405, not 404."""
        assert client_a.get(reverse("scm:dutytariff_delete", args=[999999])).status_code == 405
        assert client_a.get(
            reverse("scm:landedcostvoucher_allocate", args=[999999])).status_code == 405

    def test_finance_get_on_delete_deletes_nothing(self, client_a, finance_duty_tariff_a,
                                                   finance_voucher_a, finance_charge_a):
        from apps.scm.models import DutyTariff, LandedCostCharge, LandedCostVoucher
        client_a.get(reverse("scm:dutytariff_delete", args=[finance_duty_tariff_a.pk]))
        client_a.get(reverse("scm:landedcostvoucher_delete", args=[finance_voucher_a.pk]))
        client_a.get(reverse("scm:landedcostcharge_delete", args=[finance_charge_a.pk]))
        assert DutyTariff.objects.filter(pk=finance_duty_tariff_a.pk).exists()
        assert LandedCostVoucher.objects.filter(pk=finance_voucher_a.pk).exists()
        assert LandedCostCharge.objects.filter(pk=finance_charge_a.pk).exists()

    @pytest.mark.parametrize("url_name", _FINANCE_MONEY_VERBS,
                             ids=[name.split(":")[1] for name in _FINANCE_MONEY_VERBS])
    def test_finance_get_on_a_money_verb_changes_nothing(self, client_a, url_name,
                                                         finance_voucher_a, finance_charge_a):
        from apps.scm.models import LandedCostAllocation
        assert client_a.get(reverse(url_name, args=[finance_voucher_a.pk])).status_code == 405
        finance_voucher_a.refresh_from_db()
        assert finance_voucher_a.status == "draft"
        assert finance_voucher_a.bill_id is None
        assert not LandedCostAllocation.objects.exists()

    def test_finance_member_get_on_a_money_verb_is_403_not_405(self, member_client,
                                                               finance_voucher_a):
        """``@tenant_admin_required`` wraps ``@require_POST``, so the ROLE is checked first."""
        assert member_client.get(
            reverse("scm:landedcostvoucher_allocate",
                    args=[finance_voucher_a.pk])).status_code == 403


# =================================================================================================
# NOT HERE, deliberately: the list query budget (the chained ``__str__`` FK hop) and the
# pagination happy path are asserted ONCE, in ``test_finance_views.py`` — that lane's versions are
# scale-invariant (3 rows vs. 21 must cost the same) rather than a fixed ceiling, so duplicating
# them here would only have added a weaker second copy of the same assertion.
# =================================================================================================
