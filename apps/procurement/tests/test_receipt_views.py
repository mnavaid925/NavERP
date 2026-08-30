"""Procurement 6.12 Goods Receipt & Inspection — view / CRUD integration flows.

Every surface is exercised through the real URLconf and rendered bytes: the three registers
(tolerance policies, discrepancies, returns to vendor) plus the three computed boards (receiving
console, tolerance exceptions, receipt audit) — search, each filter, junk FK/enum params, page 2
and a page past the end — then the create / edit / delete verbs and the workflow POSTs.

Contract discipline followed here:

* a context key is only asserted "present" together with an assertion that it is POPULATED (L41);
* every reference date derives from ``timezone.localdate()``, never ``date.today()`` (L16);
* page-2 cases build enough rows to actually cross the page size (15 for the registers, 30 for
  the boards) — a page-2 guard is invisible at fixture size (L9);
* junk FK params and junk enum params must render 200 and echo back sanitized, never 500 (L11);
* the two hand-parsed number surfaces (the discrepancy prefill, and the console form's dynamic
  ``qty_<pk>`` fields) are probed with NaN / Infinity / negative / over-max_digits (L35);
* every list view is wrapped in ``django_assert_max_num_queries`` because each renders a chained
  ``__str__`` FK hop.
"""
import datetime
from decimal import Decimal

import pytest

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.procurement.models import (
    AdvancedShipmentNotice, AsnLine, ReceiptDiscrepancy, ReceiptTolerancePolicy, ReturnToVendor,
    ReturnToVendorLine,
)
from apps.scm.models import (
    GoodsReceiptLine, GoodsReceiptNote, LotSerial, PurchaseOrder, PurchaseOrderLine,
)

pytestmark = pytest.mark.django_db


# ================================================================== helpers

def _receipt_today():
    """The SAME basis every 6.12 view uses — never ``date.today()`` (L16)."""
    return timezone.localdate()


def _receipt_days(n):
    return datetime.timedelta(days=n)


def _receipt_templates(response):
    return [t.name for t in response.templates if t.name]


def _receipt_messages(response):
    return [str(m) for m in response.context["messages"]]


def _receipt_pks(response):
    return [o.pk for o in response.context["object_list"]]


def _receipt_audit_rows(model, obj, action):
    ct = ContentType.objects.get_for_model(model)
    return AuditLog.objects.filter(content_type=ct, object_id=obj.pk, action=action)


#: Junk values every int-FK filter on every 6.12 list/board must SKIP rather than 500 on (L11).
#: The superscript two is the sharp one: ``isdigit()`` is True for it but ``int()`` refuses it.
_RECEIPT_JUNK_INTS = ["abc", "999999999999999999999", "²", "-1", "1.5", ""]


def _receipt_policy_post(**overrides):
    """A complete, valid ``ReceiptTolerancePolicyForm`` POST body."""
    body = {
        "name": "Console band", "item": "", "category": "", "vendor": "",
        "over_receipt_pct": "7", "under_receipt_pct": "", "over_receipt_qty": "",
        "early_receipt_days": "", "late_receipt_days": "", "action": "warn",
        "price_variance_pct": "", "priority": "20", "notes": "", "is_active": "on",
    }
    body.update(overrides)
    return body


def _receipt_discrepancy_post(**overrides):
    """A complete, valid ``ReceiptDiscrepancyForm`` POST body (create shape)."""
    body = {
        "goods_receipt": "", "goods_receipt_line": "", "kind": "damaged", "severity": "major",
        "quantity_affected": "2", "item_description": "", "sku_hint": "", "lot_number": "",
        "serial_number": "", "expiry_date": "", "description": "Two cartons crushed in transit.",
        "evidence_url": "", "remedy": "pending", "vendor_reference": "", "nonconformance": "",
        "quarantine_order": "", "return_to_vendor": "",
    }
    body.update(overrides)
    return body


def _receipt_rtv_post(**overrides):
    """A complete, valid ``ReturnToVendorForm`` POST body."""
    body = {
        "vendor": "", "purchase_order": "", "goods_receipt": "", "discrepancy": "",
        "reason": "damaged", "reason_note": "", "remedy": "credit",
        "supplier_rma_number": "RMA-CREATE-1", "carrier_name": "", "tracking_number": "",
        "expected_return_date": "", "credit_note_ref": "", "notes": "",
    }
    body.update(overrides)
    return body


def _receipt_line_management(total=1, initial=0):
    return {
        "lines-TOTAL_FORMS": str(total), "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "50",
    }


def _receipt_line_post(index=0, **overrides):
    body = {
        f"lines-{index}-id": "", f"lines-{index}-goods_receipt_line": "",
        f"lines-{index}-po_line": "", f"lines-{index}-item_description": "",
        f"lines-{index}-sku_hint": "", f"lines-{index}-uom_hint": "",
        f"lines-{index}-quantity_returned": "1", f"lines-{index}-lot_number": "",
        f"lines-{index}-serial_number": "", f"lines-{index}-condition_note": "",
    }
    body.update({f"lines-{index}-{key}": value for key, value in overrides.items()})
    return body


def _receipt_bulk_policies(tenant, count, prefix="Bulk band"):
    """``count`` tolerance rules — enough to push the 15-row register onto page 2."""
    return [
        ReceiptTolerancePolicy.objects.create(
            tenant=tenant, name=f"{prefix} {index:03d}", over_receipt_pct=Decimal("5"),
            priority=50 + index)
        for index in range(count)
    ]


def _receipt_bulk_discrepancies(tenant, grn, count):
    return [
        ReceiptDiscrepancy.objects.create(
            tenant=tenant, goods_receipt=grn, kind="documentation", severity="minor",
            quantity_affected=Decimal("0"),
            description=f"Bulk paperwork finding {index:03d}.")
        for index in range(count)
    ]


def _receipt_bulk_rtvs(tenant, vendor, count):
    return [
        ReturnToVendor.objects.create(
            tenant=tenant, vendor=vendor, reason="damaged", remedy="credit",
            supplier_rma_number=f"BULK-RMA-{index:03d}")
        for index in range(count)
    ]


def _receipt_bulk_asns(tenant, po, po_line, count):
    """``count`` in-transit notices, each with one declared line on the SAME ordered line."""
    rows = []
    for index in range(count):
        asn = AdvancedShipmentNotice.objects.create(
            tenant=tenant, purchase_order=po, status="in_transit", source="manual",
            supplier_reference=f"BULK-DN-{index:03d}",
            tracking_number=f"BULK-TRK-{index:03d}",
            expected_delivery_date=_receipt_today() + _receipt_days(index + 1))
        AsnLine.objects.create(asn=asn, po_line=po_line, quantity_shipped=Decimal("1"),
                               sku_hint="BRG-40")
        rows.append(asn)
    return rows


def _receipt_bulk_over_lines(tenant, vendor, count):
    """One order of ``count`` single-unit lines, all received five-fold — every line over."""
    order = PurchaseOrder.objects.create(
        tenant=tenant, vendor=vendor, status="approved", order_date=_receipt_today(),
        expected_date=_receipt_today())
    receipt = GoodsReceiptNote.objects.create(
        tenant=tenant, purchase_order=order, receipt_date=_receipt_today(), status="draft",
        delivery_note_ref="BULK-DN-OVER")
    rows = []
    for index in range(count):
        po_line = PurchaseOrderLine.objects.create(
            purchase_order=order, item_description=f"Bulk part {index:03d}",
            quantity=Decimal("1"), unit_price=Decimal("3.00"),
            sku_hint=f"BULK-{index:03d}", uom_hint="EA")
        rows.append(GoodsReceiptLine.objects.create(
            goods_receipt=receipt, po_line=po_line, quantity_received=Decimal("5")))
    return receipt, rows


def _receipt_bulk_audit(tenant, grn, count):
    ct = ContentType.objects.get_for_model(GoodsReceiptNote)
    return [
        AuditLog.objects.create(
            tenant=tenant, content_type=ct, object_id=grn.pk,
            target=f"Bulk receipt entry {index:03d}", action="update")
        for index in range(count)
    ]


# ================================================================== tolerance policy register


def test_receipt_tolerancepolicy_list_renders_contract_context(
        client_a, receipt_policy_catchall_a, receipt_policy_item_a, receipt_policy_category_a,
        receipt_policy_vendor_a, receipt_policy_inactive_a, receipt_item_a, receipt_vendor_a):
    r = client_a.get(reverse("procurement:tolerancepolicy_list"))
    assert r.status_code == 200
    assert ("procurement/goodsreceiptinspection/tolerancepolicy/list.html"
            in _receipt_templates(r))

    ctx = r.context
    assert len(ctx["object_list"]) == 5
    assert ctx["page_obj"].paginator.count == 5
    assert ctx["q"] == ""
    assert ctx["scope"] == ""
    assert [v for v, _ in ctx["action_choices"]] == ["none", "warn", "block_flag"]
    assert [v for v, _ in ctx["scope_choices"]] == ["item", "category", "catchall"]
    assert [i.pk for i in ctx["items"]] == [receipt_item_a.pk]
    assert [v.pk for v in ctx["vendors"]] == [receipt_vendor_a.pk]
    assert ctx["stats"] == {"total": 5, "active": 4, "flagging": 1, "catch_all": 3}

    body = r.content.decode()
    for policy in (receipt_policy_catchall_a, receipt_policy_item_a, receipt_policy_vendor_a):
        assert policy.name in body


def test_receipt_tolerancepolicy_list_search_matches_each_field(
        client_a, receipt_policy_catchall_a, receipt_policy_item_a, receipt_policy_vendor_a):
    url = reverse("procurement:tolerancepolicy_list")

    r = client_a.get(url, {"q": "BRG-40 strict"})
    assert _receipt_pks(r) == [receipt_policy_item_a.pk]
    assert r.context["q"] == "BRG-40 strict"

    # item__sku — the chained search leg
    r = client_a.get(url, {"q": "BRG-40"})
    assert _receipt_pks(r) == [receipt_policy_item_a.pk]

    # vendor__name
    r = client_a.get(url, {"q": "Northwind Forge"})
    assert _receipt_pks(r) == [receipt_policy_vendor_a.pk]

    r = client_a.get(url, {"q": "no-such-band"})
    assert r.status_code == 200 and _receipt_pks(r) == []


def test_receipt_tolerancepolicy_list_notes_search_leg(client_a, tenant_a):
    marked = ReceiptTolerancePolicy.objects.create(
        tenant=tenant_a, name="Noted band", over_receipt_pct=Decimal("2"),
        notes="Agreed at the quarterly business review")
    ReceiptTolerancePolicy.objects.create(tenant=tenant_a, name="Quiet band",
                                          over_receipt_pct=Decimal("2"))
    r = client_a.get(reverse("procurement:tolerancepolicy_list"), {"q": "quarterly business"})
    assert _receipt_pks(r) == [marked.pk]


def test_receipt_tolerancepolicy_list_action_and_active_filters(
        client_a, receipt_policy_catchall_a, receipt_policy_item_a, receipt_policy_inactive_a):
    url = reverse("procurement:tolerancepolicy_list")

    r = client_a.get(url, {"action": "block_flag"})
    assert _receipt_pks(r) == [receipt_policy_item_a.pk]

    r = client_a.get(url, {"action": "none"})
    assert _receipt_pks(r) == []

    r = client_a.get(url, {"active": "False"})
    assert _receipt_pks(r) == [receipt_policy_inactive_a.pk]

    r = client_a.get(url, {"active": "True"})
    assert set(_receipt_pks(r)) == {receipt_policy_catchall_a.pk, receipt_policy_item_a.pk}


def test_receipt_tolerancepolicy_list_item_and_vendor_filters(
        client_a, receipt_policy_catchall_a, receipt_policy_item_a, receipt_policy_vendor_a,
        receipt_item_a, receipt_vendor_a):
    url = reverse("procurement:tolerancepolicy_list")

    r = client_a.get(url, {"item": str(receipt_item_a.pk)})
    assert _receipt_pks(r) == [receipt_policy_item_a.pk]

    r = client_a.get(url, {"vendor": str(receipt_vendor_a.pk)})
    assert _receipt_pks(r) == [receipt_policy_vendor_a.pk]

    r = client_a.get(url, {"item": str(receipt_item_a.pk + 9999)})
    assert _receipt_pks(r) == []


def test_receipt_tolerancepolicy_list_scope_filter_narrows_before_pagination(
        client_a, receipt_policy_catchall_a, receipt_policy_item_a, receipt_policy_category_a):
    url = reverse("procurement:tolerancepolicy_list")

    r = client_a.get(url, {"scope": "item"})
    assert _receipt_pks(r) == [receipt_policy_item_a.pk]
    assert r.context["scope"] == "item"
    assert r.context["page_obj"].paginator.count == 1

    r = client_a.get(url, {"scope": "category"})
    assert _receipt_pks(r) == [receipt_policy_category_a.pk]

    r = client_a.get(url, {"scope": "catchall"})
    assert _receipt_pks(r) == [receipt_policy_catchall_a.pk]

    # unknown scope: ignored, echoed back EMPTY, and every row still shown
    r = client_a.get(url, {"scope": "zzz"})
    assert r.status_code == 200
    assert r.context["scope"] == ""
    assert len(_receipt_pks(r)) == 3
    # the stat cards stay whole-workspace, deliberately
    assert r.context["stats"]["total"] == 3


@pytest.mark.parametrize("value", _RECEIPT_JUNK_INTS)
def test_receipt_tolerancepolicy_list_junk_fk_params_never_500(client_a,
                                                               receipt_policy_catchall_a, value):
    url = reverse("procurement:tolerancepolicy_list")
    for param in ("item", "vendor"):
        r = client_a.get(url, {param: value})
        assert r.status_code == 200
        assert _receipt_pks(r) == [receipt_policy_catchall_a.pk]


@pytest.mark.parametrize("params", [
    {"action": "zzz"}, {"active": "abc"}, {"scope": "zzz"}, {"q": "%"},
])
def test_receipt_tolerancepolicy_list_junk_enum_params_never_500(client_a,
                                                                 receipt_policy_catchall_a,
                                                                 params):
    r = client_a.get(reverse("procurement:tolerancepolicy_list"), params)
    assert r.status_code == 200
    assert "object_list" in r.context


def test_receipt_tolerancepolicy_list_pagination_page_two_and_past_the_end(client_a, tenant_a):
    _receipt_bulk_policies(tenant_a, 18)
    url = reverse("procurement:tolerancepolicy_list")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 15
    assert first.context["page_obj"].number == 1
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 3
    assert second.context["page_obj"].number == 2
    assert set(_receipt_pks(first)).isdisjoint(_receipt_pks(second))

    past = client_a.get(url, {"page": "999"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2

    junk = client_a.get(url, {"page": "abc"})
    assert junk.status_code == 200 and junk.context["page_obj"].number == 1


def test_receipt_tolerancepolicy_list_query_count_is_bounded(
        client_a, tenant_a, receipt_item_a, receipt_vendor_a, django_assert_max_num_queries):
    # 15 rows, each rendering obj.item.sku, obj.category.name and obj.vendor.name. Without the
    # select_related chain in _scoped() this is 45+.
    rows = _receipt_bulk_policies(tenant_a, 15)
    ReceiptTolerancePolicy.objects.filter(pk__in=[r.pk for r in rows]).update(
        item=receipt_item_a, vendor=receipt_vendor_a)
    with django_assert_max_num_queries(16):
        r = client_a.get(reverse("procurement:tolerancepolicy_list"))
        assert r.status_code == 200
        assert len(r.context["object_list"]) == 15
        r.content.decode()


def test_receipt_tolerancepolicy_list_never_shows_other_tenant_rows(
        client_a, receipt_policy_catchall_a, receipt_policy_b):
    r = client_a.get(reverse("procurement:tolerancepolicy_list"))
    pks = _receipt_pks(r)
    assert receipt_policy_catchall_a.pk in pks
    assert receipt_policy_b.pk not in pks
    assert (reverse("procurement:tolerancepolicy_detail", args=[receipt_policy_b.pk])
            not in r.content.decode())


# ------------------------------------------------------------------ tolerance policy detail


def test_receipt_tolerancepolicy_detail_renders_contract_context(
        client_a, receipt_policy_catchall_a, receipt_grn_line_a, receipt_item_a):
    r = client_a.get(reverse("procurement:tolerancepolicy_detail",
                             args=[receipt_policy_catchall_a.pk]))
    assert r.status_code == 200
    assert ("procurement/goodsreceiptinspection/tolerancepolicy/detail.html"
            in _receipt_templates(r))

    ctx = r.context
    assert ctx["obj"].pk == receipt_policy_catchall_a.pk
    assert ctx["example"]["ordered"] == Decimal("100")
    assert ctx["example"]["max_accept"] == Decimal("105")
    assert ctx["example"]["min_accept"] == Decimal("90")
    assert ctx["example"]["unlimited"] is False
    assert ctx["scope_label"] == "Catch-all"
    assert ctx["specificity_tier"] == 1
    assert ctx["advisory_note"] == "This policy flags; it never blocks scm:goodsreceipt_receive."
    assert ctx["can_edit"] is True and ctx["can_delete"] is True

    # POPULATED, not merely present: the catch-all governs the workspace's only receipt line.
    rows = ctx["governed_lines"]
    assert len(rows) == 1
    row = rows[0]
    assert row["receipt_line"].pk == receipt_grn_line_a.pk
    assert row["ordered"] == Decimal("10")
    assert row["received"] == Decimal("12")
    assert row["verdict"] == "over"
    assert row["verdict_css"] == "badge-amber"
    assert row["verdict_label"] == "Over-receipt"


def test_receipt_tolerancepolicy_detail_inactive_rule_governs_nothing(
        client_a, receipt_policy_inactive_a, receipt_grn_line_a):
    r = client_a.get(reverse("procurement:tolerancepolicy_detail",
                             args=[receipt_policy_inactive_a.pk]))
    assert r.status_code == 200
    assert r.context["governed_lines"] == []


def test_receipt_tolerancepolicy_detail_member_sees_no_write_buttons(
        member_client, receipt_policy_catchall_a):
    r = member_client.get(reverse("procurement:tolerancepolicy_detail",
                                  args=[receipt_policy_catchall_a.pk]))
    assert r.status_code == 200
    assert r.context["can_edit"] is False and r.context["can_delete"] is False


def test_receipt_tolerancepolicy_detail_cross_tenant_is_404(client_a, receipt_policy_b):
    r = client_a.get(reverse("procurement:tolerancepolicy_detail", args=[receipt_policy_b.pk]))
    assert r.status_code == 404


# ------------------------------------------------------------------ tolerance policy create/edit


def test_receipt_tolerancepolicy_create_get_context(client_a, receipt_item_a, receipt_vendor_a):
    r = client_a.get(reverse("procurement:tolerancepolicy_create"))
    assert r.status_code == 200
    assert ("procurement/goodsreceiptinspection/tolerancepolicy/form.html"
            in _receipt_templates(r))
    assert r.context["is_edit"] is False

    form = r.context["form"]
    assert "name" in form.fields
    assert list(form.fields["item"].queryset) == [receipt_item_a]
    assert list(form.fields["vendor"].queryset) == [receipt_vendor_a]
    for hidden in ("tenant", "created_at", "updated_at"):
        assert hidden not in form.fields


def test_receipt_tolerancepolicy_create_post_saves_with_request_tenant(client_a, tenant_a):
    r = client_a.post(reverse("procurement:tolerancepolicy_create"),
                      _receipt_policy_post(name="Dock band", priority="4"), follow=True)
    assert r.status_code == 200

    obj = ReceiptTolerancePolicy.objects.get(name="Dock band")
    assert obj.tenant_id == tenant_a.pk
    assert obj.over_receipt_pct == Decimal("7")
    assert obj.priority == 4
    assert obj.is_active is True
    assert _receipt_audit_rows(ReceiptTolerancePolicy, obj, "create").exists()
    # crud_create redirects to the register
    assert r.redirect_chain[-1][0] == reverse("procurement:tolerancepolicy_list")


def test_receipt_tolerancepolicy_create_invalid_post_rerenders_without_saving(client_a):
    before = ReceiptTolerancePolicy.objects.count()
    r = client_a.post(reverse("procurement:tolerancepolicy_create"),
                      _receipt_policy_post(name=""))
    assert r.status_code == 200
    assert r.context["form"].errors
    assert ReceiptTolerancePolicy.objects.count() == before


def test_receipt_tolerancepolicy_create_is_admin_only(member_client):
    assert member_client.get(reverse("procurement:tolerancepolicy_create")).status_code == 403
    assert member_client.post(reverse("procurement:tolerancepolicy_create"),
                              _receipt_policy_post()).status_code == 403
    assert not ReceiptTolerancePolicy.objects.filter(name="Console band").exists()


def test_receipt_tolerancepolicy_edit_get_and_post(client_a, receipt_policy_catchall_a):
    url = reverse("procurement:tolerancepolicy_edit", args=[receipt_policy_catchall_a.pk])

    r = client_a.get(url)
    assert r.status_code == 200
    assert ("procurement/goodsreceiptinspection/tolerancepolicy/form.html"
            in _receipt_templates(r))
    assert r.context["is_edit"] is True
    assert r.context["obj"].pk == receipt_policy_catchall_a.pk

    r = client_a.post(url, _receipt_policy_post(name="Widened band", over_receipt_pct="12",
                                                under_receipt_pct="10", priority="10"))
    assert r.status_code == 302
    assert r.url == reverse("procurement:tolerancepolicy_detail",
                            args=[receipt_policy_catchall_a.pk])

    receipt_policy_catchall_a.refresh_from_db()
    assert receipt_policy_catchall_a.name == "Widened band"
    assert receipt_policy_catchall_a.over_receipt_pct == Decimal("12")


def test_receipt_tolerancepolicy_edit_is_admin_only_and_cross_tenant_404(
        member_client, client_a, receipt_policy_catchall_a, receipt_policy_b):
    assert member_client.get(reverse("procurement:tolerancepolicy_edit",
                                     args=[receipt_policy_catchall_a.pk])).status_code == 403
    assert client_a.get(reverse("procurement:tolerancepolicy_edit",
                                args=[receipt_policy_b.pk])).status_code == 404


def test_receipt_tolerancepolicy_delete_is_post_only(client_a, receipt_policy_catchall_a):
    url = reverse("procurement:tolerancepolicy_delete", args=[receipt_policy_catchall_a.pk])

    got = client_a.get(url)
    assert got.status_code == 405
    assert ReceiptTolerancePolicy.objects.filter(pk=receipt_policy_catchall_a.pk).exists()

    r = client_a.post(url)
    assert r.status_code == 302
    assert r.url == reverse("procurement:tolerancepolicy_list")
    assert not ReceiptTolerancePolicy.objects.filter(pk=receipt_policy_catchall_a.pk).exists()


def test_receipt_tolerancepolicy_delete_gates(member_client, client_a, receipt_policy_catchall_a,
                                              receipt_policy_b):
    assert member_client.post(reverse("procurement:tolerancepolicy_delete",
                                      args=[receipt_policy_catchall_a.pk])).status_code == 403
    assert ReceiptTolerancePolicy.objects.filter(pk=receipt_policy_catchall_a.pk).exists()

    assert client_a.post(reverse("procurement:tolerancepolicy_delete",
                                 args=[receipt_policy_b.pk])).status_code == 404
    assert ReceiptTolerancePolicy.objects.filter(pk=receipt_policy_b.pk).exists()


# ================================================================== discrepancy register


def test_receipt_discrepancy_list_renders_contract_context(
        client_a, receipt_discrepancy_open_a, receipt_discrepancy_header_a,
        receipt_discrepancy_notified_a, receipt_discrepancy_resolved_a, receipt_grn_a,
        receipt_vendor_a):
    r = client_a.get(reverse("procurement:discrepancy_list"))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/discrepancy/list.html" in _receipt_templates(r)

    ctx = r.context
    assert len(ctx["object_list"]) == 4
    assert ctx["page_obj"].paginator.count == 4
    assert ctx["q"] == ""
    assert [v for v, _ in ctx["status_choices"]] == ["open", "vendor_notified", "resolved",
                                                     "cancelled"]
    assert [v for v, _ in ctx["kind_choices"]] == [
        "over_shipment", "short_shipment", "damaged", "wrong_item", "quality_failure",
        "documentation", "late_delivery"]
    assert [v for v, _ in ctx["severity_choices"]] == ["minor", "major", "critical"]
    assert [v for v, _ in ctx["remedy_choices"]] == ["pending", "replacement", "credit", "rtv",
                                                     "accept_as_is", "scrap"]
    assert receipt_grn_a.pk in [g.pk for g in ctx["receipts"]]
    assert [v.pk for v in ctx["vendors"]] == [receipt_vendor_a.pk]
    assert ctx["stats"] == {"open": 2, "notified": 1, "resolved": 1, "critical": 0}

    body = r.content.decode()
    assert receipt_discrepancy_open_a.number in body


@pytest.mark.parametrize("term_attr", ["number", "description"])
def test_receipt_discrepancy_list_search_matches_each_field(
        client_a, receipt_discrepancy_open_a, receipt_discrepancy_header_a, term_attr):
    term = getattr(receipt_discrepancy_open_a, term_attr)
    r = client_a.get(reverse("procurement:discrepancy_list"), {"q": term})
    assert r.status_code == 200
    assert _receipt_pks(r) == [receipt_discrepancy_open_a.pk]
    assert r.context["q"] == term


def test_receipt_discrepancy_list_search_matches_receipt_and_vendor_reference(
        client_a, receipt_discrepancy_open_a, receipt_discrepancy_notified_a, receipt_grn_a):
    url = reverse("procurement:discrepancy_list")

    r = client_a.get(url, {"q": receipt_grn_a.number})
    assert set(_receipt_pks(r)) == {receipt_discrepancy_open_a.pk,
                                    receipt_discrepancy_notified_a.pk}

    r = client_a.get(url, {"q": "SUP-CASE-11"})
    assert _receipt_pks(r) == [receipt_discrepancy_notified_a.pk]

    r = client_a.get(url, {"q": "no-such-finding"})
    assert r.status_code == 200 and _receipt_pks(r) == []


def test_receipt_discrepancy_list_status_kind_severity_remedy_filters(
        client_a, receipt_discrepancy_open_a, receipt_discrepancy_header_a,
        receipt_discrepancy_notified_a, receipt_discrepancy_resolved_a):
    url = reverse("procurement:discrepancy_list")

    r = client_a.get(url, {"status": "vendor_notified"})
    assert _receipt_pks(r) == [receipt_discrepancy_notified_a.pk]

    r = client_a.get(url, {"status": "resolved"})
    assert _receipt_pks(r) == [receipt_discrepancy_resolved_a.pk]

    r = client_a.get(url, {"kind": "documentation"})
    assert _receipt_pks(r) == [receipt_discrepancy_header_a.pk]

    r = client_a.get(url, {"severity": "minor"})
    assert _receipt_pks(r) == [receipt_discrepancy_header_a.pk]

    r = client_a.get(url, {"remedy": "credit"})
    assert _receipt_pks(r) == [receipt_discrepancy_resolved_a.pk]

    r = client_a.get(url, {"remedy": "scrap"})
    assert _receipt_pks(r) == []


def test_receipt_discrepancy_list_grn_and_vendor_filters(
        client_a, receipt_discrepancy_open_a, receipt_discrepancy_header_a, receipt_grn_a,
        receipt_vendor_a):
    url = reverse("procurement:discrepancy_list")

    r = client_a.get(url, {"grn": str(receipt_grn_a.pk)})
    assert set(_receipt_pks(r)) == {receipt_discrepancy_open_a.pk,
                                    receipt_discrepancy_header_a.pk}

    r = client_a.get(url, {"vendor": str(receipt_vendor_a.pk)})
    assert len(_receipt_pks(r)) == 2

    r = client_a.get(url, {"grn": str(receipt_grn_a.pk + 9999)})
    assert _receipt_pks(r) == []


@pytest.mark.parametrize("value", _RECEIPT_JUNK_INTS)
def test_receipt_discrepancy_list_junk_fk_params_never_500(client_a, receipt_discrepancy_open_a,
                                                           value):
    url = reverse("procurement:discrepancy_list")
    for param in ("grn", "vendor"):
        r = client_a.get(url, {param: value})
        assert r.status_code == 200
        assert _receipt_pks(r) == [receipt_discrepancy_open_a.pk]


@pytest.mark.parametrize("params", [
    {"status": "zzz"}, {"kind": "zzz"}, {"severity": "zzz"}, {"remedy": "zzz"},
])
def test_receipt_discrepancy_list_junk_enum_params_never_500(client_a,
                                                             receipt_discrepancy_open_a, params):
    r = client_a.get(reverse("procurement:discrepancy_list"), params)
    assert r.status_code == 200
    assert _receipt_pks(r) == []


def test_receipt_discrepancy_list_pagination_page_two_and_past_the_end(client_a, tenant_a,
                                                                       receipt_grn_a):
    _receipt_bulk_discrepancies(tenant_a, receipt_grn_a, 18)
    url = reverse("procurement:discrepancy_list")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 15
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 3
    assert set(_receipt_pks(first)).isdisjoint(_receipt_pks(second))

    past = client_a.get(url, {"page": "999"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2

    junk = client_a.get(url, {"page": "abc"})
    assert junk.status_code == 200 and junk.context["page_obj"].number == 1


def test_receipt_discrepancy_list_query_count_is_bounded(client_a, tenant_a, receipt_grn_a,
                                                          django_assert_max_num_queries):
    # 15 rows; the `vendor` property is TWO hops (goods_receipt -> purchase_order -> vendor).
    _receipt_bulk_discrepancies(tenant_a, receipt_grn_a, 15)
    with django_assert_max_num_queries(18):
        r = client_a.get(reverse("procurement:discrepancy_list"))
        assert r.status_code == 200
        assert len(r.context["object_list"]) == 15
        r.content.decode()


def test_receipt_discrepancy_list_never_shows_other_tenant_rows(client_a,
                                                                 receipt_discrepancy_open_a,
                                                                 receipt_discrepancy_b):
    r = client_a.get(reverse("procurement:discrepancy_list"))
    pks = _receipt_pks(r)
    assert receipt_discrepancy_open_a.pk in pks
    assert receipt_discrepancy_b.pk not in pks
    assert (reverse("procurement:discrepancy_detail", args=[receipt_discrepancy_b.pk])
            not in r.content.decode())


# ------------------------------------------------------------------ discrepancy detail


def test_receipt_discrepancy_detail_renders_contract_context(
        client_a, receipt_discrepancy_open_a, receipt_grn_a, receipt_grn_line2_a,
        receipt_po_a, receipt_vendor_a, receipt_policy_catchall_a):
    r = client_a.get(reverse("procurement:discrepancy_detail",
                             args=[receipt_discrepancy_open_a.pk]))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/discrepancy/detail.html" in _receipt_templates(r)

    ctx = r.context
    assert ctx["obj"].pk == receipt_discrepancy_open_a.pk
    assert ctx["receipt"].pk == receipt_grn_a.pk
    assert ctx["receipt_line"].pk == receipt_grn_line2_a.pk
    assert ctx["order"].pk == receipt_po_a.pk
    assert ctx["vendor"].pk == receipt_vendor_a.pk
    assert "vendor_reference" in ctx["notify_form"].fields
    assert ctx["resolve_form"].initial["remedy"] == receipt_discrepancy_open_a.remedy
    assert "resolution_notes" in ctx["cancel_form"].fields
    assert ctx["tolerance_rule"].pk == receipt_policy_catchall_a.pk
    assert ctx["tolerance_verdict"] == "short"
    assert ctx["tolerance_reason"]
    assert ctx["tolerance_css"] == "badge-amber"
    assert ctx["tolerance_label"] == "Under-receipt"
    assert ctx["evidence_is_image"] is False
    assert ctx["rtv_prefill_url"] == (
        f"{reverse('procurement:rtv_create')}?discrepancy={receipt_discrepancy_open_a.pk}")
    assert ctx["can_edit"] is True
    assert ctx["can_notify"] is True
    assert ctx["can_resolve"] is True
    assert ctx["can_cancel"] is True
    assert ctx["can_raise_rtv"] is True
    assert ctx["can_delete"] is True


def test_receipt_discrepancy_detail_resolved_finding_is_frozen(client_a,
                                                                receipt_discrepancy_resolved_a):
    r = client_a.get(reverse("procurement:discrepancy_detail",
                             args=[receipt_discrepancy_resolved_a.pk]))
    ctx = r.context
    assert ctx["can_edit"] is False
    assert ctx["can_notify"] is False
    assert ctx["can_resolve"] is False
    assert ctx["can_cancel"] is False
    assert ctx["can_raise_rtv"] is False


def test_receipt_discrepancy_detail_header_level_finding_has_no_line(
        client_a, receipt_discrepancy_header_a):
    r = client_a.get(reverse("procurement:discrepancy_detail",
                             args=[receipt_discrepancy_header_a.pk]))
    assert r.status_code == 200
    assert r.context["receipt_line"] is None
    assert r.context["tolerance_verdict"] in {"ok", "no_rule", "early", "late"}


def test_receipt_discrepancy_detail_cross_tenant_is_404(client_a, receipt_discrepancy_b):
    r = client_a.get(reverse("procurement:discrepancy_detail", args=[receipt_discrepancy_b.pk]))
    assert r.status_code == 404


# ------------------------------------------------------------------ discrepancy create


def test_receipt_discrepancy_create_get_context(client_a, receipt_grn_a):
    r = client_a.get(reverse("procurement:discrepancy_create"))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/discrepancy/form.html" in _receipt_templates(r)

    ctx = r.context
    assert ctx["is_edit"] is False
    assert ctx["obj"] is None
    assert receipt_grn_a.pk in [g.pk for g in ctx["receipts"]]
    assert ".pdf" in ctx["allowed_extensions"]
    assert ctx["max_upload_mb"] == 20

    form = ctx["form"]
    assert "goods_receipt" in form.fields
    for hidden in ("tenant", "number", "status", "vendor_notified_on", "resolved_at",
                   "resolved_by", "resolution_notes", "created_by"):
        assert hidden not in form.fields


def test_receipt_discrepancy_create_post_saves_with_request_tenant(client_a, tenant_a,
                                                                    admin_user, receipt_grn_a):
    body = _receipt_discrepancy_post(goods_receipt=str(receipt_grn_a.pk), kind="damaged",
                                     quantity_affected="2")
    r = client_a.post(reverse("procurement:discrepancy_create"), body)
    assert r.status_code == 302

    obj = ReceiptDiscrepancy.objects.get(description="Two cartons crushed in transit.")
    assert obj.tenant_id == tenant_a.pk
    assert obj.created_by_id == admin_user.pk
    assert obj.goods_receipt_id == receipt_grn_a.pk
    assert obj.status == "open"
    assert obj.number.startswith("RDS-")
    assert r.url == reverse("procurement:discrepancy_detail", args=[obj.pk])
    assert _receipt_audit_rows(ReceiptDiscrepancy, obj, "create").exists()


def test_receipt_discrepancy_create_invalid_post_rerenders_without_saving(client_a,
                                                                          receipt_grn_a):
    before = ReceiptDiscrepancy.objects.count()
    r = client_a.post(reverse("procurement:discrepancy_create"),
                      _receipt_discrepancy_post(goods_receipt=str(receipt_grn_a.pk),
                                                description=""))
    assert r.status_code == 200
    assert r.context["form"].errors
    assert ReceiptDiscrepancy.objects.count() == before


def test_receipt_discrepancy_create_prefill_from_exceptions_board(
        client_a, receipt_grn_a, receipt_grn_line_a):
    r = client_a.get(reverse("procurement:discrepancy_create"), {
        "goods_receipt": str(receipt_grn_a.pk),
        "goods_receipt_line": str(receipt_grn_line_a.pk),
        "kind": "over_shipment",
        "quantity_affected": "2",
    })
    assert r.status_code == 200
    initial = r.context["form"].initial
    assert initial["goods_receipt"] == receipt_grn_a.pk
    assert initial["goods_receipt_line"] == receipt_grn_line_a.pk
    assert initial["kind"] == "over_shipment"
    assert initial["quantity_affected"] == Decimal("2")


def test_receipt_discrepancy_create_prefill_drops_foreign_and_unknown_values(
        client_a, receipt_grn_b, receipt_grn_line_b):
    r = client_a.get(reverse("procurement:discrepancy_create"), {
        "goods_receipt": str(receipt_grn_b.pk),
        "goods_receipt_line": str(receipt_grn_line_b.pk),
        "kind": "not_a_kind",
    })
    assert r.status_code == 200
    initial = r.context["form"].initial
    assert "goods_receipt" not in initial
    assert "goods_receipt_line" not in initial
    assert "kind" not in initial


@pytest.mark.parametrize("raw", [
    "NaN", "nan", "Infinity", "-Infinity", "1e400", "abc", "-5", "0",
    "12345678901234567890123456789012", "", "   ",
])
def test_receipt_discrepancy_create_prefill_rejects_bad_numbers(client_a, raw):
    """L35: the hand-parsed ``?quantity_affected=`` must be a 200 with NO prefill, never a 500."""
    r = client_a.get(reverse("procurement:discrepancy_create"), {"quantity_affected": raw})
    assert r.status_code == 200
    assert "quantity_affected" not in r.context["form"].initial


def test_receipt_discrepancy_create_prefill_line_alone_fills_its_receipt(client_a, receipt_grn_a,
                                                                         receipt_grn_line_a):
    r = client_a.get(reverse("procurement:discrepancy_create"),
                     {"goods_receipt_line": str(receipt_grn_line_a.pk)})
    assert r.status_code == 200
    initial = r.context["form"].initial
    assert initial["goods_receipt"] == receipt_grn_a.pk
    assert initial["goods_receipt_line"] == receipt_grn_line_a.pk


def test_receipt_discrepancy_create_rejects_cross_tenant_fk_post(client_a, receipt_grn_b):
    before = ReceiptDiscrepancy.objects.count()
    r = client_a.post(reverse("procurement:discrepancy_create"),
                      _receipt_discrepancy_post(goods_receipt=str(receipt_grn_b.pk)))
    assert r.status_code == 200
    assert r.context["form"].errors
    assert ReceiptDiscrepancy.objects.count() == before


# ------------------------------------------------------------------ discrepancy edit / delete


def test_receipt_discrepancy_edit_get_drops_the_receipt_field(client_a,
                                                               receipt_discrepancy_open_a,
                                                               receipt_grn_a):
    r = client_a.get(reverse("procurement:discrepancy_edit",
                             args=[receipt_discrepancy_open_a.pk]))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/discrepancy/form.html" in _receipt_templates(r)
    assert r.context["is_edit"] is True
    assert r.context["obj"].pk == receipt_discrepancy_open_a.pk
    assert receipt_grn_a.pk in [g.pk for g in r.context["receipts"]]
    assert r.context["max_upload_mb"] == 20
    # re-pointing a saved finding would orphan its receipt line, so the field is popped entirely
    assert "goods_receipt" not in r.context["form"].fields


def test_receipt_discrepancy_edit_post_updates_and_redirects_to_detail(
        client_a, receipt_discrepancy_open_a, receipt_grn_line2_a):
    url = reverse("procurement:discrepancy_edit", args=[receipt_discrepancy_open_a.pk])
    body = _receipt_discrepancy_post(
        goods_receipt_line=str(receipt_grn_line2_a.pk), kind="short_shipment", severity="critical",
        quantity_affected="3", description="Three cartons short after a recount.")
    body.pop("goods_receipt")

    r = client_a.post(url, body)
    assert r.status_code == 302
    assert r.url == reverse("procurement:discrepancy_detail",
                            args=[receipt_discrepancy_open_a.pk])

    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.severity == "critical"
    assert receipt_discrepancy_open_a.quantity_affected == Decimal("3")
    assert receipt_discrepancy_open_a.status == "open"


def test_receipt_discrepancy_edit_refused_once_closed(client_a, receipt_discrepancy_resolved_a):
    url = reverse("procurement:discrepancy_edit", args=[receipt_discrepancy_resolved_a.pk])
    before = receipt_discrepancy_resolved_a.description

    r = client_a.get(url, follow=True)
    assert r.status_code == 200
    assert any("can no longer be edited" in m for m in _receipt_messages(r))

    body = _receipt_discrepancy_post(description="Rewritten after the fact.")
    body.pop("goods_receipt")
    client_a.post(url, body)
    receipt_discrepancy_resolved_a.refresh_from_db()
    assert receipt_discrepancy_resolved_a.description == before


def test_receipt_discrepancy_edit_cross_tenant_is_404(client_a, receipt_discrepancy_b):
    assert client_a.get(reverse("procurement:discrepancy_edit",
                                args=[receipt_discrepancy_b.pk])).status_code == 404


def test_receipt_discrepancy_delete_is_post_only_and_admin_gated(
        client_a, member_client, receipt_discrepancy_header_a):
    url = reverse("procurement:discrepancy_delete", args=[receipt_discrepancy_header_a.pk])

    got = client_a.get(url)
    assert got.status_code == 405
    assert ReceiptDiscrepancy.objects.filter(pk=receipt_discrepancy_header_a.pk).exists()

    assert member_client.post(url).status_code == 403
    assert ReceiptDiscrepancy.objects.filter(pk=receipt_discrepancy_header_a.pk).exists()

    r = client_a.post(url)
    assert r.status_code == 302
    assert r.url == reverse("procurement:discrepancy_list")
    assert not ReceiptDiscrepancy.objects.filter(pk=receipt_discrepancy_header_a.pk).exists()


def test_receipt_discrepancy_delete_cross_tenant_is_404(client_a, receipt_discrepancy_b):
    assert client_a.post(reverse("procurement:discrepancy_delete",
                                 args=[receipt_discrepancy_b.pk])).status_code == 404
    assert ReceiptDiscrepancy.objects.filter(pk=receipt_discrepancy_b.pk).exists()


# ------------------------------------------------------------------ discrepancy workflow POSTs


def test_receipt_discrepancy_notify_vendor_stamps_once(client_a, admin_user,
                                                        receipt_discrepancy_open_a):
    url = reverse("procurement:discrepancy_notify_vendor", args=[receipt_discrepancy_open_a.pk])
    notified_on = _receipt_today() - _receipt_days(1)

    r = client_a.post(url, {"vendor_reference": "SUP-9",
                            "vendor_notified_on": notified_on.strftime("%Y-%m-%d")}, follow=True)
    assert r.status_code == 200
    assert any("Supplier notified" in m for m in _receipt_messages(r))

    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "vendor_notified"
    assert receipt_discrepancy_open_a.vendor_notified_on == notified_on
    assert receipt_discrepancy_open_a.vendor_reference == "SUP-9"

    # a double-submit must NOT re-stamp the date the supplier SLA is measured from
    r = client_a.post(url, {"vendor_reference": "", "vendor_notified_on": ""}, follow=True)
    assert any("already been notified" in m for m in _receipt_messages(r))
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.vendor_notified_on == notified_on
    assert receipt_discrepancy_open_a.vendor_reference == "SUP-9"


def test_receipt_discrepancy_notify_vendor_empty_post_uses_today(client_a,
                                                                  receipt_discrepancy_open_a):
    r = client_a.post(reverse("procurement:discrepancy_notify_vendor",
                              args=[receipt_discrepancy_open_a.pk]), {})
    assert r.status_code == 302
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "vendor_notified"
    assert receipt_discrepancy_open_a.vendor_notified_on == _receipt_today()


def test_receipt_discrepancy_notify_vendor_invalid_date_records_nothing(
        client_a, receipt_discrepancy_open_a):
    r = client_a.post(reverse("procurement:discrepancy_notify_vendor",
                              args=[receipt_discrepancy_open_a.pk]),
                      {"vendor_notified_on": "not-a-date"}, follow=True)
    assert r.status_code == 200
    assert any("nothing was recorded" in m for m in _receipt_messages(r))
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "open"
    assert receipt_discrepancy_open_a.vendor_notified_on is None


def test_receipt_discrepancy_resolve_requires_remedy_and_notes(client_a,
                                                                receipt_discrepancy_open_a):
    url = reverse("procurement:discrepancy_resolve", args=[receipt_discrepancy_open_a.pk])

    r = client_a.post(url, {"remedy": "", "resolution_notes": ""}, follow=True)
    assert any("was not closed" in m for m in _receipt_messages(r))
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "open"

    r = client_a.post(url, {"remedy": "replacement",
                            "resolution_notes": "Supplier is re-sending the pallet."}, follow=True)
    assert any("resolved" in m.lower() for m in _receipt_messages(r))
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "resolved"
    assert receipt_discrepancy_open_a.remedy == "replacement"
    assert receipt_discrepancy_open_a.resolved_at is not None


def test_receipt_discrepancy_cancel_accepts_an_empty_reason(client_a,
                                                             receipt_discrepancy_header_a):
    r = client_a.post(reverse("procurement:discrepancy_cancel",
                              args=[receipt_discrepancy_header_a.pk]), {}, follow=True)
    assert r.status_code == 200
    receipt_discrepancy_header_a.refresh_from_db()
    assert receipt_discrepancy_header_a.status == "cancelled"


def test_receipt_discrepancy_cancel_refused_once_resolved(client_a,
                                                           receipt_discrepancy_resolved_a):
    r = client_a.post(reverse("procurement:discrepancy_cancel",
                              args=[receipt_discrepancy_resolved_a.pk]),
                      {"resolution_notes": "changed my mind"}, follow=True)
    assert any("cannot be cancelled" in m for m in _receipt_messages(r))
    receipt_discrepancy_resolved_a.refresh_from_db()
    assert receipt_discrepancy_resolved_a.status == "resolved"


@pytest.mark.parametrize("url_name", ["discrepancy_notify_vendor", "discrepancy_resolve",
                                      "discrepancy_cancel"])
def test_receipt_discrepancy_verbs_reject_get(client_a, receipt_discrepancy_open_a, url_name):
    r = client_a.get(reverse(f"procurement:{url_name}", args=[receipt_discrepancy_open_a.pk]))
    assert r.status_code == 405
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "open"


@pytest.mark.parametrize("url_name", ["discrepancy_notify_vendor", "discrepancy_resolve",
                                      "discrepancy_cancel"])
def test_receipt_discrepancy_verbs_cross_tenant_are_404(client_a, receipt_discrepancy_b,
                                                         url_name):
    r = client_a.post(reverse(f"procurement:{url_name}", args=[receipt_discrepancy_b.pk]),
                      {"remedy": "credit", "resolution_notes": "not mine"})
    assert r.status_code == 404
    receipt_discrepancy_b.refresh_from_db()
    assert receipt_discrepancy_b.status == "open"


# ================================================================== return-to-vendor register


def test_receipt_rtv_list_renders_contract_context(
        client_a, receipt_rtv_draft_a, receipt_rtv_line_a, receipt_rtv_authorized_a,
        receipt_rtv_shipped_a, receipt_vendor_a, receipt_po_a):
    r = client_a.get(reverse("procurement:rtv_list"))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/rtv/list.html" in _receipt_templates(r)

    ctx = r.context
    assert len(ctx["object_list"]) == 3
    assert ctx["page_obj"].paginator.count == 3
    assert ctx["q"] == ""
    assert [v for v, _ in ctx["status_choices"]] == ["draft", "authorized", "shipped", "closed",
                                                     "cancelled"]
    assert [v for v, _ in ctx["reason_choices"]] == [
        "damaged", "defective", "wrong_item", "over_shipment", "expired", "not_to_spec", "other"]
    assert [v for v, _ in ctx["remedy_choices"]] == ["credit", "replacement", "repair", "none"]
    assert [v.pk for v in ctx["vendors"]] == [receipt_vendor_a.pk]
    assert [p.pk for p in ctx["purchase_orders"]] == [receipt_po_a.pk]
    assert ctx["stats"] == {"draft": 1, "authorized": 1, "shipped": 1, "closed": 0}

    body = r.content.decode()
    for rtv in (receipt_rtv_draft_a, receipt_rtv_authorized_a, receipt_rtv_shipped_a):
        assert rtv.number in body
    # the derived credit is rendered from the lines, never a stored balance
    assert "75.00" in body


@pytest.mark.parametrize("term_attr", ["number", "supplier_rma_number", "tracking_number"])
def test_receipt_rtv_list_search_matches_each_field(client_a, receipt_rtv_shipped_a,
                                                    receipt_rtv_draft_a, term_attr):
    term = getattr(receipt_rtv_shipped_a, term_attr)
    r = client_a.get(reverse("procurement:rtv_list"), {"q": term})
    assert r.status_code == 200
    assert _receipt_pks(r) == [receipt_rtv_shipped_a.pk]
    assert r.context["q"] == term


def test_receipt_rtv_list_search_matches_vendor_and_order(client_a, receipt_rtv_draft_a,
                                                          receipt_po_a):
    url = reverse("procurement:rtv_list")

    r = client_a.get(url, {"q": "Northwind Forge"})
    assert _receipt_pks(r) == [receipt_rtv_draft_a.pk]

    r = client_a.get(url, {"q": receipt_po_a.number})
    assert _receipt_pks(r) == [receipt_rtv_draft_a.pk]

    r = client_a.get(url, {"q": "no-such-return"})
    assert r.status_code == 200 and _receipt_pks(r) == []


def test_receipt_rtv_list_status_reason_remedy_filters(client_a, receipt_rtv_draft_a,
                                                       receipt_rtv_authorized_a,
                                                       receipt_rtv_shipped_a):
    url = reverse("procurement:rtv_list")

    r = client_a.get(url, {"status": "draft"})
    assert _receipt_pks(r) == [receipt_rtv_draft_a.pk]

    r = client_a.get(url, {"status": "shipped"})
    assert _receipt_pks(r) == [receipt_rtv_shipped_a.pk]

    r = client_a.get(url, {"reason": "defective"})
    assert _receipt_pks(r) == [receipt_rtv_authorized_a.pk]

    r = client_a.get(url, {"remedy": "replacement"})
    assert _receipt_pks(r) == [receipt_rtv_authorized_a.pk]

    r = client_a.get(url, {"remedy": "repair"})
    assert _receipt_pks(r) == []


def test_receipt_rtv_list_vendor_and_po_filters(client_a, receipt_rtv_draft_a,
                                                receipt_rtv_authorized_a, receipt_vendor_a,
                                                receipt_po_a):
    url = reverse("procurement:rtv_list")

    r = client_a.get(url, {"vendor": str(receipt_vendor_a.pk)})
    assert set(_receipt_pks(r)) == {receipt_rtv_draft_a.pk, receipt_rtv_authorized_a.pk}

    r = client_a.get(url, {"po": str(receipt_po_a.pk)})
    assert _receipt_pks(r) == [receipt_rtv_draft_a.pk]

    r = client_a.get(url, {"po": str(receipt_po_a.pk + 9999)})
    assert _receipt_pks(r) == []


@pytest.mark.parametrize("value", _RECEIPT_JUNK_INTS)
def test_receipt_rtv_list_junk_fk_params_never_500(client_a, receipt_rtv_draft_a, value):
    url = reverse("procurement:rtv_list")
    for param in ("vendor", "po"):
        r = client_a.get(url, {param: value})
        assert r.status_code == 200
        assert _receipt_pks(r) == [receipt_rtv_draft_a.pk]


@pytest.mark.parametrize("params", [{"status": "zzz"}, {"reason": "zzz"}, {"remedy": "zzz"}])
def test_receipt_rtv_list_junk_enum_params_never_500(client_a, receipt_rtv_draft_a, params):
    r = client_a.get(reverse("procurement:rtv_list"), params)
    assert r.status_code == 200
    assert _receipt_pks(r) == []


def test_receipt_rtv_list_pagination_page_two_and_past_the_end(client_a, tenant_a,
                                                               receipt_vendor_a):
    _receipt_bulk_rtvs(tenant_a, receipt_vendor_a, 18)
    url = reverse("procurement:rtv_list")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 15
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 3
    assert set(_receipt_pks(first)).isdisjoint(_receipt_pks(second))

    past = client_a.get(url, {"page": "999"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2

    junk = client_a.get(url, {"page": "abc"})
    assert junk.status_code == 200 and junk.context["page_obj"].number == 1


def test_receipt_rtv_list_query_count_is_bounded(client_a, tenant_a, receipt_vendor_a,
                                                 django_assert_max_num_queries):
    # 15 rows, each carrying the rma_duplicate_flag Exists annotation, a prefetched line set and
    # a chained ReturnToVendor.__str__ -> vendor hop.
    _receipt_bulk_rtvs(tenant_a, receipt_vendor_a, 15)
    with django_assert_max_num_queries(20):
        r = client_a.get(reverse("procurement:rtv_list"))
        assert r.status_code == 200
        assert len(r.context["object_list"]) == 15
        r.content.decode()


def test_receipt_rtv_list_never_shows_other_tenant_rows(client_a, receipt_rtv_draft_a,
                                                        receipt_rtv_b):
    r = client_a.get(reverse("procurement:rtv_list"))
    pks = _receipt_pks(r)
    assert receipt_rtv_draft_a.pk in pks
    assert receipt_rtv_b.pk not in pks
    assert reverse("procurement:rtv_detail", args=[receipt_rtv_b.pk]) not in r.content.decode()


# ------------------------------------------------------------------ RTV detail


def test_receipt_rtv_detail_renders_contract_context(client_a, receipt_rtv_draft_a,
                                                     receipt_rtv_line_a, receipt_vendor_a,
                                                     receipt_po_a, receipt_grn_a):
    r = client_a.get(reverse("procurement:rtv_detail", args=[receipt_rtv_draft_a.pk]))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/rtv/detail.html" in _receipt_templates(r)

    ctx = r.context
    assert ctx["obj"].pk == receipt_rtv_draft_a.pk
    assert [line.pk for line in ctx["lines"]] == [receipt_rtv_line_a.pk]
    assert len(ctx["line_rows"]) == 1
    row = ctx["line_rows"][0]
    assert row["quantity"] == Decimal("3")
    assert row["unit_price"] == Decimal("25.00")
    assert row["expected_credit"] == Decimal("75.00")
    assert ctx["expected_credit_value"] == Decimal("75.00")
    assert ctx["vendor"].pk == receipt_vendor_a.pk
    assert ctx["order"].pk == receipt_po_a.pk
    assert ctx["receipt"].pk == receipt_grn_a.pk
    assert ctx["discrepancy"] is None
    assert "carrier_name" in ctx["ship_form"].fields
    assert "credit_note_ref" in ctx["close_form"].fields
    assert "cancellation_reason" in ctx["cancel_form"].fields
    assert ctx["has_duplicate_rma"] is False
    assert "posts no stock movement" in ctx["non_posting_note"]
    assert ctx["can_edit"] is True
    assert ctx["can_authorize"] is True
    assert ctx["can_ship"] is False
    assert ctx["can_close"] is False
    assert ctx["can_cancel"] is True
    assert ctx["can_delete"] is True


def test_receipt_rtv_detail_expected_credit_is_derived_every_read(client_a, receipt_rtv_draft_a,
                                                                  receipt_rtv_line_a):
    url = reverse("procurement:rtv_detail", args=[receipt_rtv_draft_a.pk])
    assert client_a.get(url).context["expected_credit_value"] == Decimal("75.00")

    ReturnToVendorLine.objects.filter(pk=receipt_rtv_line_a.pk).update(
        quantity_returned=Decimal("4"))
    # nothing was saved on the header, and the total still moves
    assert client_a.get(url).context["expected_credit_value"] == Decimal("100.00")


def test_receipt_rtv_detail_gates_follow_the_status(client_a, member_client,
                                                    receipt_rtv_shipped_a):
    ctx = client_a.get(reverse("procurement:rtv_detail",
                               args=[receipt_rtv_shipped_a.pk])).context
    assert ctx["can_edit"] is False
    assert ctx["can_authorize"] is False
    assert ctx["can_ship"] is False
    assert ctx["can_close"] is True
    assert ctx["can_cancel"] is False
    assert ctx["can_delete"] is False

    member = member_client.get(reverse("procurement:rtv_detail",
                                       args=[receipt_rtv_shipped_a.pk])).context
    assert member["can_authorize"] is False and member["can_delete"] is False


def test_receipt_rtv_detail_cross_tenant_is_404(client_a, receipt_rtv_b):
    assert client_a.get(reverse("procurement:rtv_detail",
                                args=[receipt_rtv_b.pk])).status_code == 404


# ------------------------------------------------------------------ RTV create / edit / delete


def test_receipt_rtv_create_get_context(client_a, receipt_vendor_a, receipt_po_a):
    r = client_a.get(reverse("procurement:rtv_create"))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/rtv/form.html" in _receipt_templates(r)

    ctx = r.context
    assert ctx["is_edit"] is False
    assert ctx["obj"] is None
    assert ctx["formset"] is None
    assert ctx["receipt"] is None

    form = ctx["form"]
    assert list(form.fields["vendor"].queryset) == [receipt_vendor_a]
    assert list(form.fields["purchase_order"].queryset) == [receipt_po_a]
    for hidden in ("tenant", "number", "status", "shipped_on", "authorized_by", "authorized_at",
                   "closed_at", "cancelled_at", "cancellation_reason", "created_by"):
        assert hidden not in form.fields


def test_receipt_rtv_create_post_saves_with_request_tenant(client_a, tenant_a, admin_user,
                                                           receipt_vendor_a):
    body = _receipt_rtv_post(vendor=str(receipt_vendor_a.pk), reason="damaged",
                             supplier_rma_number="RMA-NEW-1")
    r = client_a.post(reverse("procurement:rtv_create"), body)
    assert r.status_code == 302

    obj = ReturnToVendor.objects.get(supplier_rma_number="RMA-NEW-1")
    assert obj.tenant_id == tenant_a.pk
    assert obj.created_by_id == admin_user.pk
    assert obj.status == "draft"
    assert obj.number.startswith("RTV-")
    assert r.url == reverse("procurement:rtv_detail", args=[obj.pk])
    assert _receipt_audit_rows(ReturnToVendor, obj, "create").exists()


def test_receipt_rtv_create_prefill_from_a_discrepancy(client_a, receipt_discrepancy_notified_a,
                                                       receipt_grn_a, receipt_po_a,
                                                       receipt_vendor_a):
    r = client_a.get(reverse("procurement:rtv_create"),
                     {"discrepancy": str(receipt_discrepancy_notified_a.pk)})
    assert r.status_code == 200
    initial = r.context["form"].initial
    assert initial["discrepancy"] == receipt_discrepancy_notified_a.pk
    # kind "damaged" maps onto reason "damaged"
    assert initial["reason"] == "damaged"
    assert initial["goods_receipt"] == receipt_grn_a.pk
    assert initial["purchase_order"] == receipt_po_a.pk
    assert initial["vendor"] == receipt_vendor_a.pk


def test_receipt_rtv_create_prefill_skips_reason_for_a_short_shipment(
        client_a, receipt_discrepancy_open_a):
    r = client_a.get(reverse("procurement:rtv_create"),
                     {"discrepancy": str(receipt_discrepancy_open_a.pk)})
    assert r.status_code == 200
    initial = r.context["form"].initial
    assert initial["discrepancy"] == receipt_discrepancy_open_a.pk
    assert "reason" not in initial


@pytest.mark.parametrize("raw", ["abc", "999999999999999999999", "0", "-4"])
def test_receipt_rtv_create_prefill_ignores_junk_discrepancy(client_a, raw):
    r = client_a.get(reverse("procurement:rtv_create"), {"discrepancy": raw})
    assert r.status_code == 200
    assert r.context["form"].initial == {}


def test_receipt_rtv_create_prefill_ignores_a_foreign_discrepancy(client_a,
                                                                  receipt_discrepancy_b):
    r = client_a.get(reverse("procurement:rtv_create"),
                     {"discrepancy": str(receipt_discrepancy_b.pk)})
    assert r.status_code == 200
    assert r.context["form"].initial == {}


def test_receipt_rtv_create_rejects_cross_tenant_vendor_post(client_a, receipt_vendor_b):
    before = ReturnToVendor.objects.count()
    r = client_a.post(reverse("procurement:rtv_create"),
                      _receipt_rtv_post(vendor=str(receipt_vendor_b.pk)))
    assert r.status_code == 200
    assert r.context["form"].errors
    assert ReturnToVendor.objects.count() == before


def test_receipt_rtv_edit_get_context_carries_the_line_formset(client_a, receipt_rtv_draft_a,
                                                               receipt_rtv_line_a,
                                                               receipt_grn_a):
    r = client_a.get(reverse("procurement:rtv_edit", args=[receipt_rtv_draft_a.pk]))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/rtv/form.html" in _receipt_templates(r)

    ctx = r.context
    assert ctx["is_edit"] is True
    assert ctx["obj"].pk == receipt_rtv_draft_a.pk
    assert ctx["receipt"].pk == receipt_grn_a.pk
    formset = ctx["formset"]
    assert formset.prefix == "lines"
    # one saved row plus the two extras
    assert len(formset.forms) == 3
    assert formset.forms[0].instance.pk == receipt_rtv_line_a.pk


def test_receipt_rtv_edit_post_saves_header_and_lines(client_a, receipt_rtv_draft_a,
                                                      receipt_vendor_a, receipt_po_a,
                                                      receipt_grn_a, receipt_po_line_a):
    body = _receipt_rtv_post(vendor=str(receipt_vendor_a.pk),
                             purchase_order=str(receipt_po_a.pk),
                             goods_receipt=str(receipt_grn_a.pk),
                             reason="damaged", remedy="credit",
                             supplier_rma_number="RMA-77", notes="Two crushed cartons.")
    body.update(_receipt_line_management(total=1, initial=0))
    body.update(_receipt_line_post(0, po_line=str(receipt_po_line_a.pk),
                                   quantity_returned="2"))

    r = client_a.post(reverse("procurement:rtv_edit", args=[receipt_rtv_draft_a.pk]), body)
    assert r.status_code == 302
    assert r.url == reverse("procurement:rtv_detail", args=[receipt_rtv_draft_a.pk])

    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.notes == "Two crushed cartons."
    assert receipt_rtv_draft_a.lines.count() == 1
    line = receipt_rtv_draft_a.lines.first()
    assert line.quantity_returned == Decimal("2")
    assert line.po_line_id == receipt_po_line_a.pk
    assert receipt_rtv_draft_a.expected_credit_value == Decimal("50.00")

    audit = _receipt_audit_rows(ReturnToVendor, receipt_rtv_draft_a, "update").first()
    assert audit is not None and audit.changes.get("lines") == 1


def test_receipt_rtv_edit_rejects_a_cross_tenant_line(client_a, receipt_rtv_draft_a,
                                                      receipt_vendor_a, receipt_po_a,
                                                      receipt_grn_a, receipt_po_line_b):
    body = _receipt_rtv_post(vendor=str(receipt_vendor_a.pk),
                             purchase_order=str(receipt_po_a.pk),
                             goods_receipt=str(receipt_grn_a.pk))
    body.update(_receipt_line_management(total=1, initial=0))
    body.update(_receipt_line_post(0, po_line=str(receipt_po_line_b.pk),
                                   quantity_returned="1"))

    r = client_a.post(reverse("procurement:rtv_edit", args=[receipt_rtv_draft_a.pk]), body)
    assert r.status_code == 200
    assert r.context["formset"].errors[0]
    assert receipt_rtv_draft_a.lines.count() == 0


def test_receipt_rtv_edit_refused_once_authorized(client_a, receipt_rtv_authorized_a,
                                                  receipt_vendor_a):
    url = reverse("procurement:rtv_edit", args=[receipt_rtv_authorized_a.pk])

    r = client_a.get(url, follow=True)
    assert r.status_code == 200
    assert any("can no longer be edited" in m for m in _receipt_messages(r))

    body = _receipt_rtv_post(vendor=str(receipt_vendor_a.pk), notes="sneaky rewrite")
    body.update(_receipt_line_management(total=0, initial=0))
    client_a.post(url, body)
    receipt_rtv_authorized_a.refresh_from_db()
    assert receipt_rtv_authorized_a.notes != "sneaky rewrite"


def test_receipt_rtv_edit_cross_tenant_is_404(client_a, receipt_rtv_b):
    assert client_a.get(reverse("procurement:rtv_edit",
                                args=[receipt_rtv_b.pk])).status_code == 404


def test_receipt_rtv_delete_is_post_only_and_admin_gated(client_a, member_client,
                                                         receipt_rtv_draft_a):
    url = reverse("procurement:rtv_delete", args=[receipt_rtv_draft_a.pk])

    got = client_a.get(url)
    assert got.status_code == 405
    assert ReturnToVendor.objects.filter(pk=receipt_rtv_draft_a.pk).exists()

    assert member_client.post(url).status_code == 403
    assert ReturnToVendor.objects.filter(pk=receipt_rtv_draft_a.pk).exists()

    r = client_a.post(url)
    assert r.status_code == 302
    assert r.url == reverse("procurement:rtv_list")
    assert not ReturnToVendor.objects.filter(pk=receipt_rtv_draft_a.pk).exists()


def test_receipt_rtv_delete_refuses_a_non_draft(client_a, receipt_rtv_authorized_a):
    r = client_a.post(reverse("procurement:rtv_delete", args=[receipt_rtv_authorized_a.pk]),
                      follow=True)
    assert r.status_code == 200
    assert any("Only a draft return can be deleted" in m for m in _receipt_messages(r))
    assert ReturnToVendor.objects.filter(pk=receipt_rtv_authorized_a.pk).exists()


def test_receipt_rtv_delete_cross_tenant_is_404(client_a, receipt_rtv_b):
    assert client_a.post(reverse("procurement:rtv_delete",
                                 args=[receipt_rtv_b.pk])).status_code == 404
    assert ReturnToVendor.objects.filter(pk=receipt_rtv_b.pk).exists()


# ------------------------------------------------------------------ RTV workflow POSTs


def test_receipt_rtv_authorize_is_admin_only_and_idempotent(client_a, member_client, admin_user,
                                                            receipt_rtv_draft_a):
    url = reverse("procurement:rtv_authorize", args=[receipt_rtv_draft_a.pk])

    assert client_a.get(url).status_code == 405
    assert member_client.post(url).status_code == 403
    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "draft"

    r = client_a.post(url, follow=True)
    assert any("authorized" in m.lower() for m in _receipt_messages(r))
    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "authorized"
    assert receipt_rtv_draft_a.authorized_by_id == admin_user.pk
    stamped_at = receipt_rtv_draft_a.authorized_at

    r = client_a.post(url, follow=True)
    assert any("is already" in m for m in _receipt_messages(r))
    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.authorized_at == stamped_at


def test_receipt_rtv_ship_records_the_despatch(client_a, receipt_rtv_authorized_a):
    url = reverse("procurement:rtv_ship", args=[receipt_rtv_authorized_a.pk])
    shipped_on = _receipt_today() - _receipt_days(2)

    assert client_a.get(url).status_code == 405

    r = client_a.post(url, {"carrier_name": "DHL", "tracking_number": "TRK-RTV-9",
                            "shipped_on": shipped_on.strftime("%Y-%m-%d")}, follow=True)
    assert r.status_code == 200
    receipt_rtv_authorized_a.refresh_from_db()
    assert receipt_rtv_authorized_a.status == "shipped"
    assert receipt_rtv_authorized_a.carrier_name == "DHL"
    assert receipt_rtv_authorized_a.tracking_number == "TRK-RTV-9"
    assert receipt_rtv_authorized_a.shipped_on == shipped_on


def test_receipt_rtv_ship_refused_from_a_draft(client_a, receipt_rtv_draft_a):
    r = client_a.post(reverse("procurement:rtv_ship", args=[receipt_rtv_draft_a.pk]),
                      {"carrier_name": "DHL"}, follow=True)
    assert any("only an authorized return can be shipped" in m for m in _receipt_messages(r))
    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "draft"
    assert receipt_rtv_draft_a.carrier_name == ""


def test_receipt_rtv_close_route_records_the_credit_reference(client_a, receipt_rtv_shipped_a):
    url = reverse("procurement:rtv_close", args=[receipt_rtv_shipped_a.pk])
    assert client_a.get(url).status_code == 405

    r = client_a.post(url, {"credit_note_ref": "CN-4411"}, follow=True)
    assert r.status_code == 200
    receipt_rtv_shipped_a.refresh_from_db()
    assert receipt_rtv_shipped_a.status == "closed"
    assert receipt_rtv_shipped_a.credit_note_ref == "CN-4411"

    audit = _receipt_audit_rows(ReturnToVendor, receipt_rtv_shipped_a, "update").first()
    assert audit is not None and "expected_credit" in audit.changes


def test_receipt_rtv_cancel_requires_a_reason(client_a, receipt_rtv_draft_a):
    url = reverse("procurement:rtv_cancel", args=[receipt_rtv_draft_a.pk])

    r = client_a.post(url, {"cancellation_reason": ""}, follow=True)
    assert any("Give a reason when cancelling a return." in m for m in _receipt_messages(r))
    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "draft"

    r = client_a.post(url, {"cancellation_reason": "Supplier collected on site."}, follow=True)
    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "cancelled"
    assert receipt_rtv_draft_a.cancellation_reason == "Supplier collected on site."


def test_receipt_rtv_cancel_refused_once_shipped(client_a, receipt_rtv_shipped_a):
    r = client_a.post(reverse("procurement:rtv_cancel", args=[receipt_rtv_shipped_a.pk]),
                      {"cancellation_reason": "too late"}, follow=True)
    assert any("cannot be cancelled" in m for m in _receipt_messages(r))
    receipt_rtv_shipped_a.refresh_from_db()
    assert receipt_rtv_shipped_a.status == "shipped"


def test_receipt_rtv_lifecycle_writes_no_stock_and_no_ledger(client_a, receipt_rtv_draft_a,
                                                             receipt_rtv_line_a):
    """The 6.12 invariant: a return records the commercial claim only (L36)."""
    from apps.accounting.models import JournalEntry
    from apps.scm.models import StockMove

    moves_before = StockMove.objects.count()
    entries_before = JournalEntry.objects.count()

    client_a.post(reverse("procurement:rtv_authorize", args=[receipt_rtv_draft_a.pk]))
    client_a.post(reverse("procurement:rtv_ship", args=[receipt_rtv_draft_a.pk]),
                  {"carrier_name": "DHL"})
    client_a.post(reverse("procurement:rtv_close", args=[receipt_rtv_draft_a.pk]),
                  {"credit_note_ref": "CN-1"})

    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "closed"
    assert StockMove.objects.count() == moves_before
    assert JournalEntry.objects.count() == entries_before


@pytest.mark.parametrize("url_name", ["rtv_ship", "rtv_close", "rtv_cancel"])
def test_receipt_rtv_verbs_cross_tenant_are_404(client_a, receipt_rtv_b, url_name):
    r = client_a.post(reverse(f"procurement:{url_name}", args=[receipt_rtv_b.pk]),
                      {"cancellation_reason": "not mine"})
    assert r.status_code == 404
    receipt_rtv_b.refresh_from_db()
    assert receipt_rtv_b.status == "draft"


# ================================================================== receiving console


def test_receipt_receiving_console_renders_contract_context(
        client_a, receipt_asn_a, receipt_asn_line_a, receipt_asn_no_reference_a,
        receipt_asn_draft_a, receipt_vendor_a, receipt_po_a, receipt_location_a,
        receipt_policy_catchall_a, receipt_item_a):
    r = client_a.get(reverse("procurement:receiving_console"))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/receiving_console.html" in _receipt_templates(r)

    ctx = r.context
    # the draft notice is never an arrival
    pks = [asn.pk for asn in ctx["object_list"]]
    assert set(pks) == {receipt_asn_a.pk, receipt_asn_no_reference_a.pk}
    assert receipt_asn_draft_a.pk not in pks
    assert ctx["page_obj"].paginator.count == 2
    assert ctx["q"] == ""
    assert ctx["arrival"] == "" and ctx["status"] == ""
    assert [v for v, _ in ctx["status_choices"]] == ["submitted", "in_transit", "delivered"]
    assert [k for k, _ in ctx["arrival_choices"]] == ["today", "overdue", "awaiting"]
    assert [v.pk for v in ctx["vendors"]] == [receipt_vendor_a.pk]
    assert [p.pk for p in ctx["purchase_orders"]] == [receipt_po_a.pk]
    assert [loc.pk for loc in ctx["locations"]] == [receipt_location_a.pk]
    assert ctx["can_mint"] is True
    assert ctx["stats"] == {"awaiting": 0, "arrived_today": 1, "overdue": 1, "booked_7d": 0}

    # rows are POPULATED, and so is each row's line list (L41)
    rows = {row["asn"].pk: row for row in ctx["rows"]}
    assert set(rows) == {receipt_asn_a.pk, receipt_asn_no_reference_a.pk}
    row = rows[receipt_asn_a.pk]
    assert row["order"].pk == receipt_po_a.pk
    assert row["vendor"].pk == receipt_vendor_a.pk
    assert row["is_booked"] is False and row["existing_receipt"] is None
    assert row["tolerance_verdict"] in dict(ReceiptTolerancePolicy.VERDICT_CHOICES)
    assert row["tolerance_css"].startswith("badge-")
    assert row["tolerance_reason"]
    assert len(row["lines"]) == 1
    line = row["lines"][0]
    assert line["asn_line"].pk == receipt_asn_line_a.pk
    assert line["declared"] == Decimal("5")
    assert line["ordered"] == Decimal("10")
    assert line["received"] == Decimal("0")
    assert line["outstanding"] == Decimal("10")
    assert line["sku_hint"] == "BRG-40"
    assert line["lot_number"] == "LOT-A1"
    assert line["verdict"] in dict(ReceiptTolerancePolicy.VERDICT_CHOICES)
    assert line["verdict_label"]

    body = r.content.decode()
    assert receipt_asn_a.number in body
    assert receipt_asn_draft_a.number not in body


def test_receipt_receiving_console_member_is_not_offered_the_mint_button(member_client,
                                                                        receipt_asn_a):
    r = member_client.get(reverse("procurement:receiving_console"))
    assert r.status_code == 200
    assert r.context["can_mint"] is False


def test_receipt_receiving_console_arrival_tabs(client_a, receipt_asn_a,
                                                receipt_asn_no_reference_a):
    url = reverse("procurement:receiving_console")

    r = client_a.get(url, {"arrival": "today"})
    assert [a.pk for a in r.context["object_list"]] == [receipt_asn_a.pk]
    assert r.context["arrival"] == "today"
    assert r.context["page_obj"].paginator.count == 1

    r = client_a.get(url, {"arrival": "overdue"})
    assert [a.pk for a in r.context["object_list"]] == [receipt_asn_no_reference_a.pk]

    r = client_a.get(url, {"arrival": "awaiting"})
    assert list(r.context["object_list"]) == []

    # unknown tab: ignored, echoed back empty, every row still shown
    r = client_a.get(url, {"arrival": "zzz"})
    assert r.status_code == 200
    assert r.context["arrival"] == ""
    assert len(r.context["object_list"]) == 2


def test_receipt_receiving_console_status_and_search_filters(client_a, receipt_asn_a,
                                                             receipt_asn_no_reference_a,
                                                             receipt_asn_draft_a):
    url = reverse("procurement:receiving_console")

    r = client_a.get(url, {"status": "in_transit"})
    assert len(r.context["object_list"]) == 2
    assert r.context["status"] == "in_transit"

    r = client_a.get(url, {"status": "delivered"})
    assert list(r.context["object_list"]) == []

    # a status this board can never show is sanitized away rather than silently emptying it
    r = client_a.get(url, {"status": "draft"})
    assert r.status_code == 200
    assert r.context["status"] == ""
    assert len(r.context["object_list"]) == 2

    r = client_a.get(url, {"q": "NW-DN-7001"})
    assert [a.pk for a in r.context["object_list"]] == [receipt_asn_a.pk]
    assert r.context["q"] == "NW-DN-7001"

    r = client_a.get(url, {"q": "no-such-shipment"})
    assert r.status_code == 200 and list(r.context["object_list"]) == []


def test_receipt_receiving_console_vendor_and_po_filters(client_a, receipt_asn_a,
                                                         receipt_vendor_a, receipt_po_a):
    url = reverse("procurement:receiving_console")

    r = client_a.get(url, {"vendor": str(receipt_vendor_a.pk)})
    assert receipt_asn_a.pk in [a.pk for a in r.context["object_list"]]

    r = client_a.get(url, {"po": str(receipt_po_a.pk)})
    assert receipt_asn_a.pk in [a.pk for a in r.context["object_list"]]

    r = client_a.get(url, {"po": str(receipt_po_a.pk + 9999)})
    assert list(r.context["object_list"]) == []


@pytest.mark.parametrize("value", _RECEIPT_JUNK_INTS)
def test_receipt_receiving_console_junk_fk_params_never_500(client_a, receipt_asn_a, value):
    url = reverse("procurement:receiving_console")
    for param in ("vendor", "po"):
        r = client_a.get(url, {param: value})
        assert r.status_code == 200
        assert receipt_asn_a.pk in [a.pk for a in r.context["object_list"]]


def test_receipt_receiving_console_pagination_page_two_and_past_the_end(
        client_a, tenant_a, receipt_po_a, receipt_po_line_a):
    _receipt_bulk_asns(tenant_a, receipt_po_a, receipt_po_line_a, 34)
    url = reverse("procurement:receiving_console")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 30
    assert first.context["page_obj"].paginator.num_pages == 2
    assert len(first.context["rows"]) == 30

    second = client_a.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 4
    assert len(second.context["rows"]) == 4
    first_pks = {a.pk for a in first.context["object_list"]}
    second_pks = {a.pk for a in second.context["object_list"]}
    assert first_pks.isdisjoint(second_pks)

    past = client_a.get(url, {"page": "999"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2

    junk = client_a.get(url, {"page": "abc"})
    assert junk.status_code == 200 and junk.context["page_obj"].number == 1


def test_receipt_receiving_console_query_count_is_bounded(
        client_a, tenant_a, receipt_po_a, receipt_po_line_a, receipt_item_a,
        receipt_policy_catchall_a, django_assert_max_num_queries):
    # 30 shipments, each with a declared line: the tolerance rules, the QC rules, the SKU map and
    # the received-per-ordered-line aggregate must each be fetched ONCE for the whole page.
    _receipt_bulk_asns(tenant_a, receipt_po_a, receipt_po_line_a, 30)
    with django_assert_max_num_queries(30):
        r = client_a.get(reverse("procurement:receiving_console"))
        assert r.status_code == 200
        assert len(r.context["rows"]) == 30
        r.content.decode()


def test_receipt_receiving_console_never_shows_other_tenant_rows(client_a, receipt_asn_a,
                                                                 receipt_asn_b):
    r = client_a.get(reverse("procurement:receiving_console"))
    pks = [a.pk for a in r.context["object_list"]]
    assert receipt_asn_a.pk in pks
    assert receipt_asn_b.pk not in pks


# ------------------------------------------------------------------ console: book a receipt


def test_receipt_receiving_console_book_creates_a_draft_receipt(
        client_a, tenant_a, admin_user, receipt_asn_a, receipt_asn_line_a, receipt_location_a):
    url = reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk])
    body = {
        "receipt_date": _receipt_today().strftime("%Y-%m-%d"),
        "location": str(receipt_location_a.pk),
        "notes": "Two pallets on the dock.",
        f"qty_{receipt_asn_line_a.pk}": "5",
    }
    r = client_a.post(url, body)
    assert r.status_code == 302

    receipt = GoodsReceiptNote.objects.get(delivery_note_ref="NW-DN-7001")
    assert r.url == reverse("scm:goodsreceipt_detail", args=[receipt.pk])
    assert receipt.tenant_id == tenant_a.pk
    assert receipt.status == "draft"
    assert receipt.received_by_id == admin_user.pk
    assert receipt.location_id == receipt_location_a.pk
    assert receipt.receipt_date == _receipt_today()
    assert receipt.notes == "Two pallets on the dock."
    assert receipt.number.startswith("GRN-")

    lines = list(receipt.lines.all())
    assert len(lines) == 1
    assert lines[0].quantity_received == Decimal("5")
    assert lines[0].po_line_id == receipt_asn_line_a.po_line_id
    assert _receipt_audit_rows(GoodsReceiptNote, receipt, "create").exists()


def test_receipt_receiving_console_book_is_idempotent_on_the_delivery_note(
        client_a, receipt_asn_a, receipt_asn_line_a):
    url = reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk])
    body = {"receipt_date": _receipt_today().strftime("%Y-%m-%d"), "location": "", "notes": "",
            f"qty_{receipt_asn_line_a.pk}": "5"}

    client_a.post(url, body)
    assert GoodsReceiptNote.objects.filter(delivery_note_ref="NW-DN-7001").count() == 1
    minted = GoodsReceiptNote.objects.get(delivery_note_ref="NW-DN-7001")

    second = client_a.post(url, body, follow=True)
    assert second.status_code == 200
    assert any("already covers delivery note" in m for m in _receipt_messages(second))
    assert GoodsReceiptNote.objects.filter(delivery_note_ref="NW-DN-7001").count() == 1
    assert second.redirect_chain[0][0] == reverse("scm:goodsreceipt_detail", args=[minted.pk])


def test_receipt_receiving_console_book_keys_a_blank_reference_on_the_asn_number(
        client_a, receipt_asn_no_reference_a):
    line = receipt_asn_no_reference_a.lines.first()
    url = reverse("procurement:receiving_console_book", args=[receipt_asn_no_reference_a.pk])
    body = {"receipt_date": _receipt_today().strftime("%Y-%m-%d"), "location": "", "notes": "",
            f"qty_{line.pk}": "2"}

    client_a.post(url, body)
    receipt = GoodsReceiptNote.objects.get(delivery_note_ref=receipt_asn_no_reference_a.number)
    assert receipt.lines.count() == 1

    # a re-click must not burn a second GRN number against the same declaration
    client_a.post(url, body)
    assert GoodsReceiptNote.objects.filter(
        delivery_note_ref=receipt_asn_no_reference_a.number).count() == 1


def test_receipt_receiving_console_book_marks_the_row_as_booked(client_a, receipt_asn_a,
                                                                receipt_asn_line_a):
    client_a.post(reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
                  {"receipt_date": _receipt_today().strftime("%Y-%m-%d"), "location": "",
                   "notes": "", f"qty_{receipt_asn_line_a.pk}": "5"})

    r = client_a.get(reverse("procurement:receiving_console"))
    row = next(row for row in r.context["rows"] if row["asn"].pk == receipt_asn_a.pk)
    assert row["is_booked"] is True
    assert row["existing_receipt"].delivery_note_ref == "NW-DN-7001"
    assert r.context["stats"]["booked_7d"] == 1


def test_receipt_receiving_console_book_refuses_an_empty_declaration(client_a, receipt_asn_a,
                                                                    receipt_asn_line_a):
    """A zero total must never mint an empty draft GRN (and burn a GRN number)."""
    before = GoodsReceiptNote.objects.count()
    r = client_a.post(reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
                      {"receipt_date": _receipt_today().strftime("%Y-%m-%d"), "location": "",
                       "notes": "", f"qty_{receipt_asn_line_a.pk}": "0"}, follow=True)
    assert r.status_code == 200
    assert any("Enter a received quantity on at least one line." in m
               for m in _receipt_messages(r))
    assert GoodsReceiptNote.objects.count() == before


@pytest.mark.parametrize("quantity", ["NaN", "Infinity", "-Infinity", "-5", "abc", "1e400",
                                      "123456789012345678901234567890"])
def test_receipt_receiving_console_book_rejects_bad_quantities(client_a, receipt_asn_a,
                                                               receipt_asn_line_a, quantity):
    """L35: every hand-posted figure is a friendly error, never a 500 and never a GRN."""
    before = GoodsReceiptNote.objects.count()
    r = client_a.post(reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
                      {"receipt_date": _receipt_today().strftime("%Y-%m-%d"), "location": "",
                       "notes": "", f"qty_{receipt_asn_line_a.pk}": quantity}, follow=True)
    assert r.status_code == 200
    assert any("Could not book this arrival" in m for m in _receipt_messages(r))
    assert GoodsReceiptNote.objects.count() == before


def test_receipt_receiving_console_book_requires_a_receipt_date(client_a, receipt_asn_a,
                                                                receipt_asn_line_a):
    before = GoodsReceiptNote.objects.count()
    r = client_a.post(reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
                      {"receipt_date": "", "location": "", "notes": "",
                       f"qty_{receipt_asn_line_a.pk}": "5"}, follow=True)
    assert r.status_code == 200
    assert any("receipt_date" in m for m in _receipt_messages(r))
    assert GoodsReceiptNote.objects.count() == before


def test_receipt_receiving_console_book_rejects_a_foreign_location(client_a, receipt_asn_a,
                                                                   receipt_asn_line_a,
                                                                   receipt_location_b):
    """For a ModelChoiceField the queryset IS the authorization boundary."""
    before = GoodsReceiptNote.objects.count()
    r = client_a.post(reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
                      {"receipt_date": _receipt_today().strftime("%Y-%m-%d"),
                       "location": str(receipt_location_b.pk), "notes": "",
                       f"qty_{receipt_asn_line_a.pk}": "5"}, follow=True)
    assert r.status_code == 200
    assert any("location" in m for m in _receipt_messages(r))
    assert GoodsReceiptNote.objects.count() == before


def test_receipt_receiving_console_book_drops_a_crafted_foreign_line_quantity(
        client_a, receipt_asn_a, receipt_asn_line_a, receipt_asn_no_reference_a):
    """``qty_<pk>`` for a line that is not on THIS shipment is a field the form never declares."""
    other_line = receipt_asn_no_reference_a.lines.first()
    r = client_a.post(reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
                      {"receipt_date": _receipt_today().strftime("%Y-%m-%d"), "location": "",
                       "notes": "", f"qty_{receipt_asn_line_a.pk}": "5",
                       f"qty_{other_line.pk}": "99"})
    assert r.status_code == 302
    receipt = GoodsReceiptNote.objects.get(delivery_note_ref="NW-DN-7001")
    assert receipt.lines.count() == 1
    assert receipt.lines.first().quantity_received == Decimal("5")


def test_receipt_receiving_console_book_refuses_a_draft_shipment(client_a, receipt_asn_draft_a):
    before = GoodsReceiptNote.objects.count()
    r = client_a.post(reverse("procurement:receiving_console_book",
                              args=[receipt_asn_draft_a.pk]),
                      {"receipt_date": _receipt_today().strftime("%Y-%m-%d")}, follow=True)
    assert r.status_code == 200
    assert any("only a declared shipment can be booked" in m for m in _receipt_messages(r))
    assert GoodsReceiptNote.objects.count() == before


def test_receipt_receiving_console_book_refuses_a_closed_order(client_a, receipt_asn_a,
                                                               receipt_asn_line_a, receipt_po_a):
    PurchaseOrder.objects.filter(pk=receipt_po_a.pk).update(status="closed")
    before = GoodsReceiptNote.objects.count()
    r = client_a.post(reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
                      {"receipt_date": _receipt_today().strftime("%Y-%m-%d"), "location": "",
                       "notes": "", f"qty_{receipt_asn_line_a.pk}": "5"}, follow=True)
    assert r.status_code == 200
    assert any("reopen it in SCM" in m for m in _receipt_messages(r))
    assert GoodsReceiptNote.objects.count() == before


def test_receipt_receiving_console_book_is_post_only_and_member_visible(
        client_a, member_client, receipt_asn_a, receipt_asn_line_a):
    url = reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk])
    before = GoodsReceiptNote.objects.count()

    assert client_a.get(url).status_code == 405
    assert GoodsReceiptNote.objects.count() == before

    # the BOOK verb is deliberately NOT admin-gated — the clerk on the dock uses it
    r = member_client.post(url, {"receipt_date": _receipt_today().strftime("%Y-%m-%d"),
                                 "location": "", "notes": "",
                                 f"qty_{receipt_asn_line_a.pk}": "5"})
    assert r.status_code == 302
    assert GoodsReceiptNote.objects.filter(delivery_note_ref="NW-DN-7001").exists()


def test_receipt_receiving_console_book_cross_tenant_is_404(client_a, receipt_asn_b):
    before = GoodsReceiptNote.objects.count()
    r = client_a.post(reverse("procurement:receiving_console_book", args=[receipt_asn_b.pk]),
                      {"receipt_date": _receipt_today().strftime("%Y-%m-%d")})
    assert r.status_code == 404
    assert GoodsReceiptNote.objects.count() == before


# ------------------------------------------------------------------ console: mint declared lots


def test_receipt_receiving_console_mint_lots_creates_then_adopts(client_a, tenant_a,
                                                                 receipt_asn_a,
                                                                 receipt_asn_line_a,
                                                                 receipt_item_a):
    url = reverse("procurement:receiving_console_mint_lots", args=[receipt_asn_a.pk])

    r = client_a.post(url, follow=True)
    assert r.status_code == 200
    assert r.redirect_chain[0][0] == reverse("procurement:receiving_console")
    lot = LotSerial.objects.get(tenant=tenant_a, item=receipt_item_a, number="LOT-A1")
    assert lot.kind == "lot"

    again = client_a.post(url, follow=True)
    assert any("already existed" in m for m in _receipt_messages(again))
    assert LotSerial.objects.filter(tenant=tenant_a, number="LOT-A1").count() == 1


def test_receipt_receiving_console_mint_lots_reports_an_unmatched_sku(client_a, receipt_asn_a,
                                                                     receipt_asn_line_a):
    # no Item carries SKU BRG-40 in this test, so the line is REPORTED, never fatal
    r = client_a.post(reverse("procurement:receiving_console_mint_lots",
                              args=[receipt_asn_a.pk]), follow=True)
    assert r.status_code == 200
    assert any("No item matches the SKU on" in m for m in _receipt_messages(r))
    assert LotSerial.objects.count() == 0


def test_receipt_receiving_console_mint_lots_says_so_when_nothing_is_declared(
        client_a, receipt_asn_no_reference_a):
    r = client_a.post(reverse("procurement:receiving_console_mint_lots",
                              args=[receipt_asn_no_reference_a.pk]), follow=True)
    assert r.status_code == 200
    assert any("declares no lot or serial numbers to mint" in m for m in _receipt_messages(r))
    assert LotSerial.objects.count() == 0


def test_receipt_receiving_console_mint_lots_gates(client_a, member_client, receipt_asn_a,
                                                   receipt_asn_line_a, receipt_asn_b):
    url = reverse("procurement:receiving_console_mint_lots", args=[receipt_asn_a.pk])
    assert client_a.get(url).status_code == 405
    assert member_client.post(url).status_code == 403
    assert LotSerial.objects.count() == 0

    assert client_a.post(reverse("procurement:receiving_console_mint_lots",
                                 args=[receipt_asn_b.pk])).status_code == 404


# ================================================================== tolerance exceptions board


def test_receipt_tolerance_exceptions_renders_contract_context(
        client_a, receipt_grn_line_a, receipt_grn_line2_a, receipt_grn_early_a,
        receipt_grn_late_a, receipt_grn_cancelled_a, receipt_vendor_a, receipt_po_a):
    r = client_a.get(reverse("procurement:tolerance_exceptions"))
    assert r.status_code == 200
    assert ("procurement/goodsreceiptinspection/tolerance_exceptions.html"
            in _receipt_templates(r))

    ctx = r.context
    assert ctx["q"] == ""
    assert ctx["bucket"] == "over"          # DEFAULT_BUCKET
    assert [k for k, _ in ctx["bucket_choices"]] == ["over", "short", "early", "late"]
    assert [v.pk for v in ctx["vendors"]] == [receipt_vendor_a.pk]
    assert ctx["stats"] == {"over": 2, "short": 2, "early": 1, "late": 1, "no_policy": 4}
    assert ctx["page_obj"].paginator.count == 2

    rows = ctx["rows"]
    assert len(rows) == 2
    row = next(row for row in rows if row["receipt_line"].pk == receipt_grn_line_a.pk)
    assert row["order"].pk == receipt_po_a.pk
    assert row["vendor"].pk == receipt_vendor_a.pk
    assert row["ordered"] == Decimal("10")
    assert row["received"] == Decimal("12")     # cumulative across live receipts
    assert row["rejected"] == Decimal("1")
    assert row["sku_hint"] == "BRG-40"
    assert row["description"] == "Bearing housing 40mm"
    assert row["rule"] is None                  # nothing configured in this test
    assert row["verdict"] == "no_rule"
    assert row["verdict_label"] == "No policy"
    assert row["reason"]
    assert row["receipt_date"] == _receipt_today()
    assert row["expected_date"] == _receipt_today()
    assert row["prefill_url"].startswith(reverse("procurement:discrepancy_create"))
    assert f"goods_receipt_line={receipt_grn_line_a.pk}" in row["prefill_url"]


def test_receipt_tolerance_exceptions_each_bucket_narrows_in_the_orm(
        client_a, receipt_grn_line_a, receipt_grn_line2_a, receipt_grn_early_a,
        receipt_grn_late_a):
    url = reverse("procurement:tolerance_exceptions")
    early_line = GoodsReceiptLine.objects.get(goods_receipt=receipt_grn_early_a)
    late_line = GoodsReceiptLine.objects.get(goods_receipt=receipt_grn_late_a)

    r = client_a.get(url, {"bucket": "over"})
    assert set(_receipt_pks(r)) == {receipt_grn_line_a.pk, early_line.pk}
    assert r.context["page_obj"].paginator.count == 2

    r = client_a.get(url, {"bucket": "short"})
    assert set(_receipt_pks(r)) == {receipt_grn_line2_a.pk, late_line.pk}

    r = client_a.get(url, {"bucket": "early"})
    assert _receipt_pks(r) == [early_line.pk]
    assert r.context["bucket"] == "early"

    r = client_a.get(url, {"bucket": "late"})
    assert _receipt_pks(r) == [late_line.pk]


@pytest.mark.parametrize("raw", ["zzz", "", "OVER", "1", "over "])
def test_receipt_tolerance_exceptions_unknown_bucket_falls_back_to_over(client_a,
                                                                       receipt_grn_line_a, raw):
    r = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": raw})
    assert r.status_code == 200
    assert r.context["bucket"] in {"over", raw.strip()}
    assert receipt_grn_line_a.pk in _receipt_pks(r)


def test_receipt_tolerance_exceptions_excludes_cancelled_receipts(client_a, receipt_grn_line_a,
                                                                  receipt_grn_cancelled_a):
    cancelled_line = GoodsReceiptLine.objects.get(goods_receipt=receipt_grn_cancelled_a)
    for bucket in ("over", "short", "early", "late"):
        r = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": bucket})
        assert r.status_code == 200
        assert cancelled_line.pk not in _receipt_pks(r)
    # and its 5 units never count towards the cumulative figure either
    r = client_a.get(reverse("procurement:tolerance_exceptions"))
    row = next(row for row in r.context["rows"] if row["receipt_line"].pk == receipt_grn_line_a.pk)
    assert row["received"] == Decimal("12")


def test_receipt_tolerance_exceptions_verdict_follows_the_governing_policy(
        client_a, receipt_grn_line_a, receipt_policy_catchall_a):
    r = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": "over"})
    row = next(row for row in r.context["rows"] if row["receipt_line"].pk == receipt_grn_line_a.pk)
    assert row["rule"].pk == receipt_policy_catchall_a.pk
    assert row["verdict"] == "over"
    assert row["verdict_css"] == "badge-amber"
    assert row["verdict_label"] == "Over-receipt"
    assert r.context["stats"]["no_policy"] == 0


def test_receipt_tolerance_exceptions_search_and_vendor_filters(client_a, receipt_grn_line_a,
                                                                receipt_grn_a, receipt_vendor_a):
    url = reverse("procurement:tolerance_exceptions")

    r = client_a.get(url, {"q": receipt_grn_a.number})
    assert _receipt_pks(r) == [receipt_grn_line_a.pk]
    assert r.context["q"] == receipt_grn_a.number

    r = client_a.get(url, {"q": "BRG-40"})
    assert _receipt_pks(r) == [receipt_grn_line_a.pk]

    r = client_a.get(url, {"q": "no-such-line"})
    assert r.status_code == 200 and _receipt_pks(r) == []

    r = client_a.get(url, {"vendor": str(receipt_vendor_a.pk)})
    assert _receipt_pks(r) == [receipt_grn_line_a.pk]


@pytest.mark.parametrize("value", _RECEIPT_JUNK_INTS)
def test_receipt_tolerance_exceptions_junk_vendor_never_500(client_a, receipt_grn_line_a, value):
    r = client_a.get(reverse("procurement:tolerance_exceptions"), {"vendor": value})
    assert r.status_code == 200
    assert _receipt_pks(r) == [receipt_grn_line_a.pk]


def test_receipt_tolerance_exceptions_pagination_page_two_and_past_the_end(client_a, tenant_a,
                                                                          receipt_vendor_a):
    _receipt_bulk_over_lines(tenant_a, receipt_vendor_a, 34)
    url = reverse("procurement:tolerance_exceptions")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 30
    assert first.context["page_obj"].paginator.num_pages == 2
    assert len(first.context["rows"]) == 30

    second = client_a.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 4
    assert len(second.context["rows"]) == 4
    assert set(_receipt_pks(first)).isdisjoint(_receipt_pks(second))

    past = client_a.get(url, {"page": "999"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2

    junk = client_a.get(url, {"page": "abc"})
    assert junk.status_code == 200 and junk.context["page_obj"].number == 1


def test_receipt_tolerance_exceptions_query_count_is_bounded(client_a, tenant_a,
                                                             receipt_vendor_a,
                                                             receipt_policy_catchall_a,
                                                             django_assert_max_num_queries):
    _receipt_bulk_over_lines(tenant_a, receipt_vendor_a, 30)
    with django_assert_max_num_queries(30):
        r = client_a.get(reverse("procurement:tolerance_exceptions"))
        assert r.status_code == 200
        assert len(r.context["rows"]) == 30
        r.content.decode()


def test_receipt_tolerance_exceptions_never_shows_other_tenant_rows(client_a,
                                                                    receipt_grn_line_a,
                                                                    receipt_grn_line_b):
    r = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": "short"})
    assert receipt_grn_line_b.pk not in _receipt_pks(r)
    r = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": "over"})
    assert receipt_grn_line_b.pk not in _receipt_pks(r)


# ================================================================== receipt audit trail


def _receipt_seed_audit(tenant, grn, discrepancy, other_grn):
    ct_grn = ContentType.objects.get_for_model(GoodsReceiptNote)
    ct_discrepancy = ContentType.objects.get_for_model(ReceiptDiscrepancy)
    own = AuditLog.objects.create(tenant=tenant, content_type=ct_grn, object_id=grn.pk,
                                  target=grn.number, action="create")
    child = AuditLog.objects.create(tenant=tenant, content_type=ct_discrepancy,
                                    object_id=discrepancy.pk, target=discrepancy.number,
                                    action="update")
    unrelated = AuditLog.objects.create(tenant=tenant, content_type=ct_grn,
                                        object_id=other_grn.pk, target=other_grn.number,
                                        action="delete")
    return own, child, unrelated


def test_receipt_audit_renders_contract_context(client_a, tenant_a, receipt_grn_a,
                                                receipt_discrepancy_open_a, receipt_grn_early_a):
    own, child, unrelated = _receipt_seed_audit(tenant_a, receipt_grn_a,
                                                receipt_discrepancy_open_a, receipt_grn_early_a)
    r = client_a.get(reverse("procurement:receipt_audit"))
    assert r.status_code == 200
    assert "procurement/goodsreceiptinspection/receipt_audit.html" in _receipt_templates(r)

    ctx = r.context
    assert set(_receipt_pks(r)) == {own.pk, child.pk, unrelated.pk}
    assert [e.pk for e in ctx["entries"]] == _receipt_pks(r)
    assert ctx["page_obj"].paginator.count == 3
    assert ctx["q"] == ""
    assert ctx["grn"] is None
    assert ctx["action"] == ""
    assert [v for v, _ in ctx["action_choices"]] == ["create", "update", "delete"]
    assert receipt_grn_a.pk in [g.pk for g in ctx["receipts"]]
    assert ctx["stats"] == {"total": 3, "creates": 1, "updates": 1, "deletes": 1}
    assert "append-only audit trail" in ctx["feed_note"]


def test_receipt_audit_grn_filter_widens_to_the_receipts_consequences(
        client_a, tenant_a, receipt_grn_a, receipt_discrepancy_open_a, receipt_grn_early_a):
    own, child, unrelated = _receipt_seed_audit(tenant_a, receipt_grn_a,
                                                receipt_discrepancy_open_a, receipt_grn_early_a)
    r = client_a.get(reverse("procurement:receipt_audit"), {"grn": str(receipt_grn_a.pk)})
    assert r.status_code == 200
    assert r.context["grn"].pk == receipt_grn_a.pk
    assert set(_receipt_pks(r)) == {own.pk, child.pk}
    assert unrelated.pk not in _receipt_pks(r)
    # the tiles stay whole-workspace
    assert r.context["stats"]["total"] == 3


@pytest.mark.parametrize("value", _RECEIPT_JUNK_INTS)
def test_receipt_audit_junk_grn_narrows_nothing(client_a, tenant_a, receipt_grn_a,
                                                receipt_discrepancy_open_a, receipt_grn_early_a,
                                                value):
    _receipt_seed_audit(tenant_a, receipt_grn_a, receipt_discrepancy_open_a, receipt_grn_early_a)
    r = client_a.get(reverse("procurement:receipt_audit"), {"grn": value})
    assert r.status_code == 200
    assert r.context["grn"] is None
    assert len(_receipt_pks(r)) == 3


def test_receipt_audit_foreign_grn_narrows_nothing(client_a, tenant_a, receipt_grn_a,
                                                   receipt_discrepancy_open_a,
                                                   receipt_grn_early_a, receipt_grn_b):
    _receipt_seed_audit(tenant_a, receipt_grn_a, receipt_discrepancy_open_a, receipt_grn_early_a)
    r = client_a.get(reverse("procurement:receipt_audit"), {"grn": str(receipt_grn_b.pk)})
    assert r.status_code == 200
    assert r.context["grn"] is None
    assert len(_receipt_pks(r)) == 3


def test_receipt_audit_action_and_search_filters(client_a, tenant_a, receipt_grn_a,
                                                 receipt_discrepancy_open_a,
                                                 receipt_grn_early_a):
    own, child, unrelated = _receipt_seed_audit(tenant_a, receipt_grn_a,
                                                receipt_discrepancy_open_a, receipt_grn_early_a)
    url = reverse("procurement:receipt_audit")

    r = client_a.get(url, {"action": "create"})
    assert _receipt_pks(r) == [own.pk]
    assert r.context["action"] == "create"

    r = client_a.get(url, {"action": "delete"})
    assert _receipt_pks(r) == [unrelated.pk]

    # a junk token narrows nothing rather than rendering an empty page under an "All" select
    r = client_a.get(url, {"action": "zzz"})
    assert r.status_code == 200
    assert r.context["action"] == ""
    assert len(_receipt_pks(r)) == 3

    r = client_a.get(url, {"q": receipt_discrepancy_open_a.number})
    assert _receipt_pks(r) == [child.pk]

    r = client_a.get(url, {"q": "no-such-target"})
    assert r.status_code == 200 and _receipt_pks(r) == []


def test_receipt_audit_pagination_page_two_and_past_the_end(client_a, tenant_a, receipt_grn_a):
    _receipt_bulk_audit(tenant_a, receipt_grn_a, 34)
    url = reverse("procurement:receipt_audit")

    first = client_a.get(url)
    assert len(first.context["object_list"]) == 30
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 4
    assert set(_receipt_pks(first)).isdisjoint(_receipt_pks(second))

    past = client_a.get(url, {"page": "999"})
    assert past.status_code == 200 and past.context["page_obj"].number == 2

    junk = client_a.get(url, {"page": "abc"})
    assert junk.status_code == 200 and junk.context["page_obj"].number == 1


def test_receipt_audit_query_count_is_bounded(client_a, tenant_a, receipt_grn_a, admin_user,
                                              django_assert_max_num_queries):
    rows = _receipt_bulk_audit(tenant_a, receipt_grn_a, 30)
    AuditLog.objects.filter(pk__in=[row.pk for row in rows]).update(user=admin_user)
    with django_assert_max_num_queries(18):
        r = client_a.get(reverse("procurement:receipt_audit"))
        assert r.status_code == 200
        assert len(r.context["entries"]) == 30
        r.content.decode()


def test_receipt_audit_never_shows_other_tenant_rows(client_a, tenant_a, tenant_b, receipt_grn_a,
                                                     receipt_grn_b):
    ct = ContentType.objects.get_for_model(GoodsReceiptNote)
    mine = AuditLog.objects.create(tenant=tenant_a, content_type=ct, object_id=receipt_grn_a.pk,
                                   target=receipt_grn_a.number, action="create")
    theirs = AuditLog.objects.create(tenant=tenant_b, content_type=ct,
                                     object_id=receipt_grn_b.pk, target="Globex receipt",
                                     action="create")
    r = client_a.get(reverse("procurement:receipt_audit"))
    assert _receipt_pks(r) == [mine.pk]
    assert theirs.pk not in _receipt_pks(r)
    assert "Globex receipt" not in r.content.decode()
