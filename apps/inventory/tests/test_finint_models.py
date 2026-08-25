"""Inventory 5.18 Accounting & Financial Integration — model + service tests.

Covers TaxRule resolution semantics, the GLPostRule account map, and both posting
services' happy paths and refusals against a REAL scm.StockAdjustment / StockMove ledger.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounting.models import FiscalPeriod, GLAccount, JournalEntry, JournalLine, TaxCode
from apps.inventory.models import (
    GLPostRule,
    JournalSyncLog,
    TaxRule,
    post_adjustment_to_gl,
    post_cogs_batch,
)
from apps.scm.models import Item, Location, StockAdjustment, StockAdjustmentLine, StockMove


# ----------------------------------------------------------------------------- local fixtures

@pytest.fixture
def gl_accounts(db, tenant_a):
    inv = GLAccount.objects.create(tenant=tenant_a, code="1500", name="Inventory",
                                   account_type="asset")
    cogs = GLAccount.objects.create(tenant=tenant_a, code="5000", name="Cost of Goods Sold",
                                    account_type="expense")
    gain = GLAccount.objects.create(tenant=tenant_a, code="6100", name="Adjustment Gain/Loss",
                                    account_type="expense")
    return {"inventory": inv, "cogs": cogs, "gain": gain}


@pytest.fixture
def open_period(db, tenant_a):
    today = timezone.localdate()
    return FiscalPeriod.objects.create(
        tenant=tenant_a, name=f"{today:%b %Y}", period_type="month",
        start_date=today.replace(day=1), end_date=today + datetime.timedelta(days=28),
        status="open")


@pytest.fixture
def adjustment_rule(db, tenant_a, gl_accounts):
    return GLPostRule.objects.create(
        tenant=tenant_a, event_type="adjustment", name="Stock adjustments",
        inventory_account=gl_accounts["inventory"], offset_account=gl_accounts["gain"])


@pytest.fixture
def cogs_rule(db, tenant_a, gl_accounts):
    return GLPostRule.objects.create(
        tenant=tenant_a, event_type="cogs", name="Customer issues COGS",
        inventory_account=gl_accounts["inventory"], offset_account=gl_accounts["cogs"])


def _posted_adjustment(tenant, item, location, *, delta=Decimal("2"), cost=Decimal("10")):
    adj = StockAdjustment.objects.create(
        tenant=tenant, location=location, reason="cycle_count", status="draft",
        adjustment_date=timezone.localdate(), notes="probe")
    StockAdjustmentLine.objects.create(adjustment=adj, item=item,
                                       quantity_delta=delta, unit_cost=cost)
    adj.status = "posted"
    adj.posted_at = timezone.now()
    adj.save(update_fields=["status", "posted_at", "updated_at"])
    return adj


# --------------------------------------------------------------------------------- TaxRule

def test_finint_taxrule_numbering_and_uniqueness(tenant_a, item_a, db):
    TaxRule.objects.create(tenant=tenant_a, name="Default", tax_code_id=_tax_code(tenant_a).pk)
    assert TaxRule.objects.get(tenant=tenant_a, name="Default").number.startswith("TRT-")
    with pytest.raises(IntegrityError):
        TaxRule.objects.create(tenant=tenant_a, name="Default",
                               tax_code_id=_tax_code(tenant_a).pk)


def _tax_code(tenant):
    return TaxCode.objects.create(tenant=tenant, name="Probe Tax", rate_pct=Decimal("8.25"))


def test_finint_taxrule_resolver_specificity_ladder(tenant_a, item_a, db):
    """SKU rule beats category rule beats catch-all."""
    from apps.scm.models import ItemCategory

    cat = ItemCategory.objects.create(tenant=tenant_a, name="Fin Category")
    item_a.category = cat
    item_a.save(update_fields=["category", "updated_at"])

    code = _tax_code(tenant_a)
    catch_all = TaxRule.objects.create(tenant=tenant_a, name="All", tax_code=code, priority=900)
    assert TaxRule.resolve(tenant_a, item=item_a).pk == catch_all.pk

    category_pin = TaxRule.objects.create(tenant=tenant_a, name="Cat", tax_code=code,
                                          category=cat)
    assert TaxRule.resolve(tenant_a, item=item_a).pk == category_pin.pk

    item_pin = TaxRule.objects.create(tenant=tenant_a, name="Sku", tax_code=code, item=item_a)
    assert TaxRule.resolve(tenant_a, item=item_a).pk == item_pin.pk


def test_finint_taxrule_country_beats_wildcard_at_same_tier(tenant_a, item_a, db):
    code = _tax_code(tenant_a)
    wild = TaxRule.objects.create(tenant=tenant_a, name="Any geo", tax_code=code, priority=1)
    named = TaxRule.objects.create(tenant=tenant_a, name="Germany", country="Germany",
                                   tax_code=code, priority=999)
    assert TaxRule.resolve(tenant_a, item=None, country="germany").pk == named.pk
    assert TaxRule.resolve(tenant_a, item=None, country="France").pk == wild.pk


def test_finint_taxrule_inactive_skipped_and_rate_for_zero_default(tenant_a, item_a, db):
    code = _tax_code(tenant_a)
    only = TaxRule.objects.create(tenant=tenant_a, name="Only", tax_code=code, is_active=False)
    assert TaxRule.resolve(tenant_a, item=item_a) is None
    assert TaxRule.rate_for(tenant_a, item=item_a) == Decimal("0")
    only.is_active = True
    only.save()
    assert TaxRule.rate_for(tenant_a, item=item_a) == Decimal("8.25")


# ------------------------------------------------------------------------------- GLPostRule

def test_finint_glpostrule_one_mapping_per_event_type_per_tenant(tenant_a, tenant_b,
                                                                 gl_accounts, db):
    GLPostRule.objects.create(tenant=tenant_a, event_type="adjustment", name="A",
                              inventory_account=gl_accounts["inventory"],
                              offset_account=gl_accounts["gain"])
    # same event type, other tenant — legal; same tenant — refused by unique_together
    GLPostRule.objects.create(tenant=tenant_b, event_type="adjustment", name="B",
                              inventory_account=gl_accounts["inventory"],
                              offset_account=gl_accounts["gain"])
    with pytest.raises(IntegrityError):
        GLPostRule.objects.create(tenant=tenant_a, event_type="adjustment", name="A2",
                                  inventory_account=gl_accounts["inventory"],
                                  offset_account=gl_accounts["gain"])


# --------------------------------------------------------------- posting services: adjustment

@pytest.fixture
def finint_item_location(db, tenant_a):
    item = Item.objects.create(tenant=tenant_a, sku="FIN-1", name="Fin Widget")
    loc = Location.objects.create(tenant=tenant_a, code="FIN-BIN", name="Bin",
                                  location_type="bin")
    return item, loc


@pytest.mark.django_db
def test_finint_post_adjustment_gain_direction(tenant_a, admin_user, adjustment_rule,
                                               open_period, finint_item_location):
    item, loc = finint_item_location
    adj = _posted_adjustment(tenant_a, item, loc, delta=Decimal("2"), cost=Decimal("10"))
    log, je = post_adjustment_to_gl(tenant_a, admin_user, adj)
    assert log.number.startswith("JSY-") and je.status == "posted"
    lines = {l.gl_account_id: l for l in je.lines.all()}
    debit = sum(l.debit for l in je.lines.all())
    credit = sum(l.credit for l in je.lines.all())
    assert debit == credit == Decimal("20.00")
    # found stock: DR inventory, CR offset
    assert lines[adjustment_rule.inventory_account_id].debit == Decimal("20.00")
    assert lines[adjustment_rule.offset_account_id].credit == Decimal("20.00")


@pytest.mark.django_db
def test_finint_post_adjustment_writeoff_direction_and_double_post_refusal(
        tenant_a, admin_user, adjustment_rule, open_period, finint_item_location):
    item, loc = finint_item_location
    adj = _posted_adjustment(tenant_a, item, loc, delta=Decimal("-3"), cost=Decimal("5"))
    log, je = post_adjustment_to_gl(tenant_a, admin_user, adj)
    lines = {l.gl_account_id: l for l in je.lines.all()}
    assert lines[adjustment_rule.offset_account_id].debit == Decimal("15.00")
    assert lines[adjustment_rule.inventory_account_id].credit == Decimal("15.00")
    with pytest.raises(ValidationError):
        post_adjustment_to_gl(tenant_a, admin_user, adj)


@pytest.mark.django_db
def test_finint_post_adjustment_refusals(tenant_a, admin_user, adjustment_rule,
                                         finint_item_location):
    item, loc = finint_item_location
    draft = StockAdjustment.objects.create(
        tenant=tenant_a, location=loc, reason="cycle_count", status="draft",
        adjustment_date=timezone.localdate())
    with pytest.raises(ValidationError):
        post_adjustment_to_gl(tenant_a, admin_user, draft)  # not posted

    zero = _posted_adjustment(tenant_a, item, loc, delta=Decimal("0"))
    with pytest.raises(ValidationError):
        post_adjustment_to_gl(tenant_a, admin_user, zero)  # net-zero value

    with pytest.raises(ValidationError):  # no open fiscal period anywhere in this block
        posted = _posted_adjustment(tenant_a, item, loc)
        post_adjustment_to_gl(tenant_a, admin_user, posted)


# -------------------------------------------------------------- posting services: COGS batch

@pytest.mark.django_db
def test_finint_cogs_batch_posts_balanced_entry_and_refuses_overlap(
        tenant_a, admin_user, cogs_rule, open_period, finint_item_location):
    item, loc = finint_item_location
    now = timezone.now()
    StockMove.objects.create(tenant=tenant_a, item=item, location=loc, quantity=-Decimal("4"),
                             unit_cost=Decimal("7"), move_type="issue", moved_at=now)
    StockMove.objects.create(tenant=tenant_a, item=item, location=loc, quantity=-Decimal("1"),
                             unit_cost=Decimal("9"), move_type="issue", moved_at=now)

    log, je = post_cogs_batch(tenant_a, admin_user,
                              timezone.localdate() - datetime.timedelta(days=7),
                              timezone.localdate())
    assert log.moves_count == 2 and log.total_value == Decimal("37.00")
    assert je.status == "posted"
    debit = sum(l.debit for l in je.lines.all())
    credit = sum(l.credit for l in je.lines.all())
    assert debit == credit == Decimal("37.00")
    assert {l.gl_account_id for l in je.lines.all()} == {
        cogs_rule.offset_account_id, cogs_rule.inventory_account_id}

    with pytest.raises(ValidationError):
        post_cogs_batch(tenant_a, admin_user,
                        timezone.localdate() - datetime.timedelta(days=1),
                        timezone.localdate())  # overlaps


@pytest.mark.django_db
def test_finint_cogs_batch_empty_window_and_bad_range(tenant_a, admin_user, cogs_rule,
                                                      open_period, finint_item_location):
    with pytest.raises(ValidationError):
        post_cogs_batch(tenant_a, admin_user,
                        timezone.localdate() - datetime.timedelta(days=3),
                        timezone.localdate())  # no moves
    with pytest.raises(ValidationError):
        post_cogs_batch(tenant_a, admin_user, timezone.localdate(),
                        timezone.localdate() - datetime.timedelta(days=3))  # inverted
