"""Inventory 5.7 Stock Movement & Transfers - board, queue and governance verbs.

The movement documents are SCM 4.3's ``StockTransfer`` spine; these tests drive THIS
module's HTTP surface: the inter/intra classification lens on the board, the tiered
approval queue (including its refusal paths), the admin gating on decisions, and
cross-tenant isolation on every route into the workflow.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import TransferApproval, TransferApprovalRule, TransferRoute
from apps.scm.models import Item, Location, StockTransfer, StockTransferLine

pytestmark = pytest.mark.django_db


def make_location(tenant, code):
    return Location.objects.create(tenant=tenant, code=code, name=code)


@pytest.fixture
def two_warehouses(db, tenant_a):
    """A bin under each of two warehouse roots -> an INTER-warehouse move between them."""
    wh1 = make_location(tenant_a, "WH1")
    wh2 = make_location(tenant_a, "WH2")
    bin1 = Location.objects.create(tenant=tenant_a, code="WH1-B1", name="Bin",
                                   parent=wh1)
    bin2 = Location.objects.create(tenant=tenant_a, code="WH2-B1", name="Bin",
                                   parent=wh2)
    return wh1, wh2, bin1, bin2


def make_transfer(tenant, source, destination, with_line=True):
    trf = StockTransfer.objects.create(
        tenant=tenant, from_location=source, to_location=destination,
        transfer_date=timezone.now().date())
    if with_line:
        # TransferLine.item is NOT NULL — one reusable stock SKU per workspace.
        item, _ = Item.objects.get_or_create(
            tenant=tenant, sku="TRF-ITEM",
            defaults={"name": "Transfer Test Widget"})
        StockTransferLine.objects.create(transfer=trf, item=item, quantity=5)
    return trf


# ------------------------------------------------------------------ board


class TestBoard:
    def test_renders_with_scope_and_status_filters(self, client_a, tenant_a, two_warehouses):
        wh1, _, bin1, bin2 = two_warehouses
        bin_same_root = Location.objects.create(
            tenant=tenant_a, code="WH1-B9", name="Bin", parent=wh1)
        inter = make_transfer(tenant_a, bin1, bin2)  # WH1 -> WH2: inter
        intra = make_transfer(tenant_a, bin1, bin_same_root)  # WH1 -> WH1: intra

        html = client_a.get(
            reverse("inventory:transfer_board") + "?scope=inter").content.decode()
        assert inter.number in html
        assert intra.number not in html

        html = client_a.get(
            reverse("inventory:transfer_board") + "?scope=intra&status=draft").content.decode()
        assert intra.number in html
        assert inter.number not in html

    def test_inter_vs_intra_classification(self, client_a, tenant_a, two_warehouses):
        _, _, bin1, bin2 = two_warehouses
        same_root = Location.objects.create(
            tenant=tenant_a, code="WH1-B2", name="Bin", parent_id=bin1.parent_id)
        make_transfer(tenant_a, bin1, bin2)   # WH1 -> WH2: inter
        make_transfer(tenant_a, bin1, same_root)  # WH1 -> WH1: intra
        html = client_a.get(reverse("inventory:transfer_board")).content.decode()
        assert "Inter-Warehouse" in html and "Intra-Warehouse" in html

    def test_requires_login(self, db, two_warehouses):
        from django.test import Client
        response = Client().get(reverse("inventory:transfer_board"))
        assert response.status_code == 302


# ------------------------------------------------------------------ submit + queue


class TestGovernanceFlow:
    @pytest.fixture
    def rule(self, db, tenant_a):
        return TransferApprovalRule.objects.create(
            tenant=tenant_a, name="Two tiers for all", applies_to="all",
            min_units=0, tier_count=2)

    def test_submit_parks_at_pending_approval(self, client_a, rule, tenant_a, two_warehouses):
        _, _, src, dst = two_warehouses
        route = TransferRoute.objects.create(tenant=tenant_a, name="R")
        trf = make_transfer(tenant_a, src, dst)
        response = client_a.post(reverse("inventory:transfer_submit", args=[trf.pk]),
                                 {"route": str(route.pk)})
        assert response.status_code == 302
        trf.refresh_from_db()
        assert trf.status == "pending_approval"
        assert trf.route == route

    def test_submit_without_lines_is_refused(self, client_a, rule, tenant_a, two_warehouses):
        _, _, src, dst = two_warehouses
        trf = make_transfer(tenant_a, src, dst, with_line=False)
        client_a.post(reverse("inventory:transfer_submit", args=[trf.pk]), {})
        trf.refresh_from_db()
        assert trf.status == "draft"

    def test_bogus_route_is_refused(self, client_a, rule, tenant_a, two_warehouses):
        _, _, src, dst = two_warehouses
        trf = make_transfer(tenant_a, src, dst)
        client_a.post(reverse("inventory:transfer_submit", args=[trf.pk]),
                      {"route": "999999"})
        trf.refresh_from_db()
        assert trf.status == "draft"

    def test_route_pinned_to_wrong_origin_is_refused(self, client_a, rule, tenant_a,
                                                     two_warehouses):
        """A route pinned at the wrong end must not carry the movement — covers()
        refuses it and the draft keeps both its status and its empty route."""
        _, _, src, dst = two_warehouses
        backwards = TransferRoute.objects.create(
            tenant=tenant_a, name="Backwards", origin_location=dst)
        trf = make_transfer(tenant_a, src, dst)
        client_a.post(reverse("inventory:transfer_submit", args=[trf.pk]),
                      {"route": str(backwards.pk)})
        trf.refresh_from_db()
        assert trf.status == "draft"
        assert trf.route is None

    def test_no_rules_falls_back_to_one_default_tier(self, client_a, tenant_a, two_warehouses):
        """With zero matching rules the fallback is ONE signature — never a bypass:
        a single approve clears the implicit tier and flips the spine to approved."""
        _, _, src, dst = two_warehouses
        trf = make_transfer(tenant_a, src, dst)
        client_a.post(reverse("inventory:transfer_submit", args=[trf.pk]), {})
        trf.refresh_from_db()
        assert trf.status == "pending_approval"
        client_a.post(reverse("inventory:transfer_tier_approve", args=[trf.pk, 1]))
        trf.refresh_from_db()
        assert trf.status == "approved"
        assert trf.approval_decisions.count() == 1

    def test_full_chain_approves_then_reject_returns_to_draft(self, client_a, rule, tenant_a,
                                                              two_warehouses):
        _, _, src, dst = two_warehouses
        trf = make_transfer(tenant_a, src, dst)
        client_a.post(reverse("inventory:transfer_submit", args=[trf.pk]), {})
        # Out-of-order first decision must be refused.
        client_a.post(reverse("inventory:transfer_tier_approve", args=[trf.pk, 2]))
        assert trf.approval_decisions.count() == 0
        client_a.post(reverse("inventory:transfer_tier_approve", args=[trf.pk, 1]))
        trf.refresh_from_db()
        assert trf.status == "pending_approval"
        client_a.post(reverse("inventory:transfer_tier_approve", args=[trf.pk, 2]))
        trf.refresh_from_db()
        assert trf.status == "approved"

        # A fresh movement rejected at tier 1 returns to draft with history intact.
        other = make_transfer(tenant_a, src, dst)
        client_a.post(reverse("inventory:transfer_submit", args=[other.pk]), {})
        client_a.post(reverse("inventory:transfer_tier_reject", args=[other.pk, 1]))
        other.refresh_from_db()
        assert other.status == "draft"
        assert other.approval_decisions.filter(decision="rejected").exists()

    def test_tier_decisions_are_admin_gated(self, member_client, tenant_a, rule, two_warehouses):
        _, _, src, dst = two_warehouses
        trf = make_transfer(tenant_a, src, dst)
        member_client.post(reverse("inventory:transfer_submit", args=[trf.pk]), {})
        response = member_client.post(
            reverse("inventory:transfer_tier_approve", args=[trf.pk, 1]))
        assert response.status_code == 403
        assert trf.approval_decisions.count() == 0


# ------------------------------------------------------------------ isolation


class TestTenantIsolation:
    def test_foreign_records_are_404(self, client_a, tenant_b, two_warehouses):
        _, _, src, _ = two_warehouses
        foreign_dst = make_location(tenant_b, "WH-B")
        trf = make_transfer(tenant_b, foreign_dst, src)
        route = TransferRoute.objects.create(tenant=tenant_b, name="Foreign Route")
        rule = TransferApprovalRule.objects.create(tenant=tenant_b, name="Foreign Rule")
        for url in (
            reverse("inventory:transfer_panel", args=[trf.pk]),
            reverse("inventory:transferroute_detail", args=[route.pk]),
            reverse("inventory:transferapprovalrule_edit", args=[rule.pk]),
        ):
            assert client_a.get(url).status_code == 404
        assert client_a.post(
            reverse("inventory:transfer_submit", args=[trf.pk]), {}).status_code == 404
        assert client_a.post(
            reverse("inventory:transfer_tier_approve", args=[trf.pk, 1])).status_code == 404

