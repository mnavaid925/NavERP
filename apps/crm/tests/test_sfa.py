"""Tests for CRM §1.2 Sales Force Automation sub-module.

Covers: enhanced Opportunity, Territory, Product, PriceBook, OpportunitySplit,
Quote, QuoteLine, SalesQuota — models, forms, views, action endpoints, and
multi-tenant IDOR isolation.
"""
import pytest
from decimal import Decimal
from django.urls import reverse
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db


# =================================================================== Fixtures

@pytest.fixture
def account_a(db, tenant_a):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization", name="Acme Ltd")


@pytest.fixture
def account_b(db, tenant_b):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Ltd")


@pytest.fixture
def territory_a(db, tenant_a, admin_user):
    from apps.crm.models import Territory
    return Territory.objects.create(
        tenant=tenant_a, name="West Coast", region="AMER", segment="SMB", manager=admin_user
    )


@pytest.fixture
def territory_b(db, tenant_b, admin_b):
    from apps.crm.models import Territory
    return Territory.objects.create(
        tenant=tenant_b, name="East Region", region="AMER", segment="Enterprise"
    )


@pytest.fixture
def product_a(db, tenant_a):
    from apps.crm.models import Product
    return Product.objects.create(
        tenant=tenant_a, name="Widget Pro", sku="WGT-001",
        product_type="good", unit_price="100.00", cost="60.00", tax_pct="10.00"
    )


@pytest.fixture
def product_b(db, tenant_b):
    from apps.crm.models import Product
    return Product.objects.create(
        tenant=tenant_b, name="Globex Service", sku="SVC-001",
        product_type="service", unit_price="200.00", cost="50.00"
    )


@pytest.fixture
def pricebook_a(db, tenant_a):
    from apps.crm.models import PriceBook
    return PriceBook.objects.create(
        tenant=tenant_a, name="Standard", currency_code="USD",
        price_adjustment_pct="0.00", is_default=True
    )


@pytest.fixture
def pricebook_b(db, tenant_b):
    from apps.crm.models import PriceBook
    return PriceBook.objects.create(
        tenant=tenant_b, name="Globex Book", price_adjustment_pct="-10.00"
    )


@pytest.fixture
def opportunity_a(db, tenant_a, account_a, territory_a):
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant_a, name="Big Deal",
        account=account_a, territory=territory_a,
        stage="prospecting", amount="5000.00", probability=20,
        forecast_category="pipeline",
    )


@pytest.fixture
def opportunity_b(db, tenant_b, account_b):
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant_b, name="Globex Deal",
        account=account_b, stage="qualification",
        amount="3000.00", probability=50,
    )


@pytest.fixture
def quote_a(db, tenant_a, opportunity_a, pricebook_a):
    from apps.crm.models import Quote
    return Quote.objects.create(
        tenant=tenant_a, name="Q1 Proposal",
        opportunity=opportunity_a, price_book=pricebook_a,
        status="draft",
    )


@pytest.fixture
def quote_b(db, tenant_b, opportunity_b):
    from apps.crm.models import Quote
    return Quote.objects.create(
        tenant=tenant_b, name="Globex Quote",
        opportunity=opportunity_b, status="draft",
    )


@pytest.fixture
def quota_a(db, tenant_a, admin_user, territory_a):
    from apps.crm.models import SalesQuota
    return SalesQuota.objects.create(
        tenant=tenant_a, owner=admin_user, territory=territory_a,
        period_type="quarter", period_year=2026, period_number=1,
        target_amount="50000.00",
    )


@pytest.fixture
def quota_b(db, tenant_b, admin_b, territory_b):
    from apps.crm.models import SalesQuota
    return SalesQuota.objects.create(
        tenant=tenant_b, owner=admin_b, territory=territory_b,
        period_type="quarter", period_year=2026, period_number=1,
        target_amount="30000.00",
    )


@pytest.fixture
def split_a(db, tenant_a, opportunity_a, admin_user):
    from apps.crm.models import OpportunitySplit
    return OpportunitySplit.objects.create(
        tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
        split_type="revenue", percentage="60.00",
    )


# =================================================================== MODEL INVARIANTS

class TestOpportunitySave:
    """Opportunity.save() / from_db stage-change stamping."""

    def test_stage_changed_at_stamped_on_create(self, tenant_a, account_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Fresh", account=account_a,
            stage="prospecting", amount="1000.00", probability=10,
        )
        assert opp.stage_changed_at is not None

    def test_stage_changed_at_stamped_on_stage_change(self, opportunity_a):
        from datetime import timedelta

        from django.utils import timezone

        from apps.crm.models import Opportunity
        # Force a known-old stamp in the DB (bypassing save), then reload so from_db() sets
        # _loaded_stage. Using a day-old anchor makes the "moved forward" assertion deterministic
        # (two consecutive timezone.now() calls can collide to the same microsecond on fast CPUs).
        old = timezone.now() - timedelta(days=1)
        Opportunity.objects.filter(pk=opportunity_a.pk).update(stage_changed_at=old)
        opp = Opportunity.objects.get(pk=opportunity_a.pk)
        opp.stage = "qualification"
        opp.save()
        opp.refresh_from_db()
        assert opp.stage_changed_at > old

    def test_stage_changed_at_not_updated_on_non_stage_edit(self, opportunity_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.get(pk=opportunity_a.pk)
        original_stamp = opp.stage_changed_at
        opp.description = "Updated description only"
        opp.save()
        opp.refresh_from_db()
        assert opp.stage_changed_at == original_stamp

    def test_lost_at_stamped_when_entering_closed_lost(self, opportunity_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.get(pk=opportunity_a.pk)
        assert opp.lost_at is None
        opp.stage = "closed_lost"
        opp.save()
        opp.refresh_from_db()
        assert opp.lost_at is not None

    def test_lost_at_not_overwritten_on_resave_as_lost(self, opportunity_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.get(pk=opportunity_a.pk)
        opp.stage = "closed_lost"
        opp.save()
        opp.refresh_from_db()
        first_lost_at = opp.lost_at
        opp.description = "still lost"
        opp.save()
        opp.refresh_from_db()
        assert opp.lost_at == first_lost_at

    def test_lost_at_cleared_when_reopened(self, opportunity_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.get(pk=opportunity_a.pk)
        opp.stage = "closed_lost"
        opp.save()
        opp.refresh_from_db()
        assert opp.lost_at is not None
        # Re-open to an open stage — lost_at must be cleared
        opp = Opportunity.objects.get(pk=opp.pk)
        opp.stage = "prospecting"
        opp.save()
        opp.refresh_from_db()
        assert opp.lost_at is None

    def test_weighted_amount_correct(self, tenant_a, account_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="WA Test", account=account_a,
            stage="proposal", amount="4000.00", probability=25,
        )
        # 4000 × 25 / 100 = 1000
        assert opp.weighted_amount == Decimal("1000.00")

    def test_weighted_amount_decimal_safe_on_fresh_instance(self, tenant_a, account_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="DS", account=account_a,
            stage="prospecting", amount="500.00", probability=50,
        )
        # Must not raise TypeError on a freshly-created (un-round-tripped) instance
        result = opp.weighted_amount
        assert result is not None

    def test_is_open_true_for_open_stages(self, tenant_a, account_a):
        from apps.crm.models import Opportunity
        for stage in ["prospecting", "qualification", "proposal", "negotiation"]:
            opp = Opportunity(tenant=tenant_a, name="X", stage=stage)
            assert opp.is_open is True

    def test_is_open_false_for_closed_stages(self, tenant_a, account_a):
        from apps.crm.models import Opportunity
        for stage in ["closed_won", "closed_lost"]:
            opp = Opportunity(tenant=tenant_a, name="X", stage=stage)
            assert opp.is_open is False

    def test_str_format(self, opportunity_a):
        s = str(opportunity_a)
        assert "OPP-00001" in s
        assert "Big Deal" in s

    def test_auto_number_per_tenant(self, tenant_a, tenant_b, account_a, account_b):
        from apps.crm.models import Opportunity
        a = Opportunity.objects.create(
            tenant=tenant_a, name="A", account=account_a, stage="prospecting"
        )
        b = Opportunity.objects.create(
            tenant=tenant_b, name="B", account=account_b, stage="prospecting"
        )
        assert a.number == "OPP-00001"
        assert b.number == "OPP-00001"


class TestTerritoryModel:
    def test_number_format(self, tenant_a):
        from apps.crm.models import Territory
        t = Territory.objects.create(tenant=tenant_a, name="North")
        assert t.number == "TER-00001"

    def test_sequential_per_tenant(self, tenant_a):
        from apps.crm.models import Territory
        t1 = Territory.objects.create(tenant=tenant_a, name="N1")
        t2 = Territory.objects.create(tenant=tenant_a, name="N2")
        assert t1.number == "TER-00001"
        assert t2.number == "TER-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import Territory
        a = Territory.objects.create(tenant=tenant_a, name="A")
        b = Territory.objects.create(tenant=tenant_b, name="B")
        assert a.number == "TER-00001"
        assert b.number == "TER-00001"

    def test_str_format(self, territory_a):
        s = str(territory_a)
        assert "TER-00001" in s
        assert "West Coast" in s

    def test_is_active_default(self, tenant_a):
        from apps.crm.models import Territory
        t = Territory.objects.create(tenant=tenant_a, name="X")
        assert t.is_active is True

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import Territory
        from django.db import IntegrityError
        Territory.objects.create(tenant=tenant_a, name="First")
        with pytest.raises(IntegrityError):
            Territory.objects.create(tenant=tenant_a, name="Dup", number="TER-00001")


class TestProductModel:
    def test_number_format(self, tenant_a):
        from apps.crm.models import Product
        p = Product.objects.create(tenant=tenant_a, name="Gadget", unit_price="50.00")
        assert p.number == "PRD-00001"

    def test_sequential_per_tenant(self, tenant_a):
        from apps.crm.models import Product
        p1 = Product.objects.create(tenant=tenant_a, name="A", unit_price="10.00")
        p2 = Product.objects.create(tenant=tenant_a, name="B", unit_price="20.00")
        assert p1.number == "PRD-00001"
        assert p2.number == "PRD-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import Product
        a = Product.objects.create(tenant=tenant_a, name="A")
        b = Product.objects.create(tenant=tenant_b, name="B")
        assert a.number == "PRD-00001"
        assert b.number == "PRD-00001"

    def test_str_format(self, product_a):
        s = str(product_a)
        assert "PRD-00001" in s
        assert "Widget Pro" in s

    def test_margin_pct_none_when_price_zero(self, tenant_a):
        from apps.crm.models import Product
        p = Product.objects.create(tenant=tenant_a, name="Free", unit_price="0.00", cost="5.00")
        assert p.margin_pct is None

    def test_margin_pct_correct(self, product_a):
        # unit_price=100, cost=60 → margin = (100-60)/100 * 100 = 40%
        assert float(product_a.margin_pct) == pytest.approx(40.0)

    def test_margin_pct_decimal_safe_on_fresh_instance(self, tenant_a):
        from apps.crm.models import Product
        p = Product.objects.create(
            tenant=tenant_a, name="Fresh", unit_price="200.00", cost="100.00"
        )
        # Must not raise TypeError on un-round-tripped instance
        result = p.margin_pct
        assert result is not None
        assert float(result) == pytest.approx(50.0)

    def test_margin_pct_100_when_cost_zero(self, tenant_a):
        from apps.crm.models import Product
        p = Product.objects.create(tenant=tenant_a, name="NoCoGS", unit_price="100.00", cost="0.00")
        assert float(p.margin_pct) == pytest.approx(100.0)

    def test_type_choices(self):
        from apps.crm.models import Product
        keys = [k for k, _ in Product.TYPE_CHOICES]
        assert set(keys) == {"good", "service", "subscription"}

    def test_is_active_default(self, tenant_a):
        from apps.crm.models import Product
        p = Product.objects.create(tenant=tenant_a, name="Active")
        assert p.is_active is True


class TestPriceBookModel:
    def test_number_format(self, tenant_a):
        from apps.crm.models import PriceBook
        pb = PriceBook.objects.create(tenant=tenant_a, name="Standard")
        assert pb.number == "PB-00001"

    def test_sequential_per_tenant(self, tenant_a):
        from apps.crm.models import PriceBook
        pb1 = PriceBook.objects.create(tenant=tenant_a, name="A")
        pb2 = PriceBook.objects.create(tenant=tenant_a, name="B")
        assert pb1.number == "PB-00001"
        assert pb2.number == "PB-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import PriceBook
        a = PriceBook.objects.create(tenant=tenant_a, name="A")
        b = PriceBook.objects.create(tenant=tenant_b, name="B")
        assert a.number == "PB-00001"
        assert b.number == "PB-00001"

    def test_str_format(self, pricebook_a):
        s = str(pricebook_a)
        assert "PB-00001" in s
        assert "Standard" in s

    def test_adjusted_price_no_adjustment(self, pricebook_a):
        # 0% adjustment — price unchanged
        result = pricebook_a.adjusted_price(Decimal("100.00"))
        assert result == pytest.approx(Decimal("100.00"))

    def test_adjusted_price_positive_adjustment(self, tenant_a):
        from apps.crm.models import PriceBook
        pb = PriceBook.objects.create(tenant=tenant_a, name="Premium", price_adjustment_pct="20.00")
        result = pb.adjusted_price(Decimal("100.00"))
        assert result == pytest.approx(Decimal("120.00"))

    def test_adjusted_price_negative_adjustment(self, tenant_a):
        from apps.crm.models import PriceBook
        pb = PriceBook.objects.create(tenant=tenant_a, name="Discount", price_adjustment_pct="-10.00")
        result = pb.adjusted_price(Decimal("200.00"))
        assert result == pytest.approx(Decimal("180.00"))

    def test_adjusted_price_decimal_safe(self, tenant_a):
        from apps.crm.models import PriceBook
        # Pass string base — adjusted_price() must Decimal-cast it
        pb = PriceBook.objects.create(tenant=tenant_a, name="Safe", price_adjustment_pct="10.00")
        result = pb.adjusted_price("100.00")
        assert result == pytest.approx(Decimal("110.00"))

    def test_is_active_default(self, tenant_a):
        from apps.crm.models import PriceBook
        pb = PriceBook.objects.create(tenant=tenant_a, name="New")
        assert pb.is_active is True


class TestOpportunitySplitModel:
    def test_split_amount_correct(self, tenant_a, opportunity_a, admin_user):
        from apps.crm.models import OpportunitySplit
        split = OpportunitySplit.objects.create(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="revenue", percentage="40.00",
        )
        # opp amount=5000, percentage=40 → 5000*40/100 = 2000
        assert split.split_amount == Decimal("2000.00")

    def test_split_amount_decimal_safe(self, tenant_a, opportunity_a, admin_user):
        from apps.crm.models import OpportunitySplit
        split = OpportunitySplit(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="overlay", percentage=Decimal("25.00"),
        )
        # Don't save — test the property on an unsaved instance
        result = split.split_amount
        assert result is not None

    def test_str_format(self, split_a, admin_user):
        s = str(split_a)
        assert "60%" in s or "60.00%" in s
        assert "Revenue" in s

    def test_clean_rejects_zero_percentage(self, tenant_a, opportunity_a, admin_user):
        from apps.crm.models import OpportunitySplit
        from django.core.exceptions import ValidationError
        split = OpportunitySplit(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="revenue", percentage=Decimal("0.00"),
        )
        with pytest.raises(ValidationError, match="greater than zero"):
            split.clean()

    def test_clean_rejects_negative_percentage(self, tenant_a, opportunity_a, admin_user):
        from apps.crm.models import OpportunitySplit
        from django.core.exceptions import ValidationError
        split = OpportunitySplit(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="revenue", percentage=Decimal("-5.00"),
        )
        with pytest.raises(ValidationError, match="greater than zero"):
            split.clean()

    def test_clean_rejects_revenue_splits_exceeding_100(self, tenant_a, opportunity_a,
                                                         admin_user, member_user):
        from apps.crm.models import OpportunitySplit
        from django.core.exceptions import ValidationError
        # First split: 60%
        OpportunitySplit.objects.create(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="revenue", percentage=Decimal("60.00"),
        )
        # Second split: would push to 110% → rejected
        split2 = OpportunitySplit(
            tenant=tenant_a, opportunity=opportunity_a, user=member_user,
            split_type="revenue", percentage=Decimal("50.00"),
        )
        with pytest.raises(ValidationError, match="100%"):
            split2.clean()

    def test_clean_allows_revenue_splits_exactly_100(self, tenant_a, opportunity_a,
                                                      admin_user, member_user):
        from apps.crm.models import OpportunitySplit
        OpportunitySplit.objects.create(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="revenue", percentage=Decimal("60.00"),
        )
        split2 = OpportunitySplit(
            tenant=tenant_a, opportunity=opportunity_a, user=member_user,
            split_type="revenue", percentage=Decimal("40.00"),
        )
        # Should NOT raise
        split2.clean()

    def test_clean_excludes_self_on_edit(self, tenant_a, opportunity_a, admin_user):
        """clean() must exclude self when editing (so a save doesn't count the row twice)."""
        from apps.crm.models import OpportunitySplit
        split = OpportunitySplit.objects.create(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="revenue", percentage=Decimal("60.00"),
        )
        # Re-clean the same split at the same percentage — must not fail
        split.clean()

    def test_clean_overlay_type_uncapped(self, tenant_a, opportunity_a, admin_user, member_user):
        """Overlay splits are not subject to the ≤100% revenue cap."""
        from apps.crm.models import OpportunitySplit
        # Put revenue at 100%
        OpportunitySplit.objects.create(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="revenue", percentage=Decimal("100.00"),
        )
        overlay = OpportunitySplit(
            tenant=tenant_a, opportunity=opportunity_a, user=member_user,
            split_type="overlay", percentage=Decimal("50.00"),
        )
        # Should NOT raise for overlay type
        overlay.clean()


class TestQuoteModel:
    def test_number_format(self, tenant_a, opportunity_a):
        from apps.crm.models import Quote
        q = Quote.objects.create(tenant=tenant_a, name="Test Quote", opportunity=opportunity_a)
        assert q.number == "QUO-00001"

    def test_sequential_per_tenant(self, tenant_a, opportunity_a):
        from apps.crm.models import Quote
        q1 = Quote.objects.create(tenant=tenant_a, name="Q1", opportunity=opportunity_a)
        q2 = Quote.objects.create(tenant=tenant_a, name="Q2", opportunity=opportunity_a)
        assert q1.number == "QUO-00001"
        assert q2.number == "QUO-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b, opportunity_a, opportunity_b):
        from apps.crm.models import Quote
        a = Quote.objects.create(tenant=tenant_a, name="A", opportunity=opportunity_a)
        b = Quote.objects.create(tenant=tenant_b, name="B", opportunity=opportunity_b)
        assert a.number == "QUO-00001"
        assert b.number == "QUO-00001"

    def test_str_format(self, quote_a):
        s = str(quote_a)
        assert "QUO-00001" in s
        assert "Q1 Proposal" in s

    def test_status_default_draft(self, tenant_a, opportunity_a):
        from apps.crm.models import Quote
        q = Quote.objects.create(tenant=tenant_a, name="New", opportunity=opportunity_a)
        assert q.status == "draft"

    def test_is_open_for_draft_and_sent(self, quote_a):
        assert quote_a.is_open is True
        from apps.crm.models import Quote
        Quote.objects.filter(pk=quote_a.pk).update(status="sent")
        quote_a.refresh_from_db()
        assert quote_a.is_open is True

    def test_is_open_false_for_accepted(self, quote_a):
        from apps.crm.models import Quote
        Quote.objects.filter(pk=quote_a.pk).update(status="accepted")
        quote_a.refresh_from_db()
        assert quote_a.is_open is False

    def test_is_expired_true_when_past_valid_until(self, tenant_a, opportunity_a):
        from apps.crm.models import Quote
        import datetime
        q = Quote.objects.create(
            tenant=tenant_a, name="Expired",
            opportunity=opportunity_a, status="draft",
            valid_until=datetime.date(2000, 1, 1),
        )
        assert q.is_expired is True

    def test_is_expired_false_when_future_valid_until(self, tenant_a, opportunity_a):
        from apps.crm.models import Quote
        import datetime
        q = Quote.objects.create(
            tenant=tenant_a, name="Not Expired",
            opportunity=opportunity_a, status="draft",
            valid_until=datetime.date(2099, 12, 31),
        )
        assert q.is_expired is False

    def test_is_expired_false_when_no_valid_until(self, quote_a):
        assert quote_a.is_expired is False

    def test_unique_together_tenant_number(self, tenant_a, opportunity_a):
        from apps.crm.models import Quote
        from django.db import IntegrityError
        Quote.objects.create(tenant=tenant_a, name="First", opportunity=opportunity_a)
        with pytest.raises(IntegrityError):
            Quote.objects.create(
                tenant=tenant_a, name="Dup",
                opportunity=opportunity_a, number="QUO-00001"
            )


class TestQuoteLineProperties:
    def test_line_subtotal_with_discount(self, tenant_a, quote_a, product_a):
        from apps.crm.models import QuoteLine
        line = QuoteLine(
            tenant=tenant_a, quote=quote_a, product=product_a,
            description="Test", quantity=Decimal("2"), unit_price=Decimal("100.00"),
            discount_pct=Decimal("10.00"), tax_pct=Decimal("0"),
        )
        # subtotal = 2 * 100 * (1 - 10/100) = 180
        assert line.line_subtotal == pytest.approx(Decimal("180.00"))

    def test_line_tax(self, tenant_a, quote_a, product_a):
        from apps.crm.models import QuoteLine
        line = QuoteLine(
            tenant=tenant_a, quote=quote_a, product=product_a,
            description="Test", quantity=Decimal("2"), unit_price=Decimal("100.00"),
            discount_pct=Decimal("0"), tax_pct=Decimal("10.00"),
        )
        # tax = 200 * 10/100 = 20
        assert line.line_tax == pytest.approx(Decimal("20.00"))

    def test_line_total(self, tenant_a, quote_a, product_a):
        from apps.crm.models import QuoteLine
        line = QuoteLine(
            tenant=tenant_a, quote=quote_a, product=product_a,
            description="Test", quantity=Decimal("1"), unit_price=Decimal("100.00"),
            discount_pct=Decimal("0"), tax_pct=Decimal("10.00"),
        )
        # total = 100 + 10 = 110
        assert line.line_total == pytest.approx(Decimal("110.00"))

    def test_line_properties_decimal_safe_on_fresh_instance(self, tenant_a, quote_a, product_a):
        from apps.crm.models import QuoteLine
        line = QuoteLine(
            tenant=tenant_a, quote=quote_a, description="Unsaved",
            quantity=Decimal("2"), unit_price=Decimal("50.00"),
            discount_pct=Decimal("0"), tax_pct=Decimal("5"),
        )
        # Must not raise before DB round-trip
        assert line.line_subtotal is not None
        assert line.line_tax is not None
        assert line.line_total is not None

    def test_str_format(self, tenant_a, quote_a, product_a):
        from apps.crm.models import QuoteLine
        line = QuoteLine.objects.create(
            tenant=tenant_a, quote=quote_a, product=product_a,
            description="Widget", quantity=Decimal("3"),
            unit_price=Decimal("100.00"),
        )
        s = str(line)
        assert "Widget" in s
        assert "3" in s


class TestQuoteRecalcTotals:
    """Quote.recalc_totals() correctness for a known line set."""

    def _make_line(self, tenant, quote, description, qty, price, disc, tax):
        from apps.crm.models import QuoteLine
        return QuoteLine.objects.create(
            tenant=tenant, quote=quote,
            description=description, quantity=qty,
            unit_price=price, discount_pct=disc, tax_pct=tax,
        )

    def test_recalc_with_single_line_no_discount(self, tenant_a, quote_a):
        self._make_line(tenant_a, quote_a, "A", Decimal("2"), Decimal("100.00"),
                        Decimal("0"), Decimal("10.00"))
        quote_a.recalc_totals()
        quote_a.refresh_from_db()
        # subtotal = 200, tax = 20, total = 220
        assert quote_a.subtotal == Decimal("200.00")
        assert quote_a.tax_total == Decimal("20.00")
        assert quote_a.total == Decimal("220.00")

    def test_recalc_with_per_line_discount(self, tenant_a, quote_a):
        # recalc_totals() sums the lines in Python (Decimal-safe), so the per-line discount
        # applies correctly on every backend: 1 * 200 * (1 - 10%) = 180.
        self._make_line(tenant_a, quote_a, "B", Decimal("1"), Decimal("200.00"),
                        Decimal("10.00"), Decimal("0"))
        quote_a.recalc_totals()
        quote_a.refresh_from_db()
        assert quote_a.subtotal == Decimal("180.00")
        assert quote_a.tax_total == Decimal("0.00")
        assert quote_a.total == Decimal("180.00")

    def test_recalc_with_quote_level_discount(self, tenant_a, opportunity_a):
        from apps.crm.models import Quote
        q = Quote.objects.create(
            tenant=tenant_a, name="QL Disc", opportunity=opportunity_a,
            status="draft", discount_pct=Decimal("10.00"),
        )
        self._make_line(tenant_a, q, "C", Decimal("1"), Decimal("100.00"),
                        Decimal("0"), Decimal("0"))
        q.recalc_totals()
        q.refresh_from_db()
        # subtotal = 100 * 0.9 = 90, tax=0, total=90
        assert q.subtotal == Decimal("90.00")
        assert q.total == Decimal("90.00")

    def test_recalc_with_multiple_lines(self, tenant_a, quote_a):
        self._make_line(tenant_a, quote_a, "L1", Decimal("1"), Decimal("100.00"),
                        Decimal("0"), Decimal("10.00"))
        self._make_line(tenant_a, quote_a, "L2", Decimal("2"), Decimal("50.00"),
                        Decimal("0"), Decimal("0"))
        quote_a.recalc_totals()
        quote_a.refresh_from_db()
        # L1: net=100, tax=10; L2: net=100, tax=0; total_sub=200, total_tax=10
        assert quote_a.subtotal == Decimal("200.00")
        assert quote_a.tax_total == Decimal("10.00")
        assert quote_a.total == Decimal("210.00")

    def test_recalc_with_no_lines_zeros_totals(self, quote_a):
        quote_a.recalc_totals()
        quote_a.refresh_from_db()
        assert quote_a.subtotal == Decimal("0.00")
        assert quote_a.tax_total == Decimal("0.00")
        assert quote_a.total == Decimal("0.00")

    def test_recalc_exact_decimals_combined_line_and_quote_discount(self, tenant_a, opportunity_a):
        """Exact Decimal check: line disc 10% + quote disc 20% + tax 5% (Python-summed, portable).

        line_subtotal = 1 * 500 * (1 - 10%) = 450; line_tax = 450 * 5% = 22.50.
        Quote-level 20% discount factor = 0.80:
          subtotal = 450 * 0.80 = 360.00; tax = 22.50 * 0.80 = 18.00; total = 378.00.
        """
        from apps.crm.models import Quote, QuoteLine
        q = Quote.objects.create(
            tenant=tenant_a, name="Combined", opportunity=opportunity_a,
            status="draft", discount_pct=Decimal("20.00"),
        )
        QuoteLine.objects.create(
            tenant=tenant_a, quote=q, description="X",
            quantity=Decimal("1"), unit_price=Decimal("500.00"),
            discount_pct=Decimal("10.00"), tax_pct=Decimal("5.00"),
        )
        q.recalc_totals()
        q.refresh_from_db()
        assert q.subtotal == Decimal("360.00")
        assert q.tax_total == Decimal("18.00")
        assert q.total == Decimal("378.00")


class TestSalesQuotaModel:
    def test_number_format(self, tenant_a, admin_user):
        from apps.crm.models import SalesQuota
        q = SalesQuota.objects.create(
            tenant=tenant_a, owner=admin_user,
            period_type="quarter", period_year=2026, period_number=1,
            target_amount="10000.00",
        )
        assert q.number == "QTA-00001"

    def test_sequential_per_tenant(self, tenant_a, admin_user, member_user):
        from apps.crm.models import SalesQuota
        q1 = SalesQuota.objects.create(
            tenant=tenant_a, owner=admin_user,
            period_type="month", period_year=2026, period_number=1,
            target_amount="5000.00",
        )
        q2 = SalesQuota.objects.create(
            tenant=tenant_a, owner=member_user,
            period_type="month", period_year=2026, period_number=2,
            target_amount="6000.00",
        )
        assert q1.number == "QTA-00001"
        assert q2.number == "QTA-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b, admin_user, admin_b):
        from apps.crm.models import SalesQuota
        a = SalesQuota.objects.create(
            tenant=tenant_a, owner=admin_user,
            period_type="quarter", period_year=2026, period_number=1,
            target_amount="10000.00",
        )
        b = SalesQuota.objects.create(
            tenant=tenant_b, owner=admin_b,
            period_type="quarter", period_year=2026, period_number=1,
            target_amount="20000.00",
        )
        assert a.number == "QTA-00001"
        assert b.number == "QTA-00001"

    def test_str_format(self, quota_a):
        s = str(quota_a)
        assert "QTA-00001" in s
        assert "2026" in s

    def test_unique_together_tenant_number(self, tenant_a, admin_user):
        from apps.crm.models import SalesQuota
        from django.db import IntegrityError
        SalesQuota.objects.create(
            tenant=tenant_a, owner=admin_user,
            period_type="quarter", period_year=2026, period_number=2,
            target_amount="1000.00",
        )
        with pytest.raises(IntegrityError):
            SalesQuota.objects.create(
                tenant=tenant_a, owner=admin_user,
                period_type="month", period_year=2027, period_number=1,
                target_amount="2000.00", number="QTA-00001"
            )

    def test_unique_together_owner_territory_period(self, tenant_a, admin_user, territory_a):
        from apps.crm.models import SalesQuota
        from django.db import IntegrityError
        SalesQuota.objects.create(
            tenant=tenant_a, owner=admin_user, territory=territory_a,
            period_type="quarter", period_year=2026, period_number=1,
            target_amount="10000.00",
        )
        with pytest.raises(IntegrityError):
            SalesQuota.objects.create(
                tenant=tenant_a, owner=admin_user, territory=territory_a,
                period_type="quarter", period_year=2026, period_number=1,
                target_amount="99999.00",
            )

    def test_period_choices(self):
        from apps.crm.models import SalesQuota
        keys = [k for k, _ in SalesQuota.PERIOD_CHOICES]
        assert set(keys) == {"month", "quarter", "year"}


# =================================================================== FORM SECURITY

class TestOpportunityFormExclusions:
    def test_lost_at_not_in_form(self, tenant_a):
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        assert "lost_at" not in form.fields

    def test_stage_changed_at_not_in_form(self, tenant_a):
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        assert "stage_changed_at" not in form.fields

    def test_tenant_not_in_form(self, tenant_a):
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_in_form(self, tenant_a):
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        assert "number" not in form.fields


class TestQuoteFormExclusions:
    def test_status_not_in_form(self, tenant_a):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(tenant=tenant_a)
        assert "status" not in form.fields

    def test_subtotal_not_in_form(self, tenant_a):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(tenant=tenant_a)
        assert "subtotal" not in form.fields

    def test_tax_total_not_in_form(self, tenant_a):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(tenant=tenant_a)
        assert "tax_total" not in form.fields

    def test_total_not_in_form(self, tenant_a):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(tenant=tenant_a)
        assert "total" not in form.fields

    def test_sent_at_not_in_form(self, tenant_a):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(tenant=tenant_a)
        assert "sent_at" not in form.fields

    def test_accepted_at_not_in_form(self, tenant_a):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(tenant=tenant_a)
        assert "accepted_at" not in form.fields

    def test_tenant_not_in_form(self, tenant_a):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_in_form(self, tenant_a):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(tenant=tenant_a)
        assert "number" not in form.fields


class TestSalesQuotaFormDuplicateRejection:
    def test_clean_rejects_duplicate_quota(self, tenant_a, admin_user, territory_a):
        from apps.crm.forms import SalesQuotaForm
        # First quota exists
        from apps.crm.models import SalesQuota
        SalesQuota.objects.create(
            tenant=tenant_a, owner=admin_user, territory=territory_a,
            period_type="quarter", period_year=2026, period_number=1,
            target_amount="10000.00",
        )
        form = SalesQuotaForm(
            tenant=tenant_a,
            data={
                "owner": admin_user.pk,
                "territory": territory_a.pk,
                "period_type": "quarter",
                "period_year": 2026,
                "period_number": 1,
                "target_amount": "20000.00",
            }
        )
        assert not form.is_valid()
        assert "__all__" in form.errors or any(
            "quota already exists" in str(e) for e in form.errors.get("__all__", [])
        )

    def test_clean_allows_different_period(self, tenant_a, admin_user, territory_a):
        from apps.crm.forms import SalesQuotaForm
        from apps.crm.models import SalesQuota
        SalesQuota.objects.create(
            tenant=tenant_a, owner=admin_user, territory=territory_a,
            period_type="quarter", period_year=2026, period_number=1,
            target_amount="10000.00",
        )
        form = SalesQuotaForm(
            tenant=tenant_a,
            data={
                "owner": admin_user.pk,
                "territory": territory_a.pk,
                "period_type": "quarter",
                "period_year": 2026,
                "period_number": 2,  # different period
                "target_amount": "20000.00",
            }
        )
        assert form.is_valid(), form.errors


class TestOpportunitySplitFormValidators:
    """Percentage field validators block negative and over-100 values at the form level."""

    def test_split_form_rejects_negative_percentage(self, tenant_a, opportunity_a, admin_user):
        from apps.crm.forms import OpportunitySplitForm
        form = OpportunitySplitForm(
            tenant=tenant_a,
            data={
                "user": admin_user.pk,
                "split_type": "revenue",
                "percentage": "-5",
                "notes": "",
            }
        )
        assert not form.is_valid()
        assert "percentage" in form.errors

    def test_split_form_rejects_over_100_percentage(self, tenant_a, opportunity_a, admin_user):
        from apps.crm.forms import OpportunitySplitForm
        form = OpportunitySplitForm(
            tenant=tenant_a,
            data={
                "user": admin_user.pk,
                "split_type": "revenue",
                "percentage": "150",
                "notes": "",
            }
        )
        assert not form.is_valid()
        assert "percentage" in form.errors

    def test_split_form_accepts_valid_percentage(self, tenant_a, admin_user):
        from apps.crm.forms import OpportunitySplitForm
        form = OpportunitySplitForm(
            tenant=tenant_a,
            data={
                "user": admin_user.pk,
                "split_type": "revenue",
                "percentage": "60",
                "notes": "",
            }
        )
        assert form.is_valid(), form.errors


class TestCrossTenantFKRejection:
    def test_quote_form_rejects_cross_tenant_opportunity(
        self, tenant_a, opportunity_b
    ):
        from apps.crm.forms import QuoteForm
        form = QuoteForm(
            tenant=tenant_a,
            data={
                "name": "Injected Quote",
                "opportunity": str(opportunity_b.pk),  # cross-tenant
                "currency_code": "USD",
                "discount_pct": "0",
            }
        )
        assert not form.is_valid()
        assert "opportunity" in form.errors

    def test_quoteline_form_rejects_cross_tenant_product(
        self, tenant_a, product_b
    ):
        from apps.crm.forms import QuoteLineForm
        form = QuoteLineForm(
            tenant=tenant_a,
            data={
                "product": str(product_b.pk),  # cross-tenant injection
                "description": "Injected Line",
                "quantity": "1",
                "unit_price": "100",
                "discount_pct": "0",
                "tax_pct": "0",
            }
        )
        assert not form.is_valid()
        assert "product" in form.errors

    def test_opportunitysplit_form_rejects_cross_tenant_user(
        self, tenant_a, admin_b
    ):
        from apps.crm.forms import OpportunitySplitForm
        form = OpportunitySplitForm(
            tenant=tenant_a,
            data={
                "user": str(admin_b.pk),  # cross-tenant user
                "split_type": "revenue",
                "percentage": "50",
                "notes": "",
            }
        )
        assert not form.is_valid()
        assert "user" in form.errors


# =================================================================== VIEWS / CRUD

class TestTerritoryViews:
    def test_list_200(self, client_a, territory_a):
        resp = client_a.get(reverse("crm:territory_list"))
        assert resp.status_code == 200

    def test_list_shows_own_territory(self, client_a, territory_a):
        resp = client_a.get(reverse("crm:territory_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert territory_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, territory_a, territory_b):
        resp = client_a.get(reverse("crm:territory_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert territory_b.pk not in pks

    def test_detail_200(self, client_a, territory_a):
        resp = client_a.get(reverse("crm:territory_detail", args=[territory_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, territory_a):
        resp = client_a.get(reverse("crm:territory_detail", args=[territory_a.pk]))
        assert resp.context["obj"].pk == territory_a.pk

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:territory_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import Territory
        resp = client_a.post(reverse("crm:territory_create"), {
            "name": "New Territory",
            "region": "EMEA",
            "segment": "Enterprise",
            "is_active": "on",
        })
        assert resp.status_code == 302
        t = Territory.objects.filter(tenant=tenant_a, name="New Territory").first()
        assert t is not None
        assert t.number.startswith("TER-")

    def test_edit_get_200(self, client_a, territory_a):
        resp = client_a.get(reverse("crm:territory_edit", args=[territory_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, territory_a):
        resp = client_a.post(reverse("crm:territory_edit", args=[territory_a.pk]), {
            "name": "West Coast Renamed",
            "region": "AMER",
            "segment": "SMB",
            "is_active": "on",
        })
        assert resp.status_code == 302
        territory_a.refresh_from_db()
        assert territory_a.name == "West Coast Renamed"

    def test_delete_removes_record(self, client_a, territory_a):
        from apps.crm.models import Territory
        pk = territory_a.pk
        resp = client_a.post(reverse("crm:territory_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Territory.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:territory_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestProductViews:
    def test_list_200(self, client_a, product_a):
        resp = client_a.get(reverse("crm:product_list"))
        assert resp.status_code == 200

    def test_list_shows_own_product(self, client_a, product_a):
        resp = client_a.get(reverse("crm:product_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert product_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, product_a, product_b):
        resp = client_a.get(reverse("crm:product_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert product_b.pk not in pks

    def test_detail_200(self, client_a, product_a):
        resp = client_a.get(reverse("crm:product_detail", args=[product_a.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:product_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import Product
        resp = client_a.post(reverse("crm:product_create"), {
            "name": "New Widget",
            "sku": "NEW-001",
            "product_type": "good",
            "unit_price": "150.00",
            "cost": "80.00",
            "tax_pct": "5.00",
            "is_active": "on",
        })
        assert resp.status_code == 302
        p = Product.objects.filter(tenant=tenant_a, name="New Widget").first()
        assert p is not None
        assert p.number.startswith("PRD-")

    def test_edit_get_200(self, client_a, product_a):
        resp = client_a.get(reverse("crm:product_edit", args=[product_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_record(self, client_a, product_a):
        from apps.crm.models import Product
        pk = product_a.pk
        resp = client_a.post(reverse("crm:product_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Product.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:product_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestPriceBookViews:
    def test_list_200(self, client_a, pricebook_a):
        resp = client_a.get(reverse("crm:pricebook_list"))
        assert resp.status_code == 200

    def test_list_shows_own_pricebook(self, client_a, pricebook_a):
        resp = client_a.get(reverse("crm:pricebook_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert pricebook_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, pricebook_a, pricebook_b):
        resp = client_a.get(reverse("crm:pricebook_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert pricebook_b.pk not in pks

    def test_detail_200(self, client_a, pricebook_a):
        resp = client_a.get(reverse("crm:pricebook_detail", args=[pricebook_a.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:pricebook_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import PriceBook
        resp = client_a.post(reverse("crm:pricebook_create"), {
            "name": "New Book",
            "currency_code": "EUR",
            "region": "EU",
            "tier": "Standard",
            "price_adjustment_pct": "-5.00",
            "is_default": "",
            "is_active": "on",
        })
        assert resp.status_code == 302
        pb = PriceBook.objects.filter(tenant=tenant_a, name="New Book").first()
        assert pb is not None
        assert pb.number.startswith("PB-")

    def test_edit_get_200(self, client_a, pricebook_a):
        resp = client_a.get(reverse("crm:pricebook_edit", args=[pricebook_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_record(self, client_a, pricebook_a):
        from apps.crm.models import PriceBook
        pk = pricebook_a.pk
        resp = client_a.post(reverse("crm:pricebook_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PriceBook.objects.filter(pk=pk).exists()


class TestOpportunityViews:
    def test_list_200(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_list"))
        assert resp.status_code == 200

    def test_list_shows_own_opportunity(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert opportunity_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, opportunity_a, opportunity_b):
        resp = client_a.get(reverse("crm:opportunity_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert opportunity_b.pk not in pks

    def test_detail_200(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_detail", args=[opportunity_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_detail", args=[opportunity_a.pk]))
        assert resp.context["obj"].pk == opportunity_a.pk

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:opportunity_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a, account_a):
        from apps.crm.models import Opportunity
        resp = client_a.post(reverse("crm:opportunity_create"), {
            "name": "New Opportunity",
            "account": str(account_a.pk),
            "stage": "prospecting",
            "forecast_category": "pipeline",
            "amount": "10000.00",
            "probability": 10,
        })
        assert resp.status_code == 302
        opp = Opportunity.objects.filter(tenant=tenant_a, name="New Opportunity").first()
        assert opp is not None
        assert opp.number.startswith("OPP-")

    def test_edit_get_200(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_edit", args=[opportunity_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_record(self, client_a, opportunity_a):
        from apps.crm.models import Opportunity
        pk = opportunity_a.pk
        resp = client_a.post(reverse("crm:opportunity_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Opportunity.objects.filter(pk=pk).exists()

    def test_board_returns_200(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_board"))
        assert resp.status_code == 200

    def test_board_has_columns_context(self, client_a):
        resp = client_a.get(reverse("crm:opportunity_board"))
        assert "columns" in resp.context

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:opportunity_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestOpportunityAdvance:
    def test_advance_moves_to_next_stage(self, client_a, opportunity_a):
        from apps.crm.models import Opportunity
        assert opportunity_a.stage == "prospecting"
        client_a.post(reverse("crm:opportunity_advance", args=[opportunity_a.pk]))
        opportunity_a.refresh_from_db()
        assert opportunity_a.stage == "qualification"

    def test_advance_closed_won_sets_probability_100(self, client_a, tenant_a, account_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Nearly Won", account=account_a,
            stage="negotiation", amount="1000.00", probability=90,
        )
        client_a.post(reverse("crm:opportunity_advance", args=[opp.pk]))
        opp.refresh_from_db()
        assert opp.stage == "closed_won"
        assert opp.probability == 100

    def test_advance_closed_won_sets_forecast_closed(self, client_a, tenant_a, account_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Closing", account=account_a,
            stage="negotiation", amount="2000.00", probability=80,
        )
        client_a.post(reverse("crm:opportunity_advance", args=[opp.pk]))
        opp.refresh_from_db()
        assert opp.forecast_category == "closed"

    def test_advance_already_won_is_noop(self, client_a, tenant_a, account_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Won", account=account_a,
            stage="closed_won", amount="1000.00", probability=100,
        )
        client_a.post(reverse("crm:opportunity_advance", args=[opp.pk]))
        opp.refresh_from_db()
        assert opp.stage == "closed_won"

    def test_advance_stamps_stage_changed_at(self, client_a, opportunity_a):
        opp = opportunity_a
        original = opp.stage_changed_at
        client_a.post(reverse("crm:opportunity_advance", args=[opp.pk]))
        opp.refresh_from_db()
        assert opp.stage_changed_at >= original

    def test_advance_redirects_to_detail(self, client_a, opportunity_a):
        resp = client_a.post(reverse("crm:opportunity_advance", args=[opportunity_a.pk]))
        assert resp.status_code == 302
        assert str(opportunity_a.pk) in resp["Location"]


class TestOpportunitySplitViews:
    def test_split_add_valid_persists(self, client_a, tenant_a, opportunity_a, member_user):
        from apps.crm.models import OpportunitySplit
        resp = client_a.post(
            reverse("crm:opportunitysplit_add", args=[opportunity_a.pk]),
            {"user": str(member_user.pk), "split_type": "revenue", "percentage": "30", "notes": ""},
        )
        assert resp.status_code == 302
        assert OpportunitySplit.objects.filter(
            tenant=tenant_a, opportunity=opportunity_a, user=member_user
        ).exists()

    def test_split_add_over_100_pct_rejected(self, client_a, tenant_a, opportunity_a,
                                              admin_user, member_user):
        from apps.crm.models import OpportunitySplit
        # Pre-create a split at 80%
        OpportunitySplit.objects.create(
            tenant=tenant_a, opportunity=opportunity_a, user=admin_user,
            split_type="revenue", percentage=Decimal("80.00"),
        )
        before = OpportunitySplit.objects.filter(
            tenant=tenant_a, opportunity=opportunity_a
        ).count()
        # Try to add another 30% → total would be 110% → rejected
        client_a.post(
            reverse("crm:opportunitysplit_add", args=[opportunity_a.pk]),
            {"user": str(member_user.pk), "split_type": "revenue", "percentage": "30", "notes": ""},
        )
        after = OpportunitySplit.objects.filter(
            tenant=tenant_a, opportunity=opportunity_a
        ).count()
        assert after == before  # no new row

    def test_split_remove_deletes(self, client_a, split_a):
        from apps.crm.models import OpportunitySplit
        pk = split_a.pk
        opp_pk = split_a.opportunity_id
        resp = client_a.post(reverse("crm:opportunitysplit_remove", args=[pk]))
        assert resp.status_code == 302
        assert not OpportunitySplit.objects.filter(pk=pk).exists()

    def test_split_remove_redirects_to_opportunity(self, client_a, split_a):
        opp_pk = split_a.opportunity_id
        resp = client_a.post(reverse("crm:opportunitysplit_remove", args=[split_a.pk]))
        assert str(opp_pk) in resp["Location"]


class TestQuoteViews:
    def test_list_200(self, client_a, quote_a):
        resp = client_a.get(reverse("crm:quote_list"))
        assert resp.status_code == 200

    def test_list_shows_own_quote(self, client_a, quote_a):
        resp = client_a.get(reverse("crm:quote_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert quote_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, quote_a, quote_b):
        resp = client_a.get(reverse("crm:quote_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert quote_b.pk not in pks

    def test_detail_200(self, client_a, quote_a):
        resp = client_a.get(reverse("crm:quote_detail", args=[quote_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, quote_a):
        resp = client_a.get(reverse("crm:quote_detail", args=[quote_a.pk]))
        assert resp.context["obj"].pk == quote_a.pk

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:quote_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a, opportunity_a):
        from apps.crm.models import Quote
        resp = client_a.post(reverse("crm:quote_create"), {
            "name": "New Quote",
            "opportunity": str(opportunity_a.pk),
            "currency_code": "USD",
            "discount_pct": "0",
        })
        assert resp.status_code == 302
        q = Quote.objects.filter(tenant=tenant_a, name="New Quote").first()
        assert q is not None
        assert q.number.startswith("QUO-")
        assert q.status == "draft"

    def test_edit_get_200(self, client_a, quote_a):
        resp = client_a.get(reverse("crm:quote_edit", args=[quote_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_record(self, client_a, quote_a):
        from apps.crm.models import Quote
        pk = quote_a.pk
        resp = client_a.post(reverse("crm:quote_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Quote.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:quote_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestQuoteLineViews:
    def test_quoteline_add_creates_line(self, client_a, tenant_a, quote_a, product_a):
        from apps.crm.models import QuoteLine
        resp = client_a.post(
            reverse("crm:quoteline_add", args=[quote_a.pk]),
            {
                "product": str(product_a.pk),
                "description": "Widget Pro",
                "quantity": "2",
                "unit_price": "100.00",
                "discount_pct": "0",
                "tax_pct": "10.00",
            }
        )
        assert resp.status_code == 302
        assert QuoteLine.objects.filter(tenant=tenant_a, quote=quote_a).exists()

    def test_quoteline_add_recalcs_totals(self, client_a, tenant_a, quote_a, product_a):
        # Note: the view auto-fills tax_pct from the product when the submitted
        # tax_pct is falsy (0). product_a.tax_pct = 10.00, so:
        # subtotal = 1 * 200 = 200, tax = 200 * 0.10 = 20, total = 220.
        client_a.post(
            reverse("crm:quoteline_add", args=[quote_a.pk]),
            {
                "product": str(product_a.pk),
                "description": "Test",
                "quantity": "1",
                "unit_price": "200.00",
                "discount_pct": "0",
                "tax_pct": "0",  # falsy → view fills from product_a.tax_pct (10%)
            }
        )
        quote_a.refresh_from_db()
        assert quote_a.subtotal == Decimal("200.00")
        # Tax is auto-filled from product: 200 * 10% = 20; total = 220
        assert quote_a.total == Decimal("220.00")

    def test_quoteline_add_blocked_when_accepted(self, client_a, quote_a, product_a):
        from apps.crm.models import Quote, QuoteLine
        Quote.objects.filter(pk=quote_a.pk).update(status="accepted")
        before = QuoteLine.objects.filter(quote=quote_a).count()
        client_a.post(
            reverse("crm:quoteline_add", args=[quote_a.pk]),
            {
                "description": "Blocked line",
                "quantity": "1",
                "unit_price": "100.00",
                "discount_pct": "0",
                "tax_pct": "0",
            }
        )
        assert QuoteLine.objects.filter(quote=quote_a).count() == before

    def test_quoteline_remove_drops_line(self, client_a, tenant_a, quote_a, product_a):
        from apps.crm.models import QuoteLine
        line = QuoteLine.objects.create(
            tenant=tenant_a, quote=quote_a, product=product_a,
            description="To Remove", quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
        )
        pk = line.pk
        resp = client_a.post(reverse("crm:quoteline_remove", args=[pk]))
        assert resp.status_code == 302
        assert not QuoteLine.objects.filter(pk=pk).exists()

    def test_quoteline_remove_recalcs_totals(self, client_a, tenant_a, quote_a, product_a):
        from apps.crm.models import QuoteLine
        line = QuoteLine.objects.create(
            tenant=tenant_a, quote=quote_a, product=product_a,
            description="Will Remove", quantity=Decimal("2"),
            unit_price=Decimal("100.00"),
            discount_pct=Decimal("0"), tax_pct=Decimal("0"),
        )
        # Recalc after adding
        quote_a.recalc_totals()
        quote_a.refresh_from_db()
        assert quote_a.total > Decimal("0")
        # Remove and verify zeros
        client_a.post(reverse("crm:quoteline_remove", args=[line.pk]))
        quote_a.refresh_from_db()
        assert quote_a.total == Decimal("0.00")

    def test_quoteline_add_blocked_when_declined(self, client_a, quote_a, product_a):
        from apps.crm.models import Quote, QuoteLine
        Quote.objects.filter(pk=quote_a.pk).update(status="declined")
        before = QuoteLine.objects.filter(quote=quote_a).count()
        client_a.post(
            reverse("crm:quoteline_add", args=[quote_a.pk]),
            {"description": "Blocked", "quantity": "1", "unit_price": "50", "discount_pct": "0", "tax_pct": "0"}
        )
        assert QuoteLine.objects.filter(quote=quote_a).count() == before


class TestQuoteWorkflow:
    def test_quote_send_draft_becomes_sent(self, client_a, quote_a):
        from apps.crm.models import Quote
        assert quote_a.status == "draft"
        client_a.post(reverse("crm:quote_send", args=[quote_a.pk]))
        quote_a.refresh_from_db()
        assert quote_a.status == "sent"

    def test_quote_send_stamps_sent_at(self, client_a, quote_a):
        client_a.post(reverse("crm:quote_send", args=[quote_a.pk]))
        quote_a.refresh_from_db()
        assert quote_a.sent_at is not None

    def test_quote_send_wrong_state_is_noop(self, client_a, quote_a):
        from apps.crm.models import Quote
        # Already accepted — send should bounce
        Quote.objects.filter(pk=quote_a.pk).update(status="accepted")
        client_a.post(reverse("crm:quote_send", args=[quote_a.pk]))
        quote_a.refresh_from_db()
        assert quote_a.status == "accepted"

    def test_quote_accept_sent_becomes_accepted(self, client_a, quote_a):
        from apps.crm.models import Quote
        Quote.objects.filter(pk=quote_a.pk).update(status="sent")
        client_a.post(reverse("crm:quote_accept", args=[quote_a.pk]))
        quote_a.refresh_from_db()
        assert quote_a.status == "accepted"

    def test_quote_accept_stamps_accepted_at(self, client_a, quote_a):
        from apps.crm.models import Quote
        Quote.objects.filter(pk=quote_a.pk).update(status="sent")
        client_a.post(reverse("crm:quote_accept", args=[quote_a.pk]))
        quote_a.refresh_from_db()
        assert quote_a.accepted_at is not None

    def test_quote_accept_wrong_state_is_noop(self, client_a, quote_a):
        # Draft quote — accept must be noop
        assert quote_a.status == "draft"
        client_a.post(reverse("crm:quote_accept", args=[quote_a.pk]))
        quote_a.refresh_from_db()
        assert quote_a.status == "draft"

    def test_quote_decline_sent_becomes_declined(self, client_a, quote_a):
        from apps.crm.models import Quote
        Quote.objects.filter(pk=quote_a.pk).update(status="sent")
        client_a.post(reverse("crm:quote_decline", args=[quote_a.pk]))
        quote_a.refresh_from_db()
        assert quote_a.status == "declined"

    def test_quote_decline_wrong_state_is_noop(self, client_a, quote_a):
        assert quote_a.status == "draft"
        client_a.post(reverse("crm:quote_decline", args=[quote_a.pk]))
        quote_a.refresh_from_db()
        assert quote_a.status == "draft"

    def test_quote_send_redirects_to_detail(self, client_a, quote_a):
        resp = client_a.post(reverse("crm:quote_send", args=[quote_a.pk]))
        assert resp.status_code == 302
        assert str(quote_a.pk) in resp["Location"]

    def test_quote_accept_redirects_to_detail(self, client_a, quote_a):
        from apps.crm.models import Quote
        Quote.objects.filter(pk=quote_a.pk).update(status="sent")
        resp = client_a.post(reverse("crm:quote_accept", args=[quote_a.pk]))
        assert resp.status_code == 302
        assert str(quote_a.pk) in resp["Location"]


class TestSalesQuotaViews:
    def test_list_200(self, client_a, quota_a):
        resp = client_a.get(reverse("crm:salesquota_list"))
        assert resp.status_code == 200

    def test_list_shows_own_quota(self, client_a, quota_a):
        resp = client_a.get(reverse("crm:salesquota_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert quota_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, quota_a, quota_b):
        resp = client_a.get(reverse("crm:salesquota_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert quota_b.pk not in pks

    def test_detail_200(self, client_a, quota_a):
        resp = client_a.get(reverse("crm:salesquota_detail", args=[quota_a.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:salesquota_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a, admin_user, territory_a):
        from apps.crm.models import SalesQuota
        resp = client_a.post(reverse("crm:salesquota_create"), {
            "owner": str(admin_user.pk),
            "territory": str(territory_a.pk),
            "period_type": "month",
            "period_year": 2026,
            "period_number": 6,
            "target_amount": "15000.00",
            "notes": "",
        })
        assert resp.status_code == 302
        q = SalesQuota.objects.filter(
            tenant=tenant_a, period_type="month", period_number=6
        ).first()
        assert q is not None
        assert q.number.startswith("QTA-")

    def test_edit_get_200(self, client_a, quota_a):
        resp = client_a.get(reverse("crm:salesquota_edit", args=[quota_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_record(self, client_a, quota_a):
        from apps.crm.models import SalesQuota
        pk = quota_a.pk
        resp = client_a.post(reverse("crm:salesquota_delete", args=[pk]))
        assert resp.status_code == 302
        assert not SalesQuota.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:salesquota_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestForecastView:
    def test_forecast_returns_200(self, client_a):
        resp = client_a.get(reverse("crm:forecast"))
        assert resp.status_code == 200

    def test_forecast_has_cats_context(self, client_a):
        resp = client_a.get(reverse("crm:forecast"))
        assert "cats" in resp.context

    def test_forecast_has_quotas_context(self, client_a):
        resp = client_a.get(reverse("crm:forecast"))
        assert "quotas" in resp.context

    def test_forecast_has_totals_context(self, client_a):
        resp = client_a.get(reverse("crm:forecast"))
        assert "totals" in resp.context
        totals = resp.context["totals"]
        assert "pipeline" in totals
        assert "weighted" in totals
        assert "won" in totals
        assert "target" in totals

    def test_forecast_quota_attainment_with_fixture(self, client_a, tenant_a, account_a,
                                                     admin_user, territory_a):
        """Forecast view computes attainment % from a small fixture of won opps + quotas."""
        from apps.crm.models import Opportunity, SalesQuota
        # Create a won opportunity assigned to admin_user in territory_a
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Won Deal", account=account_a,
            stage="closed_won", amount="20000.00", probability=100,
            owner=admin_user, territory=territory_a,
            forecast_category="closed",
        )
        # Create a quota targeting admin_user + territory_a for Q1 2026
        quota = SalesQuota.objects.create(
            tenant=tenant_a, owner=admin_user, territory=territory_a,
            period_type="quarter", period_year=2026, period_number=1,
            target_amount="25000.00",
        )
        resp = client_a.get(reverse("crm:forecast"))
        assert resp.status_code == 200
        quotas = resp.context["quotas"]
        # Find our quota row
        our_row = next((r for r in quotas if r["q"].pk == quota.pk), None)
        assert our_row is not None
        # 20000 / 25000 * 100 = 80%
        assert our_row["pct"] == 80

    def test_forecast_totals_count_open_pipeline(self, client_a, tenant_a, account_a):
        from apps.crm.models import Opportunity
        Opportunity.objects.create(
            tenant=tenant_a, name="Open", account=account_a,
            stage="proposal", amount="10000.00", probability=50,
        )
        resp = client_a.get(reverse("crm:forecast"))
        totals = resp.context["totals"]
        assert totals["pipeline"] >= Decimal("10000")

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:forecast"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# =================================================================== MULTI-TENANT IDOR

class TestTerritoryIDOR:
    def test_detail_cross_tenant_404(self, client_a, territory_b):
        resp = client_a.get(reverse("crm:territory_detail", args=[territory_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, territory_b):
        resp = client_a.get(reverse("crm:territory_edit", args=[territory_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, territory_b):
        resp = client_a.post(
            reverse("crm:territory_edit", args=[territory_b.pk]),
            {"name": "Hijacked", "is_active": "on"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, territory_b):
        resp = client_a.post(reverse("crm:territory_delete", args=[territory_b.pk]))
        assert resp.status_code == 404


class TestProductIDOR:
    def test_detail_cross_tenant_404(self, client_a, product_b):
        resp = client_a.get(reverse("crm:product_detail", args=[product_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, product_b):
        resp = client_a.get(reverse("crm:product_edit", args=[product_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, product_b):
        resp = client_a.post(
            reverse("crm:product_edit", args=[product_b.pk]),
            {"name": "Hijacked"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, product_b):
        resp = client_a.post(reverse("crm:product_delete", args=[product_b.pk]))
        assert resp.status_code == 404


class TestPriceBookIDOR:
    def test_detail_cross_tenant_404(self, client_a, pricebook_b):
        resp = client_a.get(reverse("crm:pricebook_detail", args=[pricebook_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, pricebook_b):
        resp = client_a.get(reverse("crm:pricebook_edit", args=[pricebook_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, pricebook_b):
        resp = client_a.post(
            reverse("crm:pricebook_edit", args=[pricebook_b.pk]),
            {"name": "Hijacked", "price_adjustment_pct": "50"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, pricebook_b):
        resp = client_a.post(reverse("crm:pricebook_delete", args=[pricebook_b.pk]))
        assert resp.status_code == 404


class TestOpportunityIDOR:
    def test_detail_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.get(reverse("crm:opportunity_detail", args=[opportunity_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.get(reverse("crm:opportunity_edit", args=[opportunity_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.post(
            reverse("crm:opportunity_edit", args=[opportunity_b.pk]),
            {"name": "Hijacked", "stage": "closed_won"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.post(reverse("crm:opportunity_delete", args=[opportunity_b.pk]))
        assert resp.status_code == 404

    def test_advance_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.post(reverse("crm:opportunity_advance", args=[opportunity_b.pk]))
        assert resp.status_code == 404

    def test_split_add_cross_tenant_opportunity_404(self, client_a, opportunity_b, admin_user):
        resp = client_a.post(
            reverse("crm:opportunitysplit_add", args=[opportunity_b.pk]),
            {"user": str(admin_user.pk), "split_type": "revenue", "percentage": "30"},
        )
        assert resp.status_code == 404


class TestQuoteIDOR:
    def test_detail_cross_tenant_404(self, client_a, quote_b):
        resp = client_a.get(reverse("crm:quote_detail", args=[quote_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, quote_b):
        resp = client_a.get(reverse("crm:quote_edit", args=[quote_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, quote_b):
        resp = client_a.post(
            reverse("crm:quote_edit", args=[quote_b.pk]),
            {"name": "Hijacked"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, quote_b):
        resp = client_a.post(reverse("crm:quote_delete", args=[quote_b.pk]))
        assert resp.status_code == 404

    def test_send_cross_tenant_404(self, client_a, quote_b):
        resp = client_a.post(reverse("crm:quote_send", args=[quote_b.pk]))
        assert resp.status_code == 404

    def test_accept_cross_tenant_404(self, client_a, quote_b):
        resp = client_a.post(reverse("crm:quote_accept", args=[quote_b.pk]))
        assert resp.status_code == 404

    def test_decline_cross_tenant_404(self, client_a, quote_b):
        resp = client_a.post(reverse("crm:quote_decline", args=[quote_b.pk]))
        assert resp.status_code == 404

    def test_quoteline_add_cross_tenant_404(self, client_a, quote_b, product_a):
        resp = client_a.post(
            reverse("crm:quoteline_add", args=[quote_b.pk]),
            {"description": "Injected", "quantity": "1", "unit_price": "100",
             "discount_pct": "0", "tax_pct": "0"},
        )
        assert resp.status_code == 404


class TestOpportunitySplitIDOR:
    def test_split_remove_cross_tenant_404(self, client_a, tenant_b, opportunity_b, admin_b):
        from apps.crm.models import OpportunitySplit
        split_b = OpportunitySplit.objects.create(
            tenant=tenant_b, opportunity=opportunity_b, user=admin_b,
            split_type="revenue", percentage=Decimal("50.00"),
        )
        resp = client_a.post(reverse("crm:opportunitysplit_remove", args=[split_b.pk]))
        assert resp.status_code == 404
        assert OpportunitySplit.objects.filter(pk=split_b.pk).exists()


class TestSalesQuotaIDOR:
    def test_detail_cross_tenant_404(self, client_a, quota_b):
        resp = client_a.get(reverse("crm:salesquota_detail", args=[quota_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, quota_b):
        resp = client_a.get(reverse("crm:salesquota_edit", args=[quota_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, quota_b):
        resp = client_a.post(
            reverse("crm:salesquota_edit", args=[quota_b.pk]),
            {"target_amount": "99999"},
        )
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, quota_b):
        resp = client_a.post(reverse("crm:salesquota_delete", args=[quota_b.pk]))
        assert resp.status_code == 404


# =================================================================== AUTH / ANONYMOUS

class TestSFAAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("crm:opportunity_list", []),
        ("crm:opportunity_board", []),
        ("crm:territory_list", []),
        ("crm:product_list", []),
        ("crm:pricebook_list", []),
        ("crm:quote_list", []),
        ("crm:salesquota_list", []),
        ("crm:forecast", []),
        ("crm:opportunity_create", []),
        ("crm:territory_create", []),
        ("crm:product_create", []),
        ("crm:pricebook_create", []),
        ("crm:quote_create", []),
        ("crm:salesquota_create", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# =================================================================== N+1 QUERY BUDGET

class TestSFAListQueryBudget:
    def test_opportunity_list_query_count(
        self, client_a, tenant_a, account_a, django_assert_max_num_queries
    ):
        from apps.crm.models import Opportunity
        for i in range(5):
            Opportunity.objects.create(
                tenant=tenant_a, name=f"Opp{i}", account=account_a,
                stage="prospecting", amount="1000.00", probability=10,
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("crm:opportunity_list"))

    def test_product_list_query_count(
        self, client_a, tenant_a, django_assert_max_num_queries
    ):
        from apps.crm.models import Product
        for i in range(5):
            Product.objects.create(tenant=tenant_a, name=f"P{i}", unit_price="10.00")
        with django_assert_max_num_queries(15):
            client_a.get(reverse("crm:product_list"))

    def test_quote_list_query_count(
        self, client_a, tenant_a, opportunity_a, django_assert_max_num_queries
    ):
        from apps.crm.models import Quote
        for i in range(5):
            Quote.objects.create(
                tenant=tenant_a, name=f"Q{i}", opportunity=opportunity_a
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("crm:quote_list"))
